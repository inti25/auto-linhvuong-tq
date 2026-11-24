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
        sess.gateway.building_list = lambda cid: {  # type: ignore[method-assign]
            "ret": 0,
            "items": [
                {"m_lpos": 1, "m_lgid": 1, "m_szname": "官府", "m_llevel": 5},
                {"m_lpos": 2, "m_lgid": 3, "m_szname": "民房", "m_llevel": 3},
            ],
        }
        sess.gateway.call = lambda ep, api_id, params=None: {"ret": 0}  # type: ignore[method-assign]
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


def test_aux_countdown_ticks_in_snapshot_and_app_js_has_ticker(tmp_path, monkeypatch):
    import requests
    from pathlib import Path
    from linhvuong.runtime import AccountSession

    now = [1000.0]
    monkeypatch.setattr(runtime_mod.time, "monotonic", lambda: now[0])

    sess = AccountSession("aux @ S53", requests.Session(), 53, "aux", data_dir=tmp_path)
    sess.gateway.page_building = lambda cid: {"ret": 0, "plus_finish": 120}  # type: ignore[method-assign]
    sess.gateway.call = lambda ep, api_id, params=None: (  # type: ignore[method-assign]
        {"ret": 0, "left": 45}
        if ep == "Common.ashx" and api_id == 140
        else {"ret": 0, "plus_finish": 0}
    )
    monkeypatch.setattr(runtime_mod, "parse_boost_remaining_time", lambda resp, cid: 120)

    sess._check_boost_once()
    sess._check_explore_once()
    a0 = sess.get_aux_status()
    assert a0["boost_left_seconds"] == 120
    assert a0["explore_left_seconds"] == 45

    now[0] += 5.0
    a1 = sess.get_aux_status()
    assert a1["boost_left_seconds"] == 115
    assert a1["explore_left_seconds"] == 40

    now[0] += 100.0
    a2 = sess.get_aux_status()
    assert a2["boost_left_seconds"] == 15
    assert a2["explore_left_seconds"] == 0

    sess.destroy()

    app_js = (Path(__file__).resolve().parents[1] / "linhvuong" / "web" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "setInterval(" in app_js
    assert "renderAuxCountdownsOnly" in app_js


def test_resource_monitor_uses_s58_city_and_resource_info(tmp_path):
    import threading
    import time
    import requests
    from linhvuong.roster import City, Roster
    from linhvuong.runtime import AccountSession

    sess = AccountSession("resmon @ S58", requests.Session(), 58, "resmon", data_dir=tmp_path)
    sess.roster = Roster(cities=[City(id=401, name="ThienCo")])
    sess.profile.resource.resource_cities = [401]
    sess.profile.resource.gold_threshold = 10000
    sess.profile.resource.gold_box_idx = 4
    sess.profile.resource.tn_box_idx = 4
    sess.profile.resource.wood_pct = 70.0
    sess.profile.resource.iron_pct = 70.0
    sess.profile.resource.stone_pct = 70.0
    sess.profile.resource.food_pct = 70.0

    opened_boxes: list[tuple[int, str]] = []
    switched_cities: list[int] = []
    opened_event = threading.Event()
    mode = {"case": "high_gold_low_wood"}

    def fake_city_info(cid: int):
        if mode["case"] == "api_error":
            return {"ret": -1}
        return {"ret": 0, "m_lmoney_balance": 2_000_000}

    def fake_resource_info(cid: int):
        if mode["case"] == "api_error":
            return None
        return {
            "ret": 0,
            "m_lwood_balance": 100,
            "m_liron_balance": 900_000,
            "m_lstone_balance": 900_000,
            "m_lfood_balance": 900_000,
            "m_lmax_storage": 1_000_000,
        }

    def fake_set_current_city(cid: int):
        switched_cities.append(cid)
        return {"ret": 0}

    def fake_call(ep, api_id, params=None):
        if ep == "Common.ashx" and api_id == 48:
            opened_boxes.append((int(params["lBoxID"]), mode["case"]))
            opened_event.set()
            return {"ret": 0}
        return {"ret": 0}

    sess.gateway.city_info = fake_city_info  # type: ignore[method-assign]
    sess.gateway.resource_info = fake_resource_info  # type: ignore[method-assign]
    sess.gateway.set_current_city = fake_set_current_city  # type: ignore[method-assign]
    sess.gateway.call = fake_call  # type: ignore[method-assign]

    sess.start_resource_monitor()
    assert opened_event.wait(timeout=2.0)
    sess.stop_resource_monitor()
    if sess._res_monitor_thread:
        sess._res_monitor_thread.join(timeout=1.5)

    assert switched_cities == [401]
    assert opened_boxes == [(24, "high_gold_low_wood")]
    logs_text = "\n".join(str(x) for x in sess.logs["building"])
    assert "Vàng=" not in logs_text
    assert "Khoáng sản dưới ngưỡng" in logs_text

    # Khi API trả lỗi (None / ret != 0), tuyệt đối không suy thành vàng=0 để mở rương
    opened_boxes.clear()
    switched_cities.clear()
    mode["case"] = "api_error"
    sess.start_resource_monitor()
    time.sleep(0.2)
    sess.stop_resource_monitor()
    if sess._res_monitor_thread:
        sess._res_monitor_thread.join(timeout=1.5)
    assert opened_boxes == []
    assert switched_cities == []
    sess.destroy()


def test_start_all_accounts_skips_resource_monitor(tmp_path):
    import requests
    from linhvuong.runtime import AccountSession, WorkspaceManager

    wm = WorkspaceManager(data_dir=tmp_path)
    sess = AccountSession("batch @ S58", requests.Session(), 58, "batch", data_dir=tmp_path)
    called_tasks: list[str] = []
    sess.resume_tasks = lambda names: called_tasks.extend(names) or list(names)  # type: ignore[method-assign]
    wm.sessions[sess.account_key] = sess

    assert wm.start_all_accounts() == 1
    assert "resource_monitor" not in called_tasks
    assert "building" in called_tasks
    assert "binhman" in called_tasks
    wm.graceful_shutdown()


def test_s58_boost_and_building_list_use_rest_apis(tmp_path):
    import requests
    from linhvuong.roster import City, Roster
    from linhvuong.runtime import AccountSession

    sess = AccountSession("s58api @ S58", requests.Session(), 58, "s58api", data_dir=tmp_path)
    sess.roster = Roster(cities=[City(id=10129, name="1")])
    sess.profile.building.auto_boost = True

    legacy_calls: list[tuple[str, int]] = []

    def fail_if_legacy_call(ep, api_id, params=None):
        legacy_calls.append((ep, api_id))
        return {"ret": 1}

    sess.gateway.call = fail_if_legacy_call  # type: ignore[method-assign]
    sess.gateway.page_building = lambda cid: {"ret": 0, "plus_finish": 4125000, "list": []}  # type: ignore[method-assign]
    sess.gateway.building_list = lambda cid: {  # type: ignore[method-assign]
        "ret": 0,
        "items": [{"m_lpos": 1, "m_lgid": 4, "m_llevel": 30, "m_szname": "仓库"}],
    }

    sess._check_boost_once()
    assert sess.get_aux_status()["boost_left_seconds"] == 4125000
    assert legacy_calls == []

    plans = sess.fetch_city_buildings(10129)
    assert len(plans) == 1
    assert plans[0]["pid"] == 1
    assert plans[0]["gid"] == 4
    assert plans[0]["cur_lvl"] == 30
    assert legacy_calls == []
    sess.destroy()


def test_web_scroll_preserved_on_rerender_and_logs():
    import os
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")

    app_js_path = Path(__file__).resolve().parents[1] / "linhvuong" / "web" / "static" / "app.js"
    js_test = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const appCode = fs.readFileSync(process.env.APP_JS_PATH, "utf8");

function makeEl(tag, id = "", className = "") {
  const el = {
    tagName: tag.toUpperCase(),
    id,
    className,
    dataset: {},
    style: {},
    children: [],
    listeners: {},
    _innerHTML: "",
    _textContent: "",
    scrollTop: 0,
    scrollLeft: 0,
    scrollHeight: 1000,
    clientHeight: 200,
    value: "",
    checked: false,
    disabled: false,
    classList: {
      _set: new Set(className ? className.split(/\s+/) : []),
      add(...xs) { xs.forEach((x) => this._set.add(x)); },
      remove(...xs) { xs.forEach((x) => this._set.delete(x)); },
      toggle(x, force) {
        if (force === undefined) {
          if (this._set.has(x)) this._set.delete(x); else this._set.add(x);
        } else if (force) this._set.add(x); else this._set.delete(x);
      },
      contains(x) { return this._set.has(x); },
    },
    addEventListener(ev, fn) { (this.listeners[ev] ||= []).push(fn); },
    dispatchEvent(ev) { (this.listeners[ev.type] || []).forEach((fn) => fn(ev)); },
    appendChild(ch) { this.children.push(ch); return ch; },
    remove() {},
    contains(other) {
      if (other === this) return true;
      return this.children.some((c) => c.contains && c.contains(other));
    },
    focus() { document.activeElement = this; },
    setSelectionRange() {},
    querySelectorAll(sel) {
      const out = [];
      const walk = (node) => {
        for (const c of node.children || []) {
          if (matchesSel(c, sel)) out.push(c);
          walk(c);
        }
      };
      walk(this);
      return out;
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
  };
  Object.defineProperty(el, "textContent", {
    get() { return this._textContent; },
    set(v) {
      this._textContent = String(v ?? "");
      if (this.classList.contains("log-box")) {
        const lines = this._textContent ? this._textContent.split("\n").length : 0;
        this.scrollHeight = Math.max(200, lines * 20);
      }
    },
  });
  Object.defineProperty(el, "innerHTML", {
    get() { return this._innerHTML; },
    set(v) {
      this._innerHTML = String(v ?? "");
      this.innerHTMLCount = (this.innerHTMLCount || 0) + 1;
      // Simulate browser behavior: replacing innerHTML destroys children (new scrollTop=0)
      this.children = [];
      if (this.id === "tab-content") {
        // Create 3 .table-wrap + 1 #log-internal + key controls
        for (let i = 0; i < 3; i++) {
          const tw = makeEl("div", "", "table-wrap");
          tw.scrollHeight = 1000;
          tw.clientHeight = 240;
          this.children.push(tw);
        }
        const logBox = makeEl("div", "log-internal", "log-box");
        logBox.textContent = Array.from({ length: 50 }, (_, i) => `line ${i}`).join("\n");
        this.children.push(logBox);
        registerById(logBox);
        const inp = makeEl("input", "", "bld-tgt");
        inp.dataset.pid = "1";
        this.children.push(inp);
        const chk = makeEl("input", "", "bld-chk");
        chk.dataset.pid = "1";
        this.children.push(chk);
        const ids = [
          "btn-tgl-bld","btn-tgl-res","btn-tgl-resmon","btn-bld-fetch","btn-res-fetch",
          "btn-bld-all-on","btn-bld-all-off","bld-slots","bld-speedup","bld-spd-item",
          "bld-spd-hrs","bld-interval","bld-even","aux-comfort","aux-boost","rsrc-open-bld",
          "btn-bld-all-chk","btn-bld-none-chk","bld-batch-lvl","btn-bld-set-all","btn-bld-demolish",
          "res-art","res-even","res-interval","btn-res-all","btn-res-none","res-batch-lvl",
          "btn-res-set-all","rsrc-gold","rsrc-wood","rsrc-iron","rsrc-stone","rsrc-food",
          "rsrc-gbox","rsrc-tnbox","rsrc-prefer-market","rsrc-auto-sell","rsrc-sell-pct",
          "aux-daily","aux-explore","aux-whip","aux-coin","aux-turns",
          "logi-amt","dt-x","dt-y","btn-run-explore","btn-chest-start","btn-chest-stop",
          "btn-logi-xfer","btn-logi-comfort","btn-logi-daily","btn-dt-start","btn-dt-stop","btn-clr-int-log",
          "aux-boost-lbl","aux-explore-lbl","dt-status-lbl","chest-progress-fill","chest-progress-lbl",
          "dt-camp","chest-type","chest-city","chest-times","logi-from","logi-to","logi-type",
          "btn-nc-clear","dt-origin-lbl","bld-tgt-lvl","btn-bld-up-lvl","btn-bld-down-lvl",
          "btn-bld-mv-up","btn-bld-mv-down","aux-tribute","aux-tribute-gid","btn-tribute-now",
          "aux-general-visit","aux-visit-lbl",
          "btn-apply-rsrc","btn-xfer-add","btn-xfer-del","xfer-int","btn-tgl-xfer","xfer-status-lbl",
          "btn-logi-load-stock","army-xfer-from","army-xfer-to","btn-army-xfer-load-stock",
          "army-xfer-weapon","army-xfer-loop","btn-tgl-army-xfer","btn-army-xfer-once",
          "army-xfer-status-lbl","xfer-panel-market","xfer-panel-army",
          "aux-training","aux-training-lbl","btn-open-training-aux"
        ];
        for (const cid of ids) {
          const c = makeEl("button", cid, "");
          this.children.push(c);
          registerById(c);
        }
      } else if (this.id === "account-list") {
        const card = makeEl("div", "", "account-card");
        card.dataset.key = "tester @ S53";
        this.children.push(card);
      }
    },
  });
  return el;
}

function matchesSel(el, sel) {
  return sel.split(",").map((s) => s.trim()).some((part) => {
    if (part.startsWith(".")) return el.classList.contains(part.slice(1).split(/[\s\[:]/)[0]);
    if (part.startsWith("#")) return el.id === part.slice(1);
    return el.tagName.toLowerCase() === part.split(/[\s\[:.]/)[0].toLowerCase();
  });
}

const byId = new Map();
function registerById(el) { if (el.id) byId.set(el.id, el); }

const allStaticIds = [
  "admin-login-view","app-shell","game-login-view","dashboard-view","account-list","tab-content",
  "ws-title","ws-status-pill","ws-proxy-pill","ws-realtime-pill","btn-reload-roster",
  "btn-rotate-proxy","btn-notify-settings","btn-account-logout","profile-header-bar",
  "hdr-profile-name","hdr-profile-export","hdr-save-vault","hdr-auto-resume","hdr-autostart-count",
  "captcha-banner","captcha-reason-text","toast-stack","sidebar","admin-login-form","admin-user","admin-pass",
  "admin-login-error","btn-admin-logout","btn-mobile-menu","btn-add-account","btn-start-all","btn-stop-all",
  "btn-open-syslogs","btn-admin-settings","btn-coffee","modal-close","btn-sound-toggle","btn-resume-captcha",
  "hdr-profile-import","btn-autostart-cfg","btn-free-proxy","btn-test-proxy","game-login-form","btn-game-login",
  "btn-save-acc-only","btn-delete-acc","modal-backdrop","modal-title","modal-body","modal-footer",
  "btn-relogin","hdr-profile-save","gl-server","gl-proxy","gl-server-hint"
];
for (const id of allStaticIds) registerById(makeEl("div", id, id === "tab-content" ? "ws-body" : ""));
byId.get("account-list").scrollHeight = 900;
byId.get("tab-content").scrollHeight = 1200;

const document = {
  activeElement: null,
  addEventListener: () => {},
  getElementById: (id) => byId.get(id) || null,
  querySelectorAll: (sel) => (sel === ".tab-btn" ? [] : []),
  createElement: (tag) => makeEl(tag),
};
document.activeElement = makeEl("body");

const sampleProfile = {
  building: { cities: { "1001": { enabled: true, plans: [{ pid: 1, gid: 1, name: "Quan Phủ", cur_lvl: 5, target_level: 20, enabled: true }] } }, slots: 1, interval: "20" },
  research: { city_id: 1001, techs: [{ id: 1, name: "Trồng trọt", enabled: true, target_level: 20 }], interval: "20" },
  resource: { resource_cities: [], gold_threshold: "10000" },
  logistics: {},
  ditrai: {},
  thao_phat: { generals: [] },
  binh_man: { bases: {} },
  goi_dan: { generals: [] },
  crafting: { cities: {} },
  combat: {},
  nien_thu: { generals: [] },
  notifications: {},
};
const sampleSnap = {
  summary: { account_key: "tester @ S53", status: "connected", status_text: "OK", tasks: {} },
  profile: structuredClone(sampleProfile),
  roster: { bases: [{ id: 1001, name: "Lạc Dương", display_name: "Lạc Dương", pos_x: 1, pos_y: 2 }], cities: [{ id: 1001, name: "Lạc Dương", display_name: "Lạc Dương" }], camps: [], generals: [] },
  tech_levels: {},
  logs: { building: Array.from({ length: 50 }, (_, i) => `log ${i}`), logistics: [], global: [] },
  aux: {},
};

let wsInstance = null;
class FakeWS {
  constructor() { wsInstance = this; }
  close() {}
}

let putCount = 0;
const windowObj = {
  location: { protocol: "http:", host: "127.0.0.1:8000" },
  listeners: {},
  addEventListener(ev, fn) { (this.listeners[ev] ||= []).push(fn); },
  setTimeout,
  clearTimeout,
  setInterval: () => 1,
  WebSocket: FakeWS,
  Notification: { permission: "denied" },
  confirm: () => true,
  fetch: async (url, opts) => {
    if (url === "/api/auth/status") return { status: 200, ok: true, text: async () => JSON.stringify({ auth_enabled: false, authenticated: true, username: "admin", vault_unlocked: true }) };
    if (url === "/api/meta") return { status: 200, ok: true, text: async () => JSON.stringify({ missions: [], techs: [], tech_names: [], man_targets: [], attack_action_options: [], formations: [], stratagems: [], chests: [], weapons: [], resumable_tasks: [] }) };
    if (url === "/api/accounts") return { status: 200, ok: true, text: async () => JSON.stringify({ accounts: [{ account_key: "tester @ S53", status: "connected", config: {} }] }) };
    if (url.endsWith("/snapshot")) return { status: 200, ok: true, text: async () => JSON.stringify(sampleSnap) };
    if (url.endsWith("/profile") && opts?.method === "PUT") {
      putCount++;
      wsInstance.onmessage({ data: JSON.stringify({ account_key: "tester @ S53", event: "profile_updated", payload: structuredClone(sampleProfile) }) });
      return { status: 200, ok: true, text: async () => JSON.stringify({ ok: true, profile: sampleProfile }) };
    }
    return { status: 200, ok: true, text: async () => "{}" };
  },
};
windowObj.window = windowObj;
windowObj.document = document;
windowObj.navigator = {};
Object.assign(windowObj, { Object, Array, Number, String, Boolean, Set, Map, Math, Date, JSON, Error, RegExp, Promise, encodeURIComponent, structuredClone });

(async () => {
  const ctx = vm.createContext(windowObj);
  vm.runInContext(appCode, ctx);
  for (const fn of windowObj.listeners["DOMContentLoaded"] || []) await fn();
  await new Promise((r) => setTimeout(r, 50));

  const tabRoot = byId.get("tab-content");
  const accList = byId.get("account-list");

  // Scroll all boxes to mid positions
  accList.scrollTop = 55;
  tabRoot.scrollTop = 120;
  for (const tw of tabRoot.querySelectorAll(".table-wrap")) tw.scrollTop = 120;
  byId.get("log-internal").scrollTop = 80;

  // 1. Trigger background roster_updated -> must preserve scrollTop of root, .table-wrap, #log-internal
  wsInstance.onmessage({ data: JSON.stringify({ account_key: "tester @ S53", event: "roster_updated", payload: sampleSnap.roster }) });
  assert.equal(tabRoot.scrollTop, 120, "tab-content scrollTop reset on roster_updated");
  for (const tw of tabRoot.querySelectorAll(".table-wrap")) {
    assert.equal(tw.scrollTop, 120, "table-wrap scrollTop reset on roster_updated");
  }
  assert.equal(byId.get("log-internal").scrollTop, 80, "log-internal scrollTop reset on roster_updated");

  // 2. Trigger sidebar status_changed -> must preserve account-list scrollTop
  wsInstance.onmessage({ data: JSON.stringify({ account_key: "tester @ S53", event: "status_changed", payload: { status: "connected" } }) });
  assert.equal(accList.scrollTop, 55, "account-list scrollTop reset on status_changed");

  // 3. Trigger incoming log while scrolled up -> must stay at 80; when at bottom -> follow to bottom
  wsInstance.onmessage({ data: JSON.stringify({ account_key: "tester @ S53", event: "log", payload: { channel: "building", line: "new line 1" } }) });
  assert.equal(byId.get("log-internal").scrollTop, 80, "log-internal jumped while scrolled up");
  const box = byId.get("log-internal");
  box.scrollTop = box.scrollHeight - box.clientHeight;
  wsInstance.onmessage({ data: JSON.stringify({ account_key: "tester @ S53", event: "log", payload: { channel: "building", line: "new line 2" } }) });
  assert.equal(box.scrollTop, box.scrollHeight, "log-internal did not auto-scroll when at bottom");

  // 4. Self-initiated profile save (checkbox + delayed PUT/WS echo) must NOT wipe DOM/focus
  const rendersBefore = tabRoot.innerHTMLCount;
  const tgtInput = tabRoot.querySelector(".bld-tgt");
  tgtInput.focus();
  const chk = tabRoot.querySelector(".bld-chk");
  chk.checked = false;
  chk.onchange();
  await new Promise((r) => setTimeout(r, 380));
  assert.equal(putCount, 1, "expected PUT /profile after debounce");
  assert.equal(tabRoot.innerHTMLCount, rendersBefore, "self profile_updated triggered full tab re-render");
  assert.equal(document.activeElement, tgtInput, "focus lost on self profile_updated");
})();
"""

    proc = subprocess.run(
        [node, "-e", js_test],
        env={**os.environ, "APP_JS_PATH": str(app_js_path)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert proc.returncode == 0, f"JS scroll regression failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"


def test_stratagem_combo_idx_matches_desktop(tmp_path, monkeypatch):
    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    sess = wm.login_account(server_id=53, username="strat", password="pw")
    expected = {0: 0, 1: 93, 2: 95, 3: 94}
    for idx, sid in expected.items():
        sess.profile.combat.stratagem_combo_idx = idx
        assert sess._build_combat_config().offensive_stratagem_id == sid
    wm.graceful_shutdown()


def test_transfer_loop_stops_when_garrison_lacks_troops(tmp_path, monkeypatch):
    import time

    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    sess = wm.login_account(server_id=53, username="xfer", password="pw")
    sess.update_profile({
        "logistics": {
            "transfer_orders": [{"from_city_id": 1001, "to_city_id": 1002, "army_id": 108, "amount": 500}],
            "transfer_interval": "3",
        }
    })

    calls = []

    def _fake_garrison(self, cid):
        # Lượt 1 đủ 500, lượt 2 chỉ còn 100 -> phải dừng vòng lặp
        return {108: 500} if len(calls) == 0 else {108: 100}

    monkeypatch.setattr(runtime_mod.LogisticsTask, "get_garrison_troops", _fake_garrison)
    monkeypatch.setattr(runtime_mod.LogisticsTask, "transfer_army", lambda self, order: calls.append(order.amount) or True)

    orig_wait = sess._transfer_stop.wait
    monkeypatch.setattr(sess._transfer_stop, "wait", lambda _t: orig_wait(0.01))

    sess.start_transfer_loop()
    assert sess._transfer_thread is not None
    sess._transfer_thread.join(timeout=2.0)

    assert calls == [500]
    assert sess._transfer_running is False
    assert "thiếu quân giới" in sess._transfer_status
    wm.graceful_shutdown()


def test_auto_tribute_runs_once_per_day_for_enabled_cities_only(tmp_path, monkeypatch):
    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    sess = wm.login_account(server_id=53, username="trib", password="pw")
    sess.update_profile({
        "building": {
            "cities": {
                "1001": {"name": "Lạc Dương", "enabled": True},
                "-2001": {"name": "Trại 1", "enabled": True},
            }
        },
        "logistics": {"tribute_enabled": True, "tribute_building_gid": 2},
    })
    sent = []
    monkeypatch.setattr(sess, "tribute_city", lambda cid, gid=1: sent.append((cid, gid)))

    sess._check_tribute_once()
    sess._check_tribute_once()  # cùng ngày không gọi lại lần 2
    assert sent == [(1001, 2)]
    wm.graceful_shutdown()


def test_web_armament_rename_equip_and_logistics_endpoints(tmp_path, monkeypatch):
    from linhvuong.armament import ArmamentSnapshot
    from linhvuong.generals import EquipmentInventory, EquipmentItem

    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="pw")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    snap = ArmamentSnapshot(infantry=(101, 0, 0), cavalry=(201, 0, 0), battle_array=2, names={101: "Đao", 201: "Giáp"})
    monkeypatch.setattr(runtime_mod, "fetch_armament", lambda gw, gid, bid: snap)

    inv = EquipmentInventory(
        free_items={("vo", 1): [EquipmentItem(item_id=1, equip_type=1, item_type_id=1101, level=10)]},
        equipped_by_general={1: {2: EquipmentItem(item_id=2, equip_type=2, item_type_id=2101, level=12)}},
    )
    monkeypatch.setattr(runtime_mod, "fetch_equipment_inventory", lambda gw: inv)

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
        assert client.post(
            "/api/accounts/login",
            json={"server_id": 53, "username": "armuser", "password": "pw"},
        ).status_code == 200

        meta = client.get("/api/meta").json()
        assert meta["rename_max_width"] == 17
        assert len(meta["armament_scopes"]) == 4
        assert len(meta["add_point_modes"]) == 6

        r_snaps = client.get("/api/accounts/armuser%20%40%20S53/armament/snapshots")
        assert r_snaps.status_code == 200
        assert "1" in r_snaps.json()["snapshots"]

        r_tpl = client.post("/api/accounts/armuser%20%40%20S53/armament/template", json={"general_id": 1})
        assert r_tpl.status_code == 200
        assert r_tpl.json()["info"]["battle_array"] == 2

        r_cmp = client.post(
            "/api/accounts/armuser%20%40%20S53/armament/compare",
            json={"template_id": 1, "general_ids": [1], "scopes": ["infantry"], "sync_formation": True},
        )
        assert r_cmp.status_code == 200
        assert r_cmp.json()["result"]["1"] == "match"

        r_ren = client.post(
            "/api/accounts/armuser%20%40%20S53/rename/preview",
            json={"general_ids": [1, 2], "prefix": "LV_", "numbered": True, "start_index": 1},
        )
        assert r_ren.status_code == 200
        rows = r_ren.json()["rows"]
        assert [r["new_name"] for r in rows] == ["LV_01", "LV_02"]
        assert all(r["valid"] for r in rows)

        r_eq = client.get("/api/accounts/armuser%20%40%20S53/equip/inventory")
        assert r_eq.status_code == 200
        eq_inv = r_eq.json()["inventory"]
        assert eq_inv["free_vo"] == [1, 0, 0, 0]
        assert eq_inv["free_van"] == [0, 0, 0, 0]
        assert "Lv.12" in eq_inv["equipped_by_general"]["1"]["2"]

        assert client.post("/api/accounts/armuser%20%40%20S53/armament/stop").status_code == 200
        assert client.post("/api/accounts/armuser%20%40%20S53/rename/stop").status_code == 200

        r_ap = client.post(
            "/api/accounts/armuser%20%40%20S53/add-points/run",
            json={"general_ids": [1], "mode": "pair_1_3", "points_per_add": 10, "times": 1, "add_all": False},
        )
        assert r_ap.status_code == 200
        assert client.post("/api/accounts/armuser%20%40%20S53/add-points/stop").status_code == 200

        r_ap_bad = client.post(
            "/api/accounts/armuser%20%40%20S53/add-points/run",
            json={"general_ids": [], "mode": "pair_1_3"},
        )
        assert r_ap_bad.status_code == 400

        assert any(w["id"] == 452 for w in meta["transfer_weapons"])

        monkeypatch.setattr(
            runtime_mod.LogisticsTask,
            "get_city_weapon_stocks",
            lambda self, cid: [{"id": 108, "name": "Bách thắng trường đao", "category_mask": 1, "count": 5000}],
        )
        r_cw = client.get("/api/accounts/armuser%20%40%20S53/aux/city-weapons?city_id=1")
        assert r_cw.status_code == 200
        assert r_cw.json()["items"][0]["count"] == 5000

        # Chợ: từ == đến hoặc trại (<0) bị từ chối HTTP 400
        assert client.post(
            "/api/accounts/armuser%20%40%20S53/aux/transfer",
            json={"from_city_id": 1, "to_city_id": 1, "army_id": 108, "amount": 10},
        ).status_code == 400
        assert client.post(
            "/api/accounts/armuser%20%40%20S53/aux/transfer",
            json={"from_city_id": 1, "to_city_id": -2001, "army_id": 108, "amount": 10},
        ).status_code == 400

        # Quân đội: start/stop + lưu profile transfer_mode="army"
        monkeypatch.setattr(runtime_mod.ArmyWeaponTransferTask, "run", lambda *a, **kw: "completed:2000")
        r_ax_bad = client.post(
            "/api/accounts/armuser%20%40%20S53/aux/army-transfer/start",
            json={"from_city_id": 1, "to_city_id": 2, "weapon_id": 406, "general_ids": []},
        )
        assert r_ax_bad.status_code == 400
        r_ax = client.post(
            "/api/accounts/armuser%20%40%20S53/aux/army-transfer/start",
            json={"from_city_id": 1, "to_city_id": 2, "weapon_id": 406, "general_ids": [1], "loop": False},
        )
        assert r_ax.status_code == 200
        assert client.post("/api/accounts/armuser%20%40%20S53/aux/army-transfer/stop").status_code == 200

        r_prof = client.put(
            "/api/accounts/armuser%20%40%20S53/profile",
            json={
                "logistics": {
                    "transfer_mode": "army",
                    "army_transfer_from_city_id": 1,
                    "army_transfer_to_city_id": 2,
                    "army_transfer_weapon_id": 452,
                    "army_transfer_general_ids": [1],
                    "army_transfer_loop": False,
                }
            },
        )
        assert r_prof.status_code == 200
        lg = r_prof.json()["profile"]["logistics"]
        assert lg["transfer_mode"] == "army"
        assert lg["army_transfer_weapon_id"] == 452
        assert lg["army_transfer_general_ids"] == [1]
        assert lg["army_transfer_loop"] is False

    wm.graceful_shutdown()


def test_web_equip_run_forwards_selected_general_ids(tmp_path, monkeypatch):
    import time

    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="pw")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
        assert client.post(
            "/api/accounts/login",
            json={"server_id": 58, "username": "eqweb", "password": "pw"},
        ).status_code == 200

        sess = wm.get_session("eqweb @ S58")
        sess.gateway.call = lambda *a, **kw: {"ret": 0, "list": []}
        sess.gateway.optimization = lambda *a, **kw: {"ret": 0, "list": [], "total": 0}

        r_eq = client.post(
            "/api/accounts/eqweb%20%40%20S58/equip/run",
            json={"mode": "assign", "general_ids": [1], "reassign": False},
        )
        assert r_eq.status_code == 200

        deadline = time.monotonic() + 2.0
        while sess._equip_running and time.monotonic() < deadline:
            time.sleep(0.02)

        assert "Lỗi" not in sess._equip_status, f"Equip failed: {sess._equip_status} | {sess.get_logs('equip')}"
        assert sess._equip_status.startswith("Hoàn tất:")

    wm.graceful_shutdown()


def test_web_equip_modal_selection_excludes_hidden_generals():
    import os
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")

    app_js_path = Path(__file__).resolve().parents[1] / "linhvuong" / "web" / "static" / "app.js"
    js_test = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const appCode = fs.readFileSync(process.env.APP_JS_PATH, "utf8");

const byId = new Map();
function registerById(el) {
  if (el && el.id) byId.set(el.id, el);
}

function parseAttrs(attrStr) {
  const attrs = {};
  const re = /([a-zA-Z0-9_-]+)(?:="([^"]*)")?/g;
  let m;
  while ((m = re.exec(attrStr))) {
    attrs[m[1]] = m[2] !== undefined ? m[2] : "";
  }
  return attrs;
}

function matchesSel(el, sel) {
  return sel
    .split(",")
    .map((s) => s.trim())
    .some((part) => {
      if (part.startsWith(".")) return el.classList.contains(part.slice(1).split(/[\s\[:]/)[0]);
      if (part.startsWith("#")) return el.id === part.slice(1);
      return el.tagName.toLowerCase() === part.split(/[\s\[:.]/)[0].toLowerCase();
    });
}

function makeEl(tag, id = "", className = "") {
  const el = {
    tagName: tag.toUpperCase(),
    id,
    className,
    dataset: {},
    style: {},
    children: [],
    listeners: {},
    _innerHTML: "",
    _textContent: "",
    value: "",
    checked: false,
    disabled: false,
    classList: {
      _set: new Set(className ? className.split(/\s+/).filter(Boolean) : []),
      add(...xs) {
        xs.forEach((x) => this._set.add(x));
      },
      remove(...xs) {
        xs.forEach((x) => this._set.delete(x));
      },
      toggle(x, force) {
        if (force === undefined) {
          if (this._set.has(x)) this._set.delete(x);
          else this._set.add(x);
        } else if (force) this._set.add(x);
        else this._set.delete(x);
      },
      contains(x) {
        return this._set.has(x);
      },
    },
    addEventListener(ev, fn) {
      (this.listeners[ev] ||= []).push(fn);
    },
    dispatchEvent(ev) {
      (this.listeners[ev.type] || []).forEach((fn) => fn(ev));
    },
    appendChild(ch) {
      this.children.push(ch);
      return ch;
    },
    remove() {},
    contains(other) {
      return other === this || this.children.some((c) => c.contains && c.contains(other));
    },
    querySelectorAll(sel) {
      const out = [];
      const walk = (n) => {
        for (const c of n.children || []) {
          if (matchesSel(c, sel)) out.push(c);
          walk(c);
        }
      };
      walk(this);
      return out;
    },
    querySelector(sel) {
      return this.querySelectorAll(sel)[0] || null;
    },
  };
  Object.defineProperty(el, "textContent", {
    get() {
      return this._textContent;
    },
    set(v) {
      this._textContent = String(v ?? "");
    },
  });
  Object.defineProperty(el, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(v) {
      this._innerHTML = String(v ?? "");
      this.children = [];
      const selectRe = /<select\b([^>]*)>([\s\S]*?)<\/select>/gi;
      let sm;
      while ((sm = selectRe.exec(this._innerHTML))) {
        const attrs = parseAttrs(sm[1]);
        const selEl = makeEl("select", attrs.id || "", attrs.class || "");
        const optRe = /<option\b([^>]*)>/gi;
        let om;
        let firstVal = "";
        let selectedVal = null;
        while ((om = optRe.exec(sm[2]))) {
          const oa = parseAttrs(om[1]);
          const ov = oa.value ?? "";
          if (firstVal === "") firstVal = ov;
          if ("selected" in oa) selectedVal = ov;
        }
        selEl.value = selectedVal !== null ? selectedVal : firstVal;
        this.children.push(selEl);
        registerById(selEl);
      }
      const tagRe = /<(button|input|tbody|div|span)\b([^>]*)>/gi;
      let tm;
      while ((tm = tagRe.exec(this._innerHTML))) {
        const attrs = parseAttrs(tm[2]);
        if (!attrs.id && !attrs.class) continue;
        const child = makeEl(tm[1].toLowerCase(), attrs.id || "", attrs.class || "");
        if ("checked" in attrs) child.checked = true;
        if (attrs.value !== undefined) child.value = attrs.value;
        for (const [k, val] of Object.entries(attrs)) {
          if (k.startsWith("data-")) {
            const dk = k.slice(5).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
            child.dataset[dk] = val;
          }
        }
        this.children.push(child);
        registerById(child);
      }
    },
  });
  return el;
}

const staticIds = [
  "admin-login-view","app-shell","game-login-view","dashboard-view","account-list","tab-content",
  "ws-title","ws-status-pill","ws-proxy-pill","ws-realtime-pill","btn-reload-roster",
  "btn-rotate-proxy","btn-notify-settings","btn-account-logout","profile-header-bar",
  "hdr-profile-name","hdr-profile-export","hdr-save-vault","hdr-auto-resume","hdr-autostart-count",
  "captcha-banner","captcha-reason-text","toast-stack","sidebar","admin-login-form","admin-user","admin-pass",
  "admin-login-error","btn-admin-logout","btn-mobile-menu","btn-add-account","btn-start-all","btn-stop-all",
  "btn-open-syslogs","btn-admin-settings","btn-coffee","modal-close","btn-sound-toggle","btn-resume-captcha",
  "hdr-profile-import","btn-autostart-cfg","btn-free-proxy","btn-test-proxy","game-login-form","btn-game-login",
  "btn-save-acc-only","btn-delete-acc","modal-backdrop","modal-title","modal-body","modal-footer",
  "btn-relogin","hdr-profile-save","gl-server","gl-proxy","gl-server-hint"
];
for (const id of staticIds) registerById(makeEl("div", id, ""));

const tabBtnOverview = makeEl("button", "", "tab-btn");
tabBtnOverview.dataset.tab = "overview";

const document = {
  activeElement: makeEl("body"),
  addEventListener: () => {},
  getElementById: (id) => byId.get(id) || null,
  querySelectorAll: (sel) => (sel === ".tab-btn" ? [tabBtnOverview] : []),
  createElement: (tag) => makeEl(tag),
};

const generals = [];
for (let i = 1; i <= 10; i++) {
  generals.push({
    id: i,
    name: `Vo_C1_${i}`,
    role: "vo",
    city_id: 1001,
    level: 50 - i,
    status: 0,
    status_text: "Rảnh",
    army: { total: 100 },
  });
}
for (let i = 1; i <= 5; i++) {
  generals.push({
    id: 100 + i,
    name: `Van_C1_${i}`,
    role: "van",
    city_id: 1001,
    level: 40 - i,
    status: 0,
    status_text: "Rảnh",
    is_mayor: i === 1,
  });
}
for (let i = 11; i <= 15; i++) {
  generals.push({
    id: i,
    name: `Vo_C2_${i}`,
    role: "vo",
    city_id: 1002,
    level: 45 - i,
    status: 0,
    status_text: "Rảnh",
    army: { total: 100 },
  });
}
for (let i = 6; i <= 10; i++) {
  generals.push({
    id: 100 + i,
    name: `Van_C2_${i}`,
    role: "van",
    city_id: 1002,
    level: 40 - i,
    status: 0,
    status_text: "Rảnh",
    is_mayor: i === 6,
  });
}

const sampleSnap = {
  summary: { account_key: "tester @ S58", status: "connected", status_text: "OK", tasks: {} },
  profile: {
    building: { cities: {} },
    research: { techs: [] },
    resource: { resource_cities: [] },
    logistics: {},
    ditrai: {},
    thao_phat: { generals: [] },
    binh_man: { bases: {} },
    goi_dan: { generals: [] },
    crafting: { cities: {} },
    combat: {},
    nien_thu: { generals: [] },
    notifications: {},
  },
  roster: {
    bases: [
      { id: 1001, name: "Thành 1", display_name: "Thành 1", type: "Thành", pos_x: 1, pos_y: 2 },
      { id: 1002, name: "Thành 2", display_name: "Thành 2", type: "Thành", pos_x: 3, pos_y: 4 },
    ],
    cities: [
      { id: 1001, name: "Thành 1", display_name: "Thành 1" },
      { id: 1002, name: "Thành 2", display_name: "Thành 2" },
    ],
    camps: [],
    generals,
  },
  tech_levels: {},
  logs: { equip: [] },
  aux: {},
};

let confirmResult = true;
const confirmCalls = [];
const equipRunBodies = [];

const windowObj = {
  location: { protocol: "http:", host: "127.0.0.1:8000" },
  listeners: {},
  addEventListener(ev, fn) {
    (this.listeners[ev] ||= []).push(fn);
  },
  setTimeout(fn, delay, ...args) {
    const t = setTimeout(fn, delay, ...args);
    if (t && typeof t.unref === "function") t.unref();
    return t;
  },
  clearTimeout,
  setInterval: () => 1,
  WebSocket: class {
    close() {}
  },
  Notification: { permission: "denied" },
  confirm: (msg) => {
    confirmCalls.push(String(msg));
    return confirmResult;
  },
  fetch: async (url, opts) => {
    if (url === "/api/auth/status") {
      return {
        status: 200,
        ok: true,
        text: async () => JSON.stringify({ auth_enabled: false, authenticated: true, username: "admin", vault_unlocked: true }),
      };
    }
    if (url === "/api/meta") {
      return {
        status: 200,
        ok: true,
        text: async () =>
          JSON.stringify({
            missions: [],
            techs: [],
            tech_names: [],
            man_targets: [],
            attack_action_options: [],
            formations: [],
            stratagems: [],
            chests: [],
            weapons: [],
            resumable_tasks: [],
          }),
      };
    }
    if (url === "/api/accounts") {
      return {
        status: 200,
        ok: true,
        text: async () => JSON.stringify({ accounts: [{ account_key: "tester @ S58", status: "connected", config: {} }] }),
      };
    }
    if (url.endsWith("/snapshot")) {
      return { status: 200, ok: true, text: async () => JSON.stringify(sampleSnap) };
    }
    if (url.endsWith("/equip/inventory")) {
      return {
        status: 200,
        ok: true,
        text: async () => JSON.stringify({ ok: true, inventory: { free_vo: [10, 10, 10, 10], free_van: [10, 10, 10, 10], equipped_by_general: {} } }),
      };
    }
    if (url.endsWith("/equip/run")) {
      equipRunBodies.push(JSON.parse(opts.body));
      return { status: 200, ok: true, text: async () => JSON.stringify({ ok: true }) };
    }
    return { status: 200, ok: true, text: async () => "{}" };
  },
};
windowObj.window = windowObj;
windowObj.document = document;
windowObj.navigator = {};
Object.assign(windowObj, { Object, Array, Number, String, Boolean, Set, Map, Math, Date, JSON, Error, RegExp, Promise, encodeURIComponent, structuredClone });

const sortedIds = (xs) => [...xs].sort((a, b) => a - b);

(async () => {
  const ctx = vm.createContext(windowObj);
  vm.runInContext(appCode, ctx);
  for (const fn of windowObj.listeners["DOMContentLoaded"] || []) await fn();
  await new Promise((r) => setTimeout(r, 30));

  tabBtnOverview.onclick();

  // 1. Starts empty (Desktop parity) and blocks empty submit
  await byId.get("btn-open-equip").onclick();
  assert.equal(byId.get("eq-city").value, "1001");
  assert.match(byId.get("eq-summary").textContent, /Đang chọn: 0 \(Tổng chọn: 0\)/);
  assert.equal(byId.get("eq-all").checked, false);
  for (const chk of byId.get("eq-tbody").querySelectorAll(".eq-chk")) {
    assert.equal(chk.checked, false, "checkboxes must start unchecked");
  }
  const toastsBefore = byId.get("toast-stack").children.length;
  byId.get("btn-eq-assign").onclick();
  byId.get("btn-eq-remove").onclick();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(equipRunBodies.length, 0, "empty selection must not POST /equip/run");
  assert.equal(byId.get("toast-stack").children.length, toastsBefore + 2, "empty submit should show warning toasts");
  assert.ok(byId.get("toast-stack").children.slice(-2).every((t) => t.className.includes("warn")));

  // 2. Select 10 Võ in filtered city (btn-eq-vo) -> sends ONLY [1..10], zero confirm()
  byId.get("btn-eq-vo").onclick();
  byId.get("btn-eq-assign").onclick();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(confirmCalls.length, 0, "no confirm expected when all selected generals are visible");
  assert.equal(equipRunBodies.length, 1);
  assert.equal(equipRunBodies[0].mode, "assign");
  assert.deepEqual(sortedIds(equipRunBodies[0].general_ids), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

  // 3. Filter city=all + role=vo, check 10 Võ -> sends ONLY [1..10]
  await byId.get("btn-open-equip").onclick();
  byId.get("eq-city").value = "all";
  byId.get("eq-city").onchange();
  byId.get("eq-role").value = "vo";
  byId.get("eq-role").onchange();
  for (const chk of byId.get("eq-tbody").querySelectorAll(".eq-chk")) {
    if (Number(chk.dataset.gid) <= 10) {
      chk.checked = true;
      chk.onchange();
    }
  }
  byId.get("btn-eq-assign").onclick();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(confirmCalls.length, 0);
  assert.equal(equipRunBodies.length, 2);
  assert.deepEqual(sortedIds(equipRunBodies[1].general_ids), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

  // 4. btn-eq-none clears hidden selections too
  await byId.get("btn-open-equip").onclick();
  byId.get("eq-city").value = "all";
  byId.get("eq-city").onchange();
  byId.get("eq-role").value = "all";
  byId.get("eq-role").onchange();
  byId.get("btn-eq-all").onclick();
  byId.get("eq-role").value = "vo";
  byId.get("eq-role").onchange();
  byId.get("btn-eq-none").onclick();
  for (const chk of byId.get("eq-tbody").querySelectorAll(".eq-chk")) {
    if (Number(chk.dataset.gid) <= 10) {
      chk.checked = true;
      chk.onchange();
    }
  }
  byId.get("btn-eq-assign").onclick();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(confirmCalls.length, 0);
  assert.equal(equipRunBodies.length, 3);
  assert.deepEqual(sortedIds(equipRunBodies[2].general_ids), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);

  // 5. Hidden-selection warning & cancel guard
  byId.get("btn-eq-none").onclick();
  byId.get("eq-city").value = "all";
  byId.get("eq-city").onchange();
  byId.get("eq-role").value = "all";
  byId.get("eq-role").onchange();
  byId.get("btn-eq-all").onclick();
  byId.get("eq-role").value = "vo";
  byId.get("eq-role").onchange();
  assert.ok(byId.get("eq-summary").textContent.includes("gồm 10 tướng đang ẩn bởi bộ lọc"));
  confirmResult = false;
  byId.get("btn-eq-assign").onclick();
  byId.get("btn-eq-remove").onclick();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(confirmCalls.length, 2, "both assign and remove must ask confirmation when hidden generals are selected");
  assert.equal(equipRunBodies.length, 3, "declining confirm must abort /equip/run");

  // 6. Intentional cross-city selection still works when confirmed
  byId.get("btn-eq-none").onclick();
  byId.get("eq-city").value = "1001";
  byId.get("eq-city").onchange();
  for (const chk of byId.get("eq-tbody").querySelectorAll(".eq-chk")) {
    if (Number(chk.dataset.gid) <= 5) {
      chk.checked = true;
      chk.onchange();
    }
  }
  byId.get("eq-city").value = "1002";
  byId.get("eq-city").onchange();
  for (const chk of byId.get("eq-tbody").querySelectorAll(".eq-chk")) {
    const gid = Number(chk.dataset.gid);
    if (gid >= 11 && gid <= 15) {
      chk.checked = true;
      chk.onchange();
    }
  }
  confirmResult = true;
  byId.get("btn-eq-assign").onclick();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(confirmCalls.length, 3, "cross-city hidden selection should trigger confirm");
  assert.equal(equipRunBodies.length, 4);
  assert.deepEqual(sortedIds(equipRunBodies[3].general_ids), [1, 2, 3, 4, 5, 11, 12, 13, 14, 15]);

  // 7. Unequip (btn-eq-remove) also respects selection
  byId.get("btn-eq-none").onclick();
  byId.get("eq-city").value = "1001";
  byId.get("eq-city").onchange();
  byId.get("eq-role").value = "all";
  byId.get("eq-role").onchange();
  byId.get("btn-eq-vo").onclick();
  byId.get("btn-eq-remove").onclick();
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(confirmCalls.length, 3, "no extra confirm expected for visible unequip");
  assert.equal(equipRunBodies.length, 5);
  assert.deepEqual(
    { ...equipRunBodies[4], general_ids: sortedIds(equipRunBodies[4].general_ids) },
    { mode: "unequip", general_ids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], reassign: false }
  );
})();
"""

    proc = subprocess.run(
        [node, "-e", js_test],
        env={**os.environ, "APP_JS_PATH": str(app_js_path)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert proc.returncode == 0, f"Web equip selection test failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"


def test_aux_loop_daily_reward_isolation_retry_timezone_and_captcha(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from unittest.mock import patch
    from linhvuong.tasks.base import CaptchaRequired

    reset_notified_bosses()
    monkeypatch.setattr(runtime_mod, "login", lambda *a, **kw: None)
    monkeypatch.setattr(runtime_mod, "fetch_roster", lambda gw: _fake_roster())

    # (c) Ngáy game phải theo UTC+7 ngay cả khi OS chạy UTC ở 00:00–06:59 VN
    fixed_utc = datetime(2026, 11, 19, 21, 25, 0, tzinfo=timezone.utc)
    assert hasattr(runtime_mod, "_game_today_str"), "_game_today_str chưa được định nghĩa trong runtime"
    assert runtime_mod._game_today_str(fixed_utc) == "2026-11-20"

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    responses = iter([
        {"ret": -1},          # Lần 1: lỗi tạm thời -> KHÔNG khóa ngày hôm nay
        CaptchaRequired,      # Lần 2: gặp Captcha 110 -> pause & không khóa ngày hôm nay
        {"ret": 0},           # Lần 3 (sau resume): thành công -> khóa ngày hôm nay
    ])
    opt63_calls = []

    def fake_call(gw, page, action_id, payload=None, **kw):
        if page == "OPT.ashx" and action_id == 63:
            opt63_calls.append((page, action_id, dict(payload or {})))
            nxt = next(responses)
            if nxt is CaptchaRequired:
                raise CaptchaRequired("Yêu cầu Captcha")
            return nxt
        return {"ret": 0}

    # Stub trên lớp trước login_account để _aux_loop thật không gọi mạng ra ngoài
    monkeypatch.setattr(runtime_mod.GatewayClient, "call", fake_call)
    monkeypatch.setattr(runtime_mod.AccountSession, "_check_boost_once", MagicMock(side_effect=RuntimeError("boom boost")))
    monkeypatch.setattr(runtime_mod.AccountSession, "_check_explore_once", lambda self: None)
    monkeypatch.setattr(runtime_mod.AccountSession, "_check_tribute_once", lambda self: None)
    monkeypatch.setattr(runtime_mod.AccountSession, "_check_general_visit_once", lambda self: None)

    sess = wm.login_account(
        server_id=58,
        username="dailyuser",
        password="pw",
        fetch_initial_roster=False,
    )
    try:
        # login_account(..., fetch_initial_roster=False) vẫn phải khởi động aux loop
        assert sess._aux_thread is not None and sess._aux_thread.is_alive()

        with patch.object(runtime_mod, "_game_today_str", return_value="2026-11-20"):
            # Bật auto_daily_reward qua import_profile -> đánh thức _aux_loop thật ngay lập tức;
            # Tick 1: _check_boost_once lỗi RuntimeError nhưng _check_daily_reward_once vẫn chạy, gặp ret=-1 -> không khóa ngày
            prof = sess.profile.to_dict()
            prof["logistics"]["auto_daily_reward"] = True
            sess.import_profile(prof)

            import time as _t
            deadline = _t.monotonic() + 2.0
            while len(opt63_calls) < 1 and _t.monotonic() < deadline:
                _t.sleep(0.02)

            # Dừng luồng nền để kiểm tra tuần tự các tick tiếp theo một cách xác định
            sess._aux_stop.set()
            sess._aux_wakeup.set()
            sess._aux_thread.join(timeout=2.0)

            assert len(opt63_calls) == 1
            assert sess._last_daily_claim_date is None

            # Tick 2: gặp CaptchaRequired -> gọi _handle_captcha, không khóa ngày
            sess._check_daily_reward_once()
            assert len(opt63_calls) == 2
            assert sess.captcha_required is True
            assert sess._last_daily_claim_date is None

            # Khi đang dính captcha_required, _check_daily_reward_once không spam server
            sess._check_daily_reward_once()
            assert len(opt63_calls) == 2

            # Giải captcha -> resume_after_captcha đánh thức aux loop và Tick 3 nhận thưởng thành công
            sess.resume_after_captcha()
            assert sess.captcha_required is False
            assert sess._aux_wakeup.is_set()
            sess._check_daily_reward_once()
            assert len(opt63_calls) == 3
            assert sess._last_daily_claim_date == "2026-11-20"
    finally:
        wm.graceful_shutdown()


def test_web_enhance_endpoints_high_level_destroy_guard_and_captcha(tmp_path, monkeypatch):
    import time

    _mock_offline(monkeypatch)
    assert "enhance" not in runtime_mod.RESUMABLE_TASKS
    assert all(tid != "enhance" for tid, _ in runtime_mod.AUTO_START_TASK_LABELS)

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="pw")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    monkeypatch.setattr("linhvuong.enhance.DEFAULT_DELAY_RANGE", (0.0, 0.0))

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
        assert client.post(
            "/api/accounts/login",
            json={"server_id": 58, "username": "enhuser", "password": "pw"},
        ).status_code == 200

        sess = wm.get_session("enhuser @ S58")
        state = {"lvl": 0, "captcha_on_enhance": False}

        def fake_opt(action, payload=None, **_kw):
            if action == "equipment":
                return {
                    "ret": 0,
                    "list": [[5001, 1, 1135, 0, 0, 0, 0, state["lvl"], 0, ""]],
                    "page": 0,
                    "pageSize": 50,
                    "total": 1,
                    "revision": [1, 1],
                }
            return {"ret": 0}

        def fake_call(ep, oid, payload=None, **_kw):
            if ep == "Common.ashx" and oid == 2:
                return {"ret": 0, "Table": [{"gem_id": 341, "counts": 15}, {"gem_id": 342, "counts": 8}, {"gem_id": 354, "counts": 40}]}
            if ep == "Common.ashx" and oid == 117:
                return {"ret": 0, "list": [[5002, 2, 1104, 0, 0, 0, 0, 0]]}
            if ep == "OPT.ashx" and oid == 154:
                if state["captcha_on_enhance"]:
                    return {"ret": 110}
                state["lvl"] += 1
                return {"ret": 0}
            if ep == "OPT.ashx" and oid == 17:
                return {"ret": 0}
            return {"ret": 0}

        sess.gateway.optimization = fake_opt
        sess.gateway.call = fake_call

        r_res = client.get("/api/accounts/enhuser%20%40%20S58/enhance/resources")
        assert r_res.status_code == 200
        assert r_res.json()["resources"] == {"iron": 15, "hammer": 8, "crystal": 40}

        r_items = client.get("/api/accounts/enhuser%20%40%20S58/enhance/items?equip_type=1")
        assert r_items.status_code == 200
        assert r_items.json()["vo"][0]["item_id"] == 5001
        assert r_items.json()["vo"][0]["level"] == 1

        r_mats = client.get("/api/accounts/enhuser%20%40%20S58/enhance/materials?item_id=5001")
        assert r_mats.status_code == 200
        assert r_mats.json()["groups"][0]["key"] == "1104:1"

        r_del_block = client.post(
            "/api/accounts/enhuser%20%40%20S58/enhance/destroy",
            json={
                "equip_type": 1,
                "role": "vo",
                "item_id": 5001,
                "item_type_id": 1135,
                "level": 7,
                "quantity": 1,
                "confirm_high_level": False,
            },
        )
        assert r_del_block.status_code == 400

        r_del_ok = client.post(
            "/api/accounts/enhuser%20%40%20S58/enhance/destroy",
            json={
                "equip_type": 1,
                "role": "vo",
                "item_id": 5001,
                "item_type_id": 1135,
                "level": 7,
                "quantity": 1,
                "confirm_high_level": True,
            },
        )
        assert r_del_ok.status_code == 200
        deadline = time.monotonic() + 2.0
        while sess._enhance_running and time.monotonic() < deadline:
            time.sleep(0.02)

        r_start = client.post(
            "/api/accounts/enhuser%20%40%20S58/enhance/start",
            json={
                "equip_type": 1,
                "role": "vo",
                "item_id": 5001,
                "item_type_id": 1135,
                "start_level": 1,
                "target_level": 3,
                "protect_from_level": None,
                "material_from_level": 1,
                "material_keys": ["1104:1", "", ""],
                "loop_count": 1,
            },
        )
        assert r_start.status_code == 200
        deadline = time.monotonic() + 2.0
        while sess._enhance_running and time.monotonic() < deadline:
            time.sleep(0.02)
        assert state["lvl"] == 2
        assert sess._enhance_progress["completed_items"] == 1

        state["captcha_on_enhance"] = True
        r_cap = client.post(
            "/api/accounts/enhuser%20%40%20S58/enhance/start",
            json={
                "equip_type": 1,
                "role": "vo",
                "item_id": 5001,
                "item_type_id": 1135,
                "start_level": 1,
                "target_level": 3,
                "loop_count": 1,
            },
        )
        assert r_cap.status_code == 200
        deadline = time.monotonic() + 2.0
        while sess._enhance_running and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sess.captcha_required is True
        assert client.post("/api/accounts/enhuser%20%40%20S58/enhance/stop").status_code == 200

    wm.graceful_shutdown()


def test_runtime_and_web_auto_swap_tactician_forwarding_and_ui(tmp_path, monkeypatch):
    import time

    _mock_offline(monkeypatch)
    reset_notified_bosses()

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="webpassword")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "webpassword"}).status_code == 200
        assert client.post(
            "/api/accounts/login",
            json={"server_id": 58, "username": "swapuser", "password": "secret"},
        ).status_code == 200

        js = client.get("/static/app.js").text
        for dom_id in ("bm-swap-tac", "bm-min-tac-stam", "gd-swap-tac", "gd-min-tac-stam"):
            assert dom_id in js

        assert client.put(
            "/api/accounts/swapuser%20%40%20S58/profile",
            json={
                "binh_man": {
                    "bases": {
                        "1001": {
                            "enabled": True,
                            "mode": 2,
                            "generals": [1],
                            "auto_recruit": False,
                            "auto_morale": False,
                            "auto_swap_tactician": True,
                            "min_tactician_stamina": "45",
                        }
                    }
                },
                "goi_dan": {
                    "city_id": 1001,
                    "generals": [1],
                    "auto_recruit": False,
                    "auto_morale": False,
                    "auto_swap_tactician": True,
                    "min_tactician_stamina": "55",
                },
            },
        ).status_code == 200

        sess = wm.get_session("swapuser @ S58")
        assert sess is not None
        started = {}
        monkeypatch.setattr(sess.engine, "start", lambda name, runnable, **_kw: started.__setitem__(name, runnable))

        assert client.post("/api/accounts/swapuser%20%40%20S58/tasks/binhman/start").status_code == 200
        assert started["binhman"].tasks[0].auto_swap_tactician is True
        assert started["binhman"].tasks[0].min_tactician_stamina == 45.0

        assert client.post("/api/accounts/swapuser%20%40%20S58/tasks/goidan/start").status_code == 200
        assert started["goidan"].auto_swap_tactician is True
        assert started["goidan"].min_tactician_stamina == 55.0

        # Kiểm tra endpoints provision ("Biên chế") chuyển tiếp include_civil=True & ngưỡng thể lực
        swap_calls = []
        fetch_calls = []

        def fake_fetch(_gw, **kwargs):
            fetch_calls.append(kwargs)
            return _fake_roster()

        monkeypatch.setattr(runtime_mod, "fetch_roster", fake_fetch)
        monkeypatch.setattr(
            runtime_mod,
            "auto_swap_low_stamina_tacticians",
            lambda _gw, **kwargs: swap_calls.append(kwargs),
        )
        monkeypatch.setattr(runtime_mod.ArmyProvisioner, "heal_general", lambda self, *_a, **_kw: (True, 0, ""))

        assert client.post("/api/accounts/swapuser%20%40%20S58/tasks/binhman/provision", json={"base_id": 1001}).status_code == 200
        assert client.post("/api/accounts/swapuser%20%40%20S58/tasks/goidan/provision").status_code == 200
        deadline = time.monotonic() + 2.0
        while len(swap_calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)

        assert len(swap_calls) == 2
        assert any(c["min_stamina_pct"] == 45.0 and c["base_id"] == 1001 for c in swap_calls)
        assert any(c["min_stamina_pct"] == 55.0 and c["base_id"] == 1001 for c in swap_calls)
        assert all(fc.get("include_civil") is True for fc in fetch_calls)

    wm.graceful_shutdown()


def test_runtime_and_web_general_training_endpoints_aux_and_captcha(tmp_path, monkeypatch):
    from pathlib import Path
    import time

    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="webpassword")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "webpassword"}).status_code == 200
        assert client.post(
            "/api/accounts/login",
            json={"server_id": 58, "username": "trnuser", "password": "secret"},
        ).status_code == 200

        sess = wm.get_session("trnuser @ S58")
        calls = []
        state = {
            "2": {"slots": 2, "list": []},
            "1": {"slots": 1, "list": []},
            "captcha": False,
        }

        def fake_call(ep, oid, payload=None, **_kw):
            p = dict(payload or {})
            calls.append((ep, oid, p))
            if state["captcha"] and ep in ("Common.ashx", "OPT.ashx") and oid in (141, 178):
                return {"ret": 110}
            if ep == "Common.ashx" and oid == 141:
                assert int(p["tid"]) > 0
                return {"ret": 0, **state[str(p["lType"])], "hero": []}
            if ep == "OPT.ashx" and oid == 178:
                assert int(p["tid"]) > 0
                t = str(p["lType"])
                pos = int(p["lPos"])
                hid = int(p["lHeroID"])
                state[t]["list"].append([pos, 86400, hid, 4001, f"H{hid}"])
                return {"ret": 0, "exp": 1110}
            return {"ret": 0}

        sess.gateway.call = fake_call

        # 1. GET /training/status
        r_st = client.get("/api/accounts/trnuser%20%40%20S58/training/status")
        assert r_st.status_code == 200
        trn_data = r_st.json()["training"]
        assert trn_data["vo"]["unlocked_slots"] == 2
        assert trn_data["van"]["unlocked_slots"] == 1

        # 2. POST /training/run khi chưa chọn tướng -> 400
        r_empty = client.post("/api/accounts/trnuser%20%40%20S58/training/run", json={})
        assert r_empty.status_code == 400

        # 3. Lưu profile training qua PUT /profile
        r_put = client.put(
            "/api/accounts/trnuser%20%40%20S58/profile",
            json={"training": {"enabled": True, "vo_general_ids": [1], "van_general_ids": [2]}},
        )
        assert r_put.status_code == 200
        assert r_put.json()["profile"]["training"]["enabled"] is True
        assert sess._training_next_check_at == 0.0

        # 4. Kiểm tra _check_training_once tự động đào tạo và đặt cooldown 24h
        sess._check_training_once()
        assert len(state["2"]["list"]) == 1 and state["2"]["list"][0][2] == 1
        assert len(state["1"]["list"]) == 1 and state["1"]["list"][0][2] == 2
        assert sess._training_next_check_at > time.monotonic()

        # Gọi lại ngay khi đang trong cooldown -> không gọi thêm OPT.ashx?id=178 hoặc Common.ashx?id=141
        call_count_before = len(calls)
        sess._check_training_once()
        assert len(calls) == call_count_before

        # 5. Test POST /training/run thủ công khi các ô khả dụng hoạt động bình thường
        r_run = client.post("/api/accounts/trnuser%20%40%20S58/training/run", json={})
        assert r_run.status_code == 200
        deadline = time.monotonic() + 2.0
        while sess._training_running and time.monotonic() < deadline:
            time.sleep(0.02)

        # 6. Test Captcha 110 khi đào tạo thủ công
        state["captcha"] = True
        state["2"]["list"] = []
        r_cap = client.post("/api/accounts/trnuser%20%40%20S58/training/run", json={"train_type": 2})
        assert r_cap.status_code == 200
        deadline = time.monotonic() + 2.0
        while sess._training_running and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sess.captcha_required is True

    wm.graceful_shutdown()

    # Kiểm tra các phần tử UI đào tạo tướng trên Web Dashboard (app.js)
    app_js = (Path(__file__).resolve().parent.parent / "linhvuong" / "web" / "static" / "app.js").read_text(encoding="utf-8")
    for token in ("btn-open-training", "btn-open-training-aux", "aux-training", "/training/status", "/training/run", "openTrainingModal"):
        assert token in app_js


