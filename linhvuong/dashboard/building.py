"""Phân hệ Quản lý Xây Dựng Công Trình Đa Thành trên Dashboard."""

import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..tasks.building import BUILDING_NAMES, CHEST_MAPPING, BuildingPlan, BuildingTask as _DefaultBuildingTask
from .runners import BuildingAutoRunner as _DefaultBuildingAutoRunner
from .shared import BG, CARD, FG, MUTED, resolve_dashboard_symbol


class BuildingMixin:
    """Quản lý giao diện Tab Nội Chính & Hàng Đợi Xây Dựng đa thành."""

    def _collect_building_profile_dict(self) -> dict:
        self._save_current_bld_tree_to_cache()
        cities_cfg = {}
        if self.roster and self.roster.bases:
            ordered_cids = [b.id for b in self.roster.bases]
        else:
            all_cids = (
                set(self._city_building_plans.keys())
                | self._selected_building_cities
                | self._selected_resource_cities
            )
            if self._research_city_id:
                all_cids.add(self._research_city_id)
            ordered_cids = sorted(all_cids)

        for cid in ordered_cids:
            plans = self._city_building_plans.get(cid, [])
            base_name = ""
            if self.roster:
                b = self.roster.base_by_id(cid)
                if b:
                    base_name = b.name
            if not base_name and hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(cid)):
                base_name = self.bld_bases_tree.item(str(cid), "text")
            cities_cfg[str(cid)] = {
                "name": base_name,
                "enabled": cid in self._selected_building_cities,
                "resource": cid in self._selected_resource_cities,
                "plans": plans,
            }

        return {
            "slots": (
                int(self.bld_slots_combo.get())
                if hasattr(self, "bld_slots_combo") and self.bld_slots_combo.get()
                else 3
            ),
            "auto_speedup": bool(self.bld_speedup_var.get()) if hasattr(self, "bld_speedup_var") else False,
            "speedup_item": self.bld_speedup_item_combo.get() if hasattr(self, "bld_speedup_item_combo") else "Ngân Bảo",
            "speedup_hours": self.bld_speedup_hours_var.get() if hasattr(self, "bld_speedup_hours_var") else "1",
            "auto_boost": bool(self.bld_boost_var.get()) if hasattr(self, "bld_boost_var") else True,
            "auto_comfort": bool(self.bld_comfort_var.get()) if hasattr(self, "bld_comfort_var") else True,
            "auto_open_box": bool(self.bld_open_box_var.get()) if hasattr(self, "bld_open_box_var") else False,
            "box_type_idx": self.bld_box_combo.current() if hasattr(self, "bld_box_combo") else 0,
            "box_max": self.bld_box_max_var.get() if hasattr(self, "bld_box_max_var") else "5",
            "auto_fallback_box": bool(self.bld_box_fallback_var.get()) if hasattr(self, "bld_box_fallback_var") else True,
            "interval": self.bld_interval_var.get() if hasattr(self, "bld_interval_var") else "20",
            "plans": self._collect_bld_plans_from_tree() if hasattr(self, "bld_tree") else [],
            "cities": cities_cfg,
        }

    def _apply_building_profile_dict(self, data: dict) -> Optional[str]:
        plans_list = None
        cities_data = None
        if "plans" in data and isinstance(data["plans"], list):
            plans_list = data["plans"]
        elif "building" in data and isinstance(data["building"], dict):
            bld_data = data["building"]
            if hasattr(self, "bld_slots_combo") and "slots" in bld_data:
                self.bld_slots_combo.set(str(bld_data["slots"]))
            if hasattr(self, "bld_speedup_var") and "auto_speedup" in bld_data:
                self.bld_speedup_var.set(bool(bld_data["auto_speedup"]))
            if hasattr(self, "bld_speedup_item_combo") and "speedup_item" in bld_data:
                val = str(bld_data["speedup_item"])
                if val in ("Ngân Bảo", "Coin", "Lệnh Bài"):
                    self.bld_speedup_item_combo.set(val)
            elif hasattr(self, "bld_speedup_item_combo") and "speedup_paytype" in bld_data:
                try:
                    pt = int(bld_data["speedup_paytype"])
                    self.bld_speedup_item_combo.set("Coin" if pt == 1 else "Ngân Bảo")
                except (ValueError, TypeError):
                    pass
            if hasattr(self, "bld_speedup_hours_var") and "speedup_hours" in bld_data:
                self.bld_speedup_hours_var.set(str(bld_data["speedup_hours"]))
            if hasattr(self, "bld_boost_var") and "auto_boost" in bld_data:
                self.bld_boost_var.set(bool(bld_data["auto_boost"]))
            if hasattr(self, "bld_comfort_var") and "auto_comfort" in bld_data:
                self.bld_comfort_var.set(bool(bld_data["auto_comfort"]))
            if hasattr(self, "bld_even_var") and "even_upgrade" in bld_data:
                self.bld_even_var.set(bool(bld_data["even_upgrade"]))
            if hasattr(self, "bld_open_box_var") and "auto_open_box" in bld_data:
                self.bld_open_box_var.set(bool(bld_data["auto_open_box"]))
            if hasattr(self, "bld_box_combo") and "box_type_idx" in bld_data:
                try:
                    idx = int(bld_data["box_type_idx"])
                    if 0 <= idx < len(self.bld_box_combo["values"]):
                        self.bld_box_combo.current(idx)
                except (ValueError, IndexError):
                    pass
            if hasattr(self, "bld_box_max_var") and "box_max" in bld_data:
                self.bld_box_max_var.set(str(bld_data["box_max"]))
            if hasattr(self, "bld_box_fallback_var") and "auto_fallback_box" in bld_data:
                self.bld_box_fallback_var.set(bool(bld_data["auto_fallback_box"]))
            if hasattr(self, "bld_interval_var") and "interval" in bld_data:
                self.bld_interval_var.set(str(bld_data["interval"]))
            plans_list = bld_data.get("plans")
            cities_data = bld_data.get("cities")

        if cities_data and isinstance(cities_data, dict):
            self._loaded_profile_city_names = {}
            for cid_str, cinfo in cities_data.items():
                try:
                    cid = int(cid_str)
                except ValueError:
                    continue
                if isinstance(cinfo, dict):
                    self._loaded_profile_city_names[cid] = str(cinfo.get("name", ""))
                c_plans = cinfo.get("plans", [])
                self._city_building_plans[cid] = c_plans
                if cinfo.get("enabled", True):
                    self._selected_building_cities.add(cid)
                else:
                    self._selected_building_cities.discard(cid)
                if cinfo.get("resource", False):
                    self._selected_resource_cities.add(cid)
                elif "resource" in cinfo:
                    self._selected_resource_cities.discard(cid)
                if hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(cid)):
                    sym = "☑" if cid in self._selected_building_cities else "☐"
                    sym_res = "☑" if cid in self._selected_resource_cities else "☐"
                    vals = list(self.bld_bases_tree.item(str(cid), "values"))
                    if vals:
                        vals[0] = sym
                        if len(vals) > 1:
                            vals[1] = sym_res
                        self.bld_bases_tree.item(str(cid), values=vals)

            cur_id = self._current_bld_city_id
            if cur_id is None and self._selected_building_cities:
                cur_id = next(iter(self._selected_building_cities))
                self._current_bld_city_id = cur_id
            if cur_id and cur_id in self._city_building_plans:
                self._render_bld_tree_from_plans(self._city_building_plans[cur_id])
            elif plans_list and hasattr(self, "bld_tree"):
                self._render_bld_tree_from_plans(plans_list)

            if hasattr(self, "_append_bld_log"):
                self._append_bld_log(f"📂 Đã nạp cấu hình quy hoạch cho {len(cities_data)} căn cứ từ hồ sơ.")
            return f"Xây Dựng ({len(cities_data)} căn cứ)"
        elif plans_list and hasattr(self, "bld_tree"):
            self._render_bld_tree_from_plans(plans_list)
            if self._current_bld_city_id is not None:
                self._city_building_plans[self._current_bld_city_id] = plans_list
            if hasattr(self, "_append_bld_log"):
                self._append_bld_log(f"📂 Đã nạp cấu hình {len(plans_list)} công trình từ hồ sơ.")
            return f"Xây Dựng ({len(plans_list)} công trình)"
        return None

    def _build_building_tab(self, parent):
        self._build_internal_and_research_tab(parent)

    def _build_internal_and_research_tab(self, parent):
        # Các widget tương thích ngược
        if not hasattr(self, "bld_city_combo"):
            self.bld_city_combo = ttk.Combobox(self, state="readonly", width=18)
        if not hasattr(self, "res_city_combo"):
            self.res_city_combo = ttk.Combobox(self, state="readonly", width=18)
        if not hasattr(self, "bld_slots_combo"):
            self.bld_slots_combo = ttk.Combobox(self, state="readonly", width=3, values=["1", "2", "3"])
            self.bld_slots_combo.set("3")

        # Khung chứa 3 Cột
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=6, pady=6)
        body.columnconfigure(0, weight=2, minsize=240)
        body.columnconfigure(1, weight=3, minsize=320)
        body.columnconfigure(2, weight=3, minsize=320)
        body.rowconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # CỘT 1 (TRÁI): Chức năng, Danh sách thành, Dịch Trại
        # ---------------------------------------------------------------------
        col1 = tk.Frame(body, bg=BG)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # 1. Khung Chức năng
        f_func = ttk.LabelFrame(col1, text="Chức năng", style="Card.TLabelframe")
        f_func.pack(fill="x", padx=2, pady=(0, 4))

        r_f1 = tk.Frame(f_func, bg=BG)
        r_f1.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_f1, text="Làm Mới", style="Action.TButton", command=self.reload).pack(
            side="left", expand=True, fill="x", padx=2
        )
        ttk.Button(r_f1, text="Xem Log", style="Action.TButton", command=self._open_log_window).pack(
            side="left", expand=True, fill="x", padx=2
        )

        r_f2 = tk.Frame(f_func, bg=BG)
        r_f2.pack(fill="x", padx=4, pady=2)
        self.bld_start_btn = ttk.Button(r_f2, text="Xây", style="Danger.TButton", command=self._toggle_building)
        self.bld_start_btn.pack(side="left", expand=True, fill="x", padx=2)
        self.res_start_btn = ttk.Button(r_f2, text="Nghiên Cứu", style="Danger.TButton", command=self._toggle_research)
        self.res_start_btn.pack(side="left", expand=True, fill="x", padx=2)
        self.res_monitor_btn = ttk.Button(
            r_f2, text="Tài Nguyên", style="Danger.TButton", command=self._toggle_resource_monitor
        )
        self.res_monitor_btn.pack(side="left", expand=True, fill="x", padx=2)

        r_f3 = tk.Frame(f_func, bg=BG)
        r_f3.pack(fill="x", padx=4, pady=2)
        ttk.Button(
            r_f3, text="Chọn", style="Success.TButton", command=lambda: self._set_selected_base_state(True)
        ).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(
            r_f3, text="Bỏ Chọn", style="Danger.TButton", command=lambda: self._set_selected_base_state(False)
        ).pack(side="left", expand=True, fill="x", padx=2)

        r_f4 = tk.Frame(f_func, bg=BG)
        r_f4.pack(fill="x", padx=4, pady=2)
        ttk.Button(
            r_f4, text="Chọn Tất Cả", style="Success.TButton", command=lambda: self._select_all_bld_bases(True)
        ).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(
            r_f4, text="Bỏ Tất Cả", style="Danger.TButton", command=lambda: self._select_all_bld_bases(False)
        ).pack(side="left", expand=True, fill="x", padx=2)

        r_f5 = tk.Frame(f_func, bg=BG)
        r_f5.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_f5, text="★ Chọn NC", style="Warning.TButton", command=self._set_selected_base_as_nc).pack(
            side="left", expand=True, fill="x", padx=2
        )
        ttk.Button(r_f5, text="✖ Bỏ NC", style="Action.TButton", command=self._clear_all_nc_bases).pack(
            side="left", expand=True, fill="x", padx=2
        )

        # 2. Khung Danh sách thành
        f_bases = ttk.LabelFrame(col1, text="Danh sách thành", style="Card.TLabelframe")
        f_bases.pack(fill="both", expand=True, padx=2, pady=4)

        self.bld_bases_tree = ttk.Treeview(
            f_bases,
            columns=("select", "resource", "research", "type", "id"),
            displaycolumns=("select", "resource", "research"),
            show="tree headings",
            selectmode="browse",
        )
        self.bld_bases_tree.heading("#0", text="Thành")
        self.bld_bases_tree.heading("select", text="Chọn")
        self.bld_bases_tree.heading("resource", text="Tài nguyên")
        self.bld_bases_tree.heading("research", text="NC")

        self.bld_bases_tree.column("#0", width=105)
        self.bld_bases_tree.column("select", width=42, anchor="center")
        self.bld_bases_tree.column("resource", width=68, anchor="center")
        self.bld_bases_tree.column("research", width=38, anchor="center")

        self.bld_bases_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.bld_bases_tree.bind("<ButtonRelease-1>", self._on_bld_bases_click)
        self.bld_bases_tree.bind("<<TreeviewSelect>>", self._on_bld_base_selected)

        # 3. Khung Dịch Trại
        self._build_ditrai_panel(col1)

        # ---------------------------------------------------------------------
        # CỘT 2 (GIỮA): Quản lý nhà & Nâng cấp kỹ thuật
        # ---------------------------------------------------------------------
        col2 = tk.Frame(body, bg=BG)
        col2.grid(row=0, column=1, sticky="nsew", padx=4)
        col2.rowconfigure(0, weight=1)
        col2.rowconfigure(1, weight=1)
        col2.columnconfigure(0, weight=1)

        # 1. Xây dựng
        self.bld_queue_frame = ttk.LabelFrame(col2, text="Xây dựng", style="Card.TLabelframe")
        self.bld_queue_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        bld_bar = tk.Frame(self.bld_queue_frame, bg=BG)
        bld_bar.pack(fill="x", padx=4, pady=2)
        tk.Label(bld_bar, text="Cấp mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        ttk.Entry(bld_bar, textvariable=self.bld_target_lvl_var, width=3).pack(side="left", padx=2)
        ttk.Button(bld_bar, text="Nâng", style="Success.TButton", command=self._set_bld_target_lvl).pack(
            side="left", padx=2
        )
        ttk.Button(bld_bar, text="Hạ", style="Danger.TButton", command=self._lower_bld_target_lvl).pack(
            side="left", padx=2
        )
        ttk.Button(bld_bar, text="↑", style="Action.TButton", width=3, command=self._move_bld_up).pack(
            side="left", padx=2
        )
        ttk.Button(bld_bar, text="↓", style="Action.TButton", width=3, command=self._move_bld_down).pack(
            side="left", padx=2
        )

        r_spd = tk.Frame(self.bld_queue_frame, bg=BG)
        r_spd.pack(fill="x", padx=4, pady=(0, 2))
        tk.Checkbutton(
            r_spd,
            text="Tốc nhà bằng",
            variable=self.bld_speedup_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)
        self.bld_speedup_item_combo = ttk.Combobox(r_spd, state="readonly", width=8, values=["Ngân Bảo", "Coin"])
        self.bld_speedup_item_combo.set("Ngân Bảo")
        self.bld_speedup_item_combo.pack(side="left", padx=2)
        tk.Label(r_spd, text="đến dưới", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        ttk.Entry(r_spd, textvariable=self.bld_speedup_hours_var, width=3).pack(side="left", padx=2)
        tk.Label(r_spd, text="giờ (≤0: ngay)", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        self.bld_speedup_var.trace_add("write", self._sync_running_bld_speedup)
        self.bld_speedup_hours_var.trace_add("write", self._sync_running_bld_speedup)
        self.bld_speedup_item_combo.bind("<<ComboboxSelected>>", self._sync_running_bld_speedup)

        bld_sub = tk.Frame(self.bld_queue_frame, bg=BG)
        bld_sub.pack(fill="x", padx=4, pady=(0, 2))
        tk.Checkbutton(
            bld_sub,
            text="Nâng nhà cấp cao nhất",
            variable=self.bld_max_lvl_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)

        self.bld_tree = ttk.Treeview(
            self.bld_queue_frame,
            columns=("select", "pid", "gid", "current_lvl", "target_lvl"),
            displaycolumns=("current_lvl", "target_lvl", "select"),
            show="tree headings",
            selectmode="browse",
        )
        self.bld_tree.heading("#0", text="Nhà")
        self.bld_tree.heading("current_lvl", text="Cấp HT")
        self.bld_tree.heading("target_lvl", text="Cấp MT")
        self.bld_tree.heading("select", text="Chạy")

        self.bld_tree.column("#0", width=130)
        self.bld_tree.column("current_lvl", width=48, anchor="center")
        self.bld_tree.column("target_lvl", width=48, anchor="center")
        self.bld_tree.column("select", width=42, anchor="center")

        self.bld_tree.tag_configure("upgrade", background="#173322", foreground="#86efac")
        self.bld_tree.tag_configure("downgrade", background="#3a1d1d", foreground="#fca5a5")
        self.bld_tree.tag_configure("completed", background=CARD, foreground=MUTED)

        self.bld_tree.pack(fill="both", expand=True, padx=4, pady=2)
        self.bld_tree.bind("<ButtonRelease-1>", self._on_bld_tree_click)
        self.bld_tree.bind("<<TreeviewSelect>>", self._on_bld_tree_selected)
        self._populate_default_buildings()

        # 2. Nâng cấp kỹ thuật
        self._build_tech_queue_panel(col2)

        # ---------------------------------------------------------------------
        # CỘT 3 (PHẢI): Ngưỡng tài nguyên/rương, Phụ trợ, Chuyển quân, Lưu/Load
        # ---------------------------------------------------------------------
        col3 = tk.Frame(body, bg=BG)
        col3.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        self._build_internal_aux_col3(col3)

    def _build_ditrai_panel(self, parent) -> None:
        from .shared import ACCENT

        f_dt = ttk.LabelFrame(parent, text="🏕️ Dịch Trại", style="Card.TLabelframe")
        f_dt.pack(fill="x", padx=2, pady=(4, 0))

        r_dt1 = tk.Frame(f_dt, bg=BG)
        r_dt1.pack(fill="x", padx=4, pady=2)
        tk.Label(r_dt1, text="Trại:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(2, 4))
        self.dt_camp_combo = ttk.Combobox(r_dt1, state="readonly", width=14)
        self.dt_camp_combo.pack(side="left", fill="x", expand=True, padx=2)
        self.dt_camp_combo.bind("<<ComboboxSelected>>", self._on_dt_camp_selected)

        r_dt2 = tk.Frame(f_dt, bg=BG)
        r_dt2.pack(fill="x", padx=4, pady=1)
        self.dt_origin_lbl = tk.Label(r_dt2, text="Vị trí: (---, ---)", bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold"))
        self.dt_origin_lbl.pack(side="left", padx=2)

        r_dt3 = tk.Frame(f_dt, bg=BG)
        r_dt3.pack(fill="x", padx=4, pady=2)
        tk.Label(r_dt3, text="Đích X:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        ttk.Entry(r_dt3, textvariable=self.dt_dest_x_var, width=5).pack(side="left", padx=2)

        tk.Label(r_dt3, text="Y:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
        ttk.Entry(r_dt3, textvariable=self.dt_dest_y_var, width=5).pack(side="left", padx=2)

        r_dt4 = tk.Frame(f_dt, bg=BG)
        r_dt4.pack(fill="x", padx=4, pady=3)
        self.dt_start_btn = ttk.Button(r_dt4, text="▶ Dịch Trại", style="Success.TButton", command=self._start_ditrai)
        self.dt_start_btn.pack(side="left", fill="x", expand=True, padx=2)
        self.dt_stop_btn = ttk.Button(
            r_dt4, text="⏹ Dừng", style="Danger.TButton", command=self._stop_ditrai, state="disabled"
        )
        self.dt_stop_btn.pack(side="left", fill="x", expand=True, padx=2)

        r_dt5 = tk.Frame(f_dt, bg=BG)
        r_dt5.pack(fill="x", padx=4, pady=(1, 4))
        self.dt_status_lbl = tk.Label(
            r_dt5, text="Trạng thái: Sẵn sàng", bg=BG, fg="#4ade80", font=("Segoe UI", 9, "bold"), anchor="w"
        )
        self.dt_status_lbl.pack(side="left", fill="x", expand=True, padx=2)

    def _build_tech_queue_panel(self, col2) -> None:
        f_tech = ttk.LabelFrame(col2, text="Nâng cấp kỹ thuật", style="Card.TLabelframe")
        f_tech.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        tech_bar = tk.Frame(f_tech, bg=BG)
        tech_bar.pack(fill="x", padx=4, pady=2)
        tk.Label(tech_bar, text="Cấp mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        ttk.Entry(tech_bar, textvariable=self.res_target_lvl_var, width=3).pack(side="left", padx=2)
        ttk.Button(tech_bar, text="OK", style="Action.TButton", command=self._set_res_target_lvl_all).pack(
            side="left", padx=2
        )
        ttk.Button(tech_bar, text="↑", style="Action.TButton", width=3, command=self._move_res_up).pack(
            side="left", padx=2
        )
        ttk.Button(tech_bar, text="↓", style="Action.TButton", width=3, command=self._move_res_down).pack(
            side="left", padx=2
        )

        tech_sub = tk.Frame(f_tech, bg=BG)
        tech_sub.pack(fill="x", padx=4, pady=(0, 2))
        tk.Checkbutton(
            tech_sub,
            text="墨子 (đến dưới 24h)",
            variable=self.res_art_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)
        tk.Checkbutton(
            tech_sub,
            text="Nâng đồng đều",
            variable=self.res_even_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=4)

        self.res_tree = ttk.Treeview(
            f_tech,
            columns=("select", "id", "target_lvl", "current_lvl"),
            displaycolumns=("current_lvl", "target_lvl", "select"),
            show="tree headings",
            selectmode="browse",
        )
        self.res_tree.heading("#0", text="Kỹ Thuật")
        self.res_tree.heading("current_lvl", text="Cấp HT")
        self.res_tree.heading("target_lvl", text="Cấp MT")
        self.res_tree.heading("select", text="Chạy")

        self.res_tree.column("#0", width=130)
        self.res_tree.column("current_lvl", width=48, anchor="center")
        self.res_tree.column("target_lvl", width=48, anchor="center")
        self.res_tree.column("select", width=42, anchor="center")

        self.res_tree.tag_configure("upgrade", background="#173322", foreground="#86efac")
        self.res_tree.tag_configure("downgrade", background="#3a1d1d", foreground="#fca5a5")
        self.res_tree.tag_configure("completed", background=CARD, foreground=MUTED)

        self.res_tree.pack(fill="both", expand=True, padx=4, pady=2)
        self.res_tree.bind("<ButtonRelease-1>", self._on_res_tree_click)
        self.res_tree.bind("<<TreeviewSelect>>", self._on_res_tree_selected)
        self._populate_all_techs()

    def _build_internal_aux_col3(self, col3) -> None:
        # 1. Thiết lập ngưỡng tài nguyên và rương
        f_res_thresh = ttk.LabelFrame(col3, text="Thiết lập ngưỡng tài nguyên và rương", style="Card.TLabelframe")
        f_res_thresh.pack(fill="x", padx=2, pady=(0, 4))

        tk.Checkbutton(
            f_res_thresh,
            text="Mở khi thiếu lúc xây dựng",
            variable=self.bld_open_box_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=6, pady=(2, 2))

        r_v = tk.Frame(f_res_thresh, bg=BG)
        r_v.pack(fill="x", padx=6, pady=1)
        tk.Label(r_v, text="Vàng:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_v, textvariable=self.res_gold_thresh_var, width=12).pack(side="left", padx=4)

        r_tn1 = tk.Frame(f_res_thresh, bg=BG)
        r_tn1.pack(fill="x", padx=6, pady=1)
        tk.Label(r_tn1, text="Gỗ (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn1, textvariable=self.res_wood_pct_var, width=4).pack(side="left", padx=(2, 10))
        tk.Label(r_tn1, text="Sắt (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn1, textvariable=self.res_iron_pct_var, width=4).pack(side="left", padx=2)

        r_tn2 = tk.Frame(f_res_thresh, bg=BG)
        r_tn2.pack(fill="x", padx=6, pady=1)
        tk.Label(r_tn2, text="Đá (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn2, textvariable=self.res_stone_pct_var, width=4).pack(side="left", padx=(2, 10))
        tk.Label(r_tn2, text="Thực (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn2, textvariable=self.res_food_pct_var, width=4).pack(side="left", padx=2)

        box_options = [
            "1: 民生之囊 - Dân Sinh Bảo Nang",
            "6: 民生之幡 - Dân Sinh Bảo Phiên",
            "11: 民生之匣 - Dân Sinh Chi Hạp",
            "16: 民生之椟 - Dân Sinh Chi Độc",
            "24: 民生之鼎 - Dân Sinh Bảo Đỉnh",
            "35: 白金资源礼盒 - Bạch Kim Tài Nguyên Lễ Hộp",
        ]

        r_box1 = tk.Frame(f_res_thresh, bg=BG)
        r_box1.pack(fill="x", padx=6, pady=2)
        tk.Label(r_box1, text="Rương Vàng:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.res_gold_box_combo = ttk.Combobox(r_box1, state="readonly", width=32, values=box_options)
        self.res_gold_box_combo.set(box_options[2])
        self.res_gold_box_combo.pack(side="left", fill="x", expand=True, padx=4)

        r_box2 = tk.Frame(f_res_thresh, bg=BG)
        r_box2.pack(fill="x", padx=6, pady=2)
        tk.Label(r_box2, text="Rương TN:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.res_tn_box_combo = ttk.Combobox(r_box2, state="readonly", width=32, values=box_options)
        self.res_tn_box_combo.set(box_options[4])
        self.res_tn_box_combo.pack(side="left", fill="x", expand=True, padx=4)
        self.bld_box_combo = self.res_tn_box_combo

        ttk.Button(
            f_res_thresh, text="Áp Dụng Thiết Lập", style="Success.TButton", command=self._apply_resource_settings
        ).pack(pady=4)

        # 2. Chức năng phụ trợ
        f_aux = ttk.LabelFrame(col3, text="Chức năng phụ trợ", style="Card.TLabelframe")
        f_aux.pack(fill="x", padx=2, pady=4)

        r_aux1 = tk.Frame(f_aux, bg=BG)
        r_aux1.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(
            r_aux1,
            text="Thưởng hàng ngày",
            variable=self.aux_daily_reward_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)
        tk.Checkbutton(
            r_aux1,
            text="Tự an ủi",
            variable=self.aux_comfort_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)

        r_aux2 = tk.Frame(f_aux, bg=BG)
        r_aux2.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(
            r_aux2,
            text="DS kiến trúc",
            variable=self.aux_boost_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)
        self.aux_boost_time_lbl = tk.Label(r_aux2, text="(Còn: --)", bg=BG, fg="#4ade80", font=("Segoe UI", 8, "bold"))
        self.aux_boost_time_lbl.pack(side="left", padx=2)

        r_aux3 = tk.Frame(f_aux, bg=BG)
        r_aux3.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(
            r_aux3,
            text="Cống quận",
            variable=self.aux_tribute_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)
        self.aux_tribute_bld_combo = ttk.Combobox(
            r_aux3, state="readonly", width=16, values=["官府 (Quan Phủ)", "城墙 (Tường Thành)"]
        )
        self.aux_tribute_bld_combo.set("官府 (Quan Phủ)")
        self.aux_tribute_bld_combo.pack(side="left", padx=4)

        r_aux_visit = tk.Frame(f_aux, bg=BG)
        r_aux_visit.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(
            r_aux_visit,
            text="Báo danh tướng viếng thăm",
            variable=self.aux_general_visit_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            activeforeground=FG,
            font=("Segoe UI", 9),
            command=lambda: self._check_and_notify_general_visit(async_check=True)
            if hasattr(self, "_check_and_notify_general_visit")
            else None,
        ).pack(side="left", padx=2)
        self.aux_visit_lbl = tk.Label(
            r_aux_visit,
            text="(Chưa kiểm tra)",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        )
        self.aux_visit_lbl.pack(side="left", padx=(6, 0))

        r_aux4 = tk.Frame(f_aux, bg=BG)
        r_aux4.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(
            r_aux4,
            text="Thám bảo",
            variable=self.aux_explore_var,
            command=self._on_aux_explore_toggled,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)
        self.aux_explore_time_lbl = tk.Label(
            r_aux4,
            text="(Còn: --)",
            bg=BG,
            fg="#4ade80",
            font=("Segoe UI", 8, "bold"),
        )
        self.aux_explore_time_lbl.pack(side="left", padx=2)

        r_aux5 = tk.Frame(f_aux, bg=BG)
        r_aux5.pack(fill="x", padx=4, pady=2)
        self.aux_explore_whip_cb = tk.Checkbutton(
            r_aux5,
            text="Dùng Roi",
            variable=self.aux_explore_whip_var,
            command=lambda: self._on_explore_clear_mode_changed("whip"),
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        )
        self.aux_explore_whip_cb.pack(side="left", padx=2)
        self.aux_explore_coin_cb = tk.Checkbutton(
            r_aux5,
            text="Dùng Coin",
            variable=self.aux_explore_coin_var,
            command=lambda: self._on_explore_clear_mode_changed("coin"),
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        )
        self.aux_explore_coin_cb.pack(side="left", padx=2)
        self.aux_explore_turns_frame = tk.Frame(r_aux5, bg=BG)
        tk.Label(
            self.aux_explore_turns_frame,
            text="Số lượt:",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(4, 2))
        self.aux_explore_turns_entry = ttk.Entry(
            self.aux_explore_turns_frame,
            textvariable=self.aux_explore_turns_var,
            width=4,
        )
        self.aux_explore_turns_entry.pack(side="left")
        self._update_explore_turns_visibility()

        # 2b. Mở Rương Hàng Loạt
        f_chest = ttk.LabelFrame(col3, text="📦 Mở Rương Hàng Loạt", style="Card.TLabelframe")
        f_chest.pack(fill="x", padx=2, pady=4)

        r_c1 = tk.Frame(f_chest, bg=BG)
        r_c1.pack(fill="x", padx=4, pady=2)
        tk.Label(r_c1, text="Loại:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        chest_names = list(CHEST_MAPPING.keys())
        self.chest_type_combo = ttk.Combobox(r_c1, state="readonly", width=30, values=chest_names)
        if chest_names:
            self.chest_type_combo.current(0)
        self.chest_type_combo.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self.chest_type_combo.bind("<<ComboboxSelected>>", self._on_chest_type_selected)

        r_c2 = tk.Frame(f_chest, bg=BG)
        r_c2.pack(fill="x", padx=4, pady=2)
        tk.Label(r_c2, text="Thành:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.chest_city_combo = ttk.Combobox(r_c2, state="readonly", width=13)
        self.chest_city_combo.pack(side="left", fill="x", expand=True, padx=(4, 6))
        tk.Label(r_c2, text="Số lượt:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.chest_times_var = tk.StringVar(value="1")
        self.chest_times_entry = ttk.Entry(r_c2, textvariable=self.chest_times_var, width=5)
        self.chest_times_entry.pack(side="left", padx=(4, 0))

        r_c3 = tk.Frame(f_chest, bg=BG)
        r_c3.pack(fill="x", padx=4, pady=2)
        self.chest_start_btn = ttk.Button(
            r_c3, text="📦 Mở Rương", style="Success.TButton", command=self._start_open_chest_batch
        )
        self.chest_start_btn.pack(side="left", padx=(0, 3))
        self.chest_stop_btn = ttk.Button(
            r_c3, text="⏹ Dừng", style="Danger.TButton", state="disabled", command=self._stop_open_chest_batch
        )
        self.chest_stop_btn.pack(side="left", padx=(0, 6))
        self.chest_progress_lbl = tk.Label(r_c3, text="Tiến độ: 0% (0/0)", bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.chest_progress_lbl.pack(side="right", padx=(2, 0))

        self.chest_progress_bar = ttk.Progressbar(f_chest, orient="horizontal", mode="determinate", maximum=100)
        self.chest_progress_bar.pack(fill="x", padx=4, pady=(0, 4))

        # 3. Chuyển Quân Giới
        f_logis = ttk.LabelFrame(col3, text="Chuyển Quân Giới", style="Card.TLabelframe")
        f_logis.pack(fill="both", expand=True, padx=2, pady=4)

        r_l1 = tk.Frame(f_logis, bg=BG)
        r_l1.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l1, text="Từ", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_from_city_combo = ttk.Combobox(r_l1, state="readonly", width=11)
        self.log_from_city_combo.pack(side="left", padx=2)
        tk.Label(r_l1, text="Đến", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_to_city_combo = ttk.Combobox(r_l1, state="readonly", width=11)
        self.log_to_city_combo.pack(side="left", padx=2)

        r_l2 = tk.Frame(f_logis, bg=BG)
        r_l2.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l2, text="Vận ch", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_army_combo = ttk.Combobox(
            r_l2, state="readonly", width=10, values=["1: Bộ binh", "2: Kỵ binh", "3: Cung binh"]
        )
        self.log_army_combo.set("1: Bộ binh")
        self.log_army_combo.pack(side="left", padx=2)
        tk.Label(r_l2, text="SL", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_l2, textvariable=self.log_amount_var, width=5).pack(side="left", padx=2)

        r_l3 = tk.Frame(f_logis, bg=BG)
        r_l3.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l3, text="Lặp lại", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_l3, textvariable=self.log_interval_var, width=4).pack(side="left", padx=2)
        tk.Label(r_l3, text="giây", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=2)

        r_l_btn = tk.Frame(f_logis, bg=BG)
        r_l_btn.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_l_btn, text="Add", style="Success.TButton", command=self._add_army_transfer_order).pack(
            side="left", expand=True, fill="x", padx=2
        )
        ttk.Button(r_l_btn, text="Xóa", style="Danger.TButton", command=self._delete_army_transfer_order).pack(
            side="left", expand=True, fill="x", padx=2
        )

        self.log_transfers_tree = ttk.Treeview(
            f_logis,
            columns=("route", "amount", "army"),
            show="headings",
            selectmode="browse",
            height=3,
        )
        self.log_transfers_tree.heading("route", text="Từ – Đến")
        self.log_transfers_tree.heading("amount", text="SL")
        self.log_transfers_tree.heading("army", text="Quân giới")
        self.log_transfers_tree.column("route", width=120)
        self.log_transfers_tree.column("amount", width=40, anchor="center")
        self.log_transfers_tree.column("army", width=70, anchor="center")
        self.log_transfers_tree.pack(fill="both", expand=True, padx=4, pady=2)

        # 4. Hàng nút chân trang Cột 3
        footer = tk.Frame(col3, bg=BG)
        footer.pack(fill="x", padx=2, pady=(4, 0))
        ttk.Button(footer, text="Re-Login", style="Action.TButton", command=self._do_relogin).pack(
            side="left", expand=True, fill="x", padx=2
        )
        ttk.Button(footer, text="💾 Lưu", style="Success.TButton", command=self._save_unified_profile_dialog).pack(
            side="left", expand=True, fill="x", padx=2
        )
        ttk.Button(footer, text="📂 Load", style="Action.TButton", command=self._load_unified_profile_dialog).pack(
            side="left", expand=True, fill="x", padx=2
        )

    def _append_bld_log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        for w in list(self._active_log_texts):
            self._append_text_buffer(w, line)

    def _open_log_window(self):
        if hasattr(self, "_log_win") and self._log_win and self._log_win.winfo_exists():
            self._log_win.lift()
            self._log_win.focus_force()
            return

        win = tk.Toplevel(self)
        win.title("📜 Nhật Ký Hoạt Động (Nội Chính & Nghiên Cứu)")
        win.geometry("750x450")
        win.configure(bg=BG)
        self._log_win = win

        top_bar = tk.Frame(win, bg=BG)
        top_bar.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(
            top_bar,
            text="Nhật ký chi tiết các tác vụ Nội Chính, Xây Dựng & Nghiên Cứu",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        f_txt = tk.Frame(win, bg=BG)
        f_txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        sb = ttk.Scrollbar(f_txt, orient="vertical")
        txt = tk.Text(
            f_txt,
            bg="#111420",
            fg=FG,
            insertbackground=FG,
            font=("Consolas", 9),
            yscrollcommand=sb.set,
            wrap="word",
        )
        sb.config(command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        if txt not in self._active_log_texts:
            self._active_log_texts.append(txt)

        def clear_log():
            txt.delete("1.0", "end")
            if hasattr(self, "bld_log_text") and self.bld_log_text:
                self.bld_log_text.delete("1.0", "end")
            if hasattr(self, "logis_log_text") and self.logis_log_text:
                self.logis_log_text.delete("1.0", "end")

        ttk.Button(top_bar, text="🗑️ Xóa nhật ký", style="Danger.TButton", command=clear_log).pack(side="right", padx=4)

        if hasattr(self, "bld_log_text") and self.bld_log_text:
            try:
                existing = self.bld_log_text.get("1.0", "end-1c")
                if existing:
                    txt.insert("end", existing + "\n")
                    txt.see("end")
            except Exception:
                pass

        def on_close():
            if txt in self._active_log_texts:
                self._active_log_texts.remove(txt)
            win.destroy()
            self._log_win = None

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _lower_bld_target_lvl(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.bld_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 công trình trong bảng!")
            return
        try:
            lvl = int(self.bld_target_lvl_var.get())
            if lvl < 0 or lvl > 45:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 0 đến 45 (0: dỡ bỏ)!")
            return

        for item in sel:
            if not self.bld_tree.exists(item):
                continue
            if item.startswith("group_"):
                for child in self.bld_tree.get_children(item):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[0] = "☑"
                    c_vals[4] = lvl
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                self._update_group_summary(item)
            else:
                vals = list(self.bld_tree.item(item, "values"))
                vals[0] = "☑"
                vals[4] = lvl
                self.bld_tree.item(item, values=vals)
                self._update_bld_tree_row_style(item)
                parent = self.bld_tree.parent(item)
                if parent and parent.startswith("group_"):
                    self._update_group_summary(parent)

        self._save_current_bld_tree_to_cache()
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _set_selected_base_state(self, state: bool):
        sel = self.bld_bases_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = list(self.bld_bases_tree.item(item, "values"))
        sym = "☑" if state else "☐"
        vals[0] = sym
        self.bld_bases_tree.item(item, values=vals)
        try:
            base_id = int(item)
        except ValueError:
            base_id = int(vals[4]) if len(vals) > 4 else int(vals[2]) if len(vals) > 2 else 0
        if state:
            self._selected_building_cities.add(base_id)
        else:
            self._selected_building_cities.discard(base_id)
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _set_selected_base_as_nc(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.bld_bases_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 thành trong danh sách thành để làm Thành Nghiên Cứu!")
            return
        item = sel[0]
        try:
            base_id = int(item)
        except ValueError:
            vals = list(self.bld_bases_tree.item(item, "values"))
            base_id = int(vals[4]) if len(vals) > 4 else int(vals[2]) if len(vals) > 2 else 0

        self._research_city_id = base_id
        for iid in self.bld_bases_tree.get_children(""):
            vals = list(self.bld_bases_tree.item(iid, "values"))
            if len(vals) > 2:
                vals[2] = "★" if iid == item else "☐"
                self.bld_bases_tree.item(iid, values=vals)

        if hasattr(self, "res_city_combo") and self.roster:
            cities = self.roster.cities if self.roster.cities else self.roster.bases
            for idx, c in enumerate(cities):
                if c.id == base_id:
                    self.res_city_combo.current(idx)
                    break
        base_name = self.bld_bases_tree.item(item, "text")
        self._append_bld_log(f"★ Đã chọn '{base_name}' làm Thành Nghiên Cứu trọng điểm.")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _clear_all_nc_bases(self):
        self._research_city_id = None
        for iid in self.bld_bases_tree.get_children(""):
            vals = list(self.bld_bases_tree.item(iid, "values"))
            if len(vals) > 2:
                vals[2] = "☐"
                self.bld_bases_tree.item(iid, values=vals)
        self._append_bld_log("✖ Đã bỏ chọn tất cả Thành Nghiên Cứu.")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _get_bld_row_tag(self, cur_lvl: int, target_lvl: int) -> str:
        if cur_lvl < target_lvl:
            return "upgrade"
        elif cur_lvl > target_lvl:
            return "downgrade"
        return "completed"

    def _update_group_summary(self, group_iid: str):
        """Cập nhật trạng thái chọn, dải cấp độ hiện tại và tag màu cho dòng cha của nhóm."""
        if not hasattr(self, "bld_tree") or not self.bld_tree.exists(group_iid):
            return
        children = self.bld_tree.get_children(group_iid)
        if not children:
            return
        p_vals = list(self.bld_tree.item(group_iid, "values"))
        all_en = True
        any_en = False
        cur_lvls = []
        target_lvls = []
        for c in children:
            c_vals = self.bld_tree.item(c, "values")
            en = c_vals[0] == "☑"
            if en:
                any_en = True
            else:
                all_en = False
            try:
                cur_lvls.append(int(c_vals[3]))
                target_lvls.append(int(c_vals[4]))
            except (ValueError, TypeError):
                pass

        p_vals[0] = "☑" if all_en else ("▣" if any_en else "☐")
        if cur_lvls and target_lvls:
            min_cur, max_cur = min(cur_lvls), max(cur_lvls)
            p_vals[3] = str(min_cur) if min_cur == max_cur else f"{min_cur} - {max_cur}"
            p_vals[4] = max(target_lvls)
            tag = "completed" if all(c >= t for c, t in zip(cur_lvls, target_lvls)) else "upgrade"
            self.bld_tree.item(group_iid, values=p_vals, tags=(tag,))
        else:
            self.bld_tree.item(group_iid, values=p_vals)

    def _update_bld_tree_row_style(self, iid: str):
        if not hasattr(self, "bld_tree") or not self.bld_tree.exists(iid):
            return
        if iid.startswith("group_"):
            self._update_group_summary(iid)
            return
        vals = self.bld_tree.item(iid, "values")
        if len(vals) >= 5:
            try:
                cur_lvl = int(vals[3])
                target_lvl = int(vals[4])
                tag = self._get_bld_row_tag(cur_lvl, target_lvl)
                self.bld_tree.item(iid, tags=(tag,))
            except (ValueError, TypeError):
                pass
        parent = self.bld_tree.parent(iid)
        if parent and parent.startswith("group_"):
            self._update_group_summary(parent)

    def _populate_default_buildings(self):
        default_plots = [
            {"pid": 1, "gid": 1, "name": "官府 - Quan Phủ", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 2, "gid": 2, "name": "城墙 - Tường Thành", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 3, "gid": 3, "name": "民房 - Nhà Dân", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 4, "gid": 4, "name": "仓库 - Kho", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 5, "gid": 5, "name": "鸿胪寺 - Hồng Lư Tự", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 6, "gid": 6, "name": "大学殿 - Đại Học Điện", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 7, "gid": 7, "name": "客栈 - Quán Trọ", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 8, "gid": 8, "name": "酒馆 - Tửu Quán", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 9, "gid": 9, "name": "聚贤楼 - Tụ Hiền Lâu", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 10, "gid": 10, "name": "点将台 - Điểm Tướng Đài", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 11, "gid": 11, "name": "市场 - Chợ", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 12, "gid": 12, "name": "驿站 - Dịch Trạm", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 13, "gid": 13, "name": "兵器铺 - Xưởng Binh Khí", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 14, "gid": 14, "name": "防具铺 - Xưởng Khôi Giáp", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 15, "gid": 15, "name": "车马间 - Xưởng Ngựa", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 16, "gid": 16, "name": "校场 - Binh Trường", "cur_lvl": 0, "target_level": 20, "enabled": False},
        ]
        self._render_bld_tree_from_plans(default_plots)

    def _move_bld_up(self):
        sel = self.bld_tree.selection()
        if not sel:
            return
        item = sel[0]
        parent = self.bld_tree.parent(item)
        target = parent if parent else item
        roots = list(self.bld_tree.get_children(""))
        if target in roots:
            idx = roots.index(target)
            if idx > 0:
                self.bld_tree.move(target, "", idx - 1)
                self._save_current_bld_tree_to_cache()
                if hasattr(self, "_schedule_auto_save"):
                    self._schedule_auto_save()

    def _move_bld_down(self):
        sel = self.bld_tree.selection()
        if not sel:
            return
        item = sel[0]
        parent = self.bld_tree.parent(item)
        target = parent if parent else item
        roots = list(self.bld_tree.get_children(""))
        if target in roots:
            idx = roots.index(target)
            if idx < len(roots) - 1:
                self.bld_tree.move(target, "", idx + 1)
                self._save_current_bld_tree_to_cache()
                if hasattr(self, "_schedule_auto_save"):
                    self._schedule_auto_save()

    def _select_all_bld(self, state: bool):
        sym = "☑" if state else "☐"
        for root_iid in self.bld_tree.get_children(""):
            if root_iid.startswith("group_"):
                p_vals = list(self.bld_tree.item(root_iid, "values"))
                p_vals[0] = sym
                self.bld_tree.item(root_iid, values=p_vals)
                for child in self.bld_tree.get_children(root_iid):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[0] = sym
                    self.bld_tree.item(child, values=c_vals)
            else:
                vals = list(self.bld_tree.item(root_iid, "values"))
                vals[0] = sym
                self.bld_tree.item(root_iid, values=vals)
        self._save_current_bld_tree_to_cache()
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _set_bld_target_lvl(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.bld_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 công trình trong bảng!")
            return
        try:
            lvl = int(self.bld_target_lvl_var.get())
            if lvl < 0 or lvl > 45:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 0 đến 45 (0: dỡ bỏ)!")
            return

        for item in sel:
            if not self.bld_tree.exists(item):
                continue
            if item.startswith("group_"):
                for child in self.bld_tree.get_children(item):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[0] = "☑"
                    c_vals[4] = lvl
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                self._update_group_summary(item)
            else:
                vals = list(self.bld_tree.item(item, "values"))
                vals[0] = "☑"
                vals[4] = lvl
                self.bld_tree.item(item, values=vals)
                self._update_bld_tree_row_style(item)
                parent = self.bld_tree.parent(item)
                if parent and parent.startswith("group_"):
                    self._update_group_summary(parent)

        self._save_current_bld_tree_to_cache()
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _set_bld_target_lvl_all(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        try:
            lvl = int(self.bld_target_lvl_var.get())
            if lvl < 0 or lvl > 45:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 0 đến 45 (0: dỡ bỏ)!")
            return

        count = 0
        for root_iid in self.bld_tree.get_children(""):
            if root_iid.startswith("group_"):
                for child in self.bld_tree.get_children(root_iid):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[4] = lvl
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                    count += 1
                self._update_group_summary(root_iid)
            else:
                vals = list(self.bld_tree.item(root_iid, "values"))
                vals[4] = lvl
                self.bld_tree.item(root_iid, values=vals)
                self._update_bld_tree_row_style(root_iid)
                count += 1

        self._save_current_bld_tree_to_cache()
        self._append_bld_log(f"🎯 Đã đặt Cấp mục tiêu = {lvl} cho tất cả {count} công trình.")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _on_bld_tree_selected(self, _event=None):
        pass

    def _on_bld_tree_click(self, event):
        item = self.bld_tree.identify_row(event.y)
        col = self.bld_tree.identify_column(event.x)
        if not item or not self.bld_tree.exists(item):
            return

        # displaycolumns=("current_lvl", "target_lvl", "select")
        # identify_column: #0 (text), #1 (current_lvl - "Cấp HT"), #2 (target_lvl - "Cấp MT"), #3 (select - "Chạy")
        is_select_col = col == "#3"

        if not is_select_col:
            self.bld_tree.selection_set(item)

        if item.startswith("group_"):
            vals = list(self.bld_tree.item(item, "values"))
            if is_select_col:
                new_state = "☐" if vals[0] in ("☑", "▣") else "☑"
                vals[0] = new_state
                self.bld_tree.item(item, values=vals)
                for child in self.bld_tree.get_children(item):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[0] = new_state
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                self._update_group_summary(item)
            self._save_current_bld_tree_to_cache()
            if is_select_col and hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()
            return

        vals = list(self.bld_tree.item(item, "values"))
        parent = self.bld_tree.parent(item)
        if is_select_col:
            vals[0] = "☑" if vals[0] == "☐" else "☐"
            self.bld_tree.item(item, values=vals)
            if parent and parent.startswith("group_"):
                self._update_group_summary(parent)
            self._save_current_bld_tree_to_cache()
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()

    def _on_bld_bases_click(self, event):
        item = self.bld_bases_tree.identify_row(event.y)
        col = self.bld_bases_tree.identify_column(event.x)
        if not item or not self.bld_bases_tree.exists(item):
            return
        vals = list(self.bld_bases_tree.item(item, "values"))
        try:
            base_id = int(item)
        except ValueError:
            base_id = int(vals[4]) if len(vals) > 4 else int(vals[2]) if len(vals) > 2 else 0

        if col == "#1":
            if vals[0] == "☑":
                vals[0] = "☐"
                self._selected_building_cities.discard(base_id)
            else:
                vals[0] = "☑"
                self._selected_building_cities.add(base_id)
            self.bld_bases_tree.item(item, values=vals)
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()
        elif col == "#2":
            is_res = vals[1] if len(vals) > 1 else "☐"
            if is_res == "☑":
                vals[1] = "☐"
                self._selected_resource_cities.discard(base_id)
            else:
                vals[1] = "☑"
                self._selected_resource_cities.add(base_id)
            self.bld_bases_tree.item(item, values=vals)
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()
        elif col == "#3":
            is_nc = vals[2] if len(vals) > 2 else "☐"
            if is_nc == "★":
                vals[2] = "☐"
                self._research_city_id = None
                self.bld_bases_tree.item(item, values=vals)
            else:
                self._research_city_id = base_id
                for iid in self.bld_bases_tree.get_children(""):
                    i_vals = list(self.bld_bases_tree.item(iid, "values"))
                    if len(i_vals) > 2:
                        i_vals[2] = "★" if iid == item else "☐"
                        self.bld_bases_tree.item(iid, values=i_vals)
                if hasattr(self, "res_city_combo") and self.roster:
                    cities = self.roster.cities if self.roster.cities else self.roster.bases
                    for idx, c in enumerate(cities):
                        if c.id == base_id:
                            if 0 <= idx < len(self.res_city_combo["values"]):
                                self.res_city_combo.current(idx)
                            break
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()

    def _on_bld_base_selected(self, _event=None):
        sel = self.bld_bases_tree.selection()
        if not sel:
            return
        try:
            base_id = int(sel[0])
            self._switch_bld_base(base_id)
            if hasattr(self, "bld_city_combo") and self.roster:
                cities = self.roster.cities if self.roster.cities else self.roster.bases
                for idx, c in enumerate(cities):
                    if c.id == base_id:
                        if 0 <= idx < len(self.bld_city_combo["values"]):
                            self.bld_city_combo.current(idx)
                        break
            if hasattr(self, "dt_camp_combo") and self.roster and self.roster.camps:
                for idx, c in enumerate(self.roster.camps):
                    if c.id == base_id:
                        if 0 <= idx < len(self.dt_camp_combo["values"]):
                            self.dt_camp_combo.current(idx)
                            self._on_dt_camp_selected()
                        break
        except ValueError:
            pass

    def _on_bld_city_combo_selected(self, _event=None):
        sel_idx = self.bld_city_combo.current()
        cities = (
            self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        )
        if 0 <= sel_idx < len(cities):
            base_id = cities[sel_idx].id
            if hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(base_id)):
                self.bld_bases_tree.selection_set(str(base_id))
            self._switch_bld_base(base_id)

    def _select_all_bld_bases(self, state: bool):
        sym = "☑" if state else "☐"
        for iid in self.bld_bases_tree.get_children(""):
            vals = list(self.bld_bases_tree.item(iid, "values"))
            vals[0] = sym
            self.bld_bases_tree.item(iid, values=vals)
            try:
                bid = int(iid)
                if state:
                    self._selected_building_cities.add(bid)
                else:
                    self._selected_building_cities.discard(bid)
            except ValueError:
                pass
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _collect_bld_plans_from_tree(self) -> list[dict]:
        """Thu thập danh sách cấu hình phẳng từ bld_tree bảo toàn đúng thứ tự Loại công trình."""
        plans = []
        for root_iid in self.bld_tree.get_children(""):
            if root_iid.startswith("group_"):
                for child_iid in self.bld_tree.get_children(root_iid):
                    vals = self.bld_tree.item(child_iid, "values")
                    if len(vals) >= 5:
                        try:
                            gid = int(vals[2])
                            bname = BUILDING_NAMES.get(gid, f"Công trình {gid}")
                            c_lvl = int(vals[3]) if str(vals[3]).isdigit() else 0
                            t_lvl = int(vals[4]) if str(vals[4]).isdigit() else 20
                            plans.append(
                                {
                                    "pid": int(vals[1]),
                                    "gid": gid,
                                    "name": bname,
                                    "cur_lvl": c_lvl,
                                    "target_level": t_lvl,
                                    "enabled": vals[0] == "☑",
                                }
                            )
                        except (ValueError, TypeError, IndexError):
                            pass
            else:
                vals = self.bld_tree.item(root_iid, "values")
                name = self.bld_tree.item(root_iid, "text")
                if len(vals) >= 5:
                    try:
                        gid = int(vals[2])
                        c_lvl = int(vals[3]) if str(vals[3]).isdigit() else 0
                        t_lvl = int(vals[4]) if str(vals[4]).isdigit() else 20
                        plans.append(
                            {
                                "pid": int(vals[1]),
                                "gid": gid,
                                "name": name,
                                "cur_lvl": c_lvl,
                                "target_level": t_lvl,
                                "enabled": vals[0] == "☑",
                            }
                        )
                    except (ValueError, TypeError, IndexError):
                        pass
        return plans

    def _save_current_bld_tree_to_cache(self):
        if self._current_bld_city_id is None:
            return
        plans = self._collect_bld_plans_from_tree()
        self._city_building_plans[self._current_bld_city_id] = plans

    def _render_bld_tree_from_plans(self, plans: list[dict]):
        expanded_groups = set()
        if hasattr(self, "bld_tree"):
            for iid in self.bld_tree.get_children(""):
                if iid.startswith("group_") and bool(self.bld_tree.item(iid, "open")):
                    expanded_groups.add(iid)
        self.bld_tree.delete(*self.bld_tree.get_children(""))
        gid_order = []
        grouped: dict[int, list[dict]] = {}
        for p in plans:
            gid = int(p.get("gid", 1))
            if gid not in grouped:
                grouped[gid] = []
                gid_order.append(gid)
            grouped[gid].append(p)

        for gid in gid_order:
            plots = grouped[gid]
            plots.sort(key=lambda x: int(x.get("pid", 1)))
            if len(plots) == 1:
                p = plots[0]
                pid = int(p.get("pid", 1))
                name = p.get("name") or BUILDING_NAMES.get(gid, f"Công trình {gid}")
                en = "☑" if p.get("enabled", False) else "☐"
                cur_lvl = int(p.get("cur_lvl", 0))
                target_lvl = int(p.get("target_level", 20))
                tag = self._get_bld_row_tag(cur_lvl, target_lvl)
                self.bld_tree.insert(
                    "",
                    "end",
                    iid=str(pid),
                    text=name,
                    values=(en, pid, gid, cur_lvl, target_lvl),
                    tags=(tag,),
                )
            else:
                count = len(plots)
                name = plots[0].get("name") or BUILDING_NAMES.get(gid, f"Công trình {gid}")
                all_en = all(p.get("enabled", False) for p in plots)
                any_en = any(p.get("enabled", False) for p in plots)
                sym = "☑" if all_en else ("▣" if any_en else "☐")
                cur_lvls = [int(p.get("cur_lvl", 0)) for p in plots]
                target_lvls = [int(p.get("target_level", 20)) for p in plots]
                min_cur, max_cur = min(cur_lvls), max(cur_lvls)
                cur_str = str(min_cur) if min_cur == max_cur else f"{min_cur} - {max_cur}"
                target_str = str(max(target_lvls))
                tag = "completed" if all(c >= t for c, t in zip(cur_lvls, target_lvls)) else "upgrade"
                group_iid = f"group_{gid}"
                is_open = group_iid in expanded_groups
                self.bld_tree.insert(
                    "",
                    "end",
                    iid=group_iid,
                    text=f"{name} ({count} ô)",
                    values=(sym, f"{count} ô", gid, cur_str, target_str),
                    tags=(tag,),
                    open=is_open,
                )
                for p in plots:
                    pid = int(p.get("pid", 1))
                    en = "☑" if p.get("enabled", False) else "☐"
                    cur_lvl = int(p.get("cur_lvl", 0))
                    target_lvl = int(p.get("target_level", 20))
                    c_tag = self._get_bld_row_tag(cur_lvl, target_lvl)
                    self.bld_tree.insert(
                        group_iid,
                        "end",
                        iid=str(pid),
                        text=f"  ↳ Ô {pid}",
                        values=(en, pid, gid, cur_lvl, target_lvl),
                        tags=(c_tag,),
                    )

        children = self.bld_tree.get_children("")
        if children:
            sel = self.bld_tree.selection()
            if not sel or not self.bld_tree.exists(sel[0]):
                self.bld_tree.selection_set(children[0])
            self._on_bld_tree_selected()

    def _switch_bld_base(self, new_base_id: int):
        if self._current_bld_city_id == new_base_id:
            return
        self._save_current_bld_tree_to_cache()
        self._current_bld_city_id = new_base_id
        self._check_and_update_boost_status(async_check=True)

        base_name = f"Căn cứ {new_base_id}"
        if hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(new_base_id)):
            base_name = self.bld_bases_tree.item(str(new_base_id), "text")
        elif self.roster:
            b = self.roster.base_by_id(new_base_id)
            if b:
                base_name = b.name

        if hasattr(self, "bld_queue_frame"):
            self.bld_queue_frame.configure(text=f"Xây dựng: {base_name}")

        cached = self._city_building_plans.get(new_base_id)
        if cached:
            self._render_bld_tree_from_plans(cached)
        else:
            self._populate_default_buildings()
            if self.gateway and hasattr(self, "_fetch_city_buildings_thread"):
                threading.Thread(target=self._fetch_city_buildings_thread, args=(new_base_id,), daemon=True).start()

    def _fetch_city_buildings(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        city_id = self._current_bld_city_id
        if not city_id:
            sel_idx = self.bld_city_combo.current() if hasattr(self, "bld_city_combo") else -1
            cities = (
                self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
            )
            if 0 <= sel_idx < len(cities):
                city_id = cities[sel_idx].id
        if not city_id and self.roster and self.roster.bases:
            city_id = self.roster.bases[0].id
        if not city_id:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn căn cứ cần tải công trình!")
            return

        base_name = str(city_id)
        if self.roster:
            b = self.roster.base_by_id(city_id)
            if b:
                base_name = b.name

        self._append_bld_log(f"🔄 Đang tải dữ liệu công trình thực tế cho {base_name}...")
        threading.Thread(target=self._fetch_city_buildings_thread, args=(city_id,), daemon=True).start()

    def _fetch_city_buildings_thread(self, city_id: int):
        try:
            resp = self.gateway.building_list(city_id) or {}
            raw_items = resp.get("items") or resp.get("infos") or []
            buildings = []
            for b in raw_items:
                if isinstance(b, dict):
                    buildings.append(
                        {
                            "pid": int(b.get("m_lpos") if b.get("m_lpos") is not None else b.get("pid", 0)),
                            "gid": int(b.get("m_lgid") or b.get("gid", 0)),
                            "level": int(b.get("m_llevel") if b.get("m_llevel") is not None else b.get("level", 0)),
                            "name": str(b.get("m_szname") or b.get("name") or ""),
                        }
                    )
            try:
                self.after(0, self._update_city_buildings_ui, buildings, city_id)
            except Exception:
                pass
        except Exception as e:
            try:
                self.after(0, lambda: self._append_bld_log(f"❌ Lỗi tải công trình căn cứ {city_id}: {e}"))
            except Exception:
                pass

    def _sync_city_buildings_data(self, target_city_id: Optional[int], buildings, from_auto_cycle: bool = False):
        target_city_id = target_city_id or self._current_bld_city_id
        if not buildings:
            if not from_auto_cycle:
                self._append_bld_log("ℹ️ Server không trả về dữ liệu công trình.")
            return

        real_map: dict[int, dict] = {}
        if isinstance(buildings, dict):
            for pid_k, b_info in buildings.items():
                try:
                    pid = int(pid_k)
                    if isinstance(b_info, dict):
                        real_map[pid] = {
                            "gid": int(b_info.get("gid", 0)),
                            "level": int(b_info.get("level", 0)),
                            "name": b_info.get("name", ""),
                        }
                    elif isinstance(b_info, (list, tuple)) and len(b_info) >= 4:
                        real_map[pid] = {
                            "gid": int(b_info[1]),
                            "level": int(b_info[3]),
                            "name": str(b_info[2]) if len(b_info) > 2 else "",
                        }
                except (ValueError, TypeError):
                    pass
        elif isinstance(buildings, (list, tuple)):
            for b in buildings:
                if isinstance(b, dict):
                    pid = int(b.get("pid", 0))
                    real_map[pid] = {
                        "gid": int(b.get("gid", 0)),
                        "level": int(b.get("level", 0)),
                        "name": b.get("name", ""),
                    }
                elif isinstance(b, (list, tuple)) and len(b) >= 4:
                    pid = int(b[0])
                    real_map[pid] = {
                        "gid": int(b[1]),
                        "level": int(b[3]),
                        "name": str(b[2]) if len(b) > 2 else "",
                    }

        if not real_map:
            return

        base_name = str(target_city_id) if target_city_id else ""
        if self.roster and target_city_id:
            b = self.roster.base_by_id(target_city_id)
            if b:
                base_name = b.name

        cached_plans = list(self._city_building_plans.get(target_city_id, []))

        seen_pids = set()
        new_plans = []
        level_changes = []

        if not cached_plans:
            for pid, r_info in real_map.items():
                gid = int(r_info.get("gid", 1))
                name = BUILDING_NAMES.get(gid, r_info.get("name") or f"Công trình {gid}")
                lvl = int(r_info.get("level", 0))
                new_plans.append(
                    {
                        "pid": pid,
                        "gid": gid,
                        "name": name,
                        "cur_lvl": lvl,
                        "target_level": max(lvl + 1, 20),
                        "enabled": False,
                    }
                )
        else:
            for p in cached_plans:
                pid = int(p.get("pid", 0))
                if pid not in real_map:
                    continue
                seen_pids.add(pid)
                plan_entry = dict(p)
                r_info = real_map[pid]
                old_lvl = int(p.get("cur_lvl", 0))
                new_lvl = int(r_info.get("level", 0))
                if new_lvl != old_lvl:
                    level_changes.append((pid, plan_entry.get("name") or f"Ô {pid}", old_lvl, new_lvl))
                plan_entry["cur_lvl"] = new_lvl
                if r_info.get("gid"):
                    plan_entry["gid"] = r_info["gid"]
                    plan_entry["name"] = BUILDING_NAMES.get(
                        r_info["gid"], r_info.get("name") or plan_entry.get("name", "")
                    )
                new_plans.append(plan_entry)

            for pid, r_info in real_map.items():
                if pid not in seen_pids:
                    gid = int(r_info.get("gid", 1))
                    name = BUILDING_NAMES.get(gid, r_info.get("name") or f"Công trình {gid}")
                    lvl = int(r_info.get("level", 0))

                    same_gid_plans = [p for p in cached_plans if int(p.get("gid", 0)) == gid]
                    if same_gid_plans and all(p.get("enabled", True) for p in same_gid_plans):
                        group_target_lvl = int(same_gid_plans[0].get("target_level", max(lvl + 1, 20)))
                        new_plan = {
                            "pid": pid,
                            "gid": gid,
                            "name": name,
                            "cur_lvl": lvl,
                            "target_level": group_target_lvl,
                            "enabled": True,
                        }
                        if hasattr(self, "_append_bld_log"):
                            self._append_bld_log(
                                f"✨ [{base_name}] Ô đất mới {pid} ({name}) tự động kết nạp vào nhóm & đặt Cấp MT = {group_target_lvl}."
                            )
                    else:
                        new_plan = {
                            "pid": pid,
                            "gid": gid,
                            "name": name,
                            "cur_lvl": lvl,
                            "target_level": lvl,
                            "enabled": False,
                        }
                    new_plans.append(new_plan)

        has_struct_change = new_plans != cached_plans
        if target_city_id is not None:
            self._city_building_plans[target_city_id] = new_plans

        if (
            (target_city_id == self._current_bld_city_id or self._current_bld_city_id is None)
            and hasattr(self, "bld_tree")
            and (not from_auto_cycle or has_struct_change or level_changes)
        ):
            sel = self.bld_tree.selection()
            self._render_bld_tree_from_plans(new_plans)
            if sel and self.bld_tree.exists(sel[0]):
                try:
                    self.bld_tree.selection_set(sel[0])
                except Exception:
                    pass

        if level_changes:
            ch_str = ", ".join([f"{name} (cấp {ol}➔{nl})" for _, name, ol, nl in level_changes[:3]])
            if len(level_changes) > 3:
                ch_str += f", +{len(level_changes)-3} công trình khác"
            self._append_bld_log(f"🔄 [{base_name}] Đã đồng bộ thực tế: {ch_str}")
        elif not from_auto_cycle:
            self._append_bld_log(
                f"🔄 Đã nạp thành công {len(new_plans)} công trình thực tế của {base_name} (bảo toàn thứ tự ưu tiên)."
            )

    def _update_city_buildings_ui(self, buildings, city_id: Optional[int] = None):
        self._sync_city_buildings_data(city_id, buildings, from_auto_cycle=False)

    def _load_build_plans(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        plan_path = Path("build_plans.json") if Path("build_plans.json").exists() else Path("build_plans.example.json")
        if not plan_path.exists():
            messagebox.showerror("Lỗi", "Không tìm thấy file build_plans.json hoặc build_plans.example.json!")
            return
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        cities_data = data.get("cities", {})
        plans_list = data.get("plans", [])
        if cities_data and not plans_list:
            for _cid, cinfo in cities_data.items():
                plans_list.extend(cinfo.get("plans", []))

        if plans_list:
            self._render_bld_tree_from_plans(plans_list)
        self._append_bld_log(f"📂 Đã nạp danh sách {len(plans_list)} quy hoạch công trình.")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _save_build_plans(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        self._save_current_bld_tree_to_cache()
        plans = self._city_building_plans.get(self._current_bld_city_id, [])
        if not plans:
            plans = self._collect_bld_plans_from_tree()
        Path("build_plans.json").write_text(json.dumps({"plans": plans}, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_bld_log(f"💾 Đã lưu cấu hình {len(plans)} công trình ra build_plans.json")
        messagebox.showinfo("Thành công", "Đã lưu cấu hình ra build_plans.json!")

    def _parse_bld_speedup_hours(self) -> float:
        """Phân tích ngưỡng giờ tăng tốc xây dựng (hỗ trợ '24', '24h', '24,5')."""
        raw = self.bld_speedup_hours_var.get().strip() if hasattr(self, "bld_speedup_hours_var") else "1"
        if not raw:
            return 1.0
        cleaned = raw.lower().replace(",", ".").replace("giờ", "").replace("gio", "").replace("h", "").strip()
        try:
            return max(0.0, float(cleaned or "1"))
        except ValueError:
            return 1.0

    def _get_bld_speedup_paytype(self) -> int:
        if hasattr(self, "bld_speedup_item_combo") and self.bld_speedup_item_combo.get() == "Coin":
            return 1
        return 2

    def _sync_running_bld_speedup(self, *_args):
        """Đồng bộ tức thì thiết lập tăng tốc xây dựng vào các BuildingTask đang chạy."""
        runner = getattr(self, "_bld_runner", None)
        if not runner or not getattr(runner, "tasks", None):
            return
        auto_speedup = bool(self.bld_speedup_var.get()) if hasattr(self, "bld_speedup_var") else False
        spd_hours = self._parse_bld_speedup_hours()
        spd_paytype = self._get_bld_speedup_paytype()
        for task in runner.tasks:
            task.auto_speedup = auto_speedup
            task.speedup_hours = spd_hours
            task.paytype = spd_paytype

    def _toggle_building(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        BuildingTask = resolve_dashboard_symbol("BuildingTask", _DefaultBuildingTask)
        BuildingAutoRunner = resolve_dashboard_symbol("BuildingAutoRunner", _DefaultBuildingAutoRunner)

        if not self._bld_runner or not self._bld_runner.is_alive():
            self._save_current_bld_tree_to_cache()

            valid_base_ids = (
                {b.id for b in self.roster.bases} if (self.roster and self.roster.bases) else None
            )
            selected_cids = [
                cid for cid in self._selected_building_cities
                if valid_base_ids is None or cid in valid_base_ids
            ]
            if not selected_cids:
                if self._current_bld_city_id:
                    selected_cids = [self._current_bld_city_id]
                elif hasattr(self, "bld_city_combo"):
                    sel_idx = self.bld_city_combo.current()
                    cities = (
                        self.roster.cities
                        if (self.roster and self.roster.cities)
                        else (self.roster.bases if self.roster else [])
                    )
                    if 0 <= sel_idx < len(cities):
                        selected_cids = [cities[sel_idx].id]

            if not selected_cids:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 căn cứ để nâng cấp công trình!")
                return

            try:
                max_slots = (
                    int(self.bld_slots_combo.get())
                    if hasattr(self, "bld_slots_combo") and self.bld_slots_combo.get()
                    else 3
                )
            except (ValueError, TypeError):
                max_slots = 3

            tasks: list[BuildingTask] = []
            for cid in selected_cids:
                plan_dicts = self._city_building_plans.get(cid)
                if not plan_dicts and cid == self._current_bld_city_id:
                    plan_dicts = self._collect_bld_plans_from_tree()

                if not plan_dicts:
                    continue

                plans = [
                    BuildingPlan(
                        pid=int(p["pid"]),
                        gid=int(p["gid"]),
                        target_level=int(p["target_level"]),
                        name=p.get("name", ""),
                        enabled=bool(p.get("enabled", True)),
                    )
                    for p in plan_dicts
                    if p.get("enabled", True)
                ]
                if not plans:
                    continue

                base_name = f"Căn cứ {cid}"
                if self.roster:
                    b = self.roster.base_by_id(cid)
                    if b:
                        base_name = b.name
                box_id = 24
                if hasattr(self, "bld_box_combo") and self.bld_box_combo.get():
                    try:
                        box_id = int(self.bld_box_combo.get().split(":")[0].strip())
                    except (ValueError, IndexError):
                        box_id = 24
                max_boxes = 5
                if hasattr(self, "bld_box_max_var") and self.bld_box_max_var.get():
                    try:
                        max_boxes = int(self.bld_box_max_var.get())
                    except ValueError:
                        max_boxes = 5

                auto_open_box = bool(self.bld_open_box_var.get()) if hasattr(self, "bld_open_box_var") else False
                auto_fallback_box = (
                    bool(self.bld_box_fallback_var.get()) if hasattr(self, "bld_box_fallback_var") else True
                )
                city_auto_open_box = auto_open_box and (cid in self._selected_resource_cities)

                spd_hours = self._parse_bld_speedup_hours()
                spd_paytype = self._get_bld_speedup_paytype()

                task = BuildingTask(
                    gateway=self.gateway,
                    city_id=cid,
                    plans=plans,
                    max_slots=max_slots,
                    auto_speedup=self.bld_speedup_var.get(),
                    speedup_hours=spd_hours,
                    paytype=spd_paytype,
                    auto_boost=self.bld_boost_var.get(),
                    auto_comfort=self.bld_comfort_var.get(),
                    auto_open_box=city_auto_open_box,
                    box_id=box_id,
                    max_boxes_per_round=max_boxes,
                    auto_fallback_box=auto_fallback_box,
                    even_upgrade=False,
                    notify=lambda m, cname=base_name: self.after(0, self._append_bld_log, f"[{cname}] {m}"),
                    city_name=base_name,
                    on_sync_data=lambda target_cid, rdata: self.after(
                        0, self._sync_city_buildings_data, target_cid, rdata, True
                    ),
                    on_city_missing=lambda _missing_cid: self.after(0, self.reload),
                )
                tasks.append(task)

            if not tasks:
                messagebox.showwarning(
                    "Cảnh báo", "Vui lòng tích chọn ít nhất 1 công trình cần nâng cấp trong các căn cứ đã chọn!"
                )
                return

            try:
                bld_interval = max(3.0, float(self.bld_interval_var.get() or "20"))
            except ValueError:
                bld_interval = 20.0

            self._bld_runner = BuildingAutoRunner(
                tasks,
                interval=bld_interval,
                log_cb=lambda m: self.after(0, self._append_bld_log, m),
                status_cb=lambda _s: None,
                sync_cb=lambda target_cid, rdata: self.after(0, self._sync_city_buildings_data, target_cid, rdata, True),
            )
            self._bld_runner.start()
            self.bld_start_btn.configure(text="Đang Xây", style="Success.TButton")
        else:
            self._bld_runner.stop()
            self.bld_start_btn.configure(text="Xây", style="Danger.TButton")
            self._save_current_bld_tree_to_cache()
