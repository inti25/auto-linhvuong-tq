import math

import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import LockReason, TargetLocks
from linhvuong.scan import Scanner


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class FakeGateway:
    """Giả lập Map.ashx?id=6: mỗi mid -> payload; có thể kèm chuỗi status lỗi trước."""

    def __init__(self, views=None, failures=None):
        self.views = views or {}
        self.failures = failures or {}  # mid -> list status codes trả trước
        self.requested = []
        self.sleeps = []

    def post(self, url, data=None, headers=None, timeout=None):
        mid = int(data["mid"])
        self.requested.append(mid)
        queue = self.failures.get(mid)
        if queue:
            return FakeResponse(queue.pop(0))
        return FakeResponse(200, self.views.get(mid, {"npc_tent": []}))


def make(views=None, failures=None, locks=None):
    session = FakeGateway(views, failures)
    client = GatewayClient(53, session, sleep=session.sleeps.append)
    scanner = Scanner(client, locks or TargetLocks(), delay=0.0, sleep=lambda s: None)
    return scanner, session


def npc_at(x, y, target_id, man_type):
    return [target_id, man_type, mid_from_coords(x, y)]


def test_returns_nearest_matching_target():
    near = npc_at(5, 0, 111, 7)
    far = npc_at(25, 0, 222, 7)
    scanner, _ = make(
        {
            mid_from_coords(5, 0): {"npc_tent": [near]},
            mid_from_coords(25, 0): {"npc_tent": [far]},
        }
    )
    t = scanner.find_nearest(0, 0, radius=30, target_types=[7])
    assert (t.x, t.y, t.target_id, t.man_type) == (5, 0, 111, 7)


def test_scans_points_in_order_of_distance_within_circle():
    scanner, session = make()
    scanner.find_nearest(0, 0, radius=10, target_types=[7])
    dists = [math.dist((0, 0), _xy(m)) for m in session.requested]
    assert dists == sorted(dists)
    assert all(d <= 10 for d in dists)
    assert session.requested[0] == mid_from_coords(0, 0)


def _xy(mid):
    from linhvuong.coords import coords_from_mid

    return coords_from_mid(mid)


def test_ignores_man_types_not_requested():
    scanner, _ = make({mid_from_coords(0, 0): {"npc_tent": [npc_at(1, 1, 5, 2)]}})
    assert scanner.find_nearest(0, 0, radius=5, target_types=[7]) is None


def test_skips_locked_targets_and_locks_the_chosen_one():
    locks = TargetLocks()
    locks.try_lock(111, LockReason.TAKEN_BY_OTHER)
    scanner, _ = make(
        {mid_from_coords(0, 0): {"npc_tent": [npc_at(1, 0, 111, 7), npc_at(2, 0, 222, 7)]}},
        locks=locks,
    )
    t = scanner.find_nearest(0, 0, radius=5, target_types=[7])
    assert t.target_id == 222
    assert locks.is_locked(222)


def test_retries_on_503_with_backoff_then_succeeds():
    mid = mid_from_coords(0, 0)
    scanner, session = make({mid: {"npc_tent": [npc_at(0, 1, 9, 7)]}}, failures={mid: [503, 503]})
    t = scanner.find_nearest(0, 0, radius=2, target_types=[7])
    assert t.target_id == 9
    assert session.sleeps == [0.5, 1.0]


def test_gives_up_on_a_point_after_max_retries_and_continues():
    bad = mid_from_coords(0, 0)
    good = mid_from_coords(5, 0)
    scanner, _ = make(
        {good: {"npc_tent": [npc_at(5, 0, 3, 7)]}}, failures={bad: [503] * 10}
    )
    t = scanner.find_nearest(0, 0, radius=6, target_types=[7])
    assert t.target_id == 3


def test_skips_targets_near_thien_thanh():
    mid0 = mid_from_coords(0, 0)
    scanner, _ = make(
        {
            mid0: {
                "citys": [[1, "Lạc Dương", 6, mid_from_coords(2, 0)]],
                "npc_tent": [npc_at(3, 0, 10, 7), npc_at(30, 0, 20, 7)],
            },
            mid_from_coords(30, 0): {"npc_tent": [npc_at(30, 0, 20, 7)]},
        }
    )
    t = scanner.find_nearest(0, 0, radius=40, target_types=[7], skip_capital_radius=8)
    assert t.target_id == 20


def test_stop_event_aborts_scan():
    scanner, session = make()
    scanner.stop()
    assert scanner.find_nearest(0, 0, radius=20, target_types=[7]) is None
    assert session.requested == []


def test_origin_is_clamped_to_map_bounds():
    scanner, session = make()
    scanner.find_nearest(656, 656, radius=10, target_types=[7])
    assert max(_xy(m)[0] for m in session.requested) <= 656