def test_resource_monitor_s58_market_buy_sell_and_web_profile_roundtrip(tmp_path, monkeypatch):
    import requests
    import threading
    from pathlib import Path
    from linhvuong.runtime import AccountSession

    _mock_offline(monkeypatch)

    # 1. AccountSession.start_resource_monitor thực thi bán dư & ưu tiên mua Chợ qua S58 REST + Market passthrough
    sess = AccountSession("mktmon @ S58", requests.Session(), 58, "mktmon", data_dir=tmp_path)
    sess.roster = _fake_roster()
    sess.profile.resource.resource_cities = [1001]
    sess.profile.resource.gold_threshold = "1000"
    sess.profile.resource.wood_pct = "70"
    sess.profile.resource.iron_pct = "70"
    sess.profile.resource.stone_pct = "70"
    sess.profile.resource.food_pct = "70"
    sess.profile.resource.prefer_market_buy = True
    sess.profile.resource.auto_sell_resource = True
    sess.profile.resource.sell_threshold_pct = "90"

    calls = []
    done_ev = threading.Event()

    sess.gateway.resource_info = lambda cid: {  # type: ignore[method-assign]
        "ret": 0,
        "m_lwood_balance": 5_000_000,
        "m_liron_balance": 8_000_000,
        "m_lstone_balance": 8_000_000,
        "m_lfood_balance": 9_500_000,
        "m_lmax_storage": 10_000_000,
    }
    sess.gateway.city_info = lambda cid: {"ret": 0, "m_lmoney_balance": 50_000_000}  # type: ignore[method-assign]
    sess.gateway.building_list = lambda cid: {"ret": 0, "items": [{"m_lpos": 24, "m_lgid": 11, "m_llevel": 20}]}  # type: ignore[method-assign]

    def _call(ep, api_id, payload=None):
        p = dict(payload or {})
        calls.append((ep, api_id, p))
        if ep == "Common.ashx" and api_id == 38:
            if p.get("type") == "2":
                return {"infos": [{"seqno": "88", "seller": "9", "count": "3000", "price": "480"}]}
            return {"infos": [{"seqno": "77", "seller": "8", "count": "50", "price": "238"}]}
        if ep == "OPT.ashx" and api_id == 29:
            return 239
        if ep == "OPT.ashx" and api_id == 9:
            done_ev.set()
            return {"ret": 0}
        return {"ret": 0}

    sess.gateway.call = _call  # type: ignore[method-assign]
    sess.start_resource_monitor()
    assert done_ev.wait(timeout=2.0)
    sess.stop_resource_monitor()
    if sess._res_monitor_thread:
        sess._res_monitor_thread.join(timeout=1.5)

    assert any(ep == "OPT.ashx" and aid == 49 and p.get("sellcount1") == "1500" for ep, aid, p in calls)
    assert any(ep == "OPT.ashx" and aid == 9 and p.get("count") == "2000" for ep, aid, p in calls)
    assert not any(ep == "Common.ashx" and aid == 48 for ep, aid, _ in calls)
    sess.destroy()

    # 2. Web API PUT /profile lưu & trả về đầy đủ 3 trường chợ mới, kiểm tra app.js chứa ID & nhãn mới
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="pw")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)
    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
        assert client.post("/api/accounts/login", json={"server_id": 58, "username": "webmkt", "password": "pw"}).status_code == 200
        r_put = client.put(
            "/api/accounts/webmkt%20%40%20S58/profile",
            json={
                "resource": {
                    "prefer_market_buy": True,
                    "auto_sell_resource": True,
                    "sell_threshold_pct": "88",
                }
            },
        )
        assert r_put.status_code == 200
        rsrc = r_put.json()["profile"]["resource"]
        assert rsrc["prefer_market_buy"] is True
        assert rsrc["auto_sell_resource"] is True
        assert rsrc["sell_threshold_pct"] == "88"
    wm.graceful_shutdown()

    app_js = (Path(__file__).resolve().parent.parent / "linhvuong" / "web" / "static" / "app.js").read_text(encoding="utf-8")
    for token in ("rsrc-prefer-market", "rsrc-auto-sell", "rsrc-sell-pct", "btn-tgl-resmon", "▶️ Tài Nguyên", "📦 Tài Nguyên"):
        assert token in app_js


