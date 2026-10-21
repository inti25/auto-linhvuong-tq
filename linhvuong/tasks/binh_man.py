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


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Khoảng cách ô lưới chuẩn trong bản đồ Linh Vương: max(|dx|, |dy|)."""
    return max(abs(x1 - x2), abs(y1 - y2))


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

    def needs_return(self, remaining_percent: float) -> bool:
        """Binh lực hoặc thể lực còn lại (%) dưới ngưỡng thì cần rút về thành."""
        return remaining_percent < self.return_threshold

    def step_towards(self, target_x: int, target_y: int, step_limit: Optional[int] = None) -> tuple[int, int]:
        """Tính tọa độ bước dời kế tiếp hướng về mục tiêu, giới hạn bởi step_limit."""
        cx, cy = self.origin
        dx = target_x - cx
        dy = target_y - cy
        limit = step_limit if step_limit is not None else self.max_step

        def clamp(val: int, lim: int) -> int:
            return max(-lim, min(lim, val))

        sx = cx + clamp(dx, limit)
        sy = cy + clamp(dy, limit)
        return sx, sy

    def move_camp(self, dest_x: int, dest_y: int) -> tuple[bool, int, str]:
        """Gửi lệnh dời Trại Di Chuyển qua Common.ashx?id=55."""
        if not self.camp_id:
            self.origin = (dest_x, dest_y)
            return True, 0, "ok"

        payload = {
            "lDestX": str(dest_x),
            "lDestY": str(dest_y),
            "lTentID": str(self.camp_id),
            "_": "",
        }
        resp = self.ctx.gateway.call("Common.ashx", 55, payload) or {}
        ret = resp.get("ret", RET_OK)

        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        if ret == RET_OK:
            frozen_time = int(resp.get("frozen", 0))
            self.origin = (dest_x, dest_y)
            if frozen_time > 0:
                self.sleep_fn(frozen_time)
            return True, frozen_time, "ok"

        if ret == 39:
            # ret=39: Đã có công trình hoặc vật cản tại tọa độ đích
            return False, 0, "obstacle"

        if ret == 42:
            # ret=42: Đang trong thời gian đóng băng
            return False, 0, "frozen"

        return False, 0, f"error:{ret}"

    def advance_camp_to_target(self, target: Target) -> bool:
        """Dời Trại Di Chuyển từng bước hướng tới mục tiêu cho đến khi khoảng cách <= 2 ô."""
        while chebyshev_distance(self.origin[0], self.origin[1], target.x, target.y) > 2:
            # 1. Thử bước nhảy lớn nhất (max_step)
            sx, sy = self.step_towards(target.x, target.y, self.max_step)
            success, _, reason = self.move_camp(sx, sy)

            if not success and reason == "obstacle":
                # Thử lùi về bước nhỏ hơn 1 ô (backoff)
                sx, sy = self.step_towards(target.x, target.y, max(1, self.max_step - 1))
                success, _, reason = self.move_camp(sx, sy)

            if not success:
                self.ctx.notify(f"❌ Dời trại tới ({target.x}, {target.y}) thất bại: {reason}")
                return False

        return True

    def retreat_to_safety(self) -> None:
        """Hồi binh về thành mẹ để trị thương và bổ sung quân lực."""
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

    def run_once(self, remaining_percent: float = 100.0) -> str:
        # Kiểm tra ngưỡng an toàn trước tiên
        if self.needs_return(remaining_percent):
            self.retreat_to_safety()
            return "retreated_below_threshold"

        target = self.ctx.scanner.find_nearest(
            *self.origin,
            self.radius,
            self.man_types,
            skip_capital_radius=self.skip_capital_radius,
        )
        if target is None:
            return "no_target"

        # Nếu đang ở Trại Di Chuyển và mục tiêu xa hơn 2 ô -> Dời trại từng bước
        if self.camp_id and chebyshev_distance(self.origin[0], self.origin[1], target.x, target.y) > 2:
            reached = self.advance_camp_to_target(target)
            if not reached:
                return "relocate_failed"

        result = attack(self.ctx, target, self.generals)
        return result
