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


def make(views=None, failures=None, locks=None, step=7, workers=3):
    session = FakeGateway(views, failures)
    client = GatewayClient(53, session, sleep=session.sleeps.append)
    scanner = Scanner(client, locks or TargetLocks(), delay=0.0, step=step, workers=workers, sleep=lambda s: None)
    return scanner, session


def npc_at(x, y, target_id, man_type):
    return [target_id, man_type, mid_from_coords(x, y)]


def test_returns_nearest_matching_target():
    near = npc_at(7, 0, 111, 7)
    far = npc_at(28, 0, 222, 7)
    scanner, _ = make(
        {
            mid_from_coords(7, 0): {"npc_tent": [near]},
            mid_from_coords(28, 0): {"npc_tent": [far]},
        }
    )
    t = scanner.find_nearest(0, 0, radius=30, target_types=[7])
    assert (t.x, t.y, t.target_id, t.man_type) == (7, 0, 111, 7)


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
    good = mid_from_coords(7, 0)
    scanner, _ = make(
        {good: {"npc_tent": [npc_at(7, 0, 3, 7)]}}, failures={bad: [503] * 10}
    )
    t = scanner.find_nearest(0, 0, radius=8, target_types=[7])
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


def test_nearest_base_priority_skips_when_peer_is_closer():
    from linhvuong.scan import BasePeer
    mid0 = mid_from_coords(0, 0)
    # Man 100 tại (7, 0)
    # Man 200 tại (2, 0)
    scanner, _ = make({
        mid0: {"npc_tent": [npc_at(7, 0, 100, 7), npc_at(2, 0, 200, 7)]}
    })
    # Base A tại (0, 0), Base B tại (8, 0)
    # Man 100 cách Base A là 7, cách Base B là 1. Base B gần hơn!
    peer_b = BasePeer(base_id=202, ox=8, oy=0, radius=5, target_types=[7])
    
    # Khi Base A quét với peer_b: Base A phải bỏ qua Man 100 và chọn Man 200
    target = scanner.find_nearest(
        0, 0, radius=10, target_types=[7], owner_id=101, peers=[peer_b]
    )
    assert target is not None
    assert target.target_id == 200


def test_nearest_base_priority_claims_when_this_base_is_closer():
    from linhvuong.scan import BasePeer
    mid8 = mid_from_coords(8, 0)
    # Man 100 tại (7, 0)
    scanner, _ = make({
        mid8: {"npc_tent": [npc_at(7, 0, 100, 7)]}
    })
    # Base B tại (8, 0), Base A tại (0, 0)
    # Man 100 cách Base B là 1, cách Base A là 7. Base B gần hơn!
    peer_a = BasePeer(base_id=101, ox=0, oy=0, radius=10, target_types=[7])
    
    # Khi Base B quét: Base B gần Man 100 hơn nên được quyền nhận!
    target = scanner.find_nearest(
        8, 0, radius=5, target_types=[7], owner_id=202, peers=[peer_a]
    )
    assert target is not None
    assert target.target_id == 100


def test_concurrent_scanning_finds_nearest_and_stops_early():
    # Điểm (0, 0) không có gì, điểm (7, 0) có Man gần (d=7), điểm (21, 0) có Man xa (d=21)
    # Các điểm xa hơn không cần quét hết vì đã tìm thấy Man gần nhất
    scanner, session = make({
        mid_from_coords(7, 0): {"npc_tent": [npc_at(7, 0, 10, 7)]},
        mid_from_coords(21, 0): {"npc_tent": [npc_at(21, 0, 20, 7)]},
    }, workers=3)
    target = scanner.find_nearest(0, 0, radius=30, target_types=[7])
    assert target is not None
    assert target.target_id == 10
    assert (target.x, target.y) == (7, 0)


def test_sequential_fallback_when_workers_is_one():
    scanner, session = make({
        mid_from_coords(7, 0): {"npc_tent": [npc_at(7, 0, 10, 7)]},
    }, workers=1)
    target = scanner.find_nearest(0, 0, radius=10, target_types=[7])
    assert target is not None
    assert target.target_id == 10


def test_scanner_custom_step_and_workers():
    scanner, _ = make(step=10, workers=5)
    assert scanner.step == 10
    assert scanner.workers == 5
    pts = scanner._scan_points(0, 0, 20)
    # Với step=10, reach=20, các offset là -20, -10, 0, 10, 20
    assert any(pt[1] == 10 and pt[2] == 0 for pt in pts)
    assert not any(pt[1] == 7 for pt in pts)


