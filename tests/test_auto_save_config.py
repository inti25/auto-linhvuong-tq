"""Kiểm thử tính năng Tự động lưu cấu hình (Auto-Save) khi chỉnh sửa trên giao diện Dashboard."""

import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from linhvuong.dashboard import Dashboard
from linhvuong.roster import Army, City, General, Roster

try:
    import _tkinter
except ImportError:
    _tkinter = None


def _dummy_roster() -> Roster:
    c1 = City(id=15230, name="ThanhChinh", type="Thành", pos_x=100, pos_y=200, level=20)
    camp1 = City(id=-1085, name="TienDon", type="Doanh trại", pos_x=110, pos_y=210)
    g1 = General(id=417506, name="TrieuVan", role="vo", level=10, morale=100, stamina=95, stamina_max=100)
    g2 = General(id=417520, name="QuanVu", role="vo", level=11, morale=100, stamina=90, stamina_max=100)
    return Roster(
        cities=[c1],
        camps=[camp1],
        _generals={15230: [g1], -1085: [g2]},
        _armies={417506: Army(100, 200, 300), 417520: Army(500, 0, 0)},
    )


def _create_isolated_dashboard(tmp_path):
    if _tkinter is None:
        pytest.skip("tkinter not available")
    session = MagicMock()
    profile_path = tmp_path / "auto_profile_test_58.json"
    with patch("threading.Thread"):
        try:
            dash = Dashboard(session, 58)
            dash.withdraw()
        except Exception as e:
            pytest.skip(f"Tkinter display error: {e}")
    dash._active_profile_path = profile_path
    dash._auto_save_delay_ms = 30
    dash._auto_save_dirty = False
    dash._cancel_auto_save_timer()
    dash._loaded(_dummy_roster())
    return dash, profile_path


def _pump_until(dash: Dashboard, predicate, timeout_s: float = 1.5) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        dash.update()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_auto_save_triggered_on_var_edit(tmp_path):
    dash, profile_path = _create_isolated_dashboard(tmp_path)
    try:
        assert not profile_path.exists()

        dash.tp_min_morale_var.set("88")
        dash.bm_auto_recruit_var.set(False)
        assert _pump_until(dash, lambda: profile_path.exists())

        saved = json.loads(profile_path.read_text(encoding="utf-8"))
        assert saved["thao_phat"]["min_morale"] == "88"
        assert saved["binh_man"]["auto_recruit"] is False
    finally:
        dash.destroy()


def test_auto_save_triggered_on_treeview_toggle_and_crafting(tmp_path):
    dash, profile_path = _create_isolated_dashboard(tmp_path)
    try:
        # 1. Tick tướng Thảo Phạt trên treeview (col #1)
        items = dash.tp_gen_tree.get_children()
        assert items
        ev = SimpleNamespace(x=10, y=10)
        with patch.object(dash.tp_gen_tree, "identify_row", return_value=items[0]):
            dash._on_tp_gen_toggle(ev)

        assert _pump_until(dash, lambda: profile_path.exists())
        saved = json.loads(profile_path.read_text(encoding="utf-8"))
        assert int(items[0]) in saved["thao_phat"]["generals"]

        # 2. Chỉnh Chế tạo quân giới
        dash.craft_enable_var.set(True)
        dash.craft_amount_var.set("2500")
        assert _pump_until(
            dash,
            lambda: json.loads(profile_path.read_text(encoding="utf-8"))["crafting"]["cities"]["15230"]["amount"]
            == "2500",
        )
        saved2 = json.loads(profile_path.read_text(encoding="utf-8"))
        assert saved2["crafting"]["cities"]["15230"]["enabled"] is True
        assert saved2["crafting"]["cities"]["15230"]["amount"] == "2500"
    finally:
        dash.destroy()


def test_auto_save_suppressed_during_profile_load_and_flushed_on_destroy(tmp_path):
    dash, profile_path = _create_isolated_dashboard(tmp_path)
    external_profile = tmp_path / "external.json"
    external_profile.write_text(
        json.dumps(
            {
                "version": 1,
                "thao_phat": {"min_morale": "77", "interval": "25"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Nạp file ngoài -> không tự động kích hoạt dirty timer
    ok, _msg = dash._load_unified_profile(external_profile)
    assert ok
    assert not dash._auto_save_dirty
    assert not profile_path.exists()

    # Đổi lại đích sang profile_path rồi chỉnh UI nhưng KHÔNG pump loop -> destroy phải flush ngay
    dash._active_profile_path = profile_path
    dash.tp_interval_var.set("42")
    assert dash._auto_save_dirty is True
    dash.destroy()

    assert profile_path.exists()
    flushed = json.loads(profile_path.read_text(encoding="utf-8"))
    assert flushed["thao_phat"]["interval"] == "42"
