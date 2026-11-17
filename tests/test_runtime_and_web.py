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


def test_web_start_binhman_and_goidan_combat_config_on_web_event(tmp_path, monkeypatch):
    _mock_offline(monkeypatch)
    reset_notified_bosses()

    events = []
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    wm.subscribe(lambda key, ev, payload: events.append((key, ev, payload)))
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="webpassword")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "webpassword"}).status_code == 200
        assert client.post(
            "/api/accounts/login",
            json={"server_id": 53, "username": "bmuser", "password": "secret"},
        ).status_code == 200

        sess = wm.get_session("bmuser @ S53")
        assert sess is not None
        started = {}

        def _fake_start(name, runnable, **kwargs):
            started[name] = runnable

        monkeypatch.setattr(sess.engine, "start", _fake_start)

        assert client.put(
            "/api/accounts/bmuser%20%40%20S53/profile",
            json={
                "binh_man": {"bases": {"1001": {"enabled": True, "generals": [1]}}},
                "goi_dan": {"city_id": 1001, "generals": [1]},
            },
        ).status_code == 200

        r_bm = client.post("/api/accounts/bmuser%20%40%20S53/tasks/binhman/start")
        assert r_bm.status_code == 200
        assert r_bm.json()["ok"] is True
        bm_cfg = started["binhman"].tasks[0].combat_config
        assert callable(bm_cfg.on_web_event)
        bm_cfg.on_web_event({"kind": "boss", "title": "Boss test"})
        assert any(ev == "notification" and p.get("title") == "Boss test" for _, ev, p in events)

        r_gd = client.post("/api/accounts/bmuser%20%40%20S53/tasks/goidan/start")
        assert r_gd.status_code == 200
        assert r_gd.json()["ok"] is True
        assert callable(started["goidan"].combat_config.on_web_event)

    wm.graceful_shutdown()


