"""Đồng bộ Hồ Sơ Cấu Hình Tổng Hợp & Tự Động Lưu (Auto-Save) khi chỉnh UI."""

from contextlib import contextmanager
import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog as _default_filedialog, messagebox as _default_messagebox
from typing import Optional

from ..notifications import NotificationConfig
from ..profile import Profile, ProfileStore
from .shared import resolve_dashboard_symbol

logger = logging.getLogger("linhvuong.dashboard")


class ProfileSyncMixin:
    """Điều phối thu thập, nạp, lưu tay và tự động lưu cấu hình Dashboard."""

    @contextmanager
    def _suppress_auto_save(self):
        self._auto_save_suppress_depth = getattr(self, "_auto_save_suppress_depth", 0) + 1
        try:
            yield
        finally:
            self._auto_save_suppress_depth = max(0, getattr(self, "_auto_save_suppress_depth", 1) - 1)

    def _cancel_auto_save_timer(self):
        after_id = getattr(self, "_auto_save_after_id", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
            self._auto_save_after_id = None

    def _resolve_active_profile_target(self) -> Path:
        from ..paths import get_data_dir

        active = getattr(self, "_active_profile_path", None)
        if active is not None:
            return Path(active)
        def_name = getattr(self, "default_profile_name", "auto_profile.json")
        if hasattr(self, "profile_path_var"):
            val = (self.profile_path_var.get() or "").strip()
            if val:
                p = Path(val)
                return p if p.is_absolute() or p.parent != Path(".") else get_data_dir() / p
        p_def = Path(def_name)
        return p_def if p_def.is_absolute() or p_def.parent != Path(".") else get_data_dir() / p_def

    def _schedule_auto_save(self, *_args):
        if not getattr(self, "_auto_save_enabled", False):
            return
        if getattr(self, "_auto_save_suppress_depth", 0) > 0:
            return
        if getattr(self, "_closing", False) or getattr(self, "_destroyed", False):
            return
        self._auto_save_dirty = True
        self._cancel_auto_save_timer()
        delay_ms = int(getattr(self, "_auto_save_delay_ms", 400))
        try:
            self._auto_save_after_id = self.after(delay_ms, self._flush_auto_save)
        except (RuntimeError, tk.TclError):
            self._auto_save_after_id = None

    def _flush_auto_save(self):
        self._auto_save_after_id = None
        if not getattr(self, "_auto_save_enabled", False):
            return
        if not getattr(self, "_auto_save_dirty", False):
            return
        if getattr(self, "_auto_save_suppress_depth", 0) > 0:
            return
        try:
            self._save_unified_profile(self._resolve_active_profile_target())
        except Exception as exc:
            logger.debug(f"Auto-save hồ sơ cấu hình thất bại: {exc}")

    def _on_craft_form_var_changed(self, *_args):
        if getattr(self, "_auto_save_suppress_depth", 0) > 0:
            return
        if hasattr(self, "_save_current_craft_form_to_config"):
            self._save_current_craft_form_to_config()
        if hasattr(self, "_refresh_craft_tree"):
            self._refresh_craft_tree()
        self._schedule_auto_save()

    def _bind_auto_save_hooks(self):
        if getattr(self, "_auto_save_hooks_bound", False):
            return
        self._auto_save_hooks_bound = True

        # Các tk.Variable đại diện cho cấu hình được lưu trong hồ sơ tổng hợp
        persisted_vars = (
            # Building & Resource
            "bld_speedup_var",
            "bld_speedup_hours_var",
            "bld_open_box_var",
            "bld_box_max_var",
            "bld_box_fallback_var",
            "bld_interval_var",
            "res_gold_thresh_var",
            "res_wood_pct_var",
            "res_iron_pct_var",
            "res_stone_pct_var",
            "res_food_pct_var",
            # Research
            "res_art_var",
            "res_even_var",
            "res_interval_var",
            # Auxiliary & Logistics & DiTrai
            "aux_daily_reward_var",
            "aux_comfort_var",
            "aux_boost_var",
            "aux_tribute_var",
            "aux_explore_var",
            "aux_explore_whip_var",
            "aux_explore_coin_var",
            "aux_explore_turns_var",
            "log_amount_var",
            "dt_dest_x_var",
            "dt_dest_y_var",
            # Thao Phat
            "tp_target_inf_var",
            "tp_target_cav_var",
            "tp_target_arc_var",
            "tp_auto_recruit_var",
            "tp_auto_morale_var",
            "tp_min_morale_var",
            "tp_interval_var",
            # Goi Dan
            "gd_radius_var",
            "gd_recover_var",
            "gd_interval_var",
            "gd_target_inf_var",
            "gd_target_cav_var",
            "gd_target_arc_var",
            "gd_auto_recruit_var",
            "gd_auto_morale_var",
            "gd_min_morale_var",
            "gd_action_mode_var",
            # Binh Man
            "bm_mode_var",
            "bm_radius_var",
            "bm_min_army_var",
            "bm_min_hp_var",
            "bm_comfort_var",
            "bm_interval_var",
            "bm_camp_id_var",
            "bm_threshold_var",
            "bm_mantypes_var",
            "bm_target_inf_var",
            "bm_target_cav_var",
            "bm_target_arc_var",
            "bm_auto_recruit_var",
            "bm_auto_morale_var",
            "bm_min_morale_var",
            "bm_action_mode_var",
            # Combat
            "bt_auto_counter_var",
            "bt_window_var",
            "bt_action_mode_var",
            "bt_skip_confused_var",
            "bt_leave_boss_var",
            "bt_cleanse_var",
            "bt_retreat_var",
            "bt_auto_capture_boss_var",
            "bt_capture_morale_var",
            # Nien Thu
            "nt_target_inf_var",
            "nt_target_cav_var",
            "nt_target_arc_var",
            "nt_auto_recruit_var",
            "nt_auto_morale_var",
            "nt_min_morale_var",
            "nt_speedup_march_var",
            "nt_speedup_return_var",
            "nt_stop_jade_var",
            "nt_use_world_chat_var",
            "nt_run_immediately_var",
        )
        seen_ids: set[int] = set()
        for attr in persisted_vars:
            var = getattr(self, attr, None)
            if var is not None and hasattr(var, "trace_add") and id(var) not in seen_ids:
                seen_ids.add(id(var))
                var.trace_add("write", self._schedule_auto_save)

        # Form Chế Tạo Quân Giới: cần đồng bộ ngược vào craft_configs trước khi lưu
        for attr in ("craft_enable_var", "craft_amount_var", "craft_interval_var"):
            var = getattr(self, attr, None)
            if var is not None and hasattr(var, "trace_add") and id(var) not in seen_ids:
                seen_ids.add(id(var))
                var.trace_add("write", self._on_craft_form_var_changed)

        # Combobox lưu trong hồ sơ tổng hợp (add="+" để giữ nguyên handler gốc)
        persisted_combos = (
            "bld_slots_combo",
            "bld_speedup_item_combo",
            "res_gold_box_combo",
            "res_tn_box_combo",
            "tp_city_combo",
            "tp_mission_combo",
            "gd_city_combo",
            "gd_mode_combo",
            "gd_action_mode_combo",
            "bm_action_mode_combo",
            "log_army_combo",
            "bt_action_mode_combo",
            "bt_stratagem_combo",
            "nt_city_combo",
        )
        for attr in persisted_combos:
            combo = getattr(self, attr, None)
            if combo is not None and hasattr(combo, "bind"):
                try:
                    combo.bind("<<ComboboxSelected>>", self._schedule_auto_save, add="+")
                except Exception:
                    pass

    def _collect_unified_profile(self) -> dict:
        return {
            "version": 1,
            "building": self._collect_building_profile_dict(),
            "research": self._collect_research_profile_dict(),
            "resource": self._collect_resource_profile_dict(),
            "thao_phat": self._collect_thao_phat_profile_dict(),
            "goi_dan": self._collect_goi_dan_profile_dict(),
            "binh_man": self._collect_binh_man_profile_dict(),
            "logistics": self._collect_logistics_profile_dict(),
            "ditrai": self._collect_ditrai_profile_dict(),
            "combat": self._collect_combat_profile_dict(),
            "notifications": self.notification_config.to_dict() if hasattr(self, "notification_config") else {},
            "nien_thu": self._collect_nien_thu_profile_dict(),
            "crafting": self._collect_crafting_profile_dict(),
        }

    def _apply_unified_profile(self, data: dict) -> list[str]:
        loaded_sections: list[str] = []
        with self._suppress_auto_save():
            # 1. Xây Dựng
            bld_label = self._apply_building_profile_dict(data)
            if bld_label:
                loaded_sections.append(bld_label)

            # 2. Nghiên cứu Đại Học
            res_label = self._apply_research_profile_dict(data)
            if res_label:
                loaded_sections.append(res_label)

            # 2b. Tài Nguyên
            if "resource" in data and isinstance(data["resource"], dict):
                loaded_sections.append(self._apply_resource_profile_dict(data["resource"]))

            # 3. Thảo Phạt
            if "thao_phat" in data and isinstance(data["thao_phat"], dict):
                self._apply_thao_phat_profile_dict(data["thao_phat"])
                loaded_sections.append("Thảo Phạt")

            # 4. Gọi Man
            gd_raw = data.get("goi_dan") or data.get("goi_man")
            if gd_raw and isinstance(gd_raw, dict):
                self._apply_goi_dan_profile_dict(gd_raw)
                loaded_sections.append("Gọi Man")

            # 5. Bình Man
            if "binh_man" in data and isinstance(data["binh_man"], dict):
                self._apply_binh_man_profile_dict(data["binh_man"])
                loaded_sections.append("Bình Man")

            # 6. Hậu Cần
            if "logistics" in data and isinstance(data["logistics"], dict):
                loaded_sections.append(self._apply_logistics_profile_dict(data["logistics"]))

            # 7. Dịch Trại
            if "ditrai" in data and isinstance(data["ditrai"], dict):
                self._apply_ditrai_profile_dict(data["ditrai"])
                loaded_sections.append("Dịch Trại")

            # 8. Chiến Trường & Mưu Lược
            if "combat" in data and isinstance(data["combat"], dict):
                self._apply_combat_profile_dict(data["combat"])
                loaded_sections.append("Chiến Trường")

            # 9. Chế Tạo Quân Giới (ADR-0031)
            craft_raw = data.get("crafting") or data.get("weapon_crafting")
            if craft_raw and isinstance(craft_raw, dict):
                if self._apply_crafting_profile_dict(craft_raw):
                    loaded_sections.append("Chế Tạo Quân Giới")

            # 10. Thông Báo Đa Kênh (ADR-0036)
            if "notifications" in data and isinstance(data["notifications"], dict):
                if hasattr(self, "notification_config"):
                    self.notification_config = NotificationConfig.from_dict(data["notifications"])
                loaded_sections.append("Thông Báo")

            # 11. Sự Kiện Niên Thú
            if "nien_thu" in data and isinstance(data["nien_thu"], dict):
                self._apply_nien_thu_profile_dict(data["nien_thu"])
                loaded_sections.append("Niên Thú")

        return loaded_sections

    def _sync_state_with_roster(self, roster) -> bool:
        """Đồng bộ bộ nhớ UI với danh sách Căn Cứ thực tế từ máy chủ (ADR-0042).

        Chỉ thanh lọc khi `roster.bases` khác rỗng; trả về True nếu phát hiện
        căn cứ bị xóa, thêm mới hoặc đổi tên so với hồ sơ đã nạp.
        """
        if not roster or not getattr(roster, "bases", None):
            return False

        valid_base_ids = {b.id for b in roster.bases}
        valid_city_ids = {b.id for b in roster.bases if not b.is_camp}
        base_name_map = {b.id: b.name for b in roster.bases}
        first_base_id = roster.bases[0].id
        first_city_id = next((b.id for b in roster.bases if not b.is_camp), None)

        changed = False

        loaded_names: Optional[dict[int, str]] = getattr(self, "_loaded_profile_city_names", None)
        if loaded_names is not None:
            if any(cid not in valid_base_ids for cid in loaded_names):
                changed = True
            for b in roster.bases:
                if b.id not in loaded_names or loaded_names[b.id] != b.name:
                    changed = True

        # 1. Xây Dựng & Tài Nguyên
        if hasattr(self, "_city_building_plans"):
            stale_bld = [cid for cid in self._city_building_plans if cid not in valid_base_ids]
            for cid in stale_bld:
                self._city_building_plans.pop(cid, None)
                changed = True

        if hasattr(self, "_selected_building_cities"):
            stale_sel = self._selected_building_cities - valid_base_ids
            if stale_sel:
                self._selected_building_cities -= stale_sel
                changed = True

        if hasattr(self, "_selected_resource_cities"):
            stale_res = self._selected_resource_cities - valid_base_ids
            if stale_res:
                self._selected_resource_cities -= stale_res
                changed = True

        if getattr(self, "_current_bld_city_id", None) is not None and self._current_bld_city_id not in valid_base_ids:
            self._current_bld_city_id = first_base_id
            if hasattr(self, "_render_bld_tree_from_plans"):
                self._render_bld_tree_from_plans(self._city_building_plans.get(first_base_id, []))

        # 2. Nghiên Cứu (chỉ Thành)
        if getattr(self, "_research_city_id", None) is not None and self._research_city_id not in valid_city_ids:
            self._research_city_id = first_city_id
            changed = True

        # 3. Bình Man (cả Thành và Doanh trại)
        if hasattr(self, "bm_base_configs") and isinstance(self.bm_base_configs, dict):
            stale_bm = [bid for bid in self.bm_base_configs if bid not in valid_base_ids]
            for bid in stale_bm:
                self.bm_base_configs.pop(bid, None)
                changed = True
            for bid, bcfg in self.bm_base_configs.items():
                bname = base_name_map.get(bid, "")
                if bname and bcfg.name != bname:
                    bcfg.name = bname
                    changed = True
                if bcfg.parent_city_id:
                    try:
                        pcid = int(str(bcfg.parent_city_id).strip())
                    except ValueError:
                        pcid = None
                    if pcid is None or pcid not in valid_city_ids:
                        bcfg.parent_city_id = str(first_city_id) if first_city_id is not None else ""
                        changed = True
                if bcfg.camp_id:
                    try:
                        camp_id = int(str(bcfg.camp_id).strip())
                    except ValueError:
                        camp_id = None
                    if camp_id is None or camp_id not in valid_base_ids:
                        bcfg.camp_id = ""
                        changed = True

        if getattr(self, "_current_bm_base_id", None) is not None and self._current_bm_base_id not in valid_base_ids:
            self._current_bm_base_id = first_base_id
            changed = True

        # 4. Chế Tạo Quân Giới (chỉ Thành)
        if hasattr(self, "craft_configs") and isinstance(self.craft_configs, dict):
            stale_craft = [cid for cid in self.craft_configs if cid not in valid_city_ids]
            for cid in stale_craft:
                self.craft_configs.pop(cid, None)
                changed = True

        # 5. Tham chiếu chờ của Thảo Phạt / Niên Thú
        if getattr(self, "_pending_tp_city_id", None) is not None and self._pending_tp_city_id not in valid_base_ids:
            self._pending_tp_city_id = first_city_id if first_city_id is not None else first_base_id
            changed = True
        if getattr(self, "_pending_nt_city_id", None) is not None and self._pending_nt_city_id not in valid_city_ids:
            self._pending_nt_city_id = first_city_id
            changed = True

        self._loaded_profile_city_names = dict(base_name_map)
        return changed

    def _save_unified_profile(self, filepath: Optional[Path] = None) -> Path:
        target = Path(filepath) if filepath is not None else self._resolve_active_profile_target()
        profile_dict = self._collect_unified_profile()
        prof = Profile.from_dict(profile_dict)
        target = ProfileStore.save(prof, target)
        self._active_profile_path = target
        self._auto_save_dirty = False
        self._cancel_auto_save_timer()
        if hasattr(self, "profile_path_var"):
            self.profile_path_var.set(target.name)
        return target

    def _load_unified_profile(self, filepath: Optional[Path] = None) -> tuple[bool, str]:
        target = Path(filepath) if filepath is not None else self._resolve_active_profile_target()
        if not target.exists():
            return False, f"Không tìm thấy file: {target.name}"
        try:
            prof = ProfileStore.load(target)
            with self._suppress_auto_save():
                sections = self._apply_unified_profile(prof.to_dict())
                if getattr(self, "roster", None) and getattr(self.roster, "bases", None):
                    if self._sync_state_with_roster(self.roster):
                        if hasattr(self, "bld_bases_tree"):
                            for iid in self.bld_bases_tree.get_children(""):
                                vals = list(self.bld_bases_tree.item(iid, "values"))
                                if len(vals) > 2:
                                    try:
                                        cid_int = int(iid)
                                        vals[0] = "☑" if cid_int in self._selected_building_cities else "☐"
                                        vals[1] = "☑" if cid_int in self._selected_resource_cities else "☐"
                                        vals[2] = "★" if self._research_city_id == cid_int else "☐"
                                        self.bld_bases_tree.item(iid, values=vals)
                                    except ValueError:
                                        pass
                        if hasattr(self, "_refresh_bm_bases_tree"):
                            self._refresh_bm_bases_tree()
                        if hasattr(self, "_refresh_craft_tree"):
                            self._refresh_craft_tree()
                if hasattr(self, "profile_path_var"):
                    self.profile_path_var.set(target.name)
            self._active_profile_path = target
            self._auto_save_dirty = False
            self._cancel_auto_save_timer()
            return True, f"Đã nạp thành công các phân hệ: {', '.join(sections)}"
        except Exception as e:
            return False, f"Lỗi đọc file cấu hình: {e}"

    def _save_unified_profile_dialog(self):
        filedialog = resolve_dashboard_symbol("filedialog", _default_filedialog)
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        cur_name = self.profile_path_var.get() if hasattr(self, "profile_path_var") else "auto_profile.json"
        fpath = filedialog.asksaveasfilename(
            title="Lưu Hồ Sơ Cấu Hình Tổng",
            defaultextension=".json",
            initialfile=cur_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if fpath:
            p = self._save_unified_profile(Path(fpath))
            messagebox.showinfo("Thành công", f"Đã lưu hồ sơ cấu hình tổng vào:\n{p.name}")

    def _load_unified_profile_dialog(self):
        filedialog = resolve_dashboard_symbol("filedialog", _default_filedialog)
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fpath = filedialog.askopenfilename(
            title="Nạp Hồ Sơ Cấu Hình Tổng",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if fpath:
            ok, msg = self._load_unified_profile(Path(fpath))
            if ok:
                messagebox.showinfo("Thành công", msg)
            else:
                messagebox.showerror("Lỗi", msg)
