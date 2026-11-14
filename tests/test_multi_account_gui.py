import json
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest
import requests

from linhvuong.gui import AccountCard, AccountLoginFrame, MultiAccountApp

try:
    import _tkinter
except ImportError:
    _tkinter = None


@pytest.fixture
def temp_settings(tmp_path, monkeypatch):
    settings_file = tmp_path / "gui_settings.json"
    monkeypatch.setattr("linhvuong.gui.SETTINGS", settings_file)
    return settings_file


def safe_multi_account_app():
    if _tkinter is None:
        pytest.skip("tkinter not available")
    try:
        app = MultiAccountApp()
        app.withdraw()
        return app
    except Exception as e:
        pytest.skip(f"Tkinter display error: {e}")


def test_multi_account_app_loads_saved_accounts(temp_settings):
    init_data = {
        "server": 53,
        "username": "quilia",
        "proxy": "socks5://171.244.41.79:6060",
        "proxy_user": "user1",
        "proxy_pass": "pass1",
        "last_account": "quilia @ S53",
        "accounts": {
            "quilia @ S53": {
                "server": 53,
                "username": "quilia",
                "proxy": "socks5://171.244.41.79:6060",
                "proxy_user": "user1",
                "proxy_pass": "pass1",
            },
            "inti00 @ S57": {
                "server": 57,
                "username": "inti00",
                "proxy": "socks5://127.0.0.1:1080",
                "proxy_user": "user2",
                "proxy_pass": "pass2",
            },
        },
    }
    temp_settings.write_text(json.dumps(init_data, ensure_ascii=False, indent=2), encoding="utf-8")

    app = safe_multi_account_app()
    try:
        assert len(app.cards) == 2
        assert "quilia @ S53" in app.cards
        assert "inti00 @ S57" in app.cards

        # Mặc định chọn last_account là quilia @ S53
        assert app.current_key == "quilia @ S53"
        assert app.cards["quilia @ S53"].is_selected is True
        assert app.cards["inti00 @ S57"].is_selected is False
        assert "[S53] quilia" in app.header_title.cget("text")

        # Workspace hiển thị AccountLoginFrame cho tài khoản chưa đăng nhập
        lf = app.login_frames.get("quilia @ S53")
        assert lf is not None
        assert lf.server_var.get() == "53"
        assert lf.user_var.get() == "quilia"
        assert lf.proxy_user_var.get() == "user1"
        assert lf.pass_var.get() == ""  # Mật khẩu luôn để trống
    finally:
        app.destroy()


def test_multi_account_app_selects_account_and_switches_view(temp_settings):
    init_data = {
        "accounts": {
            "acc1 @ S53": {"server": 53, "username": "acc1"},
            "acc2 @ S57": {"server": 57, "username": "acc2"},
        },
        "last_account": "acc1 @ S53",
    }
    temp_settings.write_text(json.dumps(init_data, ensure_ascii=False, indent=2), encoding="utf-8")

    app = safe_multi_account_app()
    try:
        # Chọn sang acc2
        app._select_account("acc2 @ S57")
        assert app.current_key == "acc2 @ S57"
        assert app.cards["acc1 @ S53"].is_selected is False
        assert app.cards["acc2 @ S57"].is_selected is True
        assert "[S57] acc2" in app.header_title.cget("text")

        lf2 = app.login_frames.get("acc2 @ S57")
        assert lf2 is not None
        assert lf2.server_var.get() == "57"
        assert lf2.user_var.get() == "acc2"
    finally:
        app.destroy()


def test_multi_account_app_adds_new_account(temp_settings):
    temp_settings.write_text(json.dumps({"accounts": {}}), encoding="utf-8")
    app = safe_multi_account_app()
    try:
        initial_count = len(app.cards)
        app._on_add_account()
        assert len(app.cards) == initial_count + 1
        assert "Tài khoản mới" in app.current_key

        lf = app.login_frames.get(app.current_key)
        assert lf is not None
        assert lf.server_var.get() == ""
        assert lf.user_var.get() == ""
    finally:
        app.destroy()


def test_account_login_frame_auto_parses_proxy_colon_syntax():
    if _tkinter is None:
        pytest.skip("tkinter not available")
    root = tk.Tk()
    root.withdraw()
    try:
        lf = AccountLoginFrame(root)
        lf.proxy_var.set("103.151.123.45:8080:myuser:mypass")
        assert lf.proxy_var.get() == "103.151.123.45:8080"
        assert lf.proxy_user_var.get() == "myuser"
        assert lf.proxy_pass_var.get() == "mypass"
    finally:
        root.destroy()


