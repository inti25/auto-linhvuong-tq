"""Unit tests cho linhvuong.generals và các trường mới trong linhvuong.roster."""

import threading
from unittest.mock import MagicMock

import pytest

from linhvuong.generals import (
    EQUIP_MODE_ASSIGN,
    EQUIP_MODE_UNEQUIP,
    MODE_BY_LEVEL,
    MODE_BY_NAME,
    MODE_REMOVE,
    MODE_SEQUENTIAL,
    classify_item_role,
    collect_reward_targets,
    configure_equipment,
    configure_tacticians,
    equip_general_item,
    fetch_equipment_inventory,
    get_item_display_name,
    reward_all_generals,
    reward_general,
    reward_money_needed,
    set_tactician,
)
from linhvuong.roster import City, General, Roster, fetch_roster


def _make_city(cid: int = 100, name: str = "Thanh1", base_type: str = "Thành") -> City:
    return City(id=cid, name=name, type=base_type, pos_x=10, pos_y=20, level=15)


def _make_gen(
    gid: int,
    name: str,
    role: str,
    city_id: int = 100,
    level: int = 10,
    loyalty: int = 100,
    status: int = 0,
    special_status: int = 0,
    tactician_id: int = 0,
    tactician_name: str = "",
) -> General:
    _ = city_id
    return General(
        id=gid,
        name=name,
        role=role,
        level=level,
        morale=100,
        stamina=100,
        stamina_max=100,
        loyalty=loyalty,
        status=status,
        special_status=special_status,
        tactician_id=tactician_id,
        tactician_name=tactician_name,
    )


class FakeGateway:
    """Fake GatewayClient ghi lại toàn bộ lệnh OPT.ashx / Optimization.ashx & trả về phản hồi."""

    def __init__(self, handler=None):
        self.calls: list[tuple[str, int | str, dict]] = []
        self._handler = handler

    def call(self, endpoint: str, op_id: int, payload: dict | None = None, **_kw):
        body = dict(payload or {})
        self.calls.append((endpoint, op_id, body))
        if self._handler:
            return self._handler(endpoint, op_id, body)
        return {"ret": 0, "loyalty": 100}

    def optimization(self, action: str, payload: dict | None = None, **_kw):
        p = dict(payload or {})
        body = {"lType": str(p.get("type", "0")), **p}
        self.calls.append(("Optimization.ashx", action, body))
        if self._handler:
            if action == "equipment":
                return self._handler("Common.ashx", 24, body)
            return self._handler("Optimization.ashx", action, body)
        return {"ret": 0, "list": []}


def test_roster_parses_loyalty_special_status_and_tactician():
    """fetch_roster trích xuất đúng loyalty, special_status, tactician_id/name."""
    city_list_resp = {
        "ret": 0,
        "data": {"items": [{"m_ltype": 1, "m_lid": 15230, "m_szname": "ThanhChinh", "m_lx_pos": 100, "m_ly_pos": 200, "m_llevel": 20}]},
    }
    civil_resp = {
        "ret": 0,
        "list": [
            [
                15230,
                "ThanhChinh",
                100,
                200,
                [
                    [417513, "GiaCatLuong", 100, 100, 1, 0, 35, 92, 100, 100],
                    [417514, "QuachGia", 100, 100, 2, 0, 30, 88, 100, 100],
                    [417515, "TuanUc", 100, 100, 0, 0, 25, 100, 100, 100],
                ],
            ]
        ],
    }
    martial_resp = {
        "ret": 0,
        "list": [
            [
                15230,
                "ThanhChinh",
                100,
                200,
                [
                    [417506, "TrieuVan", 95, 100, 0, 0, 40, 85, 95, 100],
                ],
            ]
        ],
    }
    detail_resp = {
        "ret": 0,
        "list": [
            [
                0,
                "",
                [
                    [417506, "TrieuVan", 417514, "QuachGia", 0, 100, 200, 300, 0, 95, 0],
                ],
            ]
        ],
    }

    gw = MagicMock()
    gw.city_list.return_value = city_list_resp
    gw.page_official.side_effect = lambda t: civil_resp if int(t) == 1 else martial_resp
    gw.page_mytroops_list.return_value = detail_resp
    roster = fetch_roster(gw)

    by_id = {g.id: g for g in roster.generals_of(15230)}
    mayor = by_id[417513]
    assert mayor.loyalty == 92
    assert mayor.special_status == 1
    assert mayor.is_mayor is True
    assert mayor.is_available_tactician is False
    assert mayor.status_text == "Thái thú"

    tac = by_id[417514]
    assert tac.loyalty == 88
    assert tac.special_status == 2
    assert tac.is_tactician is True
    assert tac.is_available_tactician is False
    assert tac.status_text == "Mưu sĩ"

    free_civ = by_id[417515]
    assert free_civ.is_available_tactician is True
    assert free_civ.status_text == "Rảnh rỗi"

    vo = by_id[417506]
    assert vo.loyalty == 85
    assert vo.tactician_id == 417514
    assert vo.tactician_name == "QuachGia"
    assert vo.morale == 95


def test_reward_money_needed_and_collect_targets():
    assert reward_money_needed(level=10, loyalty=80) == 2000
    assert reward_money_needed(level=10, loyalty=100) == 0
    assert reward_money_needed(level=0, loyalty=50) == 0

    c1 = _make_city(1, "ThanhA")
    camp = _make_city(-5, "TraiB", base_type="Doanh trại")
    g_van_low = _make_gen(11, "VanA", "van", city_id=1, level=15, loyalty=90)   # 10*15*10=1500
    g_van_full = _make_gen(12, "VanB", "van", city_id=1, level=20, loyalty=100)
    g_vo_low = _make_gen(21, "VoA", "vo", city_id=-5, level=25, loyalty=96)     # 4*25*10=1000

    roster = Roster(
        cities=[c1],
        camps=[camp],
        _generals={1: [g_van_low, g_van_full], -5: [g_vo_low]},
    )

    targets = collect_reward_targets(roster)
    assert [t.general.id for t in targets] == [11, 21]
    assert [t.city_id for t in targets] == [1, -5]
    assert sum(t.money_needed for t in targets) == 2500


def test_reward_all_generals_handles_failures_and_stop():
    c1 = _make_city(1, "ThanhA")
    g1 = _make_gen(11, "VanA", "van", city_id=1, level=10, loyalty=90)  # 1000
    g2 = _make_gen(12, "VoB", "vo", city_id=1, level=20, loyalty=95)    # 1000 (sẽ fail)
    g3 = _make_gen(13, "VoC", "vo", city_id=1, level=10, loyalty=80)    # 2000 (không chạy nếu stop)
    roster = Roster(cities=[c1], camps=[], _generals={1: [g1, g2, g3]})

    stop = threading.Event()

    def _handler(_ep, _id, body):
        if body["lGeneralID"] == "12":
            stop.set()
            return {"ret": -2}
        return {"ret": 0, "loyalty": 100}

    gw = FakeGateway(_handler)
    logs: list[str] = []
    summary = reward_all_generals(gw, roster=roster, stop_event=stop, on_log=logs.append)

    assert summary.total == 3
    assert summary.success == 1
    assert summary.failed == 1
    assert summary.stopped is True
    assert summary.total_gold_spent == 1000
    assert len(gw.calls) == 2
    assert gw.calls[0] == ("OPT.ashx", 46, {"lCityID": "1", "lGeneralID": "11", "lMoney": "1000", "_": ""})


