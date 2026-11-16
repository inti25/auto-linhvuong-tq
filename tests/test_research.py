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
        self.cookies = {"uid": "95"}

    def _dispatch(self, key, payload):
        self.calls.append((key, dict(payload or {})))
        handler = self.handlers.get(key, {"ret": 0})
        if callable(handler):
            return Resp(handler(dict(payload or {})))
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)

    def get(self, url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        return self._dispatch(path, params)

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        return self._dispatch(key, data)


def test_research_task_dispatches_first_eligible_tech():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 5, "m_lgid": 6, "m_llevel": 17}]}},
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    {"id": 1, "level": 10},
                    {"id": 2, "level": 5},
                ],
            },
            "/api/city/current": {"ret": 0},
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    plans = [
        TechPlan(tech_id=1, target_level=12, name="Làm thực"),
        TechPlan(tech_id=2, target_level=10, name="Rèn sắt"),
    ]
    task = ResearchTask(gw, city_id=2001, plans=plans, auto_art_of_war=False)
    out = task.run_once()
    assert out == "researching"

    research_call = [d for k, d in server.calls if k == "OPT.ashx?id=44"][0]
    assert research_call["techid"] == "1"
    assert research_call["tid"] == "2001"


def test_research_task_busy_when_ongoing():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {"techid": 5, "time_left": 1200}},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
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
    gw = GatewayClient(58, server, sleep=lambda s: None)
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
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 5, "m_lgid": 6, "m_llevel": 17}]}},
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    {"id": 1, "level": 10},
                ],
            },
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
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
    gw = GatewayClient(58, server, sleep=lambda s: None)
    task = ResearchTask(gw, city_id=2001, plans=[])
    with pytest.raises(CaptchaRequired):
        task.run_once()


def test_research_task_real_server_format_and_university_detection():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": [0, 0, 0]},
            "/api/building/list": {
                "ret": 0,
                "data": {
                    "items": [
                        {"m_lpos": 1, "m_lgid": 1, "m_szname": "官府", "m_llevel": 20},
                        {"m_lpos": 5, "m_lgid": 6, "m_szname": "大学殿", "m_llevel": 17},
                    ]
                },
            },
            "Build.ashx?id=2": {
                "ret": 0,
                "list": [
                    [1, "种植技巧", 10, 6, 11, 3, 1, 2430],
                    [2, "冶炼技巧", 8, 6, 9, 3, 1, 2430],
                ],
            },
            "/api/city/current": {"ret": 0},
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    plans = [
        TechPlan(tech_id=1, target_level=12, name="种植技巧 - làm thực"),
        TechPlan(tech_id=2, target_level=10, name="冶炼技巧 - rèn sắt"),
    ]
    task = ResearchTask(gw, city_id=15230, plans=plans, auto_art_of_war=False)

    univ_pid = task.get_university_pid()
    assert univ_pid == 5

    levels = task.get_current_tech_levels()
    assert levels[1] == 10
    assert levels[2] == 8

    is_busy, cur_tid = task.is_research_ongoing()
    assert is_busy is False
    assert cur_tid is None

    out = task.run_once()
    assert out == "researching"

    opt44_calls = [d for k, d in server.calls if k == "OPT.ashx?id=44"]
    assert len(opt44_calls) == 1
    assert opt44_calls[0]["techid"] == "1"
    assert opt44_calls[0]["tid"] == "15230"


def test_get_current_tech_levels_requires_city_switch():
    current_focused_city = None

    def handle_city_cur(data):
        nonlocal current_focused_city
        current_focused_city = data.get("cityTentId")
        return {"ret": 0}

    def handle_build_2(data):
        if current_focused_city != data.get("tid"):
            return {"ret": 8}
        return {
            "ret": 0,
            "list": [
                [1, "种植技巧", 15, 6, 16, 3, 1, 2430],
                [2, "冶炼技巧", 12, 6, 13, 3, 1, 2430],
            ],
        }

    server = FakeServer(
        handlers={
            "/api/city/current": handle_city_cur,
            "Build.ashx?id=2": handle_build_2,
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 5, "m_lgid": 6, "m_llevel": 20}]}},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    task = ResearchTask(gw, city_id=21936, plans=[])

    levels = task.get_current_tech_levels()
    assert levels == {1: 15, 2: 12}


