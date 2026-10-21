import importlib
import json
import pkgutil
from unittest.mock import MagicMock, patch

import pytest
import requests

import linhvuong
from linhvuong.gui import LoginWindow


def test_all_modules_can_be_imported():
    for mod in pkgutil.walk_packages(linhvuong.__path__, linhvuong.__name__ + "."):
        m = importlib.import_module(mod.name)
        assert m is not None


@pytest.fixture
def temp_settings(tmp_path, monkeypatch):
    settings_file = tmp_path / "gui_settings.json"
    monkeypatch.setattr("linhvuong.gui.SETTINGS", settings_file)
    return settings_file


try:
    import _tkinter
except ImportError:
    _tkinter = None


def safe_login_window():
    if _tkinter is None:
        pytest.skip("tkinter not available")
    try:
        return LoginWindow()
    except Exception as e:
        pytest.skip(f"Tkinter display error: {e}")


def test_login_window_loads_proxy_settings_with_authen(temp_settings):
    temp_settings.write_text(
        json.dumps(
            {
                "server": 57,
                "username": "inti00",
                "proxy": "socks5://127.0.0.1:1080",
                "proxy_user": "p_user",
                "proxy_pass": "p_pass",
            }
        ),
        encoding="utf-8",
    )
    win = safe_login_window()
    win.withdraw()
    try:
        assert win.server_var.get() == "57"
        assert win.user_var.get() == "inti00"
        assert win.proxy_var.get() == "socks5://127.0.0.1:1080"
        assert win.proxy_user_var.get() == "p_user"
        assert win.proxy_pass_var.get() == "p_pass"
    finally:
        win.destroy()


def test_login_window_auto_parses_four_part_colon_syntax(temp_settings):
    win = safe_login_window()
    win.withdraw()
    try:
        # Giả lập người dùng dán chuỗi ip:port:user:pass vào ô Proxy
        win.proxy_var.set("103.151.123.45:8080:myuser:mypass")
        assert win.proxy_var.get() == "103.151.123.45:8080"
        assert win.proxy_user_var.get() == "myuser"
        assert win.proxy_pass_var.get() == "mypass"

        # Giả lập dán dạng socks5://ip:port:user:pass
        win.proxy_var.set("socks5://103.151.123.45:1080:usr:pwd")
        assert win.proxy_var.get() == "socks5://103.151.123.45:1080"
        assert win.proxy_user_var.get() == "usr"
        assert win.proxy_pass_var.get() == "pwd"
    finally:
        win.destroy()


def test_login_window_rejects_invalid_proxy(temp_settings):
    win = safe_login_window()
    win.withdraw()
    try:
        win.server_var.set("57")
        win.user_var.set("testuser")
        win.pass_var.set("secret")
        win.proxy_var.set("ftp://invalid:21")

        win._submit()
        assert "Proxy không hợp lệ" in win.status.get()
    finally:
        win.destroy()


def test_login_window_succeeded_persists_proxy_and_authen(temp_settings):
    win = safe_login_window()
    win.withdraw()
    try:
        session = requests.Session()
        win._succeeded(
            session,
            57,
            "testuser",
            "socks5://127.0.0.1:1080",
            "proxy_u",
            "proxy_p",
        )
        assert temp_settings.exists()
        saved = json.loads(temp_settings.read_text(encoding="utf-8"))
        assert saved["server"] == 57
        assert saved["username"] == "testuser"
        assert saved["proxy"] == "socks5://127.0.0.1:1080"
        assert saved["proxy_user"] == "proxy_u"
        assert saved["proxy_pass"] == "proxy_p"
        assert win.session is session
        assert win.server_id == 57
    finally:
        try:
            win.destroy()
        except Exception:
            pass
