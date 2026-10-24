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



