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
          "rsrc-gbox","rsrc-tnbox","aux-daily","aux-explore","aux-whip","aux-coin","aux-turns",
          "logi-amt","dt-x","dt-y","btn-run-explore","btn-chest-start","btn-chest-stop",
          "btn-logi-xfer","btn-logi-comfort","btn-logi-daily","btn-dt-start","btn-dt-stop","btn-clr-int-log",
          "aux-boost-lbl","aux-explore-lbl","dt-status-lbl","chest-progress-fill","chest-progress-lbl",
          "dt-camp","chest-type","chest-city","chest-times","logi-from","logi-to","logi-type"
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
  "btn-save-acc-only","btn-delete-acc","modal-backdrop","modal-title","modal-body","modal-footer"
];
for (const id of allStaticIds) registerById(makeEl("div", id, id === "tab-content" ? "ws-body" : ""));
byId.get("account-list").scrollHeight = 900;
byId.get("tab-content").scrollHeight = 1200;

const document = {
  activeElement: null,
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
