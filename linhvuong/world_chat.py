"""Kết nối kênh chat thế giới (XMLSocket `scs:scp`) và đọc thông báo Niên Thú."""

from dataclasses import dataclass
import html
import re
import socket
from typing import Callable, Optional


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
_TIME_ATTR_RE = re.compile(r"\btime=(['\"])([^'\"]+)\1")
_MSG_TAG_RE = re.compile(r"<msg>(.*?)</msg>", re.DOTALL)
_SGWEBIM_RE = re.compile(r"SGWebIM\.swf\?([^\s\"'<>]+)")
_SCS_RE = re.compile(r"\bscs=([^&\s\"'<>]+)")
_SCP_RE = re.compile(r"\bscp=(\d+)")


@dataclass(frozen=True)
class ChatCredentials:
    """Thông tin kết nối XMLSocket của kênh chat thế giới từ `/city`."""

    host: str
    port: int
    char_id: str
    id2: str
    uid: str
    name: str
    uname: str


@dataclass(frozen=True)
class NienThuAnnouncement:
    """Thông báo Niên Thú xuất hiện đọc từ kênh thế giới."""

    state_id: int
    state_name: str
    server_time: str
    raw_message: str


def parse_city_chat_config(page_html: str) -> Optional[ChatCredentials]:
    """Trích xuất host/port chat và tham số `SGWebIM.swf` từ HTML trang `/city`."""
    if not page_html:
        return None
    normalized = html.unescape(page_html)
    scs_m = _SCS_RE.search(normalized)
    scp_m = _SCP_RE.search(normalized)
    swf_m = _SGWEBIM_RE.search(normalized)
    if not (scs_m and scp_m and swf_m):
        return None

    params: dict[str, str] = {}
    for pair in swf_m.group(1).split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v

    char_id = params.get("id", "").strip()
    id2 = params.get("id2", "").strip()
    uid = params.get("uid", "").strip()
    if not (char_id and id2 and uid):
        return None

    return ChatCredentials(
        host=scs_m.group(1).strip(),
        port=int(scp_m.group(1)),
        char_id=char_id,
        id2=id2,
        uid=uid,
        name=params.get("n", ""),
        uname=params.get("un", ""),
    )


def build_chat_packet(tp: str, creds: ChatCredentials) -> bytes:
    """Đóng gói XMLSocket frame chuẩn `SGWebIM.swf` (`<root len='... ' ...></root>\\0`)."""
    inner = (
        f"tp='{tp}' id='{creds.char_id}' id2='{creds.id2}' uid='{creds.uid}'>"
        f"<name>{creds.name}</name><uname>{creds.uname}</uname>"
    )
    total = len(inner.encode("utf-8")) + 29
    padded = str(total).ljust(8, " ")
    return f"<root len='{padded}' {inner}</root>\x00".encode("utf-8")


def parse_nien_thu_announcement(frame: str) -> Optional[NienThuAnnouncement]:
    """Phân tích một XML frame từ chat server; trả về `NienThuAnnouncement` nếu khớp Niên Thú."""
    if not frame:
        return None
    msg_m = _MSG_TAG_RE.search(frame)
    body = msg_m.group(1) if msg_m else frame
    match = _NIEN_THU_MSG_RE.search(body)
    if not match:
        return None

    state_name = match.group(1).strip()
    state_id = STATE_IDS.get(state_name)
    if state_id is None:
        return None

    time_m = _TIME_ATTR_RE.search(frame)
    server_time = time_m.group(2).strip() if time_m else ""
    return NienThuAnnouncement(
        state_id=state_id,
        state_name=state_name,
        server_time=server_time,
        raw_message=match.group(0).strip(),
    )


def _default_socket_factory(host: str, port: int, timeout: float):
    return socket.create_connection((host, port), timeout=timeout)


class WorldChatClient:
    """Client đọc thông báo hệ thống trên kênh chat thế giới (XMLSocket)."""

    def __init__(self, socket_factory: Optional[Callable[[str, int, float], socket.socket]] = None):
        self._socket_factory = socket_factory or _default_socket_factory

    def fetch_latest_nien_thu(
        self, creds: ChatCredentials, timeout: float = 3.0
    ) -> Optional[NienThuAnnouncement]:
        """Kết nối socket chat, gửi `login` + `reqamsg` và lấy thông báo Niên Thú mới nhất."""
        sock = self._socket_factory(creds.host, creds.port, timeout)
        latest: Optional[NienThuAnnouncement] = None
        buf = bytearray()
        try:
            sock.settimeout(timeout)
            sock.sendall(build_chat_packet("login", creds))
            sock.sendall(build_chat_packet("reqamsg", creds))

            while True:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    break
                if not chunk:
                    break
                buf.extend(chunk)
                while b"\x00" in buf:
                    idx = buf.index(0)
                    raw_frame = bytes(buf[:idx]).decode("utf-8", errors="replace")
                    del buf[: idx + 1]
                    ann = parse_nien_thu_announcement(raw_frame)
                    if ann is not None and (
                        latest is None or ann.server_time >= latest.server_time
                    ):
                        latest = ann
                    if "tp='newsmsg'" in raw_frame or 'tp="newsmsg"' in raw_frame:
                        sock.settimeout(min(timeout, 0.3))
        finally:
            try:
                sock.close()
            except Exception:
                pass
        return latest
