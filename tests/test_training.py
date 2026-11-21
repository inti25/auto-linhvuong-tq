"""Kiểm thử module miền Đào Tạo Tướng (linhvuong/tasks/training.py)."""

from unittest.mock import MagicMock

import pytest

from linhvuong.roster import City, General, Roster
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.tasks.training import (
    TRAIN_TYPE_VAN,
    TRAIN_TYPE_VO,
    TrainAttemptResult,
    TrainingHallState,
    TrainSlotStatus,
    compute_next_training_check_seconds,
    fetch_training_state,
    resolve_training_city_id,
    run_training_cycle,
    start_general_training,
)


def _sample_roster() -> Roster:
    r = Roster()
    r.cities = [City(id=15237, name="ThienNam", type="Thành")]
    r.camps = [City(id=-1085, name="Go", type="Doanh trại")]
    r._generals = {
        15237: [
            General(id=101, name="Triệu Vân", role="vo", level=150, morale=100, stamina=100, stamina_max=100),
            General(id=102, name="Quan Vũ", role="vo", level=140, morale=100, stamina=100, stamina_max=100),
            General(id=103, name="Trương Phi", role="vo", level=130, morale=100, stamina=100, stamina_max=100),
            General(id=201, name="Gia Cát Lượng", role="van", level=160, morale=100, stamina=100, stamina_max=100),
            General(id=202, name="Quách Gia", role="van", level=120, morale=100, stamina=100, stamina_max=100),
        ]
    }
    return r


def test_resolve_training_city_id_requires_positive_city():
    r = Roster()
    r.camps = [City(id=-1085, name="Go", type="Doanh trại")]
    assert resolve_training_city_id(r) is None
    assert resolve_training_city_id(r, fallback_city_id=-10) is None
    assert resolve_training_city_id(r, fallback_city_id=15230) == 15230

    r.cities = [City(id=15237, name="ThienNam", type="Thành")]
    assert resolve_training_city_id(r) == 15237


def test_fetch_training_state_parses_slots_and_guards():
    gw = MagicMock()
    gw.call.return_value = {
        "ret": 0,
        "slots": 3,
        "list": [[1, 3600, 101, 4008, "Triệu Vân"]],
        "hero": [[102, 4007, "Quan Vũ"]],
    }
    st = fetch_training_state(gw, TRAIN_TYPE_VO, 15237)
    gw.call.assert_called_once_with("Common.ashx", 141, {"lType": "2", "lCityID": "15237", "_": ""})
    assert st.train_type == TRAIN_TYPE_VO
    assert st.unlocked_slots == 3
    assert len(st.slots) == 5
    assert st.slots[0].unlocked is True
    assert st.slots[0].remaining_seconds == 3600
    assert st.slots[0].hero_id == 101
    assert st.slots[0].hero_name == "Triệu Vân"
    assert st.slots[1].unlocked is True and st.slots[1].remaining_seconds == 0
    assert st.slots[2].unlocked is True and st.slots[2].remaining_seconds == 0
    assert st.slots[3].unlocked is False
    assert st.slots[4].unlocked is False
    assert st.active_hero_ids() == {101}
    assert [s.pos for s in st.free_slots()] == [2, 3]
    assert st.min_active_remaining() == 3600

    with pytest.raises(ValueError):
        fetch_training_state(gw, TRAIN_TYPE_VO, 0)
    with pytest.raises(ValueError):
        fetch_training_state(gw, TRAIN_TYPE_VO, -1085)

    gw.call.return_value = {"ret": 110}
    with pytest.raises(CaptchaRequired):
        fetch_training_state(gw, TRAIN_TYPE_VAN, 15237)


def test_start_general_training_payload_and_errors():
    gw = MagicMock()
    gw.call.return_value = {"ret": 0, "exp": 500}
    ok, ret, exp, msg = start_general_training(gw, TRAIN_TYPE_VAN, 1, 201)
    gw.call.assert_called_once_with("OPT.ashx", 178, {"lType": "1", "lPos": "1", "lHeroID": "201", "_": ""})
    assert (ok, ret, exp, msg) == (True, 0, 500, "Thành công")

    for code in (1, 40, 315, 316):
        gw.call.return_value = {"ret": code}
        ok, r_code, r_exp, r_msg = start_general_training(gw, TRAIN_TYPE_VO, 2, 102)
        assert ok is False
        assert r_code == code
        assert r_exp == 0
        assert r_msg

    gw.call.return_value = {"ret": 73}
    with pytest.raises(CaptchaRequired):
        start_general_training(gw, TRAIN_TYPE_VO, 1, 101)


