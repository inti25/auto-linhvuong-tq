"""Nhiệm vụ Logistics Hậu Cần & Chuyển Quân Giới Liên Thành.

Hỗ trợ 2 chế độ Chuyển Quân Giới (chọn bằng radio trên giao diện):
1. Chuyển bằng Chợ (`market`):
   - Kiểm tra kho quân giới tại Thành xuất phát: `Common.ashx?id=16` (`tid: from_city_id`)
     -> `list`: `[[weapon_id, name, category_mask, count], ...]`.
   - Vận chuyển qua Chợ: `OPT.ashx?id=52` (`dest`, `tid`, `gid`, `gamount`, `times=1`, ...).
     Chỉ hỗ trợ giữa các Thành (`city_id > 0`), giới hạn theo số thương đội rảnh.
2. Chuyển bằng Quân đội (`army` — theo cơ chế `ZFunction.exe` `execute_chuyen_ngua_loop`):
   - Dùng Võ tướng mang quân điều phái qua lại giữa Thành chứa QG (`from_city_id`) và
     Thành nhận QG (`to_city_id`), tận dụng ô 2 & ô 3 của `OPT.ashx?id=56` để rút quân giới
     từ kho nguồn và nhả vào kho đích qua `OPT.ashx?id=50` + `Common.ashx?id=40`.

Ngoài ra còn quản lý:
- An Dân toàn bộ các thành: `City.ashx?id=6` -> `OPT.ashx?id=4` (`lType=1`).
- Nhận thưởng chuyên cần hằng ngày: `OPT.ashx?id=63`.
"""

from dataclasses import dataclass, replace
import threading
from typing import Any, Callable, Iterable, Optional

from ..armament import (
    SCOPE_BOWMAN,
    SCOPE_CAVALRY,
    SCOPE_INFANTRY,
    ArmamentSnapshot,
    fetch_general_armament_state,
    find_general_base,
    set_general_armament,
)
from ..gateway import GatewayClient
from ..roster import Roster
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired
from .crafting import WEAPONS_DATA

# Các quân giới mở rộng xuất hiện trên Server 58+ ngoài 67 loại chế tạo cơ bản.
EXTRA_WEAPONS_DATA: dict[int, tuple[str, str]] = {
    256: ("Long phi hỏa nộ", "Cung nỗ"),
    258: ("Thiên mệnh thần cung", "Cung nỗ"),
    351: ("Long phi chiến giáp", "Khôi giáp"),
    353: ("Thiên mệnh thần giáp", "Khôi giáp"),
    452: ("Long phi thiết kỵ", "Chiến mã"),
    454: ("Thiên mệnh bảo câu", "Chiến mã"),
}

TRANSFER_WEAPONS_DATA: dict[int, tuple[str, str]] = {**WEAPONS_DATA, **EXTRA_WEAPONS_DATA}

TRANSFER_ERROR_MESSAGES: dict[int, str] = {
    4: "Thành gửi và Thành nhận không hợp lệ hoặc trùng nhau",
    40: "Tướng đang bận hoặc đang hành quân",
    42: "Kho Thành xuất phát không đủ quân giới",
    52: "Số lượng thương đội khả dụng không đủ (hoặc Thành chưa xây Chợ)",
    57: "Thành đích đã đầy Võ tướng hoặc chưa xây Điểm tướng đài",
    71: "Tướng đã có lính, bắt buộc có quân giới chính ở ô 1",
    110: "Máy chủ yêu cầu mã xác thực Captcha",
}

_BRANCH_SLOT1_CATEGORY: dict[str, int] = {
    SCOPE_INFANTRY: 4,  # Khôi giáp
    SCOPE_CAVALRY: 8,   # Chiến mã
    SCOPE_BOWMAN: 2,    # Cung nỗ
}

_CATEGORY_TO_PREFERRED_BRANCH: dict[int, str] = {
    4: SCOPE_INFANTRY,
    8: SCOPE_CAVALRY,
    2: SCOPE_BOWMAN,
}


def get_transfer_weapon_name(weapon_id: int) -> str:
    """Lấy tên hiển thị của Quân giới theo mã ID (hỗ trợ cả Server 58)."""
    info = TRANSFER_WEAPONS_DATA.get(int(weapon_id))
    return info[0] if info else f"Quân giới #{weapon_id}"


