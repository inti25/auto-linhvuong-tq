"""Đọc thông báo hệ thống (Niên Thú xuất hiện) từ `/api/notify/history` trên Server 58+."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Optional

STATE_NAMES: dict[int, str] = {
    1: "凉州",
    2: "鲜卑",
    3: "幽州",
    4: "并州",
    5: "冀州",
    6: "雍州",
    7: "司州",
    8: "兖州",
    9: "青州",
    10: "益州",
    11: "荆州",
    12: "豫州",
    13: "徐州",
    14: "扬州",
    15: "交州",
    16: "西域",
}

STATE_IDS: dict[str, int] = {name: sid for sid, name in STATE_NAMES.items()}

STATE_VI_NAMES: dict[int, str] = {
    1: "Lương Châu",
    2: "Tiên Ty",
    3: "U Châu",
    4: "Tịnh Châu",
    5: "Ký Châu",
    6: "Ung Châu",
    7: "Tư Châu",
    8: "Duyện Châu",
    9: "Thanh Châu",
    10: "Ích Châu",
    11: "Kinh Châu",
    12: "Dự Châu",
    13: "Từ Châu",
    14: "Dương Châu",
    15: "Giao Châu",
    16: "Tây Vực",
}

_NIEN_THU_MSG_RE = re.compile(r"年兽已在(.+?)附近出现[^'\"}]*")


@dataclass(frozen=True)
class NienThuAnnouncement:
    """Thông báo Niên Thú xuất hiện đọc từ `/api/notify/history`."""

    state_id: int
    state_name: str
    server_time: str
    raw_message: str
    source_id: int = 0


def parse_nien_thu_announcement(
    text_or_item: Any,
    *,
    server_time: str = "",
    source_id: int = 0,
) -> Optional[NienThuAnnouncement]:
    """Phân tích một thông báo từ `/api/notify/history` (dict hoặc chuỗi text)."""
    if isinstance(text_or_item, dict):
        text = str(text_or_item.get("text") or "")
        if not source_id:
            try:
                source_id = int(text_or_item.get("sourceId") or text_or_item.get("cursor") or 0)
            except (ValueError, TypeError):
                source_id = 0
        if not server_time:
            created_ms = text_or_item.get("createdAt")
            if created_ms:
                try:
                    dt = datetime.fromtimestamp(float(created_ms) / 1000.0, tz=timezone.utc)
                    server_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError, OSError):
                    server_time = str(created_ms)
    else:
        text = str(text_or_item or "")

    if not text:
        return None
    match = _NIEN_THU_MSG_RE.search(text)
    if not match:
        return None

    state_name = match.group(1).strip()
    state_id = STATE_IDS.get(state_name)
    if state_id is None:
        return None

    return NienThuAnnouncement(
        state_id=state_id,
        state_name=state_name,
        server_time=server_time,
        raw_message=match.group(0).strip(),
        source_id=source_id,
    )


class WorldChatClient:
    """Client đọc thông báo Niên Thú từ API `/api/notify/history` của Server 58+."""

    def fetch_latest_nien_thu(self, gateway: Any) -> Optional[NienThuAnnouncement]:
        """Lấy thông báo Niên Thú mới nhất từ `/api/notify/history`."""
        resp = gateway.notify_history() if hasattr(gateway, "notify_history") else None
        if not isinstance(resp, dict) or int(resp.get("ret", -1)) != 0:
            return None
        items = resp.get("items") or []
        if not isinstance(items, list):
            return None

        latest: Optional[NienThuAnnouncement] = None
        for item in items:
            ann = parse_nien_thu_announcement(item)
            if ann is None:
                continue
            if latest is None or (ann.source_id, ann.server_time) >= (latest.source_id, latest.server_time):
                latest = ann
        return latest
