"""Kiểm thử WorkspaceManager, AccountSession, Auto-Resume, FastAPI Web Dashboard & WebSocket."""

import json
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from linhvuong import cli
from linhvuong.notifications import reset_notified_bosses
from linhvuong.profile import Profile, ProfileStore
from linhvuong.roster import City, General, Roster
import linhvuong.runtime as runtime_mod
from linhvuong.runtime import WorkspaceManager
from linhvuong.security import WebAdminAuth
from linhvuong.web.app import create_app


def _fake_roster() -> Roster:
    r = Roster()
    r.cities = [City(id=1001, name="Lạc Dương", type="Thành", pos_x=10, pos_y=20)]
    r.camps = [City(id=-2001, name="Trại 1", type="Doanh trại", pos_x=12, pos_y=22)]
    r._generals = {
        1001: [
            General(id=1, name="Triệu Vân", role="vo", level=50, stamina=100, stamina_max=100, morale=95, loyalty=100),
            General(id=2, name="Gia Cát Lượng", role="van", level=60, stamina=100, stamina_max=100, morale=100, loyalty=100),
        ]
    }
    return r


def _mock_offline(monkeypatch):
    monkeypatch.setattr(runtime_mod, "login", lambda *a, **kw: None)
    monkeypatch.setattr(runtime_mod, "fetch_roster", lambda gw: _fake_roster())
    monkeypatch.setattr(runtime_mod.AccountSession, "start_aux_loop", lambda self: None)


def test_workspace_login_vault_and_auto_resume(tmp_path, monkeypatch):
    _mock_offline(monkeypatch)

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=True, vault_key="vault-secret-123")
    sess = wm.login_account(
        server_id=53,
        username="tester",
        password="pw",
        save_to_vault=True,
        auto_resume=True,
    )
    assert sess.account_key == "tester @ S53"
    settings_json = (tmp_path / "gui_settings.json").read_text(encoding="utf-8")
    assert "pw" not in settings_json

    # Giả lập đang chạy tác vụ research trước khi shutdown
    sess.engine.is_running = lambda tid: tid == "research"  # type: ignore[method-assign]
    wm.graceful_shutdown()

    # Khởi động lại WorkspaceManager trên cùng data_dir và vault_key
    resumed_calls = []
    wm2 = WorkspaceManager(data_dir=tmp_path, acquire_lock=True, vault_key="vault-secret-123")
    monkeypatch.setattr(
        runtime_mod.AccountSession,
        "resume_tasks",
        lambda self, names: resumed_calls.append((self.account_key, list(names))) or list(names),
    )
    restored = wm2.auto_restore_on_startup()
    assert restored["restored_accounts"] == ["tester @ S53"]
    assert resumed_calls == [("tester @ S53", ["research"])]
    wm2.graceful_shutdown()


def test_account_session_captcha_pause_and_resume(tmp_path, monkeypatch):
    reset_notified_bosses()
    _mock_offline(monkeypatch)

    events = []
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    wm.subscribe(lambda key, ev, payload: events.append((key, ev, payload)))
    sess = wm.login_account(server_id=53, username="capuser", password="pw")

    sess._handle_captcha("Captcha test 110")
    assert sess.captcha_required is True
    assert sess.get_status_snapshot()["status"] == "captcha"
    assert any(ev == "captcha_alert" for _, ev, _ in events)

    sess.engine.resume = MagicMock()  # type: ignore[method-assign]
    sess.engine.list_tasks = lambda: ["building"]  # type: ignore[method-assign]
    sess.resume_after_captcha()
    assert sess.captcha_required is False
    assert sess.get_status_snapshot()["status"] == "connected"
    sess.engine.resume.assert_called_once_with("building")
    wm.graceful_shutdown()


def test_web_app_auth_profile_sync_logs_and_websocket(tmp_path, monkeypatch):
    _mock_offline(monkeypatch)

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=True, vault_key="vault-k")
    auth = WebAdminAuth(data_dir=tmp_path, host="0.0.0.0", env_username="admin", env_password="webpassword")
    app = create_app(workspace=wm, auth=auth, host="0.0.0.0", auto_restore=False)

    with TestClient(app) as client:
        # 1. Chưa đăng nhập -> 401
        r_unauth = client.get("/api/accounts")
        assert r_unauth.status_code == 401

        # 2. Trang chủ trả HTML
        assert client.get("/").status_code == 200

        # 3. Đăng nhập Web Admin sai -> 401, đúng -> 200 + cookie
        assert client.post("/api/auth/login", json={"username": "admin", "password": "bad"}).status_code == 401
        r_ok = client.post("/api/auth/login", json={"username": "admin", "password": "webpassword"})
        assert r_ok.status_code == 200

        # 4. Metadata
        meta = client.get("/api/meta").json()
        assert meta["vault_unlocked"] is True
        assert len(meta["missions"]) == 8

        # 5. Đăng nhập game account & đồng bộ Profile qua API
        r_login = client.post(
            "/api/accounts/login",
            json={"server_id": 53, "username": "webplayer", "password": "secret", "save_to_vault": True},
        )
        assert r_login.status_code == 200
        snap = r_login.json()["snapshot"]
        assert snap["summary"]["account_key"] == "webplayer @ S53"

        r_prof = client.put(
            "/api/accounts/webplayer%20%40%20S53/profile",
            json={"building": {"slots": 2, "interval": "25"}},
        )
        assert r_prof.status_code == 200
        assert r_prof.json()["profile"]["building"]["slots"] == 2

        loaded_prof = ProfileStore.load(tmp_path / "auto_profile_webplayer_53.json")
        assert loaded_prof.building.slots == 2
        assert loaded_prof.building.interval == "25"

        # 6. WebSocket realtime kết nối được khi có cookie phiên hợp lệ
        with client.websocket_connect("/ws") as ws:
            hello = ws.receive_json()
            assert hello["event"] == "connected"
            assert any(a["account_key"] == "webplayer @ S53" for a in hello["accounts"])

        # 7. Xem & bảo vệ đường dẫn tệp log
        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "bot_webplayer_S53.log").write_text("hello log\n", encoding="utf-8")
        r_logs = client.get("/api/logs/files")
        assert r_logs.status_code == 200
        assert any(f["name"] == "bot_webplayer_S53.log" for f in r_logs.json()["files"])
        r_tail = client.get("/api/logs/files/bot_webplayer_S53.log?lines=10")
        assert r_tail.status_code == 200
        assert "hello log" in r_tail.text

    wm.graceful_shutdown()


