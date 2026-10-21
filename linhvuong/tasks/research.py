"""Nhiệm vụ Nghiên Cứu 29 Kỹ Thuật Viện Đại Học.

Reverse engineered chính xác từ ZBuild.exe:
- Quản lý tiến trình nghiên cứu kỹ thuật:
  1. Kiểm tra trạng thái nghiên cứu: City.ashx?id=37 (ttid=0, KHÔNG cần đổi thành).
  2. Đọc danh sách cấp độ 29 công nghệ: Build.ashx?id=2 (pid=8, gid=1, tab=2, tid=research_city_id).
  3. Lọc theo thứ tự ưu tiên trong cấu hình: Tìm công nghệ có level < target_level.
  4. Chuyển focus về Thành Nghiên Cứu: City.ashx?id=50 (tid=research_city_id).
  5. Ra lệnh nghiên cứu: OPT.ashx?id=44 (techid, tid).
  6. Tự động dùng Binh Pháp tăng tốc hoàn thành tức thì nếu được bật: OPT.ashx?id=180.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from ..gateway import GatewayClient
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired

# 29 Công nghệ chuẩn viện Đại Học trong Linh Vương
TECH_NAMES = {
    1: "Làm thực",
    2: "Rèn sắt",
    3: "Đào đá",
    4: "Chặt gỗ",
    5: "Mưu lược",
    6: "Tường lũy",
    7: "Trận pháp",
    8: "Bạt doanh",
    9: "Thuần hóa ngựa",
    10: "Dẫn binh",
    11: "Do thám",
    12: "Y thuật",
    13: "Luyện giáp",
    14: "Rèn đao",
    15: "Chế nỏ",
    16: "Trọng giáp",
    17: "Kỵ binh giáo",
    18: "Kỵ xạ",
    19: "Chiến xa",
    20: "Ném đá",
    21: "Hành quân",
    22: "Hậu cần",
    23: "Thống ngự",
    24: "Công thành",
    25: "Thủ thành",
    26: "Độn giáp",
    27: "Tác chiến",
    28: "Trinh sát chuyên sâu",
    29: "Cấp dưỡng",
}


@dataclass
class TechPlan:
    tech_id: int  # Mã kỹ thuật (1..29)
    target_level: int  # Cấp độ đích (1..30)
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = TECH_NAMES.get(self.tech_id, f"Kỹ thuật {self.tech_id}")


class ResearchTask:
    def __init__(
        self,
        gateway: GatewayClient,
        city_id: int,
        plans: list[TechPlan],
        auto_art_of_war: bool = False,
        notify: Callable[[str], None] = print,
    ):
        self.gateway = gateway
        self.city_id = city_id
        self.plans = plans
        self.auto_art_of_war = auto_art_of_war
        self.notify = notify

    def is_research_ongoing(self) -> tuple[bool, Optional[int]]:
        """Kiểm tra xem hiện tại có công nghệ nào đang được nghiên cứu không qua City.ashx?id=37."""
        resp = self.gateway.call("City.ashx", 37, {"ttid": "0", "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        tech_info = resp.get("tech")
        if tech_info and isinstance(tech_info, dict) and tech_info.get("techid"):
            return True, int(tech_info["techid"])
        return False, None

    def get_current_tech_levels(self) -> dict[int, int]:
        """Lấy cấp độ hiện tại của 29 kỹ thuật tại viện Đại Học qua Build.ashx?id=2."""
        payload = {
            "pid": "8",
            "gid": "1",
            "tab": "2",
            "tid": str(self.city_id),
            "_": "",
        }
        resp = self.gateway.call("Build.ashx", 2, payload) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        levels_map = {}
        for item in resp.get("list", []):
            tid = int(item.get("id", 0))
            lvl = int(item.get("level", 0))
            levels_map[tid] = lvl
        return levels_map

    def use_art_of_war(self) -> bool:
        """Sử dụng Binh Pháp hoàn thành tức thì kỹ thuật qua OPT.ashx?id=180."""
        self.notify("📜 Sử dụng Binh Pháp tăng tốc kỹ thuật hoàn tất tức thì...")
        resp = self.gateway.call("OPT.ashx", 180, {"_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        return ret == RET_OK

    def run_once(self) -> str:
        # 1. Kiểm tra xem viện Đại Học có đang bận nghiên cứu không
        is_busy, current_tech_id = self.is_research_ongoing()
        if is_busy:
            if self.auto_art_of_war:
                self.use_art_of_war()
                return "art_of_war_used"
            return "research_busy"

        # 2. Lấy cấp độ các kỹ thuật hiện tại
        current_levels = self.get_current_tech_levels()

        # 3. Lọc theo thứ tự ưu tiên tìm kỹ thuật chưa đạt cấp mục tiêu
        target_tech: Optional[TechPlan] = None
        for plan in self.plans:
            cur_lvl = current_levels.get(plan.tech_id, 0)
            if cur_lvl < plan.target_level:
                target_tech = plan
                break

        if target_tech is None:
            return "all_techs_completed"

        # 4. Chuyển thành thị focus về Thành Nghiên Cứu (City.ashx?id=50)
        self.gateway.call("City.ashx", 50, {"tid": str(self.city_id), "_": ""})

        # 5. Gửi lệnh nghiên cứu kỹ thuật qua OPT.ashx?id=44
        resp_research = self.gateway.call(
            "OPT.ashx",
            44,
            {
                "techid": str(target_tech.tech_id),
                "tid": str(self.city_id),
                "_": "",
            },
        ) or {}
        ret = resp_research.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        if ret == RET_OK:
            self.notify(f"🔬 Bắt đầu nghiên cứu kỹ thuật: {target_tech.name} (ID: {target_tech.tech_id})")
            if self.auto_art_of_war:
                self.use_art_of_war()
            return "researching"

        if ret == 32:
            return "insufficient_resources"

        return f"research_failed:{ret}"