def get_weapon_category_mask(weapon_id: int) -> int:
    """Suy ra bitmask chủng loại quân giới: 1=Binh khí, 2=Cung, 4=Giáp, 8=Ngựa, 16=Xe."""
    wid = int(weapon_id)
    if 100 <= wid < 200:
        return 1
    if 200 <= wid < 300:
        return 2
    if 300 <= wid < 400:
        return 4
    if 400 <= wid < 500:
        return 8
    if 500 <= wid < 600:
        return 16
    return 0


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _check_captcha_ret(ret: int) -> None:
    if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
        raise CaptchaRequired()


@dataclass
class ArmyTransferOrder:
    from_city_id: int
    to_city_id: int
    army_id: int  # Mã Quân giới (vd: 108, 206, 351, 406, 452, ...)
    amount: int


class LogisticsTask:
    def __init__(
        self,
        gateway: GatewayClient,
        transfer_orders: Optional[list[ArmyTransferOrder]] = None,
        monitored_city_ids: Optional[list[int]] = None,
        auto_comfort: bool = True,
        auto_daily_reward: bool = True,
        notify: Callable[[str], None] = print,
    ):
        self.gateway = gateway
        self.transfer_orders = transfer_orders or []
        self.monitored_city_ids = monitored_city_ids or []
        self.auto_comfort = auto_comfort
        self.auto_daily_reward = auto_daily_reward
        self.notify = notify

    def get_city_weapon_stocks(self, city_id: int) -> list[dict]:
        """Lấy danh sách Quân giới hiện có trong kho Thành qua Common.ashx?id=16."""
        resp = self.gateway.call("Common.ashx", 16, {"tid": str(int(city_id)), "_": ""}) or {}
        ret = _to_int(resp.get("ret"), RET_OK)
        _check_captcha_ret(ret)

        items: list[dict] = []
        for item in resp.get("list", []):
            if isinstance(item, dict):
                wid = _to_int(item.get("gid", item.get("id", 0)))
                count = _to_int(item.get("count", 0))
                cat = _to_int(item.get("type", get_weapon_category_mask(wid)))
                name = str(item.get("name") or get_transfer_weapon_name(wid))
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                wid = _to_int(item[0])
                if len(item) >= 4:
                    # Server 57/58: [weapon_id, raw_name, category_mask, count, ...]
                    cat = _to_int(item[2], get_weapon_category_mask(wid))
                    count = _to_int(item[3])
                else:
                    # Dạng 3 phần tử: [weapon_id, name, count]
                    cat = get_weapon_category_mask(wid)
                    count = _to_int(item[2])
                vn_info = TRANSFER_WEAPONS_DATA.get(wid)
                raw_name = str(item[1] or "").strip()
                name = (
                    f"{vn_info[0]} ({raw_name})"
                    if (vn_info and raw_name)
                    else (vn_info[0] if vn_info else raw_name or f"Quân giới #{wid}")
                )
            else:
                continue
            if wid > 0:
                items.append({
                    "id": wid,
                    "name": name,
                    "category_mask": cat,
                    "count": max(0, count),
                })
        return items

    def get_garrison_troops(self, city_id: int) -> dict[int, int]:
        """Lấy tồn kho Quân giới trong Thành qua Common.ashx?id=16: {weapon_id: count}."""
        return {item["id"]: item["count"] for item in self.get_city_weapon_stocks(city_id)}

    def transfer_army(self, order: ArmyTransferOrder) -> bool:
        """Thực hiện chuyển Quân giới giữa 2 Thành qua Chợ (OPT.ashx?id=52)."""
        if order.from_city_id <= 0 or order.to_city_id <= 0:
            self.notify("⚠️ [Chợ] Chuyển quân giới bằng Chợ chỉ hỗ trợ giữa các Thành (không hỗ trợ Doanh trại).")
            return False
        if order.from_city_id == order.to_city_id:
            self.notify("⚠️ [Chợ] Thành xuất phát và Thành đích phải khác nhau.")
            return False
        if order.army_id <= 0 or order.amount <= 0:
            self.notify("⚠️ [Chợ] Mã quân giới hoặc số lượng không hợp lệ.")
            return False

        wname = get_transfer_weapon_name(order.army_id)
        payload = {
            "dest": str(order.to_city_id),
            "tid": str(order.from_city_id),
            "gid": str(order.army_id),
            "gamount": str(order.amount),
            "times": "1",
            "Food": "0",
            "Wood": "0",
            "Stone": "0",
            "Iron": "0",
            "Money": "0",
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 52, payload) or {}
        ret = _to_int(resp.get("ret"), -1)
        _check_captcha_ret(ret)

        if ret == RET_OK:
            self.notify(
                f"🚚 [Chợ] Đã chuyển {order.amount:,} {wname} (ID {order.army_id}) "
                f"từ Thành {order.from_city_id} → Thành {order.to_city_id}"
            )
            return True
        err_detail = TRANSFER_ERROR_MESSAGES.get(ret, f"Mã lỗi máy chủ {ret}")
        self.notify(
            f"❌ [Chợ] Chuyển {order.amount:,} {wname} (ID {order.army_id}) "
            f"từ Thành {order.from_city_id} → Thành {order.to_city_id} thất bại (ret={ret}): {err_detail}"
        )
        return False

    def comfort_city_if_needed(self, city_id: int) -> bool:
        """Kiểm tra và An Dân nếu sĩ khí thành tụt xuống dưới 90%."""
        resp = self.gateway.call("City.ashx", 6, {"tid": str(city_id), "_": ""}) or {}
        ret = _to_int(resp.get("ret"), RET_OK)
        _check_captcha_ret(ret)

        data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
        morale = _to_int(data.get("morale", 100), 100)
        anger = _to_int(data.get("anger", 0), 0)

        if morale < 90 or anger > 0:
            self.notify(f"🕊️ Sĩ khí Thành {city_id} tụt ({morale}%), tiến hành An Dân...")
            c_resp = self.gateway.call("OPT.ashx", 4, {"lType": "1", "tid": str(city_id), "_": ""}) or {}
            return _to_int(c_resp.get("ret"), -1) == RET_OK
        return True

    def claim_daily_reward(self) -> bool:
        """Nhận điểm danh / phần thưởng hằng ngày qua OPT.ashx?id=63."""
        resp = self.gateway.call("OPT.ashx", 63, {"_": ""}) or {}
        ret = _to_int(resp.get("ret"), -1)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            self.notify("⚠️ Nhận thưởng chuyên cần: Máy chủ yêu cầu mã Captcha!")
            raise CaptchaRequired()
        if ret == RET_OK:
            self.notify("🎁 Nhận phần thưởng chuyên cần hằng ngày thành công!")
            return True
        if ret == 86:
            self.notify("ℹ️ Hôm nay bạn đã nhận thưởng chuyên cần rồi (mã 86: đã nhận trong ngày).")
            return True
        self.notify(f"❌ Nhận thưởng chuyên cần thất bại (mã phản hồi từ máy chủ: {ret})")
        return False

    def run_once(self) -> str:
        if self.auto_daily_reward:
            self.claim_daily_reward()

        if self.auto_comfort:
            for cid in self.monitored_city_ids:
                self.comfort_city_if_needed(cid)

        transferred_count = 0
        for order in self.transfer_orders:
            stock = self.get_garrison_troops(order.from_city_id)
            available = stock.get(order.army_id, 0)
            if available < order.amount:
                wname = get_transfer_weapon_name(order.army_id)
                self.notify(
                    f"⏹️ Thành {order.from_city_id} không đủ {wname} (ID {order.army_id}) "
                    f"để chuyển ({available:,}/{order.amount:,}) — dừng lượt chuyển."
                )
                break
            if not self.transfer_army(order):
                break
            transferred_count += 1

        return f"transferred:{transferred_count}" if self.transfer_orders else "logistics_idle"


