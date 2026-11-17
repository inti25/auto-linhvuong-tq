import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from linhvuong.dashboard import Dashboard
from linhvuong.profile import ProfileStore
from linhvuong.roster import Army, City, General, Roster

try:
    import _tkinter
except ImportError:
    _tkinter = None


def _dummy_roster() -> Roster:
    c1 = City(id=15230, name="ThanhChinh", type="Thành", pos_x=100, pos_y=200, level=20)
    c2 = City(id=15237, name="PhanThanh", type="Thành", pos_x=105, pos_y=205, level=15)
    camp1 = City(id=-1085, name="TienDon", type="Doanh trại", pos_x=110, pos_y=210)
    g1 = General(id=417506, name="TrieuVan", role="vo", level=10, morale=100, stamina=95, stamina_max=100)
    g2 = General(id=417520, name="QuanVu", role="vo", level=11, morale=100, stamina=90, stamina_max=100)
    return Roster(
        cities=[c1, c2],
        camps=[camp1],
        _generals={15230: [g1], -1085: [g2]},
        _armies={417506: Army(100, 200, 300), 417520: Army(500, 0, 0)},
    )


def _create_dash(tmp_path: Path, monkeypatch, username: str = "tester", server_id: int = 57) -> Dashboard:
    if _tkinter is None:
        pytest.skip("tkinter not available")
    monkeypatch.chdir(tmp_path)
    session = MagicMock()
    with patch("threading.Thread"):
        try:
            dash = Dashboard(session, server_id, username=username)
            dash.withdraw()
        except Exception as e:
            pytest.skip(f"Tkinter display error: {e}")
    return dash


def _wait_for_auto_save(dash: Dashboard, target: Path, timeout: float = 1.5) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        dash.update()
        if target.exists() and not dash._auto_save_dirty:
            return
        time.sleep(0.02)


def test_auto_save_not_triggered_on_init_or_roster_load(tmp_path, monkeypatch):
    dash = _create_dash(tmp_path, monkeypatch)
    try:
        profile_file = tmp_path / "auto_profile_tester_57.json"
        dash._loaded(_dummy_roster())
        dash.update()
        assert dash._auto_save_dirty is False
        assert not profile_file.exists()
    finally:
        dash.destroy()
    assert not profile_file.exists()


def test_auto_save_debounce_on_var_combo_dropdown_and_tree_edits(tmp_path, monkeypatch):
    dash = _create_dash(tmp_path, monkeypatch)
    try:
        dash._auto_save_delay_ms = 50
        dash._loaded(_dummy_roster())
        profile_file = tmp_path / "auto_profile_tester_57.json"
        assert not profile_file.exists()

        # 1. Edit Entry / Checkbutton variables across tabs
        dash.tp_target_inf_var.set("8500")
        dash.tp_auto_recruit_var.set(False)
        dash.bt_leave_boss_var.set(False)
        dash.nt_speedup_march_var.set(True)
        dash.dt_dest_x_var.set("321")
        dash.dt_dest_y_var.set("654")
        assert dash._auto_save_dirty is True

        _wait_for_auto_save(dash, profile_file)
        assert profile_file.exists()

        loaded = ProfileStore.load(profile_file)
        assert loaded.thao_phat.target_infantry == "8500"
        assert loaded.thao_phat.auto_recruit is False
        assert loaded.combat.leave_boss_last is False
        assert loaded.nien_thu.speed_up_march is True
        assert loaded.ditrai.dest_x == "321"
        assert loaded.ditrai.dest_y == "654"

        # 2. Edit Combobox selection & MultiSelectDropdown
        dash.tp_mission_combo.current(2)
        dash.tp_mission_combo.event_generate("<<ComboboxSelected>>")
        dash.gd_target_dropdown.set_selected([8, 9])

        _wait_for_auto_save(dash, profile_file)
        loaded2 = ProfileStore.load(profile_file)
        assert loaded2.thao_phat.mission_idx == 2
        assert loaded2.goi_dan.target_types == [8, 9]

        # 3. Edit building / research queues via UI actions
        dash.bld_target_lvl_var.set("25")
        first_bld = dash.bld_tree.get_children("")[0]
        dash.bld_tree.selection_set(first_bld)
        dash._set_bld_target_lvl()

        dash._select_all_res(True)
        dash.res_target_lvl_var.set("18")
        dash._set_res_target_lvl_all()

        _wait_for_auto_save(dash, profile_file)
        loaded3 = ProfileStore.load(profile_file)
        assert any(p.get("target_level") == 25 and p.get("enabled") for p in loaded3.building.plans)
        assert all(t.get("enabled") and t.get("target_level") == 18 for t in loaded3.research.techs)
    finally:
        dash.destroy()


