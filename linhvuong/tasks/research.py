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

TECH_NAMES = {
    1: "种植技巧 - làm thực",
    2: "冶炼技巧 - rèn sắt",
    3: "挖掘技巧 - đào đá",
    4: "伐木技巧 - chặt gỗ",
    5: "谋略技巧 - mưu lược",
    6: "侦察技巧 - trinh sát",
    7: "统帅技巧 - thống soái",
    8: "阵法技巧 - trận pháp",
    9: "拔营技巧 - bạt doanh",
    10: "储藏技巧 - trữ lương",
    11: "城建技巧 - xây thành",
    12: "战马驯服术 - thuần hóa ngựa",
    13: "盔甲制造术 - chế tạo giáp",
    14: "弓弩制造术 - chế tạo cung nỏ",
    15: "武器制造术 - chế tạo vũ khí",
    16: "弓手行军术 - hành quân cung thủ",
    17: "弓手协作力 - phối hợp cung thủ",
    18: "弓手防御术 - phòng ngự cung thủ",
    19: "弓手熟练度 - thành thục cung thủ",
    20: "骑兵行军术 - hành quân kỵ binh",
    21: "骑兵协作力 - phối hợp kỵ binh",
    22: "骑兵防御术 - phòng ngự kỵ binh",
    23: "骑兵熟练度 - thành thục kỵ binh",
    24: "步兵行军术 - hành quân bộ binh",
    25: "步兵协作力 - phối hợp bộ binh",
    26: "步兵防御术 - phòng ngự bộ binh",
    27: "步兵熟练度 - thành thục bộ binh",
    28: "抚民技巧 - an ủi dân",
    29: "城防技巧 - xây tường thành",
}


