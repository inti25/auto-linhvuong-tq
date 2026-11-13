"""Unit tests for P0-P2 server-request reduction and performance optimizations."""

from types import SimpleNamespace

import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.proxy import ProxyEndpoint, ProxyPool
from linhvuong.roster import fetch_roster
from linhvuong.scan import Scanner
from linhvuong.tasks.base import TaskContext
from linhvuong.tasks.building import BuildingPlan, BuildingTask
from linhvuong.tasks.crafting import WeaponCrafter
from linhvuong.tasks.goi_dan import GoiDan, VONG_LINH
from linhvuong.tasks.morale import MoraleTrainer
from linhvuong.tasks.research import ResearchTask, TechPlan


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class _FakeSession:
    def __init__(self, handlers=None, map_views=None):
        self.handlers = handlers or {}
        self.map_views = map_views or {}
        self.calls = []
        self.proxies = {}

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1]
        self.calls.append((key, dict(data or {})))
        if key == "Map.ashx?id=6":
            mid = int((data or {})["mid"])
            handler = self.map_views.get(mid, {"npc_tent": []})
            return _Resp(handler() if callable(handler) else handler)
        handler = self.handlers.get(key, {"ret": 0})
        if callable(handler):
            return _Resp(handler(data or {}))
        if isinstance(handler, list):
            return _Resp(handler.pop(0))
        return _Resp(handler)


def _army_row(gid: int, name: str, morale: int, upgrading_time: int = 0) -> list:
    return [gid, name, 0, "", 0, 100, 95, 100, 0, morale, upgrading_time, 501]


