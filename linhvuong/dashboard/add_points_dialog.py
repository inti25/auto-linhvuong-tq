"""Hộp thoại Cộng Điểm Văn Quan & Võ Tướng trên Desktop Dashboard."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..generals import (
    ADD_POINT_MODE_LABELS,
    ADD_POINT_MODE_PAIR_1_3,
    ADD_POINT_MODES,
    ADD_POINTS_MAX_STEP,
    ADD_POINTS_MIN_STEP,
    AddPointsSummary,
    add_points_generals,
    is_max_add_mode,
)
from ..gui import set_app_icon
from ..roster import General, Roster, fetch_roster as _default_fetch_roster
from .shared import ACCENT, BG, CARD, FG, MUTED, ROLE_TEXT, resolve_dashboard_symbol

_ALL_CITIES = "🌟 Tất cả các thành"
_ROLE_ALL = "Tất cả (Võ & Văn)"
_ROLE_VO = "Võ tướng"
_ROLE_VAN = "Văn quan"

_LABEL_TO_MODE: dict[str, str] = {ADD_POINT_MODE_LABELS[m]: m for m in ADD_POINT_MODES}


class AddPointsDialogMixin:
    """Quản lý cửa sổ Cộng Điểm Tướng trên Dashboard."""

    def _open_add_points_dialog(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        existing = getattr(self, "_add_points_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            self._on_add_points_roster_updated()
            return

        win = tk.Toplevel(self)
        win.title("✨ Cộng Điểm Văn Quan & Võ Tướng")
        win.geometry("1040x680")
        win.minsize(900, 560)
        win.configure(bg=BG)
        win.transient(self)
        set_app_icon(win)
        self._add_points_dialog = win
        self._ap_selected_ids: set[int] = set()
        self._ap_running = False
        self._ap_stop_event: Optional[threading.Event] = None
        self._ap_base_by_name: dict[str, int] = {}

        def _on_close():
            if getattr(self, "_ap_running", False):
                if not messagebox.askyesno(
                    "Đang cộng điểm tướng",
                    "Tác vụ cộng điểm đang chạy. Dừng và đóng cửa sổ?",
                    parent=win,
                ):
                    return
                if self._ap_stop_event is not None:
                    self._ap_stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Khối 1: Cài đặt chế độ cộng điểm
        cfg_frame = ttk.LabelFrame(
            win,
            text="1. Cài đặt Cộng Điểm Tướng",
            style="Card.TLabelframe",
        )
        cfg_frame.pack(fill="x", padx=12, pady=(10, 4))

        row1 = tk.Frame(cfg_frame, bg=CARD)
        row1.pack(fill="x", padx=8, pady=(6, 4))

        tk.Label(row1, text="Loại cộng:", bg=CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.ap_mode_var = tk.StringVar(value=ADD_POINT_MODE_LABELS[ADD_POINT_MODE_PAIR_1_3])
        self.ap_mode_combo = ttk.Combobox(
            row1,
            textvariable=self.ap_mode_var,
            state="readonly",
            width=30,
            values=[ADD_POINT_MODE_LABELS[m] for m in ADD_POINT_MODES],
        )
        self.ap_mode_combo.pack(side="left", padx=(6, 12))
        self.ap_mode_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_ap_config_changed())

        self.ap_add_all_var = tk.BooleanVar(value=False)
        self.ap_add_all_chk = ttk.Checkbutton(
            row1,
            text="Cộng hết điểm (+10 → +3 → +1)",
            variable=self.ap_add_all_var,
            command=self._on_ap_config_changed,
        )
        self.ap_add_all_chk.pack(side="left", padx=(0, 14))

        tk.Label(row1, text="Điểm/lần:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.ap_points_var = tk.StringVar(value="10")
        self.ap_points_entry = ttk.Entry(row1, textvariable=self.ap_points_var, width=6)
        self.ap_points_entry.pack(side="left", padx=(4, 12))

        tk.Label(row1, text="Số lần mỗi loại:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.ap_times_var = tk.StringVar(value="1")
        self.ap_times_entry = ttk.Entry(row1, textvariable=self.ap_times_var, width=6)
        self.ap_times_entry.pack(side="left", padx=(4, 0))

        self.ap_hint_var = tk.StringVar(value="")
        tk.Label(
            cfg_frame,
            textvariable=self.ap_hint_var,
            bg=CARD,
            fg=ACCENT,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=980,
            justify="left",
        ).pack(fill="x", padx=8, pady=(0, 6))

        self.ap_points_var.trace_add("write", lambda *_a: self._update_ap_hint())
        self.ap_times_var.trace_add("write", lambda *_a: self._update_ap_hint())

        # Khối 2: Bộ lọc & chọn nhanh
        top_bar = tk.Frame(win, bg=BG)
        top_bar.pack(fill="x", padx=12, pady=(4, 2))
        f_row1 = tk.Frame(top_bar, bg=BG)
        f_row1.pack(fill="x", pady=(0, 4))

        tk.Label(f_row1, text="Thành / Trại:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=(0, 6)
        )
        self.ap_city_combo = ttk.Combobox(f_row1, state="readonly", width=26)
        self.ap_city_combo.pack(side="left", padx=(0, 10))
        self.ap_city_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_add_points_tree())

        tk.Label(f_row1, text="Phân hệ:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.ap_role_combo = ttk.Combobox(
            f_row1, state="readonly", width=18, values=[_ROLE_ALL, _ROLE_VO, _ROLE_VAN]
        )
        self.ap_role_combo.set(_ROLE_ALL)
        self.ap_role_combo.pack(side="left", padx=(0, 10))
        self.ap_role_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_add_points_tree())

        tk.Label(f_row1, text="Tìm tên:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.ap_search_var = tk.StringVar(value="")
        self.ap_search_entry = ttk.Entry(f_row1, textvariable=self.ap_search_var, width=16)
        self.ap_search_entry.pack(side="left", padx=(0, 10))
        self.ap_search_var.trace_add("write", lambda *_a: self._refresh_add_points_tree())

        self.ap_only_avail_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            f_row1,
            text="Chỉ hiện tướng còn điểm > 0",
            variable=self.ap_only_avail_var,
            command=self._refresh_add_points_tree,
        ).pack(side="left", padx=(0, 8))

        self.ap_refresh_btn = ttk.Button(
            f_row1, text="🔄 Làm mới", style="Action.TButton", command=self._ap_refresh_roster
        )
        self.ap_refresh_btn.pack(side="right", padx=2)

        f_row2 = tk.Frame(top_bar, bg=BG)
        f_row2.pack(fill="x")
        for text, cmd in (
            ("☑ Tất cả", self._ap_select_all),
            ("☐ Bỏ chọn", self._ap_deselect_all),
            ("⚔️ Chọn Võ", self._ap_select_vo),
            ("📜 Chọn Văn", self._ap_select_van),
            ("✨ Chọn Còn Điểm", self._ap_select_with_points),
        ):
            ttk.Button(f_row2, text=text, style="Action.TButton", command=cmd).pack(side="left", padx=(0, 4))

        self.ap_summary_var = tk.StringVar(value="")
        tk.Label(win, textvariable=self.ap_summary_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=12, pady=(2, 4)
        )

        # Bảng danh sách tướng
        tree_frame = ttk.LabelFrame(
            win,
            text="2. Danh sách Văn quan & Võ tướng (Võ: SM / NN / TL | Văn: Mị / Mưu / Nội)",
            style="Card.TLabelframe",
        )
        tree_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self.ap_tree = ttk.Treeview(
            tree_frame,
            columns=("sel", "role", "city", "lv", "s1", "s2", "s3", "sp", "status"),
            show="tree headings",
            selectmode="browse",
        )
        for col, text, w, anchor in (
            ("#0", "Tên tướng", 145, "w"),
            ("sel", "Chọn", 45, "center"),
            ("role", "Chức vụ", 78, "center"),
            ("city", "Thành / Trại", 115, "w"),
            ("lv", "Cấp", 45, "center"),
            ("s1", "SM / Mị", 70, "e"),
            ("s2", "NN / Mưu", 70, "e"),
            ("s3", "TL / Nội", 70, "e"),
            ("sp", "Tiềm năng", 80, "e"),
            ("status", "Trạng thái", 115, "center"),
        ):
            self.ap_tree.heading(col, text=text)
            self.ap_tree.column(col, width=w, anchor=anchor)

        ap_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ap_tree.yview)
        self.ap_tree.configure(yscrollcommand=ap_scroll.set)
        self.ap_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        ap_scroll.pack(side="right", fill="y", padx=(0, 6), pady=6)

        self.ap_tree.bind("<Button-1>", self._on_ap_tree_click)
        self.ap_tree.bind("<space>", self._on_ap_tree_space)

        # Khối 3: Thực thi & nhật ký
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", padx=12, pady=(6, 4))

        self.ap_apply_btn = ttk.Button(
            btn_row, text="✨ Thực Hiện Cộng Điểm", style="Success.TButton", command=self._start_add_points_action
        )
        self.ap_apply_btn.pack(side="left", padx=(0, 6))
        self.ap_stop_btn = ttk.Button(
            btn_row, text="⏹ Dừng", style="Danger.TButton", command=self._stop_add_points_action
        )
        self.ap_stop_btn.pack(side="left")
        self.ap_stop_btn.state(["disabled"])
        ttk.Button(btn_row, text="Đóng", style="Action.TButton", command=_on_close).pack(side="right")

        self.ap_status_var = tk.StringVar(value="Sẵn sàng")
        tk.Label(win, textvariable=self.ap_status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=12, pady=(2, 2)
        )

        log_frame = ttk.LabelFrame(win, text="Nhật ký Cộng Điểm", style="Card.TLabelframe")
        log_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.ap_log_text = tk.Text(
            log_frame, height=6, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=("Consolas", 9)
        )
        self.ap_log_text.pack(fill="x", padx=6, pady=6)

        self._on_ap_config_changed()
        self._sync_ap_city_combo(default_from_overview=True)
        self._refresh_add_points_tree()

    # ------------------------------------------------------------------ config / filter
    def _current_ap_mode(self) -> str:
        raw = self.ap_mode_var.get() if hasattr(self, "ap_mode_var") else ""
        return _LABEL_TO_MODE.get(raw, ADD_POINT_MODE_PAIR_1_3)

    def _on_add_points_roster_updated(self):
        win = getattr(self, "_add_points_dialog", None)
        if win is None or not win.winfo_exists():
            return
        self._sync_ap_city_combo(default_from_overview=False)
        self._refresh_add_points_tree()

    def _on_ap_config_changed(self):
        win = getattr(self, "_add_points_dialog", None)
        if win is None or not win.winfo_exists():
            return
        add_all = bool(self.ap_add_all_var.get()) if hasattr(self, "ap_add_all_var") else False
        is_max = is_max_add_mode(self._current_ap_mode())
        if hasattr(self, "ap_points_entry") and self.ap_points_entry.winfo_exists():
            self.ap_points_entry.configure(state="disabled" if add_all else "normal")
        if hasattr(self, "ap_times_entry") and self.ap_times_entry.winfo_exists():
            self.ap_times_entry.configure(state="disabled" if (add_all or is_max) else "normal")
        self._update_ap_hint()

    def _update_ap_hint(self):
        if not hasattr(self, "ap_hint_var"):
            return
        mode = self._current_ap_mode()
        add_all = bool(self.ap_add_all_var.get()) if hasattr(self, "ap_add_all_var") else False
        is_max = is_max_add_mode(mode)
        if add_all:
            if is_max:
                self.ap_hint_var.set(
                    "Cộng hết điểm: tự động cộng +10 liên tiếp rồi hạ +3 và +1 cho đến khi hết Điểm Tiềm Năng hoặc chạm trần chênh lệch (ret=77)."
                )
            else:
                self.ap_hint_var.set(
                    "Cộng hết điểm theo cặp: cộng xen kẽ 2 chỉ số theo bậc +10 → +3 → +1; nếu 1 chỉ số chạm trần (ret=77) sẽ tiếp tục thử chỉ số kia."
                )
            return

        pts_raw = self.ap_points_var.get().strip() if hasattr(self, "ap_points_var") else ""
        times_raw = self.ap_times_var.get().strip() if hasattr(self, "ap_times_var") else ""
        if not pts_raw.isdigit() or not (ADD_POINTS_MIN_STEP <= int(pts_raw) <= ADD_POINTS_MAX_STEP):
            self.ap_hint_var.set(f"⚠️ Điểm/lần phải là số nguyên từ {ADD_POINTS_MIN_STEP} đến {ADD_POINTS_MAX_STEP}.")
            return
        pts = int(pts_raw)
        if is_max:
            self.ap_hint_var.set(f"Dự kiến mỗi tướng: lặp +{pts} điểm/lần vào chỉ số đã chọn đến khi không đủ +{pts} hoặc chạm trần.")
            return
        if not times_raw.isdigit() or int(times_raw) < 1:
            self.ap_hint_var.set("⚠️ Số lần mỗi loại phải là số nguyên ≥ 1.")
            return
        times = int(times_raw)
        self.ap_hint_var.set(f"Dự kiến mỗi tướng: +{pts} điểm × 2 chỉ số × {times} lần = tối đa {pts * 2 * times} điểm.")

    def _sync_ap_city_combo(self, default_from_overview: bool = False):
        if not hasattr(self, "ap_city_combo") or not self.ap_city_combo.winfo_exists():
            return
        values = [_ALL_CITIES]
        self._ap_base_by_name = {}
        selected_display = _ALL_CITIES

        overview_base_id = None
        if default_from_overview and hasattr(self, "city_tree"):
            sel = self.city_tree.selection()
            if sel:
                try:
                    overview_base_id = int(sel[0])
                except ValueError:
                    overview_base_id = None

        current_text = self.ap_city_combo.get()
        if self.roster:
            for base in self.roster.bases:
                values.append(base.display_name)
                self._ap_base_by_name[base.display_name] = base.id
                if default_from_overview and overview_base_id == base.id:
                    selected_display = base.display_name

        self.ap_city_combo["values"] = values
        if default_from_overview:
            self.ap_city_combo.set(selected_display)
        elif current_text in values:
            self.ap_city_combo.set(current_text)
        else:
            self.ap_city_combo.set(_ALL_CITIES)

    def _get_ap_filter_role(self) -> Optional[str]:
        val = self.ap_role_combo.get() if hasattr(self, "ap_role_combo") else _ROLE_ALL
        if val == _ROLE_VO:
            return "vo"
        if val == _ROLE_VAN:
            return "van"
        return None

    def _filtered_add_points_generals(self) -> list[tuple[int, str, General]]:
        if not self.roster:
            return []
        base_filter = self._ap_base_by_name.get(self.ap_city_combo.get()) if hasattr(self, "ap_city_combo") else None
        role_filter = self._get_ap_filter_role()
        only_avail = bool(self.ap_only_avail_var.get()) if hasattr(self, "ap_only_avail_var") else False
        query = (self.ap_search_var.get() if hasattr(self, "ap_search_var") else "").strip().lower()

        rows: list[tuple[int, str, General]] = []
        seen: set[int] = set()
        for base in self.roster.bases:
            if base_filter is not None and base.id != base_filter:
                continue
            city_rows: list[tuple[int, str, General]] = []
            for g in self.roster.generals_of(base.id):
                if g.id in seen or g.role not in ("vo", "van"):
                    continue
                if role_filter is not None and g.role != role_filter:
                    continue
                if only_avail and g.skill_point <= 0:
                    continue
                if query and query not in g.name.lower():
                    continue
                seen.add(g.id)
                city_rows.append((base.id, base.name, g))
            city_rows.sort(key=lambda r: (-r[2].skill_point, -r[2].level, r[2].id))
            rows.extend(city_rows)
        return rows

    def _refresh_add_points_tree(self):
        if not hasattr(self, "ap_tree") or not self.ap_tree.winfo_exists():
            return
        self.ap_tree.delete(*self.ap_tree.get_children())
        rows = self._filtered_add_points_generals()
        total_avail_points = 0
        for _cid, cname, g in rows:
            is_sel = g.id in self._ap_selected_ids
            total_avail_points += max(0, g.skill_point)
            role_label = "Thái thú" if g.is_mayor else ROLE_TEXT.get(g.role, g.role)
            self.ap_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(
                    "☑" if is_sel else "☐",
                    role_label,
                    cname,
                    g.level,
                    g.stat1,
                    g.stat2,
                    g.stat3,
                    g.skill_point,
                    g.status_text,
                ),
            )
        selected_visible = sum(1 for _c, _n, g in rows if g.id in self._ap_selected_ids)
        self.ap_summary_var.set(
            f"Tướng hiển thị: {len(rows)} (Tổng Điểm Tiềm Năng: {total_avail_points:,})  •  Đang chọn: {selected_visible}"
        )

    def _toggle_ap_item(self, iid: str):
        if not self.ap_tree.exists(iid):
            return
        gid = int(iid)
        if gid in self._ap_selected_ids:
            self._ap_selected_ids.discard(gid)
        else:
            self._ap_selected_ids.add(gid)
        self._refresh_add_points_tree()

    def _on_ap_tree_click(self, event):
        item = self.ap_tree.identify_row(event.y)
        col = self.ap_tree.identify_column(event.x)
        if item and self.ap_tree.exists(item) and col in ("#0", "#1"):
            self._toggle_ap_item(item)

    def _on_ap_tree_space(self, _event=None):
        sel = self.ap_tree.selection()
        if sel:
            self._toggle_ap_item(sel[0])

    def _ap_apply_bulk_selection(self, predicate):
        for _cid, _cname, g in self._filtered_add_points_generals():
            if predicate(g):
                self._ap_selected_ids.add(g.id)
            else:
                self._ap_selected_ids.discard(g.id)
        self._refresh_add_points_tree()

    def _ap_select_all(self):
        self._ap_apply_bulk_selection(lambda _g: True)

    def _ap_deselect_all(self):
        self._ap_apply_bulk_selection(lambda _g: False)

    def _ap_select_vo(self):
        self._ap_apply_bulk_selection(lambda g: g.role == "vo")

    def _ap_select_van(self):
        self._ap_apply_bulk_selection(lambda g: g.role == "van")

    def _ap_select_with_points(self):
        self._ap_apply_bulk_selection(lambda g: g.skill_point > 0)

    # ------------------------------------------------------------------ background execution
    def _append_ap_log(self, msg: str):
        self._log_global(msg)
        widget = getattr(self, "ap_log_text", None)
        if widget is not None and widget.winfo_exists():
            self._append_text_buffer(widget, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _set_ap_running(self, running: bool, allow_stop: bool = True):
        self._ap_running = running
        win = getattr(self, "_add_points_dialog", None)
        if win is None or not win.winfo_exists():
            return
        for name in ("ap_apply_btn", "ap_refresh_btn"):
            btn = getattr(self, name, None)
            if btn is not None and btn.winfo_exists():
                btn.state(["disabled"] if running else ["!disabled"])
        if hasattr(self, "ap_stop_btn") and self.ap_stop_btn.winfo_exists():
            self.ap_stop_btn.state(["!disabled"] if (running and allow_stop) else ["disabled"])

    def _stop_add_points_action(self):
        if self._ap_stop_event is not None:
            self._ap_stop_event.set()
            self.ap_status_var.set("Đang dừng tác vụ Cộng Điểm Tướng...")

    def _ap_refresh_roster(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_ap_running", False):
            return
        if self.gateway is None:
            messagebox.showwarning("Cộng Điểm Tướng", "Chưa kết nối tài khoản game.", parent=self._add_points_dialog)
            return
        self._set_ap_running(True, allow_stop=False)
        self.ap_status_var.set("Đang tải lại danh sách tướng...")
        q: queue.Queue = queue.Queue()
        self._ap_queue = q

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                q.put(("roster_done", fresh, None))
            except Exception as exc:
                q.put(("roster_done", None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_ap_queue)

    def _start_add_points_action(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_ap_running", False):
            return
        win = self._add_points_dialog
        if self.gateway is None:
            messagebox.showwarning("Cộng Điểm Tướng", "Chưa kết nối tài khoản game.", parent=win)
            return

        rows = self._filtered_add_points_generals()
        selected_ids = [g.id for _cid, _cname, g in rows if g.id in self._ap_selected_ids]
        if not selected_ids:
            messagebox.showwarning("Cộng Điểm Tướng", "Vui lòng chọn ít nhất 1 tướng trong danh sách.", parent=win)
            return

        mode = self._current_ap_mode()
        add_all = bool(self.ap_add_all_var.get())
        points_per_add = 10
        times = 1
        if not add_all:
            pts_raw = self.ap_points_var.get().strip()
            if not pts_raw.isdigit() or not (ADD_POINTS_MIN_STEP <= int(pts_raw) <= ADD_POINTS_MAX_STEP):
                messagebox.showwarning(
                    "Cộng Điểm Tướng",
                    f"Điểm/lần phải là số nguyên từ {ADD_POINTS_MIN_STEP} đến {ADD_POINTS_MAX_STEP}.",
                    parent=win,
                )
                return
            points_per_add = int(pts_raw)
            if not is_max_add_mode(mode):
                times_raw = self.ap_times_var.get().strip()
                if not times_raw.isdigit() or int(times_raw) < 1:
                    messagebox.showwarning(
                        "Cộng Điểm Tướng",
                        "Số lần mỗi loại phải là số nguyên ≥ 1.",
                        parent=win,
                    )
                    return
                times = int(times_raw)

        self._ap_stop_event = threading.Event()
        stop_event = self._ap_stop_event
        self._set_ap_running(True, allow_stop=True)
        self.ap_status_var.set(f"Đang cộng điểm cho {len(selected_ids)} tướng...")
        q: queue.Queue = queue.Queue()
        self._ap_queue = q

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                summary = add_points_generals(
                    self.gateway,
                    fresh,
                    selected_ids,
                    mode=mode,
                    points_per_add=points_per_add,
                    times=times,
                    add_all=add_all,
                    stop_event=stop_event,
                    on_log=lambda m: q.put(("log", m)),
                )
                updated_roster = fetch_roster(self.gateway) if summary.total_points_added > 0 else fresh
                q.put(("add_points_done", summary, updated_roster, None))
            except Exception as exc:
                q.put(("add_points_done", None, None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_ap_queue)

    def _poll_ap_queue(self):
        if getattr(self, "_closing", False):
            return
        q = getattr(self, "_ap_queue", None)
        if q is None:
            return
        keep = True
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            kind = item[0]
            if kind == "log":
                self._append_ap_log(item[1])
            elif kind == "roster_done":
                keep = False
                self._on_ap_roster_loaded(item[1], item[2])
            elif kind == "add_points_done":
                keep = False
                self._on_ap_finished(item[1], item[2], item[3])
        if keep and getattr(self, "_ap_running", False):
            self.after(30, self._poll_ap_queue)

    def _on_ap_roster_loaded(self, fresh_roster: Optional[Roster], error: Optional[str]):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_ap_running(False)
        win = getattr(self, "_add_points_dialog", None)
        if error is not None or fresh_roster is None:
            self._append_ap_log(f"⚠️ Lỗi tải danh sách tướng: {error}")
            if win is not None and win.winfo_exists():
                self.ap_status_var.set(f"Lỗi tải: {error}")
                messagebox.showerror("Cộng Điểm Tướng", f"Không thể tải danh sách tướng:\n{error}", parent=win)
            return
        self.roster = fresh_roster
        if hasattr(self, "_loaded"):
            self._loaded(fresh_roster)
        if win is not None and win.winfo_exists():
            self._sync_ap_city_combo(default_from_overview=False)
            self._refresh_add_points_tree()
            self.ap_status_var.set("Đã cập nhật danh sách tướng mới nhất.")

    def _on_ap_finished(
        self,
        summary: Optional[AddPointsSummary],
        fresh_roster: Optional[Roster],
        error: Optional[str],
    ):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_ap_running(False)
        win = getattr(self, "_add_points_dialog", None)
        if error is not None or summary is None:
            self._append_ap_log(f"❌ Lỗi cộng điểm tướng: {error}")
            if win is not None and win.winfo_exists():
                self.ap_status_var.set(f"Lỗi: {error}")
                messagebox.showerror("Cộng Điểm Tướng", f"Đã xảy ra lỗi:\n{error}", parent=win)
            return
        if fresh_roster is not None:
            self.roster = fresh_roster
            if hasattr(self, "_loaded") and summary.total_points_added > 0:
                self._loaded(fresh_roster)
        msg = (
            f"Hoàn tất: +{summary.total_points_added} điểm ({summary.generals_succeeded} tướng), "
            f"hết điểm {summary.skipped_no_points}, lỗi {summary.failed}"
        )
        self._append_ap_log(f"✨ {msg}")
        if win is not None and win.winfo_exists():
            self._sync_ap_city_combo(default_from_overview=False)
            self._refresh_add_points_tree()
            self.ap_status_var.set(msg)
            messagebox.showinfo(
                "Kết quả Cộng Điểm Tướng",
                (
                    f"Tổng điểm đã cộng: +{summary.total_points_added} ({summary.generals_succeeded} tướng)\n"
                    f"Số lệnh thành công: {summary.requests_succeeded}/{summary.requests_sent}\n"
                    f"Hết Điểm Tiềm Năng (bỏ qua): {summary.skipped_no_points}\n"
                    f"Thất bại: {summary.failed}"
                ),
                parent=win,
            )
