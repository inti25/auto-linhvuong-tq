import pytest
from unittest.mock import MagicMock

from linhvuong.gateway import GatewayClient
from linhvuong.roster import Army, General
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.troops import ArmyProvisioner, TargetArmy, has_population_shortage


class FakeServer:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        endpoint = url.split("/GateWay/")[1]
        self.calls.append((endpoint, dict(data)))
        payload = self.responses.get(endpoint, {"ret": 0})
        if isinstance(payload, list):
            resp_data = payload.pop(0) if payload else {"ret": 0}
        else:
            resp_data = payload

        class Resp:
            status_code = 200
            def json(self):
                return resp_data

        return Resp()


def make_provisioner(responses=None):
    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)
    return ArmyProvisioner(client, sleep_fn=lambda s: None), server


def test_target_army_defaults_and_aliases():
    t1 = TargetArmy()
    assert t1.infantry == 0
    assert t1.cavalry == 0
    assert t1.archers == 0
    assert t1.total == 0

    t2 = TargetArmy(bo_binh=1000, ky_binh=2000, cung_binh=3000)
    assert t2.infantry == 1000
    assert t2.cavalry == 2000
    assert t2.archers == 3000
    assert t2.total == 6000


def test_provisioner_adjust_troops_tops_up_deficit_only():
    prov, server = make_provisioner()
    current = Army(infantry=100, cavalry=50, archers=200)
    target = TargetArmy(infantry=300, cavalry=50, archers=150)

    results = prov.adjust_troops(
        base_id=15230,
        general_id=417506,
        current_army=current,
        target_army=target,
        auto_recruit=True,
    )

    # Chỉ bổ sung Bộ binh (+200), không tháo Cung binh (-50)
    opt6_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=6"]
    assert len(opt6_calls) == 1
    assert opt6_calls[0][1]["lSoldierType"] == "1"
    assert opt6_calls[0][1]["lAmount"] == "200"
    assert opt6_calls[0][1]["tid"] == "15230"
    assert len(results) == 1
    assert results[0] == (1, 200, True, 0)


def test_provisioner_adjust_troops_auto_recruits_when_ret_53():
    # Giả lập OPT.ashx?id=6 trả về 53 (thiếu tân binh), sau đó chiêu mộ (id=41) thành công và thử lại id=6 thành công
    responses = {
        "OPT.ashx?id=6": [{"ret": 53}, {"ret": 0}],
        "OPT.ashx?id=41": {"ret": 0},
    }
    prov, server = make_provisioner(responses)
    current = Army(infantry=0, cavalry=0, archers=0)
    target = TargetArmy(infantry=500, cavalry=0, archers=0)

    logs = []
    results = prov.adjust_troops(
        base_id=15230,
        general_id=417506,
        current_army=current,
        target_army=target,
        auto_recruit=True,
        on_log=logs.append,
    )

    assert len(results) == 1
    assert results[0] == (1, 500, True, 0)
    opt41_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=41"]
    assert len(opt41_calls) == 1
    assert opt41_calls[0][1]["lAmount"] == "500"
    assert any("Tân binh không đủ" in m for m in logs)


def test_provisioner_adjust_morale_caps_step_at_10():
    prov, server = make_provisioner()
    succ, ret = prov.adjust_morale(base_id=15230, general_id=417506, current_morale=80, min_morale=95)
    assert succ is True
    assert ret == 0

    opt47_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=47"]
    assert len(opt47_calls) == 1
    assert opt47_calls[0][1]["lAddPoint"] == "10"
    assert opt47_calls[0][1]["lGeneralID"] == "417506"


def test_provisioner_heal_general():
    prov, server = make_provisioner()
    succ, ret = prov.heal_general(base_id=15230, general_id=417506)
    assert succ is True
    assert ret == 0

    opt31_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=31"]
    assert len(opt31_calls) == 1
    assert opt31_calls[0][1]["lCityTentID"] == "15230"
    assert opt31_calls[0][1]["lGeneralID"] == "417506"


def test_provisioner_camp_generals_with_parent_city():
    # Điều tướng trại (-101) về thành mẹ (15230) -> trị thương -> bổ sung -> tái xuất ra trại
    prov, server = make_provisioner()
    current_map = {417506: Army(100, 0, 0)}
    morale_map = {417506: 80}
    target = TargetArmy(infantry=1000, cavalry=0, archers=0)

    logs = []
    succ = prov.provision_camp_generals_with_parent_city(
        camp_id=-101,
        parent_city_id=15230,
        general_ids=[417506],
        target_army=target,
        current_armies=current_map,
        current_morales=morale_map,
        min_morale=95,
        on_log=logs.append,
    )

    assert succ is True
    # Kiểm tra lệnh chuyển quân về thành mẹ và tái phái ra trại
    opt50_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=50"]
    assert len(opt50_calls) == 2
    # Lần 1: Trại (-101) -> Thành mẹ (15230)
    assert opt50_calls[0][1]["lCityID"] == "-101"
    assert opt50_calls[0][1]["lDestID"] == "15230"
    # Lần 2: Thành mẹ (15230) -> Trại (-101)
    assert opt50_calls[1][1]["lCityID"] == "15230"
    assert opt50_calls[1][1]["lDestID"] == "-101"

    # Kiểm tra trị thương và bổ sung lính tại thành mẹ
    opt31_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=31"]
    assert len(opt31_calls) == 1
    assert opt31_calls[0][1]["lCityTentID"] == "15230"

    opt6_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=6"]
    assert len(opt6_calls) == 1
    assert opt6_calls[0][1]["tid"] == "15230"
    assert opt6_calls[0][1]["lAmount"] == "900"


