"""Tab Gọi Man & Vong Linh trên giao diện Dashboard."""

import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..battle import ATTACK_ACTION_COMBO_OPTIONS
from ..locks import TargetLocks
from ..roster import fetch_roster as _default_fetch_roster
from ..scan import Scanner
from ..tasks.base import TaskContext
from ..tasks.binh_man import MAN_TARGET_OPTIONS
from ..tasks.goi_dan import GoiDan
from ..tasks.morale import MoraleTrainer as _DefaultMoraleTrainer
from ..tasks.thao_phat import ERROR_MESSAGES, TargetArmy
from ..troops import ArmyProvisioner
from .runners import GoiDanAutoRunner
from .shared import (
    BG,
    CARD,
    FG,
    MultiSelectDropdown,
    _LegacyComboAdapter,
    apply_action_mode_widgets,
    resolve_dashboard_symbol,
    sync_action_mode_from_combo,
)


class GoiDanMixin:
    """Quản lý giao diện, cấu hình hồ sơ và tác vụ Gọi Man / Vong Linh."""

    def _collect_goi_dan_profile_dict(self) -> dict:
        gd_city_id = None
        if hasattr(self, "gd_city_combo") and self.roster and self.roster.cities:
            gd_idx = self.gd_city_combo.current()
            if 0 <= gd_idx < len(self.roster.cities):
                gd_city_id = self.roster.cities[gd_idx].id
        elif getattr(self, "_pending_gd_city_id", None) is not None:
            gd_city_id = self._pending_gd_city_id

        gd_gens = []
        if hasattr(self, "gd_gen_tree") and self.gd_gen_tree.get_children():
            gd_gens = [
                int(iid)
                for iid in self.gd_gen_tree.get_children()
                if self.gd_gen_tree.item(iid, "values")[0] == "☑"
            ]
        elif getattr(self, "_pending_gd_generals", None):
            gd_gens = sorted(self._pending_gd_generals)

        return {
            "city_id": gd_city_id,
            "mode_idx": self.gd_mode_combo.current() if hasattr(self, "gd_mode_combo") else 0,
            "target_type": self._get_gd_target_type() if hasattr(self, "_get_gd_target_type") else 301,
            "target_types": self.gd_target_dropdown.get_selected() if hasattr(self, "gd_target_dropdown") else [301],
            "radius": self.gd_radius_var.get() if hasattr(self, "gd_radius_var") else "5",
            "auto_recover": bool(self.gd_recover_var.get()) if hasattr(self, "gd_recover_var") else True,
            "interval": self.gd_interval_var.get() if hasattr(self, "gd_interval_var") else "10",
            "generals": gd_gens,
            "target_infantry": self.gd_target_inf_var.get() if hasattr(self, "gd_target_inf_var") else "0",
            "target_cavalry": self.gd_target_cav_var.get() if hasattr(self, "gd_target_cav_var") else "0",
            "target_archers": self.gd_target_arc_var.get() if hasattr(self, "gd_target_arc_var") else "0",
            "auto_recruit": bool(self.gd_auto_recruit_var.get()) if hasattr(self, "gd_auto_recruit_var") else True,
            "auto_morale": bool(self.gd_auto_morale_var.get()) if hasattr(self, "gd_auto_morale_var") else True,
            "min_morale": self.gd_min_morale_var.get() if hasattr(self, "gd_min_morale_var") else "95",
            "attack_action_mode": self.gd_action_mode_var.get() if hasattr(self, "gd_action_mode_var") else "adaptive",
            "action_combo_idx": self.gd_action_mode_combo.current() if hasattr(self, "gd_action_mode_combo") else 0,
        }

    def _apply_goi_dan_profile_dict(self, gd_data: dict) -> None:
        if hasattr(self, "gd_target_dropdown"):
            if "target_types" in gd_data and gd_data["target_types"]:
                self.gd_target_dropdown.set_selected(gd_data["target_types"])
            elif "target_type" in gd_data:
                self.gd_target_dropdown.set_selected([int(gd_data["target_type"])])
            elif "mode_idx" in gd_data:
                try:
                    self.gd_mode_combo.current(int(gd_data["mode_idx"]))
                except Exception:
                    pass
        elif hasattr(self, "gd_mode_combo"):
            if "target_type" in gd_data:
                ttype = int(gd_data["target_type"])
                for idx, (t, _) in enumerate(getattr(self, "gd_target_options", [])):
                    if t == ttype:
                        self.gd_mode_combo.current(idx)
                        break
            elif "mode_idx" in gd_data:
                try:
                    self.gd_mode_combo.current(int(gd_data["mode_idx"]))
                except Exception:
                    pass
        if hasattr(self, "gd_radius_var") and "radius" in gd_data:
            self.gd_radius_var.set(str(gd_data["radius"]))
        if hasattr(self, "gd_recover_var") and "auto_recover" in gd_data:
            self.gd_recover_var.set(bool(gd_data["auto_recover"]))
        if hasattr(self, "gd_interval_var") and "interval" in gd_data:
            self.gd_interval_var.set(str(gd_data["interval"]))
        if hasattr(self, "gd_target_inf_var") and "target_infantry" in gd_data:
            self.gd_target_inf_var.set(str(gd_data["target_infantry"]))
        if hasattr(self, "gd_target_cav_var") and "target_cavalry" in gd_data:
            self.gd_target_cav_var.set(str(gd_data["target_cavalry"]))
        if hasattr(self, "gd_target_arc_var") and "target_archers" in gd_data:
            self.gd_target_arc_var.set(str(gd_data["target_archers"]))
        if hasattr(self, "gd_auto_recruit_var") and "auto_recruit" in gd_data:
            self.gd_auto_recruit_var.set(bool(gd_data["auto_recruit"]))
        if hasattr(self, "gd_auto_morale_var") and "auto_morale" in gd_data:
            self.gd_auto_morale_var.set(bool(gd_data["auto_morale"]))
        if hasattr(self, "gd_min_morale_var") and "min_morale" in gd_data:
            self.gd_min_morale_var.set(str(gd_data["min_morale"]))
        apply_action_mode_widgets(
            getattr(self, "gd_action_mode_var", None),
            getattr(self, "gd_action_mode_combo", None),
            gd_data.get("attack_action_mode") if "attack_action_mode" in gd_data else None,
            gd_data.get("action_combo_idx") if "action_combo_idx" in gd_data else None,
        )
        if "city_id" in gd_data and gd_data["city_id"] is not None:
            try:
                self._pending_gd_city_id = int(gd_data["city_id"])
            except (ValueError, TypeError):
                pass
        if "generals" in gd_data and isinstance(gd_data["generals"], list):
            gd_gens = [int(x) for x in gd_data["generals"] if str(x).isdigit()]
            self._pending_gd_generals = set(gd_gens)
            target_cid = int(gd_data["city_id"]) if ("city_id" in gd_data and str(gd_data["city_id"]).isdigit()) else None
            if not target_cid and gd_gens and self.roster and self.roster.cities:
                for c in self.roster.cities:
                    c_gens = {g.id for g in self.roster.generals_of(c.id)}
                    if any(gid in c_gens for gid in gd_gens):
                        target_cid = c.id
                        break
            if target_cid and hasattr(self, "gd_city_combo") and self.roster and self.roster.cities:
                for idx, c in enumerate(self.roster.cities):
                    if c.id == target_cid:
                        if self.gd_city_combo.current() != idx:
                            self.gd_city_combo.current(idx)
                            self._on_gd_city_selected()
                        break
            if hasattr(self, "gd_gen_tree") and self.gd_gen_tree.get_children():
                for iid in self.gd_gen_tree.get_children():
                    vals = list(self.gd_gen_tree.item(iid, "values"))
                    vals[0] = "☑" if int(iid) in self._pending_gd_generals else "☐"
                    self.gd_gen_tree.item(iid, values=vals)
                self._update_gd_gen_count_label()
        elif getattr(self, "_pending_gd_city_id", None) and hasattr(self, "gd_city_combo") and self.roster and self.roster.cities:
            for idx, c in enumerate(self.roster.cities):
                if c.id == self._pending_gd_city_id:
                    if self.gd_city_combo.current() != idx:
                        self.gd_city_combo.current(idx)
                        self._on_gd_city_selected()
                    break

    def _build_goidan_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=6)

        tk.Label(top, text="Thành trì:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.gd_city_combo = ttk.Combobox(top, state="readonly", width=20)
        self.gd_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.gd_city_combo.bind("<<ComboboxSelected>>", self._on_gd_city_selected)

        tk.Label(top, text="Loại Man mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.gd_target_options = MAN_TARGET_OPTIONS
        self.gd_target_dropdown = MultiSelectDropdown(top, options=self.gd_target_options, default_selected=[301], width=22)
        self.gd_target_dropdown.grid(row=0, column=3, sticky="w", padx=4, pady=4)
        self.gd_mode_combo = _LegacyComboAdapter(self.gd_target_dropdown)

        tk.Label(top, text="Bán kính quét:", bg=BG, fg=FG).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.gd_radius_var = tk.StringVar(value="5")
        ttk.Entry(top, textvariable=self.gd_radius_var, width=8).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Chu kỳ (s):", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.gd_interval_var = tk.StringVar(value="10")
        ttk.Entry(top, textvariable=self.gd_interval_var, width=8).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        # Row 2: Định mức quân đội (Bộ MT, Kỵ MT, Cung MT) & Nút Biên chế ngay
        tk.Label(top, text="Bộ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.gd_target_inf_var = tk.StringVar(value="0")
        ttk.Entry(top, textvariable=self.gd_target_inf_var, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        army_f = tk.Frame(top, bg=BG)
        army_f.grid(row=2, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        tk.Label(army_f, text="Kỵ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.gd_target_cav_var = tk.StringVar(value="0")
        ttk.Entry(army_f, textvariable=self.gd_target_cav_var, width=6).pack(side="left", padx=(0, 6))

        tk.Label(army_f, text="Cung MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.gd_target_arc_var = tk.StringVar(value="0")
        ttk.Entry(army_f, textvariable=self.gd_target_arc_var, width=6).pack(side="left", padx=(0, 8))

        self.gd_adjust_troops_btn = ttk.Button(army_f, text="⚔️ Biên chế ngay", style="Action.TButton", command=self._manual_adjust_gd_troops)
        self.gd_adjust_troops_btn.pack(side="left", padx=(0, 4))

        # Row 3: Tự động bổ sung lính, Tự động nâng sĩ khí, Sĩ khí tối thiểu
        self.gd_auto_recruit_var = tk.BooleanVar(value=True)
        self.gd_recover_var = self.gd_auto_recruit_var  # Giữ alias tương thích ngược
        ttk.Checkbutton(
            top,
            text="Tự động bổ sung lính",
            variable=self.gd_auto_recruit_var,
            style="TCheckbutton",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        mor_f = tk.Frame(top, bg=BG)
        mor_f.grid(row=3, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        self.gd_auto_morale_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(mor_f, text="Tự động nâng sĩ khí", variable=self.gd_auto_morale_var, style="TCheckbutton").pack(side="left", padx=(0, 8))
        tk.Label(mor_f, text="Sĩ khí tối thiểu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.gd_min_morale_var = tk.StringVar(value="95")
        ttk.Entry(mor_f, textvariable=self.gd_min_morale_var, width=5).pack(side="left")

        # Row 4: Chiêu tấn công
        tk.Label(top, text="Chiêu tấn công:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w", padx=4, pady=4)
        self.gd_action_mode_var = tk.StringVar(value="adaptive")
        self.gd_action_mode_combo = ttk.Combobox(top, state="readonly", width=24)
        self.gd_action_mode_combo["values"] = list(ATTACK_ACTION_COMBO_OPTIONS)
        self.gd_action_mode_combo.current(0)
        self.gd_action_mode_combo.grid(row=4, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        self.gd_action_mode_combo.bind("<<ComboboxSelected>>", self._on_gd_action_mode_changed)

        # Điều khiển
        ctrl_frame = tk.Frame(top, bg=BG)
        ctrl_frame.grid(row=0, column=4, rowspan=5, padx=16)
        self.gd_start_btn = ttk.Button(ctrl_frame, text="▶️ Bắt đầu Gọi Man", style="Success.TButton", command=self._toggle_goidan)
        self.gd_start_btn.pack(side="top", pady=2)
        self.gd_once_btn = ttk.Button(ctrl_frame, text="⚡ Chạy 1 Lượt", style="Action.TButton", command=self._run_goidan_once)
        self.gd_once_btn.pack(side="top", pady=2)

        # Bảng tướng & Log sắp xếp theo container body
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        # Row 0: Bảng danh sách võ tướng
        f_top = ttk.LabelFrame(body, text="Võ tướng xuất kích", style="Card.TLabelframe")
        f_top.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        btn_bar = tk.Frame(f_top, bg=BG)
        btn_bar.pack(fill="x", padx=4, pady=2)
        ttk.Button(btn_bar, text="✅ Chọn tất cả", style="Secondary.TButton", command=self._select_all_gd_gens).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="❌ Bỏ chọn tất cả", style="Secondary.TButton", command=self._deselect_all_gd_gens).pack(side="left", padx=2)
        self.gd_gen_count_lbl = tk.Label(btn_bar, text="Đã chọn: 0 tướng (0 đợt xuất kích)", bg=BG, fg=FG, font=("Segoe UI", 9, "bold"))
        self.gd_gen_count_lbl.pack(side="left", padx=8)

        self.gd_gen_tree = ttk.Treeview(
            f_top,
            columns=("select", "lv", "stamina", "morale", "infantry", "cavalry", "archers", "total_army"),
            show="tree headings",
            selectmode="browse",
            height=5,
        )
        self.gd_gen_tree.heading("#0", text="Tên võ tướng")
        self.gd_gen_tree.heading("select", text="Chọn")
        self.gd_gen_tree.heading("lv", text="Cấp")
        self.gd_gen_tree.heading("stamina", text="Thể lực")
        self.gd_gen_tree.heading("morale", text="Sĩ khí")
        self.gd_gen_tree.heading("infantry", text="Bộ binh")
        self.gd_gen_tree.heading("cavalry", text="Kỵ binh")
        self.gd_gen_tree.heading("archers", text="Cung binh")
        self.gd_gen_tree.heading("total_army", text="Tổng quân")

        self.gd_gen_tree.column("#0", width=140)
        self.gd_gen_tree.column("select", width=50, anchor="center")
        self.gd_gen_tree.column("lv", width=50, anchor="center")
        self.gd_gen_tree.column("stamina", width=75, anchor="center")
        self.gd_gen_tree.column("morale", width=65, anchor="center")
        self.gd_gen_tree.column("infantry", width=80, anchor="e")
        self.gd_gen_tree.column("cavalry", width=80, anchor="e")
        self.gd_gen_tree.column("archers", width=80, anchor="e")
        self.gd_gen_tree.column("total_army", width=85, anchor="e")

        gen_scroll = ttk.Scrollbar(f_top, orient="vertical", command=self.gd_gen_tree.yview)
        self.gd_gen_tree.configure(yscrollcommand=gen_scroll.set)
        self.gd_gen_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        gen_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))
        self.gd_gen_tree.bind("<ButtonRelease-1>", self._on_gd_gen_toggle)

        # Row 1: Khung nhật ký log Gọi Man & Vong Linh
        f_bottom = ttk.LabelFrame(body, text="Nhật ký Gọi Man & Vong Linh", style="Card.TLabelframe")
        f_bottom.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        log_bar = tk.Frame(f_bottom, bg=CARD)
        log_bar.pack(side="top", fill="x", padx=4, pady=(2, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._gd_clear_log).pack(side="right")

        log_scroll = ttk.Scrollbar(f_bottom, orient="vertical")
        self.gd_log_text = tk.Text(f_bottom, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0, yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.gd_log_text.yview)
        self.gd_log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        log_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))

    def _update_gd_gen_count_label(self):
        if not hasattr(self, "gd_gen_count_lbl") or not hasattr(self, "gd_gen_tree"):
            return
        selected_count = sum(1 for item in self.gd_gen_tree.get_children() if self.gd_gen_tree.item(item, "values")[0] == "☑")
        batches = (selected_count + 2) // 3 if selected_count > 0 else 0
        self.gd_gen_count_lbl.config(text=f"Đã chọn: {selected_count} tướng ({batches} đợt xuất kích)")

    def _select_all_gd_gens(self):
        for item in self.gd_gen_tree.get_children():
            vals = list(self.gd_gen_tree.item(item, "values"))
            vals[0] = "☑"
            self.gd_gen_tree.item(item, values=vals)
        self._update_gd_gen_count_label()
        self._schedule_auto_save()

    def _deselect_all_gd_gens(self):
        for item in self.gd_gen_tree.get_children():
            vals = list(self.gd_gen_tree.item(item, "values"))
            vals[0] = "☐"
            self.gd_gen_tree.item(item, values=vals)
        self._update_gd_gen_count_label()
        self._schedule_auto_save()

    def _on_gd_gen_toggle(self, event):
        item = self.gd_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.gd_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.gd_gen_tree.item(item, values=vals)
        self._update_gd_gen_count_label()
        self._schedule_auto_save()

    def _on_gd_city_selected(self, _event=None):
        sel_idx = self.gd_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else []
        if sel_idx < 0 or sel_idx >= len(cities):
            return
        city = cities[sel_idx]
        self.gd_gen_tree.delete(*self.gd_gen_tree.get_children())
        pending = self._pending_gd_generals
        count = 0
        for g in self.roster.generals_of(city.id):
            if g.role != "vo":
                continue
            army = self.roster.army_of(g.id)
            inf = army.infantry if army else 0
            cav = army.cavalry if army else 0
            arc = army.archers if army else 0
            total = army.total if army else 0
            if pending is not None:
                checked = "☑" if g.id in pending else "☐"
            else:
                checked = "☑" if count < 3 else "☐"
            self.gd_gen_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(checked, g.level, f"{g.stamina}/{g.stamina_max}", g.morale, inf, cav, arc, total),
            )
            count += 1
        self._pending_gd_generals = None
        self._update_gd_gen_count_label()

    def _append_gd_log(self, msg: str):
        self._append_text_buffer(self.gd_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _gd_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Gọi Man."""
        if hasattr(self, "gd_log_text") and self.gd_log_text:
            self.gd_log_text.delete("1.0", "end")

    def _on_gd_action_mode_changed(self, _event=None):
        if hasattr(self, "gd_action_mode_combo") and hasattr(self, "gd_action_mode_var"):
            sync_action_mode_from_combo(self.gd_action_mode_var, self.gd_action_mode_combo)

    def _get_gd_target_type(self) -> int:
        if hasattr(self, "gd_target_dropdown"):
            sel = self.gd_target_dropdown.get_selected()
            if sel:
                return sel[0]
        sel_idx = self.gd_mode_combo.current() if hasattr(self, "gd_mode_combo") else 0
        if 0 <= sel_idx < len(getattr(self, "gd_target_options", [])):
            return self.gd_target_options[sel_idx][0]
        return 301

    def _create_goidan_task(self) -> Optional[GoiDan]:
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel_idx = self.gd_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else []
        if sel_idx < 0 or sel_idx >= len(cities):
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
            return None
        city = cities[sel_idx]

        sel_gens = []
        if hasattr(self, "gd_gen_tree"):
            sel_gens = [int(iid) for iid in self.gd_gen_tree.get_children() if self.gd_gen_tree.item(iid, "values")[0] == "☑"]

        if not sel_gens:
            vos = [g.id for g in self.roster.generals_of(city.id) if g.role == "vo"]
            if not vos:
                msgbox.showwarning("Cảnh báo", "Thành này không có võ tướng khả dụng!")
                return None
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng xuất kích!")
            return None

        target_types = self.gd_target_dropdown.get_selected() if hasattr(self, "gd_target_dropdown") else []
        if not target_types:
            target_types = [self._get_gd_target_type()]
        target_type = target_types[0]
        mode = "vong_linh" if target_type == 301 else "dan"
        radius = int(self.gd_radius_var.get() or "5")
        locks = getattr(self, "shared_target_locks", None) or TargetLocks()
        scanner = Scanner(
            self.gateway,
            locks,
            delay=0.0,
            sleep=lambda s: None,
            map_cache_ttl=4.0,
            capitals_cache_ttl=300.0,
        )
        ctx = TaskContext(self.gateway, scanner, locks, notify=lambda m: self.after(0, self._append_gd_log, m))

        try:
            target_inf = int(self.gd_target_inf_var.get() or "0")
        except ValueError:
            target_inf = 0
        try:
            target_cav = int(self.gd_target_cav_var.get() or "0")
        except ValueError:
            target_cav = 0
        try:
            target_arc = int(self.gd_target_arc_var.get() or "0")
        except ValueError:
            target_arc = 0
        try:
            min_morale = int(self.gd_min_morale_var.get() or "95")
        except ValueError:
            min_morale = 95

        target_army = TargetArmy(infantry=target_inf, cavalry=target_cav, archers=target_arc)
        auto_recruit = bool(self.gd_auto_recruit_var.get()) if hasattr(self, "gd_auto_recruit_var") else True
        auto_morale = bool(self.gd_auto_morale_var.get()) if hasattr(self, "gd_auto_morale_var") else True
        gd_combo_val = self.gd_action_mode_combo.get() if hasattr(self, "gd_action_mode_combo") else None

        return GoiDan(
            ctx=ctx,
            generals=sel_gens,
            origin=(city.pos_x, city.pos_y) if hasattr(city, "pos_x") else (0, 0),
            radius=radius,
            mode=mode,
            target_type=target_type,
            target_types=target_types,
            city_id=city.id,
            auto_recover=self.gd_recover_var.get(),
            refill_amount=500,
            sleep_fn=time.sleep,
            combat_config=self._build_combat_config(action_combo_val=gd_combo_val),
            on_battle_found=lambda bid: self.after(
                0, lambda b=bid: self.bt_id_var.set(str(b)) if hasattr(self, "bt_id_var") else None
            ),
            on_battle_state=lambda st: self.after(
                0, lambda s=st: self._bt_render_state(s) if hasattr(self, "_bt_render_state") else None
            ),
            target_army=target_army,
            auto_recruit=auto_recruit,
            auto_morale=auto_morale,
            min_morale=min_morale,
        )

    def _manual_adjust_gd_troops(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster_fn = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        trainer_cls = resolve_dashboard_symbol("MoraleTrainer", _DefaultMoraleTrainer)
        sel_idx = self.gd_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else []
        if sel_idx < 0 or sel_idx >= len(cities):
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
            return
        city_id = cities[sel_idx].id
        sel_gens = [int(iid) for iid in self.gd_gen_tree.get_children() if self.gd_gen_tree.item(iid, "values")[0] == "☑"]
        if not sel_gens:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng!")
            return

        try:
            target_inf = int(self.gd_target_inf_var.get() or "0")
        except ValueError:
            target_inf = 0
        try:
            target_cav = int(self.gd_target_cav_var.get() or "0")
        except ValueError:
            target_cav = 0
        try:
            target_arc = int(self.gd_target_arc_var.get() or "0")
        except ValueError:
            target_arc = 0
        try:
            min_morale = int(self.gd_min_morale_var.get() or "95")
        except ValueError:
            min_morale = 95

        target_army = TargetArmy(infantry=target_inf, cavalry=target_cav, archers=target_arc)
        auto_recruit = bool(self.gd_auto_recruit_var.get()) if hasattr(self, "gd_auto_recruit_var") else True
        auto_morale = bool(self.gd_auto_morale_var.get()) if hasattr(self, "gd_auto_morale_var") else True

        def _worker():
            try:
                self.after(0, self._append_gd_log, "⚔️ Bắt đầu tiến trình biên chế Gọi Man & Luyện sĩ khí...")
                prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)

                # 1. Trị thương
                for gid in sel_gens:
                    prov.heal_general(city_id, gid)

                # 2. Bổ sung lính
                if target_army.total > 0 and auto_recruit:
                    total_needed = 0
                    fresh_roster = fetch_roster_fn(self.gateway, only_base_ids=[city_id])
                    for gid in sel_gens:
                        army = fresh_roster.army_of(gid)
                        cur_inf = army.infantry if army else 0
                        cur_cav = army.cavalry if army else 0
                        cur_arc = army.archers if army else 0
                        total_needed += max(0, target_army.infantry - cur_inf)
                        total_needed += max(0, target_army.cavalry - cur_cav)
                        total_needed += max(0, target_army.archers - cur_arc)

                    if total_needed > 0:
                        avail = prov.check_recruits(city_id)
                        if avail is not None and avail < total_needed:
                            missing = total_needed - avail
                            self.after(0, self._append_gd_log, f"📦 [Tân binh] Kho có {avail}/{total_needed}, tự động chiêu mộ thêm {missing} tân binh...")
                            b_succ, b_ret = prov.buy_recruits(city_id, missing)
                            if b_succ:
                                self.after(0, self._append_gd_log, f"   [Chiêu mộ] ✅ Đã chiêu mộ thành công {missing} tân binh!")
                            else:
                                err_desc = ERROR_MESSAGES.get(b_ret, f"Mã lỗi: {b_ret}")
                                self.after(0, self._append_gd_log, f"   [Chiêu mộ] ⚠️ Chiêu mộ thất bại ({err_desc})")

                    city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
                    troops_added = False
                    for gid in sel_gens:
                        g = city_gens.get(gid)
                        gname = g.name if g else str(gid)
                        cur_army = fresh_roster.army_of(gid)
                        results = prov.adjust_troops(
                            base_id=city_id,
                            general_id=gid,
                            current_army=cur_army,
                            target_army=target_army,
                            auto_recruit=True,
                            on_log=lambda m: self.after(0, self._append_gd_log, m),
                        )
                        if results:
                            for stype, diff, succ, ret_code in results:
                                tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(stype, "Quân")
                                if succ:
                                    if diff > 0:
                                        troops_added = True
                                    self.after(0, self._append_gd_log, f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ✅ Thành công")
                                else:
                                    err_desc = ERROR_MESSAGES.get(ret_code, f"Mã lỗi: {ret_code}")
                                    self.after(0, self._append_gd_log, f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ❌ Thất bại ({err_desc})")
                        else:
                            self.after(0, self._append_gd_log, f"   [Biên chế] Tướng {gname}: Quân số đã đủ, không cần bổ sung.")
                else:
                    fresh_roster = None
                    city_gens = {}
                    troops_added = False

                # 3. Luyện sĩ khí đồng loạt bằng MoraleTrainer (ADR-0032)
                if auto_morale:
                    if fresh_roster is None:
                        fresh_roster = fetch_roster_fn(
                            self.gateway,
                            only_base_ids=[city_id],
                            include_civil=False,
                            include_cities=False,
                        )
                        city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
                    trainer = trainer_cls(self.gateway)

                    def _on_notify_gd(msg):
                        self.after(0, self._append_gd_log, f"   {msg}")

                    trainer.adjust_squad_morale(
                        base_id=city_id,
                        general_ids=sel_gens,
                        target_morale=min_morale,
                        base_gens=city_gens,
                        on_notify=_on_notify_gd,
                        refresh_from_server=troops_added,
                    )

                self.after(0, self._append_gd_log, "🏁 Hoàn tất tiến trình biên chế Gọi Man!")
                new_roster = fetch_roster_fn(self.gateway)
                self.roster = new_roster
                self.after(0, self._on_gd_city_selected)
            except Exception as e:
                self.after(0, self._append_gd_log, f"❌ Lỗi ngoại lệ khi biên chế: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _run_goidan_once(self):
        task = self._create_goidan_task()
        if not task:
            return
        threading.Thread(target=lambda: self.after(0, self._append_gd_log, f"⚡ Kết quả chạy 1 lượt: {task.run_once()}"), daemon=True).start()

    def _toggle_goidan(self):
        if not self._gd_runner or not self._gd_runner.is_alive():
            task = self._create_goidan_task()
            if not task:
                return
            try:
                gd_interval = max(3.0, float(self.gd_interval_var.get() or "10"))
            except ValueError:
                gd_interval = 10.0
            self._gd_runner = GoiDanAutoRunner(
                task,
                interval=gd_interval,
                log_cb=lambda m: self.after(0, self._append_gd_log, m),
                status_cb=lambda s: None,
            )
            self._gd_runner.start()
            self.gd_start_btn.configure(text="⏹️ Dừng Gọi Man", style="Danger.TButton")
        else:
            self._gd_runner.stop()
            self.gd_start_btn.configure(text="▶️ Bắt đầu Gọi Man", style="Success.TButton")
