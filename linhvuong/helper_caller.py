"""Quản lý phiên Tài Khoản Gọi Hộ (Helper Caller Account) cho chế độ Gọi Man (ADR-0049)."""

from typing import Any, Callable, Optional

import requests

from .auth import login, normalize_proxy_url
from .gateway import GatewayClient
from .proxy import ProxyPool


class HelperCallerError(RuntimeError):
    """Lỗi nền tảng khi làm việc với Tài Khoản Gọi Hộ."""


class HelperCallerLoginError(HelperCallerError):
    """Lỗi đăng nhập hoặc thiếu thông tin xác thực của Tài Khoản Gọi Hộ."""


class HelperCallerCaptchaRequired(HelperCallerError):
    """Tài Khoản Gọi Hộ bị server yêu cầu Captcha."""


def canonical_account_key(username: str, server_id: int) -> str:
    """Chuẩn hóa khóa tài khoản dùng cho Két Mật Khẩu Mã Hóa và WorkspaceManager."""
    return f"{(username or '').strip()} @ S{int(server_id)}"


class HelperCallerSession:
    """Cung cấp GatewayClient cho Tài Khoản Gọi Hộ (tái sử dụng phiên hoặc đăng nhập độc lập)."""

    def __init__(
        self,
        server_id: int,
        username: str,
        password: str = "",
        proxy_raw: str = "",
        proxy_user: str = "",
        proxy_pass: str = "",
        proxy_pool: Optional[ProxyPool] = None,
        session_lookup: Optional[Callable[[int, str], Optional[GatewayClient]]] = None,
        notify: Optional[Callable[[str], None]] = None,
        login_fn: Optional[Callable[..., Any]] = None,
    ):
        self.server_id = int(server_id)
        self.username = (username or "").strip()
        self._password = password or ""
        self.proxy_raw = (proxy_raw or "").strip()
        self.proxy_user = (proxy_user or "").strip()
        self.proxy_pass = proxy_pass or ""
        self.proxy_pool = proxy_pool
        self._session_lookup = session_lookup
        self._notify = notify
        self._login_fn = login_fn or login

        self._session: Optional[requests.Session] = None
        self._gateway: Optional[GatewayClient] = None
        self.reused: bool = False

    def _resolve_proxy(self) -> Optional[str]:
        if self.proxy_pool:
            active = self.proxy_pool.get_active()
            if active and getattr(active, "url", None):
                return active.url
        if self.proxy_raw:
            return normalize_proxy_url(
                self.proxy_raw,
                username=self.proxy_user or None,
                password=self.proxy_pass or None,
            )
        return None

    def _build_relogin_callback(self, req_session: requests.Session) -> Optional[Callable[[], bool]]:
        if not self.username or not self._password:
            return None

        def auto_relogin() -> bool:
            try:
                if self._notify:
                    self._notify(
                        f"🔑 Phiên Tài Khoản Gọi Hộ '{self.username}' hết hạn (198599). Đang tự động đăng nhập lại..."
                    )
                self._login_fn(
                    req_session,
                    self.server_id,
                    self.username,
                    self._password,
                    proxy=self._resolve_proxy(),
                )
                if self._notify:
                    self._notify(f"✅ Tài Khoản Gọi Hộ '{self.username}' đã tự động đăng nhập lại!")
                return True
            except Exception as exc:
                if self._notify:
                    self._notify(f"❌ Tài Khoản Gọi Hộ '{self.username}' đăng nhập lại thất bại: {exc}")
                return False

        return auto_relogin

    def acquire_gateway(self) -> GatewayClient:
        """Lấy GatewayClient đang hoạt động hoặc đăng nhập mới cho Tài Khoản Gọi Hộ."""
        if not self.username:
            raise HelperCallerLoginError("Chưa nhập tên Tài Khoản Gọi Hộ.")

        if self._session_lookup is not None:
            existing_gw = self._session_lookup(self.server_id, self.username)
            if existing_gw is not None:
                if not self.reused and self._gateway is not existing_gw and self._notify:
                    self._notify(
                        f"🔗 Tài Khoản Gọi Hộ '{self.username}' đang đăng nhập sẵn — tái sử dụng phiên hiện có."
                    )
                self.reused = True
                self._gateway = existing_gw
                return existing_gw

        if self._gateway is not None:
            return self._gateway

        if not self._password:
            raise HelperCallerLoginError(
                f"Thiếu mật khẩu cho Tài Khoản Gọi Hộ '{self.username}' (và chưa tìm thấy phiên/Két đã lưu)."
            )

        req_session = requests.Session()
        if self.proxy_pool:
            try:
                self.proxy_pool.apply_to_session(req_session)
            except Exception:
                pass

        proxy_url = self._resolve_proxy()
        try:
            self._login_fn(
                req_session,
                self.server_id,
                self.username,
                self._password,
                proxy=proxy_url,
            )
        except Exception as exc:
            try:
                req_session.close()
            except Exception:
                pass
            raise HelperCallerLoginError(
                f"Đăng nhập Tài Khoản Gọi Hộ '{self.username}' (S{self.server_id}) thất bại: {exc}"
            ) from exc

        relogin_cb = self._build_relogin_callback(req_session)
        gateway = GatewayClient(
            self.server_id,
            req_session,
            relogin_callback=relogin_cb,
            proxy_pool=self.proxy_pool,
        )
        self.reused = False
        self._session = req_session
        self._gateway = gateway
        if self._notify:
            self._notify(f"🔑 Đã đăng nhập Tài Khoản Gọi Hộ '{self.username}' (S{self.server_id}).")
        return gateway

    def test_connection(self) -> dict:
        """Kiểm tra kết nối/đăng nhập của Tài Khoản Gọi Hộ và dọn dẹp phiên tạm nếu có."""
        self.acquire_gateway()
        info = {
            "username": self.username,
            "server_id": self.server_id,
            "reused_session": self.reused,
        }
        if not self.reused:
            self.close()
        return info

    def close(self) -> None:
        """Đóng phiên HTTP độc lập (không đóng phiên được tái sử dụng từ workspace)."""
        sess = self._session
        was_reused = self.reused
        self._session = None
        self._gateway = None
        self.reused = False
        if sess is not None and not was_reused:
            try:
                sess.close()
            except Exception:
                pass
