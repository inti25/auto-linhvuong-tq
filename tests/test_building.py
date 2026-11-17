import threading
import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.tasks.building import (
    CHEST_MAPPING,
    DEFAULT_FALLBACK_BOX_ORDER,
    NO_SWITCH_CHESTS,
    RESOURCE_BOX_NAMES,
    BuildingPlan,
    BuildingTask,
    chest_needs_city_switch,
    open_single_chest,
    run_batch_open_chest,
)


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
        self.cookies = {"uid": "95"}

    def _resolve(self, key):
        aliases = {
            "/api/city/pagebuilding": "Common.ashx?id=77",
            "/api/building/list": "City.ashx?id=5",
            "/api/city/info": "City.ashx?id=6",
            "/api/resource/info": "City.ashx?id=20",
            "/api/city/current": "City.ashx?id=50",
            "/api/building/update": "OPT.ashx?id=65",
        }
        handler = self.handlers.get(key)
        if handler is None and key in aliases:
            handler = self.handlers.get(aliases[key])
        if handler is None:
            raw = {"ret": 0}
        elif callable(handler):
            raw = handler()
        elif isinstance(handler, list):
            raw = handler.pop(0)
        else:
            raw = handler
        if not isinstance(raw, dict):
            return raw

        # Chuẩn hóa mock data sang format REST Server 58
        if key == "/api/building/list" and "items" not in raw:
            src = raw.get("infos") or raw.get("buildings") or raw.get("build") or []
            items = []
            for b in src:
                if isinstance(b, dict):
                    items.append({
                        "m_lpos": b.get("m_lpos", b.get("pid", 0)),
                        "m_lgid": b.get("m_lgid", b.get("gid", 0)),
                        "m_llevel": b.get("m_llevel", b.get("level", 0)),
                        "m_szname": b.get("m_szname", b.get("name", "")),
                    })
                elif isinstance(b, (list, tuple)) and len(b) >= 4:
                    items.append({"m_lpos": b[0], "m_lgid": b[1], "m_szname": b[2], "m_llevel": b[3]})
            return {**raw, "items": items}
        if key == "/api/city/info" and isinstance(raw.get("data"), dict):
            d = dict(raw["data"])
            if "morale" in d and "m_lmorale_current" not in d:
                d["m_lmorale_current"] = d["morale"]
            if "anger" in d and "m_lmorale_complaint" not in d:
                d["m_lmorale_complaint"] = d["anger"]
            return {**raw, "data": d}
        return raw

    def get(self, url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        self.calls.append((path, dict(params or {})))
        return Resp(self._resolve(path))

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        self.calls.append((key, dict(data or {})))
        return Resp(self._resolve(key))


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

    # Kiểm tra gọi /api/building/update với posId=1, gid=1, type=1, cityTentId=101
    upgrade_call = [d for k, d in server.calls if k == "/api/building/update"][0]
    assert upgrade_call["posId"] == "1"
    assert upgrade_call["gid"] == "1"
    assert upgrade_call["type"] == "1"
    assert upgrade_call["cityTentId"] == "101"


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

    # Kiểm tra gọi /api/building/update với posId=17, gid=9, cityTentId=101
    upgrade_call = [d for k, d in server.calls if k == "/api/building/update"][0]
    assert upgrade_call["posId"] == "17"
    assert upgrade_call["gid"] == "9"
    assert upgrade_call["cityTentId"] == "101"


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


def test_building_task_upgrades_up_to_3_slots():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 5, 0, 0],
                    [2, 2, "Tường Thành", 5, 0, 0],
                    [3, 3, "Nhà Dân", 5, 0, 0],
                    [4, 4, "Kho", 5, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=10),
        BuildingPlan(pid=2, gid=2, target_level=10),
        BuildingPlan(pid=3, gid=3, target_level=10),
        BuildingPlan(pid=4, gid=4, target_level=10),
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=3, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    upgrade_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(upgrade_calls) == 3
    called_pids = [c["posId"] for c in upgrade_calls]
    assert called_pids == ["1", "2", "3"]


def test_building_task_skips_busy_pids_and_uses_remaining_slots():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 0, 0, [[2, 2, 5, 1, 60]], []]],
            },
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 5, 0, 0],
                    [2, 2, "Tường Thành", 5, 0, 0],
                    [3, 3, "Nhà Dân", 5, 0, 0],
                    [4, 4, "Kho", 5, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=10),
        BuildingPlan(pid=2, gid=2, target_level=10),  # Đang bận ở slot
        BuildingPlan(pid=3, gid=3, target_level=10),
        BuildingPlan(pid=4, gid=4, target_level=10),
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=3, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    # Slot bận = 1, max_slots = 3 -> còn 2 slot trống -> gửi pid 1 và pid 3
    upgrade_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(upgrade_calls) == 2
    called_pids = [c["posId"] for c in upgrade_calls]
    assert called_pids == ["1", "3"]


def test_building_task_downgrades_when_cur_lvl_greater_than_target():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 15, 0, 0],
                    [2, 3, "Nhà Dân", 8, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=2, gid=3, target_level=5, name="Nhà Dân"),
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    # Kiểm tra gọi /api/building/update với posId=2, gid=3, type="2" (hạ cấp)
    opt_call = [d for k, d in server.calls if k == "/api/building/update"][0]
    assert opt_call["posId"] == "2"
    assert opt_call["gid"] == "3"
    assert opt_call["type"] == "2"
    assert opt_call["cityTentId"] == "101"


def test_building_task_demolish_to_zero_freely():
    # Q2-B: Cho phép dỡ bỏ hoàn toàn về 0 cho mọi công trình (kể cả Quan Phủ)
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 1, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=0, name="Quan Phủ"),
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    opt_call = [d for k, d in server.calls if k == "/api/building/update"][0]
    assert opt_call["posId"] == "1"
    assert opt_call["gid"] == "1"
    assert opt_call["type"] == "2"
    assert opt_call["cityTentId"] == "101"


def test_building_task_downgrade_with_auto_speedup():
    # Cơ chế tăng tốc chuẩn: tự động giảm 50% thời gian thi công cho slot bằng Ngân Bảo (paytype=2)
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": [
                {"ret": 0, "list": []},
                {"ret": 0, "list": [[101, "NB", 0, 0, [[5, 4, 9, 2, 7200]], []]]},
            ],
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [5, 4, "Kho", 10, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=5, gid=4, target_level=5, name="Kho")]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_speedup=True, speedup_hours=1.0, paytype=2, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    # Kiểm tra gọi lệnh tăng tốc đúng param1=slot 5, param2=city_id 101, paytype=2 (Ngân Bảo)
    speedup_calls = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(speedup_calls) == 1
    assert speedup_calls[0]["type"] == "1"
    assert speedup_calls[0]["param1"] == "5"
    assert speedup_calls[0]["param2"] == "101"
    assert speedup_calls[0]["paytype"] == "2"