def test_auto_save_flushes_pending_changes_on_destroy(tmp_path, monkeypatch):
    dash = _create_dash(tmp_path, monkeypatch)
    profile_file = tmp_path / "auto_profile_tester_57.json"
    dash._auto_save_delay_ms = 5000  # Long debounce so timer has not fired yet
    dash._loaded(_dummy_roster())

    dash.res_gold_thresh_var.set("999999")
    dash.craft_amount_var.set("4321")
    dash.craft_enable_var.set(True)
    assert dash._auto_save_dirty is True
    assert not profile_file.exists()

    # Closing dashboard flushes dirty state immediately
    dash.destroy()

    assert profile_file.exists()
    loaded = ProfileStore.load(profile_file)
    assert loaded.resource.gold_threshold == "999999"
    assert loaded.crafting.cities["15230"].amount == "4321"
    assert loaded.crafting.cities["15230"].enabled is True


def test_auto_save_binh_man_base_switch_preserves_and_saves_both_bases(tmp_path, monkeypatch):
    dash = _create_dash(tmp_path, monkeypatch)
    try:
        dash._auto_save_delay_ms = 40
        dash._loaded(_dummy_roster())
        profile_file = tmp_path / "auto_profile_tester_57.json"

        # Switch to camp -1085, edit radius, then switch to city 15230
        dash._switch_bm_base(-1085)
        dash.bm_radius_var.set("14")
        dash.bm_auto_recruit_var.set(False)
        dash._switch_bm_base(15230)
        dash.bm_radius_var.set("9")

        _wait_for_auto_save(dash, profile_file)
        loaded = ProfileStore.load(profile_file)
        assert loaded.binh_man.bases["-1085"].radius == "14"
        assert loaded.binh_man.bases["-1085"].auto_recruit is False
        assert loaded.binh_man.bases["15230"].radius == "9"
    finally:
        dash.destroy()


def test_auto_save_respects_loaded_custom_profile_path(tmp_path, monkeypatch):
    custom_dir = tmp_path / "profiles"
    custom_dir.mkdir()
    custom_file = custom_dir / "custom_acc.json"

    dash = _create_dash(tmp_path, monkeypatch)
    try:
        dash._auto_save_delay_ms = 40
        dash._save_unified_profile(custom_file)
        ok, _ = dash._load_unified_profile(custom_file)
        assert ok is True
        assert dash._auto_save_dirty is False

        dash.bt_window_var.set("22")
        _wait_for_auto_save(dash, custom_file)

        data = json.loads(custom_file.read_text(encoding="utf-8"))
        assert data["combat"]["formation_window_seconds"] == "22"
        assert not (tmp_path / "custom_acc.json").exists()
    finally:
        dash.destroy()


def test_auto_save_survives_load_without_overwriting_saved_data(tmp_path, monkeypatch):
    profile_file = tmp_path / "auto_profile_tester_57.json"
    dash1 = _create_dash(tmp_path, monkeypatch)
    try:
        dash1._auto_save_delay_ms = 40
        dash1._loaded(_dummy_roster())
        dash1.tp_min_morale_var.set("88")
        dash1.gd_radius_var.set("12")
        _wait_for_auto_save(dash1, profile_file)
    finally:
        dash1.destroy()

    # Re-open a fresh Dashboard; verify auto-loaded values persist and aren't overwritten on init/load
    dash2 = _create_dash(tmp_path, monkeypatch)
    try:
        assert dash2.tp_min_morale_var.get() == "88"
        assert dash2.gd_radius_var.get() == "12"
        dash2._loaded(_dummy_roster())
        dash2.update()
        assert dash2._auto_save_dirty is False
        loaded = ProfileStore.load(profile_file)
        assert loaded.thao_phat.min_morale == "88"
        assert loaded.goi_dan.radius == "12"
    finally:
        dash2.destroy()


