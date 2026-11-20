"""Màn hình chính: Tổng quan thành/tướng và đầy đủ các Tab tự động hóa Linh Vương.

Tích hợp các Tab toàn diện được tổ chức theo từng module phân hệ trong `linhvuong.dashboard`:
- `overview`: Tổng quan thành/tướng, Ban thưởng toàn bộ, Luyện Sĩ Khí.
- `crafting`: Chế tạo Quân giới đa thành (ADR-0031).
- `building` & `internal_aux`: Xây dựng, Ngưỡng tài nguyên/Rương, Mở rương, Phụ trợ, Dịch Trại.
- `research`: Nghiên cứu Đại Học (29 kỹ thuật) & Hậu cần.
- `thaophat`: Thảo Phạt Tự Động.
- `binhman`: Bình Man Đa Căn Cứ (ADR-0029).
- `ditrai`: Di Trại Độc Lập.
- `goidan`: Gọi Dân & Vong Linh.
- `battle`: Chiến Trường, Mưu Lược & Thông báo BOSS.
- `nien_thu`: Sự kiện Niên Thú.
- `tactician_dialog` & `equip_dialog`: Thiết lập Mưu sĩ & Trang bị tướng.
- `profile_sync`: Hồ sơ cấu hình tổng hợp & Auto-Save khi chỉnh UI.
"""

import logging
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Optional

from ..auth import login
from ..battle import CombatConfig
from ..engine import AutomationEngine, TaskStatus
from ..gateway import GatewayClient
from ..generals import configure_equipment, configure_tacticians, fetch_equipment_inventory, reward_all_generals
from ..gui import set_app_icon
from ..locks import TargetLocks
from ..logger import open_logs_directory, setup_logger
from ..notifications import NotificationConfig, dispatch_boss_alert
from ..profile import BaseBinhManConfig, CityCraftConfig, CraftProfile, NotificationProfile, Profile, ProfileStore
from ..roster import Army, City, General, Roster, fetch_roster
from ..tasks.building import BuildingTask
from ..tasks.logistics import LogisticsTask
from ..tasks.morale import MoraleTrainer
from ..tasks.research import ResearchTask
from ..tasks.thao_phat import TargetArmy, ThaoPhatExecutor
from ..tasks.crafting import WeaponCrafter
from .add_points_dialog import AddPointsDialogMixin
from .armament_dialog import ArmamentDialogMixin
from .battle import BattleMixin
from .binhman import BinhManMixin
from .building import BuildingMixin
from .crafting import CraftingMixin
from .ditrai import DiTraiMixin
from .enhance import EnhanceMixin
from .equip_dialog import EquipDialogMixin
from .goidan import GoiDanMixin
from .internal_aux import InternalAuxMixin
from .nien_thu import NienThuMixin
from .overview import OverviewMixin
from .profile_sync import ProfileSyncMixin
from .rename_dialog import RenameDialogMixin
from .research import ResearchMixin
from .runners import BaseTaskRunner, BinhManAutoRunner, BuildingAutoRunner, GoiDanAutoRunner, ResearchAutoRunner
from .shared import (
    ACCENT,
    BATCH_TRIM_LINES,
    BG,
    CARD,
    COMBAT_MAX_LOG_LINES,
    COMBAT_TRIM_LINES,
    DANGER,
    DEFAULT_MAX_LOG_LINES,
    FG,
    MUTED,
    ROLE_TEXT,
    SUCCESS,
    MultiSelectDropdown,
    _LegacyComboAdapter,
    apply_action_mode_widgets,
    sync_action_mode_from_combo,
)
from .tactician_dialog import TacticianDialogMixin
from .thaophat import ThaoPhatMixin

logger = logging.getLogger("linhvuong.dashboard")

__all__ = [
    "Dashboard",
    "BaseTaskRunner",
    "BinhManAutoRunner",
    "BuildingAutoRunner",
    "GoiDanAutoRunner",
    "ResearchAutoRunner",
    "MultiSelectDropdown",
    "_LegacyComboAdapter",
    "BG",
    "CARD",
    "FG",
    "MUTED",
    "ACCENT",
    "SUCCESS",
    "DANGER",
    "ROLE_TEXT",
    "DEFAULT_MAX_LOG_LINES",
    "BATCH_TRIM_LINES",
    "COMBAT_MAX_LOG_LINES",
    "COMBAT_TRIM_LINES",
    "login",
    "GatewayClient",
    "fetch_roster",
    "MoraleTrainer",
    "WeaponCrafter",
    "BuildingTask",
    "LogisticsTask",
    "ResearchTask",
    "dispatch_boss_alert",
    "messagebox",
    "filedialog",
]