def test_process_speedup_halving_loop_to_target_hours():
    # 15000s -> 7500s -> 3750s -> 1875s (<= 3600s: 3 lần giảm 50%)
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 0, 0, [[12, 11, 8, 1, 15000]], []]],
            },
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], speedup_hours=1.0, paytype=2)
    speedup_count = task.process_speedup()
    assert speedup_count == 3

    calls = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls) == 3
    assert all(c["param1"] == "12" for c in calls)
    assert all(c["param2"] == "101" for c in calls)
    assert all(c["paytype"] == "2" for c in calls)


def test_process_speedup_already_below_target_hours():
    # 1800s (30 phút) < 1h (3600s): không gọi tăng tốc
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 0, 0, [[3, 3, 5, 1, 1800]], []]],
            },
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], speedup_hours=1.0, paytype=2)
    speedup_count = task.process_speedup()
    assert speedup_count == 0

    calls = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls) == 0


def test_process_speedup_max_10_iterations_cap():
    # Thời gian thi công cực lớn: bị chặn lại ở tối đa 10 lần như ZBuild (gid=4 Kho có hỗ trợ tăng tốc)
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 0, 0, [[1, 4, 20, 1, 10_000_000]], []]],
            },
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], speedup_hours=1.0, paytype=2)
    speedup_count = task.process_speedup()
    assert speedup_count == 10

    calls = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls) == 10
    assert all(c["param1"] == "1" for c in calls)
    assert all(c["param2"] == "101" for c in calls)
    assert all(c["paytype"] == "2" for c in calls)


def test_process_speedup_stops_on_server_error():
    # Dừng vòng lặp khi server báo lỗi (ví dụ hết Ngân Bảo: ret 45)
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 0, 0, [[8, 6, 12, 1, 10000]], []]],
            },
            "OPT.ashx?id=69": [
                {"ret": 0},   # Lần 1 thành công
                {"ret": 45},  # Lần 2 thất bại (thiếu Ngân Bảo)
            ],
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], speedup_hours=1.0, paytype=2)
    speedup_count = task.process_speedup()
    assert speedup_count == 1

    calls = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls) == 2
    assert all(c["param1"] == "8" for c in calls)
    assert all(c["param2"] == "101" for c in calls)


def test_building_task_handles_ret_36_minimum_level():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 1, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 36},  # Đã đạt cấp tối thiểu
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=0, name="Quan Phủ")]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "cannot_downgrade_min_level"


def test_building_task_mixed_upgrade_and_downgrade_priority_order():
    # Q3: Thứ tự Nâng và Hạ cấp tuân thủ tuyệt đối theo thứ tự trong hàng đợi
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 10, 0, 0],
                    [2, 2, "Tường Thành", 12, 0, 0],
                    [3, 3, "Nhà Dân", 5, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=12),  # Nâng cấp 10 -> 12 (type=1)
        BuildingPlan(pid=2, gid=2, target_level=8),   # Hạ cấp 12 -> 8 (type=2)
        BuildingPlan(pid=3, gid=3, target_level=10),  # Nâng cấp 5 -> 10 (type=1)
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=2, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    opt_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(opt_calls) == 2
    # Item 1: pid=1, type="1"
    assert opt_calls[0]["posId"] == "1"
    assert opt_calls[0]["type"] == "1"
    # Item 2: pid=2, type="2"
    assert opt_calls[1]["posId"] == "2"
    assert opt_calls[1]["type"] == "2"


def test_building_task_auto_opens_box_on_insufficient_resources_and_retries_successfully():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [[1, 1, "Quan Phủ", 10, 0, 0]],
            },
            "OPT.ashx?id=65": [{"ret": 32}, {"ret": 0}],  # Lần 1: thiếu TN (32), sau khi mở rương -> thành công (0)
            "City.ashx?id=50": {"ret": 0},
            "Common.ashx?id=48": {"ret": 0},  # Mở rương thành công
            "City.ashx?id=20": {"ret": 0, "data": {"max_storage": 1000000, "wood": 1000, "stone": 1000, "iron": 1000, "food": 1000}},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=12)]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        auto_comfort=False,
        auto_boost=False,
        auto_open_box=True,
        box_id=24,
        max_boxes_per_round=5,
    )
    out = task.run_once()
    assert out == "upgrading"

    # Kiểm tra gọi /api/city/current với cityTentId=101
    switch_calls = [d for k, d in server.calls if k == "/api/city/current"]
    assert len(switch_calls) == 1
    assert switch_calls[0]["cityTentId"] == "101"

    # Kiểm tra gọi Common.ashx?id=48 mở Dân Sinh Bảo Đỉnh (lBoxID=24)
    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 1
    assert box_calls[0]["lBoxID"] == "24"

    # Kiểm tra gọi /api/building/update 2 lần (lần 1 bị 32, lần 2 thành công)
    upgrade_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(upgrade_calls) == 2


def test_building_task_auto_box_fallback_when_out_of_stock_10014():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [[1, 1, "Quan Phủ", 10, 0, 0]],
            },
            "OPT.ashx?id=65": [{"ret": 37}, {"ret": 0}],  # Lần 1: thiếu TN (37), sau khi mở rương nhỏ -> thành công (0)
            "City.ashx?id=50": {"ret": 0},
            "Common.ashx?id=48": [{"ret": 10014}, {"ret": 0}],  # Hết rương 24 (10014), chuyển rương 16 thành công (0)
            "City.ashx?id=20": {"ret": 0, "data": {"max_storage": 1000000, "wood": 1000, "stone": 1000, "iron": 1000, "food": 1000}},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=12)]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        auto_comfort=False,
        auto_boost=False,
        auto_open_box=True,
        box_id=24,
        auto_fallback_box=True,
    )
    out = task.run_once()
    assert out == "upgrading"

    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 2
    assert box_calls[0]["lBoxID"] == "24"
    assert box_calls[1]["lBoxID"] == "16"


def test_building_task_stops_when_max_boxes_reached():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [[1, 1, "Quan Phủ", 10, 0, 0]],
            },
            "OPT.ashx?id=65": {"ret": 32},  # Luôn thiếu tài nguyên
            "City.ashx?id=50": {"ret": 0},
            "Common.ashx?id=48": {"ret": 0},  # Mở rương thành công
            "City.ashx?id=20": {"ret": 0, "data": {"max_storage": 1000000, "wood": 1000, "stone": 1000, "iron": 1000, "food": 1000}},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=12)]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        auto_comfort=False,
        auto_boost=False,
        auto_open_box=True,
        box_id=24,
        max_boxes_per_round=3,
        auto_fallback_box=False,
    )
    out = task.run_once()
    assert out == "insufficient_resources"

    # Chỉ mở tối đa 3 lần
    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 3


