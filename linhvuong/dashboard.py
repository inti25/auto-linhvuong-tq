"""Màn hình chính: Tổng quan thành/tướng và Tab Thảo Phạt tự động."""

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from .gateway import GatewayClient
from .roster import Army, Roster, fetch_roster
from .tasks.thao_phat import (
    ERROR_MESSAGES,
    THAOPHAT_MISSIONS,
    TargetArmy,
    ThaoPhatAutoRunner,
    ThaoPhatExecutor,
)

BG, CARD, FG, MUTED, ACCENT, SUCCESS, DANGER = (
    "#14161f",
    "#1e2130",
    "#e8eaf2",
    "#8a90b0",
    "#6c7bff",
    "#28a745",
    "#dc3545",
)
ROLE_TEXT = {"van": "Văn tướng", "vo": "Võ tướng"}


class Dashboard(tk.Tk):
    def __init__(self, session, server_id: int):
        super().__init__()
        self.title(f"LinhVuong - Server {server_id}")
        self.configure(bg=BG)
        self.geometry("1060x650")
        self.gateway = GatewayClient(server_id, session)
        self.tp_executor = ThaoPhatExecutor(self.gateway)
        self.roster = Roster()
        self._results = queue.Queue()
        self._generals = {}  # iid -> General
        self._tp_running = False
        self._tp_stop_event = None
        self._tp_runner = None

        style = ttk.Style(self)
        style.theme_use("clam")

        # Configure tabs
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#222638", foreground=FG, padding=[16, 6],
                        font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "white")])

        # Configure Treeviews
        style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=FG,
                        rowheight=26, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#2a2e45", foreground=FG,
                        font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)])

        # Cards & inputs
        style.configure("Card.TLabelframe", background=BG, foreground=ACCENT)
        style.configure("Card.TLabelframe.Label", background=BG, foreground=ACCENT,
                        font=("Segoe UI", 11, "bold"))
        style.configure("TLabel", background=CARD, foreground=FG, font=("Segoe UI", 10))
        style.configure("Dark.TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Big.TLabel", font=("Segoe UI", 14, "bold"), foreground=ACCENT)
        style.configure("TEntry", fieldbackground="#2a2e45", foreground=FG, insertcolor=FG)
        style.configure("TCombobox", fieldbackground="#2a2e45", foreground=FG)

        # Buttons
        style.configure("Action.TButton", background=ACCENT, foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Action.TButton", background=[("active", "#8591ff")])
        style.configure("Success.TButton", background=SUCCESS, foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Success.TButton", background=[("active", "#34c759")])
        style.configure("Danger.TButton", background=DANGER, foreground="white",
                        font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Danger.TButton", background=[("active", "#ff4d4f"), ("disabled", "#552222")])

        # Top bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 6))
        self.status = tk.StringVar(value="Đang tải dữ liệu...")
        tk.Label(top, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        self.refresh_btn = ttk.Button(top, text="🔄 Làm mới", style="Action.TButton", command=self.reload)
        self.refresh_btn.pack(side="right")

        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Tab 1: Tổng quan
        tab_overview = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab_overview, text="🏰 Tổng quan & Quân đội")
        self._build_overview_tab(tab_overview)

        # Tab 2: Thảo Phạt
        tab_thaophat = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab_thaophat, text="⚔️ Thảo Phạt Tự Động")
        self._build_thaophat_tab(tab_thaophat)

        self.reload()

    # =========================================================================
    # TAB 1: TỔNG QUAN
    # =========================================================================
    def _build_overview_tab(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=6)
        body.columnconfigure((0, 1, 2), weight=1, uniform="c")
        body.rowconfigure(0, weight=1)

        # Cột 1: thành trì
        f1 = ttk.LabelFrame(body, text="Thành trì", style="Card.TLabelframe")
        f1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.city_tree = ttk.Treeview(f1, columns=("id",), show="tree headings", selectmode="browse")
        self.city_tree.heading("#0", text="Tên")
        self.city_tree.heading("id", text="ID")
        self.city_tree.column("#0", width=120)
        self.city_tree.column("id", width=70, anchor="e")
        self.city_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.city_tree.bind("<<TreeviewSelect>>", self._on_city)

        # Cột 2: tướng
        f2 = ttk.LabelFrame(body, text="Tướng trong thành", style="Card.TLabelframe")
        f2.grid(row=0, column=1, sticky="nsew", padx=6)
        self.gen_tree = ttk.Treeview(f2, columns=("role", "lv", "hp", "status"), show="tree headings", selectmode="browse")
        for col, text, w in (("#0", "Tên tướng", 100), ("role", "Loại", 70),
                             ("lv", "Cấp", 35), ("hp", "Thể lực", 70), ("status", "Trạng thái", 90)):
            self.gen_tree.heading(col, text=text)
            self.gen_tree.column(col, width=w, anchor="center" if col in ("role", "lv", "status") else ("w" if col == "#0" else "e"))
        self.gen_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.gen_tree.bind("<<TreeviewSelect>>", self._on_general)

        # Cột 3: chi tiết biên chế
        f3 = ttk.LabelFrame(body, text="Chi tiết biên chế", style="Card.TLabelframe")
        f3.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        detail = tk.Frame(f3, bg=CARD)
        detail.pack(fill="both", expand=True, padx=6, pady=6)
        self.name_var = tk.StringVar(value="Chọn một tướng")
        ttk.Label(detail, textvariable=self.name_var, style="Big.TLabel").pack(anchor="w", padx=12, pady=(12, 4))
        self.info_var = tk.StringVar()
        ttk.Label(detail, textvariable=self.info_var).pack(anchor="w", padx=12)
        self.army_frame = tk.Frame(detail, bg=CARD)
        self.army_frame.pack(fill="x", padx=12, pady=14)
        self.bars = {}
        for key, label in (("infantry", "Bộ binh"), ("cavalry", "Kỵ binh"), ("archers", "Cung binh")):
            row = tk.Frame(self.army_frame, bg=CARD)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, width=10).pack(side="left")
            bar = ttk.Progressbar(row, maximum=1, length=120)
            bar.pack(side="left", padx=6)
            val = tk.StringVar(value="-")
            ttk.Label(row, textvariable=val, width=6).pack(side="left")
            self.bars[key] = (bar, val)
        self.total_var = tk.StringVar()
        ttk.Label(detail, textvariable=self.total_var, style="Big.TLabel").pack(anchor="w", padx=12)

    # =========================================================================
    # TAB 2: THẢO PHẠT
    # =========================================================================
    def _build_thaophat_tab(self, parent):
        paned = tk.PanedWindow(parent, orient="horizontal", bg=BG, sashwidth=6)
        paned.pack(fill="both", expand=True, pady=6)

        # Khung trái: Thiết lập cấu hình & chọn tướng (chiếm 580px)
        left = tk.Frame(paned, bg=BG)
        paned.add(left, minsize=520)

        # 1. Chọn Thành & Nhiệm vụ
        cfg_box = ttk.LabelFrame(left, text="1. Chọn Cứ Điểm & Nhiệm Vụ", style="Card.TLabelframe")
        cfg_box.pack(fill="x", padx=6, pady=(0, 6))
        c_inner = tk.Frame(cfg_box, bg=CARD, padx=10, pady=8)
        c_inner.pack(fill="x")

        ttk.Label(c_inner, text="Thành:").grid(row=0, column=0, sticky="w", pady=4)
        self.tp_city_combo = ttk.Combobox(c_inner, state="readonly", width=18)
        self.tp_city_combo.grid(row=0, column=1, sticky="w", padx=6, pady=4)
        self.tp_city_combo.bind("<<ComboboxSelected>>", self._on_tp_city_selected)

        ttk.Label(c_inner, text="Nhiệm vụ:").grid(row=0, column=2, sticky="w", padx=(12, 0), pady=4)
        self.tp_mission_combo = ttk.Combobox(c_inner, state="readonly", width=22)
        mission_items = [f"{mid} - {info['name']} (Tối đa {info['max_generals']} tướng)"
                         for mid, info in THAOPHAT_MISSIONS.items()]
        self.tp_mission_combo["values"] = mission_items
        if mission_items:
            self.tp_mission_combo.current(0)
        self.tp_mission_combo.grid(row=0, column=3, sticky="w", padx=6, pady=4)

        # 2. Danh sách tướng trong thành
        gen_box = ttk.LabelFrame(left, text="2. Chọn Tướng Xuất Kích", style="Card.TLabelframe")
        gen_box.pack(fill="both", expand=True, padx=6, pady=6)
        self.tp_gen_tree = ttk.Treeview(
            gen_box,
            columns=("id", "role", "lv", "status", "morale", "troops"),
            show="tree headings",
            selectmode="extended",
            height=6,
        )
        self.tp_gen_tree.heading("#0", text="Tên")
        self.tp_gen_tree.heading("id", text="ID")
        self.tp_gen_tree.heading("role", text="Loại")
        self.tp_gen_tree.heading("lv", text="Cấp")
        self.tp_gen_tree.heading("status", text="Trạng thái")
        self.tp_gen_tree.heading("morale", text="Sĩ Khí")
        self.tp_gen_tree.heading("troops", text="Hiện có (B/K/C)")

        self.tp_gen_tree.column("#0", width=100)
        self.tp_gen_tree.column("id", width=55, anchor="e")
        self.tp_gen_tree.column("role", width=60, anchor="center")
        self.tp_gen_tree.column("lv", width=35, anchor="center")
        self.tp_gen_tree.column("status", width=95, anchor="center")
        self.tp_gen_tree.column("morale", width=55, anchor="center")
        self.tp_gen_tree.column("troops", width=110, anchor="center")
        self.tp_gen_tree.pack(fill="both", expand=True, padx=6, pady=6)

        # 3. Cấu hình quân số mục tiêu & Sĩ khí
        army_box = ttk.LabelFrame(left, text="3. Cấu Hình Biên Chế & Sĩ Khí Tối Thiểu", style="Card.TLabelframe")
        army_box.pack(fill="x", padx=6, pady=6)
        a_inner = tk.Frame(army_box, bg=CARD, padx=10, pady=8)
        a_inner.pack(fill="x")

        self.tp_bo_var = tk.StringVar(value="0")
        self.tp_ky_var = tk.StringVar(value="15000")
        self.tp_cung_var = tk.StringVar(value="0")
        self.tp_morale_var = tk.StringVar(value="51")
        self.tp_auto_recruit_var = tk.BooleanVar(value=True)

        ttk.Label(a_inner, text="Bộ binh:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(a_inner, textvariable=self.tp_bo_var, width=10).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(a_inner, text="Kỵ binh:").grid(row=0, column=2, sticky="w", padx=(10, 0), pady=4)
        ttk.Entry(a_inner, textvariable=self.tp_ky_var, width=10).grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(a_inner, text="Cung binh:").grid(row=0, column=4, sticky="w", padx=(10, 0), pady=4)
        ttk.Entry(a_inner, textvariable=self.tp_cung_var, width=10).grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(a_inner, text="Sĩ khí tối thiểu:").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 4))
        ttk.Entry(a_inner, textvariable=self.tp_morale_var, width=10).grid(row=1, column=2, sticky="w", padx=6, pady=(8, 4))

        self.tp_auto_counter_var = tk.BooleanVar(value=True)
        self.tp_leave_boss_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(
            a_inner,
            text="Tự động đổi trận hình khắc chế",
            variable=self.tp_auto_counter_var,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 2))

        ttk.Checkbutton(
            a_inner,
            text="Chừa BOSS lại cuối cùng (bắt sống)",
            variable=self.tp_leave_boss_var,
        ).grid(row=2, column=3, columnspan=3, sticky="w", padx=(12, 0), pady=(6, 2))

        # 4. Nút hành động
        btn_bar = tk.Frame(left, bg=BG)
        btn_bar.pack(fill="x", padx=6, pady=8)

        self.btn_tp_prepare = ttk.Button(btn_bar, text="⚙️ Chuẩn Bị (1 lần)",
                                         style="Action.TButton", command=self._on_tp_prepare_only)
        self.btn_tp_prepare.pack(side="left", padx=(0, 6))

        self.btn_tp_toggle = ttk.Button(btn_bar, text="⚔️ BẮT ĐẦU TỰ ĐỘNG THẢO PHẠT",
                                        style="Success.TButton", command=self._on_tp_toggle)
        self.btn_tp_toggle.pack(side="left", padx=6)

        # Khung phải: Bảng điều khiển tiến trình & Log trực tiếp (chiếm phần còn lại)
        right = tk.Frame(paned, bg=BG)
        paned.add(right, minsize=400)

        log_box = ttk.LabelFrame(right, text="Trạng Thái & Log Thực Thi", style="Card.TLabelframe")
        log_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.tp_log_text = tk.Text(log_box, bg="#10121a", fg="#a0f0a0", insertbackground="white",
                                   font=("Consolas", 9), wrap="word", borderwidth=0)
        self.tp_log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def tp_log(self, text: str):
        self.tp_log_text.insert("end", text + "\n")
        self.tp_log_text.see("end")

    def _on_tp_city_selected(self, _event=None):
        cid = self._get_selected_tp_city_id()
        if not cid:
            return
        self.tp_gen_tree.delete(*self.tp_gen_tree.get_children())
        seen = set()
        for g in self.roster.generals_of(cid):
            iid = str(g.id)
            if iid in seen:
                continue
            seen.add(iid)
            army = self.roster.army_of(g.id)
            troop_str = f"{army.infantry}/{army.cavalry}/{army.archers}" if army else "Chưa biên chế"
            self.tp_gen_tree.insert(
                "",
                "end",
                iid=iid,
                text=g.name,
                values=(g.id, ROLE_TEXT.get(g.role, g.role), g.level, g.status_text, g.morale, troop_str),
            )

    def _get_selected_tp_city_id(self) -> Optional[int]:
        txt = self.tp_city_combo.get()
        if not txt:
            return None
        try:
            return int(txt.split(" (ID: ")[1].rstrip(")"))
        except Exception:
            return None

    def _get_selected_mission_id(self) -> int:
        txt = self.tp_mission_combo.get()
        try:
            return int(txt.split(" - ")[0])
        except Exception:
            return 0

    def _on_tp_prepare_only(self):
        city_id = self._get_selected_tp_city_id()
        if not city_id:
            messagebox.showwarning("Chú ý", "Vui lòng chọn thành trì!")
            return

        selected_items = self.tp_gen_tree.selection()
        if not selected_items:
            messagebox.showwarning("Chú ý", "Vui lòng chọn ít nhất một tướng trong danh sách!")
            return

        try:
            target_army = TargetArmy(
                infantry=int(self.tp_bo_var.get().strip() or "0"),
                cavalry=int(self.tp_ky_var.get().strip() or "0"),
                archers=int(self.tp_cung_var.get().strip() or "0"),
            )
            min_morale = int(self.tp_morale_var.get().strip() or "51")
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượng quân hoặc sỹ khí phải là số nguyên!")
            return

        task_id = self._get_selected_mission_id()
        gen_ids = [int(i) for i in selected_items]
        self.btn_tp_prepare.state(["disabled"])
        self.btn_tp_toggle.state(["disabled"])
        self.tp_log("--- Bắt đầu Chuẩn Bị Tướng & Quân Đội (1 lần) ---")
        self.tp_log(f"Mục tiêu quân: Bộ={target_army.infantry}, Kỵ={target_army.cavalry}, Cung={target_army.archers}")
        self.tp_log(f"Sĩ khí tối thiểu: {min_morale}")

        threading.Thread(
            target=self._tp_prepare_worker,
            args=(city_id, task_id, gen_ids, target_army, min_morale),
            daemon=True,
        ).start()

    def _tp_prepare_worker(self, city_id, task_id, gen_ids, target_army, min_morale):
        try:
            mission = THAOPHAT_MISSIONS.get(task_id, {})
            travel_time = mission.get("travel_time", 300)
            mission_name = mission.get("name", "Thảo Phạt")

            fresh_roster = fetch_roster(self.gateway)
            self._results.put(("ok", fresh_roster))
            city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}

            troops_modified = False
            for gid in gen_ids:
                g = city_gens.get(gid)
                gname = g.name if g else str(gid)
                current_army = fresh_roster.army_of(gid)

                self.after(0, self.tp_log, f"👉 Kiểm tra tướng {gname} (ID: {gid})...")
                if g and g.status != 0:
                    self.after(0, self.tp_log, f"   ⚠️ Tướng {gname} đang bận: {g.status_text} (status={g.status})!")
                    continue

                adj_results = self.tp_executor.adjust_troops(
                    city_id,
                    gid,
                    current_army,
                    target_army,
                    auto_recruit=self.tp_auto_recruit_var.get(),
                    on_log=lambda msg: self.after(0, self.tp_log, msg),
                )
                if adj_results:
                    for stype, diff, succ, ret_code in adj_results:
                        tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(stype, "Quân")
                        if succ:
                            if diff > 0:
                                troops_modified = True
                            self.after(0, self.tp_log, f"   [Biên chế] Bổ sung {tname} +{diff}: ✅ Thành công")
                        else:
                            err_desc = ERROR_MESSAGES.get(ret_code, f"Mã lỗi: {ret_code}")
                            self.after(0, self.tp_log, f"   [Biên chế] Bổ sung {tname} +{diff}: ❌ Thất bại ({err_desc})")
                else:
                    self.after(0, self.tp_log, "   [Biên chế] Quân số đã đủ, không cần bổ sung.")

            # Nếu có biên chế quân -> tải lại roster để cập nhật sĩ khí thực tế sau khi pha loãng tân binh
            if troops_modified:
                self.after(0, self.tp_log, "📦 Đã bổ sung tân binh. Đang cập nhật lại sỹ khí thực tế sau biên chế...")
                fresh_roster = fetch_roster(self.gateway)
                self._results.put(("ok", fresh_roster))
                city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}

            # Kiểm tra & nâng sĩ khí
            for gid in gen_ids:
                g = city_gens.get(gid)
                gname = g.name if g else str(gid)
                cur_morale = g.morale if g else 0
                up_t = g.upgrading_time if g else 0

                if cur_morale < min_morale:
                    projected = min(100, cur_morale + 10)
                    is_final = (projected >= min_morale)
                    if up_t > 0:
                        if not is_final:
                            self.after(0, self.tp_log, f"   [Sĩ khí] Đang nâng sĩ khí (còn {up_t}s, đạt {projected} < {min_morale} -> cần nâng tiếp đợt sau) ⏳")
                        elif up_t <= travel_time:
                            self.after(0, self.tp_log, f"   [Sĩ khí] Đang nâng sĩ khí (còn {up_t}s <= {travel_time}s hành quân của '{mission_name}', đạt {projected} >= {min_morale} -> Kịp hoàn tất trên đường đi) ✅")
                        else:
                            excess = up_t - travel_time
                            self.after(0, self.tp_log, f"   [Sĩ khí] Đang nâng sĩ khí (còn {up_t}s > {travel_time}s hành quân, đạt {projected} >= {min_morale}, cần đợi thêm {excess}s)...")
                        continue

                    if is_final:
                        self.after(0, self.tp_log, f"   [Sĩ khí] Tướng {gname}: Sĩ khí {cur_morale} < {min_morale} (nâng lần này đạt {projected} >= {min_morale}), bắt đầu nâng...")
                    else:
                        self.after(0, self.tp_log, f"   [Sĩ khí] Tướng {gname}: Sĩ khí {cur_morale} < {min_morale} (nâng lần này đạt {projected} < {min_morale}, cần nâng tiếp đợt sau), bắt đầu nâng...")

                    m_succ, m_ret = self.tp_executor.adjust_morale(city_id, gid, cur_morale, min_morale)
                    if m_succ:
                        self.after(0, self.tp_log, "   [Sĩ khí] ✅ Bắt đầu nâng thành công!")
                    else:
                        err_desc = ERROR_MESSAGES.get(m_ret, f"Mã lỗi: {m_ret}")
                        self.after(0, self.tp_log, f"   [Sĩ khí] ❌ Nâng thất bại ({err_desc})")
                else:
                    self.after(0, self.tp_log, f"   [Sĩ khí] Tướng {gname}: Sĩ khí đã đạt {cur_morale} >= {min_morale}.")

            # Chờ đếm ngược nâng sĩ khí:
            # - Nếu nâng chưa đủ min_morale (projected < min_morale): chờ hết 100% để nâng tiếp
            # - Khi lần nâng đảm bảo đủ min_morale: chỉ cần chờ cho đến khi up_t <= travel_time
            while True:
                fresh_roster = fetch_roster(self.gateway)
                city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
                all_done = True
                wait_needed = []

                for gid in gen_ids:
                    g = city_gens.get(gid)
                    if not g:
                        continue
                    cur_m = g.morale
                    up_t = g.upgrading_time
                    if cur_m >= min_morale:
                        continue
                    projected = min(100, cur_m + 10)
                    is_final = (projected >= min_morale)

                    if up_t == 0:
                        all_done = False
                        self.after(0, self.tp_log, f"   [Sĩ khí] Tướng {g.name}: Nâng tiếp từ {cur_m} lên {projected}...")
                        self.tp_executor.adjust_morale(city_id, gid, cur_m, min_morale)
                        wait_needed.append((g.name, 5.0, "vừa bắt đầu nâng"))
                    else:
                        if not is_final:
                            all_done = False
                            wait_needed.append((g.name, float(up_t), f"còn {up_t}s (chờ đạt {projected} để nâng tiếp lượt sau)"))
                        elif up_t > travel_time:
                            excess = up_t - travel_time
                            all_done = False
                            wait_needed.append((g.name, float(excess), f"còn {up_t}s > hành quân {travel_time}s (cần giảm thêm {excess}s)"))
                        else:
                            pass

                if all_done:
                    break

                desc = "; ".join(f"{name}: {reason}" for name, _, reason in wait_needed)
                self.after(0, self.tp_log, f"⏳ [Sĩ khí] Đang chờ đếm ngược nâng sĩ khí: {desc}...")
                import time
                time.sleep(min(max(w for _, w, _ in wait_needed), 5.0))

            # Kiểm tra lại lần cuối
            fresh_roster = fetch_roster(self.gateway)
            self._results.put(("ok", fresh_roster))
            city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
            self.after(0, self.tp_log, "🔍 [Kiểm tra lại] Kết quả sau chuẩn bị:")
            for gid in gen_ids:
                g = city_gens.get(gid)
                gname = g.name if g else str(gid)
                cur_morale = g.morale if g else 0
                up_t = g.upgrading_time if g else 0
                projected = min(100, cur_morale + 10)
                army = fresh_roster.army_of(gid)
                cur_inf = army.infantry if army else 0
                cur_cav = army.cavalry if army else 0
                cur_arc = army.archers if army else 0

                if cur_morale >= min_morale:
                    morale_str = f"Sĩ khí {cur_morale}/{min_morale} (Đã đủ ✅)"
                elif up_t > 0:
                    if projected < min_morale:
                        morale_str = f"Sĩ khí {cur_morale} (+10={projected} < {min_morale}, cần nâng tiếp ⚠️)"
                    elif up_t <= travel_time:
                        morale_str = f"Sĩ khí {cur_morale} (+10={projected} >= {min_morale}) (còn {up_t}s <= {travel_time}s -> Sẵn sàng xuất phát ✅)"
                    else:
                        morale_str = f"Sĩ khí {cur_morale} (+10={projected} >= {min_morale}) (còn {up_t}s > {travel_time}s ⏳)"
                else:
                    morale_str = f"Sĩ khí {cur_morale}/{min_morale} (Chưa đủ ⚠️)"

                self.after(0, self.tp_log, f"   👉 Tướng {gname}: {morale_str} | Quân: Bộ {cur_inf}, Kỵ {cur_cav}, Cung {cur_arc}")

            self.after(0, self.tp_log, "🏁 Hoàn tất chuẩn bị tướng & quân đội!")
        except Exception as e:
            self.after(0, self.tp_log, f"❌ Lỗi ngoại lệ: {e}")
        finally:
            self.after(0, self._tp_prepare_done)

    def _tp_prepare_done(self):
        self.btn_tp_prepare.state(["!disabled"])
        self.btn_tp_toggle.state(["!disabled"])
        self.reload()

    def _on_tp_toggle(self):
        if self._tp_running:
            self._on_tp_stop()
        else:
            self._on_tp_start_auto()

    def _on_tp_stop(self):
        if self._tp_stop_event:
            self.tp_log("\n⏹️ Đang gửi tín hiệu dừng quy trình Thảo Phạt tự động... Vui lòng đợi hoàn tất kiểm tra hiện tại.")
            self._tp_stop_event.set()
            self.btn_tp_toggle.configure(text="⏳ Đang dừng...")
            self.btn_tp_toggle.state(["disabled"])

    def _on_tp_start_auto(self):
        city_id = self._get_selected_tp_city_id()
        if not city_id:
            messagebox.showwarning("Chú ý", "Vui lòng chọn thành trì!")
            return

        selected_items = self.tp_gen_tree.selection()
        if not selected_items:
            messagebox.showwarning("Chú ý", "Vui lòng chọn ít nhất một tướng trong danh sách!")
            return

        task_id = self._get_selected_mission_id()
        mission = THAOPHAT_MISSIONS.get(task_id, {})
        max_gens = mission.get("max_generals", 5)

        if len(selected_items) > max_gens:
            messagebox.showwarning(
                "Cảnh báo",
                f"Nhiệm vụ {mission.get('name')} chỉ hỗ trợ tối đa {max_gens} tướng!\n"
                f"Bạn đang chọn {len(selected_items)} tướng. Sẽ chỉ lấy {max_gens} tướng đầu tiên.",
            )
            selected_items = selected_items[:max_gens]

        try:
            target_army = TargetArmy(
                infantry=int(self.tp_bo_var.get().strip() or "0"),
                cavalry=int(self.tp_ky_var.get().strip() or "0"),
                archers=int(self.tp_cung_var.get().strip() or "0"),
            )
            min_morale = int(self.tp_morale_var.get().strip() or "51")
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượng quân hoặc sỹ khí phải là số nguyên!")
            return

        gen_ids = [int(i) for i in selected_items]

        self._tp_running = True
        self._tp_stop_event = threading.Event()

        # Cập nhật giao diện khi đang chạy
        self.btn_tp_toggle.configure(text="⏹️ DỪNG THẢO PHẠT", style="Danger.TButton")
        self.btn_tp_prepare.state(["disabled"])
        self.tp_city_combo.state(["disabled"])
        self.tp_mission_combo.state(["disabled"])

        threading.Thread(
            target=self._tp_auto_worker,
            args=(city_id, task_id, gen_ids, target_army, min_morale),
            daemon=True,
        ).start()

    def _tp_auto_worker(self, city_id, task_id, gen_ids, target_army, min_morale):
        try:
            runner = ThaoPhatAutoRunner(
                gateway=self.gateway,
                city_id=city_id,
                task_id=task_id,
                general_ids=gen_ids,
                target_army=target_army,
                min_morale=min_morale,
                auto_recruit=self.tp_auto_recruit_var.get(),
                auto_counter=self.tp_auto_counter_var.get(),
                leave_boss_last=self.tp_leave_boss_var.get(),
                stop_event=self._tp_stop_event,
                log_fn=lambda msg: self.after(0, self.tp_log, msg),
                check_interval=10.0,
            )
            self._tp_runner = runner
            runner.run()
        except Exception as e:
            self.after(0, self.tp_log, f"❌ Lỗi ngoại lệ trong Thảo Phạt tự động: {e}")
        finally:
            self.after(0, self._tp_auto_done)

    def _tp_auto_done(self):
        self._tp_running = False
        self._tp_runner = None
        self._tp_stop_event = None
        self.btn_tp_toggle.configure(text="⚔️ BẮT ĐẦU TỰ ĐỘNG THẢO PHẠT", style="Success.TButton")
        self.btn_tp_toggle.state(["!disabled"])
        self.btn_tp_prepare.state(["!disabled"])
        self.tp_city_combo.state(["!disabled", "readonly"])
        self.tp_mission_combo.state(["!disabled", "readonly"])
        self.reload()

    # =========================================================================
    # CẬP NHẬT DỮ LIỆU
    # =========================================================================
    def reload(self):
        self.refresh_btn.state(["disabled"])
        self.status.set("Đang tải dữ liệu...")
        threading.Thread(target=self._load, daemon=True).start()
        self.after(100, self._poll)

    def _load(self):
        try:
            self._results.put(("ok", fetch_roster(self.gateway)))
        except Exception as e:
            self._results.put(("error", str(e)))

    def _poll(self):
        try:
            kind, payload = self._results.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return
        if kind == "ok":
            self._loaded(payload)
        else:
            self._load_failed(payload)

    def _load_failed(self, msg):
        self.status.set(f"Lỗi tải dữ liệu: {msg}")
        self.refresh_btn.state(["!disabled"])

    def _loaded(self, roster: Roster):
        self.roster = roster
        # Tab 1
        self.city_tree.delete(*self.city_tree.get_children())
        for city in roster.cities:
            self.city_tree.insert("", "end", iid=str(city.id), text=city.name, values=(city.id,))
        self.status.set(f"{len(roster.cities)} thành trì")
        self.refresh_btn.state(["!disabled"])
        if roster.cities:
            self.city_tree.selection_set(str(roster.cities[0].id))

        # Tab 2 Combobox
        city_items = [f"{c.name} (ID: {c.id})" for c in roster.cities]
        self.tp_city_combo["values"] = city_items
        if city_items and not self.tp_city_combo.get():
            self.tp_city_combo.current(0)
            self._on_tp_city_selected()

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
            self.gen_tree.insert("", "end", iid=iid, text=g.name,
                                 values=(ROLE_TEXT.get(g.role, g.role), g.level, f"{g.stamina}/{g.stamina_max}", g.status_text))

    def _on_general(self, _event=None):
        sel = self.gen_tree.selection()
        self._show_general(self._generals.get(sel[0]) if sel else None)

    def _show_general(self, g):
        if g is None:
            self.name_var.set("Chọn một tướng")
            self.info_var.set("")
            self.total_var.set("")
            for bar, val in self.bars.values():
                bar.configure(value=0)
                val.set("-")
            return
        self.name_var.set(g.name)
        self.info_var.set(f"{ROLE_TEXT.get(g.role, g.role)}  •  Cấp {g.level}  •  Sĩ khí {g.morale}")
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