def test_research_task_handles_no_university():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "/api/city/current": {"ret": 0},
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 1, "m_lgid": 1, "m_llevel": 20}]}},
            "Build.ashx?id=2": {"ret": 8},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
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
            return {"ret": 245}
        if techid == "2":
            return {"ret": 0}
        return {"ret": 0}

    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "/api/city/current": {"ret": 0},
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 5, "m_lgid": 6, "m_llevel": 20}]}},
            "Build.ashx?id=2": {"ret": 0, "list": [[1, "Tech1", 5], [2, "Tech2", 3]]},
            "OPT.ashx?id=44": handle_opt44,
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    plans = [
        TechPlan(tech_id=1, target_level=10, name="Tech1"),
        TechPlan(tech_id=2, target_level=10, name="Tech2"),
    ]
    task = ResearchTask(gw, city_id=21936, plans=plans)
    out = task.run_once()
    assert out == "researching"
    assert calls_opt44 == ["1", "2"]


def test_research_task_even_research_ordering():
    calls_default = []
    calls_even = []

    def make_server(calls_list):
        def handle_opt44(data):
            calls_list.append(data.get("techid"))
            return {"ret": 261}

        return FakeServer(
            handlers={
                "City.ashx?id=37": {"ret": 0, "tech": {}},
                "/api/city/current": {"ret": 0},
                "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 5, "m_lgid": 6, "m_llevel": 20}]}},
                "Build.ashx?id=2": {
                    "ret": 0,
                    "list": [
                        [1, "Tech1", 7],
                        [2, "Tech2", 2],
                        [3, "Tech3", 4],
                        [4, "Tech4", 2],
                    ],
                },
                "OPT.ashx?id=44": handle_opt44,
            }
        )

    plans = [
        TechPlan(tech_id=1, target_level=10, name="Tech1"),
        TechPlan(tech_id=2, target_level=10, name="Tech2"),
        TechPlan(tech_id=3, target_level=10, name="Tech3"),
        TechPlan(tech_id=4, target_level=10, name="Tech4"),
    ]

    gw_default = GatewayClient(58, make_server(calls_default), sleep=lambda s: None)
    task_default = ResearchTask(gw_default, city_id=21936, plans=plans, even_research=False)
    task_default.run_once()
    assert calls_default == ["1", "2", "3", "4"]

    gw_even = GatewayClient(58, make_server(calls_even), sleep=lambda s: None)
    task_even = ResearchTask(gw_even, city_id=21936, plans=plans, even_research=True)
    task_even.run_once()
    assert calls_even == ["2", "4", "3", "1"]


def test_research_task_on_sync_data_callback():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "/api/city/current": {"ret": 0},
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 5, "m_lgid": 6, "m_llevel": 20}]}},
            "Build.ashx?id=2": {"ret": 0, "list": [[1, "Tech1", 5], [2, "Tech2", 3]]},
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
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
    assert synced_events[0][2] is None


def test_research_task_syncs_on_first_cycle_even_if_busy():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": [1, 5, 120]},
            "/api/city/current": {"ret": 0},
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 5, "m_lgid": 6, "m_llevel": 20}]}},
            "Build.ashx?id=2": {"ret": 0, "list": [[1, "Tech1", 5], [2, "Tech2", 3]]},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
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
    assert synced_events[0][2] == (True, 1)


def test_research_task_supports_thai_hoc_dien_gid_59():
    server = FakeServer(
        handlers={
            "City.ashx?id=37": {"ret": 0, "tech": {}},
            "/api/city/current": {"ret": 0},
            "/api/building/list": {"ret": 0, "data": {"items": [{"m_lpos": 7, "m_lgid": 59, "m_llevel": 20}]}},
            "Build.ashx?id=2": {"ret": 0, "list": [[1, "Tech1", 5], [2, "Tech2", 3]]},
            "OPT.ashx?id=44": {"ret": 0},
        }
    )
    gw = GatewayClient(58, server, sleep=lambda s: None)
    plans = [TechPlan(tech_id=1, target_level=10)]
    task = ResearchTask(gw, city_id=21936, plans=plans)

    univ_pid = task.get_university_pid()
    assert univ_pid == 7

    levels = task.get_current_tech_levels()
    assert levels == {1: 5, 2: 3}

    build_calls = [d for k, d in server.calls if k == "Build.ashx?id=2"]
    assert len(build_calls) == 1
    assert build_calls[0]["pid"] == "7"
    assert build_calls[0]["gid"] == "59"