def test_transfer_troops_between_generals_payload_noop_and_captcha():
    prov, server = make_provisioner()
    succ, ret = prov.transfer_troops_between_generals(
        base_id=15230,
        from_general_id=101,
        to_general_id=102,
        infantry=500,
        cavalry=1200,
        archers=300,
    )
    assert succ is True
    assert ret == 0
    opt39_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=39"]
    assert len(opt39_calls) == 1
    assert opt39_calls[0][1] == {
        "lFromGeneralID": "101",
        "lToGeneralID": "102",
        "infantry": "500",
        "cavalry": "1200",
        "bowman": "300",
        "mangonel": "0",
        "tid": "15230",
        "_": "",
    }

    # No-op khi cùng tướng hoặc tổng = 0
    server.calls.clear()
    assert prov.transfer_troops_between_generals(15230, 101, 101, cavalry=100) == (True, 0)
    assert prov.transfer_troops_between_generals(15230, 101, 102) == (True, 0)
    assert server.calls == []

    # Bắt Captcha cho cả ret=110 và ret=73
    for cap_ret in (110, 73):
        cap_prov, _ = make_provisioner({"OPT.ashx?id=39": {"ret": cap_ret}})
        with pytest.raises(CaptchaRequired):
            cap_prov.transfer_troops_between_generals(15230, 101, 102, cavalry=100)


def test_balance_troops_per_branch_uses_opt39_no_withdraw_and_handles_remainder():
    prov, server = make_provisioner()
    armies = {
        1: Army(infantry=1000, cavalry=12000, archers=0),
        2: Army(infantry=2000, cavalry=9000, archers=0),
        3: Army(infantry=0, cavalry=9000, archers=0),
    }
    gens = {
        1: General(1, "G1", "vo", 10, 100, 100, 100, status=0, upgrading_time=0),
        2: General(2, "G2", "vo", 10, 100, 100, 100, status=0, upgrading_time=0),
        3: General(3, "G3", "vo", 10, 100, 100, 100, status=0, upgrading_time=0),
    }
    logs = []
    updated, changed = prov.balance_troops(15230, [1, 2, 3], armies, base_gens=gens, on_log=logs.append)
    assert changed is True
    assert updated[1] == Army(1000, 10000, 0)
    assert updated[2] == Army(1000, 10000, 0)
    assert updated[3] == Army(1000, 10000, 0)
    assert all(ep == "OPT.ashx?id=39" for ep, _ in server.calls)
    assert not any(ep == "OPT.ashx?id=6" for ep, _ in server.calls)
    assert len(logs) >= 2

    # Khi max - min <= 1 -> không gọi API
    server.calls.clear()
    updated2, changed2 = prov.balance_troops(
        15230,
        [1, 2, 3],
        {1: Army(34, 0, 0), 2: Army(33, 0, 0), 3: Army(33, 0, 0)},
        base_gens=gens,
    )
    assert changed2 is False
    assert server.calls == []
    assert updated2[1].infantry == 34


def test_balance_troops_coalesces_filters_busy_and_falls_back_on_cap_error():
    # 1. Coalesce 2 binh chủng trên cùng cặp (1 -> 2)
    prov, server = make_provisioner()
    updated, changed = prov.balance_troops(
        base_id=-501,  # Hỗ trợ cả Doanh trại ID âm
        general_ids=[1, 2],
        current_armies={1: Army(400, 600, 0), 2: Army(0, 0, 0)},
    )
    assert changed is True
    assert updated[1] == Army(200, 300, 0)
    assert updated[2] == Army(200, 300, 0)
    assert len(server.calls) == 1
    assert server.calls[0][1]["tid"] == "-501"
    assert server.calls[0][1]["infantry"] == "200"
    assert server.calls[0][1]["cavalry"] == "300"

    # 2. Lọc bỏ tướng bận / đang luyện sĩ khí / văn quan
    prov_filter, srv_filter = make_provisioner()
    gens = {
        1: General(1, "Idle1", "vo", 10, 100, 100, 100, status=0, upgrading_time=0),
        2: General(2, "Busy", "vo", 10, 100, 100, 100, status=16, upgrading_time=0),
        3: General(3, "Morale", "vo", 10, 80, 100, 100, status=0, upgrading_time=120),
    }
    _, ch_filter = prov_filter.balance_troops(
        15230,
        [1, 2, 3],
        {1: Army(1000, 0, 0), 2: Army(0, 0, 0), 3: Army(0, 0, 0)},
        base_gens=gens,
    )
    assert ch_filter is False
    assert srv_filter.calls == []

    # 3. Gộp thất bại -> tách từng binh chủng; nếu tướng 2 lỗi ret=43 cho Kỵ, Bộ vẫn thành công và Kỵ chuyển sang tướng 3
    responses = {
        "OPT.ashx?id=39": [
            {"ret": 43},  # Coalesced (1 -> 2: Bộ+Kỵ) thất bại
            {"ret": 0},   # Tách Bộ (1 -> 2) thành công
            {"ret": 43},  # Tách Kỵ (1 -> 2) thất bại -> bỏ qua 2 cho Kỵ
            {"ret": 0},   # Chuyển Kỵ (1 -> 3) thành công
        ]
    }
    prov_fb, srv_fb = make_provisioner(responses)
    gens_fb = {
        1: General(1, "G1", "vo", 10, 100, 100, 100),
        2: General(2, "G2", "vo", 10, 100, 100, 100),
        3: General(3, "G3", "vo", 10, 100, 100, 100),
    }
    logs = []
    upd_fb, ch_fb = prov_fb.balance_troops(
        15230,
        [1, 2, 3],
        {
            1: Army(600, 600, 0),
            2: Army(0, 0, 0),
            3: Army(300, 0, 0),
        },
        base_gens=gens_fb,
        on_log=logs.append,
    )
    assert ch_fb is True
    assert upd_fb[2] == Army(300, 0, 0)
    assert upd_fb[3] == Army(300, 200, 0)
    assert upd_fb[1] == Army(300, 400, 0)
    assert any("thất bại" in m and "G2" in m for m in logs)


