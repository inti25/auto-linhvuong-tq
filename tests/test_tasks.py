import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import LockReason, TargetLocks
from linhvuong.scan import Scanner, Target
from linhvuong.tasks.base import (
    RET_SESSION_EXPIRED,
    CaptchaRequired,
    TaskContext,
    attack,
)
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
    """Giả lập Gateway Server 58: hỗ trợ /api/* (GET/POST) và /GateWay/*."""

    def __init__(self, map_views=None, handlers=None):
        self.map_views = map_views or {}
        self.handlers = handlers or {}
        self.calls = []
        self.cookies = {"uid": "95"}

    def get(self, url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        p = dict(params or {})
        self.calls.append((path, p))
        if path == "/api/map/query":
            return Resp(self.map_views.get(int(p["mid"]), {"npc_tent": []}))
        handler = self.handlers.get(path, {"ret": 0})
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        self.calls.append((key, dict(data or {})))
        handler = self.handlers.get(key, {"ret": 0})
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)

    def keys(self):
        return [k for k, _ in self.calls if k != "/api/map/query"]


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
    # Lần quét 1 (tìm quái có sẵn) -> rỗng; lần quét 2 (sau khi gọi bằng OPT.ashx?id=69) -> thấy 900 ở (4,4)
    scan_calls = [0]

    def map_handler(params):
        scan_calls[0] += 1
        if int(params["mid"]) == mid_from_coords(0, 0) and scan_calls[0] >= 2:
            return {"npc_tent": [man(4, 4, 900, 301)]}
        return {"npc_tent": []}

    server = FakeServer(
        handlers={
            "/api/map/query": map_handler,
            "OPT.ashx?id=69": {"ret": 0},
        },
    )
    # Gắn map_views handler động cho /api/map/query
    orig_get = server.get

    def custom_get(url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        p = dict(params or {})
        server.calls.append((path, p))
        if path == "/api/map/query":
            return Resp(map_handler(p))
        return Resp(server.handlers.get(path, {"ret": 0}))

    server.get = custom_get
    ctx, _ = ctx_for(server)
    out = GoiDan(ctx, generals=[3], origin=(0, 0), radius=5, city_id=10129, sleep_fn=lambda s: None).run_once()
    assert out == "called_and_attacked"
    keys = server.keys()
    assert "/api/city/current" in keys
    assert "OPT.ashx?id=69" in keys
    assert "OPT.ashx?id=53" in keys
    opt53_calls = [d for k, d in server.calls if k == "OPT.ashx?id=53"]
    assert opt53_calls[0]["target_id"] == "900"
    assert ctx.locks.is_locked(900)


def test_goi_dan_reports_call_failure_without_attacking():
    server = FakeServer(handlers={"OPT.ashx?id=69": {"ret": 39}})
    ctx, _ = ctx_for(server)
    out = GoiDan(ctx, generals=[3], origin=(0, 0), radius=5, city_id=10129).run_once()
    assert out == "call_failed:39"
    assert server.keys() == ["/api/city/pageofficial", "/api/city/current", "OPT.ashx?id=69"]


def test_thao_phat_starts_campaign_and_attacks():
    server = FakeServer({mid_from_coords(0, 0): {"npc_tent": [man(1, 0, 5, 9)]}})
    ctx, _ = ctx_for(server)
    out = ThaoPhat(ctx, generals=[8], origin=(0, 0), radius=5, man_types=[9]).run_once()
    assert out == "attacked"
    assert server.keys() == ["OPT.ashx?id=62", "OPT.ashx?id=53"]


def test_attack_network_error_returns_failure():
    gw = GatewayClient(53, session=None)
    gw.call = lambda *args, **kwargs: None
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0)
    ctx = TaskContext(gw, scanner, locks)
    target = Target(x=5, y=5, target_id=10, man_type=7)
    res = attack(ctx, target, [1])
    assert res == "attack_failed:network_error"


def test_attack_session_expired_alerts_and_returns_failure():
    gw = GatewayClient(53, session=None)
    gw.call = lambda *args, **kwargs: {"ret": RET_SESSION_EXPIRED}
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0)
    alerts = []
    ctx = TaskContext(gw, scanner, locks, notify=alerts.append)
    target = Target(x=5, y=5, target_id=10, man_type=7)
    res = attack(ctx, target, [1])
    assert res == f"attack_failed:{RET_SESSION_EXPIRED}"
    assert any("198599" in a for a in alerts)


