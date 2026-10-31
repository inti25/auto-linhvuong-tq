from unittest.mock import MagicMock

import pytest

from linhvuong.battle import (
    COUNTER_MAP,
    FORMATION_NAMES,
    BattleController,
    BattleState,
    BattleTroop,
)


def test_counter_map_rules():
    # 1-Trùy khắc 3-Kê, 3-Kê khắc 5-Ngư, 5-Ngư khắc 2-Câu, 2-Câu khắc 4-Hạc, 4-Hạc khắc 1-Trùy
    assert COUNTER_MAP[3] == 1
    assert COUNTER_MAP[5] == 3
    assert COUNTER_MAP[2] == 5
    assert COUNTER_MAP[4] == 2
    assert COUNTER_MAP[1] == 4


def test_parse_battle_state_live_data():
    raw_data = {
        "ret": 0,
        "site": "野地",
        "mapid": 861985,
        "bout": 2,
        "bout_left": 67,
        "attack_total": 1,
        "defend_total": 3,
        "troops": [
            [1, "NguyenDao", 1067, "廉复卢", 417506, "NB", 15230, 3497823, 1, 93, 0, 102, 0, 102, 0, 0, 0, 0, "", 1],
            [11, "", 0, "山贼", 0, "", 0, 0, 4, 85, 0, 22, 0, 0, 0, 0, 0, 0, "", 16],
            [12, "", 0, "强盗", 0, "", 0, 0, 5, 100, 0, 92, 0, 0, 0, 0, 0, 0, "", 16],
            [13, "", 0, "恶霸", 0, "", 0, 0, 2, 100, 0, 82, 0, 0, 0, 0, 0, 0, "", 16],
        ],
    }

    state = BattleState.from_json(raw_data)
    assert not state.is_ended
    assert state.bout == 2
    assert len(state.our_troops) == 1
    assert len(state.enemy_troops) == 3

    our = state.our_troops[0]
    assert our.position == 1
    assert our.general_id == 417506
    assert our.formation_id == 1  # Trùy hình

    mock_gateway = MagicMock()
    controller = BattleController(mock_gateway)

    # Địch đối diện ở vị trí 11 là Sơn Tặc mang Hạc dực (4)
    # -> Thuật toán phải chọn Câu hình (2)
    chosen_fid, desc = controller.pick_counter_formation(our, state.enemy_troops)
    assert chosen_fid == 2
    assert "Khắc chế đối diện" in desc


def test_pick_counter_formation_leaves_boss_last():
    our = BattleTroop(
        position=1,
        player_name="Player",
        user_id=1,
        general_name="Tướng Ta",
        general_id=101,
        city_id=1,
        formation_id=1,
        morale=100,
        soldiers=100,
        initial_soldiers=100,
        flag=1,
    )

    # BOSS ở vị trí 11 (đối diện) mang Trùy hình (1)
    boss = BattleTroop(
        position=11,
        player_name="",
        user_id=0,
        general_name="关羽 (BOSS)",
        general_id=0,
        city_id=0,
        formation_id=1,
        morale=100,
        soldiers=500,
        initial_soldiers=500,
        flag=0x20,
        is_boss=True,
    )

    # Lính ở vị trí 12 mang Ngư lân (5)
    minion = BattleTroop(
        position=12,
        player_name="",
        user_id=0,
        general_name="Tiểu tốt",
        general_id=0,
        city_id=0,
        formation_id=5,
        morale=100,
        soldiers=80,
        initial_soldiers=80,
        flag=0x10,
        is_boss=False,
    )

    mock_gateway = MagicMock()
    controller = BattleController(mock_gateway)

    # Với leave_boss_last=True: Bỏ qua BOSS ở vị trí 11, khắc chế minion Ngư lân (5) -> Kê hình (3)
    chosen_fid, desc = controller.pick_counter_formation(our, [boss, minion], leave_boss_last=True)
    assert chosen_fid == 3
    assert "Khắc chế số đông" in desc

    # Nếu chỉ còn BOSS: Khắc chế BOSS (Trùy hình 1 -> Hạc dực 4)
    chosen_fid, desc = controller.pick_counter_formation(our, [boss], leave_boss_last=True)
    assert chosen_fid == 4


def test_change_formation_api_call():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ret": 0}
    mock_gateway.session.post.return_value = mock_resp

    controller = BattleController(mock_gateway)
    ok = controller.change_formation(417506, 2)
    assert ok is True
    mock_gateway.session.post.assert_called_once()


