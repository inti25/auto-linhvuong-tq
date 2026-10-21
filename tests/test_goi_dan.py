import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import CaptchaRequired, TaskContext
from linhvuong.tasks.goi_dan import VONG_LINH, GoiDan


class Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class FakeServer:
    def __init__(self, map_views=None, handlers=None):
        self.map_views = map_views or {}
        self.handlers = handlers or {}
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1]
        self.calls.append((key, dict(data or {})))
        if key == "Map.ashx?id=6":
            return Resp(self.map_views.get(int(data["mid"]), {"npc_tent": []}))
        handler = self.handlers.get(key, {"ret": 0})
        if callable(handler):
            return Resp(handler())
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)


def ctx_for(server, locks=None):
    gw = GatewayClient(53, server, sleep=lambda s: None)
    locks = locks or TargetLocks()
    alerts = []
    scanner = Scanner(gw, locks, delay=0.0, sleep=lambda s: None)
    return TaskContext(gw, scanner, locks, notify=alerts.append), alerts


def man(x, y, tid, mtype):
    return [tid, mtype, mid_from_coords(x, y)]


def test_goi_dan_vong_linh_uses_item_268():
    mid = mid_from_coords(2, 2)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(2, 2, 888, VONG_LINH)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(2, 2), radius=5, mode="vong_linh", city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    # Kiểm tra các API đã được gọi
    api_names = [k for k, _ in server.calls if k != "Map.ashx?id=6"]
    assert "City.ashx?id=50" in api_names
    assert "OPT.ashx?id=69" in api_names
    assert "OPT.ashx?id=53" in api_names

    # Kiểm tra payload gọi Vong Linh (type 33, param1 268)
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "33"
    assert call_69["param1"] == "268"


def test_goi_dan_thuong_calculates_mid_and_uses_type_63():
    mid = mid_from_coords(5, 5)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(5, 5, 999, 10)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(5, 5), radius=5, mode="dan", target_type=10, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    # Kiểm tra payload gọi dân thường (type 63, param1 target_type, param2 mid)
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "63"
    assert call_69["param1"] == "10"
    assert call_69["param2"] == str(mid)


def test_goi_dan_auto_recover_triggers_heal_and_refill():
    mid = mid_from_coords(1, 1)
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(1, 1, 777, VONG_LINH)]}},
        handlers={
            "OPT.ashx?id=53": {"ret": 0},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[15, 16],
        origin=(1, 1),
        radius=5,
        city_id=123,
        auto_recover=True,
        refill_amount=500,
        soldier_type=2,
    )
    out = task.run_once()
    assert out == "attacked"

    # Kiểm tra gọi trị thương (id=31) cho 2 tướng
    heal_calls = [d for k, d in server.calls if k == "OPT.ashx?id=31"]
    assert len(heal_calls) == 2
    assert {c["lGeneralID"] for c in heal_calls} == {"15", "16"}

    # Kiểm tra gọi bổ sung tân binh (id=6)
    refill_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(refill_calls) == 2
    assert refill_calls[0]["lAmount"] == "500"
    assert refill_calls[0]["lSoldierType"] == "2"


def test_goi_dan_stops_on_captcha_at_call():
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 110},
        }
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(0, 0), radius=5, city_id=123)
    with pytest.raises(CaptchaRequired):
        task.run_once()
