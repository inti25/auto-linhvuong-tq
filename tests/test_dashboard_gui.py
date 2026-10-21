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
    c1 = City(id=15230, name="ThanhChinh")
    c2 = City(id=15237, name="PhanThanh")
    g1 = General(id=417506, name="TrieuVan", role="vo", level=10, morale=100, stamina=95, stamina_max=100)
    g2 = General(id=417513, name="GiaCatLuong", role="van", level=12, morale=100, stamina=100, stamina_max=100)
    return Roster(cities=[c1, c2], _generals={15230: [g1, g2]}, _armies={417506: Army(100, 200, 300)})


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


def test_dashboard_loaded_populates_combos_and_trees():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # Tab 1: City Tree
        city_items = dash.city_tree.get_children()
        assert len(city_items) == 2
        assert dash.city_tree.item(city_items[0], "text") == "ThanhChinh"

        # Tab 2, 3, 4, 5, 6 combos
        assert len(dash.tp_city_combo["values"]) == 2
        assert len(dash.gd_city_combo["values"]) == 2
        assert len(dash.bm_city_combo["values"]) == 2
        assert len(dash.bld_city_combo["values"]) == 2
        assert len(dash.res_city_combo["values"]) == 2
        assert len(dash.log_from_city_combo["values"]) == 2
        assert len(dash.log_to_city_combo["values"]) == 2

        # Kiểm tra Thảo Phạt chọn thành
        dash.tp_city_combo.current(0)
        dash._on_tp_city_selected()
        tp_gens = dash.tp_gen_tree.get_children()
        # Chỉ có võ tướng (TrieuVan) xuất hiện
        assert len(tp_gens) == 1
        assert dash.tp_gen_tree.item(tp_gens[0], "text") == "TrieuVan"
    finally:
        dash.destroy()


def test_dashboard_building_and_tech_tree_populated():
    dash = safe_dashboard()
    try:
        # Nạp kế hoạch xây dựng mẫu
        dash._load_build_plans()
        bld_items = dash.bld_tree.get_children()
        assert len(bld_items) > 0

        # Nạp kế hoạch kỹ thuật đại học mẫu
        dash._load_tech_plans()
        res_items = dash.res_tree.get_children()
        assert len(res_items) > 0
    finally:
        dash.destroy()
