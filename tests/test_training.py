"""Kiểm thử module miền Đào Tạo Tướng trên Server 58+ (linhvuong/tasks/training.py)."""

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
    r.cities = [City(id=10129, name="inca", type="Thành")]
    r.camps = [City(id=-1085, name="Go", type="Doanh trại")]
    r._generals = {
        10129: [
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
    assert resolve_training_city_id(r, fallback_city_id=10254) == 10254

    r.cities = [City(id=10129, name="inca", type="Thành")]
    assert resolve_training_city_id(r) == 10129


def test_fetch_training_state_uses_tid_and_parses_slots():
    gw = MagicMock()
    gw.call.return_value = {
        "ret": 0,
        "slots": 2,
        "list": [[1, 86398, 6351, 2050, "I_10"]],
        "hero": [[6330, 2050, "I_01"]],
    }
    st = fetch_training_state(gw, TRAIN_TYPE_VO, 10129)
    gw.call.assert_called_once_with("Common.ashx", 141, {"lType": "2", "tid": "10129", "_": ""})
    assert st.train_type == TRAIN_TYPE_VO
    assert st.unlocked_slots == 2
    assert len(st.slots) == 5
    assert st.slots[0].unlocked is True
    assert st.slots[0].remaining_seconds == 86398
    assert st.slots[0].hero_id == 6351
    assert st.slots[0].hero_name == "I_10"
    assert st.slots[1].unlocked is True and st.slots[1].remaining_seconds == 0
    assert st.slots[2].unlocked is False
    assert st.slots[3].unlocked is False
    assert st.slots[4].unlocked is False
    assert st.active_hero_ids() == {6351}
    assert [s.pos for s in st.free_slots()] == [2]
    assert st.min_active_remaining() == 86398

    with pytest.raises(ValueError):
        fetch_training_state(gw, TRAIN_TYPE_VO, 0)
    with pytest.raises(ValueError):
        fetch_training_state(gw, TRAIN_TYPE_VO, -1085)

    gw.call.return_value = {"ret": 110}
    with pytest.raises(CaptchaRequired):
        fetch_training_state(gw, TRAIN_TYPE_VAN, 10129)


def test_start_general_training_tid_and_s58_errmsg():
    gw = MagicMock()
    gw.call.return_value = {"ret": 0, "exp": 1930}
    ok, ret, exp, msg = start_general_training(gw, TRAIN_TYPE_VAN, 1, 201, city_id=10129)
    gw.call.assert_called_once_with(
        "OPT.ashx",
        178,
        {"lType": "1", "lPos": "1", "lHeroID": "201", "_": "", "tid": "10129"},
    )
    assert (ok, ret, exp, msg) == (True, 0, 1930, "Thành công")

    gw.call.return_value = {"ret": 20, "errMsg": "人物ID不存在"}
    ok2, r2, e2, m2 = start_general_training(gw, TRAIN_TYPE_VO, 1, 999999999, city_id=10254)
    assert (ok2, r2, e2) == (False, 20, 0)
    assert "人物ID不存在" in m2

    gw.call.return_value = {"ret": 999, "errMsg": "S58 custom err"}
    ok3, r3, _, m3 = start_general_training(gw, TRAIN_TYPE_VO, 1, 101)
    assert (ok3, r3) == (False, 999)
    assert "S58 custom err" in m3

    for code in (1, 40, 315, 316):
        gw.call.return_value = {"ret": code}
        ok_c, r_code, r_exp, r_msg = start_general_training(gw, TRAIN_TYPE_VO, 2, 102)
        assert ok_c is False
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
        TRAIN_TYPE_VO: {"slots": 2, "list": [[1, 1200, 101, 4008, "Triệu Vân"]]},
        TRAIN_TYPE_VAN: {"slots": 1, "list": []},
    }

    def fake_call(ep, oid, payload=None):
        p = dict(payload or {})
        calls.append((ep, oid, p))
        if ep == "Common.ashx" and oid == 141:
            assert p.get("tid") == "10129"
            t = int(p["lType"])
            return {"ret": 0, **hall_state[t], "hero": []}
        if ep == "OPT.ashx" and oid == 178:
            assert p.get("tid") == "10129"
            t = int(p["lType"])
            pos = int(p["lPos"])
            hid = int(p["lHeroID"])
            if hid == 102:
                return {"ret": 315}  # Đã đạt cấp tối đa -> fallback sang 103
            hall_state[t]["list"].append([pos, 86400, hid, 4000, f"H{hid}"])
            return {"ret": 0, "exp": 1110}
        return {"ret": 0}

    gw = MagicMock()
    gw.call.side_effect = fake_call

    summary = run_training_cycle(
        gw,
        10129,
        vo_general_ids=[101, 102, 103, 201],  # 101 đang chạy, 102 max cấp, 103 OK, 201 sai role bị bỏ qua
        van_general_ids=[201, 202],
        roster=roster,
        on_log=logs.append,
    )

    # Tuyệt đối không bao giờ gọi OPT.ashx?id=177
    assert all(not (ep == "OPT.ashx" and oid == 177) for ep, oid, _ in calls)
    assert [(r.train_type, r.pos, r.hero_id, r.exp) for r in summary.trained] == [
        (TRAIN_TYPE_VO, 2, 103, 1110),
        (TRAIN_TYPE_VAN, 1, 201, 1110),
    ]
    assert any(r.hero_id == 102 and r.ret == 315 for r in summary.failed)
    assert 101 in summary.skipped
    assert 201 in summary.skipped  # sai role ở hall võ
    assert any("+1,110 kinh nghiệm" in line for line in logs)
    assert summary.states[TRAIN_TYPE_VO].min_active_remaining() == 1200
    assert summary.states[TRAIN_TYPE_VAN].min_active_remaining() == 86400
    assert summary.next_check_seconds == 1202.0


def test_run_training_cycle_stops_slot_on_ret1_and_no_spam_scheduler():
    gw = MagicMock()
    gw.call.side_effect = [
        {"ret": 0, "slots": 1, "list": []},
        {"ret": 1, "errMsg": "操作失败，请稍后再试"},
        {"ret": 0, "slots": 1, "list": []},
    ]
    summary = run_training_cycle(gw, 10129, vo_general_ids=[101, 102], van_general_ids=[])
    assert len(summary.trained) == 0
    assert len(summary.failed) == 1
    assert summary.failed[0].ret == 1
    assert "操作失败" in summary.failed[0].message
    # Không gọi thêm 102 vào cùng slot 1 sau khi slot trả ret=1
    assert gw.call.call_count == 3

    # Khi slots > len(selected_generals) và mọi tướng chọn đang hồi -> chờ min_active_remaining + 2
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
    s_multi_wait = compute_next_training_check_seconds(
        {TRAIN_TYPE_VO: s_multi},
        vo_general_ids=[101],
        van_general_ids=[],
        failed_results=[],
        max_poll_seconds=3600.0,
    )
    assert s_multi_wait <= 102.0

    # Lỗi tạm 316 -> retry 300s
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
