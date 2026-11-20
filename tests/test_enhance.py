"""Tests for Cường Hóa Trang Bị & Hủy Trang Bị trên Server 58+ (ADR-0045)."""

import threading
import pytest

from linhvuong.enhance import (
    CRYSTAL_COST_BY_LEVEL,
    PROP_CRYSTAL,
    PROP_HAMMER,
    PROP_IRON,
    EnhanceConfig,
    EnhanceResources,
    call_destroy_equipment,
    call_enhance_high,
    call_enhance_low,
    fetch_enhance_materials,
    fetch_enhance_resources,
    fetch_warehouse_equipment,
    level_after_low_failure,
    pick_next_enhance_item,
    run_destroy_batch,
    run_enhance_batch,
    select_materials_for_attempt,
    should_use_protect,
)
from linhvuong.gateway import GatewayClient
from linhvuong.tasks.base import CaptchaRequired


class RawResp:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def json(self):
        import json

        return json.loads(self.text)


class FakeGateway:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, int, dict]] = []
        self.opt_calls: list[tuple[str, dict]] = []

    def call(self, endpoint: str, api_id: int, data=None, **_kw):
        body = dict(data or {})
        self.calls.append((endpoint, api_id, body))
        return self.handler(endpoint, api_id, body)

    def optimization(self, action: str, data=None, **_kw):
        body = dict(data or {})
        self.opt_calls.append((action, body))
        return self.handler("Optimization.ashx", action, body)


def test_fetch_enhance_resources_with_gateway_relaxed_json_and_captcha():
    class Sess:
        def __init__(self, resps):
            self.resps = list(resps)

        def post(self, *_a, **_kw):
            return self.resps.pop(0)

    sess = Sess([
        RawResp("{ret:0,Table:[{gem_id:341,counts:25},{gem_id:342,counts:10},{gem_id:354,counts:150}]}"),
        RawResp('{"ret": 0, "table": [{"gem_id": 341, "counts": 7}]}'),
        RawResp('{"ret": 110}'),
    ])
    gw = GatewayClient(58, sess, sleep=lambda _s: None)

    r1 = fetch_enhance_resources(gw)
    assert r1 == EnhanceResources(iron=25, hammer=10, crystal=150)

    r2 = fetch_enhance_resources(gw)
    assert r2 == EnhanceResources(iron=7, hammer=0, crystal=0)

    with pytest.raises(CaptchaRequired):
        fetch_enhance_resources(gw)


def test_fetch_warehouse_equipment_paginates_filters_equipped_and_uses_zero_based_level():
    """Kho Server 58+ tải phân trang từ Optimization.ashx?action=equipment (>50 món, reset 8102, bỏ đồ đang mặc, cấp = row[7]+1)."""
    page0 = [[1000 + i, 1, 2109, 0, 0, 0, 0, 0, 0, ""] for i in range(49)]
    page0.append([1999, 1, 2142, 0, 0, 0, 0, 14, 99, "Lữ Bố"])  # Đang mặc -> bỏ qua
    page1 = [
        [2001, 2, 2109, 0, 0, 0, 0, 0, 0, ""],   # Võ Lv.1 (row[7]=0)
        [2002, 1, 2142, 0, 0, 0, 0, 8, 0, ""],   # Võ Lv.9 (row[7]=8)
        [2004, 1, 2217, 0, 0, 0, 0, 1, 0, ""],   # Văn Lv.2 (row[7]=1)
    ]
    rev_bumped = {"done": False}

    def _handler(ep, action, body):
        assert ep == "Optimization.ashx" and action == "equipment"
        assert body["kind"] == "1" and body["type"] == "2"
        p = int(body.get("page", 0))
        if p == 1 and not rev_bumped["done"]:
            rev_bumped["done"] = True
            return {"ret": 8102}
        return {
            "ret": 0,
            "list": page0 if p == 0 else page1,
            "page": p,
            "pageSize": 50,
            "total": 53,
            "revision": [10, 20],
        }

    gw = FakeGateway(_handler)
    grouped = fetch_warehouse_equipment(gw, 2)
    assert len(grouped["vo"]) == 51
    assert grouped["vo"][-1].item_id == 2002 and grouped["vo"][-1].level == 9
    assert [(it.item_id, it.level, it.quantity) for it in grouped["van"]] == [(2004, 2, 1)]

    with pytest.raises(CaptchaRequired):
        fetch_warehouse_equipment(FakeGateway(lambda *_a: {"ret": 110}), 1)


