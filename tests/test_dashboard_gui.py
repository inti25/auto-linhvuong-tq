import json
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch
import pytest

from linhvuong.dashboard import Dashboard
from linhvuong.gateway import GatewayClient
from linhvuong.profile import CityCraftConfig
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
        assert "🏛️ Nội Chính & Nghiên Cứu" in tab_texts[0]
        assert "⚔️ Thảo Phạt" in tab_texts[1]
        assert "🏕️ Bình Man" in tab_texts[2]
        assert "🧛 Vong Linh" in tab_texts[3]
        assert "🏰 Tổng quan" in tab_texts[4]
        assert "⚔️ Chiến Trường" in tab_texts[5]
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
        dash.bld_speedup_item_combo.set("Coin")
        dash.bld_speedup_hours_var.set("3")
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
        dash.bld_speedup_item_combo.set("Ngân Bảo")
        dash.bld_speedup_hours_var.set("1")
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
        assert dash.bld_speedup_item_combo.get() == "Coin"
        assert dash.bld_speedup_hours_var.get() == "3"
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

        # Kiểm tra cấu hình màu sắc popdown listbox trên combobox
        cb = dash.tp_city_combo
        lb = tk.Listbox(cb)
        bg = cb.tk.eval(f"option get {lb} background Listbox")
        fg = cb.tk.eval(f"option get {lb} foreground Listbox")
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
        assert b0_vals[3] == "Thành"
        assert int(b0_vals[4]) == 15230

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


def test_dashboard_configurable_intervals_and_profile_sync(tmp_path):
    dash = safe_dashboard()
    try:
        # 1. Kiểm tra giá trị mặc định của 5 biến interval
        assert dash.tp_interval_var.get() == "10"
        assert dash.gd_interval_var.get() == "10"
        assert dash.bm_interval_var.get() == "15"
        assert dash.bld_interval_var.get() == "20"
        assert dash.res_interval_var.get() == "30"

        # 2. Thay đổi giá trị tùy chỉnh
        dash.tp_interval_var.set("8")
        dash.gd_interval_var.set("12")
        dash.bm_interval_var.set("25")
        dash.bld_interval_var.set("18")
        dash.res_interval_var.set("45")

        # 3. Thu thập và kiểm tra profile dictionary
        profile = dash._collect_unified_profile()
        assert profile["thao_phat"]["interval"] == "8"
        assert profile["goi_dan"]["interval"] == "12"
        assert profile["binh_man"]["interval"] == "25"
        assert profile["building"]["interval"] == "18"
        assert profile["research"]["interval"] == "45"

        # 4. Lưu ra file và reset giao diện
        prof_file = tmp_path / "interval_profile.json"
        saved = dash._save_unified_profile(prof_file)
        assert saved.exists()

        dash.tp_interval_var.set("10")
        dash.gd_interval_var.set("10")
        dash.bm_interval_var.set("15")
        dash.bld_interval_var.set("20")
        dash.res_interval_var.set("30")

        # 5. Nạp lại profile và kiểm tra khôi phục
        ok, msg = dash._load_unified_profile(prof_file)
        assert ok is True
        assert dash.tp_interval_var.get() == "8"
        assert dash.gd_interval_var.get() == "12"
        assert dash.bm_interval_var.get() == "25"
        assert dash.bld_interval_var.get() == "18"
        assert dash.res_interval_var.get() == "45"
    finally:
        dash.destroy()


def test_base_task_runner_and_thao_phat_wait_cycle():
    from linhvuong.dashboard import BaseTaskRunner
    from linhvuong.tasks.thao_phat import ThaoPhatAutoRunner
    from unittest.mock import MagicMock

    # 1. BaseTaskRunner.wait_cycle
    b_runner = BaseTaskRunner("TestRunner", lambda m: None, lambda s: None)
    with patch.object(b_runner.stop_event, "wait", return_value=False) as mock_wait:
        # Với seconds <= 3.0, actual_wait = max(1.0, seconds)
        b_runner.wait_cycle(2.0)
        assert mock_wait.call_args[0][0] == 2.0

        b_runner.wait_cycle(0.5)
        assert mock_wait.call_args[0][0] == 1.0

        # Với seconds > 3.0, actual_wait trong khoảng [seconds - jitter, seconds + jitter]
        b_runner.wait_cycle(10.0, jitter=2.0)
        called_sec = mock_wait.call_args[0][0]
        assert 8.0 <= called_sec <= 12.0

    # 2. ThaoPhatAutoRunner.wait_cycle
    tp_runner = ThaoPhatAutoRunner(gateway=MagicMock(), check_interval=10.0)
    with patch.object(tp_runner.stop_event, "wait", return_value=False) as mock_tp_wait:
        tp_runner.wait_cycle(2.5)
        assert mock_tp_wait.call_args[0][0] == 2.5

        tp_runner.wait_cycle(15.0, jitter=2.0)
        called_sec = mock_tp_wait.call_args[0][0]
        assert 13.0 <= called_sec <= 17.0


def test_dashboard_account_bound_profile(tmp_path, monkeypatch):
    if _tkinter is None:
        pytest.skip("tkinter not available")
    monkeypatch.chdir(tmp_path)
    session = MagicMock()
    with patch("threading.Thread"):
        try:
            dash = Dashboard(session, 53, username="quilia")
            dash.withdraw()
        except Exception as e:
            pytest.skip(f"Tkinter display error: {e}")
        try:
            # 1. Kiểm tra tiêu đề cửa sổ mang username
            assert "quilia" in dash.title()
            assert "53" in dash.title()
            assert dash.title() == "LinhVuong - S53 - [quilia]"

            # 2. Kiểm tra tên profile mặc định là file riêng của account
            assert dash.default_profile_name == "auto_profile_quilia_53.json"
            assert dash.profile_path_var.get() == "auto_profile_quilia_53.json"

            # 3. Lưu profile mặc định và kiểm tra đúng file riêng được tạo
            saved = dash._save_unified_profile()
            assert saved.name == "auto_profile_quilia_53.json"
            assert (tmp_path / "auto_profile_quilia_53.json").exists()
        finally:
            dash.destroy()


def test_dashboard_bld_tree_tag_colors():
    dash = safe_dashboard()
    try:
        assert dash._get_bld_row_tag(1, 10) == "upgrade"
        assert dash._get_bld_row_tag(10, 1) == "downgrade"
        assert dash._get_bld_row_tag(5, 5) == "completed"

        plans = [
            {"pid": 1, "gid": 1, "cur_lvl": 2, "target_level": 5, "enabled": True},
            {"pid": 2, "gid": 2, "cur_lvl": 8, "target_level": 3, "enabled": True},
            {"pid": 3, "gid": 3, "cur_lvl": 5, "target_level": 5, "enabled": True},
        ]
        dash._render_bld_tree_from_plans(plans)
        assert dash.bld_tree.item("1", "tags") == ("upgrade",)
        assert dash.bld_tree.item("2", "tags") == ("downgrade",)
        assert dash.bld_tree.item("3", "tags") == ("completed",)

        # Đổi mục tiêu của ô 1 từ 5 xuống 1 -> biến thành hạ cấp
        dash.bld_tree.selection_set("1")
        dash.bld_target_lvl_var.set("1")
        dash._set_bld_target_lvl()
        assert dash.bld_tree.item("1", "tags") == ("downgrade",)

        # Đổi mục tiêu của ô 1 bằng cấp hiện tại (2) -> hoàn thành
        dash.bld_target_lvl_var.set("2")
        dash._set_bld_target_lvl()
        assert dash.bld_tree.item("1", "tags") == ("completed",)
    finally:
        dash.destroy()


def test_dashboard_even_upgrade_and_research_profile_sync():
    dash = safe_dashboard()
    try:
        # Building tab không còn bld_even_var
        assert not hasattr(dash, "bld_even_var")

        # Research tab vẫn giữ res_even_var
        dash.res_even_var.set(True)

        data = dash._collect_unified_profile()
        assert "even_upgrade" not in data["building"]
        assert data["research"].get("even_research") is True

        # Đặt lại False rồi nạp lại từ data
        dash.res_even_var.set(False)
        assert dash.res_even_var.get() is False

        # Tương thích ngược: Nạp profile cũ có chứa cả even_upgrade ở building
        old_profile = dict(data)
        old_profile["building"]["even_upgrade"] = True
        dash._apply_unified_profile(old_profile)
        assert dash.res_even_var.get() is True
    finally:
        dash.destroy()


def test_dashboard_sync_city_buildings_data_preserves_queue_order():
    dash = safe_dashboard()
    try:
        dash._current_bld_city_id = 15230
        dash.bld_tree.delete(*dash.bld_tree.get_children())

        # Thiết lập thứ tự người dùng tùy biến: 6 -> 1 -> 3
        custom_plans = [
            {"pid": 6, "gid": 6, "name": "Đại Học Điện", "cur_lvl": 5, "target_level": 20, "enabled": True},
            {"pid": 1, "gid": 1, "name": "Quan Phủ", "cur_lvl": 10, "target_level": 20, "enabled": True},
            {"pid": 3, "gid": 3, "name": "Nhà Dân", "cur_lvl": 8, "target_level": 15, "enabled": True},
        ]
        dash._city_building_plans[15230] = list(custom_plans)
        dash._render_bld_tree_from_plans(custom_plans)

        children_before = dash.bld_tree.get_children("")
        assert list(children_before) == ["6", "1", "3"]

        # Giả lập server trả về dữ liệu thực tế theo thứ tự mặc định 1, 2, 3, 6 (có ô 2 mới xây thêm)
        server_buildings = [
            {"pid": 1, "gid": 1, "level": 11, "name": "Quan Phủ"},
            {"pid": 2, "gid": 2, "level": 3, "name": "Tường Thành"},  # Ô mới
            {"pid": 3, "gid": 3, "level": 8, "name": "Nhà Dân"},
            {"pid": 6, "gid": 6, "level": 6, "name": "Đại Học Điện"},
        ]

        dash._sync_city_buildings_data(15230, server_buildings, from_auto_cycle=True)

        # 1. Kiểm tra thứ tự trên Treeview: 6 -> 1 -> 3 phải giữ nguyên, 2 thêm vào cuối
        children_after = dash.bld_tree.get_children("")
        assert list(children_after) == ["6", "1", "3", "2"]

        # 2. Cấp độ thực tế được cập nhật in-place
        vals_6 = dash.bld_tree.item("6", "values")
        vals_1 = dash.bld_tree.item("1", "values")
        vals_2 = dash.bld_tree.item("2", "values")

        assert int(vals_6[3]) == 6   # cur_lvl của ô 6 tăng từ 5 lên 6
        assert int(vals_1[3]) == 11  # cur_lvl của ô 1 tăng từ 10 lên 11
        assert vals_2[0] == "☐"      # Ô 2 mới mặc định bỏ chọn
        assert int(vals_2[3]) == 3   # cur_lvl ô 2 là 3
        assert int(vals_2[4]) == 3   # target_level ô 2 mặc định bằng cấp hiện tại

        # 3. Cache _city_building_plans[15230] cũng bảo toàn trọn vẹn thứ tự
        cached = dash._city_building_plans[15230]
        cached_pids = [p["pid"] for p in cached]
        assert cached_pids == [6, 1, 3, 2]
        assert cached[0]["cur_lvl"] == 6
        assert cached[1]["cur_lvl"] == 11
    finally:
        dash.destroy()


def test_dashboard_sync_city_techs_data_preserves_queue_order():
    dash = safe_dashboard()
    try:
        # Di chuyển tech 8 (trận pháp) lên vị trí đầu tiên
        dash.res_tree.selection_set("8")
        dash.res_tree.move("8", "", 0)
        first_item = dash.res_tree.get_children("")[0]
        assert first_item == "8"

        # Đồng bộ dữ liệu thực tế từ server
        levels = {8: 15, 1: 12}
        dash._sync_city_techs_data(15230, levels, tech_status=(True, 8), from_auto_cycle=True)

        # Thứ tự cây không bị reset
        assert dash.res_tree.get_children("")[0] == "8"

        vals_8 = dash.res_tree.item("8", "values")
        assert int(vals_8[3]) == 15

        vals_1 = dash.res_tree.item("1", "values")
        assert int(vals_1[3]) == 12
    finally:
        dash.destroy()