def test_fetch_roster_slim_skips_cities_and_civil():
    server = _FakeSession(
        handlers={
            "Common.ashx?id=32": lambda d: {
                "ret": 0,
                "list": [
                    [1, "Thành 1", 100, 200, [[10, "Triệu Vân", "", 2, 0, 0, 100, 100, 0, 0, 0, 0, 0, 0, 0]]]
                ]
                if str(d.get("type")) == "2"
                else [[1, "Thành 1", 100, 200, [[99, "Tuân Úc", "", 1, 1, 0, 80, 100, 0, 0, 0, 0, 0, 0, 0]]]],
            },
            "Common.ashx?id=76": {
                "ret": 0,
                "list": [[1, "Thành 1", [_army_row(10, "Triệu Vân", 100)]]],
            },
            "Common.ashx?id=65": {"ret": 0, "list": []},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)

    roster = fetch_roster(gw, only_base_ids=[1], include_civil=False, include_cities=False)
    assert any(g.id == 10 for g in roster.generals_of(1))
    assert not any(g.id == 99 for g in roster.generals_of(1))
    assert [c.id for c in roster.cities] == [1]

    called_keys = [k for k, _ in server.calls]
    assert "Common.ashx?id=29" not in called_keys
    assert "City.ashx?id=7" not in called_keys
    c32_types = [d.get("type") for k, d in server.calls if k == "Common.ashx?id=32"]
    assert c32_types == ["2"]


def test_gateway_map_view_cache_and_invalidation():
    mid = mid_from_coords(5, 5)
    calls = {"count": 0}

    def _map_handler():
        calls["count"] += 1
        return {"ret": 0, "npc_tent": [], "seq": calls["count"]}

    server = _FakeSession(map_views={mid: _map_handler})
    gw = GatewayClient(53, server, sleep=lambda s: None)

    first = gw.map_view(mid, cache_ttl=10.0)
    second = gw.map_view(mid, cache_ttl=10.0)
    assert first["seq"] == 1
    assert second["seq"] == 1
    assert calls["count"] == 1

    gw.invalidate_map_cache(mid)
    third = gw.map_view(mid, cache_ttl=10.0)
    assert third["seq"] == 2

    gw.invalidate_map_cache()
    fourth = gw.map_view(mid, cache_ttl=10.0)
    assert fourth["seq"] == 3


def test_goi_dan_invalidates_stale_map_cache_after_calling_npc():
    mid = mid_from_coords(2, 2)
    server = _FakeSession(
        map_views={mid: {"npc_tent": []}},
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda d: server.map_views.update(
                {mid: {"npc_tent": [[888, VONG_LINH, mid]]}}
            )
            or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    assert gw.map_view(mid, cache_ttl=30.0)["npc_tent"] == []

    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0, sleep=lambda s: None, map_cache_ttl=30.0)
    task = GoiDan(
        TaskContext(gw, scanner, locks, notify=lambda m: None),
        generals=[10],
        origin=(2, 2),
        radius=5,
        mode="vong_linh",
        city_id=123,
    )
    assert task.run_once() == "called_and_attacked"


def test_gateway_proxy_failover_capped():
    class _AlwaysTimeoutSession:
        def __init__(self):
            self.proxies = {}
            self.calls = 0

        def post(self, *args, **kwargs):
            self.calls += 1
            raise TimeoutError("proxy timed out")

    ep1 = ProxyEndpoint.from_line("http://1.1.1.1:8080")
    ep2 = ProxyEndpoint.from_line("http://2.2.2.2:8080")
    ep3 = ProxyEndpoint.from_line("http://3.3.3.3:8080")
    ep4 = ProxyEndpoint.from_line("http://4.4.4.4:8080")
    assert ep1 and ep2 and ep3 and ep4
    for ep in (ep1, ep2, ep3, ep4):
        ep.alive = True
    pool = ProxyPool(endpoints=[ep1, ep2, ep3, ep4])
    pool._active_idx = 0

    sess = _AlwaysTimeoutSession()
    pool.apply_to_session(sess)
    gw = GatewayClient(53, sess, sleep=lambda s: None, max_retries=2, proxy_pool=pool, max_failovers=2)

    out = gw.call("Common.ashx", 1, {})
    assert out is None
    # 2 failovers (capped at max_failovers=2) + 2 normal retry attempts = 4 calls
    assert sess.calls == 4


def test_morale_adjust_skips_api76_and_train_multiple_batches_sync():
    server = _FakeSession(
        handlers={
            "Common.ashx?id=76": [
                # Initial city sync before OPT 47
                {
                    "ret": 0,
                    "list": [[101, "Thành 1", [_army_row(10, "Tướng A", 90, 0), _army_row(11, "Tướng B", 90, 0)]]],
                },
                # Post-dispatch batch sync (already updated to 100 after trigger)
                {
                    "ret": 0,
                    "list": [[101, "Thành 1", [_army_row(10, "Tướng A", 100, 0), _army_row(11, "Tướng B", 100, 0)]]],
                },
            ],
            "OPT.ashx?id=47": {"ret": 0, "add_point": 10},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    trainer = MoraleTrainer(gw, sleep_fn=lambda s: None, poll_interval=5.0)

    base_gens = {
        10: SimpleNamespace(name="Tướng A", morale=100, upgrading_time=0),
        11: SimpleNamespace(name="Tướng B", morale=95, upgrading_time=0),
    }
    ready, reasons = trainer.adjust_squad_morale(
        base_id=101,
        general_ids=[10, 11],
        target_morale=100,
        base_gens=base_gens,
        refresh_from_server=False,
    )
    assert ready is False
    assert len(reasons) == 1
    assert not any(k == "Common.ashx?id=76" for k, _ in server.calls)
    assert sum(1 for k, _ in server.calls if k == "OPT.ashx?id=47") == 1

    server.calls.clear()
    res = trainer.train_multiple_generals(
        targets=[
            {"city_id": 101, "general_id": 10, "current_morale": 90, "name": "Tướng A"},
            {"city_id": 101, "general_id": 11, "current_morale": 90, "name": "Tướng B"},
        ],
        target_morale=100,
    )
    assert res[10]["success"] and res[11]["success"]
    c76_count = sum(1 for k, _ in server.calls if k == "Common.ashx?id=76")
    opt47_count = sum(1 for k, _ in server.calls if k == "OPT.ashx?id=47")
    assert opt47_count == 2
    assert c76_count == 2


def test_building_task_busy_skip_comfort_throttle_and_resource_cooldown():
    server = _FakeSession(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [{"slot": 1, "bid": 1, "time_left": 1200}],
            }
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=10)]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        max_slots=1,
        auto_speedup=False,
        auto_comfort=False,
        auto_boost=False,
    )
    assert task.run_once() == "slots_busy"
    assert task.run_once() == "slots_busy"
    assert sum(1 for k, _ in server.calls if k == "Common.ashx?id=77") == 1

    server2 = _FakeSession(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=6": {"ret": 0},
            "City.ashx?id=5": {"ret": 0, "buildings": [{"pid": 1, "gid": 1, "level": 5}]},
            "City.ashx?id=20": {"ret": 0},
            "OPT.ashx?id=65": {"ret": 32},
        }
    )
    gw2 = GatewayClient(53, server2, sleep=lambda s: None)
    task2 = BuildingTask(
        gw2,
        city_id=101,
        plans=plans,
        auto_comfort=True,
        auto_boost=False,
        auto_open_box=False,
    )
    task2.comfort_interval = 300.0
    task2.resource_cooldown = 90.0
    assert task2.run_once() == "insufficient_resources"
    assert task2.run_once() == "insufficient_resources"
    assert sum(1 for k, _ in server2.calls if k == "City.ashx?id=6") == 1
    assert sum(1 for k, _ in server2.calls if k == "OPT.ashx?id=65") == 1


