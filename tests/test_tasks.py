import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import LockReason, TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import CaptchaRequired, TaskContext
from linhvuong.tasks.binh_man import BinhMan
from linhvuong.tasks.goi_dan import GoiDan
from linhvuong.tasks.thao_phat import ThaoPhat


class Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class FakeServer:
    """Giả lập Gateway: định tuyến theo endpoint?id và ghi lại các lời gọi."""

    def __init__(self, map_views=None, handlers=None):
        self.map_views = map_views or {}
        self.handlers = handlers or {}  # "OPT.ashx?id=53" -> list/callable
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1]
        self.calls.append((key, dict(data)))
        if key == "Map.ashx?id=6":
            return Resp(self.map_views.get(int(data["mid"]), {"npc_tent": []}))
        handler = self.handlers.get(key, {"ret": 0})
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)

    def keys(self):
        return [k for k, _ in self.calls if k != "Map.ashx?id=6"]


def ctx_for(server, locks=None):
    gw = GatewayClient(53, server, sleep=lambda s: None)
    locks = locks or TargetLocks()
    alerts = []
    scanner = Scanner(gw, locks, delay=0.0, sleep=lambda s: None)
    return TaskContext(gw, scanner, locks, notify=alerts.append), alerts


def man(x, y, tid, mtype):
    return [tid, mtype, mid_from_coords(x, y)]


def test_binh_man_attacks_nearest_man_with_generals():
    server = FakeServer({mid_from_coords(0, 0): {"npc_tent": [man(1, 1, 55, 7)]}})
    ctx, _ = ctx_for(server)
    out = BinhMan(ctx, generals=[11, 12], origin=(0, 0), radius=10, man_types=[7]).run_once()
    assert out == "attacked"
    key, data = server.calls[-1]
    assert key == "OPT.ashx?id=53"
    assert data["target_id"] == "55" and data["generals"] == "11,12"


def test_binh_man_reports_no_target_without_attacking():
    server = FakeServer()
    ctx, _ = ctx_for(server)
    out = BinhMan(ctx, generals=[1], origin=(0, 0), radius=5, man_types=[7]).run_once()
    assert out == "no_target"
    assert server.keys() == []


def test_ret_230_locks_target_as_taken_by_other():
    locks = TargetLocks()
    server = FakeServer(
        {mid_from_coords(0, 0): {"npc_tent": [man(1, 0, 77, 7)]}},
        {"OPT.ashx?id=53": {"ret": 230}},
    )
    ctx, _ = ctx_for(server, locks)
    out = BinhMan(ctx, generals=[1], origin=(0, 0), radius=5, man_types=[7]).run_once()
    assert out == "taken"
    assert locks.is_locked(77)


def test_binh_man_stops_and_alerts_on_captcha():
    server = FakeServer(
        {mid_from_coords(0, 0): {"npc_tent": [man(1, 0, 77, 7)]}},
        {"OPT.ashx?id=53": {"ret": 73}},
    )
    ctx, alerts = ctx_for(server)
    with pytest.raises(CaptchaRequired):
        BinhMan(ctx, generals=[1], origin=(0, 0), radius=5, man_types=[7]).run_once()
    assert alerts and "captcha" in alerts[0].lower()
    assert "Common.ashx?id=102" not in server.keys()  # không tự gửi đáp án


def test_binh_man_needs_return_below_threshold():
    ctx, _ = ctx_for(FakeServer())
    task = BinhMan(ctx, generals=[1], origin=(0, 0), radius=5, man_types=[7], return_threshold=30)
    assert task.needs_return(remaining_percent=29)
    assert not task.needs_return(remaining_percent=30)


def test_goi_dan_attacks_existing_vong_linh_without_calling():
    server = FakeServer({mid_from_coords(0, 0): {"npc_tent": [man(2, 0, 301001, 301)]}})
    ctx, _ = ctx_for(server)
    out = GoiDan(ctx, generals=[3], origin=(0, 0), radius=5).run_once()
    assert out == "attacked"
    assert "City.ashx?id=50" not in server.keys()


def test_goi_dan_calls_then_attacks_new_target():
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {
                "ret": 0,
                "new_target_id": 900,
                "new_target_mid": mid_from_coords(4, 4),
                "new_target_type": 301,
            }
        }
    )
    ctx, _ = ctx_for(server)
    out = GoiDan(ctx, generals=[3], origin=(0, 0), radius=5).run_once()
    assert out == "called_and_attacked"
    assert server.keys() == ["City.ashx?id=50", "OPT.ashx?id=53"]
    assert server.calls[-1][1]["target_id"] == "900"
    assert ctx.locks.is_locked(900)


def test_goi_dan_reports_call_failure_without_attacking():
    server = FakeServer(handlers={"City.ashx?id=50": {"ret": 39}})
    ctx, _ = ctx_for(server)
    out = GoiDan(ctx, generals=[3], origin=(0, 0), radius=5).run_once()
    assert out == "call_failed:39"
    assert server.keys() == ["City.ashx?id=50"]


def test_thao_phat_starts_campaign_and_attacks():
    server = FakeServer({mid_from_coords(0, 0): {"npc_tent": [man(1, 0, 5, 9)]}})
    ctx, _ = ctx_for(server)
    out = ThaoPhat(ctx, generals=[8], origin=(0, 0), radius=5, man_types=[9]).run_once()
    assert out == "attacked"
    assert server.keys() == ["OPT.ashx?id=62", "OPT.ashx?id=53"]