def _simulate_game_morale(armies_before, gens, calls):
    """Mô phỏng công thức sĩ khí trung bình theo quân số trong game qua các lệnh OPT.ashx?id=39."""
    totals = {gid: a.total for gid, a in armies_before.items()}
    morales = {gid: float(g.morale) for gid, g in gens.items()}
    for ep, data in calls:
        if ep != "OPT.ashx?id=39":
            continue
        d = int(data["lFromGeneralID"])
        r = int(data["lToGeneralID"])
        x = int(data["infantry"]) + int(data["cavalry"]) + int(data["bowman"]) + int(data["mangonel"])
        if x <= 0:
            continue
        n_r = totals[r]
        morales[r] = morales[d] if n_r <= 0 else (n_r * morales[r] + x * morales[d]) / (n_r + x)
        totals[r] += x
        totals[d] -= x
    return totals, morales


def test_balance_troops_morale_max_min_floor_and_donor_preservation():
    # 1. Nâng sàn sĩ khí thấp nhất: D1(1500, mor=100), D2(1500, mor=80), R1(500, mor=100), R2(500, mor=20)
    prov1, srv1 = make_provisioner()
    armies1 = {1: Army(0, 1500, 0), 2: Army(0, 1500, 0), 3: Army(0, 500, 0), 4: Army(0, 500, 0)}
    gens1 = {
        1: General(1, "D1", "vo", 10, 100, 100, 100),
        2: General(2, "D2", "vo", 10, 80, 100, 100),
        3: General(3, "R1", "vo", 10, 100, 100, 100),
        4: General(4, "R2", "vo", 10, 20, 100, 100),
    }
    upd1, ch1 = prov1.balance_troops(15230, [1, 2, 3, 4], armies1, base_gens=gens1)
    assert ch1 is True
    assert all(a == Army(0, 1000, 0) for a in upd1.values())
    _, m1 = _simulate_game_morale(armies1, gens1, srv1.calls)
    assert m1[4] == pytest.approx(60.0)
    assert m1[3] == pytest.approx(90.0)
    assert min(m1.values()) == pytest.approx(60.0)

    # 2. Bảo toàn R1=100 khi sàn cố định là D2=20 (không làm tụt R1 vô ích)
    prov2, srv2 = make_provisioner()
    armies2 = {1: Army(0, 1500, 0), 2: Army(0, 1500, 0), 3: Army(0, 500, 0), 4: Army(0, 500, 0)}
    gens2 = {
        1: General(1, "D1", "vo", 10, 100, 100, 100),
        2: General(2, "D2", "vo", 10, 20, 100, 100),
        3: General(3, "R1", "vo", 10, 100, 100, 100),
        4: General(4, "R2", "vo", 10, 20, 100, 100),
    }
    prov2.balance_troops(15230, [1, 2, 3, 4], armies2, base_gens=gens2)
    _, m2 = _simulate_game_morale(armies2, gens2, srv2.calls)
    assert m2[3] == pytest.approx(100.0)
    assert m2[4] == pytest.approx(20.0)

    # 3. Xét đúng quân số gốc n_R: R1(100, mor=20) cần 900, R2(500, mor=20) cần 500
    prov3, srv3 = make_provisioner()
    armies3 = {1: Army(0, 1900, 0), 2: Army(0, 1500, 0), 3: Army(0, 100, 0), 4: Army(0, 500, 0)}
    gens3 = {
        1: General(1, "D1", "vo", 10, 100, 100, 100),
        2: General(2, "D2", "vo", 10, 60, 100, 100),
        3: General(3, "R1", "vo", 10, 20, 100, 100),
        4: General(4, "R2", "vo", 10, 20, 100, 100),
    }
    upd3, _ = prov3.balance_troops(15230, [1, 2, 3, 4], armies3, base_gens=gens3)
    assert all(a == Army(0, 1000, 0) for a in upd3.values())
    _, m3 = _simulate_game_morale(armies3, gens3, srv3.calls)
    assert min(m3.values()) == pytest.approx(60.0)
    assert m3[4] == pytest.approx(60.0)
    assert m3[3] == pytest.approx(72.0)