def test_track_battle_casualties_and_morale():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}

    # Hiệp 1: Tướng ta 100 lính, sĩ khí 95. Địch 80 lính.
    bout1_resp = MagicMock()
    bout1_resp.status_code = 200
    bout1_resp.json.return_value = {
        "ret": 0,
        "site": "Thảo Phạt - Tiên Phong",
        "mapid": 12345,
        "bout": 1,
        "bout_left": 1,
        "attack_total": 1,
        "defend_total": 1,
        "troops": [
            [1, "Player", 1, "Triệu Vân", 999, "", 15230, 0, 1, 95, 0, 100, 0, 100, 0, 0, 0, 0, "", 1],
            [11, "", 0, "Sơn Tặc", 0, "", 0, 0, 4, 100, 0, 80, 0, 80, 0, 0, 0, 0, "", 16],
        ],
    }

    # Hiệp 2: Tướng ta còn 92 lính (-8), sĩ khí còn 89 (-6). Địch còn 20 lính (diệt 60).
    bout2_resp = MagicMock()
    bout2_resp.status_code = 200
    bout2_resp.json.return_value = {
        "ret": 0,
        "site": "Thảo Phạt - Tiên Phong",
        "mapid": 12345,
        "bout": 2,
        "bout_left": 1,
        "attack_total": 1,
        "defend_total": 1,
        "troops": [
            [1, "Player", 1, "Triệu Vân", 999, "", 15230, 0, 2, 89, 0, 92, 0, 100, 0, 0, 0, 0, "", 1],
            [11, "", 0, "Sơn Tặc", 0, "", 0, 0, 4, 80, 0, 20, 0, 80, 0, 0, 0, 0, "", 16],
        ],
    }

    # Trận kết thúc: ret = 13
    ended_resp = MagicMock()
    ended_resp.status_code = 200
    ended_resp.json.return_value = {"ret": 13}

    # POST mock calls:
    # 1st call: id=24 (bout 1)
    # 2nd call: id=57 (change formation to Câu hình 2)
    # 3rd call: id=26 (battle tips)
    # 4th call: id=24 (bout 2)
    # 5th call: id=26 (battle tips)
    # 6th call: id=24 (ended, ret=13)
    formation_resp = MagicMock()
    formation_resp.status_code = 200
    formation_resp.json.return_value = {"ret": 0}

    tips_resp = MagicMock()
    tips_resp.status_code = 200
    tips_resp.json.return_value = {
        "ret": 0,
        "last_tips_id": 1,
        "tips": [[1, 1000, "Triệu Vân xuất kích tiêu diệt 60 quân địch!"]],
    }

    def side_effect(url, data=None, headers=None, timeout=None):
        if "id=24" in url:
            if not hasattr(side_effect, "b24_count"):
                side_effect.b24_count = 0
            side_effect.b24_count += 1
            if side_effect.b24_count == 1:
                return bout1_resp
            elif side_effect.b24_count == 2:
                return bout2_resp
            else:
                return ended_resp
        elif "id=57" in url:
            return formation_resp
        elif "id=26" in url:
            return tips_resp
        return ended_resp

    mock_gateway.session.post.side_effect = side_effect

    logs = []
    ctrl = BattleController(mock_gateway)
    report = ctrl.track_battle(
        battle_id=0,
        on_log=logs.append,
        auto_counter=True,
        sleep_fn=lambda s: None,
    )

    assert report.is_victory is True
    assert report.total_bouts == 2
    assert report.initial_our_soldiers == 100
    assert report.final_our_soldiers == 92
    assert report.our_losses == 8
    assert report.initial_morale == 95
    assert report.final_morale == 89
    assert report.initial_enemy_soldiers == 80
    assert report.final_enemy_soldiers == 0
    assert report.enemy_losses == 80

    assert len(report.general_stats) == 1
    gstat = report.general_stats[0]
    assert gstat.general_id == 999
    assert gstat.general_name == "Triệu Vân"
    assert gstat.initial_soldiers == 100
    assert gstat.final_soldiers == 92
    assert gstat.loss_soldiers == 8
    assert gstat.initial_morale == 95
    assert gstat.final_morale == 89
    assert gstat.loss_morale == 6

    # Kiểm tra log từng hiệp
    assert any("Chiến trường - Hiệp 1" in l for l in logs)
    assert any("Chiến trường - Hiệp 2" in l for l in logs)
    assert any("Triệu Vân xuất kích tiêu diệt 60 quân địch" in l for l in logs)

    # Kiểm tra log tổng kết chiến đấu
    assert any("🏆 [KẾT QUẢ CHIẾN ĐẤU] CHIẾN THẮNG!" in l for l in logs)
    assert any("THIỆT HẠI QUÂN TA:" in l for l in logs)
    assert any("Tổng quân số: 92/100 quân (Thiệt hại: -8 quân, -8.0%)" in l for l in logs)
    assert any("Sĩ khí trung bình: 89/100 (Ban đầu: 95/100, Biến động: -6)" in l for l in logs)
    assert any("KẾT QUẢ TIÊU DIỆT ĐỊCH:" in l for l in logs)
    assert any("Đã tiêu diệt: 80/80 quân (100.0%)" in l for l in logs)


def test_get_campaign_status():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "ret": 0,
        "task": [[0, "踏征程", 12, 12, 300, 3]],
        "status": 1,
        "current": [0, 180, [[417506, "廉复卢", 0, "", 46, 0, 46, 0]]],
    }
    mock_gateway.session.post.return_value = resp

    ctrl = BattleController(mock_gateway)
    res = ctrl.get_campaign_status()
    assert res is not None
    assert res.get("status") == 1
    assert res["current"][1] == 180


