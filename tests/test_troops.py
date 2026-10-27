import pytest
from unittest.mock import MagicMock

from linhvuong.gateway import GatewayClient
from linhvuong.roster import Army
from linhvuong.troops import ArmyProvisioner, TargetArmy


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