def test_research_task_caches_univ_no_dup_switch_and_busy_skip():
    server = _FakeSession(
        handlers={
            "City.ashx?id=37": [
                {"ret": 0, "tech": {}},
                {"ret": 0, "tech": {}},
            ],
            "City.ashx?id=5": {"ret": 0, "buildings": [{"pid": 9, "gid": 6, "level": 10}]},
            "Build.ashx?id=2": {"ret": 0, "list": [{"id": 1, "level": 5}]},
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = ResearchTask(
        gw,
        city_id=2001,
        plans=[TechPlan(tech_id=1, target_level=10, name="Làm thực")],
        auto_art_of_war=False,
    )
    assert task.run_once() == "researching"
    assert task.run_once() == "researching"
    assert sum(1 for k, _ in server.calls if k == "City.ashx?id=5") == 1
    assert sum(1 for k, _ in server.calls if k == "City.ashx?id=50") == 2

    server_busy = _FakeSession(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {"techid": 1, "time_left": 1200}},
            "City.ashx?id=50": {"ret": 0},
            "City.ashx?id=5": {"ret": 0, "buildings": [{"pid": 9, "gid": 6, "level": 10}]},
            "Build.ashx?id=2": {"ret": 0, "list": [{"id": 1, "level": 5}]},
        }
    )
    gw_busy = GatewayClient(53, server_busy, sleep=lambda s: None)
    task_busy = ResearchTask(gw_busy, city_id=2001, plans=[TechPlan(tech_id=1, target_level=10)], auto_art_of_war=False)
    assert task_busy.run_once() == "research_busy"
    assert task_busy.run_once() == "research_busy"
    assert sum(1 for k, _ in server_busy.calls if k == "City.ashx?id=37") == 1


def test_weapon_crafter_caches_workshop_and_skips_switch_city():
    server = _FakeSession(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "City.ashx?id=5": {"ret": 0, "buildings": [{"pid": 11, "gid": 13, "level": 10}]},
            "build.ashx?id=2": {"ret": 0, "list": []},
            "OPT.ashx?id=38": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    crafter = WeaponCrafter(gw, workshop_cache_ttl=300.0)

    ok1, _, _ = crafter.craft_once(city_id=101, weapon_id=101, amount=10, switch_city=True)
    ok2, _, _ = crafter.craft_once(city_id=101, weapon_id=101, amount=10, switch_city=False)
    assert ok1 is True
    assert ok2 is True
    assert sum(1 for k, _ in server.calls if k == "City.ashx?id=5") == 1
    assert sum(1 for k, _ in server.calls if k == "City.ashx?id=50") == 1
