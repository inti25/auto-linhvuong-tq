"""Nhiệm vụ Quản lý & Nâng cấp Công trình Thành trì.

Reverse engineered chính xác từ ZBuild.exe:
- Quản lý Hàng Đợi Xây Dựng:
  1. Kiểm tra trạng thái nâng cấp thành phố: Common.ashx?id=77 (cid: city_id).
  2. Kiểm tra tài nguyên khoáng sản (Gỗ, Đá, Sắt, Lúa): City.ashx?id=20 (tid: city_id).
  3. Lấy danh sách công trình thực tế trong thành: City.ashx?id=5 (tid: city_id).
  4. Nâng cấp công trình theo mức ưu tiên cấu hình: OPT.ashx?id=65 (pid, gid, type=1, tid).
  5. Tự động tăng tốc hoàn thành: OPT.ashx?id=69 (type=1, param1=city_id, param2=slot, paytype).
  6. Kích hoạt hiệu ứng tăng tốc 20% khi hết hạn: OPT.ashx?id=69 (type=3, param1=0, param2=0, paytype=2).
  7. Tự động An Dân khôi phục sĩ khí/lòng dân: OPT.ashx?id=4 (lType=1, tid).
"""

import time
from dataclasses import dataclass
from typing import Callable, Optional

from ..gateway import GatewayClient
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired


BUILDING_NAMES = {
    1: "官府 - Quan Phủ",
    2: "城墙 - Tường Thành",
    3: "民房 - Nhà Dân",
    4: "仓库 - Kho",
    5: "鸿胪寺 - Hồng Lư Tự",
    6: "大学殿 - Đại Học Điện",
    7: "客栈 - Quán Trọ",
    8: "酒馆 - Tửu Quán",
    9: "聚贤楼 - Tụ Hiền Lâu",
    10: "点将台 - Điểm Tướng Đài",
    11: "市场 - Chợ",
    12: "驿站 - Dịch Trạm",
    13: "兵器铺 - Xưởng Binh Khí",
    14: "防具铺 - Xưởng Khôi Giáp",
    15: "车马间 - Xưởng Ngựa",
    16: "校场 - Binh Trường",
    17: "营寨栅栏 - Tường",
    18: "中军大帐 - Trung Quân Đại Trướng",
    19: "营寨校场 - Binh Trường",
    20: "营寨驿站 - Dịch Trạm",
    21: "营寨仓库 - Kho",
    54: "宫殿 - Cung Điện",
    55: "壁垒 - Bích Lũy",
    56: "高级民居 - Cao Cấp Dân Cư",
    57: "国库 - Quốc Khố",
    58: "使节殿 - Sứ Tiết Điện",
    59: "太学殿 - Thái Học Điện",
    60: "水镜庐 - Quán Trọ",
    61: "酒肆 - Tửu Quán",
    62: "幕僚邸 - Tụ Hiền Lâu",
    63: "将帅府 - Điểm Tướng Đài",
    64: "集市 - Chợ",
    65: "中央驿所 - Dịch Trạm",
    66: "兵器司 - Xưởng Binh Khí",
    67: "防具司 - Xưởng Khôi Giáp",
    68: "车马司 - Xưởng Ngựa",
    69: "督军场 - Đốc Quân Trường",
}

RESOURCE_BOX_NAMES = {
    24: "民生之鼎 - Dân Sinh Bảo Đỉnh",
    16: "民生之椟 - Dân Sinh Chi Độc",
    11: "民生之匣 - Dân Sinh Chi Hạp",
    1: "民生之囊 - Dân Sinh Chi Nang",
    35: "白金资源礼盒 - Bạch Kim Tài Nguyên Lễ Hộp",
}

DEFAULT_FALLBACK_BOX_ORDER = [24, 16, 11, 1]