def test_auto_save_tree_toggles_and_uncheck_all_generals(tmp_path, monkeypatch):
    profile_file = tmp_path / "auto_profile_tester_57.json"
    dash = _create_dash(tmp_path, monkeypatch)
    try:
        dash._auto_save_delay_ms = 40
        dash._loaded(_dummy_roster())

        # Check a general in Thảo Phạt, auto-save, then uncheck all and verify [] persists
        tp_items = dash.tp_gen_tree.get_children()
        assert len(tp_items) == 1
        monkeypatch.setattr(dash.tp_gen_tree, "identify_row", lambda _y: tp_items[0])
        dash._on_tp_gen_toggle(MagicMock(y=10))
        _wait_for_auto_save(dash, profile_file)
        assert ProfileStore.load(profile_file).thao_phat.generals == [417506]

        # Uncheck all in Gọi Dân and verify [] persists
        dash._deselect_all_gd_gens()
        _wait_for_auto_save(dash, profile_file)
        assert ProfileStore.load(profile_file).goi_dan.generals == []

        # Toggle NC base and resource city
        dash.bld_bases_tree.selection_set("15237")
        dash._set_selected_base_as_nc()
        dash.bld_bases_tree.identify_row = lambda _y: "15237"
        dash.bld_bases_tree.identify_column = lambda _x: "#2"
        dash._on_bld_bases_click(MagicMock(x=10, y=10))
        _wait_for_auto_save(dash, profile_file)

        loaded = ProfileStore.load(profile_file)
        assert loaded.research.city_id == 15237
        assert 15237 in loaded.resource.resource_cities
    finally:
        dash.destroy()


def test_dashboard_loaded_prunes_stale_cities_and_updates_existing_profile_json(tmp_path, monkeypatch):
    profile_path = tmp_path / "auto_profile_quilia_57.json"
    profile_path.write_text(
        json.dumps(
            {
                "version": 1,
                "building": {
                    "cities": {
                        "10129": {"name": "Cũ", "enabled": False, "resource": False, "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}]},
                        "10229": {"name": "", "enabled": True, "resource": True, "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}]},
                        "10230": {"name": "", "enabled": True, "resource": True, "plans": [{"pid": 1, "gid": 1, "target_level": 20, "enabled": True}]},
                    }
                },
                "research": {"city_id": 10229},
                "resource": {"resource_cities": [10229, 10230]},
                "binh_man": {
                    "current_base_id": 10229,
                    "bases": {
                        "10129": {"name": "Cũ", "enabled": False, "parent_city_id": "10229"},
                        "10229": {"name": "Ma", "enabled": True},
                    },
                },
                "crafting": {
                    "cities": {
                        "10129": {"city_id": 10129, "enabled": False},
                        "10229": {"city_id": 10229, "enabled": True},
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    dash = _create_dash(tmp_path, monkeypatch, username="quilia", server_id=57)
    try:
        dash._active_profile_path = profile_path
        ok, _msg = dash._load_unified_profile(profile_path)
        assert ok

        live_roster = Roster(
            cities=[
                City(id=10129, name="1", type="Thành", pos_x=200, pos_y=96),
                City(id=10254, name="TT", type="Thành", pos_x=180, pos_y=67),
            ],
            camps=[],
        )
        dash._loaded(live_roster)

        assert 10229 not in dash._city_building_plans
        assert 10230 not in dash._city_building_plans
        assert 10229 not in dash._selected_building_cities
        assert 10229 not in dash._selected_resource_cities
        assert 10129 not in dash._selected_building_cities  # giữ đúng enabled=False đã cấu hình
        assert dash._research_city_id == 10129
        assert set(dash.bm_base_configs.keys()) == {10129, 10254}
        assert 10229 not in dash.bm_base_configs
        assert dash.bm_base_configs[10254].enabled is False
        assert set(dash.craft_configs.keys()) == {10129}

        synced = json.loads(profile_path.read_text(encoding="utf-8"))
        assert set(synced["building"]["cities"].keys()) == {"10129", "10254"}
        assert synced["building"]["cities"]["10129"]["name"] == "1"
        assert synced["building"]["cities"]["10254"]["name"] == "TT"
        assert synced["building"]["cities"]["10254"]["enabled"] is False
        assert synced["resource"]["resource_cities"] == []
        assert synced["research"]["city_id"] == 10129
        assert set(synced["binh_man"]["bases"].keys()) == {"10129", "10254"}
        assert "10229" not in synced["binh_man"]["bases"]
        assert list(synced["crafting"]["cities"].keys()) == ["10129"]
    finally:
        dash.destroy()
