"""Tab Thảo Phạt Tự Động trên giao diện Dashboard."""

import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from ..roster import fetch_roster as _default_fetch_roster
from ..tasks.thao_phat import (
    ERROR_MESSAGES,
    THAOPHAT_MISSIONS,
    TargetArmy,
    ThaoPhatAutoRunner,
    ThaoPhatExecutor,
)
from .shared import BG, CARD, FG, resolve_dashboard_symbol


class ThaoPhatMixin:
    """Quản lý giao diện, cấu hình hồ sơ và tác vụ Thảo Phạt."""

    def _collect_thao_phat_profile_dict(self) -> dict:
        tp_city_id = None
        if hasattr(self, "tp_city_combo") and self.roster and self.roster.bases:
            sel_idx = self.tp_city_combo.current()
            if 0 <= sel_idx < len(self.roster.bases):
                tp_city_id = self.roster.bases[sel_idx].id
        elif getattr(self, "_pending_tp_city_id", None) is not None:
            tp_city_id = self._pending_tp_city_id

        tp_gens = []
        if hasattr(self, "tp_gen_tree") and self.tp_gen_tree.get_children():
            tp_gens = [int(iid) for iid in self.tp_gen_tree.get_children() if self.tp_gen_tree.item(iid, "values")[0] == "☑"]
        elif getattr(self, "_pending_tp_generals", None):
            tp_gens = list(self._pending_tp_generals)

        return {
            "city_id": tp_city_id,
            "generals": tp_gens,
            "min_army": self.tp_target_inf_var.get() if hasattr(self, "tp_target_inf_var") else (self.tp_min_army_var.get() if hasattr(self, "tp_min_army_var") else "5000"),
            "target_infantry": self.tp_target_inf_var.get() if hasattr(self, "tp_target_inf_var") else "5000",
            "target_cavalry": self.tp_target_cav_var.get() if hasattr(self, "tp_target_cav_var") else "0",
            "target_archers": self.tp_target_arc_var.get() if hasattr(self, "tp_target_arc_var") else "0",
            "mission_idx": self.tp_mission_combo.current() if hasattr(self, "tp_mission_combo") else 0,
            "auto_recruit": bool(self.tp_auto_recruit_var.get()) if hasattr(self, "tp_auto_recruit_var") else True,
            "auto_morale": bool(self.tp_auto_morale_var.get()) if hasattr(self, "tp_auto_morale_var") else True,
            "min_morale": self.tp_min_morale_var.get() if hasattr(self, "tp_min_morale_var") else "95",
            "interval": self.tp_interval_var.get() if hasattr(self, "tp_interval_var") else "10",
        }

    def _apply_thao_phat_profile_dict(self, tp_data: dict) -> None:
        if hasattr(self, "tp_target_inf_var"):
            if "target_infantry" in tp_data:
                self.tp_target_inf_var.set(str(tp_data["target_infantry"]))
            elif "min_army" in tp_data:
                self.tp_target_inf_var.set(str(tp_data["min_army"]))
        elif hasattr(self, "tp_min_army_var") and "min_army" in tp_data:
            self.tp_min_army_var.set(str(tp_data["min_army"]))

        if hasattr(self, "tp_target_cav_var") and "target_cavalry" in tp_data:
            self.tp_target_cav_var.set(str(tp_data["target_cavalry"]))
        if hasattr(self, "tp_target_arc_var") and "target_archers" in tp_data:
            self.tp_target_arc_var.set(str(tp_data["target_archers"]))

        if hasattr(self, "tp_mission_combo") and "mission_idx" in tp_data:
            try:
                self.tp_mission_combo.current(int(tp_data["mission_idx"]))
            except Exception:
                pass
        if hasattr(self, "tp_auto_recruit_var") and "auto_recruit" in tp_data:
            self.tp_auto_recruit_var.set(bool(tp_data["auto_recruit"]))
        if hasattr(self, "tp_auto_morale_var") and "auto_morale" in tp_data:
            self.tp_auto_morale_var.set(bool(tp_data["auto_morale"]))
        if hasattr(self, "tp_min_morale_var") and "min_morale" in tp_data:
            self.tp_min_morale_var.set(str(tp_data["min_morale"]))
        if hasattr(self, "tp_interval_var") and "interval" in tp_data:
            self.tp_interval_var.set(str(tp_data["interval"]))

        if "city_id" in tp_data and tp_data["city_id"] is not None:
            try:
                self._pending_tp_city_id = int(tp_data["city_id"])
                if hasattr(self, "tp_city_combo") and self.roster and self.roster.bases:
                    for idx, b in enumerate(self.roster.bases):
                        if b.id == self._pending_tp_city_id:
                            self.tp_city_combo.current(idx)
                            self._on_tp_city_selected()
                            break
            except (ValueError, TypeError):
                pass

        if "generals" in tp_data and isinstance(tp_data["generals"], list):
            self._pending_tp_generals = {int(x) for x in tp_data["generals"] if str(x).isdigit()}
            if hasattr(self, "tp_gen_tree") and self.tp_gen_tree.get_children():
                for iid in self.tp_gen_tree.get_children():
                    vals = list(self.tp_gen_tree.item(iid, "values"))
                    vals[0] = "☑" if int(iid) in self._pending_tp_generals else "☐"
                    self.tp_gen_tree.item(iid, values=vals)

    def _build_thaophat_tab(self, parent):
        top_ctrl = tk.Frame(parent, bg=BG)
        top_ctrl.pack(fill="x", pady=6)

        row1 = tk.Frame(top_ctrl, bg=BG)
        row1.pack(fill="x", pady=(0, 4))

        tk.Label(row1, text="Thành trì:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
        self.tp_city_combo = ttk.Combobox(row1, state="readonly", width=16)
        self.tp_city_combo.pack(side="left", padx=(0, 10))
        self.tp_city_combo.bind("<<ComboboxSelected>>", self._on_tp_city_selected)

        tk.Label(row1, text="Chiến dịch:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
        self.tp_mission_combo = ttk.Combobox(row1, state="readonly", width=14)
        self.tp_mission_combo["values"] = [f"{m['name']} (ID: {mid})" for mid, m in THAOPHAT_MISSIONS.items()]
        self.tp_mission_combo.current(0)
        self.tp_mission_combo.pack(side="left", padx=(0, 10))

        tk.Label(row1, text="Bộ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.tp_target_inf_var = tk.StringVar(value="5000")
        self.tp_min_army_var = self.tp_target_inf_var
        ttk.Entry(row1, textvariable=self.tp_target_inf_var, width=6).pack(side="left", padx=(0, 8))

        tk.Label(row1, text="Kỵ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.tp_target_cav_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.tp_target_cav_var, width=6).pack(side="left", padx=(0, 8))

        tk.Label(row1, text="Cung MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.tp_target_arc_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.tp_target_arc_var, width=6).pack(side="left", padx=(0, 10))

        ttk.Button(row1, text="⚔️ Biên chế ngay", style="Action.TButton", command=self._manual_adjust_tp_troops).pack(side="left", padx=(0, 6))

        self.tp_start_btn = ttk.Button(row1, text="▶️ Bắt đầu Thảo Phạt", style="Success.TButton", command=self._toggle_tp)
        self.tp_start_btn.pack(side="left", padx=4)

        row2 = tk.Frame(top_ctrl, bg=BG)
        row2.pack(fill="x", pady=(2, 0))

        self.tp_auto_recruit_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Tự động bổ sung lính", variable=self.tp_auto_recruit_var, style="TCheckbutton").pack(side="left", padx=(0, 16))

        self.tp_auto_morale_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Tự động nâng sĩ khí", variable=self.tp_auto_morale_var, style="TCheckbutton").pack(side="left", padx=(0, 8))

        tk.Label(row2, text="Sĩ khí tối thiểu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        self.tp_min_morale_var = tk.StringVar(value="95")
        ttk.Entry(row2, textvariable=self.tp_min_morale_var, width=5).pack(side="left", padx=(0, 10))

        tk.Label(row2, text="Chu kỳ (s):", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.tp_interval_var = tk.StringVar(value="10")
        ttk.Entry(row2, textvariable=self.tp_interval_var, width=4).pack(side="left", padx=(0, 10))

        tk.Label(row2, text="(Tự động tính toán thời gian hành quân để xuất quân tối ưu)", bg=BG, fg="#888888", font=("Segoe UI", 8, "italic")).pack(side="left", padx=4)

        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        f_top = ttk.LabelFrame(body, text="Võ tướng xuất kích (Chọn tối đa 5)", style="Card.TLabelframe")
        f_top.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        self.tp_gen_tree = ttk.Treeview(
            f_top,
            columns=("select", "lv", "stamina", "morale", "infantry", "cavalry", "archers", "total_army"),
            show="tree headings",
            selectmode="browse",
        )
        self.tp_gen_tree.heading("#0", text="Tên võ tướng")
        self.tp_gen_tree.heading("select", text="Chọn")
        self.tp_gen_tree.heading("lv", text="Cấp")
        self.tp_gen_tree.heading("stamina", text="Thể lực")
        self.tp_gen_tree.heading("morale", text="Sĩ khí")
        self.tp_gen_tree.heading("infantry", text="Bộ binh")
        self.tp_gen_tree.heading("cavalry", text="Kỵ binh")
        self.tp_gen_tree.heading("archers", text="Cung binh")
        self.tp_gen_tree.heading("total_army", text="Tổng quân")

        self.tp_gen_tree.column("#0", width=140)
        self.tp_gen_tree.column("select", width=50, anchor="center")
        self.tp_gen_tree.column("lv", width=50, anchor="center")
        self.tp_gen_tree.column("stamina", width=75, anchor="center")
        self.tp_gen_tree.column("morale", width=65, anchor="center")
        self.tp_gen_tree.column("infantry", width=80, anchor="e")
        self.tp_gen_tree.column("cavalry", width=80, anchor="e")
        self.tp_gen_tree.column("archers", width=80, anchor="e")
        self.tp_gen_tree.column("total_army", width=85, anchor="e")

        gen_scroll = ttk.Scrollbar(f_top, orient="vertical", command=self.tp_gen_tree.yview)
        self.tp_gen_tree.configure(yscrollcommand=gen_scroll.set)
        self.tp_gen_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        gen_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.tp_gen_tree.bind("<ButtonRelease-1>", self._on_tp_gen_toggle)

        f_bottom = ttk.LabelFrame(body, text="Nhật ký chiến dịch Thảo Phạt", style="Card.TLabelframe")
        f_bottom.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        log_bar = tk.Frame(f_bottom, bg=CARD)
        log_bar.pack(side="top", fill="x", padx=4, pady=(2, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._tp_clear_log).pack(side="right")

        log_scroll = ttk.Scrollbar(f_bottom, orient="vertical")
        self.tp_log_text = tk.Text(f_bottom, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0, yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.tp_log_text.yview)
        self.tp_log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        log_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))

    def _on_tp_city_selected(self, _event=None):
        sel_idx = self.tp_city_combo.current()
        bases = self.roster.bases if (self.roster and self.roster.bases) else []
        if sel_idx < 0 or sel_idx >= len(bases):
            return
        base = bases[sel_idx]
        self.tp_gen_tree.delete(*self.tp_gen_tree.get_children())
        pending_gens = getattr(self, "_pending_tp_generals", None)
        target_cid = getattr(self, "_pending_tp_city_id", None)
        apply_pending = (pending_gens is not None) and (target_cid is None or target_cid == base.id)
        for g in self.roster.generals_of(base.id):
            if g.role != "vo":
                continue
            army = self.roster.army_of(g.id)
            inf = army.infantry if army else 0
            cav = army.cavalry if army else 0
            arc = army.archers if army else 0
            total = army.total if army else 0
            sym = "☑" if (apply_pending and g.id in pending_gens) else "☐"
            self.tp_gen_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(sym, g.level, f"{g.stamina}/{g.stamina_max}", g.morale, inf, cav, arc, total),
            )

    def _on_tp_gen_toggle(self, event):
        item = self.tp_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.tp_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.tp_gen_tree.item(item, values=vals)
        self._schedule_auto_save()

    def _manual_adjust_tp_troops(self):
        """Bổ sung/biên chế quân lính thủ công ngay lập tức cho các tướng đã chọn."""
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        fetch_roster_fn = resolve_dashboard_symbol("fetch_roster", _default_fetch_roster)
        sel_idx = self.tp_city_combo.current()
        bases = self.roster.bases if (self.roster and self.roster.bases) else []
        if sel_idx < 0 or sel_idx >= len(bases):
            mb.showwarning("Cảnh báo", "Vui lòng chọn căn cứ!")
            return
        city_id = bases[sel_idx].id
        sel_gens = [int(iid) for iid in self.tp_gen_tree.get_children() if self.tp_gen_tree.item(iid, "values")[0] == "☑"]
        if not sel_gens:
            mb.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 võ tướng để biên chế!")
            return

        try:
            inf = int(self.tp_target_inf_var.get() or "0")
            cav = int(self.tp_target_cav_var.get() or "0")
            arc = int(self.tp_target_arc_var.get() or "0")
        except ValueError:
            mb.showerror("Lỗi", "Quân số biên chế phải là số nguyên!")
            return

        target_army = TargetArmy(infantry=inf, cavalry=cav, archers=arc)
        auto_recruit = bool(self.tp_auto_recruit_var.get())

        def _worker():
            self.after(0, self._append_tp_log, "⚔️ Bắt đầu tiến trình biên chế quân đội thủ công...")
            self.after(0, self._append_tp_log, f"   Mục tiêu: Bộ={inf}, Kỵ={cav}, Cung={arc} | Tự động chiêu mộ tân binh: {'Bật' if auto_recruit else 'Tắt'}")
            executor = getattr(self, "tp_executor", None) or ThaoPhatExecutor(self.gateway)
            try:
                if auto_recruit:
                    fresh_roster = fetch_roster_fn(self.gateway)
                    total_needed = 0
                    for gid in sel_gens:
                        cur_army = fresh_roster.army_of(gid)
                        cur_inf = cur_army.infantry if cur_army else 0
                        cur_cav = cur_army.cavalry if cur_army else 0
                        cur_arc = cur_army.archers if cur_army else 0
                        total_needed += max(0, target_army.infantry - cur_inf)
                        total_needed += max(0, target_army.cavalry - cur_cav)
                        total_needed += max(0, target_army.archers - cur_arc)
                    if total_needed > 0:
                        avail = executor.check_recruits(city_id)
                        if avail is not None and avail < total_needed:
                            missing = total_needed - avail
                            self.after(0, self._append_tp_log, f"📦 [Tân binh] Kho có {avail}/{total_needed}, tự động chiêu mộ thêm {missing} tân binh...")
                            b_succ, b_ret = executor.buy_recruits(city_id, missing)
                            if b_succ:
                                self.after(0, self._append_tp_log, f"   [Chiêu mộ] ✅ Đã chiêu mộ thành công {missing} tân binh!")
                            else:
                                err_desc = ERROR_MESSAGES.get(b_ret, f"Mã lỗi: {b_ret}")
                                self.after(0, self._append_tp_log, f"   [Chiêu mộ] ⚠️ Chiêu mộ thất bại ({err_desc})")

                fresh_roster = fetch_roster_fn(self.gateway)
                city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
                for gid in sel_gens:
                    g = city_gens.get(gid)
                    gname = g.name if g else str(gid)
                    cur_army = fresh_roster.army_of(gid)
                    results = executor.adjust_troops(
                        city_id,
                        gid,
                        cur_army,
                        target_army,
                        auto_recruit=auto_recruit,
                        on_log=lambda m: self.after(0, self._append_tp_log, m),
                    )
                    if results:
                        for stype, diff, succ, ret_code in results:
                            tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(stype, "Quân")
                            if succ:
                                self.after(0, self._append_tp_log, f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ✅ Thành công")
                            else:
                                err_desc = ERROR_MESSAGES.get(ret_code, f"Mã lỗi: {ret_code}")
                                self.after(0, self._append_tp_log, f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ❌ Thất bại ({err_desc})")
                    else:
                        self.after(0, self._append_tp_log, f"   [Biên chế] Tướng {gname}: Quân số đã đủ, không cần bổ sung.")

                self.after(0, self._append_tp_log, "🏁 Hoàn tất tiến trình biên chế quân đội!")
                new_roster = fetch_roster_fn(self.gateway)
                self.roster = new_roster
                self.after(0, self._on_tp_city_selected)
            except Exception as e:
                self.after(0, self._append_tp_log, f"❌ Lỗi ngoại lệ khi biên chế: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_tp(self):
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        if not self._tp_running:
            sel_idx = self.tp_city_combo.current()
            bases = self.roster.bases if (self.roster and self.roster.bases) else []
            if sel_idx < 0 or sel_idx >= len(bases):
                mb.showwarning("Cảnh báo", "Vui lòng chọn căn cứ!")
                return
            city_id = bases[sel_idx].id
            sel_gens = [int(iid) for iid in self.tp_gen_tree.get_children() if self.tp_gen_tree.item(iid, "values")[0] == "☑"]
            if not sel_gens:
                mb.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng!")
                return
            mission_idx = self.tp_mission_combo.current()
            task_id = list(THAOPHAT_MISSIONS.keys())[mission_idx]

            try:
                target_inf = int(self.tp_target_inf_var.get() or "0")
            except ValueError:
                target_inf = 5000

            try:
                target_cav = int(self.tp_target_cav_var.get() or "0")
            except ValueError:
                target_cav = 0

            try:
                target_arc = int(self.tp_target_arc_var.get() or "0")
            except ValueError:
                target_arc = 0

            try:
                min_morale = int(self.tp_min_morale_var.get() or "95")
            except ValueError:
                min_morale = 95

            try:
                tp_interval = max(3.0, float(self.tp_interval_var.get() or "10"))
            except ValueError:
                tp_interval = 10.0

            target_army = TargetArmy(infantry=target_inf, cavalry=target_cav, archers=target_arc)
            auto_recruit = bool(self.tp_auto_recruit_var.get()) if hasattr(self, "tp_auto_recruit_var") else True
            auto_morale = bool(self.tp_auto_morale_var.get()) if hasattr(self, "tp_auto_morale_var") else True

            self._tp_stop_event = threading.Event()
            self._tp_runner = ThaoPhatAutoRunner(
                gateway=self.gateway,
                city_id=city_id,
                task_id=task_id,
                general_ids=sel_gens,
                target_army=target_army,
                min_morale=min_morale,
                auto_recruit=auto_recruit,
                auto_morale=auto_morale,
                check_interval=tp_interval,
                stop_event=self._tp_stop_event,
                log_callback=lambda msg: self.after(0, self._append_tp_log, msg),
                status_callback=lambda st: None,
            )
            self._tp_runner.start()
            self._tp_running = True
            self.tp_start_btn.configure(text="⏹️ Dừng Thảo Phạt", style="Danger.TButton")
        else:
            if self._tp_stop_event:
                self._tp_stop_event.set()
            if self._tp_runner:
                self._tp_runner.stop()
            self._tp_running = False
            self.tp_start_btn.configure(text="▶️ Bắt đầu Thảo Phạt", style="Success.TButton")

    def _append_tp_log(self, msg: str):
        self._append_text_buffer(self.tp_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _tp_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Thảo Phạt."""
        if hasattr(self, "tp_log_text") and self.tp_log_text:
            self.tp_log_text.delete("1.0", "end")