def test_balance_troops_morale_water_filling_assortative_empty_and_replan():
    # 4. Chia nhỏ donor giữa 2 tướng yếu (water-filling) đạt tối đa sàn 45.0
    prov4, srv4 = make_provisioner()
    armies4 = {1: Army(0, 1500, 0), 2: Army(0, 1500, 0), 3: Army(0, 500, 0), 4: Army(0, 500, 0)}
    gens4 = {
        1: General(1, "D1", "vo", 10, 100, 100, 100),
        2: General(2, "D2", "vo", 10, 60, 100, 100),
        3: General(3, "R1", "vo", 10, 0, 100, 100),
        4: General(4, "R2", "vo", 10, 20, 100, 100),
    }
    prov4.balance_troops(15230, [1, 2, 3, 4], armies4, base_gens=gens4)
    _, m4 = _simulate_game_morale(armies4, gens4, srv4.calls)
    assert m4[3] == pytest.approx(45.0)
    assert m4[4] == pytest.approx(45.0)

    # 5. Đẩy R2 chạm sàn D2=50 bằng đúng phần cần thiết rồi giữ tối đa R1 (100 -> 95)
    prov5, srv5 = make_provisioner()
    armies5 = {1: Army(0, 15000, 0), 2: Army(0, 15000, 0), 3: Army(0, 5000, 0), 4: Army(0, 5000, 0)}
    gens5 = {
        1: General(1, "D1", "vo", 10, 100, 100, 100),
        2: General(2, "D2", "vo", 10, 50, 100, 100),
        3: General(3, "R1", "vo", 10, 100, 100, 100),
        4: General(4, "R2", "vo", 10, 40, 100, 100),
    }
    prov5.balance_troops(15230, [1, 2, 3, 4], armies5, base_gens=gens5)
    _, m5 = _simulate_game_morale(armies5, gens5, srv5.calls)
    assert m5[4] == pytest.approx(50.0)
    assert m5[3] == pytest.approx(95.0)

    # 6. Tướng trống 0 quân nhận trọn sĩ khí của tướng cho (kể cả khi tướng 0 quân có morale=0)
    prov6, srv6 = make_provisioner()
    armies6 = {1: Army(0, 1000, 0), 2: Army(0, 0, 0)}
    gens6 = {
        1: General(1, "D1", "vo", 10, 88, 100, 100),
        2: General(2, "R0", "vo", 10, 0, 100, 100),
    }
    prov6.balance_troops(15230, [1, 2], armies6, base_gens=gens6)
    _, m6 = _simulate_game_morale(armies6, gens6, srv6.calls)
    assert m6[2] == pytest.approx(88.0)

    # 7. Lập lại kế hoạch tối ưu sau khi một tướng nhận bị chặn (ret=43)
    prov7, srv7 = make_provisioner({"OPT.ashx?id=39": [{"ret": 43}, {"ret": 0}, {"ret": 0}]})
    armies7 = {1: Army(0, 1500, 0), 2: Army(0, 1500, 0), 3: Army(0, 500, 0), 4: Army(0, 500, 0)}
    gens7 = {
        1: General(1, "D1", "vo", 10, 100, 100, 100),
        2: General(2, "D2", "vo", 10, 50, 100, 100),
        3: General(3, "R1", "vo", 10, 100, 100, 100),
        4: General(4, "R2_cap", "vo", 10, 20, 100, 100),
    }
    upd7, ch7 = prov7.balance_troops(15230, [1, 2, 3, 4], armies7, base_gens=gens7)
    assert ch7 is True
    assert upd7[4] == Army(0, 500, 0)
    assert upd7[3] == Army(0, 1000, 0)
    # Sau khi R2 bị chặn, D1 (mor=100) phải ưu tiên ghép với R1 trước D2 (mor=50)
    ok_calls = [d for ep, d in srv7.calls[1:] if ep == "OPT.ashx?id=39"]
    assert len(ok_calls) == 1
    assert ok_calls[0]["lFromGeneralID"] == "1"
    assert ok_calls[0]["lToGeneralID"] == "3"
    assert ok_calls[0]["cavalry"] == "500"


def test_check_idle_population_parses_city6_list_and_dict_and_clamps_negative():
    prov, _ = make_provisioner({"City.ashx?id=6": {"ret": 0, "population": [123944, 123944, 21399, 94966, 7579]}})
    assert prov.check_idle_population(15230) == 7579

    prov_neg, _ = make_provisioner({"City.ashx?id=6": {"ret": 0, "population": [100, 100, 80, 30, -10]}})
    assert prov_neg.check_idle_population(15230) == 0

    prov_dict, _ = make_provisioner({"City.ashx?id=6": {"ret": 0, "data": {"m_lpopulation_idle_man": 133680}}})
    assert prov_dict.check_idle_population(10129) == 133680

    prov_cap, _ = make_provisioner({"City.ashx?id=6": {"ret": 110}})
    with pytest.raises(CaptchaRequired):
        prov_cap.check_idle_population(15230)


