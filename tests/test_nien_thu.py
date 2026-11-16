"""Tests for Niên Thú event automation on Server 58+."""

from datetime import datetime
import time

import pytest

from linhvuong.engine import AutomationEngine, TaskStatus
from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import CaptchaRequired, TaskContext
from linhvuong.tasks.nien_thu import (
    NienThuTarget,
    NienThuTask,
    NpcCityExpedition,
    attack_nien_thu,
    find_nien_thu_in_state,
    get_npc_city_expedition,
    has_ngoc_tho_jade,
    scan_all_states_for_nien_thu,
    speedup_npc_expedition,
)
from linhvuong.world_chat import (
    STATE_IDS,
    STATE_NAMES,
    NienThuAnnouncement,
    WorldChatClient,
    parse_nien_thu_announcement,
)


def test_parse_nien_thu_announcement_maps_all_16_states():
    assert len(STATE_NAMES) == 16
    assert STATE_IDS["徐州"] == 13
    assert STATE_IDS["凉州"] == 1
    assert STATE_IDS["西域"] == 16

    item = {
        "kind": "notice",
        "text": "年兽已在徐州附近出现，请各位勇士速速前往挑战！",
        "sourceId": 1776,
        "createdAt": 1794805570913,
    }
    ann = parse_nien_thu_announcement(item)
    assert ann is not None
    assert ann.state_id == 13
    assert ann.state_name == "徐州"
    assert ann.source_id == 1776
    assert "年兽已在徐州附近出现" in ann.raw_message


def test_parse_nien_thu_announcement_ignores_unrelated_system_messages():
    item = {"kind": "notice", "text": "恭喜玩家 张志文 通过游历探索获得：名将【陈泰】", "sourceId": 1776}
    assert parse_nien_thu_announcement(item) is None


def test_world_chat_client_fetches_latest_nien_thu_from_notify_history():
    history_payload = {
        "ret": 0,
        "items": [
            {"kind": "notice", "text": "年兽已在鲜卑附近出现，请各位勇士速速前往挑战！", "sourceId": 100, "createdAt": 1794800000000},
            {"kind": "notice", "text": "恭喜玩家 张志文 获得白金礼盒", "sourceId": 101, "createdAt": 1794800100000},
            {"kind": "notice", "text": "年兽已在徐州附近出现，请各位勇士速速前往挑战！", "sourceId": 102, "createdAt": 1794800200000},
        ],
    }
    gw = GatewayClient(58, _FullFakeServer(lambda ep, d: history_payload), sleep=lambda s: None)
    ann = WorldChatClient().fetch_latest_nien_thu(gw)

    assert ann is not None
    assert ann.state_id == 13
    assert ann.state_name == "徐州"
    assert ann.source_id == 102



class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeServer:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []

    def post(self, url, data=None, headers=None, timeout=None):
        endpoint = url.split("/GateWay/")[1]
        payload_in = dict(data or {})
        self.calls.append((endpoint, payload_in))
        return _Resp(self.handler(endpoint, payload_in))


def _make_gateway(handler):
    server = _FakeServer(handler)
    return GatewayClient(53, server, sleep=lambda s: None), server


def test_has_ngoc_tho_jade_detects_item_5001_and_missing():
    gw, server = _make_gateway(
        lambda ep, data: {"ret": 0, "curr": [0, 0, 0, 0], "list": [[5001, 2], [5002, 1]]}
    )
    found, count = has_ngoc_tho_jade(gw)
    assert found is True
    assert count == 2
    assert server.calls[0][0] == "Common.ashx?id=142"

    gw2, _ = _make_gateway(lambda ep, data: {"ret": 0, "curr": [0, 0, 0, 0], "list": []})
    assert has_ngoc_tho_jade(gw2) == (False, 0)


def test_find_and_scan_nien_thu_in_states_and_raises_on_captcha():
    def handler(ep, data):
        sid = int(data["lStatID"])
        if sid == 13:
            return {"ret": 0, "list": [[2683, 641, 0, "张燕"], [3101, 712, 0, "年兽"]]}
        return {"ret": 0, "list": [[2603, 358, 0, "马元义"]]}

    gw, server = _make_gateway(handler)
    target = find_nien_thu_in_state(gw, 13)
    assert target == NienThuTarget(
        state_id=13, npc_id=3101, head_id=712, name="年兽", status_flag=0
    )

    # Preferred state avoids scanning 1..16
    server.calls.clear()
    preferred = scan_all_states_for_nien_thu(gw, preferred_state_id=13)
    assert preferred == target
    assert len(server.calls) == 1

    # Fallback scans 1..13 and stops once found
    server.calls.clear()
    scanned = scan_all_states_for_nien_thu(gw)
    assert scanned == target
    assert len(server.calls) == 13

    gw_cap, _ = _make_gateway(lambda ep, data: {"ret": 73})
    with pytest.raises(CaptchaRequired):
        find_nien_thu_in_state(gw_cap, 1)


