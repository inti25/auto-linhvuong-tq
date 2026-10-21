import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.tasks.building import BuildingPlan, BuildingTask


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


def test_building_task_upgrades_first_eligible_building():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},  # slot trống
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [
                    {"pid": 1, "gid": 1, "level": 10},
                    {"pid": 2, "gid": 2, "level": 5},
                ],
            },
            "City.ashx?id=20": {"ret": 0},  # đủ tài nguyên
            "OPT.ashx?id=65": {"ret": 0},   # nâng cấp thành công
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=12, name="Thái Phủ"),
        BuildingPlan(pid=2, gid=2, target_level=10, name="Dân Cư"),
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    # Kiểm tra gọi OPT.ashx?id=65 với pid=1, gid=1, type=1
    upgrade_call = [d for k, d in server.calls if k == "OPT.ashx?id=65"][0]
    assert upgrade_call["pid"] == "1"
    assert upgrade_call["gid"] == "1"
    assert upgrade_call["type"] == "1"
    assert upgrade_call["tid"] == "101"


def test_building_task_busy_when_slots_full():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": [{"slot": 1, "bid": 1}]},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=10)]
    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=1, auto_speedup=False, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "slots_busy"


def test_building_task_all_completed():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [
                    {"pid": 1, "gid": 1, "level": 10},
                ],
            },
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=10)]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "all_buildings_completed"


def test_building_task_auto_comfort_when_morale_low():
    server = FakeServer(
        handlers={
            "City.ashx?id=6": {"ret": 0, "data": {"morale": 70, "anger": 5}},
            "OPT.ashx?id=4": {"ret": 0},
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {"ret": 0, "buildings": []},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=5)]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=True, auto_boost=False)
    task.run_once()

    # Kiểm tra đã gọi An Dân OPT.ashx?id=4
    comfort_calls = [d for k, d in server.calls if k == "OPT.ashx?id=4"]
    assert len(comfort_calls) == 1
    assert comfort_calls[0]["tid"] == "101"


def test_building_task_stops_on_captcha():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 110},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], auto_comfort=False, auto_boost=False)
    with pytest.raises(CaptchaRequired):
        task.run_once()


def test_building_task_real_server_format_and_upgrade():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 596952, 3497823, [], []]],
            },
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [0, 2, "城墙", 11, 0, 0],
                    [17, 9, "聚贤楼", 4, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 0, "duration": 49},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=17, gid=9, target_level=5, name="聚贤楼 - Tụ Hiền Lâu")]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    # Kiểm tra gọi OPT.ashx?id=65 với pid=17, gid=9, tid=101
    upgrade_call = [d for k, d in server.calls if k == "OPT.ashx?id=65"][0]
    assert upgrade_call["pid"] == "17"
    assert upgrade_call["gid"] == "9"
    assert upgrade_call["tid"] == "101"


def test_building_task_real_server_slot_busy():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 596952, 3497823, [[17, 9, 4, 1, 48]], []]],
            },
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=17, gid=9, target_level=5)]
    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=1, auto_speedup=False, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "slots_busy"