def test_set_tactician_assign_remove_and_error_mapping():
    def _handler(_ep, _id, body):
        if body["lFollowGeneralID"] == "999":
            return {"ret": 10023}
        return {"ret": 0}

    gw = FakeGateway(_handler)
    ok, ret, msg = set_tactician(gw, city_id=100, civilian_id=10, military_id=20, remove=False)
    assert (ok, ret) == (True, 0)
    assert gw.calls[-1] == (
        "OPT.ashx",
        5,
        {"lGeneralID": "10", "lType": "3", "lFollowGeneralID": "20", "lCityID": "100", "_": ""},
    )

    ok2, ret2, _ = set_tactician(gw, city_id=100, civilian_id=10, remove=True)
    assert (ok2, ret2) == (True, 0)
    assert gw.calls[-1][2]["lType"] == "0"
    assert gw.calls[-1][2]["lFollowGeneralID"] == "0"

    ok3, ret3, msg3 = set_tactician(gw, city_id=100, civilian_id=10, military_id=999, remove=False)
    assert (ok3, ret3) == (False, 10023)
    assert "Không cùng thành" in msg3


def test_configure_tacticians_by_level_same_city_only():
    """MODE_BY_LEVEL ghép cặp cao->thấp trong từng thành, bỏ qua Thái thú và Văn quan bận."""
    c1 = _make_city(100, "ThanhA")
    c2 = _make_city(200, "ThanhB")
    # Thành A: 2 Võ (lv 30, lv 50), 1 Thái thú (lv 99), 1 bận (lv 90), 2 Văn rảnh (lv 45, lv 20)
    vo_a1 = _make_gen(1, "VoA1", "vo", city_id=100, level=30)
    vo_a2 = _make_gen(2, "VoA2", "vo", city_id=100, level=50)
    van_mayor = _make_gen(10, "ThaiThuA", "van", city_id=100, level=99, status=0, special_status=1)
    van_busy = _make_gen(11, "VanBanA", "van", city_id=100, level=90, status=2, special_status=0)
    van_a1 = _make_gen(12, "VanA1", "van", city_id=100, level=20)
    van_a2 = _make_gen(13, "VanA2", "van", city_id=100, level=45)

    # Thành B: 1 Võ (lv 60), KHÔNG có Văn quan rảnh ở B (chỉ có Thái thú)
    vo_b1 = _make_gen(3, "VoB1", "vo", city_id=200, level=60)
    van_b_mayor = _make_gen(20, "ThaiThuB", "van", city_id=200, level=80, status=0, special_status=1)

    roster = Roster(
        cities=[c1, c2],
        camps=[],
        _generals={
            100: [vo_a1, vo_a2, van_mayor, van_busy, van_a1, van_a2],
            200: [vo_b1, van_b_mayor],
        },
    )

    gw = FakeGateway()
    summary = configure_tacticians(
        gw,
        roster,
        selected_general_ids=[1, 2, 3],
        mode=MODE_BY_LEVEL,
        reassign_existing=False,
    )

    assert summary.assigned == 2
    assert summary.no_available_civilian == 1
    assert summary.failed == 0
    # Cặp 1: Võ cao nhất (VoA2 id=2 lv=50) <-> Văn cao nhất (VanA2 id=13 lv=45)
    # Cặp 2: Võ kế (VoA1 id=1 lv=30) <-> Văn kế (VanA1 id=12 lv=20)
    assign_pairs = [(c[2]["lCityID"], c[2]["lGeneralID"], c[2]["lFollowGeneralID"]) for c in gw.calls]
    assert assign_pairs == [("100", "13", "2"), ("100", "12", "1")]


def test_configure_tacticians_by_name_with_by_level_fallback():
    """MODE_BY_NAME match tên trước, còn lại fallback cao->thấp."""
    c1 = _make_city(100, "ThanhA")
    vo_tri_10 = _make_gen(1, "TrungTen", "vo", city_id=100, level=10)
    vo_other_50 = _make_gen(2, "LaBo", "vo", city_id=100, level=50)
    van_tri_5 = _make_gen(10, " TrungTen ", "van", city_id=100, level=5)
    van_high_40 = _make_gen(11, "GiaCat", "van", city_id=100, level=40)

    roster = Roster(cities=[c1], camps=[], _generals={100: [vo_tri_10, vo_other_50, van_tri_5, van_high_40]})
    gw = FakeGateway()
    summary = configure_tacticians(gw, roster, [1, 2], mode=MODE_BY_NAME)

    assert summary.assigned == 2
    assert summary.name_matched == 1
    assert summary.fallback_assigned == 1
    pairs = {(c[2]["lGeneralID"], c[2]["lFollowGeneralID"]) for c in gw.calls}
    assert pairs == {("10", "1"), ("11", "2")}


