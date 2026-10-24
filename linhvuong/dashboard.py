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
import logging
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional, Union

from .auth import login
from .gateway import GatewayClient
from .locks import TargetLocks
from .logger import open_logs_directory, setup_logger

logger = logging.getLogger("linhvuong.dashboard")
from .roster import Army, City, General, Roster, fetch_roster
from .scan import Scanner
from .tasks.base import CaptchaRequired, TaskContext
from .tasks.binh_man import BinhMan
from .tasks.di_trai import DiTrai
from .tasks.building import BUILDING_NAMES, BuildingPlan, BuildingTask
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
ROLE_TEXT = {"van": "Văn quan", "vo": "Võ tướng"}


# =============================================================================
# CÁC RUNNER CHẠY NGẦM ĐA LUỒNG (THREAD-SAFE BACKGROUND RUNNERS)
# =============================================================================

class BaseTaskRunner(threading.Thread):
    def __init__(self, task_name: str, log_cb: Callable[[str], None], status_cb: Callable[[str], None]):
        super().__init__(daemon=True)
        self.task_name = task_name
        self.logger = logging.getLogger(f"linhvuong.tasks.{task_name}")
        self.log_cb = log_cb
        self.status_cb = status_cb
        self.stop_event = threading.Event()

    def log(self, msg: str):
        self.logger.info(msg)
        self.log_cb(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def stop(self):
        self.stop_event.set()
        self.log(f"⏹️ Đang dừng nhiệm vụ {self.task_name}...")
        self.status_cb("Đang dừng...")

    def wait(self, seconds: float) -> bool:
        return self.stop_event.wait(seconds)

    def wait_cycle(self, seconds: float, jitter: float = 2.0) -> bool:
        """Chờ một chu kỳ lặp với cơ chế giãn cách ngẫu nhiên nhẹ (Jitter) chống phát hiện bot.

        Nếu seconds <= 3.0, giữ nguyên (tối thiểu 1.0s).
        Nếu seconds > 3.0, thêm ngẫu nhiên trong khoảng [-jitter, +jitter], đảm bảo tối thiểu 3.0s.
        Trả về True nếu stop_event được kích hoạt.
        """
        if seconds <= 3.0:
            actual_wait = max(1.0, seconds)
        else:
            import random
            actual_wait = max(3.0, seconds + random.uniform(-jitter, jitter))
        return self.stop_event.wait(actual_wait)


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
                self.logger.warning("Server yêu cầu Captcha! Dừng nhiệm vụ Gọi Dân.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nhiệm vụ để giải thủ công.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Gọi Dân: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait_cycle(self.interval):
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
                self.logger.warning("Server yêu cầu Captcha! Dừng nhiệm vụ Bình Man.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nhiệm vụ.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Bình Man: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait_cycle(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Bình Man đã dừng.")


class BuildingAutoRunner(BaseTaskRunner):
    def __init__(
        self,
        task_or_tasks: Union[BuildingTask, list[BuildingTask]],
        interval: float,
        log_cb,
        status_cb,
        sync_cb: Optional[Callable[[int, dict], None]] = None,
    ):
        super().__init__("Xây Dựng", log_cb, status_cb)
        if isinstance(task_or_tasks, list):
            self.tasks: list[BuildingTask] = task_or_tasks
        else:
            self.tasks: list[BuildingTask] = [task_or_tasks]
        self.interval = interval
        self.sync_cb = sync_cb
        if sync_cb:
            for t in self.tasks:
                if not getattr(t, "on_sync_data", None):
                    t.on_sync_data = sync_cb

    @property
    def task(self) -> Optional[BuildingTask]:
        return self.tasks[0] if self.tasks else None

    @task.setter
    def task(self, val: BuildingTask):
        self.tasks = [val]

    def run(self):
        self.status_cb("Đang chạy...")
        num_bases = len(self.tasks)
        self.log(f"🚀 Bắt đầu giám sát & nâng cấp công trình cho {num_bases} căn cứ...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            all_completed = True
            try:
                for t in self.tasks:
                    if self.stop_event.is_set():
                        break
                    res = t.run_once()
                    if res != "all_buildings_completed":
                        all_completed = False
                
                if all_completed and self.tasks:
                    self.log("🎉 Toàn bộ công trình quy hoạch của tất cả các căn cứ đã hoàn tất!")
                    self.status_cb("Hoàn tất quy hoạch")
                    break
            except CaptchaRequired:
                self.logger.warning("Server yêu cầu Captcha! Dừng nâng cấp Xây Dựng.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nâng cấp.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Xây Dựng: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait_cycle(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Xây Dựng đã dừng.")


class ResearchAutoRunner(BaseTaskRunner):
    def __init__(
        self,
        task: ResearchTask,
        interval: float,
        log_cb,
        status_cb,
        sync_cb: Optional[Callable[[int, dict, Optional[tuple]], None]] = None,
    ):
        super().__init__("Nghiên Cứu", log_cb, status_cb)
        self.task = task
        self.interval = interval
        self.sync_cb = sync_cb
        if sync_cb and not getattr(self.task, "on_sync_data", None):
            self.task.on_sync_data = sync_cb

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
                self.logger.warning("Server yêu cầu Captcha! Dừng nghiên cứu Viện Đại Học.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nghiên cứu.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Nghiên Cứu: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait_cycle(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Nghiên Cứu đã dừng.")


# =============================================================================
# CLASS CHÍNH: DASHBOARD ĐIỀU KHIỂN
# =============================================================================

class Dashboard(tk.Tk):
    def __init__(
        self,
        session,
        server_id: int,
        username: str = "",
        password: str = "",
        proxy_raw: str = "",
        proxy_user: str = "",
        proxy_pass: str = "",
    ):
        super().__init__()
        self.session = session
        self.server_id = server_id
        self.username = username
        self._password = password
        self._proxy_raw = proxy_raw
        self._proxy_user = proxy_user
        self._proxy_pass = proxy_pass
        try:
            setup_logger(username=username or "guest", server_id=server_id)
        except Exception:
            pass
        if username:
            self.title(f"LinhVuong - S{server_id} - [{username}]")
            self.default_profile_name = f"auto_profile_{username}_{server_id}.json"
        else:
            self.title(f"LinhVuong - Server {server_id}")
            self.default_profile_name = "auto_profile.json"
        self.configure(bg=BG)
        self.geometry("1100x700")
        self.minsize(1060, 650)

        relogin_cb = None
        if self.username and self._password:
            def auto_relogin() -> bool:
                try:
                    logger.info(
                        f"Đang tự động đăng nhập lại tài khoản {self.username} (Server {self.server_id})..."
                    )
                    login(
                        self.session,
                        self.server_id,
                        self.username,
                        self._password,
                        proxy=self._proxy_raw or None,
                        proxy_user=self._proxy_user or None,
                        proxy_pass=self._proxy_pass or None,
                    )
                    return True
                except Exception as ex:
                    logger.error(f"Tự động đăng nhập lại thất bại: {ex}")
                    return False

            relogin_cb = auto_relogin

        self.gateway = GatewayClient(server_id, session, relogin_callback=relogin_cb)
        self.tp_executor = ThaoPhatExecutor(self.gateway)
        self.roster = Roster()
        self._results = queue.Queue()
        self._generals = {}

        # Trạng thái các luồng Task
        self._tp_running = False
        self._tp_runner = None
        self._gd_runner = None
        self._bm_runner = None
        self._ditrai_runner = None
        self._ditrai_stop_event = threading.Event()
        self._bld_runner = None
        self._res_runner = None
        self._city_building_plans: dict[int, list[dict]] = {}
        self._selected_building_cities: set[int] = set()
        self._selected_resource_cities: set[int] = set()
        self._research_city_id: Optional[int] = None
        self._res_monitor_running: bool = False
        self._res_monitor_thread: Optional[threading.Thread] = None
        self._current_bld_city_id: Optional[int] = None
        self._log_win = None
        self._active_log_texts: list[tk.Text] = []

        # Các biến cấu hình nội chính & tài nguyên
        self.bld_speedup_var = tk.BooleanVar(value=False)
        self.bld_speedup_hours_var = tk.StringVar(value="1")
        self.bld_open_box_var = tk.BooleanVar(value=False)
        self.bld_target_lvl_var = tk.StringVar(value="20")
        self.bld_max_lvl_var = tk.BooleanVar(value=False)
        self.res_target_lvl_var = tk.StringVar(value="20")
        self.res_art_var = tk.BooleanVar(value=False)
        self.res_even_var = tk.BooleanVar(value=False)
        self.res_interval_var = tk.StringVar(value="30")
        self.bld_interval_var = tk.StringVar(value="20")
        self.bld_box_max_var = tk.StringVar(value="5")
        self.bld_box_fallback_var = tk.BooleanVar(value=True)
        self.res_gold_thresh_var = tk.StringVar(value="100000000")
        self.res_wood_pct_var = tk.StringVar(value="70")
        self.res_iron_pct_var = tk.StringVar(value="70")
        self.res_stone_pct_var = tk.StringVar(value="70")
        self.res_food_pct_var = tk.StringVar(value="70")
        self.aux_daily_reward_var = tk.BooleanVar(value=True)
        self.aux_comfort_var = tk.BooleanVar(value=True)
        self.aux_boost_var = tk.BooleanVar(value=True)
        self.bld_boost_var = self.aux_boost_var
        self.bld_comfort_var = self.aux_comfort_var
        self.aux_tribute_var = tk.BooleanVar(value=False)
        self.log_amount_var = tk.StringVar(value="1")
        self.log_interval_var = tk.StringVar(value="60")
        self.dt_dest_x_var = tk.StringVar(value="")
        self.dt_dest_y_var = tk.StringVar(value="")

        # Widget log đệm
        self.bld_log_text = tk.Text(self)
        self.logis_log_text = tk.Text(self)
        self._active_log_texts = [self.bld_log_text, self.logis_log_text]

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

        # Cấu hình màu sắc Popdown Listbox cho tất cả Combobox trong ứng dụng
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.foreground", "#ffffff")
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))
        self.option_add("*ComboboxPopdown*Listbox.background", CARD)
        self.option_add("*ComboboxPopdown*Listbox.foreground", "#ffffff")
        self.option_add("*ComboboxPopdown*Listbox.selectBackground", ACCENT)
        self.option_add("*ComboboxPopdown*Listbox.selectForeground", "#ffffff")
        self.option_add("*ComboboxPopdown*Listbox.font", ("Segoe UI", 10))

        # Cards & inputs
        style.configure("Card.TLabelframe", background=BG, foreground=ACCENT)
        style.configure("Card.TLabelframe.Label", background=BG, foreground=ACCENT, font=("Segoe UI", 11, "bold"))
        style.configure("TLabel", background=CARD, foreground=FG, font=("Segoe UI", 10))
        style.configure("Dark.TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("Big.TLabel", font=("Segoe UI", 14, "bold"), foreground=ACCENT)
        style.configure("TEntry", fieldbackground="#2a2e45", foreground=FG, insertcolor=FG)
        style.configure(
            "TCombobox",
            background="#2a2e45",
            foreground="#ffffff",
            fieldbackground="#2a2e45",
            darkcolor="#1e2130",
            lightcolor="#3a4060",
            arrowcolor="#ffffff",
            insertcolor="#ffffff",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#2a2e45"), ("focus", "#323752"), ("disabled", "#1c1e29")],
            foreground=[("readonly", "#ffffff"), ("focus", "#ffffff"), ("disabled", "#8a90b0")],
            selectbackground=[("readonly", "#2a2e45"), ("focus", ACCENT)],
            selectforeground=[("readonly", "#ffffff"), ("focus", "#ffffff")],
            background=[("readonly", "#2a2e45"), ("active", "#3a4060")],
            arrowcolor=[("readonly", "#ffffff"), ("active", ACCENT)],
        )

        # Buttons
        style.configure("Action.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Action.TButton", background=[("active", "#8591ff")])
        style.configure("Success.TButton", background=SUCCESS, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Success.TButton", background=[("active", "#34c759")])
        style.configure("Danger.TButton", background=DANGER, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Danger.TButton", background=[("active", "#ff4d4f"), ("disabled", "#552222")])
        style.configure("Warning.TButton", background="#f59e0b", foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Warning.TButton", background=[("active", "#fbbf24")])

        # Top Bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 6))
        self.status = tk.StringVar(value="Đang kết nối & tải dữ liệu...")
        tk.Label(top, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
        self.refresh_btn = ttk.Button(top, text="🔄 Làm mới", style="Action.TButton", command=self.reload)
        self.refresh_btn.pack(side="right")
        self.open_logs_btn = ttk.Button(
            top,
            text="📂 Mở thư mục Log",
            style="Action.TButton",
            command=lambda: open_logs_directory(),
        )
        self.open_logs_btn.pack(side="right", padx=(0, 6))

        # Notebook chứa 5 Tab (theo thứ tự quy hoạch mới):
        # 1. 🏛️ Nội Chính & Nghiên Cứu
        # 2. ⚔️ Thảo Phạt
        # 3. 🏕️ Bình Man
        # 4. 🧛 Vong Linh
        # 5. 🏰 Tổng quan
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Tab 1: Nội Chính & Nghiên Cứu
        t1 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t1, text="🏛️ Nội Chính & Nghiên Cứu")
        self._build_internal_and_research_tab(t1)

        # Tab 2: Thảo Phạt Tự Động
        t2 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t2, text="⚔️ Thảo Phạt")
        self._build_thaophat_tab(t2)

        # Tab 3: Bình Man
        t3 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t3, text="🏕️ Bình Man")
        self._build_binhman_tab(t3)

        # Tab 4: Vong Linh
        t4 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t4, text="🧛 Vong Linh")
        self._build_goidan_tab(t4)

        # Tab 5: Tổng quan & Quân đội
        t5 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t5, text="🏰 Tổng quan")
        self._build_overview_tab(t5)

        # Tự động nạp hồ sơ cấu hình tổng hợp mặc định theo tài khoản
        acc_prof = Path(self.default_profile_name)
        if acc_prof.exists():
            try:
                self._load_unified_profile(acc_prof)
            except Exception:
                pass
        elif Path("auto_profile.json").exists():
            try:
                self._load_unified_profile(Path("auto_profile.json"))
                if hasattr(self, "profile_path_var"):
                    self.profile_path_var.set(self.default_profile_name)
            except Exception:
                pass

        self.reload()

    # =========================================================================
    # TAB 1: TỔNG QUAN
    # =========================================================================
    def _build_overview_tab(self, parent):
        # Thanh Hồ Sơ Cấu Hình (Quản lý tập trung toàn bộ tính năng)
        profile_frame = tk.Frame(parent, bg=BG)
        profile_frame.pack(fill="x", pady=(2, 6))

        tk.Label(profile_frame, text="📁 Hồ Sơ Cấu Hình:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 6))
        self.profile_path_var = tk.StringVar(value=self.default_profile_name)
        ttk.Label(profile_frame, textvariable=self.profile_path_var, style="Dark.TLabel", font=("Consolas", 10)).pack(side="left", padx=(0, 12))

        ttk.Button(profile_frame, text="💾 Lưu Cấu Hình Tổng", style="Action.TButton", command=self._save_unified_profile_dialog).pack(side="left", padx=3)
        ttk.Button(profile_frame, text="📂 Nạp Cấu Hình Tổng", style="Action.TButton", command=self._load_unified_profile_dialog).pack(side="left", padx=3)

        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure((0, 1, 2), weight=1, uniform="c")
        body.rowconfigure(0, weight=1)

        f1 = ttk.LabelFrame(body, text="Thành & Doanh trại", style="Card.TLabelframe")
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

        f2 = ttk.LabelFrame(body, text="Tướng đồn trú", style="Card.TLabelframe")
        f2.grid(row=0, column=1, sticky="nsew", padx=6)
        self.gen_tree = ttk.Treeview(f2, columns=("role", "lv", "hp", "status"), show="tree headings", selectmode="browse")
        for col, text, w in (("#0", "Tên tướng", 100), ("role", "Chức vụ", 70), ("lv", "Cấp", 35), ("hp", "Thể lực", 70), ("status", "Trạng thái", 90)):
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

    # -------------------------------------------------------------------------
    # HỒ SƠ CẤU HÌNH TỔNG HỢP (UNIFIED PROFILE CONFIGURATION)
    # -------------------------------------------------------------------------
    def _collect_unified_profile(self) -> dict:
        profile = {
            "version": 1,
            "building": {
                "slots": int(self.bld_slots_combo.get()) if hasattr(self, "bld_slots_combo") and self.bld_slots_combo.get() else 3,
                "auto_speedup": bool(self.bld_speedup_var.get()) if hasattr(self, "bld_speedup_var") else False,
                "auto_boost": bool(self.bld_boost_var.get()) if hasattr(self, "bld_boost_var") else True,
                "auto_comfort": bool(self.bld_comfort_var.get()) if hasattr(self, "bld_comfort_var") else True,
                "auto_open_box": bool(self.bld_open_box_var.get()) if hasattr(self, "bld_open_box_var") else False,
                "box_type_idx": self.bld_box_combo.current() if hasattr(self, "bld_box_combo") else 0,
                "box_max": self.bld_box_max_var.get() if hasattr(self, "bld_box_max_var") else "5",
                "auto_fallback_box": bool(self.bld_box_fallback_var.get()) if hasattr(self, "bld_box_fallback_var") else True,
                "interval": self.bld_interval_var.get() if hasattr(self, "bld_interval_var") else "20",
                "plans": [],
            },
            "research": {
                "art_speedup": bool(self.res_art_var.get()) if hasattr(self, "res_art_var") else False,
                "even_research": bool(self.res_even_var.get()) if hasattr(self, "res_even_var") else False,
                "interval": self.res_interval_var.get() if hasattr(self, "res_interval_var") else "30",
                "techs": [],
            },
            "thao_phat": {
                "min_army": self.tp_target_inf_var.get() if hasattr(self, "tp_target_inf_var") else (self.tp_min_army_var.get() if hasattr(self, "tp_min_army_var") else "5000"),
                "target_infantry": self.tp_target_inf_var.get() if hasattr(self, "tp_target_inf_var") else "5000",
                "target_cavalry": self.tp_target_cav_var.get() if hasattr(self, "tp_target_cav_var") else "0",
                "target_archers": self.tp_target_arc_var.get() if hasattr(self, "tp_target_arc_var") else "0",
                "mission_idx": self.tp_mission_combo.current() if hasattr(self, "tp_mission_combo") else 0,
                "auto_recruit": bool(self.tp_auto_recruit_var.get()) if hasattr(self, "tp_auto_recruit_var") else True,
                "auto_morale": bool(self.tp_auto_morale_var.get()) if hasattr(self, "tp_auto_morale_var") else True,
                "min_morale": self.tp_min_morale_var.get() if hasattr(self, "tp_min_morale_var") else "95",
                "interval": self.tp_interval_var.get() if hasattr(self, "tp_interval_var") else "10",
            },
            "goi_dan": {
                "mode_idx": self.gd_mode_combo.current() if hasattr(self, "gd_mode_combo") else 0,
                "radius": self.gd_radius_var.get() if hasattr(self, "gd_radius_var") else "5",
                "auto_recover": bool(self.gd_recover_var.get()) if hasattr(self, "gd_recover_var") else True,
                "interval": self.gd_interval_var.get() if hasattr(self, "gd_interval_var") else "10",
            },
            "binh_man": {
                "radius": self.bm_radius_var.get() if hasattr(self, "bm_radius_var") else "5",
                "min_army": self.bm_min_army_var.get() if hasattr(self, "bm_min_army_var") else "3000",
                "min_hp": self.bm_min_hp_var.get() if hasattr(self, "bm_min_hp_var") else "50",
                "auto_comfort": bool(self.bm_comfort_var.get()) if hasattr(self, "bm_comfort_var") else True,
                "interval": self.bm_interval_var.get() if hasattr(self, "bm_interval_var") else "15",
            },
            "logistics": {
                "army_type_idx": self.log_army_combo.current() if hasattr(self, "log_army_combo") else 0,
                "amount": self.log_amount_var.get() if hasattr(self, "log_amount_var") else "1000",
            },
            "ditrai": {
                "dest_x": self.dt_dest_x_var.get() if hasattr(self, "dt_dest_x_var") else "",
                "dest_y": self.dt_dest_y_var.get() if hasattr(self, "dt_dest_y_var") else "",
            },
        }

        # Thu thập Hàng đợi Xây dựng (đa căn cứ & tương thích ngược)
        self._save_current_bld_tree_to_cache()
        cities_cfg = {}
        for cid, plans in self._city_building_plans.items():
            base_name = ""
            if self.roster:
                b = self.roster.base_by_id(cid)
                if b:
                    base_name = b.name
            if not base_name and hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(cid)):
                base_name = self.bld_bases_tree.item(str(cid), "text")
            is_enabled = cid in self._selected_building_cities
            cities_cfg[str(cid)] = {
                "name": base_name,
                "enabled": is_enabled,
                "plans": plans,
            }
        profile["building"]["cities"] = cities_cfg

        if hasattr(self, "bld_tree"):
            profile["building"]["plans"] = self._collect_bld_plans_from_tree()

        # Thu thập Hàng đợi Nghiên cứu
        if hasattr(self, "res_tree"):
            for iid in self.res_tree.get_children(""):
                name = self.res_tree.item(iid, "text")
                vals = self.res_tree.item(iid, "values")
                if len(vals) >= 4:
                    profile["research"]["techs"].append({
                        "id": int(vals[1]),
                        "target_level": int(vals[2]),
                        "name": name,
                        "enabled": vals[0] == "☑",
                    })

        return profile

    def _apply_unified_profile(self, data: dict) -> list[str]:
        loaded_sections = []

        # 1. Xây Dựng (hỗ trợ cả profile đa căn cứ mới và build_plans.json cũ)
        plans_list = None
        cities_data = None
        if "plans" in data and isinstance(data["plans"], list):
            plans_list = data["plans"]
        elif "building" in data and isinstance(data["building"], dict):
            bld_data = data["building"]
            if hasattr(self, "bld_slots_combo") and "slots" in bld_data:
                self.bld_slots_combo.set(str(bld_data["slots"]))
            if hasattr(self, "bld_speedup_var") and "auto_speedup" in bld_data:
                self.bld_speedup_var.set(bool(bld_data["auto_speedup"]))
            if hasattr(self, "bld_boost_var") and "auto_boost" in bld_data:
                self.bld_boost_var.set(bool(bld_data["auto_boost"]))
            if hasattr(self, "bld_comfort_var") and "auto_comfort" in bld_data:
                self.bld_comfort_var.set(bool(bld_data["auto_comfort"]))
            if hasattr(self, "bld_even_var") and "even_upgrade" in bld_data:
                self.bld_even_var.set(bool(bld_data["even_upgrade"]))
            if hasattr(self, "bld_open_box_var") and "auto_open_box" in bld_data:
                self.bld_open_box_var.set(bool(bld_data["auto_open_box"]))
            if hasattr(self, "bld_box_combo") and "box_type_idx" in bld_data:
                try:
                    idx = int(bld_data["box_type_idx"])
                    if 0 <= idx < len(self.bld_box_combo["values"]):
                        self.bld_box_combo.current(idx)
                except (ValueError, IndexError):
                    pass
            if hasattr(self, "bld_box_max_var") and "box_max" in bld_data:
                self.bld_box_max_var.set(str(bld_data["box_max"]))
            if hasattr(self, "bld_box_fallback_var") and "auto_fallback_box" in bld_data:
                self.bld_box_fallback_var.set(bool(bld_data["auto_fallback_box"]))
            if hasattr(self, "bld_interval_var") and "interval" in bld_data:
                self.bld_interval_var.set(str(bld_data["interval"]))
            plans_list = bld_data.get("plans")
            cities_data = bld_data.get("cities")

        if cities_data and isinstance(cities_data, dict):
            for cid_str, cinfo in cities_data.items():
                try:
                    cid = int(cid_str)
                except ValueError:
                    continue
                c_plans = cinfo.get("plans", [])
                self._city_building_plans[cid] = c_plans
                if cinfo.get("enabled", True):
                    self._selected_building_cities.add(cid)
                else:
                    self._selected_building_cities.discard(cid)
                if hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(cid)):
                    sym = "☑" if cid in self._selected_building_cities else "☐"
                    vals = list(self.bld_bases_tree.item(str(cid), "values"))
                    if vals:
                        vals[0] = sym
                        self.bld_bases_tree.item(str(cid), values=vals)

            cur_id = self._current_bld_city_id
            if cur_id is None and self._selected_building_cities:
                cur_id = next(iter(self._selected_building_cities))
                self._current_bld_city_id = cur_id
            if cur_id and cur_id in self._city_building_plans:
                self._render_bld_tree_from_plans(self._city_building_plans[cur_id])
            elif plans_list and hasattr(self, "bld_tree"):
                self._render_bld_tree_from_plans(plans_list)

            loaded_sections.append(f"Xây Dựng ({len(cities_data)} căn cứ)")
            if hasattr(self, "_append_bld_log"):
                self._append_bld_log(f"📂 Đã nạp cấu hình quy hoạch cho {len(cities_data)} căn cứ từ hồ sơ.")
        elif plans_list and hasattr(self, "bld_tree"):
            self._render_bld_tree_from_plans(plans_list)
            if self._current_bld_city_id is not None:
                self._city_building_plans[self._current_bld_city_id] = plans_list
            loaded_sections.append(f"Xây Dựng ({len(plans_list)} công trình)")
            if hasattr(self, "_append_bld_log"):
                self._append_bld_log(f"📂 Đã nạp cấu hình {len(plans_list)} công trình từ hồ sơ.")

        # 2. Nghiên cứu Đại Học (hỗ trợ cả profile mới và tech_plans.json cũ)
        techs_list = None
        if "techs" in data and isinstance(data["techs"], list):
            techs_list = data["techs"]
        elif "research" in data and isinstance(data["research"], dict):
            res_data = data["research"]
            if hasattr(self, "res_art_var") and "art_speedup" in res_data:
                self.res_art_var.set(bool(res_data["art_speedup"]))
            if hasattr(self, "res_even_var") and "even_research" in res_data:
                self.res_even_var.set(bool(res_data["even_research"]))
            if hasattr(self, "res_interval_var") and "interval" in res_data:
                self.res_interval_var.set(str(res_data["interval"]))
            techs_list = res_data.get("techs") or res_data.get("plans")

        if techs_list and hasattr(self, "res_tree"):
            self.res_tree.delete(*self.res_tree.get_children(""))
            for t in techs_list:
                tid = int(t.get("id", 1))
                tname = t.get("name") or TECH_NAMES.get(tid, f"Kỹ thuật {tid}")
                en = "☑" if t.get("enabled", True) else "☐"
                target_lvl = int(t.get("target_level", 20))
                cur_lvl = t.get("current_level", "-")
                try:
                    cur_int = int(cur_lvl) if str(cur_lvl) != "-" else None
                    tag = ("completed" if cur_int >= target_lvl else "upgrade") if cur_int is not None else "upgrade"
                except (ValueError, TypeError):
                    tag = "upgrade"
                self.res_tree.insert(
                    "",
                    "end",
                    iid=str(tid),
                    text=tname,
                    values=(en, tid, target_lvl, cur_lvl),
                    tags=(tag,),
                )
            loaded_sections.append(f"Đại Học ({len(techs_list)} kỹ thuật)")
            if hasattr(self, "_append_logis_log"):
                self._append_logis_log(f"📂 Đã nạp cấu hình {len(techs_list)} kỹ thuật từ hồ sơ.")

        # 3. Thảo Phạt
        if "thao_phat" in data and isinstance(data["thao_phat"], dict):
            tp_data = data["thao_phat"]
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
            loaded_sections.append("Thảo Phạt")

        # 4. Gọi Dân
        if "goi_dan" in data and isinstance(data["goi_dan"], dict):
            gd_data = data["goi_dan"]
            if hasattr(self, "gd_mode_combo") and "mode_idx" in gd_data:
                try:
                    self.gd_mode_combo.current(int(gd_data["mode_idx"]))
                except Exception:
                    pass
            if hasattr(self, "gd_radius_var") and "radius" in gd_data:
                self.gd_radius_var.set(str(gd_data["radius"]))
            if hasattr(self, "gd_recover_var") and "auto_recover" in gd_data:
                self.gd_recover_var.set(bool(gd_data["auto_recover"]))
            if hasattr(self, "gd_interval_var") and "interval" in gd_data:
                self.gd_interval_var.set(str(gd_data["interval"]))
            loaded_sections.append("Gọi Dân")

        # 5. Bình Man
        if "binh_man" in data and isinstance(data["binh_man"], dict):
            bm_data = data["binh_man"]
            if hasattr(self, "bm_radius_var") and "radius" in bm_data:
                self.bm_radius_var.set(str(bm_data["radius"]))
            if hasattr(self, "bm_min_army_var") and "min_army" in bm_data:
                self.bm_min_army_var.set(str(bm_data["min_army"]))
            if hasattr(self, "bm_min_hp_var") and "min_hp" in bm_data:
                self.bm_min_hp_var.set(str(bm_data["min_hp"]))
            if hasattr(self, "bm_comfort_var") and "auto_comfort" in bm_data:
                self.bm_comfort_var.set(bool(bm_data["auto_comfort"]))
            if hasattr(self, "bm_interval_var") and "interval" in bm_data:
                self.bm_interval_var.set(str(bm_data["interval"]))
            loaded_sections.append("Bình Man")

        # 6. Hậu Cần
        if "logistics" in data and isinstance(data["logistics"], dict):
            log_data = data["logistics"]
            if hasattr(self, "log_army_combo") and "army_type_idx" in log_data:
                try:
                    self.log_army_combo.current(int(log_data["army_type_idx"]))
                except Exception:
                    pass
            if hasattr(self, "log_amount_var") and "amount" in log_data:
                self.log_amount_var.set(str(log_data["amount"]))
            loaded_sections.append("Hậu Cần")

        # 7. Dịch Trại
        if "ditrai" in data and isinstance(data["ditrai"], dict):
            dt_data = data["ditrai"]
            if hasattr(self, "dt_dest_x_var") and "dest_x" in dt_data:
                self.dt_dest_x_var.set(str(dt_data["dest_x"]))
            if hasattr(self, "dt_dest_y_var") and "dest_y" in dt_data:
                self.dt_dest_y_var.set(str(dt_data["dest_y"]))
            loaded_sections.append("Dịch Trại")

        return loaded_sections

    def _save_unified_profile(self, filepath: Optional[Path] = None) -> Path:
        def_name = getattr(self, "default_profile_name", "auto_profile.json")
        target = filepath or Path(self.profile_path_var.get() if hasattr(self, "profile_path_var") and self.profile_path_var.get() else def_name)
        profile = self._collect_unified_profile()
        target.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        if hasattr(self, "profile_path_var"):
            self.profile_path_var.set(target.name)
        return target

    def _load_unified_profile(self, filepath: Optional[Path] = None) -> tuple[bool, str]:
        def_name = getattr(self, "default_profile_name", "auto_profile.json")
        target = filepath or Path(self.profile_path_var.get() if hasattr(self, "profile_path_var") and self.profile_path_var.get() else def_name)
        if not target.exists():
            return False, f"Không tìm thấy file: {target.name}"
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            sections = self._apply_unified_profile(data)
            if hasattr(self, "profile_path_var"):
                self.profile_path_var.set(target.name)
            return True, f"Đã nạp thành công các phân hệ: {', '.join(sections)}"
        except Exception as e:
            return False, f"Lỗi đọc file cấu hình: {e}"

    def _save_unified_profile_dialog(self):
        cur_name = self.profile_path_var.get() if hasattr(self, "profile_path_var") else "auto_profile.json"
        fpath = filedialog.asksaveasfilename(
            title="Lưu Hồ Sơ Cấu Hình Tổng",
            defaultextension=".json",
            initialfile=cur_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if fpath:
            p = self._save_unified_profile(Path(fpath))
            messagebox.showinfo("Thành công", f"Đã lưu hồ sơ cấu hình tổng vào:\n{p.name}")

    def _load_unified_profile_dialog(self):
        fpath = filedialog.askopenfilename(
            title="Nạp Hồ Sơ Cấu Hình Tổng",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if fpath:
            ok, msg = self._load_unified_profile(Path(fpath))
            if ok:
                messagebox.showinfo("Thành công", msg)
            else:
                messagebox.showerror("Lỗi", msg)

    # =========================================================================
    # TAB 2: THẢO PHẠT
    # =========================================================================
    def _build_thaophat_tab(self, parent):
        top_ctrl = tk.Frame(parent, bg=BG)
        top_ctrl.pack(fill="x", pady=6)

        # Hàng 1: Thành trì, Chiến dịch, Cấu hình biên chế MT (Bộ, Kỵ, Cung), Nút Biên chế ngay, Nút Bắt đầu
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

        # Cấu hình biên chế quân đội: Bộ, Kỵ, Cung
        tk.Label(row1, text="Bộ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.tp_target_inf_var = tk.StringVar(value="5000")
        self.tp_min_army_var = self.tp_target_inf_var  # Giữ alias tương thích
        ttk.Entry(row1, textvariable=self.tp_target_inf_var, width=6).pack(side="left", padx=(0, 8))

        tk.Label(row1, text="Kỵ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.tp_target_cav_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.tp_target_cav_var, width=6).pack(side="left", padx=(0, 8))

        tk.Label(row1, text="Cung MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.tp_target_arc_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.tp_target_arc_var, width=6).pack(side="left", padx=(0, 10))

        # Nút Biên chế ngay
        ttk.Button(row1, text="⚔️ Biên chế ngay", style="Action.TButton", command=self._manual_adjust_tp_troops).pack(side="left", padx=(0, 6))

        # Nút Bắt đầu Thảo Phạt
        self.tp_start_btn = ttk.Button(row1, text="▶️ Bắt đầu Thảo Phạt", style="Success.TButton", command=self._toggle_tp)
        self.tp_start_btn.pack(side="left", padx=4)

        # Hàng 2: Tùy chọn Tự động bổ sung lính, Tự động nâng sĩ khí, Ngưỡng sĩ khí tối thiểu
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

        # Bảng tướng & Log sắp xếp theo ROW (Trên: Bảng tướng, Dưới: Nhật ký)
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        # Row 0: Bảng danh sách võ tướng
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

        # Row 1: Khung nhật ký log Thảo Phạt
        f_bottom = ttk.LabelFrame(body, text="Nhật ký chiến dịch Thảo Phạt", style="Card.TLabelframe")
        f_bottom.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        log_scroll = ttk.Scrollbar(f_bottom, orient="vertical")
        self.tp_log_text = tk.Text(f_bottom, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0, yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.tp_log_text.yview)
        self.tp_log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        log_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)

    def _on_tp_city_selected(self, _event=None):
        sel_idx = self.tp_city_combo.current()
        bases = self.roster.bases if (self.roster and self.roster.bases) else []
        if sel_idx < 0 or sel_idx >= len(bases):
            return
        base = bases[sel_idx]
        self.tp_gen_tree.delete(*self.tp_gen_tree.get_children())
        for g in self.roster.generals_of(base.id):
            if g.role != "vo":
                continue
            army = self.roster.army_of(g.id)
            inf = army.infantry if army else 0
            cav = army.cavalry if army else 0
            arc = army.archers if army else 0
            total = army.total if army else 0
            self.tp_gen_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=("☐", g.level, f"{g.stamina}/{g.stamina_max}", g.morale, inf, cav, arc, total),
            )

    def _on_tp_gen_toggle(self, event):
        item = self.tp_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.tp_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.tp_gen_tree.item(item, values=vals)

    def _manual_adjust_tp_troops(self):
        """Bổ sung/biên chế quân lính thủ công ngay lập tức cho các tướng đã chọn."""
        sel_idx = self.tp_city_combo.current()
        bases = self.roster.bases if (self.roster and self.roster.bases) else []
        if sel_idx < 0 or sel_idx >= len(bases):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn căn cứ!")
            return
        city_id = bases[sel_idx].id
        sel_gens = [int(iid) for iid in self.tp_gen_tree.get_children() if self.tp_gen_tree.item(iid, "values")[0] == "☑"]
        if not sel_gens:
            messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 võ tướng để biên chế!")
            return

        try:
            inf = int(self.tp_target_inf_var.get() or "0")
            cav = int(self.tp_target_cav_var.get() or "0")
            arc = int(self.tp_target_arc_var.get() or "0")
        except ValueError:
            messagebox.showerror("Lỗi", "Quân số biên chế phải là số nguyên!")
            return

        target_army = TargetArmy(infantry=inf, cavalry=cav, archers=arc)
        auto_recruit = bool(self.tp_auto_recruit_var.get())

        def _worker():
            self.after(0, self._append_tp_log, "⚔️ Bắt đầu tiến trình biên chế quân đội thủ công...")
            self.after(0, self._append_tp_log, f"   Mục tiêu: Bộ={inf}, Kỵ={cav}, Cung={arc} | Tự động chiêu mộ tân binh: {'Bật' if auto_recruit else 'Tắt'}")
            executor = getattr(self, "tp_executor", None) or ThaoPhatExecutor(self.gateway)
            try:
                # 1. Tính tổng tân binh cần và chiêu mộ trước nếu bật auto_recruit
                if auto_recruit:
                    fresh_roster = fetch_roster(self.gateway)
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

                # 2. Biên chế lính cho từng tướng
                fresh_roster = fetch_roster(self.gateway)
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
                # Tải lại roster để cập nhật cây tướng
                new_roster = fetch_roster(self.gateway)
                self.roster = new_roster
                self.after(0, self._on_tp_city_selected)
            except Exception as e:
                self.after(0, self._append_tp_log, f"❌ Lỗi ngoại lệ khi biên chế: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_tp(self):
        if not self._tp_running:
            sel_idx = self.tp_city_combo.current()
            bases = self.roster.bases if (self.roster and self.roster.bases) else []
            if sel_idx < 0 or sel_idx >= len(bases):
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn căn cứ!")
                return
            city_id = bases[sel_idx].id
            sel_gens = [int(iid) for iid in self.tp_gen_tree.get_children() if self.tp_gen_tree.item(iid, "values")[0] == "☑"]
            if not sel_gens:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng!")
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

    def _append_text_buffer(self, widget: tk.Text, line: str, max_lines: int = 1000):
        """Chèn dòng mới vào widget Text và tự động cắt tỉa các dòng cũ nhất khi vượt max_lines."""
        if not widget or not widget.winfo_exists():
            return
        widget.insert("end", line)
        try:
            line_count = int(widget.index("end-1c").split(".")[0])
            if line_count > max_lines:
                diff = line_count - max_lines
                widget.delete("1.0", f"{diff + 1}.0")
        except Exception:
            pass
        widget.see("end")

    def _append_tp_log(self, msg: str):
        self._append_text_buffer(self.tp_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

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

        tk.Label(top, text="Chu kỳ (s):", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.gd_interval_var = tk.StringVar(value="10")
        ttk.Entry(top, textvariable=self.gd_interval_var, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        # Điều khiển
        ctrl_frame = tk.Frame(top, bg=BG)
        ctrl_frame.grid(row=0, column=4, rowspan=3, padx=16)
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
        self._append_text_buffer(self.gd_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

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
            try:
                gd_interval = max(3.0, float(self.gd_interval_var.get() or "10"))
            except ValueError:
                gd_interval = 10.0
            self._gd_runner = GoiDanAutoRunner(
                task,
                interval=gd_interval,
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
        # 1. Khung Bình Man Tự Động
        f_bm = ttk.LabelFrame(parent, text="🗡️ Tự Động Bình Man", style="Card.TLabelframe")
        f_bm.pack(fill="x", padx=4, pady=4)

        tk.Label(f_bm, text="Căn cứ xuất phát:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.bm_city_combo = ttk.Combobox(f_bm, state="readonly", width=22)
        self.bm_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.bm_city_combo.bind("<<ComboboxSelected>>", self._on_bm_city_selected)

        tk.Label(f_bm, text="Thành mẹ (Hồi quân):", bg=BG, fg=FG, font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.bm_parent_city_combo = ttk.Combobox(f_bm, state="readonly", width=18)
        self.bm_parent_city_combo.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Doanh trại ID:", bg=BG, fg=FG).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.bm_camp_id_var = tk.StringVar(value="")
        ttk.Entry(f_bm, textvariable=self.bm_camp_id_var, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Ngưỡng An Toàn (%):", bg=BG, fg=FG).grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.bm_threshold_var = tk.StringVar(value="30")
        ttk.Entry(f_bm, textvariable=self.bm_threshold_var, width=8).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Bán kính quét:", bg=BG, fg=FG).grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.bm_radius_var = tk.StringVar(value="10")
        ttk.Entry(f_bm, textvariable=self.bm_radius_var, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Cấp Man (1..10):", bg=BG, fg=FG).grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.bm_mantypes_var = tk.StringVar(value="7,8,9,10")
        ttk.Entry(f_bm, textvariable=self.bm_mantypes_var, width=18).grid(row=2, column=3, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Chu kỳ (s):", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.bm_interval_var = tk.StringVar(value="15")
        ttk.Entry(f_bm, textvariable=self.bm_interval_var, width=8).grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ctrl_frame = tk.Frame(f_bm, bg=BG)
        ctrl_frame.grid(row=0, column=4, rowspan=4, padx=16)
        self.bm_start_btn = ttk.Button(ctrl_frame, text="▶️ Bắt đầu Bình Man", style="Success.TButton", command=self._toggle_binhman)
        self.bm_start_btn.pack(side="top", pady=2)
        self.bm_once_btn = ttk.Button(ctrl_frame, text="⚡ Chạy 1 Lượt", style="Action.TButton", command=self._run_binhman_once)
        self.bm_once_btn.pack(side="top", pady=2)

        # 2. Khung Nhật ký chung
        f_log = ttk.LabelFrame(parent, text="Nhật ký Bình Man", style="Card.TLabelframe")
        f_log.pack(fill="both", expand=True, padx=4, pady=4)
        self.bm_log_text = tk.Text(f_log, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.bm_log_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _append_bm_log(self, msg: str):
        self._append_text_buffer(self.bm_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _on_bm_city_selected(self, _event=None):
        sel_idx = self.bm_city_combo.current()
        bases = self.roster.camps if self.roster.camps else self.roster.bases
        if 0 <= sel_idx < len(bases):
            base = bases[sel_idx]
            if base.is_camp:
                self.bm_camp_id_var.set(str(base.id))
            else:
                self.bm_camp_id_var.set("")

    def _append_dt_log(self, msg: str):
        if hasattr(self, "_append_bld_log"):
            self._append_bld_log(msg)
        if hasattr(self, "_append_bm_log"):
            self._append_bm_log(msg)

    def _on_dt_camp_selected(self, _event=None):
        sel_idx = self.dt_camp_combo.current()
        camps = self.roster.camps if self.roster.camps else self.roster.bases
        if 0 <= sel_idx < len(camps):
            camp = camps[sel_idx]
            self.dt_origin_lbl.configure(text=f"Vị trí: ({camp.pos_x}, {camp.pos_y})")

    def _start_ditrai(self):
        if self._ditrai_runner and self._ditrai_runner.is_alive():
            messagebox.showinfo("Thông báo", "Tiến trình Di Trại đang chạy!")
            return

        camps = self.roster.camps if self.roster.camps else self.roster.bases
        sel_idx = self.dt_camp_combo.current()
        if sel_idx < 0 or sel_idx >= len(camps):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn Doanh trại cần di chuyển!")
            return
        camp = camps[sel_idx]

        dest_x_str = self.dt_dest_x_var.get().strip()
        dest_y_str = self.dt_dest_y_var.get().strip()
        if not dest_x_str or not dest_y_str:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập đầy đủ tọa độ đích X và Y!")
            return

        try:
            dest_x = int(dest_x_str)
            dest_y = int(dest_y_str)
        except ValueError:
            messagebox.showerror("Lỗi", "Tọa độ đích X và Y phải là số nguyên hợp lệ!")
            return

        self._ditrai_stop_event.clear()
        self.dt_start_btn.configure(state="disabled")
        self.dt_stop_btn.configure(state="normal")
        self.dt_status_lbl.configure(text=f"🚀 Đang di chuyển tới ({dest_x}, {dest_y})...", fg="#38bdf8")
        self._append_dt_log(f"🚀 Bắt đầu Di Trại {camp.name} từ ({camp.pos_x}, {camp.pos_y}) tới ({dest_x}, {dest_y})")

        self._ditrai_runner = threading.Thread(
            target=self._run_ditrai_thread,
            args=(camp, dest_x, dest_y),
            daemon=True,
        )
        self._ditrai_runner.start()

    def _stop_ditrai(self):
        self._ditrai_stop_event.set()
        self.dt_status_lbl.configure(text="⏹️ Đang gửi tín hiệu dừng Di Trại...", fg="#facc15")
        self._append_dt_log("⏹️ Người chơi bấm dừng Di Trại, chờ bước hiện tại kết thúc an toàn...")

    def _run_ditrai_thread(self, camp: City, dest_x: int, dest_y: int):
        def on_step_callback(new_x: int, new_y: int, frozen: int):
            self.roster.update_camp_position(camp.id, new_x, new_y)
            self.after(0, lambda: self.dt_origin_lbl.configure(text=f"Vị trí: ({new_x}, {new_y})"))
            for rem in range(frozen, 0, -1):
                if self._ditrai_stop_event.is_set():
                    break
                self.after(0, lambda r=rem: self.dt_status_lbl.configure(text=f"⏳ Đang đóng băng: {r}s...", fg="#facc15"))
                time.sleep(1)

            if not self._ditrai_stop_event.is_set():
                self.after(0, lambda: self.dt_status_lbl.configure(text="🏃 Đang di chuyển bước tiếp theo...", fg="#38bdf8"))

        ctx = TaskContext(
            self.gateway,
            None,
            TargetLocks(),
            notify=lambda m: self.after(0, self._append_dt_log, m),
        )

        task = DiTrai(
            ctx=ctx,
            camp_id=camp.id,
            origin=(camp.pos_x, camp.pos_y),
            destination=(dest_x, dest_y),
            max_step=2,
            sleep_fn=time.sleep,
            on_step=on_step_callback,
            stop_event=self._ditrai_stop_event,
        )

        try:
            result = task.advance_to_destination()
        except Exception as e:
            logging.getLogger("linhvuong.tasks.DiTrai").exception(f"Lỗi ngoại lệ trong quá trình Di Trại: {e}")
            result = f"error: {e}"
            self.after(0, self._append_dt_log, f"❌ Lỗi ngoại lệ trong quá trình Di Trại: {e}")

        def finalize():
            self.dt_start_btn.configure(state="normal")
            self.dt_stop_btn.configure(state="disabled")
            if result == "arrived":
                self.dt_status_lbl.configure(text=f"🎯 Đã đến đích ({dest_x}, {dest_y}) thành công!", fg="#4ade80")
                self._append_dt_log(f"🎯 Di Trại {camp.name} đã đến đích ({dest_x}, {dest_y}) thành công!")
            elif result == "stopped":
                self.dt_status_lbl.configure(text=f"⏹️ Đã dừng an toàn tại ({task.origin[0]}, {task.origin[1]})", fg="#94a3b8")
                self._append_dt_log(f"⏹️ Di Trại {camp.name} đã dừng an toàn tại ({task.origin[0]}, {task.origin[1]})")
            elif result == "insufficient_resources":
                self.dt_status_lbl.configure(text="❌ Thiếu tài nguyên di chuyển!", fg="#f87171")
                self._append_dt_log(f"❌ Di Trại {camp.name} thiếu tài nguyên để tiếp tục di chuyển!")
            else:
                self.dt_status_lbl.configure(text=f"❌ Dừng: {result}", fg="#f87171")
                self._append_dt_log(f"❌ Di Trại {camp.name} dừng: {result}")

            self._update_all_combos_coordinates()

        self.after(0, finalize)

    def _update_all_combos_coordinates(self):
        camps_items = [c.display_name for c in self.roster.camps] if self.roster.camps else [b.display_name for b in self.roster.bases]
        if hasattr(self, "dt_camp_combo") and camps_items:
            cur_idx = self.dt_camp_combo.current()
            self.dt_camp_combo["values"] = camps_items
            if cur_idx >= 0 and cur_idx < len(camps_items):
                self.dt_camp_combo.current(cur_idx)
                self._on_dt_camp_selected()
        if hasattr(self, "bm_city_combo") and camps_items:
            bm_idx = self.bm_city_combo.current()
            self.bm_city_combo["values"] = camps_items
            if bm_idx >= 0 and bm_idx < len(camps_items):
                self.bm_city_combo.current(bm_idx)
                self._on_bm_city_selected()

    def _create_binhman_task(self) -> Optional[BinhMan]:
        sel_idx = self.bm_city_combo.current()
        bases = self.roster.camps if self.roster.camps else self.roster.bases
        if sel_idx < 0 or sel_idx >= len(bases):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn căn cứ/doanh trại xuất phát!")
            return None
        base = bases[sel_idx]
        gens = [g.id for g in self.roster.generals_of(base.id) if g.role == "vo"][:3]
        if not gens:
            messagebox.showwarning("Cảnh báo", "Căn cứ này không có võ tướng khả dụng!")
            return None

        parent_idx = self.bm_parent_city_combo.current()
        parent_city_id = self.roster.cities[parent_idx].id if (parent_idx >= 0 and parent_idx < len(self.roster.cities)) else base.id
        parent_id = self.roster.cities[parent_idx].id if parent_idx >= 0 else None
        camp_id = int(self.bm_camp_id_var.get()) if self.bm_camp_id_var.get().strip() else (base.id if base.is_camp else None)
        radius = int(self.bm_radius_var.get() or "10")
        threshold = int(self.bm_threshold_var.get() or "30")
        man_types = [int(x.strip()) for x in self.bm_mantypes_var.get().split(",") if x.strip()]

        locks = TargetLocks()
        scanner = Scanner(self.gateway, locks, delay=0.0, sleep=lambda s: None)
        ctx = TaskContext(self.gateway, scanner, locks, notify=lambda m: self.after(0, self._append_bm_log, m))

        return BinhMan(
            ctx=ctx,
            generals=gens,
            origin=(base.pos_x, base.pos_y),
            radius=radius,
            man_types=man_types,
            camp_id=camp_id,
            parent_city_id=parent_id,
            return_threshold=threshold,
            sleep_fn=time.sleep,
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
            try:
                bm_interval = max(3.0, float(self.bm_interval_var.get() or "15"))
            except ValueError:
                bm_interval = 15.0
            self._bm_runner = BinhManAutoRunner(
                task,
                interval=bm_interval,
                log_cb=lambda m: self.after(0, self._append_bm_log, m),
                status_cb=lambda s: None,
            )
            self._bm_runner.start()
            self.bm_start_btn.configure(text="⏹️ Dừng Bình Man", style="Danger.TButton")
        else:
            self._bm_runner.stop()
            self.bm_start_btn.configure(text="▶️ Bắt đầu Bình Man", style="Success.TButton")


    # =========================================================================
    # TAB 1: NỘI CHÍNH & NGHIÊN CỨU (HỢP NHẤT 3 CỘT)
    # =========================================================================
    def _build_building_tab(self, parent):
        self._build_internal_and_research_tab(parent)

    def _build_internal_and_research_tab(self, parent):
        # Các widget tương thích ngược
        if not hasattr(self, "bld_city_combo"):
            self.bld_city_combo = ttk.Combobox(self, state="readonly", width=18)
        if not hasattr(self, "res_city_combo"):
            self.res_city_combo = ttk.Combobox(self, state="readonly", width=18)
        if not hasattr(self, "bld_slots_combo"):
            self.bld_slots_combo = ttk.Combobox(self, state="readonly", width=3, values=["1", "2", "3"])
            self.bld_slots_combo.set("3")

        # Khung chứa 3 Cột
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, padx=6, pady=6)
        body.columnconfigure(0, weight=2, minsize=240)
        body.columnconfigure(1, weight=3, minsize=320)
        body.columnconfigure(2, weight=3, minsize=320)
        body.rowconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # CỘT 1 (TRÁI): Chức năng, Danh sách thành, Tăng tốc
        # ---------------------------------------------------------------------
        col1 = tk.Frame(body, bg=BG)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # 1. Khung Chức năng
        f_func = ttk.LabelFrame(col1, text="Chức năng", style="Card.TLabelframe")
        f_func.pack(fill="x", padx=2, pady=(0, 4))

        r_f1 = tk.Frame(f_func, bg=BG)
        r_f1.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_f1, text="Làm Mới", style="Action.TButton", command=self.reload).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(r_f1, text="Xem Log", style="Action.TButton", command=self._open_log_window).pack(side="left", expand=True, fill="x", padx=2)

        r_f2 = tk.Frame(f_func, bg=BG)
        r_f2.pack(fill="x", padx=4, pady=2)
        self.bld_start_btn = ttk.Button(r_f2, text="Xây", style="Danger.TButton", command=self._toggle_building)
        self.bld_start_btn.pack(side="left", expand=True, fill="x", padx=2)
        self.res_start_btn = ttk.Button(r_f2, text="Nghiên Cứu", style="Danger.TButton", command=self._toggle_research)
        self.res_start_btn.pack(side="left", expand=True, fill="x", padx=2)
        self.res_monitor_btn = ttk.Button(r_f2, text="Tài Nguyên", style="Danger.TButton", command=self._toggle_resource_monitor)
        self.res_monitor_btn.pack(side="left", expand=True, fill="x", padx=2)

        r_f3 = tk.Frame(f_func, bg=BG)
        r_f3.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_f3, text="Chọn", style="Success.TButton", command=lambda: self._set_selected_base_state(True)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(r_f3, text="Bỏ Chọn", style="Danger.TButton", command=lambda: self._set_selected_base_state(False)).pack(side="left", expand=True, fill="x", padx=2)

        r_f4 = tk.Frame(f_func, bg=BG)
        r_f4.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_f4, text="Chọn Tất Cả", style="Success.TButton", command=lambda: self._select_all_bld_bases(True)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(r_f4, text="Bỏ Tất Cả", style="Danger.TButton", command=lambda: self._select_all_bld_bases(False)).pack(side="left", expand=True, fill="x", padx=2)

        r_f5 = tk.Frame(f_func, bg=BG)
        r_f5.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_f5, text="★ Chọn NC", style="Warning.TButton", command=self._set_selected_base_as_nc).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(r_f5, text="✖ Bỏ NC", style="Action.TButton", command=self._clear_all_nc_bases).pack(side="left", expand=True, fill="x", padx=2)

        # 2. Khung Danh sách thành
        f_bases = ttk.LabelFrame(col1, text="Danh sách thành", style="Card.TLabelframe")
        f_bases.pack(fill="both", expand=True, padx=2, pady=4)

        self.bld_bases_tree = ttk.Treeview(
            f_bases,
            columns=("select", "resource", "research", "type", "id"),
            displaycolumns=("select", "resource", "research"),
            show="tree headings",
            selectmode="browse",
        )
        self.bld_bases_tree.heading("#0", text="Thành")
        self.bld_bases_tree.heading("select", text="Chọn")
        self.bld_bases_tree.heading("resource", text="Tài nguyên")
        self.bld_bases_tree.heading("research", text="NC")

        self.bld_bases_tree.column("#0", width=105)
        self.bld_bases_tree.column("select", width=42, anchor="center")
        self.bld_bases_tree.column("resource", width=68, anchor="center")
        self.bld_bases_tree.column("research", width=38, anchor="center")

        self.bld_bases_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.bld_bases_tree.bind("<ButtonRelease-1>", self._on_bld_bases_click)
        self.bld_bases_tree.bind("<<TreeviewSelect>>", self._on_bld_base_selected)

        # 3. Khung Tăng tốc xây dựng
        f_spd = ttk.LabelFrame(col1, text="Tăng tốc xây dựng", style="Card.TLabelframe")
        f_spd.pack(fill="x", padx=2, pady=(4, 0))
        r_spd = tk.Frame(f_spd, bg=BG)
        r_spd.pack(fill="x", padx=4, pady=4)

        tk.Checkbutton(
            r_spd,
            text="Tốc nhà bằng",
            variable=self.bld_speedup_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)

        self.bld_speedup_item_combo = ttk.Combobox(r_spd, state="readonly", width=8, values=["Ngân Bảo", "Lệnh Bài"])
        self.bld_speedup_item_combo.set("Ngân Bảo")
        self.bld_speedup_item_combo.pack(side="left", padx=2)

        tk.Label(r_spd, text="đến dưới", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        ttk.Entry(r_spd, textvariable=self.bld_speedup_hours_var, width=3).pack(side="left", padx=2)
        tk.Label(r_spd, text="giờ", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=2)

        # 4. Khung Dịch Trại
        f_dt = ttk.LabelFrame(col1, text="🏕️ Dịch Trại", style="Card.TLabelframe")
        f_dt.pack(fill="x", padx=2, pady=(4, 0))

        # Doanh trại
        r_dt1 = tk.Frame(f_dt, bg=BG)
        r_dt1.pack(fill="x", padx=4, pady=2)
        tk.Label(r_dt1, text="Trại:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(2, 4))
        self.dt_camp_combo = ttk.Combobox(r_dt1, state="readonly", width=14)
        self.dt_camp_combo.pack(side="left", fill="x", expand=True, padx=2)
        self.dt_camp_combo.bind("<<ComboboxSelected>>", self._on_dt_camp_selected)

        # Vị trí hiện tại
        r_dt2 = tk.Frame(f_dt, bg=BG)
        r_dt2.pack(fill="x", padx=4, pady=1)
        self.dt_origin_lbl = tk.Label(r_dt2, text="Vị trí: (---, ---)", bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold"))
        self.dt_origin_lbl.pack(side="left", padx=2)

        # Tọa độ đích X, Y
        r_dt3 = tk.Frame(f_dt, bg=BG)
        r_dt3.pack(fill="x", padx=4, pady=2)
        tk.Label(r_dt3, text="Đích X:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        ttk.Entry(r_dt3, textvariable=self.dt_dest_x_var, width=5).pack(side="left", padx=2)

        tk.Label(r_dt3, text="Y:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
        ttk.Entry(r_dt3, textvariable=self.dt_dest_y_var, width=5).pack(side="left", padx=2)

        # Điều khiển Di Trại
        r_dt4 = tk.Frame(f_dt, bg=BG)
        r_dt4.pack(fill="x", padx=4, pady=3)
        self.dt_start_btn = ttk.Button(r_dt4, text="▶ Dịch Trại", style="Success.TButton", command=self._start_ditrai)
        self.dt_start_btn.pack(side="left", fill="x", expand=True, padx=2)
        self.dt_stop_btn = ttk.Button(r_dt4, text="⏹ Dừng", style="Danger.TButton", command=self._stop_ditrai, state="disabled")
        self.dt_stop_btn.pack(side="left", fill="x", expand=True, padx=2)

        # Trạng thái
        r_dt5 = tk.Frame(f_dt, bg=BG)
        r_dt5.pack(fill="x", padx=4, pady=(1, 4))
        self.dt_status_lbl = tk.Label(r_dt5, text="Trạng thái: Sẵn sàng", bg=BG, fg="#4ade80", font=("Segoe UI", 9, "bold"), anchor="w")
        self.dt_status_lbl.pack(side="left", fill="x", expand=True, padx=2)

        # ---------------------------------------------------------------------
        # CỘT 2 (GIỮA): Quản lý nhà & Nâng cấp kỹ thuật
        # ---------------------------------------------------------------------
        col2 = tk.Frame(body, bg=BG)
        col2.grid(row=0, column=1, sticky="nsew", padx=4)
        col2.rowconfigure(0, weight=1)
        col2.rowconfigure(1, weight=1)
        col2.columnconfigure(0, weight=1)

        # 1. Quản lý nhà
        self.bld_queue_frame = ttk.LabelFrame(col2, text="Quản lý nhà", style="Card.TLabelframe")
        self.bld_queue_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        bld_bar = tk.Frame(self.bld_queue_frame, bg=BG)
        bld_bar.pack(fill="x", padx=4, pady=2)
        tk.Label(bld_bar, text="Cấp mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        ttk.Entry(bld_bar, textvariable=self.bld_target_lvl_var, width=3).pack(side="left", padx=2)
        ttk.Button(bld_bar, text="Nâng", style="Success.TButton", command=self._set_bld_target_lvl).pack(side="left", padx=2)
        ttk.Button(bld_bar, text="Hạ", style="Danger.TButton", command=self._lower_bld_target_lvl).pack(side="left", padx=2)
        ttk.Button(bld_bar, text="↑", style="Action.TButton", width=3, command=self._move_bld_up).pack(side="left", padx=2)
        ttk.Button(bld_bar, text="↓", style="Action.TButton", width=3, command=self._move_bld_down).pack(side="left", padx=2)

        bld_sub = tk.Frame(self.bld_queue_frame, bg=BG)
        bld_sub.pack(fill="x", padx=4, pady=(0, 2))
        tk.Checkbutton(
            bld_sub,
            text="Nâng nhà cấp cao nhất",
            variable=self.bld_max_lvl_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)

        self.bld_tree = ttk.Treeview(
            self.bld_queue_frame,
            columns=("select", "pid", "gid", "current_lvl", "target_lvl"),
            displaycolumns=("current_lvl", "target_lvl", "select"),
            show="tree headings",
            selectmode="browse",
        )
        self.bld_tree.heading("#0", text="Nhà")
        self.bld_tree.heading("current_lvl", text="Cấp HT")
        self.bld_tree.heading("target_lvl", text="Cấp MT")
        self.bld_tree.heading("select", text="Chạy")

        self.bld_tree.column("#0", width=130)
        self.bld_tree.column("current_lvl", width=48, anchor="center")
        self.bld_tree.column("target_lvl", width=48, anchor="center")
        self.bld_tree.column("select", width=42, anchor="center")

        self.bld_tree.tag_configure("upgrade", background="#173322", foreground="#86efac")
        self.bld_tree.tag_configure("downgrade", background="#3a1d1d", foreground="#fca5a5")
        self.bld_tree.tag_configure("completed", background=CARD, foreground=MUTED)

        self.bld_tree.pack(fill="both", expand=True, padx=4, pady=2)
        self.bld_tree.bind("<ButtonRelease-1>", self._on_bld_tree_click)
        self.bld_tree.bind("<<TreeviewSelect>>", self._on_bld_tree_selected)
        self._populate_default_buildings()

        # 2. Nâng cấp kỹ thuật
        f_tech = ttk.LabelFrame(col2, text="Nâng cấp kỹ thuật", style="Card.TLabelframe")
        f_tech.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        tech_bar = tk.Frame(f_tech, bg=BG)
        tech_bar.pack(fill="x", padx=4, pady=2)
        tk.Label(tech_bar, text="Cấp mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        ttk.Entry(tech_bar, textvariable=self.res_target_lvl_var, width=3).pack(side="left", padx=2)
        ttk.Button(tech_bar, text="OK", style="Action.TButton", command=self._set_res_target_lvl_all).pack(side="left", padx=2)
        ttk.Button(tech_bar, text="↑", style="Action.TButton", width=3, command=self._move_res_up).pack(side="left", padx=2)
        ttk.Button(tech_bar, text="↓", style="Action.TButton", width=3, command=self._move_res_down).pack(side="left", padx=2)

        tech_sub = tk.Frame(f_tech, bg=BG)
        tech_sub.pack(fill="x", padx=4, pady=(0, 2))
        tk.Checkbutton(
            tech_sub,
            text="墨子 (đến dưới 24h)",
            variable=self.res_art_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=2)
        tk.Checkbutton(
            tech_sub,
            text="Nâng đồng đều",
            variable=self.res_even_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=4)

        self.res_tree = ttk.Treeview(
            f_tech,
            columns=("select", "id", "target_lvl", "current_lvl"),
            displaycolumns=("current_lvl", "target_lvl", "select"),
            show="tree headings",
            selectmode="browse",
        )
        self.res_tree.heading("#0", text="Kỹ Thuật")
        self.res_tree.heading("current_lvl", text="Cấp HT")
        self.res_tree.heading("target_lvl", text="Cấp MT")
        self.res_tree.heading("select", text="Chạy")

        self.res_tree.column("#0", width=130)
        self.res_tree.column("current_lvl", width=48, anchor="center")
        self.res_tree.column("target_lvl", width=48, anchor="center")
        self.res_tree.column("select", width=42, anchor="center")

        self.res_tree.tag_configure("upgrade", background="#173322", foreground="#86efac")
        self.res_tree.tag_configure("downgrade", background="#3a1d1d", foreground="#fca5a5")
        self.res_tree.tag_configure("completed", background=CARD, foreground=MUTED)

        self.res_tree.pack(fill="both", expand=True, padx=4, pady=2)
        self.res_tree.bind("<ButtonRelease-1>", self._on_res_tree_click)
        self.res_tree.bind("<<TreeviewSelect>>", self._on_res_tree_selected)
        self._populate_all_techs()

        # ---------------------------------------------------------------------
        # CỘT 3 (PHẢI): Ngưỡng tài nguyên/rương, Phụ trợ, Chuyển quân, Lưu/Load
        # ---------------------------------------------------------------------
        col3 = tk.Frame(body, bg=BG)
        col3.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        # 1. Thiết lập ngưỡng tài nguyên và rương
        f_res_thresh = ttk.LabelFrame(col3, text="Thiết lập ngưỡng tài nguyên và rương", style="Card.TLabelframe")
        f_res_thresh.pack(fill="x", padx=2, pady=(0, 4))

        tk.Checkbutton(
            f_res_thresh,
            text="Mở khi thiếu lúc xây dựng",
            variable=self.bld_open_box_var,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=6, pady=(2, 2))

        r_v = tk.Frame(f_res_thresh, bg=BG)
        r_v.pack(fill="x", padx=6, pady=1)
        tk.Label(r_v, text="Vàng:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_v, textvariable=self.res_gold_thresh_var, width=12).pack(side="left", padx=4)

        r_tn1 = tk.Frame(f_res_thresh, bg=BG)
        r_tn1.pack(fill="x", padx=6, pady=1)
        tk.Label(r_tn1, text="Gỗ (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn1, textvariable=self.res_wood_pct_var, width=4).pack(side="left", padx=(2, 10))
        tk.Label(r_tn1, text="Sắt (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn1, textvariable=self.res_iron_pct_var, width=4).pack(side="left", padx=2)

        r_tn2 = tk.Frame(f_res_thresh, bg=BG)
        r_tn2.pack(fill="x", padx=6, pady=1)
        tk.Label(r_tn2, text="Đá (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn2, textvariable=self.res_stone_pct_var, width=4).pack(side="left", padx=(2, 10))
        tk.Label(r_tn2, text="Thực (%):", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_tn2, textvariable=self.res_food_pct_var, width=4).pack(side="left", padx=2)

        box_options = [
            "1: 民生之囊 - Dân Sinh Bảo Nang",
            "11: 民生之匣 - Dân Sinh Chi Hạp",
            "16: 民生之椟 - Dân Sinh Chi Độc",
            "24: 民生之鼎 - Dân Sinh Bảo Đỉnh",
            "35: 白金资源礼盒 - Bạch Kim Tài Nguyên Lễ Hộp",
        ]

        r_box1 = tk.Frame(f_res_thresh, bg=BG)
        r_box1.pack(fill="x", padx=6, pady=2)
        tk.Label(r_box1, text="Rương Vàng:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.res_gold_box_combo = ttk.Combobox(r_box1, state="readonly", width=32, values=box_options)
        self.res_gold_box_combo.set(box_options[1])
        self.res_gold_box_combo.pack(side="left", fill="x", expand=True, padx=4)

        r_box2 = tk.Frame(f_res_thresh, bg=BG)
        r_box2.pack(fill="x", padx=6, pady=2)
        tk.Label(r_box2, text="Rương TN:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.res_tn_box_combo = ttk.Combobox(r_box2, state="readonly", width=32, values=box_options)
        self.res_tn_box_combo.set(box_options[3])
        self.res_tn_box_combo.pack(side="left", fill="x", expand=True, padx=4)
        self.bld_box_combo = self.res_tn_box_combo

        ttk.Button(f_res_thresh, text="Áp Dụng Thiết Lập", style="Success.TButton", command=self._apply_resource_settings).pack(pady=4)

        # 2. Chức năng phụ trợ
        f_aux = ttk.LabelFrame(col3, text="Chức năng phụ trợ", style="Card.TLabelframe")
        f_aux.pack(fill="x", padx=2, pady=4)

        r_aux1 = tk.Frame(f_aux, bg=BG)
        r_aux1.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(r_aux1, text="Thưởng hàng ngày", variable=self.aux_daily_reward_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        tk.Checkbutton(r_aux1, text="Tự an ủi", variable=self.aux_comfort_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)

        r_aux2 = tk.Frame(f_aux, bg=BG)
        r_aux2.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(r_aux2, text="DS kiến trúc", variable=self.aux_boost_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        self.aux_boost_time_lbl = tk.Label(r_aux2, text="(Còn: --)", bg=BG, fg="#4ade80", font=("Segoe UI", 8, "bold"))
        self.aux_boost_time_lbl.pack(side="left", padx=2)

        r_aux3 = tk.Frame(f_aux, bg=BG)
        r_aux3.pack(fill="x", padx=4, pady=2)
        tk.Checkbutton(r_aux3, text="Cống quận", variable=self.aux_tribute_var, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, font=("Segoe UI", 9)).pack(side="left", padx=2)
        self.aux_tribute_bld_combo = ttk.Combobox(r_aux3, state="readonly", width=16, values=["官府 (Quan Phủ)", "城墙 (Tường Thành)"])
        self.aux_tribute_bld_combo.set("官府 (Quan Phủ)")
        self.aux_tribute_bld_combo.pack(side="left", padx=4)

        # 3. Chuyển Quân Giới
        f_logis = ttk.LabelFrame(col3, text="Chuyển Quân Giới", style="Card.TLabelframe")
        f_logis.pack(fill="both", expand=True, padx=2, pady=4)

        r_l1 = tk.Frame(f_logis, bg=BG)
        r_l1.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l1, text="Từ", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_from_city_combo = ttk.Combobox(r_l1, state="readonly", width=11)
        self.log_from_city_combo.pack(side="left", padx=2)
        tk.Label(r_l1, text="Đến", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_to_city_combo = ttk.Combobox(r_l1, state="readonly", width=11)
        self.log_to_city_combo.pack(side="left", padx=2)

        r_l2 = tk.Frame(f_logis, bg=BG)
        r_l2.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l2, text="Vận ch", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.log_army_combo = ttk.Combobox(r_l2, state="readonly", width=10, values=["1: Bộ binh", "2: Kỵ binh", "3: Cung binh"])
        self.log_army_combo.set("1: Bộ binh")
        self.log_army_combo.pack(side="left", padx=2)
        tk.Label(r_l2, text="SL", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_l2, textvariable=self.log_amount_var, width=5).pack(side="left", padx=2)

        r_l3 = tk.Frame(f_logis, bg=BG)
        r_l3.pack(fill="x", padx=4, pady=1)
        tk.Label(r_l3, text="Lặp lại", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        ttk.Entry(r_l3, textvariable=self.log_interval_var, width=4).pack(side="left", padx=2)
        tk.Label(r_l3, text="giây", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=2)

        r_l_btn = tk.Frame(f_logis, bg=BG)
        r_l_btn.pack(fill="x", padx=4, pady=2)
        ttk.Button(r_l_btn, text="Add", style="Success.TButton", command=self._add_army_transfer_order).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(r_l_btn, text="Xóa", style="Danger.TButton", command=self._delete_army_transfer_order).pack(side="left", expand=True, fill="x", padx=2)

        self.log_transfers_tree = ttk.Treeview(
            f_logis,
            columns=("route", "amount", "army"),
            show="headings",
            selectmode="browse",
            height=3,
        )
        self.log_transfers_tree.heading("route", text="Từ – Đến")
        self.log_transfers_tree.heading("amount", text="SL")
        self.log_transfers_tree.heading("army", text="Quân giới")
        self.log_transfers_tree.column("route", width=120)
        self.log_transfers_tree.column("amount", width=40, anchor="center")
        self.log_transfers_tree.column("army", width=70, anchor="center")
        self.log_transfers_tree.pack(fill="both", expand=True, padx=4, pady=2)

        # 4. Hàng nút chân trang Cột 3
        footer = tk.Frame(col3, bg=BG)
        footer.pack(fill="x", padx=2, pady=(4, 0))
        ttk.Button(footer, text="Re-Login", style="Action.TButton", command=self._do_relogin).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(footer, text="💾 Lưu", style="Success.TButton", command=self._save_unified_profile_dialog).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(footer, text="📂 Load", style="Action.TButton", command=self._load_unified_profile_dialog).pack(side="left", expand=True, fill="x", padx=2)

    def _append_bld_log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        for w in list(self._active_log_texts):
            self._append_text_buffer(w, line)

    def _append_logis_log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        for w in list(self._active_log_texts):
            self._append_text_buffer(w, line)

    def _open_log_window(self):
        if hasattr(self, "_log_win") and self._log_win and self._log_win.winfo_exists():
            self._log_win.lift()
            self._log_win.focus_force()
            return

        win = tk.Toplevel(self)
        win.title("📜 Nhật Ký Hoạt Động (Nội Chính & Nghiên Cứu)")
        win.geometry("750x450")
        win.configure(bg=BG)
        self._log_win = win

        top_bar = tk.Frame(win, bg=BG)
        top_bar.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(
            top_bar,
            text="Nhật ký chi tiết các tác vụ Nội Chính, Xây Dựng & Nghiên Cứu",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        f_txt = tk.Frame(win, bg=BG)
        f_txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        sb = ttk.Scrollbar(f_txt, orient="vertical")
        txt = tk.Text(
            f_txt,
            bg="#111420",
            fg=FG,
            insertbackground=FG,
            font=("Consolas", 9),
            yscrollcommand=sb.set,
            wrap="word",
        )
        sb.config(command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        if txt not in self._active_log_texts:
            self._active_log_texts.append(txt)

        def clear_log():
            txt.delete("1.0", "end")
            if hasattr(self, "bld_log_text") and self.bld_log_text:
                self.bld_log_text.delete("1.0", "end")
            if hasattr(self, "logis_log_text") and self.logis_log_text:
                self.logis_log_text.delete("1.0", "end")

        ttk.Button(top_bar, text="🗑️ Xóa nhật ký", style="Danger.TButton", command=clear_log).pack(side="right", padx=4)

        # Sao chép các dòng hiện có từ bld_log_text
        if hasattr(self, "bld_log_text") and self.bld_log_text:
            try:
                existing = self.bld_log_text.get("1.0", "end-1c")
                if existing:
                    txt.insert("end", existing + "\n")
                    txt.see("end")
            except Exception:
                pass

        def on_close():
            if txt in self._active_log_texts:
                self._active_log_texts.remove(txt)
            win.destroy()
            self._log_win = None

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _lower_bld_target_lvl(self):
        sel = self.bld_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 công trình trong bảng!")
            return
        lvl = 0
        self.bld_target_lvl_var.set("0")
        for item in sel:
            if not self.bld_tree.exists(item):
                continue
            if item.startswith("group_"):
                for child in self.bld_tree.get_children(item):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[4] = lvl
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                self._update_group_summary(item)
            else:
                vals = list(self.bld_tree.item(item, "values"))
                vals[4] = lvl
                self.bld_tree.item(item, values=vals)
                self._update_bld_tree_row_style(item)
                parent = self.bld_tree.parent(item)
                if parent and parent.startswith("group_"):
                    self._update_group_summary(parent)

        self._save_current_bld_tree_to_cache()

    def _set_selected_base_state(self, state: bool):
        sel = self.bld_bases_tree.selection()
        if not sel:
            return
        item = sel[0]
        vals = list(self.bld_bases_tree.item(item, "values"))
        sym = "☑" if state else "☐"
        vals[0] = sym
        self.bld_bases_tree.item(item, values=vals)
        try:
            base_id = int(item)
        except ValueError:
            base_id = int(vals[4]) if len(vals) > 4 else int(vals[2]) if len(vals) > 2 else 0
        if state:
            self._selected_building_cities.add(base_id)
        else:
            self._selected_building_cities.discard(base_id)

    def _set_selected_base_as_nc(self):
        sel = self.bld_bases_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 thành trong danh sách thành để làm Thành Nghiên Cứu!")
            return
        item = sel[0]
        try:
            base_id = int(item)
        except ValueError:
            vals = list(self.bld_bases_tree.item(item, "values"))
            base_id = int(vals[4]) if len(vals) > 4 else int(vals[2]) if len(vals) > 2 else 0

        self._research_city_id = base_id
        for iid in self.bld_bases_tree.get_children(""):
            vals = list(self.bld_bases_tree.item(iid, "values"))
            if len(vals) > 2:
                vals[2] = "★" if iid == item else "☐"
                self.bld_bases_tree.item(iid, values=vals)

        if hasattr(self, "res_city_combo") and self.roster:
            cities = self.roster.cities if self.roster.cities else self.roster.bases
            for idx, c in enumerate(cities):
                if c.id == base_id:
                    self.res_city_combo.current(idx)
                    break
        base_name = self.bld_bases_tree.item(item, "text")
        self._append_bld_log(f"★ Đã chọn '{base_name}' làm Thành Nghiên Cứu trọng điểm.")

    def _clear_all_nc_bases(self):
        self._research_city_id = None
        for iid in self.bld_bases_tree.get_children(""):
            vals = list(self.bld_bases_tree.item(iid, "values"))
            if len(vals) > 2:
                vals[2] = "☐"
                self.bld_bases_tree.item(iid, values=vals)
        self._append_bld_log("✖ Đã bỏ chọn tất cả Thành Nghiên Cứu.")

    def _apply_resource_settings(self):
        gold_th = self.res_gold_thresh_var.get()
        w_pct = self.res_wood_pct_var.get()
        i_pct = self.res_iron_pct_var.get()
        s_pct = self.res_stone_pct_var.get()
        f_pct = self.res_food_pct_var.get()
        g_box = self.res_gold_box_combo.get() if hasattr(self, "res_gold_box_combo") else ""
        tn_box = self.res_tn_box_combo.get() if hasattr(self, "res_tn_box_combo") else ""
        self._append_bld_log(
            f"✅ Áp dụng thiết lập tài nguyên: Vàng<{gold_th}, TN G/S/Đ/T<{w_pct}%/{i_pct}%/{s_pct}%/{f_pct}%, Rương: {g_box.split(':')[0]} / {tn_box.split(':')[0]}"
        )
        messagebox.showinfo("Thành công", "Đã lưu và áp dụng thiết lập ngưỡng tài nguyên & rương!")

    def _toggle_resource_monitor(self):
        if not self._res_monitor_running:
            target_cids = list(self._selected_resource_cities)
            if not target_cids:
                if self._current_bld_city_id:
                    target_cids = [self._current_bld_city_id]
                elif hasattr(self, "bld_bases_tree"):
                    children = self.bld_bases_tree.get_children("")
                    if children:
                        try:
                            target_cids = [int(children[0])]
                        except ValueError:
                            pass
            if not target_cids:
                messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn cột 'Tài nguyên' cho ít nhất 1 thành!")
                return

            self._res_monitor_running = True
            self.res_monitor_btn.configure(text="Đang Giữ TN", style="Success.TButton")
            self._append_bld_log(f"▶️ Bắt đầu giám sát ngưỡng tài nguyên cho {len(target_cids)} thành...")
            self._res_monitor_thread = threading.Thread(target=self._run_resource_monitor_loop, daemon=True)
            self._res_monitor_thread.start()
        else:
            self._res_monitor_running = False
            self.res_monitor_btn.configure(text="Tài Nguyên", style="Danger.TButton")
            self._append_bld_log("⏹️ Đã dừng giám sát tài nguyên.")

    def _run_resource_monitor_loop(self):
        while self._res_monitor_running:
            target_cids = list(self._selected_resource_cities)
            if not target_cids and self._current_bld_city_id:
                target_cids = [self._current_bld_city_id]

            for cid in target_cids:
                if not self._res_monitor_running:
                    break
                try:
                    cname = f"Thành {cid}"
                    if self.roster:
                        b = self.roster.base_by_id(cid)
                        if b:
                            cname = b.name

                    # 1. Gọi City.ashx?id=20 lấy tài nguyên hiện tại
                    resp = self.gateway.call("City.ashx", 20, {"tid": str(cid), "_": ""}) or {}
                    money = int(resp.get("money", resp.get("gold", 0)))
                    wood = int(resp.get("wood", 0))
                    iron = int(resp.get("iron", 0))
                    stone = int(resp.get("stone", 0))
                    food = int(resp.get("food", 0))
                    max_storage = int(resp.get("max_storage", resp.get("storage", 1000000)))
                    if max_storage <= 0:
                        max_storage = 1000000

                    # 2. Kiểm tra ngưỡng vàng
                    try:
                        gold_th = int(self.res_gold_thresh_var.get().replace(",", "").replace(".", "").strip())
                    except ValueError:
                        gold_th = 100000000

                    if money < gold_th:
                        g_box_str = self.res_gold_box_combo.get() if hasattr(self, "res_gold_box_combo") else "11"
                        try:
                            g_box_id = int(g_box_str.split(":")[0].strip())
                        except (ValueError, IndexError):
                            g_box_id = 11
                        r_box = self.gateway.call("Common.ashx", 48, {"lBoxID": str(g_box_id), "_": ""}) or {}
                        ret = r_box.get("ret", 0)
                        if ret == 0:
                            self.after(0, self._append_bld_log, f"💰 [{cname}] Vàng={money:,} < ngưỡng {gold_th:,}: Đã mở rương vàng #{g_box_id}.")
                        else:
                            self.after(0, self._append_bld_log, f"⚠️ [{cname}] Mở rương vàng #{g_box_id} thất bại (mã {ret}).")

                    # 3. Kiểm tra ngưỡng khoáng sản %
                    try:
                        w_pct = float(self.res_wood_pct_var.get()) / 100.0
                        i_pct = float(self.res_iron_pct_var.get()) / 100.0
                        s_pct = float(self.res_stone_pct_var.get()) / 100.0
                        f_pct = float(self.res_food_pct_var.get()) / 100.0
                    except ValueError:
                        w_pct = i_pct = s_pct = f_pct = 0.7

                    need_tn = (
                        wood < max_storage * w_pct
                        or iron < max_storage * i_pct
                        or stone < max_storage * s_pct
                        or food < max_storage * f_pct
                    )

                    if need_tn:
                        tn_box_str = self.res_tn_box_combo.get() if hasattr(self, "res_tn_box_combo") else "24"
                        try:
                            tn_box_id = int(tn_box_str.split(":")[0].strip())
                        except (ValueError, IndexError):
                            tn_box_id = 24
                        r_box = self.gateway.call("Common.ashx", 48, {"lBoxID": str(tn_box_id), "_": ""}) or {}
                        ret = r_box.get("ret", 0)
                        if ret == 0:
                            self.after(
                                0,
                                self._append_bld_log,
                                f"📦 [{cname}] Khoáng sản dưới ngưỡng: Đã mở rương TN #{tn_box_id} (Kho {max_storage:,}).",
                            )
                        else:
                            self.after(0, self._append_bld_log, f"⚠️ [{cname}] Mở rương TN #{tn_box_id} thất bại (mã {ret}).")

                except (RuntimeError, tk.TclError):
                    break
                except Exception as e:
                    try:
                        self.after(0, self._append_bld_log, f"❌ Lỗi kiểm tra tài nguyên thành {cid}: {e}")
                    except Exception:
                        pass

            for _ in range(30):
                if not self._res_monitor_running:
                    break
                time.sleep(1)

    def _check_and_update_boost_status(self, async_check: bool = True):
        """Kiểm tra thời gian còn lại của DS kiến trúc (xây 3 công trình) và tự kích hoạt nếu hết hạn."""
        def run_check():
            if not self.gateway:
                return
            try:
                city_id = getattr(self, "_current_bld_city_id", 0) or 0
                resp = self.gateway.call("Common.ashx", 77, {"cid": str(city_id), "_": ""}) or {}
                plus_finish = 0

                # 1. Kiểm tra trường plus_finish ở root (nếu có)
                if "plus_finish" in resp:
                    try:
                        plus_finish = int(resp["plus_finish"])
                    except (ValueError, TypeError):
                        plus_finish = 0

                # 2. Kiểm tra danh sách thành trong resp["list"]
                if plus_finish <= 0:
                    city_list = resp.get("list", [])
                    target_city = None
                    for c_info in city_list:
                        if isinstance(c_info, dict):
                            c_cid = c_info.get("cid") or c_info.get("id") or c_info.get("city_id")
                            if not city_id or c_cid == city_id:
                                target_city = c_info
                                break
                        elif isinstance(c_info, (list, tuple)) and len(c_info) >= 4:
                            if not city_id or c_info[0] == city_id:
                                target_city = c_info
                                break

                    if target_city is None and city_list:
                        target_city = city_list[0]

                    if isinstance(target_city, dict):
                        plus_finish = target_city.get("plus_finish") or target_city.get("time_left") or 0
                    elif isinstance(target_city, (list, tuple)) and len(target_city) >= 4:
                        # [city_id, name, val2, val3, ...]
                        # val3: thời hạn 建筑排程 (DS kiến trúc), val2: 20% speedup
                        val2 = target_city[2]
                        val3 = target_city[3]
                        try:
                            val3 = int(val3)
                        except (ValueError, TypeError):
                            val3 = 0
                        try:
                            val2 = int(val2)
                        except (ValueError, TypeError):
                            val2 = 0
                        plus_finish = val3 if val3 > 0 else val2

                now = time.time()
                remaining = 0
                if isinstance(plus_finish, str) and ":" in plus_finish:
                    # Hỗ trợ định dạng chuỗi "2234:39:14"
                    parts = plus_finish.split(":")
                    if len(parts) == 3:
                        try:
                            remaining = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        except ValueError:
                            remaining = 0
                else:
                    try:
                        plus_finish = int(plus_finish)
                    except (ValueError, TypeError):
                        plus_finish = 0
                    if plus_finish > 1_000_000_000:
                        remaining = max(0, int(plus_finish - now))
                    elif plus_finish > 0:
                        remaining = plus_finish

                def _update_ui(text, fg):
                    if hasattr(self, "aux_boost_time_lbl") and self.aux_boost_time_lbl.winfo_exists():
                        self.aux_boost_time_lbl.configure(text=text, fg=fg)

                if remaining > 0:
                    h = remaining // 3600
                    m = (remaining % 3600) // 60
                    s = remaining % 60
                    t_str = f"{h}:{m:02d}:{s:02d}"
                    if threading.current_thread() is threading.main_thread():
                        _update_ui(f"(Còn: {t_str})", "#4ade80")
                    else:
                        try:
                            self.after(0, lambda: _update_ui(f"(Còn: {t_str})", "#4ade80"))
                        except RuntimeError:
                            pass
                else:
                    if threading.current_thread() is threading.main_thread():
                        _update_ui("(Hết hạn)", "#f87171")
                    else:
                        try:
                            self.after(0, lambda: _update_ui("(Hết hạn)", "#f87171"))
                        except RuntimeError:
                            pass
                    if self.aux_boost_var.get():
                        now_ts = time.time()
                        last_act = getattr(self, "_last_boost_act_time", 0)
                        if now_ts - last_act > 60:
                            self._last_boost_act_time = now_ts
                            msg = "⚡ DS kiến trúc đã hết hạn. Đang tự kích hoạt lại (xây 3 nhà)..."
                            if threading.current_thread() is threading.main_thread():
                                self._append_bld_log(msg)
                            else:
                                try:
                                    self.after(0, self._append_bld_log, msg)
                                except RuntimeError:
                                    pass
                            act_resp = self.gateway.call(
                                "OPT.ashx",
                                69,
                                {"type": "3", "param1": "0", "param2": "0", "paytype": "2", "_": ""},
                            ) or {}
                            ret = act_resp.get("ret", 0)
                            if ret == 0:
                                ok_msg = "✅ Kích hoạt thành công DS kiến trúc (3 vị trí xây dựng)!"
                                if threading.current_thread() is threading.main_thread():
                                    self._append_bld_log(ok_msg)
                                else:
                                    try:
                                        self.after(0, self._append_bld_log, ok_msg)
                                    except RuntimeError:
                                        pass
                                time.sleep(1)
                                self._check_and_update_boost_status(async_check=async_check)
                            else:
                                fail_msg = f"⚠️ Kích hoạt DS kiến trúc thất bại (mã {ret})."
                                if threading.current_thread() is threading.main_thread():
                                    self._append_bld_log(fail_msg)
                                else:
                                    try:
                                        self.after(0, self._append_bld_log, fail_msg)
                                    except RuntimeError:
                                        pass
            except Exception as e:
                logger.debug(f"Lỗi kiểm tra DS kiến trúc: {e}")

        if async_check:
            t = threading.Thread(target=run_check, daemon=True)
            t.start()
            return t
        else:
            run_check()

    def _do_relogin(self):
        if not self.gateway:
            messagebox.showwarning("Cảnh báo", "Chưa khởi tạo gateway!")
            return
        def run_relogin():
            try:
                self.after(0, self._append_bld_log, "🔑 Đang thực hiện đăng nhập lại tài khoản...")
                ok = False
                if self.gateway.relogin_callback:
                    ok = bool(self.gateway.relogin_callback())
                if ok:
                    self.after(0, self._append_bld_log, "✅ Đăng nhập lại thành công! Đang tải lại dữ liệu...")
                    self.after(0, self.reload)
                else:
                    self.after(0, self._append_bld_log, "❌ Đăng nhập lại không thành công hoặc không có relogin callback.")
            except Exception as e:
                self.after(0, self._append_bld_log, f"❌ Lỗi đăng nhập lại: {e}")
        threading.Thread(target=run_relogin, daemon=True).start()

    def _add_army_transfer_order(self):
        f_city = self.log_from_city_combo.get()
        t_city = self.log_to_city_combo.get()
        if not f_city or not t_city or f_city == t_city:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành đi và thành đến khác nhau!")
            return
        army = self.log_army_combo.get()
        amount = self.log_amount_var.get().strip() or "1"
        route = f"{f_city} ➔ {t_city}"
        self.log_transfers_tree.insert("", "end", values=(route, amount, army))
        self._append_bld_log(f"➕ Thêm lệnh chuyển quân giới: {route} | SL: {amount} | {army}")

    def _delete_army_transfer_order(self):
        sel = self.log_transfers_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 lệnh chuyển quân trong bảng để xóa!")
            return
        for item in sel:
            self.log_transfers_tree.delete(item)
        self._append_bld_log("🗑️ Đã xóa lệnh chuyển quân giới đã chọn.")

    def _get_bld_row_tag(self, cur_lvl: int, target_lvl: int) -> str:
        if cur_lvl < target_lvl:
            return "upgrade"
        elif cur_lvl > target_lvl:
            return "downgrade"
        return "completed"

    def _update_group_summary(self, group_iid: str):
        """Cập nhật trạng thái chọn, dải cấp độ hiện tại và tag màu cho dòng cha của nhóm."""
        if not hasattr(self, "bld_tree") or not self.bld_tree.exists(group_iid):
            return
        children = self.bld_tree.get_children(group_iid)
        if not children:
            return
        p_vals = list(self.bld_tree.item(group_iid, "values"))
        all_en = True
        any_en = False
        cur_lvls = []
        target_lvls = []
        for c in children:
            c_vals = self.bld_tree.item(c, "values")
            en = c_vals[0] == "☑"
            if en:
                any_en = True
            else:
                all_en = False
            try:
                cur_lvls.append(int(c_vals[3]))
                target_lvls.append(int(c_vals[4]))
            except (ValueError, TypeError):
                pass

        p_vals[0] = "☑" if all_en else ("▣" if any_en else "☐")
        if cur_lvls and target_lvls:
            min_cur, max_cur = min(cur_lvls), max(cur_lvls)
            p_vals[3] = str(min_cur) if min_cur == max_cur else f"{min_cur} - {max_cur}"
            p_vals[4] = max(target_lvls)
            tag = "completed" if all(c >= t for c, t in zip(cur_lvls, target_lvls)) else "upgrade"
            self.bld_tree.item(group_iid, values=p_vals, tags=(tag,))
        else:
            self.bld_tree.item(group_iid, values=p_vals)

    def _update_bld_tree_row_style(self, iid: str):
        if not hasattr(self, "bld_tree") or not self.bld_tree.exists(iid):
            return
        if iid.startswith("group_"):
            self._update_group_summary(iid)
            return
        vals = self.bld_tree.item(iid, "values")
        if len(vals) >= 5:
            try:
                cur_lvl = int(vals[3])
                target_lvl = int(vals[4])
                tag = self._get_bld_row_tag(cur_lvl, target_lvl)
                self.bld_tree.item(iid, tags=(tag,))
            except (ValueError, TypeError):
                pass
        parent = self.bld_tree.parent(iid)
        if parent and parent.startswith("group_"):
            self._update_group_summary(parent)

    def _populate_default_buildings(self):
        default_plots = [
            {"pid": 1, "gid": 1, "name": "官府 - Quan Phủ", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 2, "gid": 2, "name": "城墙 - Tường Thành", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 3, "gid": 3, "name": "民房 - Nhà Dân", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 4, "gid": 4, "name": "仓库 - Kho", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 5, "gid": 5, "name": "鸿胪寺 - Hồng Lư Tự", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 6, "gid": 6, "name": "大学殿 - Đại Học Điện", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 7, "gid": 7, "name": "客栈 - Quán Trọ", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 8, "gid": 8, "name": "酒馆 - Tửu Quán", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 9, "gid": 9, "name": "聚贤楼 - Tụ Hiền Lâu", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 10, "gid": 10, "name": "点将台 - Điểm Tướng Đài", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 11, "gid": 11, "name": "市场 - Chợ", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 12, "gid": 12, "name": "驿站 - Dịch Trạm", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 13, "gid": 13, "name": "兵器铺 - Xưởng Binh Khí", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 14, "gid": 14, "name": "防具铺 - Xưởng Khôi Giáp", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 15, "gid": 15, "name": "车马间 - Xưởng Ngựa", "cur_lvl": 0, "target_level": 20, "enabled": False},
            {"pid": 16, "gid": 16, "name": "校场 - Binh Trường", "cur_lvl": 0, "target_level": 20, "enabled": False},
        ]
        self._render_bld_tree_from_plans(default_plots)

    def _move_bld_up(self):
        sel = self.bld_tree.selection()
        if not sel:
            return
        item = sel[0]
        parent = self.bld_tree.parent(item)
        target = parent if parent else item
        roots = list(self.bld_tree.get_children(""))
        if target in roots:
            idx = roots.index(target)
            if idx > 0:
                self.bld_tree.move(target, "", idx - 1)
                self._save_current_bld_tree_to_cache()

    def _move_bld_down(self):
        sel = self.bld_tree.selection()
        if not sel:
            return
        item = sel[0]
        parent = self.bld_tree.parent(item)
        target = parent if parent else item
        roots = list(self.bld_tree.get_children(""))
        if target in roots:
            idx = roots.index(target)
            if idx < len(roots) - 1:
                self.bld_tree.move(target, "", idx + 1)
                self._save_current_bld_tree_to_cache()

    def _select_all_bld(self, state: bool):
        sym = "☑" if state else "☐"
        for root_iid in self.bld_tree.get_children(""):
            if root_iid.startswith("group_"):
                p_vals = list(self.bld_tree.item(root_iid, "values"))
                p_vals[0] = sym
                self.bld_tree.item(root_iid, values=p_vals)
                for child in self.bld_tree.get_children(root_iid):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[0] = sym
                    self.bld_tree.item(child, values=c_vals)
            else:
                vals = list(self.bld_tree.item(root_iid, "values"))
                vals[0] = sym
                self.bld_tree.item(root_iid, values=vals)
        self._save_current_bld_tree_to_cache()

    def _set_bld_target_lvl(self):
        sel = self.bld_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 công trình trong bảng!")
            return
        try:
            lvl = int(self.bld_target_lvl_var.get())
            if lvl < 0 or lvl > 40:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 0 đến 40 (0: dỡ bỏ)!")
            return

        for item in sel:
            if not self.bld_tree.exists(item):
                continue
            if item.startswith("group_"):
                for child in self.bld_tree.get_children(item):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[4] = lvl
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                self._update_group_summary(item)
            else:
                vals = list(self.bld_tree.item(item, "values"))
                vals[4] = lvl
                self.bld_tree.item(item, values=vals)
                self._update_bld_tree_row_style(item)
                parent = self.bld_tree.parent(item)
                if parent and parent.startswith("group_"):
                    self._update_group_summary(parent)

        self._save_current_bld_tree_to_cache()

    def _set_bld_target_lvl_all(self):
        try:
            lvl = int(self.bld_target_lvl_var.get())
            if lvl < 0 or lvl > 40:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 0 đến 40 (0: dỡ bỏ)!")
            return

        count = 0
        for root_iid in self.bld_tree.get_children(""):
            if root_iid.startswith("group_"):
                for child in self.bld_tree.get_children(root_iid):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[4] = lvl
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                    count += 1
                self._update_group_summary(root_iid)
            else:
                vals = list(self.bld_tree.item(root_iid, "values"))
                vals[4] = lvl
                self.bld_tree.item(root_iid, values=vals)
                self._update_bld_tree_row_style(root_iid)
                count += 1

        self._save_current_bld_tree_to_cache()
        self._append_bld_log(f"🎯 Đã đặt Cấp mục tiêu = {lvl} cho tất cả {count} công trình.")

    def _on_bld_tree_selected(self, _event=None):
        sel = self.bld_tree.selection()
        if not sel:
            return
        item = sel[0]
        if not self.bld_tree.exists(item):
            return
        vals = self.bld_tree.item(item, "values")
        if len(vals) > 4:
            try:
                self.bld_target_lvl_var.set(str(vals[4]))
            except Exception:
                pass

    def _on_bld_tree_click(self, event):
        item = self.bld_tree.identify_row(event.y)
        col = self.bld_tree.identify_column(event.x)
        if not item or not self.bld_tree.exists(item):
            return

        # displaycolumns=("current_lvl", "target_lvl", "select")
        # identify_column: #0 (text), #1 (current_lvl - "Cấp HT"), #2 (target_lvl - "Cấp MT"), #3 (select - "Chạy")
        is_select_col = (col == "#3")

        if not is_select_col:
            self.bld_tree.selection_set(item)

        if item.startswith("group_"):
            vals = list(self.bld_tree.item(item, "values"))
            if is_select_col:
                new_state = "☐" if vals[0] in ("☑", "▣") else "☑"
                vals[0] = new_state
                self.bld_tree.item(item, values=vals)
                for child in self.bld_tree.get_children(item):
                    c_vals = list(self.bld_tree.item(child, "values"))
                    c_vals[0] = new_state
                    self.bld_tree.item(child, values=c_vals)
                    self._update_bld_tree_row_style(child)
                self._update_group_summary(item)
            if len(vals) > 4:
                self.bld_target_lvl_var.set(str(vals[4]))
            self._save_current_bld_tree_to_cache()
            return

        vals = list(self.bld_tree.item(item, "values"))
        parent = self.bld_tree.parent(item)
        if is_select_col:
            vals[0] = "☑" if vals[0] == "☐" else "☐"
            self.bld_tree.item(item, values=vals)
            if parent and parent.startswith("group_"):
                self._update_group_summary(parent)
            self._save_current_bld_tree_to_cache()

        if len(vals) > 4:
            self.bld_target_lvl_var.set(str(vals[4]))

    def _on_bld_bases_click(self, event):
        item = self.bld_bases_tree.identify_row(event.y)
        col = self.bld_bases_tree.identify_column(event.x)
        if not item or not self.bld_bases_tree.exists(item):
            return
        vals = list(self.bld_bases_tree.item(item, "values"))
        try:
            base_id = int(item)
        except ValueError:
            base_id = int(vals[4]) if len(vals) > 4 else int(vals[2]) if len(vals) > 2 else 0

        if col == "#1":
            if vals[0] == "☑":
                vals[0] = "☐"
                self._selected_building_cities.discard(base_id)
            else:
                vals[0] = "☑"
                self._selected_building_cities.add(base_id)
            self.bld_bases_tree.item(item, values=vals)
        elif col == "#2":
            is_res = vals[1] if len(vals) > 1 else "☐"
            if is_res == "☑":
                vals[1] = "☐"
                self._selected_resource_cities.discard(base_id)
            else:
                vals[1] = "☑"
                self._selected_resource_cities.add(base_id)
            self.bld_bases_tree.item(item, values=vals)
        elif col == "#3":
            is_nc = vals[2] if len(vals) > 2 else "☐"
            if is_nc == "★":
                vals[2] = "☐"
                self._research_city_id = None
                self.bld_bases_tree.item(item, values=vals)
            else:
                self._research_city_id = base_id
                for iid in self.bld_bases_tree.get_children(""):
                    i_vals = list(self.bld_bases_tree.item(iid, "values"))
                    if len(i_vals) > 2:
                        i_vals[2] = "★" if iid == item else "☐"
                        self.bld_bases_tree.item(iid, values=i_vals)
                if hasattr(self, "res_city_combo") and self.roster:
                    cities = self.roster.cities if self.roster.cities else self.roster.bases
                    for idx, c in enumerate(cities):
                        if c.id == base_id:
                            if 0 <= idx < len(self.res_city_combo["values"]):
                                self.res_city_combo.current(idx)
                            break

    def _on_bld_base_selected(self, _event=None):
        sel = self.bld_bases_tree.selection()
        if not sel:
            return
        try:
            base_id = int(sel[0])
            self._switch_bld_base(base_id)
            if hasattr(self, "bld_city_combo") and self.roster:
                cities = self.roster.cities if self.roster.cities else self.roster.bases
                for idx, c in enumerate(cities):
                    if c.id == base_id:
                        if 0 <= idx < len(self.bld_city_combo["values"]):
                            self.bld_city_combo.current(idx)
                        break
            if hasattr(self, "dt_camp_combo") and self.roster and self.roster.camps:
                for idx, c in enumerate(self.roster.camps):
                    if c.id == base_id:
                        if 0 <= idx < len(self.dt_camp_combo["values"]):
                            self.dt_camp_combo.current(idx)
                            self._on_dt_camp_selected()
                        break
        except ValueError:
            pass

    def _on_bld_city_combo_selected(self, _event=None):
        sel_idx = self.bld_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        if 0 <= sel_idx < len(cities):
            base_id = cities[sel_idx].id
            if hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(base_id)):
                self.bld_bases_tree.selection_set(str(base_id))
            self._switch_bld_base(base_id)

    def _select_all_bld_bases(self, state: bool):
        sym = "☑" if state else "☐"
        for iid in self.bld_bases_tree.get_children(""):
            vals = list(self.bld_bases_tree.item(iid, "values"))
            vals[0] = sym
            self.bld_bases_tree.item(iid, values=vals)
            try:
                bid = int(iid)
                if state:
                    self._selected_building_cities.add(bid)
                else:
                    self._selected_building_cities.discard(bid)
            except ValueError:
                pass

    def _collect_bld_plans_from_tree(self) -> list[dict]:
        """Thu thập danh sách cấu hình phẳng từ bld_tree bảo toàn đúng thứ tự Loại công trình."""
        plans = []
        for root_iid in self.bld_tree.get_children(""):
            if root_iid.startswith("group_"):
                # Nhóm đa ô đất: duyệt tuần tự các ô con
                for child_iid in self.bld_tree.get_children(root_iid):
                    vals = self.bld_tree.item(child_iid, "values")
                    if len(vals) >= 5:
                        try:
                            gid = int(vals[2])
                            bname = BUILDING_NAMES.get(gid, f"Công trình {gid}")
                            c_lvl = int(vals[3]) if str(vals[3]).isdigit() else 0
                            t_lvl = int(vals[4]) if str(vals[4]).isdigit() else 20
                            plans.append({
                                "pid": int(vals[1]),
                                "gid": gid,
                                "name": bname,
                                "cur_lvl": c_lvl,
                                "target_level": t_lvl,
                                "enabled": vals[0] == "☑",
                            })
                        except (ValueError, TypeError, IndexError):
                            pass
            else:
                # Ô đơn chiếc
                vals = self.bld_tree.item(root_iid, "values")
                name = self.bld_tree.item(root_iid, "text")
                if len(vals) >= 5:
                    try:
                        gid = int(vals[2])
                        c_lvl = int(vals[3]) if str(vals[3]).isdigit() else 0
                        t_lvl = int(vals[4]) if str(vals[4]).isdigit() else 20
                        plans.append({
                            "pid": int(vals[1]),
                            "gid": gid,
                            "name": name,
                            "cur_lvl": c_lvl,
                            "target_level": t_lvl,
                            "enabled": vals[0] == "☑",
                        })
                    except (ValueError, TypeError, IndexError):
                        pass
        return plans

    def _save_current_bld_tree_to_cache(self):
        if self._current_bld_city_id is None:
            return
        plans = self._collect_bld_plans_from_tree()
        self._city_building_plans[self._current_bld_city_id] = plans

    def _render_bld_tree_from_plans(self, plans: list[dict]):
        expanded_groups = set()
        if hasattr(self, "bld_tree"):
            for iid in self.bld_tree.get_children(""):
                if iid.startswith("group_") and bool(self.bld_tree.item(iid, "open")):
                    expanded_groups.add(iid)
        self.bld_tree.delete(*self.bld_tree.get_children(""))
        gid_order = []
        grouped: dict[int, list[dict]] = {}
        for p in plans:
            gid = int(p.get("gid", 1))
            if gid not in grouped:
                grouped[gid] = []
                gid_order.append(gid)
            grouped[gid].append(p)

        for gid in gid_order:
            plots = grouped[gid]
            plots.sort(key=lambda x: int(x.get("pid", 1)))
            if len(plots) == 1:
                p = plots[0]
                pid = int(p.get("pid", 1))
                name = p.get("name") or BUILDING_NAMES.get(gid, f"Công trình {gid}")
                en = "☑" if p.get("enabled", False) else "☐"
                cur_lvl = int(p.get("cur_lvl", 0))
                target_lvl = int(p.get("target_level", 20))
                tag = self._get_bld_row_tag(cur_lvl, target_lvl)
                self.bld_tree.insert(
                    "",
                    "end",
                    iid=str(pid),
                    text=name,
                    values=(en, pid, gid, cur_lvl, target_lvl),
                    tags=(tag,),
                )
            else:
                count = len(plots)
                name = plots[0].get("name") or BUILDING_NAMES.get(gid, f"Công trình {gid}")
                all_en = all(p.get("enabled", False) for p in plots)
                any_en = any(p.get("enabled", False) for p in plots)
                sym = "☑" if all_en else ("▣" if any_en else "☐")
                cur_lvls = [int(p.get("cur_lvl", 0)) for p in plots]
                target_lvls = [int(p.get("target_level", 20)) for p in plots]
                min_cur, max_cur = min(cur_lvls), max(cur_lvls)
                cur_str = str(min_cur) if min_cur == max_cur else f"{min_cur} - {max_cur}"
                target_str = str(max(target_lvls))
                tag = "completed" if all(c >= t for c, t in zip(cur_lvls, target_lvls)) else "upgrade"
                group_iid = f"group_{gid}"
                is_open = group_iid in expanded_groups  # Mặc định là False (collapse)
                self.bld_tree.insert(
                    "",
                    "end",
                    iid=group_iid,
                    text=f"{name} ({count} ô)",
                    values=(sym, f"{count} ô", gid, cur_str, target_str),
                    tags=(tag,),
                    open=is_open,
                )
                for p in plots:
                    pid = int(p.get("pid", 1))
                    en = "☑" if p.get("enabled", False) else "☐"
                    cur_lvl = int(p.get("cur_lvl", 0))
                    target_lvl = int(p.get("target_level", 20))
                    c_tag = self._get_bld_row_tag(cur_lvl, target_lvl)
                    self.bld_tree.insert(
                        group_iid,
                        "end",
                        iid=str(pid),
                        text=f"  ↳ Ô {pid}",
                        values=(en, pid, gid, cur_lvl, target_lvl),
                        tags=(c_tag,),
                    )

        children = self.bld_tree.get_children("")
        if children:
            sel = self.bld_tree.selection()
            if not sel or not self.bld_tree.exists(sel[0]):
                self.bld_tree.selection_set(children[0])
            self._on_bld_tree_selected()

    def _switch_bld_base(self, new_base_id: int):
        if self._current_bld_city_id == new_base_id:
            return
        self._save_current_bld_tree_to_cache()
        self._current_bld_city_id = new_base_id

        base_name = f"Căn cứ {new_base_id}"
        if hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(new_base_id)):
            base_name = self.bld_bases_tree.item(str(new_base_id), "text")
        elif self.roster:
            b = self.roster.base_by_id(new_base_id)
            if b:
                base_name = b.name

        if hasattr(self, "bld_queue_frame"):
            self.bld_queue_frame.configure(text=f"Hàng Đợi Quy Hoạch: {base_name}")

        cached = self._city_building_plans.get(new_base_id)
        if cached:
            self._render_bld_tree_from_plans(cached)
        else:
            self._populate_default_buildings()
            if self.gateway and hasattr(self, "_fetch_city_buildings_thread"):
                threading.Thread(target=self._fetch_city_buildings_thread, args=(new_base_id,), daemon=True).start()

    def _fetch_city_buildings(self):
        city_id = self._current_bld_city_id
        if not city_id:
            sel_idx = self.bld_city_combo.current() if hasattr(self, "bld_city_combo") else -1
            cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
            if 0 <= sel_idx < len(cities):
                city_id = cities[sel_idx].id
        if not city_id and self.roster and self.roster.bases:
            city_id = self.roster.bases[0].id
        if not city_id:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn căn cứ cần tải công trình!")
            return

        base_name = str(city_id)
        if self.roster:
            b = self.roster.base_by_id(city_id)
            if b:
                base_name = b.name

        self._append_bld_log(f"🔄 Đang tải dữ liệu công trình thực tế cho {base_name}...")
        threading.Thread(target=self._fetch_city_buildings_thread, args=(city_id,), daemon=True).start()

    def _fetch_city_buildings_thread(self, city_id: int):
        try:
            resp = self.gateway.call("City.ashx", 5, {"tid": str(city_id), "_": ""}) or {}
            buildings = resp.get("infos") or resp.get("buildings") or resp.get("build", [])
            try:
                self.after(0, self._update_city_buildings_ui, buildings, city_id)
            except Exception:
                pass
        except Exception as e:
            try:
                self.after(0, lambda: self._append_bld_log(f"❌ Lỗi tải công trình căn cứ {city_id}: {e}"))
            except Exception:
                pass

    def _sync_city_buildings_data(self, target_city_id: Optional[int], buildings, from_auto_cycle: bool = False):
        target_city_id = target_city_id or self._current_bld_city_id
        if not buildings:
            if not from_auto_cycle:
                self._append_bld_log("ℹ️ Server không trả về dữ liệu công trình.")
            return

        # 1. Chuẩn hóa dữ liệu server: pid -> {"gid": int, "level": int, "name": str}
        real_map: dict[int, dict] = {}
        if isinstance(buildings, dict):
            for pid_k, b_info in buildings.items():
                try:
                    pid = int(pid_k)
                    if isinstance(b_info, dict):
                        real_map[pid] = {
                            "gid": int(b_info.get("gid", 0)),
                            "level": int(b_info.get("level", 0)),
                            "name": b_info.get("name", ""),
                        }
                    elif isinstance(b_info, (list, tuple)) and len(b_info) >= 4:
                        real_map[pid] = {
                            "gid": int(b_info[1]),
                            "level": int(b_info[3]),
                            "name": str(b_info[2]) if len(b_info) > 2 else "",
                        }
                except (ValueError, TypeError):
                    pass
        elif isinstance(buildings, (list, tuple)):
            for b in buildings:
                if isinstance(b, dict):
                    pid = int(b.get("pid", 0))
                    real_map[pid] = {
                        "gid": int(b.get("gid", 0)),
                        "level": int(b.get("level", 0)),
                        "name": b.get("name", ""),
                    }
                elif isinstance(b, (list, tuple)) and len(b) >= 4:
                    pid = int(b[0])
                    real_map[pid] = {
                        "gid": int(b[1]),
                        "level": int(b[3]),
                        "name": str(b[2]) if len(b) > 2 else "",
                    }

        if not real_map:
            return

        base_name = str(target_city_id) if target_city_id else ""
        if self.roster and target_city_id:
            b = self.roster.base_by_id(target_city_id)
            if b:
                base_name = b.name

        # 2. Lấy danh sách quy hoạch hiện tại (cache) để bảo toàn thứ tự 100%
        cached_plans = list(self._city_building_plans.get(target_city_id, []))

        # 3. Bảo toàn thứ tự: Duyệt theo danh sách hiện hữu
        seen_pids = set()
        new_plans = []
        level_changes = []

        if not cached_plans:
            # Chưa từng có kế hoạch: Khởi tạo mới theo danh sách server
            for pid, r_info in real_map.items():
                gid = int(r_info.get("gid", 1))
                name = BUILDING_NAMES.get(gid, r_info.get("name") or f"Công trình {gid}")
                lvl = int(r_info.get("level", 0))
                new_plans.append({
                    "pid": pid,
                    "gid": gid,
                    "name": name,
                    "cur_lvl": lvl,
                    "target_level": max(lvl + 1, 20),
                    "enabled": False,
                })
        else:
            for p in cached_plans:
                pid = int(p.get("pid", 0))
                if pid not in real_map:
                    continue  # Bỏ qua các ô đất không tồn tại trên thực tế (hoặc công trình mẫu giả định)
                seen_pids.add(pid)
                plan_entry = dict(p)
                r_info = real_map[pid]
                old_lvl = int(p.get("cur_lvl", 0))
                new_lvl = int(r_info.get("level", 0))
                if new_lvl != old_lvl:
                    level_changes.append((pid, plan_entry.get("name") or f"Ô {pid}", old_lvl, new_lvl))
                plan_entry["cur_lvl"] = new_lvl
                if r_info.get("gid"):
                    plan_entry["gid"] = r_info["gid"]
                    plan_entry["name"] = BUILDING_NAMES.get(r_info["gid"], r_info.get("name") or plan_entry.get("name", ""))
                new_plans.append(plan_entry)

            # Các ô đất mới trên server chưa có trong quy hoạch: Tự động kết nạp vào nhóm nếu nhóm chọn all (ADR-0016)
            for pid, r_info in real_map.items():
                if pid not in seen_pids:
                    gid = int(r_info.get("gid", 1))
                    name = BUILDING_NAMES.get(gid, r_info.get("name") or f"Công trình {gid}")
                    lvl = int(r_info.get("level", 0))

                    same_gid_plans = [p for p in cached_plans if int(p.get("gid", 0)) == gid]
                    if same_gid_plans and all(p.get("enabled", True) for p in same_gid_plans):
                        # Nhóm đang chọn all: Tự động bật chọn và kế thừa Cấp Mục Tiêu của nhóm
                        group_target_lvl = int(same_gid_plans[0].get("target_level", max(lvl + 1, 20)))
                        new_plan = {
                            "pid": pid,
                            "gid": gid,
                            "name": name,
                            "cur_lvl": lvl,
                            "target_level": group_target_lvl,
                            "enabled": True,
                        }
                        if hasattr(self, "_append_bld_log"):
                            self._append_bld_log(
                                f"✨ [{base_name}] Ô đất mới {pid} ({name}) tự động kết nạp vào nhóm & đặt Cấp MT = {group_target_lvl}."
                            )
                    else:
                        new_plan = {
                            "pid": pid,
                            "gid": gid,
                            "name": name,
                            "cur_lvl": lvl,
                            "target_level": lvl,
                            "enabled": False,
                        }
                    new_plans.append(new_plan)

        # Lưu lại cache
        if target_city_id is not None:
            self._city_building_plans[target_city_id] = new_plans

        # 4. Cập nhật giao diện in-place nếu căn cứ này đang hiển thị
        if (target_city_id == self._current_bld_city_id or self._current_bld_city_id is None) and hasattr(self, "bld_tree"):
            sel = self.bld_tree.selection()
            self._render_bld_tree_from_plans(new_plans)
            if sel and self.bld_tree.exists(sel[0]):
                try:
                    self.bld_tree.selection_set(sel[0])
                except Exception:
                    pass

        # 5. Ghi nhật ký phản hồi trực quan
        if level_changes:
            ch_str = ", ".join([f"{name} (cấp {ol}➔{nl})" for _, name, ol, nl in level_changes[:3]])
            if len(level_changes) > 3:
                ch_str += f", +{len(level_changes)-3} công trình khác"
            self._append_bld_log(f"🔄 [{base_name}] Đã đồng bộ thực tế: {ch_str}")
        elif not from_auto_cycle:
            self._append_bld_log(f"🔄 Đã nạp thành công {len(new_plans)} công trình thực tế của {base_name} (bảo toàn thứ tự ưu tiên).")

    def _update_city_buildings_ui(self, buildings, city_id: Optional[int] = None):
        self._sync_city_buildings_data(city_id, buildings, from_auto_cycle=False)

    def _load_build_plans(self):
        plan_path = Path("build_plans.json") if Path("build_plans.json").exists() else Path("build_plans.example.json")
        if not plan_path.exists():
            messagebox.showerror("Lỗi", "Không tìm thấy file build_plans.json hoặc build_plans.example.json!")
            return
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        cities_data = data.get("cities", {})
        plans_list = data.get("plans", [])
        if cities_data and not plans_list:
            for cid, cinfo in cities_data.items():
                plans_list.extend(cinfo.get("plans", []))

        if plans_list:
            self._render_bld_tree_from_plans(plans_list)
        self._append_bld_log(f"📂 Đã nạp danh sách {len(plans_list)} quy hoạch công trình.")

    def _save_build_plans(self):
        self._save_current_bld_tree_to_cache()
        plans = self._city_building_plans.get(self._current_bld_city_id, [])
        if not plans:
            plans = self._collect_bld_plans_from_tree()
        Path("build_plans.json").write_text(json.dumps({"plans": plans}, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_bld_log(f"💾 Đã lưu cấu hình {len(plans)} công trình ra build_plans.json")
        messagebox.showinfo("Thành công", "Đã lưu cấu hình ra build_plans.json!")

    def _toggle_building(self):
        if not self._bld_runner or not self._bld_runner.is_alive():
            self._save_current_bld_tree_to_cache()

            selected_cids = list(self._selected_building_cities)
            if not selected_cids:
                if self._current_bld_city_id:
                    selected_cids = [self._current_bld_city_id]
                elif hasattr(self, "bld_city_combo"):
                    sel_idx = self.bld_city_combo.current()
                    cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
                    if 0 <= sel_idx < len(cities):
                        selected_cids = [cities[sel_idx].id]

            if not selected_cids:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 căn cứ để nâng cấp công trình!")
                return

            try:
                max_slots = int(self.bld_slots_combo.get()) if hasattr(self, "bld_slots_combo") and self.bld_slots_combo.get() else 3
            except (ValueError, TypeError):
                max_slots = 3

            tasks: list[BuildingTask] = []
            for cid in selected_cids:
                plan_dicts = self._city_building_plans.get(cid)
                if not plan_dicts and cid == self._current_bld_city_id:
                    plan_dicts = self._collect_bld_plans_from_tree()

                if not plan_dicts:
                    continue

                plans = [
                    BuildingPlan(
                        pid=int(p["pid"]),
                        gid=int(p["gid"]),
                        target_level=int(p["target_level"]),
                        name=p.get("name", ""),
                        enabled=bool(p.get("enabled", True)),
                    )
                    for p in plan_dicts
                    if p.get("enabled", True)
                ]
                if not plans:
                    continue

                base_name = f"Căn cứ {cid}"
                if self.roster:
                    b = self.roster.base_by_id(cid)
                    if b:
                        base_name = b.name
                box_id = 24
                if hasattr(self, "bld_box_combo") and self.bld_box_combo.get():
                    try:
                        box_id = int(self.bld_box_combo.get().split(":")[0].strip())
                    except (ValueError, IndexError):
                        box_id = 24
                max_boxes = 5
                if hasattr(self, "bld_box_max_var") and self.bld_box_max_var.get():
                    try:
                        max_boxes = int(self.bld_box_max_var.get())
                    except ValueError:
                        max_boxes = 5

                auto_open_box = bool(self.bld_open_box_var.get()) if hasattr(self, "bld_open_box_var") else False
                auto_fallback_box = bool(self.bld_box_fallback_var.get()) if hasattr(self, "bld_box_fallback_var") else True

                task = BuildingTask(
                    gateway=self.gateway,
                    city_id=cid,
                    plans=plans,
                    max_slots=max_slots,
                    auto_speedup=self.bld_speedup_var.get(),
                    auto_boost=self.bld_boost_var.get(),
                    auto_comfort=self.bld_comfort_var.get(),
                    auto_open_box=auto_open_box,
                    box_id=box_id,
                    max_boxes_per_round=max_boxes,
                    auto_fallback_box=auto_fallback_box,
                    even_upgrade=False,
                    notify=lambda m, cname=base_name: self.after(0, self._append_bld_log, f"[{cname}] {m}"),
                    city_name=base_name,
                    on_sync_data=lambda target_cid, rdata: self.after(0, self._sync_city_buildings_data, target_cid, rdata, True),
                )
                tasks.append(task)

            if not tasks:
                messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 công trình cần nâng cấp trong các căn cứ đã chọn!")
                return

            try:
                bld_interval = max(3.0, float(self.bld_interval_var.get() or "20"))
            except ValueError:
                bld_interval = 20.0

            self._bld_runner = BuildingAutoRunner(
                tasks,
                interval=bld_interval,
                log_cb=lambda m: self.after(0, self._append_bld_log, m),
                status_cb=lambda s: None,
                sync_cb=lambda target_cid, rdata: self.after(0, self._sync_city_buildings_data, target_cid, rdata, True),
            )
            self._bld_runner.start()
            self.bld_start_btn.configure(text="Đang Xây", style="Success.TButton")
        else:
            self._bld_runner.stop()
            self.bld_start_btn.configure(text="Xây", style="Danger.TButton")
            self._save_current_bld_tree_to_cache()

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

        res_top = tk.Frame(f_res, bg=CARD, padx=8, pady=4)
        res_top.pack(fill="x")
        tk.Label(res_top, text="Thành:", bg=CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=4)
        self.res_city_combo = ttk.Combobox(res_top, state="readonly", width=18)
        self.res_city_combo.pack(side="left", padx=4)
        self.res_city_combo.bind("<<ComboboxSelected>>", lambda e: self._fetch_city_techs())

        self.res_art_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            res_top,
            text="📜 Binh Pháp tăng tốc",
            variable=self.res_art_var,
            bg=CARD,
            fg=FG,
            selectcolor=BG,
            activebackground=CARD,
        ).pack(side="left", padx=6)

        self.res_even_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            res_top,
            text="⚖️ Nghiên cứu đồng đều",
            variable=self.res_even_var,
            bg=CARD,
            fg=FG,
            selectcolor=BG,
            activebackground=CARD,
        ).pack(side="left", padx=6)

        tk.Label(res_top, text="Chu kỳ (s):", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 2))
        self.res_interval_var = tk.StringVar(value="30")
        ttk.Entry(res_top, textvariable=self.res_interval_var, width=4).pack(side="left", padx=(0, 6))

        self.res_start_btn = ttk.Button(res_top, text="▶️ Bắt đầu", style="Success.TButton", command=self._toggle_research)
        self.res_start_btn.pack(side="right", padx=4)

        # Thanh công cụ sắp xếp ưu tiên kỹ thuật
        res_bar = tk.Frame(f_res, bg=CARD, padx=8, pady=4)
        res_bar.pack(fill="x")
        ttk.Button(res_bar, text="⬆️ Lên", style="Action.TButton", command=self._move_res_up).pack(side="left", padx=2)
        ttk.Button(res_bar, text="⬇️ Xuống", style="Action.TButton", command=self._move_res_down).pack(side="left", padx=2)
        ttk.Button(res_bar, text="☑ Tất cả", style="Action.TButton", command=lambda: self._select_all_res(True)).pack(side="left", padx=2)
        ttk.Button(res_bar, text="☐ Bỏ chọn", style="Action.TButton", command=lambda: self._select_all_res(False)).pack(side="left", padx=2)

        tk.Label(res_bar, text="Cấp MT:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
        self.res_target_lvl_var = tk.StringVar(value="20")
        ttk.Entry(res_bar, textvariable=self.res_target_lvl_var, width=5).pack(side="left", padx=2)
        ttk.Button(res_bar, text="✏️ Đặt cấp", style="Action.TButton", command=self._set_res_target_lvl).pack(side="left", padx=2)
        ttk.Button(res_bar, text="🌟 Đặt tất cả", style="Action.TButton", command=self._set_res_target_lvl_all).pack(side="left", padx=2)
        ttk.Button(res_bar, text="🔄 Tải kỹ thuật", style="Action.TButton", command=self._fetch_city_techs).pack(side="left", padx=2)

        self.res_tree = ttk.Treeview(f_res, columns=("select", "id", "target_lvl", "current_lvl"), show="tree headings", selectmode="browse")
        self.res_tree.heading("#0", text="Tên Kỹ Thuật Đại Học")
        self.res_tree.heading("select", text="Chọn")
        self.res_tree.heading("id", text="Mã ID")
        self.res_tree.heading("target_lvl", text="Cấp MT")
        self.res_tree.heading("current_lvl", text="Cấp HT")

        self.res_tree.column("#0", width=135)
        self.res_tree.column("select", width=45, anchor="center")
        self.res_tree.column("id", width=50, anchor="center")
        self.res_tree.column("target_lvl", width=55, anchor="center")
        self.res_tree.column("current_lvl", width=55, anchor="center")

        self.res_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.res_tree.bind("<ButtonRelease-1>", self._on_res_tree_click)
        self._populate_all_techs()

        # Cột phải: Hậu Cần & Chuyển Quân Giới
        f_logis = ttk.LabelFrame(body, text="Hậu Cần & Chuyển Quân Giới", style="Card.TLabelframe")
        f_logis.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        logis_form = tk.Frame(f_logis, bg=CARD, padx=12, pady=10)
        logis_form.pack(fill="x", padx=6, pady=6)

        tk.Label(logis_form, text="Từ Căn Cứ:", bg=CARD, fg=FG).grid(row=0, column=0, sticky="w", pady=4)
        self.log_from_city_combo = ttk.Combobox(logis_form, state="readonly", width=18)
        self.log_from_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        tk.Label(logis_form, text="Đến Căn Cứ:", bg=CARD, fg=FG).grid(row=0, column=2, sticky="w", pady=4)
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
        ttk.Button(act_row, text="🚚 Chuyển Quân Giới Ngay", style="Action.TButton", command=self._do_transfer_army).pack(side="left", padx=4)
        ttk.Button(act_row, text="🕊️ An Dân Ngay", style="Action.TButton", command=self._do_comfort_now).pack(side="left", padx=4)
        ttk.Button(act_row, text="🎁 Nhận Thưởng Chuyên Cần", style="Success.TButton", command=self._do_claim_daily).pack(side="left", padx=4)

        # Log chung cho Tab 6
        f_log_tab6 = tk.Frame(f_logis, bg=CARD)
        f_log_tab6.pack(fill="both", expand=True, padx=6, pady=6)
        self.logis_log_text = tk.Text(f_log_tab6, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.logis_log_text.pack(fill="both", expand=True)

    def _append_logis_log(self, msg: str):
        logging.getLogger("linhvuong.tasks.HauCan").info(msg)
        self._append_text_buffer(self.logis_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _populate_all_techs(self):
        self.res_tree.delete(*self.res_tree.get_children())
        for tid, tname in sorted(TECH_NAMES.items()):
            self.res_tree.insert("", "end", iid=str(tid), text=tname, values=("☐", tid, 20, "-"), tags=("upgrade",))
        children = self.res_tree.get_children("")
        if children:
            sel = self.res_tree.selection()
            if not sel or not self.res_tree.exists(sel[0]):
                self.res_tree.selection_set(children[0])
            self._on_res_tree_selected()

    def _fetch_city_techs(self):
        sel_idx = self.res_city_combo.current()
        cities = self.roster.cities if self.roster.cities else self.roster.bases
        if sel_idx < 0 or sel_idx >= len(cities):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì cần tải kỹ thuật!")
            return
        city = cities[sel_idx]
        self._append_logis_log(f"🔄 Đang tải dữ liệu kỹ thuật thực tế cho thành {city.name}...")
        threading.Thread(target=self._fetch_city_techs_thread, args=(city.id,), daemon=True).start()

    def _fetch_city_techs_thread(self, city_id: int):
        try:
            # 1. Chuyển focus thành thị về city_id (bắt buộc trên server game thật)
            self.gateway.call("City.ashx", 50, {"tid": str(city_id), "_": ""})

            # 2. Tìm Đại Học Điện (gid=6) hoặc Thái Học Điện (gid=59) trong thành này
            resp_bld = self.gateway.call("City.ashx", 5, {"tid": str(city_id), "_": ""}) or {}
            b_list = resp_bld.get("infos") or resp_bld.get("buildings") or []
            univ_pid = None
            univ_gid = 6
            for b in b_list:
                if isinstance(b, (list, tuple)) and len(b) >= 2 and int(b[1]) in (6, 59):
                    univ_pid = int(b[0])
                    univ_gid = int(b[1])
                    break
                elif isinstance(b, dict) and int(b.get("gid", 0)) in (6, 59):
                    univ_pid = int(b.get("pid", 0))
                    univ_gid = int(b.get("gid", 0))
                    break

            # Nếu thành hiện tại không có Viện Đại Học / Thái Học Điện, tự động tìm thành có
            if univ_pid is None:
                found_city = None
                for c in (self.roster.cities if self.roster.cities else []):
                    if c.id == city_id:
                        continue
                    r = self.gateway.call("City.ashx", 5, {"tid": str(c.id), "_": ""}) or {}
                    for b in r.get("infos") or []:
                        if len(b) >= 2 and int(b[1]) in (6, 59):
                            found_city = c
                            break
                    if found_city:
                        break

                if found_city:
                    self.after(
                        0,
                        lambda: self._append_logis_log(
                            f"ℹ️ Thành được chọn không có Đại Học / Thái Học Điện. Tự động chuyển sang thành '{found_city.name}'..."
                        ),
                    )
                    def update_combo_and_refetch():
                        city_items = [c.display_name for c in self.roster.cities]
                        for idx, item in enumerate(city_items):
                            if str(found_city.id) in item:
                                self.res_city_combo.current(idx)
                                break
                        threading.Thread(target=self._fetch_city_techs_thread, args=(found_city.id,), daemon=True).start()

                    self.after(0, update_combo_and_refetch)
                    return
                else:
                    self.after(
                        0,
                        lambda: self._append_logis_log(
                            "⚠️ Không tìm thấy Viện Đại Học / Thái Học Điện ở bất kỳ thành nào!"
                        ),
                    )
                    return

            # 3. Lấy cấp độ 29 kỹ thuật
            resp_tech = self.gateway.call("Build.ashx", 2, {"pid": str(univ_pid), "gid": str(univ_gid), "tab": "1", "tid": str(city_id), "_": ""}) or {}
            ret = resp_tech.get("ret", 0)
            if ret != 0:
                self.after(0, lambda: self._append_logis_log(f"⚠️ Server trả về mã lỗi {ret} khi đọc kỹ thuật."))
                return

            levels = {}
            for item in resp_tech.get("list", []):
                if isinstance(item, dict):
                    levels[int(item.get("id", 0))] = int(item.get("level", 0))
                elif isinstance(item, (list, tuple)) and len(item) >= 3:
                    try:
                        levels[int(item[0])] = int(item[2])
                    except (ValueError, TypeError):
                        pass

            self.after(0, self._update_city_techs_ui, levels)
            curr = resp_tech.get("current")
            if curr and isinstance(curr, (list, tuple)) and len(curr) >= 5:
                t_name, cur_l, next_l, t_left = curr[1], curr[2], curr[3], curr[4]
                self.after(0, lambda: self._append_logis_log(f"🔬 Đang nghiên cứu: {t_name} (Cấp {cur_l} ➔ {next_l}), còn {t_left}s."))
            elif levels:
                self.after(0, lambda: self._append_logis_log(f"✅ Đã tải cấp độ {len(levels)} kỹ thuật thành công."))
        except Exception as e:
            self.after(0, lambda: self._append_logis_log(f"❌ Lỗi tải kỹ thuật thành: {e}"))

    def _sync_city_techs_data(self, city_id: int, levels_map: dict, tech_status: Optional[tuple] = None, from_auto_cycle: bool = False):
        if not levels_map:
            if not from_auto_cycle:
                self._append_logis_log("ℹ️ Server không trả về dữ liệu kỹ thuật.")
            return

        level_changes = []
        for iid in self.res_tree.get_children(""):
            try:
                tid = int(iid)
                if tid in levels_map:
                    cur_lvl = int(levels_map[tid])
                    vals = list(self.res_tree.item(iid, "values"))
                    tname = self.res_tree.item(iid, "text")
                    if len(vals) >= 3:
                        old_lvl = int(vals[3]) if len(vals) > 3 and str(vals[3]) != "-" else 0
                        if len(vals) == 3:
                            vals.append(cur_lvl)
                        else:
                            vals[3] = cur_lvl
                        if old_lvl != cur_lvl and old_lvl > 0:
                            level_changes.append((tid, tname, old_lvl, cur_lvl))
                        target_lvl = int(vals[2]) if len(vals) > 2 else 20
                        tag = "completed" if cur_lvl >= target_lvl else "upgrade"
                        self.res_tree.item(iid, values=vals, tags=(tag,))
            except (ValueError, IndexError):
                pass

        if level_changes:
            ch_str = ", ".join([f"{name} (cấp {ol}➔{nl})" for _, name, ol, nl in level_changes[:3]])
            if len(level_changes) > 3:
                ch_str += f", +{len(level_changes)-3} kỹ thuật khác"
            self._append_logis_log(f"🔄 Đã đồng bộ kỹ thuật thực tế: {ch_str}")
        elif not from_auto_cycle:
            self._append_logis_log(f"🔄 Đã nạp thành công cấp độ thực tế của {len(levels_map)} kỹ thuật (bảo toàn thứ tự ưu tiên).")

        if tech_status and tech_status[0]:
            tid = tech_status[1]
            tname = TECH_NAMES.get(tid, f"Kỹ thuật {tid}")
            if not from_auto_cycle:
                self._append_logis_log(f"🔬 Viện Đại Học đang nghiên cứu: {tname}")

    def _update_city_techs_ui(self, levels_map: dict):
        sel_idx = self.res_city_combo.current() if hasattr(self, "res_city_combo") else -1
        city_id = 0
        if self.roster and self.roster.cities and 0 <= sel_idx < len(self.roster.cities):
            city_id = self.roster.cities[sel_idx].id
        self._sync_city_techs_data(city_id, levels_map, tech_status=None, from_auto_cycle=False)

    def _move_res_up(self):
        sel = self.res_tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.res_tree.index(item)
        if idx > 0:
            self.res_tree.move(item, "", idx - 1)

    def _move_res_down(self):
        sel = self.res_tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.res_tree.index(item)
        children = self.res_tree.get_children("")
        if idx < len(children) - 1:
            self.res_tree.move(item, "", idx + 1)

    def _select_all_res(self, state: bool):
        sym = "☑" if state else "☐"
        for iid in self.res_tree.get_children(""):
            vals = list(self.res_tree.item(iid, "values"))
            vals[0] = sym
            self.res_tree.item(iid, values=vals)

    def _set_res_target_lvl(self):
        sel = self.res_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 kỹ thuật trong bảng!")
            return
        try:
            lvl = int(self.res_target_lvl_var.get())
            if lvl < 1 or lvl > 30:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 1 đến 30!")
            return
        for iid in sel:
            vals = list(self.res_tree.item(iid, "values"))
            vals[2] = lvl
            try:
                cur = int(vals[3]) if len(vals) > 3 and str(vals[3]) != "-" else None
                tag = ("completed" if cur >= lvl else "upgrade") if cur is not None else "upgrade"
                self.res_tree.item(iid, values=vals, tags=(tag,))
            except (ValueError, TypeError):
                self.res_tree.item(iid, values=vals)

    def _set_res_target_lvl_all(self):
        try:
            lvl = int(self.res_target_lvl_var.get())
            if lvl < 1 or lvl > 30:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 1 đến 30!")
            return
        count = 0
        for iid in self.res_tree.get_children(""):
            vals = list(self.res_tree.item(iid, "values"))
            if len(vals) > 2:
                vals[2] = lvl
                try:
                    cur = int(vals[3]) if len(vals) > 3 and str(vals[3]) != "-" else None
                    tag = ("completed" if cur >= lvl else "upgrade") if cur is not None else "upgrade"
                    self.res_tree.item(iid, values=vals, tags=(tag,))
                except (ValueError, TypeError):
                    self.res_tree.item(iid, values=vals)
                count += 1
        self._append_logis_log(f"🎯 Đã đặt Cấp mục tiêu = {lvl} cho tất cả {count} kỹ thuật.")

    def _on_res_tree_selected(self, _event=None):
        sel = self.res_tree.selection()
        if not sel:
            return
        item = sel[0]
        if not self.res_tree.exists(item):
            return
        vals = self.res_tree.item(item, "values")
        if len(vals) > 2:
            try:
                self.res_target_lvl_var.set(str(vals[2]))
            except Exception:
                pass

    def _on_res_tree_click(self, event):
        item = self.res_tree.identify_row(event.y)
        col = self.res_tree.identify_column(event.x)
        if not item or not self.res_tree.exists(item):
            return
        vals = list(self.res_tree.item(item, "values"))
        # displaycolumns=("current_lvl", "target_lvl", "select")
        # identify_column: #0 (text), #1 (current_lvl - "Cấp HT"), #2 (target_lvl - "Cấp MT"), #3 (select - "Chạy")
        if col == "#3":
            vals[0] = "☑" if vals[0] == "☐" else "☐"
            self.res_tree.item(item, values=vals)
        else:
            self.res_tree.selection_set(item)
        if len(vals) > 2:
            self.res_target_lvl_var.set(str(vals[2]))

    def _load_tech_plans(self):
        plan_path = Path("tech_plans.json") if Path("tech_plans.json").exists() else Path("tech_plans.example.json")
        if not plan_path.exists():
            messagebox.showerror("Lỗi", "Không tìm thấy file tech_plans.json hoặc tech_plans.example.json!")
            return
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        plans = data.get("plans", [])
        if plans:
            plan_map = {int(p["tech_id"]): p for p in plans}
            for iid in self.res_tree.get_children(""):
                tid = int(iid)
                vals = list(self.res_tree.item(iid, "values"))
                cur_lvl = vals[3] if len(vals) > 3 else "-"
                if tid in plan_map:
                    p = plan_map[tid]
                    en = "☑" if p.get("enabled", True) else "☐"
                    target_lvl = p.get("target_level", 20)
                else:
                    en = "☐"
                    target_lvl = int(vals[2]) if len(vals) > 2 else 20
                try:
                    cur_int = int(cur_lvl) if str(cur_lvl) != "-" else None
                    tag = ("completed" if cur_int >= target_lvl else "upgrade") if cur_int is not None else "upgrade"
                except (ValueError, TypeError):
                    tag = "upgrade"
                self.res_tree.item(iid, values=(en, tid, target_lvl, cur_lvl), tags=(tag,))
        self._append_logis_log(f"📂 Đã nạp cấu hình {len(plans)} kỹ thuật.")

    def _save_tech_plans(self):
        plans = []
        for iid in self.res_tree.get_children(""):
            name = self.res_tree.item(iid, "text")
            vals = self.res_tree.item(iid, "values")
            plans.append({
                "tech_id": int(vals[1]),
                "target_level": int(vals[2]),
                "name": name,
                "enabled": vals[0] == "☑",
            })
        Path("tech_plans.json").write_text(json.dumps({"plans": plans}, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_logis_log(f"💾 Đã lưu cấu hình {len(plans)} kỹ thuật ra tech_plans.json")
        messagebox.showinfo("Thành công", "Đã lưu cấu hình ra tech_plans.json!")

    def _toggle_research(self):
        if not self._res_runner or not self._res_runner.is_alive():
            sel_idx = self.res_city_combo.current()
            cities = self.roster.cities if self.roster.cities else self.roster.bases
            if sel_idx < 0 or sel_idx >= len(cities):
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì nghiên cứu!")
                return
            city_id = cities[sel_idx].id
            plans = []
            for iid in self.res_tree.get_children(""):
                name = self.res_tree.item(iid, "text")
                vals = self.res_tree.item(iid, "values")
                if vals[0] == "☑":
                    plans.append(TechPlan(tech_id=int(vals[1]), target_level=int(vals[2]), name=name, enabled=True))

            if not plans:
                messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 kỹ thuật cần nghiên cứu!")
                return

            task = ResearchTask(
                gateway=self.gateway,
                city_id=city_id,
                plans=plans,
                auto_art_of_war=self.res_art_var.get(),
                even_research=bool(self.res_even_var.get()) if hasattr(self, "res_even_var") else False,
                notify=lambda m: self.after(0, self._append_logis_log, m),
                on_sync_data=lambda target_cid, levels, t_stat: self.after(0, self._sync_city_techs_data, target_cid, levels, t_stat, True),
            )
            try:
                res_interval = max(3.0, float(self.res_interval_var.get() or "30"))
            except ValueError:
                res_interval = 30.0

            self._res_runner = ResearchAutoRunner(
                task,
                interval=res_interval,
                log_cb=lambda m: self.after(0, self._append_logis_log, m),
                status_cb=lambda s: None,
                sync_cb=lambda target_cid, levels, t_stat: self.after(0, self._sync_city_techs_data, target_cid, levels, t_stat, True),
            )
            self._res_runner.start()
            self.res_start_btn.configure(text="Đang NC", style="Success.TButton")
        else:
            self._res_runner.stop()
            self.res_start_btn.configure(text="Nghiên Cứu", style="Danger.TButton")

    def _do_transfer_army(self):
        f_idx = self.log_from_city_combo.current()
        t_idx = self.log_to_city_combo.current()
        bases = self.roster.bases
        if f_idx < 0 or t_idx < 0 or f_idx >= len(bases) or t_idx >= len(bases):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn đầy đủ Căn cứ gửi và Căn cứ nhận!")
            return
        from_id = bases[f_idx].id
        to_id = bases[t_idx].id
        army_id = self.log_army_combo.current() + 1
        amount = int(self.log_amount_var.get() or "1000")

        task = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_logis_log, m))
        order = ArmyTransferOrder(from_city_id=from_id, to_city_id=to_id, army_id=army_id, amount=amount)
        threading.Thread(target=lambda: task.transfer_army(order), daemon=True).start()

    def _do_comfort_now(self):
        f_idx = self.log_from_city_combo.current()
        bases = self.roster.bases
        if f_idx < 0 or f_idx >= len(bases):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn căn cứ cần An Dân!")
            return
        city_id = bases[f_idx].id
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
        # Tab 1: Thành & Doanh trại
        self.city_tree.delete(*self.city_tree.get_children())
        for base in roster.bases:
            coords = f"{base.pos_x},{base.pos_y}" if (base.pos_x or base.pos_y) else "-"
            self.city_tree.insert("", "end", iid=str(base.id), text=base.name, values=(base.type, base.id, coords))
        self.status.set(f"Đã tải {len(roster.cities)} thành, {len(roster.camps)} doanh trại thành công")
        self.refresh_btn.state(["!disabled"])
        if roster.bases:
            self.city_tree.selection_set(str(roster.bases[0].id))

        # Danh sách Căn cứ thi công (Thành & Doanh trại)
        if hasattr(self, "bld_bases_tree"):
            self.bld_bases_tree.delete(*self.bld_bases_tree.get_children())
            for base in roster.bases:
                iid = str(base.id)
                is_sel = "☑" if (base.id in self._selected_building_cities or (not self._selected_building_cities and base == roster.bases[0])) else "☐"
                if is_sel == "☑":
                    self._selected_building_cities.add(base.id)
                is_res = "☑" if (base.id in self._selected_resource_cities) else "☐"
                is_nc = "★" if (self._research_city_id == base.id) else "☐"
                self.bld_bases_tree.insert(
                    "",
                    "end",
                    iid=iid,
                    text=base.name,
                    values=(is_sel, is_res, is_nc, base.type, base.id),
                )
            if roster.bases:
                first_base = roster.bases[0]
                self.bld_bases_tree.selection_set(str(first_base.id))
                self._current_bld_city_id = first_base.id
                if hasattr(self, "bld_queue_frame"):
                    self.bld_queue_frame.configure(text=f"Hàng Đợi Quy Hoạch: {first_base.name}")
            self._check_and_update_boost_status()

        # Cập nhật Combobox
        all_base_items = [b.display_name for b in roster.bases]
        city_items = [c.display_name for c in roster.cities]
        camps_items = [c.display_name for c in roster.camps] if roster.camps else all_base_items

        for combo in (self.bld_city_combo, self.res_city_combo, self.bm_parent_city_combo, self.gd_city_combo):
            combo["values"] = city_items
            if city_items and not combo.get():
                combo.current(0)

        for combo in (self.tp_city_combo, self.log_from_city_combo, self.log_to_city_combo):
            combo["values"] = all_base_items
            if all_base_items and not combo.get():
                combo.current(0)

        self.bm_city_combo["values"] = camps_items
        if camps_items and not self.bm_city_combo.get():
            self.bm_city_combo.current(0)
            self._on_bm_city_selected()

        if hasattr(self, "dt_camp_combo"):
            self.dt_camp_combo["values"] = camps_items
            if camps_items and not self.dt_camp_combo.get():
                self.dt_camp_combo.current(0)
                self._on_dt_camp_selected()

        if all_base_items:
            self._on_tp_city_selected()
        if city_items:
            self._fetch_city_buildings()

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
