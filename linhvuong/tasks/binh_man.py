"""Bình Man: Tự động quét và tấn công Man quanh thành hoặc Trại Di Chuyển.

Reverse engineered chính xác từ ZMan.exe:
- Quét tìm Man trong bán kính quanh thành hoặc Trại Di Chuyển.
- Khi sử dụng Trại Di Chuyển (camp_id > 0):
  1. Nếu cự ly tới mục tiêu > 2 ô, tự động dời Trại từng bước: Common.ashx?id=55 (lDestX, lDestY, lTentID).
  2. Bắt lỗi ret=39 (vướng vật cản/địa hình): tự lùi bước nhảy (backoff) tìm ô trống phụ cận.
  3. Sau mỗi bước dời trại thành công (ret=0), đếm lùi thời gian đóng băng (frozen_time).
  4. Khi cự ly <= 2 ô, khóa mục tiêu và xuất kích tấn công: OPT.ashx?id=53.
- Ngưỡng An Toàn (Return Threshold):
  Khi quân số hoặc thể lực rơi xuống dưới ngưỡng quy định:
  1. Rút tướng về thành mẹ: OPT.ashx?id=50.
  2. Trị thương danh tướng: OPT.ashx?id=31.
  3. Chiêu mộ thêm tân binh: OPT.ashx?id=41.
  4. Phối quân vào đạo: OPT.ashx?id=6.
  5. Tái xuất quân ra Trại: OPT.ashx?id=50.
"""

import math
import time
from typing import Callable, Optional

from ..scan import Target
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired, TaskContext, attack
from .di_trai import DiTrai, chebyshev_distance


MODE_CAMP = 1  # Chế độ 1: Sử dụng Doanh trại di chuyển đến cạnh Man
MODE_CITY = 2  # Chế độ 2: Xuất quân thẳng từ Thành

MAN_TARGET_OPTIONS: list[tuple[int, str]] = [
    (301, "Vong Linh (ID 301)"),
    (1, "Cấp 1 - Uy Quốc"),
    (2, "Cấp 2 - Tiên Ti"),
    (3, "Cấp 3 - Ô Hoàn"),
    (4, "Cấp 4 - Sơn Việt"),
    (5, "Cấp 5 - Khương Để"),
    (6, "Cấp 6 - Mạnh Hoạch"),
    (7, "Cấp 7 - Hung Nô"),
    (8, "Cấp 8 - Đột Quyết"),
    (9, "Cấp 9 - Long Phi"),
    (10, "Cấp 10 - Hổ Báo Kỵ"),
]