def test_dashboard_fetch_city_techs_supports_thai_hoc_dien():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)
        calls = []

        def fake_call(path, api_id, payload):
            calls.append((path, api_id, payload))
            if path == "City.ashx" and api_id == 5:
                # Thành có Thái Học Điện (gid=59) ở ô đất pid=12
                return {"ret": 0, "infos": [[12, 59, "太学殿", 20]]}
            elif path == "Build.ashx" and api_id == 2:
                return {"ret": 0, "list": [[1, "Tech1", 10], [2, "Tech2", 5]]}
            return {"ret": 0}

        dash.gateway.call = fake_call
        dash._fetch_city_techs_thread(15230)

        # Kiểm tra gọi Build.ashx?id=2 với pid=12 và gid=59 (không tự chuyển sang thành khác)
        build_calls = [p for pth, aid, p in calls if pth == "Build.ashx" and aid == 2]
        assert len(build_calls) == 1
        assert build_calls[0]["pid"] == "12"
        assert build_calls[0]["gid"] == "59"
    finally:
        dash.destroy()



def test_dashboard_ditrai_ui_controls(monkeypatch):
    import linhvuong.dashboard
    monkeypatch.setattr(linhvuong.dashboard.messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(linhvuong.dashboard.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(linhvuong.dashboard.messagebox, "showinfo", lambda *a, **k: None)

    dash = safe_dashboard()
    try:
        # 1. Kiểm tra sự tồn tại của các widget Di Trại
        assert hasattr(dash, "dt_camp_combo")
        assert hasattr(dash, "dt_origin_lbl")
        assert hasattr(dash, "dt_dest_x_var")
        assert hasattr(dash, "dt_dest_y_var")
        assert hasattr(dash, "dt_start_btn")
        assert hasattr(dash, "dt_stop_btn")
        assert hasattr(dash, "dt_status_lbl")

        # 2. Tạo một camp trong Roster và kiểm tra nạp vào combobox
        r = Roster()
        camp = City(id=-1001, name="DoanhTrại1", type="Doanh trại", pos_x=50, pos_y=60)
        r.camps = [camp]
        dash._loaded(r)

        # Kiểm tra dt_camp_combo và bm_city_combo nạp danh sách camp
        assert len(dash.dt_camp_combo["values"]) > 0
        dash.dt_camp_combo.current(0)
        dash._on_dt_camp_selected()
        assert "(50, 60)" in dash.dt_origin_lbl.cget("text")

        # Kiểm tra bm_city_combo tự động gán bm_camp_id_var
        dash.bm_city_combo.current(0)
        dash._on_bm_city_selected()
        assert dash.bm_camp_id_var.get() == "-1001"

        # 3. Kiểm tra validation khi chưa nhập tọa độ đích
        dash.dt_dest_x_var.set("")
        dash.dt_dest_y_var.set("")
        dash._start_ditrai()
        assert str(dash.dt_start_btn["state"]) == "normal"

        # 4. Kiểm tra chọn camp trong bld_bases_tree tự động đồng bộ sang dt_camp_combo
        if hasattr(dash, "bld_bases_tree") and dash.bld_bases_tree.exists("-1001"):
            dash.bld_bases_tree.selection_set("-1001")
            dash._on_bld_base_selected()
            assert "(50, 60)" in dash.dt_origin_lbl.cget("text")

        # 5. Kiểm tra lưu và nạp profile cho Dịch Trại
        dash.dt_dest_x_var.set("123")
        dash.dt_dest_y_var.set("456")
        profile = dash._collect_unified_profile()
        assert profile.get("ditrai", {}).get("dest_x") == "123"
        assert profile.get("ditrai", {}).get("dest_y") == "456"

        dash.dt_dest_x_var.set("")
        dash.dt_dest_y_var.set("")
        sections = dash._apply_unified_profile(profile)
        assert "Dịch Trại" in sections
        assert dash.dt_dest_x_var.get() == "123"
        assert dash.dt_dest_y_var.get() == "456"
    finally:
        dash.destroy()


def test_dashboard_building_tree_hierarchy_and_checkbox_actions():
    dash = safe_dashboard()
    try:
        dash._current_bld_city_id = 15230
        dash.bld_tree.delete(*dash.bld_tree.get_children())

        # Tạo danh sách công trình: Quan Phủ (đơn chiếc) và 2 Nhà Dân (đa ô)
        plans = [
            {"pid": 1, "gid": 1, "name": "Quan Phủ", "cur_lvl": 10, "target_level": 20, "enabled": True},
            {"pid": 11, "gid": 3, "name": "Nhà Dân", "cur_lvl": 5, "target_level": 15, "enabled": True},
            {"pid": 12, "gid": 3, "name": "Nhà Dân", "cur_lvl": 8, "target_level": 15, "enabled": True},
        ]
        dash._city_building_plans[15230] = list(plans)
        dash._render_bld_tree_from_plans(plans)

        # 1. Cấu trúc cây: Quan Phủ ở root, Nhà Dân có node cha group_3
        roots = dash.bld_tree.get_children("")
        assert list(roots) == ["1", "group_3"]

        children_g3 = dash.bld_tree.get_children("group_3")
        assert list(children_g3) == ["11", "12"]

        vals_g3 = dash.bld_tree.item("group_3", "values")
        assert vals_g3[0] == "☑"
        assert vals_g3[1] == "2 ô"
        assert int(vals_g3[2]) == 3
        assert vals_g3[3] == "5 - 8"
        assert vals_g3[4] == "15"
        # Mặc định danh sách công trình đa ô là collapse (đóng)
        assert bool(dash.bld_tree.item("group_3", "open")) is False

        # Khi người dùng mở nhóm ra và re-render, trạng thái mở được bảo toàn
        dash.bld_tree.item("group_3", open=True)
        dash._render_bld_tree_from_plans(plans)
        assert bool(dash.bld_tree.item("group_3", "open")) is True

        # 2. Click checkbox (#3: Chạy) trên group_3 -> tất cả con chuyển sang "☐"
        ev = MagicMock()
        ev.x = 10
        ev.y = 10
        dash.bld_tree.identify_row = MagicMock(return_value="group_3")
        dash.bld_tree.identify_column = MagicMock(return_value="#3")
        dash._on_bld_tree_click(ev)

        assert dash.bld_tree.item("group_3", "values")[0] == "☐"
        assert dash.bld_tree.item("11", "values")[0] == "☐"
        assert dash.bld_tree.item("12", "values")[0] == "☐"

        # 3. Click checkbox (#3: Chạy) trên ô con 11 -> con 11 thành "☑", node cha group_3 thành "▣" (bán phần)
        dash.bld_tree.identify_row = MagicMock(return_value="11")
        dash.bld_tree.identify_column = MagicMock(return_value="#3")
        dash._on_bld_tree_click(ev)

        assert dash.bld_tree.item("11", "values")[0] == "☑"
        assert dash.bld_tree.item("12", "values")[0] == "☐"
        assert dash.bld_tree.item("group_3", "values")[0] == "▣"

        # 4. Đặt Cấp MT khi chọn group_3 -> cả 2 con nhận cấp MT mới
        dash.bld_tree.selection_set("group_3")
        dash.bld_target_lvl_var.set("18")
        dash._set_bld_target_lvl()

        assert int(dash.bld_tree.item("11", "values")[4]) == 18
        assert int(dash.bld_tree.item("12", "values")[4]) == 18
        assert dash.bld_tree.item("group_3", "values")[4] == "18"

        # 5. Thu thập lại danh sách phẳng: bảo toàn thứ tự root và con
        collected = dash._collect_bld_plans_from_tree()
        assert [p["pid"] for p in collected] == [1, 11, 12]
        assert [p["target_level"] for p in collected] == [20, 18, 18]
    finally:
        dash.destroy()


def test_dashboard_sync_city_buildings_auto_inherits_when_group_all_selected():
    dash = safe_dashboard()
    try:
        dash._current_bld_city_id = 15230
        dash.bld_tree.delete(*dash.bld_tree.get_children())

        # Nhóm Nhà Dân (gid=3) đang chọn all (enabled=True, target_level=16)
        # Nhóm Kho (gid=4) không chọn all (enabled=False)
        custom_plans = [
            {"pid": 11, "gid": 3, "name": "Nhà Dân", "cur_lvl": 10, "target_level": 16, "enabled": True},
            {"pid": 12, "gid": 3, "name": "Nhà Dân", "cur_lvl": 12, "target_level": 16, "enabled": True},
            {"pid": 21, "gid": 4, "name": "Kho", "cur_lvl": 5, "target_level": 10, "enabled": False},
        ]
        dash._city_building_plans[15230] = list(custom_plans)
        dash._render_bld_tree_from_plans(custom_plans)

        # Server báo về có thêm 2 ô đất mới: pid 13 (Nhà Dân) và pid 22 (Kho)
        server_buildings = [
            {"pid": 11, "gid": 3, "level": 10, "name": "Nhà Dân"},
            {"pid": 12, "gid": 3, "level": 12, "name": "Nhà Dân"},
            {"pid": 13, "gid": 3, "level": 1, "name": "Nhà Dân"},  # Mới
            {"pid": 21, "gid": 4, "level": 5, "name": "Kho"},
            {"pid": 22, "gid": 4, "level": 1, "name": "Kho"},      # Mới
        ]

        dash._sync_city_buildings_data(15230, server_buildings, from_auto_cycle=True)

        cached = dash._city_building_plans[15230]
        plan_13 = next(p for p in cached if p["pid"] == 13)
        plan_22 = next(p for p in cached if p["pid"] == 22)

        # Ô 13 kế thừa nhóm Nhà Dân: enabled=True, target_level=16
        assert plan_13["enabled"] is True
        assert plan_13["target_level"] == 16

        # Ô 22 không kế thừa (nhóm Kho không chọn all): enabled=False, target_level=cur_lvl=1
        assert plan_22["enabled"] is False
        assert plan_22["target_level"] == 1
    finally:
        dash.destroy()


def test_dashboard_move_building_group_up_down():
    dash = safe_dashboard()
    try:
        dash._current_bld_city_id = 15230
        dash.bld_tree.delete(*dash.bld_tree.get_children())

        # Thứ tự ban đầu: Quan Phủ (gid=1), Nhà Dân (group_3: 11, 12), Đại Học Điện (gid=6)
        plans = [
            {"pid": 1, "gid": 1, "name": "Quan Phủ", "cur_lvl": 10, "target_level": 20, "enabled": True},
            {"pid": 11, "gid": 3, "name": "Nhà Dân", "cur_lvl": 5, "target_level": 15, "enabled": True},
            {"pid": 12, "gid": 3, "name": "Nhà Dân", "cur_lvl": 8, "target_level": 15, "enabled": True},
            {"pid": 6, "gid": 6, "name": "Đại Học Điện", "cur_lvl": 5, "target_level": 20, "enabled": True},
        ]
        dash._city_building_plans[15230] = list(plans)
        dash._render_bld_tree_from_plans(plans)

        assert list(dash.bld_tree.get_children("")) == ["1", "group_3", "6"]

        # Chọn group_3 và di chuyển lên
        dash.bld_tree.selection_set("group_3")
        dash._move_bld_up()

        # Thứ tự root mới: group_3 lên đầu
        assert list(dash.bld_tree.get_children("")) == ["group_3", "1", "6"]
        # Các ô con bên trong group_3 vẫn nguyên vẹn
        assert list(dash.bld_tree.get_children("group_3")) == ["11", "12"]

        # Kiểm tra danh sách lưu trong cache
        cached = dash._city_building_plans[15230]
        assert [p["pid"] for p in cached] == [11, 12, 1, 6]
    finally:
        dash.destroy()


def test_dashboard_sync_city_buildings_filters_unbuilt_dummy_plots():
    dash = safe_dashboard()
    try:
        # Giả lập chuyển sang căn cứ chưa từng tải cấu hình (gọi _populate_default_buildings)
        dash._switch_bld_base(21999)

        # Server trả về dữ liệu thực tế của thành (chỉ có 1 Nhà dân ở ô 16 và 1 Quán trọ ở ô 29)
        # Các ô 3 (Nhà Dân mẫu), 7 (Quán Trọ mẫu) không có trên thực tế
        server_buildings = [
            [0, 2, "城墙", 1, 0, 0],
            [8, 1, "官府", 7, 1, 360],
            [16, 3, "民房", 1, 0, 0],
            [29, 7, "客栈", 1, 0, 0],
        ]

        dash._sync_city_buildings_data(21999, server_buildings)

        plans = dash._city_building_plans[21999]
        nha_dan = [p for p in plans if p["gid"] == 3]
        quan_tro = [p for p in plans if p["gid"] == 7]

        # Phải lọc bỏ hoàn toàn các ô mẫu giả định không có thật trên server
        assert len(nha_dan) == 1
        assert nha_dan[0]["pid"] == 16
        assert nha_dan[0]["cur_lvl"] == 1

        assert len(quan_tro) == 1
        assert quan_tro[0]["pid"] == 29
        assert quan_tro[0]["cur_lvl"] == 1

        # Treeview không gom nhóm thừa (chỉ có 1 ô mỗi loại, hiển thị ở root)
        roots = list(dash.bld_tree.get_children(""))
        assert "16" in roots
        assert "29" in roots
        assert not dash.bld_tree.exists("group_3")
        assert not dash.bld_tree.exists("group_7")
    finally:
        dash.destroy()


def test_dashboard_gateway_relogin_callback(monkeypatch):
    if _tkinter is None:
        pytest.skip("tkinter not available")
    session = MagicMock()
    login_mock = MagicMock()
    monkeypatch.setattr("linhvuong.dashboard.login", login_mock)

    with patch("threading.Thread"):
        dash = Dashboard(session, 53, username="quilia", password="secret_password")
        dash.withdraw()

    try:
        assert dash.gateway.relogin_callback is not None
        # Gọi thử relogin_callback
        success = dash.gateway.relogin_callback()
        assert success is True
        login_mock.assert_called_once_with(
            session,
            53,
            "quilia",
            "secret_password",
            proxy=None,
            proxy_user=None,
            proxy_pass=None,
        )
    finally:
        dash.destroy()


def test_dashboard_unified_internal_and_research_controls():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # 1. Quản lý nhà: [Hạ] đặt cấp mục tiêu theo ô nhập và tự tích chọn Chạy
        bld_items = dash.bld_tree.get_children()
        first_bld = bld_items[0]
        dash.bld_target_lvl_var.set("0")
        dash.bld_tree.selection_set(first_bld)
        dash._lower_bld_target_lvl()
        assert int(dash.bld_tree.item(first_bld, "values")[4]) == 0
        assert dash.bld_tree.item(first_bld, "values")[0] == "☑"
        assert dash.bld_target_lvl_var.get() == "0"

        # 2. Base controls: Chọn, Bỏ chọn, Chọn NC, Bỏ NC
        base_items = dash.bld_bases_tree.get_children()
        assert len(base_items) == 3
        dash.bld_bases_tree.selection_set(base_items[1])  # 15237
        dash._set_selected_base_state(True)
        assert dash.bld_bases_tree.item(base_items[1], "values")[0] == "☑"
        assert 15237 in dash._selected_building_cities

        dash._set_selected_base_state(False)
        assert dash.bld_bases_tree.item(base_items[1], "values")[0] == "☐"
        assert 15237 not in dash._selected_building_cities

        # Chọn NC
        dash._set_selected_base_as_nc()
        assert dash._research_city_id == 15237
        assert dash.bld_bases_tree.item(base_items[1], "values")[2] == "★"
        assert dash.bld_bases_tree.item(base_items[0], "values")[2] == "☐"

        # Bỏ NC
        dash._clear_all_nc_bases()
        assert dash._research_city_id is None
        assert dash.bld_bases_tree.item(base_items[1], "values")[2] == "☐"

        # 3. Giám sát tài nguyên: Toggle On/Off
        assert dash._res_monitor_running is False
        dash._selected_resource_cities.add(15230)
        dash._toggle_resource_monitor()
        assert dash._res_monitor_running is True
        assert dash.res_monitor_btn.cget("text") == "Đang Giữ TN"

        dash._toggle_resource_monitor()
        assert dash._res_monitor_running is False
        assert dash.res_monitor_btn.cget("text") == "Tài Nguyên"

        # 4. Xem Log popup window
        dash._open_log_window()
        assert dash._log_win is not None
        assert dash._log_win.winfo_exists()
        dash._append_bld_log("Test log message")
        assert "Test log message" in dash.bld_log_text.get("1.0", "end")
        dash._log_win.destroy()
        dash._log_win = None

        # 5. Chuyển quân giới: Add & Delete order
        dash.log_from_city_combo.set("Thành 1")
        dash.log_to_city_combo.set("Thành 2")
        dash.log_amount_var.set("500")
        dash._add_army_transfer_order()
        t_items = dash.log_transfers_tree.get_children()
        assert len(t_items) == 1
        row_vals = dash.log_transfers_tree.item(t_items[0], "values")
        assert "Thành 1 ➔ Thành 2" in row_vals[0]
        assert str(row_vals[1]) == "500"

        dash.log_transfers_tree.selection_set(t_items[0])
        dash._delete_army_transfer_order()
        assert len(dash.log_transfers_tree.get_children()) == 0

        # 6. DS kiến trúc
        assert hasattr(dash, "aux_boost_var")
        assert hasattr(dash, "aux_boost_time_lbl")
    finally:
        dash.destroy()


def test_dashboard_save_unified_profile_with_grouped_buildings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)
        b_data = [
            {"pid": 1, "gid": 1, "level": 20, "name": "Quan Phủ"},
            {"pid": 11, "gid": 3, "level": 10, "name": "Nhà Dân"},
            {"pid": 12, "gid": 3, "level": 10, "name": "Nhà Dân"},
        ]
        dash._sync_city_buildings_data(15230, b_data)
        assert dash.bld_tree.exists("group_3")

        # Lưu hồ sơ cấu hình tổng hợp không được văng lỗi ValueError
        saved_file = dash._save_unified_profile(tmp_path / "test_grouped_profile.json")
        assert saved_file.exists()

        # Kiểm tra nội dung lưu
        import json
        saved_data = json.loads(saved_file.read_text(encoding="utf-8"))
        assert "building" in saved_data
        plans = saved_data["building"]["plans"]
        assert len(plans) == 3
        # Đảm bảo các ô trong group_3 đều được lưu phẳng với đúng pid
        pids = [p["pid"] for p in plans]
        assert 1 in pids
        assert 11 in pids
        assert 12 in pids
    finally:
        dash.destroy()


def test_dashboard_treeview_checkbox_click_in_chay_column():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        class DummyEvent:
            def __init__(self, x=0, y=0):
                self.x = x
                self.y = y

        # 1. bld_tree: Cột Chạy là displaycolumn #3 (sau current_lvl #1 và target_lvl #2)
        assert dash.bld_tree.heading("current_lvl", "text") == "Cấp HT"
        assert dash.bld_tree.heading("target_lvl", "text") == "Cấp MT"
        assert dash.bld_tree.heading("select", "text") == "Chạy"

        bld_item = dash.bld_tree.get_children()[0]
        init_vals = list(dash.bld_tree.item(bld_item, "values"))
        assert init_vals[0] == "☐"

        # Click vào display column #3 (Chạy) phải toggle checkbox từ ☐ -> ☑
        dash.bld_tree.identify_row = lambda y: bld_item
        dash.bld_tree.identify_column = lambda x: "#3"
        dash._on_bld_tree_click(DummyEvent(0, 0))
        after_vals = list(dash.bld_tree.item(bld_item, "values"))
        assert after_vals[0] == "☑", f"Click vào cột Chạy (#3) phải chuyển ☐ -> ☑, nhưng nhận: {after_vals[0]}"

        # 2. res_tree: Cột Chạy là displaycolumn #3
        assert dash.res_tree.heading("current_lvl", "text") == "Cấp HT"
        assert dash.res_tree.heading("target_lvl", "text") == "Cấp MT"
        assert dash.res_tree.heading("select", "text") == "Chạy"

        res_item = dash.res_tree.get_children()[0]
        init_res_vals = list(dash.res_tree.item(res_item, "values"))
        assert init_res_vals[0] == "☐"
        assert init_res_vals[3] == "-"  # Ban đầu khi chưa tải từ server là "-"

        dash.res_tree.identify_row = lambda y: res_item
        dash.res_tree.identify_column = lambda x: "#3"
        dash._on_res_tree_click(DummyEvent(0, 0))
        after_res_vals = list(dash.res_tree.item(res_item, "values"))
        assert after_res_vals[0] == "☑", f"Click vào cột Chạy (#3) ở res_tree phải chuyển ☐ -> ☑, nhưng nhận: {after_res_vals[0]}"

        # 3. bld_bases_tree: Cột Tài nguyên là #2, Chọn là #1
        base_item = dash.bld_bases_tree.get_children()[0]
        dash.bld_bases_tree.identify_row = lambda y: base_item
        dash.bld_bases_tree.identify_column = lambda x: "#2"
        dash._on_bld_bases_click(DummyEvent(0, 0))
        base_vals = list(dash.bld_bases_tree.item(base_item, "values"))
        assert base_vals[1] == "☑"

    finally:
        dash.destroy()


def test_dashboard_boost_status_time_parsing_and_cid():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        calls = []
        def fake_call(path, api_id, payload):
            calls.append((path, api_id, payload))
            # Giả lập phản hồi thật từ server S53: 2234:39:14 = 8,044,754 giây
            if path == "Common.ashx" and api_id == 77:
                return {
                    "ret": 0,
                    "list": [
                        [15230, "ThanhChinh", 596952, 8044754, [], []]
                    ]
                }
            return {}

        dash.gateway.call = fake_call
        dash._check_and_update_boost_status(async_check=False)

        # Kiểm tra payload phải có cid
        assert any(c[0] == "Common.ashx" and c[1] == 77 and "cid" in c[2] for c in calls)
        assert dash.aux_boost_time_lbl.cget("text") == "(Còn: 2234:39:14)"
    finally:
        dash.destroy()


def test_dashboard_resource_box_combobox_width():
    dash = safe_dashboard()
    try:
        # Độ rộng của Combobox chọn rương phải đủ hiển thị tên đầy đủ
        assert dash.res_gold_box_combo.cget("width") >= 30
        assert dash.res_tn_box_combo.cget("width") >= 30
    finally:
        dash.destroy()


def test_dashboard_current_and_target_levels_sync_and_tagging():
    dash = safe_dashboard()
    try:
        # 1. Kiểm tra ban đầu của res_tree: tất cả kỹ thuật có Cấp HT là "-" và tag upgrade
        for iid in dash.res_tree.get_children(""):
            vals = dash.res_tree.item(iid, "values")
            tags = dash.res_tree.item(iid, "tags")
            assert vals[3] == "-"
            assert "upgrade" in tags

        # 2. Đồng bộ dữ liệu thực tế từ server (ví dụ kỹ thuật 1 cấp 20, kỹ thuật 2 cấp 5)
        # Kỹ thuật 1: MT=20, HT=20 -> tag completed
        # Kỹ thuật 2: MT=20, HT=5 -> tag upgrade
        levels_map = {1: 20, 2: 5}
        dash._sync_city_techs_data(15230, levels_map, from_auto_cycle=False)

        vals_1 = dash.res_tree.item("1", "values")
        tags_1 = dash.res_tree.item("1", "tags")
        assert int(vals_1[3]) == 20
        assert "completed" in tags_1

        vals_2 = dash.res_tree.item("2", "values")
        tags_2 = dash.res_tree.item("2", "tags")
        assert int(vals_2[3]) == 5
        assert "upgrade" in tags_2

        # 3. Đặt Cấp MT của kỹ thuật 2 xuống cấp 5 -> chuyển sang completed
        dash.res_tree.selection_set("2")
        dash.res_target_lvl_var.set("5")
        dash._set_res_target_lvl()
        tags_2_updated = dash.res_tree.item("2", "tags")
        assert "completed" in tags_2_updated
    finally:
        dash.destroy()


def test_two_way_target_level_binding():
    """Kiểm tra cơ chế ô nhập Cấp mục tiêu: Quản lý nhà giữ nguyên số đã nhập & tự check Chạy khi bấm Nâng/Hạ; Kỹ thuật giữ nguyên."""
    dash = safe_dashboard()
    try:
        # 1. Quản lý nhà (bld_tree):
        # Ban đầu công trình 1 có Chạy = "☐", MT = 20
        assert dash.bld_tree.item("1", "values")[0] == "☐"
        assert int(dash.bld_tree.item("1", "values")[4]) == 20

        # Điền cấp mục tiêu 25 trước, sau đó chọn công trình 1 -> ô nhập KHÔNG bị ghi đè về 20
        dash.bld_target_lvl_var.set("25")
        dash.bld_tree.selection_set("1")
        dash._on_bld_tree_selected()
        assert dash.bld_target_lvl_var.get() == "25"

        # Click mô phỏng trên dòng công trình 1 -> ô nhập vẫn giữ nguyên "25"
        ev = MagicMock()
        ev.x = 20
        ev.y = 20
        dash.bld_tree.identify_row = MagicMock(return_value="1")
        dash.bld_tree.identify_column = MagicMock(return_value="#1")
        dash._on_bld_tree_click(ev)
        assert dash.bld_tree.selection() == ("1",)
        assert dash.bld_target_lvl_var.get() == "25"

        # Bấm Nâng -> Cấp MT thành 25 và checkbox Chạy tự động check "☑"
        dash._set_bld_target_lvl()
        assert int(dash.bld_tree.item("1", "values")[4]) == 25
        assert dash.bld_tree.item("1", "values")[0] == "☑"

        # Điền cấp mục tiêu 5, chọn Tường Thành (pid 2, đang "☐"), bấm Hạ -> Cấp MT = 5 và tự động check "☑"
        assert dash.bld_tree.item("2", "values")[0] == "☐"
        dash.bld_target_lvl_var.set("5")
        dash.bld_tree.selection_set("2")
        dash._on_bld_tree_selected()
        assert dash.bld_target_lvl_var.get() == "5"
        dash._lower_bld_target_lvl()
        assert int(dash.bld_tree.item("2", "values")[4]) == 5
        assert dash.bld_tree.item("2", "values")[0] == "☑"
        assert dash.bld_target_lvl_var.get() == "5"

        # Chọn lại Quan Phủ (pid 1, MT=25) -> ô nhập vẫn giữ nguyên "5" (không load MT của Quan Phủ lên)
        dash.bld_tree.selection_set("1")
        dash._on_bld_tree_selected()
        assert dash.bld_target_lvl_var.get() == "5"

        # Kiểm tra nhóm đa ô đất (group): ban đầu chưa check ("☐")
        plans = [
            {"pid": 11, "gid": 3, "name": "民房 - Nhà Dân", "cur_lvl": 5, "target_level": 15, "enabled": False},
            {"pid": 12, "gid": 3, "name": "民房 - Nhà Dân", "cur_lvl": 8, "target_level": 18, "enabled": False},
        ]
        dash._render_bld_tree_from_plans(plans)
        assert dash.bld_tree.item("group_3", "values")[0] == "☐"

        # Điền 22, chọn group_3 -> ô nhập vẫn giữ nguyên "22"
        dash.bld_target_lvl_var.set("22")
        dash.bld_tree.selection_set("group_3")
        dash._on_bld_tree_selected()
        assert dash.bld_target_lvl_var.get() == "22"

        # Bấm Nâng trên group_3 -> cả 2 ô con và group_3 đều nhận MT=22 và tự động check "☑"
        dash._set_bld_target_lvl()
        assert int(dash.bld_tree.item("11", "values")[4]) == 22
        assert int(dash.bld_tree.item("12", "values")[4]) == 22
        assert dash.bld_tree.item("11", "values")[0] == "☑"
        assert dash.bld_tree.item("12", "values")[0] == "☑"
        assert dash.bld_tree.item("group_3", "values")[0] == "☑"

        # Bỏ chọn con 11 và 12, sau đó điền 0 và bấm Hạ trên group_3 -> cả nhóm nhận MT=0 và tự check "☑"
        dash._select_all_bld(False)
        assert dash.bld_tree.item("group_3", "values")[0] == "☐"
        dash.bld_target_lvl_var.set("0")
        dash.bld_tree.selection_set("group_3")
        dash._lower_bld_target_lvl()
        assert int(dash.bld_tree.item("11", "values")[4]) == 0
        assert int(dash.bld_tree.item("12", "values")[4]) == 0
        assert dash.bld_tree.item("11", "values")[0] == "☑"
        assert dash.bld_tree.item("12", "values")[0] == "☑"
        assert dash.bld_tree.item("group_3", "values")[0] == "☑"

        # Kiểm tra _collect_bld_plans_from_tree an toàn với cur_lvl = "-"
        dash.bld_tree.item("11", values=("☑", 11, 3, "-", 15))
        collected = dash._collect_bld_plans_from_tree()
        p11 = [p for p in collected if p["pid"] == 11][0]
        assert p11["cur_lvl"] == 0
        assert p11["target_level"] == 15

        # 2. Nâng cấp kỹ thuật (res_tree): Khi chọn item, ô nhập cập nhật theo kỹ thuật
        dash.res_tree.selection_set("1")
        dash.res_target_lvl_var.set("28")
        dash._set_res_target_lvl()
        assert int(dash.res_tree.item("1", "values")[2]) == 28

        dash.res_tree.selection_set("2")
        dash._on_res_tree_selected()
        assert dash.res_target_lvl_var.get() == "20"

        dash.res_tree.selection_set("1")
        dash._on_res_tree_selected()
        assert dash.res_target_lvl_var.get() == "28"

        # Click mô phỏng trên res_tree
        ev_res = MagicMock()
        ev_res.x = 20
        ev_res.y = 20
        dash.res_tree.identify_row = MagicMock(return_value="2")
        dash.res_tree.identify_column = MagicMock(return_value="#2")
        dash._on_res_tree_click(ev_res)
        assert dash.res_tree.selection() == ("2",)
        assert dash.res_target_lvl_var.get() == "20"
    finally:
        dash.destroy()


def test_dashboard_battle_tab_controls_and_profile():
    from linhvuong.battle import BattleState, BattleTroop

    dash = safe_dashboard()
    try:
        # 1. Kiểm tra tồn tại các UI controls của Tab Chiến trường
        assert hasattr(dash, "bt_auto_counter_var")
        assert dash.bt_auto_counter_var.get() is True
        assert hasattr(dash, "bt_window_var")
        assert dash.bt_window_var.get() == "15"
        assert hasattr(dash, "bt_skip_confused_var")
        assert dash.bt_skip_confused_var.get() is True
        assert hasattr(dash, "bt_leave_boss_var")
        assert dash.bt_leave_boss_var.get() is True
        assert hasattr(dash, "bt_cleanse_var")
        assert dash.bt_cleanse_var.get() is True
        assert hasattr(dash, "bt_retreat_var")
        assert dash.bt_retreat_var.get() == "0"
        assert hasattr(dash, "bt_our_tree")
        assert hasattr(dash, "bt_enemy_tree")

        # 2. Thu thập profile hợp nhất có mục "combat"
        prof = dash._collect_unified_profile()
        assert "combat" in prof
        assert prof["combat"]["auto_counter_formation"] is True
        assert prof["combat"]["formation_window_seconds"] == "15"
        assert prof["combat"]["skip_confused_enemy"] is True
        assert prof["combat"]["leave_boss_last"] is True
        assert prof["combat"]["auto_cleanse_confusion"] is True
        assert prof["combat"]["emergency_retreat_threshold"] == "0"

        # 3. Nạp hồ sơ cấu hình tuỳ chỉnh và kiểm tra đồng bộ lên UI
        custom_cfg = {
            "combat": {
                "auto_counter_formation": False,
                "formation_window_seconds": "10",
                "attack_action_mode": "fixed",
                "action_combo_idx": 2,
                "skip_confused_enemy": False,
                "leave_boss_last": False,
                "auto_cleanse_confusion": False,
                "emergency_retreat_threshold": "25",
                "stratagem_combo_idx": 1,
            }
        }
        loaded = dash._apply_unified_profile(custom_cfg)
        assert "Chiến Trường" in loaded
        assert dash.bt_auto_counter_var.get() is False
        assert dash.bt_window_var.get() == "10"
        assert dash.bt_skip_confused_var.get() is False
        assert dash.bt_leave_boss_var.get() is False
        assert dash.bt_cleanse_var.get() is False
        assert dash.bt_retreat_var.get() == "25"

        # 4. Kiểm tra render thông tin chiến trường lên Treeview
        our = BattleTroop(
            position=1,
            player_name="Người Chơi",
            user_id=57,
            general_name="Triệu Vân",
            general_id=101,
            city_id=1,
            formation_id=1,
            morale=100,
            soldiers=9500,
            initial_soldiers=10000,
            flag=0,
            status=0,
            attack_action=13,
            target_id=11,
        )
        enemy = BattleTroop(
            position=11,
            player_name="Quân Man",
            user_id=999,
            general_name="Man Vương",
            general_id=202,
            city_id=2,
            formation_id=2,
            morale=90,
            soldiers=18000,
            initial_soldiers=20000,
            flag=0,
            status=0,
            attack_action=1,
            target_id=1,
            is_boss=True,
        )
        fake_state = BattleState(
            ret=0,
            site="Dã ngoại cấp 5",
            map_id=1,
            bout=2,
            bout_left=30,
            attack_total=1,
            defend_total=1,
            is_attacker=True,
            our_troops=[our],
            enemy_troops=[enemy],
            boss_troops=[enemy],
        )

        dash._bt_render_state(fake_state)
        assert dash.bt_bout_var.get() == "Hiệp: 2"
        assert dash.bt_countdown_var.get() == "Đếm ngược: 30s"

        our_items = dash.bt_our_tree.get_children()
        assert len(our_items) == 1
        assert dash.bt_our_tree.item(our_items[0], "text") == "Triệu Vân"

        enemy_items = dash.bt_enemy_tree.get_children()
        assert len(enemy_items) == 1
        assert "Man Vương" in dash.bt_enemy_tree.item(enemy_items[0], "text")
        assert "👑" in dash.bt_enemy_tree.item(enemy_items[0], "text")
        assert "boss" in dash.bt_enemy_tree.item(enemy_items[0], "tags")

        # 5. Thao tác ghi log trực quan
        dash._append_bt_log("🧪 Kiểm thử log chiến trường thành công")
        dash.update()
        log_content = dash.bt_log_text.get("1.0", "end")
        assert "Kiểm thử log chiến trường thành công" in log_content
    finally:
        dash.destroy()


def test_dashboard_battle_tab_boss_load_alert():
    """Kiểm tra tab Chiến Trường hiển thị cảnh báo khi nạp chiến trường có Boss Man:
    VD: 🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!"""
    dash = safe_dashboard()
    try:
        boss_raw = [19, "", 0, "卑弥呼", 0, "", 0, 0, 4, 100, 0, 1500, 0, 1500, 0, 0, 0, 0, "", 32]
        our_raw = [1, "Player", 1001, "Triệu Vân", 5001, "", 2001, 0, 1, 100, 0, 2000, 0, 2000, 0, 1, 19, 0, "", 1]
        bout_resp = {
            "ret": 0,
            "bout": 1,
            "bout_left": 30,
            "site": "Trại Uy Quốc",
            "troops": [our_raw, boss_raw],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = bout_resp

        dash.gateway.session.post.return_value = mock_resp
        dash.bt_id_var.set("12345")
        dash._bt_load_battle()
        dash.update()

        log_content = dash.bt_log_text.get("1.0", "end")
        assert "🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!" in log_content

        enemy_items = dash.bt_enemy_tree.get_children()
        assert len(enemy_items) == 1
        assert "卑弥呼" in dash.bt_enemy_tree.item(enemy_items[0], "text")
        assert "👑" in dash.bt_enemy_tree.item(enemy_items[0], "text")
        assert "boss" in dash.bt_enemy_tree.item(enemy_items[0], "tags")
    finally:
        dash.destroy()


def test_dashboard_daily_reward_profile_and_auto_claim():
    dash = safe_dashboard()
    try:
        # 1. Kiểm tra default và collect profile
        assert hasattr(dash, "aux_daily_reward_var")
        dash.aux_daily_reward_var.set(False)
        profile = dash._collect_unified_profile()
        assert profile["logistics"]["auto_daily_reward"] is False

        # 2. Kiểm tra apply profile
        profile["logistics"]["auto_daily_reward"] = True
        loaded = dash._apply_unified_profile(profile)
        assert "Hậu Cần" in loaded
        assert dash.aux_daily_reward_var.get() is True

        # 3. Kiểm tra _do_claim_daily gọi LogisticsTask và ghi log
        with patch("linhvuong.dashboard.LogisticsTask") as mock_logistics:
            instance = mock_logistics.return_value
            instance.claim_daily_reward.return_value = True
            with patch("threading.Thread") as mock_thread:
                # Capture thread target and run synchronously
                def fake_thread_start():
                    pass
                dash._do_claim_daily()
                assert mock_thread.called
                kwargs = mock_thread.call_args[1]
                assert kwargs.get("daemon") is True
                # Chạy target lambda
                kwargs["target"]()
                assert instance.claim_daily_reward.called

        # 4. Kiểm tra _loaded trigger _do_claim_daily khi aux_daily_reward_var=True
        r = dummy_roster()
        with patch.object(dash, "_do_claim_daily") as mock_claim:
            dash._last_daily_claim_date = None
            dash.aux_daily_reward_var.set(True)
            dash._loaded(r)
            assert mock_claim.call_count == 1

            # Gọi lại lần nữa trong cùng ngày thì không gọi lại
            dash._loaded(r)
            assert mock_claim.call_count == 1
    finally:
        dash.destroy()


def test_dashboard_resource_config_and_cities_profile_sync(tmp_path):
    import json
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # 1. Thiết lập các thông số tài nguyên & thành sử dụng tài nguyên
        dash.res_gold_thresh_var.set("50000000")
        dash.res_wood_pct_var.set("60")
        dash.res_iron_pct_var.set("65")
        dash.res_stone_pct_var.set("55")
        dash.res_food_pct_var.set("80")
        if hasattr(dash, "res_gold_box_combo") and len(dash.res_gold_box_combo["values"]) > 2:
            dash.res_gold_box_combo.current(2)
        if hasattr(dash, "res_tn_box_combo") and len(dash.res_tn_box_combo["values"]) > 1:
            dash.res_tn_box_combo.current(1)

        # Chọn thành 15230 và 15237 sử dụng tài nguyên
        dash._selected_resource_cities = {15230, 15237}
        for cid in (15230, 15237):
            if dash.bld_bases_tree.exists(str(cid)):
                vals = list(dash.bld_bases_tree.item(str(cid), "values"))
                vals[1] = "☑"
                dash.bld_bases_tree.item(str(cid), values=vals)

        # 2. Thu thập và lưu profile
        prof_file = tmp_path / "resource_profile.json"
        saved = dash._save_unified_profile(prof_file)
        assert saved.exists()

        # Đọc profile kiểm tra xem có lưu section resource và resource_cities không
        profile = json.loads(saved.read_text(encoding="utf-8"))
        assert "resource" in profile, "Profile thiếu section 'resource'"
        assert profile["resource"]["gold_threshold"] == "50000000"
        assert profile["resource"]["wood_pct"] == "60"
        assert set(profile["resource"]["resource_cities"]) == {15230, 15237}

        # 3. Reset giao diện về mặc định
        dash.res_gold_thresh_var.set("100000000")
        dash.res_wood_pct_var.set("70")
        dash.res_iron_pct_var.set("70")
        dash.res_stone_pct_var.set("70")
        dash.res_food_pct_var.set("70")
        dash._selected_resource_cities.clear()
        for cid in (15230, 15237):
            if dash.bld_bases_tree.exists(str(cid)):
                vals = list(dash.bld_bases_tree.item(str(cid), "values"))
                vals[1] = "☐"
                dash.bld_bases_tree.item(str(cid), values=vals)

        # 4. Nạp lại profile
        ok, msg = dash._load_unified_profile(prof_file)
        assert ok is True
        assert "Tài Nguyên" in msg

        # Kiểm tra khôi phục giao diện và state
        assert dash.res_gold_thresh_var.get() == "50000000"
        assert dash.res_wood_pct_var.get() == "60"
        assert dash.res_iron_pct_var.get() == "65"
        assert dash.res_stone_pct_var.get() == "55"
        assert dash.res_food_pct_var.get() == "80"
        assert 15230 in dash._selected_resource_cities
        assert 15237 in dash._selected_resource_cities
        assert dash.bld_bases_tree.item("15230", "values")[1] == "☑"
        assert dash.bld_bases_tree.item("15237", "values")[1] == "☑"
    finally:
        dash.destroy()


def test_dashboard_morale_training_ui_and_actions():
    dash = safe_dashboard()
    try:
        # 1. Kiểm tra tồn tại các widget trên UI
        assert hasattr(dash, "mo_city_combo")
        assert hasattr(dash, "mo_target_morale_combo")
        assert hasattr(dash, "mo_start_btn")
        assert hasattr(dash, "mo_stop_btn")
        assert hasattr(dash, "mo_status_lbl")
        assert hasattr(dash, "mo_tree")

        # 2. Nạp roster mẫu có 2 tướng có quân đội (TrieuVan: 417506, QuanVu: 417520) và 1 tướng không có quân (GiaCatLuong: 417513)
        roster = dummy_roster()
        dash._loaded(roster)

        # Kiểm tra nạp combobox thành phố
        city_vals = list(dash.mo_city_combo["values"])
        assert "🌟 Tất cả các thành" in city_vals[0]
        assert len(city_vals) == 4  # Tất cả + 2 thành + 1 trại

        # Kiểm tra bảng tướng hiển thị đúng các tướng có quân đội
        items = dash.mo_tree.get_children("")
        assert set(items) == {"417506", "417520"}
        assert "417513" not in items  # Tướng không quân không hiển thị

        # Kiểm tra tự động chọn ban đầu (☑)
        assert dash.mo_tree.item("417506", "values")[0] == "☑"
        assert dash.mo_tree.item("417520", "values")[0] == "☑"
        assert 417506 in dash._selected_morale_generals
        assert 417520 in dash._selected_morale_generals

        # 3. Kiểm tra chức năng Bỏ chọn và Chọn tất cả
        dash._deselect_all_morale_generals()
        assert dash.mo_tree.item("417506", "values")[0] == "☐"
        assert dash.mo_tree.item("417520", "values")[0] == "☐"
        assert len(dash._selected_morale_generals) == 0

        dash._select_all_morale_generals()
        assert dash.mo_tree.item("417506", "values")[0] == "☑"
        assert dash.mo_tree.item("417520", "values")[0] == "☑"
        assert 417506 in dash._selected_morale_generals

        # 4. Kiểm tra toggle click trên dòng
        click_evt = MagicMock()
        dash.mo_tree.identify_row = MagicMock(return_value="417506")
        dash.mo_tree.identify_column = MagicMock(return_value="#1")
        dash._on_mo_tree_click(click_evt)
        assert dash.mo_tree.item("417506", "values")[0] == "☐"
        assert 417506 not in dash._selected_morale_generals

        dash._on_mo_tree_click(click_evt)
        assert dash.mo_tree.item("417506", "values")[0] == "☑"
        assert 417506 in dash._selected_morale_generals

        # 5. Kiểm tra bộ lọc theo thành phố
        # Chọn thành 15237 (PhanThanh - không có tướng)
        for idx, val in enumerate(city_vals):
            if "PhanThanh" in val:
                dash.mo_city_combo.current(idx)
                break
        dash._on_mo_city_selected()
        assert len(dash.mo_tree.get_children("")) == 0

        # Chọn thành 15230 (ThanhChinh - có TrieuVan)
        for idx, val in enumerate(city_vals):
            if "ThanhChinh" in val:
                dash.mo_city_combo.current(idx)
                break
        dash._on_mo_city_selected()
        items_c1 = dash.mo_tree.get_children("")
        assert set(items_c1) == {"417506"}

        # Quay lại tất cả các thành
        dash.mo_city_combo.current(0)
        dash._on_mo_city_selected()
        assert set(dash.mo_tree.get_children("")) == {"417506", "417520"}

        # 6. Kiểm tra kích hoạt Luyện Sĩ Khí
        with patch("linhvuong.dashboard.MoraleTrainer") as MockTrainer:
            mock_trainer_inst = MockTrainer.return_value
            mock_trainer_inst.train_multiple_generals.return_value = {
                417506: {"general_id": 417506, "success": True, "final_morale": 95, "message": "OK"},
                417520: {"general_id": 417520, "success": True, "final_morale": 95, "message": "OK"},
            }

            dash.mo_target_morale_combo.set("95")
            dash._start_morale_training()

            assert dash._morale_runner is not None
            assert dash._morale_stop_event is not None

            # Dừng luyện sĩ khí
            dash._stop_morale_training()
            assert dash._morale_stop_event.is_set()

            # Chờ luồng kết thúc
            dash._morale_runner.join(timeout=2.0)
    finally:
        dash.destroy()


def test_dashboard_binh_man_mode_toggle_and_ui_state():
    dash = safe_dashboard()
    try:
        # Kiểm tra mặc định là Mode 1 (Doanh trại)
        assert hasattr(dash, "bm_mode_var")
        assert dash.bm_mode_var.get() == 1
        assert "Doanh trại" in dash.bm_base_lbl.cget("text")
        assert str(dash.bm_parent_city_combo.cget("state")) in ("readonly", "normal")
        assert str(dash.bm_camp_id_entry.cget("state")) in ("normal", "")

        # Chuyển sang Mode 2 (Thành trì)
        dash.bm_mode_var.set(2)
        dash._on_bm_mode_changed()
        assert "Thành" in dash.bm_base_lbl.cget("text")
        assert str(dash.bm_parent_city_combo.cget("state")) == "disabled"
        assert str(dash.bm_camp_id_entry.cget("state")) == "disabled"

        # Chuyển lại về Mode 1
        dash.bm_mode_var.set(1)
        dash._on_bm_mode_changed()
        assert "Doanh trại" in dash.bm_base_lbl.cget("text")
        assert str(dash.bm_parent_city_combo.cget("state")) in ("readonly", "normal")
        assert str(dash.bm_camp_id_entry.cget("state")) in ("normal", "")
    finally:
        dash.destroy()


def test_dashboard_goi_man_target_level_options():
    dash = safe_dashboard()
    try:
        # Kiểm tra danh sách 11 cấp độ (1..10 + Vong Linh)
        assert len(dash.gd_target_options) == 11
        assert dash.gd_target_options[0] == (301, "Vong Linh (ID 301)")
        assert dash.gd_target_options[7] == (7, "Cấp 7 - Hung Nô")
        assert dash.gd_target_options[10] == (10, "Cấp 10 - Hổ Báo Kỵ")

        # Chọn Cấp 7 - Hung Nô (index 7)
        dash.gd_mode_combo.current(7)
        assert dash._get_gd_target_type() == 7

        # Chọn Vong Linh (index 0)
        dash.gd_mode_combo.current(0)
        assert dash._get_gd_target_type() == 301
    finally:
        dash.destroy()


def test_dashboard_multiselect_dropdown_sync():
    dash = safe_dashboard()
    try:
        # 1. Gọi Man MultiSelect
        assert hasattr(dash, "gd_target_dropdown")
        dash.gd_target_dropdown.set_selected([7, 8, 301])
        selected_gd = set(dash.gd_target_dropdown.get_selected())
        assert selected_gd == {7, 8, 301}

        dash.gd_target_dropdown.deselect_all()
        assert dash.gd_target_dropdown.get_selected() == []

        dash.gd_target_dropdown.select_all()
        assert len(dash.gd_target_dropdown.get_selected()) == 11

        # 2. Bình Man MultiSelect
        assert hasattr(dash, "bm_mantypes_dropdown")
        dash.bm_mantypes_dropdown.set_selected([7, 8, 9, 10])
        assert dash.bm_mantypes_dropdown.get_selected() == [7, 8, 9, 10]
        assert "7,8,9,10" in dash.bm_mantypes_var.get()

        # 3. Profile collect & apply sync
        profile = dash._collect_unified_profile()
        assert profile["goi_dan"]["target_types"] == [val for val, _ in dash.gd_target_options]
        assert profile["binh_man"]["target_types"] == [7, 8, 9, 10]

        # Thay đổi dữ liệu và nạp lại
        dash._apply_unified_profile({
            "goi_dan": {"target_types": [7, 8]},
            "binh_man": {"target_types": [5, 6, 7]},
        })
        assert set(dash.gd_target_dropdown.get_selected()) == {7, 8}
        assert set(dash.bm_mantypes_dropdown.get_selected()) == {5, 6, 7}
    finally:
        dash.destroy()


def test_dashboard_goidan_general_selection_and_task_creation():
    dash = safe_dashboard()
    try:
        c1 = City(id=101, name="ThanhChinh", type="Thành", pos_x=100, pos_y=200, level=20)
        gens = [
            General(id=1001, name="TrieuVan", role="vo", level=10, morale=100, stamina=95, stamina_max=100),
            General(id=1002, name="QuanVu", role="vo", level=11, morale=100, stamina=90, stamina_max=100),
            General(id=1003, name="TruongPhi", role="vo", level=9, morale=100, stamina=85, stamina_max=100),
            General(id=1004, name="MaSieu", role="vo", level=10, morale=100, stamina=90, stamina_max=100),
            General(id=1005, name="GiaCatLuong", role="van", level=12, morale=100, stamina=100, stamina_max=100),
        ]
        r = Roster(cities=[c1], camps=[], _generals={101: gens})
        dash._loaded(r)

        # 1. gd_gen_tree checks
        assert hasattr(dash, "gd_gen_tree")
        children = dash.gd_gen_tree.get_children()
        # Chỉ có 4 võ tướng xuất hiện, văn quan 1005 bị loại
        assert len(children) == 4
        # Mặc định chọn 3 tướng đầu tiên
        assert dash.gd_gen_tree.item("1001", "values")[0] == "☑"
        assert dash.gd_gen_tree.item("1002", "values")[0] == "☑"
        assert dash.gd_gen_tree.item("1003", "values")[0] == "☑"
        assert dash.gd_gen_tree.item("1004", "values")[0] == "☐"

        # 2. Deselect all & Select all
        dash._deselect_all_gd_gens()
        for iid in children:
            assert dash.gd_gen_tree.item(iid, "values")[0] == "☐"

        dash._select_all_gd_gens()
        for iid in children:
            assert dash.gd_gen_tree.item(iid, "values")[0] == "☑"

        # 3. Task creation with selected generals
        task = dash._create_goidan_task()
        assert task is not None
        assert task.generals == [1001, 1002, 1003, 1004]

        # 4. Khi không chọn tướng nào, task không được tạo
        dash._deselect_all_gd_gens()
        with patch("tkinter.messagebox.showwarning") as mock_warn:
            task_empty = dash._create_goidan_task()
            assert task_empty is None
            assert mock_warn.called
    finally:
        dash.destroy()


def test_dashboard_binhman_general_selection_and_task_creation():
    dash = safe_dashboard()
    try:
        camp1 = City(id=-201, name="DoanhTrai1", type="Doanh trại", pos_x=120, pos_y=220)
        c1 = City(id=101, name="ThanhChinh", type="Thành", pos_x=100, pos_y=200, level=20)
        camp_gens = [
            General(id=2001, name="TrieuVan", role="vo", level=10, morale=100, stamina=95, stamina_max=100),
            General(id=2002, name="QuanVu", role="vo", level=11, morale=100, stamina=90, stamina_max=100),
            General(id=2003, name="TruongPhi", role="vo", level=9, morale=100, stamina=85, stamina_max=100),
            General(id=2004, name="MaSieu", role="vo", level=10, morale=100, stamina=90, stamina_max=100),
            General(id=2005, name="HoangTrung", role="vo", level=10, morale=100, stamina=90, stamina_max=100),
            General(id=2006, name="GiaCatLuong", role="van", level=12, morale=100, stamina=100, stamina_max=100),
        ]
        r = Roster(cities=[c1], camps=[camp1], _generals={-201: camp_gens, 101: [camp_gens[0]]})
        dash._loaded(r)

        # 1. bm_gen_tree checks (Chế độ 1: Doanh trại mặc định)
        assert hasattr(dash, "bm_gen_tree")
        children = dash.bm_gen_tree.get_children()
        # 5 võ tướng xuất hiện, văn quan 2006 bị loại
        assert len(children) == 5
        # Mặc định chọn TẤT CẢ võ tướng (không giới hạn 3 hay 5)
        for iid in children:
            assert dash.bm_gen_tree.item(iid, "values")[0] == "☑"

        # 2. Deselect all & Select all
        dash._deselect_all_bm_gens()
        for iid in children:
            assert dash.bm_gen_tree.item(iid, "values")[0] == "☐"

        dash._select_all_bm_gens()
        for iid in children:
            assert dash.bm_gen_tree.item(iid, "values")[0] == "☑"

        # 3. Task creation with selected generals
        task = dash._create_binhman_task()
        assert task is not None
        assert task.generals == [2001, 2002, 2003, 2004, 2005]

        # 4. Khi không chọn tướng nào
        dash._deselect_all_bm_gens()
        with patch("tkinter.messagebox.showwarning") as mock_warn:
            task_empty = dash._create_binhman_task()
            assert task_empty is None
            assert mock_warn.called

        # 5. Chuyển sang Mode 2 (Thành)
        dash.bm_mode_var.set(2)
        dash._on_bm_mode_changed()
        children_mode2 = dash.bm_gen_tree.get_children()
        assert len(children_mode2) == 1
        assert children_mode2[0] == "2001"
        assert dash.bm_gen_tree.item("2001", "values")[0] == "☑"
    finally:
        dash.destroy()


def test_dashboard_profile_sync_generals_selection():
    dash = safe_dashboard()
    try:
        c1 = City(id=101, name="ThanhChinh", type="Thành", pos_x=100, pos_y=200, level=20)
        gens = [
            General(id=3001, name="TrieuVan", role="vo", level=10, morale=100, stamina=95, stamina_max=100),
            General(id=3002, name="QuanVu", role="vo", level=11, morale=100, stamina=90, stamina_max=100),
            General(id=3003, name="TruongPhi", role="vo", level=9, morale=100, stamina=85, stamina_max=100),
        ]
        r = Roster(cities=[c1], camps=[], _generals={101: gens})
        dash._loaded(r)

        # Chỉ chọn tướng 3002 ở Gọi Man
        dash._deselect_all_gd_gens()
        vals = list(dash.gd_gen_tree.item("3002", "values"))
        vals[0] = "☑"
        dash.gd_gen_tree.item("3002", values=vals)

        prof = dash._collect_unified_profile()
        assert prof["goi_dan"]["generals"] == [3002]

        # Apply profile chỉ định chọn 3001 và 3003
        dash._apply_unified_profile({
            "goi_dan": {"generals": [3001, 3003]},
            "binh_man": {"generals": [3002]},
        })
        assert dash.gd_gen_tree.item("3001", "values")[0] == "☑"
        assert dash.gd_gen_tree.item("3002", "values")[0] == "☐"
        assert dash.gd_gen_tree.item("3003", "values")[0] == "☑"
    finally:
        dash.destroy()


def test_dashboard_gen_count_label_displays_and_updates():
    dash = safe_dashboard()
    try:
        c1 = City(id=101, name="ThanhChinh", type="Thành", pos_x=100, pos_y=200, level=20)
        gens = [
            General(id=4001, name="G1", role="vo", level=10, morale=100, stamina=100, stamina_max=100),
            General(id=4002, name="G2", role="vo", level=10, morale=100, stamina=100, stamina_max=100),
            General(id=4003, name="G3", role="vo", level=10, morale=100, stamina=100, stamina_max=100),
            General(id=4004, name="G4", role="vo", level=10, morale=100, stamina=100, stamina_max=100),
            General(id=4005, name="G5", role="vo", level=10, morale=100, stamina=100, stamina_max=100),
        ]
        camp1 = City(id=501, name="DoanhTrai1", type="Doanh trại", pos_x=105, pos_y=205)
        r = Roster(cities=[c1], camps=[camp1], _generals={101: gens, 501: gens})
        dash._loaded(r)

        # 1. Gọi Man: Mặc định chọn 3 tướng đầu tiên -> 1 đợt xuất kích
        assert hasattr(dash, "gd_gen_count_lbl")
        assert dash.gd_gen_count_lbl.cget("text") == "Đã chọn: 3 tướng (1 đợt xuất kích)"

        # Bỏ chọn tất cả Gọi Man -> 0 tướng, 0 đợt
        dash._deselect_all_gd_gens()
        assert dash.gd_gen_count_lbl.cget("text") == "Đã chọn: 0 tướng (0 đợt xuất kích)"

        # Chọn tất cả Gọi Man (5 tướng) -> 2 đợt xuất kích
        dash._select_all_gd_gens()
        assert dash.gd_gen_count_lbl.cget("text") == "Đã chọn: 5 tướng (2 đợt xuất kích)"

        # 2. Bình Man: Mặc định chọn tất cả tướng võ trong căn cứ (5 tướng) -> 2 đợt xuất kích
        assert hasattr(dash, "bm_gen_count_lbl")
        assert dash.bm_gen_count_lbl.cget("text") == "Đã chọn: 5 tướng (2 đợt xuất kích)"

        # Bỏ chọn tất cả Bình Man
        dash._deselect_all_bm_gens()
        assert dash.bm_gen_count_lbl.cget("text") == "Đã chọn: 0 tướng (0 đợt xuất kích)"
    finally:
        dash.destroy()


def test_dashboard_binhman_and_goidan_army_provisioning_controls_and_profile_sync(tmp_path):
    dash = safe_dashboard()
    try:
        # 1. Kiểm tra tồn tại và giá trị mặc định (0 / 0 / 0) của Gọi Man
        assert hasattr(dash, "gd_target_inf_var")
        assert hasattr(dash, "gd_target_cav_var")
        assert hasattr(dash, "gd_target_arc_var")
        assert hasattr(dash, "gd_auto_recruit_var")
        assert hasattr(dash, "gd_auto_morale_var")
        assert hasattr(dash, "gd_min_morale_var")
        assert hasattr(dash, "gd_adjust_troops_btn")

        assert dash.gd_target_inf_var.get() == "0"
        assert dash.gd_target_cav_var.get() == "0"
        assert dash.gd_target_arc_var.get() == "0"
        assert dash.gd_auto_recruit_var.get() is True
        assert dash.gd_auto_morale_var.get() is True
        assert dash.gd_min_morale_var.get() == "95"

        # 2. Kiểm tra tồn tại và giá trị mặc định (0 / 0 / 0) của Bình Man
        assert hasattr(dash, "bm_target_inf_var")
        assert hasattr(dash, "bm_target_cav_var")
        assert hasattr(dash, "bm_target_arc_var")
        assert hasattr(dash, "bm_auto_recruit_var")
        assert hasattr(dash, "bm_auto_morale_var")
        assert hasattr(dash, "bm_min_morale_var")
        assert hasattr(dash, "bm_adjust_troops_btn")

        assert dash.bm_target_inf_var.get() == "0"
        assert dash.bm_target_cav_var.get() == "0"
        assert dash.bm_target_arc_var.get() == "0"
        assert dash.bm_auto_recruit_var.get() is True
        assert dash.bm_auto_morale_var.get() is True
        assert dash.bm_min_morale_var.get() == "95"

        # 3. Thay đổi giá trị và kiểm tra _collect_unified_profile
        dash.gd_target_inf_var.set("2000")
        dash.gd_target_cav_var.set("3000")
        dash.gd_target_arc_var.set("1000")
        dash.gd_auto_recruit_var.set(False)
        dash.gd_auto_morale_var.set(True)
        dash.gd_min_morale_var.set("90")

        dash.bm_target_inf_var.set("4000")
        dash.bm_target_cav_var.set("500")
        dash.bm_target_arc_var.set("2500")
        dash.bm_auto_recruit_var.set(True)
        dash.bm_auto_morale_var.set(False)
        dash.bm_min_morale_var.set("85")

        prof = dash._collect_unified_profile()
        assert prof["goi_dan"]["target_infantry"] == "2000"
        assert prof["goi_dan"]["target_cavalry"] == "3000"
        assert prof["goi_dan"]["target_archers"] == "1000"
        assert prof["goi_dan"]["auto_recruit"] is False
        assert prof["goi_dan"]["auto_morale"] is True
        assert prof["goi_dan"]["min_morale"] == "90"

        assert prof["binh_man"]["target_infantry"] == "4000"
        assert prof["binh_man"]["target_cavalry"] == "500"
        assert prof["binh_man"]["target_archers"] == "2500"
        assert prof["binh_man"]["auto_recruit"] is True
        assert prof["binh_man"]["auto_morale"] is False
        assert prof["binh_man"]["min_morale"] == "85"

        # 4. Lưu profile ra file và nạp lại qua _apply_unified_profile
        prof_file = tmp_path / "army_profile.json"
        dash._save_unified_profile(prof_file)

        # Reset các biến trên GUI về 0
        dash.gd_target_inf_var.set("0")
        dash.bm_target_inf_var.set("0")

        ok, msg = dash._load_unified_profile(prof_file)
        assert ok is True
        assert dash.gd_target_inf_var.get() == "2000"
        assert dash.gd_target_cav_var.get() == "3000"
        assert dash.gd_target_arc_var.get() == "1000"
        assert dash.gd_auto_recruit_var.get() is False
        assert dash.gd_auto_morale_var.get() is True
        assert dash.gd_min_morale_var.get() == "90"

        assert dash.bm_target_inf_var.get() == "4000"
        assert dash.bm_target_cav_var.get() == "500"
        assert dash.bm_target_arc_var.get() == "2500"
        assert dash.bm_auto_recruit_var.get() is True
        assert dash.bm_auto_morale_var.get() is False
        assert dash.bm_min_morale_var.get() == "85"

        # 5. Kiểm tra _create_goidan_task và _create_binhman_task nhận TargetArmy
        r = dummy_roster()
        dash._loaded(r)
        dash.gd_city_combo.current(0)
        dash._on_gd_city_selected()
        gd_task = dash._create_goidan_task()
        assert gd_task is not None
        assert gd_task.target_army is not None
        assert gd_task.target_army.infantry == 2000
        assert gd_task.target_army.cavalry == 3000
        assert gd_task.auto_recruit is False
        assert gd_task.min_morale == 90

        dash.bm_city_combo.current(0)
        dash._on_bm_city_selected()
        bm_task = dash._create_binhman_task()
        assert bm_task is not None
        assert bm_task.target_army is not None
        assert bm_task.target_army.infantry == 4000
        assert bm_task.target_army.cavalry == 500
        assert bm_task.auto_morale is False
        assert bm_task.min_morale == 85
    finally:
        dash.destroy()


def test_dashboard_multi_base_binhman_treeview_and_independent_configs(tmp_path):
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # 1. Kiểm tra bm_bases_tree hiển thị đủ 3 căn cứ
        assert hasattr(dash, "bm_bases_tree")
        children = dash.bm_bases_tree.get_children()
        assert len(children) == 3
        assert "15230" in children
        assert "15237" in children
        assert "-1085" in children

        # 2. Cấu hình căn cứ 1 (ThànhChinh 15230): mode 2, radius 12, threshold 45, target_inf 5000
        dash.bm_bases_tree.selection_set("15230")
        dash._on_bm_bases_tree_select()
        dash.bm_mode_var.set(2)
        dash._on_bm_mode_changed()
        dash.bm_radius_var.set("12")
        dash.bm_threshold_var.set("45")
        dash.bm_target_inf_var.set("5000")
        dash._save_bm_current_base_config()

        # 3. Chuyển sang Doanh trại (-1085): mode 1, radius 8, threshold 20, target_inf 2000
        dash.bm_bases_tree.selection_set("-1085")
        dash._on_bm_bases_tree_select()
        assert dash._current_bm_base_id == -1085
        dash.bm_mode_var.set(1)
        dash._on_bm_mode_changed()
        dash.bm_radius_var.set("8")
        dash.bm_threshold_var.set("20")
        dash.bm_target_inf_var.set("2000")
        dash._save_bm_current_base_config()

        # 4. Chuyển lại ThànhChinh (15230), cấu hình độc lập phải được giữ nguyên
        dash.bm_bases_tree.selection_set("15230")
        dash._on_bm_bases_tree_select()
        assert dash._current_bm_base_id == 15230
        assert dash.bm_mode_var.get() == 2
        assert dash.bm_radius_var.get() == "12"
        assert dash.bm_threshold_var.get() == "45"
        assert dash.bm_target_inf_var.get() == "5000"

        # 5. Kiểm tra nút chọn tất cả / bỏ tất cả căn cứ
        dash._select_all_bm_bases(False)
        for iid in children:
            assert dash.bm_bases_tree.item(iid, "values")[0] == "☐"
            assert dash.bm_base_configs[int(iid)].enabled is False

        dash._select_all_bm_bases(True)
        for iid in children:
            assert dash.bm_bases_tree.item(iid, "values")[0] == "☑"
            assert dash.bm_base_configs[int(iid)].enabled is True

        # 6. Lưu profile ra file và nạp lại
        prof_file = tmp_path / "multi_base_bm_profile.json"
        dash._save_unified_profile(prof_file)

        # Xóa cấu hình hiện tại để test nạp lại
        dash.bm_base_configs.clear()
        ok, _msg = dash._load_unified_profile(prof_file)
        assert ok is True
        assert 15230 in dash.bm_base_configs
        assert -1085 in dash.bm_base_configs
        assert str(dash.bm_base_configs[15230].radius) == "12"
        assert str(dash.bm_base_configs[15230].threshold) == "45"
        assert str(dash.bm_base_configs[15230].target_infantry) == "5000"
        assert str(dash.bm_base_configs[-1085].radius) == "8"
        assert str(dash.bm_base_configs[-1085].threshold) == "20"
        assert str(dash.bm_base_configs[-1085].target_infantry) == "2000"
    finally:
        dash.destroy()


def test_dashboard_multi_base_binhman_task_creation_and_peers():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # Cấu hình 15230 và -1085 đều có tướng khả dụng (TrieuVan ở 15230, QuanVu ở -1085)
        dash.bm_base_configs[15230].enabled = True
        dash.bm_base_configs[15230].generals = [417506]
        dash.bm_base_configs[-1085].enabled = True
        dash.bm_base_configs[-1085].generals = [417520]
        dash.bm_base_configs[15237].enabled = False  # Tắt PhanThanh

        tasks = dash._create_binhman_tasks()
        assert len(tasks) == 2

        task_15230 = next(t for t in tasks if t.origin == (100, 200))
        task_camp = next(t for t in tasks if t.origin == (110, 210))

        # Kiểm tra peers được thiết lập chéo cho nhau
        assert len(task_15230.peers) == 1
        assert task_15230.peers[0].base_id == -1085

        assert len(task_camp.peers) == 1
        assert task_camp.peers[0].base_id == 15230

        # Kiểm tra dùng chung TargetLocks
        assert task_15230.locks is task_camp.locks
        assert task_15230.locks is dash.shared_target_locks

        # Kiểm tra non_blocking_relocate được kích hoạt
        assert task_camp.non_blocking_relocate is True
    finally:
        dash.destroy()


def test_dashboard_multi_base_binhman_new_base_safety_defaults():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # ADR-0029 Section 5: Trạng thái thi công mặc định: enabled = False, target_army = 0/0/0
        for b in r.bases:
            cfg = dash.bm_base_configs[b.id]
            assert cfg.enabled is False
            assert cfg.target_infantry == "0"
            assert cfg.target_cavalry == "0"
            assert cfg.target_archers == "0"
            # Generals: mặc định chọn tất cả võ tướng trong căn cứ đó
            vos = [g.id for g in r.generals_of(b.id) if g.role == "vo"]
            assert set(cfg.generals) == set(vos)
    finally:
        dash.destroy()


def test_dashboard_multi_base_binhman_legacy_backward_compatibility(tmp_path):
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # Giả lập file profile cũ không có trường 'bases'
        old_data = {
            "binh_man": {
                "mode": 2,
                "radius": "14",
                "threshold": "55",
                "mantypes": "7,8",
                "generals": [417506],
                "target_infantry": "3000",
            }
        }
        prof_file = tmp_path / "old_profile.json"
        with open(prof_file, "w", encoding="utf-8") as f:
            json.dump(old_data, f)

        # Xóa cấu hình hiện tại để test nạp profile cũ
        dash.bm_base_configs.clear()
        ok, _msg = dash._load_unified_profile(prof_file)
        assert ok is True

        # Tương thích ngược: hồ sơ cũ được tự động ánh xạ vào căn cứ đang hoạt động hoặc đầu tiên (15230)
        assert 15230 in dash.bm_base_configs
        cfg = dash.bm_base_configs[15230]
        assert cfg.enabled is True
        assert cfg.mode == 2
        assert str(cfg.radius) == "14"
        assert str(cfg.threshold) == "55"
        assert cfg.generals == [417506]
        assert str(cfg.target_infantry) == "3000"
    finally:
        dash.destroy()


def test_dashboard_append_text_buffer_batch_pruning():
    """Kiểm tra cơ chế cắt tỉa theo khối (batch trimming) của _append_text_buffer (ADR-0030)."""
    dash = safe_dashboard()
    try:
        txt = tk.Text(dash)
        def _get_line_count(w):
            raw = int(w.index("end-1c").split(".")[0])
            return (raw - 1) if w.get("end-2c", "end-1c") == "\n" else raw

        # Ngưỡng 10 dòng, mỗi lần cắt tỉa xóa 4 dòng
        for i in range(1, 11):
            dash._append_text_buffer(txt, f"Dòng {i}\n", max_lines=10, trim_batch=4)
        
        # Đang có đúng 10 dòng
        assert _get_line_count(txt) == 10
        assert "Dòng 1\n" in txt.get("1.0", "end")

        # Thêm dòng 11 -> kích hoạt batch trim (xóa 5 dòng đầu)
        dash._append_text_buffer(txt, "Dòng 11\n", max_lines=10, trim_batch=4)
        assert _get_line_count(txt) == 6
        content = txt.get("1.0", "end")
        assert "Dòng 1\n" not in content
        assert "Dòng 5\n" not in content
        assert "Dòng 6\n" in content
        assert "Dòng 11\n" in content

        # Thêm 4 dòng tiếp theo (12, 13, 14, 15) -> tổng cộng 10 dòng, không bị cắt tỉa
        for i in range(12, 16):
            dash._append_text_buffer(txt, f"Dòng {i}\n", max_lines=10, trim_batch=4)
        assert _get_line_count(txt) == 10

        # Thêm dòng 16 -> chạm 11 dòng -> tiếp tục batch trim
        dash._append_text_buffer(txt, "Dòng 16\n", max_lines=10, trim_batch=4)
        assert _get_line_count(txt) == 6
        assert "Dòng 16\n" in txt.get("1.0", "end")
    finally:
        dash.destroy()


def test_dashboard_combat_log_and_manual_clear_buttons():
    """Kiểm tra ghi log chiến trường qua _append_text_buffer và các nút xóa trắng thủ công (ADR-0030)."""
    dash = safe_dashboard()
    try:
        # Ghi log vào từng tab
        dash._append_tp_log("Log Thảo Phạt 1")
        dash._append_gd_log("Log Gọi Man 1")
        dash._append_bm_log("Log Bình Man 1")
        dash._append_logis_log("Log Hậu Cần 1")
        dash._append_bt_log("Log Chiến Trường 1")

        # Kiểm tra nội dung xuất hiện
        assert "Log Thảo Phạt 1" in dash.tp_log_text.get("1.0", "end")
        assert "Log Gọi Man 1" in dash.gd_log_text.get("1.0", "end")
        assert "Log Bình Man 1" in dash.bm_log_text.get("1.0", "end")
        assert "Log Hậu Cần 1" in dash.logis_log_text.get("1.0", "end")
        assert "Log Chiến Trường 1" in dash.bt_log_text.get("1.0", "end")

        # Thực hiện xóa trắng thủ công
        dash._tp_clear_log()
        assert dash.tp_log_text.get("1.0", "end-1c") == ""

        dash._gd_clear_log()
        assert dash.gd_log_text.get("1.0", "end-1c") == ""

        dash._bm_clear_log()
        assert dash.bm_log_text.get("1.0", "end-1c") == ""

        dash._logis_clear_log()
        assert dash.logis_log_text.get("1.0", "end-1c") == ""

        dash._bt_clear_log()
        assert dash.bt_log_text.get("1.0", "end-1c") == ""
    finally:
        dash.destroy()


def test_dashboard_crafting_ui_and_actions():
    """Kiểm tra điều khiển Chế Tạo Quân Giới trên Tab Tổng quan (ADR-0031)."""
    dash = safe_dashboard()
    try:
        dash._loaded(dummy_roster())
        assert hasattr(dash, "craft_city_combo")
        assert hasattr(dash, "craft_weapon_combo")
        assert hasattr(dash, "craft_amount_var")
        assert hasattr(dash, "craft_interval_var")
        assert dash.craft_interval_var.get() == "5"
        assert hasattr(dash, "craft_enable_var")
        assert hasattr(dash, "craft_tree")
        assert dash.craft_tree.heading("interval")["text"] == "Chu kỳ (phút)"

        # Kiểm tra danh sách vũ khí trong dropdown có 67 loại
        vals = dash.craft_weapon_combo["values"]
        assert len(vals) == 67
        assert "101. Thấu giáp thương (Binh khí)" in vals[0]

        # Kiểm tra bảng danh sách thành
        children = dash.craft_tree.get_children()
        assert len(children) >= 1

        # Chọn thành đầu tiên
        first_cid = int(children[0])
        dash._select_craft_city_by_id(first_cid)

        # Chỉnh cấu hình: chọn Cung nỗ (201), số lượng 2000, chu kỳ 15 phút, bật
        for idx, item in enumerate(dash.craft_weapon_combo["values"]):
            if item.startswith("201."):
                dash.craft_weapon_combo.current(idx)
                break
        dash.craft_amount_var.set("2000")
        dash.craft_interval_var.set("15")
        dash.craft_enable_var.set(True)
        dash._save_current_craft_form_to_config()

        assert first_cid in dash.craft_configs
        cfg = dash.craft_configs[first_cid]
        assert cfg.weapon_id == 201
        assert cfg.amount == "2000"
        assert cfg.interval == "15"
        assert cfg.enabled is True

        # Kiểm tra hiển thị trên treeview
        row_vals = dash.craft_tree.item(str(first_cid), "values")
        assert row_vals[0] == "☑"
        assert "Thiết thai cung" in row_vals[2]
        assert row_vals[3] == "2000"
        assert row_vals[4] == "15"
    finally:
        dash.destroy()


def test_dashboard_crafting_profile_sync(tmp_path):
    """Kiểm tra nạp và lưu cấu hình Chế Tạo Quân Giới qua Unified Profile (ADR-0031)."""
    dash = safe_dashboard()
    try:
        dash._loaded(dummy_roster())
        # Giả lập cấu hình chế tạo cho 2 thành
        c1_id = 15230
        c2_id = 15237
        dash.craft_configs[c1_id] = CityCraftConfig(
            city_id=c1_id,
            weapon_id=301,  # Ngư lân giáp
            amount="5000",
            interval="120",
            enabled=True,
        )
        dash.craft_configs[c2_id] = CityCraftConfig(
            city_id=c2_id,
            weapon_id=401,  # Tuyệt địa mã
            amount="3000",
            interval="90",
            enabled=False,
        )
        dash._sync_craft_ui_from_current_city()

        prof_dict = dash._collect_unified_profile()
        assert "crafting" in prof_dict
        assert "cities" in prof_dict["crafting"]
        assert str(c1_id) in prof_dict["crafting"]["cities"]
        assert prof_dict["crafting"]["cities"][str(c1_id)]["weapon_id"] == 301
        assert prof_dict["crafting"]["cities"][str(c1_id)]["enabled"] is True

        # Xóa cấu hình hiện tại và test nạp lại
        dash.craft_configs.clear()
        sections = dash._apply_unified_profile(prof_dict)
        assert "Chế Tạo Quân Giới" in sections
        assert c1_id in dash.craft_configs
        assert dash.craft_configs[c1_id].weapon_id == 301
        assert dash.craft_configs[c1_id].amount == "5000"
        assert dash.craft_configs[c1_id].enabled is True

        assert c2_id in dash.craft_configs
        assert dash.craft_configs[c2_id].weapon_id == 401
        assert dash.craft_configs[c2_id].enabled is False
    finally:
        dash.destroy()


def test_dashboard_overview_two_columns_and_multi_crafting():
    """Kiểm tra chia 2 cột (Luyện sĩ khí & Chế tạo quân giới) và chọn nhiều loại quân giới cùng lúc."""
    dash = safe_dashboard()
    try:
        dash._loaded(dummy_roster())

        # 1. Kiểm tra layout 2 cột: mo_tree và craft_tree nằm trong 2 Frame thuộc layout grid
        mo_frame = dash.mo_tree.master.master
        craft_frame = dash.craft_tree.master.master
        assert mo_frame.master == craft_frame.master
        mo_grid = mo_frame.grid_info()
        craft_grid = craft_frame.grid_info()
        assert int(mo_grid["column"]) == 0
        assert int(craft_grid["column"]) == 1

        # 2. Kiểm tra MultiSelectDropdown cho quân giới
        assert hasattr(dash, "craft_weapon_dropdown")
        # Chọn nhiều loại vũ khí: 101 (Thấu giáp thương), 201 (Thiết thai cung), 301 (Ngư lân giáp)
        dash.craft_weapon_dropdown.set_selected([101, 201, 301])
        selected = dash.craft_weapon_dropdown.get_selected()
        assert selected == [101, 201, 301]

        # Lưu cấu hình và kiểm tra CityCraftConfig lưu đủ 3 loại
        dash._save_current_craft_form_to_config()
        cid = dash._get_current_craft_city_id()
        assert cid in dash.craft_configs
        cfg = dash.craft_configs[cid]
        assert cfg.weapon_ids == [101, 201, 301]
        assert cfg.weapon_id == 101

        # Kiểm tra hiển thị Treeview: báo '3 loại'
        row_vals = dash.craft_tree.item(str(cid), "values")
        assert "3 loại" in row_vals[2]

        # 3. Kiểm tra export Unified Profile lưu danh sách weapon_ids
        prof = dash._collect_unified_profile()
        assert prof["crafting"]["cities"][str(cid)]["weapon_ids"] == [101, 201, 301]

        # 4. Kiểm tra nạp lại Unified Profile
        dash.craft_configs.clear()
        dash._apply_unified_profile(prof)
        assert dash.craft_configs[cid].weapon_ids == [101, 201, 301]
        assert dash.craft_weapon_dropdown.get_selected() == [101, 201, 301]

        # 5. Kiểm tra thực thi chế tạo nhiều loại qua _do_craft_now
        with patch("linhvuong.dashboard.WeaponCrafter") as mock_crafter_cls:
            mock_crafter = mock_crafter_cls.return_value
            mock_crafter.craft_once.return_value = (True, 0, "Chế tạo thành công")
            dash._do_craft_now()

            # Chờ worker thread kết thúc
            import time
            time.sleep(0.15)

            # Phải gọi craft_once cho cả 3 loại quân giới
            assert mock_crafter.craft_once.call_count == 3
            called_wids = [call[0][1] for call in mock_crafter.craft_once.call_args_list]
            assert called_wids == [101, 201, 301]
    finally:
        dash.destroy()


def test_building_task_respects_resource_city_checkbox():
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)
        # Thành 15230 chọn xây dựng nhưng KHÔNG tích Tài nguyên
        # Thành 15237 chọn xây dựng VÀ CÓ tích Tài nguyên
        dash._selected_building_cities = {15230, 15237}
        dash._selected_resource_cities = {15237}
        dash.bld_open_box_var.set(True)

        plan = {"pid": 1, "gid": 1, "target_level": 5, "name": "Quan Phủ", "enabled": True}
        dash._city_building_plans[15230] = [plan]
        dash._city_building_plans[15237] = [plan]

        with patch("linhvuong.dashboard.BuildingTask") as mock_bld_task, \
             patch("linhvuong.dashboard.BuildingAutoRunner") as mock_runner_cls, \
             patch.object(dash, "_save_current_bld_tree_to_cache"):
            dash._toggle_building()

            calls = mock_bld_task.call_args_list
            assert len(calls) == 2
            call_15230 = next(c for c in calls if c.kwargs.get("city_id") == 15230)
            call_15237 = next(c for c in calls if c.kwargs.get("city_id") == 15237)

            # Thành không tích ô tài nguyên (15230) tuyệt đối không được tự động mở rương
            assert call_15230.kwargs.get("auto_open_box") is False
            # Thành có tích ô tài nguyên (15237) được phép mở rương khi thiếu
            assert call_15237.kwargs.get("auto_open_box") is True
    finally:
        dash.destroy()


def test_notification_and_boss_capture_gui():
    """Kiểm tra cấu hình Thông Báo Đa Kênh & Tự Động Bắt BOSS trên Dashboard (ADR-0036)."""
    dash = safe_dashboard()
    try:
        dash._loaded(dummy_roster())
        # 1. Variables and components
        assert hasattr(dash, "notification_config")
        assert hasattr(dash, "bt_auto_capture_boss_var")
        assert hasattr(dash, "bt_capture_morale_var")
        assert dash.bt_capture_morale_var.get() == "60"
        assert dash.bt_auto_capture_boss_var.get() is False

        # 2. _build_combat_config
        dash.bt_auto_capture_boss_var.set(True)
        dash.bt_capture_morale_var.set("55")
        dash.notification_config.notify_telegram = True
        dash.notification_config.telegram_bot_token = "123:ABC"

        cfg = dash._build_combat_config()
        assert cfg.auto_capture_boss is True
        assert cfg.capture_boss_max_morale == 55
        assert cfg.notification_config is not None
        assert cfg.notification_config.notify_telegram is True

        # 3. Notification Settings Dialog
        dash._open_notification_settings_dialog()
        assert dash._notify_win is not None
        assert dash._notify_win.winfo_exists()

        # Re-opening dialog should lift existing window
        dash._open_notification_settings_dialog()
        assert dash._notify_win.winfo_exists()

        # Kiểm tra bấm nút '🧪 Thử Nghiệm Thông Báo' không gây lỗi và kích hoạt dispatch_boss_alert
        test_btn = None
        for child in dash._notify_win.winfo_children():
            if isinstance(child, tk.Frame):
                for sub in child.winfo_children():
                    if isinstance(sub, ttk.Button) and "Thử Nghiệm" in sub.cget("text"):
                        test_btn = sub
                        break
        assert test_btn is not None
        with patch("linhvuong.dashboard.dispatch_boss_alert") as mock_dispatch:
            test_btn.invoke()
            mock_dispatch.assert_called_once()
            call_kwargs = mock_dispatch.call_args.kwargs
            assert call_kwargs["boss_name"] == "[Thử Nghiệm] Tào Tháo"
            assert call_kwargs["config"].notify_desktop_toast is True

        # Destroy dialog
        dash._notify_win.destroy()
        dash._notify_win = None

        # 4. Profile Collect & Apply roundtrip
        prof = dash._collect_unified_profile()
        assert "notifications" in prof
        assert prof["combat"]["auto_capture_boss"] is True
        assert prof["combat"]["capture_boss_max_morale"] == "55"
        assert prof["notifications"]["telegram_bot_token"] == "123:ABC"

        # Reset vars and reapply
        dash.bt_auto_capture_boss_var.set(False)
        dash.bt_capture_morale_var.set("60")
        dash.notification_config.telegram_bot_token = ""

        sections = dash._apply_unified_profile(prof)
        assert "Chiến Trường" in sections
        assert "Thông Báo" in sections
        assert dash.bt_auto_capture_boss_var.get() is True
        assert dash.bt_capture_morale_var.get() == "55"
        assert dash.notification_config.telegram_bot_token == "123:ABC"
    finally:
        dash.destroy()











