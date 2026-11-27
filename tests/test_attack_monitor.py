"""Kiểm thử module Cảnh Báo Quân Tấn Công (linhvuong/attack_monitor.py, notifications, runtime, web API)."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from linhvuong.attack_monitor import (
    IncomingAttack,
    IncomingAttackMonitor,
    parse_alarm_summary,
    parse_base_incoming,
)
from linhvuong.notifications import NotificationConfig, dispatch_attack_alert
from linhvuong.profile import NotificationProfile, Profile
from linhvuong.roster import City, Roster
import linhvuong.runtime as runtime_mod
from linhvuong.runtime import WorkspaceManager
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.web.app import create_app


def _sample_roster() -> Roster:
    r = Roster()
    r.cities = [
        City(id=22234, name="Q1", type="Thành", pos_x=199, pos_y=-107),
        City(id=22235, name="Q2", type="Thành", pos_x=188, pos_y=-123),
    ]
    r.camps = [
        City(id=-5001, name="Trại 1", type="Doanh trại", pos_x=190, pos_y=-120),
    ]
    return r


def test_parse_alarm_summary_and_base_incoming_real_s53_shape():
    resp41 = {
        "ret": 0,
        "infos": [
            [22234, "Q1", [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], 0],
            [22235, "Q2", [1, 9462], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], 0],
            [-5001, "Trại 1", [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], 1],
        ],
    }
    summary = parse_alarm_summary(resp41)
    assert summary == [
        (22234, "Q1", 0, 0, False),
        (22235, "Q2", 1, 9462, False),
        (-5001, "Trại 1", 0, 0, True),
    ]

    resp40 = {
        "ret": 0,
        "come": [
            [1, 0, "", 1065, "鲜卑部队", 185, -135, [], -1, -1, -1, -1, 9620, 0],
            [2, 123, "Bạn Bè", 22001, "Thành Bạn", 180, -130, [[11, "Triệu Vân"]], 1000, 0, 0, 0, 500, 0],
            [6, 456, "Do Thám", 22002, "Thành Địch", 170, -140, [], -1, -1, -1, -1, 120, 0],
            [5, 789, "Điều Phái", 22234, "Q1", 199, -107, [], -1, -1, -1, -1, 300, 0],
        ],
        "goto": [],
        "battle": [
            [88001, 99999, "Thất Man", 200, -100, 15],  # Bình Man ngoài dã ngoại -> phải bỏ qua!
            [88002, 22235, "Q2", 188, -123, 25],         # Giao chiến ngay tại Q2 -> phải nhận!
        ],
    }
    atks, bats = parse_base_incoming(
        resp40,
        target_base_id=22235,
        target_base_name="Q2",
        target_x=188,
        target_y=-123,
        server_id=53,
        now_epoch=10000.0,
    )
    assert len(atks) == 1
    assert atks[0].is_pvp is False
    assert atks[0].source_name == "鲜卑部队"
    assert atks[0].remaining_seconds == 9620
    assert atks[0].arrival_epoch == 19620.0

    assert len(bats) == 1
    assert bats[0].battle_id == 88002
    assert bats[0].battle_url == "http://sg53.dipan.com/battle/88002"


def test_monitor_pvp_filter_dedup_urgent_escalation_and_battle():
    gw = MagicMock()
    roster = _sample_roster()
    mon = IncomingAttackMonitor()

    # Giả lập phản hồi qua các lượt
    state_holder = {"step": 0}

    def fake_call(endpoint, api_id, data, **kwargs):
        s = state_holder["step"]
        if endpoint == "Common.ashx" and api_id == 41:
            if s in (0, 1, 2):
                return {"ret": 0, "infos": [[22235, "Q2", [1 if s < 2 else 2, 600], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], 0]]}
            if s == 3:
                return {"ret": 0, "infos": [[22235, "Q2", [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], 1]]}
            return {"ret": 0, "infos": [[22235, "Q2", [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], 0]]}
        if endpoint == "Common.ashx" and api_id == 40:
            if s == 0:
                return {
                    "ret": 0,
                    "come": [
                        [1, 0, "", 1065, "鲜卑部队", 185, -135, [], -1, -1, -1, -1, 600, 0],
                        [1, 777, "Tào Tháo", 30001, "Hứa Xương", 150, -100, [[5, "Hạ Hầu Đôn"]], 5000, 2000, 3000, 0, 500, 0],
                    ],
                    "battle": [[90001, 55555, "Man Ngoài", 190, -110, 10]],
                }
            if s == 1:
                # Lượt 2: cùng 1 đợt PvP còn 400s (vẫn > 300s) -> không phát trùng!
                return {
                    "ret": 0,
                    "come": [
                        [1, 0, "", 1065, "鲜卑部队", 185, -135, [], -1, -1, -1, -1, 500, 0],
                        [1, 777, "Tào Tháo", 30001, "Hứa Xương", 150, -100, [[5, "Hạ Hầu Đôn"]], 5000, 2000, 3000, 0, 400, 0],
                    ],
                    "battle": [],
                }
            if s == 2:
                # Lượt 3: đợt PvP cũ tụt xuống còn 250s (<= 300s -> urgent!) + thêm đợt thứ 2 từ cùng Tào Tháo (600s -> initial!)
                return {
                    "ret": 0,
                    "come": [
                        [1, 777, "Tào Tháo", 30001, "Hứa Xương", 150, -100, [[5, "Hạ Hầu Đôn"]], 5000, 2000, 3000, 0, 250, 0],
                        [1, 777, "Tào Tháo", 30001, "Hứa Xương", 150, -100, [[6, "Trương Liêu"]], 4000, 0, 0, 0, 600, 0],
                    ],
                    "battle": [],
                }
            if s == 3:
                # Lượt 4: chiến trường phòng thủ mở tại căn cứ (battle[0][1] == 0 nhưng Common4 trả atside == 2)
                return {
                    "ret": 0,
                    "come": [],
                    "battle": [[77111, 0, "Q2", 188, -123, 20]],
                }
            return {"ret": 0, "come": [], "battle": []}
        if endpoint == "Common.ashx" and api_id == 4:
            return {
                "ret": 0,
                "atside": 2,
                "next_left": 20,
                "enemy": [[2, 30001, "Hứa Xương", 150, -100, 777, "Tào Tháo", "Hạ Hầu Đôn"]],
            }
        return {"ret": 0}

    gw.call.side_effect = fake_call

    # Lượt 0 (now=1000): pvp_only=True chỉ nhận Tào Tháo (initial)
    snap0, ev0 = mon.check_once(gw, roster=roster, server_id=53, pvp_only=True, now_epoch=1000.0, now_monotonic=10.0)
    assert snap0.count == 1
    assert len(ev0) == 1
    assert ev0[0].stage == "initial"
    assert ev0[0].attack.attacker_name == "Tào Tháo"

    # Lượt 1 (now=1100): Tào Tháo còn 400s (arrival=1500 trùng) -> không báo lại
    state_holder["step"] = 1
    snap1, ev1 = mon.check_once(gw, roster=roster, server_id=53, pvp_only=True, now_epoch=1100.0, now_monotonic=110.0)
    assert snap1.count == 1
    assert ev1 == []

    # Lượt 2 (now=1250): đợt 1 còn 250s -> urgent; đợt 2 từ cùng nguồn (arrival=1850) -> initial
    state_holder["step"] = 2
    snap2, ev2 = mon.check_once(gw, roster=roster, server_id=53, pvp_only=True, now_epoch=1250.0, now_monotonic=260.0)
    assert snap2.count == 2
    assert [e.stage for e in ev2] == ["urgent", "initial"]

    # Lượt 3 (now=1520): chiến trường tại Q2 mở (atside=2)
    state_holder["step"] = 3
    snap3, ev3 = mon.check_once(gw, roster=roster, server_id=53, pvp_only=True, now_epoch=1520.0, now_monotonic=530.0)
    assert len(snap3.battles) == 1
    assert [e.stage for e in ev3] == ["battle"]
    assert ev3[0].battle.battle_id == 77111
    assert ev3[0].battle.attackers == ["Tào Tháo"]

    # Lượt 4: an toàn -> dọn sạch
    state_holder["step"] = 4
    snap4, ev4 = mon.check_once(gw, roster=roster, server_id=53, pvp_only=True, now_epoch=2000.0, now_monotonic=1010.0)
    assert snap4.count == 0
    assert snap4.under_attack is False
    assert ev4 == []


def test_monitor_next_check_delay_and_captcha():
    mon = IncomingAttackMonitor()
    # Khi không có địch -> giữ chu kỳ cấu hình (mặc định 5 phút = 300s)
    assert mon.next_check_delay(5, now_epoch=1000.0) == 300.0

    # Khi địch còn xa (1000s > 300s) -> giữ 300s
    mon._last_snapshot.attacks = [
        IncomingAttack(target_base_id=1, target_base_name="Q2", remaining_seconds=1000, arrival_epoch=2000.0)
    ]
    assert mon.next_check_delay(5, now_epoch=1000.0) == 300.0

    # Khi địch còn 400s -> đánh thức sớm vào mốc ~5 phút trước khi tới (~105s)
    assert mon.next_check_delay(5, now_epoch=1600.0) == 105.0

    # Khi địch còn 120s (<= 300s) -> đánh thức lúc chạm thành (~125s)
    assert mon.next_check_delay(5, now_epoch=1880.0) == 125.0

    # Captcha 110 -> raise CaptchaRequired
    gw = MagicMock()
    gw.call.return_value = {"ret": 110}
    with pytest.raises(CaptchaRequired):
        mon.check_once(gw, server_id=53)


def test_notification_config_attack_fields_backward_compat():
    old_data = {
        "desktop_enabled": False,
        "sound_enabled": True,
        "telegram_enabled": True,
        "telegram_bot_token": "tok",
        "telegram_chat_id": "cid",
    }
    np = NotificationProfile.from_dict(old_data)
    assert np.attack_alert_enabled is True
    assert np.attack_alert_pvp_only is False
    assert np.attack_check_interval_minutes == 5

    nc = NotificationConfig.from_dict(old_data)
    assert nc == NotificationConfig.from_dict(nc.to_dict())

    prof = Profile.from_dict({
        "notifications": {
            "attack_alert_enabled": False,
            "attack_alert_pvp_only": True,
            "attack_check_interval_minutes": 12,
        }
    })
    assert prof.notifications.attack_alert_enabled is False
    assert prof.notifications.attack_alert_pvp_only is True
    assert prof.notifications.attack_check_interval_minutes == 12


def test_dispatch_attack_alert_formats_html_log_and_web_event():
    cfg = NotificationConfig(
        desktop_enabled=False,
        sound_enabled=True,
        web_enabled=True,
        telegram_enabled=True,
        telegram_bot_token="bot:tok",
        telegram_chat_id="999",
    )
    atk = IncomingAttack(
        target_base_id=22235,
        target_base_name="Q2 <Main>",
        target_x=188,
        target_y=-123,
        attacker_uid=0,
        attacker_name="",
        source_id=1065,
        source_name="鲜卑部队",
        source_x=185,
        source_y=-135,
        remaining_seconds=9462,
        arrival_epoch=1795830231.0,
    )
    logs = []
    web_evs = []
    with patch("linhvuong.notifications.send_telegram_message", return_value=(True, "ok")) as mock_tg, patch(
        "threading.Thread"
    ) as mock_thread:
        # Chạy inline worker trong test
        def immediate_thread(target=None, **kw):
            m = MagicMock()
            m.start.side_effect = target
            return m

        mock_thread.side_effect = immediate_thread
        ok = dispatch_attack_alert(
            account_key="quilia00 @ S53",
            server_id=53,
            stage="initial",
            attack=atk,
            config=cfg,
            on_log=logs.append,
            on_web_event=web_evs.append,
        )
        assert ok is True
        assert len(logs) == 1
        assert "[NPC] 鲜卑部队 (185, -135)" in logs[0]
        assert len(web_evs) == 1
        assert web_evs[0]["kind"] == "attack"
        assert web_evs[0]["stage"] == "initial"
        mock_tg.assert_called_once()
        tg_msg = mock_tg.call_args[1]["message"]
        assert "Q2 &lt;Main&gt;" in tg_msg
        assert "鲜卑部队" in tg_msg


def test_runtime_and_web_attack_check_endpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_mod, "login", lambda *a, **kw: None)
    monkeypatch.setattr(runtime_mod, "fetch_roster", lambda gw: _sample_roster())
    monkeypatch.setattr(runtime_mod.AccountSession, "start_aux_loop", lambda self: None)

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    sess = wm.login_account(server_id=53, username="quilia00", password="pw")

    def fake_call(endpoint, api_id, data, **kwargs):
        if endpoint == "Common.ashx" and api_id == 41:
            return {"ret": 0, "infos": [[22235, "Q2", [1, 9462], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], 0]]}
        if endpoint == "Common.ashx" and api_id == 40:
            return {
                "ret": 0,
                "come": [[1, 0, "", 1065, "鲜卑部队", 185, -135, [], -1, -1, -1, -1, 9620, 0]],
                "battle": [],
            }
        return {"ret": 0}

    sess.gateway.call = fake_call  # type: ignore[method-assign]

    app = create_app(workspace=wm, host="127.0.0.1", allow_no_auth=True, auto_restore=False)
    client = TestClient(app)
    r = client.post(f"/api/accounts/{sess.account_key}/attacks/check")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["incoming_attacks"]["count"] == 1
    assert body["incoming_attacks"]["under_attack"] is True

    snap = sess.get_status_snapshot()
    assert snap["under_attack"] is True
    assert snap["incoming_attack_count"] == 1
    assert sess.get_aux_status()["incoming_attacks"]["count"] == 1
    wm.graceful_shutdown()