def test_get_npc_city_expedition_parses_infos_states():
    gw, _ = _make_gateway(
        lambda ep, data: {
            "ret": 0,
            "battle": [0, 0],
            "infos": [13, 556, -51, 3101, "年兽", 1, 580, 103242, "TC2_03", 0, 20000, 0, 0, 0],
        }
    )
    exp = get_npc_city_expedition(gw, 13, 3101)
    assert exp == NpcCityExpedition(
        state_id=13,
        x=556,
        y=-51,
        npc_id=3101,
        npc_name="年兽",
        mission_state=1,
        remaining_seconds=580,
        general_id=103242,
        general_name="TC2_03",
        battle_id=0,
    )


def test_attack_nien_thu_and_speedup_send_exact_endpoints():
    gw, server = _make_gateway(lambda ep, data: {"ret": 0})
    ok, ret = attack_nien_thu(gw, state_id=13, npc_id=3101, general_id=103242)
    assert (ok, ret) == (True, 0)
    assert server.calls[0][0] == "OPT.ashx?id=162"
    assert server.calls[0][1]["lStateID"] == "13"
    assert server.calls[0][1]["lNpcID"] == "3101"
    assert server.calls[0][1]["lGeneralID"] == "103242"

    ok_sp, ret_sp = speedup_npc_expedition(gw)
    assert (ok_sp, ret_sp) == (True, 0)
    assert server.calls[1][0] == "OPT.ashx?id=167"



