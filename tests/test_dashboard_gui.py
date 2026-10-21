import tkinter as tk
from tkinter import ttk
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

        # Kiểm tra đặt Cấp mục tiêu cho item được chọn
        dash.bld_target_lvl_var.set("25")
        dash._set_bld_target_lvl()
        updated_vals = dash.bld_tree.item(first_item, "values")
        assert int(updated_vals[4]) == 25

        # Kiểm tra số slot xây dựng mặc định là 3
        assert dash.bld_slots_combo.get() == "3"
        assert list(dash.bld_slots_combo["values"]) == ["1", "2", "3"]

        # Kiểm tra đặt Cấp mục tiêu = 0 (Dỡ bỏ hoàn toàn)
        dash.bld_target_lvl_var.set("0")
        dash._set_bld_target_lvl()
        updated_vals_zero = dash.bld_tree.item(first_item, "values")
        assert int(updated_vals_zero[4]) == 0

        # Kiểm tra đặt Cấp mục tiêu cho TẤT CẢ công trình
        dash.bld_target_lvl_var.set("30")
        dash._set_bld_target_lvl_all()
        for iid in dash.bld_tree.get_children():
            assert int(dash.bld_tree.item(iid, "values")[4]) == 30

        # Kiểm tra các điều khiển tự động mở đạo cụ tài nguyên
        assert hasattr(dash, "bld_open_box_var")
        assert dash.bld_open_box_var.get() is False
        assert hasattr(dash, "bld_box_combo")
        assert len(dash.bld_box_combo["values"]) == 5
        assert "24: 民生之鼎 - Dân Sinh Bảo Đỉnh" in dash.bld_box_combo.get()
        assert dash.bld_box_max_var.get() == "5"
        assert dash.bld_box_fallback_var.get() is True
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

        # Kiểm tra đặt Cấp mục tiêu cho item được chọn
        dash.res_target_lvl_var.set("28")
        dash._set_res_target_lvl()
        updated_vals = dash.res_tree.item(first_item, "values")
        assert int(updated_vals[2]) == 28

        # Kiểm tra đặt Cấp mục tiêu cho TẤT CẢ kỹ thuật
        dash.res_target_lvl_var.set("25")
        dash._set_res_target_lvl_all()
        for iid in dash.res_tree.get_children():
            assert int(dash.res_tree.item(iid, "values")[2]) == 25
    finally:
        dash.destroy()


def test_dashboard_unified_profile_export_and_import(tmp_path):
    dash = safe_dashboard()
    try:
        # Cấu hình các giá trị test trên GUI
        dash.bld_slots_combo.set("2")
        dash.bld_speedup_var.set(True)
        dash.bld_target_lvl_var.set("27")
        dash._set_bld_target_lvl_all()

        dash.res_art_var.set(True)
        dash.res_target_lvl_var.set("18")
        dash._set_res_target_lvl_all()

        dash.tp_min_army_var.set("7500")
        dash.gd_radius_var.set("9")

        dash.bld_open_box_var.set(True)
        dash.bld_box_combo.current(1)
        dash.bld_box_max_var.set("8")
        dash.bld_box_fallback_var.set(False)

        # Lưu hồ sơ tổng hợp
        prof_file = tmp_path / "custom_profile.json"
        saved_path = dash._save_unified_profile(prof_file)
        assert saved_path.exists()

        # Thay đổi dữ liệu trên GUI để kiểm tra nạp lại
        dash.bld_slots_combo.set("1")
        dash.bld_speedup_var.set(False)
        dash.bld_target_lvl_var.set("10")
        dash._set_bld_target_lvl_all()
        dash.bld_open_box_var.set(False)
        dash.bld_box_combo.current(0)
        dash.bld_box_max_var.set("2")
        dash.bld_box_fallback_var.set(True)
        dash.res_art_var.set(False)
        dash.tp_min_army_var.set("1000")
        dash.gd_radius_var.set("3")

        # Nạp lại hồ sơ
        ok, msg = dash._load_unified_profile(prof_file)
        assert ok is True
        assert "Xây Dựng" in msg
        assert "Đại Học" in msg

        # Kiểm tra dữ liệu được khôi phục chính xác
        assert dash.bld_slots_combo.get() == "2"
        assert dash.bld_speedup_var.get() is True
        assert dash.bld_open_box_var.get() is True
        assert dash.bld_box_combo.current() == 1
        assert dash.bld_box_max_var.get() == "8"
        assert dash.bld_box_fallback_var.get() is False
        for iid in dash.bld_tree.get_children():
            assert int(dash.bld_tree.item(iid, "values")[4]) == 27

        assert dash.res_art_var.get() is True
        for iid in dash.res_tree.get_children():
            assert int(dash.res_tree.item(iid, "values")[2]) == 18

        assert dash.tp_min_army_var.get() == "7500"
        assert dash.gd_radius_var.get() == "9"
    finally:
        dash.destroy()


