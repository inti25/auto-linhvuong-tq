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

from dataclasses import dataclass
from typing import Callable, Optional

from ..gateway import GatewayClient
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired


BUILDING_NAMES = {
    1: "Thái Phủ",
    2: "Tường Lũy",
    3: "Kho Lương",
    4: "Doanh Trại",
    5: "Trường Luyện Binh",
    6: "Dịch Trạm",
    7: "Tiệm Rèn",
    8: "Viện Đại Học",
    9: "Thị Trường",
    10: "Chiêu Hiền Quán",
    11: "Thần Miếu",
    12: "Sứ Quán",
    13: "Thái Y Viện",
    14: "Quân Giới Phủ",
    15: "Hồng Kê Quán",
    16: "Nhà Dân",
    21: "Ruộng Lúa",
    22: "Xưởng Gỗ",
    23: "Mỏ Đá",
    24: "Mỏ Sắt",
}


@dataclass
class BuildingPlan:
    pid: int  # Vị trí ô đất trong thành (1..32)
    gid: int  # Loại công trình (1: Thái Phủ, 8: Đại Học, 21: Ruộng...)
    target_level: int  # Cấp độ mục tiêu cần đạt (1..33)
    name: str = ""
    enabled: bool = True

    def __post_init__(self):
        if not self.name:
            self.name = BUILDING_NAMES.get(self.gid, f"Công trình {self.gid}")


class BuildingTask:
    def __init__(
        self,
        gateway: GatewayClient,
        city_id: int,
        plans: list[BuildingPlan],
        max_slots: int = 1,
        auto_speedup: bool = False,
        paytype: int = 1,
        auto_comfort: bool = True,
        auto_boost: bool = False,
        notify: Callable[[str], None] = print,
    ):
        self.gateway = gateway
        self.city_id = city_id
        self.plans = plans
        self.max_slots = max_slots
        self.auto_speedup = auto_speedup
        self.paytype = paytype
        self.auto_comfort = auto_comfort
        self.auto_boost = auto_boost
        self.notify = notify

    def check_and_activate_boost(self) -> bool:
        """Kiểm tra thời gian tăng tốc xây dựng 20% (plus_finish), kích hoạt nếu hết hạn."""
        resp = self.gateway.call("Common.ashx", 77, {"cid": "0", "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        plus_finish = int(resp.get("plus_finish", 0))
        if plus_finish <= 0 and self.auto_boost:
            self.notify("⚡ Kích hoạt hiệu ứng tăng tốc xây dựng 20%...")
            boost_resp = self.gateway.call(
                "OPT.ashx",
                69,
                {"type": "3", "param1": "0", "param2": "0", "paytype": "2"},
            ) or {}
            return boost_resp.get("ret", RET_OK) == RET_OK
        return True

    def check_and_comfort_city(self) -> bool:
        """Kiểm tra sĩ khí / dân nộ, tự động Tế Trời An Dân nếu cần."""
        resp = self.gateway.call("City.ashx", 6, {"tid": str(self.city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        data = resp.get("data", {})
        morale = int(data.get("morale", 100))
        anger = int(data.get("anger", 0))

        if morale < 90 or anger > 0:
            self.notify(f"🕊️ Sĩ khí ({morale}%) thấp hoặc dân nộ ({anger}), tiến hành An Dân...")
            comfort_resp = self.gateway.call(
                "OPT.ashx",
                4,
                {"lType": "1", "tid": str(self.city_id), "_": ""},
            ) or {}
            return comfort_resp.get("ret", RET_OK) == RET_OK
        return True

    def get_active_upgrade_slots(self) -> list[dict]:
        """Lấy danh sách các slot đang nâng cấp dở trong thành."""
        resp = self.gateway.call("Common.ashx", 77, {"cid": str(self.city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        return resp.get("list", [])

    def get_real_buildings(self) -> dict[int, dict]:
        """Lấy danh sách công trình hiện có: {pid: {"gid": gid, "level": level}}."""
        resp = self.gateway.call("City.ashx", 5, {"tid": str(self.city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        buildings_map = {}
        for b in resp.get("buildings", []):
            pid = int(b.get("pid", 0))
            buildings_map[pid] = {
                "gid": int(b.get("gid", 0)),
                "level": int(b.get("level", 0)),
            }
        return buildings_map

    def speedup_slot(self, slot_id: int) -> bool:
        """Sử dụng vật phẩm tăng tốc xây dựng hoàn thành ngay lập tức."""
        resp = self.gateway.call(
            "OPT.ashx",
            69,
            {
                "type": "1",
                "param1": str(self.city_id),
                "param2": str(slot_id),
                "paytype": str(self.paytype),
                "_": "",
            },
        ) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        return ret == RET_OK

    def run_once(self) -> str:
        # 1. Kích hoạt Boost nếu được cấu hình
        if self.auto_boost:
            self.check_and_activate_boost()

        # 2. An dân nếu sĩ khí thấp
        if self.auto_comfort:
            self.check_and_comfort_city()

        # 3. Kiểm tra các slot nâng cấp đang bận
        active_slots = self.get_active_upgrade_slots()
        if len(active_slots) >= self.max_slots:
            if self.auto_speedup:
                for slot_info in active_slots:
                    slot_num = slot_info.get("slot", 1)
                    self.speedup_slot(slot_num)
                # Sau khi speedup xong, slot được giải phóng
            else:
                return "slots_busy"

        # 4. Lấy danh sách công trình thực tế
        real_buildings = self.get_real_buildings()

        # 5. Tìm công trình ưu tiên tiếp theo cần nâng cấp
        target_plan: Optional[BuildingPlan] = None
        for plan in self.plans:
            if not getattr(plan, "enabled", True):
                continue
            current = real_buildings.get(plan.pid, {"gid": plan.gid, "level": 0})
            if current["level"] < plan.target_level:
                target_plan = plan
                break

        if target_plan is None:
            return "all_buildings_completed"

        # 6. Kiểm tra tài nguyên khoáng sản
        res_resp = self.gateway.call("City.ashx", 20, {"tid": str(self.city_id), "_": ""}) or {}
        ret_res = res_resp.get("ret", RET_OK)
        if ret_res == 110 or ret_res == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        # Nếu thiếu tài nguyên (ret=32)
        if ret_res == 32:
            return "insufficient_resources"

        # 7. Gửi lệnh nâng cấp qua OPT.ashx?id=65
        upgrade_resp = self.gateway.call(
            "OPT.ashx",
            65,
            {
                "pid": str(target_plan.pid),
                "gid": str(target_plan.gid),
                "type": "1",
                "tid": str(self.city_id),
                "_": "",
            },
        ) or {}
        ret_up = upgrade_resp.get("ret", RET_OK)
        if ret_up == 110 or ret_up == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        if ret_up == RET_OK:
            self.notify(f"🏗️ Đang nâng cấp slot {target_plan.pid} (GID: {target_plan.gid}) lên cấp tiếp theo")
            if self.auto_speedup:
                self.speedup_slot(1)
            return "upgrading"

        if ret_up == 32:
            return "insufficient_resources"

        return f"upgrade_failed:{ret_up}"
