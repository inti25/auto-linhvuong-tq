"""Màn hình chính: Tổng quan thành/tướng và đầy đủ các Tab tự động hóa Linh Vương.

Tích hợp 6 Tab toàn diện:
- Tab 1: 🏰 Tổng quan & Quân đội (Roster, Thành trì, Tướng lĩnh, Biên chế lính).
- Tab 2: ⚔️ Thảo Phạt Tự Động (8 chiến dịch dã ngoại, 5 tướng, vi điều khiển Boss slot 19).
- Tab 3: 🧛 Gọi Dân & Vong Linh (Dân thường type=63 & Vong Linh type=33/bùa 268, tự hồi phục).
- Tab 4: 🏕️ Bình Man & Di Trại (Quét Man, dời Trại từng bước, đếm lùi frozen_time, Ngưỡng An Toàn).
- Tab 5: 🏗️ Xây Dựng Công Trình (Hàng Đợi Xây Dựng, Boost 20%, Speedup, An Dân, build_plans.json).
- Tab 6: 🔬 Đại Học & Hậu Cần (29 Kỹ Thuật Đại Học, Binh Pháp, Chuyển Quân, Nhận thưởng hằng ngày).
"""

import json
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional

from .gateway import GatewayClient
from .locks import TargetLocks
from .roster import Army, General, Roster, fetch_roster
from .scan import Scanner
from .tasks.base import CaptchaRequired, TaskContext
from .tasks.binh_man import BinhMan
from .tasks.building import BuildingPlan, BuildingTask
from .tasks.goi_dan import GoiDan, VONG_LINH
from .tasks.logistics import ArmyTransferOrder, LogisticsTask
from .tasks.research import ResearchTask, TECH_NAMES, TechPlan
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


# =============================================================================
# CÁC RUNNER CHẠY NGẦM ĐA LUỒNG (THREAD-SAFE BACKGROUND RUNNERS)
# =============================================================================