def test_battle_track_forwards_on_web_event_to_boss_alert(monkeypatch):
    from linhvuong.battle import BattleEngine, BattleState, BattleTroop, CombatConfig
    import linhvuong.notifications as notif_mod

    reset_notified_bosses()
    captured = {}

    def _fake_dispatch(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(notif_mod, "dispatch_boss_alert", _fake_dispatch)

    gw = MagicMock()
    gw.user_id = 100
    gw.server_id = 53
    web_events = []
    cfg = CombatConfig(
        auto_counter_formation=False,
        leave_boss_last=True,
        on_web_event=lambda ev: web_events.append(ev),
    )
    engine = BattleEngine(gw, config=cfg)

    our = BattleTroop(
        position=1, player_name="p", user_id=100, general_name="Triệu Vân",
        general_id=1, city_id=1001, formation_id=1, morale=100,
        soldiers=1000, initial_soldiers=1000, flag=0x10,
    )
    boss = BattleTroop(
        position=11, player_name="npc", user_id=0, general_name="Mạnh Hoạch",
        general_id=99, city_id=0, formation_id=1, morale=100,
        soldiers=5000, initial_soldiers=5000, flag=0x20, is_boss=True,
    )
    boss_state = BattleState(
        ret=0,
        site="Trại Man",
        map_id=0,
        bout=1,
        bout_left=20,
        attack_total=1000,
        defend_total=5000,
        our_troops=[our],
        enemy_troops=[boss],
        boss_troops=[boss],
    )
    monkeypatch.setattr(engine, "get_battle_info", lambda bid: boss_state if bid == 777 else None)
    monkeypatch.setattr(engine, "execute_stratagems", lambda *a, **kw: None)
    monkeypatch.setattr(engine, "assign_combat_orders", lambda *a, **kw: None)

    engine.track_battle(777, max_bouts=1, sleep_fn=lambda _s: None)
    assert captured.get("on_web_event") is cfg.on_web_event


def test_web_vault_autostart_endpoints_and_auto_restore(tmp_path, monkeypatch):
    monkeypatch.delenv("LINHVUONG_VAULT_KEY", raising=False)
    _mock_offline(monkeypatch)

    # WorkspaceManager tự mở khóa Két ngay cả khi không đặt LINHVUONG_VAULT_KEY
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=True)
    assert wm.vault.is_unlocked()
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="webpassword")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    with TestClient(app) as client:
        html = client.get("/").text
        assert 'id="profile-header-bar"' in html
        assert 'id="hdr-save-vault"' in html
        assert 'id="hdr-auto-resume"' in html
        assert 'id="btn-autostart-cfg"' in html

        assert client.post("/api/auth/login", json={"username": "admin", "password": "webpassword"}).status_code == 200
        assert client.post(
            "/api/accounts/login",
            json={"server_id": 53, "username": "autouser", "password": "secret-pw", "save_to_vault": False},
        ).status_code == 200

        # Lưu mật khẩu từ session RAM vào Két qua /vault
        r_v1 = client.post("/api/accounts/autouser%20%40%20S53/vault", json={"save": True})
        assert r_v1.status_code == 200
        assert r_v1.json()["account"]["has_vault_password"] is True

        # Cấu hình tự động khởi chạy + tắt auto_resume
        r_as = client.put(
            "/api/accounts/autouser%20%40%20S53/autostart",
            json={"auto_resume": False, "auto_start_tasks": ["building", "binhman", "invalid_task"]},
        )
        assert r_as.status_code == 200
        acc = r_as.json()["account"]
        assert acc["config"]["auto_resume"] is False
        assert acc["config"]["auto_start_tasks"] == ["building", "binhman"]

        # Kiểm tra metadata trả danh sách lựa chọn auto_start_task_options
        meta = client.get("/api/meta").json()
        assert any(o["id"] == "binhman" for o in meta["auto_start_task_options"])

        # Giả lập đang chạy 'research' trước khi tắt server
        sess = wm.get_session("autouser @ S53")
        sess.engine.is_running = lambda tid: tid == "research"  # type: ignore[method-assign]

    wm.graceful_shutdown()

    # Khởi động lại: tự mở khóa bằng .vault.key, tự chạy auto_start_tasks (building, binhman) và không chạy lại 'research' vì auto_resume=False
    resumed_calls = []
    wm2 = WorkspaceManager(data_dir=tmp_path, acquire_lock=True)
    monkeypatch.setattr(
        runtime_mod.AccountSession,
        "resume_tasks",
        lambda self, names: resumed_calls.append((self.account_key, list(names))) or list(names),
    )
    restored = wm2.auto_restore_on_startup()
    assert restored["restored_accounts"] == ["autouser @ S53"]
    assert resumed_calls == [("autouser @ S53", ["building", "binhman"])]

    # Bật lại auto_resume=True -> gộp cả auto_start_tasks lẫn running_tasks trước khi tắt (không trùng)
    wm2.update_account_autostart("autouser @ S53", auto_resume=True, auto_start_tasks=["building"])
    wm2.graceful_shutdown()

    resumed_calls.clear()
    wm3 = WorkspaceManager(data_dir=tmp_path, acquire_lock=True)
    # Ghi lại runtime_state có research đang chạy
    from linhvuong.paths import runtime_state_path
    runtime_state_path(tmp_path).write_text(
        json.dumps({"version": 1, "accounts": {"autouser @ S53": {"running_tasks": ["building", "research"]}}}),
        encoding="utf-8",
    )
    restored3 = wm3.auto_restore_on_startup()
    assert restored3["restored_accounts"] == ["autouser @ S53"]
    assert resumed_calls == [("autouser @ S53", ["building", "research"])]
    wm3.graceful_shutdown()


def test_web_stop_binhman_does_not_deadlock_and_keeps_api_responsive(tmp_path, monkeypatch):
    import threading
    from linhvuong.tasks.binh_man import BinhMan

    _mock_offline(monkeypatch)
    entered_run = threading.Event()
    monkeypatch.setattr(BinhMan, "run_once", lambda self: (entered_run.set(), self.sleep_fn(10.0), "ok")[-1])

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="webpassword")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    outcome = {}

    def _run():
        with TestClient(app) as client:
            assert client.post("/api/auth/login", json={"username": "admin", "password": "webpassword"}).status_code == 200
            assert client.post(
                "/api/accounts/login",
                json={"server_id": 53, "username": "quilia", "password": "secret"},
            ).status_code == 200
            assert client.put(
                "/api/accounts/quilia%20%40%20S53/profile",
                json={"binh_man": {"bases": {"1001": {"enabled": True, "generals": [1]}}}},
            ).status_code == 200

            assert client.post("/api/accounts/quilia%20%40%20S53/tasks/binhman/start").status_code == 200
            assert entered_run.wait(timeout=2.0)

            r_stop = client.post("/api/accounts/quilia%20%40%20S53/tasks/binhman/stop")
            r_accs = client.get("/api/accounts")
            outcome["stop_code"] = r_stop.status_code
            outcome["accs_code"] = r_accs.status_code

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout=3.0)
    assert not th.is_alive(), "POST /tasks/binhman/stop hoặc GET /api/accounts bị treo deadlock!"
    assert outcome == {"stop_code": 200, "accs_code": 200}

    sess = wm.get_session("quilia @ S53")
    assert sess is not None
    runner = sess.engine.get_runner("binhman")
    if runner:
        runner.join(timeout=1.5)
        assert not runner.is_alive()
    wm.graceful_shutdown()
