import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.roster import City, General, Roster
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.tasks.logistics import ArmyTransferOrder, ArmyWeaponTransferTask, LogisticsTask


class Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class FakeServer:
    def __init__(self, handlers=None):
        self.handlers = handlers or {}
        self.calls = []
        self.cookies = {"uid": "95"}

    def _dispatch(self, key, params_or_data):
        self.calls.append((key, dict(params_or_data or {})))
        handler = self.handlers.get(key, {"ret": 0})
        if callable(handler):
            return Resp(handler())
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)

    def get(self, url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        return self._dispatch(path, params)

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        return self._dispatch(key, data)


def test_logistics_transfers_army_when_sufficient():
    server = FakeServer(
        handlers={
            "OPT.ashx?id=63": {"ret": 0},
            "Common.ashx?id=16": {
                "ret": 0,
                "list": [
                    {"gid": 1, "count": 5000},  # có 5000 bộ binh
                ],
            },
            "OPT.ashx?id=52": {"ret": 0},  # chuyển quân thành công
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    orders = [ArmyTransferOrder(from_city_id=101, to_city_id=102, army_id=1, amount=2000)]
    task = LogisticsTask(gw, transfer_orders=orders, auto_comfort=False, auto_daily_reward=True)
    out = task.run_once()
    assert out == "transferred:1"

    # Kiểm tra gọi OPT.ashx?id=52
    transfer_calls = [d for k, d in server.calls if k == "OPT.ashx?id=52"]
    assert len(transfer_calls) == 1
    call = transfer_calls[0]
    assert call["dest"] == "102"
    assert call["tid"] == "101"
    assert call["gid"] == "1"
    assert call["gamount"] == "2000"


def test_logistics_skips_when_insufficient_army():
    server = FakeServer(
        handlers={
            "Common.ashx?id=16": {
                "ret": 0,
                "list": [{"gid": 1, "count": 500}],  # chỉ có 500
            },
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    orders = [ArmyTransferOrder(from_city_id=101, to_city_id=102, army_id=1, amount=2000)]
    task = LogisticsTask(gw, transfer_orders=orders, auto_comfort=False, auto_daily_reward=False)
    out = task.run_once()
    assert out == "transferred:0"
    assert "OPT.ashx?id=52" not in [k for k, _ in server.calls]


def test_logistics_auto_comfort_for_monitored_cities():
    server = FakeServer(
        handlers={
            "/api/city/info": {"ret": 0, "data": {"m_lmorale_current": 75, "m_lmorale_complaint": 2}},
            "OPT.ashx?id=4": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = LogisticsTask(gw, monitored_city_ids=[101, 102], auto_comfort=True, auto_daily_reward=False)
    out = task.run_once()
    assert out == "logistics_idle"

    # Kiểm tra An Dân cho cả 2 thành
    comfort_calls = [d for k, d in server.calls if k == "OPT.ashx?id=4"]
    assert len(comfort_calls) == 2
    assert {c["tid"] for c in comfort_calls} == {"101", "102"}


def test_logistics_stops_on_captcha():
    server = FakeServer(
        handlers={
            "OPT.ashx?id=63": {"ret": 110},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = LogisticsTask(gw, auto_daily_reward=True)
    with pytest.raises(CaptchaRequired):
        task.run_once()


def test_claim_daily_reward_ret_86_and_notifications():
    # Kiểm tra mã ret=86 (đã nhận thưởng trong ngày) được coi là thành công và có thông báo log
    notifications = []
    server = FakeServer(
        handlers={
            "OPT.ashx?id=63": {"ret": 86},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    task = LogisticsTask(gw, notify=lambda m: notifications.append(m))
    
    result = task.claim_daily_reward()
    assert result is True, "Mã ret=86 (đã nhận trong ngày) phải trả về True"
    assert any("đã nhận thưởng" in m.lower() for m in notifications), "Phải có thông báo đã nhận thưởng"


def test_logistics_parses_s58_four_element_weapon_stock_and_stops_on_shortage():
    server = FakeServer(
        handlers={
            "Common.ashx?id=16": {
                "ret": 0,
                "list": [
                    [351, "龙飞战甲", 4, 14294],
                    [108, "百胜长刀", 1, 521659],
                    [452, "龙飞铁骑", 8, 50],
                ],
            },
            "OPT.ashx?id=52": {"ret": 0},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    task = LogisticsTask(
        gw,
        transfer_orders=[
            ArmyTransferOrder(from_city_id=10129, to_city_id=10254, army_id=108, amount=1000),
            ArmyTransferOrder(from_city_id=10129, to_city_id=10254, army_id=452, amount=500),
            ArmyTransferOrder(from_city_id=10129, to_city_id=10254, army_id=351, amount=100),
        ],
        auto_comfort=False,
        auto_daily_reward=False,
    )
    stocks = task.get_city_weapon_stocks(10129)
    assert {s["id"]: s["count"] for s in stocks} == {351: 14294, 108: 521659, 452: 50}

    out = task.run_once()
    # Lệnh 1 (108) chuyển được, lệnh 2 (452: 50 < 500) dừng ngay không chạy lệnh 3 (351)
    assert out == "transferred:1"
    transfer_calls = [d for k, d in server.calls if k == "OPT.ashx?id=52"]
    assert len(transfer_calls) == 1
    assert transfer_calls[0]["gid"] == "108"
    assert transfer_calls[0]["gamount"] == "1000"


def test_logistics_market_rejects_camp_and_same_city():
    server = FakeServer()
    gw = GatewayClient(58, server, sleep=lambda s: None)
    task = LogisticsTask(gw, auto_comfort=False, auto_daily_reward=False)
    assert task.transfer_army(ArmyTransferOrder(10129, -2001, 108, 100)) is False
    assert task.transfer_army(ArmyTransferOrder(10129, 10129, 108, 100)) is False
    assert "OPT.ashx?id=52" not in [k for k, _ in server.calls]


def test_army_weapon_transfer_single_trip_loads_and_unloads_slots_2_3():
    gen_state = {
        "city": 101,
        "cav": [10000, 452, "龙飞铁骑", 452, "龙飞铁骑", 452, "龙飞铁骑"],
    }

    class ArmyServer(FakeServer):
        def _dispatch(self, key, params_or_data):
            self.calls.append((key, dict(params_or_data or {})))
            if key == "Common.ashx?id=16":
                return Resp({"ret": 0, "list": [[108, "百胜长刀", 1, 500000]]})
            if key == "Common.ashx?id=12":
                return Resp({
                    "ret": 0,
                    "infantry_equip": [0, 0, "", 0, "", 0, ""],
                    "cavalry_equip": list(gen_state["cav"]),
                    "bowman_equip": [0, 0, "", 0, "", 0, ""],
                    "mangonel": [0, "", 0],
                    "owner_city_id": gen_state["city"],
                })
            if key == "OPT.ashx?id=56":
                gen_state["cav"] = [
                    10000,
                    int(params_or_data["lCavalryEID1"]),
                    "",
                    int(params_or_data["lCavalryEID2"]),
                    "",
                    int(params_or_data["lCavalryEID3"]),
                    "",
                ]
                return Resp({"ret": 0})
            if key == "OPT.ashx?id=50":
                gen_state["city"] = int(params_or_data["lDestID"])
                return Resp({"ret": 0})
            if key == "Common.ashx?id=40":
                return Resp({"ret": 0, "come": [], "goto": [], "battle": []})
            return Resp({"ret": 0})

    server = ArmyServer()
    gw = GatewayClient(58, server, sleep=lambda s: None)
    roster = Roster(
        cities=[City(101, "Thành Nhận"), City(102, "Thành Nguồn")],
        _generals={101: [General(id=6330, name="I_01", role="vo", level=100, morale=100, stamina=100, stamina_max=100)]},
    )
    task = ArmyWeaponTransferTask(gw, notify=lambda _m: None)
    # Chuyển Binh khí 108 từ 102 -> 101 bằng tướng Kỵ binh đang ở 101
    res = task.run(
        from_city_id=102,
        to_city_id=101,
        weapon_id=108,
        general_ids=[6330],
        roster=roster,
        loop=False,
    )
    assert res == "completed:20000"
    opt56 = [d for k, d in server.calls if k == "OPT.ashx?id=56"]
    assert [(int(x["lCavalryEID1"]), int(x["lCavalryEID2"]), int(x["lCavalryEID3"])) for x in opt56] == [
        (452, 0, 0),      # dọn ô 2 & 3 tại 101 trước khi đi
        (452, 108, 108),  # nạp 20,000 mã 108 tại 102
        (452, 0, 0),      # nhả 20,000 mã 108 vào kho 101 khi quay về
    ]
    opt50 = [(int(d["lCityID"]), int(d["lDestID"])) for k, d in server.calls if k == "OPT.ashx?id=50"]
    assert opt50 == [(101, 102), (102, 101)]


def test_army_weapon_transfer_stops_when_source_out_of_stock():
    server = FakeServer(handlers={"Common.ashx?id=16": {"ret": 0, "list": []}})
    gw = GatewayClient(58, server, sleep=lambda s: None)
    roster = Roster(
        cities=[City(101, "A"), City(102, "B")],
        _generals={101: [General(id=1, name="G1", role="vo", level=10, morale=100, stamina=100, stamina_max=100)]},
    )
    task = ArmyWeaponTransferTask(gw, notify=lambda _m: None)
    res = task.run(from_city_id=102, to_city_id=101, weapon_id=406, general_ids=[1], roster=roster, loop=True)
    assert res == "stopped_out_of_stock:0"


def test_army_get_incoming_move_duration_parses_s58_and_legacy_come():
    server = FakeServer(
        handlers={
            "Common.ashx?id=40": {
                "ret": 0,
                "come": [
                    [5, 95, "inti", 10129, "1", 200, 96, [[10698, "TP_03"], [25703, "凌得峰"]], 2000, 2000, 2000, 0, 5410, 10899],
                    [5, 95, "inti", 10129, "1", 200, 96, 42, 0, 0, 0, 0, [[9999, "Legacy"]]],
                ],
                "goto": [],
                "battle": [],
            }
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    task = ArmyWeaponTransferTask(gw, notify=lambda _m: None)
    assert task.get_incoming_move_duration(10254, [10698]) == 5410
    assert task.get_incoming_move_duration(10254, [9999]) == 42
    assert task.get_incoming_move_duration(10254, [11111]) == 0


def test_army_weapon_transfer_skips_empty_slot1_incompatible_carrier():
    server = FakeServer(
        handlers={
            "Common.ashx?id=16": {"ret": 0, "list": [[406, "Du huy ma", 8, 50000]]},
            "Common.ashx?id=12": {
                "ret": 0,
                "infantry_equip": [2000, 0, "", 0, "", 0, ""],
                "cavalry_equip": [0, 0, "", 0, "", 0, ""],
                "bowman_equip": [0, 0, "", 0, "", 0, ""],
                "mangonel": [0, "", 0],
                "owner_city_id": 102,
            },
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    roster = Roster(
        cities=[City(101, "A"), City(102, "B")],
        _generals={102: [General(id=77, name="G_Inf", role="vo", level=10, morale=100, stamina=100, stamina_max=100)]},
    )
    task = ArmyWeaponTransferTask(gw, notify=lambda _m: None)
    res = task.run(from_city_id=102, to_city_id=101, weapon_id=406, general_ids=[77], roster=roster, loop=False)
    assert res == "stopped_no_carriers:0"
    assert "OPT.ashx?id=50" not in [k for k, _ in server.calls]


def test_army_weapon_transfer_returns_source_origin_general_home_after_single_trip():
    gen_state = {
        "city": 102,
        "cav": [2000, 454, "天命宝驹", 454, "天命宝驹", 454, "天命宝驹"],
    }

    class HomeReturnServer(FakeServer):
        def _dispatch(self, key, params_or_data):
            self.calls.append((key, dict(params_or_data or {})))
            if key == "Common.ashx?id=16":
                return Resp({"ret": 0, "list": [[406, "Du huy ma", 8, 50000]]})
            if key == "Common.ashx?id=12":
                return Resp({
                    "ret": 0,
                    "infantry_equip": [0, 0, "", 0, "", 0, ""],
                    "cavalry_equip": list(gen_state["cav"]),
                    "bowman_equip": [0, 0, "", 0, "", 0, ""],
                    "mangonel": [0, "", 0],
                    "owner_city_id": gen_state["city"],
                })
            if key == "OPT.ashx?id=56":
                gen_state["cav"] = [
                    2000,
                    int(params_or_data["lCavalryEID1"]),
                    "",
                    int(params_or_data["lCavalryEID2"]),
                    "",
                    int(params_or_data["lCavalryEID3"]),
                    "",
                ]
                return Resp({"ret": 0})
            if key == "OPT.ashx?id=50":
                gen_state["city"] = int(params_or_data["lDestID"])
                return Resp({"ret": 0})
            if key == "Common.ashx?id=40":
                return Resp({"ret": 0, "come": [], "goto": [], "battle": []})
            return Resp({"ret": 0})

    server = HomeReturnServer()
    gw = GatewayClient(58, server, sleep=lambda s: None)
    roster = Roster(
        cities=[City(101, "Thành Đích"), City(102, "Thành Nguồn")],
        _generals={102: [General(id=10698, name="TP_03", role="vo", level=82, morale=97, stamina=1280, stamina_max=1280)]},
    )
    task = ArmyWeaponTransferTask(gw, notify=lambda _m: None)
    res = task.run(from_city_id=102, to_city_id=101, weapon_id=406, general_ids=[10698], roster=roster, loop=False)
    assert res == "completed:4000"
    opt50 = [(int(d["lCityID"]), int(d["lDestID"])) for k, d in server.calls if k == "OPT.ashx?id=50"]
    assert opt50 == [(102, 101), (101, 102)]
    assert gen_state["city"] == 102