def test_account_login_success_creates_dashboard_and_persists_settings(temp_settings):
    init_data = {
        "accounts": {
            "draft_user @ S53": {"server": 53, "username": "draft_user"},
        }
    }
    temp_settings.write_text(json.dumps(init_data), encoding="utf-8")

    app = safe_multi_account_app()
    try:
        mock_session = MagicMock()
        with patch("threading.Thread"):
            app._on_login_success(
                account_key="draft_user @ S53",
                session=mock_session,
                server_id=53,
                username="real_user",
                password="mypassword123",
                proxy_raw="socks5://127.0.0.1:1080",
                proxy_user="p_user",
                proxy_pass="p_pass",
                proxy_url="",
                proxy_pool=None,
            )

        new_key = "real_user @ S53"
        assert new_key in app.accounts
        assert app.accounts[new_key]["password"] == "mypassword123"  # RAM ONLY
        assert app.accounts[new_key]["session"] is mock_session

        # Kiểm tra file json trên ổ đĩa KHÔNG LƯU MẬT KHẨU
        saved = json.loads(temp_settings.read_text(encoding="utf-8"))
        assert new_key in saved["accounts"]
        assert "password" not in saved["accounts"][new_key]
        assert saved["accounts"][new_key]["username"] == "real_user"
        assert saved["accounts"][new_key]["server"] == 53
        assert saved["accounts"][new_key]["proxy"] == "socks5://127.0.0.1:1080"

        # Kiểm tra thẻ đã cập nhật thành Đã kết nối
        card = app.cards[new_key]
        assert card.is_connected is True
        assert "Đã kết nối" in card.badge_lbl.cget("text")

        # Kiểm tra Dashboard đã được tạo
        dash = app.dashboards.get(new_key)
        assert dash is not None
        assert dash.server_id == 53
        assert dash.username == "real_user"
    finally:
        app.destroy()


def test_multi_account_app_logout_clears_ram_password_and_destroys_dashboard(temp_settings):
    init_data = {
        "accounts": {
            "user1 @ S53": {"server": 53, "username": "user1"},
        }
    }
    temp_settings.write_text(json.dumps(init_data), encoding="utf-8")
    app = safe_multi_account_app()
    try:
        mock_session = MagicMock()
        with patch("threading.Thread"):
            app._on_login_success(
                account_key="user1 @ S53",
                session=mock_session,
                server_id=53,
                username="user1",
                password="secret_in_ram",
                proxy_raw="",
                proxy_user="",
                proxy_pass="",
                proxy_url="",
                proxy_pool=None,
            )
        assert app.accounts["user1 @ S53"]["password"] == "secret_in_ram"
        assert "user1 @ S53" in app.dashboards

        # Thực hiện Đăng xuất
        app._on_logout("user1 @ S53")
        assert app.accounts["user1 @ S53"]["password"] == ""  # Mật khẩu trong RAM đã bị xóa
        assert app.accounts["user1 @ S53"]["session"] is None
        assert "user1 @ S53" not in app.dashboards
        assert app.cards["user1 @ S53"].is_connected is False
        assert "Chưa đăng nhập" in app.cards["user1 @ S53"].badge_lbl.cget("text")
    finally:
        app.destroy()


def test_multi_account_app_delete_account_removes_from_settings(temp_settings):
    init_data = {
        "accounts": {
            "user1 @ S53": {"server": 53, "username": "user1"},
            "user2 @ S57": {"server": 57, "username": "user2"},
        }
    }
    temp_settings.write_text(json.dumps(init_data), encoding="utf-8")
    app = safe_multi_account_app()
    try:
        with patch("tkinter.messagebox.askyesno", return_value=True):
            app._on_delete_account("user1 @ S53")

        assert "user1 @ S53" not in app.accounts
        assert "user1 @ S53" not in app.cards

        saved = json.loads(temp_settings.read_text(encoding="utf-8"))
        assert "user1 @ S53" not in saved["accounts"]
        assert "user2 @ S57" in saved["accounts"]
    finally:
        app.destroy()


def test_multi_account_app_batch_controls(temp_settings):
    app = safe_multi_account_app()
    try:
        mock_dash1 = MagicMock()
        mock_dash1.winfo_exists.return_value = True
        mock_dash2 = MagicMock()
        mock_dash2.winfo_exists.return_value = True

        app.dashboards["acc1 @ S53"] = mock_dash1
        app.dashboards["acc2 @ S57"] = mock_dash2

        with patch("tkinter.messagebox.showinfo"):
            app._batch_start_all()
            mock_dash1.engine.start_all.assert_called_once()
            mock_dash2.engine.start_all.assert_called_once()

            app._batch_stop_all()
            mock_dash1.engine.stop_all.assert_called_once()
            mock_dash2.engine.stop_all.assert_called_once()
    finally:
        app.destroy()