def test_building_task_stops_opening_when_storage_full():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [[1, 1, "Quan Phủ", 10, 0, 0]],
            },
            "OPT.ashx?id=65": {"ret": 32},  # Thiếu tài nguyên
            "City.ashx?id=50": {"ret": 0},
            "Common.ashx?id=48": {"ret": 0},
            "City.ashx?id=20": {
                "ret": 0,
                "data": {"max_storage": 500000, "wood": 500000, "stone": 500000, "iron": 500000, "food": 500000},  # Đầy kho
            },
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=12)]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        auto_comfort=False,
        auto_boost=False,
        auto_open_box=True,
        box_id=24,
        max_boxes_per_round=5,
    )
    out = task.run_once()
    assert out == "insufficient_resources"

    # Dừng sau 1 lần mở vì phát hiện kho đã đầy
    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 1


def test_building_task_skips_error_261_and_upgrades_next_eligible():
    logs = []
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 5, 0, 0],
                    [2, 2, "Tường Thành", 5, 0, 0],
                ],
            },
            "OPT.ashx?id=65": [{"ret": 261}, {"ret": 0}],  # pid 1 bị 261, pid 2 thành công
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=10, name="Quan Phủ"),
        BuildingPlan(pid=2, gid=2, target_level=10, name="Tường Thành"),
    ]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        max_slots=1,
        auto_comfort=False,
        auto_boost=False,
        notify=logs.append,
    )
    out = task.run_once()
    assert out == "upgrading"

    # Kiểm tra log thông báo bỏ qua mã 261
    assert any("bị chặn (mã 261). Bỏ qua, nâng cấp công trình khác" in m for m in logs)
    assert any("Đang nâng cấp slot 2" in m for m in logs)

    # Kiểm tra server nhận 2 cuộc gọi OPT.ashx?id=65 (pid 1 rồi tới pid 2)
    opt_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(opt_calls) == 2
    assert opt_calls[0]["posId"] == "1"
    assert opt_calls[1]["posId"] == "2"


def test_building_task_skips_multiple_261_and_fills_available_slots():
    logs = []
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 5, 0, 0],
                    [2, 2, "Tường Thành", 5, 0, 0],
                    [3, 3, "Nhà Dân", 5, 0, 0],
                    [4, 4, "Kho", 5, 0, 0],
                ],
            },
            "OPT.ashx?id=65": [{"ret": 261}, {"ret": 0}, {"ret": 261}, {"ret": 0}],
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=10),  # 261 -> skip
        BuildingPlan(pid=2, gid=2, target_level=10),  # ret 0 -> success 1
        BuildingPlan(pid=3, gid=3, target_level=10),  # 261 -> skip
        BuildingPlan(pid=4, gid=4, target_level=10),  # ret 0 -> success 2
    ]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        max_slots=2,  # Cần 2 slot
        auto_comfort=False,
        auto_boost=False,
        notify=logs.append,
    )
    out = task.run_once()
    assert out == "upgrading"

    opt_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(opt_calls) == 4
    assert [c["posId"] for c in opt_calls] == ["1", "2", "3", "4"]


def test_building_task_all_blocked_by_261_returns_blocked():
    logs = []
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phủ", 5, 0, 0],
                    [2, 2, "Tường Thành", 5, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 261},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=10),
        BuildingPlan(pid=2, gid=2, target_level=10),
    ]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        max_slots=2,
        auto_comfort=False,
        auto_boost=False,
        notify=logs.append,
    )
    out = task.run_once()
    assert out == "blocked_error_261"
    assert len(task.skipped_pids) == 2


def test_building_task_deferred_queue_tests_errors_261_and_245_last():
    logs = []
    # Lần 1: pid 1 gặp 261, pid 2 gặp 245, pid 3 thành công (ret 0)
    # Lần 2: pid 4 bình thường thành công, pid 1 được kiểm tra cuối và thành công, pid 2 vẫn 245
    opt_responses = [
        {"ret": 261},  # Lần 1: pid 1 (bị 261 -> hoãn)
        {"ret": 245},  # Lần 1: pid 2 (bị 245 -> hoãn)
        {"ret": 0},    # Lần 1: pid 3 (thành công -> đủ 1 slot -> break)
        {"ret": 261},  # Lần 2: pid 4 (bình thường, duyệt trước, bị 261)
        {"ret": 0},    # Lần 2: pid 1 (hoãn từ lần 1, duyệt sau, thành công!)
    ]
    city_infos = [
        [1, 1, "Quan Phủ", 5, 0, 0],
        [2, 2, "Tường Thành", 5, 0, 0],
        [3, 3, "Nhà Dân", 5, 0, 0],
        [4, 4, "Kho", 5, 0, 0],
    ]
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {"ret": 0, "infos": city_infos},
            "OPT.ashx?id=65": opt_responses,
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=10, name="Quan Phủ"),
        BuildingPlan(pid=2, gid=2, target_level=10, name="Tường Thành"),
        BuildingPlan(pid=3, gid=3, target_level=10, name="Nhà Dân"),
        BuildingPlan(pid=4, gid=4, target_level=10, name="Kho"),
    ]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        max_slots=1,
        auto_comfort=False,
        auto_boost=False,
        notify=logs.append,
    )

    # Vòng lặp 1:
    res1 = task.run_once()
    assert res1 == "upgrading"
    assert task.deferred_pids == {1, 2}
    calls_cycle1 = [d["posId"] for k, d in server.calls if k == "/api/building/update"]
    assert calls_cycle1 == ["1", "2", "3"]

    # Vòng lặp 2: (pid 3 đã lên cấp 10 tức là đã xong)
    city_infos[2][3] = 10  # pid 3 level = 10 -> completed
    server.calls.clear()

    res2 = task.run_once()
    assert res2 == "upgrading"
    calls_cycle2 = [d["posId"] for k, d in server.calls if k == "/api/building/update"]
    # Kỳ vọng: pid 4 (bình thường) được duyệt trước tiên, sau đó mới tới pid 1 (hoãn)
    assert calls_cycle2 == ["4", "1"]
    # pid 1 nâng cấp thành công nên được gỡ khỏi deferred_pids, pid 4 bị 261 nên vào deferred_pids
    assert 1 not in task.deferred_pids
    assert task.deferred_pids == {2, 4}
    assert any("Slot 1 (Quan Phủ) đã được gỡ hoãn" in m for m in logs)