class ArmyWeaponTransferTask:
    """Chuyển Quân giới bằng Quân đội (Võ tướng điều phái qua lại giữa 2 Thành).

    Quy trình 1 vòng (tương thích ZFunction.exe `execute_chuyen_ngua_loop`, mở rộng cho mọi
    loại quân giới 1xx..4xx và nhiều Võ tướng song song):
    1. Kiểm tra tồn kho Quân giới tại Thành nguồn (`from_city_id`).
    2. Với tướng đang đứng tại Thành đích (`to_city_id`): dọn ô 2 & ô 3 về 0 (giữ nguyên ô 1).
    3. Điều phái các tướng tại Thành đích sang Thành nguồn (`OPT.ashx?id=50`), chờ hành quân (`Common.ashx?id=40`).
    4. Tại Thành nguồn: gán Quân giới cần chuyển vào ô 2 & ô 3 (và ô 1 nếu đang trống & hợp loại) qua `OPT.ashx?id=56`.
    5. Điều phái các tướng về lại Thành đích (`OPT.ashx?id=50`), chờ hành quân về.
    6. Tại Thành đích: đặt ô 2 & ô 3 về 0 qua `OPT.ashx?id=56` để nhả toàn bộ Quân giới vào kho đích.
    """

    def __init__(
        self,
        gateway: GatewayClient,
        notify: Callable[[str], None] = print,
    ):
        self.gateway = gateway
        self.notify = notify

    @staticmethod
    def select_carrier_branch(counts: dict[str, int], weapon_id: int) -> Optional[str]:
        """Chọn binh chủng có quân số để mang Quân giới (ưu tiên binh chủng khớp ô 1)."""
        cat = get_weapon_category_mask(weapon_id)
        preferred = _CATEGORY_TO_PREFERRED_BRANCH.get(cat)
        if preferred and counts.get(preferred, 0) > 0:
            return preferred
        best_branch = max((SCOPE_INFANTRY, SCOPE_CAVALRY, SCOPE_BOWMAN), key=lambda b: counts.get(b, 0))
        return best_branch if counts.get(best_branch, 0) > 0 else None

    @staticmethod
    def build_carry_snapshot(
        snap: ArmamentSnapshot, branch: str, weapon_id: int, *, load: bool
    ) -> Optional[ArmamentSnapshot]:
        """Tạo ArmamentSnapshot để nạp (load=True) hoặc nhả (load=False) quân giới ở ô 2 & ô 3."""
        s1, s2, s3 = getattr(snap, branch)
        wid = int(weapon_id)
        if load:
            if s1 > 0:
                new_triple = (s1, wid, wid)
            elif get_weapon_category_mask(wid) == _BRANCH_SLOT1_CATEGORY.get(branch):
                new_triple = (wid, wid, wid)
            else:
                return None
        else:
            if s2 == 0 and s3 == 0:
                return None
            new_triple = (s1, 0, 0)
        if new_triple == (s1, s2, s3):
            return None
        return replace(snap, **{branch: new_triple})

    def dispatch_general(self, general_id: int, from_city_id: int, to_city_id: int) -> tuple[bool, int]:
        """Điều phái Võ tướng giữa 2 Thành qua OPT.ashx?id=50."""
        resp = self.gateway.call(
            "OPT.ashx",
            50,
            {
                "lCityID": str(int(from_city_id)),
                "lGeneralID": str(int(general_id)),
                "lDestID": str(int(to_city_id)),
                "_": "",
            },
        ) or {}
        ret = _to_int(resp.get("ret"), -1)
        _check_captcha_ret(ret)
        return ret == RET_OK, ret

    def get_incoming_move_duration(self, target_city_id: int, general_ids: list[int]) -> int:
        """Lấy thời gian di chuyển còn lại (giây) từ Common.ashx?id=40 (`come`)."""
        resp = self.gateway.call("Common.ashx", 40, {"tid": str(int(target_city_id)), "_": ""}) or {}
        ret = _to_int(resp.get("ret"), RET_OK)
        _check_captcha_ret(ret)

        wanted = {int(g) for g in general_ids if g}
        max_duration = 0
        for entry in resp.get("come") or []:
            if not isinstance(entry, (list, tuple)) or len(entry) < 13:
                continue
            if isinstance(entry[7], (list, tuple)):
                gen_list = entry[7]
                duration = _to_int(entry[12], 0)
            elif len(entry) > 8 and isinstance(entry[8], (list, tuple)):
                gen_list = entry[8]
                dur13 = _to_int(entry[13], -1) if len(entry) > 13 else -1
                duration = dur13 if 0 <= dur13 < 86400 else _to_int(entry[12], 0)
            elif isinstance(entry[12], (list, tuple)):
                gen_list = entry[12]
                duration = _to_int(entry[7], 0)
            else:
                continue
            matched = False
            for g_item in gen_list:
                if isinstance(g_item, (list, tuple)) and len(g_item) >= 2:
                    gid = _to_int(g_item[0], 0) or _to_int(g_item[1], 0)
                elif isinstance(g_item, (list, tuple)) and len(g_item) == 1:
                    gid = _to_int(g_item[0], 0)
                else:
                    gid = _to_int(g_item, 0)
                if gid in wanted:
                    matched = True
                    break
            if matched and duration > max_duration:
                max_duration = duration
        return max_duration

    def _wait_arrival(
        self,
        target_city_id: int,
        general_ids: list[int],
        stop_event: threading.Event,
        status_cb: Optional[Callable[[str], None]] = None,
        direction_label: str = "",
    ) -> bool:
        """Chờ các tướng hoàn tất di chuyển tới Thành đích; trả False nếu bị dừng."""
        if not general_ids:
            return True
        notified_wait = False
        while True:
            if stop_event.is_set():
                return False
            rem = self.get_incoming_move_duration(target_city_id, general_ids)
            if rem <= 0:
                return True
            wait_sec = rem + 2 if not notified_wait else min(rem + 1, 15)
            msg = f"⏳ [Quân đội] Đang hành quân {direction_label}Thành {target_city_id} ({wait_sec}s)..."
            if status_cb:
                status_cb(msg)
            if not notified_wait or rem >= 10:
                self.notify(msg)
                notified_wait = True
            if stop_event.wait(wait_sec):
                return False

    def _set_armament_checked(
        self, general_id: int, gen_name: str, new_snap: ArmamentSnapshot
    ) -> tuple[bool, int]:
        ok, ret = set_general_armament(self.gateway, general_id, new_snap)
        _check_captcha_ret(ret)
        if not ok:
            err = TRANSFER_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")
            self.notify(f"⚠️ [Quân đội] {gen_name}: cập nhật quân giới thất bại (ret={ret}): {err}")
        return ok, ret

    def run(
        self,
        from_city_id: int,
        to_city_id: int,
        weapon_id: int,
        general_ids: list[int],
        roster: Roster,
        *,
        loop: bool = True,
        stop_event: Optional[threading.Event] = None,
        status_cb: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Chạy chuyển Quân giới bằng Quân đội (1 chuyến hoặc lặp vô tận)."""
        stop = stop_event or threading.Event()
        if from_city_id <= 0 or to_city_id <= 0:
            raise ValueError("Chuyển quân giới bằng Quân đội chỉ hỗ trợ giữa các Thành.")
        if from_city_id == to_city_id:
            raise ValueError("Thành chứa Quân giới và Thành nhận phải khác nhau.")
        if weapon_id <= 0 or get_weapon_category_mask(weapon_id) == 16:
            raise ValueError("Vui lòng chọn Quân giới hợp lệ (không hỗ trợ Xe ném đá).")
        clean_gids = [int(g) for g in general_ids if int(g) > 0]
        if not clean_gids:
            raise ValueError("Vui lòng chọn ít nhất 1 Võ tướng để vận chuyển.")

        wname = get_transfer_weapon_name(weapon_id)
        logistics_helper = LogisticsTask(self.gateway, notify=self.notify)
        round_no = 0
        total_transferred = 0
        origin_cities: dict[int, int] = {}
        carrier_names: dict[int, str] = {}

        def _return_carriers_to_origin(g_ids: Iterable[int]) -> None:
            for g in g_ids:
                orig_cid = origin_cities.get(g)
                if not orig_cid or orig_cid == to_city_id:
                    continue
                gname = carrier_names.get(g, f"Tướng #{g}")
                ok_home, ret_home = self.dispatch_general(g, to_city_id, orig_cid)
                if ok_home:
                    self.notify(f"🏠 [Quân đội] Chuyển xong — đã điều {gname} về Thành ban đầu {orig_cid}.")
                else:
                    self.notify(
                        f"⚠️ [Quân đội] Điều {gname} về Thành ban đầu {orig_cid} thất bại (ret={ret_home})."
                    )

        self.notify(
            f"🐎 [Quân đội] Bắt đầu chuyển {wname} (ID {weapon_id}) "
            f"từ Thành {from_city_id} → Thành {to_city_id} bằng {len(clean_gids)} Võ tướng "
            f"({'lặp vô tận' if loop else '1 chuyến'})."
        )

        while not stop.is_set():
            round_no += 1
            if status_cb:
                status_cb(f"Vòng #{round_no}: Kiểm tra kho & tướng...")

            stock = logistics_helper.get_garrison_troops(from_city_id)
            available = stock.get(int(weapon_id), 0)
            if available <= 0:
                self.notify(
                    f"⏹️ [Quân đội] Thành {from_city_id} đã hết {wname} (ID {weapon_id}) — dừng chuyển."
                )
                if total_transferred > 0:
                    _return_carriers_to_origin(clean_gids)
                return f"stopped_out_of_stock:{total_transferred}"

            # Thu thập trạng thái các tướng được chọn
            carriers: list[dict] = []
            for gid in clean_gids:
                if stop.is_set():
                    return f"stopped:{total_transferred}"
                loc = find_general_base(roster, gid)
                cur_base = loc[0] if loc else to_city_id
                g_name = loc[1].name if loc else f"Tướng #{gid}"
                if loc and loc[1].role != "vo":
                    self.notify(f"⚠️ [Quân đội] Bỏ qua {g_name}: không phải Võ tướng.")
                    continue
                snap, counts, owner_cid, ret12 = fetch_general_armament_state(self.gateway, gid, cur_base)
                _check_captcha_ret(ret12)
                if snap is None:
                    self.notify(f"⚠️ [Quân đội] Không đọc được quân giới của {g_name} (ret={ret12}).")
                    continue
                branch = self.select_carrier_branch(counts, weapon_id)
                if branch is None:
                    self.notify(f"⚠️ [Quân đội] Bỏ qua {g_name}: không có lính (Bộ/Kỵ/Cung = 0).")
                    continue
                cur_cid = int(owner_cid or cur_base)
                origin_cities.setdefault(gid, cur_cid)
                carrier_names[gid] = g_name
                carriers.append({
                    "gid": gid,
                    "name": g_name,
                    "snap": snap,
                    "branch": branch,
                    "troops": counts[branch],
                    "city_id": cur_cid,
                })

            if not carriers:
                self.notify("⏹️ [Quân đội] Không có Võ tướng hợp lệ (rảnh & có lính) để vận chuyển.")
                return f"stopped_no_carriers:{total_transferred}"

            # 1. Tướng đang ở Thành đích: dọn ô 2 & ô 3 trước khi đi, rồi điều sang Thành nguồn
            to_dispatch_src: list[dict] = []
            for c in carriers:
                if stop.is_set():
                    return f"stopped:{total_transferred}"
                if c["city_id"] == to_city_id:
                    unload_snap = self.build_carry_snapshot(c["snap"], c["branch"], weapon_id, load=False)
                    if unload_snap is not None:
                        ok, _ = self._set_armament_checked(c["gid"], c["name"], unload_snap)
                        if ok:
                            c["snap"] = unload_snap
                    ok_disp, ret_disp = self.dispatch_general(c["gid"], to_city_id, from_city_id)
                    if ok_disp:
                        to_dispatch_src.append(c)
                    else:
                        self.notify(
                            f"⚠️ [Quân đội] Điều {c['name']} sang Thành {from_city_id} thất bại (ret={ret_disp})."
                        )
                elif c["city_id"] == from_city_id:
                    to_dispatch_src.append(c)
                else:
                    self.notify(
                        f"⚠️ [Quân đội] {c['name']} đang ở Thành {c['city_id']} "
                        f"(khác Thành {from_city_id}/{to_city_id}), bỏ qua."
                    )

            if not to_dispatch_src:
                self.notify("⏹️ [Quân đội] Không điều phái được Võ tướng nào sang Thành nguồn.")
                return f"stopped_dispatch_failed:{total_transferred}"

            going_ids = [c["gid"] for c in to_dispatch_src if c["city_id"] == to_city_id]
            if going_ids:
                if not self._wait_arrival(from_city_id, going_ids, stop, status_cb, "sang "):
                    return f"stopped:{total_transferred}"
                for c in to_dispatch_src:
                    if c["city_id"] == to_city_id:
                        c["city_id"] = from_city_id

            # 2. Tại Thành nguồn: nạp quân giới vào ô 2 & ô 3 và điều về Thành đích
            loaded_carriers: list[dict] = []
            out_of_stock = False
            for c in to_dispatch_src:
                if stop.is_set():
                    return f"stopped:{total_transferred}"
                snap_now, counts_now, owner_now, ret12 = fetch_general_armament_state(
                    self.gateway, c["gid"], from_city_id
                )
                _check_captcha_ret(ret12)
                if snap_now is not None:
                    c["snap"] = snap_now
                    c["troops"] = counts_now.get(c["branch"], c["troops"])
                    if owner_now:
                        c["city_id"] = owner_now
                prev_snap = c["snap"]
                load_snap = self.build_carry_snapshot(c["snap"], c["branch"], weapon_id, load=True)
                did_load = False
                if load_snap is not None:
                    ok_load, ret_load = self._set_armament_checked(c["gid"], c["name"], load_snap)
                    if not ok_load:
                        if ret_load == 42:
                            out_of_stock = True
                        continue
                    c["snap"] = load_snap
                    did_load = True
                else:
                    _, cur_s2, cur_s3 = getattr(c["snap"], c["branch"])
                    if cur_s2 != int(weapon_id) and cur_s3 != int(weapon_id):
                        self.notify(
                            f"⚠️ [Quân đội] {c['name']} ({c['branch']} ô 1 trống) không mang được {wname}, bỏ qua."
                        )
                        continue
                # Điều phái về Thành đích
                ok_ret, ret_code = self.dispatch_general(c["gid"], from_city_id, to_city_id)
                if ok_ret:
                    loaded_carriers.append(c)
                else:
                    err_disp = TRANSFER_ERROR_MESSAGES.get(ret_code, f"Mã lỗi {ret_code}")
                    self.notify(
                        f"⚠️ [Quân đội] Điều {c['name']} sang Thành {to_city_id} thất bại (ret={ret_code}): {err_disp}."
                    )
                    if did_load:
                        ok_rb, _ = set_general_armament(self.gateway, c["gid"], prev_snap)
                        if not ok_rb:
                            un_rb = self.build_carry_snapshot(c["snap"], c["branch"], weapon_id, load=False)
                            if un_rb is not None:
                                ok_rb, _ = set_general_armament(self.gateway, c["gid"], un_rb)
                            if ok_rb and un_rb is not None:
                                c["snap"] = un_rb
                        else:
                            c["snap"] = prev_snap

            if not loaded_carriers:
                if out_of_stock:
                    self.notify(f"⏹️ [Quân đội] Kho Thành {from_city_id} không đủ {wname} — dừng.")
                    return f"stopped_out_of_stock:{total_transferred}"
                self.notify("⏹️ [Quân đội] Không có tướng nào nạp/quay về được Thành đích.")
                return f"stopped_no_carriers:{total_transferred}"

            returning_ids = [c["gid"] for c in loaded_carriers]
            if not self._wait_arrival(to_city_id, returning_ids, stop, status_cb, "về "):
                return f"stopped:{total_transferred}"

            # 3. Tại Thành đích: tháo ô 2 & ô 3 về 0 để nhả quân giới vào kho Thành đích
            round_amount = 0
            for c in loaded_carriers:
                if stop.is_set():
                    return f"stopped:{total_transferred}"
                snap_back, counts_back, _, ret12 = fetch_general_armament_state(
                    self.gateway, c["gid"], to_city_id
                )
                _check_captcha_ret(ret12)
                cur_snap = snap_back or c["snap"]
                cur_troops = counts_back.get(c["branch"], c["troops"]) if snap_back else c["troops"]
                s1, s2, s3 = getattr(cur_snap, c["branch"])
                carried_slots = (1 if s2 == int(weapon_id) else 0) + (1 if s3 == int(weapon_id) else 0)
                unload_snap = self.build_carry_snapshot(cur_snap, c["branch"], weapon_id, load=False)
                if unload_snap is not None:
                    ok_un, _ = self._set_armament_checked(c["gid"], c["name"], unload_snap)
                    if ok_un:
                        round_amount += carried_slots * cur_troops

            total_transferred += round_amount
            msg_done = (
                f"✅ [Quân đội] Vòng #{round_no} hoàn tất: đã nhập ~{round_amount:,} {wname} "
                f"(ID {weapon_id}) về Thành {to_city_id} (tổng {total_transferred:,})."
            )
            self.notify(msg_done)
            if status_cb:
                status_cb(f"Vòng #{round_no} xong (~{total_transferred:,})")

            if out_of_stock:
                _return_carriers_to_origin(c["gid"] for c in loaded_carriers)
                return f"stopped_out_of_stock:{total_transferred}"
            if not loop:
                _return_carriers_to_origin(c["gid"] for c in loaded_carriers)
                break

        return f"completed:{total_transferred}"