class BaseTaskRunner(threading.Thread):
    def __init__(self, task_name: str, log_cb: Callable[[str], None], status_cb: Callable[[str], None]):
        super().__init__(daemon=True)
        self.task_name = task_name
        self.log_cb = log_cb
        self.status_cb = status_cb
        self.stop_event = threading.Event()

    def log(self, msg: str):
        self.log_cb(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def stop(self):
        self.stop_event.set()
        self.log(f"⏹️ Đang dừng nhiệm vụ {self.task_name}...")
        self.status_cb("Đang dừng...")

    def wait(self, seconds: float) -> bool:
        return self.stop_event.wait(seconds)


class GoiDanAutoRunner(BaseTaskRunner):
    def __init__(self, task: GoiDan, interval: float, log_cb, status_cb):
        super().__init__("Gọi Dân", log_cb, status_cb)
        self.task = task
        self.interval = interval

    def run(self):
        self.status_cb("Đang chạy...")
        self.log(f"🚀 Bắt đầu nhiệm vụ Gọi Dân (chế độ: {self.task.mode})...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            try:
                res = self.task.run_once()
                self.log(f"Lượt {cycle}: Kết quả -> {res}")
            except CaptchaRequired:
                self.log("⚠️ Server yêu cầu Captcha! Dừng nhiệm vụ để giải thủ công.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Gọi Dân đã dừng.")


class BinhManAutoRunner(BaseTaskRunner):
    def __init__(self, task: BinhMan, interval: float, log_cb, status_cb):
        super().__init__("Bình Man", log_cb, status_cb)
        self.task = task
        self.interval = interval

    def run(self):
        self.status_cb("Đang chạy...")
        self.log("🚀 Bắt đầu nhiệm vụ Bình Man...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            try:
                res = self.task.run_once()
                self.log(f"Lượt {cycle}: Kết quả -> {res}")
            except CaptchaRequired:
                self.log("⚠️ Server yêu cầu Captcha! Dừng nhiệm vụ.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Bình Man đã dừng.")


class BuildingAutoRunner(BaseTaskRunner):
    def __init__(self, task: BuildingTask, interval: float, log_cb, status_cb):
        super().__init__("Xây Dựng", log_cb, status_cb)
        self.task = task
        self.interval = interval

    def run(self):
        self.status_cb("Đang chạy...")
        self.log("🚀 Bắt đầu giám sát & nâng cấp công trình...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            try:
                res = self.task.run_once()
                self.log(f"Chu kỳ {cycle}: Trạng thái -> {res}")
                if res == "all_buildings_completed":
                    self.log("🎉 Toàn bộ công trình quy hoạch đã hoàn tất!")
                    self.status_cb("Hoàn tất quy hoạch")
                    break
            except CaptchaRequired:
                self.log("⚠️ Server yêu cầu Captcha! Dừng nâng cấp.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Xây Dựng đã dừng.")


class ResearchAutoRunner(BaseTaskRunner):
    def __init__(self, task: ResearchTask, interval: float, log_cb, status_cb):
        super().__init__("Nghiên Cứu", log_cb, status_cb)
        self.task = task
        self.interval = interval

    def run(self):
        self.status_cb("Đang chạy...")
        self.log("🚀 Bắt đầu giám sát viện Đại Học & nghiên cứu kỹ thuật...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            try:
                res = self.task.run_once()
                self.log(f"Chu kỳ {cycle}: Trạng thái -> {res}")
                if res == "all_techs_completed":
                    self.log("🎉 Toàn bộ 29 kỹ thuật mục tiêu đã hoàn tất!")
                    self.status_cb("Hoàn tất 29 kỹ thuật")
                    break
            except CaptchaRequired:
                self.log("⚠️ Server yêu cầu Captcha! Dừng nghiên cứu.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Nghiên Cứu đã dừng.")


# =============================================================================
# CLASS CHÍNH: DASHBOARD ĐIỀU KHIỂN
# =============================================================================

class Dashboard(tk.Tk):
    def __init__(self, session, server_id: int):
        super().__init__()
        self.title(f"LinhVuong - Server {server_id}")
        self.configure(bg=BG)
        self.geometry("1100x700")
        self.minsize(1060, 650)
        self.gateway = GatewayClient(server_id, session)
        self.tp_executor = ThaoPhatExecutor(self.gateway)
        self.roster = Roster()
        self._results = queue.Queue()
        self._generals = {}

        # Trạng thái các luồng Task
        self._tp_running = False
        self._tp_runner = None
        self._gd_runner = None
        self._bm_runner = None
        self._bld_runner = None
        self._res_runner = None

        style = ttk.Style(self)
        style.theme_use("clam")

        # Tabs Notebook
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background="#222638",
            foreground=FG,
            padding=[14, 6],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "white")])

        # Treeviews
        style.configure(
            "Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=FG,
            rowheight=26,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#2a2e45",
            foreground=FG,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", ACCENT)])

        # Cards & inputs
        style.configure("Card.TLabelframe", background=BG, foreground=ACCENT)
        style.configure("Card.TLabelframe.Label", background=BG, foreground=ACCENT, font=("Segoe UI", 11, "bold"))
        style.configure("TLabel", background=CARD, foreground=FG, font=("Segoe UI", 10))
        style.configure("Dark.TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Big.TLabel", font=("Segoe UI", 14, "bold"), foreground=ACCENT)
        style.configure("TEntry", fieldbackground="#2a2e45", foreground=FG, insertcolor=FG)
        style.configure("TCombobox", fieldbackground="#2a2e45", foreground=FG)

        # Buttons
        style.configure("Action.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Action.TButton", background=[("active", "#8591ff")])
        style.configure("Success.TButton", background=SUCCESS, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Success.TButton", background=[("active", "#34c759")])
        style.configure("Danger.TButton", background=DANGER, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Danger.TButton", background=[("active", "#ff4d4f"), ("disabled", "#552222")])

        # Top Bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 6))
        self.status = tk.StringVar(value="Đang kết nối & tải dữ liệu...")
        tk.Label(top, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        self.refresh_btn = ttk.Button(top, text="🔄 Làm mới", style="Action.TButton", command=self.reload)
        self.refresh_btn.pack(side="right")

        # Notebook chứa 6 Tab
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Tab 1: Tổng quan & Quân đội
        t1 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t1, text="🏰 Tổng quan & Quân đội")
        self._build_overview_tab(t1)

        # Tab 2: Thảo Phạt Tự Động
        t2 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t2, text="⚔️ Thảo Phạt")
        self._build_thaophat_tab(t2)

        # Tab 3: Gọi Dân & Vong Linh
        t3 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t3, text="🧛 Gọi Dân & Vong Linh")
        self._build_goidan_tab(t3)

        # Tab 4: Bình Man & Di Trại
        t4 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t4, text="🏕️ Bình Man & Di Trại")
        self._build_binhman_tab(t4)

        # Tab 5: Xây Dựng Công Trình
        t5 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t5, text="🏗️ Xây Dựng")
        self._build_building_tab(t5)

        # Tab 6: Đại Học & Hậu Cần
        t6 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t6, text="🔬 Đại Học & Hậu Cần")
        self._build_research_and_logistics_tab(t6)

        self.reload()

    # =========================================================================
    # TAB 1: TỔNG QUAN
    # =========================================================================
    def _build_overview_tab(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=6)
        body.columnconfigure((0, 1, 2), weight=1, uniform="c")
        body.rowconfigure(0, weight=1)

        f1 = ttk.LabelFrame(body, text="Thành trì", style="Card.TLabelframe")
        f1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.city_tree = ttk.Treeview(f1, columns=("id",), show="tree headings", selectmode="browse")
        self.city_tree.heading("#0", text="Tên")
        self.city_tree.heading("id", text="ID")
        self.city_tree.column("#0", width=120)
        self.city_tree.column("id", width=70, anchor="e")
        self.city_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.city_tree.bind("<<TreeviewSelect>>", self._on_city)

        f2 = ttk.LabelFrame(body, text="Tướng trong thành", style="Card.TLabelframe")
        f2.grid(row=0, column=1, sticky="nsew", padx=6)
        self.gen_tree = ttk.Treeview(f2, columns=("role", "lv", "hp", "status"), show="tree headings", selectmode="browse")
        for col, text, w in (("#0", "Tên tướng", 100), ("role", "Loại", 70), ("lv", "Cấp", 35), ("hp", "Thể lực", 70), ("status", "Trạng thái", 90)):
            self.gen_tree.heading(col, text=text)
            self.gen_tree.column(col, width=w, anchor="center" if col in ("role", "lv", "status") else ("w" if col == "#0" else "e"))
        self.gen_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.gen_tree.bind("<<TreeviewSelect>>", self._on_general)

        f3 = ttk.LabelFrame(body, text="Chi tiết biên chế", style="Card.TLabelframe")
        f3.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        details = tk.Frame(f3, bg=CARD, padx=12, pady=12)
        details.pack(fill="both", expand=True, padx=6, pady=6)

        self.name_var = tk.StringVar(value="Chọn một tướng")
        self.info_var = tk.StringVar()
        self.total_var = tk.StringVar()
        ttk.Label(details, textvariable=self.name_var, style="Big.TLabel").pack(anchor="w", pady=(0, 2))
        ttk.Label(details, textvariable=self.info_var, foreground=MUTED).pack(anchor="w", pady=(0, 14))

        self.bars = {}
        for key, text, color in (("infantry", "Bộ binh", "#4da3ff"), ("cavalry", "Kỵ binh", "#ff9f43"), ("archers", "Cung binh", "#2ed573")):
            row = tk.Frame(details, bg=CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=text, bg=CARD, fg=FG, width=10, anchor="w", font=("Segoe UI", 10)).pack(side="left")
            val = tk.StringVar(value="-")
            bar = ttk.Progressbar(row, orient="horizontal", mode="determinate")
            bar.pack(side="left", fill="x", expand=True, padx=8)
            tk.Label(row, textvariable=val, bg=CARD, fg=FG, width=8, anchor="e", font=("Segoe UI", 10, "bold")).pack(side="right")
            self.bars[key] = (bar, val)

        ttk.Label(details, textvariable=self.total_var, font=("Segoe UI", 11, "bold"), foreground=ACCENT).pack(anchor="w", pady=(16, 0))

    # =========================================================================
    # TAB 2: THẢO PHẠT
    # =========================================================================
    def _build_thaophat_tab(self, parent):
        top_ctrl = tk.Frame(parent, bg=BG)
        top_ctrl.pack(fill="x", pady=6)

        tk.Label(top_ctrl, text="Thành trì:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.tp_city_combo = ttk.Combobox(top_ctrl, state="readonly", width=22)
        self.tp_city_combo.pack(side="left", padx=(0, 16))
        self.tp_city_combo.bind("<<ComboboxSelected>>", self._on_tp_city_selected)

        tk.Label(top_ctrl, text="Chiến dịch:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.tp_mission_combo = ttk.Combobox(top_ctrl, state="readonly", width=16)
        self.tp_mission_combo["values"] = [f"{m['name']} (ID: {mid})" for mid, m in THAOPHAT_MISSIONS.items()]
        self.tp_mission_combo.current(0)
        self.tp_mission_combo.pack(side="left", padx=(0, 16))

        tk.Label(top_ctrl, text="Quân số tối thiểu:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left", padx=(0, 6))
        self.tp_min_army_var = tk.StringVar(value="5000")
        ttk.Entry(top_ctrl, textvariable=self.tp_min_army_var, width=8).pack(side="left", padx=(0, 16))

        self.tp_start_btn = ttk.Button(top_ctrl, text="▶️ Bắt đầu Thảo Phạt", style="Success.TButton", command=self._toggle_tp)
        self.tp_start_btn.pack(side="left", padx=8)

        # Bảng tướng & Log
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=6)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        f_left = ttk.LabelFrame(body, text="Võ tướng xuất kích (Chọn tối đa 5)", style="Card.TLabelframe")
        f_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.tp_gen_tree = ttk.Treeview(f_left, columns=("select", "role", "lv", "stamina", "morale", "army"), show="tree headings", selectmode="browse")
        self.tp_gen_tree.heading("#0", text="Tên tướng")
        self.tp_gen_tree.heading("select", text="Chọn")
        self.tp_gen_tree.heading("role", text="Loại")
        self.tp_gen_tree.heading("lv", text="Cấp")
        self.tp_gen_tree.heading("stamina", text="Thể lực")
        self.tp_gen_tree.heading("morale", text="Sĩ khí")
        self.tp_gen_tree.heading("army", text="Quân số")
        self.tp_gen_tree.column("#0", width=100)
        self.tp_gen_tree.column("select", width=45, anchor="center")
        self.tp_gen_tree.column("role", width=55, anchor="center")
        self.tp_gen_tree.column("lv", width=40, anchor="center")
        self.tp_gen_tree.column("stamina", width=65, anchor="center")
        self.tp_gen_tree.column("morale", width=55, anchor="center")
        self.tp_gen_tree.column("army", width=70, anchor="e")
        self.tp_gen_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tp_gen_tree.bind("<ButtonRelease-1>", self._on_tp_gen_toggle)

        f_right = ttk.LabelFrame(body, text="Nhật ký chiến dịch Thảo Phạt", style="Card.TLabelframe")
        f_right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.tp_log_text = tk.Text(f_right, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.tp_log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _on_tp_city_selected(self, _event=None):
        sel_idx = self.tp_city_combo.current()
        if sel_idx < 0 or sel_idx >= len(self.roster.cities):
            return
        city = self.roster.cities[sel_idx]
        self.tp_gen_tree.delete(*self.tp_gen_tree.get_children())
        for g in self.roster.generals_of(city.id):
            if g.role != "vo":
                continue
            army = self.roster.army_of(g.id)
            army_count = army.total if army else 0
            self.tp_gen_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=("☐", "Võ tướng", g.level, f"{g.stamina}/{g.stamina_max}", g.morale, army_count),
            )

    def _on_tp_gen_toggle(self, event):
        item = self.tp_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.tp_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.tp_gen_tree.item(item, values=vals)

    def _toggle_tp(self):
        if not self._tp_running:
            sel_idx = self.tp_city_combo.current()
            if sel_idx < 0:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
                return
            city_id = self.roster.cities[sel_idx].id
            sel_gens = [int(iid) for iid in self.tp_gen_tree.get_children() if self.tp_gen_tree.item(iid, "values")[0] == "☑"]
            if not sel_gens:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng!")
                return
            mission_idx = self.tp_mission_combo.current()
            task_id = list(THAOPHAT_MISSIONS.keys())[mission_idx]

            self._tp_stop_event = threading.Event()
            self._tp_runner = ThaoPhatAutoRunner(
                self.gateway,
                self.tp_executor,
                city_id=city_id,
                task_id=task_id,
                general_ids=sel_gens,
                target_army=TargetArmy(bo_binh=5000),
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
            self._tp_running = False
            self.tp_start_btn.configure(text="▶️ Bắt đầu Thảo Phạt", style="Success.TButton")

    def _append_tp_log(self, msg: str):
        self.tp_log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.tp_log_text.see("end")

    # =========================================================================
    # TAB 3: GỌI DÂN & VONG LINH
    # =========================================================================
    def _build_goidan_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=6)

        tk.Label(top, text="Thành trì:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.gd_city_combo = ttk.Combobox(top, state="readonly", width=20)
        self.gd_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Chế độ:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.gd_mode_combo = ttk.Combobox(top, state="readonly", width=22)
        self.gd_mode_combo["values"] = ["Gọi Vong Linh (ID 301)", "Gọi Dân Thường"]
        self.gd_mode_combo.current(0)
        self.gd_mode_combo.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Bán kính quét:", bg=BG, fg=FG).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.gd_radius_var = tk.StringVar(value="5")
        ttk.Entry(top, textvariable=self.gd_radius_var, width=8).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        self.gd_recover_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            top,
            text="Tự động Trị thương & Bổ sung lính sau trận",
            variable=self.gd_recover_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            activeforeground=FG,
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=4, pady=4)

        # Điều khiển
        ctrl_frame = tk.Frame(top, bg=BG)
        ctrl_frame.grid(row=0, column=4, rowspan=2, padx=16)
        self.gd_start_btn = ttk.Button(ctrl_frame, text="▶️ Bắt đầu Gọi Dân", style="Success.TButton", command=self._toggle_goidan)
        self.gd_start_btn.pack(side="top", pady=2)
        self.gd_once_btn = ttk.Button(ctrl_frame, text="⚡ Chạy 1 Lượt", style="Action.TButton", command=self._run_goidan_once)
        self.gd_once_btn.pack(side="top", pady=2)

        # Log & Thông tin
        f_log = ttk.LabelFrame(parent, text="Nhật ký Gọi Dân & Vong Linh", style="Card.TLabelframe")
        f_log.pack(fill="both", expand=True, pady=6)
        self.gd_log_text = tk.Text(f_log, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.gd_log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _append_gd_log(self, msg: str):
        self.gd_log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.gd_log_text.see("end")

    def _create_goidan_task(self) -> Optional[GoiDan]:
        sel_idx = self.gd_city_combo.current()
        if sel_idx < 0:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
            return None
        city = self.roster.cities[sel_idx]
        gens = [g.id for g in self.roster.generals_of(city.id) if g.role == "vo"][:3]
        if not gens:
            messagebox.showwarning("Cảnh báo", "Thành này không có võ tướng khả dụng!")
            return None

        mode = "vong_linh" if "Vong Linh" in self.gd_mode_combo.get() else "dan"
        radius = int(self.gd_radius_var.get() or "5")
        locks = TargetLocks()
        scanner = Scanner(self.gateway, locks, delay=0.0, sleep=lambda s: None)
        ctx = TaskContext(self.gateway, scanner, locks, notify=lambda m: self.after(0, self._append_gd_log, m))

        return GoiDan(
            ctx=ctx,
            generals=gens,
            origin=(0, 0),
            radius=radius,
            mode=mode,
            city_id=city.id,
            auto_recover=self.gd_recover_var.get(),
            refill_amount=500,
        )

    def _run_goidan_once(self):
        task = self._create_goidan_task()
        if not task:
            return
        threading.Thread(target=lambda: self._append_gd_log(f"⚡ Kết quả chạy 1 lượt: {task.run_once()}"), daemon=True).start()

    def _toggle_goidan(self):
        if not self._gd_runner or not self._gd_runner.is_alive():
            task = self._create_goidan_task()
            if not task:
                return
            self._gd_runner = GoiDanAutoRunner(
                task,
                interval=10.0,
                log_cb=lambda m: self.after(0, self._append_gd_log, m),
                status_cb=lambda s: None,
            )
            self._gd_runner.start()
            self.gd_start_btn.configure(text="⏹️ Dừng Gọi Dân", style="Danger.TButton")
        else:
            self._gd_runner.stop()
            self.gd_start_btn.configure(text="▶️ Bắt đầu Gọi Dân", style="Success.TButton")

    # =========================================================================
    # TAB 4: BÌNH MAN & DI TRẠI
    # =========================================================================
    def _build_binhman_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=6)

        tk.Label(top, text="Thành xuất phát:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.bm_city_combo = ttk.Combobox(top, state="readonly", width=18)
        self.bm_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Thành mẹ (Hồi quân):", bg=BG, fg=FG, font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.bm_parent_city_combo = ttk.Combobox(top, state="readonly", width=18)
        self.bm_parent_city_combo.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Trại Di Chuyển ID:", bg=BG, fg=FG).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.bm_camp_id_var = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.bm_camp_id_var, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Ngưỡng An Toàn (%):", bg=BG, fg=FG).grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.bm_threshold_var = tk.StringVar(value="30")
        ttk.Entry(top, textvariable=self.bm_threshold_var, width=8).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Bán kính quét:", bg=BG, fg=FG).grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.bm_radius_var = tk.StringVar(value="10")
        ttk.Entry(top, textvariable=self.bm_radius_var, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Cấp Man (1..10):", bg=BG, fg=FG).grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.bm_mantypes_var = tk.StringVar(value="7,8,9,10")
        ttk.Entry(top, textvariable=self.bm_mantypes_var, width=18).grid(row=2, column=3, sticky="w", padx=4, pady=4)

        ctrl_frame = tk.Frame(top, bg=BG)
        ctrl_frame.grid(row=0, column=4, rowspan=3, padx=16)
        self.bm_start_btn = ttk.Button(ctrl_frame, text="▶️ Bắt đầu Bình Man", style="Success.TButton", command=self._toggle_binhman)
        self.bm_start_btn.pack(side="top", pady=2)
        self.bm_once_btn = ttk.Button(ctrl_frame, text="⚡ Chạy 1 Lượt", style="Action.TButton", command=self._run_binhman_once)
        self.bm_once_btn.pack(side="top", pady=2)

        f_log = ttk.LabelFrame(parent, text="Nhật ký Bình Man & Dời Trại", style="Card.TLabelframe")
        f_log.pack(fill="both", expand=True, pady=6)
        self.bm_log_text = tk.Text(f_log, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.bm_log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _append_bm_log(self, msg: str):
        self.bm_log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.bm_log_text.see("end")

    def _create_binhman_task(self) -> Optional[BinhMan]:
        sel_idx = self.bm_city_combo.current()
        if sel_idx < 0:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
            return None
        city = self.roster.cities[sel_idx]
        gens = [g.id for g in self.roster.generals_of(city.id) if g.role == "vo"][:3]
        if not gens:
            messagebox.showwarning("Cảnh báo", "Thành này không có võ tướng khả dụng!")
            return None

        parent_idx = self.bm_parent_city_combo.current()
        parent_id = self.roster.cities[parent_idx].id if parent_idx >= 0 else None
        camp_id = int(self.bm_camp_id_var.get()) if self.bm_camp_id_var.get().strip() else None
        radius = int(self.bm_radius_var.get() or "10")
        threshold = int(self.bm_threshold_var.get() or "30")
        man_types = [int(x.strip()) for x in self.bm_mantypes_var.get().split(",") if x.strip()]

        locks = TargetLocks()
        scanner = Scanner(self.gateway, locks, delay=0.0, sleep=lambda s: None)
        ctx = TaskContext(self.gateway, scanner, locks, notify=lambda m: self.after(0, self._append_bm_log, m))

        return BinhMan(
            ctx=ctx,
            generals=gens,
            origin=(0, 0),
            radius=radius,
            man_types=man_types,
            camp_id=camp_id,
            parent_city_id=parent_id,
            return_threshold=threshold,
            sleep_fn=lambda s: None,
        )

    def _run_binhman_once(self):
        task = self._create_binhman_task()
        if not task:
            return
        threading.Thread(target=lambda: self._append_bm_log(f"⚡ Kết quả chạy 1 lượt: {task.run_once()}"), daemon=True).start()

    def _toggle_binhman(self):
        if not self._bm_runner or not self._bm_runner.is_alive():
            task = self._create_binhman_task()
            if not task:
                return
            self._bm_runner = BinhManAutoRunner(
                task,
                interval=15.0,
                log_cb=lambda m: self.after(0, self._append_bm_log, m),
                status_cb=lambda s: None,
            )
            self._bm_runner.start()
            self.bm_start_btn.configure(text="⏹️ Dừng Bình Man", style="Danger.TButton")
        else:
            self._bm_runner.stop()
            self.bm_start_btn.configure(text="▶️ Bắt đầu Bình Man", style="Success.TButton")

    # =========================================================================
    # TAB 5: XÂY DỰNG CÔNG TRÌNH
    # =========================================================================
    def _build_building_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=6)

        tk.Label(top, text="Thành trì:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 6))
        self.bld_city_combo = ttk.Combobox(top, state="readonly", width=20)
        self.bld_city_combo.pack(side="left", padx=(0, 16))

        self.bld_speedup_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            top,
            text="⚡ Tự động Tăng tốc (Speedup)",
            variable=self.bld_speedup_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
        ).pack(side="left", padx=8)

        self.bld_boost_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            top,
            text="🚀 Tự kích hoạt Boost 20%",
            variable=self.bld_boost_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
        ).pack(side="left", padx=8)

        self.bld_comfort_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            top,
            text="🕊️ Tự động An Dân (sĩ khí < 90%)",
            variable=self.bld_comfort_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
        ).pack(side="left", padx=8)

        # Nút nạp / lưu quy hoạch
        btn_bar = tk.Frame(parent, bg=BG)
        btn_bar.pack(fill="x", pady=(2, 6))
        ttk.Button(btn_bar, text="📂 Nạp mẫu (build_plans.example.json)", style="Action.TButton", command=self._load_build_plans).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="💾 Lưu cấu hình", style="Action.TButton", command=self._save_build_plans).pack(side="left", padx=4)

        self.bld_start_btn = ttk.Button(btn_bar, text="▶️ Bắt đầu Nâng Cấp", style="Success.TButton", command=self._toggle_building)
        self.bld_start_btn.pack(side="right", padx=4)

        # Body: Treeview danh sách quy hoạch & Log
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        f_tree = ttk.LabelFrame(body, text="Hàng Đợi Quy Hoạch Công Trình", style="Card.TLabelframe")
        f_tree.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.bld_tree = ttk.Treeview(f_tree, columns=("pid", "gid", "target_lvl"), show="tree headings")
        self.bld_tree.heading("#0", text="Tên công trình")
        self.bld_tree.heading("pid", text="Ô đất (pid)")
        self.bld_tree.heading("gid", text="Loại (gid)")
        self.bld_tree.heading("target_lvl", text="Cấp mục tiêu")
        self.bld_tree.column("#0", width=120)
        self.bld_tree.column("pid", width=70, anchor="center")
        self.bld_tree.column("gid", width=70, anchor="center")
        self.bld_tree.column("target_lvl", width=80, anchor="center")
        self.bld_tree.pack(fill="both", expand=True, padx=6, pady=6)

        f_log = ttk.LabelFrame(body, text="Nhật ký Nâng Cấp Công Trình", style="Card.TLabelframe")
        f_log.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.bld_log_text = tk.Text(f_log, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.bld_log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _append_bld_log(self, msg: str):
        self.bld_log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.bld_log_text.see("end")

    def _load_build_plans(self):
        plan_path = Path("build_plans.example.json")
        if not plan_path.exists():
            messagebox.showerror("Lỗi", "Không tìm thấy file build_plans.example.json!")
            return
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        cities_data = data.get("cities", {})
        self.bld_tree.delete(*self.bld_tree.get_children())
        for cid, cinfo in cities_data.items():
            for p in cinfo.get("plans", []):
                self.bld_tree.insert(
                    "",
                    "end",
                    text=p.get("name", "Công trình"),
                    values=(p.get("pid"), p.get("gid"), p.get("target_level")),
                )
        self._append_bld_log("📂 Đã nạp danh sách quy hoạch công trình mẫu thành công.")

    def _save_build_plans(self):
        plans = []
        for iid in self.bld_tree.get_children():
            name = self.bld_tree.item(iid, "text")
            vals = self.bld_tree.item(iid, "values")
            plans.append({"pid": int(vals[0]), "gid": int(vals[1]), "target_level": int(vals[2]), "name": name})
        Path("build_plans.json").write_text(json.dumps({"plans": plans}, ensure_ascii=False, indent=2), encoding="utf-8")
        messagebox.showinfo("Thành công", "Đã lưu cấu hình ra build_plans.json!")

    def _toggle_building(self):
        if not self._bld_runner or not self._bld_runner.is_alive():
            sel_idx = self.bld_city_combo.current()
            if sel_idx < 0:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
                return
            city_id = self.roster.cities[sel_idx].id
            plans = []
            for iid in self.bld_tree.get_children():
                name = self.bld_tree.item(iid, "text")
                vals = self.bld_tree.item(iid, "values")
                plans.append(BuildingPlan(pid=int(vals[0]), gid=int(vals[1]), target_level=int(vals[2]), name=name))

            if not plans:
                messagebox.showwarning("Cảnh báo", "Chưa có công trình nào trong hàng đợi quy hoạch! Hãy bấm Nạp mẫu.")
                return

            task = BuildingTask(
                gateway=self.gateway,
                city_id=city_id,
                plans=plans,
                auto_speedup=self.bld_speedup_var.get(),
                auto_boost=self.bld_boost_var.get(),
                auto_comfort=self.bld_comfort_var.get(),
                notify=lambda m: self.after(0, self._append_bld_log, m),
            )
            self._bld_runner = BuildingAutoRunner(
                task,
                interval=20.0,
                log_cb=lambda m: self.after(0, self._append_bld_log, m),
                status_cb=lambda s: None,
            )
            self._bld_runner.start()
            self.bld_start_btn.configure(text="⏹️ Dừng Nâng Cấp", style="Danger.TButton")
        else:
            self._bld_runner.stop()
            self.bld_start_btn.configure(text="▶️ Bắt đầu Nâng Cấp", style="Success.TButton")

    # =========================================================================
    # TAB 6: ĐẠI HỌC & HẬU CẦN
    # =========================================================================
    def _build_research_and_logistics_tab(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=6)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Cột trái: Nghiên Cứu Viện Đại Học
        f_res = ttk.LabelFrame(body, text="Viện Đại Học (29 Kỹ Thuật)", style="Card.TLabelframe")
        f_res.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        res_ctrl = tk.Frame(f_res, bg=CARD, padx=8, pady=6)
        res_ctrl.pack(fill="x")
        tk.Label(res_ctrl, text="Thành:", bg=CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=4)
        self.res_city_combo = ttk.Combobox(res_ctrl, state="readonly", width=16)
        self.res_city_combo.pack(side="left", padx=4)

        self.res_art_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            res_ctrl,
            text="📜 Binh Pháp tăng tốc",
            variable=self.res_art_var,
            bg=CARD,
            fg=FG,
            selectcolor=BG,
            activebackground=CARD,
        ).pack(side="left", padx=6)

        ttk.Button(res_ctrl, text="📂 Nạp tech_plans", style="Action.TButton", command=self._load_tech_plans).pack(side="left", padx=4)
        self.res_start_btn = ttk.Button(res_ctrl, text="▶️ Bắt đầu", style="Success.TButton", command=self._toggle_research)
        self.res_start_btn.pack(side="right", padx=4)

        self.res_tree = ttk.Treeview(f_res, columns=("id", "target_lvl"), show="tree headings")
        self.res_tree.heading("#0", text="Tên Kỹ Thuật Đại Học")
        self.res_tree.heading("id", text="Mã (ID)")
        self.res_tree.heading("target_lvl", text="Cấp mục tiêu")
        self.res_tree.column("#0", width=140)
        self.res_tree.column("id", width=60, anchor="center")
        self.res_tree.column("target_lvl", width=80, anchor="center")
        self.res_tree.pack(fill="both", expand=True, padx=6, pady=6)

        # Cột phải: Hậu Cần & Điều Chuyển Binh Lực
        f_logis = ttk.LabelFrame(body, text="Hậu Cần & Chuyển Quân Liên Thành", style="Card.TLabelframe")
        f_logis.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        logis_form = tk.Frame(f_logis, bg=CARD, padx=12, pady=10)
        logis_form.pack(fill="x", padx=6, pady=6)

        tk.Label(logis_form, text="Từ Thành:", bg=CARD, fg=FG).grid(row=0, column=0, sticky="w", pady=4)
        self.log_from_city_combo = ttk.Combobox(logis_form, state="readonly", width=18)
        self.log_from_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        tk.Label(logis_form, text="Đến Thành:", bg=CARD, fg=FG).grid(row=0, column=2, sticky="w", pady=4)
        self.log_to_city_combo = ttk.Combobox(logis_form, state="readonly", width=18)
        self.log_to_city_combo.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        tk.Label(logis_form, text="Loại quân:", bg=CARD, fg=FG).grid(row=1, column=0, sticky="w", pady=4)
        self.log_army_combo = ttk.Combobox(logis_form, state="readonly", width=18)
        self.log_army_combo["values"] = ["1: Bộ binh", "2: Kỵ binh", "3: Cung binh"]
        self.log_army_combo.current(0)
        self.log_army_combo.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        tk.Label(logis_form, text="Số lượng:", bg=CARD, fg=FG).grid(row=1, column=2, sticky="w", pady=4)
        self.log_amount_var = tk.StringVar(value="1000")
        ttk.Entry(logis_form, textvariable=self.log_amount_var, width=12).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        # Nút điều chuyển & Tiện ích
        act_row = tk.Frame(logis_form, bg=CARD)
        act_row.grid(row=2, column=0, columnspan=4, pady=10, sticky="ew")
        ttk.Button(act_row, text="🚚 Chuyển Quân Ngay", style="Action.TButton", command=self._do_transfer_army).pack(side="left", padx=4)
        ttk.Button(act_row, text="🕊️ An Dân Ngay", style="Action.TButton", command=self._do_comfort_now).pack(side="left", padx=4)
        ttk.Button(act_row, text="🎁 Nhận Thưởng Điểm Danh", style="Success.TButton", command=self._do_claim_daily).pack(side="left", padx=4)

        # Log chung cho Tab 6
        f_log_tab6 = tk.Frame(f_logis, bg=CARD)
        f_log_tab6.pack(fill="both", expand=True, padx=6, pady=6)
        self.logis_log_text = tk.Text(f_log_tab6, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.logis_log_text.pack(fill="both", expand=True)

    def _append_logis_log(self, msg: str):
        self.logis_log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.logis_log_text.see("end")

    def _load_tech_plans(self):
        plan_path = Path("tech_plans.example.json")
        if not plan_path.exists():
            messagebox.showerror("Lỗi", "Không tìm thấy file tech_plans.example.json!")
            return
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        self.res_tree.delete(*self.res_tree.get_children())
        for p in data.get("plans", []):
            name = p.get("name") or TECH_NAMES.get(p.get("tech_id"), "Kỹ thuật")
            self.res_tree.insert("", "end", text=name, values=(p.get("tech_id"), p.get("target_level")))
        self._append_logis_log("📂 Đã nạp danh sách 29 Kỹ Thuật Đại Học mẫu thành công.")

    def _toggle_research(self):
        if not self._res_runner or not self._res_runner.is_alive():
            sel_idx = self.res_city_combo.current()
            if sel_idx < 0:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì nghiên cứu!")
                return
            city_id = self.roster.cities[sel_idx].id
            plans = []
            for iid in self.res_tree.get_children():
                name = self.res_tree.item(iid, "text")
                vals = self.res_tree.item(iid, "values")
                plans.append(TechPlan(tech_id=int(vals[0]), target_level=int(vals[1]), name=name))

            if not plans:
                messagebox.showwarning("Cảnh báo", "Chưa có kỹ thuật nào trong danh sách! Hãy bấm Nạp tech_plans.")
                return

            task = ResearchTask(
                gateway=self.gateway,
                city_id=city_id,
                plans=plans,
                auto_art_of_war=self.res_art_var.get(),
                notify=lambda m: self.after(0, self._append_logis_log, m),
            )
            self._res_runner = ResearchAutoRunner(
                task,
                interval=30.0,
                log_cb=lambda m: self.after(0, self._append_logis_log, m),
                status_cb=lambda s: None,
            )
            self._res_runner.start()
            self.res_start_btn.configure(text="⏹️ Dừng", style="Danger.TButton")
        else:
            self._res_runner.stop()
            self.res_start_btn.configure(text="▶️ Bắt đầu", style="Success.TButton")

    def _do_transfer_army(self):
        f_idx = self.log_from_city_combo.current()
        t_idx = self.log_to_city_combo.current()
        if f_idx < 0 or t_idx < 0:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn đầy đủ Thành gửi và Thành nhận!")
            return
        from_id = self.roster.cities[f_idx].id
        to_id = self.roster.cities[t_idx].id
        army_id = self.log_army_combo.current() + 1
        amount = int(self.log_amount_var.get() or "1000")

        task = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_logis_log, m))
        order = ArmyTransferOrder(from_city_id=from_id, to_city_id=to_id, army_id=army_id, amount=amount)
        threading.Thread(target=lambda: task.transfer_army(order), daemon=True).start()

    def _do_comfort_now(self):
        f_idx = self.log_from_city_combo.current()
        if f_idx < 0:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành cần An Dân!")
            return
        city_id = self.roster.cities[f_idx].id
        task = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_logis_log, m))
        threading.Thread(target=lambda: task.comfort_city_if_needed(city_id), daemon=True).start()

    def _do_claim_daily(self):
        task = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_logis_log, m))
        threading.Thread(target=lambda: task.claim_daily_reward(), daemon=True).start()

    # =========================================================================
    # CẬP NHẬT DỮ LIỆU CHUNG
    # =========================================================================
    def reload(self):
        self.refresh_btn.state(["disabled"])
        self.status.set("Đang cập nhật danh sách thành trì & tướng...")
        threading.Thread(target=self._fetch_roster_thread, daemon=True).start()

    def _fetch_roster_thread(self):
        try:
            roster = fetch_roster(self.gateway)
            self.after(0, self._loaded, roster)
        except Exception as e:
            self.after(0, self._load_failed, str(e))

    def _load_failed(self, msg):
        self.status.set(f"Lỗi tải dữ liệu: {msg}")
        self.refresh_btn.state(["!disabled"])

    def _loaded(self, roster: Roster):
        self.roster = roster
        # Tab 1
        self.city_tree.delete(*self.city_tree.get_children())
        for city in roster.cities:
            self.city_tree.insert("", "end", iid=str(city.id), text=city.name, values=(city.id,))
        self.status.set(f"Đã tải {len(roster.cities)} thành trì thành công")
        self.refresh_btn.state(["!disabled"])
        if roster.cities:
            self.city_tree.selection_set(str(roster.cities[0].id))

        # Cập nhật Combobox thành trì cho tất cả các Tab
        city_items = [f"{c.name} (ID: {c.id})" for c in roster.cities]
        for combo in (
            self.tp_city_combo,
            self.gd_city_combo,
            self.bm_city_combo,
            self.bm_parent_city_combo,
            self.bld_city_combo,
            self.res_city_combo,
            self.log_from_city_combo,
            self.log_to_city_combo,
        ):
            combo["values"] = city_items
            if city_items and not combo.get():
                combo.current(0)

        if city_items:
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
            self.gen_tree.insert(
                "",
                "end",
                iid=iid,
                text=g.name,
                values=(ROLE_TEXT.get(g.role, g.role), g.level, f"{g.stamina}/{g.stamina_max}", g.status_text),
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