def test_building_task_deferred_cleared_on_target_reached_and_reset():
    gw = GatewayClient(57, FakeServer(), sleep=lambda s: None)
    task = BuildingTask(
        gw,
        city_id=101,
        plans=[BuildingPlan(pid=1, gid=1, target_level=5)],
    )
    task.deferred_pids.add(1)
    task.deferred_pids.add(2)
    assert len(task.deferred_pids) == 2

    task.reset_deferred()
    assert len(task.deferred_pids) == 0


def test_building_task_even_upgrade_ordering():
    # Cấu hình các công trình với cấp độ hiện tại khác nhau:
    # pid 1: cấp 8 (target 10) -> Nâng cấp
    # pid 2: cấp 2 (target 10) -> Nâng cấp
    # pid 3: cấp 5 (target 10) -> Nâng cấp
    # pid 4: cấp 6 (target 2)  -> Hạ cấp
    # pid 5: cấp 2 (target 10) -> Nâng cấp (hòa cấp với pid 2)
    city_infos = [
        [1, 1, "Quan Phủ", 8, 0, 0],
        [2, 2, "Tường Thành", 2, 0, 0],
        [3, 3, "Nhà Dân", 5, 0, 0],
        [4, 4, "Kho", 6, 0, 0],
        [5, 5, "Hồng Lư Tự", 2, 0, 0],
    ]
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=10),
        BuildingPlan(pid=2, gid=2, target_level=10),
        BuildingPlan(pid=3, gid=3, target_level=10),
        BuildingPlan(pid=4, gid=4, target_level=2),
        BuildingPlan(pid=5, gid=5, target_level=10),
    ]

    # 1. Khi even_upgrade=False: Duyệt theo thứ tự bảng 1, 2, 3, 4, 5
    server_default = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {"ret": 0, "infos": city_infos},
            "OPT.ashx?id=65": [{"ret": 261}] * 5,  # Cho fail hết để xem trọn vẹn thứ tự duyệt
        }
    )
    gw_default = GatewayClient(57, server_default, sleep=lambda s: None)
    task_default = BuildingTask(gw_default, city_id=101, plans=plans, max_slots=5, even_upgrade=False)
    task_default.run_once()
    calls_default = [d["posId"] for k, d in server_default.calls if k == "/api/building/update"]
    assert calls_default == ["1", "2", "3", "4", "5"]

    # 2. Khi even_upgrade=True:
    # Nâng cấp cấp thấp nhất lên trước: pid 2 (cấp 2) và pid 5 (cấp 2) xếp trước.
    # Hòa cấp thì giữ thứ tự ban đầu: 2 trước, 5 sau.
    # Tiếp theo: pid 3 (cấp 5), pid 1 (cấp 8).
    # Cuối cùng là công trình hạ cấp: pid 4.
    # Kết quả kỳ vọng: ["2", "5", "3", "1", "4"]
    server_even = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {"ret": 0, "infos": city_infos},
            "OPT.ashx?id=65": [{"ret": 261}] * 5,
        }
    )
    gw_even = GatewayClient(57, server_even, sleep=lambda s: None)
    task_even = BuildingTask(gw_even, city_id=101, plans=plans, max_slots=5, even_upgrade=True)
    task_even.run_once()
    calls_even = [d["posId"] for k, d in server_even.calls if k == "/api/building/update"]
    assert calls_even == ["2", "5", "3", "1", "4"]


def test_building_task_on_sync_data_callback():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [
                    {"pid": 1, "gid": 1, "level": 12},
                    {"pid": 2, "gid": 2, "level": 8},
                ],
            },
            "City.ashx?id=20": {"ret": 0},
            "OPT.ashx?id=65": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=15)]
    synced_events = []

    def on_sync(city_id, real_map):
        synced_events.append((city_id, real_map))

    task = BuildingTask(gw, city_id=101, plans=plans, on_sync_data=on_sync)
    res = task.run_once()
    assert res == "upgrading"
    assert len(synced_events) == 1
    assert synced_events[0][0] == 101
    assert synced_events[0][1][1]["level"] == 12
    assert synced_events[0][1][2]["level"] == 8


def test_building_task_syncs_on_first_cycle_even_if_slots_busy():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": [{"slot": 1, "bid": 1}, {"slot": 2, "bid": 2}, {"slot": 3, "bid": 3}]},
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "Quan Phu", 10],
                    [2, 2, "Tuong Thanh", 5],
                ],
            },
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=15)]
    synced_events = []

    def on_sync(city_id, real_map):
        synced_events.append((city_id, real_map))

    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=3, auto_speedup=False, on_sync_data=on_sync)
    res = task.run_once()
    assert res == "slots_busy"
    assert len(synced_events) == 1
    assert synced_events[0][0] == 101
    assert synced_events[0][1][1]["level"] == 10
    assert synced_events[0][1][2]["level"] == 5


def test_order_plans_by_type_even_preserves_type_order_and_balances_intra_type():
    gw = GatewayClient(53, FakeServer(), sleep=lambda s: None)
    # Plans: Quan Phủ (gid=1), Nhà Dân (gid=3, 3 ô), Kho (gid=4, 2 ô)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=15, name="Quan Phủ"),
        BuildingPlan(pid=10, gid=3, target_level=10, name="Nhà Dân 1"),
        BuildingPlan(pid=11, gid=3, target_level=10, name="Nhà Dân 2"),
        BuildingPlan(pid=12, gid=3, target_level=10, name="Nhà Dân 3"),
        BuildingPlan(pid=20, gid=4, target_level=12, name="Kho 1"),
        BuildingPlan(pid=21, gid=4, target_level=12, name="Kho 2"),
    ]
    real_buildings = {
        1: {"gid": 1, "level": 12},
        10: {"gid": 3, "level": 6},
        11: {"gid": 3, "level": 2},
        12: {"gid": 3, "level": 8},
        20: {"gid": 4, "level": 9},
        21: {"gid": 4, "level": 4},
    }
    task = BuildingTask(gw, city_id=101, plans=plans)
    ordered = task._order_plans_by_type_even(plans, real_buildings)

    # 1. Thứ tự nhóm bảo toàn: gid 1 -> gid 3 -> gid 4
    gids = [p.gid for p in ordered]
    assert gids == [1, 3, 3, 3, 4, 4]

    # 2. Trong cùng nhóm gid 3: cấp thấp (pid 11, lvl 2) -> (pid 10, lvl 6) -> (pid 12, lvl 8)
    pids_g3 = [p.pid for p in ordered if p.gid == 3]
    assert pids_g3 == [11, 10, 12]

    # 3. Trong cùng nhóm gid 4: cấp thấp (pid 21, lvl 4) -> (pid 20, lvl 9)
    pids_g4 = [p.pid for p in ordered if p.gid == 4]
    assert pids_g4 == [21, 20]