def test_cli_web_help():
    with pytest.raises(SystemExit) as exc:
        cli.main(["web", "--help"])
    assert exc.value.code == 0


def test_system_alert_dedup_and_web_event(monkeypatch):
    from linhvuong.notifications import NotificationConfig, dispatch_system_alert, reset_system_alert

    reset_notified_bosses()
    web_events = []
    sent_tg = []
    monkeypatch.setattr(
        "linhvuong.notifications.send_telegram_message",
        lambda bot_token, chat_id, message: sent_tg.append((bot_token, chat_id, message)) or (True, "ok"),
    )
    cfg = NotificationConfig(
        web_enabled=True,
        telegram_enabled=True,
        telegram_alert_captcha=True,
        telegram_bot_token="tok",
        telegram_chat_id="cid",
    )

    assert dispatch_system_alert(
        "captcha", "u @ S53", "Captcha", "msg1", config=cfg, on_web_event=web_events.append
    ) is True
    # Deduplicated second call
    assert dispatch_system_alert(
        "captcha", "u @ S53", "Captcha", "msg2", config=cfg, on_web_event=web_events.append
    ) is False
    assert len(web_events) == 1

    reset_system_alert("u @ S53", "captcha")
    assert dispatch_system_alert(
        "captcha", "u @ S53", "Captcha", "msg3", config=cfg, on_web_event=web_events.append
    ) is True
    assert len(web_events) == 2


def test_web_ws_rejects_unauth_and_building_fetch(tmp_path, monkeypatch):
    from starlette.websockets import WebSocketDisconnect

    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=True)
    auth = WebAdminAuth(data_dir=tmp_path, host="0.0.0.0", env_username="admin", env_password="pw")
    app = create_app(workspace=wm, auth=auth, host="0.0.0.0", auto_restore=False)

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws"):
                pass

        assert client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
        r_login = client.post(
            "/api/accounts/login",
            json={"server_id": 53, "username": "blduser", "password": "pw"},
        )
        assert r_login.status_code == 200

        sess = wm.get_session("blduser @ S53")
        sess.gateway.call = lambda ep, api_id, params=None: (  # type: ignore[method-assign]
            {"infos": [[1, 1, "官府", 5], [2, 3, "民房", 3]]}
            if ep == "City.ashx" and api_id == 5
            else {"ret": 0}
        )
        r_bld = client.post(
            "/api/accounts/blduser%20%40%20S53/buildings/fetch",
            json={"city_id": 1001},
        )
        assert r_bld.status_code == 200
        plans = r_bld.json()["plans"]
        assert len(plans) == 2
        assert plans[0]["cur_lvl"] == 5

    wm.graceful_shutdown()


def test_systemd_unit_execstart_no_bash_default_expansion_and_env_parser(monkeypatch):
    from pathlib import Path
    from linhvuong.web.server import build_parser

    repo_root = Path(__file__).resolve().parents[1]
    service_text = (repo_root / "deploy" / "ubuntu" / "linhvuong-web.service").read_text(encoding="utf-8")
    install_text = (repo_root / "deploy" / "ubuntu" / "install.sh").read_text(encoding="utf-8")

    # systemd ExecStart không hỗ trợ cú pháp bash ${VAR:-default}; phải để server.py tự đọc env hoặc dùng ExecStart thuần
    exec_lines = [
        line.strip()
        for line in (service_text + "\n" + install_text).splitlines()
        if line.strip().startswith("ExecStart=")
    ]
    assert exec_lines, "Phải có dòng ExecStart= trong unit systemd"
    for line in exec_lines:
        assert ":-" not in line, f"ExecStart không được chứa bash default expansion: {line}"

    # Kiểm tra các tham số và giá trị mặc định trong install.sh
    for expected in (
        'VERSION="${VERSION:-latest}"',
        'WEB_HOST="${WEB_HOST:-${LINHVUONG_WEB_HOST:-0.0.0.0}}"',
        'WEB_PORT="${WEB_PORT:-${LINHVUONG_WEB_PORT:-8080}}"',
        'WEB_PASSWORD="${WEB_PASSWORD:-${LINHVUONG_WEB_PASSWORD:-admin}}"',
        "--version)",
        "--host)",
        "--port)",
        "--web-password)",
    ):
        assert expected in install_text, f"Thiếu cấu hình {expected} trong install.sh"

    # Server phải đọc LINHVUONG_WEB_HOST/PORT an toàn kể cả khi biến môi trường rỗng
    monkeypatch.setenv("LINHVUONG_WEB_HOST", "")
    monkeypatch.setenv("LINHVUONG_WEB_PORT", "")
    args = build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000

    monkeypatch.setenv("LINHVUONG_WEB_HOST", "0.0.0.0")
    monkeypatch.setenv("LINHVUONG_WEB_PORT", "9090")
    args_env = build_parser().parse_args([])
    assert args_env.host == "0.0.0.0"
    assert args_env.port == 9090
