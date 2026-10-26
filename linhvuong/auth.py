"""Đăng nhập Linh Vương (dùng chung cho CLI và GUI)."""

from typing import Optional
from urllib.parse import quote, urlsplit

import requests

LOGIN_URL = "http://pass.dipan.com/aspx/LoginAPI.aspx"


class LoginError(Exception):
    pass


def parse_server_id(raw: str) -> int:
    """Server ID là số nguyên dương: http://sg<server_id>.dipan.com/"""
    raw = raw.strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise ValueError("Server ID phải là số nguyên dương.")
    return int(raw)


def normalize_proxy_url(
    raw: Optional[str],
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[str]:
    """Chuẩn hóa chuỗi cấu hình proxy.

    - Hỗ trợ http, https, socks5 (tự động đổi sang socks5h để giải quyết DNS từ xa).
    - Hỗ trợ cú pháp:
        + host:port
        + protocol://host:port
        + host:port:user:pass (tự động nhận diện username, password)
        + protocol://host:port:user:pass
        + user:pass@host:port
        + protocol://user:pass@host:port
    - Hỗ trợ truyền riêng username và password (tự động mã hóa ký tự đặc biệt).
    - Trả về None nếu raw rỗng.
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None

    if "://" in raw:
        scheme, rest = raw.split("://", 1)
    else:
        scheme, rest = "http", raw

    u = (username or "").strip() or None
    p = (password or "").strip() or None

    # Tự động nhận diện định dạng dán nhanh: host:port:user:pass
    if "@" not in rest and ":" in rest:
        parts = rest.split(":")
        if len(parts) == 4:
            host, port, inline_user, inline_pwd = parts
            rest = f"{host}:{port}"
            if not u:
                u = inline_user
            if not p:
                p = inline_pwd

    # Nếu có u và/hoặc p và trong rest chưa có credentials (@)
    if "@" not in rest and (u or p):
        quoted_u = quote(u, safe="") if u else ""
        quoted_p = quote(p, safe="") if p else ""
        if quoted_u and quoted_p:
            rest = f"{quoted_u}:{quoted_p}@{rest}"
        elif quoted_u:
            rest = f"{quoted_u}@{rest}"

    candidate = f"{scheme}://{rest}"
    try:
        parsed = urlsplit(candidate)
    except Exception as e:
        raise ValueError(f"Định dạng Proxy không hợp lệ: {e}") from e

    scheme_lower = parsed.scheme.lower()
    if scheme_lower not in {"http", "https", "socks5", "socks5h"}:
        raise ValueError(
            f"Giao thức '{parsed.scheme}' không được hỗ trợ. Chỉ hỗ trợ http, https, socks5."
        )

    if not parsed.hostname:
        raise ValueError("Địa chỉ Proxy thiếu thông tin host.")
    if not parsed.port:
        raise ValueError("Địa chỉ Proxy cần chỉ định cổng (port), ví dụ: 127.0.0.1:8080.")

    if scheme_lower == "socks5":
        return parsed._replace(scheme="socks5h").geturl()
    return parsed._replace(scheme=scheme_lower).geturl()


def apply_proxy_to_session(
    session: requests.Session,
    proxy_raw: Optional[str],
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[str]:
    """Gán proxy chuẩn hóa vào requests.Session. Trả về URL proxy đã chuẩn hóa (hoặc None)."""
    normalized = normalize_proxy_url(proxy_raw, username=username, password=password)
    if normalized:
        session.proxies = {"http": normalized, "https": normalized}
    else:
        session.proxies = {}
    return normalized


def login(
    session: requests.Session,
    server_id: int,
    username: str,
    password: str,
    proxy: Optional[str] = None,
    proxy_user: Optional[str] = None,
    proxy_pass: Optional[str] = None,
) -> None:
    """Theo báo cáo ZMan; chưa kiểm chứng trên server thật."""
    if proxy is not None:
        apply_proxy_to_session(session, proxy, username=proxy_user, password=proxy_pass)

    cookies = getattr(session, "cookies", None)
    if cookies is not None and hasattr(cookies, "clear"):
        try:
            cookies.clear()
        except Exception:
            pass

    try:
        resp = session.post(
            LOGIN_URL,
            data={
                "LoginType1": 0,
                "UserName1": username,
                "Password1": password,
                "callback": f"http://sg{server_id}.dipan.com",
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": LOGIN_URL,
            },
            timeout=30,
        )
        if "登录成功" not in resp.text:
            text_lower = resp.text.lower()
            if resp.status_code == 403 or "forbidden" in text_lower or "invalid_ip" in text_lower:
                snippet = resp.text.strip().replace("\r", " ").replace("\n", " ")[:120]
                raise LoginError(f"Proxy từ chối kết nối (HTTP {resp.status_code}): {snippet}")
            if "验证码不正确" in resp.text:
                raise LoginError("Đăng nhập thất bại: Máy chủ yêu cầu mã xác nhận (Captcha) hoặc tài khoản bị tạm khóa kiểm tra.")
            if "用户名或密码不正确" in resp.text:
                raise LoginError("Đăng nhập thất bại: Sai tên tài khoản hoặc mật khẩu.")
            raise LoginError(f"Đăng nhập thất bại: Sai tài khoản hoặc mật khẩu (HTTP {resp.status_code}).")
        session.get(f"http://sg{server_id}.dipan.com/login", timeout=30)
    except LoginError:
        raise
    except requests.exceptions.ProxyError as e:
        raise LoginError(
            f"Lỗi kết nối Proxy: Không thể kết nối tới máy chủ qua proxy ({e})."
        ) from e
    except requests.exceptions.ConnectTimeout as e:
        if session.proxies:
            raise LoginError(
                f"Lỗi kết nối Proxy: Hết thời gian chờ kết nối qua proxy ({e})."
            ) from e
        raise LoginError(f"Lỗi mạng: Hết thời gian chờ kết nối ({e}).") from e
    except requests.RequestException as e:
        err_msg = str(e)
        if session.proxies and any(k in err_msg.lower() for k in ("proxy", "socks")):
            raise LoginError(f"Lỗi kết nối Proxy: {e}") from e
        raise LoginError(f"Lỗi mạng: {e}") from e
