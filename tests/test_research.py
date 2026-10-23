import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.tasks.research import TechPlan, ResearchTask


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


def test_research_task_dispatches_first_eligible_tech():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},  # rảnh, không có tech đang chạy
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    {"id": 1, "level": 10},
                    {"id": 2, "level": 5},
                ],
            },
            "City.ashx?id=50": {"ret": 0},  # switch city
            "OPT.ashx?id=44": {"ret": 0},   # bắt đầu nghiên cứu
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [
        TechPlan(tech_id=1, target_level=12, name="Làm thực"),
        TechPlan(tech_id=2, target_level=10, name="Rèn sắt"),
    ]
    task = ResearchTask(gw, city_id=2001, plans=plans, auto_art_of_war=False)
    out = task.run_once()
    assert out == "researching"

    # Kiểm tra gọi OPT.ashx?id=44 với techid=1, tid=2001
    research_call = [d for k, d in server.calls if k == "OPT.ashx?id=44"][0]
    assert research_call["techid"] == "1"
    assert research_call["tid"] == "2001"


def test_research_task_busy_when_ongoing():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {"techid": 5, "time_left": 1200}},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [TechPlan(tech_id=1, target_level=10)]
    task = ResearchTask(gw, city_id=2001, plans=plans, auto_art_of_war=False)
    out = task.run_once()
    assert out == "research_busy"


def test_research_task_uses_art_of_war_when_busy():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {"techid": 5, "time_left": 1200}},
            "OPT.ashx?id=180": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [TechPlan(tech_id=1, target_level=10)]
    task = ResearchTask(gw, city_id=2001, plans=plans, auto_art_of_war=True)
    out = task.run_once()
    assert out == "art_of_war_used"

    art_calls = [d for k, d in server.calls if k == "OPT.ashx?id=180"]
    assert len(art_calls) == 1


def test_research_task_all_completed():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    {"id": 1, "level": 10},
                ],
            },
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [TechPlan(tech_id=1, target_level=10)]
    task = ResearchTask(gw, city_id=2001, plans=plans)
    out = task.run_once()
    assert out == "all_techs_completed"


def test_research_task_stops_on_captcha():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 110},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = ResearchTask(gw, city_id=2001, plans=[])
    with pytest.raises(CaptchaRequired):
        task.run_once()


def test_research_task_real_server_format_and_university_detection():
    server = FakeServer(
        handlers={
            # Format thật từ server: tech là mảng [tech_id, cur_level, time_left]
            "City.ashx?id=37": {"ret": 0, "tech": [0, 0, 0]},
            # Tìm Viện Đại Học trong thành (gid=6, pid=5)
            "City.ashx?id=5": {
                "ret": 0,
                "infos": [
                    [1, 1, "官府", 20, 0, 0],
                    [5, 6, "大学殿", 17, 0, 0],
                ],
            },
            # Build.ashx?id=2 trả về mảng các mảng [tech_id, name, level, ...]
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    [1, "种植技巧", 10, 6, 11, 3, 1, 2430],
                    [2, "冶炼技巧", 8, 6, 9, 3, 1, 2430],
                ],
            },
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(57, server, sleep=lambda s: None)
    plans = [
        TechPlan(tech_id=1, target_level=12, name="种植技巧 - làm thực"),
        TechPlan(tech_id=2, target_level=10, name="冶炼技巧 - rèn sắt"),
    ]
    task = ResearchTask(gw, city_id=15230, plans=plans, auto_art_of_war=False)
    
    # 1. Kiểm tra tìm Đại học điện
    univ_pid = task.get_university_pid()
    assert univ_pid == 5

    # 2. Kiểm tra đọc cấp độ công nghệ từ mảng
    levels = task.get_current_tech_levels()
    assert levels[1] == 10
    assert levels[2] == 8

    # 3. Kiểm tra kiểm tra trạng thái đang nghiên cứu
    is_busy, cur_tid = task.is_research_ongoing()
    assert is_busy is False
    assert cur_tid is None

    # 4. Kiểm tra dispatch nghiên cứu Tech 1
    out = task.run_once()
    assert out == "researching"

    opt44_calls = [d for k, d in server.calls if k == "OPT.ashx?id=44"]
    assert len(opt44_calls) == 1
    assert opt44_calls[0]["techid"] == "1"
    assert opt44_calls[0]["tid"] == "15230"