def test_fetch_enhance_materials_and_selection_prevent_duplicates_and_rollback():
    def _handler(ep, oid, body):
        assert ep == "Common.ashx" and oid == 117
        assert body["eid"] == "5001"
        return {
            "ret": 0,
            "list": [
                [5001, 1, 1104, 0, 0, 0, 0, 0],  # Trùng món đang ép -> không được bốc
                [5002, 2, 1104, 0, 0, 0, 0, 0],  # Stack 2 món cùng ID 5002 Lv.1
                [5003, 1, 1104, 0, 0, 0, 0, 0],  # Món thứ 3 khác ID Lv.1
                [5004, 1, 1106, 0, 0, 0, 0, 1],  # Lv.2
            ],
        }

    gw = FakeGateway(_handler)
    pool = fetch_enhance_materials(gw, 5001)
    assert [(g.key, g.count) for g in pool.groups] == [("1104:1", 4), ("1106:2", 1)]

    ok, ids, _used, missing = select_materials_for_attempt(pool, ("1104:1", "1104:1", ""), target_item_id=5001)
    assert ok is True
    assert missing is None
    assert ids == (5002, 5003, 0)

    ok2, _ids2, _used2, missing2 = select_materials_for_attempt(pool, ("1104:1", "1104:1", ""), target_item_id=5001)
    assert ok2 is False
    assert "1104" in missing2 or "Lv.1" in missing2

    ok3, ids3, _used3, _ = select_materials_for_attempt(pool, ("1104:1", "", ""), target_item_id=5001)
    assert ok3 is True and ids3 == (5002, 0, 0)


def test_protect_and_low_failure_level_rules():
    assert should_use_protect(4, None) is False
    assert should_use_protect(4, 5) is False
    assert should_use_protect(5, 5) is True
    assert should_use_protect(8, 7) is True
    assert should_use_protect(9, 7) is False

    assert [level_after_low_failure(lv, False) for lv in range(1, 9)] == [1, 2, 2, 3, 4, 1, 1, 1]
    assert [level_after_low_failure(lv, True) for lv in range(1, 9)] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_run_enhance_batch_crosses_level_9_and_drops_materials():
    """Ép liền mạch từ cấp 6 lên 11: chặng 6->9 dùng ID=154 + Phôi + Búa; từ cấp 9 dùng ID=188 + Pha Lê, bỏ Phôi."""
    mat_list = [[7001, 5, 1104, 0, 0, 0, 0, 0]]
    low_results = iter([299, 0, 0, 0])   # 6(fail+búa=6), 6->7, 7->8, 8->9
    high_results = iter([325, 0, 0])     # 9(fail=9), 9->10, 10->11

    def _handler(ep, oid, _body):
        if ep == "Common.ashx" and oid == 2:
            return {
                "ret": 0,
                "Table": [
                    {"gem_id": PROP_IRON, "counts": 20},
                    {"gem_id": PROP_HAMMER, "counts": 20},
                    {"gem_id": PROP_CRYSTAL, "counts": 50},
                ],
            }
        if ep == "Common.ashx" and oid == 117:
            return {"ret": 0, "list": mat_list}
        if ep == "OPT.ashx" and oid == 154:
            return {"ret": next(low_results)}
        if ep == "OPT.ashx" and oid == 188:
            return {"ret": next(high_results)}
        return {"ret": 0}

    gw = FakeGateway(_handler)
    cfg = EnhanceConfig(
        equip_type=1,
        role="vo",
        item_id=9001,
        item_type_id=1135,
        start_level=6,
        target_level=11,
        protect_from_level=6,
        material_from_level=7,
        material_keys=("1104:1", "", ""),
        loop_count=1,
    )
    summary = run_enhance_batch(gw, cfg, sleep=lambda _s: None)

    assert summary.completed_items == 1
    assert summary.final_level == 11
    assert summary.iron_used == 4
    assert summary.hammer_used == 4
    assert summary.material_used == 2
    assert summary.crystal_used == 20

    low_calls = [body for ep, oid, body in gw.calls if ep == "OPT.ashx" and oid == 154]
    high_calls = [body for ep, oid, body in gw.calls if ep == "OPT.ashx" and oid == 188]
    assert len(low_calls) == 4
    assert [c["lSrcEquipID1"] for c in low_calls] == ["0", "0", "7001", "7001"]
    assert all(c["lPropProtect"] == "342" for c in low_calls)
    assert len(high_calls) == 3
    assert all(c["EquipID"] == "9001" for c in high_calls)


def test_run_enhance_batch_fail_closed_when_hammer_runs_out():
    """Hết Búa Bảo Hộ khi đang ở mốc bảo hộ -> dừng tuyệt đối, không ép trần."""
    def _handler(ep, oid, _body):
        if ep == "Common.ashx" and oid == 2:
            return {
                "ret": 0,
                "Table": [
                    {"gem_id": PROP_IRON, "counts": 10},
                    {"gem_id": PROP_HAMMER, "counts": 0},
                    {"gem_id": PROP_CRYSTAL, "counts": 0},
                ],
            }
        return {"ret": 0}

    gw = FakeGateway(_handler)
    cfg = EnhanceConfig(
        equip_type=2,
        role="vo",
        item_id=8001,
        item_type_id=2142,
        start_level=7,
        target_level=9,
        protect_from_level=7,
        loop_count=1,
    )
    summary = run_enhance_batch(gw, cfg, sleep=lambda _s: None)
    assert summary.completed_items == 0
    assert summary.total_attempts == 0
    assert "Búa" in summary.stop_reason
    assert not any(ep == "OPT.ashx" for ep, _oid, _b in gw.calls)