def test_dashboard_unified_profile_backward_compatibility(tmp_path):
    import json
    dash = safe_dashboard()
    try:
        # 1. Test tương thích ngược với build_plans.json cũ
        old_build_file = tmp_path / "old_build_plans.json"
        old_build_file.write_text(
            json.dumps({
                "plans": [
                    {"pid": 1, "gid": 1, "target_level": 31, "name": "Quan Phủ", "enabled": True},
                    {"pid": 2, "gid": 2, "target_level": 29, "name": "Tường Thành", "enabled": False},
                ]
            }),
            encoding="utf-8",
        )
        ok, msg = dash._load_unified_profile(old_build_file)
        assert ok is True
        bld_items = dash.bld_tree.get_children()
        assert len(bld_items) == 2
        assert int(dash.bld_tree.item("1", "values")[4]) == 31
        assert dash.bld_tree.item("1", "values")[0] == "☑"
        assert int(dash.bld_tree.item("2", "values")[4]) == 29
        assert dash.bld_tree.item("2", "values")[0] == "☐"

        # 2. Test tương thích ngược với tech_plans.json cũ
        old_tech_file = tmp_path / "old_tech_plans.json"
        old_tech_file.write_text(
            json.dumps({
                "techs": [
                    {"id": 1, "target_level": 23, "name": "Đao Thuật", "enabled": True},
                ]
            }),
            encoding="utf-8",
        )
        ok2, msg2 = dash._load_unified_profile(old_tech_file)
        assert ok2 is True
        res_items = dash.res_tree.get_children()
        assert len(res_items) == 1
        assert int(dash.res_tree.item("1", "values")[2]) == 23
    finally:
        dash.destroy()


def test_dashboard_thaophat_controls_and_profile_sync(tmp_path):
    import json
    dash = safe_dashboard()
    try:
        # Kiểm tra sự tồn tại và giá trị mặc định của các control Thảo Phạt mới
        assert hasattr(dash, "tp_target_inf_var")
        assert hasattr(dash, "tp_target_cav_var")
        assert hasattr(dash, "tp_target_arc_var")
        assert hasattr(dash, "tp_auto_recruit_var")
        assert hasattr(dash, "tp_auto_morale_var")
        assert hasattr(dash, "tp_min_morale_var")

        assert dash.tp_target_inf_var.get() == "5000"
        assert dash.tp_target_cav_var.get() == "0"
        assert dash.tp_target_arc_var.get() == "0"
        assert dash.tp_auto_recruit_var.get() is True
        assert dash.tp_auto_morale_var.get() is True
        assert dash.tp_min_morale_var.get() == "95"

        # Thay đổi giá trị và thu thập hồ sơ
        dash.tp_target_inf_var.set("3000")
        dash.tp_target_cav_var.set("1000")
        dash.tp_target_arc_var.set("2000")
        dash.tp_auto_recruit_var.set(False)
        dash.tp_auto_morale_var.set(True)
        dash.tp_min_morale_var.set("90")

        profile = dash._collect_unified_profile()
        assert profile["thao_phat"]["target_infantry"] == "3000"
        assert profile["thao_phat"]["target_cavalry"] == "1000"
        assert profile["thao_phat"]["target_archers"] == "2000"
        assert profile["thao_phat"]["auto_recruit"] is False
        assert profile["thao_phat"]["auto_morale"] is True
        assert profile["thao_phat"]["min_morale"] == "90"

        # Nạp lại profile khác
        new_data = {
            "thao_phat": {
                "target_infantry": "4000",
                "target_cavalry": "1500",
                "target_archers": "500",
                "auto_recruit": True,
                "auto_morale": False,
                "min_morale": "85",
            }
        }
        loaded = dash._apply_unified_profile(new_data)
        assert "Thảo Phạt" in loaded
        assert dash.tp_target_inf_var.get() == "4000"
        assert dash.tp_target_cav_var.get() == "1500"
        assert dash.tp_target_arc_var.get() == "500"
        assert dash.tp_auto_recruit_var.get() is True
        assert dash.tp_auto_morale_var.get() is False
        assert dash.tp_min_morale_var.get() == "85"
    finally:
        dash.destroy()