def test_configure_tacticians_reassign_checkbox_off_vs_on_and_excludes_mayor():
    """Kiểm tra checkbox 'Đổi mưu sĩ' tắt vs bật."""
    c1 = _make_city(100, "ThanhA")
    # Vo1 (lv 50) đã có VanOld (id=11, lv=20), được chọn
    # Vo2 (lv 30) chưa có MS, được chọn
    # Vo3 (lv 60) đang bận (status=1), đã có VanBusy (id=12), được chọn -> PHẢI BỎ QUA
    # Vo4 (lv 70) không được chọn, đang có VanUnselected (id=13) -> KHÔNG ĐƯỢC ĐỤNG VÀO
    # ThaiThu (id=14, special_status=1, status=0, lv=99) -> PHẢI LOẠI TRỪ
    # VanNew (id=15, lv=40, status=0, special_status=0) -> Khả dụng
    vo1 = _make_gen(1, "Vo1", "vo", city_id=100, level=50, tactician_id=11, tactician_name="VanOld")
    vo2 = _make_gen(2, "Vo2", "vo", city_id=100, level=30)
    vo3_busy = _make_gen(3, "Vo3Busy", "vo", city_id=100, level=60, status=1, tactician_id=12, tactician_name="VanBusy")
    vo4_unselected = _make_gen(4, "Vo4Other", "vo", city_id=100, level=70, tactician_id=13, tactician_name="VanOther")

    van_old = _make_gen(11, "VanOld", "van", city_id=100, level=20, special_status=2)
    van_busy_tac = _make_gen(12, "VanBusy", "van", city_id=100, level=80, special_status=2)
    van_unselected_tac = _make_gen(13, "VanOther", "van", city_id=100, level=85, special_status=2)
    van_mayor = _make_gen(14, "ThaiThu", "van", city_id=100, level=99, status=0, special_status=1)
    van_new = _make_gen(15, "VanNew", "van", city_id=100, level=40, status=0, special_status=0)

    roster = Roster(
        cities=[c1],
        camps=[],
        _generals={100: [vo1, vo2, vo3_busy, vo4_unselected, van_old, van_busy_tac, van_unselected_tac, van_mayor, van_new]},
    )

    # Case 1: reassign_existing=False -> giữ nguyên Vo1, chỉ gán cho Vo2
    gw_keep = FakeGateway()
    sum_keep = configure_tacticians(gw_keep, roster, [1, 2, 3], mode=MODE_BY_LEVEL, reassign_existing=False)
    assert sum_keep.skipped_has_tactician == 1
    assert sum_keep.skipped_busy == 1
    assert sum_keep.assigned == 1
    assert sum_keep.removed == 0
    assert gw_keep.calls == [
        ("OPT.ashx", 5, {"lGeneralID": "15", "lType": "3", "lFollowGeneralID": "2", "lCityID": "100", "_": ""})
    ]

    # Case 2: reassign_existing=True -> tháo VanOld khỏi Vo1, gộp pool {VanNew(40), VanOld(20)},
    # bỏ qua Vo3Busy & không đụng Vo4Other & loại trừ ThaiThu -> ghép Vo1(50)<->VanNew(40), Vo2(30)<->VanOld(20)
    gw_swap = FakeGateway()
    sum_swap = configure_tacticians(gw_swap, roster, [1, 2, 3], mode=MODE_BY_LEVEL, reassign_existing=True)
    assert sum_swap.removed == 1
    assert sum_swap.assigned == 2
    assert sum_swap.skipped_busy == 1
    assert [(c[2]["lType"], c[2]["lGeneralID"], c[2]["lFollowGeneralID"]) for c in gw_swap.calls] == [
        ("0", "11", "0"),  # Tháo VanOld
        ("3", "15", "1"),  # Vo1 (50) <-> VanNew (40)
        ("3", "11", "2"),  # Vo2 (30) <-> VanOld (20)
    ]


def test_configure_tacticians_remove_sequential_and_camp_warning():
    camp = _make_city(-10, "TienDon", base_type="Doanh trại")
    vo1 = _make_gen(1, "Vo1", "vo", city_id=-10, level=10, tactician_id=10, tactician_name="Van1")
    vo2 = _make_gen(2, "Vo2", "vo", city_id=-10, level=20)
    van1 = _make_gen(10, "Van1", "van", city_id=-10, level=15, special_status=3)
    van2 = _make_gen(11, "Van2", "van", city_id=-10, level=15, special_status=0)
    roster = Roster(cities=[], camps=[camp], _generals={-10: [vo1, vo2, van1, van2]})

    # Sequential mode on camp
    gw_seq = FakeGateway()
    logs: list[str] = []
    sum_seq = configure_tacticians(gw_seq, roster, [2], mode=MODE_SEQUENTIAL, on_log=logs.append)
    assert sum_seq.assigned == 1
    assert any("Doanh trại" in line for line in logs)

    # Remove mode
    gw_rem = FakeGateway()
    sum_rem = configure_tacticians(gw_rem, roster, [1, 2], mode=MODE_REMOVE)
    assert sum_rem.removed == 1
    assert sum_rem.no_tactician_to_remove == 1
    assert gw_rem.calls == [
        ("OPT.ashx", 5, {"lGeneralID": "10", "lType": "0", "lFollowGeneralID": "0", "lCityID": "-10", "_": ""})
    ]


def test_configure_tacticians_never_steals_active_tactician_and_runtime_calls_selected_ids(tmp_path, monkeypatch):
    """Không cướp Mưu sĩ đang gắn cho Võ tướng khác và AccountSession.run_tactician_action truyền đúng selected_general_ids."""
    c1 = _make_city(100, "ThanhA")
    vo_unselected = _make_gen(1, "Vo1", "vo", city_id=100, level=50, tactician_id=10, tactician_name="VanBusyTac")
    vo_target = _make_gen(2, "Vo2", "vo", city_id=100, level=40)
    # Giả sử special_status bị trễ đồng bộ = 0 nhưng vo_unselected vẫn đang giữ tactician_id=10
    van_tac_stale = _make_gen(10, "VanBusyTac", "van", city_id=100, level=60, special_status=0)
    roster = Roster(cities=[c1], camps=[], _generals={100: [vo_unselected, vo_target, van_tac_stale]})

    gw = FakeGateway()
    summary = configure_tacticians(gw, roster, [2], mode=MODE_BY_LEVEL, reassign_existing=False)
    assert summary.assigned == 0
    assert summary.no_available_civilian == 1
    assert gw.calls == []

    # Kiểm tra seam AccountSession.run_tactician_action -> configure_tacticians (tránh lỗi TypeError target_vo_ids)
    import linhvuong.runtime as runtime_mod
    from linhvuong.runtime import WorkspaceManager

    monkeypatch.setattr(runtime_mod, "login", lambda *a, **kw: None)
    monkeypatch.setattr(runtime_mod, "fetch_roster", lambda _gw: roster)
    monkeypatch.setattr(runtime_mod.AccountSession, "start_aux_loop", lambda self: None)

    wm = WorkspaceManager(data_dir=tmp_path, acquire_lock=False)
    try:
        sess = wm.login_account(server_id=58, username="u", password="p")
        sess.gateway = gw  # type: ignore[assignment]
        sess.run_tactician_action(MODE_BY_LEVEL, [2], reassign=False)
        import time as _t

        deadline = _t.monotonic() + 2.0
        while sess._tac_running and _t.monotonic() < deadline:
            _t.sleep(0.02)
        assert "❌ Lỗi:" not in sess._tac_status, sess._tac_status
        assert "Hoàn tất:" in sess._tac_status
    finally:
        wm.graceful_shutdown()


