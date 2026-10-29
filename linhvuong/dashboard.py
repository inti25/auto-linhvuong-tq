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
from typing import Any, Callable, Optional, Union

from .auth import login
from .battle import (
    ATTACK_ACTIONS,
    FORMATION_NAMES,
    STRATAGEMS,
    BattleController,
    BattleEngine,
    BattleState,
    BattleTroop,
    CombatConfig,
)
from .gateway import GatewayClient
from .engine import AutomationEngine, TaskStatus
from .locks import TargetLocks
from .logger import open_logs_directory, setup_logger
from .profile import BaseBinhManConfig, CityCraftConfig, CraftProfile, Profile, ProfileStore
from .gui import set_app_icon

logger = logging.getLogger("linhvuong.dashboard")
from .roster import Army, City, General, Roster, fetch_roster
from .scan import BasePeer, Scanner
from .tasks.base import CaptchaRequired, TaskContext
from .tasks.binh_man import MAN_TARGET_OPTIONS, MODE_CAMP, MODE_CITY, BinhMan
from .tasks.crafting import WEAPONS_DATA, WeaponCrafter, get_weapon_name
from .tasks.di_trai import DiTrai
from .tasks.building import BUILDING_NAMES, BuildingPlan, BuildingTask, parse_boost_remaining_time
from .tasks.goi_dan import GoiDan, VONG_LINH
from .tasks.logistics import ArmyTransferOrder, LogisticsTask
from .tasks.morale import MoraleTrainer
from .tasks.research import ResearchTask, TECH_NAMES, TechPlan
from .troops import ArmyProvisioner
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

# Cấu hình Cắt Tỉa Nhật Ký Giao Diện (ADR-0030)
DEFAULT_MAX_LOG_LINES = 500  # Ngưỡng dòng tối đa cho các tab tác vụ thông thường
BATCH_TRIM_LINES = 100  # Số dòng cắt tỉa theo khối khi chạm ngưỡng
COMBAT_MAX_LOG_LINES = 300  # Ngưỡng dòng tối đa cho tab Chiến Trường
COMBAT_TRIM_LINES = 60  # Số dòng cắt tỉa theo khối cho tab Chiến Trường


class MultiSelectDropdown(ttk.Menubutton):
    """Dropdown chọn nhiều lựa chọn với checkboxes trong tk.Menu."""

    def __init__(
        self,
        parent,
        options: list[tuple[int, str]],
        default_selected: Optional[list[int]] = None,
        width: int = 22,
        command: Optional[Callable[[list[int]], None]] = None,
        categories: Optional[dict[str, list[int]]] = None,
        **kwargs,
    ):
        super().__init__(parent, width=width, **kwargs)
        self.options = list(options)
        self.command = command
        self.categories = categories
        default_set = set(default_selected if default_selected is not None else [opt[0] for opt in self.options])
        self.vars: dict[int, tk.BooleanVar] = {
            val: tk.BooleanVar(value=(val in default_set)) for val, _ in self.options
        }

        self.menu = tk.Menu(self, tearoff=False)
        self["menu"] = self.menu

        self.menu.add_command(label="✅ Chọn tất cả", command=self.select_all)
        self.menu.add_command(label="❌ Bỏ chọn tất cả", command=self.deselect_all)
        self.menu.add_separator()

        if categories:
            opt_map = dict(self.options)
            for cat_name, item_ids in categories.items():
                sub = tk.Menu(self.menu, tearoff=False)

                def _make_cat_toggle(ids, select: bool):
                    def _fn():
                        for iid in ids:
                            if iid in self.vars:
                                self.vars[iid].set(select)
                        self._on_toggle()
                    return _fn

                sub.add_command(label=f"✅ Chọn tất cả ({len(item_ids)})", command=_make_cat_toggle(item_ids, True))
                sub.add_command(label=f"❌ Bỏ chọn nhóm", command=_make_cat_toggle(item_ids, False))
                sub.add_separator()

                for val in item_ids:
                    if val in opt_map:
                        sub.add_checkbutton(
                            label=opt_map[val],
                            variable=self.vars[val],
                            onvalue=True,
                            offvalue=False,
                            command=self._on_toggle,
                        )
                self.menu.add_cascade(label=f"{cat_name} ({len(item_ids)}) ‣", menu=sub)
        else:
            for val, label in self.options:
                self.menu.add_checkbutton(
                    label=label,
                    variable=self.vars[val],
                    onvalue=True,
                    offvalue=False,
                    command=self._on_toggle,
                )

        self._update_label()

    def _update_label(self) -> None:
        selected = self.get_selected()
        total = len(self.options)
        if len(selected) == total:
            self.config(text=f"Tất cả ({total}) ▾")
        elif not selected:
            self.config(text="Chưa chọn ▾")
        elif len(selected) <= 2:
            labels = []
            opt_map = dict(self.options)
            for val in selected:
                raw_lbl = opt_map.get(val, str(val))
                if " - " in raw_lbl:
                    labels.append(raw_lbl.split(" - ")[0])
                elif " (" in raw_lbl:
                    cleaned = raw_lbl.split(" (")[0]
                    if ". " in cleaned:
                        cleaned = cleaned.split(". ", 1)[-1]
                    labels.append(cleaned)
                else:
                    labels.append(raw_lbl)
            self.config(text=f"{', '.join(labels)} ▾")
        else:
            self.config(text=f"Đã chọn {len(selected)} loại ▾")

    def _on_toggle(self) -> None:
        self._update_label()
        if self.command:
            self.command(self.get_selected())

    def get_selected(self) -> list[int]:
        return [val for val, _ in self.options if self.vars[val].get()]

    def get_selected_str(self) -> str:
        return ",".join(str(x) for x in self.get_selected())

    def set_selected(self, values: Union[list[int], set[int], tuple[int, ...]]) -> None:
        val_set = {int(x) for x in values if str(x).isdigit()}
        for val, var in self.vars.items():
            var.set(val in val_set)
        self._update_label()
        if self.command:
            self.command(self.get_selected())

    def set_selected_str(self, s: str) -> None:
        if not s:
            self.deselect_all()
            return
        vals = []
        for x in str(s).split(","):
            try:
                vals.append(int(x.strip()))
            except ValueError:
                pass
        self.set_selected(vals)

    def select_all(self) -> None:
        for var in self.vars.values():
            var.set(True)
        self._update_label()
        if self.command:
            self.command(self.get_selected())

    def deselect_all(self) -> None:
        for var in self.vars.values():
            var.set(False)
        self._update_label()
        if self.command:
            self.command(self.get_selected())