def test_comfort_population_cooldown_900s_on_success_and_60s_on_ret55():
    now = [0.0]
    server = FakeServer({"OPT.ashx?id=4": [{"ret": 0}, {"ret": 55}, {"ret": 0}]})
    client = GatewayClient(57, server, sleep=lambda s: None)
    prov = ArmyProvisioner(client, sleep_fn=lambda s: None, clock_fn=lambda: now[0])

    # Lần 1 thành công (ret=0) -> khóa 900s
    assert prov.comfort_population(15230, ltype=4, respect_cooldown=True) == (True, 0)
    assert len(server.calls) == 1

    # Trước 900s -> không gửi request lên server
    now[0] = 899.0
    assert prov.comfort_population(15230, ltype=4, respect_cooldown=True) == (False, 55)
    assert len(server.calls) == 1

    # Đúng 900s -> gửi lại; giả sử trả ret=55 -> khóa 60s
    now[0] = 900.0
    assert prov.comfort_population(15230, ltype=4, respect_cooldown=True) == (False, 55)
    assert len(server.calls) == 2

    now[0] = 959.0
    assert prov.comfort_population(15230, ltype=4, respect_cooldown=True) == (False, 55)
    assert len(server.calls) == 2

    now[0] = 960.0
    assert prov.comfort_population(15230, ltype=4, respect_cooldown=True) == (True, 0)
    assert len(server.calls) == 3


def test_adjust_troops_partial_fill_after_comfort_cooldown_and_multi_general_sequential():
    # 3 tướng mỗi tướng thiếu 2000 Bộ; kho có 500 tân binh; Tăng Nhân Khẩu đang hồi (ret=55); dân rảnh = 2500
    state = {"recruits": 500, "idle_pop": 2500, "assigned": {1: 0, 2: 0, 3: 0}}

    class StatefulServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            ep = url.split("/GateWay/")[1]
            self.calls.append((ep, dict(data or {})))
            if ep == "Common.ashx?id=27":
                resp = {"ret": 0, "list": [[15230, "NB", state["recruits"]]]}
            elif ep == "City.ashx?id=6":
                resp = {"ret": 0, "population": [10000, 10000, 2000, 0, state["idle_pop"]]}
            elif ep == "OPT.ashx?id=4":
                resp = {"ret": 55}
            elif ep == "OPT.ashx?id=41":
                amt = int(data["lAmount"])
                if amt <= state["idle_pop"]:
                    state["idle_pop"] -= amt
                    state["recruits"] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 34}
            elif ep == "OPT.ashx?id=6":
                gid = int(data["lGeneralID"])
                amt = int(data["lAmount"])
                if amt <= state["recruits"]:
                    state["recruits"] -= amt
                    state["assigned"][gid] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 53}
            else:
                resp = {"ret": 0}

            class R:
                status_code = 200

                def json(self_inner):
                    return resp

            return R()

    srv = StatefulServer()
    prov = ArmyProvisioner(GatewayClient(57, srv, sleep=lambda s: None), sleep_fn=lambda s: None)
    comfort_attempted = set()
    exhausted = set()
    target = TargetArmy(infantry=2000)

    r1 = prov.adjust_troops(15230, 1, Army(0, 0, 0), target, comfort_attempted=comfort_attempted, exhausted_cities=exhausted)
    r2 = prov.adjust_troops(15230, 2, Army(0, 0, 0), target, comfort_attempted=comfort_attempted, exhausted_cities=exhausted)
    r3 = prov.adjust_troops(15230, 3, Army(0, 0, 0), target, comfort_attempted=comfort_attempted, exhausted_cities=exhausted)

    # Tướng 1 nhận đủ 2000 (500 kho + 1500 mua), Tướng 2 nhận phần còn lại 1000 và báo thiếu 1000, Tướng 3 bỏ qua vì thành đã cạn dân
    assert r1 == [(1, 2000, True, 0)]
    assert r2 == [(1, 1000, True, 0), (1, 1000, False, 34)]
    assert r3 == [(1, 2000, False, 34)]
    assert state["assigned"] == {1: 2000, 2: 1000, 3: 0}
    assert state["idle_pop"] == 0
    assert state["recruits"] == 0
    assert sum(1 for ep, _ in srv.calls if ep == "OPT.ashx?id=4") == 1
    # Tướng 3 không spam OPT.ashx?id=6 hay OPT.ashx?id=41
    assert not any(ep == "OPT.ashx?id=6" and d["lGeneralID"] == "3" for ep, d in srv.calls)
    assert has_population_shortage(r2) is True
    assert has_population_shortage(r1) is False