def test_track_battle_waits_for_march_via_common3():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}

    # Common.ashx?id=3: lượt 1 status=1 (còn 2s), lượt 2 status=2 (vào trận)
    c3_march = MagicMock()
    c3_march.status_code = 200
    c3_march.json.return_value = {"ret": 0, "status": 1, "current": [0, 2, []]}

    c3_battle = MagicMock()
    c3_battle.status_code = 200
    c3_battle.json.return_value = {"ret": 0, "status": 2, "current": [0, 60, []]}

    c3_ended = MagicMock()
    c3_ended.status_code = 200
    c3_ended.json.return_value = {"ret": 0, "status": 0, "current": []}

    # OPT.ashx?id=24: lượt 1 ret=13 (chưa tới), lượt 2 hiệp 1, lượt 3 ret=13 (hết trận)
    b24_none = MagicMock()
    b24_none.status_code = 200
    b24_none.json.return_value = {"ret": 13, "troops": []}

    b24_bout1 = MagicMock()
    b24_bout1.status_code = 200
    b24_bout1.json.return_value = {
        "ret": 0,
        "site": "Sơn Tặc",
        "bout": 1,
        "bout_left": 1,
        "troops": [
            [1, "Player", 1, "Triệu Vân", 999, "", 15230, 0, 1, 100, 0, 100, 0, 100, 0, 0, 0, 0, "", 1],
            [11, "", 0, "Sơn Tặc", 0, "", 0, 0, 4, 100, 0, 50, 0, 50, 0, 0, 0, 0, "", 16],
        ],
    }

    tips_resp = MagicMock()
    tips_resp.status_code = 200
    tips_resp.json.return_value = {
        "ret": 0,
        "last_tips_id": 1,
        "tips": [[1, 1000, "Triệu Vân đại thắng!"]],
    }

    call_counts = {"id24": 0, "id3": 0}

    def side_effect(url, data=None, headers=None, timeout=None):
        if "Common.ashx?id=3" in url:
            call_counts["id3"] += 1
            if call_counts["id3"] == 1:
                return c3_march
            elif call_counts["id3"] == 2:
                return c3_battle
            return c3_ended
        elif "id=24" in url:
            call_counts["id24"] += 1
            if call_counts["id24"] == 1:
                return b24_none
            elif call_counts["id24"] == 2:
                return b24_bout1
            return b24_none
        elif "id=26" in url:
            return tips_resp
        return b24_none

    mock_gateway.session.post.side_effect = side_effect

    logs = []
    ctrl = BattleController(mock_gateway)
    report = ctrl.track_battle(
        battle_id=0,
        on_log=logs.append,
        auto_counter=False,
        sleep_fn=lambda s: None,
    )

    assert any("Quân ta đang di chuyển tới chiến trường (còn 2s)" in l for l in logs)
    assert any("Chiến trường - Hiệp 1" in l for l in logs)
    assert any("Triệu Vân đại thắng!" in l for l in logs)
    assert report.total_bouts == 1
    assert report.is_victory is True


def test_user_id_identification_attacker_and_defender():
    # Giả lập quân ta ở phe Thủ (position 11, UserID = 888)
    # Quân địch ở phe Công (position 1, UserID = 999)
    raw_data = {
        "ret": 0,
        "site": "Thành Trì",
        "mapid": 123456,
        "bout": 1,
        "bout_left": 60,
        "attack_total": 1,
        "defend_total": 1,
        "troops": [
            [1, "Kẻ Địch", 999, "Tướng Địch", 10, "", 100, 0, 1, 100, 0, 200, 0, 0, 0, 0, 0, 0, "", 1],
            [11, "Ta", 888, "Tướng Ta", 20, "", 200, 0, 4, 100, 0, 150, 0, 0, 0, 0, 0, 0, "", 1],
        ],
    }

    state = BattleState.from_json(raw_data, current_user_id=888)
    assert not state.is_attacker
    assert len(state.our_troops) == 1
    assert state.our_troops[0].position == 11
    assert state.our_troops[0].general_name == "Tướng Ta"
    assert len(state.enemy_troops) == 1
    assert state.enemy_troops[0].position == 1


def test_attack_action_adaptive_to_unit_type():
    # Cung thủ
    troop_archer = BattleTroop(
        position=1, player_name="P", user_id=1, general_name="Cung Tướng",
        general_id=1, city_id=1, formation_id=1, morale=100, soldiers=100,
        initial_soldiers=100, flag=0, archers=80, infantry=20
    )
    assert troop_archer.dominant_soldier_type() == "archers"
    assert troop_archer.optimal_action_for_unit() == 13  # Hỏa tiễn

    # Kỵ binh
    troop_cav = BattleTroop(
        position=2, player_name="P", user_id=1, general_name="Kỵ Tướng",
        general_id=2, city_id=1, formation_id=1, morale=100, soldiers=100,
        initial_soldiers=100, flag=0, cavalry=90, archers=10
    )
    assert troop_cav.dominant_soldier_type() == "cavalry"
    assert troop_cav.optimal_action_for_unit() == 10  # Đột kích

    # Bộ binh
    troop_inf = BattleTroop(
        position=3, player_name="P", user_id=1, general_name="Bộ Tướng",
        general_id=3, city_id=1, formation_id=1, morale=100, soldiers=100,
        initial_soldiers=100, flag=0, infantry=100
    )
    assert troop_inf.dominant_soldier_type() == "infantry"
    assert troop_inf.optimal_action_for_unit() == 11  # Mãnh công


