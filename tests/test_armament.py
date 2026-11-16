"""Unit tests cho linhvuong.armament (Đồng Bộ Quân Giới, ADR-0039)."""

import threading

from linhvuong.armament import (
    SCOPE_BOWMAN,
    SCOPE_INFANTRY,
    SCOPE_MANGONEL,
    armament_matches,
    merge_armament,
    parse_armament,
    sync_armament,
)
from linhvuong.roster import City, General, Roster


def _resp(inf=(301, 101, 0), cav=(401, 101, 0), bow=(201, 301, 0), mang=501, arr=1):
    def blk(t):
        return [0, t[0], f"n{t[0]}", t[1], f"n{t[1]}", t[2], f"n{t[2]}" if t[2] else "", 1, 2, 3]

    return {
        "ret": 0,
        "infantry_equip": blk(inf),
        "cavalry_equip": blk(cav),
        "bowman_equip": blk(bow),
        "mangonel": [mang, f"n{mang}", 0],
        "battle_array": arr,
        "ratio_attack": 50,
        "ratio_PK": 20,
        "ratio_stratagem": 30,
        "withdraw_loss": 25,
        "withdraw_morale": 35,
    }


class FakeGateway:
    def __init__(self, configs, ret56=0):
        self.configs = configs  # gid -> resp dict
        self.ret56 = ret56
        self.calls = []

    def call(self, endpoint, op_id, payload=None, **_kw):
        payload = payload or {}
        self.calls.append((endpoint, op_id, dict(payload)))
        if endpoint == "Common.ashx" and op_id == 12:
            return self.configs.get(int(payload["lGeneralID"]), {"ret": 20})
        if endpoint == "OPT.ashx" and op_id == 56:
            return {"ret": self.ret56}
        if endpoint == "OPT.ashx" and op_id == 57:
            return {"ret": 0}
        return {"ret": 1}

    def ops(self, op_id):
        return [c for c in self.calls if c[1] == op_id and c[0] == "OPT.ashx"]


def _gen(gid, status=0, role="vo"):
    return General(
        id=gid, name=f"G{gid}", role=role, level=10, morale=100, stamina=100, stamina_max=100, status=status
    )


def _roster(*gens):
    r = Roster(cities=[City(id=100, name="T1")])
    r._generals[100] = list(gens)
    return r


def test_parse_armament_extracts_slots_and_formation():
    snap = parse_armament(_resp(inf=(353, 108, 0), mang=0, arr=3))
    assert snap.infantry == (353, 108, 0)
    assert snap.mangonel == 0
    assert snap.battle_array == 3
    assert snap.ratio_pk == 20
    assert snap.label(SCOPE_INFANTRY) == "n353"
    assert parse_armament({"ret": 20}) is None


def test_merge_keeps_unselected_scopes():
    tmpl = parse_armament(_resp(inf=(353, 108, 0), bow=(258, 353, 0)))
    cur = parse_armament(_resp())
    merged = merge_armament(cur, tmpl, [SCOPE_INFANTRY])
    assert merged.infantry == (353, 108, 0)
    assert merged.bowman == cur.bowman
    assert merged.cavalry == cur.cavalry


def test_matches_respects_scope_and_formation():
    tmpl = parse_armament(_resp(bow=(258, 353, 0), arr=2))
    cur = parse_armament(_resp(arr=1))
    assert armament_matches(cur, tmpl, [SCOPE_INFANTRY])
    assert not armament_matches(cur, tmpl, [SCOPE_BOWMAN])
    assert armament_matches(cur, tmpl, [SCOPE_INFANTRY], sync_formation=False)
    assert not armament_matches(cur, tmpl, [SCOPE_INFANTRY], sync_formation=True)


def test_sync_copies_selected_scope_only_and_skips_template_busy_same():
    tmpl_resp = _resp(inf=(353, 108, 0), bow=(258, 353, 0), arr=2)
    gw = FakeGateway({1: tmpl_resp, 2: _resp(), 3: _resp(), 4: tmpl_resp})
    roster = _roster(_gen(1), _gen(2), _gen(3, status=16), _gen(4), _gen(5, role="van"))
    logs = []
    summary = sync_armament(
        gw, roster, 1, [1, 2, 3, 4], scopes=[SCOPE_INFANTRY], on_log=logs.append
    )
    assert summary.synced == 1
    assert summary.skipped_template == 1
    assert summary.skipped_busy == 1
    assert summary.skipped_same == 1
    calls56 = gw.ops(56)
    assert len(calls56) == 1
    p = calls56[0][2]
    assert p["lGeneralID"] == "2"
    assert (p["lInfantryEID1"], p["lInfantryEID2"]) == ("353", "108")
    # binh chủng không tích giữ nguyên của tướng đích
    assert (p["lBowmanEID1"], p["lBowmanEID2"]) == ("201", "301")
    assert p["lMangonelEID"] == "501"
    assert not gw.ops(57)


def test_sync_formation_preserves_ratios():
    tmpl_resp = _resp(arr=4)
    gw = FakeGateway({1: tmpl_resp, 2: _resp(arr=1)})
    roster = _roster(_gen(1), _gen(2))
    summary = sync_armament(gw, roster, 1, [2], scopes=[], sync_formation=True)
    assert summary.synced == 1
    assert not gw.ops(56)
    p = gw.ops(57)[0][2]
    assert p["lBattleArray"] == "4"
    assert (p["lRatioAttack"], p["lRatioPK"], p["lRatioStra"]) == ("50", "20", "30")
    assert (p["lWithdrawLoss"], p["lWithdrawMorale"]) == ("25", "35")


def test_sync_reports_stock_error_and_continues():
    tmpl_resp = _resp(inf=(353, 108, 0))
    gw = FakeGateway({1: tmpl_resp, 2: _resp(), 3: _resp()}, ret56=42)
    roster = _roster(_gen(1), _gen(2), _gen(3))
    logs = []
    summary = sync_armament(gw, roster, 1, [2, 3], on_log=logs.append)
    assert summary.failed == 2
    assert len(gw.ops(56)) == 2
    assert any("Kho quân giới" in m for m in logs)


def test_sync_stop_event():
    gw = FakeGateway({1: _resp(inf=(353, 108, 0)), 2: _resp()})
    roster = _roster(_gen(1), _gen(2))
    ev = threading.Event()
    ev.set()
    summary = sync_armament(gw, roster, 1, [2], stop_event=ev)
    assert summary.stopped
    assert not gw.ops(56)


def test_sync_missing_template():
    gw = FakeGateway({})
    summary = sync_armament(gw, _roster(_gen(2)), 99, [2])
    assert summary.failed == 1
    assert not gw.calls