def test_adjust_troops_partial_fill_after_comfort_success_still_insufficient():
    responses = {
        "Common.ashx?id=27": {"ret": 0, "list": [[15230, "NB", 0]]},
        "OPT.ashx?id=4": {"ret": 0},
        "City.ashx?id=6": {"ret": 0, "population": [5000, 5000, 1000, 0, 1200]},
        # Thử 3000 (ret=34) -> Tăng Nhân Khẩu -> thử lại 3000 (vẫn ret=34) -> mua 1200 (ret=0)
        "OPT.ashx?id=41": [{"ret": 34}, {"ret": 34}, {"ret": 0}],
        # Thử biên chế 3000 (ret=53) -> biên chế 1200 (ret=0)
        "OPT.ashx?id=6": [{"ret": 53}, {"ret": 0}],
    }
    prov, srv = make_provisioner(responses)
    logs = []
    res = prov.adjust_troops(15230, 101, Army(0, 0, 0), TargetArmy(infantry=3000), on_log=logs.append)
    assert res == [(1, 1200, True, 0), (1, 1800, False, 34)]
    opt41 = [d["lAmount"] for ep, d in srv.calls if ep == "OPT.ashx?id=41"]
    assert opt41 == ["3000", "3000", "1200"]
    opt6 = [d["lAmount"] for ep, d in srv.calls if ep == "OPT.ashx?id=6"]
    assert opt6 == ["3000", "1200"]
    assert any("Biên chế từng phần" in m for m in logs)


def test_adjust_troops_anti_micro_drip_guard_while_waiting_but_finishes_small_tail():
    now = [0.0]
    state = {"recruits": 0, "idle_pop": 0}

    class DripServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            ep = url.split("/GateWay/")[1]
            self.calls.append((ep, dict(data or {})))
            if ep == "Common.ashx?id=27":
                resp = {"ret": 0, "list": [[15230, "NB", state["recruits"]]]}
            elif ep == "City.ashx?id=6":
                resp = {"ret": 0, "population": [5000, 5000, 1000, 0, state["idle_pop"]]}
            elif ep == "OPT.ashx?id=4":
                resp = {"ret": 55}
            elif ep == "OPT.ashx?id=41":
                amt = int(data["lAmount"])
                if amt <= state["idle_pop"]:
                    state["idle_pop"] -= amt
                    state["recruits"] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 34}
            elif ep == "OPT.ashx?id=6":
                amt = int(data["lAmount"])
                if amt <= state["recruits"]:
                    state["recruits"] -= amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 53}
            else:
                resp = {"ret": 0}

            class R:
                status_code = 200

                def json(self_inner):
                    return resp

            return R()

    srv = DripServer()
    prov = ArmyProvisioner(GatewayClient(57, srv, sleep=lambda s: None), sleep_fn=lambda s: None, clock_fn=lambda: now[0])

    # Lượt 1: cạn dân -> đánh dấu đang chờ dân và khóa comfort 60s
    r1 = prov.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(infantry=1000))
    assert r1 == [(1, 1000, False, 34)]

    # Lượt 2 (10s sau): dân tự tăng nhỏ giọt 15 (< 50) -> bỏ qua không mua/biên chế lắt nhắt
    now[0] = 10.0
    state["idle_pop"] = 15
    srv.calls.clear()
    r2 = prov.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(infantry=1000))
    assert r2 == [(1, 1000, False, 34)]
    assert not any(ep == "OPT.ashx?id=41" for ep, _ in srv.calls)

    # Lượt 3: chỉ còn thiếu 30 để đạt 100% và dân = 30 -> vẫn mua & biên chế dứt điểm!
    now[0] = 20.0
    state["idle_pop"] = 30
    srv.calls.clear()
    r3 = prov.adjust_troops(15230, 1, Army(970, 0, 0), TargetArmy(infantry=1000))
    assert r3 == [(1, 30, True, 0)]
    assert has_population_shortage(r3) is False


def test_adjust_troops_non_shortage_error_not_flagged_as_population_shortage():
    prov42, _ = make_provisioner({"OPT.ashx?id=6": {"ret": 42}})
    r42 = prov42.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(infantry=500))
    assert r42 == [(1, 500, False, 42)]
    assert has_population_shortage(r42) is False

    prov43, _ = make_provisioner({"OPT.ashx?id=6": {"ret": 43}})
    r43 = prov43.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(infantry=500))
    assert r43 == [(1, 500, False, 43)]
    assert has_population_shortage(r43) is False


def test_adjust_troops_partial_assign_preserves_non_population_buy_error_32_33():
    responses = {
        "Common.ashx?id=27": {"ret": 0, "list": [[15230, "NB", 300]]},
        "OPT.ashx?id=41": {"ret": 32},
        "OPT.ashx?id=6": [{"ret": 53}, {"ret": 0}],
    }
    prov, _ = make_provisioner(responses)
    exhausted = set()
    res = prov.adjust_troops(
        15230,
        1,
        Army(0, 0, 0),
        TargetArmy(infantry=1000),
        exhausted_cities=exhausted,
    )
    assert res == [(1, 300, True, 0), (1, 700, False, 32)]
    assert has_population_shortage(res) is False
    assert not prov._waiting_population.get(15230, False)
    assert 15230 not in exhausted


