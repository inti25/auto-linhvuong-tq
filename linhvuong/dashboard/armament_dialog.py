"""Hộp thoại Đồng Bộ Quân Giới cho Võ tướng trên Dashboard (ADR-0039)."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..armament import (
    ALL_SCOPES,
    SCOPE_NAMES,
    ArmamentSnapshot,
    ArmamentSyncSummary,
    armament_matches,
    describe_armament,
    fetch_armament,
    sync_armament,
)
from ..gui import set_app_icon
from ..roster import General, Roster, fetch_roster as _default_fetch_roster
from .shared import ACCENT, BG, CARD, FG, MUTED, resolve_dashboard_symbol

_ALL_LABEL = "🌟 Tất cả các thành"


class ArmamentDialogMixin:
    """Quản lý cửa sổ Đồng Bộ Quân Giới Võ Tướng."""

    def _armament_vo_generals(self) -> list[tuple[str, int, General]]:
        rows: list[tuple[str, int, General]] = []
        seen: set[int] = set()
        if not self.roster:
            return rows
        for base in self.roster.bases:
            for g in self.roster.generals_of(base.id):
                if g.role == "vo" and g.id not in seen:
                    seen.add(g.id)
                    rows.append((base.name, base.id, g))
        rows.sort(key=lambda r: (-r[2].level, r[2].id))
        return rows

    def _open_armament_dialog(self):
        existing = getattr(self, "_arm_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            self._on_arm_roster_updated()
            return

        win = tk.Toplevel(self)
        win.title("⚔️ Đồng Bộ Quân Giới Võ Tướng")
        win.geometry("1060x700")
        win.minsize(900, 560)
        win.configure(bg=BG)
        win.transient(self)
        set_app_icon(win)
        self._arm_dialog = win
        self._arm_selected_ids: set[int] = set()
        self._arm_running = False
        self._arm_stop_event = None
        self._arm_snapshots: dict[int, ArmamentSnapshot] = {}
        self._arm_template_by_name: dict[str, int] = {}
        self._arm_base_by_name: dict[str, int] = {}

        def _on_close():
            if getattr(self, "_arm_running", False):
                mb = resolve_dashboard_symbol("messagebox", _default_messagebox)
                if not mb.askyesno(
                    "Đang đồng bộ Quân Giới", "Tác vụ đang chạy. Dừng và đóng cửa sổ?", parent=win
                ):
                    return
                if self._arm_stop_event is not None:
                    self._arm_stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Khối 1: Chuẩn đồng bộ
        std = ttk.LabelFrame(win, text="1. Chuẩn đồng bộ (Võ tướng mẫu)", style="Card.TLabelframe")
        std.pack(fill="x", padx=12, pady=(10, 4))
        r1 = tk.Frame(std, bg=CARD)
        r1.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(r1, text="Võ tướng mẫu:", bg=CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.arm_template_combo = ttk.Combobox(r1, state="readonly", width=40)
        self.arm_template_combo.pack(side="left", padx=6)
        self.arm_template_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_arm_template_changed())
        self.arm_refresh_btn = ttk.Button(
            r1, text="🔄 Tải lại", style="Action.TButton", command=lambda: self._arm_refresh_data(True, True)
        )
        self.arm_refresh_btn.pack(side="right")

        self.arm_preview_var = tk.StringVar(value="Chưa tải cấu hình tướng mẫu.")
        tk.Label(std, textvariable=self.arm_preview_var, bg=CARD, fg=ACCENT, font=("Segoe UI", 9), anchor="w").pack(
            fill="x", padx=8
        )

        r2 = tk.Frame(std, bg=CARD)
        r2.pack(fill="x", padx=8, pady=(2, 6))
        tk.Label(r2, text="Phạm vi:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.arm_scope_vars: dict[str, tk.BooleanVar] = {}
        for scope in ALL_SCOPES:
            var = tk.BooleanVar(value=True)
            self.arm_scope_vars[scope] = var
            ttk.Checkbutton(r2, text=SCOPE_NAMES[scope], variable=var, command=self._refresh_arm_tree).pack(
                side="left", padx=4
            )
        self.arm_formation_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r2, text="Trận hình", variable=self.arm_formation_var, command=self._refresh_arm_tree).pack(
            side="left", padx=4
        )

        # Khối 2: Danh sách Võ tướng đích
        top = tk.Frame(win, bg=BG)
        top.pack(fill="x", padx=12, pady=(4, 2))
        tk.Label(top, text="Thành / Trại:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.arm_city_combo = ttk.Combobox(top, state="readonly", width=26)
        self.arm_city_combo.pack(side="left", padx=(0, 10))
        self.arm_city_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_arm_tree())
        for text, cmd in (
            ("☑ Tất cả", self._arm_select_all),
            ("☐ Bỏ chọn", self._arm_deselect_all),
            ("✨ Chưa khớp mẫu", self._arm_select_mismatch),
        ):
            ttk.Button(top, text=text, style="Action.TButton", command=cmd).pack(side="left", padx=3)

        self.arm_summary_var = tk.StringVar(value="")
        tk.Label(win, textvariable=self.arm_summary_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=12, pady=(0, 2)
        )

        tree_frame = ttk.LabelFrame(win, text="2. Danh sách Võ tướng đích", style="Card.TLabelframe")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=4)
        self.arm_tree = ttk.Treeview(
            tree_frame,
            columns=("sel", "city", "inf", "cav", "bow", "mang", "array", "status"),
            show="tree headings",
            selectmode="browse",
        )
        for col, text, w, anchor in (
            ("#0", "Võ tướng", 120, "w"),
            ("sel", "Chọn", 45, "center"),
            ("city", "Thành / Trại", 100, "w"),
            ("inf", "Bộ binh", 120, "w"),
            ("cav", "Kỵ binh", 120, "w"),
            ("bow", "Cung binh", 120, "w"),
            ("mang", "Xe ném đá", 100, "w"),
            ("array", "Trận", 45, "center"),
            ("status", "Trạng thái", 95, "center"),
        ):
            self.arm_tree.heading(col, text=text)
            self.arm_tree.column(col, width=w, anchor=anchor)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.arm_tree.yview)
        self.arm_tree.configure(yscrollcommand=scroll.set)
        self.arm_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scroll.pack(side="right", fill="y", padx=(0, 6), pady=6)
        self.arm_tree.bind("<Button-1>", self._on_arm_tree_click)
        self.arm_tree.bind("<space>", self._on_arm_tree_space)

        # Khối 3: Thực thi & nhật ký
        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(fill="x", padx=12, pady=(6, 4))
        self.arm_sync_btn = ttk.Button(
            btn_row, text="🔄 Đồng Bộ Quân Giới", style="Success.TButton", command=self._start_armament_sync
        )
        self.arm_sync_btn.pack(side="left", padx=(0, 6))
        self.arm_stop_btn = ttk.Button(btn_row, text="⏹ Dừng", style="Danger.TButton", command=self._stop_armament_sync)
        self.arm_stop_btn.pack(side="left")
        self.arm_stop_btn.state(["disabled"])
        ttk.Button(btn_row, text="Đóng", style="Action.TButton", command=_on_close).pack(side="right")

        self.arm_status_var = tk.StringVar(value="Sẵn sàng")
        tk.Label(win, textvariable=self.arm_status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=12, pady=(2, 2)
        )
        log_frame = ttk.LabelFrame(win, text="Nhật ký Quân Giới", style="Card.TLabelframe")
        log_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.arm_log_text = tk.Text(
            log_frame, height=7, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=("Consolas", 9)
        )
        self.arm_log_text.pack(fill="x", padx=6, pady=6)

        self._sync_arm_combos(initial=True)
        self._refresh_arm_tree()
        if self.gateway is not None:
            self._arm_refresh_data(reload_roster=self.roster is None, manual=False)

    # ------------------------------------------------------------------ combos / tree
    def _on_arm_roster_updated(self):
        win = getattr(self, "_arm_dialog", None)
        if win is None or not win.winfo_exists():
            return
        self._sync_arm_combos(initial=False)
        self._refresh_arm_tree()

    def _sync_arm_combos(self, initial: bool = False):
        if not hasattr(self, "arm_template_combo") or not self.arm_template_combo.winfo_exists():
            return
        rows = self._armament_vo_generals()
        cur_tpl = self.arm_template_combo.get()
        names: list[str] = []
        self._arm_template_by_name = {}
        for base_name, _bid, g in rows:
            label = f"{g.name} (Cấp {g.level}) - {base_name} #{g.id}"
            names.append(label)
            self._arm_template_by_name[label] = g.id
        self.arm_template_combo["values"] = names
        if cur_tpl in names:
            self.arm_template_combo.set(cur_tpl)
        elif names:
            self.arm_template_combo.set(names[0])
        else:
            self.arm_template_combo.set("")

        values = [_ALL_LABEL]
        self._arm_base_by_name = {}
        cur_city = self.arm_city_combo.get()
        if self.roster:
            for base in self.roster.bases:
                values.append(base.display_name)
                self._arm_base_by_name[base.display_name] = base.id
        self.arm_city_combo["values"] = values
        self.arm_city_combo.set(cur_city if cur_city in values else _ALL_LABEL)
        self._on_arm_template_changed(refresh_tree=False)

    def _arm_template_id(self) -> Optional[int]:
        return self._arm_template_by_name.get(self.arm_template_combo.get())

    def _on_arm_template_changed(self, refresh_tree: bool = True):
        tid = self._arm_template_id()
        snap = self._arm_snapshots.get(tid) if tid is not None else None
        self.arm_preview_var.set(describe_armament(snap) if snap else "Chưa tải cấu hình tướng mẫu.")
        if refresh_tree:
            self._refresh_arm_tree()

    def _arm_scopes(self) -> list[str]:
        return [s for s, v in self.arm_scope_vars.items() if v.get()]

    def _arm_matches(self, snap: Optional[ArmamentSnapshot]) -> Optional[bool]:
        tid = self._arm_template_id()
        tmpl = self._arm_snapshots.get(tid) if tid is not None else None
        if snap is None or tmpl is None:
            return None
        return armament_matches(snap, tmpl, self._arm_scopes(), bool(self.arm_formation_var.get()))

    def _refresh_arm_tree(self):
        if not hasattr(self, "arm_tree") or not self.arm_tree.winfo_exists():
            return
        self.arm_tree.delete(*self.arm_tree.get_children())
        base_filter = self._arm_base_by_name.get(self.arm_city_combo.get())
        tid = self._arm_template_id()
        shown = 0
        for base_name, base_id, g in self._armament_vo_generals():
            if base_filter is not None and base_id != base_filter:
                continue
            snap = self._arm_snapshots.get(g.id)
            match = self._arm_matches(snap)
            if g.id == tid:
                status = "Tướng mẫu"
            elif g.status != 0:
                status = g.status_text
            elif match is None:
                status = "-"
            else:
                status = "✅ Khớp" if match else "⚠️ Lệch"
            self.arm_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(
                    "☑" if g.id in self._arm_selected_ids else "☐",
                    base_name,
                    snap.label("infantry") if snap else "-",
                    snap.label("cavalry") if snap else "-",
                    snap.label("bowman") if snap else "-",
                    snap.label("mangonel") if snap else "-",
                    snap.battle_array if snap else "-",
                    status,
                ),
            )
            shown += 1
        self.arm_summary_var.set(f"Võ tướng hiển thị: {shown}  •  Đang chọn: {len(self._arm_selected_ids)}")

    def _toggle_arm_item(self, iid: str):
        if not self.arm_tree.exists(iid):
            return
        gid = int(iid)
        vals = list(self.arm_tree.item(iid, "values"))
        if vals[0] == "☑":
            vals[0] = "☐"
            self._arm_selected_ids.discard(gid)
        else:
            vals[0] = "☑"
            self._arm_selected_ids.add(gid)
        self.arm_tree.item(iid, values=vals)
        self.arm_summary_var.set(
            f"Võ tướng hiển thị: {len(self.arm_tree.get_children())}  •  Đang chọn: {len(self._arm_selected_ids)}"
        )

    def _on_arm_tree_click(self, event):
        item = self.arm_tree.identify_row(event.y)
        col = self.arm_tree.identify_column(event.x)
        if item and self.arm_tree.exists(item) and col in ("#0", "#1"):
            self._toggle_arm_item(item)

    def _on_arm_tree_space(self, _event=None):
        sel = self.arm_tree.selection()
        if sel:
            self._toggle_arm_item(sel[0])

    def _arm_bulk_select(self, predicate):
        tid = self._arm_template_id()
        for iid in self.arm_tree.get_children():
            gid = int(iid)
            chosen = gid != tid and bool(predicate(gid))
            if chosen:
                self._arm_selected_ids.add(gid)
            else:
                self._arm_selected_ids.discard(gid)
        self._refresh_arm_tree()

    def _arm_select_all(self):
        self._arm_bulk_select(lambda _gid: True)

    def _arm_deselect_all(self):
        self._arm_bulk_select(lambda _gid: False)

    def _arm_select_mismatch(self):
        self._arm_bulk_select(lambda gid: self._arm_matches(self._arm_snapshots.get(gid)) is False)

    # ------------------------------------------------------------------ log / state
    def _append_arm_log(self, msg: str):
        self._log_global(msg)
        widget = getattr(self, "arm_log_text", None)
        if widget is not None and widget.winfo_exists():
            self._append_text_buffer(widget, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _set_arm_running(self, running: bool, allow_stop: bool = True):
        self._arm_running = running
        win = getattr(self, "_arm_dialog", None)
        if win is None or not win.winfo_exists():
            return
        for name in ("arm_sync_btn", "arm_refresh_btn"):
            btn = getattr(self, name, None)
            if btn is not None and btn.winfo_exists():
                btn.state(["disabled"] if running else ["!disabled"])
        if hasattr(self, "arm_stop_btn") and self.arm_stop_btn.winfo_exists():
            self.arm_stop_btn.state(["!disabled"] if (running and allow_stop) else ["disabled"])

    def _stop_armament_sync(self):
        if self._arm_stop_event is not None:
            self._arm_stop_event.set()
            self.arm_status_var.set("Đang dừng đồng bộ Quân Giới...")

    # ------------------------------------------------------------------ background work
    def _arm_load_snapshots(self, roster: Roster) -> dict[int, ArmamentSnapshot]:
        snaps: dict[int, ArmamentSnapshot] = {}
        for base in roster.bases:
            for g in roster.generals_of(base.id):
                if g.role != "vo" or g.id in snaps:
                    continue
                snap = fetch_armament(self.gateway, g.id, base.id)
                if snap is not None:
                    snaps[g.id] = snap
        return snaps

    def _arm_refresh_data(self, reload_roster: bool = True, manual: bool = True):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_arm_running", False):
            return
        if self.gateway is None:
            if manual and getattr(self, "_arm_dialog", None):
                messagebox.showwarning("Quân Giới Tướng", "Chưa kết nối tài khoản game.", parent=self._arm_dialog)
            return
        self._set_arm_running(True, allow_stop=False)
        self.arm_status_var.set("Đang tải cấu hình Quân Giới của các Võ tướng...")
        q: queue.Queue = queue.Queue()
        self._arm_queue = q

        def _worker():
            try:
                roster = fetch_roster(self.gateway) if reload_roster else self.roster
                snaps = self._arm_load_snapshots(roster) if roster is not None else {}
                q.put(("loaded", roster if reload_roster else None, snaps, None, manual))
            except Exception as exc:
                q.put(("loaded", None, None, str(exc), manual))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_arm_queue)

    def _start_armament_sync(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_arm_running", False):
            return
        win = self._arm_dialog
        if self.gateway is None:
            messagebox.showwarning("Quân Giới Tướng", "Chưa kết nối tài khoản game.", parent=win)
            return
        template_id = self._arm_template_id()
        if template_id is None:
            messagebox.showwarning("Quân Giới Tướng", "Vui lòng chọn Võ tướng mẫu.", parent=win)
            return
        targets = sorted(g for g in self._arm_selected_ids if g != template_id)
        if not targets:
            messagebox.showwarning("Quân Giới Tướng", "Vui lòng chọn ít nhất 1 Võ tướng đích.", parent=win)
            return
        scopes = self._arm_scopes()
        sync_formation = bool(self.arm_formation_var.get())
        if not scopes and not sync_formation:
            messagebox.showwarning("Quân Giới Tướng", "Vui lòng chọn ít nhất 1 phạm vi đồng bộ.", parent=win)
            return

        self._arm_stop_event = threading.Event()
        stop_event = self._arm_stop_event
        self._set_arm_running(True, allow_stop=True)
        self.arm_status_var.set("Đang đồng bộ Quân Giới theo tướng mẫu...")
        q: queue.Queue = queue.Queue()
        self._arm_queue = q

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                summary = sync_armament(
                    self.gateway,
                    fresh,
                    template_id,
                    targets,
                    scopes=scopes,
                    sync_formation=sync_formation,
                    stop_event=stop_event,
                    on_log=lambda m: q.put(("log", m)),
                )
                snaps = self._arm_load_snapshots(fresh)
                q.put(("done", summary, fresh, snaps, None))
            except Exception as exc:
                q.put(("done", None, None, None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_arm_queue)

    def _poll_arm_queue(self):
        if getattr(self, "_closing", False):
            return
        q = getattr(self, "_arm_queue", None)
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
                self._append_arm_log(item[1])
            elif kind == "loaded":
                keep = False
                self._on_arm_loaded(*item[1:])
            elif kind == "done":
                keep = False
                self._on_arm_finished(*item[1:])
        if keep and getattr(self, "_arm_running", False):
            self.after(30, self._poll_arm_queue)

    def _on_arm_loaded(self, fresh_roster: Optional[Roster], snaps, error, manual):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_arm_running(False)
        win = getattr(self, "_arm_dialog", None)
        if error is not None or snaps is None:
            self._append_arm_log(f"⚠️ Lỗi tải cấu hình Quân Giới: {error}")
            if win is not None and win.winfo_exists():
                self.arm_status_var.set(f"Lỗi tải: {error}")
                if manual:
                    messagebox.showerror("Quân Giới Tướng", f"Không thể tải dữ liệu:\n{error}", parent=win)
            return
        if fresh_roster is not None:
            self.roster = fresh_roster
        self._arm_snapshots = snaps
        if win is not None and win.winfo_exists():
            self._sync_arm_combos(initial=False)
            self._refresh_arm_tree()
            self.arm_status_var.set(f"Đã tải cấu hình {len(snaps)} Võ tướng.")

    def _on_arm_finished(
        self,
        summary: Optional[ArmamentSyncSummary],
        fresh_roster: Optional[Roster],
        snaps,
        error: Optional[str],
    ):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_arm_running(False)
        win = getattr(self, "_arm_dialog", None)
        if error is not None or summary is None:
            self._append_arm_log(f"❌ Lỗi đồng bộ Quân Giới: {error}")
            if win is not None and win.winfo_exists():
                self.arm_status_var.set(f"Lỗi: {error}")
                messagebox.showerror("Quân Giới Tướng", f"Đã xảy ra lỗi:\n{error}", parent=win)
            return
        if fresh_roster is not None:
            self.roster = fresh_roster
        if snaps:
            self._arm_snapshots = snaps
        msg = (
            f"Hoàn tất: Đồng bộ {summary.synced}, Đã khớp {summary.skipped_same}, "
            f"Bận {summary.skipped_busy}, Thất bại {summary.failed}"
        )
        self._append_arm_log(f"⚔️ {msg}")
        if win is not None and win.winfo_exists():
            self._sync_arm_combos(initial=False)
            self._refresh_arm_tree()
            self.arm_status_var.set(msg)
            messagebox.showinfo(
                "Kết quả Đồng Bộ Quân Giới",
                (
                    f"Đã đồng bộ: {summary.synced} tướng\n"
                    f"Đã khớp mẫu (bỏ qua): {summary.skipped_same}\n"
                    f"Tướng bận (bỏ qua): {summary.skipped_busy}\n"
                    f"Thất bại: {summary.failed}"
                ),
                parent=win,
            )