class Dashboard(
    ProfileSyncMixin,
    OverviewMixin,
    CraftingMixin,
    BuildingMixin,
    InternalAuxMixin,
    ResearchMixin,
    ThaoPhatMixin,
    GoiDanMixin,
    BinhManMixin,
    DiTraiMixin,
    BattleMixin,
    NienThuMixin,
    EnhanceMixin,
    TacticianDialogMixin,
    EquipDialogMixin,
    ArmamentDialogMixin,
    RenameDialogMixin,
    AddPointsDialogMixin,
    tk.Frame,
):
    """Cửa sổ Dashboard chính điều phối toàn bộ các phân hệ tự động hóa."""

    @staticmethod
    def _sync_action_mode_from_combo(var: tk.StringVar, combo: ttk.Combobox) -> str:
        return sync_action_mode_from_combo(var, combo)

    @staticmethod
    def _apply_action_mode_widgets(
        var: Optional[tk.StringVar],
        combo: Optional[ttk.Combobox],
        action_mode: Optional[str] = None,
        combo_idx: Optional[int] = None,
    ) -> None:
        return apply_action_mode_widgets(var, combo, action_mode=action_mode, combo_idx=combo_idx)

    def __init__(
        self,
        session,
        server_id: int,
        username: str = "",
        password: str = "",
        proxy_raw: str = "",
        proxy_user: str = "",
        proxy_pass: str = "",
        proxy_pool: Optional[Any] = None,
        master: Optional[tk.Widget] = None,
    ):
        if master is None:
            self._standalone_window = tk.Tk()
            super().__init__(self._standalone_window)
            self.pack(fill="both", expand=True)
        else:
            self._standalone_window = None
            super().__init__(master)

        self.session = session
        self.server_id = server_id
        self.username = username
        self._password = password
        self._proxy_raw = proxy_raw
        self._proxy_user = proxy_user
        self._proxy_pass = proxy_pass
        self.proxy_pool = proxy_pool
        try:
            setup_logger(username=username or "guest", server_id=server_id)
        except Exception:
            pass
        if username:
            self.default_profile_name = f"auto_profile_{username}_{server_id}.json"
        else:
            self.default_profile_name = "auto_profile.json"
        self.configure(bg=BG)

        # Trạng thái Auto-Save cấu hình khi chỉnh trên UI
        self._closing: bool = False
        self._destroyed: bool = False
        self._active_profile_path: Optional[Path] = None
        self._auto_save_enabled: bool = True
        self._auto_save_suppress_depth: int = 0
        self._auto_save_after_id: Optional[str] = None
        self._auto_save_delay_ms: int = 400
        self._auto_save_dirty: bool = False

        if self._standalone_window:
            if username:
                self.title(f"LinhVuong - S{server_id} - [{username}]")
            else:
                self.title(f"LinhVuong - Server {server_id}")
            set_app_icon(self._standalone_window)
            self.geometry("1100x700")
            self.minsize(1060, 650)

        if self.proxy_pool:

            def _on_proxy_failover(old_ep, new_ep):
                old_name = old_ep.display_name if old_ep else "không rõ"
                new_name = new_ep.display_name if new_ep else "hết proxy"
                self._log_global(f"⚠️ Proxy lỗi ({old_name}). Đã tự động đổi sang proxy mới: {new_name}")
                self.after(0, self._update_title_and_proxy_status)

            self.proxy_pool.on_failover = _on_proxy_failover

        relogin_cb = None
        if self.username and self._password:

            def auto_relogin() -> bool:
                try:
                    logger.info(
                        f"Đang tự động đăng nhập lại tài khoản {self.username} (Server {self.server_id})..."
                    )
                    self._log_global("🔑 Phiên hết hạn (198599). Đang tự động đăng nhập lại tài khoản...")
                    active_p = self.proxy_pool.get_active() if self.proxy_pool else None
                    proxy_to_use = active_p.url if active_p else (self._proxy_raw or None)
                    login(
                        self.session,
                        self.server_id,
                        self.username,
                        self._password,
                        proxy=proxy_to_use,
                        proxy_user=self._proxy_user or None,
                        proxy_pass=self._proxy_pass or None,
                    )
                    logger.info(
                        f"Tự động đăng nhập lại thành công tài khoản {self.username} (Server {self.server_id})!"
                    )
                    self._log_global("✅ Tự động đăng nhập lại thành công! Đã khôi phục phiên kết nối.")
                    return True
                except Exception as ex:
                    logger.error(f"Tự động đăng nhập lại thất bại: {ex}")
                    self._log_global(f"❌ Tự động đăng nhập lại thất bại: {ex}")
                    return False

            relogin_cb = auto_relogin

        self.gateway = GatewayClient(
            server_id, session, relogin_callback=relogin_cb, proxy_pool=self.proxy_pool
        )
        self.tp_executor = ThaoPhatExecutor(self.gateway)
        self.roster = Roster()
        self._results = queue.Queue()
        self._generals = {}

        # Trạng thái các luồng Task & Động cơ điều phối tập trung (ADR-0021)
        self.engine = AutomationEngine()
        self.engine.subscribe(on_log=self._on_engine_log, on_status=self._on_engine_status)
        self._pending_nt_city_id: Optional[int] = None
        self._pending_nt_generals: Optional[set[int]] = None
        self._tp_running = False
        self._tp_runner = None
        self._gd_runner = None
        self._bm_runner = None
        self._ditrai_runner = None
        self._ditrai_stop_event = threading.Event()
        self._morale_runner = None
        self._morale_stop_event: Optional[threading.Event] = None
        self._selected_morale_generals: set[int] = set()
        self._morale_generals_data: dict[int, dict] = {}
        self._morale_init_done: bool = False
        self._bld_runner = None
        self._res_runner = None
        self._city_building_plans: dict[int, list[dict]] = {}
        self._selected_building_cities: set[int] = set()
        self._selected_resource_cities: set[int] = set()
        self._research_city_id: Optional[int] = None
        self._pending_gd_generals: Optional[set[int]] = None
        self._pending_bm_generals: Optional[set[int]] = None
        self._current_bm_base_id: Optional[int] = None
        self.bm_base_configs: dict[int, BaseBinhManConfig] = {}
        self.shared_target_locks = TargetLocks()
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
        self._boost_left_seconds: int = 0
        self._boost_countdown_after_id: Optional[str] = None
        self.aux_tribute_var = tk.BooleanVar(value=False)
        self.aux_general_visit_var = tk.BooleanVar(value=True)
        self._general_visit_city_id: Optional[int] = None
        self.aux_explore_var = tk.BooleanVar(value=False)
        self.aux_explore_whip_var = tk.BooleanVar(value=False)
        self.aux_explore_coin_var = tk.BooleanVar(value=False)
        self.aux_explore_turns_var = tk.StringVar(value="1")
        self._explore_left_seconds: int = 0
        self._explore_countdown_after_id: Optional[str] = None
        self._explore_worker_running: bool = False
        self._explore_lock = threading.Lock()
        self._explore_seq: int = 0
        self._explore_stop_requested: bool = False
        self.log_amount_var = tk.StringVar(value="1")
        self.log_interval_var = tk.StringVar(value="60")
        self.log_transfer_mode_var = tk.StringVar(value="market")
        self._market_xfer_orders: list[dict] = []
        self._market_xfer_running: bool = False
        self._market_xfer_stop = threading.Event()
        self._market_xfer_thread: Optional[threading.Thread] = None
        self.log_market_status_var = tk.StringVar(value="Sẵn sàng")
        self._army_xfer_running: bool = False
        self._army_xfer_stop = threading.Event()
        self._army_xfer_thread: Optional[threading.Thread] = None
        self._army_xfer_selected_gids: set[int] = set()
        self.army_xfer_loop_var = tk.BooleanVar(value=True)
        self.army_xfer_status_var = tk.StringVar(value="Sẵn sàng")
        self._city_weapons_cache: dict[int, list[dict]] = {}
        self.dt_dest_x_var = tk.StringVar(value="")
        self.dt_dest_y_var = tk.StringVar(value="")

        # Cấu hình Thông Báo Đa Kênh & Bắt BOSS (ADR-0036)
        self.notification_config = NotificationConfig()
        self.bt_auto_capture_boss_var = tk.BooleanVar(value=False)
        self.bt_capture_morale_var = tk.StringVar(value="60")
        self._notify_win = None

        # Cấu hình Chế Tạo Quân Giới (ADR-0031)
        self.craft_configs: dict[int, CityCraftConfig] = {}
        self._craft_running: bool = False
        self._craft_stop_event = threading.Event()
        self._craft_thread: Optional[threading.Thread] = None
        self._craft_last_run: dict[int, float] = {}
        self._craft_statuses: dict[int, str] = {}

        # Trạng thái Mở Rương Hàng Loạt
        self._chest_running: bool = False
        self._chest_stop_event: Optional[threading.Event] = None
        self._chest_thread: Optional[threading.Thread] = None
        self._chest_queue: Optional[queue.Queue] = None

        # Trạng thái Cường Hóa Trang Bị & Hủy Đồ (ADR-0045)
        self._enhance_running: bool = False
        self._enhance_stop_event = threading.Event()
        self._enhance_auto_loaded: bool = False

        # Widget log đệm
        self.bld_log_text = tk.Text(self)
        self.logis_log_text = tk.Text(self)
        self._active_log_texts = [self.bld_log_text, self.logis_log_text]

        self._configure_styles()

        # Top Bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(10, 6))
        self.status = tk.StringVar(value="Đang kết nối & tải dữ liệu...")
        tk.Label(top, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")

        self.proxy_status_var = tk.StringVar()
        self.proxy_status_lbl = tk.Label(
            top, textvariable=self.proxy_status_var, bg=BG, fg="#8591ff", font=("Segoe UI", 9, "bold")
        )
        self.proxy_status_lbl.pack(side="left", padx=12)

        self.refresh_btn = ttk.Button(top, text="🔄 Làm mới", style="Action.TButton", command=self.reload)
        self.refresh_btn.pack(side="right")
        self.open_logs_btn = ttk.Button(
            top,
            text="📂 Mở thư mục Log",
            style="Action.TButton",
            command=lambda: open_logs_directory(),
        )
        self.open_logs_btn.pack(side="right", padx=(0, 6))

        self.open_notify_btn = ttk.Button(
            top,
            text="🔔 Cài Đặt Thông Báo",
            style="Action.TButton",
            command=self._open_notification_settings_dialog,
        )
        self.open_notify_btn.pack(side="right", padx=(0, 6))

        if self.proxy_pool:
            self.rotate_proxy_btn = ttk.Button(
                top,
                text="🔄 Đổi Proxy",
                style="Warning.TButton",
                command=self._do_manual_proxy_rotate,
            )
            self.rotate_proxy_btn.pack(side="right", padx=(0, 6))

        self._update_title_and_proxy_status()

        # Notebook chứa các Tab chức năng
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        t1 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t1, text="🏛️ Nội Chính & Nghiên Cứu")
        self._build_internal_and_research_tab(t1)

        t2 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t2, text="⚔️ Thảo Phạt")
        self._build_thaophat_tab(t2)

        t3 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t3, text="🏕️ Bình Man")
        self._build_binhman_tab(t3)

        t4 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t4, text="🧛 Vong Linh / Gọi Man")
        self._build_goidan_tab(t4)

        t5 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t5, text="🏰 Tổng quan")
        self._build_overview_tab(t5)

        t6 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t6, text="⚔️ Chiến Trường")
        self._build_battle_tab(t6)

        t7 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t7, text="🧧 Niên Thú")
        self._build_nien_thu_tab(t7)

        t8 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t8, text="🔨 Cường Hóa")
        self._build_enhance_tab(t8)

        def _on_main_tab_changed(_event=None):
            try:
                if self.notebook.index(self.notebook.select()) == 7 and not getattr(self, "_enhance_auto_loaded", False):
                    self._enhance_auto_loaded = True
                    self._load_enhance_resources()
                    self._load_enhance_warehouse(getattr(self, "_enh_equip_type", 1))
            except Exception:
                pass

        self.notebook.bind("<<NotebookTabChanged>>", _on_main_tab_changed)

        # Gắn hook tự động lưu cấu hình cho toàn bộ biến UI
        self._bind_auto_save_hooks()

        # Tự động nạp hồ sơ cấu hình tổng hợp mặc định theo tài khoản
        acc_prof = Path(self.default_profile_name)
        if acc_prof.exists():
            try:
                with self._suppress_auto_save():
                    self._load_unified_profile(acc_prof)
            except Exception:
                pass
        elif Path("auto_profile.json").exists():
            try:
                with self._suppress_auto_save():
                    self._load_unified_profile(Path("auto_profile.json"))
                    if hasattr(self, "profile_path_var"):
                        self.profile_path_var.set(self.default_profile_name)
                    self._active_profile_path = acc_prof
            except Exception:
                pass

        self.reload()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

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

        style.configure("Action.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Action.TButton", background=[("active", "#8591ff")])
        style.configure("Success.TButton", background=SUCCESS, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Success.TButton", background=[("active", "#34c759")])
        style.configure("Danger.TButton", background=DANGER, foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Danger.TButton", background=[("active", "#ff4d4f"), ("disabled", "#552222")])
        style.configure("Warning.TButton", background="#f59e0b", foreground="white", font=("Segoe UI", 10, "bold"), padding=6)
        style.map("Warning.TButton", background=[("active", "#fbbf24")])

    def _on_engine_log(self, task_id: str, msg: str):
        if task_id == "nien_thu":
            try:
                self.after(0, self._append_nt_log, msg)
            except Exception:
                pass

    def _on_engine_status(self, task_id: str, status: str):
        if task_id != "nien_thu":
            return

        def _update():
            if not hasattr(self, "nt_start_btn"):
                return
            if status in (TaskStatus.STOPPED, TaskStatus.COMPLETED):
                self.nt_start_btn.configure(text="▶️ Bắt đầu Niên Thú", style="Success.TButton")
                if hasattr(self, "nt_status_var"):
                    label = "Đã hoàn tất (玉兔呈祥)" if status == TaskStatus.COMPLETED else "Đã dừng"
                    self.nt_status_var.set(label)
            elif status == TaskStatus.PAUSED_CAPTCHA:
                self.nt_start_btn.configure(text="▶️ Bắt đầu Niên Thú", style="Success.TButton")
                if hasattr(self, "nt_status_var"):
                    self.nt_status_var.set("Tạm dừng (Captcha)")

        try:
            self.after(0, _update)
        except Exception:
            pass

    def _append_text_buffer(
        self,
        widget: tk.Text,
        line: str,
        max_lines: int = DEFAULT_MAX_LOG_LINES,
        trim_batch: int = BATCH_TRIM_LINES,
    ):
        """Chèn dòng mới vào widget Text và tự động cắt tỉa theo khối khi vượt max_lines (ADR-0030)."""
        if not widget:
            return

        def _do_append():
            if not widget.winfo_exists():
                return
            widget.insert("end", line)
            try:
                raw_idx = int(widget.index("end-1c").split(".")[0])
                line_count = (raw_idx - 1) if widget.get("end-2c", "end-1c") == "\n" else raw_idx
                if line_count > max_lines:
                    target_lines = max(1, max_lines - trim_batch)
                    lines_to_delete = line_count - target_lines
                    widget.delete("1.0", f"{lines_to_delete + 1}.0")
            except Exception:
                pass
            try:
                widget.see("end")
            except Exception:
                pass

        try:
            if threading.current_thread() is threading.main_thread():
                _do_append()
            else:
                self.after(0, _do_append)
        except Exception:
            _do_append()

    def _log_global(self, msg: str):
        """Ghi thông báo hệ thống tới tất cả các tab log đang hiển thị."""

        def _do_append():
            line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
            for attr in (
                "tp_log_text",
                "gd_log_text",
                "bm_log_text",
                "dt_log_text",
                "bld_log_text",
                "logis_log_text",
                "bt_log_text",
                "enhance_log_text",
            ):
                widget = getattr(self, attr, None)
                if widget and hasattr(widget, "winfo_exists"):
                    try:
                        self._append_text_buffer(widget, line)
                    except Exception:
                        pass

        try:
            self.after(0, _do_append)
        except Exception:
            pass

    def _do_relogin(self):
        if not self.gateway:
            messagebox.showwarning("Cảnh báo", "Chưa khởi tạo gateway!")
            return

        def run_relogin():
            try:
                self._log_global("🔑 Đang thực hiện đăng nhập lại tài khoản...")
                ok = False
                if self.gateway.relogin_callback:
                    ok = bool(self.gateway.relogin_callback())
                if ok:
                    self._log_global("✅ Đăng nhập lại thành công! Đang tải lại dữ liệu...")
                    self.after(0, self.reload)
                else:
                    self._log_global("❌ Đăng nhập lại không thành công hoặc không có relogin callback.")
            except Exception as e:
                self._log_global(f"❌ Lỗi đăng nhập lại: {e}")

        threading.Thread(target=run_relogin, daemon=True).start()

    def _update_title_and_proxy_status(self):
        title_base = (
            f"LinhVuong - S{self.server_id} - [{self.username}]"
            if self.username
            else f"LinhVuong - Server {self.server_id}"
        )
        if self.proxy_pool:
            active = self.proxy_pool.get_active()
            alive_cnt = self.proxy_pool.alive_count()
            tot_cnt = self.proxy_pool.total_count()
            if active:
                p_text = f"Proxy: {active.display_name} ({alive_cnt}/{tot_cnt} sống)"
            else:
                p_text = f"Proxy: Hết proxy sống ({alive_cnt}/{tot_cnt})"
            if hasattr(self, "proxy_status_var"):
                self.proxy_status_var.set(f"🌐 {p_text}")
            self.title(f"{title_base} | {p_text}")
        else:
            if hasattr(self, "proxy_status_var"):
                if self._proxy_raw:
                    self.proxy_status_var.set(f"🌐 Proxy: {self._proxy_raw}")
                else:
                    self.proxy_status_var.set("")
            self.title(title_base)

    def _do_manual_proxy_rotate(self):
        if not self.proxy_pool:
            messagebox.showinfo("Thông báo", "Phiên hiện tại không sử dụng Bể Proxy (ProxyPool).")
            return
        new_ep = self.proxy_pool.failover(self.session)
        if new_ep:
            self._log_global(f"🔄 Đã chủ động đổi sang proxy mới: {new_ep.display_name}")
            self._update_title_and_proxy_status()
        else:
            self._log_global("❌ Không còn proxy nào khả dụng để đổi.")

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
        sync_changed = False
        had_loaded_profile_cities = bool(getattr(self, "_loaded_profile_city_names", None))
        with self._suppress_auto_save():
            self.roster = roster
            if hasattr(self, "_sync_state_with_roster"):
                sync_changed = self._sync_state_with_roster(roster)
            self.city_tree.delete(*self.city_tree.get_children())
            for base in roster.bases:
                coords = f"{base.pos_x},{base.pos_y}" if (base.pos_x or base.pos_y) else "-"
                self.city_tree.insert("", "end", iid=str(base.id), text=base.name, values=(base.type, base.id, coords))
            self.status.set(f"Đã tải {len(roster.cities)} thành, {len(roster.camps)} doanh trại thành công")
            self.refresh_btn.state(["!disabled"])
            if roster.bases:
                self.city_tree.selection_set(str(roster.bases[0].id))
                self._on_city()

            # Danh sách Căn cứ thi công (Thành & Doanh trại)
            if hasattr(self, "bld_bases_tree"):
                self.bld_bases_tree.delete(*self.bld_bases_tree.get_children())
                for base in roster.bases:
                    iid = str(base.id)
                    is_sel = (
                        "☑"
                        if (
                            base.id in self._selected_building_cities
                            or (
                                not self._selected_building_cities
                                and not had_loaded_profile_cities
                                and base == roster.bases[0]
                            )
                        )
                        else "☐"
                    )
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
                        self.bld_queue_frame.configure(text=f"Xây dựng: {first_base.name}")
                self._check_and_update_boost_status()
                self._schedule_periodic_boost_check()

            # Cập nhật Combobox
            all_base_items = [b.display_name for b in roster.bases]
            city_items = [c.display_name for c in roster.cities]
            camps_items = [c.display_name for c in roster.camps] if roster.camps else all_base_items

            for combo in (
                self.bld_city_combo,
                self.res_city_combo,
                self.bm_parent_city_combo,
                self.gd_city_combo,
                self.chest_city_combo,
            ):
                combo["values"] = city_items
                if city_items and (not combo.get() or combo.get() not in city_items):
                    combo.current(0)

            self._on_chest_type_selected()

            if self._research_city_id and hasattr(self, "res_city_combo") and roster.cities:
                for idx, c in enumerate(roster.cities):
                    if c.id == self._research_city_id:
                        if 0 <= idx < len(self.res_city_combo["values"]):
                            self.res_city_combo.current(idx)
                        break

            for combo in (self.log_from_city_combo, self.log_to_city_combo):
                combo["values"] = all_base_items
                if all_base_items and not combo.get():
                    combo.current(0)

            if hasattr(self, "army_xfer_from_combo") and hasattr(self, "army_xfer_to_combo"):
                self.army_xfer_from_combo["values"] = city_items
                self.army_xfer_to_combo["values"] = city_items
                if city_items:
                    if not self.army_xfer_from_combo.get() or self.army_xfer_from_combo.get() not in city_items:
                        self.army_xfer_from_combo.current(0)
                    if not self.army_xfer_to_combo.get() or self.army_xfer_to_combo.get() not in city_items:
                        self.army_xfer_to_combo.current(1 if len(city_items) > 1 else 0)
            if hasattr(self, "_populate_army_xfer_generals"):
                self._populate_army_xfer_generals()

            if hasattr(self, "tp_city_combo") and all_base_items:
                self.tp_city_combo["values"] = all_base_items
                tp_cid = getattr(self, "_pending_tp_city_id", None)
                matched = False
                if tp_cid is not None:
                    for idx, b in enumerate(roster.bases):
                        if b.id == tp_cid:
                            self.tp_city_combo.current(idx)
                            matched = True
                            break
                if not matched and (self.tp_city_combo.current() < 0 or not self.tp_city_combo.get()):
                    self.tp_city_combo.current(0)
                self._on_tp_city_selected()

            if hasattr(self, "nt_city_combo") and all_base_items:
                self.nt_city_combo["values"] = all_base_items
                nt_cid = getattr(self, "_pending_nt_city_id", None)
                nt_matched = False
                if nt_cid is not None:
                    for idx, b in enumerate(roster.bases):
                        if b.id == nt_cid:
                            self.nt_city_combo.current(idx)
                            nt_matched = True
                            break
                if not nt_matched and (self.nt_city_combo.current() < 0 or not self.nt_city_combo.get()):
                    self.nt_city_combo.current(0)
                self._on_nt_city_selected()

            bm_mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
            if hasattr(self, "bm_city_combo"):
                self.bm_city_combo["values"] = city_items if bm_mode == 2 else camps_items
                if (bm_mode == 2 and city_items) or camps_items:
                    if not self.bm_city_combo.get() or self.bm_city_combo.current() < 0:
                        self.bm_city_combo.current(0)

            if hasattr(self, "_refresh_bm_bases_tree"):
                self._refresh_bm_bases_tree()
            else:
                if camps_items and not self.bm_city_combo.get():
                    self.bm_city_combo.current(0)
                    self._on_bm_city_selected()

            if hasattr(self, "dt_camp_combo"):
                self.dt_camp_combo["values"] = camps_items
                if camps_items and not self.dt_camp_combo.get():
                    self.dt_camp_combo.current(0)
                    self._on_dt_camp_selected()

            if hasattr(self, "mo_city_combo"):
                mo_items = ["🌟 Tất cả các thành"] + all_base_items
                self.mo_city_combo["values"] = mo_items
                if not self.mo_city_combo.get() or self.mo_city_combo.get() not in mo_items:
                    self.mo_city_combo.current(0)
                self._refresh_morale_generals()

            if hasattr(self, "craft_city_combo"):
                self.craft_city_combo["values"] = city_items
                if not self.craft_city_combo.get() or self.craft_city_combo.get() not in city_items:
                    if city_items:
                        self.craft_city_combo.current(0)
                if hasattr(self, "_sync_craft_ui_from_current_city"):
                    self._sync_craft_ui_from_current_city()
                if hasattr(self, "_refresh_craft_tree"):
                    self._refresh_craft_tree()

            if city_items:
                self._fetch_city_buildings()
                self._on_gd_city_selected()

            if hasattr(self, "_on_tac_roster_updated"):
                self._on_tac_roster_updated()
            if hasattr(self, "_on_equip_roster_updated"):
                self._on_equip_roster_updated()
            if hasattr(self, "_on_rename_roster_updated"):
                self._on_rename_roster_updated()
            if hasattr(self, "_on_add_points_roster_updated"):
                self._on_add_points_roster_updated()

            today_str = time.strftime("%Y-%m-%d")
            if getattr(self, "aux_daily_reward_var", None) and self.aux_daily_reward_var.get():
                if getattr(self, "_last_daily_claim_date", None) != today_str:
                    self._last_daily_claim_date = today_str
                    self._do_claim_daily()
            if hasattr(self, "_check_and_notify_general_visit"):
                self._check_and_notify_general_visit(async_check=True)

        if sync_changed and getattr(self, "_auto_save_enabled", False) and hasattr(self, "_resolve_active_profile_target"):
            try:
                target = self._resolve_active_profile_target()
                if target.exists():
                    self._save_unified_profile(target)
                    if hasattr(self, "_append_bld_log"):
                        self._append_bld_log("🔄 Đã đồng bộ danh sách căn cứ thực tế vào hồ sơ JSON.")
            except Exception as exc:
                logger.debug(f"Đồng bộ hồ sơ sau khi tải roster thất bại: {exc}")

    def destroy(self):
        self._closing = True
        self._destroyed = True
        try:
            self._cancel_auto_save_timer()
            if getattr(self, "_auto_save_enabled", False) and getattr(self, "_auto_save_dirty", False):
                self._flush_auto_save()
        except Exception:
            pass
        try:
            if hasattr(self, "_morale_stop_event") and self._morale_stop_event:
                self._morale_stop_event.set()
            if hasattr(self, "_craft_stop_event") and self._craft_stop_event:
                self._craft_stop_event.set()
                self._craft_running = False
        except Exception:
            pass
        self._res_monitor_running = False
        try:
            if hasattr(self, "_general_visit_account_key"):
                from ..notifications import clear_general_visit_alerts

                clear_general_visit_alerts(self._general_visit_account_key())
        except Exception:
            pass
        try:
            if getattr(self, "_boost_after_id", None) is not None:
                self.after_cancel(self._boost_after_id)
            if getattr(self, "_boost_countdown_after_id", None) is not None:
                self.after_cancel(self._boost_countdown_after_id)
            if getattr(self, "_explore_countdown_after_id", None) is not None:
                self.after_cancel(self._explore_countdown_after_id)
        except Exception:
            pass
        for name in ("_tp_runner", "_gd_runner", "_bm_runner", "_bld_runner", "_res_runner"):
            runner = getattr(self, name, None)
            try:
                if runner is not None and hasattr(runner, "stop"):
                    runner.stop()
            except Exception:
                pass
        try:
            if getattr(self, "_ditrai_stop_event", None):
                self._ditrai_stop_event.set()
            if getattr(self, "_bt_stop_event", None):
                self._bt_stop_event.set()
            if getattr(self, "_tac_stop_event", None):
                self._tac_stop_event.set()
            if getattr(self, "_equip_stop_event", None):
                self._equip_stop_event.set()
            if getattr(self, "_enhance_stop_event", None):
                self._enhance_stop_event.set()
                self._enhance_running = False
            if getattr(self, "_chest_stop_event", None):
                self._chest_stop_event.set()
                self._chest_running = False
            if getattr(self, "_market_xfer_stop", None):
                self._market_xfer_stop.set()
                self._market_xfer_running = False
            if getattr(self, "_army_xfer_stop", None):
                self._army_xfer_stop.set()
                self._army_xfer_running = False
        except Exception:
            pass
        try:
            if hasattr(self, "engine"):
                self.engine.stop_all()
        except Exception:
            pass
        super().destroy()
        if getattr(self, "_standalone_window", None):
            try:
                self._standalone_window.destroy()
            except Exception:
                pass

    def title(self, text: Optional[str] = None) -> str:
        top = getattr(self, "_standalone_window", None) or self.winfo_toplevel()
        if top and hasattr(top, "title"):
            if text is not None:
                if getattr(self, "_standalone_window", None):
                    return top.title(text)
                elif hasattr(top, "update_account_title"):
                    top.update_account_title(self.username, text)
                return top.title(text)
            return top.title()
        return ""

    def geometry(self, geom: Optional[str] = None) -> str:
        top = getattr(self, "_standalone_window", None) or self.winfo_toplevel()
        if top and hasattr(top, "geometry"):
            return top.geometry(geom) if geom is not None else top.geometry()
        return ""

    def minsize(self, width: Optional[int] = None, height: Optional[int] = None):
        top = getattr(self, "_standalone_window", None) or self.winfo_toplevel()
        if top and hasattr(top, "minsize"):
            return top.minsize(width, height) if width is not None else top.minsize()
        return (0, 0)

    def withdraw(self):
        top = getattr(self, "_standalone_window", None) or self.winfo_toplevel()
        if top and hasattr(top, "withdraw"):
            top.withdraw()

    def deiconify(self):
        top = getattr(self, "_standalone_window", None) or self.winfo_toplevel()
        if top and hasattr(top, "deiconify"):
            top.deiconify()

    def resizable(self, width: Optional[bool] = None, height: Optional[bool] = None):
        top = getattr(self, "_standalone_window", None) or self.winfo_toplevel()
        if top and hasattr(top, "resizable"):
            return top.resizable(width, height)

    def protocol(self, name: str, func: Optional[Callable] = None):
        top = getattr(self, "_standalone_window", None) or self.winfo_toplevel()
        if top and hasattr(top, "protocol"):
            return top.protocol(name, func)