def test_building_task_upgrades_lowest_level_of_same_type_first():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},  # slot trống
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [
                    {"pid": 11, "gid": 3, "level": 7},
                    {"pid": 12, "gid": 3, "level": 3},
                ],
            },
            "City.ashx?id=20": {"ret": 0},  # đủ tài nguyên
            "OPT.ashx?id=65": {"ret": 0},   # nâng cấp thành công
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    # Plans đưa pid 11 trước pid 12
    plans = [
        BuildingPlan(pid=11, gid=3, target_level=10, name="Nhà Dân 1"),
        BuildingPlan(pid=12, gid=3, target_level=10, name="Nhà Dân 2"),
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    # Mặc định theo quy hoạch nhóm (ADR-0016), ô có cấp thấp hơn (pid=12, level 3)
    # phải được nâng trước pid=11 (level 7)
    upgrade_call = [d for k, d in server.calls if k == "/api/building/update"][0]
    assert upgrade_call["posId"] == "12"
    assert upgrade_call["gid"] == "3"


def test_building_task_skips_resource_starved_building_and_builds_next_eligible():
    def opt_handler():
        call = server.calls[-1]
        data = call[1]
        if data.get("posId") == "1":
            return {"ret": 32}
        return {"ret": 0}

    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [
                    {"pid": 1, "gid": 1, "level": 10},
                    {"pid": 2, "gid": 2, "level": 5},
                ],
            },
            "City.ashx?id=20": {"ret": 0},
            "OPT.ashx?id=65": opt_handler,
            "Common.ashx?id=48": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=12, name="Quan Phủ"),
        BuildingPlan(pid=2, gid=2, target_level=6, name="Tường Thành"),
    ]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        max_slots=1,
        auto_comfort=False,
        auto_boost=False,
        auto_open_box=True,
        box_id=24,
    )
    res = task.run_once()
    assert res == "upgrading"

    opt_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(opt_calls) == 2
    assert opt_calls[0]["posId"] == "1"
    assert opt_calls[1]["posId"] == "2"

    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 0


def test_building_task_opens_one_box_when_all_starved_then_retries_from_top_in_priority_order():
    box_opened = False

    def opt_handler():
        nonlocal box_opened
        call = server.calls[-1]
        data = call[1]
        if not box_opened:
            return {"ret": 32}
        if data.get("posId") == "1":
            return {"ret": 0}
        return {"ret": 32}

    def box_handler():
        nonlocal box_opened
        box_opened = True
        return {"ret": 0}

    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [
                    {"pid": 1, "gid": 1, "level": 10},
                    {"pid": 2, "gid": 2, "level": 5},
                ],
            },
            "City.ashx?id=20": {"ret": 0, "data": {"max_storage": 1000000, "wood": 10000}},
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=65": opt_handler,
            "Common.ashx?id=48": box_handler,
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=1, gid=1, target_level=12, name="Quan Phủ"),
        BuildingPlan(pid=2, gid=2, target_level=6, name="Tường Thành"),
    ]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        max_slots=1,
        auto_comfort=False,
        auto_boost=False,
        auto_open_box=True,
        box_id=24,
    )
    res = task.run_once()
    assert res == "upgrading"

    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 1
    assert box_calls[0]["lBoxID"] == "24"

    opt_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(opt_calls) == 3
    assert opt_calls[0]["posId"] == "1"
    assert opt_calls[1]["posId"] == "2"
    assert opt_calls[2]["posId"] == "1"


def test_building_task_does_not_activate_boost_when_already_active():
    BuildingTask._last_boost_act_time = 0.0
    server = FakeServer(
        handlers={
            "/api/city/pagebuilding": {
                "ret": 0,
                "data": {
                    "ret": 0,
                    "plus_finish": "2234:39:14",
                    "list": [[101, "NB", 738765, 2792887, [], []]],
                },
            },
            "/api/building/list": {
                "ret": 0,
                "items": [{"m_lpos": 1, "m_lgid": 1, "m_llevel": 10}],
            },
            "/api/building/update": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=12, name="Quan Phủ")]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        auto_comfort=False,
        auto_boost=True,
    )
    res = task.run_once()
    assert res == "upgrading"

    # Khi plus_finish còn hạn ("2234:39:14" > 0), tuyệt đối KHÔNG gọi kích hoạt OPT.ashx?id=69 (type=3)
    boost_calls = [d for k, d in server.calls if k == "OPT.ashx?id=69" and d.get("type") == "3"]
    assert len(boost_calls) == 0, f"DS kiến trúc đang còn hạn nhưng lại bị kích hoạt! Calls: {boost_calls}"


def test_parse_boost_remaining_time_various_formats():
    from linhvuong.tasks.building import parse_boost_remaining_time

    # 1. String HH:MM:SS từ plus_finish root
    assert parse_boost_remaining_time({"ret": 0, "plus_finish": "2234:39:14", "list": []}, 101) == 2234 * 3600 + 39 * 60 + 14

    # 2. String MM:SS
    assert parse_boost_remaining_time({"ret": 0, "plus_finish": "39:14"}, 101) == 39 * 60 + 14

    # 3. Numeric integer seconds
    assert parse_boost_remaining_time({"ret": 0, "plus_finish": 3600}, 101) == 3600

    # 4. Server 58: list[i][2] là map_id (vd 738765), list[i][3] là timestamp khác — KHÔNG được đọc nhầm là plus_finish!
    resp_map_id = {"ret": 0, "plus_finish": 0, "list": [[10129, "inca", 738765, 2792887, [], []]]}
    assert parse_boost_remaining_time(resp_map_id, 10129) == 0

    # 5. Expired / missing cases
    assert parse_boost_remaining_time({"ret": 0, "plus_finish": 0}, 101) == 0
    assert parse_boost_remaining_time({"ret": 0, "plus_finish": "00:00:00"}, 101) == 0
    assert parse_boost_remaining_time({"ret": 0, "list": []}, 101) == 0
    assert parse_boost_remaining_time({}, 101) == 0