def test_runtime_and_web_goidan_helper_caller_vault_reuse_and_validation(tmp_path, monkeypatch):
    from pathlib import Path
    import linhvuong.helper_caller as hc_mod

    _mock_offline(monkeypatch)
    monkeypatch.setattr(hc_mod, "login", lambda *a, **kw: None)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False, vault_key="test-master-key")
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="pw")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
        assert client.post("/api/accounts/login", json={"server_id": 58, "username": "mainuser", "password": "pw"}).status_code == 200
        sess = wm.get_session("mainuser @ S58")
        sess.roster = _fake_roster()

        # 1. Lưu cấu hình Tài Khoản Gọi Hộ với mục tiêu 301 -> /tasks/goidan/start trả 400
        assert client.put(
            "/api/accounts/mainuser%20%40%20S58/profile",
            json={
                "goi_dan": {
                    "city_id": 1001,
                    "generals": [1],
                    "target_types": [301],
                    "caller_enabled": True,
                    "caller_username": "altuser",
                }
            },
        ).status_code == 200
        r_301 = client.post("/api/accounts/mainuser%20%40%20S58/tasks/goidan/start")
        assert r_301.status_code == 400
        assert "Vong Linh" in r_301.json()["detail"]

        # 2. Chuyển sang Man Thường [1, 2] nhưng chưa có mật khẩu/phiên -> start trả 400
        assert client.put(
            "/api/accounts/mainuser%20%40%20S58/profile",
            json={"goi_dan": {"target_types": [1, 2], "target_type": 1}},
        ).status_code == 200
        r_nopwd = client.post("/api/accounts/mainuser%20%40%20S58/tasks/goidan/start")
        assert r_nopwd.status_code == 400

        # 3. Lưu mật khẩu vào RAM + Két (auto_resume=False), đảm bảo profile JSON không chứa password
        r_cred = client.post(
            "/api/accounts/mainuser%20%40%20S58/tasks/goidan/caller/credentials",
            json={"username": "altuser", "password": "alt-secret-pw", "save_to_vault": True},
        )
        assert r_cred.status_code == 200
        caller_info = r_cred.json()["caller"]
        assert caller_info["has_ram_password"] is True
        assert caller_info["has_vault_password"] is True
        assert caller_info["ready"] is True
        vault_entry = wm.vault.get_entry("altuser @ S58")
        assert vault_entry is not None
        assert vault_entry["password"] == "alt-secret-pw"
        assert vault_entry["auto_resume"] is False
        assert "alt-secret-pw" not in sess.profile_path.read_text(encoding="utf-8")

        # 4. Kiểm tra /caller/test mở phiên độc lập thành công
        r_test = client.post(
            "/api/accounts/mainuser%20%40%20S58/tasks/goidan/caller/test",
            json={"username": "altuser"},
        )
        assert r_test.status_code == 200
        assert r_test.json()["reused_session"] is False

        # 5. Start thành công với Man 1, 2 & HelperCallerSession được gắn đúng
        started = {}
        monkeypatch.setattr(sess.engine, "start", lambda name, runnable, **_kw: started.__setitem__(name, runnable))
        r_ok = client.post("/api/accounts/mainuser%20%40%20S58/tasks/goidan/start")
        assert r_ok.status_code == 200
        assert started["goidan"].has_helper_caller() is True
        assert started["goidan"].caller_username == "altuser"

        # 6. Nếu altuser đăng nhập sẵn trong WorkspaceManager -> tái sử dụng phiên
        assert client.post("/api/accounts/login", json={"server_id": 58, "username": "altuser", "password": "pw"}).status_code == 200
        r_test_reuse = client.post(
            "/api/accounts/mainuser%20%40%20S58/tasks/goidan/caller/test",
            json={"username": "altuser"},
        )
        assert r_test_reuse.status_code == 200
        assert r_test_reuse.json()["reused_session"] is True
        assert started["goidan"].caller_provider.acquire_gateway() is wm.get_session("altuser @ S58").gateway

    wm.graceful_shutdown()

    app_js = (Path(__file__).resolve().parent.parent / "linhvuong" / "web" / "static" / "app.js").read_text(encoding="utf-8")
    for token in ("gd-caller-en", "gd-caller-user", "gd-caller-pass", "gd-caller-vault", "btn-gd-caller-test", "gd-caller-status"):
        assert token in app_js


