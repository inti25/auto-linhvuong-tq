"""Bể Proxy Động (ProxyPool) cho Linh Vương Auto Bot.

Hỗ trợ:
- Phân tích danh sách proxy dạng ip:port:username:password hoặc ip:port.
- Tự động tải danh sách proxy qua URL từ nhà cung cấp.
- Kiểm tra tính sống/chết (Health Check) đồng thời đa luồng qua cổng game.
- Tự động hoán đổi nóng (Failover/Rotation) khi gặp sự cố kết nối trong lúc bot đang vận hành.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import logging
import re
import threading
import time
from typing import Callable, List, Optional
from urllib.parse import quote, urlsplit

import requests

from .auth import normalize_proxy_url

logger = logging.getLogger("linhvuong.proxy")


@dataclass
class ProxyEndpoint:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "socks5h"
    explicit_protocol: bool = False
    is_alive: bool = True
    latency: float = 0.0

    @property
    def display_name(self) -> str:
        """Chuỗi hiển thị an toàn (ẩn mật khẩu)."""
        auth_part = f"{self.username}@" if self.username else ""
        return f"{self.protocol}://{auth_part}{self.host}:{self.port}"

    @property
    def url(self) -> str:
        """URL proxy chuẩn hóa dùng cho requests.Session."""
        scheme = "socks5h" if self.protocol.lower() in ("socks5", "socks5h") else "http"
        u = quote(self.username, safe="") if self.username else None
        p = quote(self.password, safe="") if self.password else None
        if u and p:
            auth = f"{u}:{p}@"
        elif u:
            auth = f"{u}@"
        else:
            auth = ""
        return f"{scheme}://{auth}{self.host}:{self.port}"

    @classmethod
    def from_line(cls, line: str, default_protocol: str = "socks5h") -> Optional["ProxyEndpoint"]:
        """Phân tích một dòng văn bản thành ProxyEndpoint.

        Hỗ trợ:
        - ip:port:username:password
        - ip:port
        - protocol://ip:port:username:password
        - protocol://username:password@ip:port
        """
        raw = line.strip()
        if not raw or raw.startswith("#"):
            return None

        protocol = default_protocol
        explicit_protocol = False
        rest = raw

        # Tách giao thức nếu có
        if "://" in rest:
            explicit_protocol = True
            scheme, rest = rest.split("://", 1)
            scheme_lower = scheme.lower()
            if scheme_lower in ("http", "https"):
                protocol = "http"
            elif scheme_lower in ("socks5", "socks5h"):
                protocol = "socks5h"

        host: Optional[str] = None
        port: Optional[int] = None
        username: Optional[str] = None
        password: Optional[str] = None

        # Trường hợp có @ (dạng username:password@host:port)
        if "@" in rest:
            auth_part, host_port = rest.rsplit("@", 1)
            if ":" in auth_part:
                username, password = auth_part.split(":", 1)
            else:
                username = auth_part

            if ":" in host_port:
                h, p = host_port.split(":", 1)
                host = h.strip()
                if p.strip().isdigit():
                    port = int(p.strip())
        else:
            # Dạng phân cách dấu hai chấm phổ biến
            parts = [p.strip() for p in rest.split(":")]
            if len(parts) >= 4:
                host = parts[0]
                if parts[1].isdigit():
                    port = int(parts[1])
                username = parts[2]
                password = ":".join(parts[3:])  # Hỗ trợ mật khẩu có chứa dấu hai chấm
            elif len(parts) == 2:
                host = parts[0]
                if parts[1].isdigit():
                    port = int(parts[1])
            elif len(parts) == 3:
                host = parts[0]
                if parts[1].isdigit():
                    port = int(parts[1])
                username = parts[2]

        if not host or not port or not (1 <= port <= 65535):
            return None

        return cls(
            host=host,
            port=port,
            username=username or None,
            password=password or None,
            protocol=protocol,
            explicit_protocol=explicit_protocol,
        )


class ProxyPool:
    """Bể quản lý danh sách Proxy an toàn luồng với tính năng Health Check và Failover."""

    def __init__(
        self,
        url: Optional[str] = None,
        endpoints: Optional[List[ProxyEndpoint]] = None,
        check_timeout: float = 4.0,
        default_protocol: str = "socks5h",
        on_failover: Optional[Callable[[Optional[ProxyEndpoint], Optional[ProxyEndpoint]], None]] = None,
    ):
        self.url = (url or "").strip() or None
        self.endpoints: List[ProxyEndpoint] = list(endpoints or [])
        self.active_index: int = 0
        self.check_timeout = check_timeout
        self.default_protocol = default_protocol
        self.on_failover = on_failover
        self._lock = threading.Lock()

    def load_from_text(self, text: str, default_protocol: Optional[str] = None) -> int:
        """Nạp danh sách proxy từ chuỗi văn bản (nhiều dòng). Trả về số proxy nạp được."""
        proto = default_protocol or self.default_protocol
        with self._lock:
            new_endpoints: List[ProxyEndpoint] = []
            for line in text.splitlines():
                ep = ProxyEndpoint.from_line(line, default_protocol=proto)
                if ep:
                    new_endpoints.append(ep)
            if new_endpoints:
                self.endpoints = new_endpoints
                self.active_index = 0
            return len(new_endpoints)

    def fetch_from_url(self, url: Optional[str] = None, timeout: float = 10.0) -> int:
        """Tải danh sách proxy từ URL nguồn. Trả về số proxy tải được."""
        target_url = url or self.url
        if not target_url:
            raise ValueError("Chưa cấu hình URL tải danh sách Proxy.")

        logger.info(f"Đang tải danh sách proxy từ {target_url}...")
        resp = requests.get(
            target_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        self.url = target_url
        count = self.load_from_text(resp.text)
        logger.info(f"Đã tải thành công {count} proxy từ URL.")
        return count

    def check_endpoint(
        self,
        endpoint: ProxyEndpoint,
        target_url: str = "http://pass.dipan.com/",
        timeout: Optional[float] = None,
    ) -> bool:
        """Kiểm tra một endpoint có kết nối thông suốt tới đích hay không.

        Nếu endpoint không khai báo scheme cứng và giao thức hiện tại không truy cập được (hoặc bị 403 Forbidden do proxy),
        tự động kiểm tra giao thức thay thế (SOCKS5H <-> HTTP).
        """
        to = timeout or self.check_timeout
        protocols_to_try = [endpoint.protocol]
        if not endpoint.explicit_protocol:
            alt = "http" if endpoint.protocol == "socks5h" else "socks5h"
            protocols_to_try.append(alt)

        for proto in protocols_to_try:
            endpoint.protocol = proto
            start = time.time()
            proxies = {"http": endpoint.url, "https": endpoint.url}
            try:
                resp = requests.head(
                    target_url,
                    proxies=proxies,
                    timeout=to,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                elapsed = time.time() - start
                # Mã 200, 301, 302, 303, 307, 308 chứng tỏ kết nối thành công tới cổng game
                # Loại trừ 403 (bị proxy chặn/invalid_ip), 407 (lỗi auth proxy), 5xx
                if resp.status_code in (200, 301, 302, 303, 307, 308):
                    endpoint.latency = round(elapsed, 3)
                    endpoint.is_alive = True
                    return True
            except Exception:
                pass

        endpoint.is_alive = False
        endpoint.latency = 999.0
        return False

    def check_all(
        self,
        target_url: str = "http://pass.dipan.com/",
        max_workers: int = 10,
        timeout: Optional[float] = None,
    ) -> List[ProxyEndpoint]:
        """Kiểm tra đồng thời tất cả proxy trong pool, sắp xếp theo độ trễ thấp nhất."""
        to = timeout or self.check_timeout
        with self._lock:
            endpoints_to_check = list(self.endpoints)

        if not endpoints_to_check:
            return []

        logger.info(f"Bắt đầu kiểm tra {len(endpoints_to_check)} proxy với đích {target_url}...")
        alive: List[ProxyEndpoint] = []
        dead: List[ProxyEndpoint] = []

        workers = min(max_workers, max(1, len(endpoints_to_check)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_ep = {
                executor.submit(self.check_endpoint, ep, target_url, to): ep
                for ep in endpoints_to_check
            }
            for future in as_completed(future_to_ep):
                ep = future_to_ep[future]
                try:
                    if future.result():
                        alive.append(ep)
                    else:
                        dead.append(ep)
                except Exception:
                    ep.is_alive = False
                    dead.append(ep)

        # Sắp xếp proxy sống theo độ trễ tăng dần
        alive.sort(key=lambda x: x.latency)

        with self._lock:
            self.endpoints = alive + dead
            self.active_index = 0

        logger.info(f"Hoàn tất kiểm tra proxy: {len(alive)} sống, {len(dead)} chết.")
        return alive

    def get_active(self) -> Optional[ProxyEndpoint]:
        """Lấy proxy hiện tại đang được sử dụng (nếu còn sống)."""
        with self._lock:
            if not self.endpoints:
                return None
            if 0 <= self.active_index < len(self.endpoints):
                ep = self.endpoints[self.active_index]
                if ep.is_alive:
                    return ep
            # Nếu proxy tại active_index không sống, tìm proxy sống đầu tiên
            for idx, ep in enumerate(self.endpoints):
                if ep.is_alive:
                    self.active_index = idx
                    return ep
            return None

    def alive_count(self) -> int:
        """Số lượng proxy đang ở trạng thái sống."""
        with self._lock:
            return sum(1 for ep in self.endpoints if ep.is_alive)

    def total_count(self) -> int:
        """Tổng số proxy trong pool."""
        with self._lock:
            return len(self.endpoints)

    def apply_to_session(self, session: requests.Session) -> Optional[ProxyEndpoint]:
        """Gán proxy active vào requests.Session."""
        active = self.get_active()
        if active:
            session.proxies = {"http": active.url, "https": active.url}
            logger.info(f"Đã áp dụng proxy {active.display_name} vào session.")
        else:
            session.proxies = {}
        return active

    def failover(self, session: Optional[requests.Session] = None) -> Optional[ProxyEndpoint]:
        """Đánh dấu proxy hiện tại là lỗi và chuyển sang proxy sống tiếp theo.

        Nếu hết proxy sống và có URL, tự động tải lại và kiểm tra mẻ proxy mới.
        """
        old_ep: Optional[ProxyEndpoint] = None
        new_ep: Optional[ProxyEndpoint] = None

        with self._lock:
            if self.endpoints and 0 <= self.active_index < len(self.endpoints):
                old_ep = self.endpoints[self.active_index]
                old_ep.is_alive = False
                logger.warning(f"Đánh dấu proxy hỏng: {old_ep.display_name}")

            # Tìm proxy sống tiếp theo
            found_idx = None
            for idx in range(self.active_index + 1, len(self.endpoints)):
                if self.endpoints[idx].is_alive:
                    found_idx = idx
                    break

            if found_idx is None:
                # Tìm từ đầu đến active_index
                for idx in range(0, min(self.active_index, len(self.endpoints))):
                    if self.endpoints[idx].is_alive:
                        found_idx = idx
                        break

            if found_idx is not None:
                self.active_index = found_idx
                new_ep = self.endpoints[found_idx]

        # Nếu không còn proxy nào sống và có URL cấu hình, tự động fetch lại
        if new_ep is None and self.url:
            logger.info("Toàn bộ proxy trong pool đã cạn/chết. Đang tự động tải lại qua URL...")
            try:
                self.fetch_from_url(self.url)
                alive = self.check_all()
                if alive:
                    new_ep = alive[0]
            except Exception as ex:
                logger.error(f"Tự động tải lại proxy qua URL thất bại: {ex}")

        if new_ep:
            logger.info(f"Hoán đổi proxy thành công: {old_ep.display_name if old_ep else 'None'} -> {new_ep.display_name}")
            if session:
                session.proxies = {"http": new_ep.url, "https": new_ep.url}
            if self.on_failover:
                try:
                    self.on_failover(old_ep, new_ep)
                except Exception as ex:
                    logger.debug(f"Lỗi callback on_failover: {ex}")
            return new_ep

        logger.error("Không còn proxy nào khả dụng trong pool!")
        return None
