"""Nhiệm vụ Thảo Phạt (chiến dịch dã ngoại / boss).

Reverse engineered từ ZMan.exe:
- Nhiệm vụ: Sơn Tặc, Khăn Vàng, Đổng Trác, Lữ Bố, Quan Độ, Xích Bích, Di Lăng, GM.
- Kiểm tra số tân binh có sẵn: Common.ashx?id=27.
- Chiêu mộ tân binh: OPT.ashx?id=41 (lAmount: số lượng tân binh cần chiêu mộ).
- An dân / Tăng nhân khẩu: OPT.ashx?id=4 (lType: 4).
- Biên chế quân: OPT.ashx?id=6 (lSoldierType 1: bộ, 2: kỵ, 3: cung; lAmount: số lượng +/-).
- Luyện sỹ khí: OPT.ashx?id=47 (lAddPoint: điểm sỹ khí tăng thêm).
- Gửi Thảo Phạt: OPT.ashx?id=62 (taskid, counts, general1..5).
"""

import threading
from dataclasses import dataclass
from typing import Callable, Optional

from ..battle import BattleController
from ..gateway import GatewayClient
from ..roster import Army, fetch_roster
from .base import TaskContext, attack

# Bản đồ nhiệm vụ chuẩn từ ZMan.exe
# travel_time: Thời gian di chuyển 1 chiều (giây). Tổng thời gian khứ hồi = travel_time * 2 + thời gian chiến đấu.
THAOPHAT_MISSIONS = {
    0: {"name": "Sơn Tặc", "travel_time": 300, "max_generals": 3},
    1: {"name": "Khăn Vàng", "travel_time": 450, "max_generals": 3},
    2: {"name": "Đổng Trác", "travel_time": 750, "max_generals": 5},
    3: {"name": "Lữ Bố", "travel_time": 1050, "max_generals": 5},
    4: {"name": "Quan Độ", "travel_time": 1350, "max_generals": 5},
    5: {"name": "Xích Bích", "travel_time": 1800, "max_generals": 5},
    6: {"name": "Di Lăng", "travel_time": 1800, "max_generals": 5},
    28: {"name": "GM", "travel_time": 180, "max_generals": 5},
}

ERROR_MESSAGES = {
    0: "Thành công",
    1: "Thao tác thất bại, vui lòng thử lại sau",
    6: "Quân số không đủ",
    7: "Sỹ khí không đủ",
    8: "Thảo phạt đang trong thời gian chờ",
    20: "Tướng đang không ở trong thành (hoặc đang bận)",
    32: "Tài nguyên không đủ",
    33: "Đồng không đủ",
    34: "Dân số rảnh rỗi không đủ",
    35: "Thành không có tướng khả dụng",
    40: "Tướng đang bận (không ở trong thành)",
    53: "Tân binh không đủ để biên chế",
    55: "Đang trong thời gian chờ an dân",
    78: "Trong thời gian đóng băng không thể xuất binh",
    79: "Tướng đang làm nhiệm vụ / đang đi thảo phạt chưa về",
    10032: "Tướng không có trong thành",
    10033: "Mưu sĩ không tồn tại trong thành",
    10034: "Tướng không tồn tại trong thành",
    10035: "Tướng đang bận",
    10036: "Tướng bị thương",
    10037: "Mưu sĩ đã được gán cho tướng khác",
    10038: "Quân số không đủ",
    10039: "Sỹ khí không đủ",
    10040: "Thảo phạt đang trong thời gian chờ",
}


@dataclass
class TargetArmy:
    infantry: int = 0
    cavalry: int = 0
    archers: int = 0
    bo_binh: Optional[int] = None
    ky_binh: Optional[int] = None
    cung_binh: Optional[int] = None

    def __post_init__(self):
        if self.bo_binh is not None and self.infantry == 0:
            self.infantry = self.bo_binh
        if self.ky_binh is not None and self.cavalry == 0:
            self.cavalry = self.ky_binh
        if self.cung_binh is not None and self.archers == 0:
            self.archers = self.cung_binh



@dataclass
class ThaoPhatResult:
    success: bool
    code: int
    message: str


