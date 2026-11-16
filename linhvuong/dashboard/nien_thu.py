"""Tab Sự Kiện Niên Thú trên giao diện Dashboard."""

import time
import tkinter as tk
from tkinter import messagebox, ttk

from ..scan import Scanner
from ..tasks.base import TaskContext
from ..tasks.nien_thu import NienThuTask
from ..tasks.thao_phat import TargetArmy
from ..world_chat import NienThuAnnouncement, STATE_VI_NAMES
from .shared import ACCENT, BG, CARD, FG, resolve_dashboard_symbol


class NienThuMixin:
    """Xây dựng giao diện, hồ sơ và điều khiển sự kiện Niên Thú."""

    def _build_nien_thu_tab(self, parent):
        top_ctrl = tk.Frame(parent, bg=BG)
        top_ctrl.pack(fill="x", pady=6)

        row1 = tk.Frame(top_ctrl, bg=BG)
        row1.pack(fill="x", pady=(0, 4))

        tk.Label(row1, text="Thành/Trại:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
        self.nt_city_combo = ttk.Combobox(row1, state="readonly", width=16)
        self.nt_city_combo.pack(side="left", padx=(0, 10))
        self.nt_city_combo.bind("<<ComboboxSelected>>", self._on_nt_city_selected)

        tk.Label(row1, text="Bộ:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.nt_target_inf_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.nt_target_inf_var, width=6).pack(side="left", padx=(0, 6))

        tk.Label(row1, text="Kỵ:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.nt_target_cav_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.nt_target_cav_var, width=6).pack(side="left", padx=(0, 6))

        tk.Label(row1, text="Cung:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.nt_target_arc_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.nt_target_arc_var, width=6).pack(side="left", padx=(0, 10))

        self.nt_start_btn = ttk.Button(
            row1, text="▶️ Bắt đầu Niên Thú", style="Success.TButton", command=self._toggle_nien_thu
        )
        self.nt_start_btn.pack(side="left", padx=4)

        self.nt_status_var = tk.StringVar(value="Chưa chạy")
        tk.Label(row1, textvariable=self.nt_status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(
            side="left", padx=(8, 0)
        )

        row2 = tk.Frame(top_ctrl, bg=BG)
        row2.pack(fill="x", pady=(2, 0))

        self.nt_auto_recruit_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Tự động chiêu mộ & biên chế quân", variable=self.nt_auto_recruit_var).pack(
            side="left", padx=(0, 12)
        )

        self.nt_auto_morale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Tự động nâng sĩ khí", variable=self.nt_auto_morale_var).pack(
            side="left", padx=(0, 6)
        )

        tk.Label(row2, text="Sĩ khí:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.nt_min_morale_var = tk.StringVar(value="95")
        ttk.Entry(row2, textvariable=self.nt_min_morale_var, width=4).pack(side="left", padx=(0, 12))

        row3 = tk.Frame(top_ctrl, bg=BG)
        row3.pack(fill="x", pady=(2, 0))

        self.nt_speedup_march_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="Tốc hành quân đi (速行军)", variable=self.nt_speedup_march_var).pack(
            side="left", padx=(0, 12)
        )

        self.nt_speedup_return_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="Tốc hành quân về (速行军)", variable=self.nt_speedup_return_var).pack(
            side="left", padx=(0, 12)
        )

        self.nt_stop_jade_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row3, text="Dừng khi có 玉兔呈祥", variable=self.nt_stop_jade_var).pack(
            side="left", padx=(0, 12)
        )

        self.nt_use_world_chat_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="Theo dõi kênh Thế Giới", variable=self.nt_use_world_chat_var).pack(
            side="left", padx=(0, 12)
        )

        self.nt_run_immediately_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="Chạy ngay giờ hiện tại", variable=self.nt_run_immediately_var).pack(
            side="left", padx=(0, 8)
        )

        row4 = tk.Frame(top_ctrl, bg=BG)
        row4.pack(fill="x", pady=(2, 0))
        self.nt_ann_var = tk.StringVar(value="Kênh thế giới: Chưa có thông báo Niên Thú")
        tk.Label(row4, textvariable=self.nt_ann_var, bg=BG, fg="#9ecbff", font=("Segoe UI", 9, "italic")).pack(
            side="left"
        )

        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        f_top = ttk.LabelFrame(body, text="Võ tướng luân phiên đánh Niên Thú", style="Card.TLabelframe")
        f_top.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        self.nt_gen_tree = ttk.Treeview(
            f_top,
            columns=("select", "lv", "stamina", "morale", "infantry", "cavalry", "archers", "total_army"),
            show="tree headings",
            selectmode="browse",
        )
        self.nt_gen_tree.heading("#0", text="Tên võ tướng")
        self.nt_gen_tree.heading("select", text="Chọn")
        self.nt_gen_tree.heading("lv", text="Cấp")
        self.nt_gen_tree.heading("stamina", text="Thể lực")
        self.nt_gen_tree.heading("morale", text="Sĩ khí")
        self.nt_gen_tree.heading("infantry", text="Bộ binh")
        self.nt_gen_tree.heading("cavalry", text="Kỵ binh")
        self.nt_gen_tree.heading("archers", text="Cung binh")
        self.nt_gen_tree.heading("total_army", text="Tổng quân")

        self.nt_gen_tree.column("#0", width=140)
        self.nt_gen_tree.column("select", width=50, anchor="center")
        self.nt_gen_tree.column("lv", width=45, anchor="center")
        self.nt_gen_tree.column("stamina", width=70, anchor="center")
        self.nt_gen_tree.column("morale", width=60, anchor="center")
        self.nt_gen_tree.column("infantry", width=80, anchor="e")
        self.nt_gen_tree.column("cavalry", width=80, anchor="e")
        self.nt_gen_tree.column("archers", width=80, anchor="e")
        self.nt_gen_tree.column("total_army", width=85, anchor="e")

        gen_scroll = ttk.Scrollbar(f_top, orient="vertical", command=self.nt_gen_tree.yview)
        self.nt_gen_tree.configure(yscrollcommand=gen_scroll.set)
        self.nt_gen_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        gen_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        self.nt_gen_tree.bind("<ButtonRelease-1>", self._on_nt_gen_toggle)

        f_bottom = ttk.LabelFrame(body, text="Nhật ký Đánh Niên Thú", style="Card.TLabelframe")
        f_bottom.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        log_bar = tk.Frame(f_bottom, bg=CARD)
        log_bar.pack(side="top", fill="x", padx=4, pady=(2, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._nt_clear_log).pack(side="right")

        log_scroll = ttk.Scrollbar(f_bottom, orient="vertical")
        self.nt_log_text = tk.Text(
            f_bottom, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0, yscrollcommand=log_scroll.set
        )
        log_scroll.config(command=self.nt_log_text.yview)
        self.nt_log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        log_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))

    def _on_nt_city_selected(self, _event=None):
        if not hasattr(self, "nt_city_combo") or not hasattr(self, "nt_gen_tree"):
            return
        sel_idx = self.nt_city_combo.current()
        bases = self.roster.bases if (self.roster and self.roster.bases) else []
        if sel_idx < 0 or sel_idx >= len(bases):
            return
        base = bases[sel_idx]
        self.nt_gen_tree.delete(*self.nt_gen_tree.get_children())
        pending_gens = getattr(self, "_pending_nt_generals", None)
        target_cid = getattr(self, "_pending_nt_city_id", None)
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
            self.nt_gen_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(sym, g.level, f"{g.stamina}/{g.stamina_max}", g.morale, inf, cav, arc, total),
            )

    def _on_nt_gen_toggle(self, event):
        item = self.nt_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.nt_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.nt_gen_tree.item(item, values=vals)
        self._schedule_auto_save()

    def _collect_nien_thu_profile_dict(self) -> dict:
        nt_city_id = 0
        if hasattr(self, "nt_city_combo") and self.roster and self.roster.bases:
            sel_idx = self.nt_city_combo.current()
            if 0 <= sel_idx < len(self.roster.bases):
                nt_city_id = self.roster.bases[sel_idx].id
        elif getattr(self, "_pending_nt_city_id", None) is not None:
            nt_city_id = int(self._pending_nt_city_id)

        nt_gens: list[int] = []
        if hasattr(self, "nt_gen_tree") and self.nt_gen_tree.get_children():
            nt_gens = [
                int(iid)
                for iid in self.nt_gen_tree.get_children()
                if self.nt_gen_tree.item(iid, "values")[0] == "☑"
            ]
        elif getattr(self, "_pending_nt_generals", None):
            nt_gens = sorted(self._pending_nt_generals)

        return {
            "city_id": nt_city_id,
            "generals": nt_gens,
            "target_infantry": self.nt_target_inf_var.get() if hasattr(self, "nt_target_inf_var") else "0",
            "target_cavalry": self.nt_target_cav_var.get() if hasattr(self, "nt_target_cav_var") else "0",
            "target_archers": self.nt_target_arc_var.get() if hasattr(self, "nt_target_arc_var") else "0",
            "auto_recruit": bool(self.nt_auto_recruit_var.get()) if hasattr(self, "nt_auto_recruit_var") else False,
            "auto_morale": bool(self.nt_auto_morale_var.get()) if hasattr(self, "nt_auto_morale_var") else False,
            "min_morale": self.nt_min_morale_var.get() if hasattr(self, "nt_min_morale_var") else "95",
            "speed_up_march": bool(self.nt_speedup_march_var.get()) if hasattr(self, "nt_speedup_march_var") else False,
            "speed_up_return": bool(self.nt_speedup_return_var.get()) if hasattr(self, "nt_speedup_return_var") else False,
            "stop_on_jade": bool(self.nt_stop_jade_var.get()) if hasattr(self, "nt_stop_jade_var") else False,
            "use_world_chat": bool(self.nt_use_world_chat_var.get()) if hasattr(self, "nt_use_world_chat_var") else True,
            "run_immediately": bool(self.nt_run_immediately_var.get()) if hasattr(self, "nt_run_immediately_var") else True,
            "enabled": bool(self.engine.is_running("nien_thu")) if hasattr(self, "engine") else False,
        }

    def _apply_nien_thu_profile_dict(self, nt_data: dict) -> None:
        if hasattr(self, "nt_target_inf_var") and "target_infantry" in nt_data:
            self.nt_target_inf_var.set(str(nt_data["target_infantry"]))
        if hasattr(self, "nt_target_cav_var") and "target_cavalry" in nt_data:
            self.nt_target_cav_var.set(str(nt_data["target_cavalry"]))
        if hasattr(self, "nt_target_arc_var") and "target_archers" in nt_data:
            self.nt_target_arc_var.set(str(nt_data["target_archers"]))
        if hasattr(self, "nt_auto_recruit_var") and "auto_recruit" in nt_data:
            self.nt_auto_recruit_var.set(bool(nt_data["auto_recruit"]))
        if hasattr(self, "nt_auto_morale_var") and "auto_morale" in nt_data:
            self.nt_auto_morale_var.set(bool(nt_data["auto_morale"]))
        if hasattr(self, "nt_min_morale_var") and "min_morale" in nt_data:
            self.nt_min_morale_var.set(str(nt_data["min_morale"]))
        if hasattr(self, "nt_speedup_march_var") and "speed_up_march" in nt_data:
            self.nt_speedup_march_var.set(bool(nt_data["speed_up_march"]))
        if hasattr(self, "nt_speedup_return_var") and "speed_up_return" in nt_data:
            self.nt_speedup_return_var.set(bool(nt_data["speed_up_return"]))
        if hasattr(self, "nt_stop_jade_var") and "stop_on_jade" in nt_data:
            self.nt_stop_jade_var.set(bool(nt_data["stop_on_jade"]))
        if hasattr(self, "nt_use_world_chat_var") and "use_world_chat" in nt_data:
            self.nt_use_world_chat_var.set(bool(nt_data["use_world_chat"]))
        if hasattr(self, "nt_run_immediately_var") and "run_immediately" in nt_data:
            self.nt_run_immediately_var.set(bool(nt_data["run_immediately"]))

        if "city_id" in nt_data and nt_data["city_id"]:
            try:
                self._pending_nt_city_id = int(nt_data["city_id"])
                if hasattr(self, "nt_city_combo") and self.roster and self.roster.bases:
                    for idx, b in enumerate(self.roster.bases):
                        if b.id == self._pending_nt_city_id:
                            self.nt_city_combo.current(idx)
                            self._on_nt_city_selected()
                            break
            except (TypeError, ValueError):
                pass

        if "generals" in nt_data and isinstance(nt_data["generals"], list):
            self._pending_nt_generals = {int(x) for x in nt_data["generals"] if str(x).isdigit()}
            if hasattr(self, "nt_gen_tree") and self.nt_gen_tree.get_children():
                for iid in self.nt_gen_tree.get_children():
                    vals = list(self.nt_gen_tree.item(iid, "values"))
                    vals[0] = "☑" if int(iid) in self._pending_nt_generals else "☐"
                    self.nt_gen_tree.item(iid, values=vals)

    def _toggle_nien_thu(self):
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        if self.engine.is_running("nien_thu"):
            self.engine.stop("nien_thu")
            self.nt_start_btn.configure(text="▶️ Bắt đầu Niên Thú", style="Success.TButton")
            if hasattr(self, "nt_status_var"):
                self.nt_status_var.set("Đã dừng")
            return

        bases = self.roster.bases if (self.roster and self.roster.bases) else []
        sel_idx = self.nt_city_combo.current() if hasattr(self, "nt_city_combo") else -1
        if sel_idx < 0 or sel_idx >= len(bases):
            mb.showwarning("Cảnh báo", "Vui lòng chọn Thành/Trại xuất quân!")
            return
        city_id = bases[sel_idx].id
        sel_gens = [
            int(iid)
            for iid in self.nt_gen_tree.get_children()
            if self.nt_gen_tree.item(iid, "values")[0] == "☑"
        ]
        if not sel_gens:
            mb.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 võ tướng!")
            return

        def _parse_int(var: tk.StringVar, default: int) -> int:
            try:
                return int(var.get() or str(default))
            except (TypeError, ValueError):
                return default

        target_army = TargetArmy(
            infantry=max(0, _parse_int(self.nt_target_inf_var, 0)),
            cavalry=max(0, _parse_int(self.nt_target_cav_var, 0)),
            archers=max(0, _parse_int(self.nt_target_arc_var, 0)),
        )
        min_morale = max(0, min(100, _parse_int(self.nt_min_morale_var, 95)))
        ctx = TaskContext(
            gateway=self.gateway,
            scanner=Scanner(self.gateway, self.shared_target_locks),
            locks=self.shared_target_locks,
            notify=lambda m: self.after(0, self._append_nt_log, m),
        )
        task = NienThuTask(
            ctx=ctx,
            general_ids=sel_gens,
            city_id=city_id,
            target_army=target_army,
            auto_recruit=bool(self.nt_auto_recruit_var.get()),
            auto_morale=bool(self.nt_auto_morale_var.get()),
            min_morale=min_morale,
            speed_up_march=bool(self.nt_speedup_march_var.get()),
            speed_up_return=bool(self.nt_speedup_return_var.get()),
            stop_on_jade=bool(self.nt_stop_jade_var.get()),
            use_world_chat=bool(self.nt_use_world_chat_var.get()),
            run_immediately=bool(self.nt_run_immediately_var.get()),
            on_announcement=lambda ann: self.after(0, self._on_nt_announcement, ann),
        )
        self.engine.start("nien_thu", task, interval=5.0, jitter=1.0)
        self.nt_start_btn.configure(text="⏹️ Dừng Niên Thú", style="Danger.TButton")
        if hasattr(self, "nt_status_var"):
            self.nt_status_var.set("Đang chạy")

    def _on_nt_announcement(self, ann: NienThuAnnouncement):
        if hasattr(self, "nt_ann_var"):
            vi_name = STATE_VI_NAMES.get(ann.state_id, ann.state_name)
            self.nt_ann_var.set(f"Kênh thế giới: {vi_name} ({ann.state_name}) - {ann.server_time or '?'}")

    def _append_nt_log(self, msg: str):
        if not hasattr(self, "nt_log_text"):
            return
        ts = time.strftime("%H:%M:%S")
        self.nt_log_text.insert("end", f"[{ts}] {msg}\n")
        self.nt_log_text.see("end")

    def _nt_clear_log(self):
        if hasattr(self, "nt_log_text"):
            self.nt_log_text.delete("1.0", "end")