def test_adjust_troops_small_branch_during_waiting_does_not_clear_guard_for_next_branch():
    now = [0.0]
    state = {"recruits": 0, "idle_pop": 0, "assigned": {1: 0, 2: 0}}

    class MultiBranchServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            ep = url.split("/GateWay/")[1]
            self.calls.append((ep, dict(data or {})))
            if ep == "Common.ashx?id=27":
                resp = {"ret": 0, "list": [[15230, "NB", state["recruits"]]]}
            elif ep == "City.ashx?id=6":
                resp = {"ret": 0, "population": [5000, 5000, 1000, 0, state["idle_pop"]]}
            elif ep == "OPT.ashx?id=4":
                resp = {"ret": 55}
            elif ep == "OPT.ashx?id=41":
                amt = int(data["lAmount"])
                if amt <= state["idle_pop"]:
                    state["idle_pop"] -= amt
                    state["recruits"] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 34}
            elif ep == "OPT.ashx?id=6":
                amt = int(data["lAmount"])
                stype = int(data["lSoldierType"])
                if amt <= state["recruits"]:
                    state["recruits"] -= amt
                    state["assigned"][stype] = state["assigned"].get(stype, 0) + amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 53}
            else:
                resp = {"ret": 0}

            class R:
                status_code = 200

                def json(self_inner):
                    return resp

            return R()

    srv = MultiBranchServer()
    prov = ArmyProvisioner(GatewayClient(57, srv, sleep=lambda s: None), sleep_fn=lambda s: None, clock_fn=lambda: now[0])

    # Lượt 1: đánh dấu đang chờ dân & khóa comfort 60s
    r1 = prov.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(cavalry=5000))
    assert r1 == [(2, 5000, False, 34)]

    # Lượt 2 (10s sau): idle_pop=25, Bộ thiếu 20 (<50) và Kỵ thiếu 5000
    # Bộ mua 20 thành công, còn dư 5 dân nhàn rỗi KHÔNG được chiêu mộ nhỏ giọt cho Kỵ
    now[0] = 10.0
    state["idle_pop"] = 25
    res = prov.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(infantry=20, cavalry=5000))
    assert res == [(1, 20, True, 0), (2, 5000, False, 34)]
    assert state["idle_pop"] == 5
    assert state["assigned"] == {1: 20, 2: 0}


def test_adjust_troops_micro_drip_guard_does_not_block_next_general_small_tail():
    now = [0.0]
    state = {"recruits": 0, "idle_pop": 0, "assigned": {1: 0, 2: 0}}

    class SmallTailServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            ep = url.split("/GateWay/")[1]
            self.calls.append((ep, dict(data or {})))
            if ep == "Common.ashx?id=27":
                resp = {"ret": 0, "list": [[15230, "NB", state["recruits"]]]}
            elif ep == "City.ashx?id=6":
                resp = {"ret": 0, "population": [5000, 5000, 1000, 0, state["idle_pop"]]}
            elif ep == "OPT.ashx?id=4":
                resp = {"ret": 55}
            elif ep == "OPT.ashx?id=41":
                resp = {"ret": 34}
            elif ep == "OPT.ashx?id=6":
                amt = int(data["lAmount"])
                gid = int(data["lGeneralID"])
                if amt <= state["recruits"]:
                    state["recruits"] -= amt
                    state["assigned"][gid] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 53}
            else:
                resp = {"ret": 0}

            class R:
                status_code = 200

                def json(self_inner):
                    return resp

            return R()

    srv = SmallTailServer()
    prov = ArmyProvisioner(GatewayClient(57, srv, sleep=lambda s: None), sleep_fn=lambda s: None, clock_fn=lambda: now[0])
    prov.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(infantry=5000))

    now[0] = 10.0
    state["recruits"] = 30
    exhausted = set()
    r1 = prov.adjust_troops(15230, 1, Army(0, 0, 0), TargetArmy(infantry=5000), exhausted_cities=exhausted)
    r2 = prov.adjust_troops(15230, 2, Army(0, 0, 0), TargetArmy(infantry=20), exhausted_cities=exhausted)
    assert r1 == [(1, 5000, False, 34)]
    assert r2 == [(1, 20, True, 0)]
    assert state["recruits"] == 10
    assert state["assigned"] == {1: 0, 2: 20}


def test_provision_camp_generals_with_parent_city_respects_apply_min_batch_guard_false():
    now = [0.0]
    state = {"recruits": 0, "idle_pop": 20, "assigned": 0}

    class CampManualServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            ep = url.split("/GateWay/")[1]
            self.calls.append((ep, dict(data or {})))
            if ep == "Common.ashx?id=27":
                resp = {"ret": 0, "list": [[15230, "NB", state["recruits"]]]}
            elif ep == "City.ashx?id=6":
                resp = {"ret": 0, "population": [5000, 5000, 1000, 0, state["idle_pop"]]}
            elif ep == "OPT.ashx?id=41":
                amt = int(data["lAmount"])
                if amt <= state["idle_pop"]:
                    state["idle_pop"] -= amt
                    state["recruits"] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 34}
            elif ep == "OPT.ashx?id=6":
                amt = int(data["lAmount"])
                if amt <= state["recruits"]:
                    state["recruits"] -= amt
                    state["assigned"] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 53}
            else:
                resp = {"ret": 0}

            class R:
                status_code = 200

                def json(self_inner):
                    return resp

            return R()

    srv = CampManualServer()
    prov = ArmyProvisioner(GatewayClient(57, srv, sleep=lambda s: None), sleep_fn=lambda s: None, clock_fn=lambda: now[0])
    prov._waiting_population[15230] = True
    prov._comfort_next_allowed[15230] = now[0] + 500.0

    prov.provision_camp_generals_with_parent_city(
        camp_id=-101,
        parent_city_id=15230,
        general_ids=[417506],
        target_army=TargetArmy(infantry=1000),
        current_armies={417506: Army(0, 0, 0)},
        apply_min_batch_guard=False,
    )
    assert state["assigned"] == 20