@dataclass
class TechPlan:
    tech_id: int  # Mã kỹ thuật (1..29)
    target_level: int  # Cấp độ đích (1..30)
    name: str = ""
    enabled: bool = True

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
        even_research: bool = False,
        notify: Callable[[str], None] = print,
        on_sync_data: Optional[Callable[[int, dict[int, int], Optional[tuple]], None]] = None,
    ):
        self.gateway = gateway
        self.city_id = city_id
        self.plans = plans
        self.auto_art_of_war = auto_art_of_war
        self.even_research = even_research
        self.notify = notify
        self.on_sync_data = on_sync_data
        self._cached_levels: dict[int, int] = {}
        self._synced_once: bool = False

    def is_research_ongoing(self) -> tuple[bool, Optional[int]]:
        """Kiểm tra xem hiện tại có công nghệ nào đang được nghiên cứu không qua City.ashx?id=37."""
        resp = self.gateway.call("City.ashx", 37, {"ttid": "0", "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        tech_info = resp.get("tech")
        # Hỗ trợ dạng mảng từ server thật: [tech_id, cur_level, time_left]
        if isinstance(tech_info, (list, tuple)) and len(tech_info) > 0:
            try:
                tid = int(tech_info[0])
                if tid > 0:
                    return True, tid
            except (ValueError, TypeError):
                pass
        # Hỗ trợ dạng dict từ mock / unit test
        elif isinstance(tech_info, dict):
            tid = tech_info.get("techid") or tech_info.get("id") or 0
            if int(tid) > 0:
                return True, int(tid)

        return False, None

    def get_university_pid(self) -> Optional[int]:
        """Tìm vị trí ô đất (pid) của Viện Đại Học (Đại Học Điện, gid=6) trong thành."""
        resp = self.gateway.call("City.ashx", 5, {"tid": str(self.city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        buildings = resp.get("infos") or resp.get("buildings") or resp.get("build") or []
        for b in buildings:
            if isinstance(b, (list, tuple)) and len(b) >= 2:
                try:
                    if int(b[1]) == 6:
                        return int(b[0])
                except (ValueError, TypeError):
                    pass
            elif isinstance(b, dict):
                if int(b.get("gid", 0)) == 6:
                    return int(b.get("pid", 0))
        return None

    def get_current_tech_levels(self) -> dict[int, int]:
        """Lấy cấp độ hiện tại của 29 kỹ thuật tại viện Đại Học qua Build.ashx?id=2."""
        # Chuyển focus thành thị trước khi đọc kiến trúc (bắt buộc trên server game thật)
        self.gateway.call("City.ashx", 50, {"tid": str(self.city_id), "_": ""})

        univ_pid = self.get_university_pid()
        if univ_pid is None:
            univ_pid = 6  # Fallback cho mock/test

        payload = {
            "pid": str(univ_pid),
            "gid": "6",
            "tab": "1",
            "tid": str(self.city_id),
            "_": "",
        }
        resp = self.gateway.call("Build.ashx", 2, payload) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        if ret != RET_OK:
            self.notify(f"⚠️ Thành ID={self.city_id} không lấy được kỹ thuật (mã {ret}, kiểm tra lại Viện Đại Học).")
            return {}

        levels_map = {}
        for item in resp.get("list", []):
            if isinstance(item, dict):
                tid = int(item.get("id", 0))
                lvl = int(item.get("level", 0))
                levels_map[tid] = lvl
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                try:
                    tid = int(item[0])
                    lvl = int(item[2])
                    levels_map[tid] = lvl
                except (ValueError, TypeError):
                    pass
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
        tech_status = (is_busy, current_tech_id) if is_busy else None

        if is_busy:
            # Nếu bận nhưng chưa đọc cấp độ lần nào, đọc 1 lần để UI có cấp độ khởi tạo
            if not getattr(self, "_synced_once", False):
                try:
                    lvls = self.get_current_tech_levels()
                    if lvls:
                        self._cached_levels = lvls
                        self._synced_once = True
                        if self.on_sync_data:
                            self.on_sync_data(self.city_id, lvls, tech_status)
                except Exception:
                    pass
            elif self.on_sync_data and getattr(self, "_cached_levels", None):
                try:
                    self.on_sync_data(self.city_id, self._cached_levels, tech_status)
                except Exception:
                    pass

            if self.auto_art_of_war:
                self.use_art_of_war()
                return "art_of_war_used"
            return "research_busy"

        # 2. Lấy cấp độ các kỹ thuật hiện tại
        current_levels = self.get_current_tech_levels()
        if not current_levels:
            self.notify(f"⚠️ Không đọc được thông tin kỹ thuật từ thành ID={self.city_id} (kiểm tra lại Viện Đại Học).")
            return "tech_read_failed"

        self._cached_levels = current_levels
        self._synced_once = True
        if self.on_sync_data:
            try:
                self.on_sync_data(self.city_id, current_levels, tech_status)
            except Exception:
                pass

        # 3. Lọc theo thứ tự ưu tiên các kỹ thuật chưa đạt cấp mục tiêu
        eligible_plans = []
        for plan in self.plans:
            if not getattr(plan, "enabled", True):
                continue
            cur_lvl = current_levels.get(plan.tech_id, 0)
            if cur_lvl < plan.target_level:
                eligible_plans.append((plan, cur_lvl))

        if self.even_research:
            # Sắp xếp ổn định (stable sort): cấp độ hiện tại thấp lên cao
            eligible_plans.sort(key=lambda item: item[1])

        if not eligible_plans:
            return "all_techs_completed"

        # 4. Chuyển thành thị focus về Thành Nghiên Cứu (City.ashx?id=50)
        self.gateway.call("City.ashx", 50, {"tid": str(self.city_id), "_": ""})

        # 5. Gửi lệnh nghiên cứu kỹ thuật qua OPT.ashx?id=44, tự động bỏ qua nếu mã 245/261
        last_ret = RET_OK
        for target_tech, current_level in eligible_plans:
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
            last_ret = ret
            if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
                raise CaptchaRequired()

            if ret == RET_OK:
                self.notify(f"🔬 Bắt đầu nghiên cứu: {target_tech.name} (từ cấp {current_level} lên {current_level + 1})")
                if self.auto_art_of_war:
                    self.use_art_of_war()
                return "researching"

            if ret == 90:
                self.notify("⚠️ Viện Đại Học hiện đang bận nghiên cứu kỹ thuật khác.")
                return "research_busy"

            if ret in (245, 261):
                reason = "chưa đủ điều kiện tiên quyết" if ret == 245 else "bị chặn"
                self.notify(f"⚠️ {target_tech.name} {reason} (mã {ret}). Bỏ qua, thử kỹ thuật tiếp theo...")
                continue

            if ret in (32, 37):
                self.notify(f"⚠️ Không đủ tài nguyên để nghiên cứu {target_tech.name}")
                return "insufficient_resources"

            self.notify(f"❌ Nghiên cứu {target_tech.name} thất bại (mã {ret})")
            return f"research_failed:{ret}"

        if last_ret in (245, 261):
            return "prerequisites_not_met" if last_ret == 245 else f"blocked_error_{last_ret}"
        return f"research_failed:{last_ret}"