def test_dashboard_thaophat_row_layout_and_troops_columns():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)
        dash.tp_city_combo.current(0)
        dash._on_tp_city_selected()

        # Kiểm tra bảng tướng có 8 cột chi tiết
        cols = dash.tp_gen_tree["columns"]
        assert "infantry" in cols
        assert "cavalry" in cols
        assert "archers" in cols
        assert "total_army" in cols

        tp_gens = dash.tp_gen_tree.get_children()
        assert len(tp_gens) == 1
        vals = dash.tp_gen_tree.item(tp_gens[0], "values")
        # values: ("☐", g.level, stamina, morale, inf, cav, arc, total)
        assert vals[0] == "☐"
        assert int(vals[4]) == 100  # Bộ binh
        assert int(vals[5]) == 200  # Kỵ binh
        assert int(vals[6]) == 300  # Cung binh
        assert int(vals[7]) == 600  # Tổng quân
    finally:
        dash.destroy()


def test_dashboard_combobox_dark_palette_and_contrast():
    dash = safe_dashboard()
    try:
        style = ttk.Style(dash)
        field_map = dict(style.map("TCombobox", "fieldbackground"))
        fg_map = dict(style.map("TCombobox", "foreground"))

        # Kiểm tra chế độ readonly có nền tối và chữ trắng tương phản cao
        assert field_map.get("readonly") == "#2a2e45"
        assert fg_map.get("readonly") == "#ffffff"

        # Kiểm tra popdown listbox trên combobox thực tế
        cb = dash.tp_city_combo
        popdown = cb.tk.eval(f"ttk::combobox::PopdownWindow {cb}")
        lb = f"{popdown}.f.l"
        bg = cb.tk.eval(f"{lb} cget -background")
        fg = cb.tk.eval(f"{lb} cget -foreground")
        assert bg == "#1e2130"
        assert fg == "#ffffff"
    finally:
        dash.destroy()


