"""Phân hệ Phụ Trợ Nội Chính (Giám sát tài nguyên, Mở rương, Đốc thúc, Thám bảo, Chuyển quân)."""

import logging
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Any, Callable, Optional

from ..tasks.base import CaptchaRequired
from ..tasks.building import (
    CHEST_MAPPING,
    BuildingTask as _DefaultBuildingTask,
    chest_needs_city_switch,
    fetch_city_resources_snapshot,
    parse_boost_remaining_time,
    run_batch_open_chest,
)
from ..tasks.logistics import (
    TRANSFER_WEAPONS_DATA,
    ArmyTransferOrder,
    ArmyWeaponTransferTask,
    LogisticsTask as _DefaultLogisticsTask,
    get_transfer_weapon_name,
)
from .shared import BG, CARD, FG, MUTED, resolve_dashboard_symbol

logger = logging.getLogger("linhvuong.dashboard")


class InternalAuxMixin:
    """Quản lý Cột 3 Tab Nội Chính: ngưỡng tài nguyên/rương, phụ trợ, mở rương hàng loạt, chuyển quân."""

    def _collect_resource_profile_dict(self) -> dict:
        return {
            "gold_threshold": self.res_gold_thresh_var.get() if hasattr(self, "res_gold_thresh_var") else "100000000",
            "wood_pct": self.res_wood_pct_var.get() if hasattr(self, "res_wood_pct_var") else "70",
            "iron_pct": self.res_iron_pct_var.get() if hasattr(self, "res_iron_pct_var") else "70",
            "stone_pct": self.res_stone_pct_var.get() if hasattr(self, "res_stone_pct_var") else "70",
            "food_pct": self.res_food_pct_var.get() if hasattr(self, "res_food_pct_var") else "70",
            "gold_box_idx": self.res_gold_box_combo.current() if hasattr(self, "res_gold_box_combo") else 2,
            "tn_box_idx": self.res_tn_box_combo.current() if hasattr(self, "res_tn_box_combo") else 4,
            "auto_open_box": bool(self.bld_open_box_var.get()) if hasattr(self, "bld_open_box_var") else False,
            "resource_cities": sorted(list(self._selected_resource_cities)),
        }

    def _apply_resource_profile_dict(self, res_cfg: dict) -> Optional[str]:
        if hasattr(self, "res_gold_thresh_var") and "gold_threshold" in res_cfg:
            self.res_gold_thresh_var.set(str(res_cfg["gold_threshold"]))
        if hasattr(self, "res_wood_pct_var") and "wood_pct" in res_cfg:
            self.res_wood_pct_var.set(str(res_cfg["wood_pct"]))
        if hasattr(self, "res_iron_pct_var") and "iron_pct" in res_cfg:
            self.res_iron_pct_var.set(str(res_cfg["iron_pct"]))
        if hasattr(self, "res_stone_pct_var") and "stone_pct" in res_cfg:
            self.res_stone_pct_var.set(str(res_cfg["stone_pct"]))
        if hasattr(self, "res_food_pct_var") and "food_pct" in res_cfg:
            self.res_food_pct_var.set(str(res_cfg["food_pct"]))
        if hasattr(self, "bld_open_box_var") and "auto_open_box" in res_cfg:
            self.bld_open_box_var.set(bool(res_cfg["auto_open_box"]))
        if hasattr(self, "res_gold_box_combo") and "gold_box_idx" in res_cfg:
            try:
                g_idx = int(res_cfg["gold_box_idx"])
                if 0 <= g_idx < len(self.res_gold_box_combo["values"]):
                    self.res_gold_box_combo.current(g_idx)
            except (ValueError, IndexError):
                pass
        if hasattr(self, "res_tn_box_combo") and "tn_box_idx" in res_cfg:
            try:
                tn_idx = int(res_cfg["tn_box_idx"])
                if 0 <= tn_idx < len(self.res_tn_box_combo["values"]):
                    self.res_tn_box_combo.current(tn_idx)
            except (ValueError, IndexError):
                pass
        if "resource_cities" in res_cfg and isinstance(res_cfg["resource_cities"], list):
            self._selected_resource_cities = {int(x) for x in res_cfg["resource_cities"]}
            if hasattr(self, "bld_bases_tree"):
                for iid in self.bld_bases_tree.get_children(""):
                    try:
                        cid = int(iid)
                        vals = list(self.bld_bases_tree.item(iid, "values"))
                        if len(vals) > 1:
                            vals[1] = "☑" if cid in self._selected_resource_cities else "☐"
                            self.bld_bases_tree.item(iid, values=vals)
                    except ValueError:
                        pass
        if hasattr(self, "_append_bld_log"):
            self._append_bld_log(
                f"📂 Đã nạp cấu hình tài nguyên cho {len(self._selected_resource_cities)} thành từ hồ sơ."
            )
        return "Tài Nguyên"

    def _collect_logistics_profile_dict(self) -> dict:
        army_from_cid = self._resolve_combo_city_id(getattr(self, "army_xfer_from_combo", None), cities_only=True)
        army_to_cid = self._resolve_combo_city_id(getattr(self, "army_xfer_to_combo", None), cities_only=True)
        if not army_from_cid:
            army_from_cid = int(getattr(self, "_pending_army_xfer_from_city_id", 0) or 0)
        if not army_to_cid:
            army_to_cid = int(getattr(self, "_pending_army_xfer_to_city_id", 0) or 0)
        army_wid = self._parse_weapon_id_from_combo(getattr(self, "army_xfer_weapon_combo", None), default=406)
        return {
            "transfer_mode": (
                self.log_transfer_mode_var.get()
                if hasattr(self, "log_transfer_mode_var") and self.log_transfer_mode_var.get() in ("market", "army")
                else "market"
            ),
            "transfer_orders": list(getattr(self, "_market_xfer_orders", [])),
            "transfer_interval": self.log_interval_var.get() if hasattr(self, "log_interval_var") else "60",
            "army_transfer_from_city_id": army_from_cid,
            "army_transfer_to_city_id": army_to_cid,
            "army_transfer_weapon_id": army_wid,
            "army_transfer_general_ids": sorted(getattr(self, "_army_xfer_selected_gids", set())),
            "army_transfer_loop": bool(self.army_xfer_loop_var.get()) if hasattr(self, "army_xfer_loop_var") else True,
            "army_type_idx": self.log_army_combo.current() if hasattr(self, "log_army_combo") else 0,
            "amount": self.log_amount_var.get() if hasattr(self, "log_amount_var") else "1000",
            "auto_daily_reward": bool(self.aux_daily_reward_var.get()) if hasattr(self, "aux_daily_reward_var") else True,
            "auto_explore": bool(self.aux_explore_var.get()) if hasattr(self, "aux_explore_var") else False,
            "explore_use_whip": bool(self.aux_explore_whip_var.get()) if hasattr(self, "aux_explore_whip_var") else False,
            "explore_use_coin": bool(self.aux_explore_coin_var.get()) if hasattr(self, "aux_explore_coin_var") else False,
            "explore_turns": self.aux_explore_turns_var.get() if hasattr(self, "aux_explore_turns_var") else "1",
        }

    def _apply_logistics_profile_dict(self, log_data: dict) -> None:
        if hasattr(self, "log_transfer_mode_var") and "transfer_mode" in log_data:
            mode = str(log_data["transfer_mode"] or "market").strip().lower()
            self.log_transfer_mode_var.set(mode if mode in ("market", "army") else "market")
            self._on_transfer_mode_changed()
        if "transfer_orders" in log_data and isinstance(log_data["transfer_orders"], list):
            self._market_xfer_orders = []
            for o in log_data["transfer_orders"]:
                try:
                    self._market_xfer_orders.append({
                        "from_city_id": int(o["from_city_id"]),
                        "to_city_id": int(o["to_city_id"]),
                        "army_id": int(o["army_id"]),
                        "amount": max(1, int(o["amount"])),
                    })
                except (KeyError, TypeError, ValueError):
                    continue
            self._render_market_xfer_tree()
        if hasattr(self, "log_interval_var") and "transfer_interval" in log_data:
            self.log_interval_var.set(str(log_data["transfer_interval"]))
        if "army_transfer_from_city_id" in log_data:
            p_from = int(log_data["army_transfer_from_city_id"] or 0)
            self._pending_army_xfer_from_city_id = p_from or None
            if hasattr(self, "army_xfer_from_combo"):
                self._select_city_in_combo(self.army_xfer_from_combo, p_from, cities_only=True)
        if "army_transfer_to_city_id" in log_data:
            p_to = int(log_data["army_transfer_to_city_id"] or 0)
            self._pending_army_xfer_to_city_id = p_to or None
            if hasattr(self, "army_xfer_to_combo"):
                self._select_city_in_combo(self.army_xfer_to_combo, p_to, cities_only=True)
        if hasattr(self, "army_xfer_weapon_combo") and "army_transfer_weapon_id" in log_data:
            self._select_weapon_in_combo(self.army_xfer_weapon_combo, int(log_data["army_transfer_weapon_id"] or 406))
        if "army_transfer_general_ids" in log_data and isinstance(log_data["army_transfer_general_ids"], list):
            self._army_xfer_selected_gids = {int(g) for g in log_data["army_transfer_general_ids"] if int(g) > 0}
            if hasattr(self, "_populate_army_xfer_generals"):
                self._populate_army_xfer_generals()
        if hasattr(self, "army_xfer_loop_var") and "army_transfer_loop" in log_data:
            self.army_xfer_loop_var.set(bool(log_data["army_transfer_loop"]))
        if hasattr(self, "log_army_combo") and "army_type_idx" in log_data:
            try:
                self.log_army_combo.current(int(log_data["army_type_idx"]))
            except Exception:
                pass
        if hasattr(self, "log_amount_var") and "amount" in log_data:
            self.log_amount_var.set(str(log_data["amount"]))
        if hasattr(self, "aux_daily_reward_var") and "auto_daily_reward" in log_data:
            self.aux_daily_reward_var.set(bool(log_data["auto_daily_reward"]))
        if hasattr(self, "aux_explore_var") and "auto_explore" in log_data:
            self.aux_explore_var.set(bool(log_data["auto_explore"]))
        if "explore_use_whip" in log_data or "explore_use_coin" in log_data:
            use_whip = bool(
                log_data.get(
                    "explore_use_whip",
                    self.aux_explore_whip_var.get() if hasattr(self, "aux_explore_whip_var") else False,
                )
            )
            use_coin = bool(
                log_data.get(
                    "explore_use_coin",
                    self.aux_explore_coin_var.get() if hasattr(self, "aux_explore_coin_var") else False,
                )
            )
            if use_whip and use_coin:
                use_coin = False
            if hasattr(self, "aux_explore_whip_var"):
                self.aux_explore_whip_var.set(use_whip)
            if hasattr(self, "aux_explore_coin_var"):
                self.aux_explore_coin_var.set(use_coin)
        if hasattr(self, "aux_explore_turns_var") and "explore_turns" in log_data:
            self.aux_explore_turns_var.set(str(log_data["explore_turns"]))
        if hasattr(self, "_update_explore_turns_visibility"):
            self._update_explore_turns_visibility()

    def _build_internal_col3(self, body):
        col3 = tk.Frame(body, bg=BG)
        col3.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

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

        ttk.Button(f_res_thresh, text="Áp Dụng Thiết Lập", style="Success.TButton", command=self._apply_resource_settings).pack(pady=4)

        # 2. Chức năng phụ trợ
        f_aux = ttk.LabelFrame(col3, text="Chức năng phụ trợ", style="Card.TLabelframe")
        f_aux.pack(fill="x", padx=2, pady=4)

        r_aux1 = tk.Frame(f_aux, bg=BG)
        r_aux1.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(r_aux1, text="Thưởng hàng ngày", variable=self.aux_daily_reward_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        tk.Checkbutton(r_aux1, text="Tự an ủi", variable=self.aux_comfort_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)

        r_aux2 = tk.Frame(f_aux, bg=BG)
        r_aux2.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(r_aux2, text="DS kiến trúc", variable=self.aux_boost_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        self.aux_boost_time_lbl = tk.Label(r_aux2, text="(Còn: --)", bg=BG, fg="#4ade80", font=("Segoe UI", 8, "bold"))
        self.aux_boost_time_lbl.pack(side="left", padx=2)

        r_aux3 = tk.Frame(f_aux, bg=BG)
        r_aux3.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(r_aux3, text="Cống quận", variable=self.aux_tribute_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        self.aux_tribute_bld_combo = ttk.Combobox(r_aux3, state="readonly", width=16, values=["官府 (Quan Phủ)", "城墙 (Tường Thành)"])
        self.aux_tribute_bld_combo.set("官府 (Quan Phủ)")
        self.aux_tribute_bld_combo.pack(side="left", padx=4)

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
        self.chest_progress_lbl = tk.Label(
            r_c3, text="Tiến độ: 0% (0/0)", bg=BG, fg=MUTED, font=("Segoe UI", 8)
        )
        self.chest_progress_lbl.pack(side="right", padx=(2, 0))

        self.chest_progress_bar = ttk.Progressbar(
            f_chest, orient="horizontal", mode="determinate", maximum=100
        )
        self.chest_progress_bar.pack(fill="x", padx=4, pady=(0, 4))

        # 3. Chuyển Quân Giới (2 chế độ: Bằng Chợ / Bằng Quân đội)
        f_logis = ttk.LabelFrame(col3, text="Chuyển Quân Giới", style="Card.TLabelframe")
        f_logis.pack(fill="both", expand=True, padx=2, pady=4)

        mode_row = tk.Frame(f_logis, bg=BG)
        mode_row.pack(fill="x", padx=4, pady=(2, 4))
        tk.Radiobutton(
            mode_row,
            text="🏪 Bằng Chợ",
            variable=self.log_transfer_mode_var,
            value="market",
            command=self._on_transfer_mode_changed,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        tk.Radiobutton(
            mode_row,
            text="🐎 Bằng Quân đội",
            variable=self.log_transfer_mode_var,
            value="army",
            command=self._on_transfer_mode_changed,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        weapon_choices = [f"{wid}: {wname}" for wid, (wname, _) in sorted(TRANSFER_WEAPONS_DATA.items())]
        army_weapon_choices = [f"{wid}: {wname}" for wid, (wname, _) in sorted(TRANSFER_WEAPONS_DATA.items()) if wid < 500]

        # 3a. Khung chế độ Bằng Chợ
        self.log_market_frame = tk.Frame(f_logis, bg=BG)

        r_l1 = tk.Frame(self.log_market_frame, bg=BG)
        r_l1.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l1, text="Từ", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_from_city_combo = ttk.Combobox(r_l1, state="readonly", width=10)
        self.log_from_city_combo.pack(side="left", padx=2)
        tk.Label(r_l1, text="Đến", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_to_city_combo = ttk.Combobox(r_l1, state="readonly", width=10)
        self.log_to_city_combo.pack(side="left", padx=2)
        ttk.Button(r_l1, text="🔄", width=3, command=self._refresh_market_weapon_stock).pack(side="left", padx=2)

        r_l2 = tk.Frame(self.log_market_frame, bg=BG)
        r_l2.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l2, text="QG", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_army_combo = ttk.Combobox(r_l2, state="readonly", width=18, values=weapon_choices)
        self._select_weapon_in_combo(self.log_army_combo, 108)
        self.log_army_combo.pack(side="left", fill="x", expand=True, padx=2)
        tk.Label(r_l2, text="SL", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_l2, textvariable=self.log_amount_var, width=6).pack(side="left", padx=2)

        r_l3 = tk.Frame(self.log_market_frame, bg=BG)
        r_l3.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l3, text="Lặp lại", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_l3, textvariable=self.log_interval_var, width=4).pack(side="left", padx=2)
        tk.Label(r_l3, text="giây", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        self.log_market_status_lbl = tk.Label(r_l3, textvariable=self.log_market_status_var, bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.log_market_status_lbl.pack(side="right", padx=2)

        r_l_btn = tk.Frame(self.log_market_frame, bg=BG)
        r_l_btn.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_l_btn, text="Add", style="Success.TButton", command=self._add_army_transfer_order).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(r_l_btn, text="Xóa", style="Danger.TButton", command=self._delete_army_transfer_order).pack(side="left", expand=True, fill="x", padx=1)
        self.log_market_loop_btn = ttk.Button(
            r_l_btn, text="▶️ Chạy lặp", style="Success.TButton", command=self._toggle_market_transfer_loop
        )
        self.log_market_loop_btn.pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(r_l_btn, text="🚚 Ngay", style="Action.TButton", command=self._do_market_transfer_now).pack(side="left", expand=True, fill="x", padx=1)

        self.log_transfers_tree = ttk.Treeview(
            self.log_market_frame,
            columns=("route", "amount", "army"),
            show="headings",
            selectmode="browse",
            height=3,
        )
        self.log_transfers_tree.heading("route", text="Từ – Đến")
        self.log_transfers_tree.heading("amount", text="SL")
        self.log_transfers_tree.heading("army", text="Quân giới")
        self.log_transfers_tree.column("route", width=110)
        self.log_transfers_tree.column("amount", width=45, anchor="center")
        self.log_transfers_tree.column("army", width=95, anchor="center")
        self.log_transfers_tree.pack(fill="both", expand=True, padx=4, pady=2)

        # 3b. Khung chế độ Bằng Quân đội
        self.log_army_frame = tk.Frame(f_logis, bg=BG)

        r_a1 = tk.Frame(self.log_army_frame, bg=BG)
        r_a1.pack(fill="x", padx=4, pady=1)
        tk.Label(r_a1, text="Kho", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.army_xfer_from_combo = ttk.Combobox(r_a1, state="readonly", width=10)
        self.army_xfer_from_combo.pack(side="left", padx=2)
        tk.Label(r_a1, text="Nhận", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.army_xfer_to_combo = ttk.Combobox(r_a1, state="readonly", width=10)
        self.army_xfer_to_combo.pack(side="left", padx=2)
        ttk.Button(r_a1, text="🔄", width=3, command=self._refresh_army_weapon_stock).pack(side="left", padx=2)

        r_a2 = tk.Frame(self.log_army_frame, bg=BG)
        r_a2.pack(fill="x", padx=4, pady=1)
        tk.Label(r_a2, text="QG", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.army_xfer_weapon_combo = ttk.Combobox(r_a2, state="readonly", width=20, values=army_weapon_choices)
        self._select_weapon_in_combo(self.army_xfer_weapon_combo, 406)
        self.army_xfer_weapon_combo.pack(side="left", fill="x", expand=True, padx=2)
        tk.Checkbutton(
            r_a2,
            text="Lặp",
            variable=self.army_xfer_loop_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 8),
        ).pack(side="left")

        self.army_xfer_gen_tree = ttk.Treeview(
            self.log_army_frame,
            columns=("chk", "city", "troops"),
            show="tree headings",
            selectmode="browse",
            height=3,
        )
        self.army_xfer_gen_tree.heading("#0", text="Võ tướng")
        self.army_xfer_gen_tree.heading("chk", text="✓")
        self.army_xfer_gen_tree.heading("city", text="Thành")
        self.army_xfer_gen_tree.heading("troops", text="Quân")
        self.army_xfer_gen_tree.column("#0", width=90)
        self.army_xfer_gen_tree.column("chk", width=26, anchor="center")
        self.army_xfer_gen_tree.column("city", width=65, anchor="center")
        self.army_xfer_gen_tree.column("troops", width=55, anchor="e")
        self.army_xfer_gen_tree.pack(fill="both", expand=True, padx=4, pady=2)
        self.army_xfer_gen_tree.bind("<ButtonRelease-1>", self._on_army_xfer_gen_click)

        r_a3 = tk.Frame(self.log_army_frame, bg=BG)
        r_a3.pack(fill="x", padx=4, pady=2)
        self.army_xfer_start_btn = ttk.Button(
            r_a3, text="▶️ Bắt đầu", style="Success.TButton", command=self._toggle_army_transfer
        )
        self.army_xfer_start_btn.pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(r_a3, text="🐎 1 Chuyến", style="Action.TButton", command=self._do_army_transfer_once).pack(
            side="left", expand=True, fill="x", padx=1
        )
        self.army_xfer_status_lbl = tk.Label(
            self.log_army_frame, textvariable=self.army_xfer_status_var, bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w"
        )
        self.army_xfer_status_lbl.pack(fill="x", padx=4, pady=(0, 2))

        self._on_transfer_mode_changed()

        # 4. Hàng nút chân trang Cột 3
        footer = tk.Frame(col3, bg=BG)
        footer.pack(fill="x", padx=2, pady=(4, 0))
        ttk.Button(footer, text="Re-Login", style="Action.TButton", command=self._do_relogin).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(footer, text="💾 Lưu", style="Success.TButton", command=self._save_unified_profile_dialog).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(footer, text="📂 Load", style="Action.TButton", command=self._load_unified_profile_dialog).pack(side="left", expand=True, fill="x", padx=2)

    def _apply_resource_settings(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        gold_th = self.res_gold_thresh_var.get()
        w_pct = self.res_wood_pct_var.get()
        i_pct = self.res_iron_pct_var.get()
        s_pct = self.res_stone_pct_var.get()
        f_pct = self.res_food_pct_var.get()
        g_box = self.res_gold_box_combo.get() if hasattr(self, "res_gold_box_combo") else ""
        tn_box = self.res_tn_box_combo.get() if hasattr(self, "res_tn_box_combo") else ""
        self._append_bld_log(
            f"✅ Áp dụng thiết lập tài nguyên: Vàng<{gold_th}, TN G/S/Đ/T<{w_pct}%/{i_pct}%/{s_pct}%/{f_pct}%, Rương: {g_box.split(':')[0]} / {tn_box.split(':')[0]}"
        )
        try:
            self._save_unified_profile()
        except Exception:
            pass
        msgbox.showinfo("Thành công", "Đã lưu và áp dụng thiết lập ngưỡng tài nguyên & rương!")

    def _toggle_resource_monitor(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if not self._res_monitor_running:
            valid_base_ids = (
                {b.id for b in self.roster.bases} if (self.roster and self.roster.bases) else None
            )
            target_cids = [
                cid for cid in self._selected_resource_cities
                if valid_base_ids is None or cid in valid_base_ids
            ]
            if not target_cids:
                if self._current_bld_city_id:
                    target_cids = [self._current_bld_city_id]
                elif hasattr(self, "bld_bases_tree"):
                    children = self.bld_bases_tree.get_children("")
                    if children:
                        try:
                            target_cids = [int(children[0])]
                        except ValueError:
                            pass
            if not target_cids:
                msgbox.showwarning("Cảnh báo", "Vui lòng tích chọn cột 'Tài nguyên' cho ít nhất 1 thành!")
                return

            self._res_monitor_running = True
            self.res_monitor_btn.configure(text="Đang Giữ TN", style="Success.TButton")
            self._append_bld_log(f"▶️ Bắt đầu giám sát ngưỡng tài nguyên cho {len(target_cids)} thành...")
            self._res_monitor_thread = threading.Thread(target=self._run_resource_monitor_loop, daemon=True)
            self._res_monitor_thread.start()
        else:
            self._res_monitor_running = False
            self.res_monitor_btn.configure(text="Tài Nguyên", style="Danger.TButton")
            self._append_bld_log("⏹️ Đã dừng giám sát tài nguyên.")

    def _run_resource_monitor_loop(self):
        while self._res_monitor_running:
            valid_base_ids = (
                {b.id for b in self.roster.bases} if (self.roster and self.roster.bases) else None
            )
            target_cids = [
                cid for cid in self._selected_resource_cities
                if valid_base_ids is None or cid in valid_base_ids
            ]
            if not target_cids and self._current_bld_city_id:
                if valid_base_ids is None or self._current_bld_city_id in valid_base_ids:
                    target_cids = [self._current_bld_city_id]

            for cid in target_cids:
                if not self._res_monitor_running:
                    break
                try:
                    cname = f"Thành {cid}"
                    if self.roster:
                        b = self.roster.base_by_id(cid)
                        if b:
                            cname = b.name

                    # 1. Gọi City.ashx?id=20 + City.ashx?id=6 lấy tài nguyên và vàng hiện tại
                    snap = fetch_city_resources_snapshot(self.gateway, cid, include_gold=True)
                    if snap.get("ret", 0) == 4:
                        try:
                            self.after(0, self._append_bld_log, f"⚠️ [{cname}] Không còn tồn tại trên máy chủ (mã 4); đang đồng bộ lại...")
                            self.after(0, self.reload)
                        except Exception:
                            pass
                        continue
                    money = snap.get("money")
                    max_storage = snap.get("max_storage") or 1000000

                    # 2. Kiểm tra ngưỡng vàng
                    try:
                        gold_th = int(self.res_gold_thresh_var.get().replace(",", "").replace(".", "").strip())
                    except ValueError:
                        gold_th = 100000000
                    need_gold = money is not None and money < gold_th

                    # 3. Kiểm tra ngưỡng khoáng sản %
                    try:
                        w_pct = float(self.res_wood_pct_var.get()) / 100.0
                        i_pct = float(self.res_iron_pct_var.get()) / 100.0
                        s_pct = float(self.res_stone_pct_var.get()) / 100.0
                        f_pct = float(self.res_food_pct_var.get()) / 100.0
                    except ValueError:
                        w_pct = i_pct = s_pct = f_pct = 0.7

                    need_tn = bool(snap.get("has_resources")) and any(
                        snap.get(k) is not None and snap.get(k) < max_storage * pct
                        for k, pct in (("wood", w_pct), ("iron", i_pct), ("stone", s_pct), ("food", f_pct))
                    )

                    if need_gold or need_tn:
                        self.gateway.call("City.ashx", 50, {"tid": str(cid), "_": ""})

                    if need_gold:
                        g_box_str = self.res_gold_box_combo.get() if hasattr(self, "res_gold_box_combo") else "11"
                        try:
                            g_box_id = int(g_box_str.split(":")[0].strip())
                        except (ValueError, IndexError):
                            g_box_id = 11
                        r_box = self.gateway.call("Common.ashx", 48, {"lBoxID": str(g_box_id), "_": ""}) or {}
                        ret = r_box.get("ret", 0)
                        if ret == 0:
                            self.after(0, self._append_bld_log, f"💰 [{cname}] Vàng={money:,} < ngưỡng {gold_th:,}: Đã mở rương vàng #{g_box_id}.")
                        else:
                            self.after(0, self._append_bld_log, f"⚠️ [{cname}] Mở rương vàng #{g_box_id} thất bại (mã {ret}).")

                    if need_tn:
                        tn_box_str = self.res_tn_box_combo.get() if hasattr(self, "res_tn_box_combo") else "24"
                        try:
                            tn_box_id = int(tn_box_str.split(":")[0].strip())
                        except (ValueError, IndexError):
                            tn_box_id = 24
                        r_box = self.gateway.call("Common.ashx", 48, {"lBoxID": str(tn_box_id), "_": ""}) or {}
                        ret = r_box.get("ret", 0)
                        if ret == 0:
                            self.after(
                                0,
                                self._append_bld_log,
                                f"📦 [{cname}] Khoáng sản dưới ngưỡng: Đã mở rương TN #{tn_box_id} (Kho {max_storage:,}).",
                            )
                        else:
                            self.after(0, self._append_bld_log, f"⚠️ [{cname}] Mở rương TN #{tn_box_id} thất bại (mã {ret}).")

                except (RuntimeError, tk.TclError):
                    break
                except Exception as e:
                    try:
                        self.after(0, self._append_bld_log, f"❌ Lỗi kiểm tra tài nguyên thành {cid}: {e}")
                    except Exception:
                        pass

            for _ in range(30):
                if not self._res_monitor_running:
                    break
                time.sleep(1)

    def _on_chest_type_selected(self, _event=None):
        """Cập nhật trạng thái chọn Thành theo loại rương (vô hiệu hóa với rương cấp tài khoản)."""
        if not hasattr(self, "chest_type_combo") or not hasattr(self, "chest_city_combo"):
            return
        if getattr(self, "_chest_running", False):
            return
        chest_name = self.chest_type_combo.get().strip()
        if not chest_needs_city_switch(chest_name):
            self.chest_city_combo.configure(state="disabled")
        else:
            self.chest_city_combo.configure(state="readonly")

    def _get_selected_chest_city(self) -> tuple[Optional[int], str]:
        """Lấy Thành hợp lệ (ID dương) đang chọn cho chức năng Mở Rương Hàng Loạt."""
        if not self.roster:
            return None, ""
        sel_text = self.chest_city_combo.get().strip() if hasattr(self, "chest_city_combo") else ""
        if sel_text:
            for c in self.roster.cities:
                if sel_text in (c.display_name, c.name):
                    return c.id, c.name
            for b in self.roster.bases:
                if sel_text in (b.display_name, b.name):
                    return b.id, b.name

        if hasattr(self, "chest_city_combo"):
            sel_idx = self.chest_city_combo.current()
            if 0 <= sel_idx < len(self.roster.cities):
                c = self.roster.cities[sel_idx]
                return c.id, c.name

        cur_cid = getattr(self, "_current_bld_city_id", None)
        if cur_cid and int(cur_cid) > 0:
            b = self.roster.base_by_id(int(cur_cid))
            if b and not b.is_camp:
                return b.id, b.name
        return None, ""

    def _set_chest_controls_running(self, running: bool):
        """Chuyển trạng thái điều khiển của khung Mở Rương Hàng Loạt."""
        self._chest_running = running
        if running:
            if hasattr(self, "chest_start_btn") and self.chest_start_btn.winfo_exists():
                self.chest_start_btn.configure(state="disabled")
            if hasattr(self, "chest_stop_btn") and self.chest_stop_btn.winfo_exists():
                self.chest_stop_btn.configure(state="normal")
            if hasattr(self, "chest_type_combo") and self.chest_type_combo.winfo_exists():
                self.chest_type_combo.configure(state="disabled")
            if hasattr(self, "chest_city_combo") and self.chest_city_combo.winfo_exists():
                self.chest_city_combo.configure(state="disabled")
            if hasattr(self, "chest_times_entry") and self.chest_times_entry.winfo_exists():
                self.chest_times_entry.configure(state="disabled")
        else:
            if hasattr(self, "chest_start_btn") and self.chest_start_btn.winfo_exists():
                self.chest_start_btn.configure(state="normal")
            if hasattr(self, "chest_stop_btn") and self.chest_stop_btn.winfo_exists():
                self.chest_stop_btn.configure(state="disabled")
            if hasattr(self, "chest_type_combo") and self.chest_type_combo.winfo_exists():
                self.chest_type_combo.configure(state="readonly")
            if hasattr(self, "chest_times_entry") and self.chest_times_entry.winfo_exists():
                self.chest_times_entry.configure(state="normal")
            self._on_chest_type_selected()

    def _start_open_chest_batch(self):
        """Khởi chạy tác vụ Mở Rương Hàng Loạt bằng đa luồng."""
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_chest_running", False):
            return
        if self.gateway is None:
            msgbox.showwarning("Cảnh báo", "Chưa kết nối tài khoản game!")
            return

        chest_name = self.chest_type_combo.get().strip() if hasattr(self, "chest_type_combo") else ""
        if chest_name not in CHEST_MAPPING:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn loại rương hợp lệ!")
            return

        times_raw = self.chest_times_var.get().strip() if hasattr(self, "chest_times_var") else ""
        try:
            times = int(times_raw)
            if times <= 0:
                raise ValueError
        except (ValueError, TypeError):
            msgbox.showerror("Lỗi", "Số lượt mở rương phải là số nguyên dương!")
            return

        if times > 5000:
            if not msgbox.askyesno(
                "Xác nhận",
                f"Bạn sắp mở {times} rương. Số lượng lớn có thể mất nhiều thời gian.\nBạn có muốn tiếp tục?",
            ):
                return

        needs_switch = chest_needs_city_switch(chest_name)
        if needs_switch:
            city_id, city_name = self._get_selected_chest_city()
            if city_id is None or city_id <= 0:
                msgbox.showwarning(
                    "Cảnh báo",
                    "Vui lòng chọn một Thành hợp lệ (không phải Doanh trại) để mở loại rương này!",
                )
                return
        else:
            city_id, city_name = None, ""

        self._chest_stop_event = threading.Event()
        q: queue.Queue = queue.Queue()
        self._chest_queue = q
        self._set_chest_controls_running(True)
        if hasattr(self, "chest_progress_bar"):
            self.chest_progress_bar.configure(value=0)
        if hasattr(self, "chest_progress_lbl"):
            self.chest_progress_lbl.configure(text=f"Tiến độ: 0% (0/{times})")

        if needs_switch:
            self._append_bld_log(f"📦 Bắt đầu mở {times}x [{chest_name}] tại Thành [{city_name}]...")
        else:
            self._append_bld_log(f"📦 Bắt đầu mở {times}x [{chest_name}]...")

        stop_ev = self._chest_stop_event

        def _worker():
            summary: dict[str, Any] = {
                "success_count": 0,
                "failed_count": 0,
                "completed": 0,
                "total": times,
                "aborted_reason": None,
                "last_ret": None,
            }
            err_msg: Optional[str] = None
            try:
                summary = run_batch_open_chest(
                    gateway=self.gateway,
                    chest_name=chest_name,
                    times=times,
                    city_id=city_id,
                    city_name=city_name,
                    max_workers=5,
                    stop_event=stop_ev,
                    on_log=lambda m: q.put(("log", m)),
                    on_progress=lambda done, total, pct: q.put(("progress", done, total, pct)),
                )
            except Exception as ex:
                logger.exception(f"Lỗi khi mở rương hàng loạt: {ex}")
                err_msg = str(ex)
                q.put(("log", f"❌ Lỗi mở rương hàng loạt: {ex}"))
            finally:
                q.put(("done", chest_name, times, summary, err_msg))

        self._chest_thread = threading.Thread(target=_worker, name="OpenChestBatchRunner", daemon=True)
        self._chest_thread.start()
        self.after(20, self._poll_chest_queue)

    def _poll_chest_queue(self):
        """Rút tiến độ, log và kết quả Mở Rương Hàng Loạt trên luồng giao diện chính."""
        q = getattr(self, "_chest_queue", None)
        if q is None:
            return
        keep_polling = True
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            kind = item[0]
            if kind == "log":
                self._append_bld_log(item[1])
            elif kind == "progress":
                _, done, total, pct = item
                if hasattr(self, "chest_progress_bar") and self.chest_progress_bar.winfo_exists():
                    self.chest_progress_bar.configure(value=pct)
                if hasattr(self, "chest_progress_lbl") and self.chest_progress_lbl.winfo_exists():
                    self.chest_progress_lbl.configure(text=f"Tiến độ: {pct:.0f}% ({done}/{total})")
            elif kind == "done":
                _, chest_name, times, summary, _err = item
                keep_polling = False
                self._set_chest_controls_running(False)
                succ = summary.get("success_count", 0)
                fail = summary.get("failed_count", 0)
                comp = summary.get("completed", 0)
                tot = summary.get("total", times)
                pct = (comp / tot * 100.0) if tot > 0 else 0.0
                if hasattr(self, "chest_progress_bar") and self.chest_progress_bar.winfo_exists():
                    self.chest_progress_bar.configure(value=pct)
                if hasattr(self, "chest_progress_lbl") and self.chest_progress_lbl.winfo_exists():
                    self.chest_progress_lbl.configure(text=f"Tiến độ: {pct:.0f}% ({comp}/{tot})")
                if summary.get("aborted_reason") == "captcha" and hasattr(self, "status"):
                    self.status.set("Cần giải Captcha")
                self._append_bld_log(
                    f"🏁 Kết thúc mở [{chest_name}]: Thành công {succ}/{tot}, Thất bại {fail}."
                )
        if keep_polling and getattr(self, "_chest_running", False):
            self.after(20, self._poll_chest_queue)

    def _stop_open_chest_batch(self):
        """Dừng tiến trình Mở Rương Hàng Loạt đang chạy."""
        if getattr(self, "_chest_running", False) and getattr(self, "_chest_stop_event", None):
            self._chest_stop_event.set()
            if hasattr(self, "chest_stop_btn") and self.chest_stop_btn.winfo_exists():
                self.chest_stop_btn.configure(state="disabled")
            self._append_bld_log("⏹️ Đang dừng tiến trình mở rương...")

    def _cancel_after_timer(self, attr_name: str):
        """Hủy lịch after đang chờ theo tên thuộc tính nếu có."""
        old_id = getattr(self, attr_name, None)
        if old_id is not None:
            try:
                self.after_cancel(old_id)
            except Exception:
                pass
            setattr(self, attr_name, None)

    def _tick_aux_countdown(
        self,
        *,
        seconds_attr: str,
        after_attr: str,
        label_attr: str,
        zero_text: str,
        zero_fg: str,
        tick_cb: Callable[[], None],
        on_zero: Optional[Callable[[], None]] = None,
    ):
        """Giảm bộ đếm ngược mỗi giây và kích hoạt hành động khi về 0."""
        setattr(self, after_attr, None)
        try:
            lbl = getattr(self, label_attr, None)
            if not (lbl is not None and lbl.winfo_exists()):
                return
            secs = max(0, int(getattr(self, seconds_attr, 0) or 0) - 1)
            setattr(self, seconds_attr, secs)
            if secs > 0:
                lbl.configure(text=f"(Còn: {self._format_explore_countdown(secs)})", fg="#4ade80")
                setattr(self, after_attr, self.after(1000, tick_cb))
            else:
                lbl.configure(text=zero_text, fg=zero_fg)
                if on_zero is not None:
                    on_zero()
        except (RuntimeError, tk.TclError):
            pass

    def _cancel_boost_countdown_timer(self):
        self._cancel_after_timer("_boost_countdown_after_id")

    def _tick_boost_countdown(self):
        self._tick_aux_countdown(
            seconds_attr="_boost_left_seconds",
            after_attr="_boost_countdown_after_id",
            label_attr="aux_boost_time_lbl",
            zero_text="(Hết hạn)",
            zero_fg="#f87171",
            tick_cb=self._tick_boost_countdown,
            on_zero=lambda: self._check_and_update_boost_status(async_check=True)
            if self.aux_boost_var.get()
            else None,
        )

    def _update_boost_countdown_ui(self, remaining: int):
        def _apply():
            try:
                if not (hasattr(self, "aux_boost_time_lbl") and self.aux_boost_time_lbl.winfo_exists()):
                    return
                self._cancel_boost_countdown_timer()
                secs = max(0, int(remaining))
                self._boost_left_seconds = secs
                if secs > 0:
                    self.aux_boost_time_lbl.configure(
                        text=f"(Còn: {self._format_explore_countdown(secs)})",
                        fg="#4ade80",
                    )
                    self._boost_countdown_after_id = self.after(1000, self._tick_boost_countdown)
                else:
                    self.aux_boost_time_lbl.configure(text="(Hết hạn)", fg="#f87171")
            except (RuntimeError, tk.TclError):
                pass

        if threading.current_thread() is threading.main_thread():
            _apply()
        else:
            try:
                self.after(0, _apply)
            except (RuntimeError, tk.TclError):
                pass

    def _check_and_update_boost_status(self, async_check: bool = True):
        """Kiểm tra thời gian còn lại của DS kiến trúc (xây 3 công trình) và tự kích hoạt nếu hết hạn."""
        building_task_cls = resolve_dashboard_symbol("BuildingTask", _DefaultBuildingTask)

        def run_check():
            if not self.gateway:
                return
            try:
                city_id = getattr(self, "_current_bld_city_id", 0) or 0
                resp = self.gateway.call("Common.ashx", 77, {"cid": str(city_id), "_": ""}) or {}
                remaining = parse_boost_remaining_time(resp, city_id)
                self._update_boost_countdown_ui(remaining)

                if remaining <= 0:
                    if self.aux_boost_var.get():
                        now_ts = time.time()
                        last_act = max(
                            getattr(self, "_last_boost_act_time", 0),
                            getattr(building_task_cls, "_last_boost_act_time", 0),
                        )
                        if now_ts - last_act > 60:
                            self._last_boost_act_time = now_ts
                            building_task_cls._last_boost_act_time = now_ts
                            msg = "⚡ DS kiến trúc đã hết hạn. Đang tự kích hoạt lại (3 vị trí thi công)..."
                            if threading.current_thread() is threading.main_thread():
                                self._append_bld_log(msg)
                            else:
                                try:
                                    self.after(0, self._append_bld_log, msg)
                                except RuntimeError:
                                    pass
                            act_resp = self.gateway.call(
                                "OPT.ashx",
                                69,
                                {"type": "3", "param1": "0", "param2": "0", "paytype": "2", "_": ""},
                            ) or {}
                            ret = act_resp.get("ret", 0)
                            if ret == 0:
                                ok_msg = "✅ Kích hoạt thành công DS kiến trúc (3 vị trí thi công)!"
                                if threading.current_thread() is threading.main_thread():
                                    self._append_bld_log(ok_msg)
                                else:
                                    try:
                                        self.after(0, self._append_bld_log, ok_msg)
                                    except RuntimeError:
                                        pass
                                time.sleep(1)
                                self._check_and_update_boost_status(async_check=async_check)
                            else:
                                fail_msg = f"⚠️ Kích hoạt DS kiến trúc thất bại (mã {ret})."
                                if threading.current_thread() is threading.main_thread():
                                    self._append_bld_log(fail_msg)
                                else:
                                    try:
                                        self.after(0, self._append_bld_log, fail_msg)
                                    except RuntimeError:
                                        pass
            except Exception as e:
                logger.debug(f"Lỗi kiểm tra DS kiến trúc: {e}")

        if async_check:
            t = threading.Thread(target=run_check, daemon=True)
            t.start()
            return t
        else:
            run_check()

    def _update_explore_turns_visibility(self):
        """Ẩn/hiện ô nhập số lượt Thám bảo tùy theo checkbox Dùng Roi / Dùng Coin."""
        if not hasattr(self, "aux_explore_turns_frame"):
            return
        show = bool(self.aux_explore_whip_var.get() or self.aux_explore_coin_var.get())
        if show:
            if not self.aux_explore_turns_frame.winfo_manager():
                self.aux_explore_turns_frame.pack(side="left", padx=2)
        else:
            self.aux_explore_turns_frame.pack_forget()

    def _on_explore_clear_mode_changed(self, source: str):
        """Đảm bảo Dùng Roi và Dùng Coin loại trừ lẫn nhau và đồng bộ ô Số lượt."""
        if source == "whip" and self.aux_explore_whip_var.get():
            self.aux_explore_coin_var.set(False)
        elif source == "coin" and self.aux_explore_coin_var.get():
            self.aux_explore_whip_var.set(False)
        self._update_explore_turns_visibility()
        if self.aux_explore_var.get() and (self.aux_explore_whip_var.get() or self.aux_explore_coin_var.get()):
            self._check_and_run_explore(async_check=True)

    def _on_aux_explore_toggled(self):
        """Kích hoạt hoặc dừng kiểm tra/chạy Thám bảo khi bật tắt checkbox."""
        self._explore_stop_requested = not bool(self.aux_explore_var.get())
        self._check_and_run_explore(async_check=True)

    def _log_explore(self, msg: str):
        """Ghi nhật ký Thám bảo an toàn luồng vào Nhật ký Nội Chính."""
        if threading.current_thread() is threading.main_thread():
            self._append_bld_log(msg)
        else:
            try:
                self.after(0, self._append_bld_log, msg)
            except (RuntimeError, tk.TclError):
                pass

    def _reset_explore_clear_mode_ui(self):
        """Bỏ tích Dùng Roi / Dùng Coin và ẩn ô Số lượt sau khi hoàn tất lượt."""
        def _do():
            try:
                if hasattr(self, "aux_explore_whip_var"):
                    self.aux_explore_whip_var.set(False)
                if hasattr(self, "aux_explore_coin_var"):
                    self.aux_explore_coin_var.set(False)
                self._update_explore_turns_visibility()
            except (RuntimeError, tk.TclError):
                pass

        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            try:
                self.after(0, _do)
            except (RuntimeError, tk.TclError):
                pass

    @staticmethod
    def _format_explore_countdown(seconds: int) -> str:
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}:{m:02d}:{s:02d}"

    def _cancel_explore_countdown_timer(self):
        self._cancel_after_timer("_explore_countdown_after_id")

    def _tick_explore_countdown(self):
        self._tick_aux_countdown(
            seconds_attr="_explore_left_seconds",
            after_attr="_explore_countdown_after_id",
            label_attr="aux_explore_time_lbl",
            zero_text="(Sẵn sàng)",
            zero_fg="#4ade80",
            tick_cb=self._tick_explore_countdown,
            on_zero=lambda: self._check_and_run_explore(async_check=True)
            if self.aux_explore_var.get() and not self._explore_worker_running
            else None,
        )

    def _update_explore_countdown_ui(
        self, left_seconds: Optional[int], error_text: str = "", seq: Optional[int] = None
    ):
        def _apply():
            try:
                if seq is not None and seq != self._explore_seq:
                    return
                if not (hasattr(self, "aux_explore_time_lbl") and self.aux_explore_time_lbl.winfo_exists()):
                    return
                self._cancel_explore_countdown_timer()
                if error_text or left_seconds is None:
                    self._explore_left_seconds = 0
                    self.aux_explore_time_lbl.configure(text=f"({error_text or 'Lỗi'})", fg="#f87171")
                    return
                secs = max(0, int(left_seconds))
                self._explore_left_seconds = secs
                if secs > 0:
                    self.aux_explore_time_lbl.configure(
                        text=f"(Còn: {self._format_explore_countdown(secs)})",
                        fg="#4ade80",
                    )
                    self._explore_countdown_after_id = self.after(1000, self._tick_explore_countdown)
                else:
                    self.aux_explore_time_lbl.configure(text="(Sẵn sàng)", fg="#4ade80")
            except (RuntimeError, tk.TclError):
                pass

        if threading.current_thread() is threading.main_thread():
            _apply()
        else:
            try:
                self.after(0, _apply)
            except (RuntimeError, tk.TclError):
                pass

    def _api_check_explore_status(self) -> tuple[bool, int, str]:
        """Gọi Common.ashx?id=140 (lAction=0) kiểm tra thời gian chờ Thám bảo."""
        try:
            resp = self.gateway.call("Common.ashx", 140, {"lAction": "0", "lParam": "0", "_": ""})
            if not isinstance(resp, dict):
                return False, 0, "Lỗi kết nối"
            ret_val = resp.get("ret", -1)
            if ret_val != 0:
                return False, 0, f"Lỗi API {ret_val}"
            try:
                left_seconds = max(0, int(resp.get("left", 0) or 0))
            except (TypeError, ValueError):
                left_seconds = 0
            return left_seconds == 0, left_seconds, ""
        except Exception as e:
            return False, 0, f"Lỗi: {e}"

    def _api_clear_explore_cooldown(self, clear_type: int) -> bool:
        """Gọi Common.ashx?id=140 (lAction=2) xóa thời gian chờ bằng Roi (1) hoặc Coin (2)."""
        try:
            resp = self.gateway.call(
                "Common.ashx", 140, {"lAction": "2", "lParam": str(clear_type), "_": ""}
            )
            return isinstance(resp, dict) and resp.get("ret", -1) == 0
        except Exception:
            return False

    def _api_perform_explore(self) -> tuple[bool, str]:
        """Gọi Common.ashx?id=140 (lAction=1) thực hiện Thám bảo và trích xuất tên vật phẩm."""
        try:
            resp = self.gateway.call("Common.ashx", 140, {"lAction": "1", "lParam": "0", "_": ""})
            if not isinstance(resp, dict) or resp.get("ret", -1) != 0:
                return False, ""
            bonus = str(resp.get("bonus", "") or "")
            match = re.search(r"获得：([^×<\n]+)", bonus)
            if match:
                item_name = match.group(1).strip()
            else:
                item_name = bonus.strip() or "Vật phẩm"
            return True, item_name
        except Exception:
            return False, ""

    def _check_and_run_explore(self, async_check: bool = True):
        """Kiểm tra thời gian chờ Thám bảo và tự động thám bảo theo chế độ đã chọn."""
        if not self.gateway:
            return None
        if async_check and self._explore_worker_running:
            return None

        on_main = threading.current_thread() is threading.main_thread()
        if on_main:
            auto_explore = bool(self.aux_explore_var.get())
            use_whip = bool(self.aux_explore_whip_var.get())
            use_coin = bool(self.aux_explore_coin_var.get())
            turns_str = self.aux_explore_turns_var.get().strip()
            if auto_explore:
                self._explore_stop_requested = False
        else:
            auto_explore = False
            use_whip = False
            use_coin = False
            turns_str = "1"

        def run_check():
            if not self._explore_lock.acquire(blocking=not async_check):
                return
            try:
                self._explore_worker_running = True
                self._explore_seq += 1
                seq = self._explore_seq

                if auto_explore and (use_whip or use_coin):
                    clear_type = 1 if use_whip else 2
                    mode_name = "Roi" if clear_type == 1 else "Coin"
                    try:
                        turns = int(turns_str)
                    except (TypeError, ValueError):
                        turns = 0

                    if turns <= 0:
                        self._log_explore(
                            "⚠️ Số lượt thám bảo phải là số nguyên dương (> 0). Chuyển về chế độ chờ countdown."
                        )
                        self._reset_explore_clear_mode_ui()
                    else:
                        self._log_explore(f"🧭 Bắt đầu Thám bảo {turns} lượt (Dùng {mode_name})...")
                        success_count = 0
                        for turn_idx in range(1, turns + 1):
                            if self._explore_stop_requested:
                                self._log_explore(f"🛑 Đã dừng Thám bảo ở lượt {turn_idx}/{turns}.")
                                break
                            can_explore, left_seconds, err = self._api_check_explore_status()
                            if err:
                                self._log_explore(f"❌ Lượt {turn_idx}/{turns}: Lỗi kiểm tra Thám bảo ({err}).")
                                break
                            if not can_explore and left_seconds > 0:
                                if not self._api_clear_explore_cooldown(clear_type):
                                    self._log_explore(
                                        f"⚠️ Lượt {turn_idx}/{turns}: Không thể xóa thời gian chờ (hết {mode_name}?), chuyển về chế độ chờ countdown."
                                    )
                                    break
                                can_explore, left_seconds, err = self._api_check_explore_status()
                                if err or not can_explore:
                                    self._log_explore(
                                        f"❌ Lượt {turn_idx}/{turns}: Vẫn còn thời gian chờ sau khi xóa ({err or f'{left_seconds}s'})."
                                    )
                                    break
                            ok, item_name = self._api_perform_explore()
                            if ok:
                                success_count += 1
                                self._log_explore(f"🧭 Thám bảo lượt {turn_idx}/{turns}: Nhận được {item_name}")
                            else:
                                self._log_explore(f"❌ Thám bảo lượt {turn_idx}/{turns} thất bại.")
                                break
                        self._reset_explore_clear_mode_ui()
                        self._log_explore(f"✅ Hoàn tất Thám bảo ({success_count}/{turns} lượt thành công).")
                        can_explore, left_seconds, err = self._api_check_explore_status()
                        self._update_explore_countdown_ui(None if err else left_seconds, err, seq=seq)
                        return

                can_explore, left_seconds, err = self._api_check_explore_status()
                if err:
                    self._update_explore_countdown_ui(None, err, seq=seq)
                    return

                if can_explore and auto_explore and not self._explore_stop_requested:
                    ok, item_name = self._api_perform_explore()
                    if ok:
                        self._log_explore(f"🧭 Thám bảo tự động: Nhận được {item_name}")
                    else:
                        self._log_explore("⚠️ Thám bảo tự động thất bại.")
                    can_explore, left_seconds, err = self._api_check_explore_status()
                    if err:
                        self._update_explore_countdown_ui(None, err, seq=seq)
                        return

                self._update_explore_countdown_ui(left_seconds, "", seq=seq)
            except Exception as e:
                logger.debug(f"Lỗi kiểm tra/chạy Thám bảo: {e}")
            finally:
                self._explore_worker_running = False
                self._explore_lock.release()

        if async_check:
            t = threading.Thread(target=run_check, daemon=True)
            t.start()
            return t
        run_check()
        return None

    def _schedule_periodic_boost_check(self):
        # Hủy timer cũ để tránh nhân bản chuỗi lặp mỗi lần reload roster
        old_id = getattr(self, "_boost_after_id", None)
        if old_id is not None:
            try:
                self.after_cancel(old_id)
            except Exception:
                pass
            self._boost_after_id = None
        try:
            if hasattr(self, "aux_boost_time_lbl") and self.aux_boost_time_lbl.winfo_exists():
                self._check_and_update_boost_status(async_check=True)
                self._check_and_run_explore(async_check=True)
                today_str = time.strftime("%Y-%m-%d")
                if getattr(self, "aux_daily_reward_var", None) and self.aux_daily_reward_var.get():
                    if getattr(self, "_last_daily_claim_date", None) != today_str:
                        self._last_daily_claim_date = today_str
                        self._do_claim_daily()
                self._boost_after_id = self.after(60000, self._schedule_periodic_boost_check)
        except (RuntimeError, tk.TclError):
            pass

    @staticmethod
    def _parse_weapon_id_from_combo(combo, default: int = 108) -> int:
        raw = str(combo.get() or "") if combo is not None else ""
        head = raw.split(":", 1)[0].strip()
        try:
            wid = int(head)
            if wid > 0:
                return wid
        except ValueError:
            pass
        return default

    def _resolve_combo_city_id(self, combo, *, cities_only: bool = False) -> int:
        if combo is None or not getattr(self, "roster", None):
            return 0
        pool = self.roster.cities if cities_only else self.roster.bases
        idx = combo.current()
        if 0 <= idx < len(pool):
            return int(pool[idx].id)
        text = str(combo.get() or "").strip()
        for b in pool:
            if b.display_name == text or b.name == text:
                return int(b.id)
        return 0

    def _select_city_in_combo(self, combo, city_id: int, *, cities_only: bool = False) -> None:
        if combo is None or not getattr(self, "roster", None) or not city_id:
            return
        pool = self.roster.cities if cities_only else self.roster.bases
        for idx, b in enumerate(pool):
            if int(b.id) == int(city_id):
                if 0 <= idx < len(combo["values"]):
                    combo.current(idx)
                break

    @staticmethod
    def _select_weapon_in_combo(combo, weapon_id: int) -> None:
        if combo is None:
            return
        vals = list(combo["values"] or [])
        prefix = f"{int(weapon_id)}:"
        for idx, val in enumerate(vals):
            if str(val).startswith(prefix):
                combo.current(idx)
                return

    def _on_transfer_mode_changed(self):
        mode = self.log_transfer_mode_var.get() if hasattr(self, "log_transfer_mode_var") else "market"
        if hasattr(self, "log_market_frame") and hasattr(self, "log_army_frame"):
            if mode == "army":
                self.log_market_frame.pack_forget()
                self.log_army_frame.pack(fill="both", expand=True)
            else:
                self.log_army_frame.pack_forget()
                self.log_market_frame.pack(fill="both", expand=True)

    def _city_display_name(self, city_id: int) -> str:
        if getattr(self, "roster", None):
            b = self.roster.base_by_id(city_id)
            if b:
                return b.name
        return str(city_id)

    def _render_market_xfer_tree(self) -> None:
        if not hasattr(self, "log_transfers_tree"):
            return
        self.log_transfers_tree.delete(*self.log_transfers_tree.get_children())
        for o in getattr(self, "_market_xfer_orders", []):
            route = f"{self._city_display_name(o['from_city_id'])} ➔ {self._city_display_name(o['to_city_id'])}"
            wname = f"{o['army_id']}: {get_transfer_weapon_name(o['army_id'])}"
            self.log_transfers_tree.insert("", "end", values=(route, o["amount"], wname))

    def _refresh_weapon_stock_for(self, city_id: int, combo, *, exclude_siege: bool = False) -> None:
        if city_id <= 0:
            msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn Thành hợp lệ để tải kho Quân giới!")
            return
        LogisticsTask = resolve_dashboard_symbol("LogisticsTask", _DefaultLogisticsTask)

        def _worker():
            try:
                stocks = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_bld_log, m)).get_city_weapon_stocks(city_id)
            except CaptchaRequired:
                self.after(0, self._append_bld_log, "⚠️ Tải kho quân giới gặp Captcha (mã 110).")
                return
            except Exception as exc:
                self.after(0, self._append_bld_log, f"❌ Lỗi tải kho quân giới: {exc}")
                return

            def _apply():
                if getattr(self, "_destroyed", False):
                    return
                self._city_weapons_cache[city_id] = stocks
                cur_wid = self._parse_weapon_id_from_combo(combo, default=0)
                seen: set[int] = set()
                vals: list[str] = []
                for s in stocks:
                    wid = int(s["id"])
                    if exclude_siege and wid >= 500:
                        continue
                    seen.add(wid)
                    vals.append(f"{wid}: {s['name']} [{s['count']:,}]")
                for wid, (wname, _) in sorted(TRANSFER_WEAPONS_DATA.items()):
                    if wid in seen or (exclude_siege and wid >= 500):
                        continue
                    vals.append(f"{wid}: {wname}")
                combo["values"] = vals
                if cur_wid:
                    self._select_weapon_in_combo(combo, cur_wid)
                elif vals:
                    combo.current(0)
                self._append_bld_log(f"🔄 Đã tải kho Thành {self._city_display_name(city_id)}: {len(stocks)} loại Quân giới.")

            try:
                self.after(0, _apply)
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_market_weapon_stock(self):
        cid = self._resolve_combo_city_id(getattr(self, "log_from_city_combo", None), cities_only=False)
        self._refresh_weapon_stock_for(cid, self.log_army_combo, exclude_siege=False)

    def _refresh_army_weapon_stock(self):
        cid = self._resolve_combo_city_id(getattr(self, "army_xfer_from_combo", None), cities_only=True)
        self._refresh_weapon_stock_for(cid, self.army_xfer_weapon_combo, exclude_siege=True)

    def _add_army_transfer_order(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        f_city = self.log_from_city_combo.get()
        t_city = self.log_to_city_combo.get()
        if not f_city or not t_city or f_city == t_city:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn 2 Thành đi và đến khác nhau!")
            return
        from_cid = self._resolve_combo_city_id(self.log_from_city_combo, cities_only=False)
        to_cid = self._resolve_combo_city_id(self.log_to_city_combo, cities_only=False)
        if from_cid < 0 or to_cid < 0:
            msgbox.showwarning("Cảnh báo", "Chuyển quân giới bằng Chợ chỉ hỗ trợ giữa các Thành (không hỗ trợ Doanh trại)!")
            return
        army_label = self.log_army_combo.get()
        wid = self._parse_weapon_id_from_combo(self.log_army_combo, default=108)
        try:
            amt = max(1, int(str(self.log_amount_var.get() or "1").strip()))
        except ValueError:
            amt = 1
        if from_cid > 0 and to_cid > 0:
            self._market_xfer_orders.append({
                "from_city_id": from_cid,
                "to_city_id": to_cid,
                "army_id": wid,
                "amount": amt,
            })
        route = f"{f_city} ➔ {t_city}"
        self.log_transfers_tree.insert("", "end", values=(route, str(amt), army_label))
        self._append_bld_log(f"➕ Thêm lệnh chuyển quân giới: {route} | SL: {amt} | {army_label}")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _delete_army_transfer_order(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.log_transfers_tree.selection()
        if not sel:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn 1 lệnh chuyển quân giới trong bảng để xóa!")
            return
        children = list(self.log_transfers_tree.get_children())
        indices = sorted((children.index(item) for item in sel if item in children), reverse=True)
        for idx in indices:
            if 0 <= idx < len(getattr(self, "_market_xfer_orders", [])):
                self._market_xfer_orders.pop(idx)
        for item in sel:
            self.log_transfers_tree.delete(item)
        self._append_bld_log("🗑️ Đã xóa lệnh chuyển quân giới đã chọn.")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _do_market_transfer_now(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        LogisticsTask = resolve_dashboard_symbol("LogisticsTask", _DefaultLogisticsTask)
        from_cid = self._resolve_combo_city_id(self.log_from_city_combo, cities_only=False)
        to_cid = self._resolve_combo_city_id(self.log_to_city_combo, cities_only=False)
        if from_cid <= 0 or to_cid <= 0 or from_cid == to_cid:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn 2 Thành đi và đến khác nhau!")
            return
        wid = self._parse_weapon_id_from_combo(self.log_army_combo, default=108)
        try:
            amt = max(1, int(str(self.log_amount_var.get() or "1").strip()))
        except ValueError:
            amt = 1
        order = ArmyTransferOrder(from_city_id=from_cid, to_city_id=to_cid, army_id=wid, amount=amt)
        task = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_bld_log, m))

        def _worker():
            try:
                task.transfer_army(order)
            except CaptchaRequired:
                self.after(0, self._append_bld_log, "⚠️ Chuyển quân giới bằng Chợ gặp Captcha (mã 110)!")
            except Exception as exc:
                self.after(0, self._append_bld_log, f"❌ Lỗi chuyển quân giới: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_market_transfer_loop(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        LogisticsTask = resolve_dashboard_symbol("LogisticsTask", _DefaultLogisticsTask)
        if self._market_xfer_running:
            self._market_xfer_running = False
            self._market_xfer_stop.set()
            self.log_market_status_var.set("Đã dừng")
            self.log_market_loop_btn.configure(text="▶️ Chạy lặp", style="Success.TButton")
            return
        if not self._market_xfer_orders:
            msgbox.showwarning("Cảnh báo", "Vui lòng thêm ít nhất 1 lệnh vào bảng hàng đợi!")
            return
        try:
            interval = max(3.0, float(self.log_interval_var.get() or "60"))
        except ValueError:
            interval = 60.0
        self._market_xfer_running = True
        self._market_xfer_stop.clear()
        self.log_market_status_var.set(f"Đang chạy lặp mỗi {int(interval)}s")
        self.log_market_loop_btn.configure(text="⏹️ Dừng lặp", style="Danger.TButton")

        def _loop():
            task = LogisticsTask(
                self.gateway,
                auto_comfort=False,
                auto_daily_reward=False,
                notify=lambda m: self.after(0, self._append_bld_log, m),
            )
            final_status = "Đã dừng"
            try:
                while not self._market_xfer_stop.is_set():
                    for o in list(self._market_xfer_orders):
                        if self._market_xfer_stop.is_set():
                            break
                        order = ArmyTransferOrder(
                            from_city_id=int(o["from_city_id"]),
                            to_city_id=int(o["to_city_id"]),
                            army_id=int(o["army_id"]),
                            amount=int(o["amount"]),
                        )
                        stock = task.get_garrison_troops(order.from_city_id)
                        available = stock.get(order.army_id, 0)
                        if available < order.amount:
                            wname = get_transfer_weapon_name(order.army_id)
                            self.after(
                                0,
                                self._append_bld_log,
                                f"⏹️ Thành {order.from_city_id} thiếu {wname} ({available:,}/{order.amount:,}) — dừng lặp.",
                            )
                            final_status = "Đã dừng: thiếu quân giới"
                            return
                        if not task.transfer_army(order):
                            final_status = "Đã dừng: chuyển thất bại"
                            return
                    if self._market_xfer_stop.wait(interval):
                        break
            except CaptchaRequired:
                self.after(0, self._append_bld_log, "⚠️ Chuyển quân giới tạm dừng do Captcha (mã 110)!")
                final_status = "Tạm dừng (Captcha)"
            except Exception as exc:
                self.after(0, self._append_bld_log, f"❌ Lỗi vòng lặp chuyển quân giới: {exc}")
                final_status = f"Lỗi: {exc}"
            finally:
                def _reset():
                    self._market_xfer_running = False
                    if not getattr(self, "_destroyed", False):
                        self.log_market_status_var.set(final_status)
                        self.log_market_loop_btn.configure(text="▶️ Chạy lặp", style="Success.TButton")
                try:
                    self.after(0, _reset)
                except (RuntimeError, tk.TclError):
                    pass

        self._market_xfer_thread = threading.Thread(target=_loop, daemon=True)
        self._market_xfer_thread.start()

    def _populate_army_xfer_generals(self):
        if not hasattr(self, "army_xfer_gen_tree") or not getattr(self, "roster", None):
            return
        self.army_xfer_gen_tree.delete(*self.army_xfer_gen_tree.get_children())
        seen_gids: set[int] = set()
        for b in self.roster.bases:
            for g in self.roster.generals_of(b.id):
                if g.role != "vo" or g.id in seen_gids:
                    continue
                seen_gids.add(g.id)
                chk = "☑" if g.id in self._army_xfer_selected_gids else "☐"
                army = self.roster.army_of(g.id)
                troops = army.total if army else 0
                self.army_xfer_gen_tree.insert(
                    "", "end", iid=str(g.id), text=g.name, values=(chk, b.name, f"{troops:,}")
                )

    def _on_army_xfer_gen_click(self, event):
        region = self.army_xfer_gen_tree.identify("region", event.x, event.y)
        iid = self.army_xfer_gen_tree.identify_row(event.y)
        if not iid or region == "heading":
            return
        try:
            gid = int(iid)
        except ValueError:
            return
        if gid in self._army_xfer_selected_gids:
            self._army_xfer_selected_gids.remove(gid)
        else:
            self._army_xfer_selected_gids.add(gid)
        vals = list(self.army_xfer_gen_tree.item(iid, "values"))
        if vals:
            vals[0] = "☑" if gid in self._army_xfer_selected_gids else "☐"
            self.army_xfer_gen_tree.item(iid, values=vals)
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _toggle_army_transfer(self):
        if self._army_xfer_running:
            self._army_xfer_running = False
            self._army_xfer_stop.set()
            self.army_xfer_status_var.set("Đã dừng")
            self.army_xfer_start_btn.configure(text="▶️ Bắt đầu", style="Success.TButton")
            return
        self._start_army_transfer(loop=bool(self.army_xfer_loop_var.get()))

    def _do_army_transfer_once(self):
        if self._army_xfer_running:
            return
        self._start_army_transfer(loop=False)

    def _start_army_transfer(self, *, loop: bool):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        from_cid = self._resolve_combo_city_id(self.army_xfer_from_combo, cities_only=True)
        to_cid = self._resolve_combo_city_id(self.army_xfer_to_combo, cities_only=True)
        if from_cid <= 0 or to_cid <= 0 or from_cid == to_cid:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn 2 Thành chứa và nhận khác nhau!")
            return
        wid = self._parse_weapon_id_from_combo(self.army_xfer_weapon_combo, default=406)
        gids = sorted(self._army_xfer_selected_gids)
        if not gids:
            msgbox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 Võ tướng!")
            return
        self._army_xfer_running = True
        self._army_xfer_stop.clear()
        self.army_xfer_status_var.set(f"Đang chạy ({get_transfer_weapon_name(wid)})")
        self.army_xfer_start_btn.configure(text="⏹️ Dừng", style="Danger.TButton")

        def _worker():
            task = ArmyWeaponTransferTask(self.gateway, notify=lambda m: self.after(0, self._append_bld_log, m))
            final_status = "Đã dừng"
            try:
                res = task.run(
                    from_city_id=from_cid,
                    to_city_id=to_cid,
                    weapon_id=wid,
                    general_ids=gids,
                    roster=self.roster,
                    loop=loop,
                    stop_event=self._army_xfer_stop,
                    status_cb=lambda m: self.after(0, self.army_xfer_status_var.set, m),
                )
                if res.startswith("completed"):
                    final_status = "Hoàn tất"
                elif res.startswith("stopped_out_of_stock"):
                    final_status = "Đã dừng: hết quân giới nguồn"
            except CaptchaRequired:
                self.after(0, self._append_bld_log, "⚠️ Chuyển bằng Quân đội tạm dừng do Captcha (mã 110)!")
                final_status = "Tạm dừng (Captcha)"
            except Exception as exc:
                self.after(0, self._append_bld_log, f"❌ Lỗi chuyển bằng Quân đội: {exc}")
                final_status = f"Lỗi: {exc}"
            finally:
                def _reset():
                    self._army_xfer_running = False
                    if not getattr(self, "_destroyed", False):
                        self.army_xfer_status_var.set(final_status)
                        self.army_xfer_start_btn.configure(text="▶️ Bắt đầu", style="Success.TButton")
                try:
                    self.after(0, _reset)
                except (RuntimeError, tk.TclError):
                    pass

        self._army_xfer_thread = threading.Thread(target=_worker, daemon=True)
        self._army_xfer_thread.start()