def test_classify_item_role_and_fetch_equipment_inventory():
    """Phân hệ đúng đồ Võ (x1xx) / đồ Văn (x2xx), tách stack và sắp xếp Cao -> Thấp."""
    assert classify_item_role(1135) == "vo"
    assert classify_item_role(4112) == "vo"
    assert classify_item_role(1220) == "van"
    assert classify_item_role(2217) == "van"
    assert classify_item_role(4216) == "van"
    assert classify_item_role(999) is None

    def _handler(_ep, _oid, body):
        lt = body.get("lType")
        if lt == "1":  # Mũ
            return {
                "ret": 0,
                "list": [
                    # [0]=id, [1]=qty, [2]=type_id, ..., [7]=level, [8]=gen_id, [9]=gen_name
                    [101, 2, 1104, 0, 0, 0, 0, 1, 0, ""],       # 2x Mũ võ Lv.1 trong kho
                    [102, 1, 1135, 0, 0, 0, 0, 10, 0, ""],      # Mũ võ Lv.10 trong kho
                    [103, 1, 1120, 0, 0, 0, 0, 10, 0, ""],      # Mũ võ Lv.10 type thấp hơn 1135
                    [104, 1, 1220, 0, 0, 0, 0, 8, 10, "VanA"],   # Mũ văn Lv.8 đang mặc bởi ID 10
                ],
            }
        if lt == "2":  # Vũ khí
            return {
                "ret": 0,
                "list": [
                    [201, 1, 2217, 0, 0, 0, 0, 12, 0, ""],      # Quạt văn Lv.12
                    [202, 1, 2142, 0, 0, 0, 0, 9, 0, ""],       # Phương thiên kích Lv.9
                ],
            }
        return {"ret": 0, "list": []}

    gw = FakeGateway(_handler)
    inv = fetch_equipment_inventory(gw)

    vo_helms = inv.free_items[("vo", 1)]
    assert [it.item_id for it in vo_helms] == [102, 103, 101, 101]
    assert [it.item_type_id for it in vo_helms] == [1135, 1120, 1104, 1104]
    assert inv.count_free("vo", 2) == 1
    assert inv.count_free("van", 2) == 1
    assert inv.equipped_by_general[10][1].item_id == 104
    assert inv.equipped_by_general[10][1].short_label == "武侯纶巾 (Lv.8)"


def test_configure_equipment_priority_role_separation_and_upgrade():
    """Võ/Văn tách hệ riêng, ưu tiên cấp tướng Cao -> Thấp, nâng cấp và hoàn trả đồ cũ về pool."""
    c1 = _make_city(100, "ThanhA")
    vo_high = _make_gen(1, "VoHigh", "vo", city_id=100, level=60)
    vo_low = _make_gen(2, "VoLow", "vo", city_id=100, level=25)
    vo_busy = _make_gen(3, "VoBusy", "vo", city_id=100, level=95, status=1)
    van_high = _make_gen(4, "VanHigh", "van", city_id=100, level=50)
    van_low = _make_gen(5, "VanLow", "van", city_id=100, level=15)

    roster = Roster(cities=[c1], camps=[], _generals={100: [vo_low, vo_high, vo_busy, van_low, van_high]})

    def _handler(ep, oid, body):
        if ep == "Common.ashx" and oid == 24:
            lt = body["lType"]
            if lt == "1":  # Mũ: VoHigh đang mặc 1104 Lv.1; kho có 1135 Lv.10 + Mũ văn 1220 Lv.7 & 1205 Lv.2
                return {
                    "ret": 0,
                    "list": [
                        [1001, 1, 1104, 0, 0, 0, 0, 1, 1, "VoHigh"],
                        [1002, 1, 1135, 0, 0, 0, 0, 10, 0, ""],
                        [1003, 1, 1220, 0, 0, 0, 0, 7, 0, ""],
                        [1004, 1, 1205, 0, 0, 0, 0, 2, 0, ""],
                    ],
                }
            if lt == "2":  # Vũ khí: 1 stack x2 món 2109 Lv.1 + 1 kích 2142 Lv.5
                return {
                    "ret": 0,
                    "list": [
                        [2001, 2, 2109, 0, 0, 0, 0, 1, 0, ""],
                        [2002, 1, 2142, 0, 0, 0, 0, 5, 0, ""],
                    ],
                }
            return {"ret": 0, "list": []}
        return {"ret": 0}

    gw = FakeGateway(_handler)
    summary = configure_equipment(
        gw,
        roster,
        selected_general_ids=[1, 2, 3, 4, 5],
        mode=EQUIP_MODE_ASSIGN,
        reassign_existing=False,
    )

    assert summary.skipped_busy == 1
    assert summary.failed == 0

    opt_calls = [
        (int(body["lGeneralID"]), int(body["lEquipType"]), int(body["lEquipID"]))
        for ep, oid, body in gw.calls
        if ep == "OPT.ashx" and oid == 58
    ]
    # Kiểm tra thứ tự ưu tiên theo từng nhóm: VoHigh(1) mặc trước VoLow(2), VanHigh(4) mặc trước VanLow(5)
    assert opt_calls == [
        (1, 1, 1002),  # VoHigh nâng cấp Mũ 1135 (Lv.10), hoàn 1001 về pool
        (1, 2, 2002),  # VoHigh lấy Vũ khí 2142 (Lv.5)
        (2, 1, 1001),  # VoLow được hưởng Mũ 1104 (Lv.1) vừa hoàn lại từ VoHigh!
        (2, 2, 2001),  # VoLow lấy Vũ khí 2109 (Lv.1)
        (4, 1, 1003),  # VanHigh lấy Mũ Văn 1220 (Lv.7)
        (5, 1, 1004),  # VanLow lấy Mũ Văn 1205 (Lv.2)
    ]


def test_configure_equipment_reassign_existing_and_unequip_mode():
    """Checkbox Đổi trang bị thu hồi đồ về kho chia lại Cao->Thấp; Tháo trang bị gọi lEquipID=0."""
    c1 = _make_city(100, "ThanhA")
    vo_high = _make_gen(1, "VoHigh", "vo", city_id=100, level=80)
    vo_low = _make_gen(2, "VoLow", "vo", city_id=100, level=20)
    van_busy = _make_gen(3, "VanBusy", "van", city_id=100, level=60, status=2)
    roster = Roster(cities=[c1], camps=[], _generals={100: [vo_low, vo_high, van_busy]})

    def _mock_calls(_ep, oid, body):
        if _ep == "Common.ashx" and oid == 24:
            if body["lType"] == "2":
                return {
                    "ret": 0,
                    "list": [
                        [301, 1, 2109, 0, 0, 0, 0, 1, 1, "VoHigh"],   # Tướng cao đang mặc cùi
                        [302, 1, 2142, 0, 0, 0, 0, 12, 2, "VoLow"],   # Tướng thấp đang mặc xịn
                        [303, 1, 2217, 0, 0, 0, 0, 9, 3, "VanBusy"],  # Tướng bận không được đụng
                    ],
                }
            return {"ret": 0, "list": []}
        return {"ret": 0}

    # 1. Không bật Đổi trang bị -> không tháo, kho không có đồ -> 0 thay đổi
    gw_keep = FakeGateway(_mock_calls)
    sum_keep = configure_equipment(gw_keep, roster, [1, 2, 3], mode=EQUIP_MODE_ASSIGN, reassign_existing=False)
    assert sum_keep.skipped_busy == 1
    assert sum_keep.equipped == 0
    assert sum_keep.unequipped == 0

    # 2. Bật Đổi trang bị -> tháo 301 (của VoHigh) & 302 (của VoLow), chia lại 302 cho VoHigh, 301 cho VoLow
    gw_swap = FakeGateway(_mock_calls)
    sum_swap = configure_equipment(gw_swap, roster, [1, 2, 3], mode=EQUIP_MODE_ASSIGN, reassign_existing=True)
    assert sum_swap.skipped_busy == 1
    assert sum_swap.unequipped == 2
    assert sum_swap.equipped == 2
    swap_ops = [
        (int(body["lGeneralID"]), int(body["lEquipType"]), int(body["lEquipID"]))
        for ep, oid, body in gw_swap.calls
        if ep == "OPT.ashx" and oid == 58
    ]
    assert swap_ops == [
        (1, 2, 0),    # Tháo của VoHigh
        (2, 2, 0),    # Tháo của VoLow
        (1, 2, 302),  # VoHigh nhận 2142 (Lv.12)
        (2, 2, 301),  # VoLow nhận 2109 (Lv.1)
    ]

    # 3. Chế độ Tháo trang bị -> chỉ tháo tướng rảnh được chọn
    gw_unequip = FakeGateway(_mock_calls)
    sum_un = configure_equipment(gw_unequip, roster, [1, 2, 3], mode=EQUIP_MODE_UNEQUIP)
    assert sum_un.skipped_busy == 1
    assert sum_un.unequipped == 2
    assert [
        (int(body["lGeneralID"]), int(body["lEquipID"]))
        for ep, oid, body in gw_unequip.calls
        if ep == "OPT.ashx" and oid == 58
    ] == [(1, 0), (2, 0)]


