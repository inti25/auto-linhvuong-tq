"""Di Trại Độc Lập: Dời Doanh trại dã ngoại từng bước trên bản đồ tọa độ.

Reverse engineered và chuẩn hóa theo ZMan.exe & ADR-0014:
- Dời trại từng bước dựa trên phản hồi máy chủ qua API: Common.ashx?id=55 (lDestX, lDestY, lTentID).
- Bước nhảy tối đa: max_step = 2 (khoảng cách Chebyshev).
- Cơ chế Lách Vật Cản: khi máy chủ trả về ret=39 (vướng ô/chướng ngại vật), tự động dò bước 1 ô
  và các ô lân cận có khoảng cách tới đích nhỏ nhất (Greedy Local Search with Backoff).
- Đếm lùi thời gian đóng băng (frozen_time) an toàn kết hợp cờ ngắt stop_event.
- Đồng bộ tọa độ tức thì qua callback on_step.
"""

import threading
import time
from typing import Callable, Optional

from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired, TaskContext


def chebyshev_distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Khoảng cách ô lưới chuẩn trong bản đồ Linh Vương: max(|dx|, |dy|)."""
    return max(abs(x1 - x2), abs(y1 - y2))


class DiTrai:
    def __init__(
        self,
        ctx: Optional[TaskContext],
        camp_id: int,
        origin: tuple[int, int],
        destination: tuple[int, int],
        max_step: int = 2,
        sleep_fn: Callable[[float], None] = time.sleep,
        on_step: Optional[Callable[[int, int, int], None]] = None,
        stop_event: Optional[threading.Event] = None,
        stop_at_distance: int = 0,
    ):
        self.ctx = ctx
        self.camp_id = camp_id
        self.origin = origin
        self.destination = destination
        self.max_step = max_step
        self.sleep_fn = sleep_fn
        self.on_step = on_step
        self.stop_event = stop_event
        self.stop_at_distance = stop_at_distance

    def _notify(self, msg: str) -> None:
        if self.ctx and self.ctx.notify:
            self.ctx.notify(msg)

    def _sleep_safe(self, seconds: float) -> None:
        """Nghỉ với khả năng ngắt sớm nếu stop_event được kích hoạt."""
        if self.sleep_fn != time.sleep:
            self.sleep_fn(seconds)
            return

        remaining = float(seconds)
        while remaining > 0:
            if self.stop_event and self.stop_event.is_set():
                break
            sleep_chunk = min(1.0, remaining)
            time.sleep(sleep_chunk)
            remaining -= sleep_chunk

    def step_towards(
        self, target_x: int, target_y: int, step_limit: Optional[int] = None
    ) -> tuple[int, int]:
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

    def move_step(self, dest_x: int, dest_y: int) -> tuple[bool, int, str]:
        """Gửi lệnh dời Doanh trại qua Common.ashx?id=55."""
        if not self.ctx or not self.ctx.gateway:
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
            if self.on_step:
                self.on_step(dest_x, dest_y, frozen_time)
            if frozen_time > 0:
                self._sleep_safe(frozen_time)
            return True, frozen_time, "ok"

        if ret == 39:
            # ret=39: Đã có công trình hoặc chướng ngại vật
            return False, 0, "obstacle"

        if ret == 42:
            # ret=42: Đang trong thời gian đóng băng
            return False, 0, "frozen"

        if ret == 40:
            # ret=40: Thiếu tài nguyên di trại
            return False, 0, "insufficient_resources"

        return False, 0, f"error:{ret}"

    def advance_to_destination(self) -> str:
        """Dời Doanh trại từng bước cho tới khi đến đích (hoặc đạt stop_at_distance) hoặc nhận lệnh dừng."""
        dest_x, dest_y = self.destination
        initial_dist = chebyshev_distance(self.origin[0], self.origin[1], dest_x, dest_y)
        max_total_steps = max(30, initial_dist * 4)
        total_steps = 0
        consecutive_obstacles = 0
        best_dist = initial_dist
        visited_coords = {self.origin}

        while total_steps < max_total_steps:
            if self.stop_event and self.stop_event.is_set():
                self._notify("⏹️ Tiến trình Di Trại đã được dừng theo yêu cầu người chơi.")
                return "stopped"

            cur_dist = chebyshev_distance(self.origin[0], self.origin[1], dest_x, dest_y)
            if cur_dist <= self.stop_at_distance:
                if self.stop_at_distance == 0:
                    self._notify(f"🎯 Doanh trại đã đến đích ({dest_x}, {dest_y}) thành công!")
                    return "arrived"
                else:
                    self._notify(
                        f"🎯 Doanh trại đã vào phạm vi tiếp cận (cự ly {cur_dist} <= {self.stop_at_distance}) tại ({self.origin[0]}, {self.origin[1]})."
                    )
                    return "arrived"

            total_steps += 1

            # 1. Thử bước nhảy thẳng tối đa hướng về đích
            sx, sy = self.step_towards(dest_x, dest_y, self.max_step)
            success, frozen, reason = self.move_step(sx, sy)

            if success:
                visited_coords.add((sx, sy))
                if cur_dist < best_dist:
                    best_dist = cur_dist
                    consecutive_obstacles = 0
                continue

            if reason == "insufficient_resources":
                self._notify("❌ Di trại thất bại: Không đủ tài nguyên để tiếp tục dời trại!")
                return "insufficient_resources"

            if reason == "frozen":
                self._notify("⏳ Doanh trại đang trong thời gian đóng băng, chờ 3s thử lại...")
                self._sleep_safe(3)
                continue

            if reason == "obstacle":
                # Kích hoạt Lách Vật Cản (Greedy Local Search with Backoff)
                self._notify(f"⚠️ Vướng chướng ngại vật tại ({sx}, {sy}), kích hoạt Lách Vật Cản...")
                consecutive_obstacles += 1
                if consecutive_obstacles > 5:
                    self._notify("❌ Quá 5 lần thử Lách Vật Cản không thành công, tạm dừng để tránh kẹt.")
                    return "blocked"

                # 2. Thử bước nhảy nhỏ 1 ô thẳng về đích
                detour_success = False
                if self.max_step > 1:
                    s1x, s1y = self.step_towards(dest_x, dest_y, 1)
                    if (s1x, s1y) != (sx, sy) and (s1x, s1y) not in visited_coords:
                        s_ok, _, s_reason = self.move_step(s1x, s1y)
                        if s_ok:
                            detour_success = True
                            visited_coords.add((s1x, s1y))

                # 3. Nếu vẫn vướng, dò 8 ô lân cận xung quanh ô hiện tại
                if not detour_success:
                    cx, cy = self.origin
                    candidates = []
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            if dx == 0 and dy == 0:
                                continue
                            nx, ny = cx + dx, cy + dy
                            if (nx, ny) == (sx, sy) or (nx, ny) in visited_coords:
                                continue
                            d = chebyshev_distance(nx, ny, dest_x, dest_y)
                            candidates.append((d, nx, ny))

                    # Sắp xếp các ô kề cận theo khoảng cách gần đích nhất
                    candidates.sort(key=lambda item: item[0])

                    for _, cand_x, cand_y in candidates[:4]:
                        if self.stop_event and self.stop_event.is_set():
                            return "stopped"
                        c_ok, _, _ = self.move_step(cand_x, cand_y)
                        if c_ok:
                            detour_success = True
                            visited_coords.add((cand_x, cand_y))
                            self._notify(f"✅ Đã Lách Vật Cản thành công qua ô phụ cận ({cand_x}, {cand_y})")
                            break

                if not detour_success:
                    self._notify(f"❌ Không tìm được lối lách vật cản tại ({self.origin[0]}, {self.origin[1]}).")
                    return "blocked"

                continue

            # Các lỗi khác không xác định
            self._notify(f"❌ Di trại thất bại với mã lỗi: {reason}")
            return reason

        self._notify("⚠️ Vượt quá số bước di chuyển tối đa cho phép.")
        return "blocked"