def test_adjust_troops_partial_by_equipment_on_ret42_single_and_double_slot():
    # Case A: Ngựa 1 ô (406), kho có 27006逾辉马, diff=43373 -> OPT.ashx?id=6 lần đầu ret=42 -> biên chế từng phần 27006
    c27_a = {
        "ret": 0,
        "list": [[21936, "ThienCo", 50000, [[8025897, "讨逆盔甲"]], [[27006, "逾辉马"]]]],
    }
    c12_a = {
        "ret": 0,
        "cavalry_equip": [27627, 406, "逾辉马", 0, "", 306, "讨逆盔甲"],
    }
    prov_a, srv_a = make_provisioner(
        {
            "Common.ashx?id=27": c27_a,
            "Common.ashx?id=12": c12_a,
            "OPT.ashx?id=6": [{"ret": 42}, {"ret": 0}],
        }
    )
    res_a = prov_a.adjust_troops(21936, 106412, Army(0, 27627, 0), TargetArmy(cavalry=71000))
    assert res_a == [(2, 27006, True, 0), (2, 16367, False, 42)]
    assert has_population_shortage(res_a) is False
    assert [d["lAmount"] for ep, d in srv_a.calls if ep == "OPT.ashx?id=6"] == ["43373", "27006"]

    # Case B: Ngựa gắn cả 2 ô (406, 406, 306) như thực tế ThienCo -> 27006 vẫn ret=42 -> lùi xuống 13503 thành công
    c12_b = {
        "ret": 0,
        "cavalry_equip": [27627, 406, "逾辉马", 406, "逾辉马", 306, "讨逆盔甲"],
    }
    prov_b, srv_b = make_provisioner(
        {
            "Common.ashx?id=27": c27_a,
            "Common.ashx?id=12": c12_b,
            "OPT.ashx?id=6": [{"ret": 42}, {"ret": 42}, {"ret": 0}],
        }
    )
    res_b = prov_b.adjust_troops(21936, 106412, Army(0, 27627, 0), TargetArmy(cavalry=71000))
    assert res_b == [(2, 13503, True, 0), (2, 29870, False, 42)]
    assert [d["lAmount"] for ep, d in srv_b.calls if ep == "OPT.ashx?id=6"] == ["43373", "27006", "13503"]

    # Case C: Gặp ret=42 khi thử đủ diff, hạ xuống mức quân giới 13503 lại thiếu tân binh (ret=53) -> tự chiêu mộ từ dân nhàn rỗi và biên chế 13503
    state_c = {"recruits": 5000, "idle_pop": 20000, "assigned": 0}

    class EquipAndPopServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            ep = url.split("/GateWay/")[1]
            self.calls.append((ep, dict(data or {})))
            if ep == "Common.ashx?id=27":
                resp = {"ret": 0, "list": [[21936, "ThienCo", state_c["recruits"], [[8025897, "讨逆盔甲"]], [[27006, "逾辉马"]]]]}
            elif ep == "Common.ashx?id=12":
                resp = c12_a
            elif ep == "City.ashx?id=6":
                resp = {"ret": 0, "population": [100000, 100000, 1000, 0, state_c["idle_pop"]]}
            elif ep == "OPT.ashx?id=41":
                amt = int(data["lAmount"])
                if amt <= state_c["idle_pop"]:
                    state_c["idle_pop"] -= amt
                    state_c["recruits"] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 34}
            elif ep == "OPT.ashx?id=6":
                amt = int(data["lAmount"])
                if amt > 27006:
                    resp = {"ret": 42}
                elif amt <= state_c["recruits"]:
                    state_c["recruits"] -= amt
                    state_c["assigned"] += amt
                    resp = {"ret": 0}
                else:
                    resp = {"ret": 53}
            else:
                resp = {"ret": 0}

            class R:
                status_code = 200

                def json(self_inner):
                    return resp

            return R()

    srv_c = EquipAndPopServer()
    prov_c = ArmyProvisioner(GatewayClient(53, srv_c, sleep=lambda s: None), sleep_fn=lambda s: None)
    res_c = prov_c.adjust_troops(21936, 106412, Army(0, 27627, 0), TargetArmy(cavalry=71000))
    assert res_c == [(2, 25000, True, 0), (2, 18373, False, 34)]
    assert state_c["assigned"] == 25000
    assert state_c["recruits"] == 0
    assert state_c["idle_pop"] == 0




