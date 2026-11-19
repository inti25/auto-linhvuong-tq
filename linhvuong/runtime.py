"""Lõi Điều Phối Headless Dùng Chung (WorkspaceManager & AccountSession - ADR-0038).

Cung cấp toàn bộ vòng đời phiên tài khoản, đồng bộ ProfileStore, điều phối
7 phân hệ tự động hóa qua AutomationEngine, bộ đệm nhật ký vòng và phát sự kiện
thời gian thực mà hoàn toàn không phụ thuộc Tkinter.
"""

from collections import deque
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional, Union

import requests

from .auth import LoginError, login, normalize_proxy_url, parse_server_id
from .armament import (
    ALL_SCOPES as ARM_ALL_SCOPES,
    SCOPE_NAMES as ARM_SCOPE_NAMES,
    armament_matches,
    describe_armament,
    fetch_armament,
    find_general_base,
    sync_armament,
)
from .battle import (
    ATTACK_ACTION_COMBO_OPTIONS,
    ATTACK_ACTIONS,
    FORMATION_NAMES,
    STRATAGEMS,
    BattleController,
    BattleState,
    CombatConfig,
    parse_attack_action_combo,
)
from .engine import AutomationEngine, TaskStatus
from .gateway import GatewayClient
from .generals import (
    EQUIP_MODE_ASSIGN,
    EQUIP_MODE_UNEQUIP,
    EQUIP_TYPES,
    RENAME_MAX_WIDTH,
    build_rename_plan,
    collect_reward_targets,
    configure_equipment,
    configure_tacticians,
    fetch_equipment_inventory,
    general_name_width,
    rename_generals,
    reward_all_generals,
    validate_general_name,
)
from .locks import TargetLocks
from .logger import setup_logger
from .notifications import (
    NotificationConfig,
    dispatch_boss_alert,
    dispatch_system_alert,
    reset_system_alert,
)
from .paths import (
    DataDirLock,
    atomic_write_text,
    ensure_data_dir,
    get_data_dir,
    logs_dir,
    runtime_state_path,
    settings_path,
)
from .profile import BaseBinhManConfig, CityCraftConfig, Profile, ProfileStore
from .proxy import DEFAULT_FREE_PROXY_URL, ProxyPool
from .roster import Roster, fetch_roster
from .scan import BasePeer, Scanner
from .security import CredentialVault, VaultError, resolve_or_create_vault_key
from .tasks.base import CaptchaRequired, TaskContext
from .tasks.binh_man import MAN_TARGET_OPTIONS, BinhMan
from .tasks.building import (
    BUILDING_NAMES,
    CHEST_MAPPING,
    BuildingPlan,
    BuildingTask,
    chest_needs_city_switch,
    fetch_city_resources_snapshot,
    parse_boost_remaining_time,
    run_batch_open_chest,
)
from .tasks.crafting import WEAPONS_DATA, WeaponCrafter, get_weapon_name
from .tasks.di_trai import DiTrai
from .tasks.goi_dan import GoiDan
from .tasks.logistics import (
    TRANSFER_WEAPONS_DATA,
    ArmyTransferOrder,
    ArmyWeaponTransferTask,
    LogisticsTask,
    get_transfer_weapon_name,
)
from .tasks.morale import MoraleTrainer
from .tasks.nien_thu import NienThuTask
from .tasks.research import TECH_NAMES, ResearchTask, TechPlan
from .tasks.thao_phat import (
    ERROR_MESSAGES,
    THAOPHAT_MISSIONS,
    TargetArmy,
    ThaoPhatAutoRunner,
    ThaoPhatExecutor,
)
from .troops import ArmyProvisioner
from .world_chat import STATE_VI_NAMES

logger = logging.getLogger("linhvuong.runtime")

RESUMABLE_TASKS = (
    "building",
    "research",
    "thaophat",
    "binhman",
    "goidan",
    "nienthu",
    "resource_monitor",
    "crafting",
    "transfer_loop",
    "army_transfer",
)

AUTO_START_TASK_LABELS = (
    ("building", "🏛️ Xây dựng"),
    ("research", "🔬 Nghiên cứu"),
    ("thaophat", "⚔️ Thảo phạt"),
    ("binhman", "🏕️ Bình man"),
    ("goidan", "🧛 Gọi man"),
    ("nienthu", "🧧 Niên thú"),
    ("crafting", "🛡️ Chế tạo quân giới"),
    ("transfer_loop", "🚚 Chuyển quân giới lặp"),
    ("resource_monitor", "📦 Tự mở rương TN/Vàng"),
)


def _normalize_auto_start_tasks(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple, set)):
        return []
    allowed = set(RESUMABLE_TASKS)
    out: list[str] = []
    for item in raw:
        name = str(item or "").strip()
        if name in allowed and name not in out:
            out.append(name)
    return out

