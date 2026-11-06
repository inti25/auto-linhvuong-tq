import time
from unittest.mock import MagicMock, patch

import pytest

from linhvuong.battle import BattleController, BattleEngine, BattleState, BattleTroop, CombatConfig
from linhvuong.notifications import (
    NotificationConfig,
    dispatch_boss_alert,
    reset_notified_bosses,
    send_desktop_toast,
    send_telegram_message,
)
from linhvuong.profile import CombatProfile, NotificationProfile, Profile


def test_notification_config_serialization():
    """Kiểm tra khởi tạo và tuần tự hóa NotificationProfile."""
    cfg = NotificationConfig(
        desktop_enabled=True,
        sound_enabled=False,
        telegram_enabled=True,
        telegram_bot_token="123456:ABC-DEF",
        telegram_chat_id="987654",
    )
    d = cfg.to_dict()
    assert d["desktop_enabled"] is True
    assert d["sound_enabled"] is False
    assert d["telegram_enabled"] is True
    assert d["telegram_bot_token"] == "123456:ABC-DEF"
    assert d["telegram_chat_id"] == "987654"

    cfg2 = NotificationConfig.from_dict(d)
    assert cfg2 == cfg

    # Kiểm tra khởi tạo bằng tên tham số mới notify_desktop_toast / notify_sound / notify_telegram
    cfg_alt = NotificationConfig(
        notify_desktop_toast=False,
        notify_sound=True,
        notify_telegram=True,
        telegram_bot_token="bot:tok",
        telegram_chat_id="chat123",
    )
    assert cfg_alt.desktop_enabled is False
    assert cfg_alt.notify_desktop_toast is False
    assert cfg_alt.sound_enabled is True
    assert cfg_alt.notify_sound is True
    assert cfg_alt.telegram_enabled is True
    assert cfg_alt.notify_telegram is True

    # Profile integration
    prof = Profile(
        notifications=NotificationProfile(
            notify_desktop_toast=True,
            notify_sound=False,
            notify_telegram=True,
            telegram_bot_token="tok",
            telegram_chat_id="cid",
        ),
        combat=CombatProfile(
            auto_capture_boss=True,
            capture_boss_max_morale="55",
        ),
    )
    p_dict = prof.to_dict()
    assert p_dict["notifications"]["telegram_enabled"] is True
    assert p_dict["notifications"]["notify_desktop_toast"] is True
    assert p_dict["combat"]["auto_capture_boss"] is True
    assert p_dict["combat"]["capture_boss_max_morale"] == "55"

    prof2 = Profile.from_dict(p_dict)
    assert prof2.notifications.telegram_enabled is True
    assert prof2.notifications.notify_desktop_toast is True
    assert prof2.combat.auto_capture_boss is True
    assert prof2.combat.capture_boss_max_morale == "55"


def test_send_desktop_toast_calls_powershell():
    """Kiểm tra send_desktop_toast gọi subprocess.Popen với PowerShell."""
    with patch("subprocess.Popen") as mock_popen, patch("linhvuong.notifications.play_alert_sound") as mock_sound:
        res = send_desktop_toast("Tiêu đề", "Nội dung", sound=True)
        assert res is True
        mock_sound.assert_called_once()
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "powershell" in args[0]


def test_send_telegram_message():
    """Kiểm tra gửi tin nhắn Telegram thành công và xử lý lỗi."""
    # 1. Thiếu cấu hình
    ok, msg = send_telegram_message("", "", "test")
    assert ok is False
    assert "Thiếu" in msg

    # 2. Thành công
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ok, msg = send_telegram_message("test_token", "12345", "<b>Hello</b>")
        assert ok is True
        assert "thành công" in msg
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "api.telegram.org/bottest_token/sendMessage" in url
        payload = mock_post.call_args[1]["json"]
        assert payload["chat_id"] == "12345"
        assert payload["text"] == "<b>Hello</b>"

    # 3. Lỗi từ máy chủ Telegram
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"description": "Chat not found"}
        mock_post.return_value = mock_resp

        ok, msg = send_telegram_message("test_token", "invalid_id", "test")
        assert ok is False
        assert "Chat not found" in msg


