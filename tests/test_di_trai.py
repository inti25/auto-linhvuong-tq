import threading
import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import CaptchaRequired, TaskContext
from linhvuong.tasks.di_trai import DiTrai, chebyshev_distance


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
            return Resp(handler(dict(data or {})))
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)


def ctx_for(server):
    gw = GatewayClient(53, server, sleep=lambda s: None)
    locks = TargetLocks()
    alerts = []
    scanner = Scanner(gw, locks, delay=0.0, sleep=lambda s: None)
    return TaskContext(gw, scanner, locks, notify=alerts.append), alerts


def test_di_trai_step_towards():
    task = DiTrai(
        ctx=None,
        camp_id=123,
        origin=(0, 0),
        destination=(5, 5),
        max_step=2,
    )
    assert task.step_towards(5, 5, step_limit=2) == (2, 2)
    assert task.step_towards(5, 5, step_limit=1) == (1, 1)
    assert task.step_towards(-3, 0, step_limit=2) == (-2, 0)


def test_di_trai_move_step_success():
    server = FakeServer(handlers={"Common.ashx?id=55": {"ret": 0, "frozen": 20}})
    ctx, _ = ctx_for(server)
    sleeps = []
    task = DiTrai(
        ctx=ctx,
        camp_id=999,
        origin=(10, 10),
        destination=(10, 14),
        sleep_fn=sleeps.append,
    )

    success, frozen, reason = task.move_step(10, 12)
    assert success is True
    assert frozen == 20
    assert reason == "ok"
    assert task.origin == (10, 12)
    assert sleeps == [20]

    call = server.calls[0]
    assert call[0] == "Common.ashx?id=55"
    assert call[1]["lDestX"] == "10"
    assert call[1]["lDestY"] == "12"
    assert call[1]["lTentID"] == "999"


def test_di_trai_advance_to_destination_multi_step():
    # Đi từ (0, 0) đến (4, 4) qua 2 bước: (2, 2) -> (4, 4)
    server = FakeServer(handlers={"Common.ashx?id=55": {"ret": 0, "frozen": 10}})
    ctx, alerts = ctx_for(server)
    steps_recorded = []

    task = DiTrai(
        ctx=ctx,
        camp_id=555,
        origin=(0, 0),
        destination=(4, 4),
        max_step=2,
        sleep_fn=lambda s: None,
        on_step=lambda x, y, f: steps_recorded.append((x, y, f)),
    )

    result = task.advance_to_destination()
    assert result == "arrived"
    assert task.origin == (4, 4)
    assert steps_recorded == [(2, 2, 10), (4, 4, 10)]
    assert len(server.calls) == 2


def test_di_trai_obstacle_handling_lach_vat_can():
    # Đi từ (0, 0) đến (4, 4). Bước nhảy thẳng (2, 2) bị cản ret=39.
    # Lách Vật Cản sẽ thử các ô kề cận, sau đó tiếp tục đi tới đích (4, 4).
    def handler(payload):
        dest_x = int(payload.get("lDestX", 0))
        dest_y = int(payload.get("lDestY", 0))
        if dest_x == 2 and dest_y == 2:
            return {"ret": 39}  # vướng ô (2, 2)
        return {"ret": 0, "frozen": 5}

    server = FakeServer(handlers={"Common.ashx?id=55": handler})
    ctx, alerts = ctx_for(server)
    steps_recorded = []

    task = DiTrai(
        ctx=ctx,
        camp_id=777,
        origin=(0, 0),
        destination=(4, 4),
        max_step=2,
        sleep_fn=lambda s: None,
        on_step=lambda x, y, f: steps_recorded.append((x, y, f)),
    )

    result = task.advance_to_destination()
    assert result == "arrived"
    assert task.origin == (4, 4)
    assert any("Lách Vật Cản" in a for a in alerts)


def test_di_trai_stop_event_cancels_run():
    server = FakeServer(handlers={"Common.ashx?id=55": {"ret": 0, "frozen": 10}})
    ctx, _ = ctx_for(server)
    stop_event = threading.Event()

    task = DiTrai(
        ctx=ctx,
        camp_id=888,
        origin=(0, 0),
        destination=(10, 10),
        max_step=2,
        sleep_fn=lambda s: None,
        stop_event=stop_event,
    )

    stop_event.set()
    result = task.advance_to_destination()
    assert result == "stopped"
    assert len(server.calls) == 0


def test_di_trai_insufficient_resources():
    server = FakeServer(handlers={"Common.ashx?id=55": {"ret": 40}})
    ctx, _ = ctx_for(server)

    task = DiTrai(
        ctx=ctx,
        camp_id=111,
        origin=(0, 0),
        destination=(2, 2),
        sleep_fn=lambda s: None,
    )

    result = task.advance_to_destination()
    assert result == "insufficient_resources"


def test_di_trai_stop_at_distance():
    # Kiểm tra trường hợp dừng khi khoảng cách <= stop_at_distance (dành cho Bình Man tiếp cận quái)
    server = FakeServer(handlers={"Common.ashx?id=55": {"ret": 0, "frozen": 5}})
    ctx, _ = ctx_for(server)

    task = DiTrai(
        ctx=ctx,
        camp_id=222,
        origin=(0, 0),
        destination=(6, 6),
        max_step=2,
        sleep_fn=lambda s: None,
        stop_at_distance=2,
    )

    result = task.advance_to_destination()
    assert result == "arrived"
    # Cự ly Chebyshev tới (6, 6) phải <= 2 ô
    assert chebyshev_distance(task.origin[0], task.origin[1], 6, 6) <= 2
