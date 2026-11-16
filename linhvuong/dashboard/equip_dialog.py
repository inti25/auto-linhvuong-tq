"""Cửa sổ Tự động Trang bị Quan văn & Võ tướng trên Dashboard."""

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Callable, Optional

from ..generals import (
    EQUIP_MODE_ASSIGN,
    EQUIP_MODE_UNEQUIP,
    EQUIP_TYPES,
    EquipSummary,
    EquipmentInventory,
    civil_priority_tier,
    configure_equipment,
    fetch_equipment_inventory,
)
from ..gui import set_app_icon
from ..roster import General, Roster, fetch_roster as _default_fetch_roster
from .shared import ACCENT, BG, CARD, FG, MUTED, ROLE_TEXT, resolve_dashboard_symbol


class EquipDialogMixin:
    """Quản lý cửa sổ Tự động Trang bị Quan văn & Võ tướng theo cấp độ Cao -> Thấp."""

    _EQUIP_ROLE_ALL = "👥 Tất cả (Võ + Văn)"
    _EQUIP_ROLE_VO = "⚔️ Chỉ Võ tướng"
    _EQUIP_ROLE_VAN = "📜 Chỉ Văn quan"

    def _open_equip_dialog(self):
        """Mở cửa sổ Tự động trang bị Quan văn & Võ tướng theo cấp độ Cao -> Thấp."""
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        existing = getattr(self, "_equip_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            self._on_equip_roster_updated()
            return

        win = tk.Toplevel(self)
        win.title("🛡️ Tự Động Trang Bị Quan Văn & Võ Tướng")
        win.geometry("1020x660")
        win.minsize(860, 540)
        win.configure(bg=BG)
        win.transient(self)
        set_app_icon(win)
        self._equip_dialog = win
        self._equip_selected_ids: set[int] = set()
        self._equip_running = False
        self._equip_stop_event = None
        self._equip_base_by_name: dict[str, int] = {}
        self._equip_inventory: Optional[EquipmentInventory] = None

        def _on_close():
            if getattr(self, "_equip_running", False):
                if not msgbox.askyesno(
                    "Đang xử lý Trang bị",
                    "Tác vụ trang bị đang chạy. Dừng và đóng cửa sổ?",
                    parent=win,
                ):
                    return
                if self._equip_stop_event is not None:
                    self._equip_stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Thanh bộ lọc Thành, Phân hệ & nút chọn nhanh
        top_bar = tk.Frame(win, bg=BG)
        top_bar.pack(fill="x", padx=12, pady=(10, 4))

        row1 = tk.Frame(top_bar, bg=BG)
        row1.pack(fill="x", pady=(0, 4))

        tk.Label(row1, text="Thành / Trại:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.equip_city_combo = ttk.Combobox(row1, state="readonly", width=26)
        self.equip_city_combo.pack(side="left", padx=(0, 12))
        self.equip_city_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_equip_tree())

        tk.Label(row1, text="Phân hệ:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.equip_role_combo = ttk.Combobox(
            row1,
            state="readonly",
            width=22,
            values=[self._EQUIP_ROLE_ALL, self._EQUIP_ROLE_VO, self._EQUIP_ROLE_VAN],
        )
        self.equip_role_combo.set(self._EQUIP_ROLE_ALL)
        self.equip_role_combo.pack(side="left", padx=(0, 10))
        self.equip_role_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_equip_tree())

        self.equip_refresh_btn = ttk.Button(
            row1,
            text="🔄 Tải kho & trang bị",
            style="Action.TButton",
            command=lambda: self._equip_refresh_data(reload_roster=True, manual=True),
        )
        self.equip_refresh_btn.pack(side="right", padx=2)

        row2 = tk.Frame(top_bar, bg=BG)
        row2.pack(fill="x")
        ttk.Button(row2, text="☑ Tất cả", style="Action.TButton", command=self._equip_select_all).pack(side="left", padx=(0, 4))
        ttk.Button(row2, text="☐ Bỏ chọn", style="Action.TButton", command=self._equip_deselect_all).pack(side="left", padx=4)
        ttk.Button(row2, text="⚔️ Chọn Võ", style="Action.TButton", command=self._equip_select_vo).pack(side="left", padx=4)
        ttk.Button(row2, text="📜 Chọn Văn", style="Action.TButton", command=self._equip_select_van).pack(side="left", padx=4)
        ttk.Button(row2, text="✨ Thiếu đồ", style="Action.TButton", command=self._equip_select_incomplete).pack(
            side="left", padx=4
        )

        self.equip_summary_var = tk.StringVar(value="")
        tk.Label(win, textvariable=self.equip_summary_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(
            anchor="w", padx=12, pady=(2, 4)
        )

        # Bảng danh sách Quan văn & Võ tướng
        tree_frame = ttk.LabelFrame(
            win,
            text="Danh sách Quan văn & Võ tướng (ưu tiên cấp Cao → Thấp)",
            style="Card.TLabelframe",
        )
        tree_frame.pack(fill="both", expand=True, padx=12, pady=4)

        self.equip_tree = ttk.Treeview(
            tree_frame,
            columns=("sel", "role", "city", "lv", "helm", "weapon", "armor", "horse", "status"),
            show="tree headings",
            selectmode="browse",
        )
        for col, text, w, anchor in (
            ("#0", "Tên tướng", 125, "w"),
            ("sel", "Chọn", 45, "center"),
            ("role", "Chức vụ", 78, "center"),
            ("city", "Thành / Trại", 110, "w"),
            ("lv", "Cấp", 45, "center"),
            ("helm", "Mũ", 125, "w"),
            ("weapon", "Vũ khí", 125, "w"),
            ("armor", "Giáp", 125, "w"),
            ("horse", "Thú cưỡi", 125, "w"),
            ("status", "Trạng thái", 95, "center"),
        ):
            self.equip_tree.heading(col, text=text)
            self.equip_tree.column(col, width=w, anchor=anchor)

        equip_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.equip_tree.yview)
        self.equip_tree.configure(yscrollcommand=equip_scroll.set)
        self.equip_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        equip_scroll.pack(side="right", fill="y", padx=(0, 6), pady=6)

        self.equip_tree.bind("<Button-1>", self._on_equip_tree_click)
        self.equip_tree.bind("<space>", self._on_equip_tree_space)

        # Tùy chọn Đổi trang bị + các nút hành động
        ctrl_frame = tk.Frame(win, bg=BG)
        ctrl_frame.pack(fill="x", padx=12, pady=(6, 4))

        self.equip_reassign_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            ctrl_frame,
            text="Đổi trang bị (tháo toàn bộ đồ của các tướng đã chọn về kho để chia lại từ đầu theo cấp Cao → Thấp)",
            variable=self.equip_reassign_var,
        ).pack(anchor="w", pady=(0, 6))

        btn_row = tk.Frame(ctrl_frame, bg=BG)
        btn_row.pack(fill="x")

        self.equip_action_buttons: list[ttk.Button] = []
        action_specs = (
            ("🛡️ Tự Động Trang Bị (Cao → Thấp)", "Success.TButton", EQUIP_MODE_ASSIGN),
            ("🔓 Tháo Trang Bị", "Warning.TButton", EQUIP_MODE_UNEQUIP),
        )
        for label, style_name, mode_val in action_specs:
            btn = ttk.Button(
                btn_row,
                text=label,
                style=style_name,
                command=lambda m=mode_val: self._start_equip_action(m),
            )
            btn.pack(side="left", padx=(0, 6))
            self.equip_action_buttons.append(btn)

        self.equip_stop_btn = ttk.Button(btn_row, text="⏹ Dừng", style="Danger.TButton", command=self._stop_equip_action)
        self.equip_stop_btn.pack(side="left", padx=(6, 0))
        self.equip_stop_btn.state(["disabled"])

        ttk.Button(btn_row, text="Đóng", style="Action.TButton", command=_on_close).pack(side="right")

        self.equip_status_var = tk.StringVar(value="Sẵn sàng")
        tk.Label(win, textvariable=self.equip_status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(
            anchor="w", padx=12, pady=(4, 2)
        )

        log_frame = ttk.LabelFrame(win, text="Nhật ký Trang bị", style="Card.TLabelframe")
        log_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.equip_log_text = tk.Text(
            log_frame,
            height=7,
            bg=CARD,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            font=("Consolas", 9),
        )
        self.equip_log_text.pack(fill="x", padx=6, pady=6)

        self._sync_equip_city_combo(default_from_overview=True)
        self._refresh_equip_tree()
        if self.gateway is not None:
            self._equip_refresh_data(reload_roster=self.roster is None, manual=False)

    def _on_equip_roster_updated(self):
        """Đồng bộ danh sách thành và tướng khi cửa sổ Trang bị tướng đang mở."""
        win = getattr(self, "_equip_dialog", None)
        if win is None or not win.winfo_exists():
            return
        self._sync_equip_city_combo(default_from_overview=False)
        self._refresh_equip_tree()

    def _sync_equip_city_combo(self, default_from_overview: bool = False):
        """Cập nhật danh sách Thành/Trại trong combobox của hộp thoại Trang bị."""
        if not hasattr(self, "equip_city_combo") or not self.equip_city_combo.winfo_exists():
            return
        all_label = "🌟 Tất cả các thành"
        values = [all_label]
        self._equip_base_by_name = {}
        selected_display = all_label

        overview_base_id = None
        if default_from_overview and hasattr(self, "city_tree"):
            sel = self.city_tree.selection()
            if sel:
                try:
                    overview_base_id = int(sel[0])
                except ValueError:
                    overview_base_id = None

        current_text = self.equip_city_combo.get()
        if self.roster:
            for base in self.roster.bases:
                values.append(base.display_name)
                self._equip_base_by_name[base.display_name] = base.id
                if default_from_overview and overview_base_id == base.id:
                    selected_display = base.display_name

        self.equip_city_combo["values"] = values
        if default_from_overview:
            self.equip_city_combo.set(selected_display)
        elif current_text in values:
            self.equip_city_combo.set(current_text)
        else:
            self.equip_city_combo.set(all_label)

    def _get_equip_filter_base_id(self) -> Optional[int]:
        """Trả về base_id đang lọc hoặc None nếu chọn tất cả các thành."""
        if not hasattr(self, "equip_city_combo"):
            return None
        return self._equip_base_by_name.get(self.equip_city_combo.get())

    def _get_equip_filter_role(self) -> Optional[str]:
        """Trả về 'vo', 'van' hoặc None nếu hiển thị cả hai hệ."""
        if not hasattr(self, "equip_role_combo"):
            return None
        val = self.equip_role_combo.get()
        if val == self._EQUIP_ROLE_VO:
            return "vo"
        if val == self._EQUIP_ROLE_VAN:
            return "van"
        return None

    def _refresh_equip_tree(self):
        """Đổ dữ liệu Văn quan & Võ tướng theo bộ lọc vào equip_tree (xếp Cao -> Thấp)."""
        if not hasattr(self, "equip_tree") or not self.equip_tree.winfo_exists():
            return
        self.equip_tree.delete(*self.equip_tree.get_children())
        if not self.roster:
            self.equip_summary_var.set("Chưa có dữ liệu Roster.")
            return

        filter_base_id = self._get_equip_filter_base_id()
        filter_role = self._get_equip_filter_role()
        inv = getattr(self, "_equip_inventory", None)

        rows: list[tuple[str, General]] = []
        seen: set[int] = set()
        for base in self.roster.bases:
            if filter_base_id is not None and base.id != filter_base_id:
                continue
            for g in self.roster.generals_of(base.id):
                if g.id in seen or g.role not in ("vo", "van"):
                    continue
                if filter_role is not None and g.role != filter_role:
                    continue
                seen.add(g.id)
                rows.append((base.name, g))

        active_tac_ids = self.roster.active_tactician_ids()
        rows.sort(
            key=lambda item: (
                civil_priority_tier(item[1], active_tac_ids) if item[1].role == "van" else 2,
                -item[1].level,
                item[1].id,
            )
        )

        for base_name, g in rows:
            is_sel = "☑" if g.id in self._equip_selected_ids else "☐"
            slots = inv.equipped_by_general.get(g.id, {}) if inv is not None else {}
            helm_txt = slots[1].short_label if 1 in slots else "-"
            weapon_txt = slots[2].short_label if 2 in slots else "-"
            armor_txt = slots[3].short_label if 3 in slots else "-"
            horse_txt = slots[4].short_label if 4 in slots else "-"
            self.equip_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(
                    is_sel,
                    ROLE_TEXT.get(g.role, g.role),
                    base_name,
                    g.level,
                    helm_txt,
                    weapon_txt,
                    armor_txt,
                    horse_txt,
                    g.status_text,
                ),
            )

        self._update_equip_summary(len(rows))

    def _update_equip_summary(self, shown_count: Optional[int] = None):
        """Cập nhật dòng thống kê nhanh phía trên bảng Trang bị."""
        if not hasattr(self, "equip_summary_var"):
            return
        if shown_count is None and hasattr(self, "equip_tree") and self.equip_tree.winfo_exists():
            shown_count = len(self.equip_tree.get_children())
        visible_ids = {int(iid) for iid in self.equip_tree.get_children()} if hasattr(self, "equip_tree") else set()
        selected_visible = len(self._equip_selected_ids & visible_ids)
        inv = getattr(self, "_equip_inventory", None)
        if inv is not None:
            vo_counts = "/".join(str(inv.count_free("vo", t)) for t in EQUIP_TYPES)
            van_counts = "/".join(str(inv.count_free("van", t)) for t in EQUIP_TYPES)
            inv_part = (
                f"  •  Kho Võ (Mũ/VK/Giáp/Ngựa): {vo_counts}"
                f"  •  Kho Văn (Mũ/VK/Giáp/Ngựa): {van_counts}"
            )
        else:
            inv_part = "  •  (Chưa tải dữ liệu kho trang bị)"
        self.equip_summary_var.set(
            f"Tướng hiển thị: {shown_count or 0}  •  Đang chọn: {selected_visible} "
            f"(Tổng chọn: {len(self._equip_selected_ids)}){inv_part}"
        )

    def _toggle_equip_item(self, iid: str):
        """Đảo trạng thái chọn/bỏ chọn cho một dòng trong equip_tree."""
        if not self.equip_tree.exists(iid):
            return
        gid = int(iid)
        vals = list(self.equip_tree.item(iid, "values"))
        if vals[0] == "☑":
            vals[0] = "☐"
            self._equip_selected_ids.discard(gid)
        else:
            vals[0] = "☑"
            self._equip_selected_ids.add(gid)
        self.equip_tree.item(iid, values=vals)
        self._update_equip_summary()

    def _on_equip_tree_click(self, event):
        item = self.equip_tree.identify_row(event.y)
        col = self.equip_tree.identify_column(event.x)
        if not item or not self.equip_tree.exists(item):
            return
        if col in ("#1", "#0") or not col:
            self._toggle_equip_item(item)

    def _on_equip_tree_space(self, _event=None):
        sel = self.equip_tree.selection()
        if sel:
            self._toggle_equip_item(sel[0])

    def _apply_equip_bulk_selection(self, predicate: Callable[[General], bool]):
        """Áp dụng chọn hàng loạt lên các tướng đang hiển thị thỏa predicate."""
        if not self.roster or not hasattr(self, "equip_tree") or not self.equip_tree.winfo_exists():
            return
        by_id: dict[int, General] = {}
        for base in self.roster.bases:
            for g in self.roster.generals_of(base.id):
                if g.role in ("vo", "van"):
                    by_id[g.id] = g
        for iid in self.equip_tree.get_children():
            gid = int(iid)
            g = by_id.get(gid)
            selected = bool(g and predicate(g))
            if selected:
                self._equip_selected_ids.add(gid)
            else:
                self._equip_selected_ids.discard(gid)
            vals = list(self.equip_tree.item(iid, "values"))
            vals[0] = "☑" if selected else "☐"
            self.equip_tree.item(iid, values=vals)
        self._update_equip_summary()

    def _equip_select_all(self):
        self._apply_equip_bulk_selection(lambda _g: True)

    def _equip_deselect_all(self):
        self._apply_equip_bulk_selection(lambda _g: False)

    def _equip_select_vo(self):
        self._apply_equip_bulk_selection(lambda g: g.role == "vo")

    def _equip_select_van(self):
        self._apply_equip_bulk_selection(lambda g: g.role == "van")

    def _equip_select_incomplete(self):
        inv = getattr(self, "_equip_inventory", None)
        if inv is None:
            self._apply_equip_bulk_selection(lambda _g: True)
            return
        self._apply_equip_bulk_selection(lambda g: len(inv.equipped_by_general.get(g.id, {})) < len(EQUIP_TYPES))

    def _append_equip_log(self, msg: str):
        """Ghi log vào cả khung mini trong hộp thoại Trang bị và log toàn cục."""
        self._log_global(msg)
        widget = getattr(self, "equip_log_text", None)
        if widget is not None and widget.winfo_exists():
            self._append_text_buffer(widget, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _set_equip_running(self, running: bool, allow_stop: bool = True):
        """Bật/tắt các nút điều khiển trong hộp thoại Trang bị khi đang chạy."""
        self._equip_running = running
        win = getattr(self, "_equip_dialog", None)
        if win is None or not win.winfo_exists():
            return
        for btn in getattr(self, "equip_action_buttons", []):
            if btn.winfo_exists():
                btn.state(["disabled"] if running else ["!disabled"])
        if hasattr(self, "equip_refresh_btn") and self.equip_refresh_btn.winfo_exists():
            self.equip_refresh_btn.state(["disabled"] if running else ["!disabled"])
        if hasattr(self, "equip_stop_btn") and self.equip_stop_btn.winfo_exists():
            self.equip_stop_btn.state(["!disabled"] if (running and allow_stop) else ["disabled"])

    def _stop_equip_action(self):
        if self._equip_stop_event is not None:
            self._equip_stop_event.set()
            self.equip_status_var.set("Đang dừng tác vụ Trang bị...")

    def _equip_refresh_data(self, reload_roster: bool = True, manual: bool = True):
        """Tải lại kho đồ đạc (và Roster nếu cần) trên luồng nền."""
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster_fn = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_equip_running", False):
            return
        if self.gateway is None:
            if manual and getattr(self, "_equip_dialog", None):
                msgbox.showwarning("Trang Bị Tướng", "Chưa kết nối tài khoản game.", parent=self._equip_dialog)
            return

        self._set_equip_running(True, allow_stop=False)
        if hasattr(self, "equip_status_var"):
            self.equip_status_var.set("Đang tải dữ liệu kho đồ & trang bị đang mặc...")
        q: queue.Queue = queue.Queue()
        self._equip_queue = q

        def _worker():
            try:
                fresh_roster = fetch_roster_fn(self.gateway) if reload_roster else None
                inv = fetch_equipment_inventory(self.gateway)
                q.put(("inv_done", fresh_roster, inv, None, manual))
            except Exception as exc:
                q.put(("inv_done", None, None, str(exc), manual))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_equip_queue)

    def _start_equip_action(self, mode: str):
        """Khởi chạy tác vụ Tự động trang bị / Tháo trang bị trên luồng nền qua Queue."""
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster_fn = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_equip_running", False):
            return
        if self.gateway is None:
            msgbox.showwarning("Trang Bị Tướng", "Chưa kết nối tài khoản game.", parent=self._equip_dialog)
            return

        selected_ids = sorted(self._equip_selected_ids)
        if not selected_ids:
            msgbox.showwarning(
                "Trang Bị Tướng",
                "Vui lòng chọn ít nhất 1 Quan văn hoặc Võ tướng trong danh sách.",
                parent=self._equip_dialog,
            )
            return

        reassign_existing = bool(self.equip_reassign_var.get()) if hasattr(self, "equip_reassign_var") else False
        self._equip_stop_event = threading.Event()
        stop_event = self._equip_stop_event
        self._set_equip_running(True, allow_stop=True)
        self.equip_status_var.set("Đang tải kho trang bị mới nhất & thực thi...")
        q: queue.Queue = queue.Queue()
        self._equip_queue = q

        def _worker():
            try:
                fresh_roster = fetch_roster_fn(self.gateway)
                fresh_inventory = fetch_equipment_inventory(self.gateway)
                summary = configure_equipment(
                    self.gateway,
                    fresh_roster,
                    selected_general_ids=selected_ids,
                    mode=mode,
                    reassign_existing=reassign_existing,
                    inventory=fresh_inventory,
                    stop_event=stop_event,
                    on_log=lambda m: q.put(("log", m)),
                )
                q.put(("action_done", summary, fresh_roster, fresh_inventory, None))
            except Exception as exc:
                q.put(("action_done", None, None, None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_equip_queue)

    def _poll_equip_queue(self):
        """Rút log và kết quả Trang bị từ hàng đợi trên luồng giao diện chính."""
        if getattr(self, "_closing", False):
            return
        q = getattr(self, "_equip_queue", None)
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
                self._append_equip_log(item[1])
            elif kind == "inv_done":
                _, fresh_roster, inv, err, manual = item
                keep_polling = False
                self._on_equip_inventory_loaded(fresh_roster, inv, err, manual)
            elif kind == "action_done":
                _, summary, fresh_roster, fresh_inventory, err = item
                keep_polling = False
                self._on_equip_finished(summary, fresh_roster, fresh_inventory, err)
        if keep_polling and getattr(self, "_equip_running", False):
            self.after(30, self._poll_equip_queue)

    def _on_equip_inventory_loaded(
        self,
        fresh_roster: Optional[Roster],
        inventory: Optional[EquipmentInventory],
        error: Optional[str],
        manual: bool,
    ):
        """Cập nhật dữ liệu kho trang bị và bảng hiển thị sau khi tải xong."""
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_equip_running(False)
        win = getattr(self, "_equip_dialog", None)

        if error is not None or inventory is None:
            err_msg = error or "Không tải được kho trang bị."
            self._append_equip_log(f"⚠️ Lỗi tải kho trang bị: {err_msg}")
            if win is not None and win.winfo_exists():
                self.equip_status_var.set(f"Lỗi tải kho: {err_msg}")
                if manual:
                    msgbox.showerror("Trang Bị Tướng", f"Không thể tải kho trang bị:\n{err_msg}", parent=win)
            return

        if fresh_roster is not None:
            self.roster = fresh_roster
        self._equip_inventory = inventory
        if win is not None and win.winfo_exists():
            self._sync_equip_city_combo(default_from_overview=False)
            self._refresh_equip_tree()
            self.equip_status_var.set("Đã cập nhật kho đồ & trang bị đang mặc.")

    def _on_equip_finished(
        self,
        summary: Optional[EquipSummary],
        fresh_roster: Optional[Roster],
        fresh_inventory: Optional[EquipmentInventory],
        error: Optional[str] = None,
    ):
        """Cập nhật trạng thái sau khi tự động trang bị / tháo trang bị xong."""
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_equip_running(False)
        win = getattr(self, "_equip_dialog", None)

        if error is not None or summary is None:
            err_msg = error or "Lỗi không xác định."
            self._append_equip_log(f"❌ Lỗi thao tác trang bị: {err_msg}")
            if win is not None and win.winfo_exists():
                self.equip_status_var.set(f"Lỗi: {err_msg}")
                msgbox.showerror("Trang Bị Tướng", f"Đã xảy ra lỗi:\n{err_msg}", parent=win)
            return

        if fresh_roster is not None:
            self.roster = fresh_roster
        if fresh_inventory is not None:
            self._equip_inventory = fresh_inventory

        msg = (
            f"Hoàn tất: Mặc/nâng {summary.equipped}, Tháo {summary.unequipped}, "
            f"Giữ tối ưu {summary.skipped_optimal}, Hết đồ {summary.no_item_available}, "
            f"Bận {summary.skipped_busy}, Thất bại {summary.failed}"
        )
        self._append_equip_log(f"🛡️ {msg}")

        if win is not None and win.winfo_exists():
            self._sync_equip_city_combo(default_from_overview=False)
            self._refresh_equip_tree()
            self.equip_status_var.set(msg)
            msgbox.showinfo(
                "Kết quả Tự Động Trang Bị",
                (
                    f"Mặc mới / nâng cấp: {summary.equipped} món\n"
                    f"Đã tháo về kho: {summary.unequipped} món\n"
                    f"Đã tối ưu (giữ nguyên): {summary.skipped_optimal} ô\n"
                    f"Không còn đồ trong kho: {summary.no_item_available} ô\n"
                    f"Tướng đang bận (bỏ qua): {summary.skipped_busy} tướng\n"
                    f"Thất bại: {summary.failed}"
                ),
                parent=win,
            )
