"""Phân hệ Chế Tạo Quân Giới Đa Thành (ADR-0031) trên Dashboard."""

import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from ..profile import CityCraftConfig
from ..tasks.crafting import WEAPONS_DATA, WeaponCrafter as _DefaultWeaponCrafter, get_weapon_name
from .shared import CARD, FG, MUTED, MultiSelectDropdown, _LegacyComboAdapter, resolve_dashboard_symbol


class CraftingMixin:
    """Quản lý giao diện, cấu hình đa thành và tiến trình Chế Tạo Quân Giới."""

    def _collect_crafting_profile_dict(self) -> dict:
        if hasattr(self, "_save_current_craft_form_to_config"):
            self._save_current_craft_form_to_config()
        craft_cities = {}
        for cid, cfg in getattr(self, "craft_configs", {}).items():
            wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
            craft_cities[str(cid)] = {
                "city_id": cid,
                "weapon_id": cfg.weapon_id,
                "weapon_ids": list(wids),
                "amount": str(cfg.amount),
                "interval": str(cfg.interval),
                "enabled": bool(cfg.enabled),
            }
        return {"cities": craft_cities}

    def _apply_crafting_profile_dict(self, craft_raw: dict) -> bool:
        raw_cities = craft_raw.get("cities")
        if not isinstance(raw_cities, dict):
            return False
        for cid_str, cinfo in raw_cities.items():
            if isinstance(cinfo, dict):
                try:
                    cid = int(cinfo.get("city_id") or cid_str)
                    self.craft_configs[cid] = CityCraftConfig.from_dict(cinfo)
                except Exception:
                    pass
        if hasattr(self, "_sync_craft_ui_from_current_city"):
            self._sync_craft_ui_from_current_city()
        if hasattr(self, "_refresh_craft_tree"):
            self._refresh_craft_tree()
        return True

    def _build_crafting_panel(self, parent) -> None:
        f_craft = ttk.LabelFrame(parent, text="🛠️ Chế Tạo Quân Giới (Đa Thành)", style="Card.TLabelframe")
        f_craft.grid(row=0, column=1, sticky="nsew", padx=(3, 0))

        craft_ctrl_f = tk.Frame(f_craft, bg=CARD)
        craft_ctrl_f.pack(fill="x", padx=6, pady=4)

        cr_row1 = tk.Frame(craft_ctrl_f, bg=CARD)
        cr_row1.pack(fill="x", pady=(0, 2))

        tk.Label(cr_row1, text="Thành:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 4))
        self.craft_city_combo = ttk.Combobox(cr_row1, state="readonly", width=16)
        self.craft_city_combo.pack(side="left", padx=(0, 6))
        self.craft_city_combo.bind("<<ComboboxSelected>>", self._on_craft_city_selected)

        tk.Label(cr_row1, text="Quân giới:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(4, 4))
        weapon_options = [(wid, f"{wid}. {wname} ({wcat})") for wid, (wname, wcat) in sorted(WEAPONS_DATA.items())]
        weapon_categories = {
            "🗡️ Binh khí": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Binh khí"],
            "🏹 Cung nỗ": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Cung nỗ"],
            "🛡️ Khôi giáp": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Khôi giáp"],
            "🐎 Chiến mã": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Chiến mã"],
            "🚜 Xe ném đá": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Xe ném đá"],
        }
        self.craft_weapon_dropdown = MultiSelectDropdown(
            cr_row1,
            options=weapon_options,
            default_selected=[101],
            width=22,
            categories=weapon_categories,
            command=self._on_craft_weapon_dropdown_changed,
        )
        self.craft_weapon_dropdown.pack(side="left", padx=(0, 6))
        self.craft_weapon_combo = _LegacyComboAdapter(self.craft_weapon_dropdown)

        cr_row2 = tk.Frame(craft_ctrl_f, bg=CARD)
        cr_row2.pack(fill="x", pady=(2, 2))

        tk.Label(cr_row2, text="Số lượng/mẻ:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        self.craft_amount_var = tk.StringVar(value="1000")
        craft_amount_entry = ttk.Entry(cr_row2, textvariable=self.craft_amount_var, width=7)
        craft_amount_entry.pack(side="left", padx=(0, 6))
        craft_amount_entry.bind("<FocusOut>", lambda e: self._save_current_craft_form_to_config())

        tk.Label(cr_row2, text="Chu kỳ (phút):", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        self.craft_interval_var = tk.StringVar(value="5")
        craft_interval_entry = ttk.Entry(cr_row2, textvariable=self.craft_interval_var, width=5)
        craft_interval_entry.pack(side="left", padx=(0, 6))
        craft_interval_entry.bind("<FocusOut>", lambda e: self._save_current_craft_form_to_config())

        self.craft_enable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            cr_row2,
            text="Bật thành này",
            variable=self.craft_enable_var,
            style="TCheckbutton",
            command=self._on_craft_enable_toggled,
        ).pack(side="left", padx=(4, 4))

        cr_row3 = tk.Frame(craft_ctrl_f, bg=CARD)
        cr_row3.pack(fill="x", pady=(2, 0))

        ttk.Button(cr_row3, text="⚡ Chế tạo ngay", style="Action.TButton", command=self._do_craft_now).pack(side="left", padx=(2, 3))

        self.craft_start_btn = ttk.Button(cr_row3, text="▶️ Bắt đầu", style="Success.TButton", command=self._toggle_craft_running)
        self.craft_start_btn.pack(side="left", padx=3)

        self.craft_status_lbl = tk.Label(cr_row3, text="", bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self.craft_status_lbl.pack(side="left", padx=(6, 4))

        craft_table_frame = tk.Frame(f_craft, bg=CARD)
        craft_table_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        craft_columns = ("sel", "city", "weapon", "amount", "interval", "status")
        self.craft_tree = ttk.Treeview(craft_table_frame, columns=craft_columns, show="headings", selectmode="browse")

        self.craft_tree.heading("sel", text="Bật")
        self.craft_tree.heading("city", text="Thành trì")
        self.craft_tree.heading("weapon", text="Quân Giới")
        self.craft_tree.heading("amount", text="Số lượng")
        self.craft_tree.heading("interval", text="Chu kỳ (phút)")
        self.craft_tree.heading("status", text="Trạng thái")

        self.craft_tree.column("sel", width=40, anchor="center")
        self.craft_tree.column("city", width=110, anchor="w")
        self.craft_tree.column("weapon", width=150, anchor="w")
        self.craft_tree.column("amount", width=75, anchor="e")
        self.craft_tree.column("interval", width=80, anchor="center")
        self.craft_tree.column("status", width=140, anchor="w")

        craft_scroll = ttk.Scrollbar(craft_table_frame, orient="vertical", command=self.craft_tree.yview)
        self.craft_tree.configure(yscrollcommand=craft_scroll.set)
        craft_scroll.pack(side="right", fill="y")
        self.craft_tree.pack(side="left", fill="both", expand=True)

        self.craft_tree.bind("<ButtonRelease-1>", self._on_craft_tree_click)
        self.craft_tree.bind("<<TreeviewSelect>>", self._on_craft_tree_select)

    def _get_current_craft_city_id(self) -> Optional[int]:
        if not hasattr(self, "craft_city_combo"):
            return None
        sel_idx = self.craft_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        if 0 <= sel_idx < len(cities):
            return cities[sel_idx].id
        return None

    def _sync_craft_ui_from_current_city(self):
        cid = self._get_current_craft_city_id()
        if not cid:
            return
        if cid not in self.craft_configs:
            self.craft_configs[cid] = CityCraftConfig(city_id=cid, weapon_id=101, weapon_ids=[101], amount="1000", interval="5", enabled=False)
        cfg = self.craft_configs[cid]
        with self._suppress_auto_save():
            self.craft_amount_var.set(str(cfg.amount))
            self.craft_interval_var.set(str(cfg.interval))
            self.craft_enable_var.set(bool(cfg.enabled))

            wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
            if hasattr(self, "craft_weapon_dropdown"):
                self.craft_weapon_dropdown.set_selected(wids)

    def _save_current_craft_form_to_config(self):
        cid = self._get_current_craft_city_id()
        if not cid:
            return
        if hasattr(self, "craft_weapon_dropdown"):
            wids = self.craft_weapon_dropdown.get_selected()
        elif hasattr(self, "craft_weapon_combo"):
            w_val = self.craft_weapon_combo.get()
            try:
                wid = int(w_val.split(".")[0])
            except (ValueError, IndexError):
                wid = 101
            wids = [wid]
        else:
            wids = [101]

        if not wids:
            wids = [101]

        amount = self.craft_amount_var.get() if hasattr(self, "craft_amount_var") else "1000"
        interval = self.craft_interval_var.get() if hasattr(self, "craft_interval_var") else "5"
        enabled = self.craft_enable_var.get() if hasattr(self, "craft_enable_var") else False

        self.craft_configs[cid] = CityCraftConfig(
            city_id=cid,
            weapon_id=wids[0],
            weapon_ids=wids,
            amount=str(amount),
            interval=str(interval),
            enabled=bool(enabled),
        )
        self._refresh_craft_tree()

    def _on_craft_city_selected(self, _event=None):
        self._sync_craft_ui_from_current_city()

    def _on_craft_weapon_dropdown_changed(self, _selected_ids=None):
        self._save_current_craft_form_to_config()
        self._schedule_auto_save()

    def _on_craft_weapon_selected(self, _event=None):
        self._save_current_craft_form_to_config()
        self._schedule_auto_save()

    def _on_craft_enable_toggled(self):
        self._save_current_craft_form_to_config()
        self._schedule_auto_save()

    def _refresh_craft_tree(self):
        if not hasattr(self, "craft_tree"):
            return
        cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        for c in cities:
            cid_str = str(c.id)
            cfg = self.craft_configs.get(c.id, CityCraftConfig(city_id=c.id, enabled=False))
            check = "☑" if cfg.enabled else "☐"
            wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
            if len(wids) == 1:
                w_display = f"{wids[0]}. {get_weapon_name(wids[0])}"
            elif len(wids) > 1:
                first_name = get_weapon_name(wids[0])
                w_display = f"{len(wids)} loại ({first_name}, ...)"
            else:
                w_display = "Chưa chọn"
            status = self._craft_statuses.get(c.id, "Sẵn sàng" if cfg.enabled else "Chưa kích hoạt")
            vals = (check, f"{c.name} ({c.id})", w_display, cfg.amount, cfg.interval, status)

            if self.craft_tree.exists(cid_str):
                self.craft_tree.item(cid_str, values=vals)
            else:
                self.craft_tree.insert("", "end", iid=cid_str, values=vals)

    def _on_craft_tree_click(self, event):
        region = self.craft_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.craft_tree.identify_column(event.x)
        row_id = self.craft_tree.identify_row(event.y)
        if not row_id:
            return
        try:
            cid = int(row_id)
        except ValueError:
            return

        if col == "#1":
            cfg = self.craft_configs.get(cid, CityCraftConfig(city_id=cid, enabled=False))
            cfg.enabled = not cfg.enabled
            self.craft_configs[cid] = cfg
            if cid == self._get_current_craft_city_id():
                with self._suppress_auto_save():
                    self.craft_enable_var.set(cfg.enabled)
            self._refresh_craft_tree()
            self._schedule_auto_save()
        else:
            self._select_craft_city_by_id(cid)

    def _on_craft_tree_select(self, _event=None):
        sel = self.craft_tree.selection()
        if not sel:
            return
        try:
            cid = int(sel[0])
            self._select_craft_city_by_id(cid)
        except ValueError:
            pass

    def _select_craft_city_by_id(self, target_cid: int):
        if not hasattr(self, "craft_city_combo"):
            return
        cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        for idx, c in enumerate(cities):
            if c.id == target_cid:
                self.craft_city_combo.current(idx)
                self._sync_craft_ui_from_current_city()
                break

    def _do_craft_now(self):
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        crafter_cls = resolve_dashboard_symbol("WeaponCrafter", _DefaultWeaponCrafter)
        self._save_current_craft_form_to_config()
        cid = self._get_current_craft_city_id()
        if not cid:
            mb.showwarning("Cảnh báo", "Vui lòng chọn thành trì cần chế tạo quân giới!")
            return
        cfg = self.craft_configs.get(cid)
        if not cfg:
            return

        wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
        if not wids:
            mb.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 loại quân giới để chế tạo!")
            return

        amount = int(cfg.amount) if str(cfg.amount).isdigit() else 1000
        names = [get_weapon_name(wid) for wid in wids]
        names_str = ", ".join(names[:2]) + (f" (+{len(names)-2})" if len(names) > 2 else "")

        self.craft_status_lbl.config(text=f"Đang gửi lệnh chế tạo {amount}x [{names_str}]...")

        def _worker():
            crafter = crafter_cls(self.gateway)
            success_count = 0
            err_msg = ""
            for wid in wids:
                success, ret, msg = crafter.craft_once(
                    cid,
                    wid,
                    amount,
                    notify=lambda m: self._log_global(m),
                )
                if success:
                    success_count += 1
                else:
                    err_msg = msg
                    if ret == 32:
                        break

            def _update_ui():
                if success_count == len(wids):
                    res_txt = f"Hoàn thành {success_count}/{len(wids)} loại ({time.strftime('%H:%M:%S')})"
                else:
                    res_txt = f"Chế tạo {success_count}/{len(wids)} loại. {err_msg}"
                self.craft_status_lbl.config(text=res_txt)
                self._craft_statuses[cid] = f"OK {success_count}/{len(wids)} ({time.strftime('%H:%M:%S')})" if success_count > 0 else (err_msg or "Lỗi")
                self._refresh_craft_tree()

            try:
                self.after(0, _update_ui)
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_craft_running(self):
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        if not self._craft_running:
            self._save_current_craft_form_to_config()
            enabled_count = sum(1 for cfg in self.craft_configs.values() if cfg.enabled)
            if enabled_count == 0:
                mb.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 thành cần chế tạo quân giới!")
                return
            self._craft_running = True
            self._craft_stop_event.clear()
            self.craft_start_btn.configure(text="⏹️ Dừng", style="Danger.TButton")
            self.craft_status_lbl.config(text=f"Đang chạy chế tạo tự động cho {enabled_count} thành...")
            self._craft_thread = threading.Thread(target=self._craft_worker_loop, daemon=True)
            self._craft_thread.start()
        else:
            self._craft_running = False
            self._craft_stop_event.set()
            self.craft_start_btn.configure(text="▶️ Bắt đầu", style="Success.TButton")
            self.craft_status_lbl.config(text="Đã dừng chế tạo tự động.")

    def _craft_worker_loop(self):
        crafter_cls = resolve_dashboard_symbol("WeaponCrafter", _DefaultWeaponCrafter)
        crafter = crafter_cls(self.gateway, workshop_cache_ttl=300.0)
        while self._craft_running and not self._craft_stop_event.is_set():
            now = time.time()
            for cid, cfg in list(self.craft_configs.items()):
                if self._craft_stop_event.is_set():
                    break
                if not cfg.enabled:
                    continue
                last = self._craft_last_run.get(cid, 0)
                try:
                    interval_sec = float(cfg.interval) * 60.0
                except (ValueError, TypeError):
                    interval_sec = 300.0
                if now - last >= interval_sec:
                    amount = int(cfg.amount) if str(cfg.amount).isdigit() else 1000
                    wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
                    if not wids:
                        continue

                    def _set_pending(city_id=cid, count=len(wids)):
                        self._craft_statuses[city_id] = f"Đang chế tạo {count} loại quân giới..."
                        self._refresh_craft_tree()
                    try:
                        self.after(0, _set_pending)
                    except (RuntimeError, tk.TclError):
                        pass

                    succ_cnt = 0
                    last_ret = 0
                    for idx, wid in enumerate(wids):
                        if self._craft_stop_event.is_set():
                            break
                        succ, ret, msg = crafter.craft_once(
                            cid,
                            wid,
                            amount,
                            notify=lambda m: self._log_global(m),
                            switch_city=(idx == 0),
                        )
                        last_ret = ret
                        if succ:
                            succ_cnt += 1
                        elif ret == 32:
                            break

                    self._craft_last_run[cid] = time.time()
                    if succ_cnt == len(wids):
                        res_status = f"OK {succ_cnt}/{len(wids)} ({time.strftime('%H:%M:%S')})"
                    elif succ_cnt > 0:
                        res_status = f"Một phần ({succ_cnt}/{len(wids)})"
                    else:
                        res_status = f"Thất bại (ret={last_ret})"

                    def _set_done(city_id=cid, status_str=res_status):
                        self._craft_statuses[city_id] = status_str
                        self._refresh_craft_tree()
                    try:
                        self.after(0, _set_done)
                    except (RuntimeError, tk.TclError):
                        pass

            self._craft_stop_event.wait(1.0)