def test_multi_account_app_poll_statuses_updates_badges_and_detects_captcha(temp_settings):
    init_data = {
        "accounts": {
            "acc1 @ S53": {"server": 53, "username": "acc1"},
        }
    }
    temp_settings.write_text(json.dumps(init_data), encoding="utf-8")
    app = safe_multi_account_app()
    try:
        mock_dash = MagicMock()
        mock_dash.winfo_exists.return_value = True
        mock_dash._tp_running = True
        mock_dash._bm_runner = None
        mock_dash._bld_runner = None
        mock_dash._res_runner = None
        mock_dash._morale_runner = None
        mock_dash._craft_running = False
        mock_dash._gd_runner = None
        mock_dash.engine.tasks = {}

        app.dashboards["acc1 @ S53"] = mock_dash

        # Polling bình thường: đang chạy Thảo Phạt
        app._poll_statuses()
        card = app.cards["acc1 @ S53"]
        assert "Đang chạy" in card.badge_lbl.cget("text")
        assert "Thảo Phạt" in card.task_lbl.cget("text")

        # Giả lập phát hiện Captcha
        task_mock = MagicMock()
        task_mock.last_error = "Server yêu cầu Captcha!"
        mock_dash.engine.tasks = {"tp": task_mock}

        app._poll_statuses()
        assert "Cần giải Captcha" in card.badge_lbl.cget("text")
    finally:
        app.destroy()



def test_multi_account_app_coffee_button_and_dialog(temp_settings):
    app = safe_multi_account_app()
    try:
        assert hasattr(app, "coffee_btn")
        assert app.coffee_btn.cget("text") == "☕ Buy me a coffee"

        # Gọi mở dialog ủng hộ tác giả
        app._show_coffee_dialog()
        # Tìm Toplevel con của app
        toplevels = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
        assert len(toplevels) == 1
        dlg = toplevels[0]
        assert "Buy Me A Coffee" in dlg.title()

        # Kiểm tra nội dung văn bản tri ân
        labels = []
        for w in dlg.winfo_children():
            if isinstance(w, tk.Label):
                labels.append(w.cget("text"))
            if hasattr(w, "winfo_children"):
                for child in w.winfo_children():
                    if isinstance(child, tk.Label):
                        labels.append(child.cget("text"))
        assert any("Cảm ơn bạn đã tin tưởng" in txt for txt in labels)
        assert not any("Không tìm thấy tệp mã QR" in txt for txt in labels)

        dlg.destroy()
    finally:
        app.destroy()


def test_multi_account_app_relogin_after_logout_button_is_enabled(temp_settings, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_data = {
        "accounts": {
            "user1 @ S53": {"server": 53, "username": "user1"},
        }
    }
    temp_settings.write_text(json.dumps(init_data), encoding="utf-8")
    app = safe_multi_account_app()
    state = {"phase": "init", "logout_btn_disabled": None, "logout_pass": None, "logout_status": None, "relogged_in": False, "error": None}
    try:
        with patch("linhvuong.gui.login"), patch("linhvuong.dashboard.GatewayClient"):
            def step_login1():
                lf = app.login_frames["user1 @ S53"]
                lf.pass_var.set("secret1")
                lf.btn.invoke()
                state["phase"] = "wait_login1"
                app.after(20, poll)

            def poll(attempts=0):
                if attempts > 100:
                    state["error"] = f"Timeout in phase {state['phase']}"
                    app.quit()
                    return
                if state["phase"] == "wait_login1":
                    if "user1 @ S53" in app.dashboards:
                        app._on_logout("user1 @ S53")
                        lf_after = app.login_frames.get("user1 @ S53")
                        state["logout_btn_disabled"] = lf_after.btn.instate(["disabled"]) if lf_after else None
                        state["logout_pass"] = lf_after.pass_var.get() if lf_after else None
                        state["logout_status"] = lf_after.status.get() if lf_after else None
                        if lf_after and not state["logout_btn_disabled"]:
                            lf_after.pass_var.set("secret2")
                            lf_after.btn.invoke()
                            state["phase"] = "wait_login2"
                            app.after(20, poll, 0)
                            return
                        app.quit()
                        return
                elif state["phase"] == "wait_login2":
                    if "user1 @ S53" in app.dashboards:
                        state["relogged_in"] = True
                        app.quit()
                        return
                app.after(20, poll, attempts + 1)

            app.after(10, step_login1)
            app.mainloop()

        assert state["error"] is None, state["error"]
        assert state["logout_btn_disabled"] is False
        assert state["logout_pass"] == ""
        assert state["logout_status"] == ""
        assert state["relogged_in"] is True
    finally:
        app.destroy()
