"""Phân hệ Bình Man Đa Căn Cứ (ADR-0029) trên Dashboard."""

import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..battle import ATTACK_ACTION_COMBO_OPTIONS, parse_attack_action_combo
from ..generals import auto_swap_low_stamina_tacticians, parse_stamina_threshold
from ..profile import BaseBinhManConfig
from ..roster import fetch_roster as _default_fetch_roster
from ..scan import BasePeer, Scanner
from ..tasks.base import CaptchaRequired, TaskContext
from ..tasks.binh_man import MAN_TARGET_OPTIONS, BinhMan
from ..tasks.morale import MoraleTrainer as _DefaultMoraleTrainer
from ..tasks.thao_phat import TargetArmy
from ..troops import ArmyProvisioner
from .runners import BinhManAutoRunner
from .shared import (
    BG,
    CARD,
    FG,
    MultiSelectDropdown,
    apply_action_mode_widgets,
    resolve_dashboard_symbol,
    sync_action_mode_from_combo,
)


class BinhManMixin:
    """Quản lý giao diện, cấu hình từng căn cứ, điều phối và chạy Bình Man."""

    def _collect_binh_man_profile_dict(self) -> dict:
        if hasattr(self, "_save_bm_current_base_config"):
            self._save_bm_current_base_config()
        bm_gens = []
        if hasattr(self, "bm_gen_tree") and self.bm_gen_tree.get_children():
            bm_gens = [
                int(iid)
                for iid in self.bm_gen_tree.get_children()
                if self.bm_gen_tree.item(iid, "values")[0] == "☑"
            ]
        elif getattr(self, "_pending_bm_generals", None):
            bm_gens = sorted(self._pending_bm_generals)

        return {
            "mode": self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1,
            "radius": self.bm_radius_var.get() if hasattr(self, "bm_radius_var") else "5",
            "min_army": self.bm_min_army_var.get() if hasattr(self, "bm_min_army_var") else "3000",
            "min_hp": self.bm_min_hp_var.get() if hasattr(self, "bm_min_hp_var") else "50",
            "auto_comfort": bool(self.bm_comfort_var.get()) if hasattr(self, "bm_comfort_var") else True,
            "interval": self.bm_interval_var.get() if hasattr(self, "bm_interval_var") else "15",
            "camp_id": self.bm_camp_id_var.get() if hasattr(self, "bm_camp_id_var") else "",
            "threshold": self.bm_threshold_var.get() if hasattr(self, "bm_threshold_var") else "30",
            "mantypes": (
                self.bm_mantypes_dropdown.get_selected_str()
                if hasattr(self, "bm_mantypes_dropdown")
                else (self.bm_mantypes_var.get() if hasattr(self, "bm_mantypes_var") else "7,8,9,10")
            ),
            "target_types": (
                self.bm_mantypes_dropdown.get_selected()
                if hasattr(self, "bm_mantypes_dropdown")
                else [7, 8, 9, 10]
            ),
            "generals": bm_gens,
            "target_infantry": self.bm_target_inf_var.get() if hasattr(self, "bm_target_inf_var") else "0",
            "target_cavalry": self.bm_target_cav_var.get() if hasattr(self, "bm_target_cav_var") else "0",
            "target_archers": self.bm_target_arc_var.get() if hasattr(self, "bm_target_arc_var") else "0",
            "auto_recruit": bool(self.bm_auto_recruit_var.get()) if hasattr(self, "bm_auto_recruit_var") else True,
            "even_troops": bool(self.bm_even_troops_var.get()) if hasattr(self, "bm_even_troops_var") else False,
            "auto_morale": bool(self.bm_auto_morale_var.get()) if hasattr(self, "bm_auto_morale_var") else True,
            "min_morale": self.bm_min_morale_var.get() if hasattr(self, "bm_min_morale_var") else "95",
            "auto_swap_tactician": bool(self.bm_auto_swap_tactician_var.get()) if hasattr(self, "bm_auto_swap_tactician_var") else False,
            "min_tactician_stamina": self.bm_min_tactician_stamina_var.get() if hasattr(self, "bm_min_tactician_stamina_var") else "30",
            "attack_action_mode": self.bm_action_mode_var.get() if hasattr(self, "bm_action_mode_var") else "adaptive",
            "action_combo_idx": self.bm_action_mode_combo.current() if hasattr(self, "bm_action_mode_combo") else 0,
            "current_base_id": self._current_bm_base_id,
            "bases": (
                {str(bid): cfg.to_dict() for bid, cfg in self.bm_base_configs.items()}
                if hasattr(self, "bm_base_configs")
                else {}
            ),
        }

    def _apply_binh_man_profile_dict(self, bm_data: dict) -> None:
        if hasattr(self, "bm_mode_var") and "mode" in bm_data:
            try:
                self.bm_mode_var.set(int(bm_data["mode"]))
                if hasattr(self, "_update_bm_mode_ui_states"):
                    self._update_bm_mode_ui_states(int(bm_data["mode"]))
            except Exception:
                pass
        if hasattr(self, "bm_radius_var") and "radius" in bm_data:
            self.bm_radius_var.set(str(bm_data["radius"]))
        if hasattr(self, "bm_min_army_var") and "min_army" in bm_data:
            self.bm_min_army_var.set(str(bm_data["min_army"]))
        if hasattr(self, "bm_min_hp_var") and "min_hp" in bm_data:
            self.bm_min_hp_var.set(str(bm_data["min_hp"]))
        if hasattr(self, "bm_comfort_var") and "auto_comfort" in bm_data:
            self.bm_comfort_var.set(bool(bm_data["auto_comfort"]))
        if hasattr(self, "bm_interval_var") and "interval" in bm_data:
            self.bm_interval_var.set(str(bm_data["interval"]))
        if hasattr(self, "bm_camp_id_var") and "camp_id" in bm_data:
            self.bm_camp_id_var.set(str(bm_data["camp_id"]))
        if hasattr(self, "bm_mantypes_dropdown"):
            if "target_types" in bm_data and bm_data["target_types"]:
                self.bm_mantypes_dropdown.set_selected(bm_data["target_types"])
            elif "mantypes" in bm_data:
                self.bm_mantypes_dropdown.set_selected_str(str(bm_data["mantypes"]))
        if hasattr(self, "bm_mantypes_var") and "mantypes" in bm_data:
            self.bm_mantypes_var.set(str(bm_data["mantypes"]))
        if hasattr(self, "bm_threshold_var") and "threshold" in bm_data:
            self.bm_threshold_var.set(str(bm_data["threshold"]))
        if hasattr(self, "bm_target_inf_var") and "target_infantry" in bm_data:
            self.bm_target_inf_var.set(str(bm_data["target_infantry"]))
        if hasattr(self, "bm_target_cav_var") and "target_cavalry" in bm_data:
            self.bm_target_cav_var.set(str(bm_data["target_cavalry"]))
        if hasattr(self, "bm_target_arc_var") and "target_archers" in bm_data:
            self.bm_target_arc_var.set(str(bm_data["target_archers"]))
        if hasattr(self, "bm_auto_recruit_var") and "auto_recruit" in bm_data:
            self.bm_auto_recruit_var.set(bool(bm_data["auto_recruit"]))
        if hasattr(self, "bm_even_troops_var") and "even_troops" in bm_data:
            self.bm_even_troops_var.set(bool(bm_data["even_troops"]))
        if hasattr(self, "bm_auto_morale_var") and "auto_morale" in bm_data:
            self.bm_auto_morale_var.set(bool(bm_data["auto_morale"]))
        if hasattr(self, "bm_min_morale_var") and "min_morale" in bm_data:
            self.bm_min_morale_var.set(str(bm_data["min_morale"]))
        if hasattr(self, "bm_auto_swap_tactician_var") and "auto_swap_tactician" in bm_data:
            self.bm_auto_swap_tactician_var.set(bool(bm_data["auto_swap_tactician"]))
        if hasattr(self, "bm_min_tactician_stamina_var") and "min_tactician_stamina" in bm_data:
            self.bm_min_tactician_stamina_var.set(str(bm_data["min_tactician_stamina"]))
        apply_action_mode_widgets(
            getattr(self, "bm_action_mode_var", None),
            getattr(self, "bm_action_mode_combo", None),
            bm_data.get("attack_action_mode") if "attack_action_mode" in bm_data else None,
            bm_data.get("action_combo_idx") if "action_combo_idx" in bm_data else None,
        )
        if "current_base_id" in bm_data and bm_data["current_base_id"] is not None:
            try:
                self._current_bm_base_id = int(bm_data["current_base_id"])
            except (ValueError, TypeError):
                pass
        if "bases" in bm_data and isinstance(bm_data["bases"], dict) and bm_data["bases"]:
            self.bm_base_configs.clear()
            self._pending_bm_generals = None
            for bid_str, bcfg_raw in bm_data["bases"].items():
                if isinstance(bcfg_raw, dict):
                    try:
                        bid = int(bid_str)
                        self.bm_base_configs[bid] = BaseBinhManConfig.from_dict(bcfg_raw)
                    except ValueError:
                        pass
            if hasattr(self, "bm_bases_tree") and self.roster:
                self._refresh_bm_bases_tree()
        else:
            # Tương thích ngược tuyệt đối (ADR-0029 Section 1):
            # Tệp hồ sơ cũ chưa có trường 'bases', tự động ánh xạ các giá trị phẳng vào căn cứ đang hoạt động hoặc căn cứ đầu tiên
            bm_gens = [int(x) for x in bm_data.get("generals", []) if str(x).isdigit()] if "generals" in bm_data else []
            m_types_str = str(bm_data.get("mantypes", "7,8,9,10"))
            legacy_cfg = BaseBinhManConfig(
                name="",
                enabled=True,
                mode=int(bm_data.get("mode", 1)),
                radius=str(bm_data.get("radius", "5")),
                threshold=str(bm_data.get("threshold", "30")),
                camp_id=str(bm_data.get("camp_id", "")),
                parent_city_id=str(bm_data.get("parent_city_id", "")),
                mantypes=m_types_str,
                target_types=[int(x.strip()) for x in m_types_str.split(",") if x.strip().isdigit()],
                generals=bm_gens,
                target_infantry=str(bm_data.get("target_infantry", "0")),
                target_cavalry=str(bm_data.get("target_cavalry", "0")),
                target_archers=str(bm_data.get("target_archers", "0")),
                auto_recruit=bool(bm_data.get("auto_recruit", True)),
                even_troops=bool(bm_data.get("even_troops", False)),
                auto_morale=bool(bm_data.get("auto_morale", True)),
                min_morale=str(bm_data.get("min_morale", "95")),
                auto_swap_tactician=bool(bm_data.get("auto_swap_tactician", False)),
                min_tactician_stamina=str(bm_data.get("min_tactician_stamina", "30")),
                attack_action_mode=str(bm_data.get("attack_action_mode", "adaptive")),
                action_combo_idx=int(bm_data.get("action_combo_idx", 0)),
            )
            self._pending_bm_legacy_config = legacy_cfg
            target_bid = None
            if legacy_cfg.mode == 1 and legacy_cfg.camp_id and str(legacy_cfg.camp_id).lstrip("-").isdigit():
                target_bid = int(legacy_cfg.camp_id)
            elif self._current_bm_base_id:
                curr_b = next((b for b in self.roster.bases if b.id == self._current_bm_base_id), None) if self.roster else None
                if curr_b and (legacy_cfg.mode == 1 or not curr_b.is_camp):
                    target_bid = self._current_bm_base_id
            if target_bid is None and self.roster:
                if legacy_cfg.mode == 2 and self.roster.cities:
                    target_bid = self.roster.cities[0].id
                elif legacy_cfg.mode == 1 and self.roster.camps:
                    target_bid = self.roster.camps[0].id
                elif self.roster.bases:
                    target_bid = self.roster.bases[0].id

            if target_bid is not None:
                self.bm_base_configs[target_bid] = legacy_cfg
                self._current_bm_base_id = target_bid
                if hasattr(self, "bm_bases_tree") and self.roster:
                    self._refresh_bm_bases_tree()
        if "generals" in bm_data and isinstance(bm_data["generals"], list):
            bm_gens = [int(x) for x in bm_data["generals"] if str(x).isdigit()]
            self._pending_bm_generals = set(bm_gens)
            if hasattr(self, "bm_gen_tree") and self.bm_gen_tree.get_children():
                for iid in self.bm_gen_tree.get_children():
                    vals = list(self.bm_gen_tree.item(iid, "values"))
                    vals[0] = "☑" if int(iid) in self._pending_bm_generals else "☐"
                    self.bm_gen_tree.item(iid, values=vals)
                self._update_bm_gen_count_label()

    def _build_binhman_tab(self, parent):
        container = tk.Frame(parent, bg=BG)
        container.pack(fill="both", expand=True, padx=4, pady=4)
        container.columnconfigure(0, weight=0, minsize=290)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        col_left = tk.Frame(container, bg=BG)
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        col_right = tk.Frame(container, bg=BG)
        col_right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # ---------------------------------------------------------------------
        # CỘT TRÁI: Danh sách căn cứ & Điều khiển chạy
        # ---------------------------------------------------------------------
        f_bases = ttk.LabelFrame(col_left, text="🏰 Danh Sách Căn Cứ Bình Man", style="Card.TLabelframe")
        f_bases.pack(fill="both", expand=True, padx=2, pady=(0, 4))

        bar1 = tk.Frame(f_bases, bg=BG)
        bar1.pack(fill="x", padx=4, pady=2)
        ttk.Button(bar1, text="✅ Chọn tất cả", style="Secondary.TButton", command=lambda: self._select_all_bm_bases(True)).pack(side="left", padx=2)
        ttk.Button(bar1, text="❌ Bỏ tất cả", style="Secondary.TButton", command=lambda: self._select_all_bm_bases(False)).pack(side="left", padx=2)

        bar2 = tk.Frame(f_bases, bg=BG)
        bar2.pack(fill="x", padx=4, pady=2)
        ttk.Button(bar2, text="⚔️ Biên chế TẤT CẢ căn cứ", style="Action.TButton", command=self._manual_adjust_all_bm_troops).pack(side="left", fill="x", expand=True, padx=2)

        tree_frame = tk.Frame(f_bases, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.bm_bases_tree = ttk.Treeview(
            tree_frame,
            columns=("select", "type", "coords", "gens"),
            show="tree headings",
            selectmode="browse",
        )
        self.bm_bases_tree.heading("#0", text="Căn cứ")
        self.bm_bases_tree.heading("select", text="Chạy")
        self.bm_bases_tree.heading("type", text="Loại")
        self.bm_bases_tree.heading("coords", text="Tọa độ")
        self.bm_bases_tree.heading("gens", text="Tướng")

        self.bm_bases_tree.column("#0", width=95)
        self.bm_bases_tree.column("select", width=42, anchor="center")
        self.bm_bases_tree.column("type", width=65, anchor="center")
        self.bm_bases_tree.column("coords", width=65, anchor="center")
        self.bm_bases_tree.column("gens", width=50, anchor="center")

        bm_bases_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.bm_bases_tree.yview)
        self.bm_bases_tree.configure(yscrollcommand=bm_bases_scroll.set)
        self.bm_bases_tree.pack(side="left", fill="both", expand=True)
        bm_bases_scroll.pack(side="right", fill="y")

        self.bm_bases_tree.bind("<ButtonRelease-1>", self._on_bm_bases_tree_click)
        self.bm_bases_tree.bind("<<TreeviewSelect>>", self._on_bm_bases_tree_select)

        # Khung điều khiển tiến trình
        f_ctrl = ttk.LabelFrame(col_left, text="Điều khiển tiến trình", style="Card.TLabelframe")
        f_ctrl.pack(fill="x", padx=2, pady=(0, 2))

        r_cycle = tk.Frame(f_ctrl, bg=BG)
        r_cycle.pack(fill="x", padx=4, pady=2)
        tk.Label(r_cycle, text="Chu kỳ quét (s):", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bm_interval_var = tk.StringVar(value="15")
        ttk.Entry(r_cycle, textvariable=self.bm_interval_var, width=6).pack(side="left")

        r_btns = tk.Frame(f_ctrl, bg=BG)
        r_btns.pack(fill="x", padx=4, pady=4)
        self.bm_start_btn = ttk.Button(r_btns, text="▶️ Bắt đầu Bình Man", style="Success.TButton", command=self._toggle_binhman)
        self.bm_start_btn.pack(side="left", fill="x", expand=True, padx=2)
        self.bm_once_btn = ttk.Button(r_btns, text="⚡ Chạy 1 Lượt", style="Action.TButton", command=self._run_binhman_once)
        self.bm_once_btn.pack(side="left", padx=2)

        # ---------------------------------------------------------------------
        # CỘT PHẢI: Cấu hình căn cứ hiện tại, Danh sách tướng & Log
        # ---------------------------------------------------------------------
        col_right.rowconfigure(0, weight=0)
        col_right.rowconfigure(1, weight=1)
        col_right.rowconfigure(2, weight=1)
        col_right.columnconfigure(0, weight=1)

        # 1. Cấu hình chi tiết căn cứ
        self.bm_detail_frame = ttk.LabelFrame(col_right, text="⚙️ Cấu hình căn cứ hiện tại", style="Card.TLabelframe")
        self.bm_detail_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        f_bm = self.bm_detail_frame

        # Chế độ tác chiến (Mode 1: Di Doanh trại, Mode 2: Xuất quân thẳng từ Thành)
        tk.Label(f_bm, text="Chế độ tác chiến:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.bm_mode_var = tk.IntVar(value=1)
        mode_f = tk.Frame(f_bm, bg=BG)
        mode_f.grid(row=0, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        self.bm_mode_camp_rb = tk.Radiobutton(
            mode_f, text="1: Di Doanh trại đến cạnh Man", variable=self.bm_mode_var, value=1,
            command=self._on_bm_mode_changed, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, activeforeground=FG
        )
        self.bm_mode_camp_rb.pack(side="left", padx=(0, 10))
        self.bm_mode_city_rb = tk.Radiobutton(
            mode_f, text="2: Xuất quân thẳng từ Thành", variable=self.bm_mode_var, value=2,
            command=self._on_bm_mode_changed, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, activeforeground=FG
        )
        self.bm_mode_city_rb.pack(side="left")

        self.bm_base_lbl = tk.Label(f_bm, text="Doanh trại xuất phát:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold"))
        self.bm_base_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.bm_city_combo = ttk.Combobox(f_bm, state="readonly", width=22)
        self.bm_city_combo.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.bm_city_combo.bind("<<ComboboxSelected>>", self._on_bm_city_selected)

        self.bm_parent_city_lbl = tk.Label(f_bm, text="Thành mẹ (Hồi quân):", bg=BG, fg=FG, font=("Segoe UI", 10))
        self.bm_parent_city_lbl.grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.bm_parent_city_combo = ttk.Combobox(f_bm, state="readonly", width=18)
        self.bm_parent_city_combo.grid(row=1, column=3, sticky="w", padx=4, pady=4)

        self.bm_camp_id_lbl = tk.Label(f_bm, text="Doanh trại ID:", bg=BG, fg=FG)
        self.bm_camp_id_lbl.grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.bm_camp_id_var = tk.StringVar(value="")
        self.bm_camp_id_entry = ttk.Entry(f_bm, textvariable=self.bm_camp_id_var, width=12)
        self.bm_camp_id_entry.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Ngưỡng An Toàn (%):", bg=BG, fg=FG).grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.bm_threshold_var = tk.StringVar(value="30")
        ttk.Entry(f_bm, textvariable=self.bm_threshold_var, width=8).grid(row=2, column=3, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Bán kính quét:", bg=BG, fg=FG).grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.bm_radius_var = tk.StringVar(value="10")
        ttk.Entry(f_bm, textvariable=self.bm_radius_var, width=8).grid(row=3, column=1, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Loại Man mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=3, column=2, sticky="w", padx=4, pady=4)
        self.bm_mantypes_var = tk.StringVar(value="7,8,9,10")
        self.bm_mantypes_dropdown = MultiSelectDropdown(
            f_bm,
            options=MAN_TARGET_OPTIONS,
            default_selected=[7, 8, 9, 10],
            width=22,
            command=lambda sel: self.bm_mantypes_var.set(",".join(str(x) for x in sel)),
        )
        self.bm_mantypes_dropdown.grid(row=3, column=3, sticky="w", padx=4, pady=4)

        # Row 4: Định mức quân đội (Bộ MT, Kỵ MT, Cung MT) & Nút Biên chế căn cứ này
        tk.Label(f_bm, text="Bộ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w", padx=4, pady=4)
        self.bm_target_inf_var = tk.StringVar(value="0")
        ttk.Entry(f_bm, textvariable=self.bm_target_inf_var, width=8).grid(row=4, column=1, sticky="w", padx=4, pady=4)

        bm_army_f = tk.Frame(f_bm, bg=BG)
        bm_army_f.grid(row=4, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        tk.Label(bm_army_f, text="Kỵ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.bm_target_cav_var = tk.StringVar(value="0")
        ttk.Entry(bm_army_f, textvariable=self.bm_target_cav_var, width=6).pack(side="left", padx=(0, 6))

        tk.Label(bm_army_f, text="Cung MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.bm_target_arc_var = tk.StringVar(value="0")
        ttk.Entry(bm_army_f, textvariable=self.bm_target_arc_var, width=6).pack(side="left", padx=(0, 8))

        self.bm_adjust_troops_btn = ttk.Button(bm_army_f, text="⚔️ Biên chế ngay", style="Action.TButton", command=self._manual_adjust_bm_troops)
        self.bm_adjust_troops_btn.pack(side="left", padx=(0, 4))

        # Row 5: Tự động bổ sung lính, San đều quân, Tự động nâng sĩ khí, Sĩ khí tối thiểu
        bm_rec_f = tk.Frame(f_bm, bg=BG)
        bm_rec_f.grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        self.bm_auto_recruit_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bm_rec_f,
            text="Tự động bổ sung lính",
            variable=self.bm_auto_recruit_var,
            style="TCheckbutton",
        ).pack(side="left", padx=(0, 8))
        self.bm_even_troops_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            bm_rec_f,
            text="San đều quân",
            variable=self.bm_even_troops_var,
            style="TCheckbutton",
        ).pack(side="left")

        bm_mor_f = tk.Frame(f_bm, bg=BG)
        bm_mor_f.grid(row=5, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        self.bm_auto_morale_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bm_mor_f, text="Tự động nâng sĩ khí", variable=self.bm_auto_morale_var, style="TCheckbutton").pack(side="left", padx=(0, 8))
        tk.Label(bm_mor_f, text="Sĩ khí tối thiểu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.bm_min_morale_var = tk.StringVar(value="95")
        ttk.Entry(bm_mor_f, textvariable=self.bm_min_morale_var, width=5).pack(side="left")

        # Row 6: Tự động đổi mưu sĩ
        self.bm_auto_swap_tactician_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f_bm,
            text="Tự động đổi mưu sĩ",
            variable=self.bm_auto_swap_tactician_var,
            style="TCheckbutton",
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        bm_tac_f = tk.Frame(f_bm, bg=BG)
        bm_tac_f.grid(row=6, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        tk.Label(bm_tac_f, text="Thể lực tối thiểu (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.bm_min_tactician_stamina_var = tk.StringVar(value="30")
        ttk.Entry(bm_tac_f, textvariable=self.bm_min_tactician_stamina_var, width=5).pack(side="left")

        # Row 7: Chiêu tấn công
        tk.Label(f_bm, text="Chiêu tấn công:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=7, column=0, sticky="w", padx=4, pady=4)
        self.bm_action_mode_var = tk.StringVar(value="adaptive")
        self.bm_action_mode_combo = ttk.Combobox(f_bm, state="readonly", width=24)
        self.bm_action_mode_combo["values"] = list(ATTACK_ACTION_COMBO_OPTIONS)
        self.bm_action_mode_combo.current(0)
        self.bm_action_mode_combo.grid(row=7, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        self.bm_action_mode_combo.bind("<<ComboboxSelected>>", self._on_bm_action_mode_changed)

        # 2. Bảng danh sách võ tướng
        f_gens = ttk.LabelFrame(col_right, text="Võ tướng xuất kích", style="Card.TLabelframe")
        f_gens.grid(row=1, column=0, sticky="nsew", pady=(0, 4))

        btn_bar = tk.Frame(f_gens, bg=BG)
        btn_bar.pack(fill="x", padx=4, pady=2)
        ttk.Button(btn_bar, text="✅ Chọn tất cả", style="Secondary.TButton", command=self._select_all_bm_gens).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="❌ Bỏ chọn tất cả", style="Secondary.TButton", command=self._deselect_all_bm_gens).pack(side="left", padx=2)
        self.bm_gen_count_lbl = tk.Label(btn_bar, text="Đã chọn: 0 tướng (0 đợt xuất kích)", bg=BG, fg=FG, font=("Segoe UI", 9, "bold"))
        self.bm_gen_count_lbl.pack(side="left", padx=8)

        self.bm_gen_tree = ttk.Treeview(
            f_gens,
            columns=("select", "lv", "stamina", "morale", "infantry", "cavalry", "archers", "total_army"),
            show="tree headings",
            selectmode="browse",
            height=5,
        )
        self.bm_gen_tree.heading("#0", text="Tên võ tướng")
        self.bm_gen_tree.heading("select", text="Chọn")
        self.bm_gen_tree.heading("lv", text="Cấp")
        self.bm_gen_tree.heading("stamina", text="Thể lực")
        self.bm_gen_tree.heading("morale", text="Sĩ khí")
        self.bm_gen_tree.heading("infantry", text="Bộ binh")
        self.bm_gen_tree.heading("cavalry", text="Kỵ binh")
        self.bm_gen_tree.heading("archers", text="Cung binh")
        self.bm_gen_tree.heading("total_army", text="Tổng quân")

        self.bm_gen_tree.column("#0", width=140)
        self.bm_gen_tree.column("select", width=50, anchor="center")
        self.bm_gen_tree.column("lv", width=50, anchor="center")
        self.bm_gen_tree.column("stamina", width=75, anchor="center")
        self.bm_gen_tree.column("morale", width=65, anchor="center")
        self.bm_gen_tree.column("infantry", width=80, anchor="e")
        self.bm_gen_tree.column("cavalry", width=80, anchor="e")
        self.bm_gen_tree.column("archers", width=80, anchor="e")
        self.bm_gen_tree.column("total_army", width=85, anchor="e")

        gen_scroll = ttk.Scrollbar(f_gens, orient="vertical", command=self.bm_gen_tree.yview)
        self.bm_gen_tree.configure(yscrollcommand=gen_scroll.set)
        self.bm_gen_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        gen_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))
        self.bm_gen_tree.bind("<ButtonRelease-1>", self._on_bm_gen_toggle)

        # 3. Khung nhật ký Bình Man
        f_log = ttk.LabelFrame(col_right, text="Nhật ký Bình Man", style="Card.TLabelframe")
        f_log.grid(row=2, column=0, sticky="nsew", pady=(0, 0))

        log_bar = tk.Frame(f_log, bg=CARD)
        log_bar.pack(side="top", fill="x", padx=4, pady=(2, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._bm_clear_log).pack(side="right")

        log_scroll = ttk.Scrollbar(f_log, orient="vertical")
        self.bm_log_text = tk.Text(f_log, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0, yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.bm_log_text.yview)
        self.bm_log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        log_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))

    def _update_bm_gen_count_label(self):
        if not hasattr(self, "bm_gen_count_lbl") or not hasattr(self, "bm_gen_tree"):
            return
        selected_count = sum(1 for item in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(item, "values")[0] == "☑")
        batches = (selected_count + 2) // 3 if selected_count > 0 else 0
        self.bm_gen_count_lbl.config(text=f"Đã chọn: {selected_count} tướng ({batches} đợt xuất kích)")

    def _update_bm_bases_tree_gen_count(self):
        if not hasattr(self, "bm_bases_tree") or not hasattr(self, "bm_gen_tree") or self._current_bm_base_id is None:
            return
        iid = str(self._current_bm_base_id)
        if not self.bm_bases_tree.exists(iid):
            return
        vals = list(self.bm_bases_tree.item(iid, "values"))
        sel_count = sum(1 for item in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(item, "values")[0] == "☑")
        total_count = len(self.bm_gen_tree.get_children())
        if len(vals) > 3:
            vals[3] = f"{sel_count}/{total_count}"
            self.bm_bases_tree.item(iid, values=vals)

    def _select_all_bm_gens(self):
        for item in self.bm_gen_tree.get_children():
            vals = list(self.bm_gen_tree.item(item, "values"))
            vals[0] = "☑"
            self.bm_gen_tree.item(item, values=vals)
        self._update_bm_gen_count_label()
        self._update_bm_bases_tree_gen_count()
        self._schedule_auto_save()

    def _deselect_all_bm_gens(self):
        for item in self.bm_gen_tree.get_children():
            vals = list(self.bm_gen_tree.item(item, "values"))
            vals[0] = "☐"
            self.bm_gen_tree.item(item, values=vals)
        self._update_bm_gen_count_label()
        self._update_bm_bases_tree_gen_count()
        self._schedule_auto_save()

    def _on_bm_gen_toggle(self, event):
        item = self.bm_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.bm_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.bm_gen_tree.item(item, values=vals)
        self._update_bm_gen_count_label()
        self._update_bm_bases_tree_gen_count()
        self._schedule_auto_save()

    def _append_bm_log(self, msg: str):
        self._append_text_buffer(self.bm_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _bm_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Bình Man."""
        if hasattr(self, "bm_log_text") and self.bm_log_text:
            self.bm_log_text.delete("1.0", "end")

    def _update_bm_mode_ui_states(self, mode: int):
        if hasattr(self, "bm_city_combo") and hasattr(self, "roster") and self.roster:
            if mode == 2:
                items = [c.display_name for c in self.roster.cities]
            else:
                items = [c.display_name for c in self.roster.camps] if self.roster.camps else [b.display_name for b in self.roster.bases]
            self.bm_city_combo["values"] = items

        if mode == 2:  # Chế độ 2: Xuất quân thẳng từ Thành
            if hasattr(self, "bm_base_lbl"):
                self.bm_base_lbl.configure(text="Thành xuất phát:")
            if hasattr(self, "bm_parent_city_lbl"):
                self.bm_parent_city_lbl.configure(state="disabled")
            if hasattr(self, "bm_parent_city_combo"):
                self.bm_parent_city_combo.configure(state="disabled")
            if hasattr(self, "bm_camp_id_lbl"):
                self.bm_camp_id_lbl.configure(state="disabled")
            if hasattr(self, "bm_camp_id_entry"):
                self.bm_camp_id_entry.configure(state="disabled")
        else:  # Chế độ 1: Di Doanh trại
            if hasattr(self, "bm_base_lbl"):
                self.bm_base_lbl.configure(text="Doanh trại xuất phát:")
            if hasattr(self, "bm_parent_city_lbl"):
                self.bm_parent_city_lbl.configure(state="normal")
            if hasattr(self, "bm_parent_city_combo"):
                self.bm_parent_city_combo.configure(state="readonly")
            if hasattr(self, "bm_camp_id_lbl"):
                self.bm_camp_id_lbl.configure(state="normal")
            if hasattr(self, "bm_camp_id_entry"):
                self.bm_camp_id_entry.configure(state="normal")

    def _on_bm_action_mode_changed(self, _event=None):
        if hasattr(self, "bm_action_mode_combo") and hasattr(self, "bm_action_mode_var"):
            sync_action_mode_from_combo(self.bm_action_mode_var, self.bm_action_mode_combo)
        if hasattr(self, "_save_bm_current_base_config"):
            self._save_bm_current_base_config()

    def _on_bm_mode_changed(self):
        mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
        self._update_bm_mode_ui_states(mode)
        if hasattr(self, "bm_city_combo"):
            combo_len = len(self.bm_city_combo["values"])
            if combo_len > 0 and (self.bm_city_combo.current() < 0 or self.bm_city_combo.current() >= combo_len):
                self.bm_city_combo.current(0)
        self._on_bm_city_selected()

    def _on_bm_city_selected(self, _event=None):
        mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
        sel_idx = self.bm_city_combo.current() if hasattr(self, "bm_city_combo") else -1
        if mode == 2:
            bases = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        else:
            bases = self.roster.camps if (self.roster and self.roster.camps) else (self.roster.bases if self.roster else [])

        if 0 <= sel_idx < len(bases):
            base = bases[sel_idx]
            if hasattr(self, "bm_bases_tree") and self.bm_bases_tree.exists(str(base.id)):
                self.bm_bases_tree.selection_set(str(base.id))
            self._switch_bm_base(base.id)

    def _get_or_create_bm_base_config(self, base) -> BaseBinhManConfig:
        cfg = self.bm_base_configs.get(base.id)
        if cfg is None:
            if getattr(self, "_pending_bm_legacy_config", None):
                cfg = self._pending_bm_legacy_config
                self._pending_bm_legacy_config = None
                self.bm_base_configs[base.id] = cfg
                return cfg

            def_mode = 1 if base.is_camp else 2
            def_camp_id = str(base.id) if base.is_camp else ""
            vos = [g.id for g in self.roster.generals_of(base.id) if g.role == "vo"] if self.roster else []
            t_rad = self.bm_radius_var.get() if hasattr(self, "bm_radius_var") else "10"
            t_thresh = self.bm_threshold_var.get() if hasattr(self, "bm_threshold_var") else "30"
            t_min_mor = self.bm_min_morale_var.get() if hasattr(self, "bm_min_morale_var") else "95"
            t_auto_rec = bool(self.bm_auto_recruit_var.get()) if hasattr(self, "bm_auto_recruit_var") else True
            t_auto_mor = bool(self.bm_auto_morale_var.get()) if hasattr(self, "bm_auto_morale_var") else True
            t_auto_swap_tac = bool(self.bm_auto_swap_tactician_var.get()) if hasattr(self, "bm_auto_swap_tactician_var") else False
            t_min_tac_stam = self.bm_min_tactician_stamina_var.get() if hasattr(self, "bm_min_tactician_stamina_var") else "30"

            # ADR-0029 Section 5: Bộ quy tắc an toàn mặc định cho căn cứ mới
            # - enabled = False (chưa chọn chạy)
            # - generals = tất cả võ tướng có trong căn cứ
            # - Định mức lính: 0 / 0 / 0
            cfg = BaseBinhManConfig(
                enabled=False,
                mode=def_mode,
                radius=str(t_rad),
                threshold=str(t_thresh),
                camp_id=def_camp_id,
                generals=vos,
                target_infantry="0",
                target_cavalry="0",
                target_archers="0",
                auto_recruit=t_auto_rec,
                auto_morale=t_auto_mor,
                min_morale=str(t_min_mor),
                auto_swap_tactician=t_auto_swap_tac,
                min_tactician_stamina=str(t_min_tac_stam or "30"),
                attack_action_mode="adaptive",
                action_combo_idx=0,
            )
            self.bm_base_configs[base.id] = cfg
        return cfg

    def _refresh_bm_bases_tree(self):
        if not hasattr(self, "bm_bases_tree") or not self.roster:
            return
        if getattr(self, "_pending_bm_legacy_config", None) and self.roster.bases:
            if not any(b.id in self.bm_base_configs for b in self.roster.bases):
                if self._pending_bm_legacy_config.mode == 2 and self.roster.cities:
                    target_bid = self.roster.cities[0].id
                elif self._pending_bm_legacy_config.mode == 1 and self.roster.camps:
                    target_bid = self.roster.camps[0].id
                else:
                    target_bid = self.roster.bases[0].id
                self.bm_base_configs[target_bid] = self._pending_bm_legacy_config
                if not self._pending_bm_legacy_config.generals:
                    self._pending_bm_legacy_config.generals = [g.id for g in self.roster.generals_of(target_bid) if g.role == "vo"]
            self._pending_bm_legacy_config = None

        self.bm_bases_tree.delete(*self.bm_bases_tree.get_children())
        for base in self.roster.bases:
            cfg = self._get_or_create_bm_base_config(base)

            is_sel = "☑" if cfg.enabled else "☐"
            b_type = "⛺ Trại" if base.is_camp else "🏰 Thành"
            coords = f"({base.pos_x},{base.pos_y})" if (base.pos_x or base.pos_y) else "-"
            total_vos = len([g for g in self.roster.generals_of(base.id) if g.role == "vo"])
            gens_text = f"{len(cfg.generals)}/{total_vos}"
            self.bm_bases_tree.insert(
                "",
                "end",
                iid=str(base.id),
                text=base.name,
                values=(is_sel, b_type, coords, gens_text),
            )

        if self.roster.bases:
            target_id = self._current_bm_base_id if (self._current_bm_base_id and any(b.id == self._current_bm_base_id for b in self.roster.bases)) else None
            if target_id is None:
                for b in self.roster.bases:
                    cfg = self.bm_base_configs.get(b.id)
                    if cfg and cfg.enabled:
                        target_id = b.id
                        break
            if target_id is None:
                cur_mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
                if cur_mode == 1 and self.roster.camps:
                    target_id = self.roster.camps[0].id
                else:
                    target_id = self.roster.bases[0].id

            self._current_bm_base_id = target_id
            iid = str(target_id)
            if self.bm_bases_tree.exists(iid):
                self.bm_bases_tree.selection_set(iid)
                self._load_bm_base_config(target_id)

    def _on_bm_bases_tree_click(self, event):
        item = self.bm_bases_tree.identify_row(event.y)
        col = self.bm_bases_tree.identify_column(event.x)
        if not item or not self.bm_bases_tree.exists(item):
            return
        try:
            base_id = int(item)
        except ValueError:
            return
        if col == "#1":  # Column 'select'
            vals = list(self.bm_bases_tree.item(item, "values"))
            cfg = self.bm_base_configs.setdefault(base_id, BaseBinhManConfig())
            if vals[0] == "☑":
                vals[0] = "☐"
                cfg.enabled = False
            else:
                vals[0] = "☑"
                cfg.enabled = True
            self.bm_bases_tree.item(item, values=vals)
            self._schedule_auto_save()

    def _on_bm_bases_tree_select(self, _event=None):
        sel = self.bm_bases_tree.selection()
        if not sel:
            return
        try:
            base_id = int(sel[0])
            if base_id == self._current_bm_base_id:
                return
            self._switch_bm_base(base_id)
            self._schedule_auto_save()
        except ValueError:
            pass

    def _switch_bm_base(self, base_id: int):
        if self._current_bm_base_id is not None and self._current_bm_base_id != base_id:
            self._save_bm_current_base_config()
        self._load_bm_base_config(base_id)

    def _select_all_bm_bases(self, enabled: bool):
        if not hasattr(self, "bm_bases_tree"):
            return
        for iid in self.bm_bases_tree.get_children(""):
            vals = list(self.bm_bases_tree.item(iid, "values"))
            vals[0] = "☑" if enabled else "☐"
            self.bm_bases_tree.item(iid, values=vals)
            try:
                bid = int(iid)
                if bid in self.bm_base_configs:
                    self.bm_base_configs[bid].enabled = enabled
            except ValueError:
                pass
        self._schedule_auto_save()

    def _save_bm_current_base_config(self):
        if self._current_bm_base_id is None:
            return
        base_id = self._current_bm_base_id
        cfg = self.bm_base_configs.get(base_id)
        if cfg is None:
            cfg = BaseBinhManConfig()
            self.bm_base_configs[base_id] = cfg

        if hasattr(self, "bm_mode_var"):
            cfg.mode = self.bm_mode_var.get()
        if hasattr(self, "bm_radius_var"):
            cfg.radius = str(self.bm_radius_var.get() or "10")
        if hasattr(self, "bm_threshold_var"):
            cfg.threshold = str(self.bm_threshold_var.get() or "30")
        if hasattr(self, "bm_camp_id_var") and cfg.mode == 1:
            cfg.camp_id = self.bm_camp_id_var.get().strip()
        if hasattr(self, "bm_parent_city_combo") and self.roster and self.roster.cities:
            pidx = self.bm_parent_city_combo.current()
            if 0 <= pidx < len(self.roster.cities):
                cfg.parent_city_id = str(self.roster.cities[pidx].id)
        if hasattr(self, "bm_mantypes_dropdown"):
            cfg.target_types = self.bm_mantypes_dropdown.get_selected()
            cfg.mantypes = self.bm_mantypes_dropdown.get_selected_str()
        elif hasattr(self, "bm_mantypes_var"):
            cfg.mantypes = self.bm_mantypes_var.get()
            cfg.target_types = [int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()]
        if hasattr(self, "bm_gen_tree"):
            cfg.generals = [int(iid) for iid in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(iid, "values")[0] == "☑"]
        if hasattr(self, "bm_target_inf_var"):
            cfg.target_infantry = str(self.bm_target_inf_var.get() or "0")
        if hasattr(self, "bm_target_cav_var"):
            cfg.target_cavalry = str(self.bm_target_cav_var.get() or "0")
        if hasattr(self, "bm_target_arc_var"):
            cfg.target_archers = str(self.bm_target_arc_var.get() or "0")
        if hasattr(self, "bm_auto_recruit_var"):
            cfg.auto_recruit = bool(self.bm_auto_recruit_var.get())
        if hasattr(self, "bm_even_troops_var"):
            cfg.even_troops = bool(self.bm_even_troops_var.get())
        if hasattr(self, "bm_auto_morale_var"):
            cfg.auto_morale = bool(self.bm_auto_morale_var.get())
        if hasattr(self, "bm_min_morale_var"):
            cfg.min_morale = str(self.bm_min_morale_var.get() or "95")
        if hasattr(self, "bm_auto_swap_tactician_var"):
            cfg.auto_swap_tactician = bool(self.bm_auto_swap_tactician_var.get())
        if hasattr(self, "bm_min_tactician_stamina_var"):
            cfg.min_tactician_stamina = str(self.bm_min_tactician_stamina_var.get() or "30")
        if hasattr(self, "bm_action_mode_combo"):
            idx = self.bm_action_mode_combo.current()
            cfg.action_combo_idx = idx if idx >= 0 else 0
            if hasattr(self, "bm_action_mode_var"):
                cfg.attack_action_mode = sync_action_mode_from_combo(self.bm_action_mode_var, self.bm_action_mode_combo)
            else:
                cfg.attack_action_mode = parse_attack_action_combo(self.bm_action_mode_combo.get())[0]
        self._update_bm_bases_tree_gen_count()

    def _load_bm_base_config(self, base_id: int):
        self._current_bm_base_id = base_id
        if not self.roster:
            return
        base = next((b for b in self.roster.bases if b.id == base_id), None)
        if not base:
            return

        cfg = self._get_or_create_bm_base_config(base)

        with self._suppress_auto_save():
            if hasattr(self, "bm_detail_frame"):
                self.bm_detail_frame.configure(text=f"⚙️ Cấu hình căn cứ: {base.name} ({base.pos_x}, {base.pos_y})")

            if hasattr(self, "bm_mode_var"):
                self.bm_mode_var.set(cfg.mode)
            if hasattr(self, "bm_radius_var"):
                self.bm_radius_var.set(str(cfg.radius))
            if hasattr(self, "bm_threshold_var"):
                self.bm_threshold_var.set(str(cfg.threshold))
            if hasattr(self, "bm_camp_id_var"):
                self.bm_camp_id_var.set(str(cfg.camp_id) if cfg.camp_id is not None else "")
            if hasattr(self, "bm_parent_city_combo") and self.roster.cities:
                if cfg.parent_city_id:
                    for idx, c in enumerate(self.roster.cities):
                        if str(c.id) == str(cfg.parent_city_id):
                            self.bm_parent_city_combo.current(idx)
                            break
                elif not self.bm_parent_city_combo.get() and len(self.roster.cities) > 0:
                    self.bm_parent_city_combo.current(0)
            if hasattr(self, "bm_mantypes_dropdown"):
                t_types = cfg.target_types if cfg.target_types else ([int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()] if isinstance(cfg.mantypes, str) else [7, 8, 9, 10])
                self.bm_mantypes_dropdown.set_selected(t_types)
            if hasattr(self, "bm_mantypes_var"):
                self.bm_mantypes_var.set(cfg.mantypes if isinstance(cfg.mantypes, str) else ",".join(str(x) for x in cfg.mantypes))
            if hasattr(self, "bm_target_inf_var"):
                self.bm_target_inf_var.set(str(cfg.target_infantry))
            if hasattr(self, "bm_target_cav_var"):
                self.bm_target_cav_var.set(str(cfg.target_cavalry))
            if hasattr(self, "bm_target_arc_var"):
                self.bm_target_arc_var.set(str(cfg.target_archers))
            if hasattr(self, "bm_auto_recruit_var"):
                self.bm_auto_recruit_var.set(cfg.auto_recruit)
            if hasattr(self, "bm_even_troops_var"):
                self.bm_even_troops_var.set(bool(getattr(cfg, "even_troops", False)))
            if hasattr(self, "bm_auto_morale_var"):
                self.bm_auto_morale_var.set(cfg.auto_morale)
            if hasattr(self, "bm_min_morale_var"):
                self.bm_min_morale_var.set(str(cfg.min_morale))
            if hasattr(self, "bm_auto_swap_tactician_var"):
                self.bm_auto_swap_tactician_var.set(bool(cfg.auto_swap_tactician))
            if hasattr(self, "bm_min_tactician_stamina_var"):
                self.bm_min_tactician_stamina_var.set(str(cfg.min_tactician_stamina or "30"))
            apply_action_mode_widgets(
                getattr(self, "bm_action_mode_var", None),
                getattr(self, "bm_action_mode_combo", None),
                str(getattr(cfg, "attack_action_mode", "adaptive") or "adaptive"),
                int(getattr(cfg, "action_combo_idx", 0) or 0),
            )

            self._update_bm_mode_ui_states(cfg.mode)

            if hasattr(self, "bm_city_combo"):
                combo_values = list(self.bm_city_combo["values"])
                for idx, val in enumerate(combo_values):
                    if base.name in val:
                        self.bm_city_combo.current(idx)
                        break

            if hasattr(self, "bm_bases_tree") and self.bm_bases_tree.exists(str(base_id)):
                cur_sel = self.bm_bases_tree.selection()
                if not cur_sel or cur_sel[0] != str(base_id):
                    self.bm_bases_tree.selection_set(str(base_id))

        if hasattr(self, "bm_gen_tree"):
            self.bm_gen_tree.delete(*self.bm_gen_tree.get_children())
            sel_gens_set = set(cfg.generals) if cfg.generals is not None else set()
            pending = self._pending_bm_generals
            for g in self.roster.generals_of(base.id):
                if g.role != "vo":
                    continue
                army = self.roster.army_of(g.id)
                inf = army.infantry if army else 0
                cav = army.cavalry if army else 0
                arc = army.archers if army else 0
                total = army.total if army else 0
                if pending is not None:
                    checked = "☑" if g.id in pending else "☐"
                elif cfg.generals is not None:
                    checked = "☑" if g.id in sel_gens_set else "☐"
                else:
                    checked = "☑"
                self.bm_gen_tree.insert(
                    "",
                    "end",
                    iid=str(g.id),
                    text=g.name,
                    values=(checked, g.level, f"{g.stamina}/{g.stamina_max}", g.morale, inf, cav, arc, total),
                )
            self._pending_bm_generals = None
            self._update_bm_gen_count_label()
            self._update_bm_bases_tree_gen_count()

    def _create_binhman_tasks(self) -> list[BinhMan]:
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        self._save_bm_current_base_config()
        if not self.roster or not self.roster.bases:
            msgbox.showwarning("Cảnh báo", "Dữ liệu tướng và căn cứ chưa sẵn sàng!")
            return []

        enabled_bases = [b for b in self.roster.bases if self.bm_base_configs.get(b.id, BaseBinhManConfig()).enabled]
        if not enabled_bases:
            if self._current_bm_base_id:
                curr_base = next((b for b in self.roster.bases if b.id == self._current_bm_base_id), None)
                if curr_base:
                    enabled_bases = [curr_base]
            if not enabled_bases:
                msgbox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 căn cứ để chạy Bình Man!")
                return []

        all_peers: list[BasePeer] = []
        for b in enabled_bases:
            cfg = self.bm_base_configs.get(b.id)
            if not cfg or not cfg.generals:
                continue
            t_types = cfg.target_types if cfg.target_types else ([int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()] if isinstance(cfg.mantypes, str) else [7, 8, 9, 10])
            all_peers.append(
                BasePeer(
                    base_id=b.id,
                    ox=b.pos_x,
                    oy=b.pos_y,
                    radius=int(cfg.radius) if str(cfg.radius).isdigit() else 10,
                    target_types=t_types,
                    origin=(b.pos_x, b.pos_y),
                    mantypes=t_types,
                    name=b.name,
                )
            )

        tasks: list[BinhMan] = []
        for b in enabled_bases:
            cfg = self.bm_base_configs.get(b.id)
            if not cfg:
                continue
            sel_gens = cfg.generals
            if not sel_gens:
                continue

            mode = cfg.mode
            camp_id = int(cfg.camp_id) if (mode == 1 and cfg.camp_id and str(cfg.camp_id).lstrip("-").isdigit()) else (b.id if (mode == 1 and b.is_camp) else None)
            parent_id = int(cfg.parent_city_id) if (cfg.parent_city_id and str(cfg.parent_city_id).isdigit()) else b.id

            scanner = Scanner(
                self.gateway,
                self.shared_target_locks,
                delay=0.0,
                sleep=lambda s: None,
                map_cache_ttl=4.0,
                capitals_cache_ttl=300.0,
            )
            ctx = TaskContext(self.gateway, scanner, self.shared_target_locks, notify=lambda m, bname=b.name: self.after(0, self._append_bm_log, f"[{bname}] {m}"))
            peers = [p for p in all_peers if p.base_id != b.id]

            t_inf = int(cfg.target_infantry) if str(cfg.target_infantry).isdigit() else 0
            t_cav = int(cfg.target_cavalry) if str(cfg.target_cavalry).isdigit() else 0
            t_arc = int(cfg.target_archers) if str(cfg.target_archers).isdigit() else 0
            target_army = TargetArmy(infantry=t_inf, cavalry=t_cav, archers=t_arc)
            rad_int = int(cfg.radius) if str(cfg.radius).isdigit() else 10
            thresh_int = int(cfg.threshold) if str(cfg.threshold).isdigit() else 30
            mor_int = int(cfg.min_morale) if str(cfg.min_morale).isdigit() else 95
            b_types = cfg.target_types if cfg.target_types else ([int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()] if isinstance(cfg.mantypes, str) else [7, 8, 9, 10])
            combo_vals = list(ATTACK_ACTION_COMBO_OPTIONS)
            c_idx = int(getattr(cfg, "action_combo_idx", 0) or 0)
            b_combo_val = combo_vals[c_idx] if 0 <= c_idx < len(combo_vals) else combo_vals[0]

            task = BinhMan(
                ctx=ctx,
                generals=sel_gens,
                origin=(b.pos_x, b.pos_y),
                radius=rad_int,
                man_types=b_types,
                camp_id=camp_id,
                parent_city_id=parent_id,
                city_id=b.id if mode == 2 else parent_id,
                return_threshold=thresh_int,
                mode=mode,
                sleep_fn=time.sleep,
                combat_config=self._build_combat_config(action_combo_val=b_combo_val),
                on_battle_found=lambda bid: self.after(
                    0, lambda x=bid: self.bt_id_var.set(str(x)) if hasattr(self, "bt_id_var") else None
                ),
                on_battle_state=lambda st: self.after(
                    0, lambda s=st: self._bt_render_state(s) if hasattr(self, "_bt_render_state") else None
                ),
                target_army=target_army,
                auto_recruit=cfg.auto_recruit,
                auto_morale=cfg.auto_morale,
                min_morale=mor_int,
                auto_swap_tactician=bool(getattr(cfg, "auto_swap_tactician", False)),
                min_tactician_stamina=parse_stamina_threshold(getattr(cfg, "min_tactician_stamina", "30")),
                peers=peers,
                non_blocking_relocate=True,
                base_name=b.name,
                even_troops=bool(getattr(cfg, "even_troops", False)),
            )
            tasks.append(task)

        if tasks:
            def _make_peers_fn(for_task_id: int):
                def _get_peers() -> list[BasePeer]:
                    result = []
                    for other in tasks:
                        if other.origin_id != for_task_id:
                            result.append(
                                BasePeer(
                                    base_id=other.origin_id,
                                    ox=other.origin[0],
                                    oy=other.origin[1],
                                    radius=other.radius,
                                    target_types=other.man_types,
                                    origin=other.origin,
                                    mantypes=other.man_types,
                                    name=getattr(other, "base_name", ""),
                                )
                            )
                    return result
                return _get_peers

            for t in tasks:
                t.peers_fn = _make_peers_fn(t.origin_id)

        if not tasks:
            msgbox.showwarning("Cảnh báo", "Không có căn cứ nào có võ tướng khả dụng được chọn!")
        return tasks

    def _create_binhman_task(self, base_id: Optional[int] = None) -> Optional[BinhMan]:
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if base_id is not None:
            tasks = self._create_binhman_tasks()
            for t in tasks:
                if getattr(t, "city_id", None) == base_id or getattr(t, "camp_id", None) == base_id:
                    return t
            return None

        self._save_bm_current_base_config()
        mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
        sel_idx = self.bm_city_combo.current() if hasattr(self, "bm_city_combo") else -1
        if mode == 2:
            bases = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        else:
            bases = self.roster.camps if (self.roster and self.roster.camps) else (self.roster.bases if self.roster else [])

        if sel_idx < 0 or sel_idx >= len(bases):
            if self._current_bm_base_id and self.roster:
                base = next((b for b in self.roster.bases if b.id == self._current_bm_base_id), None)
            else:
                base = None
        else:
            base = bases[sel_idx]

        if not base:
            msg = "Vui lòng chọn Thành xuất phát!" if mode == 2 else "Vui lòng chọn căn cứ/doanh trại xuất phát!"
            msgbox.showwarning("Cảnh báo", msg)
            return None

        sel_gens = []
        if hasattr(self, "bm_gen_tree"):
            sel_gens = [int(iid) for iid in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(iid, "values")[0] == "☑"]
        if not sel_gens and self.roster:
            cfg = self.bm_base_configs.get(base.id)
            if cfg and cfg.generals:
                sel_gens = cfg.generals

        if not sel_gens:
            vos = [g.id for g in self.roster.generals_of(base.id) if g.role == "vo"] if self.roster else []
            if not vos:
                msgbox.showwarning("Cảnh báo", "Căn cứ này không có võ tướng khả dụng!")
                return None
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng xuất kích!")
            return None

        parent_idx = self.bm_parent_city_combo.current() if hasattr(self, "bm_parent_city_combo") else -1
        parent_id = self.roster.cities[parent_idx].id if (self.roster and self.roster.cities and 0 <= parent_idx < len(self.roster.cities)) else None
        camp_id = int(self.bm_camp_id_var.get()) if (mode == 1 and hasattr(self, "bm_camp_id_var") and self.bm_camp_id_var.get().strip()) else (base.id if (mode == 1 and base.is_camp) else None)
        radius = int(self.bm_radius_var.get() or "10") if hasattr(self, "bm_radius_var") else 10
        try:
            threshold = int(self.bm_threshold_var.get() or "30") if hasattr(self, "bm_threshold_var") else 30
        except ValueError:
            threshold = 30
        if hasattr(self, "bm_mantypes_dropdown"):
            man_types = self.bm_mantypes_dropdown.get_selected()
        elif hasattr(self, "bm_mantypes_var"):
            man_types = [int(x.strip()) for x in self.bm_mantypes_var.get().split(",") if x.strip()]
        else:
            man_types = [7, 8, 9, 10]
        if not man_types:
            man_types = [7, 8, 9, 10]

        locks = self.shared_target_locks
        scanner = Scanner(
            self.gateway,
            locks,
            delay=0.0,
            sleep=lambda s: None,
            map_cache_ttl=4.0,
            capitals_cache_ttl=300.0,
        )
        ctx = TaskContext(self.gateway, scanner, locks, notify=lambda m: self.after(0, self._append_bm_log, m))

        try:
            target_inf = int(self.bm_target_inf_var.get() or "0")
        except (ValueError, AttributeError):
            target_inf = 0
        try:
            target_cav = int(self.bm_target_cav_var.get() or "0")
        except (ValueError, AttributeError):
            target_cav = 0
        try:
            target_arc = int(self.bm_target_arc_var.get() or "0")
        except (ValueError, AttributeError):
            target_arc = 0
        try:
            min_morale = int(self.bm_min_morale_var.get() or "95")
        except (ValueError, AttributeError):
            min_morale = 95

        target_army = TargetArmy(infantry=target_inf, cavalry=target_cav, archers=target_arc)
        auto_recruit = bool(self.bm_auto_recruit_var.get()) if hasattr(self, "bm_auto_recruit_var") else True
        auto_morale = bool(self.bm_auto_morale_var.get()) if hasattr(self, "bm_auto_morale_var") else True
        auto_swap_tactician = (
            bool(self.bm_auto_swap_tactician_var.get())
            if hasattr(self, "bm_auto_swap_tactician_var")
            else False
        )
        min_tactician_stamina = parse_stamina_threshold(
            self.bm_min_tactician_stamina_var.get()
            if hasattr(self, "bm_min_tactician_stamina_var")
            else "30"
        )
        bm_combo_val = self.bm_action_mode_combo.get() if hasattr(self, "bm_action_mode_combo") else None

        return BinhMan(
            ctx=ctx,
            generals=sel_gens,
            origin=(base.pos_x, base.pos_y),
            radius=radius,
            man_types=man_types,
            camp_id=camp_id,
            parent_city_id=parent_id or base.id,
            city_id=base.id if mode == 2 else parent_id,
            return_threshold=threshold,
            mode=mode,
            sleep_fn=time.sleep,
            combat_config=self._build_combat_config(action_combo_val=bm_combo_val),
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
            auto_swap_tactician=auto_swap_tactician,
            min_tactician_stamina=min_tactician_stamina,
            base_name=base.name,
            even_troops=bool(self.bm_even_troops_var.get()) if hasattr(self, "bm_even_troops_var") else False,
        )

    def _provision_base_troops(
        self,
        base_id: int,
        base_name: str,
        cfg: BaseBinhManConfig,
        prov: ArmyProvisioner,
    ):
        fetch_roster_fn = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        trainer_cls = resolve_dashboard_symbol("MoraleTrainer", _DefaultMoraleTrainer)
        sel_gens = cfg.generals
        if not sel_gens:
            return

        t_inf = int(cfg.target_infantry) if str(cfg.target_infantry).isdigit() else 0
        t_cav = int(cfg.target_cavalry) if str(cfg.target_cavalry).isdigit() else 0
        t_arc = int(cfg.target_archers) if str(cfg.target_archers).isdigit() else 0
        target_army = TargetArmy(infantry=t_inf, cavalry=t_cav, archers=t_arc)
        auto_recruit = cfg.auto_recruit
        auto_morale = cfg.auto_morale
        even_troops = bool(getattr(cfg, "even_troops", False))
        min_morale = int(cfg.min_morale) if str(cfg.min_morale).isdigit() else 95
        auto_swap_tac = bool(getattr(cfg, "auto_swap_tactician", False))
        min_tac_stam = parse_stamina_threshold(getattr(cfg, "min_tactician_stamina", "30"))
        mode = cfg.mode
        parent_id = int(cfg.parent_city_id) if (cfg.parent_city_id and str(cfg.parent_city_id).isdigit()) else None

        prefix = f"[{base_name}] " if base_name else ""
        self.after(0, self._append_bm_log, f"⚔️ {prefix}Tiến hành biên chế {len(sel_gens)} tướng...")

        if mode == 2:
            city_id = base_id
            for gid in sel_gens:
                prov.heal_general(city_id, gid)

            fresh_roster = None
            troops_added = False
            troops_balanced = False
            city_gens = {}
            current_armies = {}
            if auto_swap_tac or even_troops or (target_army.total > 0 and auto_recruit):
                fresh_roster = fetch_roster_fn(
                    self.gateway,
                    only_base_ids=[city_id],
                    include_civil=auto_swap_tac,
                    include_cities=False,
                )
                city_gens = {g.id: g for g in fresh_roster.generals_of(city_id) if g.role == "vo"}
                current_armies = {gid: fresh_roster.army_of(gid) for gid in sel_gens}
                if even_troops:
                    current_armies, troops_balanced = prov.balance_troops(
                        base_id=city_id,
                        general_ids=sel_gens,
                        current_armies=current_armies,
                        base_gens=city_gens,
                        on_log=lambda m: self.after(0, self._append_bm_log, f"   {prefix}{m}"),
                    )
                if target_army.total > 0 and auto_recruit:
                    comfort_attempted: set[int] = set()
                    exhausted_cities: set[int] = set()
                    for gid in sel_gens:
                        army = current_armies.get(gid)
                        adj_res = prov.adjust_troops(
                            base_id=city_id,
                            general_id=gid,
                            current_army=army,
                            target_army=target_army,
                            auto_recruit=True,
                            on_log=lambda m: self.after(0, self._append_bm_log, f"{prefix}{m}"),
                            comfort_attempted=comfort_attempted,
                            exhausted_cities=exhausted_cities,
                            apply_min_batch_guard=False,
                        )
                        if any(succ and diff > 0 for _, diff, succ, _ in (adj_res or [])):
                            troops_added = True

            if auto_swap_tac:
                if fresh_roster is None:
                    fresh_roster = fetch_roster_fn(
                        self.gateway,
                        only_base_ids=[city_id],
                        include_civil=True,
                        include_cities=False,
                    )
                try:
                    auto_swap_low_stamina_tacticians(
                        self.gateway,
                        roster=fresh_roster,
                        base_id=city_id,
                        general_ids=sel_gens,
                        min_stamina_pct=min_tac_stam,
                        on_log=lambda m: self.after(0, self._append_bm_log, f"   {prefix}{m}"),
                    )
                except CaptchaRequired:
                    self.after(0, self._append_bm_log, f"⛔ {prefix}Đổi Mưu sĩ gặp Captcha (mã 110).")
                    return

            if auto_morale:
                if fresh_roster is None:
                    fresh_roster = fetch_roster_fn(
                        self.gateway,
                        only_base_ids=[city_id],
                        include_civil=False,
                        include_cities=False,
                    )
                city_gens = {g.id: g for g in fresh_roster.generals_of(city_id) if g.role == "vo"}
                trainer = trainer_cls(self.gateway)

                def _on_notify_bm_city(msg):
                    self.after(0, self._append_bm_log, f"   {prefix}{msg}")

                trainer.adjust_squad_morale(
                    base_id=city_id,
                    general_ids=sel_gens,
                    target_morale=min_morale,
                    base_gens=city_gens,
                    on_notify=_on_notify_bm_city,
                    refresh_from_server=troops_added or troops_balanced,
                )
        else:
            camp_id = base_id
            for gid in sel_gens:
                prov.heal_general(camp_id, gid)

            fresh_roster = None
            troops_added = False
            troops_balanced = False
            rechecked = None
            moved_to_parent = False
            camp_gens = {}
            current_armies = {}
            if auto_swap_tac or even_troops or target_army.total > 0:
                fresh_roster = fetch_roster_fn(
                    self.gateway,
                    only_base_ids=[camp_id],
                    include_civil=auto_swap_tac,
                    include_cities=False,
                )
                camp_gens = {g.id: g for g in fresh_roster.generals_of(camp_id) if g.role == "vo"}
                current_armies = {gid: fresh_roster.army_of(gid) for gid in sel_gens}
                if even_troops:
                    current_armies, troops_balanced = prov.balance_troops(
                        base_id=camp_id,
                        general_ids=sel_gens,
                        current_armies=current_armies,
                        base_gens=camp_gens,
                        on_log=lambda m: self.after(0, self._append_bm_log, f"   {prefix}{m}"),
                    )

            if target_army.total > 0 and fresh_roster is not None:
                for gid in sel_gens:
                    army = current_armies.get(gid)
                    adj_res = prov.adjust_troops(
                        base_id=camp_id,
                        general_id=gid,
                        current_army=army,
                        target_army=target_army,
                        auto_recruit=False,
                        on_log=lambda m: self.after(0, self._append_bm_log, f"{prefix}{m}"),
                    )
                    if any(succ and diff > 0 for _, diff, succ, _ in (adj_res or [])):
                        troops_added = True

                rechecked = (
                    fetch_roster_fn(
                        self.gateway,
                        only_base_ids=[camp_id],
                        include_civil=auto_swap_tac,
                        include_cities=False,
                    )
                    if troops_added
                    else fresh_roster
                )
                rechecked_armies = (
                    {gid: rechecked.army_of(gid) for gid in sel_gens}
                    if troops_added
                    else current_armies
                )
                def_gens = []
                for gid in sel_gens:
                    a = rechecked_armies.get(gid)
                    inf = a.infantry if a else 0
                    cav = a.cavalry if a else 0
                    arc = a.archers if a else 0
                    if inf < target_army.infantry or cav < target_army.cavalry or arc < target_army.archers:
                        def_gens.append(gid)

                if def_gens:
                    if parent_id:
                        self.after(0, self._append_bm_log, f"⛺ {prefix}Quân đồn trú tại trại không đủ cho {len(def_gens)} tướng. Tự động điều về Thành mẹ {parent_id} bổ sung...")
                        prov.provision_camp_generals_with_parent_city(
                            camp_id=camp_id,
                            parent_city_id=parent_id,
                            general_ids=def_gens,
                            target_army=target_army,
                            current_armies=rechecked_armies,
                            min_morale=min_morale,
                            on_log=lambda m: self.after(0, self._append_bm_log, f"{prefix}{m}"),
                        )
                        moved_to_parent = True
                    else:
                        self.after(0, self._append_bm_log, f"⚠️ {prefix}Quân đồn trú tại trại không đủ và chưa chọn Thành mẹ! Vui lòng chọn Thành mẹ.")

            camp_roster = rechecked if (rechecked is not None and not moved_to_parent) else None
            if auto_swap_tac:
                if camp_roster is None:
                    camp_roster = fetch_roster_fn(
                        self.gateway,
                        only_base_ids=[camp_id],
                        include_civil=True,
                        include_cities=False,
                    )
                try:
                    auto_swap_low_stamina_tacticians(
                        self.gateway,
                        roster=camp_roster,
                        base_id=camp_id,
                        general_ids=sel_gens,
                        min_stamina_pct=min_tac_stam,
                        on_log=lambda m: self.after(0, self._append_bm_log, f"   {prefix}{m}"),
                    )
                except CaptchaRequired:
                    self.after(0, self._append_bm_log, f"⛔ {prefix}Đổi Mưu sĩ gặp Captcha (mã 110).")
                    return

            if auto_morale:
                if camp_roster is None:
                    camp_roster = fetch_roster_fn(
                        self.gateway,
                        only_base_ids=[camp_id],
                        include_civil=False,
                        include_cities=False,
                    )
                camp_gens = {g.id: g for g in camp_roster.generals_of(camp_id) if g.role == "vo"}
                trainer = trainer_cls(self.gateway)

                def _on_notify_bm_camp(msg):
                    self.after(0, self._append_bm_log, f"   {prefix}{msg}")

                trainer.adjust_squad_morale(
                    base_id=camp_id,
                    general_ids=sel_gens,
                    target_morale=min_morale,
                    base_gens=camp_gens,
                    on_notify=_on_notify_bm_camp,
                    refresh_from_server=troops_added or troops_balanced,
                )

    def _manual_adjust_bm_troops(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster_fn = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        self._save_bm_current_base_config()
        if not self.roster or not self.roster.bases:
            msgbox.showwarning("Cảnh báo", "Dữ liệu tướng và căn cứ chưa sẵn sàng!")
            return

        base_id = self._current_bm_base_id or self.roster.bases[0].id
        base = next((b for b in self.roster.bases if b.id == base_id), None)
        if not base:
            msgbox.showwarning("Cảnh báo", "Không tìm thấy căn cứ!")
            return

        cfg = self.bm_base_configs.get(base_id, BaseBinhManConfig())
        if not cfg.generals:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng!")
            return

        def _worker():
            try:
                self.after(0, self._append_bm_log, f"⚔️ Bắt đầu tiến trình biên chế quân đội Bình Man cho {base.name}...")
                prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)
                self._provision_base_troops(base.id, base.name, cfg, prov)
                self.after(0, self._append_bm_log, f"🏁 Hoàn tất biên chế quân đội cho căn cứ {base.name}!")
                self.roster = fetch_roster_fn(self.gateway)
                self.after(0, self._load_bm_base_config, base.id)
            except Exception as e:
                self.after(0, self._append_bm_log, f"❌ Lỗi ngoại lệ khi biên chế: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _manual_adjust_all_bm_troops(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster_fn = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        self._save_bm_current_base_config()
        if not self.roster:
            msgbox.showwarning("Cảnh báo", "Dữ liệu chưa sẵn sàng!")
            return

        enabled_bases = [b for b in self.roster.bases if self.bm_base_configs.get(b.id, BaseBinhManConfig()).enabled]
        if not enabled_bases:
            msgbox.showwarning("Cảnh báo", "Chưa chọn căn cứ nào để biên chế!")
            return

        def _worker():
            try:
                self.after(0, self._append_bm_log, f"⚔️ Bắt đầu biên chế hàng loạt cho {len(enabled_bases)} căn cứ...")
                prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)
                for b in enabled_bases:
                    cfg = self.bm_base_configs.get(b.id, BaseBinhManConfig())
                    if not cfg.generals:
                        self.after(0, self._append_bm_log, f"⏩ [{b.name}] Bỏ qua vì không có võ tướng nào được chọn.")
                        continue
                    self._provision_base_troops(b.id, b.name, cfg, prov)

                self.after(0, self._append_bm_log, "🏁 Hoàn tất biên chế quân đội cho TẤT CẢ căn cứ đã chọn!")
                self.roster = fetch_roster_fn(self.gateway)
                if self._current_bm_base_id:
                    self.after(0, self._load_bm_base_config, self._current_bm_base_id)
            except Exception as e:
                self.after(0, self._append_bm_log, f"❌ Lỗi biên chế hàng loạt: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _run_binhman_once(self):
        tasks = self._create_binhman_tasks()
        if not tasks:
            return

        def _worker():
            threads = []
            for t in tasks:
                def _sub_worker(task=t):
                    bname = getattr(task, "base_name", f"Base-{getattr(task, 'city_id', '')}")
                    res = task.run_once()
                    self.after(0, self._append_bm_log, f"⚡ [{bname}] Kết quả chạy 1 lượt: {res}")

                th = threading.Thread(target=_sub_worker, daemon=True)
                threads.append(th)
                th.start()
            for th in threads:
                th.join()

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_binhman(self):
        if not self._bm_runner or not self._bm_runner.is_alive():
            tasks = self._create_binhman_tasks()
            if not tasks:
                return
            try:
                bm_interval = max(3.0, float(self.bm_interval_var.get() or "15"))
            except ValueError:
                bm_interval = 15.0
            self._bm_runner = BinhManAutoRunner(
                tasks,
                interval=bm_interval,
                log_cb=lambda m: self.after(0, self._append_bm_log, m),
                status_cb=lambda s: None,
            )
            self._bm_runner.start()
            self.bm_start_btn.configure(text="⏹️ Dừng Bình Man", style="Danger.TButton")
        else:
            self._bm_runner.stop()
            self.bm_start_btn.configure(text="▶️ Bắt đầu Bình Man", style="Success.TButton")