LOG_CHANNELS = (
    "global",
    "building",
    "logistics",
    "thaophat",
    "binhman",
    "goidan",
    "battle",
    "nienthu",
    "crafting",
    "tactician",
    "equip",
    "chest",
    "armament",
    "rename",
)


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        if val is None or str(val).strip() == "":
            return default
        return int(str(val).replace(",", "").replace(".", "").strip())
    except (ValueError, TypeError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or str(val).strip() == "":
            return default
        cleaned = str(val).lower().replace(",", ".").replace("giờ", "").replace("gio", "").replace("h", "").strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def serialize_roster(roster: Optional[Roster]) -> dict:
    if not roster:
        return {"cities": [], "camps": [], "bases": [], "generals": [], "armies": {}}
    bases_list = []
    for b in roster.bases:
        bases_list.append({
            "id": b.id,
            "name": b.name,
            "display_name": b.display_name,
            "type": b.type,
            "is_camp": b.is_camp,
            "pos_x": b.pos_x,
            "pos_y": b.pos_y,
        })
    gens_list = []
    for b in roster.bases:
        for g in roster.generals_of(b.id):
            army = roster.army_of(g.id)
            gens_list.append({
                "id": g.id,
                "name": g.name,
                "role": g.role,
                "city_id": b.id,
                "level": g.level,
                "stamina": g.stamina,
                "stamina_max": g.stamina_max,
                "morale": g.morale,
                "loyalty": g.loyalty,
                "status": g.status,
                "status_text": g.status_text,
                "tactician_id": getattr(g, "tactician_id", 0),
                "tactician_name": g.tactician_name,
                "is_mayor": bool(getattr(g, "is_mayor", False)),
                "is_tactician": bool(getattr(g, "is_tactician", False)),
                "upgrading_time": getattr(g, "upgrading_time", 0),
                "army": {
                    "infantry": army.infantry if army else 0,
                    "cavalry": army.cavalry if army else 0,
                    "archers": army.archers if army else 0,
                    "total": army.total if army else 0,
                },
            })
    return {
        "cities": [b for b in bases_list if not b["is_camp"]],
        "camps": [b for b in bases_list if b["is_camp"]],
        "bases": bases_list,
        "generals": gens_list,
    }


def serialize_battle_state(state: Optional[BattleState]) -> Optional[dict]:
    if not state:
        return None

    def _troop(t):
        return {
            "position": t.position,
            "general_name": t.general_name,
            "soldiers": t.soldiers,
            "initial_soldiers": t.initial_soldiers,
            "morale": t.morale,
            "formation_id": t.formation_id,
            "formation_name": FORMATION_NAMES.get(t.formation_id, f"Trận {t.formation_id}"),
            "status": t.status,
            "status_text": "Hỗn loạn" if t.status == 1 else ("BOSS" if t.is_boss else "Bình thường"),
            "attack_action": t.attack_action,
            "attack_action_name": ATTACK_ACTIONS.get(t.attack_action, str(t.attack_action)),
            "target_id": t.target_id,
            "is_boss": t.is_boss,
        }

    return {
        "ret": state.ret,
        "site": state.site,
        "bout": state.bout,
        "bout_left": state.bout_left,
        "our_troops": [_troop(t) for t in state.our_troops],
        "enemy_troops": [_troop(t) for t in state.enemy_troops],
        "has_boss": bool(state.boss_troops),
    }


class _BinhManRunnable:
    """Adapter điều phối Bình Man đa căn cứ tương thích AutomationEngine + CaptchaRequired."""

    def __init__(self, tasks: list[BinhMan], interval: float, log_cb: Callable[[str], None]):
        self.tasks = tasks
        self.interval = max(3.0, float(interval))
        self.log_cb = log_cb
        self.stop_event = threading.Event()

    def _run_base(self, task: BinhMan):
        base_label = getattr(task, "base_name", "") or f"Căn cứ {task.origin_id}"
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            try:
                res = task.run_once()
                if not (isinstance(res, str) and res.startswith("no_target")):
                    self.log_cb(f"[{base_label}] Lượt {cycle}: {res}")
            except CaptchaRequired:
                self.log_cb(f"⚠️ [{base_label}] Server yêu cầu Captcha! Tạm dừng Bình Man.")
                raise
            except Exception as exc:
                self.log_cb(f"❌ [{base_label}] Lỗi Bình Man: {exc}")
            if self.stop_event.wait(self.interval):
                break

    def _bind_stop_event(self) -> None:
        for t in self.tasks:
            t.stop_event = self.stop_event
            if getattr(t, "ctx", None) is not None:
                t.ctx.stop_event = self.stop_event
            if getattr(t, "sleep_fn", None) is time.sleep:
                t.sleep_fn = lambda s, ev=self.stop_event: ev.wait(max(0.0, float(s)))

    def run(self):
        self._bind_stop_event()
        if len(self.tasks) == 1:
            self._run_base(self.tasks[0])
            return
        captcha_hit = threading.Event()
        threads = []

        def _worker(t: BinhMan):
            try:
                self._run_base(t)
            except CaptchaRequired:
                captcha_hit.set()
                self.stop_event.set()

        for t in self.tasks:
            th = threading.Thread(target=_worker, args=(t,), daemon=True)
            threads.append(th)
            th.start()
        for th in threads:
            th.join()
        if captcha_hit.is_set():
            raise CaptchaRequired()


class AccountSession:
    """Phiên điều hành độc lập cho 1 tài khoản Linh Vương (không phụ thuộc Tkinter)."""

    def __init__(
        self,
        account_key: str,
        session: requests.Session,
        server_id: int,
        username: str,
        password: str = "",
        proxy_raw: str = "",
        proxy_user: str = "",
        proxy_pass: str = "",
        proxy_url: str = "",
        proxy_pool: Optional[ProxyPool] = None,
        data_dir: Optional[Union[str, Path]] = None,
        event_cb: Optional[Callable[[str, str, dict], None]] = None,
    ):
        self.account_key = account_key
        self.session = session
        self.server_id = int(server_id)
        self.username = username
        self._password = password
        self.proxy_raw = proxy_raw
        self.proxy_user = proxy_user
        self.proxy_pass = proxy_pass
        self.proxy_url = proxy_url
        self.proxy_pool = proxy_pool
        self.data_dir = get_data_dir(data_dir)
        self._event_cb = event_cb
        self._lock = threading.RLock()

        try:
            setup_logger(username=username or "guest", server_id=self.server_id, log_dir=logs_dir(self.data_dir))
        except Exception:
            pass

        self.profile_path = ProfileStore.resolve_profile_path(
            username=username, server_id=self.server_id, data_dir=self.data_dir
        )
        if self.profile_path.exists():
            try:
                self.profile = ProfileStore.load(self.profile_path)
            except Exception as exc:
                logger.warning(f"Lỗi nạp hồ sơ {self.profile_path}: {exc}")
                self.profile = Profile()
        else:
            self.profile = Profile()

        if self.proxy_pool:
            def _on_failover(old_ep, new_ep):
                old_n = old_ep.display_name if old_ep else "không rõ"
                new_n = new_ep.display_name if new_ep else "hết proxy"
                self.append_log("global", f"⚠️ Proxy lỗi ({old_n}). Đã tự động đổi sang: {new_n}")
                self._emit("proxy_updated", self.get_proxy_status())
                if not new_ep:
                    dispatch_system_alert(
                        "disconnect",
                        self.account_key,
                        "Hết Proxy Khả Dụng",
                        f"Tất cả proxy trong pool của [{self.account_key}] đã chết.",
                        config=self._notification_config(),
                        on_log=lambda m: self.append_log("global", m),
                        on_web_event=lambda ev: self._emit("notification", ev),
                    )
            self.proxy_pool.on_failover = _on_failover

        relogin_cb = self._build_relogin_callback()
        self.gateway = GatewayClient(
            self.server_id, self.session, relogin_callback=relogin_cb, proxy_pool=self.proxy_pool
        )
        self.tp_executor = ThaoPhatExecutor(self.gateway)
        self.roster = Roster()
        self.shared_target_locks = TargetLocks()

        self.engine = AutomationEngine()
        self.engine.subscribe(on_log=self._on_engine_log, on_status=self._on_engine_status)

        self.status = "connected"
        self.status_text = "Đã kết nối"
        self.captcha_required = False
        self.captcha_reason = ""
        self._destroyed = False

        self.logs: dict[str, deque[str]] = {
            ch: deque(maxlen=300 if ch == "battle" else 500) for ch in LOG_CHANNELS
        }

        # State phụ trợ & worker Threads ngoài AutomationEngine
        self._tech_levels: dict[int, int] = {}
        self._tech_current: Optional[dict] = None
        self._last_daily_claim_date: Optional[str] = None
        self._last_boost_act_time: float = 0.0
        self._boost_left_seconds: int = 0
        self._boost_checked_at: Optional[float] = None
        self._explore_left_seconds: int = 0
        self._explore_checked_at: Optional[float] = None

        self._res_monitor_running = False
        self._res_monitor_stop = threading.Event()
        self._res_monitor_thread: Optional[threading.Thread] = None

        self._craft_running = False
        self._craft_stop = threading.Event()
        self._craft_thread: Optional[threading.Thread] = None
        self._craft_last_run: dict[int, float] = {}
        self._craft_statuses: dict[int, str] = {}

        self._morale_running = False
        self._morale_stop = threading.Event()
        self._morale_thread: Optional[threading.Thread] = None
        self._morale_status = "Chờ lệnh"
        self._morale_gen_status: dict[int, str] = {}

        self._ditrai_running = False
        self._ditrai_stop = threading.Event()
        self._ditrai_thread: Optional[threading.Thread] = None
        self._ditrai_status = "Sẵn sàng"

        self._battle_running = False
        self._battle_stop = threading.Event()
        self._battle_thread: Optional[threading.Thread] = None
        self._battle_id = 0
        self._battle_state: Optional[dict] = None
        self._roster_resync_lock = threading.Lock()
        self._roster_resync_inflight = False

        self._chest_running = False
        self._chest_stop = threading.Event()
        self._chest_thread: Optional[threading.Thread] = None
        self._chest_progress = {"done": 0, "total": 0, "pct": 0.0, "status": "Sẵn sàng"}

        self._tac_running = False
        self._tac_stop = threading.Event()
        self._tac_status = "Sẵn sàng"

        self._equip_running = False
        self._equip_stop = threading.Event()
        self._equip_status = "Sẵn sàng"
        self._equip_inventory: Optional[dict] = None

        self._transfer_running = False
        self._transfer_stop = threading.Event()
        self._transfer_thread: Optional[threading.Thread] = None
        self._transfer_status = "Sẵn sàng"
        self._army_xfer_running = False
        self._army_xfer_stop = threading.Event()
        self._army_xfer_thread: Optional[threading.Thread] = None
        self._army_xfer_status = "Sẵn sàng"
        self._tribute_last_date: Optional[str] = None

        self._arm_running = False
        self._arm_stop = threading.Event()
        self._arm_status = "Sẵn sàng"

        self._ren_running = False
        self._ren_stop = threading.Event()
        self._ren_status = "Sẵn sàng"
        self._ren_progress = {"done": 0, "total": 0}

        self._nien_thu_ann: Optional[dict] = None
        self._last_roster_err: Optional[str] = None

        # Auxiliary periodic timer (boost/explore/daily)
        self._aux_stop = threading.Event()
        self._aux_wakeup = threading.Event()
        self._aux_thread: Optional[threading.Thread] = None

    def _emit(self, event_type: str, payload: dict) -> None:
        if self._event_cb and not self._destroyed:
            try:
                self._event_cb(self.account_key, event_type, payload)
            except Exception:
                pass

    def _notification_config(self) -> NotificationConfig:
        np = self.profile.notifications
        return NotificationConfig(
            desktop_enabled=np.desktop_enabled,
            sound_enabled=np.sound_enabled,
            web_enabled=np.web_enabled,
            telegram_enabled=np.telegram_enabled,
            telegram_alert_captcha=np.telegram_alert_captcha,
            telegram_alert_disconnect=np.telegram_alert_disconnect,
            telegram_bot_token=np.telegram_bot_token,
            telegram_chat_id=np.telegram_chat_id,
        )

    def _build_relogin_callback(self) -> Optional[Callable[[], bool]]:
        if not self.username or not self._password:
            return None

        def auto_relogin() -> bool:
            try:
                self.append_log("global", "🔑 Phiên hết hạn (198599). Đang tự động đăng nhập lại...")
                active_p = self.proxy_pool.get_active() if self.proxy_pool else None
                proxy_to_use = active_p.url if active_p else (self.proxy_raw or None)
                login(
                    self.session,
                    self.server_id,
                    self.username,
                    self._password,
                    proxy=proxy_to_use,
                    proxy_user=self.proxy_user or None,
                    proxy_pass=self.proxy_pass or None,
                )
                self.append_log("global", "✅ Tự động đăng nhập lại thành công!")
                reset_system_alert(self.account_key, "disconnect")
                return True
            except Exception as ex:
                self.append_log("global", f"❌ Tự động đăng nhập lại thất bại: {ex}")
                self.status = "error"
                self.status_text = f"Lỗi phiên: {ex}"
                self._emit("status_changed", self.get_status_snapshot())
                dispatch_system_alert(
                    "disconnect",
                    self.account_key,
                    "Mất Kết Nối Phiên Game",
                    f"Tự động đăng nhập lại thất bại: {ex}",
                    config=self._notification_config(),
                    on_log=lambda m: self.append_log("global", m),
                    on_web_event=lambda ev: self._emit("notification", ev),
                )
                return False

        return auto_relogin

    def append_log(self, channel: str, msg: str) -> None:
        ch = channel if channel in self.logs else "global"
        ts = time.strftime("%H:%M:%S")
        line = msg if msg.startswith("[") else f"[{ts}] {msg}"
        line = line.rstrip("\n")
        with self._lock:
            self.logs[ch].append(line)
            if ch != "global":
                self.logs["global"].append(f"[{ch}] {line}")
        self._emit("log", {"channel": ch, "line": line})

    def get_logs(self, channel: str = "global") -> list[str]:
        ch = channel if channel in self.logs else "global"
        with self._lock:
            return list(self.logs[ch])

    def clear_logs(self, channel: str = "global") -> None:
        ch = channel if channel in self.logs else "global"
        with self._lock:
            self.logs[ch].clear()
        self._emit("logs_cleared", {"channel": ch})

    def _handle_captcha(self, reason: str = "Server yêu cầu xác nhận Captcha (mã 110)") -> None:
        self.captcha_required = True
        self.captcha_reason = reason
        self.status = "captcha"
        self.status_text = "Cần giải Captcha"
        self._emit("captcha_alert", {"reason": reason})
        self._emit("status_changed", self.get_status_snapshot())
        dispatch_system_alert(
            "captcha",
            self.account_key,
            "Cần Giải Captcha",
            f"{reason}. Các tác vụ tự động đã tạm dừng chờ bạn xác nhận tiếp tục trên Web Dashboard.",
            config=self._notification_config(),
            on_log=lambda m: self.append_log("global", m),
            on_web_event=lambda ev: self._emit("notification", ev),
        )

    def _on_engine_log(self, task_id: str, msg: str) -> None:
        ch_map = {
            "building": "building",
            "research": "logistics",
            "thaophat": "thaophat",
            "binhman": "binhman",
            "goidan": "goidan",
            "nienthu": "nienthu",
        }
        self.append_log(ch_map.get(task_id, "global"), msg)

    def _on_engine_status(self, task_id: str, status: str) -> None:
        if status == TaskStatus.PAUSED_CAPTCHA:
            self._handle_captcha(f"Nhiệm vụ '{task_id}' tạm dừng do server yêu cầu Captcha.")
        elif task_id in ("thaophat", "binhman") and "Captcha" in status:
            self._handle_captcha(status)
        self._emit("status_changed", self.get_status_snapshot())

    def _set_boost_left(self, seconds: int) -> None:
        self._boost_left_seconds = max(0, int(seconds))
        self._boost_checked_at = time.monotonic()

    def _set_explore_left(self, seconds: int) -> None:
        self._explore_left_seconds = max(0, int(seconds))
        self._explore_checked_at = time.monotonic()

    @staticmethod
    def _remaining_countdown(base_seconds: int, checked_at: Optional[float]) -> int:
        if base_seconds <= 0:
            return 0
        if checked_at is None:
            return base_seconds
        elapsed = max(0, int(time.monotonic() - checked_at))
        return max(0, base_seconds - elapsed)

    def start_aux_loop(self) -> None:
        if self._aux_thread and self._aux_thread.is_alive():
            return
        self._aux_stop.clear()
        self._aux_wakeup.clear()

        def _loop():
            while not self._aux_stop.is_set() and not self._destroyed:
                try:
                    self._check_boost_once()
                    self._check_explore_once()
                    self._check_daily_reward_once()
                    self._check_tribute_once()
                except Exception:
                    pass
                wait_sec = 60.0
                aux = self.get_aux_status()
                if self.profile.building.auto_boost and aux["boost_left_seconds"] > 0:
                    wait_sec = min(wait_sec, max(1.0, float(aux["boost_left_seconds"])))
                if self.profile.logistics.auto_explore and aux["explore_left_seconds"] > 0:
                    wait_sec = min(wait_sec, max(1.0, float(aux["explore_left_seconds"])))
                self._aux_wakeup.wait(wait_sec)
                self._aux_wakeup.clear()

        self._aux_thread = threading.Thread(target=_loop, name=f"AuxLoop-{self.account_key}", daemon=True)
        self._aux_thread.start()

    def _check_boost_once(self) -> None:
        cid = self._default_city_id() or 0
        resp = self.gateway.call("Common.ashx", 77, {"cid": str(cid), "_": ""}) or {}
        rem = parse_boost_remaining_time(resp, cid)
        self._set_boost_left(rem)
        if rem <= 0 and self.profile.building.auto_boost:
            now_ts = time.time()
            if now_ts - self._last_boost_act_time > 60:
                self._last_boost_act_time = now_ts
                self.append_log("building", "⚡ DS kiến trúc đã hết hạn. Đang tự kích hoạt lại (3 vị trí)...")
                act = self.gateway.call("OPT.ashx", 69, {"type": "3", "param1": "0", "param2": "0", "paytype": "2", "_": ""}) or {}
                if act.get("ret", 0) == 0:
                    self.append_log("building", "✅ Kích hoạt thành công DS kiến trúc!")
                    resp2 = self.gateway.call("Common.ashx", 77, {"cid": str(cid), "_": ""}) or {}
                    self._set_boost_left(parse_boost_remaining_time(resp2, cid))
        self._emit("aux_updated", self.get_aux_status())

    def _check_explore_once(self) -> None:
        resp = self.gateway.call("Common.ashx", 140, {"lAction": "0", "lParam": "0", "_": ""})
        if not isinstance(resp, dict) or resp.get("ret", -1) != 0:
            return
        left = max(0, _safe_int(resp.get("left", 0), 0))
        self._set_explore_left(left)
        if left == 0 and self.profile.logistics.auto_explore:
            r_perf = self.gateway.call("Common.ashx", 140, {"lAction": "1", "lParam": "0", "_": ""})
            if isinstance(r_perf, dict) and r_perf.get("ret", -1) == 0:
                bonus = str(r_perf.get("bonus", "") or "")
                m = re.search(r"获得：([^×<\n]+)", bonus)
                item_name = m.group(1).strip() if m else (bonus.strip() or "Vật phẩm")
                self.append_log("building", f"🧭 Thám bảo tự động: Nhận được {item_name}")
                resp2 = self.gateway.call("Common.ashx", 140, {"lAction": "0", "lParam": "0", "_": ""})
                if isinstance(resp2, dict) and resp2.get("ret", -1) == 0:
                    self._set_explore_left(_safe_int(resp2.get("left", 0), 0))
        self._emit("aux_updated", self.get_aux_status())

    def _check_daily_reward_once(self) -> None:
        today = time.strftime("%Y-%m-%d")
        if self.profile.logistics.auto_daily_reward and self._last_daily_claim_date != today:
            self._last_daily_claim_date = today
            task = LogisticsTask(self.gateway, notify=lambda m: self.append_log("logistics", m))
            task.claim_daily_reward()

    # -------------------------------------------------------------------------
    # HỒ SƠ & TRẠNG THÁI TỔNG HỢP
    # -------------------------------------------------------------------------
    def save_profile(self) -> Path:
        with self._lock:
            saved = ProfileStore.save(self.profile, self.profile_path)
            return saved

    def update_profile(self, patch: dict) -> dict:
        with self._lock:
            current = self.profile.to_dict()
            for key, val in patch.items():
                if key in current and isinstance(current[key], dict) and isinstance(val, dict):
                    merged = dict(current[key])
                    merged.update(val)
                    current[key] = merged
                else:
                    current[key] = val
            self.profile = Profile.from_dict(current)
            if self.roster and self.roster.bases:
                self.profile.sync_with_bases(self.roster.bases)
            self.save_profile()
            data = self.profile.to_dict()
        self._emit("profile_updated", data)
        if "building" in patch or "logistics" in patch:
            self._aux_wakeup.set()
        return data

    def import_profile(self, data: dict) -> dict:
        with self._lock:
            self.profile = Profile.from_dict(data)
            if self.roster and self.roster.bases:
                self.profile.sync_with_bases(self.roster.bases)
            self.save_profile()
            out = self.profile.to_dict()
        self._emit("profile_updated", out)
        return out

    def get_proxy_status(self) -> dict:
        if self.proxy_pool:
            active = self.proxy_pool.get_active()
            return {
                "mode": "pool",
                "active": active.display_name if active else None,
                "alive": self.proxy_pool.alive_count(),
                "total": self.proxy_pool.total_count(),
            }
        return {
            "mode": "single" if self.proxy_raw else "direct",
            "active": self.proxy_raw or None,
            "alive": 1 if self.proxy_raw else 0,
            "total": 1 if self.proxy_raw else 0,
        }

    def get_aux_status(self) -> dict:
        if self._boost_left_seconds > 0 and self._boost_checked_at is None:
            self._boost_checked_at = time.monotonic()
        if self._explore_left_seconds > 0 and self._explore_checked_at is None:
            self._explore_checked_at = time.monotonic()
        return {
            "boost_left_seconds": self._remaining_countdown(self._boost_left_seconds, self._boost_checked_at),
            "explore_left_seconds": self._remaining_countdown(self._explore_left_seconds, self._explore_checked_at),
            "ditrai_running": self._ditrai_running,
            "ditrai_status": self._ditrai_status,
            "chest_running": self._chest_running,
            "chest_progress": dict(self._chest_progress),
            "morale_running": self._morale_running,
            "morale_status": self._morale_status,
            "morale_gen_status": dict(self._morale_gen_status),
            "craft_running": self._craft_running,
            "craft_statuses": dict(self._craft_statuses),
            "battle_running": self._battle_running,
            "battle_id": self._battle_id,
            "battle_state": self._battle_state,
            "tactician_running": self._tac_running,
            "tactician_status": self._tac_status,
            "equip_running": self._equip_running,
            "equip_status": self._equip_status,
            "transfer_running": self._transfer_running,
            "transfer_status": self._transfer_status,
            "army_transfer_running": self._army_xfer_running,
            "army_transfer_status": self._army_xfer_status,
            "armament_running": self._arm_running,
            "armament_status": self._arm_status,
            "rename_running": self._ren_running,
            "rename_status": self._ren_status,
            "rename_progress": dict(self._ren_progress),
            "nien_thu_announcement": self._nien_thu_ann,
        }

    def get_task_states(self) -> dict[str, dict]:
        return {
            "building": {"running": self.engine.is_running("building"), "status": self.engine.get_status("building")},
            "research": {"running": self.engine.is_running("research"), "status": self.engine.get_status("research")},
            "thaophat": {"running": self.engine.is_running("thaophat"), "status": self.engine.get_status("thaophat")},
            "binhman": {"running": self.engine.is_running("binhman"), "status": self.engine.get_status("binhman")},
            "goidan": {"running": self.engine.is_running("goidan"), "status": self.engine.get_status("goidan")},
            "nienthu": {"running": self.engine.is_running("nienthu"), "status": self.engine.get_status("nienthu")},
            "resource_monitor": {"running": self._res_monitor_running, "status": "Đang chạy..." if self._res_monitor_running else "Đã dừng"},
            "crafting": {"running": self._craft_running, "status": "Đang chạy..." if self._craft_running else "Đã dừng"},
            "transfer_loop": {"running": self._transfer_running, "status": self._transfer_status},
            "army_transfer": {"running": self._army_xfer_running, "status": self._army_xfer_status},
            "battle": {"running": self._battle_running, "status": "Đang chạy..." if self._battle_running else "Đã dừng"},
            "morale": {"running": self._morale_running, "status": self._morale_status},
            "ditrai": {"running": self._ditrai_running, "status": self._ditrai_status},
        }

    def get_running_task_names(self) -> list[str]:
        states = self.get_task_states()
        return [name for name in RESUMABLE_TASKS if states.get(name, {}).get("running")]

    def get_status_snapshot(self) -> dict:
        states = self.get_task_states()
        label_map = {
            "building": "🏗️ Xây",
            "research": "🔬 NC",
            "thaophat": "⚔️ TP",
            "binhman": "🏕️ BM",
            "goidan": "🧛 GM",
            "nienthu": "🧧 NT",
            "resource_monitor": "📦 TN",
            "crafting": "🛡️ Rèn",
            "transfer_loop": "🚚 CQG",
            "army_transfer": "🐎 CQG-QĐ",
        }
        active = [lbl for tid, lbl in label_map.items() if states.get(tid, {}).get("running")]
        eff_status = "captcha" if self.captcha_required else ("connected" if self.status != "error" else "error")
        eff_text = "Cần giải Captcha" if self.captcha_required else ("Đang chạy" if active else self.status_text)
        return {
            "account_key": self.account_key,
            "server_id": self.server_id,
            "username": self.username,
            "status": eff_status,
            "status_text": eff_text,
            "captcha_required": self.captcha_required,
            "captcha_reason": self.captcha_reason,
            "tasks_summary": " | ".join(active) if active else "Nghỉ",
            "tasks": states,
            "proxy": self.get_proxy_status(),
        }

    def get_full_snapshot(self) -> dict:
        return {
            "summary": self.get_status_snapshot(),
            "profile": self.profile.to_dict(),
            "profile_filename": self.profile_path.name,
            "roster": serialize_roster(self.roster),
            "tech_levels": dict(self._tech_levels),
            "tech_current": self._tech_current,
            "aux": self.get_aux_status(),
            "logs": {ch: self.get_logs(ch) for ch in LOG_CHANNELS},
        }

    def _default_city_id(self) -> Optional[int]:
        if self.roster.cities:
            return self.roster.cities[0].id
        if self.roster.bases:
            return self.roster.bases[0].id
        return None

    # -------------------------------------------------------------------------
    # ROSTER / BUILDING / TECH SYNC
    # -------------------------------------------------------------------------
    def _ensure_roster_loaded(self) -> Roster:
        if not self.roster or not self.roster.bases:
            self.reload_roster()
        return self.roster

    def _trigger_roster_resync_async(self, missing_city_id: int) -> None:
        with self._roster_resync_lock:
            if self._roster_resync_inflight:
                return
            self._roster_resync_inflight = True

        def _worker():
            try:
                self.append_log("building", f"🔄 Căn cứ {missing_city_id} không còn tồn tại; đang đồng bộ lại danh sách căn cứ...")
                self.reload_roster()
            except Exception as exc:
                logger.warning(f"Đồng bộ lại roster sau khi mất căn cứ {missing_city_id} thất bại: {exc}")
            finally:
                with self._roster_resync_lock:
                    self._roster_resync_inflight = False

        threading.Thread(target=_worker, daemon=True).start()

    def reload_roster(self) -> dict:
        roster = fetch_roster(self.gateway)
        self.roster = roster
        self._last_roster_err = None
        if roster.bases:
            with self._lock:
                sync_res = self.profile.sync_with_bases(roster.bases)
                if sync_res.changed:
                    self.save_profile()
                    profile_dict = self.profile.to_dict()
                else:
                    profile_dict = None
            if sync_res.changed:
                parts = []
                if sync_res.removed_ids:
                    parts.append(f"xóa {len(sync_res.removed_ids)} căn cứ không còn tồn tại ({sync_res.removed_ids})")
                if sync_res.added_ids:
                    parts.append(f"thêm {len(sync_res.added_ids)} căn cứ mới ({sync_res.added_ids})")
                if sync_res.renamed_ids:
                    parts.append(f"cập nhật tên {len(sync_res.renamed_ids)} căn cứ")
                if parts:
                    self.append_log("building", f"🔄 Đồng bộ danh sách căn cứ: {', '.join(parts)}.")
                if profile_dict is not None:
                    self._emit("profile_updated", profile_dict)
        data = serialize_roster(roster)
        self._emit("roster_updated", data)
        self._emit("status_changed", self.get_status_snapshot())
        return data

    def fetch_city_buildings(self, city_id: int) -> list[dict]:
        resp = self.gateway.call("City.ashx", 5, {"tid": str(city_id), "_": ""}) or {}
        buildings = resp.get("infos") or resp.get("buildings") or resp.get("build", [])
        plans = self._sync_city_buildings_from_raw(city_id, buildings, from_auto_cycle=False)
        return plans

    def _sync_city_buildings_from_raw(
        self, target_city_id: int, buildings: Any, from_auto_cycle: bool = False
    ) -> list[dict]:
        if not buildings:
            return []

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
            return []

        base = self.roster.base_by_id(target_city_id)
        base_name = base.name if base else str(target_city_id)

        from .profile import CityBuildingConfig

        city_cfg = self.profile.building.cities.get(str(target_city_id))
        cached_plans = list(city_cfg.plans) if city_cfg else []

        seen_pids = set()
        new_plans: list[dict] = []
        level_changes = []

        if not cached_plans:
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
                    continue
                seen_pids.add(pid)
                entry = dict(p)
                r_info = real_map[pid]
                old_lvl = int(p.get("cur_lvl", 0))
                new_lvl = int(r_info.get("level", 0))
                if new_lvl != old_lvl:
                    level_changes.append((pid, entry.get("name") or f"Ô {pid}", old_lvl, new_lvl))
                entry["cur_lvl"] = new_lvl
                if r_info.get("gid"):
                    entry["gid"] = r_info["gid"]
                    entry["name"] = BUILDING_NAMES.get(r_info["gid"], r_info.get("name") or entry.get("name", ""))
                new_plans.append(entry)

            for pid, r_info in real_map.items():
                if pid not in seen_pids:
                    gid = int(r_info.get("gid", 1))
                    name = BUILDING_NAMES.get(gid, r_info.get("name") or f"Công trình {gid}")
                    lvl = int(r_info.get("level", 0))
                    same_gid = [p for p in cached_plans if int(p.get("gid", 0)) == gid]
                    if same_gid and all(p.get("enabled", True) for p in same_gid):
                        group_tgt = int(same_gid[0].get("target_level", max(lvl + 1, 20)))
                        new_plans.append({
                            "pid": pid,
                            "gid": gid,
                            "name": name,
                            "cur_lvl": lvl,
                            "target_level": group_tgt,
                            "enabled": True,
                        })
                    else:
                        new_plans.append({
                            "pid": pid,
                            "gid": gid,
                            "name": name,
                            "cur_lvl": lvl,
                            "target_level": lvl,
                            "enabled": False,
                        })

        with self._lock:
            if str(target_city_id) not in self.profile.building.cities:
                self.profile.building.cities[str(target_city_id)] = CityBuildingConfig(
                    name=base_name, enabled=True, resource=False, plans=new_plans
                )
            else:
                self.profile.building.cities[str(target_city_id)].name = base_name
                self.profile.building.cities[str(target_city_id)].plans = new_plans
            if new_plans != cached_plans:
                self.save_profile()
                self._emit("profile_updated", self.profile.to_dict())

        if level_changes:
            ch_str = ", ".join(f"{nm} (cấp {ol}➔{nl})" for _, nm, ol, nl in level_changes[:3])
            if len(level_changes) > 3:
                ch_str += f", +{len(level_changes)-3} công trình"
            self.append_log("building", f"🔄 [{base_name}] Đồng bộ thực tế: {ch_str}")
        elif not from_auto_cycle:
            self.append_log("building", f"🔄 Đã tải {len(new_plans)} công trình thực tế của {base_name}.")

        return new_plans

    def fetch_city_techs(self, city_id: Optional[int] = None) -> dict:
        cid = city_id or self.profile.research.city_id or self._default_city_id()
        if not cid:
            raise ValueError("Không tìm thấy thành trì để tải kỹ thuật.")

        def _find_univ(target_cid: int):
            self.gateway.call("City.ashx", 50, {"tid": str(target_cid), "_": ""})
            resp_bld = self.gateway.call("City.ashx", 5, {"tid": str(target_cid), "_": ""}) or {}
            b_list = resp_bld.get("infos") or resp_bld.get("buildings") or []
            for b in b_list:
                if isinstance(b, (list, tuple)) and len(b) >= 2 and int(b[1]) in (6, 59):
                    return int(b[0]), int(b[1])
                if isinstance(b, dict) and int(b.get("gid", 0)) in (6, 59):
                    return int(b.get("pid", 0)), int(b.get("gid", 0))
            return None, None

        univ_pid, univ_gid = _find_univ(cid)
        if univ_pid is None:
            for c in self.roster.cities:
                if c.id == cid:
                    continue
                p, g = _find_univ(c.id)
                if p is not None:
                    cid, univ_pid, univ_gid = c.id, p, g
                    break

        if univ_pid is None:
            raise ValueError("Không tìm thấy Viện Đại Học / Thái Học Điện ở bất kỳ thành nào!")

        resp_tech = self.gateway.call(
            "Build.ashx", 2, {"pid": str(univ_pid), "gid": str(univ_gid), "tab": "1", "tid": str(cid), "_": ""}
        ) or {}
        if resp_tech.get("ret", 0) != 0:
            raise RuntimeError(f"Server trả mã lỗi {resp_tech.get('ret')} khi đọc kỹ thuật.")

        levels: dict[int, int] = {}
        for item in resp_tech.get("list", []):
            if isinstance(item, dict):
                levels[int(item.get("id", 0))] = int(item.get("level", 0))
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                try:
                    levels[int(item[0])] = int(item[2])
                except (ValueError, TypeError):
                    pass

        self._tech_levels = levels
        curr = resp_tech.get("current")
        self._tech_current = (
            {"name": curr[1], "cur": curr[2], "next": curr[3], "left": curr[4]}
            if isinstance(curr, (list, tuple)) and len(curr) >= 5
            else None
        )
        # Cập nhật current_level vào profile.research.techs nếu có
        if not self.profile.research.techs:
            self.profile.research.techs = [
                {
                    "id": tid,
                    "target_level": 20,
                    "name": tname,
                    "enabled": False,
                    "current_level": levels.get(tid, 0),
                }
                for tid, tname in sorted(TECH_NAMES.items())
            ]
        else:
            for t in self.profile.research.techs:
                tid = int(t.get("id", 0))
                if tid in levels:
                    t["current_level"] = levels[tid]
        self.profile.research.city_id = cid
        self.save_profile()
        self._emit("profile_updated", self.profile.to_dict())
        self._emit("techs_updated", {"city_id": cid, "levels": levels, "current": self._tech_current})
        self.append_log("logistics", f"✅ Đã tải cấp độ {len(levels)} kỹ thuật cho thành {cid}.")
        return {"city_id": cid, "levels": levels, "current": self._tech_current}

    # -------------------------------------------------------------------------
    # XÂY DỰNG / NGHIÊN CỨU / TÀI NGUYÊN / PHỤ TRỢ
    # -------------------------------------------------------------------------
    def start_building(self) -> None:
        self._ensure_roster_loaded()
        b_prof = self.profile.building
        valid_base_ids = {b.id for b in self.roster.bases} if self.roster and self.roster.bases else None
        selected_cids = [
            int(cid_str) for cid_str, cdata in b_prof.cities.items()
            if cid_str.lstrip("-").isdigit()
            and cdata.enabled
            and (valid_base_ids is None or int(cid_str) in valid_base_ids)
        ]
        if not selected_cids and self._default_city_id():
            selected_cids = [self._default_city_id()]  # type: ignore[list-item]
        if not selected_cids:
            raise ValueError("Chưa có căn cứ nào hợp lệ được chọn để xây dựng.")

        box_options_ids = [1, 6, 11, 16, 24, 35]
        box_idx = max(0, min(len(box_options_ids) - 1, int(b_prof.box_type_idx)))
        box_id = box_options_ids[box_idx]
        max_boxes = max(1, _safe_int(b_prof.box_max, 5))
        spd_hours = max(0.0, _safe_float(b_prof.speedup_hours, 1.0))

        tasks: list[BuildingTask] = []
        for cid in selected_cids:
            cdata = b_prof.cities.get(str(cid))
            plan_dicts = cdata.plans if cdata else b_prof.plans
            plans = [
                BuildingPlan(
                    pid=int(p["pid"]),
                    gid=int(p["gid"]),
                    target_level=int(p["target_level"]),
                    name=p.get("name", ""),
                    enabled=bool(p.get("enabled", True)),
                )
                for p in (plan_dicts or [])
                if p.get("enabled", True)
            ]
            if not plans:
                continue
            base = self.roster.base_by_id(cid)
            bname = base.name if base else f"Căn cứ {cid}"
            city_open_box = bool(b_prof.auto_open_box and cdata and cdata.resource)
            tasks.append(
                BuildingTask(
                    gateway=self.gateway,
                    city_id=cid,
                    plans=plans,
                    max_slots=max(1, min(3, int(b_prof.slots or 3))),
                    auto_speedup=b_prof.auto_speedup,
                    speedup_hours=spd_hours,
                    paytype=b_prof.speedup_paytype,
                    auto_boost=b_prof.auto_boost,
                    auto_comfort=b_prof.auto_comfort,
                    auto_open_box=city_open_box,
                    box_id=box_id,
                    max_boxes_per_round=max_boxes,
                    auto_fallback_box=b_prof.auto_fallback_box,
                    even_upgrade=b_prof.even_upgrade,
                    notify=lambda m, cname=bname: self.append_log("building", f"[{cname}] {m}"),
                    city_name=bname,
                    on_sync_data=lambda target_cid, rdata: self._sync_city_buildings_from_raw(
                        target_cid, rdata, from_auto_cycle=True
                    ),
                    on_city_missing=self._trigger_roster_resync_async,
                )
            )
        if not tasks:
            raise ValueError("Chưa có công trình nào được tích chọn trong các căn cứ đã bật.")

        interval = max(3.0, _safe_float(b_prof.interval, 20.0))
        self.engine.start("building", tasks, interval=interval, jitter=2.0)
        self._emit("status_changed", self.get_status_snapshot())

    def stop_building(self) -> None:
        self.engine.stop("building")
        self._emit("status_changed", self.get_status_snapshot())

    def start_research(self) -> None:
        r_prof = self.profile.research
        cid = r_prof.city_id or self._default_city_id()
        if not cid:
            raise ValueError("Vui lòng chọn Thành Nghiên Cứu.")
        plans = [
            TechPlan(
                tech_id=int(t["id"]),
                target_level=int(t.get("target_level", 20)),
                name=t.get("name", ""),
                enabled=True,
            )
            for t in r_prof.techs
            if t.get("enabled", False)
        ]
        if not plans:
            raise ValueError("Vui lòng tích chọn ít nhất 1 Kỹ Thuật Đại Học.")

        def _on_sync(target_cid: int, levels_map: dict, _t_stat: Any):
            if levels_map:
                self._tech_levels.update({int(k): int(v) for k, v in levels_map.items()})
                for t in self.profile.research.techs:
                    tid = int(t.get("id", 0))
                    if tid in levels_map:
                        t["current_level"] = int(levels_map[tid])
                self._emit("techs_updated", {"city_id": target_cid, "levels": self._tech_levels, "current": self._tech_current})

        task = ResearchTask(
            gateway=self.gateway,
            city_id=cid,
            plans=plans,
            auto_art_of_war=r_prof.art_speedup,
            even_research=r_prof.even_research,
            notify=lambda m: self.append_log("logistics", m),
            on_sync_data=_on_sync,
        )
        interval = max(3.0, _safe_float(r_prof.interval, 30.0))
        self.engine.start("research", task, interval=interval, jitter=2.0)
        self._emit("status_changed", self.get_status_snapshot())

    def stop_research(self) -> None:
        self.engine.stop("research")
        self._emit("status_changed", self.get_status_snapshot())

    def start_resource_monitor(self) -> None:
        if self._res_monitor_running:
            return
        self._ensure_roster_loaded()
        valid_base_ids = {b.id for b in self.roster.bases} if self.roster and self.roster.bases else None
        res_cids = [
            cid for cid in self.profile.resource.resource_cities
            if valid_base_ids is None or cid in valid_base_ids
        ]
        if not res_cids:
            res_cids = [
                int(cid_str)
                for cid_str, cdata in self.profile.building.cities.items()
                if cid_str.lstrip("-").isdigit()
                and cdata.resource
                and (valid_base_ids is None or int(cid_str) in valid_base_ids)
            ]
        if not res_cids and self._default_city_id():
            res_cids = [self._default_city_id()]  # type: ignore[list-item]
        if not res_cids:
            raise ValueError("Vui lòng chọn ít nhất 1 thành hợp lệ để giám sát tài nguyên.")

        stop_ev = threading.Event()
        self._res_monitor_stop = stop_ev
        self._res_monitor_running = True
        self.append_log("building", f"▶️ Bắt đầu giám sát ngưỡng tài nguyên cho {len(res_cids)} thành...")
        box_ids = [1, 6, 11, 16, 24, 35]

        def _loop():
            while self._res_monitor_running and not stop_ev.is_set():
                r_cfg = self.profile.resource
                cur_valid_ids = {b.id for b in self.roster.bases} if self.roster and self.roster.bases else None
                raw_cids = list(r_cfg.resource_cities) or res_cids
                cids = [cid for cid in raw_cids if cur_valid_ids is None or cid in cur_valid_ids]
                for cid in cids:
                    if not self._res_monitor_running or stop_ev.is_set():
                        break
                    try:
                        base = self.roster.base_by_id(cid)
                        cname = base.name if base else f"Thành {cid}"
                        snap = fetch_city_resources_snapshot(self.gateway, cid, include_gold=True)
                        if snap.get("ret", 0) == 4:
                            self._trigger_roster_resync_async(cid)
                            continue

                        money = snap.get("money")
                        gold_th = _safe_int(r_cfg.gold_threshold, 100000000)
                        need_gold = money is not None and money < gold_th

                        max_storage = snap.get("max_storage") or 1000000
                        w_pct = max(0.0, _safe_float(r_cfg.wood_pct, 70.0) / 100.0)
                        i_pct = max(0.0, _safe_float(r_cfg.iron_pct, 70.0) / 100.0)
                        s_pct = max(0.0, _safe_float(r_cfg.stone_pct, 70.0) / 100.0)
                        f_pct = max(0.0, _safe_float(r_cfg.food_pct, 70.0) / 100.0)
                        need_tn = bool(snap.get("has_resources")) and any(
                            snap.get(k) is not None and snap.get(k) < max_storage * pct
                            for k, pct in (("wood", w_pct), ("iron", i_pct), ("stone", s_pct), ("food", f_pct))
                        )

                        if need_gold or need_tn:
                            self.gateway.call("City.ashx", 50, {"tid": str(cid), "_": ""})

                        if need_gold:
                            g_idx = max(0, min(len(box_ids) - 1, int(r_cfg.gold_box_idx)))
                            g_box_id = box_ids[g_idx]
                            r_box = self.gateway.call("Common.ashx", 48, {"lBoxID": str(g_box_id), "_": ""}) or {}
                            if r_box.get("ret", 0) == 0:
                                self.append_log("building", f"💰 [{cname}] Vàng={money:,} < {gold_th:,}: Đã mở rương vàng #{g_box_id}.")
                            else:
                                self.append_log("building", f"⚠️ [{cname}] Mở rương vàng #{g_box_id} lỗi (ret={r_box.get('ret')}).")

                        if need_tn:
                            tn_idx = max(0, min(len(box_ids) - 1, int(r_cfg.tn_box_idx)))
                            tn_box_id = box_ids[tn_idx]
                            r_box = self.gateway.call("Common.ashx", 48, {"lBoxID": str(tn_box_id), "_": ""}) or {}
                            if r_box.get("ret", 0) == 0:
                                self.append_log("building", f"📦 [{cname}] Khoáng sản dưới ngưỡng: Đã mở rương TN #{tn_box_id}.")
                            else:
                                self.append_log("building", f"⚠️ [{cname}] Mở rương TN #{tn_box_id} lỗi (ret={r_box.get('ret')}).")
                    except CaptchaRequired:
                        self._handle_captcha("Giám sát tài nguyên gặp Captcha (mã 110).")
                        if self._res_monitor_thread is threading.current_thread():
                            self._res_monitor_running = False
                        break
                    except Exception as exc:
                        self.append_log("building", f"❌ Lỗi giám sát TN thành {cid}: {exc}")
                if stop_ev.wait(30.0):
                    break
            if self._res_monitor_thread is threading.current_thread():
                self._res_monitor_running = False
                self._emit("status_changed", self.get_status_snapshot())

        self._res_monitor_thread = threading.Thread(target=_loop, daemon=True)
        self._res_monitor_thread.start()
        self._emit("status_changed", self.get_status_snapshot())

    def stop_resource_monitor(self) -> None:
        self._res_monitor_running = False
        self._res_monitor_stop.set()
        self.append_log("building", "⏹️ Đã dừng giám sát tài nguyên.")
        self._emit("status_changed", self.get_status_snapshot())

    def start_batch_open_chest(self, chest_name: str, times: int, city_id: Optional[int] = None) -> None:
        if self._chest_running:
            raise RuntimeError("Tiến trình Mở Rương Hàng Loạt đang chạy.")
        if chest_name not in CHEST_MAPPING:
            raise ValueError("Loại rương không hợp lệ.")
        if times <= 0:
            raise ValueError("Số lượt mở rương phải > 0.")

        needs_switch = chest_needs_city_switch(chest_name)
        city_name = ""
        if needs_switch:
            if not city_id or city_id <= 0:
                raise ValueError("Loại rương này yêu cầu chọn Thành hợp lệ (ID dương).")
            b = self.roster.base_by_id(city_id)
            city_name = b.name if b else str(city_id)

        self._chest_running = True
        self._chest_stop.clear()
        self._chest_progress = {"done": 0, "total": times, "pct": 0.0, "status": "Đang mở..."}
        self._emit("aux_updated", self.get_aux_status())

        def _worker():
            try:
                summary = run_batch_open_chest(
                    gateway=self.gateway,
                    chest_name=chest_name,
                    times=times,
                    city_id=city_id,
                    city_name=city_name,
                    max_workers=5,
                    stop_event=self._chest_stop,
                    on_log=lambda m: self.append_log("building", m),
                    on_progress=self._on_chest_progress,
                )
                if summary.get("aborted_reason") == "captcha":
                    self._handle_captcha("Mở rương hàng loạt gặp Captcha (mã 110).")
                self._chest_progress = {
                    "done": summary.get("completed", times),
                    "total": times,
                    "pct": (summary.get("completed", 0) / times * 100.0) if times else 100.0,
                    "status": f"Hoàn tất {summary.get('success_count', 0)}/{times}",
                }
                self.append_log(
                    "building",
                    f"🏁 Kết thúc mở [{chest_name}]: Thành công {summary.get('success_count', 0)}/{times}, Thất bại {summary.get('failed_count', 0)}.",
                )
            except Exception as exc:
                self._chest_progress["status"] = f"Lỗi: {exc}"
                self.append_log("building", f"❌ Lỗi mở rương hàng loạt: {exc}")
            finally:
                self._chest_running = False
                self._emit("aux_updated", self.get_aux_status())

        self._chest_thread = threading.Thread(target=_worker, daemon=True)
        self._chest_thread.start()

    def _on_chest_progress(self, done: int, total: int, pct: float) -> None:
        self._chest_progress = {"done": done, "total": total, "pct": round(pct, 1), "status": f"Đang mở ({done}/{total})"}
        self._emit("aux_updated", self.get_aux_status())

    def stop_batch_open_chest(self) -> None:
        self._chest_stop.set()
        self.append_log("building", "⏹️ Đang dừng tiến trình mở rương hàng loạt...")

    def run_explore(self, use_whip: bool = False, use_coin: bool = False, turns: int = 1) -> None:
        def _worker():
            try:
                if use_whip or use_coin:
                    clear_type = 1 if use_whip else 2
                    mode_name = "Roi" if clear_type == 1 else "Coin"
                    self.append_log("building", f"🧭 Bắt đầu Thám bảo {turns} lượt (Dùng {mode_name})...")
                    succ = 0
                    for idx in range(1, max(1, turns) + 1):
                        r0 = self.gateway.call("Common.ashx", 140, {"lAction": "0", "lParam": "0", "_": ""}) or {}
                        left = _safe_int(r0.get("left", 0), 0)
                        if left > 0:
                            r2 = self.gateway.call("Common.ashx", 140, {"lAction": "2", "lParam": str(clear_type), "_": ""}) or {}
                            if r2.get("ret", -1) != 0:
                                self.append_log("building", f"⚠️ Lượt {idx}/{turns}: Không thể xóa thời gian chờ bằng {mode_name}.")
                                break
                        r1 = self.gateway.call("Common.ashx", 140, {"lAction": "1", "lParam": "0", "_": ""}) or {}
                        if r1.get("ret", -1) == 0:
                            succ += 1
                            bonus = str(r1.get("bonus", "") or "")
                            m = re.search(r"获得：([^×<\n]+)", bonus)
                            item = m.group(1).strip() if m else (bonus.strip() or "Vật phẩm")
                            self.append_log("building", f"🧭 Thám bảo lượt {idx}/{turns}: Nhận được {item}")
                        else:
                            self.append_log("building", f"❌ Thám bảo lượt {idx}/{turns} thất bại.")
                            break
                    self.append_log("building", f"✅ Hoàn tất Thám bảo ({succ}/{turns} lượt).")
                self._check_explore_once()
            except Exception as exc:
                self.append_log("building", f"❌ Lỗi Thám bảo: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def fetch_city_weapons(self, city_id: int) -> list[dict]:
        """Tải danh sách Quân giới hiện có trong kho Thành từ Common.ashx?id=16."""
        if int(city_id) <= 0:
            return []
        task = LogisticsTask(self.gateway, notify=lambda m: self.append_log("logistics", m))
        return task.get_city_weapon_stocks(int(city_id))

    def transfer_army(self, from_city_id: int, to_city_id: int, army_id: int, amount: int) -> None:
        if from_city_id <= 0 or to_city_id <= 0:
            raise ValueError("Chuyển quân giới bằng Chợ chỉ hỗ trợ giữa các Thành (không hỗ trợ Doanh trại).")
        if from_city_id == to_city_id:
            raise ValueError("Thành gửi và Thành nhận phải khác nhau.")
        if army_id <= 0 or amount <= 0:
            raise ValueError("Mã Quân giới và số lượng phải lớn hơn 0.")

        task = LogisticsTask(self.gateway, notify=lambda m: self.append_log("logistics", m))
        order = ArmyTransferOrder(from_city_id=from_city_id, to_city_id=to_city_id, army_id=army_id, amount=amount)

        def _worker():
            try:
                task.transfer_army(order)
            except CaptchaRequired:
                self._handle_captcha("Chuyển quân giới tạm dừng do Captcha (mã 110).")
            except Exception as exc:
                self.append_log("logistics", f"❌ Lỗi chuyển quân giới: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def comfort_city(self, city_id: int) -> None:
        task = LogisticsTask(self.gateway, notify=lambda m: self.append_log("logistics", m))
        threading.Thread(target=lambda: task.comfort_city_if_needed(city_id), daemon=True).start()

    def claim_daily_reward(self) -> None:
        task = LogisticsTask(self.gateway, notify=lambda m: self.append_log("logistics", m))
        threading.Thread(target=lambda: task.claim_daily_reward(), daemon=True).start()

    def tribute_city(self, city_id: int, building_gid: int = 1) -> None:
        cid = int(city_id)
        gid = int(building_gid)
        if cid <= 0:
            raise ValueError("Cống quận chỉ áp dụng cho Thành, không áp dụng cho Doanh trại.")
        if gid not in (1, 2):
            raise ValueError("Công trình Cống quận chỉ hỗ trợ Quan Phủ (1) hoặc Tường Thành (2).")

        def _worker():
            try:
                resp = self.gateway.call(
                    "OPT.ashx", 146, {"tid": str(cid), "gid": str(gid), "_": ""}
                ) or {}
                ret = resp.get("ret", -1)
                if ret == 110:
                    self._handle_captcha("Cống quận tạm dừng do Captcha.")
                elif ret == 0:
                    self.append_log("building", f"✅ Đã gửi lệnh Cống quận cho thành {cid}.")
                else:
                    self.append_log("building", f"⚠️ Cống quận thành {cid} trả về mã lỗi {ret}.")
            except CaptchaRequired:
                self._handle_captcha("Cống quận tạm dừng do Captcha.")
            except Exception as exc:
                self.append_log("building", f"❌ Lỗi Cống quận: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _check_tribute_once(self) -> None:
        """Cống quận tự động tối đa 1 lần/ngày cho các Thành đang bật Xây (bỏ qua Doanh trại)."""
        lg = self.profile.logistics
        today = time.strftime("%Y-%m-%d")
        if not lg.tribute_enabled or self._tribute_last_date == today:
            return
        self._ensure_roster_loaded()
        if not self.roster or not self.roster.cities:
            return
        valid = {c.id for c in self.roster.cities}
        city_ids = [
            int(cid) for cid, cfg in self.profile.building.cities.items()
            if cfg.enabled and int(cid) > 0 and int(cid) in valid
        ]
        if not city_ids:
            return
        for cid in city_ids:
            self.tribute_city(cid, lg.tribute_building_gid)
        self._tribute_last_date = today

    def transfer_loop_orders(self) -> list[ArmyTransferOrder]:
        return [
            ArmyTransferOrder(
                from_city_id=int(o["from_city_id"]),
                to_city_id=int(o["to_city_id"]),
                army_id=int(o["army_id"]),
                amount=int(o["amount"]),
            )
            for o in self.profile.logistics.transfer_orders
        ]

    def start_transfer_loop(self) -> None:
        """Chạy lặp bảng Chuyển quân giới bằng Chợ; dừng ngay khi Thành nguồn thiếu hàng (ADR-0042)."""
        if self._transfer_running:
            return
        orders = self.transfer_loop_orders()
        if not orders:
            raise ValueError("Chưa có lệnh Chuyển quân giới nào trong bảng.")
        for order in orders:
            if order.from_city_id <= 0 or order.to_city_id <= 0 or order.from_city_id == order.to_city_id:
                raise ValueError("Chuyển quân giới bằng Chợ yêu cầu 2 Thành khác nhau (không hỗ trợ Doanh trại).")
        interval = max(3.0, _safe_float(self.profile.logistics.transfer_interval, 60.0))
        self._transfer_running = True
        self._transfer_stop.clear()
        self._transfer_status = f"Đang chạy lặp mỗi {int(interval)}s"

        def _loop():
            task = LogisticsTask(
                self.gateway,
                auto_comfort=False,
                auto_daily_reward=False,
                notify=lambda m: self.append_log("logistics", m),
            )
            stopped_reason: Optional[str] = None
            try:
                while not self._transfer_stop.is_set():
                    cur_orders = self.transfer_loop_orders()
                    if not cur_orders:
                        self.append_log("logistics", "⏹️ Không còn lệnh Chuyển quân giới — dừng vòng lặp.")
                        stopped_reason = "Đã dừng: không có lệnh"
                        return
                    for order in cur_orders:
                        if self._transfer_stop.is_set():
                            break
                        garrison = task.get_garrison_troops(order.from_city_id)
                        available = garrison.get(order.army_id, 0)
                        if available < order.amount:
                            wname = get_transfer_weapon_name(order.army_id)
                            self.append_log(
                                "logistics",
                                f"⏹️ Thành {order.from_city_id} thiếu {wname} (ID {order.army_id}) "
                                f"({available:,}/{order.amount:,}) — dừng vòng lặp Chuyển quân giới.",
                            )
                            stopped_reason = "Đã dừng: thiếu quân giới"
                            return
                        if not task.transfer_army(order):
                            stopped_reason = "Đã dừng: chuyển thất bại"
                            return
                    if self._transfer_stop.wait(interval):
                        break
            except CaptchaRequired:
                self._handle_captcha("Chuyển quân giới tạm dừng do Captcha.")
                stopped_reason = "Tạm dừng (Captcha)"
            except Exception as exc:
                self.append_log("logistics", f"❌ Lỗi vòng lặp Chuyển quân giới: {exc}")
                stopped_reason = f"Lỗi: {exc}"
            finally:
                self._transfer_status = stopped_reason or "Đã dừng"
                self._transfer_running = False
                self._emit("aux_updated", self.get_aux_status())
                self._emit("status_changed", self.get_status_snapshot())

        self._transfer_thread = threading.Thread(target=_loop, daemon=True)
        self._transfer_thread.start()
        self._emit("aux_updated", self.get_aux_status())
        self._emit("status_changed", self.get_status_snapshot())

    def stop_transfer_loop(self) -> None:
        self._transfer_running = False
        self._transfer_stop.set()
        self._army_xfer_running = False
        self._army_xfer_stop.set()
        self._transfer_status = "Đã dừng"
        self._emit("aux_updated", self.get_aux_status())
        self._emit("status_changed", self.get_status_snapshot())

    def start_army_transfer(
        self,
        from_city_id: Optional[int] = None,
        to_city_id: Optional[int] = None,
        weapon_id: Optional[int] = None,
        general_ids: Optional[list[int]] = None,
        *,
        loop: Optional[bool] = None,
    ) -> None:
        """Chạy Chuyển quân giới bằng Quân đội (điều phái Võ tướng qua lại giữa 2 Thành)."""
        if self._army_xfer_running:
            raise RuntimeError("Tiến trình Chuyển quân giới bằng Quân đội đang chạy.")
        lg = self.profile.logistics
        src_cid = int(lg.army_transfer_from_city_id if from_city_id is None else from_city_id)
        dst_cid = int(lg.army_transfer_to_city_id if to_city_id is None else to_city_id)
        wid = int(lg.army_transfer_weapon_id if weapon_id is None else weapon_id)
        raw_gids = lg.army_transfer_general_ids if general_ids is None else general_ids
        run_loop = bool(lg.army_transfer_loop if loop is None else loop)

        if src_cid <= 0 or dst_cid <= 0:
            raise ValueError("Chuyển quân giới bằng Quân đội chỉ hỗ trợ giữa các Thành.")
        if src_cid == dst_cid:
            raise ValueError("Thành chứa Quân giới và Thành nhận phải khác nhau.")
        clean_gids = [int(g) for g in raw_gids if int(g) > 0]
        if not clean_gids:
            raise ValueError("Vui lòng chọn ít nhất 1 Võ tướng.")
        if wid <= 0:
            raise ValueError("Vui lòng chọn Quân giới hợp lệ.")

        self._ensure_roster_loaded()
        self._army_xfer_running = True
        self._army_xfer_stop.clear()
        wname = get_transfer_weapon_name(wid)
        self._army_xfer_status = f"Đang chạy ({wname}, {len(clean_gids)} tướng)"

        def _set_status(msg: str) -> None:
            self._army_xfer_status = msg
            self._emit("aux_updated", self.get_aux_status())

        def _worker():
            task = ArmyWeaponTransferTask(self.gateway, notify=lambda m: self.append_log("logistics", m))
            final_status = "Đã dừng"
            try:
                res = task.run(
                    from_city_id=src_cid,
                    to_city_id=dst_cid,
                    weapon_id=wid,
                    general_ids=clean_gids,
                    roster=self.roster,
                    loop=run_loop,
                    stop_event=self._army_xfer_stop,
                    status_cb=_set_status,
                )
                if res.startswith("stopped_out_of_stock"):
                    final_status = "Đã dừng: hết quân giới nguồn"
                elif res.startswith("stopped_no_carriers"):
                    final_status = "Đã dừng: không có tướng hợp lệ"
                elif res.startswith("stopped_dispatch_failed"):
                    final_status = "Đã dừng: lỗi điều phái tướng"
                elif res.startswith("completed"):
                    final_status = "Hoàn tất"
            except CaptchaRequired:
                self._handle_captcha("Chuyển quân giới bằng Quân đội tạm dừng do Captcha.")
                final_status = "Tạm dừng (Captcha)"
            except Exception as exc:
                self.append_log("logistics", f"❌ Lỗi Chuyển quân giới bằng Quân đội: {exc}")
                final_status = f"Lỗi: {exc}"
            finally:
                self._army_xfer_running = False
                self._army_xfer_status = final_status
                self._emit("aux_updated", self.get_aux_status())
                self._emit("status_changed", self.get_status_snapshot())

        self._army_xfer_thread = threading.Thread(target=_worker, daemon=True)
        self._army_xfer_thread.start()
        self._emit("aux_updated", self.get_aux_status())
        self._emit("status_changed", self.get_status_snapshot())

    def stop_army_transfer(self) -> None:
        self._army_xfer_running = False
        self._army_xfer_stop.set()
        self._army_xfer_status = "Đã dừng"
        self._emit("aux_updated", self.get_aux_status())
        self._emit("status_changed", self.get_status_snapshot())

    # -------------------------------------------------------------------------
    # DI TRẠI ĐỘC LẬP
    # -------------------------------------------------------------------------
    def start_ditrai(self, camp_id: int, dest_x: int, dest_y: int) -> None:
        if self._ditrai_running:
            raise RuntimeError("Tiến trình Di Trại đang chạy.")
        camp = self.roster.base_by_id(camp_id)
        if not camp:
            raise ValueError("Không tìm thấy Doanh trại đã chọn.")

        self._ditrai_running = True
        self._ditrai_stop.clear()
        self._ditrai_status = f"🚀 Đang di chuyển tới ({dest_x}, {dest_y})..."
        self.append_log("building", f"🚀 Bắt đầu Di Trại {camp.name} từ ({camp.pos_x}, {camp.pos_y}) tới ({dest_x}, {dest_y})")
        self._emit("aux_updated", self.get_aux_status())

        def on_step(new_x: int, new_y: int, frozen: int):
            self.roster.update_camp_position(camp.id, new_x, new_y)
            self._emit("roster_updated", serialize_roster(self.roster))
            for rem in range(frozen, 0, -1):
                if self._ditrai_stop.is_set():
                    break
                self._ditrai_status = f"⏳ Đóng băng: {rem}s..."
                self._emit("aux_updated", self.get_aux_status())
                time.sleep(1)
            if not self._ditrai_stop.is_set():
                self._ditrai_status = "🏃 Đang di chuyển bước tiếp theo..."
                self._emit("aux_updated", self.get_aux_status())

        def _worker():
            ctx = TaskContext(self.gateway, None, TargetLocks(), notify=lambda m: self.append_log("building", m))
            task = DiTrai(
                ctx=ctx,
                camp_id=camp.id,
                origin=(camp.pos_x, camp.pos_y),
                destination=(dest_x, dest_y),
                max_step=2,
                sleep_fn=time.sleep,
                on_step=on_step,
                stop_event=self._ditrai_stop,
            )
            try:
                res = task.advance_to_destination()
                if res == "arrived":
                    self._ditrai_status = f"🎯 Đã đến đích ({dest_x}, {dest_y})!"
                    self.append_log("building", f"🎯 Di Trại {camp.name} đã đến đích ({dest_x}, {dest_y})!")
                elif res == "stopped":
                    self._ditrai_status = f"⏹️ Đã dừng tại ({task.origin[0]}, {task.origin[1]})"
                else:
                    self._ditrai_status = f"❌ Dừng: {res}"
            except CaptchaRequired:
                self._ditrai_status = "⚠️ Cần giải Captcha"
                self._handle_captcha("Di Trại gặp Captcha (mã 110).")
            except Exception as exc:
                self._ditrai_status = f"❌ Lỗi: {exc}"
                self.append_log("building", f"❌ Lỗi Di Trại: {exc}")
            finally:
                self._ditrai_running = False
                self._emit("aux_updated", self.get_aux_status())
                self._emit("status_changed", self.get_status_snapshot())

        self._ditrai_thread = threading.Thread(target=_worker, daemon=True)
        self._ditrai_thread.start()

    def stop_ditrai(self) -> None:
        self._ditrai_stop.set()
        self._ditrai_status = "⏹️ Đang dừng Di Trại..."
        self._emit("aux_updated", self.get_aux_status())

    # -------------------------------------------------------------------------
    # CHIẾN TRƯỜNG & MƯU LƯỢC
    # -------------------------------------------------------------------------
    def _build_combat_config(self, action_combo_idx: Optional[int] = None) -> CombatConfig:
        cb = self.profile.combat
        combo_opts = list(ATTACK_ACTION_COMBO_OPTIONS)
        idx = action_combo_idx if action_combo_idx is not None else cb.action_combo_idx
        combo_val = combo_opts[idx] if 0 <= idx < len(combo_opts) else combo_opts[0]
        action_mode, fixed_id = parse_attack_action_combo(combo_val)

        stratagem_ids = [0, 93, 95, 94]  # khớp Desktop (ADR-0042)
        s_idx = int(cb.stratagem_combo_idx or 0)
        s_id = stratagem_ids[s_idx] if 0 <= s_idx < len(stratagem_ids) else 0

        return CombatConfig(
            auto_counter_formation=cb.auto_counter_formation,
            formation_window_seconds=_safe_int(cb.formation_window_seconds, 15),
            attack_action_mode=action_mode,
            fixed_action_id=fixed_id,
            skip_confused_enemy=cb.skip_confused_enemy,
            leave_boss_last=cb.leave_boss_last,
            auto_cleanse_confusion=cb.auto_cleanse_confusion,
            emergency_retreat_threshold=_safe_int(cb.emergency_retreat_threshold, 0),
            offensive_stratagem_id=s_id,
            auto_capture_boss=cb.auto_capture_boss,
            capture_boss_max_morale=_safe_int(cb.capture_boss_max_morale, 60),
            notification_config=self._notification_config(),
            server_id=self.server_id,
            on_web_event=lambda ev: self._emit("notification", ev),
        )

    def _on_battle_state(self, state: BattleState) -> None:
        self._battle_state = serialize_battle_state(state)
        self._emit("battle_updated", {"battle_id": self._battle_id, "state": self._battle_state})

    def load_battle(self, battle_id: int) -> dict:
        self._battle_id = int(battle_id)
        ctrl = BattleController(self.gateway)
        state = ctrl.get_battle_info(self._battle_id)
        if not state or state.ret != 0:
            ret = state.ret if state else "None"
            self.append_log("battle", f"❌ Không tải được chiến trường ID {battle_id} (ret={ret})")
            raise RuntimeError(f"Không tải được chiến trường (ret={ret})")
        self._on_battle_state(state)
        self.append_log("battle", f"✅ Đã tải '{state.site}' (ID: {battle_id}, Hiệp: {state.bout}, Còn: {state.bout_left}s)")
        return self._battle_state or {}

    def start_battle_tracker(self, battle_id: int) -> None:
        if self._battle_running:
            return
        self._battle_id = int(battle_id)
        self._battle_running = True
        self._battle_stop.clear()
        cfg = self._build_combat_config()
        self.append_log("battle", f"🚀 Bắt đầu theo dõi & tác chiến chiến trường ID {battle_id}...")

        def _worker():
            ctrl = BattleController(self.gateway, config=cfg)
            try:
                ctrl.track_battle(
                    battle_id=self._battle_id,
                    on_log=lambda m: self.append_log("battle", m),
                    on_boss_alert=lambda m: self.append_log("battle", m),
                    on_state=self._on_battle_state,
                    stop_event=self._battle_stop,
                    config=cfg,
                )
                self.append_log("battle", "🏁 Đã hoàn tất phiên theo dõi chiến trường.")
            except Exception as exc:
                self.append_log("battle", f"❌ Lỗi tác chiến: {exc}")
            finally:
                self._battle_running = False
                self._emit("aux_updated", self.get_aux_status())
                self._emit("status_changed", self.get_status_snapshot())

        self._battle_thread = threading.Thread(target=_worker, daemon=True)
        self._battle_thread.start()
        self._emit("aux_updated", self.get_aux_status())

    def stop_battle_tracker(self) -> None:
        self._battle_stop.set()
        self._battle_running = False
        self.append_log("battle", "⏹️ Đã dừng theo dõi chiến trường.")
        self._emit("aux_updated", self.get_aux_status())

    def battle_change_formation(self, battle_id: int, position: int, formation_id: int) -> bool:
        ctrl = BattleController(self.gateway)
        st = ctrl.get_battle_info(battle_id)
        if not st:
            return False
        troop = next((t for t in st.our_troops if t.position == position), None)
        if not troop:
            return False
        ok = ctrl._change_formation_preserving_plan(troop, formation_id, battle_id=battle_id)
        if ok:
            self.append_log("battle", f"🔄 Đổi [{troop.general_name}] sang {FORMATION_NAMES.get(formation_id, formation_id)}")
            try:
                self.load_battle(battle_id)
            except Exception:
                pass
        return bool(ok)

    def battle_cast_stratagem(self, battle_id: int, position: int, stratagem_id: int) -> bool:
        ctrl = BattleController(self.gateway)
        ok = ctrl.cast_stratagem(battle_id, position, stratagem_id)
        sname = STRATAGEMS.get(stratagem_id, f"Mưu kế {stratagem_id}")
        if ok:
            self.append_log("battle", f"✨ Thi triển [{sname}] lên ô {position}")
            try:
                self.load_battle(battle_id)
            except Exception:
                pass
        return bool(ok)

    def battle_defend_all(self, battle_id: int) -> None:
        ctrl = BattleController(self.gateway)
        st = ctrl.get_battle_info(battle_id)
        if not st:
            return
        for our in st.our_troops:
            dest = our.target_id if our.target_id != 0 else (st.enemy_troops[0].position if st.enemy_troops else 0)
            ctrl.change_target_attack(battle_id, our.position, dest, action=3)
        self.append_log("battle", "🛡️ Đã chuyển toàn quân sang thế Phòng ngự (action 3)")
        try:
            self.load_battle(battle_id)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # THẢO PHẠT / BÌNH MAN / GỌI DÂN / NIÊN THÚ
    # -------------------------------------------------------------------------
    def start_thaophat(self) -> None:
        tp = self.profile.thao_phat
        cid = tp.city_id or self._default_city_id()
        if not cid:
            raise ValueError("Vui lòng chọn căn cứ Thảo Phạt.")
        if not tp.generals:
            raise ValueError("Vui lòng chọn ít nhất 1 võ tướng xuất kích Thảo Phạt.")
        mission_keys = list(THAOPHAT_MISSIONS.keys())
        m_idx = max(0, min(len(mission_keys) - 1, int(tp.mission_idx or 0)))
        task_id = mission_keys[m_idx]
        target_army = TargetArmy(
            infantry=max(0, _safe_int(tp.target_infantry, 5000)),
            cavalry=max(0, _safe_int(tp.target_cavalry, 0)),
            archers=max(0, _safe_int(tp.target_archers, 0)),
        )
        interval = max(3.0, _safe_float(tp.interval, 10.0))

        runner = ThaoPhatAutoRunner(
            gateway=self.gateway,
            city_id=cid,
            task_id=task_id,
            general_ids=list(tp.generals),
            target_army=target_army,
            min_morale=max(0, min(100, _safe_int(tp.min_morale, 95))),
            auto_recruit=tp.auto_recruit,
            auto_morale=tp.auto_morale,
            check_interval=interval,
            log_callback=lambda m: self.append_log("thaophat", m),
            status_callback=lambda st: self._on_tp_runner_status(st),
        )
        self.engine.start("thaophat", runner, interval=interval, jitter=2.0)
        self._emit("status_changed", self.get_status_snapshot())

    def _on_tp_runner_status(self, st: str) -> None:
        if "Captcha" in str(st):
            self._handle_captcha(str(st))

    def stop_thaophat(self) -> None:
        self.engine.stop("thaophat")
        self._emit("status_changed", self.get_status_snapshot())

    def adjust_thaophat_troops(self) -> None:
        tp = self.profile.thao_phat
        cid = tp.city_id or self._default_city_id()
        if not cid or not tp.generals:
            raise ValueError("Vui lòng chọn căn cứ và ít nhất 1 võ tướng Thảo Phạt.")
        target_army = TargetArmy(
            infantry=max(0, _safe_int(tp.target_infantry, 5000)),
            cavalry=max(0, _safe_int(tp.target_cavalry, 0)),
            archers=max(0, _safe_int(tp.target_archers, 0)),
        )

        def _worker():
            try:
                self.append_log("thaophat", "⚔️ Bắt đầu biên chế quân đội Thảo Phạt...")
                if tp.auto_recruit:
                    fresh = fetch_roster(self.gateway)
                    needed = 0
                    for gid in tp.generals:
                        a = fresh.army_of(gid)
                        needed += max(0, target_army.infantry - (a.infantry if a else 0))
                        needed += max(0, target_army.cavalry - (a.cavalry if a else 0))
                        needed += max(0, target_army.archers - (a.archers if a else 0))
                    if needed > 0:
                        avail = self.tp_executor.check_recruits(cid)
                        if avail is not None and avail < needed:
                            self.tp_executor.buy_recruits(cid, needed - avail)
                fresh = fetch_roster(self.gateway)
                for gid in tp.generals:
                    self.tp_executor.adjust_troops(
                        cid, gid, fresh.army_of(gid), target_army,
                        auto_recruit=tp.auto_recruit,
                        on_log=lambda m: self.append_log("thaophat", m),
                    )
                self.append_log("thaophat", "🏁 Hoàn tất biên chế quân Thảo Phạt!")
                self.reload_roster()
            except Exception as exc:
                self.append_log("thaophat", f"❌ Lỗi biên chế Thảo Phạt: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _create_goidan_task(self) -> GoiDan:
        gd = self.profile.goi_dan
        cid = gd.city_id or self._default_city_id()
        if not cid:
            raise ValueError("Vui lòng chọn thành trì Gọi Man.")
        if not gd.generals:
            raise ValueError("Vui lòng chọn ít nhất 1 võ tướng xuất kích Gọi Man.")
        city = self.roster.base_by_id(cid)
        target_types = list(gd.target_types) if gd.target_types else [gd.target_type or 301]
        first_t = target_types[0]
        mode = "vong_linh" if first_t == 301 else "dan"
        scanner = Scanner(
            self.gateway, self.shared_target_locks, delay=0.0, sleep=lambda _s: None,
            map_cache_ttl=4.0, capitals_cache_ttl=300.0,
        )
        ctx = TaskContext(self.gateway, scanner, self.shared_target_locks, notify=lambda m: self.append_log("goidan", m))
        target_army = TargetArmy(
            infantry=max(0, _safe_int(gd.target_infantry, 0)),
            cavalry=max(0, _safe_int(gd.target_cavalry, 0)),
            archers=max(0, _safe_int(gd.target_archers, 0)),
        )
        return GoiDan(
            ctx=ctx,
            generals=list(gd.generals),
            origin=(city.pos_x, city.pos_y) if city else (0, 0),
            radius=max(1, _safe_int(gd.radius, 5)),
            mode=mode,
            target_type=first_t,
            target_types=target_types,
            city_id=cid,
            auto_recover=gd.auto_recover,
            refill_amount=500,
            sleep_fn=time.sleep,
            combat_config=self._build_combat_config(gd.action_combo_idx),
            on_battle_found=lambda bid: setattr(self, "_battle_id", bid),
            on_battle_state=self._on_battle_state,
            target_army=target_army,
            auto_recruit=gd.auto_recruit,
            auto_morale=gd.auto_morale,
            min_morale=max(0, min(100, _safe_int(gd.min_morale, 95))),
        )

    def start_goidan(self) -> None:
        task = self._create_goidan_task()
        interval = max(3.0, _safe_float(self.profile.goi_dan.interval, 10.0))
        self.engine.start("goidan", task, interval=interval, jitter=2.0)
        self._emit("status_changed", self.get_status_snapshot())

    def stop_goidan(self) -> None:
        self.engine.stop("goidan")
        self._emit("status_changed", self.get_status_snapshot())

    def run_goidan_once(self) -> None:
        task = self._create_goidan_task()
        threading.Thread(
            target=lambda: self.append_log("goidan", f"⚡ Kết quả chạy 1 lượt Gọi Man: {task.run_once()}"),
            daemon=True,
        ).start()

    def adjust_goidan_troops(self) -> None:
        gd = self.profile.goi_dan
        cid = gd.city_id or self._default_city_id()
        if not cid or not gd.generals:
            raise ValueError("Vui lòng chọn thành và võ tướng Gọi Man.")
        target_army = TargetArmy(
            infantry=max(0, _safe_int(gd.target_infantry, 0)),
            cavalry=max(0, _safe_int(gd.target_cavalry, 0)),
            archers=max(0, _safe_int(gd.target_archers, 0)),
        )
        min_morale = max(0, min(100, _safe_int(gd.min_morale, 95)))

        def _worker():
            try:
                self.append_log("goidan", "⚔️ Bắt đầu biên chế Gọi Man & Luyện sĩ khí...")
                prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)
                for gid in gd.generals:
                    prov.heal_general(cid, gid)
                fresh = fetch_roster(self.gateway, only_base_ids=[cid])
                troops_added = False
                if target_army.total > 0 and gd.auto_recruit:
                    needed = 0
                    for gid in gd.generals:
                        a = fresh.army_of(gid)
                        needed += max(0, target_army.infantry - (a.infantry if a else 0))
                        needed += max(0, target_army.cavalry - (a.cavalry if a else 0))
                        needed += max(0, target_army.archers - (a.archers if a else 0))
                    if needed > 0:
                        avail = prov.check_recruits(cid)
                        if avail is not None and avail < needed:
                            prov.buy_recruits(cid, needed - avail)
                    for gid in gd.generals:
                        res = prov.adjust_troops(
                            base_id=cid, general_id=gid, current_army=fresh.army_of(gid),
                            target_army=target_army, auto_recruit=True,
                            on_log=lambda m: self.append_log("goidan", m),
                        )
                        if any(succ and diff > 0 for _, diff, succ, _ in (res or [])):
                            troops_added = True
                if gd.auto_morale:
                    city_gens = {g.id: g for g in fresh.generals_of(cid)}
                    MoraleTrainer(self.gateway).adjust_squad_morale(
                        base_id=cid, general_ids=list(gd.generals), target_morale=min_morale,
                        base_gens=city_gens, on_notify=lambda m: self.append_log("goidan", m),
                        refresh_from_server=troops_added,
                    )
                self.append_log("goidan", "🏁 Hoàn tất biên chế Gọi Man!")
                self.reload_roster()
            except Exception as exc:
                self.append_log("goidan", f"❌ Lỗi biên chế Gọi Man: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def _create_binhman_tasks(self) -> list[BinhMan]:
        bm = self.profile.binh_man
        enabled_bases = [
            b for b in self.roster.bases
            if bm.bases.get(str(b.id), BaseBinhManConfig()).enabled
        ]
        if not enabled_bases and bm.current_base_id:
            b = self.roster.base_by_id(bm.current_base_id)
            if b:
                enabled_bases = [b]
        if not enabled_bases:
            raise ValueError("Vui lòng chọn ít nhất 1 Căn Cứ Bình Man.")

        all_peers: list[BasePeer] = []
        for b in enabled_bases:
            cfg = bm.bases.get(str(b.id))
            if not cfg or not cfg.generals:
                continue
            t_types = cfg.target_types or [7, 8, 9, 10]
            all_peers.append(
                BasePeer(
                    base_id=b.id, ox=b.pos_x, oy=b.pos_y,
                    radius=_safe_int(cfg.radius, 10), target_types=t_types,
                    origin=(b.pos_x, b.pos_y), mantypes=t_types, name=b.name,
                )
            )

        tasks: list[BinhMan] = []
        for b in enabled_bases:
            cfg = bm.bases.get(str(b.id))
            if not cfg or not cfg.generals:
                continue
            mode = int(cfg.mode or 1)
            camp_id = _safe_int(cfg.camp_id, b.id if (mode == 1 and b.is_camp) else 0) if mode == 1 else None
            if mode == 1 and camp_id == 0:
                camp_id = b.id if b.is_camp else None
            parent_id = _safe_int(cfg.parent_city_id, b.id) or b.id
            scanner = Scanner(
                self.gateway, self.shared_target_locks, delay=0.0, sleep=lambda _s: None,
                map_cache_ttl=4.0, capitals_cache_ttl=300.0,
            )
            ctx = TaskContext(
                self.gateway, scanner, self.shared_target_locks,
                notify=lambda m, bname=b.name: self.append_log("binhman", f"[{bname}] {m}"),
            )
            target_army = TargetArmy(
                infantry=max(0, _safe_int(cfg.target_infantry, 0)),
                cavalry=max(0, _safe_int(cfg.target_cavalry, 0)),
                archers=max(0, _safe_int(cfg.target_archers, 0)),
            )
            b_types = cfg.target_types or [7, 8, 9, 10]
            tasks.append(
                BinhMan(
                    ctx=ctx,
                    generals=list(cfg.generals),
                    origin=(b.pos_x, b.pos_y),
                    radius=max(1, _safe_int(cfg.radius, 10)),
                    man_types=b_types,
                    camp_id=camp_id,
                    parent_city_id=parent_id,
                    city_id=b.id if mode == 2 else parent_id,
                    return_threshold=max(0, _safe_int(cfg.threshold, 30)),
                    mode=mode,
                    sleep_fn=time.sleep,
                    combat_config=self._build_combat_config(cfg.action_combo_idx),
                    on_battle_found=lambda bid: setattr(self, "_battle_id", bid),
                    on_battle_state=self._on_battle_state,
                    target_army=target_army,
                    auto_recruit=cfg.auto_recruit,
                    auto_morale=cfg.auto_morale,
                    min_morale=max(0, min(100, _safe_int(cfg.min_morale, 95))),
                    peers=[p for p in all_peers if p.base_id != b.id],
                    non_blocking_relocate=True,
                    base_name=b.name,
                )
            )
        if not tasks:
            raise ValueError("Không có căn cứ Bình Man nào có võ tướng khả dụng được chọn.")
        for t in tasks:
            tid = t.origin_id
            t.peers_fn = lambda for_id=tid: [
                BasePeer(
                    base_id=o.origin_id, ox=o.origin[0], oy=o.origin[1],
                    radius=o.radius, target_types=o.man_types,
                    origin=o.origin, mantypes=o.man_types, name=getattr(o, "base_name", ""),
                )
                for o in tasks if o.origin_id != for_id
            ]
        return tasks

    def start_binhman(self) -> None:
        tasks = self._create_binhman_tasks()
        interval = max(3.0, _safe_float(self.profile.binh_man.interval, 15.0))
        runnable = _BinhManRunnable(tasks, interval=interval, log_cb=lambda m: self.append_log("binhman", m))
        self.engine.start("binhman", runnable, interval=interval, jitter=2.0)
        self._emit("status_changed", self.get_status_snapshot())

    def stop_binhman(self) -> None:
        self.engine.stop("binhman")
        self._emit("status_changed", self.get_status_snapshot())

    def run_binhman_once(self) -> None:
        tasks = self._create_binhman_tasks()

        def _worker():
            for t in tasks:
                try:
                    res = t.run_once()
                    self.append_log("binhman", f"⚡ [{getattr(t, 'base_name', '')}] Kết quả 1 lượt: {res}")
                except CaptchaRequired:
                    self._handle_captcha("Bình Man 1 lượt gặp Captcha.")
                    break
                except Exception as exc:
                    self.append_log("binhman", f"❌ Lỗi Bình Man: {exc}")

        threading.Thread(target=_worker, daemon=True).start()

    def adjust_binhman_troops(self, base_id: Optional[int] = None) -> None:
        bm = self.profile.binh_man
        if base_id is not None:
            b = self.roster.base_by_id(base_id)
            if not b:
                raise ValueError("Không tìm thấy căn cứ.")
            targets = [b]
        else:
            targets = [b for b in self.roster.bases if bm.bases.get(str(b.id), BaseBinhManConfig()).enabled]
        if not targets:
            raise ValueError("Chưa chọn căn cứ Bình Man để biên chế.")

        def _worker():
            prov = ArmyProvisioner(self.gateway, sleep_fn=time.sleep)
            for b in targets:
                cfg = bm.bases.get(str(b.id), BaseBinhManConfig())
                if not cfg.generals:
                    continue
                try:
                    self.append_log("binhman", f"⚔️ [{b.name}] Đang biên chế {len(cfg.generals)} tướng...")
                    target_army = TargetArmy(
                        infantry=max(0, _safe_int(cfg.target_infantry, 0)),
                        cavalry=max(0, _safe_int(cfg.target_cavalry, 0)),
                        archers=max(0, _safe_int(cfg.target_archers, 0)),
                    )
                    min_morale = max(0, min(100, _safe_int(cfg.min_morale, 95)))
                    for gid in cfg.generals:
                        prov.heal_general(b.id, gid)
                    fresh = fetch_roster(self.gateway, only_base_ids=[b.id], include_civil=False, include_cities=False)
                    troops_added = False
                    if target_army.total > 0:
                        for gid in cfg.generals:
                            res = prov.adjust_troops(
                                base_id=b.id, general_id=gid, current_army=fresh.army_of(gid),
                                target_army=target_army, auto_recruit=(cfg.mode == 2 and cfg.auto_recruit),
                                on_log=lambda m, bn=b.name: self.append_log("binhman", f"[{bn}] {m}"),
                            )
                            if any(succ and diff > 0 for _, diff, succ, _ in (res or [])):
                                troops_added = True
                        if cfg.mode == 1 and cfg.parent_city_id and str(cfg.parent_city_id).isdigit():
                            prov.provision_camp_generals_with_parent_city(
                                camp_id=b.id, parent_city_id=int(cfg.parent_city_id),
                                general_ids=list(cfg.generals), target_army=target_army,
                                min_morale=min_morale,
                                on_log=lambda m, bn=b.name: self.append_log("binhman", f"[{bn}] {m}"),
                            )
                    if cfg.auto_morale:
                        gens = {g.id: g for g in fresh.generals_of(b.id)}
                        MoraleTrainer(self.gateway).adjust_squad_morale(
                            base_id=b.id, general_ids=list(cfg.generals), target_morale=min_morale,
                            base_gens=gens, on_notify=lambda m, bn=b.name: self.append_log("binhman", f"[{bn}] {m}"),
                            refresh_from_server=troops_added,
                        )
                except Exception as exc:
                    self.append_log("binhman", f"❌ [{b.name}] Lỗi biên chế: {exc}")
            self.append_log("binhman", "🏁 Hoàn tất biên chế Bình Man!")
            try:
                self.reload_roster()
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def start_nienthu(self) -> None:
        nt = self.profile.nien_thu
        cid = nt.city_id or self._default_city_id()
        if not cid:
            raise ValueError("Vui lòng chọn Thành/Trại đánh Niên Thú.")
        if not nt.generals:
            raise ValueError("Vui lòng chọn ít nhất 1 võ tướng đánh Niên Thú.")
        target_army = TargetArmy(
            infantry=max(0, _safe_int(nt.target_infantry, 0)),
            cavalry=max(0, _safe_int(nt.target_cavalry, 0)),
            archers=max(0, _safe_int(nt.target_archers, 0)),
        )
        ctx = TaskContext(
            gateway=self.gateway,
            scanner=Scanner(self.gateway, self.shared_target_locks),
            locks=self.shared_target_locks,
            notify=lambda m: self.append_log("nienthu", m),
        )

        def _on_ann(ann):
            vi_name = STATE_VI_NAMES.get(ann.state_id, ann.state_name)
            self._nien_thu_ann = {
                "state_id": ann.state_id,
                "state_name": ann.state_name,
                "vi_name": vi_name,
                "server_time": ann.server_time,
            }
            self._emit("aux_updated", self.get_aux_status())

        task = NienThuTask(
            ctx=ctx,
            general_ids=list(nt.generals),
            city_id=cid,
            target_army=target_army,
            auto_recruit=nt.auto_recruit,
            auto_morale=nt.auto_morale,
            min_morale=max(0, min(100, _safe_int(nt.min_morale, 95))),
            speed_up_march=nt.speed_up_march,
            speed_up_return=nt.speed_up_return,
            stop_on_jade=nt.stop_on_jade,
            use_world_chat=nt.use_world_chat,
            run_immediately=nt.run_immediately,
            on_announcement=_on_ann,
        )
        self.engine.start("nienthu", task, interval=5.0, jitter=1.0)
        self._emit("status_changed", self.get_status_snapshot())

    def stop_nienthu(self) -> None:
        self.engine.stop("nienthu")
        self._emit("status_changed", self.get_status_snapshot())

    # -------------------------------------------------------------------------
    # TỔNG QUAN: BAN THƯỞNG / SĨ KHÍ / QUÂN GIỚI / MƯU SĨ / TRANG BỊ
    # -------------------------------------------------------------------------
    def preview_reward_all(self) -> dict:
        fresh = fetch_roster(self.gateway)
        self.roster = fresh
        self._emit("roster_updated", serialize_roster(fresh))
        targets = collect_reward_targets(fresh)
        return {
            "count": len(targets),
            "van_count": sum(1 for t in targets if t.general.role == "van"),
            "vo_count": sum(1 for t in targets if t.general.role != "van"),
            "total_gold": sum(t.money_needed for t in targets),
        }

    def run_reward_all(self) -> dict:
        fresh = fetch_roster(self.gateway)
        summary = reward_all_generals(
            self.gateway, roster=fresh, on_log=lambda m: self.append_log("global", m)
        )
        if summary.success > 0:
            try:
                self.reload_roster()
            except Exception:
                pass
        return {
            "total": summary.total,
            "success": summary.success,
            "failed": summary.failed,
            "total_gold_spent": summary.total_gold_spent,
        }

    def start_morale_training(self, general_ids: list[int], target_morale: int = 100) -> None:
        if self._morale_running:
            raise RuntimeError("Tiến trình Luyện Sĩ Khí đang chạy.")
        targets = []
        id_set = set(int(g) for g in general_ids)
        for base in self.roster.bases:
            for g in self.roster.generals_of(base.id):
                if g.id not in id_set:
                    continue
                army = self.roster.army_of(g.id)
                if not army or army.total <= 0:
                    continue
                targets.append({
                    "city_id": base.id,
                    "general_id": g.id,
                    "current_morale": g.morale,
                    "name": g.name,
                    "city_name": base.name,
                    "army": army,
                })
        if not targets:
            raise ValueError("Vui lòng chọn ít nhất 1 tướng có quân đội.")

        self._morale_running = True
        self._morale_stop.clear()
        self._morale_status = f"Đang luyện cho {len(targets)} tướng..."
        for t in targets:
            self._morale_gen_status[t["general_id"]] = "Đang luyện..."
        self._emit("aux_updated", self.get_aux_status())

        def _worker():
            trainer = MoraleTrainer(self.gateway)
            try:
                def _on_prog(completed, total, res):
                    gid = res["general_id"]
                    icon = "✅" if res["success"] else "❌"
                    self._morale_gen_status[gid] = f"{icon} {res['message']} ({res['final_morale']}/100)"
                    self._morale_status = f"Tiến độ: {completed}/{total} tướng..."
                    self._emit("aux_updated", self.get_aux_status())

                def _on_step(gid, cur, _tgt, msg):
                    self._morale_gen_status[gid] = f"{msg} ({cur}/100)"
                    self._emit("aux_updated", self.get_aux_status())

                results = trainer.train_multiple_generals(
                    targets=targets,
                    target_morale=target_morale,
                    stop_event=self._morale_stop,
                    on_progress=_on_prog,
                    on_step=_on_step,
                )
                succ = sum(1 for r in results.values() if r.get("success"))
                self._morale_status = f"Hoàn thành: {succ}/{len(targets)} tướng đạt {target_morale}."
                try:
                    self.reload_roster()
                except Exception:
                    pass
            except Exception as exc:
                self._morale_status = f"❌ Lỗi: {exc}"
            finally:
                self._morale_running = False
                self._emit("aux_updated", self.get_aux_status())

        self._morale_thread = threading.Thread(target=_worker, daemon=True)
        self._morale_thread.start()

    def stop_morale_training(self) -> None:
        self._morale_stop.set()
        self._morale_status = "Đang dừng luyện sĩ khí..."
        self._emit("aux_updated", self.get_aux_status())

    def craft_now(self, city_id: int) -> None:
        cfg = self.profile.crafting.cities.get(str(city_id))
        if not cfg:
            raise ValueError("Chưa cấu hình chế tạo cho thành này.")
        wids = cfg.weapon_ids or [cfg.weapon_id]
        amount = max(1, _safe_int(cfg.amount, 1000))

        def _worker():
            crafter = WeaponCrafter(self.gateway)
            succ_cnt = 0
            err_msg = ""
            for wid in wids:
                succ, ret, msg = crafter.craft_once(city_id, wid, amount, notify=lambda m: self.append_log("crafting", m))
                if succ:
                    succ_cnt += 1
                else:
                    err_msg = msg
                    if ret == 32:
                        break
            self._craft_statuses[city_id] = (
                f"OK {succ_cnt}/{len(wids)} ({time.strftime('%H:%M:%S')})"
                if succ_cnt > 0
                else (err_msg or "Lỗi")
            )
            self._emit("aux_updated", self.get_aux_status())

        threading.Thread(target=_worker, daemon=True).start()

    def start_crafting(self) -> None:
        if self._craft_running:
            return
        self._ensure_roster_loaded()
        valid_city_ids = {c.id for c in self.roster.cities} if self.roster and self.roster.cities else None
        enabled = [
            c for cid_str, c in self.profile.crafting.cities.items()
            if c.enabled and (valid_city_ids is None or int(c.city_id or cid_str) in valid_city_ids)
        ]
        if not enabled:
            raise ValueError("Vui lòng bật ít nhất 1 thành hợp lệ để chế tạo quân giới.")
        self._craft_running = True
        self._craft_stop.clear()

        def _loop():
            crafter = WeaponCrafter(self.gateway, workshop_cache_ttl=300.0)
            while self._craft_running and not self._craft_stop.is_set():
                now = time.time()
                cur_valid_city_ids = {c.id for c in self.roster.cities} if self.roster and self.roster.cities else None
                for cid_str, cfg in list(self.profile.crafting.cities.items()):
                    if self._craft_stop.is_set():
                        break
                    if not cfg.enabled:
                        continue
                    cid = int(cfg.city_id or cid_str)
                    if cur_valid_city_ids is not None and cid not in cur_valid_city_ids:
                        continue
                    interval_sec = max(10.0, _safe_float(cfg.interval, 5.0) * 60.0)
                    if now - self._craft_last_run.get(cid, 0.0) >= interval_sec:
                        wids = cfg.weapon_ids or [cfg.weapon_id]
                        amount = max(1, _safe_int(cfg.amount, 1000))
                        succ_cnt = 0
                        last_ret = 0
                        for idx, wid in enumerate(wids):
                            if self._craft_stop.is_set():
                                break
                            succ, ret, _msg = crafter.craft_once(
                                cid, wid, amount, notify=lambda m: self.append_log("crafting", m),
                                switch_city=(idx == 0),
                            )
                            last_ret = ret
                            if succ:
                                succ_cnt += 1
                            elif ret == 32:
                                break
                        self._craft_last_run[cid] = time.time()
                        self._craft_statuses[cid] = (
                            f"OK {succ_cnt}/{len(wids)} ({time.strftime('%H:%M:%S')})"
                            if succ_cnt > 0
                            else f"Thất bại (ret={last_ret})"
                        )
                        self._emit("aux_updated", self.get_aux_status())
                if self._craft_stop.wait(1.0):
                    break
            self._craft_running = False
            self._emit("status_changed", self.get_status_snapshot())

        self._craft_thread = threading.Thread(target=_loop, daemon=True)
        self._craft_thread.start()
        self._emit("status_changed", self.get_status_snapshot())

    def stop_crafting(self) -> None:
        self._craft_running = False
        self._craft_stop.set()
        self._emit("status_changed", self.get_status_snapshot())

    def run_tactician_action(self, mode: str, general_ids: list[int], reassign: bool = False) -> None:
        if self._tac_running:
            raise RuntimeError("Đang xử lý Thiết lập Mưu sĩ.")
        if not general_ids:
            raise ValueError("Vui lòng chọn ít nhất 1 Võ tướng.")
        self._tac_running = True
        self._tac_stop.clear()
        self._tac_status = f"Đang xử lý Mưu sĩ ({mode})..."
        self._emit("aux_updated", self.get_aux_status())

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                summary = configure_tacticians(
                    self.gateway,
                    roster=fresh,
                    target_vo_ids=list(general_ids),
                    mode=mode,
                    reassign_existing=reassign,
                    stop_event=self._tac_stop,
                    on_log=lambda m: self.append_log("tactician", m),
                )
                self._tac_status = f"Hoàn tất: {summary.assigned} biên chế, {summary.removed} tháo, {summary.failed} lỗi"
                self.reload_roster()
            except Exception as exc:
                self._tac_status = f"❌ Lỗi: {exc}"
                self.append_log("tactician", f"❌ Lỗi Mưu sĩ: {exc}")
            finally:
                self._tac_running = False
                self._emit("aux_updated", self.get_aux_status())

        threading.Thread(target=_worker, daemon=True).start()

    def stop_tactician_action(self) -> None:
        self._tac_stop.set()

    def fetch_equip_inventory(self) -> dict:
        inv = fetch_equipment_inventory(self.gateway)
        data = {
            "total_items": len(inv.items) if hasattr(inv, "items") else 0,
            "free_vo": [inv.count_free("vo", t) for t in EQUIP_TYPES] if hasattr(inv, "count_free") else [0, 0, 0, 0],
            "free_van": [inv.count_free("van", t) for t in EQUIP_TYPES] if hasattr(inv, "count_free") else [0, 0, 0, 0],
            "equipped_by_general": {
                str(gid): {
                    str(slot): item.short_label if hasattr(item, "short_label") else (item.name if hasattr(item, "name") else str(item))
                    for slot, item in slots.items()
                }
                for gid, slots in getattr(inv, "equipped_by_general", {}).items()
            },
        }
        self._equip_inventory = data
        return data

    def run_equip_action(self, mode: str, general_ids: list[int], reassign: bool = False) -> None:
        if self._equip_running:
            raise RuntimeError("Đang xử lý Trang bị.")
        if not general_ids:
            raise ValueError("Vui lòng chọn ít nhất 1 tướng.")
        self._equip_running = True
        self._equip_stop.clear()
        self._equip_status = "Đang xử lý Trang bị..."
        self._emit("aux_updated", self.get_aux_status())

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                summary = configure_equipment(
                    self.gateway,
                    roster=fresh,
                    target_general_ids=list(general_ids),
                    mode=mode,
                    reassign_existing=reassign,
                    stop_event=self._equip_stop,
                    on_log=lambda m: self.append_log("equip", m),
                )
                self._equip_status = f"Hoàn tất: {summary.equipped} mặc, {summary.unequipped} tháo, {summary.failed} lỗi"
                self.fetch_equip_inventory()
                self.reload_roster()
            except Exception as exc:
                self._equip_status = f"❌ Lỗi: {exc}"
                self.append_log("equip", f"❌ Lỗi Trang bị: {exc}")
            finally:
                self._equip_running = False
                self._emit("aux_updated", self.get_aux_status())

        threading.Thread(target=_worker, daemon=True).start()

    def stop_equip_action(self) -> None:
        self._equip_stop.set()

    # -------------------------------------------------------------------------
    # ĐỒNG BỘ QUÂN GIỚI VÕ TƯỚNG (ADR-0041 / ADR-0042)
    # -------------------------------------------------------------------------
    def fetch_all_armaments(self) -> dict:
        self._ensure_roster_loaded()
        out: dict[str, dict] = {}
        seen: set[int] = set()
        for base in self.roster.bases:
            for gen in self.roster.generals_of(base.id):
                if gen.role != "vo" or gen.id in seen:
                    continue
                seen.add(gen.id)
                snap = fetch_armament(self.gateway, gen.id, base.id)
                if snap is not None:
                    out[str(gen.id)] = {
                        "infantry": list(snap.infantry),
                        "cavalry": list(snap.cavalry),
                        "bowman": list(snap.bowman),
                        "mangonel": snap.mangonel,
                        "battle_array": snap.battle_array,
                        "formation_name": FORMATION_NAMES.get(snap.battle_array, str(snap.battle_array)),
                        "labels": {s: snap.label(s) for s in ARM_ALL_SCOPES},
                        "summary": describe_armament(snap),
                    }
        return out

    def armament_template_info(self, general_id: int) -> dict:
        self._ensure_roster_loaded()
        loc = find_general_base(self.roster, int(general_id))
        if loc is None:
            raise ValueError("Không tìm thấy Võ tướng mẫu.")
        base_id, gen = loc
        snap = fetch_armament(self.gateway, gen.id, base_id)
        if snap is None:
            raise RuntimeError(f"Không đọc được cấu hình quân giới của {gen.name}.")
        return {
            "general_id": gen.id,
            "general_name": gen.name,
            "battle_array": snap.battle_array,
            "formation_name": FORMATION_NAMES.get(snap.battle_array, str(snap.battle_array)),
            "scopes": {
                s: {"name": ARM_SCOPE_NAMES[s], "eids": list(snap.eids(s)), "label": snap.label(s)}
                for s in ARM_ALL_SCOPES
            },
            "summary": describe_armament(snap),
        }

    def armament_compare(
        self, template_id: int, general_ids: list[int], scopes: list[str], sync_formation: bool = False
    ) -> dict:
        """Trả {general_id: 'match'|'diff'|'error'} so với tướng mẫu."""
        self._ensure_roster_loaded()
        tpl_loc = find_general_base(self.roster, int(template_id))
        if tpl_loc is None:
            raise ValueError("Không tìm thấy Võ tướng mẫu.")
        tpl = fetch_armament(self.gateway, tpl_loc[1].id, tpl_loc[0])
        if tpl is None:
            raise RuntimeError("Không đọc được cấu hình tướng mẫu.")
        out: dict[str, str] = {}
        for gid in general_ids:
            loc = find_general_base(self.roster, int(gid))
            if loc is None:
                out[str(gid)] = "error"
                continue
            cur = fetch_armament(self.gateway, loc[1].id, loc[0])
            if cur is None:
                out[str(gid)] = "error"
            else:
                out[str(gid)] = "match" if armament_matches(cur, tpl, scopes, sync_formation) else "diff"
        return out

    def run_armament_sync(
        self, template_id: int, general_ids: list[int], scopes: list[str], sync_formation: bool = False
    ) -> None:
        if self._arm_running:
            raise RuntimeError("Đang đồng bộ Quân Giới.")
        if not general_ids:
            raise ValueError("Vui lòng chọn ít nhất 1 Võ tướng đích.")
        self._ensure_roster_loaded()
        self._arm_running = True
        self._arm_stop.clear()
        self._arm_status = "Đang đồng bộ Quân Giới..."
        self._emit("aux_updated", self.get_aux_status())

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                s = sync_armament(
                    self.gateway,
                    fresh,
                    int(template_id),
                    [int(x) for x in general_ids],
                    scopes=scopes,
                    sync_formation=sync_formation,
                    stop_event=self._arm_stop,
                    on_log=lambda m: self.append_log("armament", m),
                )
                self._arm_status = (
                    f"Hoàn tất: {s.synced} đồng bộ, {s.skipped_same} đã khớp, "
                    f"{s.skipped_busy} bận, {s.failed} lỗi"
                )
            except Exception as exc:
                self._arm_status = f"❌ Lỗi: {exc}"
                self.append_log("armament", f"❌ Lỗi đồng bộ Quân Giới: {exc}")
            finally:
                self._arm_running = False
                self._emit("aux_updated", self.get_aux_status())

        threading.Thread(target=_worker, daemon=True).start()

    def stop_armament_sync(self) -> None:
        self._arm_stop.set()

    # -------------------------------------------------------------------------
    # ĐỔI TÊN VĂN QUAN & VÕ TƯỚNG (ADR-0042)
    # -------------------------------------------------------------------------
    def preview_rename(self, general_ids: list[int], prefix: str, numbered: bool = True, start_index: int = 1) -> dict:
        self._ensure_roster_loaded()
        by_id = {}
        for base in self.roster.bases:
            for g in self.roster.generals_of(base.id):
                by_id.setdefault(g.id, (base.id, g))
        ordered = [by_id[int(i)] for i in general_ids if int(i) in by_id]
        plan = build_rename_plan(ordered, prefix, numbered=numbered, start_index=start_index)
        rows = []
        for cid, gen, new_name in plan:
            ok, err = validate_general_name(new_name)
            rows.append({
                "general_id": gen.id,
                "city_id": cid,
                "name": gen.name,
                "new_name": new_name,
                "width": general_name_width(new_name),
                "valid": ok,
                "error": err,
            })
        return {"max_width": RENAME_MAX_WIDTH, "rows": rows}

    def run_rename(self, items: list[dict]) -> None:
        if self._ren_running:
            raise RuntimeError("Đang đổi tên tướng.")
        pairs = [(int(i["general_id"]), str(i["new_name"])) for i in items]
        if not pairs:
            raise ValueError("Vui lòng chọn ít nhất 1 tướng để đổi tên.")
        self._ren_running = True
        self._ren_stop.clear()
        self._ren_status = "Đang đổi tên..."
        self._ren_progress = {"done": 0, "total": len(pairs)}
        self._emit("aux_updated", self.get_aux_status())

        def _on_prog(done: int, total: int) -> None:
            self._ren_progress = {"done": done, "total": total}
            self._emit("aux_updated", self.get_aux_status())

        def _worker():
            try:
                fresh = fetch_roster(self.gateway)
                s = rename_generals(
                    self.gateway,
                    fresh,
                    pairs,
                    stop_event=self._ren_stop,
                    on_log=lambda m: self.append_log("rename", m),
                    on_progress=_on_prog,
                )
                self._ren_status = (
                    f"Hoàn tất: {s.renamed} đổi, {s.skipped_same} trùng, "
                    f"{s.skipped_blocked} bị chặn, {s.invalid_name} tên sai, {s.failed} lỗi"
                )
                self.reload_roster()
            except Exception as exc:
                self._ren_status = f"❌ Lỗi: {exc}"
                self.append_log("rename", f"❌ Lỗi đổi tên: {exc}")
            finally:
                self._ren_running = False
                self._emit("aux_updated", self.get_aux_status())

        threading.Thread(target=_worker, daemon=True).start()

    def stop_rename(self) -> None:
        self._ren_stop.set()

    # -------------------------------------------------------------------------
    # CAPTCHA / PROXY / RELOGIN / AUTO-RESUME / SHUTDOWN
    # -------------------------------------------------------------------------
    def resume_after_captcha(self) -> None:
        self.captcha_required = False
        self.captcha_reason = ""
        self.status = "connected"
        self.status_text = "Đã kết nối"
        reset_system_alert(self.account_key, "captcha")
        for tid in self.engine.list_tasks():
            self.engine.resume(tid)
        self.append_log("global", "▶️ Đã xác nhận giải Captcha — tiếp tục các tác vụ tạm dừng.")
        self._emit("status_changed", self.get_status_snapshot())

    def rotate_proxy(self) -> dict:
        if not self.proxy_pool:
            raise RuntimeError("Phiên này không dùng Bể Proxy (ProxyPool).")
        new_ep = self.proxy_pool.failover(self.session)
        if new_ep:
            self.append_log("global", f"🔄 Đã đổi sang proxy mới: {new_ep.display_name}")
        else:
            self.append_log("global", "❌ Không còn proxy khả dụng.")
        status = self.get_proxy_status()
        self._emit("proxy_updated", status)
        self._emit("status_changed", self.get_status_snapshot())
        return status

    def relogin(self) -> bool:
        if not self.gateway.relogin_callback:
            raise RuntimeError("Phiên không có mật khẩu trong RAM để đăng nhập lại tự động.")
        ok = bool(self.gateway.relogin_callback())
        if ok:
            self.status = "connected"
            self.status_text = "Đã kết nối"
            self.reload_roster()
        return ok

    def test_notification(self) -> None:
        dispatch_boss_alert(
            boss_name="[Thử Nghiệm] Tào Tháo",
            position=11,
            site="Chiến trường",
            battle_id=9999,
            server_id=self.server_id,
            config=self._notification_config(),
            on_log=lambda m: self.append_log("battle", m),
            on_web_event=lambda ev: self._emit("notification", ev),
        )

    def resume_tasks(self, task_names: list[str]) -> list[str]:
        started = []
        actions = {
            "building": self.start_building,
            "research": self.start_research,
            "thaophat": self.start_thaophat,
            "binhman": self.start_binhman,
            "goidan": self.start_goidan,
            "nienthu": self.start_nienthu,
            "resource_monitor": self.start_resource_monitor,
            "crafting": self.start_crafting,
            "transfer_loop": self.start_transfer_loop,
            "army_transfer": self.start_army_transfer,
        }
        for name in task_names:
            fn = actions.get(name)
            if not fn:
                continue
            try:
                fn()
                started.append(name)
            except Exception as exc:
                self.append_log("global", f"⚠️ Không thể tự động khôi phục tác vụ '{name}': {exc}")
        return started

    def stop_all_tasks(self, wait_timeout: Optional[float] = None) -> None:
        self.engine.stop_all(wait_timeout=wait_timeout)
        self._res_monitor_running = False
        self._res_monitor_stop.set()
        self._craft_running = False
        self._craft_stop.set()
        self._transfer_running = False
        self._transfer_stop.set()
        self._army_xfer_running = False
        self._army_xfer_stop.set()
        self._arm_stop.set()
        self._ren_stop.set()
        self._morale_stop.set()
        self._ditrai_stop.set()
        self._battle_stop.set()
        self._battle_running = False
        self._chest_stop.set()
        self._tac_stop.set()
        self._equip_stop.set()
        self._emit("status_changed", self.get_status_snapshot())

    def destroy(self) -> None:
        self._destroyed = True
        self._aux_stop.set()
        self._aux_wakeup.set()
        try:
            self.save_profile()
        except Exception:
            pass
        self.stop_all_tasks(wait_timeout=1.5)


class WorkspaceManager:
    """Quản lý Không Gian Đa Tài Khoản headless dùng chung cho Web Server & CLI/Desktop."""

    def __init__(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        acquire_lock: bool = False,
        vault_key: Optional[str] = None,
    ):
        self.data_dir = ensure_data_dir(data_dir)
        self._dir_lock: Optional[DataDirLock] = DataDirLock(self.data_dir) if acquire_lock else None
        if self._dir_lock is not None:
            self._dir_lock.acquire()

        effective_vault_key = (
            resolve_or_create_vault_key(self.data_dir) if vault_key is None else vault_key
        )
        self.vault = CredentialVault(data_dir=self.data_dir, master_key=effective_vault_key)
        self._lock = threading.RLock()
        self.accounts: dict[str, dict] = {}
        self.sessions: dict[str, AccountSession] = {}
        self.last_account: str = ""
        self._listeners: list[Callable[[str, str, dict], None]] = []

        self._load_accounts()

    def subscribe(self, listener: Callable[[str, str, dict], None]) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str, str, dict], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _broadcast(self, account_key: str, event_type: str, payload: dict) -> None:
        if event_type == "status_changed":
            try:
                self._save_runtime_state()
            except Exception:
                pass
        with self._lock:
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(account_key, event_type, payload)
            except Exception:
                pass

    def _load_accounts(self) -> None:
        sf = settings_path(self.data_dir)
        if not sf.exists():
            return
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
        except Exception:
            return

        raw_accounts = data.get("accounts")
        if isinstance(raw_accounts, dict) and raw_accounts:
            for k, v in raw_accounts.items():
                if isinstance(v, dict):
                    self.accounts[k] = {
                        "server": v.get("server", ""),
                        "username": v.get("username", ""),
                        "proxy_url": v.get("proxy_url", ""),
                        "proxy": v.get("proxy", "") or v.get("proxy_raw", ""),
                        "proxy_user": v.get("proxy_user", ""),
                        "proxy_pass": v.get("proxy_pass", ""),
                        "auto_resume": bool(v.get("auto_resume", True)),
                        "auto_start_tasks": _normalize_auto_start_tasks(v.get("auto_start_tasks")),
                    }
        elif data.get("username"):
            srv = data.get("server", "")
            usr = data.get("username", "")
            k = f"{usr} @ S{srv}"
            self.accounts[k] = {
                "server": srv,
                "username": usr,
                "proxy_url": data.get("proxy_url", ""),
                "proxy": data.get("proxy", ""),
                "proxy_user": data.get("proxy_user", ""),
                "proxy_pass": data.get("proxy_pass", ""),
                "auto_resume": True,
                "auto_start_tasks": [],
            }
        self.last_account = str(data.get("last_account", "") or "")

    def persist_settings(self) -> None:
        clean_accounts = {}
        with self._lock:
            for k, v in self.accounts.items():
                u = v.get("username", "")
                s = v.get("server", "")
                if not u or not s:
                    continue
                clean_accounts[k] = {
                    "server": s,
                    "username": u,
                    "proxy_url": v.get("proxy_url", ""),
                    "proxy": v.get("proxy", ""),
                    "proxy_user": v.get("proxy_user", ""),
                    "proxy_pass": v.get("proxy_pass", ""),
                    "auto_resume": bool(v.get("auto_resume", True)),
                    "auto_start_tasks": _normalize_auto_start_tasks(v.get("auto_start_tasks")),
                }
            last_acc = self.last_account if self.last_account in clean_accounts else next(iter(clean_accounts.keys()), "")
            first_acc = next(iter(clean_accounts.values()), {})
            data = {
                "server": first_acc.get("server", ""),
                "username": first_acc.get("username", ""),
                "proxy_url": first_acc.get("proxy_url", ""),
                "proxy": first_acc.get("proxy", ""),
                "proxy_user": first_acc.get("proxy_user", ""),
                "proxy_pass": first_acc.get("proxy_pass", ""),
                "last_account": last_acc,
                "accounts": clean_accounts,
            }
        atomic_write_text(settings_path(self.data_dir), json.dumps(data, ensure_ascii=False, indent=2))

    def list_accounts(self) -> list[dict]:
        with self._lock:
            vault_keys = set(self.vault.list_saved_keys()) if self.vault.is_unlocked() else set()
            items = []
            for key, acc in self.accounts.items():
                sess = self.sessions.get(key)
                if sess:
                    summary = sess.get_status_snapshot()
                else:
                    summary = {
                        "account_key": key,
                        "server_id": _safe_int(acc.get("server"), 0),
                        "username": acc.get("username", ""),
                        "status": "disconnected",
                        "status_text": "Chưa đăng nhập",
                        "captcha_required": False,
                        "captcha_reason": "",
                        "tasks_summary": "Nghỉ",
                        "tasks": {},
                        "proxy": {
                            "mode": "pool" if acc.get("proxy_url") else ("single" if acc.get("proxy") else "direct"),
                            "active": acc.get("proxy") or None,
                            "alive": 0,
                            "total": 0,
                        },
                    }
                summary["config"] = dict(acc)
                summary["has_vault_password"] = key in vault_keys
                items.append(summary)
            return items

    def add_or_update_account(
        self,
        *,
        server_id: int,
        username: str,
        proxy_url: str = "",
        proxy: str = "",
        proxy_user: str = "",
        proxy_pass: str = "",
        auto_resume: bool = True,
        auto_start_tasks: Optional[list[str]] = None,
        old_key: Optional[str] = None,
    ) -> dict:
        sid = parse_server_id(str(server_id))
        usr = (username or "").strip()
        if not usr:
            raise ValueError("Tên tài khoản không được để trống.")
        canonical = f"{usr} @ S{sid}"
        with self._lock:
            existing_cfg = self.accounts.get(canonical) or (self.accounts.get(old_key) if old_key else None) or {}
            if old_key and old_key != canonical and old_key in self.accounts:
                self.accounts.pop(old_key, None)
                if old_key in self.sessions:
                    self.sessions[canonical] = self.sessions.pop(old_key)
                    self.sessions[canonical].account_key = canonical
                self.vault.rename_entry(old_key, canonical)
            resolved_tasks = (
                _normalize_auto_start_tasks(auto_start_tasks)
                if auto_start_tasks is not None
                else _normalize_auto_start_tasks(existing_cfg.get("auto_start_tasks"))
            )
            self.accounts[canonical] = {
                "server": sid,
                "username": usr,
                "proxy_url": proxy_url.strip(),
                "proxy": proxy.strip(),
                "proxy_user": proxy_user.strip(),
                "proxy_pass": proxy_pass,
                "auto_resume": bool(auto_resume),
                "auto_start_tasks": resolved_tasks,
            }
            self.last_account = canonical
            self.persist_settings()
        self._broadcast(canonical, "accounts_changed", {"accounts": self.list_accounts()})
        return next(a for a in self.list_accounts() if a["account_key"] == canonical)

    def set_account_vault_password(
        self,
        account_key: str,
        *,
        save: bool,
        password: str = "",
        auto_resume: Optional[bool] = None,
    ) -> dict:
        """Lưu hoặc xóa mật khẩu game trong Két Mật Khẩu Mã Hóa cho một tài khoản."""
        with self._lock:
            acc = self.accounts.get(account_key)
            if not acc:
                raise KeyError(f"Không tìm thấy tài khoản '{account_key}'.")
            if save:
                sess = self.sessions.get(account_key)
                pwd = password or (sess._password if sess else "") or (
                    self.vault.get_password(account_key) if self.vault.is_unlocked() else ""
                )
                if not pwd:
                    raise ValueError("Vui lòng nhập mật khẩu game để lưu vào Két.")
                eff_resume = bool(acc.get("auto_resume", True)) if auto_resume is None else bool(auto_resume)
                self.vault.set_entry(account_key, pwd, auto_resume=eff_resume)
            else:
                self.vault.remove_entry(account_key)
        accounts = self.list_accounts()
        self._broadcast(account_key, "accounts_changed", {"accounts": accounts})
        return next(a for a in accounts if a["account_key"] == account_key)

    def update_account_autostart(
        self,
        account_key: str,
        *,
        auto_resume: Optional[bool] = None,
        auto_start_tasks: Optional[list[str]] = None,
    ) -> dict:
        """Cập nhật tùy chọn tự động khởi chạy khi server/bot khởi động."""
        with self._lock:
            acc = self.accounts.get(account_key)
            if not acc:
                raise KeyError(f"Không tìm thấy tài khoản '{account_key}'.")
            if auto_resume is not None:
                acc["auto_resume"] = bool(auto_resume)
            if auto_start_tasks is not None:
                acc["auto_start_tasks"] = _normalize_auto_start_tasks(auto_start_tasks)
            self.persist_settings()
            if auto_resume is not None and self.vault.is_unlocked() and self.vault.has_vault_file():
                try:
                    entry = self.vault.get_entry(account_key)
                    if entry and entry.get("password"):
                        self.vault.set_entry(account_key, entry["password"], auto_resume=bool(acc["auto_resume"]))
                except VaultError:
                    pass
        accounts = self.list_accounts()
        self._broadcast(account_key, "accounts_changed", {"accounts": accounts})
        return next(a for a in accounts if a["account_key"] == account_key)

    def delete_account(self, account_key: str) -> None:
        self.logout_account(account_key)
        with self._lock:
            self.accounts.pop(account_key, None)
            self.vault.remove_entry(account_key)
            self.persist_settings()
        self._broadcast(account_key, "accounts_changed", {"accounts": self.list_accounts()})

    def test_proxy_list(self, proxy_url: str) -> dict:
        url = (proxy_url or "").strip()
        if not url:
            raise ValueError("Vui lòng nhập URL danh sách Proxy.")
        pool = ProxyPool(url=url)
        count = pool.fetch_from_url()
        if count == 0:
            return {"count": 0, "alive": 0, "best": None, "message": "Không tìm thấy proxy hợp lệ."}
        alive = pool.check_all()
        best = {"display_name": alive[0].display_name, "latency": alive[0].latency} if alive else None
        msg = (
            f"Tìm thấy {len(alive)}/{count} proxy sống (Tốt nhất: {alive[0].display_name} - {alive[0].latency}s)"
            if alive
            else f"Đã tải {count} proxy nhưng toàn bộ không kết nối được game."
        )
        return {"count": count, "alive": len(alive), "best": best, "message": msg}

    def login_account(
        self,
        *,
        server_id: int,
        username: str,
        password: str = "",
        proxy_url: str = "",
        proxy: str = "",
        proxy_user: str = "",
        proxy_pass: str = "",
        save_to_vault: bool = False,
        auto_resume: bool = True,
        auto_start_tasks: Optional[list[str]] = None,
        old_key: Optional[str] = None,
        fetch_initial_roster: bool = True,
    ) -> AccountSession:
        sid = parse_server_id(str(server_id))
        usr = (username or "").strip()
        if not usr:
            raise ValueError("Tên tài khoản không được để trống.")
        canonical = f"{usr} @ S{sid}"

        pwd = password
        if not pwd and self.vault.is_unlocked():
            pwd = self.vault.get_password(canonical)
        if not pwd:
            raise LoginError("Vui lòng nhập mật khẩu tài khoản game.")

        p_url = (proxy_url or "").strip()
        p_raw = (proxy or "").strip()
        p_user = (proxy_user or "").strip()
        p_pass = proxy_pass or ""

        normalized_proxy = None
        if not p_url and p_raw:
            normalized_proxy = normalize_proxy_url(p_raw, username=p_user, password=p_pass)

        req_session = requests.Session()
        proxy_pool: Optional[ProxyPool] = None
        if p_url:
            proxy_pool = ProxyPool(url=p_url)
            count = proxy_pool.fetch_from_url()
            alive = proxy_pool.check_all()
            if not alive:
                raise LoginError(f"Tải được {count} proxy từ URL nhưng toàn bộ đều không kết nối được.")
            proxy_pool.apply_to_session(req_session)

        if not p_url and normalized_proxy:
            login(req_session, sid, usr, pwd, proxy=normalized_proxy)
        else:
            login(req_session, sid, usr, pwd)

        self.add_or_update_account(
            server_id=sid,
            username=usr,
            proxy_url=p_url,
            proxy=p_raw,
            proxy_user=p_user,
            proxy_pass=p_pass,
            auto_resume=auto_resume,
            auto_start_tasks=auto_start_tasks,
            old_key=old_key,
        )

        if save_to_vault:
            self.vault.set_entry(canonical, pwd, auto_resume=auto_resume)

        old_sess = self.sessions.pop(canonical, None)
        if old_sess:
            old_sess.destroy()

        acc_sess = AccountSession(
            account_key=canonical,
            session=req_session,
            server_id=sid,
            username=usr,
            password=pwd,
            proxy_raw=p_raw,
            proxy_user=p_user,
            proxy_pass=p_pass,
            proxy_url=p_url,
            proxy_pool=proxy_pool,
            data_dir=self.data_dir,
            event_cb=self._broadcast,
        )
        with self._lock:
            self.sessions[canonical] = acc_sess

        if fetch_initial_roster:
            try:
                acc_sess.reload_roster()
            except Exception as exc:
                acc_sess.append_log("global", f"⚠️ Không thể tải danh sách thành ngay sau đăng nhập: {exc}")
            acc_sess.start_aux_loop()

        self._broadcast(canonical, "accounts_changed", {"accounts": self.list_accounts()})
        return acc_sess

    def logout_account(self, account_key: str) -> None:
        with self._lock:
            sess = self.sessions.pop(account_key, None)
        if sess:
            sess.destroy()
        self._broadcast(account_key, "accounts_changed", {"accounts": self.list_accounts()})

    def get_session(self, account_key: str) -> AccountSession:
        with self._lock:
            sess = self.sessions.get(account_key)
        if not sess:
            raise KeyError(f"Tài khoản '{account_key}' chưa đăng nhập.")
        return sess

    def start_all_accounts(self) -> int:
        count = 0
        batch_tasks = [t for t in RESUMABLE_TASKS if t not in ("resource_monitor", "transfer_loop")]
        with self._lock:
            sessions = list(self.sessions.values())
        for sess in sessions:
            try:
                started = sess.resume_tasks(batch_tasks)
                if started:
                    count += 1
            except Exception:
                pass
        return count

    def stop_all_accounts(self) -> int:
        with self._lock:
            sessions = list(self.sessions.values())
        for sess in sessions:
            sess.stop_all_tasks(wait_timeout=1.5)
        return len(sessions)

    def _save_runtime_state(self) -> None:
        state: dict[str, dict] = {"version": 1, "accounts": {}}
        with self._lock:
            for key, sess in self.sessions.items():
                running = sess.get_running_task_names()
                if running:
                    state["accounts"][key] = {"running_tasks": running}
        atomic_write_text(runtime_state_path(self.data_dir), json.dumps(state, ensure_ascii=False, indent=2))

    def auto_restore_on_startup(self) -> dict:
        """Tự động đăng nhập lại từ Két Mật Khẩu Mã Hóa và khôi phục tác vụ (ADR-0039)."""
        if not self.vault.is_unlocked() or not self.vault.has_vault_file():
            return {"restored_accounts": [], "resumed_tasks": {}}

        saved_state = {}
        rpath = runtime_state_path(self.data_dir)
        if rpath.exists():
            try:
                saved_state = json.loads(rpath.read_text(encoding="utf-8")).get("accounts", {})
            except Exception:
                saved_state = {}

        restored = []
        resumed_tasks: dict[str, list[str]] = {}
        for key, acc in list(self.accounts.items()):
            try:
                entry = self.vault.get_entry(key)
            except VaultError as exc:
                logger.error(f"Không thể giải mã Két Mật Khẩu Mã Hóa khi khởi động: {exc}")
                break
            if not entry or not entry.get("password"):
                continue
            try:
                sess = self.login_account(
                    server_id=_safe_int(acc.get("server"), 0),
                    username=acc.get("username", ""),
                    password=entry["password"],
                    proxy_url=acc.get("proxy_url", ""),
                    proxy=acc.get("proxy", ""),
                    proxy_user=acc.get("proxy_user", ""),
                    proxy_pass=acc.get("proxy_pass", ""),
                    save_to_vault=False,
                    auto_resume=bool(acc.get("auto_resume", True)),
                )
                restored.append(key)
                tasks_to_start = list(_normalize_auto_start_tasks(acc.get("auto_start_tasks")))
                if acc.get("auto_resume", True) and entry.get("auto_resume", True):
                    for tname in saved_state.get(key, {}).get("running_tasks", []):
                        if tname not in tasks_to_start:
                            tasks_to_start.append(tname)
                if tasks_to_start:
                    resumed = sess.resume_tasks(tasks_to_start)
                    if resumed:
                        resumed_tasks[key] = resumed
            except Exception as exc:
                logger.warning(f"Tự khôi phục đăng nhập tài khoản '{key}' thất bại: {exc}")

        return {"restored_accounts": restored, "resumed_tasks": resumed_tasks}

    def graceful_shutdown(self) -> None:
        """Lưu trạng thái tác vụ đang chạy, dừng an toàn mọi phiên và nhả khóa dữ liệu."""
        try:
            self._save_runtime_state()
        except Exception as exc:
            logger.warning(f"Không thể lưu runtime_state.json khi tắt: {exc}")

        with self._lock:
            sessions = list(self.sessions.values())
        for sess in sessions:
            try:
                sess.destroy()
            except Exception:
                pass
        with self._lock:
            self.sessions.clear()

        if self._dir_lock is not None:
            self._dir_lock.release()
