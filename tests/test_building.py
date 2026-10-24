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

    upgrade_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert len(upgrade_calls) == 3
    called_pids = [c["pid"] for c in upgrade_calls]
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
    upgrade_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert len(upgrade_calls) == 2
    called_pids = [c["pid"] for c in upgrade_calls]
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

    # Kiểm tra gọi OPT.ashx?id=65 với pid=2, gid=3, type="2" (hạ cấp)
    opt_call = [d for k, d in server.calls if k == "OPT.ashx?id=65"][0]
    assert opt_call["pid"] == "2"
    assert opt_call["gid"] == "3"
    assert opt_call["type"] == "2"
    assert opt_call["tid"] == "101"


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

    opt_call = [d for k, d in server.calls if k == "OPT.ashx?id=65"][0]
    assert opt_call["pid"] == "1"
    assert opt_call["gid"] == "1"
    assert opt_call["type"] == "2"
    assert opt_call["tid"] == "101"


def test_building_task_downgrade_with_auto_speedup():
    # Q4: Cơ chế tăng tốc áp dụng đồng bộ cho cả hạ cấp
    server = FakeServer(
        handlers={
            "Common.ashx?id=77": {"ret": 0, "list": []},
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
    task = BuildingTask(gw, city_id=101, plans=plans, auto_speedup=True, auto_comfort=False, auto_boost=False)
    out = task.run_once()
    assert out == "upgrading"

    # Kiểm tra gọi lệnh tăng tốc slot
    speedup_calls = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(speedup_calls) == 1
    assert speedup_calls[0]["type"] == "1"
    assert speedup_calls[0]["param1"] == "101"
    assert speedup_calls[0]["param2"] == "1"


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

    opt_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert len(opt_calls) == 2
    # Item 1: pid=1, type="1"
    assert opt_calls[0]["pid"] == "1"
    assert opt_calls[0]["type"] == "1"
    # Item 2: pid=2, type="2"
    assert opt_calls[1]["pid"] == "2"
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

    # Kiểm tra gọi City.ashx?id=50 với tid=101
    switch_calls = [d for k, d in server.calls if k == "City.ashx?id=50"]
    assert len(switch_calls) == 1
    assert switch_calls[0]["tid"] == "101"

    # Kiểm tra gọi Common.ashx?id=48 mở Dân Sinh Bảo Đỉnh (lBoxID=24)
    box_calls = [d for k, d in server.calls if k == "Common.ashx?id=48"]
    assert len(box_calls) == 1
    assert box_calls[0]["lBoxID"] == "24"

    # Kiểm tra gọi OPT.ashx?id=65 2 lần (lần 1 bị 32, lần 2 thành công)
    upgrade_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
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
    opt_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert len(opt_calls) == 2
    assert opt_calls[0]["pid"] == "1"
    assert opt_calls[1]["pid"] == "2"


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

    opt_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert len(opt_calls) == 4
    assert [c["pid"] for c in opt_calls] == ["1", "2", "3", "4"]


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
    calls_cycle1 = [d["pid"] for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert calls_cycle1 == ["1", "2", "3"]

    # Vòng lặp 2: (pid 3 đã lên cấp 10 tức là đã xong)
    city_infos[2][3] = 10  # pid 3 level = 10 -> completed
    server.calls.clear()

    res2 = task.run_once()
    assert res2 == "upgrading"
    calls_cycle2 = [d["pid"] for k, d in server.calls if k == "OPT.ashx?id=65"]
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
    calls_default = [d["pid"] for k, d in server_default.calls if k == "OPT.ashx?id=65"]
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
    calls_even = [d["pid"] for k, d in server_even.calls if k == "OPT.ashx?id=65"]
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
    upgrade_call = [d for k, d in server.calls if k == "OPT.ashx?id=65"][0]
    assert upgrade_call["pid"] == "12"
    assert upgrade_call["gid"] == "3"


def test_building_task_skips_resource_starved_building_and_builds_next_eligible():
    def opt_handler():
        call = server.calls[-1]
        data = call[1]
        if data.get("pid") == "1":
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

    opt_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert len(opt_calls) == 2
    assert opt_calls[0]["pid"] == "1"
    assert opt_calls[1]["pid"] == "2"

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
        if data.get("pid") == "1":
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

    opt_calls = [d for k, d in server.calls if k == "OPT.ashx?id=65"]
    assert len(opt_calls) == 3
    assert opt_calls[0]["pid"] == "1"
    assert opt_calls[1]["pid"] == "2"
    assert opt_calls[2]["pid"] == "1"
