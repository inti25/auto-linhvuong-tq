"""Bình Man: quét Man quanh thành/Trại Di Chuyển rồi xuất quân.

Chưa làm: dời Trại Di Chuyển từng bước, chữa thương, bổ sung binh (chưa có đặc tả).
"""

from .base import TaskContext, attack


class BinhMan:
    def __init__(
        self,
        ctx: TaskContext,
        generals: list[int],
        origin: tuple[int, int],
        radius: int,
        man_types: list[int],
        return_threshold: int = 0,
        skip_capital_radius: int = 0,
    ):
        self.ctx = ctx
        self.generals = generals
        self.origin = origin
        self.radius = radius
        self.man_types = man_types
        self.return_threshold = return_threshold
        self.skip_capital_radius = skip_capital_radius

    def needs_return(self, remaining_percent: float) -> bool:
        """Binh còn lại (%) dưới ngưỡng thì cần rút về thành."""
        return remaining_percent < self.return_threshold

    def run_once(self) -> str:
        target = self.ctx.scanner.find_nearest(
            *self.origin,
            self.radius,
            self.man_types,
            skip_capital_radius=self.skip_capital_radius,
        )
        if target is None:
            return "no_target"
        return attack(self.ctx, target, self.generals)