def parse_remaining_seconds(raw_val) -> int:
    """Chuyển đổi giá trị thời gian còn lại (giây, HH:MM:SS, MM:SS, hoặc Unix timestamp) sang số giây."""
    if raw_val in (None, "", 0, "0"):
        return 0

    if isinstance(raw_val, str) and ":" in raw_val:
        parts = [p.strip() for p in raw_val.split(":")]
        if len(parts) == 3:
            try:
                return max(0, int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
            except ValueError:
                return 0
        if len(parts) == 2:
            try:
                return max(0, int(parts[0]) * 60 + int(parts[1]))
            except ValueError:
                return 0
        return 0

    try:
        val = int(float(raw_val))
    except (ValueError, TypeError):
        return 0

    if val > 1_000_000_000:
        return max(0, int(val - time.time()))
    return max(0, val)


def parse_boost_remaining_time(resp: dict, city_id: int = 0) -> int:
    """Trích xuất thời gian còn lại (giây) của DS kiến trúc từ response Common.ashx?id=77."""
    if not isinstance(resp, dict):
        return 0

    plus_finish = None

    # 1. Kiểm tra trường plus_finish ở root (nếu có)
    if "plus_finish" in resp and resp["plus_finish"] not in (None, "", 0, "0"):
        plus_finish = resp["plus_finish"]

    # 2. Kiểm tra danh sách thành trong resp["list"]
    if plus_finish is None or plus_finish == 0:
        city_list = resp.get("list", [])
        target_city = None
        for c_info in city_list:
            if isinstance(c_info, dict):
                c_cid = c_info.get("cid") or c_info.get("id") or c_info.get("city_id")
                if not city_id or str(c_cid) == str(city_id):
                    target_city = c_info
                    break
            elif isinstance(c_info, (list, tuple)) and len(c_info) >= 4:
                if not city_id or str(c_info[0]) == str(city_id):
                    target_city = c_info
                    break

        if target_city is None and city_list:
            target_city = city_list[0]

        if isinstance(target_city, dict):
            plus_finish = (
                target_city.get("plus_finish")
                or target_city.get("val3")
                or target_city.get("time_left")
                or 0
            )
        elif isinstance(target_city, (list, tuple)) and len(target_city) >= 4:
            # [city_id, name, val2, val3, ...]
            # val3: thời hạn 建筑排程 (DS kiến trúc - 3 vị trí), val2: 20% speedup
            val2 = target_city[2]
            val3 = target_city[3]
            if val3 not in (None, "", 0, "0"):
                plus_finish = val3
            elif val2 not in (None, "", 0, "0"):
                plus_finish = val2
            else:
                plus_finish = 0

    return parse_remaining_seconds(plus_finish)


@dataclass
class BuildingPlan:
    pid: int  # Vị trí ô đất trong thành (1..32)
    gid: int  # Loại công trình (1: Thái Phủ, 8: Đại Học, 21: Ruộng...)
    target_level: int  # Cấp độ mục tiêu cần đạt (0..33, 0 nghĩa là dỡ bỏ hoàn toàn)
    name: str = ""
    enabled: bool = True

    def __post_init__(self):
        if not self.name:
            self.name = BUILDING_NAMES.get(self.gid, f"Công trình {self.gid}")


class BuildingTask:
    _last_boost_act_time: float = 0.0

    def __init__(
        self,
        gateway: GatewayClient,
        city_id: int,
        plans: list[BuildingPlan],
        max_slots: int = 3,
        auto_speedup: bool = False,
        speedup_hours: float = 1.0,
        paytype: int = 2,
        auto_comfort: bool = True,
        auto_boost: bool = False,
        auto_open_box: bool = False,
        box_id: int = 24,
        max_boxes_per_round: int = 5,
        auto_fallback_box: bool = True,
        even_upgrade: bool = False,
        notify: Callable[[str], None] = print,
        city_name: str = "",
        on_sync_data: Optional[Callable[[int, dict[int, dict]], None]] = None,
    ):
        self.gateway = gateway
        self.city_id = city_id
        self.city_name = city_name
        self.plans = plans
        self.max_slots = max_slots
        self.auto_speedup = auto_speedup
        try:
            self.speedup_hours = max(0.0, float(speedup_hours))
        except (ValueError, TypeError):
            self.speedup_hours = 1.0
        self.paytype = int(paytype)
        self.auto_comfort = auto_comfort
        self.auto_boost = auto_boost
        self.auto_open_box = auto_open_box
        self.box_id = box_id
        self.max_boxes_per_round = max_boxes_per_round
        self.auto_fallback_box = auto_fallback_box
        self.even_upgrade = even_upgrade
        self.notify = notify
        self.on_sync_data = on_sync_data
        self.skipped_pids: set[int] = set()
        self.deferred_pids: set[int] = set()

    def reset_skipped(self):
        """Xóa danh sách các slot công trình tạm thời bị bỏ qua."""
        self.skipped_pids.clear()

    def reset_deferred(self):
        """Xóa danh sách các slot công trình bị hoãn kiểm tra (mã lỗi 261, 245)."""
        self.deferred_pids.clear()

    def _log(self, msg: str):
        if self.city_name:
            self.notify(f"[{self.city_name}] {msg}")
        else:
            self.notify(msg)

    def _fetch_c77(self, force: bool = False) -> dict:
        """Đọc và cache kết quả Common.ashx?id=77 trong chu kỳ ngắn để tránh gọi trùng."""
        now = time.time()
        cached = getattr(self, "_c77_cache", None)
        cached_time = getattr(self, "_c77_cache_time", 0.0)
        if not force and cached is not None and (now - cached_time < 3.0):
            return cached

        resp = self.gateway.call("Common.ashx", 77, {"cid": str(self.city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        self._c77_cache = resp
        self._c77_cache_time = now
        return resp

    def check_and_activate_boost(self) -> bool:
        """Kiểm tra thời gian DS kiến trúc (xây 3 nhà), kích hoạt nếu hết hạn."""
        if not self.auto_boost:
            return True

        resp = self._fetch_c77()
        remaining = parse_boost_remaining_time(resp, self.city_id)
        if remaining <= 0:
            now_ts = time.time()
            if now_ts - BuildingTask._last_boost_act_time < 60:
                # Đang trong thời gian chờ sau lần kích hoạt gần nhất (tránh kích hoạt lặp giữa các thành)
                return True

            BuildingTask._last_boost_act_time = now_ts
            self._log("⚡ DS kiến trúc đã hết hạn. Đang tự kích hoạt lại (3 vị trí thi công)...")
            boost_resp = self.gateway.call(
                "OPT.ashx",
                69,
                {"type": "3", "param1": "0", "param2": "0", "paytype": "2", "_": ""},
            ) or {}
            self._c77_cache = None
            ret = boost_resp.get("ret", RET_OK)
            if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
                raise CaptchaRequired()
            if ret == RET_OK:
                self._log("✅ Kích hoạt thành công DS kiến trúc (3 vị trí thi công)!")
                return True
            else:
                self._log(f"⚠️ Kích hoạt DS kiến trúc thất bại (mã {ret}).")
                return False
        return True

    def check_and_comfort_city(self) -> bool:
        """Kiểm tra sĩ khí / dân nộ, tự động Tế Trời An Dân nếu cần."""
        resp = self.gateway.call("City.ashx", 6, {"tid": str(self.city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        data = resp.get("data", {})
        if data:
            morale = int(data.get("morale", 100))
            anger = int(data.get("anger", 0))
        elif isinstance(resp.get("morale"), (list, tuple)):
            m_list = resp["morale"]
            morale = int(m_list[0]) if m_list else 100
            anger = int(m_list[1]) if len(m_list) > 1 else 0
        else:
            morale = int(resp.get("morale", 100))
            anger = int(resp.get("anger", 0))

        if morale < 90 or anger > 0:
            self._log(f"🕊️ Sĩ khí ({morale}%) thấp hoặc dân nộ ({anger}), tiến hành An Dân...")
            comfort_resp = self.gateway.call(
                "OPT.ashx",
                4,
                {"lType": "1", "tid": str(self.city_id), "_": ""},
            ) or {}
            return comfort_resp.get("ret", RET_OK) == RET_OK
        return True

    def get_active_upgrade_slots(self) -> list:
        """Lấy danh sách các slot đang nâng cấp dở trong thành."""
        resp = self._fetch_c77()

        city_list = resp.get("list", [])
        for city_info in city_list:
            if isinstance(city_info, dict):
                # Hỗ trợ cấu trúc mock trong test
                return city_list
            if isinstance(city_info, (list, tuple)) and len(city_info) >= 5:
                if str(city_info[0]) == str(self.city_id):
                    upgrades = city_info[4]
                    if isinstance(upgrades, list):
                        return upgrades

        # Fallback qua Build.ashx?id=2
        fb_resp = self.gateway.call("Build.ashx", 2, {"pid": "8", "gid": "1", "tab": "2", "tid": str(self.city_id), "_": ""}) or {}
        return fb_resp.get("list", [])

    def get_real_buildings(self) -> dict[int, dict]:
        """Lấy danh sách công trình hiện có: {pid: {"gid": gid, "level": level, "name": name}}."""
        resp = self.gateway.call("City.ashx", 5, {"tid": str(self.city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        buildings_list = resp.get("infos") or resp.get("buildings") or resp.get("build", [])
        buildings_map = {}
        for b in buildings_list:
            if isinstance(b, dict):
                pid = int(b.get("pid", 0))
                buildings_map[pid] = {
                    "gid": int(b.get("gid", 0)),
                    "level": int(b.get("level", 0)),
                    "name": b.get("name", ""),
                }
            elif isinstance(b, (list, tuple)) and len(b) >= 4:
                pid = int(b[0])
                buildings_map[pid] = {
                    "gid": int(b[1]),
                    "level": int(b[3]),
                    "name": str(b[2]) if len(b) > 2 else "",
                }
        return buildings_map

    def speedup_slot(self, slot_id: int, paytype: Optional[int] = None) -> bool:
        """Sử dụng vật phẩm tăng tốc xây dựng (giảm 50% thời gian thi công)."""
        pt = paytype if paytype is not None else self.paytype
        resp = self.gateway.call(
            "OPT.ashx",
            69,
            {
                "type": "1",
                "param1": str(slot_id),
                "param2": str(self.city_id),
                "paytype": str(pt),
                "_": "",
            },
        ) or {}
        self._c77_cache = None
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        if ret != RET_OK:
            err_map = {
                4: "Mã thành trì không hợp lệ",
                8: "Vị trí công trình không hợp lệ",
                30: "Không đủ Coin (元宝)",
                31: "Không có nhà đang xây ở slot này",
                45: "Không đủ Ngân Bảo (点券)",
                999: "Lỗi không xác định",
            }
            msg = err_map.get(ret, f"Lỗi mã {ret}")
            self._log(f"❌ Tăng tốc thất bại cho slot {slot_id}: {msg}")
            return False
        return True

    def process_speedup(self) -> int:
        """Tăng tốc các công trình đang thi công theo cơ chế chuẩn ZBuild.

        Mỗi lần gọi OPT.ashx?id=69 giảm 50% thời gian thi công còn lại.
        Vòng lặp giảm thời gian cho mỗi slot chạy cho đến khi thời gian còn lại
        < target_hours * 3600 (mặc định 1h = 3600s) hoặc tối đa 10 lần.
        """
        target_seconds = int(self.speedup_hours * 3600)
        active_slots = self.get_active_upgrade_slots()
        if not active_slots:
            return 0

        total_speedups = 0
        for item in active_slots:
            if isinstance(item, (list, tuple)):
                if len(item) < 1:
                    continue
                try:
                    slot = int(item[0])
                except (ValueError, TypeError):
                    continue
                time_left = parse_remaining_seconds(item[4]) if len(item) >= 5 else 0
            elif isinstance(item, dict):
                try:
                    slot = int(item.get("slot") or item.get("pid") or 1)
                except (ValueError, TypeError):
                    continue
                raw_time = item.get("time_left") if item.get("time_left") is not None else item.get("time")
                time_left = parse_remaining_seconds(raw_time)
            else:
                continue

            if time_left <= target_seconds:
                self._log(f"   ✓ Slot {slot}: còn {time_left // 60} phút (< {self.speedup_hours:g}h), không cần tăng tốc")
                continue

            self._log(f"   🔄 Slot {slot}: còn {time_left // 60} phút, cần giảm xuống < {self.speedup_hours:g}h")
            current_time = time_left
            speedup_count = 0

            while current_time > target_seconds and speedup_count < 10:
                success = self.speedup_slot(slot)
                if not success:
                    self._log(f"      ❌ Tăng tốc thất bại ở lần {speedup_count + 1}")
                    break
                speedup_count += 1
                current_time //= 2
                self._log(f"      ✅ Lần {speedup_count}: còn {current_time // 60} phút")

            if speedup_count > 0:
                self._log(f"   ✅ Đã tăng tốc {speedup_count} lần cho slot {slot}")
                total_speedups += speedup_count

        if total_speedups > 0:
            self._c77_cache = None

        return total_speedups

    def _order_plans_by_type_even(
        self, plans_list: list[BuildingPlan], real_buildings: dict[int, dict]
    ) -> list[BuildingPlan]:
        """Sắp xếp danh sách thi công bảo toàn thứ tự Loại công trình, trong đó các ô cùng loại được nâng đồng đều."""
        groups: dict[int, list[BuildingPlan]] = {}
        for p in plans_list:
            groups.setdefault(p.gid, []).append(p)

        ordered = []
        for gid, group_plans in groups.items():
            upgrades = []
            downgrades = []
            completed = []
            for p in group_plans:
                cur = real_buildings.get(p.pid, {"gid": p.gid, "level": 0})
                cur_lvl = cur.get("level", 0)
                if cur_lvl < p.target_level:
                    upgrades.append(p)
                elif cur_lvl > p.target_level:
                    downgrades.append(p)
                else:
                    completed.append(p)
            # Cùng loại: nâng các ô cấp thấp hơn lên trước để đồng đều
            upgrades.sort(key=lambda p: real_buildings.get(p.pid, {}).get("level", 0))
            downgrades.sort(key=lambda p: real_buildings.get(p.pid, {}).get("level", 0), reverse=True)
            ordered.extend(upgrades + downgrades + completed)
        return ordered

    def _open_one_resource_box(self) -> bool:
        """Mở đúng 1 đạo cụ tài nguyên qua Common.ashx?id=48 khi toàn bộ công trình thiếu tài nguyên."""
        if getattr(self, "_storage_full", False):
            self._log("⚠️ Kho tài nguyên đã đầy sức chứa tối đa, ngừng mở thêm đạo cụ.")
            return False

        # 1. Chuyển ngữ cảnh về thành trì đang thi công
        self.gateway.call("City.ashx", 50, {"tid": str(self.city_id), "_": ""})

        boxes_to_try = [self.box_id]
        if self.auto_fallback_box:
            for bid in DEFAULT_FALLBACK_BOX_ORDER:
                if bid not in boxes_to_try:
                    boxes_to_try.append(bid)

        for cur_box_id in boxes_to_try:
            box_label = RESOURCE_BOX_NAMES.get(cur_box_id, f"Rương {cur_box_id}")
            resp = self.gateway.call("Common.ashx", 48, {"lBoxID": str(cur_box_id), "_": ""}) or {}
            ret = resp.get("ret", RET_OK)
            if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
                raise CaptchaRequired()

            if ret == 10014:
                self._log(f"ℹ️ Đã hết {box_label} trong túi đồ (mã 10014).")
                continue

            if ret != RET_OK:
                self._log(f"⚠️ Mở {box_label} thất bại (mã {ret}).")
                continue

            self._log(f"🎁 Đã mở thành công 1 {box_label} (toàn bộ công trình thiếu tài nguyên).")

            # Kiểm tra sức chứa tối đa của kho tài nguyên để tránh tràn kho ở các lần tiếp theo
            res_resp = self.gateway.call("City.ashx", 20, {"tid": str(self.city_id), "_": ""}) or {}
            res_data = res_resp.get("data", {})
            if res_data:
                max_storage = int(res_data.get("max_storage", 0))
                if max_storage > 0:
                    is_storage_full = all(
                        int(res_data.get(k, 0)) >= max_storage
                        for k in ("wood", "stone", "iron", "food")
                    )
                    if is_storage_full:
                        self._log("⚠️ Kho tài nguyên đã đầy sức chứa tối đa, ngừng mở thêm đạo cụ.")
                        self._storage_full = True
            return True

        self._log("⚠️ Không còn rương tài nguyên nào trong túi đồ có thể mở.")
        return False

    def run_once(self) -> str:
        self._c77_cache = None
        self._storage_full = False
        # 1. Kích hoạt Boost nếu được cấu hình
        if self.auto_boost:
            self.check_and_activate_boost()

        # 2. An dân nếu sĩ khí thấp
        if self.auto_comfort:
            self.check_and_comfort_city()

        # 3. Tự động tăng tốc các slot đang thi công theo cơ chế ZBuild
        if self.auto_speedup:
            self.process_speedup()

        # 4. Kiểm tra các slot nâng cấp đang bận
        active_slots = self.get_active_upgrade_slots()
        if len(active_slots) >= self.max_slots:
            if not getattr(self, "_synced_once", False):
                try:
                    rb = self.get_real_buildings()
                    self._synced_once = True
                    if self.on_sync_data:
                        self.on_sync_data(self.city_id, {k: dict(v) for k, v in rb.items()})
                except Exception:
                    pass
            return "slots_busy"

        available_slots = self.max_slots - len(active_slots)
        if available_slots <= 0:
            if not getattr(self, "_synced_once", False):
                try:
                    rb = self.get_real_buildings()
                    self._synced_once = True
                    if self.on_sync_data:
                        self.on_sync_data(self.city_id, {k: dict(v) for k, v in rb.items()})
                except Exception:
                    pass
            return "slots_busy"

        # 4. Lấy danh sách công trình thực tế
        real_buildings = self.get_real_buildings()
        self._synced_once = True
        if self.on_sync_data:
            try:
                self.on_sync_data(self.city_id, {k: dict(v) for k, v in real_buildings.items()})
            except Exception:
                pass

        # Trích xuất danh sách pid đang được nâng cấp dở
        busy_pids = set()
        for s in active_slots:
            if isinstance(s, (list, tuple)) and len(s) > 0:
                try:
                    busy_pids.add(int(s[0]))
                except (ValueError, TypeError):
                    pass
            elif isinstance(s, dict):
                if "pid" in s:
                    busy_pids.add(int(s["pid"]))
                elif "bid" in s:
                    busy_pids.add(int(s["bid"]))

        # 5. Duyệt danh sách quy hoạch và gửi lệnh nâng/hạ cấp cho tới khi lấp đầy available_slots
        processed_count = 0
        has_uncompleted = False
        has_eligible_candidate = False
        last_error = None
        opened_boxes_count = 0

        # Sắp xếp danh sách duyệt: Công trình bình thường duyệt trước, các ô lỗi 261/245 kiểm tra sau cùng
        normal_plans = [p for p in self.plans if p.pid not in self.deferred_pids]
        deferred_plans = [p for p in self.plans if p.pid in self.deferred_pids]

        if self.even_upgrade:
            # Cân bằng cấp độ toàn thành phố (toàn cục)
            def sort_even(plans_list):
                upgrades = []
                downgrades = []
                for p in plans_list:
                    cur = real_buildings.get(p.pid, {"gid": p.gid, "level": 0})
                    if cur["level"] < p.target_level:
                        upgrades.append(p)
                    else:
                        downgrades.append(p)
                upgrades.sort(key=lambda p: real_buildings.get(p.pid, {}).get("level", 0))
                return upgrades + downgrades

            normal_plans = sort_even(normal_plans)
            deferred_plans = sort_even(deferred_plans)
        else:
            # Mặc định: Bảo toàn thứ tự Loại công trình, nâng đồng đều nội bộ loại (ADR-0016)
            normal_plans = self._order_plans_by_type_even(normal_plans, real_buildings)
            deferred_plans = self._order_plans_by_type_even(deferred_plans, real_buildings)

        ordered_plans = normal_plans + deferred_plans

        while processed_count < available_slots:
            starved_pids = set()
            built_any_in_pass = False

            for plan in ordered_plans:
                if not getattr(plan, "enabled", True):
                    continue
                cur = real_buildings.get(plan.pid, {"gid": plan.gid, "level": 0})
                cur_lvl = cur["level"]
                if cur_lvl == plan.target_level:
                    self.deferred_pids.discard(plan.pid)
                    continue

                has_uncompleted = True

                if plan.pid in busy_pids:
                    continue

                if plan.pid in self.skipped_pids:
                    continue

                if plan.pid in starved_pids:
                    continue

                has_eligible_candidate = True
                action_type = 1 if cur_lvl < plan.target_level else 2
                bname = plan.name or BUILDING_NAMES.get(plan.gid, f"Công trình {plan.gid}")
                action_verb = "nâng cấp" if action_type == 1 else "hạ cấp"
                next_lvl = cur_lvl + 1 if action_type == 1 else cur_lvl - 1
                icon = "🏗️" if action_type == 1 else "🏚️"

                resp = self.gateway.call(
                    "OPT.ashx",
                    65,
                    {
                        "pid": str(plan.pid),
                        "gid": str(plan.gid),
                        "type": str(action_type),
                        "tid": str(self.city_id),
                        "_": "",
                    },
                ) or {}
                ret = resp.get("ret", RET_OK)
                if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
                    raise CaptchaRequired()

                if ret == RET_OK:
                    if plan.pid in self.deferred_pids:
                        self._log(f"🎉 Slot {plan.pid} ({bname}) đã được gỡ hoãn và {action_verb} thành công!")
                        self.deferred_pids.discard(plan.pid)
                    self._log(f"{icon} Đang {action_verb} slot {plan.pid} ({bname}) từ cấp {cur_lvl} {'lên' if action_type == 1 else 'xuống'} {next_lvl}")
                    if self.auto_speedup:
                        self._c77_cache = None
                        self.process_speedup()
                    processed_count += 1
                    busy_pids.add(plan.pid)
                    built_any_in_pass = True
                    real_buildings[plan.pid] = {"gid": plan.gid, "level": next_lvl, "name": bname}
                    if processed_count >= available_slots:
                        break
                elif ret == 261:
                    self._log(f"⚠️ {action_verb.capitalize()} slot {plan.pid} ({bname}) bị chặn (mã 261). Bỏ qua, nâng cấp công trình khác (hoãn kiểm tra cuối ở vòng sau)...")
                    self.skipped_pids.add(plan.pid)
                    self.deferred_pids.add(plan.pid)
                    if not last_error:
                        last_error = "blocked_error_261"
                    continue
                elif ret == 245:
                    self._log(f"⚠️ Chưa đủ điều kiện tiên quyết để {action_verb} slot {plan.pid} ({bname}) (mã 245). Bỏ qua, nâng cấp công trình khác (hoãn kiểm tra cuối ở vòng sau)...")
                    self.skipped_pids.add(plan.pid)
                    self.deferred_pids.add(plan.pid)
                    if not last_error:
                        last_error = "prerequisites_not_met"
                    continue
                elif ret == 36:
                    self._log(f"⚠️ Không thể hạ cấp slot {plan.pid} ({bname}) (đã đến cấp tối thiểu)")
                    self.skipped_pids.add(plan.pid)
                    if not last_error:
                        last_error = "cannot_downgrade_min_level"
                    continue
                elif ret in (32, 37):
                    self._log(f"ℹ️ Không đủ tài nguyên để {action_verb} slot {plan.pid} ({bname}), chuyển qua công trình khác...")
                    starved_pids.add(plan.pid)
                    if not last_error:
                        last_error = "insufficient_resources"
                    continue
                else:
                    self._log(f"❌ {action_verb.capitalize()} slot {plan.pid} ({bname}) thất bại (mã {ret}). Bỏ qua, nâng cấp công trình khác...")
                    self.skipped_pids.add(plan.pid)
                    if not last_error:
                        last_error = f"{'upgrade' if action_type == 1 else 'downgrade'}_failed:{ret}"
                    continue

            if processed_count >= available_slots:
                break

            if built_any_in_pass:
                continue

            if starved_pids:
                if self.auto_open_box:
                    if opened_boxes_count < self.max_boxes_per_round:
                        opened = self._open_one_resource_box()
                        if opened:
                            opened_boxes_count += 1
                            continue
                        else:
                            break
                    else:
                        self._log(f"⚠️ Đã đạt giới hạn mở tối đa {self.max_boxes_per_round} rương/đợt mà vẫn chưa đủ tài nguyên.")
                        break
                else:
                    self._log("⚠️ Toàn bộ công trình khả dụng đều thiếu tài nguyên (chế độ tự mở rương đang Tắt).")
                    break
            else:
                break

        # 6. Tổng kết kết quả sau vòng lặp
        if processed_count > 0:
            self.skipped_pids.clear()
            return "upgrading"

        if not has_uncompleted:
            return "all_buildings_completed"

        if not has_eligible_candidate and self.skipped_pids:
            self.skipped_pids.clear()
            if not last_error:
                last_error = "all_eligible_buildings_skipped"

        if last_error:
            return last_error

        return "slots_busy"