def test_get_current_tech_levels_requires_city_switch():
    current_focused_city = None

    def handle_city_50(data):
        nonlocal current_focused_city
        current_focused_city = data.get("tid")
        return {"ret": 0}

    def handle_build_2(data):
        # Server Linh Vương thật: nếu chưa switch tới tid tương ứng, trả về ret: 8
        if current_focused_city != data.get("tid"):
            return {"ret": 8}
        return {
            "ret": 0,
            "list": [
                [1, "种植技巧", 15, 6, 16, 3, 1, 2430],
                [2, "冶炼技巧", 12, 6, 13, 3, 1, 2430],
            ],
        }

    class CustomServer(FakeServer):
        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            self.calls.append((key, dict(data or {})))
            if key == "City.ashx?id=50":
                return Resp(handle_city_50(dict(data or {})))
            if key == "Build.ashx?id=2":
                return Resp(handle_build_2(dict(data or {})))
            if key == "City.ashx?id=5":
                return Resp({"ret": 0, "infos": [[5, 6, "大学殿", 20]]})
            return Resp({"ret": 0})

    server = CustomServer()
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = ResearchTask(gw, city_id=21936, plans=[])

    levels = task.get_current_tech_levels()
    assert levels == {1: 15, 2: 12}


def test_research_task_handles_no_university():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "City.ashx?id=50": {"ret": 0},
            "City.ashx?id=5": {"ret": 0, "infos": [[1, 1, "官府", 20]]},  # không có Đại Học
            "Build.ashx?id=2": {"ret": 8},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    task = ResearchTask(gw, city_id=21915, plans=[TechPlan(tech_id=1, target_level=10)])
    assert task.get_university_pid() is None
    levels = task.get_current_tech_levels()
    assert levels == {}
    assert task.run_once() == "tech_read_failed"


def test_research_task_skips_prerequisites_not_met_and_tries_next():
    calls_opt44 = []

    def handle_opt44(data):
        techid = data.get("techid")
        calls_opt44.append(techid)
        if techid == "1":
            return {"ret": 245}  # Tech 1 chưa đủ điều kiện tiên quyết
        if techid == "2":
            return {"ret": 0}    # Tech 2 thành công
        return {"ret": 0}

    class OptServer(FakeServer):
        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            self.calls.append((key, dict(data or {})))
            if key == "City.ashx?id=37":
                return Resp({"ret": 0, "tech": {}})
            if key == "City.ashx?id=50":
                return Resp({"ret": 0})
            if key == "City.ashx?id=5":
                return Resp({"ret": 0, "infos": [[5, 6, "大学殿", 20]]})
            if key == "Build.ashx?id=2":
                return Resp({"ret": 0, "list": [[1, "Tech1", 5], [2, "Tech2", 3]]})
            if key == "OPT.ashx?id=44":
                return Resp(handle_opt44(dict(data or {})))
            return Resp({"ret": 0})

    gw = GatewayClient(53, OptServer(), sleep=lambda s: None)
    plans = [
        TechPlan(tech_id=1, target_level=10, name="Tech1"),
        TechPlan(tech_id=2, target_level=10, name="Tech2"),
    ]
    task = ResearchTask(gw, city_id=21936, plans=plans)
    out = task.run_once()
    assert out == "researching"
    assert calls_opt44 == ["1", "2"]  # Tech 1 gặp 245, tự động bỏ qua và chuyển sang Tech 2 thành công