class _LegacyComboAdapter:
    """Bộ chuyển đổi tương thích ngược cho code cũ hoặc test truy cập combobox."""

    def __init__(self, dropdown: MultiSelectDropdown):
        self._dropdown = dropdown
        self.values = [lbl for _, lbl in dropdown.options]

    def current(self, idx: Optional[int] = None):
        if idx is None:
            sel = self._dropdown.get_selected()
            if not sel:
                return 0
            for i, (val, _) in enumerate(self._dropdown.options):
                if val == sel[0]:
                    return i
            return 0
        if 0 <= idx < len(self._dropdown.options):
            val = self._dropdown.options[idx][0]
            self._dropdown.set_selected([val])

    def get(self) -> str:
        sel = self._dropdown.get_selected()
        if not sel:
            return ""
        opt_dict = dict(self._dropdown.options)
        return opt_dict.get(sel[0], str(sel[0]))

    def bind(self, sequence, func, add=None):
        pass

    def __getitem__(self, item):
        if item == "values":
            return self.values
        return None

    def __setitem__(self, item, val):
        if item == "values":
            self.values = val


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
        self.task.stop_event = self.stop_event
        if getattr(self.task, "sleep_fn", None) is time.sleep:
            self.task.sleep_fn = lambda s: self.wait(s)
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
    def __init__(self, task_or_tasks: Union[BinhMan, list[BinhMan]], interval: float, log_cb, status_cb):
        super().__init__("Bình Man", log_cb, status_cb)
        if isinstance(task_or_tasks, list):
            self.tasks: list[BinhMan] = task_or_tasks
        else:
            self.tasks: list[BinhMan] = [task_or_tasks]
        self.interval = interval

    @property
    def task(self) -> Optional[BinhMan]:
        return self.tasks[0] if self.tasks else None

    @task.setter
    def task(self, val: BinhMan):
        self.tasks = [val]

    def run(self):
        for t in self.tasks:
            t.stop_event = self.stop_event
            if getattr(t, "sleep_fn", None) is time.sleep:
                t.sleep_fn = lambda s: self.wait(s)
        self.status_cb("Đang chạy...")
        num_bases = len(self.tasks)
        if num_bases > 1:
            self.log(f"🚀 Bắt đầu điều phối Bình Man Đa Căn Cứ cho {num_bases} căn cứ...")
        else:
            self.log("🚀 Bắt đầu nhiệm vụ Bình Man...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            has_action = False
            try:
                for t in self.tasks:
                    if self.stop_event.is_set():
                        break
                    base_label = getattr(t, "base_name", "") or f"Căn cứ {t.origin_id}"
                    res = t.run_once()
                    if num_bases > 1:
                        self.log(f"[{base_label}] Lượt {cycle}: Kết quả -> {res}")
                    else:
                        self.log(f"Lượt {cycle}: Kết quả -> {res}")
                    if res not in ("no_target", "generals_busy", "camp_frozen", "waiting_morale", "target_claimed_by_other"):
                        has_action = True
            except CaptchaRequired:
                self.logger.warning("Server yêu cầu Captcha! Dừng nhiệm vụ Bình Man.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nhiệm vụ.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Bình Man: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            # Cơ chế chuyển lượt không chặn (ADR-0029): Chỉ khi toàn bộ các căn cứ đều không có hành động khả dụng mới nghỉ trọn vẹn interval giây
            wait_time = self.interval if not has_action else 1.0
            if self.wait_cycle(wait_time if not has_action else min(wait_time, 2.0)):
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

class Dashboard(tk.Frame):
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
        self.aux_tribute_var = tk.BooleanVar(value=False)
        self.log_amount_var = tk.StringVar(value="1")
        self.log_interval_var = tk.StringVar(value="60")
        self.dt_dest_x_var = tk.StringVar(value="")
        self.dt_dest_y_var = tk.StringVar(value="")

        # Cấu hình Chế Tạo Quân Giới (ADR-0031)
        self.craft_configs: dict[int, CityCraftConfig] = {}
        self._craft_running: bool = False
        self._craft_stop_event = threading.Event()
        self._craft_thread: Optional[threading.Thread] = None
        self._craft_last_run: dict[int, float] = {}
        self._craft_statuses: dict[int, str] = {}

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

        if self.proxy_pool:
            self.rotate_proxy_btn = ttk.Button(
                top,
                text="🔄 Đổi Proxy",
                style="Warning.TButton",
                command=self._do_manual_proxy_rotate,
            )
            self.rotate_proxy_btn.pack(side="right", padx=(0, 6))

        self._update_title_and_proxy_status()

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

        # Tab 4: Gọi Man & Vong Linh
        t4 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t4, text="🧛 Vong Linh / Gọi Man")
        self._build_goidan_tab(t4)

        # Tab 5: Tổng quan & Quân đội
        t5 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t5, text="🏰 Tổng quan")
        self._build_overview_tab(t5)

        # Tab 6: Chiến Trường
        t6 = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(t6, text="⚔️ Chiến Trường")
        self._build_battle_tab(t6)

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
        self.gen_tree = ttk.Treeview(f2, columns=("role", "lv", "hp", "status"), show="tree headings", selectmode="browse")
        for col, text, w in (("#0", "Tên tướng", 100), ("role", "Chức vụ", 70), ("lv", "Cấp", 35), ("hp", "Thể lực", 70), ("status", "Trạng thái", 90)):
            self.gen_tree.heading(col, text=text)
            self.gen_tree.column(col, width=w, anchor="center" if col in ("role", "lv", "status") else ("w" if col == "#0" else "e"))
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

        ttk.Button(mo_row1, text="☑ Tất cả", style="Action.TButton", command=self._select_all_morale_generals).pack(side="left", padx=2)
        ttk.Button(mo_row1, text="☐ Bỏ chọn", style="Action.TButton", command=self._deselect_all_morale_generals).pack(side="left", padx=2)

        mo_row2 = tk.Frame(mo_ctrl_f, bg=CARD)
        mo_row2.pack(fill="x", pady=(2, 0))

        self.mo_start_btn = ttk.Button(mo_row2, text="⚔️ Luyện Sĩ Khí", style="Action.TButton", command=self._start_morale_training)
        self.mo_start_btn.pack(side="left", padx=(2, 3))

        self.mo_stop_btn = ttk.Button(mo_row2, text="⏹️ Dừng", style="Danger.TButton", command=self._stop_morale_training, state="disabled")
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
        f_craft = ttk.LabelFrame(bottom_body, text="🛠️ Chế Tạo Quân Giới (Đa Thành)", style="Card.TLabelframe")
        f_craft.grid(row=0, column=1, sticky="nsew", padx=(3, 0))

        craft_ctrl_f = tk.Frame(f_craft, bg=CARD)
        craft_ctrl_f.pack(fill="x", padx=6, pady=4)

        cr_row1 = tk.Frame(craft_ctrl_f, bg=CARD)
        cr_row1.pack(fill="x", pady=(0, 2))

        tk.Label(cr_row1, text="Thành:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 4))
        self.craft_city_combo = ttk.Combobox(cr_row1, state="readonly", width=16)
        self.craft_city_combo.pack(side="left", padx=(0, 6))
        self.craft_city_combo.bind("<<ComboboxSelected>>", self._on_craft_city_selected)

        tk.Label(cr_row1, text="Quân giới:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(4, 4))
        weapon_options = [(wid, f"{wid}. {wname} ({wcat})") for wid, (wname, wcat) in sorted(WEAPONS_DATA.items())]
        weapon_categories = {
            "🗡️ Binh khí": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Binh khí"],
            "🏹 Cung nỗ": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Cung nỗ"],
            "🛡️ Khôi giáp": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Khôi giáp"],
            "🐎 Chiến mã": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Chiến mã"],
            "🚜 Xe ném đá": [wid for wid, (_, cat) in sorted(WEAPONS_DATA.items()) if cat == "Xe ném đá"],
        }
        self.craft_weapon_dropdown = MultiSelectDropdown(
            cr_row1,
            options=weapon_options,
            default_selected=[101],
            width=22,
            categories=weapon_categories,
            command=self._on_craft_weapon_dropdown_changed,
        )
        self.craft_weapon_dropdown.pack(side="left", padx=(0, 6))
        self.craft_weapon_combo = _LegacyComboAdapter(self.craft_weapon_dropdown)

        cr_row2 = tk.Frame(craft_ctrl_f, bg=CARD)
        cr_row2.pack(fill="x", pady=(2, 2))

        tk.Label(cr_row2, text="Số lượng/mẻ:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        self.craft_amount_var = tk.StringVar(value="1000")
        craft_amount_entry = ttk.Entry(cr_row2, textvariable=self.craft_amount_var, width=7)
        craft_amount_entry.pack(side="left", padx=(0, 6))
        craft_amount_entry.bind("<FocusOut>", lambda e: self._save_current_craft_form_to_config())

        tk.Label(cr_row2, text="Chu kỳ (phút):", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(4, 2))
        self.craft_interval_var = tk.StringVar(value="5")
        craft_interval_entry = ttk.Entry(cr_row2, textvariable=self.craft_interval_var, width=5)
        craft_interval_entry.pack(side="left", padx=(0, 6))
        craft_interval_entry.bind("<FocusOut>", lambda e: self._save_current_craft_form_to_config())

        self.craft_enable_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            cr_row2,
            text="Bật thành này",
            variable=self.craft_enable_var,
            style="TCheckbutton",
            command=self._on_craft_enable_toggled,
        ).pack(side="left", padx=(4, 4))

        cr_row3 = tk.Frame(craft_ctrl_f, bg=CARD)
        cr_row3.pack(fill="x", pady=(2, 0))

        ttk.Button(cr_row3, text="⚡ Chế tạo ngay", style="Action.TButton", command=self._do_craft_now).pack(side="left", padx=(2, 3))

        self.craft_start_btn = ttk.Button(cr_row3, text="▶️ Bắt đầu", style="Success.TButton", command=self._toggle_craft_running)
        self.craft_start_btn.pack(side="left", padx=3)

        self.craft_status_lbl = tk.Label(cr_row3, text="", bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self.craft_status_lbl.pack(side="left", padx=(6, 4))

        # Bảng trạng thái chế tạo đa thành
        craft_table_frame = tk.Frame(f_craft, bg=CARD)
        craft_table_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        craft_columns = ("sel", "city", "weapon", "amount", "interval", "status")
        self.craft_tree = ttk.Treeview(craft_table_frame, columns=craft_columns, show="headings", selectmode="browse")

        self.craft_tree.heading("sel", text="Bật")
        self.craft_tree.heading("city", text="Thành trì")
        self.craft_tree.heading("weapon", text="Quân Giới")
        self.craft_tree.heading("amount", text="Số lượng")
        self.craft_tree.heading("interval", text="Chu kỳ (phút)")
        self.craft_tree.heading("status", text="Trạng thái")

        self.craft_tree.column("sel", width=40, anchor="center")
        self.craft_tree.column("city", width=110, anchor="w")
        self.craft_tree.column("weapon", width=150, anchor="w")
        self.craft_tree.column("amount", width=75, anchor="e")
        self.craft_tree.column("interval", width=80, anchor="center")
        self.craft_tree.column("status", width=140, anchor="w")

        craft_scroll = ttk.Scrollbar(craft_table_frame, orient="vertical", command=self.craft_tree.yview)
        self.craft_tree.configure(yscrollcommand=craft_scroll.set)
        craft_scroll.pack(side="right", fill="y")
        self.craft_tree.pack(side="left", fill="both", expand=True)

        self.craft_tree.bind("<ButtonRelease-1>", self._on_craft_tree_click)
        self.craft_tree.bind("<<TreeviewSelect>>", self._on_craft_tree_select)

    # -------------------------------------------------------------------------
    # CHẾ TẠO QUÂN GIỚI ĐA THÀNH (ADR-0031)
    # -------------------------------------------------------------------------
    def _get_current_craft_city_id(self) -> Optional[int]:
        if not hasattr(self, "craft_city_combo"):
            return None
        sel_idx = self.craft_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        if 0 <= sel_idx < len(cities):
            return cities[sel_idx].id
        return None

    def _sync_craft_ui_from_current_city(self):
        cid = self._get_current_craft_city_id()
        if not cid:
            return
        if cid not in self.craft_configs:
            self.craft_configs[cid] = CityCraftConfig(city_id=cid, weapon_id=101, weapon_ids=[101], amount="1000", interval="5", enabled=False)
        cfg = self.craft_configs[cid]
        self.craft_amount_var.set(str(cfg.amount))
        self.craft_interval_var.set(str(cfg.interval))
        self.craft_enable_var.set(bool(cfg.enabled))

        wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
        if hasattr(self, "craft_weapon_dropdown"):
            self.craft_weapon_dropdown.set_selected(wids)

    def _save_current_craft_form_to_config(self):
        cid = self._get_current_craft_city_id()
        if not cid:
            return
        if hasattr(self, "craft_weapon_dropdown"):
            wids = self.craft_weapon_dropdown.get_selected()
        elif hasattr(self, "craft_weapon_combo"):
            w_val = self.craft_weapon_combo.get()
            try:
                wid = int(w_val.split(".")[0])
            except (ValueError, IndexError):
                wid = 101
            wids = [wid]
        else:
            wids = [101]

        if not wids:
            wids = [101]

        amount = self.craft_amount_var.get() if hasattr(self, "craft_amount_var") else "1000"
        interval = self.craft_interval_var.get() if hasattr(self, "craft_interval_var") else "5"
        enabled = self.craft_enable_var.get() if hasattr(self, "craft_enable_var") else False

        self.craft_configs[cid] = CityCraftConfig(
            city_id=cid,
            weapon_id=wids[0],
            weapon_ids=wids,
            amount=str(amount),
            interval=str(interval),
            enabled=bool(enabled),
        )
        self._refresh_craft_tree()

    def _on_craft_city_selected(self, _event=None):
        self._sync_craft_ui_from_current_city()

    def _on_craft_weapon_dropdown_changed(self, _selected_ids=None):
        self._save_current_craft_form_to_config()

    def _on_craft_weapon_selected(self, _event=None):
        self._save_current_craft_form_to_config()

    def _on_craft_enable_toggled(self):
        self._save_current_craft_form_to_config()

    def _refresh_craft_tree(self):
        if not hasattr(self, "craft_tree"):
            return
        cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        for c in cities:
            cid_str = str(c.id)
            cfg = self.craft_configs.get(c.id, CityCraftConfig(city_id=c.id, enabled=False))
            check = "☑" if cfg.enabled else "☐"
            wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
            if len(wids) == 1:
                w_display = f"{wids[0]}. {get_weapon_name(wids[0])}"
            elif len(wids) > 1:
                first_name = get_weapon_name(wids[0])
                w_display = f"{len(wids)} loại ({first_name}, ...)"
            else:
                w_display = "Chưa chọn"
            status = self._craft_statuses.get(c.id, "Sẵn sàng" if cfg.enabled else "Chưa kích hoạt")
            vals = (check, f"{c.name} ({c.id})", w_display, cfg.amount, cfg.interval, status)

            if self.craft_tree.exists(cid_str):
                self.craft_tree.item(cid_str, values=vals)
            else:
                self.craft_tree.insert("", "end", iid=cid_str, values=vals)

    def _on_craft_tree_click(self, event):
        region = self.craft_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.craft_tree.identify_column(event.x)
        row_id = self.craft_tree.identify_row(event.y)
        if not row_id:
            return
        try:
            cid = int(row_id)
        except ValueError:
            return

        if col == "#1":  # Bấm vào cột checkbox
            cfg = self.craft_configs.get(cid, CityCraftConfig(city_id=cid, enabled=False))
            cfg.enabled = not cfg.enabled
            self.craft_configs[cid] = cfg
            if cid == self._get_current_craft_city_id():
                self.craft_enable_var.set(cfg.enabled)
            self._refresh_craft_tree()
        else:
            self._select_craft_city_by_id(cid)

    def _on_craft_tree_select(self, _event=None):
        sel = self.craft_tree.selection()
        if not sel:
            return
        try:
            cid = int(sel[0])
            self._select_craft_city_by_id(cid)
        except ValueError:
            pass

    def _select_craft_city_by_id(self, target_cid: int):
        if not hasattr(self, "craft_city_combo"):
            return
        cities = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        for idx, c in enumerate(cities):
            if c.id == target_cid:
                self.craft_city_combo.current(idx)
                self._sync_craft_ui_from_current_city()
                break

    def _do_craft_now(self):
        self._save_current_craft_form_to_config()
        cid = self._get_current_craft_city_id()
        if not cid:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì cần chế tạo quân giới!")
            return
        cfg = self.craft_configs.get(cid)
        if not cfg:
            return

        wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
        if not wids:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 loại quân giới để chế tạo!")
            return

        amount = int(cfg.amount) if str(cfg.amount).isdigit() else 1000
        names = [get_weapon_name(wid) for wid in wids]
        names_str = ", ".join(names[:2]) + (f" (+{len(names)-2})" if len(names) > 2 else "")

        self.craft_status_lbl.config(text=f"Đang gửi lệnh chế tạo {amount}x [{names_str}]...")

        def _worker():
            crafter = WeaponCrafter(self.gateway)
            success_count = 0
            err_msg = ""
            for wid in wids:
                success, ret, msg = crafter.craft_once(
                    cid,
                    wid,
                    amount,
                    notify=lambda m: self._log_global(m),
                )
                if success:
                    success_count += 1
                else:
                    err_msg = msg
                    if ret == 32:  # Thiếu tài nguyên
                        break

            def _update_ui():
                if success_count == len(wids):
                    res_txt = f"Hoàn thành {success_count}/{len(wids)} loại ({time.strftime('%H:%M:%S')})"
                else:
                    res_txt = f"Chế tạo {success_count}/{len(wids)} loại. {err_msg}"
                self.craft_status_lbl.config(text=res_txt)
                self._craft_statuses[cid] = f"OK {success_count}/{len(wids)} ({time.strftime('%H:%M:%S')})" if success_count > 0 else (err_msg or "Lỗi")
                self._refresh_craft_tree()

            try:
                self.after(0, _update_ui)
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_craft_running(self):
        if not self._craft_running:
            self._save_current_craft_form_to_config()
            enabled_count = sum(1 for cfg in self.craft_configs.values() if cfg.enabled)
            if enabled_count == 0:
                messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 thành cần chế tạo quân giới!")
                return
            self._craft_running = True
            self._craft_stop_event.clear()
            self.craft_start_btn.configure(text="⏹️ Dừng", style="Danger.TButton")
            self.craft_status_lbl.config(text=f"Đang chạy chế tạo tự động cho {enabled_count} thành...")
            self._craft_thread = threading.Thread(target=self._craft_worker_loop, daemon=True)
            self._craft_thread.start()
        else:
            self._craft_running = False
            self._craft_stop_event.set()
            self.craft_start_btn.configure(text="▶️ Bắt đầu", style="Success.TButton")
            self.craft_status_lbl.config(text="Đã dừng chế tạo tự động.")

    def _craft_worker_loop(self):
        crafter = WeaponCrafter(self.gateway)
        while self._craft_running and not self._craft_stop_event.is_set():
            now = time.time()
            for cid, cfg in list(self.craft_configs.items()):
                if self._craft_stop_event.is_set():
                    break
                if not cfg.enabled:
                    continue
                last = self._craft_last_run.get(cid, 0)
                try:
                    interval_sec = float(cfg.interval) * 60.0
                except (ValueError, TypeError):
                    interval_sec = 300.0
                if now - last >= interval_sec:
                    amount = int(cfg.amount) if str(cfg.amount).isdigit() else 1000
                    wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
                    if not wids:
                        continue

                    def _set_pending(city_id=cid, count=len(wids)):
                        self._craft_statuses[city_id] = f"Đang chế tạo {count} loại quân giới..."
                        self._refresh_craft_tree()
                    try:
                        self.after(0, _set_pending)
                    except (RuntimeError, tk.TclError):
                        pass

                    succ_cnt = 0
                    last_ret = 0
                    for wid in wids:
                        if self._craft_stop_event.is_set():
                            break
                        succ, ret, msg = crafter.craft_once(
                            cid,
                            wid,
                            amount,
                            notify=lambda m: self._log_global(m),
                        )
                        last_ret = ret
                        if succ:
                            succ_cnt += 1
                        elif ret == 32:
                            # Hết tài nguyên trong thành, dừng các loại còn lại trong chu kỳ này
                            break

                    self._craft_last_run[cid] = time.time()
                    if succ_cnt == len(wids):
                        res_status = f"OK {succ_cnt}/{len(wids)} ({time.strftime('%H:%M:%S')})"
                    elif succ_cnt > 0:
                        res_status = f"Một phần ({succ_cnt}/{len(wids)})"
                    else:
                        res_status = f"Thất bại (ret={last_ret})"

                    def _set_done(city_id=cid, status_str=res_status):
                        self._craft_statuses[city_id] = status_str
                        self._refresh_craft_tree()
                    try:
                        self.after(0, _set_done)
                    except (RuntimeError, tk.TclError):
                        pass

            self._craft_stop_event.wait(1.0)

    # -------------------------------------------------------------------------
    # HỒ SƠ CẤU HÌNH TỔNG HỢP (UNIFIED PROFILE CONFIGURATION)
    # -------------------------------------------------------------------------
    def _collect_unified_profile(self) -> dict:
        if hasattr(self, "_save_bm_current_base_config"):
            self._save_bm_current_base_config()
        tp_city_id = None
        if hasattr(self, "tp_city_combo") and self.roster and self.roster.bases:
            sel_idx = self.tp_city_combo.current()
            if 0 <= sel_idx < len(self.roster.bases):
                tp_city_id = self.roster.bases[sel_idx].id
        elif getattr(self, "_pending_tp_city_id", None) is not None:
            tp_city_id = self._pending_tp_city_id

        tp_gens = []
        if hasattr(self, "tp_gen_tree"):
            tp_gens = [int(iid) for iid in self.tp_gen_tree.get_children() if self.tp_gen_tree.item(iid, "values")[0] == "☑"]
        if not tp_gens and getattr(self, "_pending_tp_generals", None):
            tp_gens = list(self._pending_tp_generals)

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
                "city_id": self._research_city_id,
                "techs": [],
            },
            "resource": {
                "gold_threshold": self.res_gold_thresh_var.get() if hasattr(self, "res_gold_thresh_var") else "100000000",
                "wood_pct": self.res_wood_pct_var.get() if hasattr(self, "res_wood_pct_var") else "70",
                "iron_pct": self.res_iron_pct_var.get() if hasattr(self, "res_iron_pct_var") else "70",
                "stone_pct": self.res_stone_pct_var.get() if hasattr(self, "res_stone_pct_var") else "70",
                "food_pct": self.res_food_pct_var.get() if hasattr(self, "res_food_pct_var") else "70",
                "gold_box_idx": self.res_gold_box_combo.current() if hasattr(self, "res_gold_box_combo") else 1,
                "tn_box_idx": self.res_tn_box_combo.current() if hasattr(self, "res_tn_box_combo") else 3,
                "auto_open_box": bool(self.bld_open_box_var.get()) if hasattr(self, "bld_open_box_var") else False,
                "resource_cities": sorted(list(self._selected_resource_cities)),
            },
            "thao_phat": {
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
            },
            "goi_dan": {
                "mode_idx": self.gd_mode_combo.current() if hasattr(self, "gd_mode_combo") else 0,
                "target_type": self._get_gd_target_type() if hasattr(self, "_get_gd_target_type") else 301,
                "target_types": self.gd_target_dropdown.get_selected() if hasattr(self, "gd_target_dropdown") else [301],
                "radius": self.gd_radius_var.get() if hasattr(self, "gd_radius_var") else "5",
                "auto_recover": bool(self.gd_recover_var.get()) if hasattr(self, "gd_recover_var") else True,
                "interval": self.gd_interval_var.get() if hasattr(self, "gd_interval_var") else "10",
                "generals": [int(iid) for iid in self.gd_gen_tree.get_children() if self.gd_gen_tree.item(iid, "values")[0] == "☑"] if hasattr(self, "gd_gen_tree") else [],
                "target_infantry": self.gd_target_inf_var.get() if hasattr(self, "gd_target_inf_var") else "0",
                "target_cavalry": self.gd_target_cav_var.get() if hasattr(self, "gd_target_cav_var") else "0",
                "target_archers": self.gd_target_arc_var.get() if hasattr(self, "gd_target_arc_var") else "0",
                "auto_recruit": bool(self.gd_auto_recruit_var.get()) if hasattr(self, "gd_auto_recruit_var") else True,
                "auto_morale": bool(self.gd_auto_morale_var.get()) if hasattr(self, "gd_auto_morale_var") else True,
                "min_morale": self.gd_min_morale_var.get() if hasattr(self, "gd_min_morale_var") else "95",
            },
            "binh_man": {
                "mode": self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1,
                "radius": self.bm_radius_var.get() if hasattr(self, "bm_radius_var") else "5",
                "min_army": self.bm_min_army_var.get() if hasattr(self, "bm_min_army_var") else "3000",
                "min_hp": self.bm_min_hp_var.get() if hasattr(self, "bm_min_hp_var") else "50",
                "auto_comfort": bool(self.bm_comfort_var.get()) if hasattr(self, "bm_comfort_var") else True,
                "interval": self.bm_interval_var.get() if hasattr(self, "bm_interval_var") else "15",
                "camp_id": self.bm_camp_id_var.get() if hasattr(self, "bm_camp_id_var") else "",
                "threshold": self.bm_threshold_var.get() if hasattr(self, "bm_threshold_var") else "30",
                "mantypes": self.bm_mantypes_dropdown.get_selected_str() if hasattr(self, "bm_mantypes_dropdown") else (self.bm_mantypes_var.get() if hasattr(self, "bm_mantypes_var") else "7,8,9,10"),
                "target_types": self.bm_mantypes_dropdown.get_selected() if hasattr(self, "bm_mantypes_dropdown") else [7, 8, 9, 10],
                "generals": [int(iid) for iid in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(iid, "values")[0] == "☑"] if hasattr(self, "bm_gen_tree") else [],
                "target_infantry": self.bm_target_inf_var.get() if hasattr(self, "bm_target_inf_var") else "0",
                "target_cavalry": self.bm_target_cav_var.get() if hasattr(self, "bm_target_cav_var") else "0",
                "target_archers": self.bm_target_arc_var.get() if hasattr(self, "bm_target_arc_var") else "0",
                "auto_recruit": bool(self.bm_auto_recruit_var.get()) if hasattr(self, "bm_auto_recruit_var") else True,
                "auto_morale": bool(self.bm_auto_morale_var.get()) if hasattr(self, "bm_auto_morale_var") else True,
                "min_morale": self.bm_min_morale_var.get() if hasattr(self, "bm_min_morale_var") else "95",
                "current_base_id": self._current_bm_base_id,
                "bases": {str(bid): cfg.to_dict() for bid, cfg in self.bm_base_configs.items()} if hasattr(self, "bm_base_configs") else {},
            },
            "logistics": {
                "army_type_idx": self.log_army_combo.current() if hasattr(self, "log_army_combo") else 0,
                "amount": self.log_amount_var.get() if hasattr(self, "log_amount_var") else "1000",
                "auto_daily_reward": bool(self.aux_daily_reward_var.get()) if hasattr(self, "aux_daily_reward_var") else True,
            },
            "ditrai": {
                "dest_x": self.dt_dest_x_var.get() if hasattr(self, "dt_dest_x_var") else "",
                "dest_y": self.dt_dest_y_var.get() if hasattr(self, "dt_dest_y_var") else "",
            },
            "combat": {
                "auto_counter_formation": bool(self.bt_auto_counter_var.get()) if hasattr(self, "bt_auto_counter_var") else True,
                "formation_window_seconds": self.bt_window_var.get() if hasattr(self, "bt_window_var") else "15",
                "attack_action_mode": self.bt_action_mode_var.get() if hasattr(self, "bt_action_mode_var") else "adaptive",
                "action_combo_idx": self.bt_action_mode_combo.current() if hasattr(self, "bt_action_mode_combo") else 0,
                "skip_confused_enemy": bool(self.bt_skip_confused_var.get()) if hasattr(self, "bt_skip_confused_var") else True,
                "leave_boss_last": bool(self.bt_leave_boss_var.get()) if hasattr(self, "bt_leave_boss_var") else True,
                "auto_cleanse_confusion": bool(self.bt_cleanse_var.get()) if hasattr(self, "bt_cleanse_var") else True,
                "emergency_retreat_threshold": self.bt_retreat_var.get() if hasattr(self, "bt_retreat_var") else "0",
                "stratagem_combo_idx": self.bt_stratagem_combo.current() if hasattr(self, "bt_stratagem_combo") else 0,
            },
        }

        # Thu thập Hàng đợi Xây dựng (đa căn cứ & tương thích ngược)
        self._save_current_bld_tree_to_cache()
        cities_cfg = {}
        all_cids = set(self._city_building_plans.keys()) | self._selected_building_cities | self._selected_resource_cities
        if self._research_city_id:
            all_cids.add(self._research_city_id)
        if self.roster:
            for b in self.roster.bases:
                all_cids.add(b.id)

        for cid in sorted(all_cids):
            plans = self._city_building_plans.get(cid, [])
            base_name = ""
            if self.roster:
                b = self.roster.base_by_id(cid)
                if b:
                    base_name = b.name
            if not base_name and hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(cid)):
                base_name = self.bld_bases_tree.item(str(cid), "text")
            is_enabled = cid in self._selected_building_cities
            is_resource = cid in self._selected_resource_cities
            cities_cfg[str(cid)] = {
                "name": base_name,
                "enabled": is_enabled,
                "resource": is_resource,
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

        # Thu thập Chế Tạo Quân Giới (ADR-0031)
        if hasattr(self, "_save_current_craft_form_to_config"):
            self._save_current_craft_form_to_config()
        craft_cities = {}
        for cid, cfg in getattr(self, "craft_configs", {}).items():
            wids = cfg.weapon_ids if (hasattr(cfg, "weapon_ids") and cfg.weapon_ids) else [cfg.weapon_id]
            craft_cities[str(cid)] = {
                "city_id": cid,
                "weapon_id": cfg.weapon_id,
                "weapon_ids": list(wids),
                "amount": str(cfg.amount),
                "interval": str(cfg.interval),
                "enabled": bool(cfg.enabled),
            }
        profile["crafting"] = {"cities": craft_cities}

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
                if cinfo.get("resource", False):
                    self._selected_resource_cities.add(cid)
                elif "resource" in cinfo:
                    self._selected_resource_cities.discard(cid)
                if hasattr(self, "bld_bases_tree") and self.bld_bases_tree.exists(str(cid)):
                    sym = "☑" if cid in self._selected_building_cities else "☐"
                    sym_res = "☑" if cid in self._selected_resource_cities else "☐"
                    vals = list(self.bld_bases_tree.item(str(cid), "values"))
                    if vals:
                        vals[0] = sym
                        if len(vals) > 1:
                            vals[1] = sym_res
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
            if "city_id" in res_data and res_data["city_id"] is not None:
                try:
                    self._research_city_id = int(res_data["city_id"])
                    if hasattr(self, "bld_bases_tree"):
                        for iid in self.bld_bases_tree.get_children(""):
                            vals = list(self.bld_bases_tree.item(iid, "values"))
                            if len(vals) > 2:
                                vals[2] = "★" if int(iid) == self._research_city_id else "☐"
                                self.bld_bases_tree.item(iid, values=vals)
                except (ValueError, TypeError):
                    pass
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

        # 2b. Tài Nguyên
        if "resource" in data and isinstance(data["resource"], dict):
            res_cfg = data["resource"]
            if hasattr(self, "res_gold_thresh_var") and "gold_threshold" in res_cfg:
                self.res_gold_thresh_var.set(str(res_cfg["gold_threshold"]))
            if hasattr(self, "res_wood_pct_var") and "wood_pct" in res_cfg:
                self.res_wood_pct_var.set(str(res_cfg["wood_pct"]))
            if hasattr(self, "res_iron_pct_var") and "iron_pct" in res_cfg:
                self.res_iron_pct_var.set(str(res_cfg["iron_pct"]))
            if hasattr(self, "res_stone_pct_var") and "stone_pct" in res_cfg:
                self.res_stone_pct_var.set(str(res_cfg["stone_pct"]))
            if hasattr(self, "res_food_pct_var") and "food_pct" in res_cfg:
                self.res_food_pct_var.set(str(res_cfg["food_pct"]))
            if hasattr(self, "bld_open_box_var") and "auto_open_box" in res_cfg:
                self.bld_open_box_var.set(bool(res_cfg["auto_open_box"]))
            if hasattr(self, "res_gold_box_combo") and "gold_box_idx" in res_cfg:
                try:
                    g_idx = int(res_cfg["gold_box_idx"])
                    if 0 <= g_idx < len(self.res_gold_box_combo["values"]):
                        self.res_gold_box_combo.current(g_idx)
                except (ValueError, IndexError):
                    pass
            if hasattr(self, "res_tn_box_combo") and "tn_box_idx" in res_cfg:
                try:
                    tn_idx = int(res_cfg["tn_box_idx"])
                    if 0 <= tn_idx < len(self.res_tn_box_combo["values"]):
                        self.res_tn_box_combo.current(tn_idx)
                except (ValueError, IndexError):
                    pass
            if "resource_cities" in res_cfg and isinstance(res_cfg["resource_cities"], list):
                self._selected_resource_cities = {int(x) for x in res_cfg["resource_cities"]}
                if hasattr(self, "bld_bases_tree"):
                    for iid in self.bld_bases_tree.get_children(""):
                        try:
                            cid = int(iid)
                            vals = list(self.bld_bases_tree.item(iid, "values"))
                            if len(vals) > 1:
                                vals[1] = "☑" if cid in self._selected_resource_cities else "☐"
                                self.bld_bases_tree.item(iid, values=vals)
                        except ValueError:
                            pass
            loaded_sections.append("Tài Nguyên")
            if hasattr(self, "_append_bld_log"):
                self._append_bld_log(f"📂 Đã nạp cấu hình tài nguyên cho {len(self._selected_resource_cities)} thành từ hồ sơ.")

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

            loaded_sections.append("Thảo Phạt")

        # 4. Gọi Man
        gd_raw = data.get("goi_dan") or data.get("goi_man")
        if gd_raw and isinstance(gd_raw, dict):
            gd_data = gd_raw
            if hasattr(self, "gd_target_dropdown"):
                if "target_types" in gd_data and gd_data["target_types"]:
                    self.gd_target_dropdown.set_selected(gd_data["target_types"])
                elif "target_type" in gd_data:
                    self.gd_target_dropdown.set_selected([int(gd_data["target_type"])])
                elif "mode_idx" in gd_data:
                    try:
                        self.gd_mode_combo.current(int(gd_data["mode_idx"]))
                    except Exception:
                        pass
            elif hasattr(self, "gd_mode_combo"):
                if "target_type" in gd_data:
                    ttype = int(gd_data["target_type"])
                    for idx, (t, _) in enumerate(getattr(self, "gd_target_options", [])):
                        if t == ttype:
                            self.gd_mode_combo.current(idx)
                            break
                elif "mode_idx" in gd_data:
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
            if hasattr(self, "gd_target_inf_var") and "target_infantry" in gd_data:
                self.gd_target_inf_var.set(str(gd_data["target_infantry"]))
            if hasattr(self, "gd_target_cav_var") and "target_cavalry" in gd_data:
                self.gd_target_cav_var.set(str(gd_data["target_cavalry"]))
            if hasattr(self, "gd_target_arc_var") and "target_archers" in gd_data:
                self.gd_target_arc_var.set(str(gd_data["target_archers"]))
            if hasattr(self, "gd_auto_recruit_var") and "auto_recruit" in gd_data:
                self.gd_auto_recruit_var.set(bool(gd_data["auto_recruit"]))
            if hasattr(self, "gd_auto_morale_var") and "auto_morale" in gd_data:
                self.gd_auto_morale_var.set(bool(gd_data["auto_morale"]))
            if hasattr(self, "gd_min_morale_var") and "min_morale" in gd_data:
                self.gd_min_morale_var.set(str(gd_data["min_morale"]))
            if "generals" in gd_data and isinstance(gd_data["generals"], list):
                gd_gens = [int(x) for x in gd_data["generals"] if str(x).isdigit()]
                self._pending_gd_generals = set(gd_gens)
                if hasattr(self, "gd_gen_tree") and self.gd_gen_tree.get_children():
                    for iid in self.gd_gen_tree.get_children():
                        vals = list(self.gd_gen_tree.item(iid, "values"))
                        vals[0] = "☑" if int(iid) in self._pending_gd_generals else "☐"
                        self.gd_gen_tree.item(iid, values=vals)
                    self._update_gd_gen_count_label()
            loaded_sections.append("Gọi Man")

        # 5. Bình Man
        if "binh_man" in data and isinstance(data["binh_man"], dict):
            bm_data = data["binh_man"]
            if hasattr(self, "bm_mode_var") and "mode" in bm_data:
                try:
                    self.bm_mode_var.set(int(bm_data["mode"]))
                    if hasattr(self, "_update_bm_mode_ui_states"):
                        self._update_bm_mode_ui_states(int(bm_data["mode"]))
                except Exception:
                    pass
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
            if hasattr(self, "bm_camp_id_var") and "camp_id" in bm_data:
                self.bm_camp_id_var.set(str(bm_data["camp_id"]))
            if hasattr(self, "bm_mantypes_dropdown"):
                if "target_types" in bm_data and bm_data["target_types"]:
                    self.bm_mantypes_dropdown.set_selected(bm_data["target_types"])
                elif "mantypes" in bm_data:
                    self.bm_mantypes_dropdown.set_selected_str(str(bm_data["mantypes"]))
            if hasattr(self, "bm_mantypes_var") and "mantypes" in bm_data:
                self.bm_mantypes_var.set(str(bm_data["mantypes"]))
            if hasattr(self, "bm_threshold_var") and "threshold" in bm_data:
                self.bm_threshold_var.set(str(bm_data["threshold"]))
            if hasattr(self, "bm_target_inf_var") and "target_infantry" in bm_data:
                self.bm_target_inf_var.set(str(bm_data["target_infantry"]))
            if hasattr(self, "bm_target_cav_var") and "target_cavalry" in bm_data:
                self.bm_target_cav_var.set(str(bm_data["target_cavalry"]))
            if hasattr(self, "bm_target_arc_var") and "target_archers" in bm_data:
                self.bm_target_arc_var.set(str(bm_data["target_archers"]))
            if hasattr(self, "bm_auto_recruit_var") and "auto_recruit" in bm_data:
                self.bm_auto_recruit_var.set(bool(bm_data["auto_recruit"]))
            if hasattr(self, "bm_auto_morale_var") and "auto_morale" in bm_data:
                self.bm_auto_morale_var.set(bool(bm_data["auto_morale"]))
            if hasattr(self, "bm_min_morale_var") and "min_morale" in bm_data:
                self.bm_min_morale_var.set(str(bm_data["min_morale"]))
            if "current_base_id" in bm_data and bm_data["current_base_id"] is not None:
                try:
                    self._current_bm_base_id = int(bm_data["current_base_id"])
                except (ValueError, TypeError):
                    pass
            if "bases" in bm_data and isinstance(bm_data["bases"], dict) and bm_data["bases"]:
                self.bm_base_configs.clear()
                self._pending_bm_generals = None
                for bid_str, bcfg_raw in bm_data["bases"].items():
                    if isinstance(bcfg_raw, dict):
                        try:
                            bid = int(bid_str)
                            self.bm_base_configs[bid] = BaseBinhManConfig.from_dict(bcfg_raw)
                        except ValueError:
                            pass
                if hasattr(self, "bm_bases_tree") and self.roster:
                    self._refresh_bm_bases_tree()
            else:
                # Tương thích ngược tuyệt đối (ADR-0029 Section 1):
                # Tệp hồ sơ cũ chưa có trường 'bases', tự động ánh xạ các giá trị phẳng vào căn cứ đang hoạt động hoặc căn cứ đầu tiên
                bm_gens = [int(x) for x in bm_data.get("generals", []) if str(x).isdigit()] if "generals" in bm_data else []
                m_types_str = str(bm_data.get("mantypes", "7,8,9,10"))
                legacy_cfg = BaseBinhManConfig(
                    name="",
                    enabled=True,
                    mode=int(bm_data.get("mode", 1)),
                    radius=str(bm_data.get("radius", "5")),
                    threshold=str(bm_data.get("threshold", "30")),
                    camp_id=str(bm_data.get("camp_id", "")),
                    parent_city_id=str(bm_data.get("parent_city_id", "")),
                    mantypes=m_types_str,
                    target_types=[int(x.strip()) for x in m_types_str.split(",") if x.strip().isdigit()],
                    generals=bm_gens,
                    target_infantry=str(bm_data.get("target_infantry", "0")),
                    target_cavalry=str(bm_data.get("target_cavalry", "0")),
                    target_archers=str(bm_data.get("target_archers", "0")),
                    auto_recruit=bool(bm_data.get("auto_recruit", True)),
                    auto_morale=bool(bm_data.get("auto_morale", True)),
                    min_morale=str(bm_data.get("min_morale", "95")),
                )
                self._pending_bm_legacy_config = legacy_cfg
                target_bid = None
                if legacy_cfg.mode == 1 and legacy_cfg.camp_id and str(legacy_cfg.camp_id).lstrip("-").isdigit():
                    target_bid = int(legacy_cfg.camp_id)
                elif self._current_bm_base_id:
                    curr_b = next((b for b in self.roster.bases if b.id == self._current_bm_base_id), None) if self.roster else None
                    if curr_b and (legacy_cfg.mode == 1 or not curr_b.is_camp):
                        target_bid = self._current_bm_base_id
                if target_bid is None and self.roster:
                    if legacy_cfg.mode == 2 and self.roster.cities:
                        target_bid = self.roster.cities[0].id
                    elif legacy_cfg.mode == 1 and self.roster.camps:
                        target_bid = self.roster.camps[0].id
                    elif self.roster.bases:
                        target_bid = self.roster.bases[0].id

                if target_bid is not None:
                    self.bm_base_configs[target_bid] = legacy_cfg
                    self._current_bm_base_id = target_bid
                    if hasattr(self, "bm_bases_tree") and self.roster:
                        self._refresh_bm_bases_tree()
            if "generals" in bm_data and isinstance(bm_data["generals"], list):
                bm_gens = [int(x) for x in bm_data["generals"] if str(x).isdigit()]
                self._pending_bm_generals = set(bm_gens)
                if hasattr(self, "bm_gen_tree") and self.bm_gen_tree.get_children():
                    for iid in self.bm_gen_tree.get_children():
                        vals = list(self.bm_gen_tree.item(iid, "values"))
                        vals[0] = "☑" if int(iid) in self._pending_bm_generals else "☐"
                        self.bm_gen_tree.item(iid, values=vals)
                    self._update_bm_gen_count_label()
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
            if hasattr(self, "aux_daily_reward_var") and "auto_daily_reward" in log_data:
                self.aux_daily_reward_var.set(bool(log_data["auto_daily_reward"]))
            loaded_sections.append("Hậu Cần")

        # 7. Dịch Trại
        if "ditrai" in data and isinstance(data["ditrai"], dict):
            dt_data = data["ditrai"]
            if hasattr(self, "dt_dest_x_var") and "dest_x" in dt_data:
                self.dt_dest_x_var.set(str(dt_data["dest_x"]))
            if hasattr(self, "dt_dest_y_var") and "dest_y" in dt_data:
                self.dt_dest_y_var.set(str(dt_data["dest_y"]))
            loaded_sections.append("Dịch Trại")

        # 8. Chiến Trường & Mưu Lược
        if "combat" in data and isinstance(data["combat"], dict):
            cb_data = data["combat"]
            if hasattr(self, "bt_auto_counter_var") and "auto_counter_formation" in cb_data:
                self.bt_auto_counter_var.set(bool(cb_data["auto_counter_formation"]))
            if hasattr(self, "bt_window_var") and "formation_window_seconds" in cb_data:
                self.bt_window_var.set(str(cb_data["formation_window_seconds"]))
            if hasattr(self, "bt_action_mode_var") and "attack_action_mode" in cb_data:
                self.bt_action_mode_var.set(str(cb_data["attack_action_mode"]))
            if hasattr(self, "bt_action_mode_combo") and "action_combo_idx" in cb_data:
                try:
                    self.bt_action_mode_combo.current(int(cb_data["action_combo_idx"]))
                except Exception:
                    pass
            if hasattr(self, "bt_skip_confused_var") and "skip_confused_enemy" in cb_data:
                self.bt_skip_confused_var.set(bool(cb_data["skip_confused_enemy"]))
            if hasattr(self, "bt_leave_boss_var") and "leave_boss_last" in cb_data:
                self.bt_leave_boss_var.set(bool(cb_data["leave_boss_last"]))
            if hasattr(self, "bt_cleanse_var") and "auto_cleanse_confusion" in cb_data:
                self.bt_cleanse_var.set(bool(cb_data["auto_cleanse_confusion"]))
            if hasattr(self, "bt_retreat_var") and "emergency_retreat_threshold" in cb_data:
                self.bt_retreat_var.set(str(cb_data["emergency_retreat_threshold"]))
            if hasattr(self, "bt_stratagem_combo") and "stratagem_combo_idx" in cb_data:
                try:
                    self.bt_stratagem_combo.current(int(cb_data["stratagem_combo_idx"]))
                except Exception:
                    pass
            loaded_sections.append("Chiến Trường")

        # 9. Chế Tạo Quân Giới (ADR-0031)
        craft_raw = data.get("crafting") or data.get("weapon_crafting")
        if craft_raw and isinstance(craft_raw, dict):
            raw_cities = craft_raw.get("cities")
            if isinstance(raw_cities, dict):
                for cid_str, cinfo in raw_cities.items():
                    if isinstance(cinfo, dict):
                        try:
                            cid = int(cinfo.get("city_id") or cid_str)
                            self.craft_configs[cid] = CityCraftConfig.from_dict(cinfo)
                        except Exception:
                            pass
                if hasattr(self, "_sync_craft_ui_from_current_city"):
                    self._sync_craft_ui_from_current_city()
                if hasattr(self, "_refresh_craft_tree"):
                    self._refresh_craft_tree()
                loaded_sections.append("Chế Tạo Quân Giới")

        return loaded_sections

    def _save_unified_profile(self, filepath: Optional[Path] = None) -> Path:
        def_name = getattr(self, "default_profile_name", "auto_profile.json")
        target = filepath or Path(self.profile_path_var.get() if hasattr(self, "profile_path_var") and self.profile_path_var.get() else def_name)
        profile_dict = self._collect_unified_profile()
        prof = Profile.from_dict(profile_dict)
        target = ProfileStore.save(prof, target)
        if hasattr(self, "profile_path_var"):
            self.profile_path_var.set(target.name)
        return target

    def _load_unified_profile(self, filepath: Optional[Path] = None) -> tuple[bool, str]:
        def_name = getattr(self, "default_profile_name", "auto_profile.json")
        target = filepath or Path(self.profile_path_var.get() if hasattr(self, "profile_path_var") and self.profile_path_var.get() else def_name)
        if not target.exists():
            return False, f"Không tìm thấy file: {target.name}"
        try:
            prof = ProfileStore.load(target)
            sections = self._apply_unified_profile(prof.to_dict())
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

    def _append_text_buffer(
        self,
        widget: tk.Text,
        line: str,
        max_lines: int = DEFAULT_MAX_LOG_LINES,
        trim_batch: int = BATCH_TRIM_LINES,
    ):
        """Chèn dòng mới vào widget Text và tự động cắt tỉa theo khối khi vượt max_lines.

        Tuân thủ ADR-0030:
        - Cắt tỉa theo khối (batch trimming) thay vì cắt từng dòng lẻ tẻ nhằm tránh làm chậm giao diện.
        - Tự động cuộn xuống dòng cuối cùng (widget.see("end")).
        - Đảm bảo an toàn luồng nếu được gọi từ background thread.
        """
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

    def _append_tp_log(self, msg: str):
        self._append_text_buffer(self.tp_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _tp_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Thảo Phạt."""
        if hasattr(self, "tp_log_text") and self.tp_log_text:
            self.tp_log_text.delete("1.0", "end")

    # =========================================================================
    # TAB 3: GỌI MAN & VONG LINH
    # =========================================================================
    def _build_goidan_tab(self, parent):
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=6)

        tk.Label(top, text="Thành trì:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.gd_city_combo = ttk.Combobox(top, state="readonly", width=20)
        self.gd_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.gd_city_combo.bind("<<ComboboxSelected>>", self._on_gd_city_selected)

        tk.Label(top, text="Loại Man mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        self.gd_target_options = MAN_TARGET_OPTIONS
        self.gd_target_dropdown = MultiSelectDropdown(top, options=self.gd_target_options, default_selected=[301], width=22)
        self.gd_target_dropdown.grid(row=0, column=3, sticky="w", padx=4, pady=4)
        self.gd_mode_combo = _LegacyComboAdapter(self.gd_target_dropdown)

        tk.Label(top, text="Bán kính quét:", bg=BG, fg=FG).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.gd_radius_var = tk.StringVar(value="5")
        ttk.Entry(top, textvariable=self.gd_radius_var, width=8).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        tk.Label(top, text="Chu kỳ (s):", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.gd_interval_var = tk.StringVar(value="10")
        ttk.Entry(top, textvariable=self.gd_interval_var, width=8).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        # Row 2: Định mức quân đội (Bộ MT, Kỵ MT, Cung MT) & Nút Biên chế ngay
        tk.Label(top, text="Bộ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.gd_target_inf_var = tk.StringVar(value="0")
        ttk.Entry(top, textvariable=self.gd_target_inf_var, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        army_f = tk.Frame(top, bg=BG)
        army_f.grid(row=2, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        tk.Label(army_f, text="Kỵ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.gd_target_cav_var = tk.StringVar(value="0")
        ttk.Entry(army_f, textvariable=self.gd_target_cav_var, width=6).pack(side="left", padx=(0, 6))

        tk.Label(army_f, text="Cung MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.gd_target_arc_var = tk.StringVar(value="0")
        ttk.Entry(army_f, textvariable=self.gd_target_arc_var, width=6).pack(side="left", padx=(0, 8))

        self.gd_adjust_troops_btn = ttk.Button(army_f, text="⚔️ Biên chế ngay", style="Action.TButton", command=self._manual_adjust_gd_troops)
        self.gd_adjust_troops_btn.pack(side="left", padx=(0, 4))

        # Row 3: Tự động bổ sung lính, Tự động nâng sĩ khí, Sĩ khí tối thiểu
        self.gd_auto_recruit_var = tk.BooleanVar(value=True)
        self.gd_recover_var = self.gd_auto_recruit_var  # Giữ alias tương thích ngược
        ttk.Checkbutton(
            top,
            text="Tự động bổ sung lính",
            variable=self.gd_auto_recruit_var,
            style="TCheckbutton",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        mor_f = tk.Frame(top, bg=BG)
        mor_f.grid(row=3, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        self.gd_auto_morale_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(mor_f, text="Tự động nâng sĩ khí", variable=self.gd_auto_morale_var, style="TCheckbutton").pack(side="left", padx=(0, 8))
        tk.Label(mor_f, text="Sĩ khí tối thiểu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.gd_min_morale_var = tk.StringVar(value="95")
        ttk.Entry(mor_f, textvariable=self.gd_min_morale_var, width=5).pack(side="left")

        # Điều khiển
        ctrl_frame = tk.Frame(top, bg=BG)
        ctrl_frame.grid(row=0, column=4, rowspan=4, padx=16)
        self.gd_start_btn = ttk.Button(ctrl_frame, text="▶️ Bắt đầu Gọi Man", style="Success.TButton", command=self._toggle_goidan)
        self.gd_start_btn.pack(side="top", pady=2)
        self.gd_once_btn = ttk.Button(ctrl_frame, text="⚡ Chạy 1 Lượt", style="Action.TButton", command=self._run_goidan_once)
        self.gd_once_btn.pack(side="top", pady=2)

        # Bảng tướng & Log sắp xếp theo container body
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        # Row 0: Bảng danh sách võ tướng
        f_top = ttk.LabelFrame(body, text="Võ tướng xuất kích", style="Card.TLabelframe")
        f_top.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        btn_bar = tk.Frame(f_top, bg=BG)
        btn_bar.pack(fill="x", padx=4, pady=2)
        ttk.Button(btn_bar, text="✅ Chọn tất cả", style="Secondary.TButton", command=self._select_all_gd_gens).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="❌ Bỏ chọn tất cả", style="Secondary.TButton", command=self._deselect_all_gd_gens).pack(side="left", padx=2)
        self.gd_gen_count_lbl = tk.Label(btn_bar, text="Đã chọn: 0 tướng (0 đợt xuất kích)", bg=BG, fg=FG, font=("Segoe UI", 9, "bold"))
        self.gd_gen_count_lbl.pack(side="left", padx=8)

        self.gd_gen_tree = ttk.Treeview(
            f_top,
            columns=("select", "lv", "stamina", "morale", "infantry", "cavalry", "archers", "total_army"),
            show="tree headings",
            selectmode="browse",
            height=5,
        )
        self.gd_gen_tree.heading("#0", text="Tên võ tướng")
        self.gd_gen_tree.heading("select", text="Chọn")
        self.gd_gen_tree.heading("lv", text="Cấp")
        self.gd_gen_tree.heading("stamina", text="Thể lực")
        self.gd_gen_tree.heading("morale", text="Sĩ khí")
        self.gd_gen_tree.heading("infantry", text="Bộ binh")
        self.gd_gen_tree.heading("cavalry", text="Kỵ binh")
        self.gd_gen_tree.heading("archers", text="Cung binh")
        self.gd_gen_tree.heading("total_army", text="Tổng quân")

        self.gd_gen_tree.column("#0", width=140)
        self.gd_gen_tree.column("select", width=50, anchor="center")
        self.gd_gen_tree.column("lv", width=50, anchor="center")
        self.gd_gen_tree.column("stamina", width=75, anchor="center")
        self.gd_gen_tree.column("morale", width=65, anchor="center")
        self.gd_gen_tree.column("infantry", width=80, anchor="e")
        self.gd_gen_tree.column("cavalry", width=80, anchor="e")
        self.gd_gen_tree.column("archers", width=80, anchor="e")
        self.gd_gen_tree.column("total_army", width=85, anchor="e")

        gen_scroll = ttk.Scrollbar(f_top, orient="vertical", command=self.gd_gen_tree.yview)
        self.gd_gen_tree.configure(yscrollcommand=gen_scroll.set)
        self.gd_gen_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        gen_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))
        self.gd_gen_tree.bind("<ButtonRelease-1>", self._on_gd_gen_toggle)

        # Row 1: Khung nhật ký log Gọi Man & Vong Linh
        f_bottom = ttk.LabelFrame(body, text="Nhật ký Gọi Man & Vong Linh", style="Card.TLabelframe")
        f_bottom.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        log_bar = tk.Frame(f_bottom, bg=CARD)
        log_bar.pack(side="top", fill="x", padx=4, pady=(2, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._gd_clear_log).pack(side="right")

        log_scroll = ttk.Scrollbar(f_bottom, orient="vertical")
        self.gd_log_text = tk.Text(f_bottom, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0, yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.gd_log_text.yview)
        self.gd_log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        log_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))

    def _update_gd_gen_count_label(self):
        if not hasattr(self, "gd_gen_count_lbl") or not hasattr(self, "gd_gen_tree"):
            return
        selected_count = sum(1 for item in self.gd_gen_tree.get_children() if self.gd_gen_tree.item(item, "values")[0] == "☑")
        batches = (selected_count + 2) // 3 if selected_count > 0 else 0
        self.gd_gen_count_lbl.config(text=f"Đã chọn: {selected_count} tướng ({batches} đợt xuất kích)")

    def _select_all_gd_gens(self):
        for item in self.gd_gen_tree.get_children():
            vals = list(self.gd_gen_tree.item(item, "values"))
            vals[0] = "☑"
            self.gd_gen_tree.item(item, values=vals)
        self._update_gd_gen_count_label()

    def _deselect_all_gd_gens(self):
        for item in self.gd_gen_tree.get_children():
            vals = list(self.gd_gen_tree.item(item, "values"))
            vals[0] = "☐"
            self.gd_gen_tree.item(item, values=vals)
        self._update_gd_gen_count_label()

    def _on_gd_gen_toggle(self, event):
        item = self.gd_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.gd_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.gd_gen_tree.item(item, values=vals)
        self._update_gd_gen_count_label()

    def _on_gd_city_selected(self, _event=None):
        sel_idx = self.gd_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else []
        if sel_idx < 0 or sel_idx >= len(cities):
            return
        city = cities[sel_idx]
        self.gd_gen_tree.delete(*self.gd_gen_tree.get_children())
        pending = self._pending_gd_generals
        count = 0
        for g in self.roster.generals_of(city.id):
            if g.role != "vo":
                continue
            army = self.roster.army_of(g.id)
            inf = army.infantry if army else 0
            cav = army.cavalry if army else 0
            arc = army.archers if army else 0
            total = army.total if army else 0
            if pending is not None:
                checked = "☑" if g.id in pending else "☐"
            else:
                checked = "☑" if count < 3 else "☐"
            self.gd_gen_tree.insert(
                "",
                "end",
                iid=str(g.id),
                text=g.name,
                values=(checked, g.level, f"{g.stamina}/{g.stamina_max}", g.morale, inf, cav, arc, total),
            )
            count += 1
        self._pending_gd_generals = None
        self._update_gd_gen_count_label()

    def _append_gd_log(self, msg: str):
        self._append_text_buffer(self.gd_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _gd_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Gọi Man."""
        if hasattr(self, "gd_log_text") and self.gd_log_text:
            self.gd_log_text.delete("1.0", "end")

    def _get_gd_target_type(self) -> int:
        if hasattr(self, "gd_target_dropdown"):
            sel = self.gd_target_dropdown.get_selected()
            if sel:
                return sel[0]
        sel_idx = self.gd_mode_combo.current() if hasattr(self, "gd_mode_combo") else 0
        if 0 <= sel_idx < len(getattr(self, "gd_target_options", [])):
            return self.gd_target_options[sel_idx][0]
        return 301

    def _create_goidan_task(self) -> Optional[GoiDan]:
        sel_idx = self.gd_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else []
        if sel_idx < 0 or sel_idx >= len(cities):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
            return None
        city = cities[sel_idx]

        sel_gens = []
        if hasattr(self, "gd_gen_tree"):
            sel_gens = [int(iid) for iid in self.gd_gen_tree.get_children() if self.gd_gen_tree.item(iid, "values")[0] == "☑"]

        if not sel_gens:
            vos = [g.id for g in self.roster.generals_of(city.id) if g.role == "vo"]
            if not vos:
                messagebox.showwarning("Cảnh báo", "Thành này không có võ tướng khả dụng!")
                return None
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng xuất kích!")
            return None

        target_types = self.gd_target_dropdown.get_selected() if hasattr(self, "gd_target_dropdown") else []
        if not target_types:
            target_types = [self._get_gd_target_type()]
        target_type = target_types[0]
        mode = "vong_linh" if target_type == 301 else "dan"
        radius = int(self.gd_radius_var.get() or "5")
        locks = TargetLocks()
        scanner = Scanner(self.gateway, locks, delay=0.0, sleep=lambda s: None)
        ctx = TaskContext(self.gateway, scanner, locks, notify=lambda m: self.after(0, self._append_gd_log, m))

        try:
            target_inf = int(self.gd_target_inf_var.get() or "0")
        except ValueError:
            target_inf = 0
        try:
            target_cav = int(self.gd_target_cav_var.get() or "0")
        except ValueError:
            target_cav = 0
        try:
            target_arc = int(self.gd_target_arc_var.get() or "0")
        except ValueError:
            target_arc = 0
        try:
            min_morale = int(self.gd_min_morale_var.get() or "95")
        except ValueError:
            min_morale = 95

        target_army = TargetArmy(infantry=target_inf, cavalry=target_cav, archers=target_arc)
        auto_recruit = bool(self.gd_auto_recruit_var.get()) if hasattr(self, "gd_auto_recruit_var") else True
        auto_morale = bool(self.gd_auto_morale_var.get()) if hasattr(self, "gd_auto_morale_var") else True

        return GoiDan(
            ctx=ctx,
            generals=sel_gens,
            origin=(city.pos_x, city.pos_y) if hasattr(city, "pos_x") else (0, 0),
            radius=radius,
            mode=mode,
            target_type=target_type,
            target_types=target_types,
            city_id=city.id,
            auto_recover=self.gd_recover_var.get(),
            refill_amount=500,
            sleep_fn=time.sleep,
            combat_config=self._build_combat_config(),
            on_battle_found=lambda bid: self.after(
                0, lambda b=bid: self.bt_id_var.set(str(b)) if hasattr(self, "bt_id_var") else None
            ),
            on_battle_state=lambda st: self.after(
                0, lambda s=st: self._bt_render_state(s) if hasattr(self, "_bt_render_state") else None
            ),
            target_army=target_army,
            auto_recruit=auto_recruit,
            auto_morale=auto_morale,
            min_morale=min_morale,
        )

    def _manual_adjust_gd_troops(self):
        sel_idx = self.gd_city_combo.current()
        cities = self.roster.cities if (self.roster and self.roster.cities) else []
        if sel_idx < 0 or sel_idx >= len(cities):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì!")
            return
        city_id = cities[sel_idx].id
        sel_gens = [int(iid) for iid in self.gd_gen_tree.get_children() if self.gd_gen_tree.item(iid, "values")[0] == "☑"]
        if not sel_gens:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng!")
            return

        try:
            target_inf = int(self.gd_target_inf_var.get() or "0")
        except ValueError:
            target_inf = 0
        try:
            target_cav = int(self.gd_target_cav_var.get() or "0")
        except ValueError:
            target_cav = 0
        try:
            target_arc = int(self.gd_target_arc_var.get() or "0")
        except ValueError:
            target_arc = 0
        try:
            min_morale = int(self.gd_min_morale_var.get() or "95")
        except ValueError:
            min_morale = 95

        target_army = TargetArmy(infantry=target_inf, cavalry=target_cav, archers=target_arc)
        auto_recruit = bool(self.gd_auto_recruit_var.get()) if hasattr(self, "gd_auto_recruit_var") else True
        auto_morale = bool(self.gd_auto_morale_var.get()) if hasattr(self, "gd_auto_morale_var") else True

        def _worker():
            try:
                self.after(0, self._append_gd_log, "⚔️ Bắt đầu tiến trình biên chế Gọi Man & Luyện sĩ khí...")
                prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)

                # 1. Trị thương
                for gid in sel_gens:
                    prov.heal_general(city_id, gid)

                # 2. Bổ sung lính
                if target_army.total > 0 and auto_recruit:
                    total_needed = 0
                    fresh_roster = fetch_roster(self.gateway, only_base_ids=[city_id])
                    for gid in sel_gens:
                        army = fresh_roster.army_of(gid)
                        cur_inf = army.infantry if army else 0
                        cur_cav = army.cavalry if army else 0
                        cur_arc = army.archers if army else 0
                        total_needed += max(0, target_army.infantry - cur_inf)
                        total_needed += max(0, target_army.cavalry - cur_cav)
                        total_needed += max(0, target_army.archers - cur_arc)

                    if total_needed > 0:
                        avail = prov.check_recruits(city_id)
                        if avail is not None and avail < total_needed:
                            missing = total_needed - avail
                            self.after(0, self._append_gd_log, f"📦 [Tân binh] Kho có {avail}/{total_needed}, tự động chiêu mộ thêm {missing} tân binh...")
                            b_succ, b_ret = prov.buy_recruits(city_id, missing)
                            if b_succ:
                                self.after(0, self._append_gd_log, f"   [Chiêu mộ] ✅ Đã chiêu mộ thành công {missing} tân binh!")
                            else:
                                err_desc = ERROR_MESSAGES.get(b_ret, f"Mã lỗi: {b_ret}")
                                self.after(0, self._append_gd_log, f"   [Chiêu mộ] ⚠️ Chiêu mộ thất bại ({err_desc})")

                    fresh_roster = fetch_roster(self.gateway, only_base_ids=[city_id])
                    city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
                    for gid in sel_gens:
                        g = city_gens.get(gid)
                        gname = g.name if g else str(gid)
                        cur_army = fresh_roster.army_of(gid)
                        results = prov.adjust_troops(
                            base_id=city_id,
                            general_id=gid,
                            current_army=cur_army,
                            target_army=target_army,
                            auto_recruit=True,
                            on_log=lambda m: self.after(0, self._append_gd_log, m),
                        )
                        if results:
                            for stype, diff, succ, ret_code in results:
                                tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(stype, "Quân")
                                if succ:
                                    self.after(0, self._append_gd_log, f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ✅ Thành công")
                                else:
                                    err_desc = ERROR_MESSAGES.get(ret_code, f"Mã lỗi: {ret_code}")
                                    self.after(0, self._append_gd_log, f"   [Biên chế] Tướng {gname}: Bổ sung {tname} +{diff} ❌ Thất bại ({err_desc})")
                        else:
                            self.after(0, self._append_gd_log, f"   [Biên chế] Tướng {gname}: Quân số đã đủ, không cần bổ sung.")

                # 3. Luyện sĩ khí đồng loạt bằng MoraleTrainer (ADR-0032)
                if auto_morale:
                    fresh_roster = fetch_roster(self.gateway, only_base_ids=[city_id])
                    city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
                    trainer = MoraleTrainer(self.gateway)
                    def _on_notify_gd(msg):
                        self.after(0, self._append_gd_log, f"   {msg}")
                    trainer.adjust_squad_morale(
                        base_id=city_id,
                        general_ids=sel_gens,
                        target_morale=min_morale,
                        base_gens=city_gens,
                        on_notify=_on_notify_gd,
                    )

                self.after(0, self._append_gd_log, "🏁 Hoàn tất tiến trình biên chế Gọi Man!")
                new_roster = fetch_roster(self.gateway)
                self.roster = new_roster
                self.after(0, self._on_gd_city_selected)
            except Exception as e:
                self.after(0, self._append_gd_log, f"❌ Lỗi ngoại lệ khi biên chế: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _run_goidan_once(self):
        task = self._create_goidan_task()
        if not task:
            return
        threading.Thread(target=lambda: self.after(0, self._append_gd_log, f"⚡ Kết quả chạy 1 lượt: {task.run_once()}"), daemon=True).start()

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
            self.gd_start_btn.configure(text="⏹️ Dừng Gọi Man", style="Danger.TButton")
        else:
            self._gd_runner.stop()
            self.gd_start_btn.configure(text="▶️ Bắt đầu Gọi Man", style="Success.TButton")

    # =========================================================================
    # TAB 4: BÌNH MAN & DI TRẠI
    # =========================================================================
    def _build_binhman_tab(self, parent):
        container = tk.Frame(parent, bg=BG)
        container.pack(fill="both", expand=True, padx=4, pady=4)
        container.columnconfigure(0, weight=0, minsize=290)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        col_left = tk.Frame(container, bg=BG)
        col_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        col_right = tk.Frame(container, bg=BG)
        col_right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # ---------------------------------------------------------------------
        # CỘT TRÁI: Danh sách căn cứ & Điều khiển chạy
        # ---------------------------------------------------------------------
        f_bases = ttk.LabelFrame(col_left, text="🏰 Danh Sách Căn Cứ Bình Man", style="Card.TLabelframe")
        f_bases.pack(fill="both", expand=True, padx=2, pady=(0, 4))

        bar1 = tk.Frame(f_bases, bg=BG)
        bar1.pack(fill="x", padx=4, pady=2)
        ttk.Button(bar1, text="✅ Chọn tất cả", style="Secondary.TButton", command=lambda: self._select_all_bm_bases(True)).pack(side="left", padx=2)
        ttk.Button(bar1, text="❌ Bỏ tất cả", style="Secondary.TButton", command=lambda: self._select_all_bm_bases(False)).pack(side="left", padx=2)

        bar2 = tk.Frame(f_bases, bg=BG)
        bar2.pack(fill="x", padx=4, pady=2)
        ttk.Button(bar2, text="⚔️ Biên chế TẤT CẢ căn cứ", style="Action.TButton", command=self._manual_adjust_all_bm_troops).pack(side="left", fill="x", expand=True, padx=2)

        tree_frame = tk.Frame(f_bases, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.bm_bases_tree = ttk.Treeview(
            tree_frame,
            columns=("select", "type", "coords", "gens"),
            show="tree headings",
            selectmode="browse",
        )
        self.bm_bases_tree.heading("#0", text="Căn cứ")
        self.bm_bases_tree.heading("select", text="Chạy")
        self.bm_bases_tree.heading("type", text="Loại")
        self.bm_bases_tree.heading("coords", text="Tọa độ")
        self.bm_bases_tree.heading("gens", text="Tướng")

        self.bm_bases_tree.column("#0", width=95)
        self.bm_bases_tree.column("select", width=42, anchor="center")
        self.bm_bases_tree.column("type", width=65, anchor="center")
        self.bm_bases_tree.column("coords", width=65, anchor="center")
        self.bm_bases_tree.column("gens", width=50, anchor="center")

        bm_bases_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.bm_bases_tree.yview)
        self.bm_bases_tree.configure(yscrollcommand=bm_bases_scroll.set)
        self.bm_bases_tree.pack(side="left", fill="both", expand=True)
        bm_bases_scroll.pack(side="right", fill="y")

        self.bm_bases_tree.bind("<ButtonRelease-1>", self._on_bm_bases_tree_click)
        self.bm_bases_tree.bind("<<TreeviewSelect>>", self._on_bm_bases_tree_select)

        # Khung điều khiển tiến trình
        f_ctrl = ttk.LabelFrame(col_left, text="Điều khiển tiến trình", style="Card.TLabelframe")
        f_ctrl.pack(fill="x", padx=2, pady=(0, 2))

        r_cycle = tk.Frame(f_ctrl, bg=BG)
        r_cycle.pack(fill="x", padx=4, pady=2)
        tk.Label(r_cycle, text="Chu kỳ quét (s):", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bm_interval_var = tk.StringVar(value="15")
        ttk.Entry(r_cycle, textvariable=self.bm_interval_var, width=6).pack(side="left")

        r_btns = tk.Frame(f_ctrl, bg=BG)
        r_btns.pack(fill="x", padx=4, pady=4)
        self.bm_start_btn = ttk.Button(r_btns, text="▶️ Bắt đầu Bình Man", style="Success.TButton", command=self._toggle_binhman)
        self.bm_start_btn.pack(side="left", fill="x", expand=True, padx=2)
        self.bm_once_btn = ttk.Button(r_btns, text="⚡ Chạy 1 Lượt", style="Action.TButton", command=self._run_binhman_once)
        self.bm_once_btn.pack(side="left", padx=2)

        # ---------------------------------------------------------------------
        # CỘT PHẢI: Cấu hình căn cứ hiện tại, Danh sách tướng & Log
        # ---------------------------------------------------------------------
        col_right.rowconfigure(0, weight=0)
        col_right.rowconfigure(1, weight=1)
        col_right.rowconfigure(2, weight=1)
        col_right.columnconfigure(0, weight=1)

        # 1. Cấu hình chi tiết căn cứ
        self.bm_detail_frame = ttk.LabelFrame(col_right, text="⚙️ Cấu hình căn cứ hiện tại", style="Card.TLabelframe")
        self.bm_detail_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        f_bm = self.bm_detail_frame

        # Chế độ tác chiến (Mode 1: Di Doanh trại, Mode 2: Xuất quân thẳng từ Thành)
        tk.Label(f_bm, text="Chế độ tác chiến:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.bm_mode_var = tk.IntVar(value=1)
        mode_f = tk.Frame(f_bm, bg=BG)
        mode_f.grid(row=0, column=1, columnspan=3, sticky="w", padx=4, pady=4)
        self.bm_mode_camp_rb = tk.Radiobutton(
            mode_f, text="1: Di Doanh trại đến cạnh Man", variable=self.bm_mode_var, value=1,
            command=self._on_bm_mode_changed, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, activeforeground=FG
        )
        self.bm_mode_camp_rb.pack(side="left", padx=(0, 10))
        self.bm_mode_city_rb = tk.Radiobutton(
            mode_f, text="2: Xuất quân thẳng từ Thành", variable=self.bm_mode_var, value=2,
            command=self._on_bm_mode_changed, bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, activeforeground=FG
        )
        self.bm_mode_city_rb.pack(side="left")

        self.bm_base_lbl = tk.Label(f_bm, text="Doanh trại xuất phát:", bg=BG, fg=FG, font=("Segoe UI", 10, "bold"))
        self.bm_base_lbl.grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.bm_city_combo = ttk.Combobox(f_bm, state="readonly", width=22)
        self.bm_city_combo.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.bm_city_combo.bind("<<ComboboxSelected>>", self._on_bm_city_selected)

        self.bm_parent_city_lbl = tk.Label(f_bm, text="Thành mẹ (Hồi quân):", bg=BG, fg=FG, font=("Segoe UI", 10))
        self.bm_parent_city_lbl.grid(row=1, column=2, sticky="w", padx=4, pady=4)
        self.bm_parent_city_combo = ttk.Combobox(f_bm, state="readonly", width=18)
        self.bm_parent_city_combo.grid(row=1, column=3, sticky="w", padx=4, pady=4)

        self.bm_camp_id_lbl = tk.Label(f_bm, text="Doanh trại ID:", bg=BG, fg=FG)
        self.bm_camp_id_lbl.grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.bm_camp_id_var = tk.StringVar(value="")
        self.bm_camp_id_entry = ttk.Entry(f_bm, textvariable=self.bm_camp_id_var, width=12)
        self.bm_camp_id_entry.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Ngưỡng An Toàn (%):", bg=BG, fg=FG).grid(row=2, column=2, sticky="w", padx=4, pady=4)
        self.bm_threshold_var = tk.StringVar(value="30")
        ttk.Entry(f_bm, textvariable=self.bm_threshold_var, width=8).grid(row=2, column=3, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Bán kính quét:", bg=BG, fg=FG).grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.bm_radius_var = tk.StringVar(value="10")
        ttk.Entry(f_bm, textvariable=self.bm_radius_var, width=8).grid(row=3, column=1, sticky="w", padx=4, pady=4)

        tk.Label(f_bm, text="Loại Man mục tiêu:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=3, column=2, sticky="w", padx=4, pady=4)
        self.bm_mantypes_var = tk.StringVar(value="7,8,9,10")
        self.bm_mantypes_dropdown = MultiSelectDropdown(
            f_bm,
            options=MAN_TARGET_OPTIONS,
            default_selected=[7, 8, 9, 10],
            width=22,
            command=lambda sel: self.bm_mantypes_var.set(",".join(str(x) for x in sel)),
        )
        self.bm_mantypes_dropdown.grid(row=3, column=3, sticky="w", padx=4, pady=4)

        # Row 4: Định mức quân đội (Bộ MT, Kỵ MT, Cung MT) & Nút Biên chế căn cứ này
        tk.Label(f_bm, text="Bộ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w", padx=4, pady=4)
        self.bm_target_inf_var = tk.StringVar(value="0")
        ttk.Entry(f_bm, textvariable=self.bm_target_inf_var, width=8).grid(row=4, column=1, sticky="w", padx=4, pady=4)

        bm_army_f = tk.Frame(f_bm, bg=BG)
        bm_army_f.grid(row=4, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        tk.Label(bm_army_f, text="Kỵ MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.bm_target_cav_var = tk.StringVar(value="0")
        ttk.Entry(bm_army_f, textvariable=self.bm_target_cav_var, width=6).pack(side="left", padx=(0, 6))

        tk.Label(bm_army_f, text="Cung MT:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 2))
        self.bm_target_arc_var = tk.StringVar(value="0")
        ttk.Entry(bm_army_f, textvariable=self.bm_target_arc_var, width=6).pack(side="left", padx=(0, 8))

        self.bm_adjust_troops_btn = ttk.Button(bm_army_f, text="⚔️ Biên chế ngay", style="Action.TButton", command=self._manual_adjust_bm_troops)
        self.bm_adjust_troops_btn.pack(side="left", padx=(0, 4))

        # Row 5: Tự động bổ sung lính, Tự động nâng sĩ khí, Sĩ khí tối thiểu
        self.bm_auto_recruit_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            f_bm,
            text="Tự động bổ sung lính",
            variable=self.bm_auto_recruit_var,
            style="TCheckbutton",
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        bm_mor_f = tk.Frame(f_bm, bg=BG)
        bm_mor_f.grid(row=5, column=2, columnspan=2, sticky="w", padx=4, pady=4)
        self.bm_auto_morale_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bm_mor_f, text="Tự động nâng sĩ khí", variable=self.bm_auto_morale_var, style="TCheckbutton").pack(side="left", padx=(0, 8))
        tk.Label(bm_mor_f, text="Sĩ khí tối thiểu:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.bm_min_morale_var = tk.StringVar(value="95")
        ttk.Entry(bm_mor_f, textvariable=self.bm_min_morale_var, width=5).pack(side="left")

        # 2. Bảng danh sách võ tướng
        f_gens = ttk.LabelFrame(col_right, text="Võ tướng xuất kích", style="Card.TLabelframe")
        f_gens.grid(row=1, column=0, sticky="nsew", pady=(0, 4))

        btn_bar = tk.Frame(f_gens, bg=BG)
        btn_bar.pack(fill="x", padx=4, pady=2)
        ttk.Button(btn_bar, text="✅ Chọn tất cả", style="Secondary.TButton", command=self._select_all_bm_gens).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="❌ Bỏ chọn tất cả", style="Secondary.TButton", command=self._deselect_all_bm_gens).pack(side="left", padx=2)
        self.bm_gen_count_lbl = tk.Label(btn_bar, text="Đã chọn: 0 tướng (0 đợt xuất kích)", bg=BG, fg=FG, font=("Segoe UI", 9, "bold"))
        self.bm_gen_count_lbl.pack(side="left", padx=8)

        self.bm_gen_tree = ttk.Treeview(
            f_gens,
            columns=("select", "lv", "stamina", "morale", "infantry", "cavalry", "archers", "total_army"),
            show="tree headings",
            selectmode="browse",
            height=5,
        )
        self.bm_gen_tree.heading("#0", text="Tên võ tướng")
        self.bm_gen_tree.heading("select", text="Chọn")
        self.bm_gen_tree.heading("lv", text="Cấp")
        self.bm_gen_tree.heading("stamina", text="Thể lực")
        self.bm_gen_tree.heading("morale", text="Sĩ khí")
        self.bm_gen_tree.heading("infantry", text="Bộ binh")
        self.bm_gen_tree.heading("cavalry", text="Kỵ binh")
        self.bm_gen_tree.heading("archers", text="Cung binh")
        self.bm_gen_tree.heading("total_army", text="Tổng quân")

        self.bm_gen_tree.column("#0", width=140)
        self.bm_gen_tree.column("select", width=50, anchor="center")
        self.bm_gen_tree.column("lv", width=50, anchor="center")
        self.bm_gen_tree.column("stamina", width=75, anchor="center")
        self.bm_gen_tree.column("morale", width=65, anchor="center")
        self.bm_gen_tree.column("infantry", width=80, anchor="e")
        self.bm_gen_tree.column("cavalry", width=80, anchor="e")
        self.bm_gen_tree.column("archers", width=80, anchor="e")
        self.bm_gen_tree.column("total_army", width=85, anchor="e")

        gen_scroll = ttk.Scrollbar(f_gens, orient="vertical", command=self.bm_gen_tree.yview)
        self.bm_gen_tree.configure(yscrollcommand=gen_scroll.set)
        self.bm_gen_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        gen_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))
        self.bm_gen_tree.bind("<ButtonRelease-1>", self._on_bm_gen_toggle)

        # 3. Khung nhật ký Bình Man
        f_log = ttk.LabelFrame(col_right, text="Nhật ký Bình Man", style="Card.TLabelframe")
        f_log.grid(row=2, column=0, sticky="nsew", pady=(0, 0))

        log_bar = tk.Frame(f_log, bg=CARD)
        log_bar.pack(side="top", fill="x", padx=4, pady=(2, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._bm_clear_log).pack(side="right")

        log_scroll = ttk.Scrollbar(f_log, orient="vertical")
        self.bm_log_text = tk.Text(f_log, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0, yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.bm_log_text.yview)
        self.bm_log_text.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        log_scroll.pack(side="right", fill="y", padx=(0, 4), pady=(0, 4))

    def _update_bm_gen_count_label(self):
        if not hasattr(self, "bm_gen_count_lbl") or not hasattr(self, "bm_gen_tree"):
            return
        selected_count = sum(1 for item in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(item, "values")[0] == "☑")
        batches = (selected_count + 2) // 3 if selected_count > 0 else 0
        self.bm_gen_count_lbl.config(text=f"Đã chọn: {selected_count} tướng ({batches} đợt xuất kích)")

    def _update_bm_bases_tree_gen_count(self):
        if not hasattr(self, "bm_bases_tree") or not hasattr(self, "bm_gen_tree") or self._current_bm_base_id is None:
            return
        iid = str(self._current_bm_base_id)
        if not self.bm_bases_tree.exists(iid):
            return
        vals = list(self.bm_bases_tree.item(iid, "values"))
        sel_count = sum(1 for item in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(item, "values")[0] == "☑")
        total_count = len(self.bm_gen_tree.get_children())
        if len(vals) > 3:
            vals[3] = f"{sel_count}/{total_count}"
            self.bm_bases_tree.item(iid, values=vals)

    def _select_all_bm_gens(self):
        for item in self.bm_gen_tree.get_children():
            vals = list(self.bm_gen_tree.item(item, "values"))
            vals[0] = "☑"
            self.bm_gen_tree.item(item, values=vals)
        self._update_bm_gen_count_label()
        self._update_bm_bases_tree_gen_count()

    def _deselect_all_bm_gens(self):
        for item in self.bm_gen_tree.get_children():
            vals = list(self.bm_gen_tree.item(item, "values"))
            vals[0] = "☐"
            self.bm_gen_tree.item(item, values=vals)
        self._update_bm_gen_count_label()
        self._update_bm_bases_tree_gen_count()

    def _on_bm_gen_toggle(self, event):
        item = self.bm_gen_tree.identify_row(event.y)
        if not item:
            return
        vals = list(self.bm_gen_tree.item(item, "values"))
        vals[0] = "☑" if vals[0] == "☐" else "☐"
        self.bm_gen_tree.item(item, values=vals)
        self._update_bm_gen_count_label()
        self._update_bm_bases_tree_gen_count()

    def _append_bm_log(self, msg: str):
        self._append_text_buffer(self.bm_log_text, f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    def _bm_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Bình Man."""
        if hasattr(self, "bm_log_text") and self.bm_log_text:
            self.bm_log_text.delete("1.0", "end")

    def _update_bm_mode_ui_states(self, mode: int):
        if hasattr(self, "bm_city_combo") and hasattr(self, "roster") and self.roster:
            if mode == 2:
                items = [c.display_name for c in self.roster.cities]
            else:
                items = [c.display_name for c in self.roster.camps] if self.roster.camps else [b.display_name for b in self.roster.bases]
            self.bm_city_combo["values"] = items

        if mode == 2:  # Chế độ 2: Xuất quân thẳng từ Thành
            if hasattr(self, "bm_base_lbl"):
                self.bm_base_lbl.configure(text="Thành xuất phát:")
            if hasattr(self, "bm_parent_city_lbl"):
                self.bm_parent_city_lbl.configure(state="disabled")
            if hasattr(self, "bm_parent_city_combo"):
                self.bm_parent_city_combo.configure(state="disabled")
            if hasattr(self, "bm_camp_id_lbl"):
                self.bm_camp_id_lbl.configure(state="disabled")
            if hasattr(self, "bm_camp_id_entry"):
                self.bm_camp_id_entry.configure(state="disabled")
        else:  # Chế độ 1: Di Doanh trại
            if hasattr(self, "bm_base_lbl"):
                self.bm_base_lbl.configure(text="Doanh trại xuất phát:")
            if hasattr(self, "bm_parent_city_lbl"):
                self.bm_parent_city_lbl.configure(state="normal")
            if hasattr(self, "bm_parent_city_combo"):
                self.bm_parent_city_combo.configure(state="readonly")
            if hasattr(self, "bm_camp_id_lbl"):
                self.bm_camp_id_lbl.configure(state="normal")
            if hasattr(self, "bm_camp_id_entry"):
                self.bm_camp_id_entry.configure(state="normal")

    def _on_bm_mode_changed(self):
        mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
        self._update_bm_mode_ui_states(mode)
        if hasattr(self, "bm_city_combo"):
            combo_len = len(self.bm_city_combo["values"])
            if combo_len > 0 and (self.bm_city_combo.current() < 0 or self.bm_city_combo.current() >= combo_len):
                self.bm_city_combo.current(0)
        self._on_bm_city_selected()

    def _on_bm_city_selected(self, _event=None):
        mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
        sel_idx = self.bm_city_combo.current() if hasattr(self, "bm_city_combo") else -1
        if mode == 2:
            bases = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        else:
            bases = self.roster.camps if (self.roster and self.roster.camps) else (self.roster.bases if self.roster else [])

        if 0 <= sel_idx < len(bases):
            base = bases[sel_idx]
            if hasattr(self, "bm_bases_tree") and self.bm_bases_tree.exists(str(base.id)):
                self.bm_bases_tree.selection_set(str(base.id))
            self._switch_bm_base(base.id)

    def _get_or_create_bm_base_config(self, base) -> BaseBinhManConfig:
        cfg = self.bm_base_configs.get(base.id)
        if cfg is None:
            if getattr(self, "_pending_bm_legacy_config", None):
                cfg = self._pending_bm_legacy_config
                self._pending_bm_legacy_config = None
                self.bm_base_configs[base.id] = cfg
                return cfg

            def_mode = 1 if base.is_camp else 2
            def_camp_id = str(base.id) if base.is_camp else ""
            vos = [g.id for g in self.roster.generals_of(base.id) if g.role == "vo"] if self.roster else []
            t_rad = self.bm_radius_var.get() if hasattr(self, "bm_radius_var") else "10"
            t_thresh = self.bm_threshold_var.get() if hasattr(self, "bm_threshold_var") else "30"
            t_min_mor = self.bm_min_morale_var.get() if hasattr(self, "bm_min_morale_var") else "95"
            t_auto_rec = bool(self.bm_auto_recruit_var.get()) if hasattr(self, "bm_auto_recruit_var") else True
            t_auto_mor = bool(self.bm_auto_morale_var.get()) if hasattr(self, "bm_auto_morale_var") else True

            # ADR-0029 Section 5: Bộ quy tắc an toàn mặc định cho căn cứ mới
            # - enabled = False (chưa chọn chạy)
            # - generals = tất cả võ tướng có trong căn cứ
            # - Định mức lính: 0 / 0 / 0
            cfg = BaseBinhManConfig(
                enabled=False,
                mode=def_mode,
                radius=str(t_rad),
                threshold=str(t_thresh),
                camp_id=def_camp_id,
                generals=vos,
                target_infantry="0",
                target_cavalry="0",
                target_archers="0",
                auto_recruit=t_auto_rec,
                auto_morale=t_auto_mor,
                min_morale=str(t_min_mor),
            )
            self.bm_base_configs[base.id] = cfg
        return cfg

    def _refresh_bm_bases_tree(self):
        if not hasattr(self, "bm_bases_tree") or not self.roster:
            return
        if getattr(self, "_pending_bm_legacy_config", None) and self.roster.bases:
            if not any(b.id in self.bm_base_configs for b in self.roster.bases):
                if self._pending_bm_legacy_config.mode == 2 and self.roster.cities:
                    target_bid = self.roster.cities[0].id
                elif self._pending_bm_legacy_config.mode == 1 and self.roster.camps:
                    target_bid = self.roster.camps[0].id
                else:
                    target_bid = self.roster.bases[0].id
                self.bm_base_configs[target_bid] = self._pending_bm_legacy_config
                if not self._pending_bm_legacy_config.generals:
                    self._pending_bm_legacy_config.generals = [g.id for g in self.roster.generals_of(target_bid) if g.role == "vo"]
            self._pending_bm_legacy_config = None

        self.bm_bases_tree.delete(*self.bm_bases_tree.get_children())
        for base in self.roster.bases:
            cfg = self._get_or_create_bm_base_config(base)

            is_sel = "☑" if cfg.enabled else "☐"
            b_type = "⛺ Trại" if base.is_camp else "🏰 Thành"
            coords = f"({base.pos_x},{base.pos_y})" if (base.pos_x or base.pos_y) else "-"
            total_vos = len([g for g in self.roster.generals_of(base.id) if g.role == "vo"])
            gens_text = f"{len(cfg.generals)}/{total_vos}"
            self.bm_bases_tree.insert(
                "",
                "end",
                iid=str(base.id),
                text=base.name,
                values=(is_sel, b_type, coords, gens_text),
            )

        if self.roster.bases:
            target_id = self._current_bm_base_id if (self._current_bm_base_id and any(b.id == self._current_bm_base_id for b in self.roster.bases)) else None
            if target_id is None:
                for b in self.roster.bases:
                    cfg = self.bm_base_configs.get(b.id)
                    if cfg and cfg.enabled:
                        target_id = b.id
                        break
            if target_id is None:
                cur_mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
                if cur_mode == 1 and self.roster.camps:
                    target_id = self.roster.camps[0].id
                else:
                    target_id = self.roster.bases[0].id

            self._current_bm_base_id = target_id
            iid = str(target_id)
            if self.bm_bases_tree.exists(iid):
                self.bm_bases_tree.selection_set(iid)
                self._load_bm_base_config(target_id)

    def _on_bm_bases_tree_click(self, event):
        item = self.bm_bases_tree.identify_row(event.y)
        col = self.bm_bases_tree.identify_column(event.x)
        if not item or not self.bm_bases_tree.exists(item):
            return
        try:
            base_id = int(item)
        except ValueError:
            return
        if col == "#1":  # Column 'select'
            vals = list(self.bm_bases_tree.item(item, "values"))
            cfg = self.bm_base_configs.setdefault(base_id, BaseBinhManConfig())
            if vals[0] == "☑":
                vals[0] = "☐"
                cfg.enabled = False
            else:
                vals[0] = "☑"
                cfg.enabled = True
            self.bm_bases_tree.item(item, values=vals)

    def _on_bm_bases_tree_select(self, _event=None):
        sel = self.bm_bases_tree.selection()
        if not sel:
            return
        try:
            base_id = int(sel[0])
            self._switch_bm_base(base_id)
        except ValueError:
            pass

    def _switch_bm_base(self, base_id: int):
        if self._current_bm_base_id is not None and self._current_bm_base_id != base_id:
            self._save_bm_current_base_config()
        self._load_bm_base_config(base_id)

    def _select_all_bm_bases(self, enabled: bool):
        if not hasattr(self, "bm_bases_tree"):
            return
        for iid in self.bm_bases_tree.get_children(""):
            vals = list(self.bm_bases_tree.item(iid, "values"))
            vals[0] = "☑" if enabled else "☐"
            self.bm_bases_tree.item(iid, values=vals)
            try:
                bid = int(iid)
                if bid in self.bm_base_configs:
                    self.bm_base_configs[bid].enabled = enabled
            except ValueError:
                pass

    def _save_bm_current_base_config(self):
        if self._current_bm_base_id is None:
            return
        base_id = self._current_bm_base_id
        cfg = self.bm_base_configs.get(base_id)
        if cfg is None:
            cfg = BaseBinhManConfig()
            self.bm_base_configs[base_id] = cfg

        if hasattr(self, "bm_mode_var"):
            cfg.mode = self.bm_mode_var.get()
        if hasattr(self, "bm_radius_var"):
            cfg.radius = str(self.bm_radius_var.get() or "10")
        if hasattr(self, "bm_threshold_var"):
            cfg.threshold = str(self.bm_threshold_var.get() or "30")
        if hasattr(self, "bm_camp_id_var") and cfg.mode == 1:
            cfg.camp_id = self.bm_camp_id_var.get().strip()
        if hasattr(self, "bm_parent_city_combo") and self.roster and self.roster.cities:
            pidx = self.bm_parent_city_combo.current()
            if 0 <= pidx < len(self.roster.cities):
                cfg.parent_city_id = str(self.roster.cities[pidx].id)
        if hasattr(self, "bm_mantypes_dropdown"):
            cfg.target_types = self.bm_mantypes_dropdown.get_selected()
            cfg.mantypes = self.bm_mantypes_dropdown.get_selected_str()
        elif hasattr(self, "bm_mantypes_var"):
            cfg.mantypes = self.bm_mantypes_var.get()
            cfg.target_types = [int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()]
        if hasattr(self, "bm_gen_tree"):
            cfg.generals = [int(iid) for iid in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(iid, "values")[0] == "☑"]
        if hasattr(self, "bm_target_inf_var"):
            cfg.target_infantry = str(self.bm_target_inf_var.get() or "0")
        if hasattr(self, "bm_target_cav_var"):
            cfg.target_cavalry = str(self.bm_target_cav_var.get() or "0")
        if hasattr(self, "bm_target_arc_var"):
            cfg.target_archers = str(self.bm_target_arc_var.get() or "0")
        if hasattr(self, "bm_auto_recruit_var"):
            cfg.auto_recruit = bool(self.bm_auto_recruit_var.get())
        if hasattr(self, "bm_auto_morale_var"):
            cfg.auto_morale = bool(self.bm_auto_morale_var.get())
        if hasattr(self, "bm_min_morale_var"):
            cfg.min_morale = str(self.bm_min_morale_var.get() or "95")
        self._update_bm_bases_tree_gen_count()

    def _load_bm_base_config(self, base_id: int):
        self._current_bm_base_id = base_id
        if not self.roster:
            return
        base = next((b for b in self.roster.bases if b.id == base_id), None)
        if not base:
            return

        cfg = self._get_or_create_bm_base_config(base)

        if hasattr(self, "bm_detail_frame"):
            self.bm_detail_frame.configure(text=f"⚙️ Cấu hình căn cứ: {base.name} ({base.pos_x}, {base.pos_y})")

        if hasattr(self, "bm_mode_var"):
            self.bm_mode_var.set(cfg.mode)
        if hasattr(self, "bm_radius_var"):
            self.bm_radius_var.set(str(cfg.radius))
        if hasattr(self, "bm_threshold_var"):
            self.bm_threshold_var.set(str(cfg.threshold))
        if hasattr(self, "bm_camp_id_var"):
            self.bm_camp_id_var.set(str(cfg.camp_id) if cfg.camp_id is not None else "")
        if hasattr(self, "bm_parent_city_combo") and self.roster.cities:
            if cfg.parent_city_id:
                for idx, c in enumerate(self.roster.cities):
                    if str(c.id) == str(cfg.parent_city_id):
                        self.bm_parent_city_combo.current(idx)
                        break
            elif not self.bm_parent_city_combo.get() and len(self.roster.cities) > 0:
                self.bm_parent_city_combo.current(0)
        if hasattr(self, "bm_mantypes_dropdown"):
            t_types = cfg.target_types if cfg.target_types else ([int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()] if isinstance(cfg.mantypes, str) else [7, 8, 9, 10])
            self.bm_mantypes_dropdown.set_selected(t_types)
        if hasattr(self, "bm_mantypes_var"):
            self.bm_mantypes_var.set(cfg.mantypes if isinstance(cfg.mantypes, str) else ",".join(str(x) for x in cfg.mantypes))
        if hasattr(self, "bm_target_inf_var"):
            self.bm_target_inf_var.set(str(cfg.target_infantry))
        if hasattr(self, "bm_target_cav_var"):
            self.bm_target_cav_var.set(str(cfg.target_cavalry))
        if hasattr(self, "bm_target_arc_var"):
            self.bm_target_arc_var.set(str(cfg.target_archers))
        if hasattr(self, "bm_auto_recruit_var"):
            self.bm_auto_recruit_var.set(cfg.auto_recruit)
        if hasattr(self, "bm_auto_morale_var"):
            self.bm_auto_morale_var.set(cfg.auto_morale)
        if hasattr(self, "bm_min_morale_var"):
            self.bm_min_morale_var.set(str(cfg.min_morale))

        self._update_bm_mode_ui_states(cfg.mode)

        if hasattr(self, "bm_city_combo"):
            combo_values = list(self.bm_city_combo["values"])
            for idx, val in enumerate(combo_values):
                if base.name in val:
                    self.bm_city_combo.current(idx)
                    break

        if hasattr(self, "bm_bases_tree") and self.bm_bases_tree.exists(str(base_id)):
            cur_sel = self.bm_bases_tree.selection()
            if not cur_sel or cur_sel[0] != str(base_id):
                self.bm_bases_tree.selection_set(str(base_id))

        if hasattr(self, "bm_gen_tree"):
            self.bm_gen_tree.delete(*self.bm_gen_tree.get_children())
            sel_gens_set = set(cfg.generals) if cfg.generals is not None else set()
            pending = self._pending_bm_generals
            for g in self.roster.generals_of(base.id):
                if g.role != "vo":
                    continue
                army = self.roster.army_of(g.id)
                inf = army.infantry if army else 0
                cav = army.cavalry if army else 0
                arc = army.archers if army else 0
                total = army.total if army else 0
                if pending is not None:
                    checked = "☑" if g.id in pending else "☐"
                elif cfg.generals is not None:
                    checked = "☑" if g.id in sel_gens_set else "☐"
                else:
                    checked = "☑"
                self.bm_gen_tree.insert(
                    "",
                    "end",
                    iid=str(g.id),
                    text=g.name,
                    values=(checked, g.level, f"{g.stamina}/{g.stamina_max}", g.morale, inf, cav, arc, total),
                )
            self._pending_bm_generals = None
            self._update_bm_gen_count_label()
            self._update_bm_bases_tree_gen_count()


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
        cities_items = [c.display_name for c in self.roster.cities]
        if hasattr(self, "dt_camp_combo") and camps_items:
            cur_idx = self.dt_camp_combo.current()
            self.dt_camp_combo["values"] = camps_items
            if cur_idx >= 0 and cur_idx < len(camps_items):
                self.dt_camp_combo.current(cur_idx)
                self._on_dt_camp_selected()
        if hasattr(self, "bm_city_combo"):
            mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
            items = cities_items if (mode == 2 and cities_items) else camps_items
            if items:
                bm_idx = self.bm_city_combo.current()
                self.bm_city_combo["values"] = items
                if bm_idx >= 0 and bm_idx < len(items):
                    self.bm_city_combo.current(bm_idx)
                    self._on_bm_city_selected()

    def _create_binhman_tasks(self) -> list[BinhMan]:
        self._save_bm_current_base_config()
        if not self.roster or not self.roster.bases:
            messagebox.showwarning("Cảnh báo", "Dữ liệu tướng và căn cứ chưa sẵn sàng!")
            return []

        enabled_bases = [b for b in self.roster.bases if self.bm_base_configs.get(b.id, BaseBinhManConfig()).enabled]
        if not enabled_bases:
            if self._current_bm_base_id:
                curr_base = next((b for b in self.roster.bases if b.id == self._current_bm_base_id), None)
                if curr_base:
                    enabled_bases = [curr_base]
            if not enabled_bases:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 căn cứ để chạy Bình Man!")
                return []

        all_peers: list[BasePeer] = []
        for b in enabled_bases:
            cfg = self.bm_base_configs.get(b.id)
            if not cfg or not cfg.generals:
                continue
            t_types = cfg.target_types if cfg.target_types else ([int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()] if isinstance(cfg.mantypes, str) else [7, 8, 9, 10])
            all_peers.append(
                BasePeer(
                    base_id=b.id,
                    ox=b.pos_x,
                    oy=b.pos_y,
                    radius=int(cfg.radius) if str(cfg.radius).isdigit() else 10,
                    target_types=t_types,
                    origin=(b.pos_x, b.pos_y),
                    mantypes=t_types,
                    name=b.name,
                )
            )

        tasks: list[BinhMan] = []
        for b in enabled_bases:
            cfg = self.bm_base_configs.get(b.id)
            if not cfg:
                continue
            sel_gens = cfg.generals
            if not sel_gens:
                continue

            mode = cfg.mode
            camp_id = int(cfg.camp_id) if (mode == 1 and cfg.camp_id and str(cfg.camp_id).lstrip("-").isdigit()) else (b.id if (mode == 1 and b.is_camp) else None)
            parent_id = int(cfg.parent_city_id) if (cfg.parent_city_id and str(cfg.parent_city_id).isdigit()) else b.id

            scanner = Scanner(self.gateway, self.shared_target_locks, delay=0.0, sleep=lambda s: None)
            ctx = TaskContext(self.gateway, scanner, self.shared_target_locks, notify=lambda m, bname=b.name: self.after(0, self._append_bm_log, f"[{bname}] {m}"))
            peers = [p for p in all_peers if p.base_id != b.id]

            t_inf = int(cfg.target_infantry) if str(cfg.target_infantry).isdigit() else 0
            t_cav = int(cfg.target_cavalry) if str(cfg.target_cavalry).isdigit() else 0
            t_arc = int(cfg.target_archers) if str(cfg.target_archers).isdigit() else 0
            target_army = TargetArmy(infantry=t_inf, cavalry=t_cav, archers=t_arc)
            rad_int = int(cfg.radius) if str(cfg.radius).isdigit() else 10
            thresh_int = int(cfg.threshold) if str(cfg.threshold).isdigit() else 30
            mor_int = int(cfg.min_morale) if str(cfg.min_morale).isdigit() else 95
            b_types = cfg.target_types if cfg.target_types else ([int(x.strip()) for x in cfg.mantypes.split(",") if x.strip().isdigit()] if isinstance(cfg.mantypes, str) else [7, 8, 9, 10])

            task = BinhMan(
                ctx=ctx,
                generals=sel_gens,
                origin=(b.pos_x, b.pos_y),
                radius=rad_int,
                man_types=b_types,
                camp_id=camp_id,
                parent_city_id=parent_id,
                city_id=b.id if mode == 2 else parent_id,
                return_threshold=thresh_int,
                mode=mode,
                sleep_fn=time.sleep,
                combat_config=self._build_combat_config(),
                on_battle_found=lambda bid: self.after(
                    0, lambda x=bid: self.bt_id_var.set(str(x)) if hasattr(self, "bt_id_var") else None
                ),
                on_battle_state=lambda st: self.after(
                    0, lambda s=st: self._bt_render_state(s) if hasattr(self, "_bt_render_state") else None
                ),
                target_army=target_army,
                auto_recruit=cfg.auto_recruit,
                auto_morale=cfg.auto_morale,
                min_morale=mor_int,
                peers=peers,
                non_blocking_relocate=True,
                base_name=b.name,
            )
            tasks.append(task)

        if not tasks:
            messagebox.showwarning("Cảnh báo", "Không có căn cứ nào có võ tướng khả dụng được chọn!")
        return tasks

    def _create_binhman_task(self, base_id: Optional[int] = None) -> Optional[BinhMan]:
        if base_id is not None:
            tasks = self._create_binhman_tasks()
            for t in tasks:
                if getattr(t, "city_id", None) == base_id or getattr(t, "camp_id", None) == base_id:
                    return t
            return None

        self._save_bm_current_base_config()
        mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
        sel_idx = self.bm_city_combo.current() if hasattr(self, "bm_city_combo") else -1
        if mode == 2:
            bases = self.roster.cities if (self.roster and self.roster.cities) else (self.roster.bases if self.roster else [])
        else:
            bases = self.roster.camps if (self.roster and self.roster.camps) else (self.roster.bases if self.roster else [])

        if sel_idx < 0 or sel_idx >= len(bases):
            if self._current_bm_base_id and self.roster:
                base = next((b for b in self.roster.bases if b.id == self._current_bm_base_id), None)
            else:
                base = None
        else:
            base = bases[sel_idx]

        if not base:
            msg = "Vui lòng chọn Thành xuất phát!" if mode == 2 else "Vui lòng chọn căn cứ/doanh trại xuất phát!"
            messagebox.showwarning("Cảnh báo", msg)
            return None

        sel_gens = []
        if hasattr(self, "bm_gen_tree"):
            sel_gens = [int(iid) for iid in self.bm_gen_tree.get_children() if self.bm_gen_tree.item(iid, "values")[0] == "☑"]
        if not sel_gens and self.roster:
            cfg = self.bm_base_configs.get(base.id)
            if cfg and cfg.generals:
                sel_gens = cfg.generals

        if not sel_gens:
            vos = [g.id for g in self.roster.generals_of(base.id) if g.role == "vo"] if self.roster else []
            if not vos:
                messagebox.showwarning("Cảnh báo", "Căn cứ này không có võ tướng khả dụng!")
                return None
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng xuất kích!")
            return None

        parent_idx = self.bm_parent_city_combo.current() if hasattr(self, "bm_parent_city_combo") else -1
        parent_id = self.roster.cities[parent_idx].id if (self.roster and self.roster.cities and 0 <= parent_idx < len(self.roster.cities)) else None
        camp_id = int(self.bm_camp_id_var.get()) if (mode == 1 and hasattr(self, "bm_camp_id_var") and self.bm_camp_id_var.get().strip()) else (base.id if (mode == 1 and base.is_camp) else None)
        radius = int(self.bm_radius_var.get() or "10") if hasattr(self, "bm_radius_var") else 10
        try:
            threshold = int(self.bm_threshold_var.get() or "30") if hasattr(self, "bm_threshold_var") else 30
        except ValueError:
            threshold = 30
        if hasattr(self, "bm_mantypes_dropdown"):
            man_types = self.bm_mantypes_dropdown.get_selected()
        elif hasattr(self, "bm_mantypes_var"):
            man_types = [int(x.strip()) for x in self.bm_mantypes_var.get().split(",") if x.strip()]
        else:
            man_types = [7, 8, 9, 10]
        if not man_types:
            man_types = [7, 8, 9, 10]

        locks = self.shared_target_locks
        scanner = Scanner(self.gateway, locks, delay=0.0, sleep=lambda s: None)
        ctx = TaskContext(self.gateway, scanner, locks, notify=lambda m: self.after(0, self._append_bm_log, m))

        try:
            target_inf = int(self.bm_target_inf_var.get() or "0")
        except (ValueError, AttributeError):
            target_inf = 0
        try:
            target_cav = int(self.bm_target_cav_var.get() or "0")
        except (ValueError, AttributeError):
            target_cav = 0
        try:
            target_arc = int(self.bm_target_arc_var.get() or "0")
        except (ValueError, AttributeError):
            target_arc = 0
        try:
            min_morale = int(self.bm_min_morale_var.get() or "95")
        except (ValueError, AttributeError):
            min_morale = 95

        target_army = TargetArmy(infantry=target_inf, cavalry=target_cav, archers=target_arc)
        auto_recruit = bool(self.bm_auto_recruit_var.get()) if hasattr(self, "bm_auto_recruit_var") else True
        auto_morale = bool(self.bm_auto_morale_var.get()) if hasattr(self, "bm_auto_morale_var") else True

        return BinhMan(
            ctx=ctx,
            generals=sel_gens,
            origin=(base.pos_x, base.pos_y),
            radius=radius,
            man_types=man_types,
            camp_id=camp_id,
            parent_city_id=parent_id or base.id,
            city_id=base.id if mode == 2 else parent_id,
            return_threshold=threshold,
            mode=mode,
            sleep_fn=time.sleep,
            combat_config=self._build_combat_config(),
            on_battle_found=lambda bid: self.after(
                0, lambda b=bid: self.bt_id_var.set(str(b)) if hasattr(self, "bt_id_var") else None
            ),
            on_battle_state=lambda st: self.after(
                0, lambda s=st: self._bt_render_state(s) if hasattr(self, "_bt_render_state") else None
            ),
            target_army=target_army,
            auto_recruit=auto_recruit,
            auto_morale=auto_morale,
            min_morale=min_morale,
            base_name=base.name,
        )

    def _provision_base_troops(
        self,
        base_id: int,
        base_name: str,
        cfg: BaseBinhManConfig,
        prov: ArmyProvisioner,
    ):
        sel_gens = cfg.generals
        if not sel_gens:
            return

        t_inf = int(cfg.target_infantry) if str(cfg.target_infantry).isdigit() else 0
        t_cav = int(cfg.target_cavalry) if str(cfg.target_cavalry).isdigit() else 0
        t_arc = int(cfg.target_archers) if str(cfg.target_archers).isdigit() else 0
        target_army = TargetArmy(infantry=t_inf, cavalry=t_cav, archers=t_arc)
        auto_recruit = cfg.auto_recruit
        auto_morale = cfg.auto_morale
        min_morale = int(cfg.min_morale) if str(cfg.min_morale).isdigit() else 95
        mode = cfg.mode
        parent_id = int(cfg.parent_city_id) if (cfg.parent_city_id and str(cfg.parent_city_id).isdigit()) else None

        prefix = f"[{base_name}] " if base_name else ""
        self.after(0, self._append_bm_log, f"⚔️ {prefix}Tiến hành biên chế {len(sel_gens)} tướng...")

        if mode == 2:
            city_id = base_id
            for gid in sel_gens:
                prov.heal_general(city_id, gid)

            if target_army.total > 0 and auto_recruit:
                fresh_roster = fetch_roster(self.gateway, only_base_ids=[city_id])
                for gid in sel_gens:
                    army = fresh_roster.army_of(gid)
                    prov.adjust_troops(
                        base_id=city_id,
                        general_id=gid,
                        current_army=army,
                        target_army=target_army,
                        auto_recruit=True,
                        on_log=lambda m: self.after(0, self._append_bm_log, f"{prefix}{m}"),
                    )

            if auto_morale:
                fresh_roster = fetch_roster(self.gateway, only_base_ids=[city_id])
                city_gens = {g.id: g for g in fresh_roster.generals_of(city_id)}
                trainer = MoraleTrainer(self.gateway)
                def _on_notify_bm_city(msg):
                    self.after(0, self._append_bm_log, f"   {prefix}{msg}")
                trainer.adjust_squad_morale(
                    base_id=city_id,
                    general_ids=sel_gens,
                    target_morale=min_morale,
                    base_gens=city_gens,
                    on_notify=_on_notify_bm_city,
                )
        else:
            camp_id = base_id
            for gid in sel_gens:
                prov.heal_general(camp_id, gid)

            if target_army.total > 0:
                fresh_roster = fetch_roster(self.gateway, only_base_ids=[camp_id])
                for gid in sel_gens:
                    army = fresh_roster.army_of(gid)
                    prov.adjust_troops(
                        base_id=camp_id,
                        general_id=gid,
                        current_army=army,
                        target_army=target_army,
                        auto_recruit=False,
                        on_log=lambda m: self.after(0, self._append_bm_log, f"{prefix}{m}"),
                    )

                rechecked = fetch_roster(self.gateway, only_base_ids=[camp_id])
                def_gens = []
                for gid in sel_gens:
                    a = rechecked.army_of(gid)
                    inf = a.infantry if a else 0
                    cav = a.cavalry if a else 0
                    arc = a.archers if a else 0
                    if inf < target_army.infantry or cav < target_army.cavalry or arc < target_army.archers:
                        def_gens.append(gid)

                if def_gens:
                    if parent_id:
                        self.after(0, self._append_bm_log, f"⛺ {prefix}Quân đồn trú tại trại không đủ cho {len(def_gens)} tướng. Tự động điều về Thành mẹ {parent_id} bổ sung...")
                        prov.provision_camp_generals_with_parent_city(
                            camp_id=camp_id,
                            parent_city_id=parent_id,
                            general_ids=def_gens,
                            target_army=target_army,
                            min_morale=min_morale,
                            on_log=lambda m: self.after(0, self._append_bm_log, f"{prefix}{m}"),
                        )
                    else:
                        self.after(0, self._append_bm_log, f"⚠️ {prefix}Quân đồn trú tại trại không đủ và chưa chọn Thành mẹ! Vui lòng chọn Thành mẹ.")

            if auto_morale:
                fresh_roster = fetch_roster(self.gateway, only_base_ids=[camp_id])
                camp_gens = {g.id: g for g in fresh_roster.generals_of(camp_id)}
                trainer = MoraleTrainer(self.gateway)
                def _on_notify_bm_camp(msg):
                    self.after(0, self._append_bm_log, f"   {prefix}{msg}")
                trainer.adjust_squad_morale(
                    base_id=camp_id,
                    general_ids=sel_gens,
                    target_morale=min_morale,
                    base_gens=camp_gens,
                    on_notify=_on_notify_bm_camp,
                )

    def _manual_adjust_bm_troops(self):
        self._save_bm_current_base_config()
        if not self.roster or not self.roster.bases:
            messagebox.showwarning("Cảnh báo", "Dữ liệu tướng và căn cứ chưa sẵn sàng!")
            return

        base_id = self._current_bm_base_id or self.roster.bases[0].id
        base = next((b for b in self.roster.bases if b.id == base_id), None)
        if not base:
            messagebox.showwarning("Cảnh báo", "Không tìm thấy căn cứ!")
            return

        cfg = self.bm_base_configs.get(base_id, BaseBinhManConfig())
        if not cfg.generals:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 võ tướng!")
            return

        def _worker():
            try:
                self.after(0, self._append_bm_log, f"⚔️ Bắt đầu tiến trình biên chế quân đội Bình Man cho {base.name}...")
                prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)
                self._provision_base_troops(base.id, base.name, cfg, prov)
                self.after(0, self._append_bm_log, f"🏁 Hoàn tất biên chế quân đội cho căn cứ {base.name}!")
                self.roster = fetch_roster(self.gateway)
                self.after(0, self._load_bm_base_config, base.id)
            except Exception as e:
                self.after(0, self._append_bm_log, f"❌ Lỗi ngoại lệ khi biên chế: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _manual_adjust_all_bm_troops(self):
        self._save_bm_current_base_config()
        if not self.roster:
            messagebox.showwarning("Cảnh báo", "Dữ liệu chưa sẵn sàng!")
            return

        enabled_bases = [b for b in self.roster.bases if self.bm_base_configs.get(b.id, BaseBinhManConfig()).enabled]
        if not enabled_bases:
            messagebox.showwarning("Cảnh báo", "Chưa chọn căn cứ nào để biên chế!")
            return

        def _worker():
            try:
                self.after(0, self._append_bm_log, f"⚔️ Bắt đầu biên chế hàng loạt cho {len(enabled_bases)} căn cứ...")
                prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)
                for b in enabled_bases:
                    cfg = self.bm_base_configs.get(b.id, BaseBinhManConfig())
                    if not cfg.generals:
                        self.after(0, self._append_bm_log, f"⏩ [{b.name}] Bỏ qua vì không có võ tướng nào được chọn.")
                        continue
                    self._provision_base_troops(b.id, b.name, cfg, prov)

                self.after(0, self._append_bm_log, "🏁 Hoàn tất biên chế quân đội cho TẤT CẢ căn cứ đã chọn!")
                self.roster = fetch_roster(self.gateway)
                if self._current_bm_base_id:
                    self.after(0, self._load_bm_base_config, self._current_bm_base_id)
            except Exception as e:
                self.after(0, self._append_bm_log, f"❌ Lỗi biên chế hàng loạt: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _run_binhman_once(self):
        tasks = self._create_binhman_tasks()
        if not tasks:
            return
        def _worker():
            for t in tasks:
                bname = getattr(t, "base_name", f"Base-{getattr(t, 'city_id', '')}")
                res = t.run_once()
                self.after(0, self._append_bm_log, f"⚡ [{bname}] Kết quả chạy 1 lượt: {res}")
        threading.Thread(target=_worker, daemon=True).start()

    def _toggle_binhman(self):
        if not self._bm_runner or not self._bm_runner.is_alive():
            tasks = self._create_binhman_tasks()
            if not tasks:
                return
            try:
                bm_interval = max(3.0, float(self.bm_interval_var.get() or "15"))
            except ValueError:
                bm_interval = 15.0
            self._bm_runner = BinhManAutoRunner(
                tasks,
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
        logging.getLogger("linhvuong.tasks.HauCan").info(msg)
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        for w in list(self._active_log_texts):
            self._append_text_buffer(w, line)

    def _logis_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Hậu Cần & Điều Chuyển."""
        if hasattr(self, "logis_log_text") and self.logis_log_text:
            self.logis_log_text.delete("1.0", "end")

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
        try:
            self._save_unified_profile()
        except Exception:
            pass
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
                remaining = parse_boost_remaining_time(resp, city_id)

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
                        last_act = max(
                            getattr(self, "_last_boost_act_time", 0),
                            getattr(BuildingTask, "_last_boost_act_time", 0),
                        )
                        if now_ts - last_act > 60:
                            self._last_boost_act_time = now_ts
                            BuildingTask._last_boost_act_time = now_ts
                            msg = "⚡ DS kiến trúc đã hết hạn. Đang tự kích hoạt lại (3 vị trí thi công)..."
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
                                ok_msg = "✅ Kích hoạt thành công DS kiến trúc (3 vị trí thi công)!"
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

    def _schedule_periodic_boost_check(self):
        # Hủy timer cũ để tránh nhân bản chuỗi lặp mỗi lần reload roster
        old_id = getattr(self, "_boost_after_id", None)
        if old_id is not None:
            try:
                self.after_cancel(old_id)
            except Exception:
                pass
            self._boost_after_id = None
        try:
            if hasattr(self, "aux_boost_time_lbl") and self.aux_boost_time_lbl.winfo_exists():
                self._check_and_update_boost_status(async_check=True)
                today_str = time.strftime("%Y-%m-%d")
                if getattr(self, "aux_daily_reward_var", None) and self.aux_daily_reward_var.get():
                    if getattr(self, "_last_daily_claim_date", None) != today_str:
                        self._last_daily_claim_date = today_str
                        self._do_claim_daily()
                self._boost_after_id = self.after(60000, self._schedule_periodic_boost_check)
        except (RuntimeError, tk.TclError):
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
        self._check_and_update_boost_status(async_check=True)

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
                city_auto_open_box = auto_open_box and (cid in self._selected_resource_cities)

                task = BuildingTask(
                    gateway=self.gateway,
                    city_id=cid,
                    plans=plans,
                    max_slots=max_slots,
                    auto_speedup=self.bld_speedup_var.get(),
                    auto_boost=self.bld_boost_var.get(),
                    auto_comfort=self.bld_comfort_var.get(),
                    auto_open_box=city_auto_open_box,
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
        log_bar = tk.Frame(f_log_tab6, bg=CARD)
        log_bar.pack(side="top", fill="x", pady=(0, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._logis_clear_log).pack(side="right")
        self.logis_log_text = tk.Text(f_log_tab6, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0)
        self.logis_log_text.pack(fill="both", expand=True)

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
        try:
            self._append_logis_log("🎁 Đang gửi yêu cầu nhận thưởng chuyên cần hàng ngày...")
            if hasattr(self, "_append_bld_log"):
                self._append_bld_log("🎁 Đang gửi yêu cầu nhận thưởng chuyên cần hàng ngày...")
        except (RuntimeError, tk.TclError):
            pass

        def _on_notify(m: str):
            try:
                self.after(0, self._append_logis_log, m)
                if hasattr(self, "_append_bld_log"):
                    self.after(0, self._append_bld_log, m)
            except (RuntimeError, tk.TclError):
                pass

        task = LogisticsTask(self.gateway, notify=_on_notify)
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
            self._schedule_periodic_boost_check()

        # Cập nhật Combobox
        all_base_items = [b.display_name for b in roster.bases]
        city_items = [c.display_name for c in roster.cities]
        camps_items = [c.display_name for c in roster.camps] if roster.camps else all_base_items

        for combo in (self.bld_city_combo, self.res_city_combo, self.bm_parent_city_combo, self.gd_city_combo):
            combo["values"] = city_items
            if city_items and not combo.get():
                combo.current(0)

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

        today_str = time.strftime("%Y-%m-%d")
        if getattr(self, "aux_daily_reward_var", None) and self.aux_daily_reward_var.get():
            if getattr(self, "_last_daily_claim_date", None) != today_str:
                self._last_daily_claim_date = today_str
                self._do_claim_daily()

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

    # -------------------------------------------------------------------------
    # LUYỆN SĨ KHÍ QUÂN ĐỘI ĐA THÀNH (CONCURRENT MULTI-CITY MORALE TRAINING)
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
        if not hasattr(self, "_morale_generals_data") or not self._morale_generals_data:
            self.mo_status_lbl.configure(text="⚠️ Không có tướng có quân đội nào để luyện.")
            return

        targets = [
            data for gid, data in self._morale_generals_data.items()
            if gid in self._selected_morale_generals
        ]

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

                def _on_step(gid, cur, tgt, step_msg):
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

    # =========================================================================
    # TAB 6: CHIẾN TRƯỜNG & MƯU LƯỢC
    # =========================================================================
    def _build_battle_tab(self, parent):
        top_ctrl = tk.Frame(parent, bg=BG)
        top_ctrl.pack(fill="x", pady=6)

        # Hàng 1: Mã Chiến Trường, Nút Nạp, Nút Bắt đầu/Dừng Theo dõi tự động, Hiệp đấu, Đếm ngược
        row1 = tk.Frame(top_ctrl, bg=BG)
        row1.pack(fill="x", pady=(0, 4))

        tk.Label(row1, text="Mã Chiến Trường (ID):", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
        self.bt_id_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.bt_id_var, width=10).pack(side="left", padx=(0, 8))

        ttk.Button(row1, text="🔍 Nạp Chiến Trường", style="Action.TButton", command=self._bt_load_battle).pack(side="left", padx=(0, 6))

        self.bt_start_btn = ttk.Button(row1, text="▶️ Theo Dõi & Tác Chiến", style="Success.TButton", command=self._bt_toggle_auto)
        self.bt_start_btn.pack(side="left", padx=(0, 16))

        self.bt_bout_var = tk.StringVar(value="Hiệp: -")
        tk.Label(row1, textvariable=self.bt_bout_var, bg=BG, fg="#4da3ff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 12))

        self.bt_countdown_var = tk.StringVar(value="Đếm ngược: -s")
        tk.Label(row1, textvariable=self.bt_countdown_var, bg=BG, fg="#ff9f43", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))

        # Khung cấu hình tác chiến
        cfg_frame = ttk.LabelFrame(top_ctrl, text="Thiết lập Tác chiến & Mưu lược", style="Card.TLabelframe")
        cfg_frame.pack(fill="x", pady=4, padx=2)

        cfg_r1 = tk.Frame(cfg_frame, bg=CARD)
        cfg_r1.pack(fill="x", pady=2, padx=4)

        self.bt_auto_counter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r1, text="Tự đổi trận ngũ hành", variable=self.bt_auto_counter_var, style="TCheckbutton").pack(side="left", padx=(0, 12))

        tk.Label(cfg_r1, text="Cửa sổ đổi trận:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 2))
        self.bt_window_var = tk.StringVar(value="15")
        ttk.Entry(cfg_r1, textvariable=self.bt_window_var, width=4).pack(side="left", padx=(0, 2))
        tk.Label(cfg_r1, text="s cuối hiệp", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 12))

        self.bt_leave_boss_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r1, text="Bắt sống BOSS (Phòng ngự khi chỉ còn BOSS)", variable=self.bt_leave_boss_var, style="TCheckbutton").pack(side="left", padx=(0, 12))

        self.bt_cleanse_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r1, text="Tự giải Hỗn loạn (mưu kế 96)", variable=self.bt_cleanse_var, style="TCheckbutton").pack(side="left", padx=(0, 10))

        cfg_r2 = tk.Frame(cfg_frame, bg=CARD)
        cfg_r2.pack(fill="x", pady=2, padx=4)

        tk.Label(cfg_r2, text="Chiêu tấn công:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bt_action_mode_var = tk.StringVar(value="adaptive")
        self.bt_action_mode_combo = ttk.Combobox(cfg_r2, state="readonly", width=24)
        self.bt_action_mode_combo["values"] = [
            "Tự thích ứng theo binh chủng",
            "Cố định Hỏa tiễn (13 - Cung)",
            "Cố định Đột kích (10 - Kỵ)",
            "Cố định Mãnh công (11 - Bộ)",
            "Tấn công phổ thông (1)",
        ]
        self.bt_action_mode_combo.current(0)
        self.bt_action_mode_combo.pack(side="left", padx=(0, 12))
        self.bt_action_mode_combo.bind("<<ComboboxSelected>>", self._on_bt_action_mode_changed)

        self.bt_skip_confused_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r2, text="Bỏ qua địch hỗn loạn", variable=self.bt_skip_confused_var, style="TCheckbutton").pack(side="left", padx=(0, 12))

        tk.Label(cfg_r2, text="Mưu kế Hiệp 1:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.bt_stratagem_combo = ttk.Combobox(cfg_r2, state="readonly", width=18)
        self.bt_stratagem_combo["values"] = [
            "0. Không dùng",
            "93. Phản khách vi chủ",
            "95. Cầm tặc cầm vương",
            "94. Quan môn tróc tặc",
        ]
        self.bt_stratagem_combo.current(0)
        self.bt_stratagem_combo.pack(side="left", padx=(0, 12))

        tk.Label(cfg_r2, text="Rút lui khẩn cấp (mưu 92 khi lính < %):", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.bt_retreat_var = tk.StringVar(value="0")
        ttk.Entry(cfg_r2, textvariable=self.bt_retreat_var, width=4).pack(side="left", padx=(0, 6))

        # Thân giao diện: 2 Bảng (Trái: Phe Ta, Phải: Phe Địch)
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure((0, 1), weight=1, uniform="bt")
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        # Trái: Bảng Quân Ta
        f_left = ttk.LabelFrame(body, text="🛡️ Phe Ta (Quân đội & Tướng lĩnh)", style="Card.TLabelframe")
        f_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))

        self.bt_our_tree = ttk.Treeview(
            f_left,
            columns=("pos", "army", "morale", "fid", "status", "action", "target"),
            show="tree headings",
            selectmode="browse",
        )
        self.bt_our_tree.heading("#0", text="Tên tướng")
        self.bt_our_tree.heading("pos", text="Vị trí")
        self.bt_our_tree.heading("army", text="Quân số")
        self.bt_our_tree.heading("morale", text="Sĩ khí")
        self.bt_our_tree.heading("fid", text="Trận hình")
        self.bt_our_tree.heading("status", text="Trạng thái")
        self.bt_our_tree.heading("action", text="Lệnh đánh")
        self.bt_our_tree.heading("target", text="Mục tiêu")

        self.bt_our_tree.column("#0", width=120)
        self.bt_our_tree.column("pos", width=40, anchor="center")
        self.bt_our_tree.column("army", width=75, anchor="e")
        self.bt_our_tree.column("morale", width=55, anchor="center")
        self.bt_our_tree.column("fid", width=85, anchor="center")
        self.bt_our_tree.column("status", width=75, anchor="center")
        self.bt_our_tree.column("action", width=85, anchor="center")
        self.bt_our_tree.column("target", width=55, anchor="center")

        our_scroll = ttk.Scrollbar(f_left, orient="vertical", command=self.bt_our_tree.yview)
        self.bt_our_tree.configure(yscrollcommand=our_scroll.set)
        self.bt_our_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        our_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)

        # Phải: Bảng Quân Địch
        f_right = ttk.LabelFrame(body, text="🎯 Phe Địch", style="Card.TLabelframe")
        f_right.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))

        self.bt_enemy_tree = ttk.Treeview(
            f_right,
            columns=("pos", "army", "morale", "fid", "status", "target"),
            show="tree headings",
            selectmode="browse",
        )
        self.bt_enemy_tree.heading("#0", text="Tên địch")
        self.bt_enemy_tree.heading("pos", text="Vị trí")
        self.bt_enemy_tree.heading("army", text="Quân số")
        self.bt_enemy_tree.heading("morale", text="Sĩ khí")
        self.bt_enemy_tree.heading("fid", text="Trận hình")
        self.bt_enemy_tree.heading("status", text="Trạng thái")
        self.bt_enemy_tree.heading("target", text="Mục tiêu")

        self.bt_enemy_tree.column("#0", width=120)
        self.bt_enemy_tree.column("pos", width=40, anchor="center")
        self.bt_enemy_tree.column("army", width=75, anchor="e")
        self.bt_enemy_tree.column("morale", width=55, anchor="center")
        self.bt_enemy_tree.column("fid", width=85, anchor="center")
        self.bt_enemy_tree.column("status", width=75, anchor="center")
        self.bt_enemy_tree.column("target", width=55, anchor="center")

        en_scroll = ttk.Scrollbar(f_right, orient="vertical", command=self.bt_enemy_tree.yview)
        self.bt_enemy_tree.configure(yscrollcommand=en_scroll.set)
        self.bt_enemy_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        en_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)

        # Khung nhật ký chiến trường & Hàng nút thao tác nhanh
        f_bottom = ttk.LabelFrame(body, text="Nhật ký chiến trường & Thao tác thủ công", style="Card.TLabelframe")
        f_bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))

        # Hàng thao tác thủ công nhanh
        manual_bar = tk.Frame(f_bottom, bg=CARD)
        manual_bar.pack(fill="x", padx=6, pady=(4, 2))

        tk.Label(manual_bar, text="Đổi Trận:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bt_manual_formation_combo = ttk.Combobox(manual_bar, state="readonly", width=12)
        self.bt_manual_formation_combo["values"] = ["1. Trùy hình", "2. Câu hình", "3. Kê hình", "4. Hạc dực", "5. Ngư lân"]
        self.bt_manual_formation_combo.current(0)
        self.bt_manual_formation_combo.pack(side="left", padx=(0, 4))
        ttk.Button(manual_bar, text="🔄 Đổi ngay", style="Action.TButton", command=self._bt_manual_change_formation).pack(side="left", padx=(0, 12))

        tk.Label(manual_bar, text="Mưu kế:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bt_manual_stratagem_combo = ttk.Combobox(manual_bar, state="readonly", width=18)
        self.bt_manual_stratagem_combo["values"] = [
            "96. Hủy bỏ trạng thái",
            "92. Kim thiền thoát xác",
            "93. Phản khách vi chủ",
            "95. Cầm tặc cầm vương",
            "94. Quan môn tróc tặc",
        ]
        self.bt_manual_stratagem_combo.current(0)
        self.bt_manual_stratagem_combo.pack(side="left", padx=(0, 4))
        ttk.Button(manual_bar, text="✨ Kích hoạt", style="Action.TButton", command=self._bt_manual_cast_stratagem).pack(side="left", padx=(0, 12))

        ttk.Button(manual_bar, text="🛡️ Phòng ngự toàn quân", style="Action.TButton", command=self._bt_manual_defend_all).pack(side="left", padx=(0, 8))
        ttk.Button(manual_bar, text="🗑️ Xóa log", style="Action.TButton", command=self._bt_clear_log).pack(side="right", padx=4)

        # Log Text box
        log_frame = tk.Frame(f_bottom, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        self.bt_log_text = tk.Text(log_frame, bg="#0d0e15", fg="#dcdde1", font=("Consolas", 9), wrap="word")
        bt_log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.bt_log_text.yview)
        self.bt_log_text.configure(yscrollcommand=bt_log_scroll.set)
        self.bt_log_text.pack(side="left", fill="both", expand=True)
        bt_log_scroll.pack(side="right", fill="y")

    def _on_bt_action_mode_changed(self, event=None):
        val = self.bt_action_mode_combo.get()
        if "thích ứng" in val.lower():
            self.bt_action_mode_var.set("adaptive")
        else:
            self.bt_action_mode_var.set("fixed")

    def _append_bt_log(self, msg: str):
        if hasattr(self, "bt_log_text") and self.bt_log_text:
            line = msg if msg.endswith("\n") else (msg + "\n")
            self._append_text_buffer(
                self.bt_log_text,
                line,
                max_lines=COMBAT_MAX_LOG_LINES,
                trim_batch=COMBAT_TRIM_LINES,
            )

    def _bt_clear_log(self):
        if hasattr(self, "bt_log_text"):
            self.bt_log_text.delete("1.0", "end")

    def _bt_load_battle(self):
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0
        engine = BattleController(self.gateway)
        state = engine.get_battle_info(battle_id)
        if not state or state.ret != 0:
            self._append_bt_log(f"❌ Không tải được thông tin chiến trường (ID: {battle_id}, ret: {state.ret if state else 'None'})")
            return
        self._bt_render_state(state)
        self._append_bt_log(f"✅ Đã tải thông tin chiến trường '{state.site}' (ID: {battle_id}, Hiệp: {state.bout}, Còn lại: {state.bout_left}s)")

    def _bt_render_state(self, state: BattleState):
        self.bt_bout_var.set(f"Hiệp: {state.bout}")
        self.bt_countdown_var.set(f"Đếm ngược: {state.bout_left}s")

        # Cập nhật bảng quân ta
        self.bt_our_tree.delete(*self.bt_our_tree.get_children())
        for t in state.our_troops:
            fname = FORMATION_NAMES.get(t.formation_id, f"Trận {t.formation_id}")
            status_str = "Hỗn loạn" if t.status == 1 else "Bình thường"
            act_name = ATTACK_ACTIONS.get(t.attack_action, str(t.attack_action))
            target_str = str(t.target_id) if t.target_id != 0 else "Tùy chọn"
            self.bt_our_tree.insert(
                "", "end", iid=str(t.position), text=t.general_name,
                values=(t.position, f"{t.soldiers}/{t.initial_soldiers}", t.morale, fname, status_str, act_name, target_str)
            )

        # Cập nhật bảng quân địch
        self.bt_enemy_tree.delete(*self.bt_enemy_tree.get_children())
        for e in state.enemy_troops:
            fname = FORMATION_NAMES.get(e.formation_id, f"Trận {e.formation_id}")
            status_str = "Hỗn loạn" if e.status == 1 else ("BOSS" if e.is_boss else "Bình thường")
            target_str = str(e.target_id) if e.target_id != 0 else "Tùy chọn"
            self.bt_enemy_tree.insert(
                "", "end", iid=str(e.position), text=f"{e.general_name} {'👑' if e.is_boss else ''}",
                values=(e.position, f"{e.soldiers}/{e.initial_soldiers}", e.morale, fname, status_str, target_str)
            )

    def _bt_toggle_auto(self):
        if getattr(self, "_bt_running", False):
            self._bt_running = False
            if hasattr(self, "_bt_stop_event"):
                self._bt_stop_event.set()
            self.bt_start_btn.configure(text="▶️ Theo Dõi & Tác Chiến", style="Success.TButton")
            self._append_bt_log("⏹️ Đã dừng tiến trình theo dõi tác chiến tự động.")
        else:
            self._bt_running = True
            self._bt_stop_event = threading.Event()
            self.bt_start_btn.configure(text="⏹️ Dừng Theo Dõi", style="Danger.TButton")
            threading.Thread(target=self._bt_auto_thread, daemon=True).start()

    def _build_combat_config(self) -> CombatConfig:
        action_mode = "adaptive"
        fixed_id = 13
        combo_val = self.bt_action_mode_combo.get() if hasattr(self, "bt_action_mode_combo") else ""
        if "13" in combo_val:
            fixed_id = 13
            action_mode = "fixed"
        elif "10" in combo_val:
            fixed_id = 10
            action_mode = "fixed"
        elif "11" in combo_val:
            fixed_id = 11
            action_mode = "fixed"
        elif "1" in combo_val:
            fixed_id = 1
            action_mode = "fixed"

        s_val = self.bt_stratagem_combo.get() if hasattr(self, "bt_stratagem_combo") else ""
        s_id = int(s_val.split(".")[0]) if "." in s_val and s_val.split(".")[0].isdigit() else 0

        win_raw = self.bt_window_var.get() if hasattr(self, "bt_window_var") else "15"
        retreat_raw = self.bt_retreat_var.get() if hasattr(self, "bt_retreat_var") else "0"

        return CombatConfig(
            auto_counter_formation=bool(self.bt_auto_counter_var.get()) if hasattr(self, "bt_auto_counter_var") else True,
            formation_window_seconds=int(win_raw) if win_raw.isdigit() else 15,
            attack_action_mode=action_mode,
            fixed_action_id=fixed_id,
            skip_confused_enemy=bool(self.bt_skip_confused_var.get()) if hasattr(self, "bt_skip_confused_var") else True,
            leave_boss_last=bool(self.bt_leave_boss_var.get()) if hasattr(self, "bt_leave_boss_var") else True,
            auto_cleanse_confusion=bool(self.bt_cleanse_var.get()) if hasattr(self, "bt_cleanse_var") else True,
            emergency_retreat_threshold=int(retreat_raw) if retreat_raw.isdigit() else 0,
            offensive_stratagem_id=s_id,
        )

    def _bt_auto_thread(self):
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0

        cfg = self._build_combat_config()

        self._append_bt_log(f"🚀 Bắt đầu động cơ tác chiến tự động cho chiến trường ID {battle_id}...")
        engine = BattleController(self.gateway, config=cfg)

        try:
            report = engine.track_battle(
                battle_id=battle_id,
                on_log=self._append_bt_log,
                on_state=lambda st: self.after(0, lambda s=st: self._bt_render_state(s)),
                stop_event=self._bt_stop_event,
                config=cfg,
            )
            self._append_bt_log("🏁 Đã hoàn tất phiên theo dõi chiến trường.")
        except Exception as ex:
            self._append_bt_log(f"❌ Lỗi tác chiến: {ex}")
        finally:
            self._bt_running = False
            self.after(0, lambda: self.bt_start_btn.configure(text="▶️ Theo Dõi & Tác Chiến", style="Success.TButton"))

    def _bt_manual_change_formation(self):
        sel = self.bt_our_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn một tướng ta từ bảng danh sách bên trái để đổi trận hình!")
            return
        pos_id = int(sel[0])
        fid_str = self.bt_manual_formation_combo.get()
        fid = int(fid_str.split(".")[0]) if "." in fid_str else 1
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0

        engine = BattleController(self.gateway)
        st = engine.get_battle_info(battle_id)
        if not st:
            return
        target_troop = next((t for t in st.our_troops if t.position == pos_id), None)
        if not target_troop:
            return
        ok = engine._change_formation_preserving_plan(target_troop, fid, battle_id=battle_id)
        if ok:
            self._append_bt_log(f"🔄 Đã gửi lệnh đổi tướng [{target_troop.general_name}] sang {FORMATION_NAMES.get(fid, fid)}")
            self._bt_load_battle()
        else:
            self._append_bt_log(f"❌ Đổi trận hình thất bại cho tướng [{target_troop.general_name}]")

    def _bt_manual_cast_stratagem(self):
        sel = self.bt_our_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn một tướng ta từ bảng danh sách bên trái để thi triển mưu kế!")
            return
        pos_id = int(sel[0])
        s_str = self.bt_manual_stratagem_combo.get()
        sid = int(s_str.split(".")[0]) if "." in s_str else 96
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0

        engine = BattleController(self.gateway)
        ok = engine.cast_stratagem(battle_id, pos_id, sid)
        s_name = STRATAGEMS.get(sid, f"Mưu kế {sid}")
        if ok:
            self._append_bt_log(f"✨ Đã thi triển mưu kế [{s_name}] lên vị trí {pos_id}")
            self._bt_load_battle()
        else:
            self._append_bt_log(f"❌ Thi triển mưu kế thất bại (vị trí {pos_id}, mưu kế {sid})")

    def _bt_manual_defend_all(self):
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0
        engine = BattleController(self.gateway)
        st = engine.get_battle_info(battle_id)
        if not st:
            return
        for our in st.our_troops:
            dest = our.target_id if our.target_id != 0 else (st.enemy_troops[0].position if st.enemy_troops else 0)
            engine.change_target_attack(battle_id, our.position, dest, action=3)
        self._append_bt_log("🛡️ Đã chuyển toàn bộ quân ta sang thế Phòng ngự (action 3)")
        self._bt_load_battle()

    def destroy(self):
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
            if getattr(self, "_boost_after_id", None) is not None:
                self.after_cancel(self._boost_after_id)
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
