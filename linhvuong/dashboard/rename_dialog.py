"""Hộp thoại Đổi Tên Tướng (theo tiền tố + số thứ tự 01, 02... hoặc tên cố định)."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..generals import (
    RENAME_MAX_WIDTH,
    RenameSummary,
    build_rename_plan,
    general_name_width,
    rename_generals,
    sanitize_general_name,
    validate_general_name,
)
from ..gui import set_app_icon
from ..roster import General, Roster, fetch_roster as _default_fetch_roster
from .shared import ACCENT, BG, CARD, FG, MUTED, ROLE_TEXT, resolve_dashboard_symbol

_ALL_CITIES = "🌟 Tất cả các thành"
_ROLE_ALL = "Tất cả (Võ & Văn)"
_ROLE_VO = "Võ tướng"
_ROLE_VAN = "Quan văn"


class RenameDialogMixin:
    """Quản lý cửa sổ Đổi Tên Tướng trên Dashboard."""

    def _open_rename_dialog(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        existing = getattr(self, "_rename_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            self._on_rename_roster_updated()
            return

        win = tk.Toplevel(self)
        win.title("✏️ Đổi Tên Văn Quan & Võ Tướng")
        win.geometry("980x660")
        win.minsize(840, 540)
        win.configure(bg=BG)
        win.transient(self)
        set_app_icon(win)
        self._rename_dialog = win
        self._ren_selected_ids: set[int] = set()
        self._ren_running = False
        self._ren_stop_event: Optional[threading.Event] = None
        self._ren_base_by_name: dict[str, int] = {}

        def _on_close():
            if getattr(self, "_ren_running", False):
                if not messagebox.askyesno(
                    "Đang đổi tên tướng",
                    "Tác vụ đổi tên đang chạy. Dừng và đóng cửa sổ?",
                    parent=win,
                ):
                    return
                if self._ren_stop_event is not None:
                    self._ren_stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Khối 1: Quy tắc đặt tên mới (Tiền tố + số thứ tự từ 01 hoặc tên cố định)
        cfg_frame = ttk.LabelFrame(
            win,
            text="1. Quy tắc đặt tên mới (Tiền tố + số thứ tự hoặc tên cố định)",
            style="Card.TLabelframe",
        )
        cfg_frame.pack(fill="x", padx=12, pady=(10, 4))

        row1 = tk.Frame(cfg_frame, bg=CARD)
        row1.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(row1, text="Tiền tố / Tên mới:", bg=CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.ren_prefix_var = tk.StringVar(value="DT_")
        self.ren_prefix_entry = ttk.Entry(row1, textvariable=self.ren_prefix_var, width=22)
        self.ren_prefix_entry.pack(side="left", padx=(6, 12))

        self.ren_numbered_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            row1,
            text="Đánh số thứ tự (01, 02...)",
            variable=self.ren_numbered_var,
            command=self._refresh_rename_tree,
        ).pack(side="left", padx=(0, 12))

        tk.Label(row1, text="Bắt đầu từ:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.ren_start_var = tk.StringVar(value="1")
        self.ren_start_entry = ttk.Entry(row1, textvariable=self.ren_start_var, width=6)
        self.ren_start_entry.pack(side="left", padx=(4, 12))

        self.ren_example_var = tk.StringVar(value="")
        self.ren_example_lbl = tk.Label(
            row1, textvariable=self.ren_example_var, bg=CARD, fg=ACCENT, font=("Segoe UI", 9, "bold")
        )
        self.ren_example_lbl.pack(side="left", padx=(4, 0))

        self.ren_hint_var = tk.StringVar(
            value=(
                f"Hướng dẫn: Nhập tiền tố (vd 'DT_') để đổi lần lượt thành DT_01, DT_02... theo thứ tự bảng. "
                f"Bỏ tick 'Đánh số thứ tự' để đặt cùng 1 tên cố định. Giới hạn ≤ {RENAME_MAX_WIDTH} đơn vị (chữ Hán/có dấu tính 2)."
            )
        )
        tk.Label(
            cfg_frame,
            textvariable=self.ren_hint_var,
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=930,
            justify="left",
        ).pack(fill="x", padx=8, pady=(2, 6))

        self.ren_prefix_var.trace_add("write", lambda *_a: self._on_rename_pattern_changed())
        self.ren_start_var.trace_add("write", lambda *_a: self._on_rename_pattern_changed())

        # Khối 2: Bộ lọc Thành/Phân hệ & nút chọn nhanh
        top_bar = tk.Frame(win, bg=BG)
        top_bar.pack(fill="x", padx=12, pady=(4, 2))
        f_row1 = tk.Frame(top_bar, bg=BG)
        f_row1.pack(fill="x", pady=(0, 4))

        tk.Label(f_row1, text="Thành / Trại:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=(0, 6)
        )
        self.ren_city_combo = ttk.Combobox(f_row1, state="readonly", width=26)
        self.ren_city_combo.pack(side="left", padx=(0, 12))
        self.ren_city_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_rename_tree())

        tk.Label(f_row1, text="Phân hệ:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.ren_role_combo = ttk.Combobox(
            f_row1, state="readonly", width=20, values=[_ROLE_ALL, _ROLE_VO, _ROLE_VAN]
        )
        self.ren_role_combo.set(_ROLE_ALL)
        self.ren_role_combo.pack(side="left", padx=(0, 10))
        self.ren_role_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_rename_tree())

        self.ren_refresh_btn = ttk.Button(
            f_row1, text="🔄 Làm mới", style="Action.TButton", command=self._rename_refresh_roster
        )
        self.ren_refresh_btn.pack(side="right", padx=2)

        f_row2 = tk.Frame(top_bar, bg=BG)
        f_row2.pack(fill="x")
        for text, cmd in (
            ("☑ Tất cả", self._ren_select_all),
            ("☐ Bỏ chọn", self._ren_deselect_all),
            ("⚔️ Chọn Võ", self._ren_select_vo),
            ("📜 Chọn Văn", self._ren_select_van),
        ):
            ttk.Button(f_row2, text=text, style="Action.TButton", command=cmd).pack(side="left", padx=(0, 4))

        self.ren_summary_var = tk.StringVar(value="")
        tk.Label(win, textvariable=self.ren_summary_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=12, pady=(2, 4)
        )

        # Bảng danh sách tướng & xem trước tên mới
        tree_frame = ttk.LabelFrame(
            win,
            text="2. Danh sách Văn quan & Võ tướng (cột 'Tên mới (Xem trước)' áp dụng cho các tướng đã chọn)",
            style="Card.TLabelframe",
        )
        tree_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self.ren_tree = ttk.Treeview(
            tree_frame,
            columns=("sel", "role", "city", "lv", "preview", "status"),
            show="tree headings",
            selectmode="browse",
        )
        for col, text, w, anchor in (
            ("#0", "Tên hiện tại", 145, "w"),
            ("sel", "Chọn", 45, "center"),
            ("role", "Chức vụ", 80, "center"),
            ("city", "Thành / Trại", 115, "w"),
            ("lv", "Cấp", 50, "center"),
            ("preview", "Tên mới (Xem trước)", 175, "w"),
            ("status", "Trạng thái", 115, "center"),
        ):
            self.ren_tree.heading(col, text=text)
            self.ren_tree.column(col, width=w, anchor=anchor)

        ren_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.ren_tree.yview)
        self.ren_tree.configure(yscrollcommand=ren_scroll.set)
        self.ren_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        ren_scroll.pack(side="right", fill="y", padx=(0, 6), pady=6)

        self.ren_tree.bind("<Button-1>", self._on_ren_tree_click)
        self.ren_tree.bind("<space>", self._on_ren_tree_space)

        # Khối 3: Thực thi & nhật ký
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", padx=12, pady=(6, 4))

        self.ren_apply_btn = ttk.Button(
            btn_row, text="✏️ Thực Hiện Đổi Tên", style="Success.TButton", command=self._start_rename_action
        )
        self.ren_apply_btn.pack(side="left", padx=(0, 6))
        self.ren_stop_btn = ttk.Button(
            btn_row, text="⏹ Dừng", style="Danger.TButton", command=self._stop_rename_action
        )
        self.ren_stop_btn.pack(side="left")
        self.ren_stop_btn.state(["disabled"])
        ttk.Button(btn_row, text="Đóng", style="Action.TButton", command=_on_close).pack(side="right")

        self.ren_status_var = tk.StringVar(value="Sẵn sàng")
        tk.Label(win, textvariable=self.ren_status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=12, pady=(2, 2)
        )

        log_frame = ttk.LabelFrame(win, text="Nhật ký Đổi tên", style="Card.TLabelframe")
        log_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.ren_log_text = tk.Text(
            log_frame, height=6, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=("Consolas", 9)
        )
        self.ren_log_text.pack(fill="x", padx=6, pady=6)

        self._sync_rename_city_combo(default_from_overview=True)
        self._refresh_rename_tree()

    # ------------------------------------------------------------------ filter / preview
    def _on_rename_roster_updated(self):
        win = getattr(self, "_rename_dialog", None)
        if win is None or not win.winfo_exists():
            return
        self._sync_rename_city_combo(default_from_overview=False)
        self._refresh_rename_tree()

    def _on_rename_pattern_changed(self):
        win = getattr(self, "_rename_dialog", None)
        if win is None or not win.winfo_exists():
            return
        numbered = bool(self.ren_numbered_var.get()) if hasattr(self, "ren_numbered_var") else True
        if hasattr(self, "ren_start_entry") and self.ren_start_entry.winfo_exists():
            self.ren_start_entry.configure(state="normal" if numbered else "disabled")
        self._refresh_rename_tree()

    def _sync_rename_city_combo(self, default_from_overview: bool = False):
        if not hasattr(self, "ren_city_combo") or not self.ren_city_combo.winfo_exists():
            return
        values = [_ALL_CITIES]
        self._ren_base_by_name = {}
        selected_display = _ALL_CITIES

        overview_base_id = None
        if default_from_overview and hasattr(self, "city_tree"):
            sel = self.city_tree.selection()
            if sel:
                try:
                    overview_base_id = int(sel[0])
                except ValueError:
                    overview_base_id = None

        current_text = self.ren_city_combo.get()
        if self.roster:
            for base in self.roster.bases:
                values.append(base.display_name)
                self._ren_base_by_name[base.display_name] = base.id
                if default_from_overview and overview_base_id == base.id:
                    selected_display = base.display_name

        self.ren_city_combo["values"] = values
        if default_from_overview:
            self.ren_city_combo.set(selected_display)
        elif current_text in values:
            self.ren_city_combo.set(current_text)
        else:
            self.ren_city_combo.set(_ALL_CITIES)

    def _get_ren_filter_role(self) -> Optional[str]:
        val = self.ren_role_combo.get() if hasattr(self, "ren_role_combo") else _ROLE_ALL
        if val == _ROLE_VO:
            return "vo"
        if val == _ROLE_VAN:
            return "van"
        return None

    def _filtered_rename_generals(self) -> list[tuple[int, str, General]]:
        if not self.roster:
            return []
        base_filter = self._ren_base_by_name.get(self.ren_city_combo.get()) if hasattr(self, "ren_city_combo") else None
        role_filter = self._get_ren_filter_role()
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
                seen.add(g.id)
                city_rows.append((base.id, base.name, g))
            city_rows.sort(key=lambda r: (-r[2].level, r[2].id))
            rows.extend(city_rows)
        return rows

    def _parse_ren_start_index(self) -> int:
        raw = self.ren_start_var.get().strip() if hasattr(self, "ren_start_var") else "1"
        try:
            return max(1, int(raw))
        except ValueError:
            return 1

    def _compute_selected_rename_plan(self) -> list[tuple[int, General, str]]:
        rows = self._filtered_rename_generals()
        selected_rows = [(cid, g) for cid, _cname, g in rows if g.id in self._ren_selected_ids]
        prefix = self.ren_prefix_var.get() if hasattr(self, "ren_prefix_var") else ""
        numbered = bool(self.ren_numbered_var.get()) if hasattr(self, "ren_numbered_var") else True
        start_idx = self._parse_ren_start_index()
        return build_rename_plan(selected_rows, prefix, numbered=numbered, start_index=start_idx)

    def _update_rename_example_label(self):
        if not hasattr(self, "ren_example_var"):
            return
        prefix = sanitize_general_name(self.ren_prefix_var.get() if hasattr(self, "ren_prefix_var") else "")
        numbered = bool(self.ren_numbered_var.get()) if hasattr(self, "ren_numbered_var") else True
        start_idx = self._parse_ren_start_index()
        if not prefix:
            self.ren_example_var.set("⚠️ Nhập tiền tố hoặc tên mới")
            return
        sample = f"{prefix}{start_idx:02d}" if numbered else prefix
        ok, _err = validate_general_name(sample)
        w = general_name_width(sample)
        tail = f", {prefix}{start_idx + 1:02d}..." if numbered else ""
        if ok:
            self.ren_example_var.set(f"Mẫu: {sample}{tail} ({w}/{RENAME_MAX_WIDTH})")
        else:
            self.ren_example_var.set(f"⚠️ Quá dài: {sample} ({w}/{RENAME_MAX_WIDTH})")

    def _refresh_rename_tree(self):
        if not hasattr(self, "ren_tree") or not self.ren_tree.winfo_exists():
            return
        self.ren_tree.delete(*self.ren_tree.get_children())
        rows = self._filtered_rename_generals()
        plan = self._compute_selected_rename_plan()
        preview_by_gid = {g.id: new_name for _cid, g, new_name in plan}

        invalid_count = 0
        for _cid, cname, g in rows:
            is_sel = g.id in self._ren_selected_ids
            preview = preview_by_gid.get(g.id, "") if is_sel else "-"
            if is_sel:
                if not preview:
                    preview = "⚠️ (Trống)"
                    invalid_count += 1
                else:
                    ok_v, _err = validate_general_name(preview)
                    if not ok_v:
                        preview = f"⚠️ {preview} (Quá dài)"
                        invalid_count += 1
            self.ren_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(
                    "☑" if is_sel else "☐",
                    ROLE_TEXT.get(g.role, g.role),
                    cname,
                    g.level,
                    preview,
                    g.status_text,
                ),
            )

        self._update_rename_example_label()
        warn_part = f"  •  ⚠️ Không hợp lệ: {invalid_count}" if invalid_count else ""
        self.ren_summary_var.set(
            f"Tướng hiển thị: {len(rows)}  •  Đã chọn đổi tên: {len(plan)}{warn_part}"
        )

    def _toggle_ren_item(self, iid: str):
        if not self.ren_tree.exists(iid):
            return
        gid = int(iid)
        if gid in self._ren_selected_ids:
            self._ren_selected_ids.discard(gid)
        else:
            self._ren_selected_ids.add(gid)
        self._refresh_rename_tree()

    def _on_ren_tree_click(self, event):
        item = self.ren_tree.identify_row(event.y)
        col = self.ren_tree.identify_column(event.x)
        if item and self.ren_tree.exists(item) and col in ("#0", "#1"):
            self._toggle_ren_item(item)

    def _on_ren_tree_space(self, _event=None):
        sel = self.ren_tree.selection()
        if sel:
            self._toggle_ren_item(sel[0])

    def _ren_apply_bulk_selection(self, predicate):
        for _cid, _cname, g in self._filtered_rename_generals():
            if predicate(g):
                self._ren_selected_ids.add(g.id)
            else:
                self._ren_selected_ids.discard(g.id)
        self._refresh_rename_tree()

    def _ren_select_all(self):
        self._ren_apply_bulk_selection(lambda _g: True)

    def _ren_deselect_all(self):
        self._ren_apply_bulk_selection(lambda _g: False)

    def _ren_select_vo(self):
        self._ren_apply_bulk_selection(lambda g: g.role == "vo")

    def _ren_select_van(self):
        self._ren_apply_bulk_selection(lambda g: g.role == "van")

    # ------------------------------------------------------------------ background execution
    def _append_ren_log(self, msg: str):
        self._log_global(msg)
        widget = getattr(self, "ren_log_text", None)
        if widget is not None and widget.winfo_exists():
            self._append_text_buffer(widget, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _set_ren_running(self, running: bool, allow_stop: bool = True):
        self._ren_running = running
        win = getattr(self, "_rename_dialog", None)
        if win is None or not win.winfo_exists():
            return
        for name in ("ren_apply_btn", "ren_refresh_btn"):
            btn = getattr(self, name, None)
            if btn is not None and btn.winfo_exists():
                btn.state(["disabled"] if running else ["!disabled"])
        if hasattr(self, "ren_stop_btn") and self.ren_stop_btn.winfo_exists():
            self.ren_stop_btn.state(["!disabled"] if (running and allow_stop) else ["disabled"])

    def _stop_rename_action(self):
        if self._ren_stop_event is not None:
            self._ren_stop_event.set()
            self.ren_status_var.set("Đang dừng tác vụ Đổi tên tướng...")

    def _rename_refresh_roster(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_ren_running", False):
            return
        if self.gateway is None:
            messagebox.showwarning("Đổi Tên Tướng", "Chưa kết nối tài khoản game.", parent=self._rename_dialog)
            return
        self._set_ren_running(True, allow_stop=False)
        self.ren_status_var.set("Đang tải lại danh sách tướng...")
        q: queue.Queue = queue.Queue()
        self._ren_queue = q

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                q.put(("roster_done", fresh, None))
            except Exception as exc:
                q.put(("roster_done", None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_rename_queue)

    def _start_rename_action(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_ren_running", False):
            return
        win = self._rename_dialog
        if self.gateway is None:
            messagebox.showwarning("Đổi Tên Tướng", "Chưa kết nối tài khoản game.", parent=win)
            return

        plan = self._compute_selected_rename_plan()
        if not plan:
            messagebox.showwarning("Đổi Tên Tướng", "Vui lòng chọn ít nhất 1 tướng trong danh sách.", parent=win)
            return

        prefix_clean = sanitize_general_name(self.ren_prefix_var.get())
        if not prefix_clean:
            messagebox.showwarning("Đổi Tên Tướng", "Vui lòng nhập tiền tố hoặc tên mới.", parent=win)
            return

        invalid_samples = []
        for _cid, gen, new_name in plan:
            ok_v, err_v = validate_general_name(new_name)
            if not ok_v:
                invalid_samples.append(f"{gen.name} → {new_name}: {err_v}")
        if invalid_samples:
            preview_err = "\n".join(invalid_samples[:5])
            messagebox.showerror(
                "Tên mới không hợp lệ",
                f"Có {len(invalid_samples)} tên vượt giới hạn máy chủ:\n{preview_err}",
                parent=win,
            )
            return

        rename_items = [(gen.id, new_name) for _cid, gen, new_name in plan]
        self._ren_stop_event = threading.Event()
        stop_event = self._ren_stop_event
        self._set_ren_running(True, allow_stop=True)
        self.ren_status_var.set(f"Đang đổi tên cho {len(rename_items)} tướng...")
        q: queue.Queue = queue.Queue()
        self._ren_queue = q

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                summary = rename_generals(
                    self.gateway,
                    fresh,
                    rename_items,
                    stop_event=stop_event,
                    on_log=lambda m: q.put(("log", m)),
                )
                updated_roster = fetch_roster(self.gateway) if summary.renamed > 0 else fresh
                q.put(("rename_done", summary, updated_roster, None))
            except Exception as exc:
                q.put(("rename_done", None, None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_rename_queue)

    def _poll_rename_queue(self):
        if getattr(self, "_closing", False):
            return
        q = getattr(self, "_ren_queue", None)
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
                self._append_ren_log(item[1])
            elif kind == "roster_done":
                keep = False
                self._on_ren_roster_loaded(item[1], item[2])
            elif kind == "rename_done":
                keep = False
                self._on_ren_finished(item[1], item[2], item[3])
        if keep and getattr(self, "_ren_running", False):
            self.after(30, self._poll_rename_queue)

    def _on_ren_roster_loaded(self, fresh_roster: Optional[Roster], error: Optional[str]):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_ren_running(False)
        win = getattr(self, "_rename_dialog", None)
        if error is not None or fresh_roster is None:
            self._append_ren_log(f"⚠️ Lỗi tải danh sách tướng: {error}")
            if win is not None and win.winfo_exists():
                self.ren_status_var.set(f"Lỗi tải: {error}")
                messagebox.showerror("Đổi Tên Tướng", f"Không thể tải danh sách tướng:\n{error}", parent=win)
            return
        self.roster = fresh_roster
        if hasattr(self, "_loaded"):
            self._loaded(fresh_roster)
        if win is not None and win.winfo_exists():
            self._sync_rename_city_combo(default_from_overview=False)
            self._refresh_rename_tree()
            self.ren_status_var.set("Đã cập nhật danh sách tướng mới nhất.")

    def _on_ren_finished(
        self,
        summary: Optional[RenameSummary],
        fresh_roster: Optional[Roster],
        error: Optional[str],
    ):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_ren_running(False)
        win = getattr(self, "_rename_dialog", None)
        if error is not None or summary is None:
            self._append_ren_log(f"❌ Lỗi đổi tên tướng: {error}")
            if win is not None and win.winfo_exists():
                self.ren_status_var.set(f"Lỗi: {error}")
                messagebox.showerror("Đổi Tên Tướng", f"Đã xảy ra lỗi:\n{error}", parent=win)
            return
        if fresh_roster is not None:
            self.roster = fresh_roster
            if hasattr(self, "_loaded") and summary.renamed > 0:
                self._loaded(fresh_roster)
        msg = (
            f"Hoàn tất: Đổi tên {summary.renamed}, Trùng tên {summary.skipped_same}, "
            f"Không hợp lệ {summary.invalid_name}, Khóa {summary.skipped_blocked}, Lỗi {summary.failed}"
        )
        self._append_ren_log(f"✏️ {msg}")
        if win is not None and win.winfo_exists():
            self._sync_rename_city_combo(default_from_overview=False)
            self._refresh_rename_tree()
            self.ren_status_var.set(msg)
            messagebox.showinfo(
                "Kết quả Đổi Tên Tướng",
                (
                    f"Đổi tên thành công: {summary.renamed} tướng\n"
                    f"Trùng tên hiện tại (bỏ qua): {summary.skipped_same}\n"
                    f"Tên không hợp lệ: {summary.invalid_name}\n"
                    f"Trạng thái khóa (bỏ qua): {summary.skipped_blocked}\n"
                    f"Thất bại: {summary.failed}"
                ),
                parent=win,
            )
