import json
import pytest
from unittest.mock import MagicMock, patch
from linhvuong.dashboard import Dashboard
from linhvuong.roster import Army, City, General, Roster

try:
    import _tkinter
except ImportError:
    _tkinter = None


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


def safe_dashboard():
    if _tkinter is None:
        pytest.skip("tkinter not available")
    session = MagicMock()
    with patch("threading.Thread"):
        try:
            dash = Dashboard(session, 57)
            dash.withdraw()
        except Exception as e:
            pytest.skip(f"Tkinter display error: {e}")
    return dash


def test_thao_phat_and_binh_man_widgets_after_load_config(tmp_path):
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        # 1. Thiết lập các dropdown & checkbox cho Thảo Phạt
        # Chọn thành thứ 2 (PhanThanh - 15237) hoặc camp (-1085)
        dash.tp_city_combo.current(2)  # TienDon (-1085)
        dash._on_tp_city_selected()
        # Chọn tướng trong Thảo Phạt
        tp_gens = dash.tp_gen_tree.get_children()
        assert len(tp_gens) >= 1
        # Check tướng QuanVu (417520)
        dash.tp_gen_tree.item(tp_gens[0], values=("☑",) + tuple(dash.tp_gen_tree.item(tp_gens[0], "values")[1:]))
        dash.tp_mission_combo.current(2)  # Mission index 2
        dash.tp_auto_recruit_var.set(False)  # Checkbox False
        dash.tp_auto_morale_var.set(False)   # Checkbox False

        # 2. Thiết lập các dropdown & checkbox cho Bình Man
        # Chọn base -1085 trong Bình Man
        dash._switch_bm_base(-1085)
        dash.bm_mode_var.set(1)
        dash._on_bm_mode_changed()
        dash.bm_auto_recruit_var.set(False)
        dash.bm_auto_morale_var.set(False)
        dash.bm_parent_city_combo.current(1)  # PhanThanh (15237)
        dash.bm_mantypes_dropdown.set_selected([1, 2])
        # Check tướng trong bm_gen_tree cho -1085
        bm_gens = dash.bm_gen_tree.get_children()
        assert len(bm_gens) >= 1
        dash.bm_gen_tree.item(bm_gens[0], values=("☑",) + tuple(dash.bm_gen_tree.item(bm_gens[0], "values")[1:]))
        dash._save_bm_current_base_config()

        # Thiết lập base 15230 (Thành Chính, mode 2)
        dash._switch_bm_base(15230)
        dash.bm_mode_var.set(2)
        dash._on_bm_mode_changed()
        dash.bm_mantypes_dropdown.set_selected([3, 4])
        dash._save_bm_current_base_config()

        # Chọn căn cứ chạy trong bm_bases_tree
        dash.bm_base_configs[-1085].enabled = True
        dash.bm_base_configs[15230].enabled = False
        dash._refresh_bm_bases_tree()

        # 3. Lưu profile
        prof_file = tmp_path / "test_prof.json"
        dash._save_unified_profile(prof_file)

        # 4. Tạo dashboard mới và nạp config lên (kịch bản nạp sau khi đã load roster)
        dash2 = safe_dashboard()
        try:
            dash2._loaded(r)
            ok, msg = dash2._load_unified_profile(prof_file)
            assert ok is True

            # KIỂM TRA THẢO PHẠT
            failures = []
            # Dropdown thành trì:
            if dash2.tp_city_combo.current() != 2:
                failures.append(f"tp_city_combo: current is {dash2.tp_city_combo.current()}, expected 2")
            # Dropdown chiến dịch:
            if dash2.tp_mission_combo.current() != 2:
                failures.append(f"tp_mission_combo: current is {dash2.tp_mission_combo.current()}, expected 2")
            # Checkbox tự động bổ sung lính:
            if dash2.tp_auto_recruit_var.get() is not False:
                failures.append(f"tp_auto_recruit_var: {dash2.tp_auto_recruit_var.get()} expected False")
            # Checkbox tự động nâng sĩ khí:
            if dash2.tp_auto_morale_var.get() is not False:
                failures.append(f"tp_auto_morale_var: {dash2.tp_auto_morale_var.get()} expected False")
            # Checkbox tướng trong tp_gen_tree:
            tp_items = dash2.tp_gen_tree.get_children()
            checked_tp_gens = [iid for iid in tp_items if dash2.tp_gen_tree.item(iid, "values")[0] == "☑"]
            if "417520" not in checked_tp_gens:
                failures.append(f"tp_gen_tree: {checked_tp_gens} does not contain 417520")

            # KIỂM TRA BÌNH MAN
            dash2._switch_bm_base(15230)
            if not dash2.bm_city_combo.get() or "ThanhChinh" not in dash2.bm_city_combo.get():
                failures.append(f"bm_city_combo for 15230: '{dash2.bm_city_combo.get()}', values={dash2.bm_city_combo['values']}")
            if set(dash2.bm_mantypes_dropdown.get_selected()) != {3, 4}:
                failures.append(f"bm_mantypes_dropdown for 15230: {dash2.bm_mantypes_dropdown.get_selected()} expected [3, 4]")

            dash2._switch_bm_base(-1085)
            # Dropdown căn cứ:
            if not dash2.bm_city_combo.get() or "TienDon" not in dash2.bm_city_combo.get():
                failures.append(f"bm_city_combo for -1085: '{dash2.bm_city_combo.get()}', values={dash2.bm_city_combo['values']}")
            # Dropdown thành mẹ:
            if dash2.bm_parent_city_combo.current() != 1:
                failures.append(f"bm_parent_city_combo: current is {dash2.bm_parent_city_combo.current()}, expected 1")
            # Dropdown loại man:
            if set(dash2.bm_mantypes_dropdown.get_selected()) != {1, 2}:
                failures.append(f"bm_mantypes_dropdown: {dash2.bm_mantypes_dropdown.get_selected()} expected [1, 2]")
            # Checkbox tự động bổ sung lính:
            if dash2.bm_auto_recruit_var.get() is not False:
                failures.append(f"bm_auto_recruit_var: {dash2.bm_auto_recruit_var.get()} expected False")
            # Checkbox tự động nâng sĩ khí:
            if dash2.bm_auto_morale_var.get() is not False:
                failures.append(f"bm_auto_morale_var: {dash2.bm_auto_morale_var.get()} expected False")
            # Checkbox căn cứ chạy trong bm_bases_tree:
            if dash2.bm_bases_tree.item("-1085", "values")[0] != "☑":
                failures.append(f"bm_bases_tree -1085: {dash2.bm_bases_tree.item('-1085', 'values')[0]} expected ☑")
            if dash2.bm_bases_tree.item("15230", "values")[0] != "☐":
                failures.append(f"bm_bases_tree 15230: {dash2.bm_bases_tree.item('15230', 'values')[0]} expected ☐")
            # Checkbox tướng trong bm_gen_tree:
            dash2._switch_bm_base(-1085)
            bm_items = dash2.bm_gen_tree.get_children()
            checked_bm_gens = [iid for iid in bm_items if dash2.bm_gen_tree.item(iid, "values")[0] == "☑"]
            if "417520" not in checked_bm_gens:
                failures.append(f"bm_gen_tree: {checked_bm_gens} does not contain 417520")

            assert not failures, "\n".join(failures)

        finally:
            dash2.destroy()
    finally:
        dash.destroy()


