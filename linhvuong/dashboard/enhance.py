"""Tab Cường Hóa Trang Bị & Hủy Trang Bị trên Dashboard Desktop (ADR-0043)."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from ..enhance import (
    DESTROY_WARN_LEVEL,
    MAX_EQUIP_LEVEL,
    EnhanceConfig,
    EnhanceProgress,
    WarehouseItem,
    fetch_enhance_materials,
    fetch_enhance_resources,
    fetch_warehouse_equipment,
    run_destroy_batch,
    run_enhance_batch,
)
from ..gui import set_app_icon
from ..notifications import dispatch_system_alert
from ..tasks.base import CaptchaRequired
from .shared import ACCENT, BG, CARD, DANGER, FG, MUTED, resolve_dashboard_symbol

_NO_MATERIAL_LABEL = "Không dùng phôi"
_NO_PROTECT_LABEL = "Không dùng Búa"
_EQUIP_BUTTON_LABELS: tuple[tuple[int, str], ...] = (
    (1, "🪖 Mũ"),
    (2, "⚔️ Vũ khí"),
    (3, "🛡️ Giáp"),
    (4, "🐎 Ngựa"),
)


class EnhanceMixin:
    """Quản lý Tab Cường Hóa Trang Bị (1->15) & Hủy Trang Bị trên Desktop."""

    def _build_enhance_tab(self, parent: tk.Widget) -> None:
        self._enh_equip_type: int = 1
        self._enh_role: str = "vo"
        self._enh_items_by_role: dict[str, list[WarehouseItem]] = {"vo": [], "van": []}
        self._enh_item_lookup: dict[int, WarehouseItem] = {}
        self._enh_selected_item: Optional[WarehouseItem] = None
        self._enh_mat_key_map: dict[str, str] = {_NO_MATERIAL_LABEL: ""}
        self._enh_sort_reverse: dict[str, bool] = {}
        self._enh_ui_queue: queue.Queue = queue.Queue()
        self._enh_ui_polling: bool = False
        self._enh_active_workers: int = 0

        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(0, weight=1, uniform="enh_col")
        body.columnconfigure(1, weight=1, uniform="enh_col")
        body.rowconfigure(0, weight=1)

        left_col = tk.Frame(body, bg=BG)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left_col.columnconfigure(0, weight=1)
        left_col.rowconfigure(0, weight=1)

        right_col = tk.Frame(body, bg=BG)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_col.columnconfigure(0, weight=1)
        right_col.rowconfigure(2, weight=1)

        # --- Cột trái 1: Kho Trang Bị ---
        f_inv = ttk.LabelFrame(left_col, text="1. Kho Trang Bị (Chưa Mặc)", style="Card.TLabelframe")
        f_inv.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        type_bar = tk.Frame(f_inv, bg=CARD)
        type_bar.pack(fill="x", padx=6, pady=(6, 4))
        self.enh_type_btns: dict[int, ttk.Button] = {}
        for eq_type, label in _EQUIP_BUTTON_LABELS:
            btn = ttk.Button(
                type_bar,
                text=label,
                style="Action.TButton",
                command=lambda t=eq_type: self._load_enhance_warehouse(t),
            )
            btn.pack(side="left", padx=(0, 4))
            self.enh_type_btns[eq_type] = btn

        self.enh_reload_btn = ttk.Button(
            type_bar,
            text="🔄 Tải kho",
            style="Action.TButton",
            command=lambda: self._load_enhance_warehouse(self._enh_equip_type),
        )
        self.enh_reload_btn.pack(side="right")

        filter_bar = tk.Frame(f_inv, bg=CARD)
        filter_bar.pack(fill="x", padx=6, pady=(0, 4))
        tk.Label(filter_bar, text="Lọc tên/cấp/ID:", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(
            side="left", padx=(0, 6)
        )
        self.enh_filter_var = tk.StringVar(value="")
        filter_entry = ttk.Entry(filter_bar, textvariable=self.enh_filter_var)
        filter_entry.pack(side="left", fill="x", expand=True)
        filter_entry.bind("<KeyRelease>", lambda _e: self._refresh_enhance_trees())

        self.enh_role_nb = ttk.Notebook(f_inv)
        self.enh_role_nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        vo_tab = tk.Frame(self.enh_role_nb, bg=CARD)
        van_tab = tk.Frame(self.enh_role_nb, bg=CARD)
        self.enh_role_nb.add(vo_tab, text="⚔️ Võ Tướng")
        self.enh_role_nb.add(van_tab, text="📜 Văn Quan")
        self.enh_vo_tree = self._create_enhance_tree(vo_tab)
        self.enh_van_tree = self._create_enhance_tree(van_tab)
        self.enh_role_nb.bind("<<NotebookTabChanged>>", self._on_enhance_role_tab_changed)

        # --- Cột trái 2: Thiết Lập Cường Hóa ---
        f_cfg = ttk.LabelFrame(left_col, text="2. Thiết Lập Cường Hóa", style="Card.TLabelframe")
        f_cfg.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.enh_selected_var = tk.StringVar(value="Chưa chọn trang bị trong kho")
        tk.Label(
            f_cfg, textvariable=self.enh_selected_var, bg=CARD, fg="#38bdf8", font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=8, pady=(6, 4))

        cfg_row = tk.Frame(f_cfg, bg=CARD)
        cfg_row.pack(fill="x", padx=8, pady=(0, 6))

        tk.Label(cfg_row, text="Cấp mục tiêu:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.enh_target_combo = ttk.Combobox(cfg_row, state="readonly", width=11)
        self.enh_target_combo.pack(side="left", padx=(0, 10))
        self.enh_target_combo.bind("<<ComboboxSelected>>", self._on_enhance_target_changed)

        tk.Label(cfg_row, text="Búa Bảo Hộ:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        protect_vals = [_NO_PROTECT_LABEL] + [f"Từ cấp {lv}" for lv in range(2, 9)]
        self.enh_protect_combo = ttk.Combobox(cfg_row, state="readonly", width=15, values=protect_vals)
        self.enh_protect_combo.set("Từ cấp 7")
        self.enh_protect_combo.pack(side="left", padx=(0, 10))

        tk.Label(cfg_row, text="Số lượng món:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.enh_loop_var = tk.StringVar(value="1")
        self.enh_loop_entry = ttk.Entry(cfg_row, textvariable=self.enh_loop_var, width=7)
        self.enh_loop_entry.pack(side="left")

        # --- Cột trái 3: Phôi Cường Hóa ---
        f_mat = ttk.LabelFrame(left_col, text="3. Phôi Cường Hóa (Chặng cấp 1→8)", style="Card.TLabelframe")
        f_mat.grid(row=2, column=0, sticky="ew")

        mat_top = tk.Frame(f_mat, bg=CARD)
        mat_top.pack(fill="x", padx=8, pady=(6, 4))
        tk.Label(mat_top, text="Dùng Phôi từ cấp:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.enh_mat_from_combo = ttk.Combobox(
            mat_top,
            state="readonly",
            width=12,
            values=[f"Từ cấp {lv}" for lv in range(1, 9)],
        )
        self.enh_mat_from_combo.set("Từ cấp 1")
        self.enh_mat_from_combo.pack(side="left")

        self.enh_refresh_mats_btn = ttk.Button(
            mat_top,
            text="🔄 Tải Phôi",
            style="Action.TButton",
            command=self._load_selected_item_materials,
        )
        self.enh_refresh_mats_btn.pack(side="right")

        self.enh_mat_combos: list[ttk.Combobox] = []
        for slot_idx in range(1, 4):
            row = tk.Frame(f_mat, bg=CARD)
            row.pack(fill="x", padx=8, pady=2)
            tk.Label(row, text=f"Phôi {slot_idx}:", bg=CARD, fg=FG, width=8, anchor="w", font=("Segoe UI", 9)).pack(
                side="left"
            )
            cb = ttk.Combobox(row, state="readonly", values=[_NO_MATERIAL_LABEL])
            cb.set(_NO_MATERIAL_LABEL)
            cb.pack(side="left", fill="x", expand=True)
            self.enh_mat_combos.append(cb)

        act_bar = tk.Frame(f_mat, bg=CARD)
        act_bar.pack(fill="x", padx=8, pady=(8, 8))
        self.enh_start_btn = ttk.Button(
            act_bar, text="🔨 Nâng Cấp", style="Success.TButton", command=self._start_enhancing
        )
        self.enh_start_btn.pack(side="left", padx=(0, 6))
        self.enh_stop_btn = ttk.Button(
            act_bar, text="⏹️ Dừng", style="Danger.TButton", command=self._stop_enhancing, state="disabled"
        )
        self.enh_stop_btn.pack(side="left", padx=(0, 6))
        self.enh_destroy_btn = ttk.Button(
            act_bar, text="🔥 Hủy Đồ", style="Warning.TButton", command=self._open_destroy_dialog
        )
        self.enh_destroy_btn.pack(side="left")

        # --- Cột phải 1: Tài Nguyên ---
        f_res = ttk.LabelFrame(right_col, text="Tài Nguyên Hiện Có", style="Card.TLabelframe")
        f_res.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        res_row = tk.Frame(f_res, bg=CARD)
        res_row.pack(fill="x", padx=8, pady=6)
        self.enh_iron_var = tk.StringVar(value="0")
        self.enh_hammer_var = tk.StringVar(value="0")
        self.enh_crystal_var = tk.StringVar(value="0")

        for lbl_txt, var in (
            ("Huyền Thiết (341):", self.enh_iron_var),
            ("Búa Bảo Hộ (342):", self.enh_hammer_var),
            ("Pha Lê (354):", self.enh_crystal_var),
        ):
            tk.Label(res_row, text=lbl_txt, bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 3))
            tk.Label(res_row, textvariable=var, bg=CARD, fg="#38bdf8", font=("Segoe UI", 10, "bold")).pack(
                side="left", padx=(0, 12)
            )

        self.enh_refresh_res_btn = ttk.Button(
            res_row,
            text="🔄 Cập nhật tài nguyên",
            style="Action.TButton",
            command=self._load_enhance_resources,
        )
        self.enh_refresh_res_btn.pack(side="right")

        # --- Cột phải 2: Quá Trình & Thống Kê ---
        f_prog = ttk.LabelFrame(right_col, text="Quá Trình & Thống Kê", style="Card.TLabelframe")
        f_prog.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        p_top = tk.Frame(f_prog, bg=CARD)
        p_top.pack(fill="x", padx=8, pady=(6, 2))
        self.enh_progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(p_top, variable=self.enh_progress_var, maximum=100, mode="determinate").pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self.enh_pct_var = tk.StringVar(value="0%")
        tk.Label(p_top, textvariable=self.enh_pct_var, bg=CARD, fg=ACCENT, font=("Segoe UI", 9, "bold"), width=5).pack(
            side="right"
        )

        self.enh_status_var = tk.StringVar(value="Sẵn sàng")
        tk.Label(
            f_prog, textvariable=self.enh_status_var, bg=CARD, fg=ACCENT, font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=8, pady=(2, 2))

        stats_grid = tk.Frame(f_prog, bg=CARD)
        stats_grid.pack(fill="x", padx=8, pady=(0, 6))
        stats_grid.columnconfigure(0, weight=1)
        stats_grid.columnconfigure(1, weight=1)

        self.enh_item_stat_var = tk.StringVar(value="Món: 0/0")
        self.enh_lvl_stat_var = tk.StringVar(value="Cấp: -")
        self.enh_attempt_stat_var = tk.StringVar(value="Lượt ép: 0")
        self.enh_used_stat_var = tk.StringVar(value="Tiêu hao: Sắt 0 | Búa 0 | Pha Lê 0 | Phôi 0")

        tk.Label(stats_grid, textvariable=self.enh_item_stat_var, bg=CARD, fg=FG, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(stats_grid, textvariable=self.enh_lvl_stat_var, bg=CARD, fg="#f59e0b", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=1, sticky="w"
        )
        tk.Label(stats_grid, textvariable=self.enh_attempt_stat_var, bg=CARD, fg=FG, font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        tk.Label(stats_grid, textvariable=self.enh_used_stat_var, bg=CARD, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=1, column=1, sticky="w", pady=(2, 0)
        )

        # --- Cột phải 3: Nhật Ký ---
        f_log = ttk.LabelFrame(right_col, text="Nhật Ký Cường Hóa", style="Card.TLabelframe")
        f_log.grid(row=2, column=0, sticky="nsew")

        log_bar = tk.Frame(f_log, bg=CARD)
        log_bar.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Button(log_bar, text="🗑️ Xóa log", style="Action.TButton", command=self._clear_enhance_log).pack(
            side="right"
        )

        self.enhance_log_text = tk.Text(
            f_log,
            bg="#0d0e15",
            fg="#d4d7e3",
            insertbackground=FG,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        log_scroll = ttk.Scrollbar(f_log, orient="vertical", command=self.enhance_log_text.yview)
        self.enhance_log_text.configure(yscrollcommand=log_scroll.set)
        self.enhance_log_text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=(0, 6))
        log_scroll.pack(side="right", fill="y", padx=(0, 6), pady=(0, 6))

    def _create_enhance_tree(self, parent: tk.Widget) -> ttk.Treeview:
        cols = ("name", "level", "quantity", "id")
        tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        for col, text, w, anchor in (
            ("name", "Tên trang bị", 180, "w"),
            ("level", "Cấp", 65, "center"),
            ("quantity", "SL", 55, "center"),
            ("id", "ID", 90, "e"),
        ):
            tree.heading(col, text=text, command=lambda t=tree, c=col: self._sort_enhance_tree(t, c))
            tree.column(col, width=w, anchor=anchor)

        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        tree.bind("<<TreeviewSelect>>", self._on_enhance_item_selected)
        return tree

    def _sort_enhance_tree(self, tree: ttk.Treeview, col: str) -> None:
        key = f"{id(tree)}:{col}"
        reverse = not self._enh_sort_reverse.get(key, False)
        self._enh_sort_reverse[key] = reverse
        rows = [(tree.set(iid, col), iid) for iid in tree.get_children("")]

        def _sort_val(raw: str):
            cleaned = str(raw).replace("Cấp ", "").strip()
            if cleaned.isdigit():
                return (0, int(cleaned))
            return (1, cleaned.lower())

        rows.sort(key=lambda pair: _sort_val(pair[0]), reverse=reverse)
        for idx, (_val, iid) in enumerate(rows):
            tree.move(iid, "", idx)

    def _schedule_enh_ui(self, fn) -> None:
        if getattr(self, "_destroyed", False):
            return
        if threading.current_thread() is threading.main_thread():
            try:
                if not self.winfo_exists():
                    return
            except Exception:
                return
            fn()
            return
        if not hasattr(self, "_enh_ui_queue"):
            self._enh_ui_queue = queue.Queue()
        self._enh_ui_queue.put(fn)

    def _start_enhance_ui_pump(self) -> None:
        if getattr(self, "_destroyed", False) or getattr(self, "_enh_ui_polling", False):
            return
        self._enh_ui_polling = True
        try:
            self.after(15, self._poll_enhance_ui_queue)
        except Exception:
            self._enh_ui_polling = False

    def _poll_enhance_ui_queue(self) -> None:
        if getattr(self, "_destroyed", False):
            self._enh_ui_polling = False
            return
        try:
            if not self.winfo_exists():
                self._enh_ui_polling = False
                return
        except Exception:
            self._enh_ui_polling = False
            return

        q = getattr(self, "_enh_ui_queue", None)
        if q is not None:
            while True:
                try:
                    fn = q.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn()
                except Exception:
                    pass

        still_busy = getattr(self, "_enh_active_workers", 0) > 0 or (q is not None and not q.empty())
        if still_busy and not getattr(self, "_destroyed", False):
            try:
                self.after(20, self._poll_enhance_ui_queue)
            except Exception:
                self._enh_ui_polling = False
        else:
            self._enh_ui_polling = False

    def _run_enhance_worker(self, target) -> None:
        if not hasattr(self, "_enh_ui_queue"):
            self._enh_ui_queue = queue.Queue()
        if not hasattr(self, "_enh_active_workers"):
            self._enh_active_workers = 0
        self._enh_active_workers += 1
        self._start_enhance_ui_pump()

        def _wrapped():
            try:
                target()
            finally:
                def _dec():
                    self._enh_active_workers = max(0, getattr(self, "_enh_active_workers", 1) - 1)

                self._schedule_enh_ui(_dec)

        threading.Thread(target=_wrapped, daemon=True).start()

    def _append_enhance_log(self, msg: str) -> None:
        if not hasattr(self, "enhance_log_text"):
            return
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        self._append_text_buffer(self.enhance_log_text, line)

    def _clear_enhance_log(self) -> None:
        if hasattr(self, "enhance_log_text"):
            self.enhance_log_text.delete("1.0", "end")

    def _notify_enhance_captcha(self, reason: str) -> None:
        self._schedule_enh_ui(lambda: self.enh_status_var.set("Tạm dừng (Captcha)"))
        self._schedule_enh_ui(lambda: self._append_enhance_log(f"⚠️ {reason}"))
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        self._schedule_enh_ui(lambda: mb.showwarning("Cần giải Captcha", reason, parent=self))
        account_key = f"{getattr(self, 'username', '') or 'guest'}-{getattr(self, 'server_id', 0)}"
        try:
            dispatch_system_alert(
                "captcha",
                account_key,
                "Cần Giải Captcha",
                reason,
                config=getattr(self, "notification_config", None),
                on_log=lambda m: self._schedule_enh_ui(lambda msg=m: self._append_enhance_log(msg)),
            )
        except Exception:
            pass

    def _load_enhance_resources(self) -> None:
        if not getattr(self, "gateway", None):
            return

        def _worker():
            try:
                res = fetch_enhance_resources(self.gateway)
                def _apply():
                    self.enh_iron_var.set(f"{res.iron:,}")
                    self.enh_hammer_var.set(f"{res.hammer:,}")
                    self.enh_crystal_var.set(f"{res.crystal:,}")
                self._schedule_enh_ui(_apply)
            except CaptchaRequired:
                self._notify_enhance_captcha("Tải tài nguyên cường hóa gặp Captcha (mã 110).")
            except Exception as exc:
                self._schedule_enh_ui(lambda e=exc: self._append_enhance_log(f"❌ Lỗi tải tài nguyên: {e}"))

        self._run_enhance_worker(_worker)

    def _load_enhance_warehouse(self, equip_type: int) -> None:
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        if getattr(self, "_enhance_running", False):
            mb.showwarning("Cảnh báo", "Đang chạy Cường Hóa / Hủy Đồ, vui lòng dừng trước khi chuyển loại.", parent=self)
            return
        if not getattr(self, "gateway", None):
            return
        self._enh_equip_type = int(equip_type)
        self._enh_selected_item = None
        if hasattr(self, "enh_selected_var"):
            self.enh_selected_var.set("Chưa chọn trang bị trong kho")
        if hasattr(self, "enh_target_combo"):
            self.enh_target_combo["values"] = []
            self.enh_target_combo.set("")
        self._reset_enhance_material_combos()

        def _worker():
            try:
                grouped = fetch_warehouse_equipment(self.gateway, self._enh_equip_type)
                def _apply():
                    self._enh_items_by_role = grouped
                    self._refresh_enhance_trees()
                    self._append_enhance_log(
                        f"📦 Đã tải kho: {len(grouped.get('vo', []))} món Võ, {len(grouped.get('van', []))} món Văn."
                    )
                self._schedule_enh_ui(_apply)
            except CaptchaRequired:
                self._notify_enhance_captcha("Tải kho trang bị gặp Captcha (mã 110).")
            except Exception as exc:
                self._schedule_enh_ui(lambda e=exc: self._append_enhance_log(f"❌ Lỗi tải kho: {e}"))

        self._run_enhance_worker(_worker)

    def _refresh_enhance_trees(self) -> None:
        query = (self.enh_filter_var.get() if hasattr(self, "enh_filter_var") else "").strip().lower()
        self._enh_item_lookup = {}
        for role_key, tree in (("vo", self.enh_vo_tree), ("van", self.enh_van_tree)):
            for iid in tree.get_children(""):
                tree.delete(iid)
            for item in self._enh_items_by_role.get(role_key, []):
                self._enh_item_lookup[item.item_id] = item
                if query and (
                    query not in item.name.lower()
                    and query not in str(item.level)
                    and query not in str(item.item_id)
                ):
                    continue
                tree.insert(
                    "",
                    "end",
                    iid=str(item.item_id),
                    values=(item.name, f"Cấp {item.level}", item.quantity, item.item_id),
                )

    def _on_enhance_role_tab_changed(self, _event=None) -> None:
        idx = self.enh_role_nb.index(self.enh_role_nb.select())
        self._enh_role = "van" if idx == 1 else "vo"
        self._enh_selected_item = None
        self.enh_selected_var.set("Chưa chọn trang bị trong kho")
        self.enh_target_combo["values"] = []
        self.enh_target_combo.set("")
        self._reset_enhance_material_combos()

    def _on_enhance_item_selected(self, event=None) -> None:
        widget = event.widget if event else (self.enh_van_tree if self._enh_role == "van" else self.enh_vo_tree)
        self._enh_role = "van" if widget is self.enh_van_tree else "vo"
        sel = widget.selection()
        if not sel:
            return
        try:
            item_id = int(sel[0])
        except ValueError:
            return
        item = self._enh_item_lookup.get(item_id)
        if item is None:
            return
        self._enh_selected_item = item
        self.enh_selected_var.set(f"Đang chọn: {item.name} — Cấp {item.level} (ID: {item.item_id}, SL: {item.quantity})")

        if item.level >= MAX_EQUIP_LEVEL:
            self.enh_target_combo["values"] = []
            self.enh_target_combo.set("")
        else:
            vals = [f"Cấp {lv}" for lv in range(item.level + 1, MAX_EQUIP_LEVEL + 1)]
            self.enh_target_combo["values"] = vals
            default_target = 7 if item.level < 7 else min(MAX_EQUIP_LEVEL, item.level + 1)
            self.enh_target_combo.set(f"Cấp {default_target}")
            if item.level >= 9:
                self.enh_protect_combo.set(_NO_PROTECT_LABEL)
                self.enh_protect_combo.configure(state="disabled")
            else:
                self.enh_protect_combo.configure(state="readonly")
                if default_target >= 7:
                    self.enh_protect_combo.set("Từ cấp 7")
                else:
                    self.enh_protect_combo.set(_NO_PROTECT_LABEL)

        if item.level < 9:
            self._load_selected_item_materials()
        else:
            self._reset_enhance_material_combos()

    def _on_enhance_target_changed(self, _event=None) -> None:
        target = self._parse_selected_target_level()
        if target is None:
            return
        item = self._enh_selected_item
        if target >= 7 and (item is None or item.level < 9):
            if self.enh_protect_combo.get() == _NO_PROTECT_LABEL:
                self.enh_protect_combo.set("Từ cấp 7")

    def _reset_enhance_material_combos(self) -> None:
        self._enh_mat_key_map = {_NO_MATERIAL_LABEL: ""}
        if hasattr(self, "enh_mat_combos"):
            for cb in self.enh_mat_combos:
                cb["values"] = [_NO_MATERIAL_LABEL]
                cb.set(_NO_MATERIAL_LABEL)

    def _load_selected_item_materials(self) -> None:
        item = self._enh_selected_item
        if item is None or not getattr(self, "gateway", None):
            return

        def _worker():
            try:
                pool = fetch_enhance_materials(self.gateway, item.item_id)
                def _apply():
                    labels = [_NO_MATERIAL_LABEL]
                    key_map = {_NO_MATERIAL_LABEL: ""}
                    for grp in pool.groups:
                        labels.append(grp.display_label)
                        key_map[grp.display_label] = grp.key
                    self._enh_mat_key_map = key_map
                    for cb in self.enh_mat_combos:
                        prev = cb.get()
                        cb["values"] = labels
                        cb.set(prev if prev in labels else _NO_MATERIAL_LABEL)
                    self._append_enhance_log(f"📦 Đã tải {len(pool.groups)} loại Phôi Cường Hóa cho {item.name}.")
                self._schedule_enh_ui(_apply)
            except CaptchaRequired:
                self._notify_enhance_captcha("Tải Phôi Cường Hóa gặp Captcha (mã 110).")
            except Exception as exc:
                self._schedule_enh_ui(lambda e=exc: self._append_enhance_log(f"❌ Lỗi tải Phôi: {e}"))

        self._run_enhance_worker(_worker)

    def _parse_selected_target_level(self) -> Optional[int]:
        raw = self.enh_target_combo.get().replace("Cấp", "").strip()
        return int(raw) if raw.isdigit() else None

    def _parse_protect_from_level(self) -> Optional[int]:
        raw = self.enh_protect_combo.get().replace("Từ cấp", "").strip()
        return int(raw) if raw.isdigit() else None

    def _parse_material_from_level(self) -> int:
        raw = self.enh_mat_from_combo.get().replace("Từ cấp", "").strip()
        return int(raw) if raw.isdigit() else 1

    def _set_enhance_running_state(self, running: bool) -> None:
        self._enhance_running = running
        self.enh_start_btn.configure(state=("disabled" if running else "normal"))
        self.enh_destroy_btn.configure(state=("disabled" if running else "normal"))
        self.enh_stop_btn.configure(state=("normal" if running else "disabled"))
        for btn in self.enh_type_btns.values():
            btn.configure(state=("disabled" if running else "normal"))

    def _apply_enhance_progress(self, prog: EnhanceProgress) -> None:
        self.enh_progress_var.set(float(prog.pct))
        self.enh_pct_var.set(f"{prog.pct}%")
        self.enh_status_var.set(prog.status)
        if prog.mode == "destroy":
            self.enh_item_stat_var.set(f"Hủy: {prog.destroyed_count}/{prog.destroy_total}")
        else:
            self.enh_item_stat_var.set(
                f"Món: {prog.item_index}/{prog.total_items} (Hoàn tất: {prog.completed_items})"
            )
        self.enh_lvl_stat_var.set(
            f"Cấp: {prog.current_level}/{prog.target_level}" if prog.target_level else "Cấp: -"
        )
        self.enh_attempt_stat_var.set(
            f"Lượt ép: {prog.total_attempts} (✅ {prog.success_attempts} / ❌ {prog.fail_attempts})"
        )
        self.enh_used_stat_var.set(
            f"Tiêu hao: Sắt {prog.iron_used} | Búa {prog.hammer_used} | Pha Lê {prog.crystal_used} | Phôi {prog.material_used}"
        )
        if prog.resources:
            self.enh_iron_var.set(f"{int(prog.resources.get('iron', 0)):,}")
            self.enh_hammer_var.set(f"{int(prog.resources.get('hammer', 0)):,}")
            self.enh_crystal_var.set(f"{int(prog.resources.get('crystal', 0)):,}")

    def _start_enhancing(self) -> None:
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        if getattr(self, "_enhance_running", False):
            mb.showwarning("Cảnh báo", "Quá trình Cường Hóa / Hủy Đồ đang chạy!", parent=self)
            return
        item = self._enh_selected_item
        if item is None:
            mb.showwarning("Cảnh báo", "Vui lòng chọn trang bị cần cường hóa!", parent=self)
            return
        target_level = self._parse_selected_target_level()
        if target_level is None:
            mb.showwarning("Cảnh báo", "Vui lòng chọn cấp độ mục tiêu!", parent=self)
            return
        loop_raw = self.enh_loop_var.get().strip()
        if not loop_raw.isdigit():
            mb.showwarning("Cảnh báo", "Số lượng món phải là số nguyên dương!", parent=self)
            return

        mat_keys = tuple(self._enh_mat_key_map.get(cb.get(), "") for cb in self.enh_mat_combos)
        cfg = EnhanceConfig(
            equip_type=item.equip_type,
            role=item.role,
            item_id=item.item_id,
            item_type_id=item.item_type_id,
            start_level=item.level,
            target_level=target_level,
            protect_from_level=self._parse_protect_from_level(),
            material_from_level=self._parse_material_from_level(),
            material_keys=(mat_keys[0], mat_keys[1], mat_keys[2]),
            loop_count=int(loop_raw),
        )
        try:
            cfg.validate()
        except ValueError as exc:
            mb.showwarning("Cảnh báo", str(exc), parent=self)
            return

        self._enhance_stop_event.clear()
        self._set_enhance_running_state(True)

        def _worker():
            try:
                run_enhance_batch(
                    self.gateway,
                    cfg,
                    stop_event=self._enhance_stop_event,
                    on_log=lambda m: self._schedule_enh_ui(lambda msg=m: self._append_enhance_log(msg)),
                    on_progress=lambda p: self._schedule_enh_ui(lambda prog=p: self._apply_enhance_progress(prog)),
                )
            except CaptchaRequired:
                self._notify_enhance_captcha("Cường hóa trang bị tạm dừng do Captcha (mã 110).")
            except Exception as exc:
                self._schedule_enh_ui(lambda e=exc: self._append_enhance_log(f"❌ Lỗi cường hóa: {e}"))
            finally:
                def _finish():
                    self._set_enhance_running_state(False)
                    self._load_enhance_warehouse(self._enh_equip_type)
                self._schedule_enh_ui(_finish)

        self._run_enhance_worker(_worker)

    def _stop_enhancing(self) -> None:
        if hasattr(self, "_enhance_stop_event"):
            self._enhance_stop_event.set()
        self._append_enhance_log("⏹️ Đã gửi yêu cầu dừng Cường Hóa / Hủy Đồ...")

    def _open_destroy_dialog(self) -> None:
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        if getattr(self, "_enhance_running", False):
            mb.showwarning("Cảnh báo", "Đang chạy Cường Hóa / Hủy Đồ, vui lòng dừng lại trước!", parent=self)
            return
        item = self._enh_selected_item
        if item is None:
            mb.showwarning("Cảnh báo", "Vui lòng chọn trang bị cần hủy!", parent=self)
            return

        same_items = [
            it
            for it in self._enh_items_by_role.get(item.role, [])
            if it.item_type_id == item.item_type_id and it.level == item.level
        ]
        total_stock = max(1, sum(it.quantity for it in same_items))
        is_high = item.level >= DESTROY_WARN_LEVEL

        win = tk.Toplevel(self)
        win.title("🔥 Hủy Trang Bị")
        win.geometry("420x310" if is_high else "400x240")
        win.configure(bg=BG)
        win.transient(self)
        win.grab_set()
        set_app_icon(win)
        self._enhance_destroy_dialog = win

        tk.Label(win, text="HỦY TRANG BỊ VĨNH VIỄN", bg=BG, fg=DANGER, font=("Segoe UI", 12, "bold")).pack(
            pady=(12, 6)
        )
        tk.Label(
            win,
            text=f"Trang bị: {item.name} (Cấp {item.level}, ID: {item.item_id})\nTồn kho cùng loại & cấp: {total_stock}",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 10),
        ).pack(pady=(0, 8))

        confirm_var = tk.BooleanVar(value=not is_high)
        if is_high:
            warn_frame = tk.Frame(win, bg="#3b1219", highlightbackground=DANGER, highlightthickness=1)
            warn_frame.pack(fill="x", padx=16, pady=(0, 8))
            tk.Label(
                warn_frame,
                text=f"⚠️ CẢNH BÁO ĐỒ CẤP CAO (Cấp {item.level} ≥ {DESTROY_WARN_LEVEL})\nHành động này xóa vĩnh viễn không thể khôi phục!",
                bg="#3b1219",
                fg="#fecaca",
                font=("Segoe UI", 9, "bold"),
                justify="left",
            ).pack(anchor="w", padx=8, pady=(6, 4))
            chk = ttk.Checkbutton(
                warn_frame,
                text=f"Tôi xác nhận hủy vĩnh viễn trang bị cấp {item.level}",
                variable=confirm_var,
            )
            chk.pack(anchor="w", padx=8, pady=(0, 6))

        qty_row = tk.Frame(win, bg=BG)
        qty_row.pack(pady=4)
        tk.Label(qty_row, text=f"Số lượng hủy (1..{total_stock}):", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(
            side="left", padx=(0, 8)
        )
        qty_var = tk.StringVar(value="1")
        qty_entry = ttk.Entry(qty_row, textvariable=qty_var, width=8)
        qty_entry.pack(side="left")
        qty_entry.focus_set()

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(pady=14)

        def _confirm():
            if is_high and not confirm_var.get():
                mb.showwarning("Cảnh báo", "Vui lòng tích xác nhận hủy đồ cấp cao!", parent=win)
                return
            raw_qty = qty_var.get().strip()
            if not raw_qty.isdigit():
                mb.showwarning("Lỗi", "Vui lòng nhập số lượng hợp lệ!", parent=win)
                return
            qty = int(raw_qty)
            if qty < 1 or qty > total_stock:
                mb.showwarning("Lỗi", f"Số lượng hủy phải nằm trong khoảng 1..{total_stock}!", parent=win)
                return
            win.destroy()
            self._start_destroy_worker(item, qty)

        confirm_btn = ttk.Button(
            btn_row,
            text="🔥 Xác nhận hủy",
            style="Danger.TButton",
            command=_confirm,
            state=("disabled" if is_high else "normal"),
        )
        confirm_btn.pack(side="left", padx=6)
        ttk.Button(btn_row, text="Đóng", style="Action.TButton", command=win.destroy).pack(side="left", padx=6)

        if is_high:
            def _toggle_confirm(*_args):
                confirm_btn.configure(state=("normal" if confirm_var.get() else "disabled"))

            confirm_var.trace_add("write", _toggle_confirm)

        win._qty_var = qty_var
        win._confirm_var = confirm_var
        win._confirm_btn = confirm_btn
        self._enh_destroy_qty_var = qty_var
        self._enh_destroy_confirm_var = confirm_var
        self._enh_destroy_confirm_btn = confirm_btn

    def _start_destroy_worker(self, item: WarehouseItem, qty: int) -> None:
        self._enhance_stop_event.clear()
        self._set_enhance_running_state(True)

        def _worker():
            try:
                run_destroy_batch(
                    self.gateway,
                    equip_type=item.equip_type,
                    role=item.role,
                    start_item_id=item.item_id,
                    item_type_id=item.item_type_id,
                    target_level=item.level,
                    quantity=qty,
                    stop_event=self._enhance_stop_event,
                    on_log=lambda m: self._schedule_enh_ui(lambda msg=m: self._append_enhance_log(msg)),
                    on_progress=lambda p: self._schedule_enh_ui(lambda prog=p: self._apply_enhance_progress(prog)),
                )
            except CaptchaRequired:
                self._notify_enhance_captcha("Hủy trang bị tạm dừng do Captcha (mã 110).")
            except Exception as exc:
                self._schedule_enh_ui(lambda e=exc: self._append_enhance_log(f"❌ Lỗi hủy trang bị: {e}"))
            finally:
                def _finish():
                    self._set_enhance_running_state(False)
                    self._load_enhance_warehouse(self._enh_equip_type)
                self._schedule_enh_ui(_finish)

        self._run_enhance_worker(_worker)