def test_research_task_even_research_ordering():
    calls_default = []
    calls_even = []

    def make_server(calls_list):
        class EvenServer(FakeServer):
            def post(self, url, data=None, headers=None, timeout=None):
                key = url.split("/GateWay/")[1]
                if key == "City.ashx?id=37":
                    return Resp({"ret": 0, "tech": {}})
                if key == "City.ashx?id=50":
                    return Resp({"ret": 0})
                if key == "City.ashx?id=5":
                    return Resp({"ret": 0, "infos": [[5, 6, "大学殿", 20]]})
                if key == "Build.ashx?id=2":
                    return Resp({
                        "ret": 0,
                        "list": [
                            [1, "Tech1", 7],
                            [2, "Tech2", 2],
                            [3, "Tech3", 4],
                            [4, "Tech4", 2],
                        ],
                    })
                if key == "OPT.ashx?id=44":
                    calls_list.append(dict(data or {}).get("techid"))
                    return Resp({"ret": 261})  # Giả lập fail để xem thứ tự duyệt hết
                return Resp({"ret": 0})
        return EvenServer()

    plans = [
        TechPlan(tech_id=1, target_level=10, name="Tech1"),
        TechPlan(tech_id=2, target_level=10, name="Tech2"),
        TechPlan(tech_id=3, target_level=10, name="Tech3"),
        TechPlan(tech_id=4, target_level=10, name="Tech4"),
    ]

    # 1. Khi even_research=False: Duyệt tuần tự theo bảng 1, 2, 3, 4
    gw_default = GatewayClient(53, make_server(calls_default), sleep=lambda s: None)
    task_default = ResearchTask(gw_default, city_id=21936, plans=plans, even_research=False)
    task_default.run_once()
    assert calls_default == ["1", "2", "3", "4"]

    # 2. Khi even_research=True:
    # Tech 2 (cấp 2) và Tech 4 (cấp 2) duyệt trước, giữ thứ tự 2 rồi tới 4.
    # Tiếp theo Tech 3 (cấp 4).
    # Cuối cùng Tech 1 (cấp 7).
    # Thứ tự kỳ vọng: ["2", "4", "3", "1"]
    gw_even = GatewayClient(53, make_server(calls_even), sleep=lambda s: None)
    task_even = ResearchTask(gw_even, city_id=21936, plans=plans, even_research=True)
    task_even.run_once()
    assert calls_even == ["2", "4", "3", "1"]


def test_research_task_on_sync_data_callback():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "City.ashx?id=50": {"ret": 0},
            "City.ashx?id=5": {"ret": 0, "infos": [[5, 6, "大学殿", 20]]},
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    [1, "Tech1", 5],
                    [2, "Tech2", 3],
                ],
            },
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [TechPlan(tech_id=1, target_level=10)]
    synced_events = []

    def on_sync(city_id, levels, tech_status):
        synced_events.append((city_id, levels, tech_status))

    task = ResearchTask(gw, city_id=21936, plans=plans, on_sync_data=on_sync)
    res = task.run_once()
    assert res == "researching"
    assert len(synced_events) == 1
    assert synced_events[0][0] == 21936
    assert synced_events[0][1] == {1: 5, 2: 3}
    assert synced_events[0][2] is None  # not busy


def test_research_task_syncs_on_first_cycle_even_if_busy():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": [1, 5, 120]},  # đang nghiên cứu tech 1
            "City.ashx?id=50": {"ret": 0},
            "City.ashx?id=5": {"ret": 0, "infos": [[5, 6, "大学殿", 20]]},
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    [1, "Tech1", 5],
                    [2, "Tech2", 3],
                ],
            },
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [TechPlan(tech_id=2, target_level=10)]
    synced_events = []

    def on_sync(city_id, levels, tech_status):
        synced_events.append((city_id, levels, tech_status))

    task = ResearchTask(gw, city_id=21936, plans=plans, auto_art_of_war=False, on_sync_data=on_sync)
    res = task.run_once()
    assert res == "research_busy"
    assert len(synced_events) == 1
    assert synced_events[0][0] == 21936
    assert synced_events[0][1] == {1: 5, 2: 3}
    assert synced_events[0][2] == (True, 1)  # is_busy=True, tech_id=1


def test_research_task_supports_thai_hoc_dien_gid_59():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "City.ashx?id=50": {"ret": 0},
            # Thành có Thái Học Điện (gid=59) ở ô đất pid=7
            "City.ashx?id=5": {"ret": 0, "infos": [[7, 59, "太学殿", 20]]},
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    [1, "Tech1", 5],
                    [2, "Tech2", 3],
                ],
            },
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(53, server, sleep=lambda s: None)
    plans = [TechPlan(tech_id=1, target_level=10)]
    task = ResearchTask(gw, city_id=21936, plans=plans)

    # 1. Nhận diện được Thái Học Điện (gid=59)
    univ_pid = task.get_university_pid()
    assert univ_pid == 7

    # 2. Đọc cấp độ kỹ thuật qua Build.ashx?id=2 với gid=59
    levels = task.get_current_tech_levels()
    assert levels == {1: 5, 2: 3}

    build_calls = [d for k, d in server.calls if k == "Build.ashx?id=2"]
    assert len(build_calls) == 1
    assert build_calls[0]["pid"] == "7"
    assert build_calls[0]["gid"] == "59"






