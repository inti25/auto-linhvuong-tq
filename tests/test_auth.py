from unittest.mock import MagicMock, patch

import pytest
import requests

from linhvuong.auth import (
    LoginError,
    apply_proxy_to_session,
    login,
    normalize_proxy_url,
    parse_server_id,
)


def test_server_id_accepts_digits_with_whitespace():
    assert parse_server_id(" 53 ") == 53


@pytest.mark.parametrize("raw", ["", "abc", "-5", "0", "5 3", "1.5"])
def test_server_id_rejects_non_positive_integers(raw):
    with pytest.raises(ValueError):
        parse_server_id(raw)


@pytest.mark.parametrize("empty_val", [None, "", "   ", "\t\n"])
def test_normalize_proxy_url_empty_returns_none(empty_val):
    assert normalize_proxy_url(empty_val) is None


def test_normalize_proxy_url_defaults_to_http():
    assert normalize_proxy_url("127.0.0.1:8080") == "http://127.0.0.1:8080"
    assert normalize_proxy_url("user:pass@proxy.local:3128") == "http://user:pass@proxy.local:3128"


def test_normalize_proxy_url_converts_socks5_to_socks5h():
    assert normalize_proxy_url("socks5://127.0.0.1:1080") == "socks5h://127.0.0.1:1080"
    assert (
        normalize_proxy_url("socks5://user:pass@127.0.0.1:1080")
        == "socks5h://user:pass@127.0.0.1:1080"
    )
    assert normalize_proxy_url("socks5h://127.0.0.1:1080") == "socks5h://127.0.0.1:1080"


def test_normalize_proxy_url_supports_https():
    assert normalize_proxy_url("https://secure-proxy.com:8443") == "https://secure-proxy.com:8443"


def test_normalize_proxy_url_four_part_colon_syntax():
    # Cú pháp phổ biến: ip:port:user:pass
    assert (
        normalize_proxy_url("103.151.123.45:8080:myuser:mypass")
        == "http://myuser:mypass@103.151.123.45:8080"
    )
    assert (
        normalize_proxy_url("socks5://103.151.123.45:1080:myuser:mypass")
        == "socks5h://myuser:mypass@103.151.123.45:1080"
    )


def test_normalize_proxy_url_with_explicit_username_password():
    assert (
        normalize_proxy_url("127.0.0.1:8080", username="admin", password="p@ss:word")
        == "http://admin:p%40ss%3Aword@127.0.0.1:8080"
    )
    assert (
        normalize_proxy_url("socks5://127.0.0.1:1080", username="admin", password="secret")
        == "socks5h://admin:secret@127.0.0.1:1080"
    )


@pytest.mark.parametrize(
    "invalid_input",
    [
        "ftp://127.0.0.1:21",
        "ws://127.0.0.1:8080",
        "127.0.0.1",  # Thiếu port
        "socks5://localhost",  # Thiếu port
        "http://:8080",  # Thiếu host
    ],
)
def test_normalize_proxy_url_rejects_invalid(invalid_input):
    with pytest.raises(ValueError):
        normalize_proxy_url(invalid_input)


def test_apply_proxy_to_session():
    session = requests.Session()
    norm = apply_proxy_to_session(session, "socks5://127.0.0.1:1080", "user", "pass")
    assert norm == "socks5h://user:pass@127.0.0.1:1080"
    assert session.proxies == {
        "http": "socks5h://user:pass@127.0.0.1:1080",
        "https": "socks5h://user:pass@127.0.0.1:1080",
    }

    apply_proxy_to_session(session, "")
    assert session.proxies == {}


def test_login_raises_login_error_on_proxy_failure():
    session = requests.Session()
    session.post = MagicMock(
        side_effect=requests.exceptions.ProxyError("Cannot connect to proxy")
    )
    with pytest.raises(LoginError) as exc_info:
        login(
            session,
            53,
            "testuser",
            "testpass",
            proxy="127.0.0.1:8080",
            proxy_user="admin",
            proxy_pass="secret",
        )
    assert "Lỗi kết nối Proxy" in str(exc_info.value)


def test_login_raises_login_error_on_proxy_timeout():
    session = requests.Session()
    session.post = MagicMock(
        side_effect=requests.exceptions.ConnectTimeout("Connection timed out")
    )
    with pytest.raises(LoginError) as exc_info:
        login(session, 53, "testuser", "testpass", proxy="socks5://127.0.0.1:1080")
    assert "Lỗi kết nối Proxy" in str(exc_info.value)


def test_login_success():
    session = requests.Session()
    mock_post_resp = MagicMock()
    mock_post_resp.text = "登录成功"
    session.post = MagicMock(return_value=mock_post_resp)
    mock_get_resp = MagicMock()
    session.get = MagicMock(return_value=mock_get_resp)

    login(session, 57, "validuser", "validpass")
    session.post.assert_called_once()
    session.get.assert_called_once_with("http://sg57.dipan.com/login", timeout=30)


def test_login_invalid_credentials_error():
    session = requests.Session()
    mock_post_resp = MagicMock()
    mock_post_resp.text = 'id="lbl_Error">登录失败：用户名或密码不正确。</span>'
    session.post = MagicMock(return_value=mock_post_resp)

    with pytest.raises(LoginError) as exc_info:
        login(session, 57, "inti00", "wrongpass")
    assert "Sai tên tài khoản hoặc mật khẩu" in str(exc_info.value)


def test_login_captcha_required_error():
    session = requests.Session()
    mock_post_resp = MagicMock()
    mock_post_resp.text = 'id="lbl_Error">登录失败：验证码不正确。</span>'
    session.post = MagicMock(return_value=mock_post_resp)

    with pytest.raises(LoginError) as exc_info:
        login(session, 57, "inti00", "anypass")
    assert "Captcha" in str(exc_info.value)