def test_attack_auto_relogins_and_succeeds_on_session_expired():
    class MockSess:
        def __init__(self):
            self.calls = 0

        def post(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return Resp({"ret": RET_SESSION_EXPIRED})
            return Resp({"ret": 0})

    relogin_called = []
    sess = MockSess()
    gw = GatewayClient(
        53, sess, sleep=lambda s: None, relogin_callback=lambda: relogin_called.append(True) or True
    )
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0)
    ctx = TaskContext(gw, scanner, locks)
    target = Target(x=5, y=5, target_id=10, man_type=7)

    res = attack(ctx, target, [1])
    assert res == "attacked"
    assert len(relogin_called) == 1
    assert sess.calls == 2


def test_attack_empty_generals_returns_error():
    gw = GatewayClient(53, session=None)
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0)
    ctx = TaskContext(gw, scanner, locks)
    target = Target(x=5, y=5, target_id=10, man_type=7)
    assert attack(ctx, target, []) == "attack_failed:no_generals"


def test_attack_splits_more_than_3_generals_into_batches_with_delay():
    calls = []

    def mock_call(endpoint, action_id, payload):
        calls.append((endpoint, action_id, payload))
        return {"ret": 0}

    gw = GatewayClient(53, session=None)
    gw.call = mock_call
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0)
    alerts = []
    ctx = TaskContext(gw, scanner, locks, notify=alerts.append)
    target = Target(x=10, y=20, target_id=555, man_type=7)

    delays = []
    # 5 võ tướng: chia thành 2 đợt (3 tướng và 2 tướng)
    res = attack(
        ctx,
        target,
        generals=[101, 102, 103, 104, 105],
        batch_size=3,
        batch_delay=0.5,
        sleep_fn=delays.append,
    )

    assert res == "attacked"
    assert len(calls) == 2
    # Đợt 1
    assert calls[0][0] == "OPT.ashx"
    assert calls[0][1] == 53
    assert calls[0][2]["generals"] == "101,102,103"
    assert calls[0][2]["target_id"] == "555"
    # Đợt 2
    assert calls[1][0] == "OPT.ashx"
    assert calls[1][1] == 53
    assert calls[1][2]["generals"] == "104,105"
    assert calls[1][2]["target_id"] == "555"

    # Có delay giữa 2 đợt
    assert delays == [0.5]
    # Có thông báo tiến độ từng đợt
    assert any("Đợt 1/2" in a for a in alerts)
    assert any("Đợt 2/2" in a for a in alerts)
    assert any("Hoàn tất xuất kích 2 đợt" in a for a in alerts)


def test_attack_batch_short_circuits_on_error():
    calls = []

    def mock_call(endpoint, action_id, payload):
        calls.append((endpoint, action_id, payload))
        if len(calls) == 1:
            return {"ret": 230}  # RET_TAKEN_BY_OTHER
        return {"ret": 0}

    gw = GatewayClient(53, session=None)
    gw.call = mock_call
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0)
    alerts = []
    ctx = TaskContext(gw, scanner, locks, notify=alerts.append)
    target = Target(x=10, y=20, target_id=555, man_type=7)

    delays = []
    res = attack(
        ctx,
        target,
        generals=[1, 2, 3, 4, 5, 6],
        batch_size=3,
        batch_delay=0.5,
        sleep_fn=delays.append,
    )

    # Đợt 1 thất bại -> ngắt chuỗi ngay, không gọi đợt 2
    assert res == "taken"
    assert len(calls) == 1
    assert delays == []


def test_attack_sends_official_dipan_barracks_parameters():
    """OPT.ashx?id=53 trên server thật dipan.com bắt buộc đủ bộ tham số từ barracks.js (_fightGo),
    nếu thiếu sẽ bị trả về ret=198599.
    """
    calls = []

    def mock_call(endpoint, action_id, payload):
        calls.append((endpoint, action_id, payload))
        return {"ret": 0}

    gw = GatewayClient(53, session=None)
    gw.call = mock_call
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0)
    ctx = TaskContext(gw, scanner, locks, notify=lambda m: None)
    target = Target(x=268, y=251, target_id=1002, man_type=1)

    res = attack(ctx, target, generals=[99057, 99056], origin_id=21936)
    assert res == "attacked"
    assert len(calls) == 1
    payload = calls[0][2]
    assert payload["lDestID"] == str(mid_from_coords(268, 251))
    assert payload["lType"] == "1"
    assert payload["lGeneralID1"] == "99057"
    assert payload["lGeneralID2"] == "99056"
    assert payload["lGeneralID3"] == "0"
    assert payload["lBout"] == "-1"
    assert payload["lTarget1GID"] == "0"
    assert payload["lTarget2GID"] == "0"
    assert payload["lTarget3GID"] == "0"
    assert payload["lPlusFuncID"] == "0"
    assert payload["lPlusDestID"] == "0"
    assert payload["tid"] == "21936"