def test_dispatch_boss_alert_deduplication():
    """Kiểm tra cơ chế chống lặp: chỉ thông báo 1 lần cho mỗi Boss trên cùng chiến trường."""
    reset_notified_bosses()
    cfg = NotificationConfig(desktop_enabled=False, sound_enabled=False, telegram_enabled=False)
    logged = []

    # Lần 1: Thành công
    res1 = dispatch_boss_alert(
        boss_name="卑弥呼",
        position=11,
        site="倭国部队",
        battle_id=1012,
        server_id=53,
        map_coords=(263, 229),
        config=cfg,
        on_log=logged.append,
    )
    assert res1 is True
    assert len(logged) == 1

    # Lần 2: Cùng battle 1012 và pos 11 -> Bị lọc chống lặp
    res2 = dispatch_boss_alert(
        boss_name="卑弥呼",
        position=11,
        site="倭国部队",
        battle_id=1012,
        server_id=53,
        map_coords=(263, 229),
        config=cfg,
        on_log=logged.append,
    )
    assert res2 is False
    assert len(logged) == 1  # Không phát thêm log

    # Khác chiến trường (VD: 1013) -> Được phát
    res3 = dispatch_boss_alert(
        boss_name="卑弥呼",
        position=11,
        site="倭国部队",
        battle_id=1013,
        server_id=53,
        config=cfg,
        on_log=logged.append,
    )
    assert res3 is True
    assert len(logged) == 2


def test_auto_capture_boss_when_morale_below_threshold():
    """Kiểm tra tính năng tự động bắt BOSS bằng ngân bảo khi sĩ khí < 60."""
    mock_gw = MagicMock()
    mock_gw.base_url = "http://sg53.dipan.com"
    mock_gw._headers.return_value = {}
    mock_gw.current_user_id = 4954
    engine = BattleEngine(mock_gw)

    # Giả lập trạng thái chiến trường: Chỉ còn lại 1 mình Boss Himiko (ô 11) với sĩ khí 45 (< 60)
    our_troop1 = BattleTroop.from_raw([1, "quilia", 4954, "TC1_01", 99056, "", 21936, 0, 1, 100, 0, 10000, 0, 10000, 0, 1, 11, 0, "", 1])
    our_troop2 = BattleTroop.from_raw([2, "quilia", 4954, "TC1_02", 99057, "", 21936, 0, 1, 100, 0, 10000, 0, 10000, 0, 1, 11, 0, "", 1])
    boss_troop = BattleTroop.from_raw([11, "", 0, "卑弥呼", 0, "", 0, 0, 5, 45, 0, 0, 1000, 1000, 0, 0, 0, 0, "", 32])

    state = BattleState(
        ret=0,
        site="倭国部队",
        map_id=561571,
        bout=5,
        bout_left=25,
        attack_total=2,
        defend_total=1,
        our_troops=[our_troop1, our_troop2],
        enemy_troops=[boss_troop],
        boss_troops=[boss_troop],
    )

    # 1. Cấu hình bật tự động bắt (morale < 60)
    cfg = CombatConfig(
        leave_boss_last=True,
        auto_capture_boss=True,
        capture_boss_max_morale=60,
    )

    # Giả lập Common.ashx?id=71 trả về đủ điều kiện (fee = 50, ratio = 85%)
    # Giả lập OPT.ashx?id=54 trả về thành công
    def mock_post_gateway(endpoint, api_id, payload, referer_path="/"):
        if endpoint == "Common.ashx" and api_id == 71:
            return {"ret": 0, "fee": 50, "ratio": 85}
        if endpoint == "OPT.ashx" and api_id == 54:
            return {"ret": 0}
        return {"ret": 0}

    engine._post_gateway = mock_post_gateway
    engine.change_target_attack = MagicMock(return_value=True)

    logs = []
    engine.assign_combat_orders(state, battle_id=1012, config=cfg, on_log=logs.append)

    # Tướng 1 (chủ tướng) phải thi triển action = 5 (Cầm Hoạch)
    engine.change_target_attack.assert_any_call(1012, 1, 11, action=5)
    assert our_troop1.attack_action == 5

    # Tướng 2 phải chuyển thế Phòng Ngự (action = 3) để tránh đánh chết Boss
    engine.change_target_attack.assert_any_call(1012, 2, 11, action=3)
    assert our_troop2.attack_action == 3

    assert any("Cầm Hoạch" in m and "50 Coin" in m and "85%" in m for m in logs)