class BinhMan:
    def __init__(
        self,
        ctx: TaskContext,
        generals: list[int],
        origin: tuple[int, int],
        radius: int,
        man_types: list[int],
        camp_id: Optional[int] = None,
        parent_city_id: Optional[int] = None,
        return_threshold: int = 0,
        max_step: int = 2,
        skip_capital_radius: int = 0,
        auto_recover: bool = False,
        sleep_fn: Callable[[float], None] = time.sleep,
        mode: Optional[int] = None,
        city_id: Optional[int] = None,
        check_idle: bool = True,
    ):
        self.ctx = ctx
        self.generals = generals
        self.origin = origin
        self.radius = radius
        self.man_types = man_types
        self.camp_id = camp_id
        self.parent_city_id = parent_city_id
        self.return_threshold = return_threshold
        self.max_step = max_step
        self.skip_capital_radius = skip_capital_radius
        self.auto_recover = auto_recover
        self.sleep_fn = sleep_fn
        self.city_id = city_id or parent_city_id
        self.check_idle = check_idle

        # Tự động suy ra mode nếu không chỉ định: có camp_id là Chế độ 1, không có là Chế độ 2
        if mode is not None:
            self.mode = mode
        else:
            self.mode = MODE_CAMP if self.camp_id else MODE_CITY

    def needs_return(self, remaining_percent: float) -> bool:
        """Binh lực hoặc thể lực còn lại (%) dưới ngưỡng thì cần rút về thành."""
        return remaining_percent < self.return_threshold

    def check_generals_idle(self) -> bool:
        """Kiểm tra toàn bộ võ tướng có đang rảnh rỗi (status == 0) hay không."""
        if not self.generals:
            return True
        resp = self.ctx.gateway.call("Common.ashx", 32, {"type": "2", "_": ""}) or {}
        if not resp or "list" not in resp:
            return True

        for entry in resp.get("list", []):
            g_entries = entry[4] if len(entry) > 4 else []
            for g in g_entries:
                try:
                    gid = int(g[0])
                except (ValueError, IndexError, TypeError):
                    continue
                if gid in self.generals:
                    status = int(g[5]) if len(g) > 5 else 0
                    if status != 0:
                        return False
        return True

    def step_towards(self, target_x: int, target_y: int, step_limit: Optional[int] = None) -> tuple[int, int]:
        """Tính tọa độ bước dời kế tiếp hướng về mục tiêu, giới hạn bởi step_limit."""
        mover = DiTrai(
            ctx=self.ctx,
            camp_id=self.camp_id or 0,
            origin=self.origin,
            destination=(target_x, target_y),
            max_step=self.max_step,
            sleep_fn=self.sleep_fn,
        )
        return mover.step_towards(target_x, target_y, step_limit)

    def move_camp(self, dest_x: int, dest_y: int) -> tuple[bool, int, str]:
        """Gửi lệnh dời Trại Di Chuyển qua Common.ashx?id=55."""
        if not self.camp_id:
            self.origin = (dest_x, dest_y)
            return True, 0, "ok"

        mover = DiTrai(
            ctx=self.ctx,
            camp_id=self.camp_id,
            origin=self.origin,
            destination=(dest_x, dest_y),
            max_step=self.max_step,
            sleep_fn=self.sleep_fn,
        )
        success, frozen, reason = mover.move_step(dest_x, dest_y)
        if success:
            self.origin = mover.origin
        return success, frozen, reason

    def advance_camp_to_target(self, target: Target) -> bool:
        """Dời Trại Di Chuyển từng bước hướng tới mục tiêu cho đến khi khoảng cách <= 2 ô."""
        if not self.camp_id:
            return True

        mover = DiTrai(
            ctx=self.ctx,
            camp_id=self.camp_id,
            origin=self.origin,
            destination=(target.x, target.y),
            max_step=self.max_step,
            sleep_fn=self.sleep_fn,
            stop_at_distance=2,
        )
        res = mover.advance_to_destination()
        self.origin = mover.origin
        return res in ("arrived", "stopped")

    def retreat_to_safety(self) -> None:
        """Hồi binh về thành mẹ để trị thương và bổ sung quân lực (Chế độ 1 - Doanh trại)."""
        if not self.parent_city_id or not self.camp_id:
            return

        for gid in self.generals:
            # 1. Điều tướng về thành mẹ (OPT.ashx?id=50)
            self.ctx.gateway.call(
                "OPT.ashx",
                50,
                {
                    "lCityID": str(self.camp_id),
                    "lGeneralID": str(gid),
                    "lDestID": str(self.parent_city_id),
                    "_": "",
                },
            )
            # 2. Trị thương (OPT.ashx?id=31)
            self.ctx.gateway.call(
                "OPT.ashx",
                31,
                {"lCityTentID": str(self.parent_city_id), "lGeneralID": str(gid), "_": ""},
            )
            # 3. Mua tân binh và bổ sung nếu cần (OPT.ashx?id=41, id=6)
            self.ctx.gateway.call(
                "OPT.ashx",
                41,
                {"lAmount": "1000", "tid": str(self.parent_city_id), "_": ""},
            )
            self.ctx.gateway.call(
                "OPT.ashx",
                6,
                {
                    "lGeneralID": str(gid),
                    "lSoldierType": "1",
                    "lAmount": "1000",
                    "tid": str(self.parent_city_id),
                    "_": "",
                },
            )
            # 4. Tái phái tướng trở lại Trại (OPT.ashx?id=50)
            self.ctx.gateway.call(
                "OPT.ashx",
                50,
                {
                    "lCityID": str(self.parent_city_id),
                    "lGeneralID": str(gid),
                    "lDestID": str(self.camp_id),
                    "_": "",
                },
            )

    def recover_in_city(self) -> None:
        """Trị thương và bổ sung quân tại chỗ trong Thành (Chế độ 2 - Xuất quân từ Thành)."""
        cid = self.city_id or self.parent_city_id or 0
        for gid in self.generals:
            # 1. Trị thương (OPT.ashx?id=31)
            self.ctx.gateway.call(
                "OPT.ashx",
                31,
                {"lCityTentID": str(cid), "lGeneralID": str(gid), "_": ""},
            )
            # 2. Chiêu mộ tân binh nếu cần (OPT.ashx?id=41)
            self.ctx.gateway.call(
                "OPT.ashx",
                41,
                {"lAmount": "1000", "tid": str(cid), "_": ""},
            )
            # 3. Biên chế quân vào đạo (OPT.ashx?id=6)
            self.ctx.gateway.call(
                "OPT.ashx",
                6,
                {
                    "lGeneralID": str(gid),
                    "lSoldierType": "1",
                    "lAmount": "1000",
                    "tid": str(cid),
                    "_": "",
                },
            )

    def run_once(self, remaining_percent: float = 100.0) -> str:
        # 1. Kiểm tra ngưỡng an toàn trước tiên
        if self.needs_return(remaining_percent):
            if self.mode == MODE_CAMP:
                self.retreat_to_safety()
                return "retreated_below_threshold"
            else:
                self.recover_in_city()
                return "recovered_in_city"

        # 2. Kiểm tra tướng rảnh rỗi (Idle Check) nếu bật check_idle
        if self.check_idle and (self.city_id or self.camp_id):
            if not self.check_generals_idle():
                if self.ctx.notify:
                    self.ctx.notify("⏳ Võ tướng đang bận hoặc hành quân trên đường, chờ hồi thành...")
                return "generals_busy"

        # 3. Quét tìm Man mục tiêu
        target = self.ctx.scanner.find_nearest(
            *self.origin,
            self.radius,
            self.man_types,
            skip_capital_radius=self.skip_capital_radius,
        )
        if target is None:
            return "no_target"

        # 4. Nếu ở Chế độ 1 (Doanh trại) và mục tiêu xa hơn 2 ô -> Dời trại từng bước
        if self.mode == MODE_CAMP and self.camp_id and chebyshev_distance(self.origin[0], self.origin[1], target.x, target.y) > 2:
            reached = self.advance_camp_to_target(target)
            if not reached:
                return "relocate_failed"

        # 5. Xuất quân tấn công (hỗ trợ chia nhiều đợt nếu > 3 tướng)
        result = attack(self.ctx, target, self.generals, sleep_fn=self.sleep_fn)
        return result

