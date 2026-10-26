"""Hạ tầng chung cho các nhiệm vụ."""

from dataclasses import dataclass
from typing import Callable, Optional

from ..gateway import GatewayClient
from ..locks import LockReason, TargetLocks
from ..scan import Scanner, Target

# ---- Mã trả về (ret) ----
RET_OK = 0
RET_TAKEN_BY_OTHER = 230  # xác nhận từ ZMan (ret230): Mục tiêu đã bị người khác đánh
# SUY ĐOÁN (chưa kiểm chứng): ret báo cần giải captcha. Báo cáo chỉ nêu Common.ashx?id=73.
RET_CAPTCHA_REQUIRED = 73
RET_SESSION_EXPIRED = 198599


class CaptchaRequired(Exception):
    """Server yêu cầu captcha: dừng nhiệm vụ và chờ người dùng giải thủ công."""


@dataclass
class TaskContext:
    gateway: GatewayClient
    scanner: Scanner
    locks: TargetLocks
    notify: Callable[[str], None] = print


def attack(ctx: TaskContext, target: Target, generals: list[int]) -> str:
    """OPT.ashx?id=53 (xác nhận). Tên trường payload là SUY ĐOÁN, cần đối chiếu HAR thật."""
    resp = ctx.gateway.call(
        "OPT.ashx",
        53,
        {
            "target_id": str(target.target_id),
            "generals": ",".join(str(g) for g in generals),
            "x": str(target.x),
            "y": str(target.y),
        },
    )
    if resp is None:
        return "attack_failed:network_error"

    ret = resp.get("ret", RET_OK)
    if ret == RET_CAPTCHA_REQUIRED:
        ctx.notify("Server yêu cầu captcha - hãy giải thủ công rồi chạy lại nhiệm vụ.")
        raise CaptchaRequired()
    if ret == RET_SESSION_EXPIRED:
        ctx.notify("⚠️ Phiên đăng nhập đã hết hạn (198599).")
        return f"attack_failed:{ret}"
    if ret == RET_TAKEN_BY_OTHER:
        ctx.locks.mark(target.target_id, LockReason.TAKEN_BY_OTHER)
        return "taken"
    if ret != RET_OK:
        return f"attack_failed:{ret}"
    return "attacked"

