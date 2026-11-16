"""Hộp thoại Thiết lập Mưu sĩ cho Võ tướng trên Dashboard."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Callable, Optional

from ..generals import (
    MODE_BY_LEVEL,
    MODE_BY_NAME,
    MODE_REMOVE,
    MODE_SEQUENTIAL,
    TacticianSummary,
    configure_tacticians,
)
from ..gui import set_app_icon
from ..roster import General, fetch_roster as _default_fetch_roster
from .shared import ACCENT, BG, CARD, FG, MUTED, resolve_dashboard_symbol


class TacticianDialogMixin:
    """Quản lý cửa sổ Thiết Lập Mưu Sĩ Cho Võ Tướng."""

    def _open_tactician_dialog(self):
        """Mở cửa sổ thiết lập Mưu sĩ cho Võ tướng theo thành/toàn bộ."""
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        existing = getattr(self, "_tac_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            self._on_tac_roster_updated()
            return

        win = tk.Toplevel(self)
        win.title("🧠 Thiết Lập Mưu Sĩ Cho Võ Tướng")
        win.geometry("920x640")
        win.minsize(780, 520)
        win.configure(bg=BG)
        win.transient(self)
        set_app_icon(win)
        self._tac_dialog = win
        self._tac_selected_ids: set[int] = set()
        self._tac_running = False
        self._tac_stop_event = None
        self._tac_base_by_name: dict[str, int] = {}

        def _on_close():
            if getattr(self, "_tac_running", False):
                if not messagebox.askyesno(
                    "Đang xử lý Mưu sĩ",
                    "Tác vụ thiết lập Mưu sĩ đang chạy. Dừng và đóng cửa sổ?",
                    parent=win,
                ):
                    return
                if self._tac_stop_event is not None:
                    self._tac_stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Thanh bộ lọc thành & nút chọn nhanh
        top_bar = tk.Frame(win, bg=BG)
        top_bar.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(top_bar, text="Thành / Trại:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=(0, 6)
        )
        self.tac_city_combo = ttk.Combobox(top_bar, state="readonly", width=28)
        self.tac_city_combo.pack(side="left", padx=(0, 10))
        self.tac_city_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_tac_tree())

        ttk.Button(top_bar, text="☑ Tất cả", style="Action.TButton", command=self._tac_select_all).pack(
            side="left", padx=2
        )
        ttk.Button(top_bar, text="☐ Bỏ chọn", style="Action.TButton", command=self._tac_deselect_all).pack(
            side="left", padx=2
        )
        ttk.Button(
            top_bar, text="✨ Chỉ chưa có MS", style="Action.TButton", command=self._tac_select_unassigned
        ).pack(side="left", padx=2)
        self.tac_refresh_btn = ttk.Button(
            top_bar, text="🔄 Làm mới", style="Action.TButton", command=self._tac_refresh_roster
        )
        self.tac_refresh_btn.pack(side="right", padx=2)

        self.tac_summary_var = tk.StringVar(value="")
        tk.Label(win, textvariable=self.tac_summary_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=12, pady=(0, 4)
        )

        # Bảng danh sách Võ tướng
        tree_frame = ttk.LabelFrame(win, text="Danh sách Võ tướng", style="Card.TLabelframe")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self.tac_tree = ttk.Treeview(
            tree_frame,
            columns=("sel", "city", "lv", "tactician", "status"),
            show="tree headings",
            selectmode="browse",
        )
        for col, text, w, anchor in (
            ("#0", "Võ tướng", 150, "w"),
            ("sel", "Chọn", 50, "center"),
            ("city", "Thành / Trại", 150, "w"),
            ("lv", "Cấp", 55, "center"),
            ("tactician", "Mưu sĩ hiện tại", 170, "w"),
            ("status", "Trạng thái", 130, "center"),
        ):
            self.tac_tree.heading(col, text=text)
            self.tac_tree.column(col, width=w, anchor=anchor)

        tac_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tac_tree.yview)
        self.tac_tree.configure(yscrollcommand=tac_scroll.set)
        self.tac_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        tac_scroll.pack(side="right", fill="y", padx=(0, 6), pady=6)

        self.tac_tree.bind("<Button-1>", self._on_tac_tree_click)
        self.tac_tree.bind("<space>", self._on_tac_tree_space)

        # Tùy chọn Đổi mưu sĩ + các nút chế độ
        ctrl_frame = tk.Frame(win, bg=BG)
        ctrl_frame.pack(fill="x", padx=12, pady=(6, 4))

        self.tac_reassign_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ctrl_frame,
            text="Đổi mưu sĩ (tháo mưu sĩ hiện tại của Võ tướng đã chọn để biên chế lại; trừ Văn quan đang làm Thái thú / bận)",
            variable=self.tac_reassign_var,
        ).pack(anchor="w", pady=(0, 6))

        btn_row = tk.Frame(ctrl_frame, bg=BG)
        btn_row.pack(fill="x")

        self.tac_mode_buttons: list[ttk.Button] = []
        mode_specs = (
            ("📈 Theo cấp (Cao → Thấp)", "Success.TButton", MODE_BY_LEVEL),
            ("🏷️ Theo tên", "Action.TButton", MODE_BY_NAME),
            ("🔢 Tuần tự", "Action.TButton", MODE_SEQUENTIAL),
            ("🔓 Tháo Mưu sĩ", "Warning.TButton", MODE_REMOVE),
        )
        for label, style_name, mode_val in mode_specs:
            btn = ttk.Button(
                btn_row,
                text=label,
                style=style_name,
                command=lambda m=mode_val: self._start_tactician_action(m),
            )
            btn.pack(side="left", padx=(0, 6))
            self.tac_mode_buttons.append(btn)

        self.tac_stop_btn = ttk.Button(
            btn_row, text="⏹ Dừng", style="Danger.TButton", command=self._stop_tactician_action
        )
        self.tac_stop_btn.pack(side="left", padx=(6, 0))
        self.tac_stop_btn.state(["disabled"])

        ttk.Button(btn_row, text="Đóng", style="Action.TButton", command=_on_close).pack(side="right")

        # Trạng thái & nhật ký mini
        self.tac_status_var = tk.StringVar(value="Sẵn sàng")
        tk.Label(win, textvariable=self.tac_status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=12, pady=(4, 2)
        )

        log_frame = ttk.LabelFrame(win, text="Nhật ký Mưu sĩ", style="Card.TLabelframe")
        log_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.tac_log_text = tk.Text(
            log_frame,
            height=7,
            bg=CARD,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=("Consolas", 9),
        )
        self.tac_log_text.pack(fill="x", padx=6, pady=6)

        self._sync_tac_city_combo(default_from_overview=True)
        self._refresh_tac_tree()

    def _on_tac_roster_updated(self):
        """Đồng bộ danh sách thành và Võ tướng khi cửa sổ Thiết lập Mưu sĩ đang mở."""
        win = getattr(self, "_tac_dialog", None)
        if win is None or not win.winfo_exists():
            return
        self._sync_tac_city_combo(default_from_overview=False)
        self._refresh_tac_tree()

    def _sync_tac_city_combo(self, default_from_overview: bool = False):
        """Cập nhật danh sách Thành/Trại trong combobox của hộp thoại Mưu sĩ."""
        if not hasattr(self, "tac_city_combo") or not self.tac_city_combo.winfo_exists():
            return
        all_label = "🌟 Tất cả các thành"
        values = [all_label]
        self._tac_base_by_name = {}
        selected_display = all_label

        overview_base_id = None
        if default_from_overview and hasattr(self, "city_tree"):
            sel = self.city_tree.selection()
            if sel:
                try:
                    overview_base_id = int(sel[0])
                except ValueError:
                    overview_base_id = None

        current_text = self.tac_city_combo.get()
        if self.roster:
            for base in self.roster.bases:
                values.append(base.display_name)
                self._tac_base_by_name[base.display_name] = base.id
                if default_from_overview and overview_base_id == base.id:
                    selected_display = base.display_name

        self.tac_city_combo["values"] = values
        if default_from_overview:
            self.tac_city_combo.set(selected_display)
        elif current_text in values:
            self.tac_city_combo.set(current_text)
        else:
            self.tac_city_combo.set(all_label)

    def _get_tac_filter_base_id(self) -> Optional[int]:
        """Trả về base_id đang lọc hoặc None nếu chọn tất cả các thành."""
        if not hasattr(self, "tac_city_combo"):
            return None
        return self._tac_base_by_name.get(self.tac_city_combo.get())

    def _refresh_tac_tree(self):
        """Đổ dữ liệu Võ tướng theo thành đang chọn vào tac_tree và cập nhật tóm tắt."""
        if not hasattr(self, "tac_tree") or not self.tac_tree.winfo_exists():
            return
        self.tac_tree.delete(*self.tac_tree.get_children())
        if not self.roster:
            self.tac_summary_var.set("Chưa có dữ liệu Roster.")
            return

        filter_base_id = self._get_tac_filter_base_id()
        seen: set[int] = set()
        shown_count = 0
        free_civilians = 0

        for base in self.roster.bases:
            if filter_base_id is not None and base.id != filter_base_id:
                continue
            for g in self.roster.generals_of(base.id):
                if g.id in seen:
                    continue
                seen.add(g.id)
                if g.role == "van":
                    if g.is_available_tactician:
                        free_civilians += 1
                    continue
                if g.role != "vo":
                    continue
                shown_count += 1
                is_sel = "☑" if g.id in self._tac_selected_ids else "☐"
                self.tac_tree.insert(
                    "",
                    "end",
                    iid=str(g.id),
                    text=g.name,
                    values=(
                        is_sel,
                        base.name,
                        g.level,
                        g.tactician_name or "-",
                        g.status_text,
                    ),
                )

        self._update_tac_summary(shown_count, free_civilians)

    def _update_tac_summary(self, shown_count: Optional[int] = None, free_civilians: Optional[int] = None):
        """Cập nhật dòng thống kê nhanh phía trên bảng Võ tướng."""
        if not hasattr(self, "tac_summary_var"):
            return
        if shown_count is None and hasattr(self, "tac_tree") and self.tac_tree.winfo_exists():
            shown_count = len(self.tac_tree.get_children())
        if free_civilians is None and self.roster:
            filter_base_id = self._get_tac_filter_base_id()
            seen_van: set[int] = set()
            free_civilians = 0
            for base in self.roster.bases:
                if filter_base_id is not None and base.id != filter_base_id:
                    continue
                for g in self.roster.generals_of(base.id):
                    if g.id in seen_van or g.role != "van":
                        continue
                    seen_van.add(g.id)
                    if g.is_available_tactician:
                        free_civilians += 1
        visible_ids = {int(iid) for iid in self.tac_tree.get_children()} if hasattr(self, "tac_tree") else set()
        selected_visible = len(self._tac_selected_ids & visible_ids)
        self.tac_summary_var.set(
            f"Võ tướng hiển thị: {shown_count or 0}  •  Đang chọn: {selected_visible} "
            f"(Tổng chọn: {len(self._tac_selected_ids)})  •  "
            f"Văn quan sẵn sàng làm Mưu sĩ: {free_civilians or 0}"
        )

    def _toggle_tac_item(self, iid: str):
        """Đảo trạng thái chọn/bỏ chọn cho một dòng trong tac_tree."""
        if not self.tac_tree.exists(iid):
            return
        gid = int(iid)
        vals = list(self.tac_tree.item(iid, "values"))
        if vals[0] == "☑":
            vals[0] = "☐"
            self._tac_selected_ids.discard(gid)
        else:
            vals[0] = "☑"
            self._tac_selected_ids.add(gid)
        self.tac_tree.item(iid, values=vals)
        self._update_tac_summary()

    def _on_tac_tree_click(self, event):
        item = self.tac_tree.identify_row(event.y)
        col = self.tac_tree.identify_column(event.x)
        if not item or not self.tac_tree.exists(item):
            return
        if col in ("#1", "#0") or not col:
            self._toggle_tac_item(item)

    def _on_tac_tree_space(self, _event=None):
        sel = self.tac_tree.selection()
        if sel:
            self._toggle_tac_item(sel[0])

    def _apply_tac_bulk_selection(self, predicate: Callable[[General], bool]):
        """Áp dụng chọn hàng loạt lên các Võ tướng đang hiển thị thỏa predicate."""
        if not self.roster or not hasattr(self, "tac_tree") or not self.tac_tree.winfo_exists():
            return
        by_id: dict[int, General] = {}
        for base in self.roster.bases:
            for g in self.roster.generals_of(base.id):
                if g.role == "vo":
                    by_id[g.id] = g
        for iid in self.tac_tree.get_children():
            gid = int(iid)
            g = by_id.get(gid)
            selected = bool(g and predicate(g))
            if selected:
                self._tac_selected_ids.add(gid)
            else:
                self._tac_selected_ids.discard(gid)
            vals = list(self.tac_tree.item(iid, "values"))
            vals[0] = "☑" if selected else "☐"
            self.tac_tree.item(iid, values=vals)
        self._update_tac_summary()

    def _tac_select_all(self):
        self._apply_tac_bulk_selection(lambda _g: True)

    def _tac_deselect_all(self):
        self._apply_tac_bulk_selection(lambda _g: False)

    def _tac_select_unassigned(self):
        self._apply_tac_bulk_selection(lambda g: g.tactician_id <= 0)

    def _tac_refresh_roster(self):
        if getattr(self, "_tac_running", False):
            return
        self.reload()

    def _append_tac_log(self, msg: str):
        """Ghi log vào cả khung mini trong hộp thoại Mưu sĩ và log toàn cục (gọi trên UI thread)."""
        self._log_global(msg)
        widget = getattr(self, "tac_log_text", None)
        if widget is not None and widget.winfo_exists():
            self._append_text_buffer(widget, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _set_tac_running(self, running: bool):
        """Bật/tắt các nút điều khiển trong hộp thoại Mưu sĩ khi đang chạy."""
        self._tac_running = running
        win = getattr(self, "_tac_dialog", None)
        if win is None or not win.winfo_exists():
            return
        for btn in getattr(self, "tac_mode_buttons", []):
            if btn.winfo_exists():
                btn.state(["disabled"] if running else ["!disabled"])
        if hasattr(self, "tac_refresh_btn") and self.tac_refresh_btn.winfo_exists():
            self.tac_refresh_btn.state(["disabled"] if running else ["!disabled"])
        if hasattr(self, "tac_stop_btn") and self.tac_stop_btn.winfo_exists():
            self.tac_stop_btn.state(["!disabled"] if running else ["disabled"])

    def _stop_tactician_action(self):
        if self._tac_stop_event is not None:
            self._tac_stop_event.set()
            self.tac_status_var.set("Đang dừng tác vụ Mưu sĩ...")

    def _start_tactician_action(self, mode: str):
        """Khởi chạy tác vụ biên chế / tháo Mưu sĩ trên luồng nền qua Queue."""
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_tac_running", False):
            return
        if self.gateway is None:
            messagebox.showwarning("Thiết Lập Mưu Sĩ", "Chưa kết nối tài khoản game.", parent=self._tac_dialog)
            return

        selected_ids = sorted(self._tac_selected_ids)
        if not selected_ids:
            messagebox.showwarning(
                "Thiết Lập Mưu Sĩ",
                "Vui lòng chọn ít nhất 1 Võ tướng trong danh sách.",
                parent=self._tac_dialog,
            )
            return

        reassign_existing = bool(self.tac_reassign_var.get()) if hasattr(self, "tac_reassign_var") else False
        self._tac_stop_event = threading.Event()
        stop_event = self._tac_stop_event
        self._set_tac_running(True)
        self.tac_status_var.set("Đang tải dữ liệu tướng mới nhất & thực thi...")
        q: queue.Queue = queue.Queue()
        self._tac_queue = q

        def _worker():
            try:
                fresh_roster = fetch_roster(self.gateway)
                summary = configure_tacticians(
                    self.gateway,
                    fresh_roster,
                    selected_general_ids=selected_ids,
                    mode=mode,
                    reassign_existing=reassign_existing,
                    stop_event=stop_event,
                    on_log=lambda m: q.put(("log", m)),
                )
                q.put(("done", summary, None))
            except Exception as exc:
                q.put(("done", None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_tac_queue)

    def _poll_tac_queue(self):
        """Rút log và kết quả Mưu sĩ từ hàng đợi trên luồng giao diện chính."""
        if getattr(self, "_closing", False):
            return
        q = getattr(self, "_tac_queue", None)
        if q is None:
            return
        keep_polling = True
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            if item[0] == "log":
                self._append_tac_log(item[1])
            elif item[0] == "done":
                keep_polling = False
                self._on_tactician_finished(item[1], item[2])
        if keep_polling and getattr(self, "_tac_running", False):
            self.after(30, self._poll_tac_queue)

    def _on_tactician_finished(self, summary: Optional[TacticianSummary], error: Optional[str] = None):
        """Cập nhật trạng thái sau khi biên chế / tháo Mưu sĩ xong."""
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_tac_running(False)
        win = getattr(self, "_tac_dialog", None)

        if error is not None or summary is None:
            err_msg = error or "Lỗi không xác định."
            self._append_tac_log(f"❌ Lỗi thiết lập Mưu sĩ: {err_msg}")
            if win is not None and win.winfo_exists():
                self.tac_status_var.set(f"Lỗi: {err_msg}")
                messagebox.showerror("Thiết Lập Mưu Sĩ", f"Đã xảy ra lỗi:\n{err_msg}", parent=win)
            return

        skipped = (
            summary.skipped_has_tactician
            + summary.skipped_busy
            + summary.no_tactician_to_remove
            + summary.no_available_civilian
        )
        msg = (
            f"Hoàn tất: Biên chế {summary.assigned}, Tháo {summary.removed}, "
            f"Bỏ qua {skipped}, Thất bại {summary.failed}"
        )
        self._append_tac_log(f"🧠 {msg}")
        if win is not None and win.winfo_exists():
            self.tac_status_var.set(msg)
            messagebox.showinfo(
                "Kết quả Thiết Lập Mưu Sĩ",
                (
                    f"Biên chế mới: {summary.assigned}\n"
                    f"Đã tháo: {summary.removed}\n"
                    f"Đã có Mưu sĩ (giữ nguyên): {summary.skipped_has_tactician}\n"
                    f"Đang bận (bỏ qua): {summary.skipped_busy}\n"
                    f"Thiếu Văn quan khả dụng: {summary.no_available_civilian}\n"
                    f"Thất bại: {summary.failed}"
                ),
                parent=win,
            )

        if summary.assigned > 0 or summary.removed > 0:
            self.reload()
