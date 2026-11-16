"""Tab Tổng quan, Thành/Tướng, Ban thưởng toàn bộ và Luyện Sĩ Khí trên Dashboard."""

import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..generals import RewardSummary, collect_reward_targets, reward_all_generals
from ..roster import General, Roster, fetch_roster as _default_fetch_roster
from ..tasks.morale import MoraleTrainer as _DefaultMoraleTrainer
from .shared import ACCENT, BG, CARD, FG, MUTED, ROLE_TEXT, resolve_dashboard_symbol

logger = logging.getLogger("linhvuong.dashboard")


class OverviewMixin:
    """Quản lý Tab 1: Tổng quan, Ban thưởng toàn bộ và Luyện sĩ khí quân đội."""

    def _build_overview_tab(self, parent):
        # Thanh Hồ Sơ Cấu Hình (Quản lý tập trung toàn bộ tính năng)
        profile_frame = tk.Frame(parent, bg=BG)
        profile_frame.pack(fill="x", pady=(2, 6))

        tk.Label(profile_frame, text="📁 Hồ Sơ Cấu Hình:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(
            side="left", padx=(4, 6)
        )
        self.profile_path_var = tk.StringVar(value=self.default_profile_name)
        ttk.Label(profile_frame, textvariable=self.profile_path_var, style="Dark.TLabel", font=("Consolas", 10)).pack(
            side="left", padx=(0, 12)
        )

        ttk.Button(
            profile_frame, text="💾 Lưu Cấu Hình Tổng", style="Action.TButton", command=self._save_unified_profile_dialog
        ).pack(side="left", padx=3)
        ttk.Button(
            profile_frame, text="📂 Nạp Cấu Hình Tổng", style="Action.TButton", command=self._load_unified_profile_dialog
        ).pack(side="left", padx=3)
        self.reward_all_btn = ttk.Button(
            profile_frame,
            text="🎁 Ban Thưởng Toàn Bộ",
            style="Success.TButton",
            command=self._on_reward_all_clicked,
        )
        self.reward_all_btn.pack(side="left", padx=(8, 3))
        self.tactician_btn = ttk.Button(
            profile_frame,
            text="🧠 Thiết Lập Mưu Sĩ",
            style="Action.TButton",
            command=self._open_tactician_dialog,
        )
        self.tactician_btn.pack(side="left", padx=3)
        self.equip_btn = ttk.Button(
            profile_frame,
            text="🛡️ Trang Bị Tướng",
            style="Action.TButton",
            command=self._open_equip_dialog,
        )
        self.equip_btn.pack(side="left", padx=3)
        self.armament_btn = ttk.Button(
            profile_frame,
            text="⚔️ Quân Giới Tướng",
            style="Action.TButton",
            command=self._open_armament_dialog,
        )
        self.armament_btn.pack(side="left", padx=3)

        # Tầng trên: Thành & Doanh trại, Tướng đồn trú, Chi tiết biên chế
        top_body = tk.Frame(parent, bg=BG)
        top_body.pack(fill="both", expand=True, pady=(4, 2))
        top_body.columnconfigure((0, 1, 2), weight=1, uniform="c")
        top_body.rowconfigure(0, weight=1)

        f1 = ttk.LabelFrame(top_body, text="Thành & Doanh trại", style="Card.TLabelframe")
        f1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.city_tree = ttk.Treeview(f1, columns=("type", "id", "coords"), show="tree headings", selectmode="browse")
        self.city_tree.heading("#0", text="Tên")
        self.city_tree.heading("type", text="Loại")
        self.city_tree.heading("id", text="ID")
        self.city_tree.heading("coords", text="Tọa độ")
        self.city_tree.column("#0", width=110)
        self.city_tree.column("type", width=75, anchor="center")
        self.city_tree.column("id", width=60, anchor="e")
        self.city_tree.column("coords", width=65, anchor="center")
        self.city_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.city_tree.bind("<<TreeviewSelect>>", self._on_city)

        f2 = ttk.LabelFrame(top_body, text="Tướng đồn trú", style="Card.TLabelframe")
        f2.grid(row=0, column=1, sticky="nsew", padx=6)
        self.gen_tree = ttk.Treeview(
            f2,
            columns=("role", "lv", "hp", "loyalty", "tactician", "status"),
            show="tree headings",
            selectmode="browse",
        )
        for col, text, w in (
            ("#0", "Tên tướng", 100),
            ("role", "Chức vụ", 70),
            ("lv", "Cấp", 35),
            ("hp", "Thể lực", 68),
            ("loyalty", "TT", 38),
            ("tactician", "Mưu sĩ", 90),
            ("status", "Trạng thái", 85),
        ):
            self.gen_tree.heading(col, text=text)
            anchor = (
                "center" if col in ("role", "lv", "loyalty", "status") else ("w" if col in ("#0", "tactician") else "e")
            )
            self.gen_tree.column(col, width=w, anchor=anchor)
        self.gen_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.gen_tree.bind("<<TreeviewSelect>>", self._on_general)

        f3 = ttk.LabelFrame(top_body, text="Chi tiết biên chế", style="Card.TLabelframe")
        f3.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        details = tk.Frame(f3, bg=CARD, padx=12, pady=12)
        details.pack(fill="both", expand=True, padx=6, pady=6)

        self.name_var = tk.StringVar(value="Chọn một tướng")
        self.info_var = tk.StringVar()
        self.total_var = tk.StringVar()
        ttk.Label(details, textvariable=self.name_var, style="Big.TLabel").pack(anchor="w", pady=(0, 2))
        ttk.Label(details, textvariable=self.info_var, foreground=MUTED).pack(anchor="w", pady=(0, 14))

        self.bars = {}
        for key, text, _color in (
            ("infantry", "Bộ binh", "#4da3ff"),
            ("cavalry", "Kỵ binh", "#ff9f43"),
            ("archers", "Cung binh", "#2ed573"),
        ):
            row = tk.Frame(details, bg=CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=text, bg=CARD, fg=FG, width=10, anchor="w", font=("Segoe UI", 10)).pack(side="left")
            val = tk.StringVar(value="-")
            bar = ttk.Progressbar(row, orient="horizontal", mode="determinate")
            bar.pack(side="left", fill="x", expand=True, padx=8)
            tk.Label(row, textvariable=val, bg=CARD, fg=FG, width=8, anchor="e", font=("Segoe UI", 10, "bold")).pack(
                side="right"
            )
            self.bars[key] = (bar, val)

        ttk.Label(details, textvariable=self.total_var, font=("Segoe UI", 11, "bold"), foreground=ACCENT).pack(
            anchor="w", pady=(16, 0)
        )

        # Tầng dưới: Khung 2 cột (Cột 1: Luyện Sĩ Khí, Cột 2: Chế Tạo Quân Giới)
        bottom_body = tk.Frame(parent, bg=BG)
        bottom_body.pack(fill="both", expand=True, pady=(2, 4))
        bottom_body.columnconfigure(0, weight=1)
        bottom_body.columnconfigure(1, weight=1)
        bottom_body.rowconfigure(0, weight=1)

        # Cột 1: Luyện Sĩ Khí Quân Đội (Đa Thành)
        f_morale = ttk.LabelFrame(bottom_body, text="⚔️ Luyện Sĩ Khí Quân Đội (Đa Thành)", style="Card.TLabelframe")
        f_morale.grid(row=0, column=0, sticky="nsew", padx=(0, 3))

        mo_ctrl_f = tk.Frame(f_morale, bg=CARD)
        mo_ctrl_f.pack(fill="x", padx=6, pady=4)

        mo_row1 = tk.Frame(mo_ctrl_f, bg=CARD)
        mo_row1.pack(fill="x", pady=(0, 2))

        tk.Label(mo_row1, text="Thành:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 4))
        self.mo_city_combo = ttk.Combobox(mo_row1, state="readonly", width=16)
        self.mo_city_combo.pack(side="left", padx=(0, 6))
        self.mo_city_combo.bind("<<ComboboxSelected>>", self._on_mo_city_selected)

        tk.Label(mo_row1, text="Đích:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        self.mo_target_morale_combo = ttk.Combobox(mo_row1, state="readonly", width=4, values=["100", "95", "90", "85"])
        self.mo_target_morale_combo.set("100")
        self.mo_target_morale_combo.pack(side="left", padx=(0, 6))

        ttk.Button(mo_row1, text="☑ Tất cả", style="Action.TButton", command=self._select_all_morale_generals).pack(
            side="left", padx=2
        )
        ttk.Button(mo_row1, text="☐ Bỏ chọn", style="Action.TButton", command=self._deselect_all_morale_generals).pack(
            side="left", padx=2
        )

        mo_row2 = tk.Frame(mo_ctrl_f, bg=CARD)
        mo_row2.pack(fill="x", pady=(2, 0))

        self.mo_start_btn = ttk.Button(
            mo_row2, text="⚔️ Luyện Sĩ Khí", style="Action.TButton", command=self._start_morale_training
        )
        self.mo_start_btn.pack(side="left", padx=(2, 3))

        self.mo_stop_btn = ttk.Button(
            mo_row2, text="⏹️ Dừng", style="Danger.TButton", command=self._stop_morale_training, state="disabled"
        )
        self.mo_stop_btn.pack(side="left", padx=3)

        self.mo_status_lbl = tk.Label(mo_row2, text="", bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self.mo_status_lbl.pack(side="left", padx=(6, 4))

        # Bảng tướng có quân đội
        mo_table_f = tk.Frame(f_morale, bg=CARD)
        mo_table_f.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        columns = ("sel", "name", "city", "morale", "army", "troops", "status")
        self.mo_tree = ttk.Treeview(mo_table_f, columns=columns, show="headings", selectmode="browse")

        self.mo_tree.heading("sel", text="Chọn")
        self.mo_tree.heading("name", text="Tên tướng")
        self.mo_tree.heading("city", text="Thành")
        self.mo_tree.heading("morale", text="Sĩ khí")
        self.mo_tree.heading("army", text="Quân số")
        self.mo_tree.heading("troops", text="Chi tiết")
        self.mo_tree.heading("status", text="Trạng thái")

        self.mo_tree.column("sel", width=40, anchor="center")
        self.mo_tree.column("name", width=95, anchor="w")
        self.mo_tree.column("city", width=105, anchor="w")
        self.mo_tree.column("morale", width=55, anchor="center")
        self.mo_tree.column("army", width=70, anchor="e")
        self.mo_tree.column("troops", width=110, anchor="w")
        self.mo_tree.column("status", width=120, anchor="w")

        mo_scroll = ttk.Scrollbar(mo_table_f, orient="vertical", command=self.mo_tree.yview)
        self.mo_tree.configure(yscrollcommand=mo_scroll.set)
        mo_scroll.pack(side="right", fill="y")
        self.mo_tree.pack(side="left", fill="both", expand=True)

        self.mo_tree.bind("<ButtonRelease-1>", self._on_mo_tree_click)
        self.mo_tree.bind("<space>", self._on_mo_tree_space)

        # Cột 2: Chế Tạo Quân Giới (Đa Thành) - ADR-0031
        self._build_crafting_panel(bottom_body)

    def _on_city(self, _event=None):
        sel = self.city_tree.selection()
        self.gen_tree.delete(*self.gen_tree.get_children())
        self._generals = {}
        self._show_general(None)
        if not sel:
            return
        seen = set()
        for g in self.roster.generals_of(int(sel[0])):
            iid = str(g.id)
            if iid in seen:
                continue
            seen.add(iid)
            self._generals[iid] = g
            self.gen_tree.insert(
                "",
                "end",
                iid=iid,
                text=g.name,
                values=(
                    ROLE_TEXT.get(g.role, g.role),
                    g.level,
                    f"{g.stamina}/{g.stamina_max}",
                    g.loyalty,
                    g.tactician_name or "-",
                    g.status_text,
                ),
            )

    def _on_general(self, _event=None):
        sel = self.gen_tree.selection()
        self._show_general(self._generals.get(sel[0]) if sel else None)

    def _show_general(self, g: Optional[General]):
        if g is None:
            self.name_var.set("Chọn một tướng")
            self.info_var.set("")
            self.total_var.set("")
            for bar, val in self.bars.values():
                bar.configure(value=0)
                val.set("-")
            return
        self.name_var.set(g.name)
        info_parts = [
            ROLE_TEXT.get(g.role, g.role),
            f"Cấp {g.level}",
            f"Sĩ khí {g.morale}",
            f"TT {g.loyalty}",
        ]
        if g.role == "vo":
            info_parts.append(f"Mưu sĩ: {g.tactician_name or 'Chưa có'}")
        self.info_var.set("  •  ".join(info_parts))
        army = self.roster.army_of(g.id)
        if army is None:
            self.total_var.set("Không có biên chế quân")
            for bar, val in self.bars.values():
                bar.configure(value=0)
                val.set("-")
            return
        top = max(army.infantry, army.cavalry, army.archers, 1)
        for key, (bar, val) in self.bars.items():
            n = getattr(army, key)
            bar.configure(maximum=top, value=n)
            val.set(str(n))
        self.total_var.set(f"Tổng quân: {army.total}")

    # -------------------------------------------------------------------------
    # BAN THƯỞNG TOÀN BỘ VĂN QUAN & VÕ TƯỚNG
    # -------------------------------------------------------------------------
    def _set_reward_busy(self, busy: bool):
        """Cập nhật trạng thái đang xử lý của nút Ban thưởng toàn bộ."""
        self._reward_running = busy
        if hasattr(self, "reward_all_btn") and self.reward_all_btn.winfo_exists():
            self.reward_all_btn.state(["disabled"] if busy else ["!disabled"])

    def _on_reward_all_clicked(self):
        """Tải lại roster mới nhất rồi mở hộp thoại xác nhận Ban thưởng toàn bộ."""
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        fetch_roster = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        if getattr(self, "_reward_running", False):
            return
        if self.gateway is None:
            messagebox.showwarning("Ban Thưởng Toàn Bộ", "Chưa kết nối tài khoản game.", parent=self)
            return
        self._set_reward_busy(True)
        self.status.set("Đang kiểm tra Lòng trung thành của Văn quan & Võ tướng...")
        q: queue.Queue = queue.Queue()
        self._reward_queue = q

        def _fetch_worker():
            try:
                fresh_roster = fetch_roster(self.gateway)
                q.put(("fetched", fresh_roster, None))
            except Exception as exc:
                q.put(("fetched", None, str(exc)))

        threading.Thread(target=_fetch_worker, daemon=True).start()
        self.after(20, self._poll_reward_queue)

    def _poll_reward_queue(self):
        """Rút kết quả Ban thưởng từ hàng đợi trên luồng giao diện chính."""
        if getattr(self, "_closing", False):
            return
        q = getattr(self, "_reward_queue", None)
        if q is None:
            return
        keep_polling = True
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            kind = item[0]
            if kind == "fetched":
                _, fresh_roster, err = item
                keep_polling = False
                self._confirm_and_run_reward(fresh_roster, err)
            elif kind == "log":
                self._log_global(item[1])
            elif kind == "done":
                _, summary, err = item
                keep_polling = False
                self._on_reward_finished(summary, err)
        if keep_polling and getattr(self, "_reward_running", False):
            self.after(30, self._poll_reward_queue)

    def _confirm_and_run_reward(self, fresh_roster: Optional[Roster], error: Optional[str] = None):
        """Hiển thị xác nhận số tướng và ước tính Vàng, sau đó chạy Ban thưởng nền."""
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        if error is not None or fresh_roster is None:
            self._set_reward_busy(False)
            err_msg = error or "Không tải được danh sách tướng."
            self.status.set(f"Lỗi kiểm tra Lòng trung thành: {err_msg}")
            self._log_global(f"❌ Ban thưởng thất bại khi tải dữ liệu: {err_msg}")
            messagebox.showerror("Ban Thưởng Toàn Bộ", f"Không thể tải danh sách tướng:\n{err_msg}", parent=self)
            return

        targets = collect_reward_targets(fresh_roster)
        if not targets:
            self._set_reward_busy(False)
            self.status.set("Tất cả Văn quan và Võ tướng đều đã đạt 100 Lòng trung thành.")
            messagebox.showinfo(
                "Ban Thưởng Toàn Bộ",
                "Tất cả Văn quan và Võ tướng đều đã đạt 100 Lòng trung thành.",
                parent=self,
            )
            return

        total_gold = sum(t.money_needed for t in targets)
        van_count = sum(1 for t in targets if t.general.role == "van")
        vo_count = len(targets) - van_count
        confirmed = messagebox.askyesno(
            "Xác nhận Ban Thưởng Toàn Bộ",
            (
                f"Tìm thấy {len(targets)} tướng có Lòng trung thành < 100 "
                f"({van_count} Văn quan, {vo_count} Võ tướng).\n\n"
                f"Ước tính tổng Vàng cần dùng: {total_gold:,}\n\n"
                "Bạn có muốn tiến hành Ban thưởng toàn bộ lên 100 ngay không?"
            ),
            parent=self,
        )
        if not confirmed:
            self._set_reward_busy(False)
            self.status.set("Đã hủy Ban thưởng toàn bộ.")
            return

        self.status.set(f"Đang Ban thưởng {len(targets)} tướng...")
        self._execute_reward_worker(fresh_roster)

    def _execute_reward_worker(self, target_roster: Roster):
        """Thực thi Ban thưởng toàn bộ trên luồng nền qua Queue."""
        self._set_reward_busy(True)
        q: queue.Queue = queue.Queue()
        self._reward_queue = q

        def _worker():
            try:
                summary = reward_all_generals(
                    self.gateway,
                    roster=target_roster,
                    on_log=lambda m: q.put(("log", m)),
                )
                q.put(("done", summary, None))
            except Exception as exc:
                q.put(("done", None, str(exc)))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(20, self._poll_reward_queue)

    def _on_reward_finished(self, summary: Optional[RewardSummary], error: Optional[str] = None):
        """Tổng kết Ban thưởng và làm mới Roster nếu có ít nhất 1 tướng thành công."""
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_closing", False):
            return
        self._set_reward_busy(False)
        if error is not None or summary is None:
            err_msg = error or "Lỗi không xác định."
            self.status.set(f"Ban thưởng lỗi: {err_msg}")
            self._log_global(f"❌ Ban thưởng lỗi: {err_msg}")
            messagebox.showerror("Ban Thưởng Toàn Bộ", f"Đã xảy ra lỗi khi Ban thưởng:\n{err_msg}", parent=self)
            return

        summary_msg = (
            f"Thành công: {summary.success}/{summary.total} tướng\n"
            f"Thất bại: {summary.failed}\n"
            f"Tổng Vàng đã chi: {summary.total_gold_spent:,}"
        )
        self.status.set(
            f"Ban thưởng xong: {summary.success}/{summary.total} tướng (đã chi {summary.total_gold_spent:,} Vàng)"
        )
        self._log_global(
            f"🎁 Ban thưởng hoàn tất: {summary.success} thành công, "
            f"{summary.failed} thất bại, chi {summary.total_gold_spent:,} Vàng."
        )
        if summary.failed > 0:
            messagebox.showwarning("Kết quả Ban Thưởng", summary_msg, parent=self)
        else:
            messagebox.showinfo("Kết quả Ban Thưởng", summary_msg, parent=self)

        if summary.success > 0:
            self.reload()

    # -------------------------------------------------------------------------
    # LUYỆN SĨ KHÍ QUÂN ĐỘI (ĐA THÀNH)
    # -------------------------------------------------------------------------
    def _on_mo_city_selected(self, _event=None):
        self._refresh_morale_generals()

    def _refresh_morale_generals(self):
        if not hasattr(self, "mo_tree") or not self.roster:
            return
        self.mo_tree.delete(*self.mo_tree.get_children())
        self._morale_generals_data = {}

        sel_city_text = self.mo_city_combo.get() if hasattr(self, "mo_city_combo") else ""
        target_base_id = None
        if sel_city_text and not sel_city_text.startswith("🌟"):
            for b in self.roster.bases:
                if b.display_name == sel_city_text:
                    target_base_id = b.id
                    break

        first_init = not getattr(self, "_morale_init_done", False)

        for base in self.roster.bases:
            if target_base_id is not None and base.id != target_base_id:
                continue
            for g in self.roster.generals_of(base.id):
                army = self.roster.army_of(g.id)
                if not army or army.total <= 0:
                    continue
                if first_init:
                    self._selected_morale_generals.add(g.id)
                is_sel = "☑" if g.id in self._selected_morale_generals else "☐"
                troops_str = f"B:{army.infantry:,}  K:{army.cavalry:,}  C:{army.archers:,}"
                self.mo_tree.insert(
                    "",
                    "end",
                    iid=str(g.id),
                    values=(
                        is_sel,
                        g.name,
                        f"{base.name} ({base.id})",
                        f"{g.morale}/100",
                        f"{army.total:,}",
                        troops_str,
                        "Chờ lệnh",
                    ),
                )
                self._morale_generals_data[g.id] = {
                    "city_id": base.id,
                    "general_id": g.id,
                    "current_morale": g.morale,
                    "name": g.name,
                    "city_name": base.name,
                    "army": army,
                }
        if first_init:
            self._morale_init_done = True

    def _select_all_morale_generals(self):
        if not hasattr(self, "mo_tree"):
            return
        for iid in self.mo_tree.get_children(""):
            gid = int(iid)
            self._selected_morale_generals.add(gid)
            vals = list(self.mo_tree.item(iid, "values"))
            vals[0] = "☑"
            self.mo_tree.item(iid, values=vals)

    def _deselect_all_morale_generals(self):
        if not hasattr(self, "mo_tree"):
            return
        for iid in self.mo_tree.get_children(""):
            gid = int(iid)
            self._selected_morale_generals.discard(gid)
            vals = list(self.mo_tree.item(iid, "values"))
            vals[0] = "☐"
            self.mo_tree.item(iid, values=vals)

    def _on_mo_tree_click(self, event):
        item = self.mo_tree.identify_row(event.y)
        col = self.mo_tree.identify_column(event.x)
        if not item or not self.mo_tree.exists(item):
            return
        if col == "#1" or not col:
            gid = int(item)
            vals = list(self.mo_tree.item(item, "values"))
            if vals[0] == "☑":
                vals[0] = "☐"
                self._selected_morale_generals.discard(gid)
            else:
                vals[0] = "☑"
                self._selected_morale_generals.add(gid)
            self.mo_tree.item(item, values=vals)

    def _on_mo_tree_space(self, _event=None):
        sel = self.mo_tree.selection()
        if not sel:
            return
        item = sel[0]
        if not self.mo_tree.exists(item):
            return
        gid = int(item)
        vals = list(self.mo_tree.item(item, "values"))
        if vals[0] == "☑":
            vals[0] = "☐"
            self._selected_morale_generals.discard(gid)
        else:
            vals[0] = "☑"
            self._selected_morale_generals.add(gid)
        self.mo_tree.item(item, values=vals)

    def _start_morale_training(self):
        MoraleTrainer = resolve_dashboard_symbol("MoraleTrainer", _DefaultMoraleTrainer)
        if not hasattr(self, "_morale_generals_data") or not self._morale_generals_data:
            self.mo_status_lbl.configure(text="⚠️ Không có tướng có quân đội nào để luyện.")
            return

        targets = [data for gid, data in self._morale_generals_data.items() if gid in self._selected_morale_generals]

        if not targets:
            self.mo_status_lbl.configure(text="⚠️ Vui lòng chọn ít nhất một tướng.")
            return

        target_m_str = self.mo_target_morale_combo.get().strip() if hasattr(self, "mo_target_morale_combo") else "100"
        try:
            target_morale = int(target_m_str)
        except ValueError:
            target_morale = 100

        self.mo_start_btn.configure(state="disabled")
        self.mo_stop_btn.configure(state="normal")
        self.mo_status_lbl.configure(text=f"Đang chuẩn bị luyện cho {len(targets)} tướng...")

        for item in targets:
            iid = str(item["general_id"])
            if self.mo_tree.exists(iid):
                vals = list(self.mo_tree.item(iid, "values"))
                vals[6] = "Đang luyện..."
                self.mo_tree.item(iid, values=vals)

        self._morale_stop_event = threading.Event()
        trainer = MoraleTrainer(self.gateway)

        def _worker_thread():
            try:

                def _on_prog(completed, total, res):
                    def _update_ui():
                        gid = res["general_id"]
                        succ = res["success"]
                        final_m = res["final_morale"]
                        msg = res["message"]
                        status_icon = "✅" if succ else "❌"
                        iid = str(gid)
                        if self.mo_tree.exists(iid):
                            vals = list(self.mo_tree.item(iid, "values"))
                            vals[3] = f"{final_m}/100"
                            vals[6] = f"{status_icon} {msg}"
                            self.mo_tree.item(iid, values=vals)
                        self.mo_status_lbl.configure(text=f"Tiến độ: {completed}/{total} tướng...")

                    try:
                        self.after(0, _update_ui)
                    except (RuntimeError, tk.TclError):
                        pass

                def _on_step(gid, cur, _tgt, step_msg):
                    def _update_row():
                        iid = str(gid)
                        if self.mo_tree.exists(iid):
                            vals = list(self.mo_tree.item(iid, "values"))
                            vals[3] = f"{cur}/100"
                            vals[6] = step_msg
                            self.mo_tree.item(iid, values=vals)

                    try:
                        self.after(0, _update_row)
                    except (RuntimeError, tk.TclError):
                        pass

                results = trainer.train_multiple_generals(
                    targets=targets,
                    target_morale=target_morale,
                    stop_event=self._morale_stop_event,
                    on_progress=_on_prog,
                    on_step=_on_step,
                )

                def _done_ui():
                    self.mo_start_btn.configure(state="normal")
                    self.mo_stop_btn.configure(state="disabled")
                    succ_cnt = sum(1 for r in results.values() if r.get("success"))
                    self.mo_status_lbl.configure(
                        text=f"Hoàn thành: {succ_cnt}/{len(targets)} tướng đạt mục tiêu ({target_morale})."
                    )
                    threading.Thread(target=self._fetch_roster_thread, daemon=True).start()

                try:
                    self.after(0, _done_ui)
                except (RuntimeError, tk.TclError):
                    pass

            except Exception as ex:
                logger.error(f"Lỗi khi luyện sĩ khí: {ex}")

                def _err_ui():
                    self.mo_start_btn.configure(state="normal")
                    self.mo_stop_btn.configure(state="disabled")
                    self.mo_status_lbl.configure(text=f"❌ Lỗi: {ex}")

                try:
                    self.after(0, _err_ui)
                except (RuntimeError, tk.TclError):
                    pass

        self._morale_runner = threading.Thread(target=_worker_thread, daemon=True)
        self._morale_runner.start()

    def _stop_morale_training(self):
        if self._morale_stop_event:
            self._morale_stop_event.set()
            self.mo_status_lbl.configure(text="Đang dừng tiến trình luyện sĩ khí...")
        self.mo_stop_btn.configure(state="disabled")
