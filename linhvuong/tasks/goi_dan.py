"""Gọi Dân (Vong Linh): đánh Vong Linh có sẵn, nếu không có thì gọi mới rồi đánh.

Chuỗi API xác nhận từ ZMan: City.ashx?id=50 (gọi) -> OPT.ashx?id=69 (param1/param2) -> tấn công.
Kết quả gọi chứa new_target_id/new_target_mid/new_target_type. Payload chi tiết của id=50/69
là SUY ĐOÁN (bytecode 3.13 chưa giải mã được); cần đối chiếu HAR thật.
"""

from ..coords import coords_from_mid
from ..locks import LockReason
from ..scan import Target
from .base import RET_OK, TaskContext, attack

VONG_LINH = 301


class GoiDan:
    def __init__(
        self,
        ctx: TaskContext,
        generals: list[int],
        origin: tuple[int, int],
        radius: int,
        skip_capital_radius: int = 0,
    ):
        self.ctx = ctx
        self.generals = generals
        self.origin = origin
        self.radius = radius
        self.skip_capital_radius = skip_capital_radius

    def run_once(self) -> str:
        target = self.ctx.scanner.find_nearest(
            *self.origin,
            self.radius,
            [VONG_LINH],
            skip_capital_radius=self.skip_capital_radius,
        )
        if target is not None:
            return attack(self.ctx, target, self.generals)

        resp = self.ctx.gateway.call("City.ashx", 50, {}) or {}
        ret = resp.get("ret", RET_OK)
        if ret != RET_OK or "new_target_id" not in resp:
            return f"call_failed:{ret}"
        x, y = coords_from_mid(int(resp["new_target_mid"]))
        target = Target(x, y, int(resp["new_target_id"]), int(resp.get("new_target_type", VONG_LINH)))
        self.ctx.locks.try_lock(target.target_id, LockReason.CLAIMED)
        result = attack(self.ctx, target, self.generals)
        return "called_and_attacked" if result == "attacked" else result