def test_change_target_attack_opt_54():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ret": 0}
    mock_gateway.session.post.return_value = mock_resp

    engine = BattleController(mock_gateway)
    ok = engine.change_target_attack(battle_id=1001, pos_id=1, dest_pos_id=11, action=13)
    assert ok is True
    mock_gateway.session.post.assert_called_once()
    args, kwargs = mock_gateway.session.post.call_args
    assert "OPT.ashx?id=54" in args[0]
    assert kwargs["data"]["action"] == "13"
    assert kwargs["data"]["destposid"] == "11"
    assert kwargs["data"]["posid"] == "1"


def test_cast_stratagem_opt_70():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ret": 0}
    mock_gateway.session.post.return_value = mock_resp

    engine = BattleController(mock_gateway)
    ok = engine.cast_stratagem(battle_id=1001, pos_id=1, stratagem_id=96)
    assert ok is True
    args, kwargs = mock_gateway.session.post.call_args
    assert "OPT.ashx?id=70" in args[0]
    assert kwargs["data"]["lPlusFunc"] == "96"
    assert kwargs["data"]["lDestPosID"] == "1"


def test_auto_cleanse_confusion_stratagem():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ret": 0}
    mock_gateway.session.post.return_value = mock_resp

    our = BattleTroop(
        position=1, player_name="P", user_id=1, general_name="Tướng Ta",
        general_id=10, city_id=1, formation_id=1, morale=100, soldiers=100,
        initial_soldiers=100, flag=0, status=1  # Đang bị Hỗn loạn
    )
    state = BattleState(
        ret=0, site="Test", map_id=1, bout=2, bout_left=30, attack_total=1, defend_total=1,
        our_troops=[our], enemy_troops=[]
    )

    engine = BattleController(mock_gateway)
    logs = engine.execute_stratagems(state, battle_id=55)
    assert any("Hủy bỏ trạng thái (96)" in l for l in logs)
    assert our.status == 0  # Đã giải phóng


def test_boss_isolation_switches_to_defend():
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg57.dipan.com"
    mock_gateway._headers.return_value = {}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ret": 0}
    mock_gateway.session.post.return_value = mock_resp

    our = BattleTroop(
        position=1, player_name="P", user_id=1, general_name="Tướng Ta",
        general_id=10, city_id=1, formation_id=1, morale=100, soldiers=100,
        initial_soldiers=100, flag=0, attack_action=13
    )
    boss = BattleTroop(
        position=19, player_name="", user_id=0, general_name="Trương Phi (BOSS)",
        general_id=0, city_id=0, formation_id=1, morale=100, soldiers=500,
        initial_soldiers=500, flag=0x20, is_boss=True
    )
    state = BattleState(
        ret=0, site="Test", map_id=1, bout=3, bout_left=30, attack_total=1, defend_total=1,
        our_troops=[our], enemy_troops=[boss], boss_troops=[boss]
    )

    engine = BattleController(mock_gateway)
    logs = engine.assign_combat_orders(state, battle_id=55)
    assert our.attack_action == 3  # Tự động về Phòng ngự
    assert our.target_id == 19
    assert any("Bắt sống BOSS" in l for l in logs)


def test_troop_from_raw_common_monsters_not_identified_as_boss():
    """Kiểm tra quái dã ngoại thông thường (Sơn Tặc, Cường Đạo, Ác Bá, flag=16) không bị nhận diện nhầm là BOSS."""
    raw_bandit = [11, "", 0, "山贼", 0, "", 0, 0, 4, 100, 0, 47, 0, 47, 0, 0, 0, 0, "", 16]
    raw_robber = [12, "", 0, "强盗", 0, "", 0, 0, 4, 100, 0, 59, 0, 59, 0, 0, 0, 0, "", 16]
    raw_bully = [13, "", 0, "恶霸", 0, "", 0, 0, 4, 100, 0, 71, 0, 71, 0, 0, 0, 0, "", 16]

    t1 = BattleTroop.from_raw(raw_bandit)
    t2 = BattleTroop.from_raw(raw_robber)
    t3 = BattleTroop.from_raw(raw_bully)

    assert not t1.is_boss, f"Sơn tặc (pos {t1.position}, flag {t1.flag}) không được là BOSS"
    assert not t2.is_boss, f"Cường đạo (pos {t2.position}, flag {t2.flag}) không được là BOSS"
    assert not t3.is_boss, f"Ác bá (pos {t3.position}, flag {t3.flag}) không được là BOSS"


