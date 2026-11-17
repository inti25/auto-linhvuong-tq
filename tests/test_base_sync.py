"""Kiểm thử Đồng Bộ Danh Sách Căn Cứ trên AccountSession (Headless/Web) & AutomationEngine."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from linhvuong.engine import AutomationEngine, TaskStatus
from linhvuong.roster import City, Roster
from linhvuong.runtime import AccountSession
from linhvuong.tasks.building import BuildingPlan, BuildingTask


def test_account_session_reload_roster_prunes_stale_cities_and_saves_json(tmp_path):
    profile_path = tmp_path / "auto_profile_quilia_58.json"
    profile_path.write_text(
        json.dumps(
            {
                "version": 1,
                "building": {
                    "cities": {
                        "10129": {
                            "name": "Cũ",
                            "enabled": False,
                            "resource": False,
                            "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}],
                        },
                        "10229": {
                            "name": "",
                            "enabled": True,
                            "resource": True,
                            "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}],
                        },
                        "10230": {
                            "name": "",
                            "enabled": True,
                            "resource": True,
                            "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}],
                        },
                    }
                },
                "research": {"city_id": 10229},
                "resource": {"resource_cities": [10229, 10230]},
                "binh_man": {
                    "current_base_id": 10229,
                    "bases": {
                        "10129": {"name": "Cũ", "enabled": False, "parent_city_id": "10229"},
                        "10229": {"name": "", "enabled": True},
                    },
                },
                "crafting": {
                    "cities": {
                        "10129": {"city_id": 10129, "enabled": False},
                        "10229": {"city_id": 10229, "enabled": True},
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    events: list[tuple[str, dict]] = []
    sess = AccountSession(
        account_key="quilia @ S58",
        session=requests.Session(),
        server_id=58,
        username="quilia",
        data_dir=tmp_path,
        event_cb=lambda _k, ev, payload: events.append((ev, payload)),
    )

    live_roster = Roster(
        cities=[
            City(id=10129, name="1", type="Thành", pos_x=200, pos_y=96),
            City(id=10254, name="TT", type="Thành", pos_x=180, pos_y=67),
        ],
        camps=[],
    )
    with patch("linhvuong.runtime.fetch_roster", return_value=live_roster):
        sess.reload_roster()

    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    assert list(saved["building"]["cities"].keys()) == ["10129", "10254"]
    assert saved["building"]["cities"]["10129"]["name"] == "1"
    assert saved["building"]["cities"]["10129"]["enabled"] is False
    assert saved["building"]["cities"]["10254"]["name"] == "TT"
    assert saved["building"]["cities"]["10254"]["enabled"] is False
    assert saved["resource"]["resource_cities"] == []
    assert saved["research"]["city_id"] == 10129
    assert list(saved["binh_man"]["bases"].keys()) == ["10129"]
    assert saved["binh_man"]["bases"]["10129"]["parent_city_id"] == "10129"
    assert list(saved["crafting"]["cities"].keys()) == ["10129"]
    assert any(ev == "profile_updated" for ev, _ in events)


def test_account_session_start_tasks_ignore_stale_cities_in_profile(tmp_path):
    profile_path = tmp_path / "auto_profile_quilia_58.json"
    profile_path.write_text(
        json.dumps(
            {
                "version": 1,
                "building": {
                    "cities": {
                        "10129": {
                            "name": "1",
                            "enabled": True,
                            "resource": True,
                            "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}],
                        },
                        "10229": {
                            "name": "",
                            "enabled": True,
                            "resource": True,
                            "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}],
                        },
                    }
                },
                "resource": {"resource_cities": [10229]},
                "crafting": {"cities": {"10229": {"city_id": 10229, "enabled": True}}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sess = AccountSession(
        account_key="quilia @ S58",
        session=requests.Session(),
        server_id=58,
        username="quilia",
        data_dir=tmp_path,
    )
    # Giả lập roster thực tế chỉ có 10129 nhưng profile trong bộ nhớ vẫn còn 10229 (vd: vừa load từ ngoài)
    sess.roster = Roster(cities=[City(id=10129, name="1", type="Thành")], camps=[])

    captured_tasks = []
    with patch.object(sess.engine, "start", side_effect=lambda _tid, tasks, **_kw: captured_tasks.extend(tasks)):
        sess.start_building()

    assert [t.city_id for t in captured_tasks] == [10129]

    with pytest.raises(ValueError, match="ít nhất 1 thành"):
        sess.start_crafting()


def test_engine_prunes_city_not_found_from_building_task_list():
    gw = MagicMock()

    def _gw_call(endpoint, cmd_id, params=None):
        if endpoint == "Common.ashx" and cmd_id == 77:
            return {"ret": 0, "list": []}
        if endpoint == "Build.ashx" and cmd_id == 2:
            return {"ret": 0, "list": []}
        if endpoint == "City.ashx" and cmd_id == 5:
            cid = int((params or {}).get("tid", 0) or 0)
            if cid == 10229:
                return {"ret": 4, "infos": []}
            return {"ret": 0, "infos": [{"pid": 1, "gid": 1, "level": 20, "name": "Quan Phủ"}]}
        return {"ret": 0}

    gw.call.side_effect = _gw_call

    t_dead = BuildingTask(gw, city_id=10229, plans=[BuildingPlan(1, 1, 20)], auto_comfort=False, auto_boost=False)
    t_live = BuildingTask(gw, city_id=10129, plans=[BuildingPlan(1, 1, 20)], auto_comfort=False, auto_boost=False)

    statuses = []
    engine = AutomationEngine(on_status=lambda _tid, st: statuses.append(st))
    tasks = [t_dead, t_live]
    engine.start("building", tasks, interval=0.05, jitter=0.0)
    runner = engine._runners["building"]
    runner.join(timeout=3.0)

    assert t_dead not in tasks
    assert TaskStatus.COMPLETED in statuses