class ThaoPhatExecutor:
    def __init__(self, gateway: GatewayClient):
        self.gateway = gateway

    def check_recruits(self, city_id: int) -> Optional[int]:
        """
        Kiểm tra số lượng tân binh có sẵn trong kho của thành từ API Common.ashx?id=27.
        Trả về số tân binh (int), hoặc None nếu không lấy được.
        """
        resp = self.gateway.call("Common.ashx", 27, {"_": ""}) or {}
        if resp.get("ret") == 0:
            for city_data in resp.get("list", []):
                if isinstance(city_data, list) and len(city_data) > 2:
                    try:
                        if int(city_data[0]) == int(city_id):
                            return int(city_data[2])
                    except (ValueError, TypeError):
                        continue
        return None

    def comfort_population(self, city_id: int, ltype: int = 4) -> tuple[bool, int]:
        """
        Gọi API an dân / tăng nhân khẩu (OPT.ashx?id=4).
        lType=4: Tăng nhân khẩu.
        Trả về (success, ret_code).
        """
        payload = {
            "lType": str(ltype),
            "tid": str(city_id),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 4, payload) or {}
        ret = resp.get("ret", -1)
        return ret == 0, ret

    def buy_recruits(
        self,
        city_id: int,
        amount: int,
        auto_comfort: bool = True,
    ) -> tuple[bool, int]:
        """
        Chiêu mộ tân binh bằng API OPT.ashx?id=41.
        Nếu thiếu dân rảnh rỗi (ret=34) và auto_comfort=True:
            Tự động gọi an dân (lType=4) tăng nhân khẩu rồi thử lại.
        Trả về (success, ret_code).
        """
        if amount <= 0:
            return True, 0

        payload = {
            "lAmount": str(amount),
            "tid": str(city_id),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 41, payload) or {}
        ret = resp.get("ret", -1)

        if ret == 34 and auto_comfort:
            self.comfort_population(city_id, ltype=4)
            self.gateway._sleep(1.0)
            resp = self.gateway.call("OPT.ashx", 41, payload) or {}
            ret = resp.get("ret", -1)

        return ret == 0, ret

    def adjust_troops(
        self,
        city_id: int,
        general_id: int,
        current_army: Optional[Army],
        target_army: TargetArmy,
        auto_recruit: bool = True,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> list[tuple[int, int, bool, int]]:
        """
        Thiết lập biên chế quân cho tướng bằng API id=6.
        Nếu tân binh không đủ (ret=53) và auto_recruit=True:
            Tự động chiêu mộ tân binh (API id=41) và thử lại biên chế.
        Trả về danh sách [(soldier_type, amount, success, ret_code)]
        """
        current_inf = current_army.infantry if current_army else 0
        current_cav = current_army.cavalry if current_army else 0
        current_arc = current_army.archers if current_army else 0

        adjustments = [
            (1, target_army.infantry - current_inf),
            (2, target_army.cavalry - current_cav),
            (3, target_army.archers - current_arc),
        ]

        results = []
        for soldier_type, diff in adjustments:
            # Chỉ bổ sung quân nếu thiếu (diff > 0), không tháo quân nếu thừa
            if diff <= 0:
                continue
            payload = {
                "lGeneralID": str(general_id),
                "lSoldierType": str(soldier_type),
                "lAmount": str(diff),
                "tid": str(city_id),
                "_": "",
            }
            resp = self.gateway.call("OPT.ashx", 6, payload) or {}
            ret = resp.get("ret", -1)

            # Nếu tân binh không đủ để biên chế (ret=53) và bật tự động chiêu mộ
            if ret == 53 and auto_recruit:
                tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(soldier_type, "Quân")
                if on_log:
                    on_log(f"   [Chiêu mộ] Tân binh không đủ để bổ sung {tname} +{diff}, tự động chiêu mộ...")
                buy_succ, buy_ret = self.buy_recruits(city_id, diff)
                if buy_succ:
                    if on_log:
                        on_log(f"   [Chiêu mộ] ✅ Chiêu mộ thành công {diff} tân binh, tiếp tục biên chế...")
                    resp = self.gateway.call("OPT.ashx", 6, payload) or {}
                    ret = resp.get("ret", -1)
                else:
                    err_desc = ERROR_MESSAGES.get(buy_ret, f"Mã lỗi: {buy_ret}")
                    if on_log:
                        on_log(f"   [Chiêu mộ] ❌ Chiêu mộ thất bại ({err_desc})")

            results.append((soldier_type, diff, ret == 0, ret))
        return results

    def adjust_morale(
        self,
        city_id: int,
        general_id: int,
        current_morale: int,
        min_morale: int = 51,
    ) -> tuple[bool, int]:
        """
        Nâng sỹ khí cho tướng nếu sỹ khí hiện tại < min_morale bằng API id=47.
        Mỗi lần nâng sỹ khí tăng tối đa 10 điểm (nâng trên 10 điểm yêu cầu đạo cụ rượu).
        Trả về (success, ret_code)
        """
        if current_morale >= min_morale or current_morale >= 100:
            return True, 0
        add_point = min(10, max(1, 100 - current_morale))
        payload = {
            "lAddPoint": str(add_point),
            "lGeneralID": str(general_id),
            "tid": str(city_id),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 47, payload) or {}
        ret = resp.get("ret", -1)
        return ret == 0, ret

    def send_request(
        self,
        city_id: int,
        task_id: int,
        general_ids: list[int],
    ) -> ThaoPhatResult:
        """
        Gửi yêu cầu Thảo Phạt bằng API id=62.
        """
        if task_id not in THAOPHAT_MISSIONS:
            return ThaoPhatResult(False, -1, f"TaskID {task_id} không hợp lệ")

        mission = THAOPHAT_MISSIONS[task_id]
        max_gens = mission.get("max_generals", 5)
        selected_gens = general_ids[:max_gens]
        counts = len(selected_gens)

        payload = {
            "taskid": str(task_id),
            "counts": str(counts),
            "general1": str(selected_gens[0]) if counts > 0 else "0",
            "general2": str(selected_gens[1]) if counts > 1 else "0",
            "general3": str(selected_gens[2]) if counts > 2 else "0",
            "general4": str(selected_gens[3]) if counts > 3 else "0",
            "general5": str(selected_gens[4]) if counts > 4 else "0",
            "tid": str(city_id),
            "_": "",
        }

        resp = self.gateway.call("OPT.ashx", 62, payload) or {}
        ret = resp.get("ret", -1)
        msg = ERROR_MESSAGES.get(ret, f"Mã lỗi: {ret}")
        return ThaoPhatResult(success=(ret == 0), code=ret, message=msg)


class ThaoPhatAutoRunner:
    """Vòng lặp Thảo Phạt tự động liên tục cho đến khi stop_event được kích hoạt.

    Quy trình trong mỗi lượt:
    1. Chờ tất cả tướng được chọn về thành và rảnh rỗi (status == 0).
    2. Bổ sung quân số theo cấu hình (chỉ bổ sung nếu thiếu, không tháo nếu thừa).
    3. Luyện sĩ khí nếu sĩ khí hiện tại < min_morale, chờ luyện sĩ khí hoàn tất hoặc thời gian hoàn tất nhỏ hơn thời gian hành quân và lần nâng sĩ khí đó đảm bảo đủ sĩ khí theo cấu hình. 
- mỗi lần nâng sĩ khí tăng 10 điểm
- ví dụ sĩ khí cấu hình là 95, nếu sĩ khí hiện tại <=84 sau khi nâng sĩ khí là 94 chưa đủ thì phải chờ nâng sĩ khí kết thúc rồi nâng tiếp, lần thứ 2 nâng sẽ là 94 + 10 > 95 vậy sẽ tính thời gian nâng còn lại so sáng với thời gian hành quân để tiến hành thảo phạt
    4. Nhận nhiệm vụ / Gửi lệnh xuất kích Thảo Phạt (API id=62).
    5. Theo dõi hành quân và đợi tất cả tướng hoàn thành trở về thành rảnh rỗi.
    6. Lặp lại chu kỳ mới.
    """

    def __init__(
        self,
        gateway: GatewayClient,
        *args,
        city_id: Optional[int] = None,
        task_id: Optional[int] = None,
        general_ids: Optional[list[int]] = None,
        target_army: Optional[TargetArmy] = None,
        min_morale: int = 95,
        auto_recruit: bool = True,
        auto_morale: bool = True,
        track_battle: bool = True,
        auto_counter: bool = True,
        leave_boss_last: bool = True,
        stop_event: Optional[threading.Event] = None,
        log_fn: Optional[Callable[[str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        check_interval: float = 10.0,
        executor: Optional[ThaoPhatExecutor] = None,
        **kwargs,
    ):
        if args:
            if isinstance(args[0], ThaoPhatExecutor):
                executor = args[0]
                remaining = args[1:]
            else:
                remaining = args
            if len(remaining) > 0 and city_id is None:
                city_id = remaining[0]
            if len(remaining) > 1 and task_id is None:
                task_id = remaining[1]
            if len(remaining) > 2 and general_ids is None:
                general_ids = remaining[2]
            if len(remaining) > 3 and target_army is None:
                target_army = remaining[3]

        self.gateway = gateway
        self.city_id = city_id or 0
        self.task_id = task_id or 0
        self.general_ids = general_ids or []
        self.target_army = target_army or TargetArmy()
        self.min_morale = min_morale
        self.auto_recruit = auto_recruit
        self.auto_morale = auto_morale
        self.track_battle = track_battle
        self.auto_counter = auto_counter
        self.leave_boss_last = leave_boss_last
        self.stop_event = stop_event or threading.Event()
        self.log_fn = log_callback or log_fn or (lambda msg: None)
        self.status_callback = status_callback
        self.check_interval = check_interval
        self.executor = executor or ThaoPhatExecutor(gateway)
        self.completed_cycles = 0
        self._thread: Optional[threading.Thread] = None

    def start(self) -> threading.Thread:
        """Khởi chạy runner trong background thread."""
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        return self._thread

    def is_alive(self) -> bool:
        return self._thread.is_alive() if self._thread else False

    def log(self, msg: str) -> None:
        self.log_fn(msg)
        if self.status_callback:
            self.status_callback(msg)

    def wait(self, seconds: float) -> bool:
        """Chờ `seconds` giây. Trả về True nếu stop_event được kích hoạt (người dùng bấm dừng)."""
        return self.stop_event.wait(seconds)

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        mission_info = THAOPHAT_MISSIONS.get(self.task_id, {})
        mission_name = mission_info.get("name", f"Nhiệm vụ {self.task_id}")
        travel_time = mission_info.get("travel_time", 300)

        self.log("==================================================")
        self.log(f"⚔️ BẮT ĐẦU VÒNG LẶP THẢO PHẠT TỰ ĐỘNG: '{mission_name}'")
        self.log(f"   Thành ID: {self.city_id} | Tướng: {self.general_ids}")
        self.log(f"   Mục tiêu quân: Bộ={self.target_army.infantry}, Kỵ={self.target_army.cavalry}, Cung={self.target_army.archers}")
        self.log(f"   Tự động bổ sung lính: {'Bật' if self.auto_recruit else 'Tắt'} | Tự động nâng sĩ khí: {'Bật' if self.auto_morale else 'Tắt'}")
        self.log(f"   Sĩ khí tối thiểu: {self.min_morale} | Thời gian hành quân: ~{travel_time}s")
        self.log("==================================================")

        while not self.stop_event.is_set():
            cycle = self.completed_cycles + 1
            self.log(f"\n🔄 [Lượt {cycle}] Bắt đầu kiểm tra điều kiện xuất kích...")

            try:
                # -------------------------------------------------------------
                # BƯỚC 1: Chờ tất cả tướng về thành và rảnh rỗi (status == 0)
                # -------------------------------------------------------------
                all_ready = False
                last_logged_busy = None
                last_logged_upgrading = None
                while not self.stop_event.is_set() and not all_ready:
                    roster = fetch_roster(self.gateway)
                    city_gens = {g.id: g for g in roster.generals_of(self.city_id)}

                    busy_list = []
                    for gid in self.general_ids:
                        g = city_gens.get(gid)
                        if not g:
                            busy_list.append((gid, f"Tướng {gid} không có trong thành {self.city_id}"))
                        elif g.status != 0:
                            busy_list.append((gid, f"{g.name}: {g.status_text} (status={g.status})"))

                    if busy_list:
                        desc = ", ".join(f"[{item[1]}]" for item in busy_list)
                        if desc != last_logged_busy:
                            last_logged_busy = desc
                            self.log(f"⏳ Tướng chưa rảnh rỗi: {desc}. Đang chờ (timer chạy ngầm)...")
                        if self.wait(self.check_interval):
                            break
                        continue
                    last_logged_busy = None

                    # Nếu tướng đang nâng sĩ khí mà quân số đang thiếu:
                    # Chờ đếm ngược nâng sĩ khí xong (vì API biên chế lính id=6 sẽ bị từ chối khi upgrading_time > 0)
                    upgrading_list = []
                    for gid in self.general_ids:
                        g = city_gens.get(gid)
                        if g and g.upgrading_time > 0:
                            army = roster.army_of(gid)
                            cur_inf = army.infantry if army else 0
                            cur_cav = army.cavalry if army else 0
                            cur_arc = army.archers if army else 0
                            needs_recruit = (
                                cur_inf < self.target_army.infantry
                                or cur_cav < self.target_army.cavalry
                                or cur_arc < self.target_army.archers
                            )
                            if needs_recruit:
                                upgrading_list.append((g.name, g.upgrading_time))

                    if upgrading_list:
                        desc = ", ".join(f"{name} (còn {t}s)" for name, t in upgrading_list)
                        max_up = max(t for _, t in upgrading_list)
                        if desc != last_logged_upgrading:
                            last_logged_upgrading = desc
                            self.log(f"⏳ Đang nâng sĩ khí (cần chờ xong để bổ sung quân): {desc} (timer chạy ngầm)...")
                        wait_t = max_up if self.check_interval >= 1.0 else self.check_interval
                        if self.wait(wait_t):
                            break
                        continue
                    last_logged_upgrading = None

                    all_ready = True

                if self.stop_event.is_set():
                    break

                # -------------------------------------------------------------
                # BƯỚC 2: Bổ sung quân số cho từng tướng (nếu thiếu)
                # -------------------------------------------------------------
                roster = fetch_roster(self.gateway)
                city_gens = {g.id: g for g in roster.generals_of(self.city_id)}
                recruit_failed = False
                troops_added = False

                if self.auto_recruit:
                    # Kiểm tra tổng quân cần bổ sung và chủ động chiêu mộ trước nếu thiếu
                    total_needed = 0
                    for gid in self.general_ids:
                        current_army = roster.army_of(gid)
                        cur_inf = current_army.infantry if current_army else 0
                        cur_cav = current_army.cavalry if current_army else 0
                        cur_arc = current_army.archers if current_army else 0
                        total_needed += max(0, self.target_army.infantry - cur_inf)
                        total_needed += max(0, self.target_army.cavalry - cur_cav)
                        total_needed += max(0, self.target_army.archers - cur_arc)

                    if total_needed > 0:
                        avail = self.executor.check_recruits(self.city_id)
                        if avail is not None and avail < total_needed:
                            missing = total_needed - avail
                            self.log(f"📦 [Tân binh] Kho hiện có {avail}/{total_needed}, tự động chiêu mộ thêm {missing} tân binh...")
                            b_succ, b_ret = self.executor.buy_recruits(self.city_id, missing)
                            if b_succ:
                                self.log(f"   [Chiêu mộ] ✅ Đã chiêu mộ thành công {missing} tân binh!")
                            else:
                                err_desc = ERROR_MESSAGES.get(b_ret, f"Mã lỗi: {b_ret}")
                                self.log(f"   [Chiêu mộ] ⚠️ Chiêu mộ tân binh thất bại ({err_desc})")

                    for gid in self.general_ids:
                        if self.stop_event.is_set():
                            break
                        g = city_gens.get(gid)
                        gname = g.name if g else str(gid)
                        current_army = roster.army_of(gid)

                        adj_results = self.executor.adjust_troops(
                            self.city_id,
                            gid,
                            current_army,
                            self.target_army,
                            auto_recruit=self.auto_recruit,
                            on_log=self.log,
                        )
                        if adj_results:
                            for stype, diff, succ, ret_code in adj_results:
                                tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(stype, "Quân")
                                if succ:
                                    if diff > 0:
                                        troops_added = True
                                    self.log(f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ✅ Thành công")
                                else:
                                    err_desc = ERROR_MESSAGES.get(ret_code, f"Mã lỗi: {ret_code}")
                                    self.log(f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ❌ Thất bại ({err_desc})")
                                    recruit_failed = True
                        else:
                            self.log(f"   [Biên chế] Tướng {gname}: Quân số đã đủ, không cần bổ sung.")

                    if self.stop_event.is_set():
                        break

                    if recruit_failed:
                        self.log("⚠️ Có lỗi khi biên chế lính (ví dụ thiếu tân binh/tài nguyên). Chờ 30s trước khi thử lại...")
                        if self.wait(30.0):
                            break
                        continue

                    if troops_added:
                        self.log("📦 Đã bổ sung tân binh vào đội hình. Quét lại sỹ khí thực tế sau khi biên chế...")
                else:
                    self.log("⏭️ [Biên chế] Tự động bổ sung lính đang tắt, bỏ qua bước bổ sung quân.")

                # -------------------------------------------------------------
                # BƯỚC 3: Luyện sỹ khí cho từng tướng (nếu < min_morale)
                # - Mỗi lần nâng sĩ khí tăng 10 điểm (tối đa 100).
                # - Nếu sĩ khí sau lần nâng hiện tại chưa đạt min_morale (ví dụ cur <= 84 nâng lên 94 < 95):
                #   bắt buộc phải chờ đợt nâng này kết thúc hoàn toàn (up_t về 0) rồi nâng tiếp lần 2.
                # - Khi lần nâng đảm bảo đủ sĩ khí theo cấu hình (ví dụ cur = 94 nâng lên 100 >= 95):
                #   chỉ cần thời gian nâng còn lại up_t <= travel_time là có thể xuất phát.
                # -------------------------------------------------------------
                first_morale_check = True
                last_logged_morale_wait = None
                while not self.stop_event.is_set():
                    fresh_roster = fetch_roster(self.gateway)
                    city_gens = {g.id: g for g in fresh_roster.generals_of(self.city_id)}

                    if first_morale_check:
                        first_morale_check = False
                        self.log(f"🔍 [Sĩ khí] Kiểm tra sỹ khí của các tướng (mục tiêu >= {self.min_morale}):")
                        for gid in self.general_ids:
                            g = city_gens.get(gid)
                            gname = g.name if g else str(gid)
                            cur_m = g.morale if g else 0
                            self.log(f"   👉 Tướng {gname}: Sĩ khí hiện tại là {cur_m}/{self.min_morale}")

                    all_morale_ready = True
                    wait_needed = []

                    for gid in self.general_ids:
                        g = city_gens.get(gid)
                        gname = g.name if g else str(gid)
                        cur_morale = g.morale if g else 0
                        up_t = g.upgrading_time if g else 0

                        if cur_morale >= self.min_morale:
                            continue

                        if not self.auto_morale:
                            all_morale_ready = False
                            wait_needed.append((gname, 10.0, f"Sĩ khí {cur_morale} < {self.min_morale} (tự động nâng sĩ khí đang tắt)"))
                            continue

                        projected = min(100, cur_morale + 10)
                        is_final_upgrade = (projected >= self.min_morale)

                        if up_t == 0:
                            all_morale_ready = False
                            if is_final_upgrade:
                                self.log(f"   [Sĩ khí] Tướng {gname}: Sĩ khí {cur_morale} < {self.min_morale} (lần nâng này đạt {projected} >= {self.min_morale}), bắt đầu nâng...")
                            else:
                                self.log(f"   [Sĩ khí] Tướng {gname}: Sĩ khí {cur_morale} < {self.min_morale} (lần nâng này đạt {projected} < {self.min_morale}, cần nâng tiếp đợt sau), bắt đầu nâng...")

                            m_succ, m_ret = self.executor.adjust_morale(self.city_id, gid, cur_morale, self.min_morale)
                            if m_succ:
                                self.log(f"   [Sĩ khí] Tướng {gname}: ✅ Bắt đầu nâng thành công!")
                                wait_needed.append((gname, 5.0, "vừa bắt đầu nâng"))
                            else:
                                err_desc = ERROR_MESSAGES.get(m_ret, f"Mã lỗi: {m_ret}")
                                self.log(f"   [Sĩ khí] Tướng {gname}: ❌ Nâng thất bại ({err_desc})")
                                wait_needed.append((gname, 10.0, f"thử lại ({err_desc})"))
                        else:
                            if not is_final_upgrade:
                                all_morale_ready = False
                                wait_needed.append((gname, float(up_t), f"còn {up_t}s (chờ đạt {projected} để nâng tiếp lượt sau)"))
                            elif up_t > travel_time:
                                excess = up_t - travel_time
                                all_morale_ready = False
                                wait_needed.append((gname, float(excess), f"còn {up_t}s > hành quân {travel_time}s (cần giảm thêm {excess}s)"))
                            else:
                                # up_t <= travel_time và is_final_upgrade -> Đủ điều kiện!
                                pass

                    if all_morale_ready:
                        break

                    max_wait = max(wait for _, wait, _ in wait_needed)
                    desc = "; ".join(f"{name}: {reason}" for name, _, reason in wait_needed)
                    if desc != last_logged_morale_wait:
                        last_logged_morale_wait = desc
                        self.log(f"⏳ [Sĩ khí] Đang đợi nâng sĩ khí: {desc} (timer chạy ngầm)...")
                    wait_sec = max_wait if self.check_interval >= 1.0 else self.check_interval
                    if self.wait(wait_sec):
                        break
                    last_logged_morale_wait = None

                if self.stop_event.is_set():
                    break

                # -------------------------------------------------------------
                # KIỂM TRA LẠI: Xác nhận sĩ khí đạt chuẩn trước khi xuất quân
                # -------------------------------------------------------------
                fresh_roster = fetch_roster(self.gateway)
                city_gens = {g.id: g for g in fresh_roster.generals_of(self.city_id)}
                morale_ready = True

                self.log("🔍 [Kiểm tra lại] Đánh giá sỹ khí và thời gian hành quân trước khi xuất quân:")
                for gid in self.general_ids:
                    g = city_gens.get(gid)
                    gname = g.name if g else str(gid)
                    cur_morale = g.morale if g else 0
                    up_t = g.upgrading_time if g else 0
                    projected = min(100, cur_morale + 10)

                    if cur_morale >= self.min_morale:
                        self.log(f"   ✅ Tướng {gname}: Sĩ khí {cur_morale}/{self.min_morale} (Đã đủ)")
                    elif up_t > 0:
                        if projected < self.min_morale:
                            self.log(f"   ⚠️ Tướng {gname}: Sĩ khí {cur_morale} (+10 = {projected} < {self.min_morale}), chưa đủ dù nâng xong đợt này!")
                            morale_ready = False
                        elif up_t > travel_time:
                            excess = up_t - travel_time
                            self.log(f"   ⚠️ Tướng {gname}: Nâng sĩ khí còn {up_t}s > hành quân {travel_time}s (cần chờ thêm {excess}s)!")
                            morale_ready = False
                        else:
                            self.log(f"   ✅ Tướng {gname}: Sĩ khí {cur_morale} (+10={projected} >= {self.min_morale}) đang nâng (còn {up_t}s <= hành quân {travel_time}s -> hoàn tất trên đường đi) (Sẵn sàng)")
                    else:
                        self.log(f"   ⚠️ Tướng {gname}: Sĩ khí {cur_morale} < {self.min_morale} (chưa đạt yêu cầu)!")
                        morale_ready = False

                if not morale_ready:
                    self.log("⏳ Sĩ khí chưa đạt yêu cầu xuất kích. Chờ kiểm tra/nâng lại...")
                    wait_sec = self.check_interval if self.check_interval < 1.0 else min(10.0, self.check_interval)
                    if self.wait(wait_sec):
                        break
                    continue

                # -------------------------------------------------------------
                # BƯỚC 4: Nhận nhiệm vụ / Gửi lệnh Thảo Phạt (API id=62)
                # -------------------------------------------------------------
                self.log(f"🚀 [Lượt {cycle}] Gửi lệnh Thảo Phạt '{mission_name}' với {len(self.general_ids)} tướng...")
                res = self.executor.send_request(self.city_id, self.task_id, self.general_ids)

                if not res.success:
                    err_desc = ERROR_MESSAGES.get(res.code, res.message)
                    self.log(f"❌ Gửi Thảo Phạt thất bại: {err_desc} (mã: {res.code})")
                    wait_sec = 30.0 if res.code in (8, 79, 10040) else 15.0
                    self.log(f"⏳ Chờ {int(wait_sec)}s trước khi thử lại lượt này...")
                    if self.wait(wait_sec):
                        break
                    continue

                round_trip_sec = travel_time * 2
                self.log(f"🎉 Gửi Thảo Phạt thành công! Tướng đã xuất kích.")
                self.log(f"⏳ Thời gian hành quân: Đi {travel_time}s ({travel_time // 60}p) + Về {travel_time}s ({travel_time // 60}p) [Tổng ~{round_trip_sec}s chưa tính chiến đấu].")

                # -------------------------------------------------------------
                # BƯỚC 5: Theo dõi và chờ tất cả tướng trở về thành rảnh rỗi (status == 0)
                # -------------------------------------------------------------
                if self.check_interval < 1.0:
                    # Chế độ test / mô phỏng nhanh
                    if self.track_battle:
                        battle_ctrl = BattleController(self.gateway)
                        battle_ctrl.track_battle(
                            battle_id=0,
                            on_log=self.log,
                            auto_counter=self.auto_counter,
                            leave_boss_last=self.leave_boss_last,
                            stop_event=self.stop_event,
                            sleep_fn=lambda s: None,
                        )
                    if self.wait(self.check_interval):
                        break
                else:
                    # Chế độ thực tế: Theo dõi hành quân qua Common.ashx?id=3
                    battle_ctrl = BattleController(self.gateway)
                    c_info = battle_ctrl.get_campaign_status()
                    c_status = c_info.get("status", 1) if c_info else 1
                    curr = c_info.get("current", []) if c_info else []
                    m_countdown = curr[1] if len(curr) > 1 and curr[1] > 0 else travel_time

                    self.log(f"   🚶 [Hành quân] Đang di chuyển tới '{mission_name}' (~{m_countdown}s, timer chạy ngầm)...")

                    # Chờ cho đến khi tới chiến trường (status == 2 hoặc countdown <= 0)
                    while m_countdown > 3 and c_status == 1:
                        if self.stop_event.is_set():
                            break
                        sleep_time = min(15.0, max(3.0, float(m_countdown - 3)))
                        if self.wait(sleep_time):
                            break
                        c_info = battle_ctrl.get_campaign_status()
                        if c_info:
                            c_status = c_info.get("status", 1)
                            curr = c_info.get("current", [])
                            m_countdown = curr[1] if len(curr) > 1 else 0
                        else:
                            break

                    if self.stop_event.is_set():
                        break

                    self.log(f"   ⚔️ [Chiến trường] Đã tới '{mission_name}', đang vào chiến trường theo dõi...")

                    # BƯỚC 5: Theo dõi chiến trường, ghi log quân số thiệt hại, sĩ khí và kết quả chiến đấu
                    if self.track_battle:
                        battle_sleep = (lambda s: None) if self.check_interval < 1.0 else time.sleep
                        battle_ctrl.track_battle(
                            battle_id=0,
                            on_log=self.log,
                            auto_counter=self.auto_counter,
                            leave_boss_last=self.leave_boss_last,
                            stop_event=self.stop_event,
                            sleep_fn=battle_sleep,
                        )

                    if self.stop_event.is_set():
                        break

                    self.log(f"   🚶 [Hành quân] Trận chiến kết thúc! Tướng đang trên đường trở về thành (~{travel_time}s, timer chạy ngầm)...")
                    # Chờ an toàn 80% thời gian lượt về trước khi bắt đầu polling
                    if self.wait(float(travel_time) * 0.8):
                        break

                while not self.stop_event.is_set():
                    roster = fetch_roster(self.gateway)
                    city_gens = {g.id: g for g in roster.generals_of(self.city_id)}

                    busy_count = 0
                    for gid in self.general_ids:
                        g = city_gens.get(gid)
                        if g and g.status != 0:
                            busy_count += 1

                    if busy_count == 0:
                        self.completed_cycles += 1
                        self.log(f"🏁 [Lượt {cycle}] Hoàn thành lượt {cycle}: ✅ Tất cả tướng đã hoàn thành nhiệm vụ và trở về thành an toàn!")
                        break
                    else:
                        if self.wait(self.check_interval):
                            break

                if self.stop_event.is_set():
                    break

                # Nghỉ ngắn trước khi bắt đầu chu kỳ kế tiếp
                self.wait(min(3.0, self.check_interval))

            except Exception as e:
                self.log(f"❌ Ngoại lệ trong vòng lặp Thảo Phạt: {e}. Thử lại sau {int(self.check_interval)}s...")
                if self.wait(self.check_interval):
                    break

        self.log("\n⏹️ ĐÃ DỪNG TÍNH NĂNG THẢO PHẠT TỰ ĐỘNG.")
        self.log(f"   Tổng số lượt Thảo Phạt hoàn thành: {self.completed_cycles}")


# Lớp giữ tương thích với test_tasks.py cũ
class ThaoPhat:
    def __init__(
        self,
        ctx: TaskContext,
        generals: list[int],
        origin: tuple[int, int],
        radius: int,
        man_types: list[int],
    ):
        self.ctx = ctx
        self.generals = generals
        self.origin = origin
        self.radius = radius
        self.man_types = man_types
        self.executor = ThaoPhatExecutor(ctx.gateway)

    def run_once(self) -> str:
        target = self.ctx.scanner.find_nearest(*self.origin, self.radius, self.man_types)
        if target is None:
            return "no_target"
        self.ctx.gateway.call("OPT.ashx", 62, {"target_id": str(target.target_id)})
        return attack(self.ctx, target, self.generals)