def test_building_task_activates_boost_when_expired():
    BuildingTask._last_boost_act_time = 0.0
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                # Expired: val3 = 0, val2 = 0
                "list": [[101, "NB", 0, 0, [], []]],
            },
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [{"pid": 1, "gid": 1, "level": 10}],
            },
            "OPT.ashx?id=65": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=12, name="Quan Phủ")]
    task = BuildingTask(
        gw,
        city_id=101,
        plans=plans,
        auto_comfort=False,
        auto_boost=True,
    )
    res = task.run_once()
    assert res == "upgrading"

    # Khi DS kiến trúc hết hạn, kích hoạt OPT.ashx?id=69 (type=3) đúng 1 lần
    boost_calls = [d for k, d in server.calls if k == "OPT.ashx?id=69" and d.get("type") == "3"]
    assert len(boost_calls) == 1
    assert boost_calls[0]["paytype"] == "2"


def test_building_task_cooldown_prevents_multiple_activations():
    BuildingTask._last_boost_act_time = 0.0
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [
                    [101, "City 1", 0, 0, [], []],
                    [102, "City 2", 0, 0, [], []],
                ],
            },
            "City.ashx?id=5": {
                "ret": 0,
                "buildings": [{"pid": 1, "gid": 1, "level": 10}],
            },
            "OPT.ashx?id=65": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task1 = BuildingTask(
        gw,
        city_id=101,
        plans=[BuildingPlan(pid=1, gid=1, target_level=12, name="Quan Phủ")],
        auto_comfort=False,
        auto_boost=True,
    )
    task2 = BuildingTask(
        gw,
        city_id=102,
        plans=[BuildingPlan(pid=1, gid=1, target_level=12, name="Quan Phủ")],
        auto_comfort=False,
        auto_boost=True,
    )

    # Chạy lần 1 cho thành 1 -> kích hoạt
    task1.run_once()
    # Chạy lần 2 cho thành 2 ngay sau đó -> bị cooldown 60s chặn lại, KHÔNG được kích hoạt lần 2
    task2.run_once()

    boost_calls = [d for k, d in server.calls if k == "OPT.ashx?id=69" and d.get("type") == "3"]
    assert len(boost_calls) == 1, f"DS kiến trúc bị kích hoạt nhiều lần: {len(boost_calls)} lần"


def test_building_task_caches_c77_within_cycle():
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {"ret": 0, "buildings": []},
            "City.ashx?id=20": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], auto_comfort=False, auto_boost=True)
    task.run_once()
    c77_calls = [c for c in server.calls if c[0] == "/api/city/pagebuilding"]
    # Cả check_and_activate_boost và get_active_upgrade_slots cùng chia sẻ 1 lần gọi
    assert len(c77_calls) == 1


def test_process_speedup_handles_hhmmss_string_and_str_city_id():
    # Máy chủ trả về city_id dạng chuỗi và thời gian còn lại dạng "HH:MM:SS" (> 24h)
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [["101", "NB", 0, 0, [[5, 3, 25, 1, "30:00:00"]], []]],
            },
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], auto_speedup=True, speedup_hours=24.0, paytype=2)
    speedup_count = task.process_speedup()
    # 30h > 24h -> giảm 1 lần còn 15h <= 24h
    assert speedup_count == 1
    calls = [d for k, d in server.calls if k == "OPT.ashx?id=69" and d.get("type") == "1"]
    assert len(calls) == 1
    assert calls[0]["param1"] == "5"
    assert calls[0]["param2"] == "101"


def test_process_speedup_handles_unix_timestamp():
    import time

    future_ts = int(time.time()) + 30 * 3600  # còn 30 giờ (> 24h)
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {
                "ret": 0,
                "list": [[101, "NB", 0, 0, [[7, 6, 30, 1, future_ts]], []]],
            },
            "OPT.ashx?id=69": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=101, plans=[], auto_speedup=True, speedup_hours=24.0, paytype=2)
    speedup_count = task.process_speedup()
    assert speedup_count == 1


def test_building_task_does_not_build_when_slot_check_fails():
    # Khi cả Common.ashx?id=77 và Build.ashx?id=2 đều lỗi/timeout, không được phép gửi OPT.ashx?id=65
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 999},
            "Build.ashx?id=2": {"ret": 8},
            "City.ashx?id=5": {"ret": 0, "infos": [[1, 1, "Quan Phủ", 5, 0, 0]]},
            "OPT.ashx?id=65": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [BuildingPlan(pid=1, gid=1, target_level=10), BuildingPlan(pid=2, gid=2, target_level=10)]
    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=3, auto_comfort=False, auto_boost=False)

    out = task.run_once()
    assert out == "slots_read_failed"
    assert [d for k, d in server.calls if k == "/api/building/update"] == []


def test_building_task_shared_c77_miss_requeries_own_city_before_fallback():
    # Runner tiêm shared cache Common.ashx?id=77 của thành 101 (chỉ chứa thành 101).
    # Thành 102 đã đủ 3 công trình xây dựng -> phải tự hỏi lại Common.ashx?id=77 với cid=102 và dừng ngay,
    # không được rơi xuống fallback Build.ashx?id=2 lỗi rồi gửi OPT.ashx?id=65.
    class _PerCityServer:
        def __init__(self):
            self.calls = []
            self.cookies = {"uid": "95"}

        def get(self, url, params=None, headers=None, timeout=None):
            path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
            p = dict(params or {})
            self.calls.append((path, p))
            if path == "/api/city/pagebuilding":
                cid = int(p.get("cityTentId", 0))
                if cid == 101:
                    return Resp({"ret": 0, "data": {"ret": 0, "plus_finish": 1000, "list": [[101, "C1", 738765, 1000, [], []]]}})
                return Resp({
                    "ret": 0,
                    "data": {
                        "ret": 0,
                        "plus_finish": 1000,
                        "list": [[102, "C2", 738765, 1000, [[1, 1, 5, 1, 120], [2, 2, 5, 1, 240], [3, 3, 5, 1, 360]], []]],
                    },
                })
            if path == "/api/building/list":
                return Resp({"ret": 0, "data": {"items": [{"m_lpos": 4, "m_lgid": 4, "m_szname": "Kho", "m_llevel": 5}]}})
            return Resp({"ret": 0})

        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
            self.calls.append((key, dict(data or {})))
            if key == "Build.ashx?id=2":
                return Resp({"ret": 8})
            return Resp({"ret": 0})

    server = _PerCityServer()
    gw = GatewayClient(58, server, sleep=lambda s: None)
    t1 = BuildingTask(gw, city_id=101, plans=[], max_slots=3, auto_comfort=False, auto_boost=False)
    t2 = BuildingTask(gw, city_id=102, plans=[BuildingPlan(pid=4, gid=4, target_level=10)], max_slots=3, auto_comfort=False, auto_boost=False)

    shared = gw.page_building(101)
    t1.set_c77_cache(shared)
    t2.set_c77_cache(shared)

    assert t1.run_once() == "all_buildings_completed"
    assert t2.run_once() == "slots_busy"
    assert [d for k, d in server.calls if k == "/api/building/update" and str(d.get("cityTentId")) == "102"] == []