class _FullFakeServer(_FakeServer):
    def __init__(self, handler, cookies=None):
        super().__init__(handler)
        self.cookies = cookies or {"uid": "95"}

    def get(self, url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        p = dict(params or {})
        self.calls.append((path, p))
        return _Resp(self.handler(path, p))


def _make_ctx(handler):
    server = _FullFakeServer(handler)
    gw = GatewayClient(58, server, sleep=lambda s: None)
    locks = TargetLocks()
    logs: list[str] = []
    ctx = TaskContext(
        gateway=gw,
        scanner=Scanner(gw, locks),
        locks=locks,
        notify=logs.append,
    )
    return ctx, server, logs


class _FakeChatClient:
    def __init__(self, ann):
        self._ann = ann
        self.called = 0

    def fetch_latest_nien_thu(self, gateway):
        self.called += 1
        return self._ann


def test_nien_thu_task_stops_immediately_when_stop_on_jade_finds_5001():
    def handler(ep, data):
        if ep == "Common.ashx?id=142":
            return {"ret": 0, "list": [[5001, 1]]}
        raise AssertionError(f"Unexpected call after jade found: {ep}")

    ctx, _, logs = _make_ctx(handler)
    completed_cb = []
    task = NienThuTask(
        ctx=ctx,
        general_ids=[103242],
        stop_on_jade=True,
        sleep_fn=lambda s: None,
        on_completed=lambda: completed_cb.append(True),
    )

    engine = AutomationEngine()
    engine.start("nien_thu", task, interval=0.05, jitter=0.0)
    time.sleep(0.2)

    assert engine.get_status("nien_thu") == TaskStatus.COMPLETED
    assert completed_cb == [True]
    assert any("5001" in m or "玉兔呈祥" in m for m in logs)


def test_nien_thu_task_uses_world_chat_picks_idle_general_and_caps_speedup():
    exp_calls = [0]

    def handler(ep, data):
        if ep == "Common.ashx?id=126":
            assert data["lStatID"] == "13"
            return {"ret": 0, "list": [[3101, 712, 0, "年兽"]]}
        if ep == "Common.ashx?id=127":
            exp_calls[0] += 1
            if exp_calls[0] == 1:
                return {"ret": 0, "infos": [0] * 14}
            if exp_calls[0] == 2:
                return {
                    "ret": 0,
                    "infos": [13, 556, -51, 3101, "年兽", 1, 300, 103242, "G2", 0, 0, 0, 0, 0],
                }
            return {
                "ret": 0,
                "infos": [13, 556, -51, 3101, "年兽", 1, 45, 103242, "G2", 0, 0, 0, 0, 0],
            }
        if ep == "/api/city/pageofficial":
            # General 101 busy (16), general 102 idle (0)
            return {"ret": 0, "data": {"ret": 0, "list": [[21936, "Thanh", 0, 0, [[101, "G1", 0, 0, 0, 16], [102, "G2", 0, 0, 0, 0]]]]}}
        if ep == "OPT.ashx?id=162":
            return {"ret": 0}
        if ep == "OPT.ashx?id=167":
            return {"ret": 0}
        raise AssertionError(f"Unexpected endpoint {ep}")

    ctx, server, _ = _make_ctx(handler)
    chat_ann = NienThuAnnouncement(13, "徐州", "2026-11-14 09:00:00", "年兽已在徐州附近出现", source_id=1776)
    fake_chat = _FakeChatClient(chat_ann)
    seen_anns = []
    now = datetime(2026, 11, 14, 8, 2, 0)  # local 08:02

    task = NienThuTask(
        ctx=ctx,
        general_ids=[101, 102],
        speed_up_march=True,
        use_world_chat=True,
        now_fn=lambda: now,
        sleep_fn=lambda s: None,
        chat_client_factory=lambda: fake_chat,
        on_announcement=seen_anns.append,
    )

    res = task.run_step()
    assert res == "attacked:13:3101"
    assert fake_chat.called == 1
    assert seen_anns == [chat_ann]

    opt162 = [d for ep, d in server.calls if ep == "OPT.ashx?id=162"]
    assert len(opt162) == 1
    assert opt162[0]["lStateID"] == "13"
    assert opt162[0]["lNpcID"] == "3101"
    assert opt162[0]["lGeneralID"] == "102"

    # Called OPT 167 once, then stopped because remaining_seconds dropped to 45 (<= 60)
    opt167 = [d for ep, d in server.calls if ep == "OPT.ashx?id=167"]
    assert len(opt167) == 1


def test_nien_thu_task_hourly_dedup_and_top_of_hour_schedule():
    def handler(ep, data):
        if ep == "Common.ashx?id=126":
            return {"ret": 0, "list": [[3101, 712, 0, "年兽"]] if data["lStatID"] == "5" else []}
        if ep == "Common.ashx?id=127":
            return {"ret": 0, "infos": [0] * 14}
        if ep == "/api/city/pageofficial":
            return {"ret": 0, "data": {"ret": 0, "list": [[21936, "T", 0, 0, [[102, "G2", 0, 0, 0, 0]]]]}}
        if ep == "OPT.ashx?id=162":
            return {"ret": 0}
        raise AssertionError(f"Unexpected {ep}")

    ctx, server, _ = _make_ctx(handler)
    clock = [datetime(2026, 11, 14, 8, 5, 0)]
    task = NienThuTask(
        ctx=ctx,
        general_ids=[102],
        use_world_chat=False,
        run_immediately=True,
        now_fn=lambda: clock[0],
        sleep_fn=lambda s: None,
    )

    assert task.run_step() == "attacked:5:3101"
    calls_after_first = len(server.calls)

    # Same hour -> skips until top of next hour
    clock[0] = datetime(2026, 11, 14, 8, 10, 0)
    assert task.run_step() == "waiting_next_hour"
    assert len(server.calls) == calls_after_first

    # Top of next hour -> runs new cycle
    clock[0] = datetime(2026, 11, 14, 9, 0, 2)
    assert task.run_step() == "attacked:5:3101"


def test_nien_thu_task_respects_run_immediately_false_until_next_hour():
    ctx, server, _ = _make_ctx(lambda ep, data: {"ret": 0})
    clock = [datetime(2026, 11, 14, 8, 15, 0)]
    task = NienThuTask(
        ctx=ctx,
        general_ids=[102],
        use_world_chat=False,
        run_immediately=False,
        now_fn=lambda: clock[0],
        sleep_fn=lambda s: None,
    )
    assert task.run_step() == "waiting_next_hour"
    assert len(server.calls) == 0


def test_nien_thu_task_speeds_up_return_when_expedition_returning_and_avoids_overwrite():
    def handler(ep, data):
        if ep == "Common.ashx?id=126":
            return {"ret": 0, "list": [[3101, 712, 0, "年兽"]] if data["lStatID"] == "5" else []}
        if ep == "Common.ashx?id=127":
            # mission_state=3 returning, 420s left
            return {
                "ret": 0,
                "infos": [5, 354, 252, 3101, "年兽", 3, 420, 102, "G2", 0, 0, 0, 0, 0],
            }
        if ep == "OPT.ashx?id=167":
            return {"ret": 0}
        raise AssertionError(f"Unexpected {ep}")

    ctx, server, _ = _make_ctx(handler)
    task = NienThuTask(
        ctx=ctx,
        general_ids=[102],
        use_world_chat=False,
        speed_up_return=True,
        now_fn=lambda: datetime(2026, 11, 14, 9, 0, 1),
        sleep_fn=lambda s: None,
    )
    res = task.run_step()
    assert res == "expedition_busy:returning"
    assert not any(ep == "OPT.ashx?id=162" for ep, _ in server.calls)
    assert any(ep == "OPT.ashx?id=167" for ep, _ in server.calls)