def test_dashboard_multi_city_building_ui_and_plan_separation():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # 1. Kiểm tra danh sách Căn cứ thi công (Thành & Doanh trại)
        base_items = dash.bld_bases_tree.get_children()
        assert len(base_items) == 3  # 2 Thành + 1 Doanh trại

        # Mặc định căn cứ đầu tiên được chọn
        b0_vals = dash.bld_bases_tree.item(base_items[0], "values")
        assert b0_vals[0] == "☑"
        assert b0_vals[1] == "Thành"
        assert int(b0_vals[2]) == 15230

        # Kiểm tra Select All / Deselect All cho căn cứ
        dash._select_all_bld_bases(False)
        assert len(dash._selected_building_cities) == 0
        for iid in dash.bld_bases_tree.get_children():
            assert dash.bld_bases_tree.item(iid, "values")[0] == "☐"

        dash._select_all_bld_bases(True)
        assert len(dash._selected_building_cities) == 3
        for iid in dash.bld_bases_tree.get_children():
            assert dash.bld_bases_tree.item(iid, "values")[0] == "☑"

        # 2. Kiểm tra tính độc lập cấu hình giữa các căn cứ
        # Căn cứ 1 (15230): Đặt cấp công trình ô 1 = 30
        dash._switch_bld_base(15230)
        dash.bld_tree.selection_set("1")
        dash.bld_target_lvl_var.set("30")
        dash._set_bld_target_lvl()
        assert int(dash.bld_tree.item("1", "values")[4]) == 30

        # Chuyển sang Căn cứ 2 (15237): Đặt cấp công trình ô 1 = 18
        dash._switch_bld_base(15237)
        assert dash._current_bld_city_id == 15237
        dash.bld_tree.selection_set("1")
        dash.bld_target_lvl_var.set("18")
        dash._set_bld_target_lvl()
        assert int(dash.bld_tree.item("1", "values")[4]) == 18

        # Chuyển lại Căn cứ 1 (15230): Cấp ô 1 vẫn phải là 30
        dash._switch_bld_base(15230)
        assert int(dash.bld_tree.item("1", "values")[4]) == 30

        # Chuyển lại Căn cứ 2 (15237): Cấp ô 1 vẫn là 18
        dash._switch_bld_base(15237)
        assert int(dash.bld_tree.item("1", "values")[4]) == 18
    finally:
        dash.destroy()


def test_dashboard_building_multi_runner_execution():
    from unittest.mock import MagicMock
    from linhvuong.dashboard import BuildingAutoRunner
    from linhvuong.tasks.building import BuildingTask

    t1 = MagicMock(spec=BuildingTask)
    t1.city_id = 101
    t1.city_name = "Thành 1"
    t1.run_once.side_effect = ["upgrading", "all_buildings_completed"]

    t2 = MagicMock(spec=BuildingTask)
    t2.city_id = 102
    t2.city_name = "Thành 2"
    t2.run_once.side_effect = ["upgrading", "all_buildings_completed"]

    logs = []
    statuses = []
    runner = BuildingAutoRunner(
        task_or_tasks=[t1, t2],
        interval=0.01,
        log_cb=logs.append,
        status_cb=statuses.append,
    )
    runner.start()
    runner.join(timeout=2.0)

    assert not runner.is_alive()
    assert t1.run_once.call_count >= 2
    assert t2.run_once.call_count >= 2
    assert any("2 căn cứ" in m for m in logs)
    assert any("Toàn bộ công trình quy hoạch của tất cả các căn cứ đã hoàn tất" in m for m in logs)


def test_dashboard_multi_city_profile_sync(tmp_path):
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # Cấu hình căn cứ 1 (15230)
        dash._switch_bld_base(15230)
        dash.bld_tree.selection_set("1")
        dash.bld_target_lvl_var.set("31")
        dash._set_bld_target_lvl()

        # Cấu hình căn cứ 2 (15237)
        dash._switch_bld_base(15237)
        dash.bld_tree.selection_set("1")
        dash.bld_target_lvl_var.set("19")
        dash._set_bld_target_lvl()

        # Lưu hồ sơ
        prof_file = tmp_path / "multi_city_profile.json"
        saved = dash._save_unified_profile(prof_file)
        assert saved.exists()

        # Reset dữ liệu trên giao diện
        dash._switch_bld_base(15230)
        dash.bld_tree.selection_set("1")
        dash.bld_target_lvl_var.set("10")
        dash._set_bld_target_lvl()

        # Nạp lại hồ sơ
        ok, msg = dash._load_unified_profile(prof_file)
        assert ok is True

        # Kiểm tra căn cứ 1 khôi phục mức 31
        dash._switch_bld_base(15230)
        assert int(dash.bld_tree.item("1", "values")[4]) == 31

        # Kiểm tra căn cứ 2 khôi phục mức 19
        dash._switch_bld_base(15237)
        assert int(dash.bld_tree.item("1", "values")[4]) == 19
    finally:
        dash.destroy()