def test_building_task_rechecks_slots_and_stops_on_unexpected_opt65_failure_when_full():
    # Khi server thực tế đã đủ 3 công trình đang xây (ví dụ queue vừa đầy sau lần check đầu),
    # nếu OPT.ashx?id=65 trả lỗi bất thường (ngoài 261/245/36/32/37), task phải kiểm tra lại slot
    # và dừng ngay thay vì spam OPT.ashx?id=65 cho các công trình khác trong danh sách.
    c77_responses = [
        {"ret": 0, "list": [[101, "NB", 0, 1000, [[1, 1, 5, 1, 120], [2, 2, 5, 1, 240]], []]]},
        {"ret": 0, "list": [[101, "NB", 0, 1000, [[1, 1, 5, 1, 120], [2, 2, 5, 1, 240], [3, 3, 5, 1, 360]], []]]},
    ]
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": lambda: c77_responses.pop(0),
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [4, 4, "Kho", 5, 0, 0],
                    [5, 5, "Dân cư", 5, 0, 0],
                    [6, 6, "Trại gỗ", 5, 0, 0],
                ],
            },
            "OPT.ashx?id=65": {"ret": 29},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        BuildingPlan(pid=4, gid=4, target_level=10),
        BuildingPlan(pid=5, gid=5, target_level=10),
        BuildingPlan(pid=6, gid=6, target_level=10),
    ]
    task = BuildingTask(gw, city_id=101, plans=plans, max_slots=3, auto_comfort=False, auto_boost=False)

    out = task.run_once()
    assert out == "slots_busy"
    opt65_calls = [d for k, d in server.calls if k == "/api/building/update"]
    assert len(opt65_calls) == 1


def test_chest_catalog_and_resource_box_constants():
    assert len(CHEST_MAPPING) == 33
    assert len(NO_SWITCH_CHESTS) == 17
    assert set(NO_SWITCH_CHESTS).issubset(set(CHEST_MAPPING.keys()))
    assert 6 in RESOURCE_BOX_NAMES
    assert "Dân Sinh Bảo Phiên" in RESOURCE_BOX_NAMES[6]
    assert DEFAULT_FALLBACK_BOX_ORDER == [24, 16, 11, 6, 1]


def test_open_single_chest_api48_with_and_without_city_switch():
    # 1. Rương cần chuyển thành (Dân Sinh Bảo Nang -> id=1)
    server = FakeServer(handlers={"/api/city/current": {"ret": 0}, "Common.ashx?id=48": {"ret": 0}})
    gw = GatewayClient(58, server, sleep=lambda s: None)
    assert chest_needs_city_switch("民生之囊 - Dân Sinh Bảo Nang") is True

    ok, ret, _msg = open_single_chest(gw, "民生之囊 - Dân Sinh Bảo Nang", city_id=101)
    assert (ok, ret) == (True, 0)
    assert [k for k, _ in server.calls] == ["/api/city/current", "Common.ashx?id=48"]
    assert server.calls[0][1]["cityTentId"] == "101"
    assert server.calls[1][1]["lBoxID"] == "1"

    # 2. Từ chối mở rương cần chuyển thành nếu city_id là Doanh trại (<= 0) hoặc None
    server.calls.clear()
    ok_camp, ret_camp, _ = open_single_chest(gw, "民生之囊 - Dân Sinh Bảo Nang", city_id=-1085)
    assert ok_camp is False
    assert ret_camp == -2
    assert server.calls == []

    # 3. Rương cấp tài khoản (Phúc Khoán Bảo Nang -> id=5, không chuyển thành)
    server.calls.clear()
    assert chest_needs_city_switch("福券之囊 - Phúc Khoán Bảo Nang") is False
    ok2, ret2, _ = open_single_chest(gw, "福券之囊 - Phúc Khoán Bảo Nang", city_id=None)
    assert (ok2, ret2) == (True, 0)
    assert [k for k, _ in server.calls] == ["Common.ashx?id=48"]
    assert server.calls[0][1]["lBoxID"] == "5"


def test_open_single_chest_special_gift_pack_api69():
    server = FakeServer(handlers={"OPT.ashx?id=69": {"ret": 0}})
    gw = GatewayClient(58, server, sleep=lambda s: None)

    chest = "金碧辉煌礼包 - Kim Bích Huy Hoàng Lễ Bao"
    assert chest_needs_city_switch(chest) is False
    ok, ret, _ = open_single_chest(gw, chest, city_id=101)
    assert (ok, ret) == (True, 0)
    assert [k for k, _ in server.calls] == ["OPT.ashx?id=69"]
    payload = server.calls[0][1]
    assert payload["type"] == "33"
    assert payload["param1"] == "222"
    assert payload["param2"] == "0"
    assert payload["paytype"] == "1"


def test_run_batch_open_chest_bulk_api_success():
    """Trên Server 58+, các rương thuộc bulkAllowed dùng Optimization.ashx?action=bulk-start + bulk-status."""
    recorded_calls = []

    class _BulkServer:
        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1]
            recorded_calls.append((key, dict(data or {})))
            if key == "Optimization.ashx?action=capabilities":
                return Resp({"ret": 0, "bulkEnabled": True, "bulkMax": 99, "bulkAllowed": [5]})
            if key == "Optimization.ashx?action=bulk-start":
                return Resp({
                    "ret": 0,
                    "requestId": (data or {})["requestId"],
                    "boxId": 5,
                    "planned": 10,
                    "completed": 10,
                    "state": 1,
                })
            return Resp({"ret": 0})

    gw = GatewayClient(58, _BulkServer(), sleep=lambda s: None)
    logs = []
    progress_events = []

    summary = run_batch_open_chest(
        gateway=gw,
        chest_name="福券之囊 - Phúc Khoán Bảo Nang",
        times=10,
        max_workers=5,
        on_log=logs.append,
        on_progress=lambda d, t, p: progress_events.append((d, t, p)),
    )

    assert summary["success_count"] == 10
    assert summary["completed"] == 10
    assert summary["aborted_reason"] is None
    bulk_calls = [d for k, d in recorded_calls if k == "Optimization.ashx?action=bulk-start"]
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["boxId"] == "5"
    assert bulk_calls[0]["limit"] == "10"
    assert progress_events[-1] == (10, 10, 100.0)