def test_run_training_cycle_multiple_slots_active_skip_and_fallback():
    roster = _sample_roster()
    logs: list[str] = []
    calls: list[tuple[str, int, dict]] = []
    hall_state = {
        TRAIN_TYPE_VO: {"slots": 3, "list": [[1, 1200, 101, 4008, "Triệu Vân"]]},
        TRAIN_TYPE_VAN: {"slots": 1, "list": []},
    }

    def fake_call(ep, oid, payload=None):
        p = dict(payload or {})
        calls.append((ep, oid, p))
        if ep == "Common.ashx" and oid == 141:
            t = int(p["lType"])
            return {"ret": 0, **hall_state[t], "hero": []}
        if ep == "OPT.ashx" and oid == 178:
            t = int(p["lType"])
            pos = int(p["lPos"])
            hid = int(p["lHeroID"])
            if hid == 102:
                return {"ret": 315}  # Đã đạt cấp tối đa -> fallback sang 103
            hall_state[t]["list"].append([pos, 86400, hid, 4000, f"H{hid}"])
            return {"ret": 0, "exp": 250}
        return {"ret": 0}

    gw = MagicMock()
    gw.call.side_effect = fake_call

    summary = run_training_cycle(
        gw,
        15237,
        vo_general_ids=[101, 102, 103, 201],  # 101 đang chạy, 102 max cấp, 103 OK, 201 sai role bị bỏ qua
        van_general_ids=[201, 202],
        roster=roster,
        on_log=logs.append,
    )

    # Tuyệt đối không bao giờ gọi OPT.ashx?id=177
    assert all(not (ep == "OPT.ashx" and oid == 177) for ep, oid, _ in calls)
    assert [(r.train_type, r.pos, r.hero_id, r.exp) for r in summary.trained] == [
        (TRAIN_TYPE_VO, 2, 103, 250),
        (TRAIN_TYPE_VAN, 1, 201, 250),
    ]
    assert any(r.hero_id == 102 and r.ret == 315 for r in summary.failed)
    assert 101 in summary.skipped
    assert 201 in summary.skipped  # sai role ở hall võ
    assert any("+250 kinh nghiệm" in line for line in logs)
    assert summary.states[TRAIN_TYPE_VO].min_active_remaining() == 1200
    assert summary.states[TRAIN_TYPE_VAN].min_active_remaining() == 86400
    assert summary.next_check_seconds == 1202.0


def test_run_training_cycle_stops_slot_on_ret1_and_no_spam_scheduler():
    gw = MagicMock()
    gw.call.side_effect = [
        {"ret": 0, "slots": 1, "list": []},
        {"ret": 1},  # slot 1 đang bận/lỗi
        {"ret": 0, "slots": 1, "list": []},
    ]
    summary = run_training_cycle(gw, 15237, vo_general_ids=[101, 102], van_general_ids=[])
    assert len(summary.trained) == 0
    assert len(summary.failed) == 1
    assert summary.failed[0].ret == 1
    # Không gọi thêm 102 vào cùng slot 1 sau khi slot trả ret=1
    assert gw.call.call_count == 3

    # Test compute_next_training_check_seconds khi slots > len(selected_generals)
    s_multi = TrainingHallState(
        train_type=TRAIN_TYPE_VO,
        unlocked_slots=3,
        slots=[
            TrainSlotStatus(pos=1, unlocked=True, remaining_seconds=100, hero_id=101, hero_name="A"),
            TrainSlotStatus(pos=2, unlocked=True, remaining_seconds=0),
            TrainSlotStatus(pos=3, unlocked=True, remaining_seconds=0),
        ],
        checked_at=0.0,
    )
    # Mock time so elapsed == 0
    s_multi_wait = compute_next_training_check_seconds(
        {TRAIN_TYPE_VO: s_multi},
        vo_general_ids=[101],
        van_general_ids=[],
        failed_results=[],
        max_poll_seconds=3600.0,
    )
    assert s_multi_wait <= 102.0

    # Test lỗi tạm 316 retry 300s
    s_free = TrainingHallState(
        train_type=TRAIN_TYPE_VO,
        unlocked_slots=1,
        slots=[TrainSlotStatus(pos=1, unlocked=True)],
        checked_at=0.0,
    )
    temp_wait = compute_next_training_check_seconds(
        {TRAIN_TYPE_VO: s_free},
        vo_general_ids=[101],
        van_general_ids=[],
        failed_results=[TrainAttemptResult(TRAIN_TYPE_VO, 1, 101, "A", False, 316, 0, "err")],
        max_poll_seconds=3600.0,
        retry_temp_error_seconds=300.0,
    )
    assert temp_wait == 300.0