def test_auto_capture_boss_fallback_when_insufficient_yuanbao():
    """Kiểm tra khi máy chủ báo thiếu ngân bảo (ret 30), bot tự động chuyển toàn quân sang Thủ."""
    mock_gw = MagicMock()
    mock_gw.base_url = "http://sg53.dipan.com"
    mock_gw._headers.return_value = {}
    mock_gw.current_user_id = 4954
    engine = BattleEngine(mock_gw)

    our_troop1 = BattleTroop.from_raw([1, "quilia", 4954, "TC1_01", 99056, "", 21936, 0, 1, 100, 0, 10000, 0, 10000, 0, 1, 11, 0, "", 1])
    boss_troop = BattleTroop.from_raw([11, "", 0, "卑弥呼", 0, "", 0, 0, 5, 45, 0, 0, 1000, 1000, 0, 0, 0, 0, "", 32])

    state = BattleState(
        ret=0,
        site="倭国部队",
        map_id=561571,
        bout=5,
        bout_left=25,
        attack_total=1,
        defend_total=1,
        our_troops=[our_troop1],
        enemy_troops=[boss_troop],
        boss_troops=[boss_troop],
    )

    cfg = CombatConfig(
        leave_boss_last=True,
        auto_capture_boss=True,
        capture_boss_max_morale=60,
    )

    # Máy chủ báo lỗi 30: Thiếu ngân bảo
    engine._post_gateway = MagicMock(return_value={"ret": 30, "fee": 100})
    engine.change_target_attack = MagicMock(return_value=True)

    logs = []
    engine.assign_combat_orders(state, battle_id=1012, config=cfg, on_log=logs.append)

    # Không được áp action = 5 mà phải chuyển sang action = 3 (Phòng ngự)
    engine.change_target_attack.assert_called_with(1012, 1, 11, action=3)
    assert our_troop1.attack_action == 3
    assert any("Không đủ Coin" in m for m in logs)


def test_auto_capture_boss_wears_down_morale_when_morale_too_high():
    """Kiểm tra khi sĩ khí Boss còn >= 60, quân ta tiếp tục tấn công bào mòn để hạ sĩ khí."""
    mock_gw = MagicMock()
    mock_gw.base_url = "http://sg53.dipan.com"
    mock_gw._headers.return_value = {}
    engine = BattleEngine(mock_gw)

    our_troop1 = BattleTroop.from_raw([1, "quilia", 4954, "TC1_01", 99056, "", 21936, 0, 1, 100, 0, 10000, 0, 10000, 0, 1, 11, 0, "", 1])
    boss_troop = BattleTroop.from_raw([11, "", 0, "卑弥呼", 0, "", 0, 0, 5, 85, 0, 0, 2000, 2000, 0, 0, 0, 0, "", 32])

    state = BattleState(
        ret=0,
        site="倭国部队",
        map_id=561571,
        bout=2,
        bout_left=25,
        attack_total=1,
        defend_total=1,
        our_troops=[our_troop1],
        enemy_troops=[boss_troop],
        boss_troops=[boss_troop],
    )

    cfg = CombatConfig(
        leave_boss_last=True,
        auto_capture_boss=True,
        capture_boss_max_morale=60,
    )

    engine.change_target_attack = MagicMock(return_value=True)
    logs = []
    engine.assign_combat_orders(state, battle_id=1012, config=cfg, on_log=logs.append)

    # Tấn công bào mòn (action = 1) chứ chưa bắt (action != 5)
    engine.change_target_attack.assert_called_with(1012, 1, 11, action=1)
    assert any("Bào mòn BOSS" in m and "85% >= 60%" in m for m in logs)
