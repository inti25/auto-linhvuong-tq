"""Hạ tầng chung cho các nhiệm vụ."""

import time
from dataclasses import dataclass
from typing import Callable, Optional

from ..coords import mid_from_coords
from ..gateway import GatewayClient
from ..locks import LockReason, TargetLocks
from ..scan import Scanner, Target

# ---- Mã trả về (ret) ----
RET_OK = 0
RET_TAKEN_BY_OTHER = 230  # xác nhận từ ZMan (ret230): Mục tiêu đã bị người khác đánh
# SUY ĐOÁN (chưa kiểm chứng): ret báo cần giải captcha. Báo cáo chỉ nêu Common.ashx?id=73.
RET_CAPTCHA_REQUIRED = 73
RET_SESSION_EXPIRED = 198599

# Trạng thái võ tướng có thể đang ở chiến trường hoặc hành quân thế giới (Common.ashx?id=32, g[5])
WORLD_ACTIVE_STATUSES = {16, 26}


class CaptchaRequired(Exception):
    """Server yêu cầu captcha: dừng nhiệm vụ và chờ người dùng giải thủ công."""


@dataclass
class TaskContext:
    gateway: GatewayClient
    scanner: Scanner
    locks: TargetLocks
    notify: Callable[[str], None] = print


def inspect_general_statuses(gateway: GatewayClient, generals: list[int]) -> dict[int, int]:
    """Đọc trạng thái thực tế của danh sách võ tướng từ Common.ashx?id=32."""
    if not generals:
        return {}
    wanted = {int(g) for g in generals}
    resp = gateway.call("Common.ashx", 32, {"type": "2", "_": ""}) or {}
    if not resp or "list" not in resp:
        return {}

    statuses: dict[int, int] = {}
    for entry in resp.get("list", []):
        g_entries = entry[4] if len(entry) > 4 else []
        for g in g_entries:
            try:
                gid = int(g[0])
            except (ValueError, IndexError, TypeError):
                continue
            if gid in wanted:
                statuses[gid] = int(g[5]) if len(g) > 5 else 0
    return statuses


def attack(
    ctx: TaskContext,
    target: Target,
    generals: list[int],
    batch_size: int = 3,
    batch_delay: float = 0.5,
    sleep_fn: Callable[[float], None] = time.sleep,
    origin_id: int = 0,
) -> str:
    """OPT.ashx?id=53 (xác nhận từ barracks.js _fightGo). Tối đa 3 đạo/lần xuất quân."""
    if not generals:
        return "attack_failed:no_generals"

    bsize = max(1, batch_size)
    batches = [generals[i:i + bsize] for i in range(0, len(generals), bsize)]
    total_batches = len(batches)
    dest_mid = mid_from_coords(target.x, target.y)

    for idx, batch in enumerate(batches):
        if idx > 0 and batch_delay > 0:
            sleep_fn(batch_delay)

        gen_slots = [batch[0] if len(batch) > 0 else 0, batch[1] if len(batch) > 1 else 0, batch[2] if len(batch) > 2 else 0]
        resp = ctx.gateway.call(
            "OPT.ashx",
            53,
            {
                "lDestID": str(dest_mid),
                "lType": "1",
                "lGeneralID1": str(gen_slots[0]),
                "lGeneralID2": str(gen_slots[1]),
                "lGeneralID3": str(gen_slots[2]),
                "lBout": "-1",
                "lTarget1GID": "0",
                "lTarget2GID": "0",
                "lTarget3GID": "0",
                "lPlusFuncID": "0",
                "lPlusDestID": "0",
                "tid": str(origin_id),
                "target_id": str(target.target_id),
                "generals": ",".join(str(g) for g in batch),
                "x": str(target.x),
                "y": str(target.y),
            },
        )
        if resp is None:
            if total_batches > 1 and ctx.notify:
                ctx.notify(f"❌ Đợt {idx + 1}/{total_batches} xuất quân thất bại: lỗi mạng.")
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
            if total_batches > 1 and ctx.notify:
                ctx.notify(f"⚠️ Đợt {idx + 1}/{total_batches}: Mục tiêu đã bị người khác chiếm.")
            return "taken"
        if ret != RET_OK:
            if total_batches > 1 and ctx.notify:
                ctx.notify(f"❌ Đợt {idx + 1}/{total_batches} xuất quân thất bại (mã lỗi: {ret}).")
            return f"attack_failed:{ret}"

        if total_batches > 1 and ctx.notify:
            ctx.notify(f"⚔️ Đợt {idx + 1}/{total_batches} ({len(batch)} đạo) xuất kích thành công...")

    if total_batches > 1 and ctx.notify:
        ctx.notify(f"✅ Hoàn tất xuất kích {total_batches} đợt ({len(generals)} đạo quân) tới mục tiêu ({target.x}, {target.y}).")
    return "attacked"