def test_track_battle_switches_formation_immediately_inside_window_even_when_target_id_zero():
    """Khi vào chiến trường ở cuối hiệp (bout_left <= window) và OPT.ashx?id=54 bị từ chối
    (tướng không có mưu sĩ đi kèm -> target_id vẫn bằng 0), động cơ chiến trường vẫn phải
    đổi sang trận hình khắc chế ngay trước khi sleep và bảo toàn tỷ lệ tác chiến từ Common.ashx?id=12.
    """
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg53.dipan.com"
    mock_gateway._headers.return_value = {}

    events: list[tuple[str, object]] = []

    def side_effect(url, data=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        payload = dict(data or {})
        hdrs = dict(headers or {})
        events.append((url, (payload, hdrs)))

        if "OPT.ashx?id=24" in url:
            b24_calls = sum(1 for u, _ in events if "OPT.ashx?id=24" in u)
            if b24_calls == 1:
                resp.json.return_value = {
                    "ret": 0,
                    "site": "倭国部队",
                    "mapid": 1002,
                    "bout": 1,
                    "bout_left": 12,
                    "attack_total": 1,
                    "defend_total": 1,
                    "troops": [
                        [1, "quilia", 738816, "TP1", 99056, "", 21936, 0, 1, 100, 0, 0, 8395, 8395, 0, 0, 0, 0, "", 1],
                        [11, "", 0, "倭国部队", 0, "", 0, 0, 4, 100, 0, 5000, 0, 5000, 0, 0, 0, 0, "", 16],
                    ],
                }
            else:
                resp.json.return_value = {"ret": 13, "troops": []}
            return resp

        if "OPT.ashx?id=54" in url:
            # Mô phỏng server từ chối đổi mục tiêu/chiêu thức -> our.target_id giữ nguyên 0
            resp.json.return_value = {"ret": 40}
            return resp

        if "Common.ashx?id=12" in url:
            resp.json.return_value = {
                "ret": 0,
                "battle_array": 1,
                "ratio_attack": 80,
                "ratio_PK": 10,
                "ratio_stratagem": 10,
                "withdraw_loss": 15,
                "withdraw_morale": 20,
            }
            return resp

        resp.json.return_value = {"ret": 0, "last_tips_id": 0, "tips": []}
        return resp

    mock_gateway.session.post.side_effect = side_effect

    def record_sleep(sec: float) -> None:
        events.append(("SLEEP", sec))

    ctrl = BattleController(mock_gateway)
    ctrl.track_battle(battle_id=1002, auto_counter=True, sleep_fn=record_sleep)

    opt57_indices = [i for i, (u, _) in enumerate(events) if "OPT.ashx?id=57" in str(u)]
    sleep_indices = [i for i, (u, _) in enumerate(events) if u == "SLEEP"]

    assert len(opt57_indices) == 1, "Phải gửi OPT.ashx?id=57 đổi trận dù our.target_id == 0"
    assert sleep_indices and opt57_indices[0] < sleep_indices[0], (
        "Khi bout_left (12s) <= formation_window_seconds (15s), phải đổi trận ngay trước khi sleep"
    )

    opt57_payload, opt57_headers = events[opt57_indices[0]][1]
    assert opt57_payload["lGeneralID"] == "99056"
    assert opt57_payload["lBattleArray"] == "2"  # Câu hình (2) khắc Hạc dực (4)
    assert opt57_payload["lRatioAttack"] == "80"
    assert opt57_payload["lRatioPK"] == "10"
    assert opt57_payload["lRatioStra"] == "10"
    assert opt57_payload["lWithdrawLoss"] == "15"
    assert opt57_payload["lWithdrawMorale"] == "20"
    assert opt57_headers.get("Referer") == "http://sg53.dipan.com/battle/1002"


def test_assign_combat_orders_falls_back_to_normal_attack_when_unit_skill_rejected():
    """Tướng không có mưu sĩ đi kèm (tactician_id=0) khi gọi chiêu thức binh chủng (10..14)
    bị server từ chối thì phải tự động lùi về Tấn công phổ thông (action=1) để khóa mục tiêu.
    """
    mock_gateway = MagicMock()
    mock_gateway.base_url = "http://sg53.dipan.com"
    mock_gateway._headers.return_value = {}

    sent_actions: list[str] = []

    def side_effect(url, data=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        act = str((data or {}).get("action", ""))
        sent_actions.append(act)
        if act == "10":
            resp.json.return_value = {"ret": 40}  # Từ chối Đột kích vì không có mưu sĩ
        else:
            resp.json.return_value = {"ret": 0}
        return resp

    mock_gateway.session.post.side_effect = side_effect

    our = BattleTroop(
        position=1, player_name="quilia", user_id=738816, general_name="TP1",
        general_id=99056, city_id=21936, formation_id=1, morale=100, soldiers=8395,
        initial_soldiers=8395, flag=1, cavalry=8395, tactician_id=0,
    )
    enemy = BattleTroop(
        position=11, player_name="", user_id=0, general_name="倭国部队",
        general_id=0, city_id=0, formation_id=4, morale=100, soldiers=5000,
        initial_soldiers=5000, flag=16,
    )
    state = BattleState(
        ret=0, site="倭国部队", map_id=1002, bout=1, bout_left=30,
        attack_total=1, defend_total=1, our_troops=[our], enemy_troops=[enemy],
    )

    engine = BattleController(mock_gateway)
    engine.assign_combat_orders(state, battle_id=1002)

    assert sent_actions == ["10", "1"]
    assert our.target_id == 11
    assert our.attack_action == 1






def test_troop_from_raw_man_monsters_at_pos_19_not_identified_as_boss():
    """Kiểm tra các tướng quái Man tộc (Ô Hoàn, Tiên Ti, Hung Nô, Nam Man...)
    đứng ở vị trí 19 (chủ soái dã ngoại, flag=16) không bị nhận diện nhầm là BOSS."""
    raw_wuhuan = [19, "", 0, "乌桓千夫长", 0, "", 0, 0, 4, 100, 0, 500, 0, 500, 0, 0, 0, 0, "", 16]
    raw_xianbei = [19, "", 0, "鲜卑百夫长", 0, "", 0, 0, 4, 100, 0, 500, 0, 500, 0, 0, 0, 0, "", 16]
    raw_xiongnu = [19, "", 0, "匈奴万夫长", 0, "", 0, 0, 4, 100, 0, 500, 0, 500, 0, 0, 0, 0, "", 16]
    raw_nanman = [19, "", 0, "南蛮头领", 0, "", 0, 0, 4, 100, 0, 500, 0, 500, 0, 0, 0, 0, "", 16]
    raw_shanxian = [19, "", 0, "山越首领", 0, "", 0, 0, 4, 100, 0, 500, 0, 500, 0, 0, 0, 0, "", 16]

    for raw in [raw_wuhuan, raw_xianbei, raw_xiongnu, raw_nanman, raw_shanxian]:
        t = BattleTroop.from_raw(raw)
        assert not t.is_boss, f"Quái Man '{t.general_name}' tại pos {t.position} không được coi là BOSS"


def test_boss_man_detection_ashigaru_taisho_and_tribal_bosses():
    """Kiểm tra nhận diện chính xác Boss Man tộc:
    - [足轻大将] (Túc Khinh Đại Tướng) tại vị trí 19 hoặc bất kỳ vị trí nào
    - [倭国足轻大将] có tiền tố tên bộ tộc Uy Quốc
    - Các Boss Man khác: 侍大将, 南蛮大王, 匈奴单于, 突厥可汗, 带来洞主
    - Đồng thời không nhận diện nhầm quái thường: 倭国足轻, 足轻队长, 乌桓千夫长."""
    # 1. Boss Man Uy Quốc (VD: 足轻大将)
    raw_ashigaru = [19, "", 0, "足轻大将", 0, "", 0, 0, 4, 100, 0, 1500, 0, 1500, 0, 0, 0, 0, "", 16]
    t1 = BattleTroop.from_raw(raw_ashigaru)
    assert t1.is_boss is True, "足轻大将 tại vị trí 19 phải được nhận diện là BOSS"

    # 2. Có tiền tố bộ tộc Uy Quốc (倭国足轻大将)
    raw_woguo_ashigaru = [19, "", 0, "倭国足轻大将", 0, "", 0, 0, 4, 100, 0, 1500, 0, 1500, 0, 0, 0, 0, "", 16]
    t2 = BattleTroop.from_raw(raw_woguo_ashigaru)
    assert t2.is_boss is True, "倭国足轻大将 phải được nhận diện là BOSS dù có tiền tố 倭国"

    # 3. Xuất hiện tại vị trí khác vị trí 19 (ví dụ pos 11)
    raw_pos11 = [11, "", 0, "足轻大将", 0, "", 0, 0, 4, 100, 0, 1500, 0, 1500, 0, 0, 0, 0, "", 16]
    t3 = BattleTroop.from_raw(raw_pos11)
    assert t3.is_boss is True, "足轻大将 tại vị trí 11 vẫn phải là BOSS"

    # 4. Các thủ lĩnh / Boss Man tộc khác
    boss_cases = [
        ("侍大将", 19),
        ("南蛮大王", 19),
        ("匈奴单于", 19),
        ("突厥可汗", 19),
        ("带来洞主", 19),
        ("山越大首领", 19),
    ]
    for bname, pos in boss_cases:
        raw_b = [pos, "", 0, bname, 0, "", 0, 0, 4, 100, 0, 2000, 0, 2000, 0, 0, 0, 0, "", 16]
        tb = BattleTroop.from_raw(raw_b)
        assert tb.is_boss is True, f"Boss Man '{bname}' phải được nhận diện là BOSS"

    # 5. Đảm bảo lính thường và đội trưởng tép không bị nhận diện nhầm thành BOSS
    mob_cases = [
        ("倭国足轻", 19),
        ("倭国足轻", 11),
        ("足轻队长", 19),
        ("足轻", 11),
        ("乌桓千夫长", 19),
        ("南蛮头领", 19),
    ]
    for mname, pos in mob_cases:
        raw_m = [pos, "", 0, mname, 0, "", 0, 0, 4, 100, 0, 500, 0, 500, 0, 0, 0, 0, "", 16]
        tm = BattleTroop.from_raw(raw_m)
        assert tm.is_boss is False, f"Quái thường '{mname}' không được nhận diện nhầm là BOSS"


def test_track_battle_boss_alert_format_and_deduplication():
    """Kiểm tra format cảnh báo phát hiện Boss Man chuẩn xác:
    VD: 🐉 PHÁT HIỆN BOSS [足轻大将] tại vị trí 19!
    và không bị trùng lặp log khi on_boss_alert và on_log cùng trỏ tới 1 notify callback."""
    mock_gw = MagicMock()
    mock_gw.base_url = "http://test.com"
    mock_gw._headers.return_value = {}
    mock_gw.current_user_id = 1001

    boss_raw = [19, "", 0, "足轻大将", 0, "", 0, 0, 4, 100, 0, 1500, 0, 1500, 0, 0, 0, 0, "", 16]
    our_raw = [1, "Player", 1001, "Triệu Vân", 5001, "", 2001, 0, 1, 100, 0, 2000, 0, 2000, 0, 1, 19, 0, "", 1]

    # Hiệp 1: Còn cả ta và boss -> Hiệp 2: Kết thúc
    bout1_resp = {
        "ret": 0,
        "bout": 1,
        "bout_left": 30,
        "site": "Quân đoàn Man tộc",
        "troops": [our_raw, boss_raw],
        "tips": [],
    }
    bout2_resp = {
        "ret": 0,
        "bout": 2,
        "bout_left": 0,
        "site": "Quân đoàn Man tộc",
        "troops": [our_raw],
        "tips": [],
    }

    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.json.return_value = bout1_resp

    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.json.return_value = bout2_resp

    resp_tip = MagicMock()
    resp_tip.status_code = 200
    resp_tip.json.return_value = {"ret": 0, "tips": []}

    mock_gw.session.post.side_effect = [resp1, resp_tip, resp2, resp_tip]

    logged_messages = []
    def single_notify(msg: str):
        logged_messages.append(msg)

    ctrl = BattleController(mock_gw)
    report = ctrl.track_battle(
        battle_id=9999,
        on_log=single_notify,
        on_boss_alert=single_notify,  # cả 2 cùng trỏ tới 1 hàm như trong BinhMan / GoiDan
        leave_boss_last=True,
        sleep_fn=lambda s: None,
    )

    assert report.boss_detected is True
    assert report.boss_name == "足轻大将"

    # Kiểm tra log phát hiện boss đúng định dạng
    boss_alerts = [m for m in logged_messages if "🐉 PHÁT HIỆN BOSS [足轻大将] tại vị trí 19!" in m]
    assert len(boss_alerts) == 1, f"Thông báo boss phải được log đúng 1 lần, thực tế: {len(boss_alerts)} lần ({boss_alerts})"
    assert "🐉 PHÁT HIỆN BOSS [足轻大将] tại vị trí 19!" in boss_alerts[0]


def test_troop_from_raw_real_server_mixed_troops_soldier_count():
    """Kiểm tra dữ liệu thực tế từ máy chủ (VD: server 53 quái 鲜卑千夫长 có 2154 bộ binh và 1569 kỵ binh).
    Số quân soldiers phải tính tổng toàn bộ binh chủng (3723 lính), không được bỏ sót kỵ binh."""
    raw_qianfu = [11, "", 0, "鲜卑千夫长", 0, "", 0, 0, 2, 100, 0, 2154, 1569, 0, 0, 0, 0, 0, "", 16]
    troop = BattleTroop.from_raw(raw_qianfu)
    assert troop.infantry == 2154
    assert troop.cavalry == 1569
    assert troop.soldiers == 3723
    assert troop.initial_soldiers == 3723
    assert not troop.is_boss

    raw_yongshi = [12, "", 0, "鲜卑勇士", 0, "", 0, 0, 2, 100, 0, 0, 5000, 0, 0, 0, 0, 0, "", 16]
    troop_ys = BattleTroop.from_raw(raw_yongshi)
    assert troop_ys.cavalry == 5000
    assert troop_ys.soldiers == 5000
    assert not troop_ys.is_boss


def test_wait_and_track_world_battle_marching_countdown_and_arrival_grace_period():
    """Kiểm tra cơ chế theo dõi chiến trường khi quân đang hành quân (sắp tới nơi):
    - Đếm lùi thời gian hành quân (>5s và <=5s 'chuẩn bị tiếp chiến').
    - Khi quân vừa tới nơi (was_marching, march_left=None), phải có grace period chờ server khởi tạo
      thay vì return None ngay lập tức."""
    mock_gw = MagicMock()
    mock_gw.base_url = "http://sg53.dipan.com"
    mock_gw._headers.return_value = {}

    def mk_resp(data):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = data
        return m

    resp_march_8 = {"ret": 0, "goto": [[7001, 1, 0, "", 555, "鲜卑", 269, 211, [[99056, "TC8"]], 0, 16000, 0, 0, 8, 1]], "battle": []}
    resp_march_3 = {"ret": 0, "goto": [[7001, 1, 0, "", 555, "鲜卑", 269, 211, [[99056, "TC8"]], 0, 16000, 0, 0, 3, 1]], "battle": []}
    resp_arrival = {"ret": 0, "goto": [], "battle": []}
    resp_battle_ready = {"ret": 0, "goto": [], "battle": [[1054, 1054, "鲜卑部队", 269, 211, 67]]}

    c4_empty = {"ret": 0, "battle_id": 0, "myside": []}
    c4_ready = {"ret": 0, "battle_id": 1054, "myside": [[1, 21936, "ThienCo", 280, 237, 738816, "quilia", "TC8", 0, 16000, 0, 0, 100, 99056]]}

    b24_ended = {"ret": 13}

    r40_queue = [resp_march_8, resp_march_3, resp_arrival, resp_arrival, resp_battle_ready]
    c4_queue = [c4_empty, c4_ready]

    def session_post(url, data=None, headers=None, timeout=None):
        if "id=32" in url:
            return mk_resp({"ret": 0, "list": []})
        if "id=40" in url:
            data = r40_queue.pop(0) if r40_queue else {"ret": 0, "goto": [], "battle": []}
            return mk_resp(data)
        if "id=4" in url:
            data = c4_queue.pop(0) if c4_queue else {"ret": 0, "battle_id": 0, "myside": []}
            return mk_resp(data)
        if "id=24" in url:
            return mk_resp(b24_ended)
        return mk_resp({"ret": 0})

    mock_gw.session.post.side_effect = session_post

    logs = []
    ctrl = BattleController(mock_gw)
    report = ctrl.wait_and_track_world_battle(
        generals=[99056],
        origin_id=21936,
        on_log=logs.append,
        sleep_fn=lambda s: None,
    )

    assert report is not None
    assert any("⏳ Quân ta đang hành quân tới mục tiêu (còn ~8s)..." in l for l in logs)
    assert any("⚡ Quân ta sắp tới nơi (còn ~3s), chuẩn bị tiếp chiến..." in l for l in logs)
    assert any("⚔️ Quân ta đã tới vị trí mục tiêu, đang kết nối chiến trường..." in l for l in logs)
    assert any("⚔️ Phát hiện chiến trường đang diễn ra (ID: 1054)" in l for l in logs)


def test_inspect_world_movements_resolves_base_from_common_32_when_origin_zero():
    """Khi origin_id=0 (không chỉ định thành), inspect_world_movements phải tự tra cứu
    căn cứ của võ tướng qua Common.ashx?id=32 để thăm dò đúng tid của thành/trại đó."""
    mock_gw = MagicMock()
    mock_gw.base_url = "http://sg53.dipan.com"
    mock_gw._headers.return_value = {}

    def mk_resp(data):
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = data
        return m

    def session_post(url, data=None, headers=None, timeout=None):
        if "id=32" in url:
            return mk_resp({
                "ret": 0,
                "list": [
                    [21936, "ThienCo", 280, 237, [[99056, "TC8", "", 2, 0, 16, 76, 100, 860, 860]]],
                ],
            })
        if "id=40" in url and data and data.get("tid") == "21936":
            return mk_resp({
                "ret": 0,
                "battle": [[1054, 1054, "鲜卑部队", 269, 211, 67]],
                "goto": [],
            })
        if "id=4" in url:
            return mk_resp({
                "ret": 0,
                "battle_id": 1054,
                "myside": [[1, 21936, "ThienCo", 280, 237, 738816, "quilia", "TC8", 0, 16000, 0, 0, 100, 99056]],
            })
        return mk_resp({"ret": 0, "battle": [], "goto": []})

    mock_gw.session.post.side_effect = session_post

    ctrl = BattleController(mock_gw)
    bid, state, march = ctrl.inspect_world_movements(generals=[99056], origin_id=0)
    assert bid == 1054
    assert march is None


def test_binh_man_pos_11_regular_troop_and_bujiang_not_identified_as_boss():
    """Kiểm tra trận Bình Man không có boss nhưng quân địch tiền phong ở vị trí 11
    (như 倭国部将, 倭国部队, 部将...) với cờ flag 16, 32 hoặc 48 (0x20)
    tuyệt đối KHÔNG bị nhận diện nhầm là BOSS.
    """
    test_cases = [
        ("倭国部将", 16),
        ("倭国部将", 48),
        ("倭国部队", 16),
        ("倭国部队", 48),
        ("部将", 16),
        ("部将", 48),
        ("鲜卑部将", 16),
        ("南蛮部将", 16),
        ("先锋", 16),
        ("副将", 16),
    ]

    for name, flag in test_cases:
        raw = [11, "", 0, name, 0, "", 0, 0, 4, 100, 0, 5000, 0, 5000, 0, 0, 0, 0, "", flag]
        troop = BattleTroop.from_raw(raw)
        assert troop.is_boss is False, (
            f"Quái thường '{name}' tại vị trí 11 (flag {flag}) không được coi là BOSS"
        )

    # Mô phỏng trận Bình Man 1013 (sg53.dipan.com/battle/1013)
    battle_1013_payload = {
        "ret": 0,
        "site": "倭国部队",
        "mapid": 1013,
        "bout": 1,
        "bout_left": 30,
        "attack_total": 1,
        "defend_total": 1,
        "troops": [
            [1, "quilia", 738816, "TC1_01", 99056, "", 21936, 0, 1, 100, 0, 0, 8000, 8000, 0, 0, 0, 0, "", 1],
            [11, "", 0, "倭国部将", 0, "", 0, 0, 4, 100, 0, 5000, 0, 5000, 0, 0, 0, 0, "", 48],
        ],
    }
    state = BattleState.from_json(battle_1013_payload, current_user_id=738816)
    assert len(state.boss_troops) == 0, "Trận Bình Man 1013 không có BOSS thì boss_troops phải rỗng"
    assert state.enemy_troops[0].is_boss is False

    # Đồng thời đảm bảo Boss thật (足轻大将, 侍大将) tại vị trí 11 vẫn được nhận diện chính xác
    real_boss_pos11 = BattleTroop.from_raw(
        [11, "", 0, "足轻大将", 0, "", 0, 0, 4, 100, 0, 1500, 0, 1500, 0, 0, 0, 0, "", 16]
    )
    assert real_boss_pos11.is_boss is True, "Boss thật [足轻大将] tại vị trí 11 phải được nhận diện là BOSS"


