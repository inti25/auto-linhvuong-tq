import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from linhvuong.dashboard import Dashboard
from linhvuong.gateway import GatewayClient
from linhvuong.roster import Army, City, General, Roster

try:
    import _tkinter
except ImportError:
    _tkinter = None


def safe_dashboard(roster_mock=None):
    if _tkinter is None:
        pytest.skip("tkinter not available")
    session = MagicMock()
    # Mock reload thread so it doesn't make real requests
    with patch("threading.Thread") as mock_thread:
        try:
            dash = Dashboard(session, 57)
            dash.withdraw()
        except Exception as e:
            pytest.skip(f"Tkinter display error: {e}")
    return dash


def dummy_roster():
    c1 = City(id=15230, name="ThanhChinh", type="Thành", pos_x=100, pos_y=200, level=20)
    c2 = City(id=15237, name="PhanThanh", type="Thành", pos_x=105, pos_y=205, level=15)
    camp1 = City(id=-1085, name="TienDon", type="Doanh trại", pos_x=110, pos_y=210)
    g1 = General(id=417506, name="TrieuVan", role="vo", level=10, morale=100, stamina=95, stamina_max=100)
    g2 = General(id=417513, name="GiaCatLuong", role="van", level=12, morale=100, stamina=100, stamina_max=100)
    g3 = General(id=417520, name="QuanVu", role="vo", level=11, morale=100, stamina=90, stamina_max=100)
    return Roster(
        cities=[c1, c2],
        camps=[camp1],
        _generals={15230: [g1, g2], -1085: [g3]},
        _armies={417506: Army(100, 200, 300), 417520: Army(500, 0, 0)},
    )


def test_dashboard_initializes_six_tabs():
    dash = safe_dashboard()
    try:
        tabs = dash.notebook.tabs()
        assert len(tabs) == 6
        tab_texts = [dash.notebook.tab(t, "text") for t in tabs]
        assert "🏰 Tổng quan & Quân đội" in tab_texts[0]
        assert "⚔️ Thảo Phạt" in tab_texts[1]
        assert "🧛 Gọi Dân & Vong Linh" in tab_texts[2]
        assert "🏕️ Bình Man & Di Trại" in tab_texts[3]
        assert "🏗️ Xây Dựng" in tab_texts[4]
        assert "🔬 Đại Học & Hậu Cần" in tab_texts[5]
    finally:
        dash.destroy()


def test_dashboard_loaded_populates_camps_and_filters_martial_generals():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # Tab 1: City Tree phải hiện cả 2 Thành và 1 Doanh trại
        city_items = dash.city_tree.get_children()
        assert len(city_items) == 3

        c0_vals = dash.city_tree.item(city_items[0], "values")
        c2_vals = dash.city_tree.item(city_items[2], "values")
        assert c0_vals[0] == "Thành"
        assert int(c0_vals[1]) == 15230
        assert c2_vals[0] == "Doanh trại"
        assert int(c2_vals[1]) == -1085

        # Comboboxes nhận căn cứ
        assert len(dash.tp_city_combo["values"]) == 3
        assert len(dash.gd_city_combo["values"]) == 2  # Chỉ gọi dân ở Thành kiên cố
        assert len(dash.bm_parent_city_combo["values"]) == 2  # Căn cứ xuất phát (Thành cha)
        assert len(dash.bm_city_combo["values"]) == 1  # Doanh trại cần di dời
        assert len(dash.bld_city_combo["values"]) == 2  # Chỉ xây ở Thành kiên cố
        assert len(dash.res_city_combo["values"]) == 2  # Nghiên cứu ở Thành kiên cố
        assert len(dash.log_from_city_combo["values"]) == 3
        assert len(dash.log_to_city_combo["values"]) == 3

        # Tab 2: Thảo Phạt chọn thành chính (15230)
        # Chỉ có võ tướng (TrieuVan) xuất hiện, GiaCatLuong (van) bị lọc bỏ hoàn toàn
        dash.tp_city_combo.current(0)
        dash._on_tp_city_selected()
        tp_gens = dash.tp_gen_tree.get_children()
        assert len(tp_gens) == 1
        assert dash.tp_gen_tree.item(tp_gens[0], "text") == "TrieuVan"

        # Tab 2: Thảo phạt chọn Doanh trại (-1085)
        dash.tp_city_combo.current(2)
        dash._on_tp_city_selected()
        tp_camp_gens = dash.tp_gen_tree.get_children()
        assert len(tp_camp_gens) == 1
        assert dash.tp_gen_tree.item(tp_camp_gens[0], "text") == "QuanVu"
    finally:
        dash.destroy()


def test_dashboard_building_tree_interactive_controls():
    dash = safe_dashboard()
    try:
        bld_items = dash.bld_tree.get_children()
        assert len(bld_items) == 16
        assert dash.bld_tree.item(bld_items[0], "text") == "官府 - Quan Phủ"

        # Kiểm tra Select All / Deselect All
        dash._select_all_bld(False)
        for iid in dash.bld_tree.get_children():
            assert dash.bld_tree.item(iid, "values")[0] == "☐"

        dash._select_all_bld(True)
        for iid in dash.bld_tree.get_children():
            assert dash.bld_tree.item(iid, "values")[0] == "☑"

        # Kiểm tra thay đổi thứ tự ưu tiên (Move Down / Move Up)
        first_item = bld_items[0]
        second_item = bld_items[1]
        dash.bld_tree.selection_set(first_item)
        dash._move_bld_down()
        new_children = dash.bld_tree.get_children()
        assert new_children[0] == second_item
        assert new_children[1] == first_item

        dash._move_bld_up()
        new_children_after_up = dash.bld_tree.get_children()
        assert new_children_after_up[0] == first_item

        # Kiểm tra đặt Cấp mục tiêu
        dash.bld_target_lvl_var.set("25")
        dash._set_bld_target_lvl()
        updated_vals = dash.bld_tree.item(first_item, "values")
        assert int(updated_vals[4]) == 25
    finally:
        dash.destroy()


def test_dashboard_tech_tree_interactive_controls():
    dash = safe_dashboard()
    try:
        res_items = dash.res_tree.get_children()
        # Hiển thị đầy đủ 29 kỹ thuật đại học
        assert len(res_items) == 29

        # Kiểm tra Select All / Deselect All
        dash._select_all_res(False)
        for iid in dash.res_tree.get_children():
            assert dash.res_tree.item(iid, "values")[0] == "☐"

        dash._select_all_res(True)
        for iid in dash.res_tree.get_children():
            assert dash.res_tree.item(iid, "values")[0] == "☑"

        # Kiểm tra thay đổi thứ tự ưu tiên (Move Down / Move Up)
        first_item = res_items[0]
        second_item = res_items[1]
        dash.res_tree.selection_set(first_item)
        dash._move_res_down()
        new_children = dash.res_tree.get_children()
        assert new_children[0] == second_item
        assert new_children[1] == first_item

        dash._move_res_up()
        new_children_after_up = dash.res_tree.get_children()
        assert new_children_after_up[0] == first_item

        # Kiểm tra đặt Cấp mục tiêu
        dash.res_target_lvl_var.set("28")
        dash._set_res_target_lvl()
        updated_vals = dash.res_tree.item(first_item, "values")
        assert int(updated_vals[2]) == 28
    finally:
        dash.destroy()