def test_configure_equipment_stacked_item_split_and_failed_item_eviction():
    """Làm mới item_id mới khi mặc stack > 1 và loại bỏ món lỗi khỏi pool để không lặp lỗi."""
    # Kiểm tra các mã đã bổ sung từ Dipan.SanGuo.Config.js (Arm)
    assert get_item_display_name(1103) == "光荣头盔"
    assert get_item_display_name(2101) == "梅花亮银枪"
    assert get_item_display_name(2205) == "精钢扇"
    assert get_item_display_name(3208) == "锦绣珠袍"
    assert get_item_display_name(4120) == "祥瑞金牛"
    assert get_item_display_name(4213) == "白石"

    # 1. Server tách item_id mới cho phần dư khi mặc trang bị stack > 1
    c1 = _make_city(100, "ThanhA")
    vo1 = _make_gen(1, "Vo1", "vo", city_id=100, level=90)
    vo2 = _make_gen(2, "Vo2", "vo", city_id=100, level=80)
    vo3 = _make_gen(3, "Vo3", "vo", city_id=100, level=70)
    roster = Roster(cities=[c1], camps=[], _generals={100: [vo3, vo1, vo2]})

    helm_rows = [[16950692, 3, 1113, 30, 0, 0, 15, 0, 0, ""]]

    def _stacked_handler(ep, oid, body):
        if ep == "Common.ashx" and oid == 24:
            if body["lType"] == "1":
                return {"ret": 0, "list": [list(r) for r in helm_rows]}
            return {"ret": 0, "list": []}
        if ep == "OPT.ashx" and oid == 58:
            gid = int(body["lGeneralID"])
            eid = int(body["lEquipID"])
            for idx, r in enumerate(list(helm_rows)):
                if r[0] == eid and r[8] == 0:
                    qty = r[1]
                    helm_rows[idx] = [eid, 1, 1113, 30, 0, 0, 15, 0, gid, f"Vo{gid}"]
                    if qty > 1:
                        next_id = 16939353 if eid == 16950692 else 16900001
                        helm_rows.append([next_id, qty - 1, 1113, 30, 0, 0, 15, 0, 0, ""])
                    return {"ret": 0}
            return {"ret": 1}
        return {"ret": 0}

    gw = FakeGateway(_stacked_handler)
    summary = configure_equipment(gw, roster, [1, 2, 3], mode=EQUIP_MODE_ASSIGN, reassign_existing=False)
    assert summary.equipped == 3
    assert summary.failed == 0
    assert [
        (int(body["lGeneralID"]), int(body["lEquipType"]), int(body["lEquipID"]))
        for ep, oid, body in gw.calls
        if ep == "OPT.ashx" and oid == 58
    ] == [
        (1, 1, 16950692),
        (2, 1, 16939353),
        (3, 1, 16900001),
    ]

    # 2. Ứng viên ở đầu pool lỗi (ret=1) phải bị loại sạch để tướng sau lấy món hợp lệ đứng sau
    vo_a = _make_gen(11, "VoA", "vo", city_id=100, level=60)
    vo_b = _make_gen(12, "VoB", "vo", city_id=100, level=50)
    roster_err = Roster(cities=[c1], camps=[], _generals={100: [vo_b, vo_a]})

    def _error_eviction_handler(ep, oid, body):
        if ep == "Common.ashx" and oid == 24:
            if body["lType"] == "2":
                return {
                    "ret": 0,
                    "list": [
                        [9001, 2, 2115, 0, 19, 7, 0, 0, 0, ""],
                        [9002, 1, 2101, 0, 2, 0, 0, 0, 0, ""],
                    ],
                }
            return {"ret": 0, "list": []}
        if ep == "OPT.ashx" and oid == 58:
            if int(body["lEquipID"]) == 9001:
                return {"ret": 1}
            return {"ret": 0}
        return {"ret": 0}

    gw_err = FakeGateway(_error_eviction_handler)
    sum_err = configure_equipment(gw_err, roster_err, [11, 12], mode=EQUIP_MODE_ASSIGN)
    assert sum_err.failed == 1
    assert sum_err.equipped == 1
    assert [
        (int(body["lGeneralID"]), int(body["lEquipType"]), int(body["lEquipID"]))
        for ep, oid, body in gw_err.calls
        if ep == "OPT.ashx" and oid == 58
    ] == [
        (11, 2, 9001),
        (12, 2, 9002),
    ]


