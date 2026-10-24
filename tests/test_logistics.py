import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.tasks.logistics import ArmyTransferOrder, LogisticsTask


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

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1]
        self.calls.append((key, dict(data or {})))
        handler = self.handlers.get(key, {"ret": 0})
        if callable(handler):
            return Resp(handler())
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)


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
            "City.ashx?id=6": {"ret": 0, "data": {"morale": 75, "anger": 2}},
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