def test_run_enhance_batch_multi_item_and_network_retry_sync():
    """Ép 2 món liên tiếp qua Optimization.ashx?action=equipment và retry lỗi mạng kèm đồng bộ cấp thật."""
    warehouse_state = [
        [3001, 1, 1104, 0, 0, 0, 0, 0, 0, ""],  # Lv.1 (món đầu)
        [3002, 1, 1104, 0, 0, 0, 0, 2, 0, ""],  # Lv.3 (đã >= đích -> phải bỏ qua!)
        [3003, 1, 1104, 0, 0, 0, 0, 0, 0, ""],  # Lv.1 (món thứ 2 hợp lệ)
    ]
    synced_once = {"done": False}

    def _handler(ep, oid, body):
        if ep == "Common.ashx" and oid == 2:
            return {"ret": 0, "Table": [{"gem_id": PROP_IRON, "counts": 20}]}
        if ep == "Optimization.ashx" and oid == "equipment":
            return {"ret": 0, "list": [list(r) for r in warehouse_state], "page": 0, "pageSize": 50, "total": len(warehouse_state), "revision": [1, 1]}
        if ep == "OPT.ashx" and oid == 154:
            eid = int(body["lDstEquipID"])
            if eid == 3001 and not synced_once["done"]:
                synced_once["done"] = True
                warehouse_state[0][7] = 1
                return None
            for r in warehouse_state:
                if r[0] == eid:
                    r[7] += 1
            return {"ret": 0}
        return {"ret": 0}

    gw = FakeGateway(_handler)
    cfg = EnhanceConfig(
        equip_type=1,
        role="vo",
        item_id=3001,
        item_type_id=1104,
        start_level=1,
        target_level=3,
        protect_from_level=None,
        loop_count=3,
    )
    summary = run_enhance_batch(gw, cfg, sleep=lambda _s: None)
    assert summary.completed_items == 2
    assert "Hết món cùng loại" in summary.stop_reason
    opt_targets = [int(b["lDstEquipID"]) for ep, oid, b in gw.calls if ep == "OPT.ashx" and oid == 154]
    assert opt_targets == [3001, 3001, 3003, 3003]


def test_run_destroy_batch_handles_stacks_stop_and_captcha():
    rows = [[4001, 2, 1104, 0, 0, 0, 0, 0, 0, ""]]

    def _handler(ep, oid, body):
        if ep == "Optimization.ashx" and oid == "equipment":
            return {"ret": 0, "list": [list(r) for r in rows], "page": 0, "pageSize": 50, "total": len(rows), "revision": [1, 1]}
        if ep == "OPT.ashx" and oid == 17:
            assert body["lEquipID"] in ("4001", "4002")
            if rows[0][1] > 1:
                rows[0] = [4002, 1, 1104, 0, 0, 0, 0, 0, 0, ""]
            else:
                rows.clear()
            return {"ret": 0}
        return {"ret": 0}

    gw = FakeGateway(_handler)
    summary = run_destroy_batch(
        gw,
        equip_type=1,
        role="vo",
        start_item_id=4001,
        item_type_id=1104,
        target_level=1,
        quantity=2,
        sleep=lambda _s: None,
    )
    assert summary.destroyed == 2
    assert summary.failed == 0
    assert [int(b["lEquipID"]) for ep, oid, b in gw.calls if ep == "OPT.ashx" and oid == 17] == [4001, 4002]

    gw_cap = FakeGateway(lambda ep, oid, _b: {"ret": 110} if ep == "OPT.ashx" else {"ret": 0})
    with pytest.raises(CaptchaRequired):
        run_destroy_batch(
            gw_cap,
            equip_type=1,
            role="vo",
            start_item_id=4001,
            item_type_id=1104,
            target_level=1,
            quantity=1,
            sleep=lambda _s: None,
        )

    stop_ev = threading.Event()
    stop_ev.set()
    s_stop = run_destroy_batch(
        gw,
        equip_type=1,
        role="vo",
        start_item_id=4001,
        item_type_id=1104,
        target_level=1,
        quantity=2,
        stop_event=stop_ev,
        sleep=lambda _s: None,
    )
    assert s_stop.stopped is True
    assert s_stop.destroyed == 0


def test_call_enhance_high_formats_alliance_required_error_ret_27():
    """Mã ret=27 (联盟编号不存在) từ OPT.ashx?id=188 được diễn giải rõ sang tiếng Việt."""
    gw = FakeGateway(
        lambda ep, oid, _b: {"ret": 27, "errMsg": "联盟编号不存在"}
        if ep == "OPT.ashx" and oid == 188
        else {"ret": 0, "Table": [{"gem_id": PROP_CRYSTAL, "counts": 20}]}
    )
    ok, ret, msg = call_enhance_high(gw, 95937)
    assert ok is False
    assert ret == 27
    assert "Liên Minh" in msg and "联盟编号不存在" in msg

    cfg = EnhanceConfig(
        equip_type=2,
        role="vo",
        item_id=95937,
        item_type_id=2142,
        start_level=9,
        target_level=10,
        loop_count=1,
    )
    summary = run_enhance_batch(gw, cfg, sleep=lambda _s: None)
    assert summary.completed_items == 0
    assert summary.final_level == 9
    assert "Liên Minh" in summary.stop_reason