def test_configure_equipment_smart_civil_mayor_tactician_idle_priority():
    """Thái thú ưu tiên đồ Nội chính > 0; đồ Nội chính = 0 nhường Mưu sĩ đang biên chế -> Nhàn rỗi -> Vét Thái thú."""
    c1 = _make_city(100, "ThanhA")
    vo_gen = General(
        id=1,
        name="VoMaster",
        role="vo",
        level=120,
        morale=100,
        stamina=100,
        stamina_max=100,
        tactician_id=13,
        tactician_name="MuuSiTheoTuong",
    )
    mayor = General(
        id=10,
        name="ThaiThu",
        role="van",
        level=200,
        morale=100,
        stamina=100,
        stamina_max=100,
        special_status=1,
    )
    tactician = General(
        id=11,
        name="MuuSi",
        role="van",
        level=100,
        morale=100,
        stamina=100,
        stamina_max=100,
        special_status=3,
    )
    # Văn quan biên chế được nhận diện qua active_tactician_ids() dù special_status=0
    tactician_via_vo = General(
        id=13,
        name="MuuSiTheoTuong",
        role="van",
        level=95,
        morale=100,
        stamina=100,
        stamina_max=100,
        special_status=0,
    )
    idle_van = General(
        id=12,
        name="NhanRoi",
        role="van",
        level=150,
        morale=100,
        stamina=100,
        stamina_max=100,
        special_status=0,
    )

    assert tactician.is_tactician is True
    assert tactician.status_text == "Mưu sĩ"

    roster = Roster(
        cities=[c1],
        camps=[],
        _generals={100: [idle_van, tactician, mayor]},
    )

    def _civil_handler(ep, oid, body):
        if ep == "Common.ashx" and oid == 24:
            lt = body["lType"]
            if lt == "1":
                return {
                    "ret": 0,
                    "list": [
                        [1001, 1, 1220, 60, 10, 27, 0, 1, 0, ""],   # 武侯纶巾 (Nội chính = 0)
                        [1002, 1, 1207, 20, 0, 0, 14, 1, 0, ""],   # 状元冠 (Nội chính = 14)
                    ],
                }
            if lt == "2":
                return {
                    "ret": 0,
                    "list": [
                        [2000, 1, 2218, 0, 16, 30, 0, 1, 10, "ThaiThu"],  # 智多星羽扇 (Nội chính = 0)
                        [2001, 1, 2217, 0, 26, 0, 20, 1, 0, ""],           # 文曲星羽扇 (Nội chính = 20)
                    ],
                }
            if lt == "4":
                return {
                    "ret": 0,
                    "list": [
                        [4001, 1, 4213, 0, 3, 15, 0, 1, 0, ""],   # 白石 (Nội chính = 0)
                        [4002, 1, 4205, 0, 0, 10, 0, 1, 0, ""],   # 快航 (Nội chính = 0)
                    ],
                }
            return {"ret": 0, "list": []}
        return {"ret": 0}

    gw = FakeGateway(_civil_handler)
    summary = configure_equipment(
        gw,
        roster,
        [10, 11, 12],
        mode=EQUIP_MODE_ASSIGN,
        reassign_existing=False,
    )
    assert summary.equipped == 6
    assert summary.failed == 0
    assert [
        (int(body["lGeneralID"]), int(body["lEquipType"]), int(body["lEquipID"]))
        for ep, oid, body in gw.calls
        if ep == "OPT.ashx" and oid == 58
    ] == [
        (10, 1, 1002),  # Thái thú chọn 1207 (Nội chính = 14), nhường 1220
        (10, 2, 2001),  # Thái thú nâng cấp từ 2218 -> 2217 (Nội chính = 20), trả 2000 về kho
        (11, 1, 1001),  # Mưu sĩ (Lv.100) nhận 1220 trước Văn nhàn rỗi (Lv.150)
        (11, 2, 2000),  # Mưu sĩ nhận lại 2218 từ Thái thú
        (11, 4, 4001),  # Mưu sĩ nhận ngựa 白石 (4213)
        (12, 4, 4002),  # Văn nhàn rỗi nhận ngựa 快航 (4205)
    ]

    # Kiểm tra vòng vét cuối cho Thái thú + nhận diện Mưu sĩ qua active_tactician_ids()
    roster_sweep = Roster(
        cities=[c1],
        camps=[],
        _generals={100: [vo_gen, idle_van, tactician_via_vo, tactician, mayor]},
    )
    assert roster_sweep.active_tactician_ids() == {13}

    def _sweep_handler(ep, oid, body):
        if ep == "Common.ashx" and oid == 24 and body["lType"] == "4":
            return {
                "ret": 0,
                "list": [
                    [4001, 1, 4213, 0, 3, 15, 0, 1, 0, ""],
                    [4002, 1, 4205, 0, 0, 10, 0, 1, 0, ""],
                    [4003, 1, 4201, 0, 0, 2, 0, 1, 0, ""],   # 松风 dư thứ 3 -> vét cho Thái thú ở cuối
                    [4004, 1, 4202, 0, 0, 4, 0, 1, 0, ""],   # 飞镰 -> nhường cho Nhàn rỗi trước Thái thú
                ],
            }
        return {"ret": 0, "list": []}

    gw_sweep = FakeGateway(_sweep_handler)
    sum_sweep = configure_equipment(
        gw_sweep,
        roster_sweep,
        [10, 11, 12, 13],
        mode=EQUIP_MODE_ASSIGN,
    )
    assert sum_sweep.equipped == 4
    assert [
        (int(body["lGeneralID"]), int(body["lEquipType"]), int(body["lEquipID"]))
        for ep, oid, body in gw_sweep.calls
        if ep == "OPT.ashx" and oid == 58
    ] == [
        (11, 4, 4001),  # Mưu sĩ Lv.100 lấy 白石 (4213)
        (13, 4, 4002),  # Mưu sĩ biên chế Lv.95 lấy 快航 (4205)
        (12, 4, 4004),  # Văn nhàn rỗi Lv.150 lấy 飞镰 (4202)
        (10, 4, 4003),  # Thái thú Lv.200 vét ô trống cuối cùng bằng 松风 (4201)
    ]


def test_fetch_equipment_inventory_paginates_over_50_items():
    """Tải đầy đủ nhiều trang từ Optimization.ashx?action=equipment khi kho vượt quá 50 món."""
    page0 = [[5000 + i, 1, 1135, 100, 10, 10, 0, 10, 0, ""] for i in range(50)]
    page1 = [[5050 + i, 1, 1135, 100, 10, 10, 0, 10, 0, ""] for i in range(5)]

    def _paged_handler(_ep, _oid, body):
        if body.get("lType") == "1":
            p = int(body.get("page", 0))
            return {
                "ret": 0,
                "list": page0 if p == 0 else page1,
                "page": p,
                "pageSize": 50,
                "total": 55,
                "revision": [111, 222],
            }
        return {"ret": 0, "list": [], "page": 0, "pageSize": 50, "total": 0, "revision": [1, 1]}

    inv = fetch_equipment_inventory(FakeGateway(_paged_handler))
    assert inv.count_free("vo", 1) == 55


