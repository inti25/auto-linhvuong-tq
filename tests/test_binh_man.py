import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import CaptchaRequired, TaskContext
from linhvuong.tasks.binh_man import BinhMan, chebyshev_distance


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


def test_chebyshev_distance():
    assert chebyshev_distance(0, 0, 2, 2) == 2
    assert chebyshev_distance(0, 0, 3, 1) == 3
    assert chebyshev_distance(5, 5, 2, 2) == 3


def test_binh_man_moves_camp_step_by_step_towards_far_target():
    # Mục tiêu tại (5, 5), Trại xuất phát tại (0, 0)
    # Bán kính 10, max_step 2 ô/bước
    target_mid = mid_from_coords(5, 5)
    sleeps = []
    server = FakeServer(
        map_views={
            mid_from_coords(0, 0): {"npc_tent": [man(5, 5, 100, 7)]},
            target_mid: {"npc_tent": [man(5, 5, 100, 7)]},
        },
        handlers={
            "Common.ashx?id=55": {"ret": 0, "frozen": 15},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[1],
        origin=(0, 0),
        radius=10,
        man_types=[7],
        camp_id=9999,
        max_step=2,
        sleep_fn=sleeps.append,
    )

    out = task.run_once()
    assert out == "attacked"

    # Kiểm tra các lần dời Trại qua Common.ashx?id=55
    move_calls = [d for k, d in server.calls if k == "Common.ashx?id=55"]
    # Từ (0,0) -> (2,2) -> (4,4). Khi tại (4,4), khoảng cách tới (5,5) là 1 ô (<= 2 ô) -> dừng dời và tấn công!
    assert len(move_calls) >= 2
    assert sleeps == [15] * len(move_calls)
    assert task.origin == (4, 4)

    # Đã tấn công mục tiêu
    attack_calls = [d for k, d in server.calls if k == "OPT.ashx?id=53"]
    assert len(attack_calls) == 1
    assert attack_calls[0]["target_id"] == "100"


def test_binh_man_handles_obstacle_and_backoff():
    # Mục tiêu tại (4, 4), Trại tại (0, 0)
    # Bước đầu tới (2, 2) bị ret=39 (vướng), bot tự lùi về bước 1 ô (1, 1)
    target_mid = mid_from_coords(4, 4)
    server = FakeServer(
        map_views={mid_from_coords(0, 0): {"npc_tent": [man(4, 4, 101, 7)]}},
        handlers={
            "Common.ashx?id=55": [
                {"ret": 39},  # bước 2 ô thất bại vì vướng
                {"ret": 0, "frozen": 10},  # lùi về 1 ô thành công!
                {"ret": 0, "frozen": 10},  # bước tiếp
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[1],
        origin=(0, 0),
        radius=10,
        man_types=[7],
        camp_id=8888,
        max_step=2,
        sleep_fn=lambda s: None,
    )
    out = task.run_once()
    assert out == "attacked"


def test_binh_man_retreats_to_parent_city_below_threshold():
    server = FakeServer(
        handlers={
            "OPT.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
        }
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[20, 21],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        camp_id=5555,
        parent_city_id=1001,
        return_threshold=30,
    )

    out = task.run_once(remaining_percent=25.0)
    assert out == "retreated_below_threshold"

    # Kiểm tra điều động về thành mẹ và tái xuất quân
    transit_calls = [d for k, d in server.calls if k == "OPT.ashx?id=50"]
    assert len(transit_calls) == 4  # 2 tướng về thành mẹ + 2 tướng ra lại trại
    # Kiểm tra trị thương và bổ sung lính
    heal_calls = [d for k, d in server.calls if k == "OPT.ashx?id=31"]
    assert len(heal_calls) == 2