def test_runtime_and_web_even_troops_forwarding_and_provision(tmp_path, monkeypatch):
    from pathlib import Path
    import time
    import linhvuong.runtime as rt_mod
    from linhvuong.profile import BaseBinhManConfig

    _mock_offline(monkeypatch)
    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    auth = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", env_username="admin", env_password="pw")
    app = create_app(workspace=wm, auth=auth, host="127.0.0.1", auto_restore=False)

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "pw"}).status_code == 200
        assert client.post("/api/accounts/login", json={"server_id": 58, "username": "evenuser", "password": "pw"}).status_code == 200
        sess = wm.get_session("evenuser @ S58")
        sess.roster = _fake_roster()

        # 1. Task creation forwards even_troops
        sess.profile.goi_dan.city_id = 1001
        sess.profile.goi_dan.generals = [1]
        sess.profile.goi_dan.even_troops = True
        assert sess._create_goidan_task().even_troops is True

        sess.profile.binh_man.bases["1001"] = BaseBinhManConfig(
            name="TT", enabled=True, mode=2, generals=[1], even_troops=True
        )
        bm_tasks = sess._create_binhman_tasks()
        assert len(bm_tasks) == 1
        assert bm_tasks[0].even_troops is True

        # 2. Manual adjust_*_troops gọi balance_troops khi even_troops=True
        balanced_bases = []
        monkeypatch.setattr(rt_mod, "fetch_roster", lambda *_a, **_kw: sess.roster)
        monkeypatch.setattr(sess.gateway, "call", lambda *_a, **_kw: {"ret": 0})
        monkeypatch.setattr(sess.profile.goi_dan, "auto_morale", False)
        sess.profile.binh_man.bases["1001"].auto_morale = False
        orig_balance = rt_mod.ArmyProvisioner.balance_troops

        def _spy_balance(self, base_id, general_ids, current_armies, base_gens=None, on_log=None):
            balanced_bases.append(base_id)
            return orig_balance(self, base_id, general_ids, current_armies, base_gens=base_gens, on_log=on_log)

        monkeypatch.setattr(rt_mod.ArmyProvisioner, "balance_troops", _spy_balance)
        sess.adjust_goidan_troops()
        sess.adjust_binhman_troops(base_id=1001)
        deadline = time.monotonic() + 2.0
        while len(balanced_bases) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert balanced_bases.count(1001) == 2

        # 3. Web PUT /profile persists even_troops for binh_man & goi_dan
        r_put = client.put(
            "/api/accounts/evenuser%20%40%20S58/profile",
            json={
                "goi_dan": {"even_troops": True},
                "binh_man": {"even_troops": True, "bases": {"1001": {"even_troops": True, "enabled": True, "mode": 2, "generals": [1]}}},
            },
        )
        assert r_put.status_code == 200
        p = r_put.json()["profile"]
        assert p["goi_dan"]["even_troops"] is True
        assert p["binh_man"]["bases"]["1001"]["even_troops"] is True

    wm.graceful_shutdown()
    app_js = (Path(__file__).resolve().parent.parent / "linhvuong" / "web" / "static" / "app.js").read_text(encoding="utf-8")
    assert "bm-even-troops" in app_js
    assert "gd-even-troops" in app_js