def test_configure_equipment_ret_301_skips_for_male_and_keeps_for_eligible_general():
    """Khi OPT.ashx?id=58 trả ret=301 (đồ nữ/tướng Man), tướng nam bỏ qua sang món kế tiếp và giữ lại trong pool."""
    from linhvuong.generals import EquipmentInventory, EquipmentItem, configure_equipment
    from linhvuong.roster import City, General, Roster

    attempts: list[tuple[int, int, int]] = []

    def _handler(ep, oid, body):
        assert (ep, oid) == ("OPT.ashx", 58)
        gid = int(body["lGeneralID"])
        eq_type = int(body["lEquipType"])
        item_id = int(body["lEquipID"])
        attempts.append((gid, eq_type, item_id))
        if gid == 101 and item_id == 9101:
            return {"ret": 301, "errMsg": "该装备仅限女性名(蛮)将使用"}
        return {"ret": 0}

    roster = Roster(
        cities=[City(id=1, name="Thành chính")],
        _generals={
            1: [
                General(id=101, name="Tào Tháo", role="vo", level=100, morale=100, stamina=100, stamina_max=100),
                General(id=102, name="Chân Mật", role="vo", level=90, morale=100, stamina=100, stamina_max=100),
            ]
        },
    )
    inv = EquipmentInventory(
        free_items={
            ("vo", 1): [
                EquipmentItem(item_id=9101, equip_type=1, item_type_id=1139, level=100),
                EquipmentItem(item_id=9102, equip_type=1, item_type_id=1135, level=80),
            ]
        }
    )

    logs: list[str] = []
    summary = configure_equipment(
        FakeGateway(_handler),
        roster,
        [101, 102],
        inventory=inv,
        on_log=logs.append,
    )

    assert summary.failed == 0
    assert summary.equipped == 2
    assert summary.no_item_available == 6
    assert inv.equipped_by_general[101][1].item_id == 9102
    assert inv.equipped_by_general[102][1].item_id == 9101
    assert inv.count_free("vo", 1) == 0
    assert attempts == [(101, 1, 9101), (101, 1, 9102), (102, 1, 9101)]
    assert any("thử món kế tiếp" in line for line in logs)


def test_configure_equipment_mayor_ret_301_falls_back_to_leftover_pass_without_retrying():
    """Thái thú gặp ret=301 ở lượt Nội chính sẽ không bị tính lỗi và được vét đồ khác ở lượt 3."""
    from linhvuong.generals import EquipmentInventory, EquipmentItem, configure_equipment
    from linhvuong.roster import City, General, Roster

    attempts: list[tuple[int, int]] = []

    def _handler(_ep, _oid, body):
        gid = int(body["lGeneralID"])
        item_id = int(body["lEquipID"])
        attempts.append((gid, item_id))
        if item_id == 9201:
            return {"ret": 301, "errMsg": "该装备仅限女性名(蛮)将使用"}
        return {"ret": 0}

    roster = Roster(
        cities=[City(id=1, name="Thành chính")],
        _generals={
            1: [
                General(
                    id=201,
                    name="Tuân Úc",
                    role="van",
                    level=100,
                    morale=100,
                    stamina=100,
                    stamina_max=100,
                    special_status=1,
                )
            ]
        },
    )
    inv = EquipmentInventory(
        free_items={
            ("van", 1): [
                EquipmentItem(item_id=9201, equip_type=1, item_type_id=1239, level=100, politics=50),
                EquipmentItem(item_id=9202, equip_type=1, item_type_id=1205, level=20, politics=0),
            ]
        }
    )

    summary = configure_equipment(FakeGateway(_handler), roster, [201], inventory=inv)

    assert summary.failed == 0
    assert summary.equipped == 1
    assert summary.no_item_available == 3
    assert inv.equipped_by_general[201][1].item_id == 9202
    assert inv.count_free("van", 1) == 1  # 9201 vẫn được giữ lại trong kho
    # 9201 chỉ bị thử đúng 1 lần ở lượt Nội chính, lượt 3 bỏ qua 9201 để mặc thẳng 9202
    assert attempts == [(201, 9201), (201, 9202)]



def test_build_rename_plan_prefix_numbering_and_validation():
    from linhvuong.generals import (
        build_rename_plan,
        general_name_width,
        sanitize_general_name,
        validate_general_name,
    )

    assert sanitize_general_name("  DT_'1\" ") == "DT_’1’"
    assert general_name_width("DT_01") == 5
    assert general_name_width("吴沛祖") == 6
    assert validate_general_name("DT_01")[0] is True
    assert validate_general_name("")[0] is False
    assert validate_general_name("A" * 18)[0] is False

    g1 = _make_gen(1, "A", "vo")
    g2 = _make_gen(2, "B", "van")
    plan = build_rename_plan([(100, g1), (100, g2)], "DT_", numbered=True, start_index=1)
    assert [(g.id, n) for _, g, n in plan] == [(1, "DT_01"), (2, "DT_02")]

    # Khi >= 100 tướng (hoặc start_index >= 99), tự động pad 3 chữ số
    plan_100 = build_rename_plan([(100, g1), (100, g2)], "DT_", numbered=True, start_index=99)
    assert [(g.id, n) for _, g, n in plan_100] == [(1, "DT_099"), (2, "DT_100")]

    fixed = build_rename_plan([(100, g1)], "TàoTháo", numbered=False)
    assert fixed[0][2] == "TàoTháo"


def test_rename_generals_executes_and_handles_edge_cases():
    from linhvuong.generals import RENAME_STATUS_BLOCKED, rename_generals

    g1 = _make_gen(1, "Old1", "vo", status=16)  # Bận xuất chinh vẫn được đổi tên
    g2 = _make_gen(2, "DT_02", "van", status=0)  # Trùng tên mới -> skip
    g3 = _make_gen(3, "Blocked", "vo", status=RENAME_STATUS_BLOCKED)  # Bị khóa 35 -> skip
    g4 = _make_gen(4, "TooLong", "vo", status=0)
    g5 = _make_gen(5, "ServerErr", "vo", status=0)

    roster = Roster(
        cities=[_make_city(10129, "1")],
        _generals={10129: [g1, g2, g3, g4, g5]},
    )

    def _handler(ep, op_id, body):
        assert ep == "OPT.ashx" and op_id == 43
        if body["lGeneralID"] == "5":
            return {"ret": 15}
        return {"ret": 0}

    gw = FakeGateway(_handler)
    logs: list[str] = []
    summary = rename_generals(
        gw,
        roster,
        [(1, "DT_01"), (2, "DT_02"), (3, "DT_03"), (4, "A" * 18), (5, "DT_05")],
        on_log=logs.append,
    )
    assert summary.renamed == 1
    assert summary.skipped_same == 1
    assert summary.skipped_blocked == 1
    assert summary.invalid_name == 1
    assert summary.failed == 1
    assert len(gw.calls) == 2
    assert gw.calls[0][2] == {"lCityID": "10129", "lGeneralID": "1", "szNewName": "DT_01", "_": ""}