def test_thao_phat_and_binh_man_widgets_after_load_config_startup(tmp_path):
    dash = safe_dashboard()
    try:
        r = dummy_roster()
        dash._loaded(r)

        dash.tp_city_combo.current(2)
        dash._on_tp_city_selected()
        tp_gens = dash.tp_gen_tree.get_children()
        dash.tp_gen_tree.item(tp_gens[0], values=("☑",) + tuple(dash.tp_gen_tree.item(tp_gens[0], "values")[1:]))
        dash.tp_mission_combo.current(2)
        dash.tp_auto_recruit_var.set(False)
        dash.tp_auto_morale_var.set(False)

        dash._switch_bm_base(-1085)
        dash.bm_mode_var.set(1)
        dash._on_bm_mode_changed()
        dash.bm_auto_recruit_var.set(False)
        dash.bm_auto_morale_var.set(False)
        dash.bm_parent_city_combo.current(1)
        dash.bm_mantypes_dropdown.set_selected([1, 2])
        bm_gens = dash.bm_gen_tree.get_children()
        dash.bm_gen_tree.item(bm_gens[0], values=("☑",) + tuple(dash.bm_gen_tree.item(bm_gens[0], "values")[1:]))
        dash._save_bm_current_base_config()
        dash.bm_base_configs[-1085].enabled = True
        dash.bm_base_configs[15230].enabled = False
        dash._refresh_bm_bases_tree()

        prof_file = tmp_path / "test_prof_startup.json"
        dash._save_unified_profile(prof_file)

        # Dashboard mới: load profile TRƯỚC, rồi mới _loaded(roster)
        dash2 = safe_dashboard()
        try:
            ok, msg = dash2._load_unified_profile(prof_file)
            assert ok is True
            dash2._loaded(r)

            failures = []
            if dash2.tp_city_combo.current() != 2:
                failures.append(f"tp_city_combo: current is {dash2.tp_city_combo.current()}, expected 2")
            if dash2.tp_mission_combo.current() != 2:
                failures.append(f"tp_mission_combo: current is {dash2.tp_mission_combo.current()}, expected 2")
            if dash2.tp_auto_recruit_var.get() is not False:
                failures.append(f"tp_auto_recruit_var: {dash2.tp_auto_recruit_var.get()} expected False")
            if dash2.tp_auto_morale_var.get() is not False:
                failures.append(f"tp_auto_morale_var: {dash2.tp_auto_morale_var.get()} expected False")
            tp_items = dash2.tp_gen_tree.get_children()
            checked_tp_gens = [iid for iid in tp_items if dash2.tp_gen_tree.item(iid, "values")[0] == "☑"]
            if "417520" not in checked_tp_gens:
                failures.append(f"tp_gen_tree: {checked_tp_gens} does not contain 417520")

            if dash2.bm_parent_city_combo.current() != 1:
                failures.append(f"bm_parent_city_combo: current is {dash2.bm_parent_city_combo.current()}, expected 1")
            if set(dash2.bm_mantypes_dropdown.get_selected()) != {1, 2}:
                failures.append(f"bm_mantypes_dropdown: {dash2.bm_mantypes_dropdown.get_selected()} expected [1, 2]")
            if dash2.bm_auto_recruit_var.get() is not False:
                failures.append(f"bm_auto_recruit_var: {dash2.bm_auto_recruit_var.get()} expected False")
            if dash2.bm_auto_morale_var.get() is not False:
                failures.append(f"bm_auto_morale_var: {dash2.bm_auto_morale_var.get()} expected False")
            if dash2.bm_bases_tree.item("-1085", "values")[0] != "☑":
                failures.append(f"bm_bases_tree -1085: {dash2.bm_bases_tree.item('-1085', 'values')[0]} expected ☑")
            if dash2.bm_bases_tree.item("15230", "values")[0] != "☐":
                failures.append(f"bm_bases_tree 15230: {dash2.bm_bases_tree.item('15230', 'values')[0]} expected ☐")

            dash2._switch_bm_base(-1085)
            bm_items = dash2.bm_gen_tree.get_children()
            checked_bm_gens = [iid for iid in bm_items if dash2.bm_gen_tree.item(iid, "values")[0] == "☑"]
            if "417520" not in checked_bm_gens:
                failures.append(f"bm_gen_tree: {checked_bm_gens} does not contain 417520")

            assert not failures, "\n".join(failures)
        finally:
            dash2.destroy()
    finally:
        dash.destroy()