def test_run_batch_open_chest_bulk_aborts_on_8108_out_of_stock():
    chest_name = "神武之囊 - Thần Vũ Bảo Nang"
    box_id = int(CHEST_MAPPING[chest_name])

    class _OutServer:
        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1]
            if key == "Optimization.ashx?action=capabilities":
                return Resp({"ret": 0, "bulkEnabled": True, "bulkMax": 99, "bulkAllowed": [box_id]})
            if key == "Optimization.ashx?action=bulk-start":
                return Resp({"ret": 8108, "errMsg": "没有可用宝箱或配套钥匙。"})
            return Resp({"ret": 0})

    gw = GatewayClient(58, _OutServer(), sleep=lambda s: None)
    logs = []
    summary = run_batch_open_chest(
        gateway=gw,
        chest_name=chest_name,
        times=30,
        on_log=logs.append,
    )
    assert summary["aborted_reason"] == "out_of_stock"
    assert summary["last_ret"] == 8108
    assert summary["completed"] == 0


def test_run_batch_open_chest_fallback_single_when_bulk_disabled_and_aborts_on_captcha():
    class _CaptchaServer:
        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1]
            if key == "Optimization.ashx?action=capabilities":
                return Resp({"ret": 0, "bulkEnabled": False, "bulkAllowed": []})
            return Resp({"ret": 110})

    gw = GatewayClient(58, _CaptchaServer(), sleep=lambda s: None)
    stop_ev = threading.Event()
    logs = []
    summary = run_batch_open_chest(
        gateway=gw,
        chest_name="神武之囊 - Thần Vũ Bảo Nang",
        times=20,
        max_workers=5,
        stop_event=stop_ev,
        on_log=logs.append,
    )

    assert summary["aborted_reason"] == "captcha"
    assert stop_ev.is_set() is True
    assert any("Captcha" in m for m in logs)


def test_process_speedup_skips_non_speeduppable_buildings_and_avoids_ret_1_spam():
    """Quan Phủ (1), Thành Tường (2), Cung Điện (54), Bích Lũy (55) và công trình NPC (22..53) không hỗ trợ tăng tốc;
    process_speedup phải bỏ qua chúng để tránh gọi OPT.ashx?id=69 gây lỗi ret=1 lặp lại, trong khi vẫn tăng tốc công trình hợp lệ.
    """
    server = FakeServer(
        handlers={
            "/api/city/pagebuilding": {
                "ret": 0,
                "data": {
                    "ret": 0,
                    "plus_finish": 1000,
                    "list": [
                        [
                            10129,
                            "1",
                            738765,
                            2792887,
                            [
                                [8, 1, 9, 1, 7200],   # Quan Phủ (gid=1) -> không tăng tốc
                                [0, 2, 5, 1, 7200],   # Thành Tường (gid=2) -> không tăng tốc
                                [2, 54, 1, 1, 7200],  # Cung Điện (gid=54) -> không tăng tốc
                                [3, 55, 1, 1, 7200],  # Bích Lũy (gid=55) -> không tăng tốc
                                [4, 22, 1, 1, 7200],  # Công trình NPC (gid=22..53) -> không tăng tốc
                                [9, 3, 6, 1, 7200],   # Dân Phòng (gid=3) -> hợp lệ, giảm 50% (7200 -> 3600 <= 3600)
                            ],
                            [],
                        ]
                    ],
                },
            },
            "OPT.ashx?id=69": lambda: {"ret": 0}
            if server.calls[-1][1].get("param1") == "9"
            else {"ret": 1, "errMsg": "操作失败，请稍后再试"},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    logs: list[str] = []
    task = BuildingTask(gw, city_id=10129, plans=[], auto_speedup=True, speedup_hours=1.0, paytype=2, notify=logs.append)

    speedup_count = task.process_speedup()
    assert speedup_count == 1

    calls = [d for k, d in server.calls if k == "OPT.ashx?id=69" and d.get("type") == "1"]
    assert len(calls) == 1
    assert calls[0]["param1"] == "9"
    assert calls[0]["param2"] == "10129"
    assert not any("Tăng tốc thất bại" in line for line in logs)



def _instant_speedup_server(initial_left: int):
    state = {"left": initial_left}

    def opt69():
        t = server.calls[-1][1].get("type")
        if t == "1":
            state["left"] //= 2
        elif t == "2":
            state["left"] = max(0, state["left"] - 3600)
        return {"ret": 0}

    def pagebuilding():
        slots = [[9, 3, 6, 1, state["left"]]] if state["left"] > 0 else []
        return {"ret": 0, "data": {"ret": 0, "plus_finish": 1000, "list": [[10129, "1", 1, 1, slots, []]]}}

    server = FakeServer(handlers={"/api/city/pagebuilding": pagebuilding, "OPT.ashx?id=69": opt69})
    return server, state


@pytest.mark.parametrize("hours", [0, -1])
@pytest.mark.parametrize(
    "initial,expected_types",
    [(20000, ["1", "1", "1", "2"]), (7200, ["1", "2"]), (3600, ["2"]), (300, ["2"])],
)
def test_process_speedup_instant_when_hours_not_positive(hours, initial, expected_types):
    server, state = _instant_speedup_server(initial)
    gw = GatewayClient(58, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=10129, plans=[], auto_speedup=True, speedup_hours=hours, paytype=2)

    task.process_speedup()

    types = [d["type"] for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert types == expected_types
    assert state["left"] == 0


def test_process_speedup_positive_hours_does_not_use_one_hour_item():
    server, state = _instant_speedup_server(20000)
    gw = GatewayClient(58, server, sleep=lambda s: None)
    task = BuildingTask(gw, city_id=10129, plans=[], auto_speedup=True, speedup_hours=1.0, paytype=2)

    task.process_speedup()

    types = [d["type"] for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert set(types) == {"1"}
    assert 0 < state["left"] <= 3600


def test_building_task_aborts_open_box_when_city_switch_fails():

    """Nếu /api/city/current thất bại (vd ret=8600), không mở rương vào sai thành."""
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
            "City.ashx?id=5": {"ret": 0, "infos": [[1, 1, "Quan Phủ", 10, 0, 0]]},
            "OPT.ashx?id=65": {"ret": 32},
            "City.ashx?id=50": {"ret": 8600, "errMsg": "请求未发送"},
            "Common.ashx?id=48": {"ret": 0},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    logs: list[str] = []
    task = BuildingTask(
        gw,
        city_id=10254,
        plans=[BuildingPlan(pid=1, gid=1, target_level=12)],
        auto_comfort=False,
        auto_boost=False,
        auto_open_box=True,
        box_id=24,
        notify=logs.append,
    )
    out = task.run_once()
    assert out == "insufficient_resources"
    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 0
    assert any("chuyển" in line.lower() for line in logs)