def test_add_general_point_validates_and_parses_server_errors():
    from linhvuong.generals import add_general_point

    def _handler(ep, op_id, body):
        assert ep == "OPT.ashx" and op_id == 67
        if body["lAttribType"] == "2":
            return {"ret": 77, "errMsg": "人物属性点分配过于悬殊"}
        if int(body["lAdd"]) > 5:
            return {"ret": 38, "errMsg": "没有可分配技能点"}
        return {"ret": 0}

    gw = FakeGateway(_handler)
    ok0, ret0, _ = add_general_point(gw, 10129, 25702, 1, 3)
    assert (ok0, ret0) == (True, 0)

    ok77, ret77, msg77 = add_general_point(gw, 10129, 25702, 2, 1)
    assert ok77 is False and ret77 == 77 and "tổng 2 thuộc tính" in msg77

    ok38, ret38, msg38 = add_general_point(gw, 10129, 25702, 1, 10)
    assert ok38 is False and ret38 == 38 and "Điểm Tiềm Năng" in msg38

    ok_bad, ret_bad, _ = add_general_point(gw, 10129, 25702, 4, 1)
    assert ok_bad is False and ret_bad == 1 and len(gw.calls) == 3

    ok_zero, ret_zero, _ = add_general_point(gw, 10129, 25702, 1, 0)
    assert ok_zero is False and ret_zero == 1 and len(gw.calls) == 3


def test_add_points_generals_pair_fixed_and_ret77_continuation():
    from linhvuong.generals import ADD_POINT_MODE_PAIR_1_3, add_points_generals

    # Mô phỏng tướng có skill_point=50; thuộc tính 1 đang bằng trần (200 == 50 + 150)
    # Lượt 1: +10 vào 1 -> ret=77; +10 vào 3 -> thành công (160) -> nới trần cho 1!
    # Lượt 2: +10 vào 1 -> thành công; +10 vào 3 -> thành công
    state = {"sp": 50, "s1": 200, "s2": 50, "s3": 150}

    def _handler(_ep, _op_id, body):
        attr = int(body["lAttribType"])
        amt = int(body["lAdd"])
        if amt > state["sp"]:
            return {"ret": 38}
        if attr == 1 and state["s1"] + amt > state["s2"] + state["s3"]:
            return {"ret": 77}
        if attr == 3 and state["s3"] + amt > state["s1"] + state["s2"]:
            return {"ret": 77}
        state["sp"] -= amt
        state[f"s{attr}"] += amt
        return {"ret": 0}

    g = General(id=10, name="QuanVũ", role="vo", level=50, morale=100, stamina=100, stamina_max=100, skill_point=50)
    roster = Roster(cities=[_make_city(10129, "1")], _generals={10129: [g]})
    gw = FakeGateway(_handler)

    summary = add_points_generals(gw, roster, [10], mode=ADD_POINT_MODE_PAIR_1_3, points_per_add=10, times=2)
    assert summary.generals_succeeded == 1
    assert summary.total_points_added == 30
    assert summary.requests_sent == 4
    assert summary.requests_succeeded == 3
    assert state == {"sp": 20, "s1": 210, "s2": 50, "s3": 170}


def test_add_points_generals_add_all_steps_down_10_3_1_max_and_pair():
    from linhvuong.generals import ADD_POINT_MODE_MAX_1, ADD_POINT_MODE_PAIR_1_3, add_points_generals

    # 1) Max 1 với 24 điểm: +10, +10, (thử +10 -> ret=38), +3, (thử +3 -> ret=38), +1, (thử +1 -> ret=38)
    sp_max = {"sp": 24, "s1": 100, "s2": 100, "s3": 100}

    def _max_handler(_ep, _op_id, body):
        amt = int(body["lAdd"])
        if amt > sp_max["sp"]:
            return {"ret": 38}
        sp_max["sp"] -= amt
        sp_max["s1"] += amt
        return {"ret": 0}

    g_max = General(id=11, name="TriệuVân", role="vo", level=50, morale=100, stamina=100, stamina_max=100, skill_point=24)
    r_max = Roster(cities=[_make_city(10129, "1")], _generals={10129: [g_max]})
    gw_max = FakeGateway(_max_handler)
    s_max = add_points_generals(gw_max, r_max, [11], mode=ADD_POINT_MODE_MAX_1, add_all=True)
    assert s_max.total_points_added == 24
    assert sp_max["sp"] == 0
    assert [int(b["lAdd"]) for _, _, b in gw_max.calls] == [10, 10, 10, 3, 3, 1, 1]

    # 2) Pair 1 & 3 với 27 điểm: +10 (1), +10 (3), thử +10 (1) -> ret=38 => hạ +3 (1), +3 (3), thử +3 (1) -> ret=38 => hạ +1 (1), thử +1 (3) -> ret=38
    sp_pair = {"sp": 27, "s1": 100, "s2": 100, "s3": 100}

    def _pair_handler(_ep, _op_id, body):
        attr = int(body["lAttribType"])
        amt = int(body["lAdd"])
        if amt > sp_pair["sp"]:
            return {"ret": 38}
        sp_pair["sp"] -= amt
        sp_pair[f"s{attr}"] += amt
        return {"ret": 0}

    g_pair = General(id=12, name="GiaCát", role="van", level=50, morale=100, stamina=100, stamina_max=100, skill_point=27)
    r_pair = Roster(cities=[_make_city(10129, "1")], _generals={10129: [g_pair]})
    gw_pair = FakeGateway(_pair_handler)
    s_pair = add_points_generals(gw_pair, r_pair, [12], mode=ADD_POINT_MODE_PAIR_1_3, add_all=True)
    assert s_pair.total_points_added == 27
    assert sp_pair == {"sp": 0, "s1": 114, "s2": 100, "s3": 113}


def test_add_points_generals_allows_busy_skips_zero_points_and_supports_stop():
    import threading
    from linhvuong.generals import ADD_POINT_MODE_MAX_1, add_points_generals

    g_busy = General(id=1, name="Busy", role="vo", level=10, morale=100, stamina=100, stamina_max=100, status=16, skill_point=20)
    g_zero = General(id=2, name="Zero", role="van", level=10, morale=100, stamina=100, stamina_max=100, status=0, skill_point=0)
    g_ok = General(id=3, name="Ready", role="vo", level=10, morale=100, stamina=100, stamina_max=100, status=0, skill_point=30)
    roster = Roster(cities=[_make_city(10129, "1")], _generals={10129: [g_busy, g_zero, g_ok]})

    stop_ev = threading.Event()
    calls = []

    def _handler(_ep, _op_id, body):
        calls.append(int(body["lGeneralID"]))
        if len(calls) == 1:
            return {"ret": 0}
        if len(calls) == 2:
            # Lần 2 của g_busy gặp hết điểm -> sang g_ok
            return {"ret": 38}
        stop_ev.set()
        return {"ret": 0}

    gw = FakeGateway(_handler)
    s = add_points_generals(gw, roster, [1, 2, 3, 999], mode=ADD_POINT_MODE_MAX_1, points_per_add=10, stop_event=stop_ev)
    assert s.skipped_no_points == 1
    assert s.total_points_added == 20
    assert s.generals_succeeded == 2
    assert calls == [1, 1, 3]
    assert s.stopped is True
