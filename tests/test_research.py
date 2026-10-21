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

