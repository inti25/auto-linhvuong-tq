"""Tác vụ Đánh Niên Thú: tìm Niên Thú theo thông báo thế giới & Châu Thành, xuất kích & tăng tốc."""

from dataclasses import dataclass
from datetime import datetime
import threading
import time
from typing import Callable, Optional

from ..gateway import GatewayClient
from ..roster import fetch_roster
from ..troops import ArmyProvisioner, TargetArmy
from ..world_chat import (
    STATE_NAMES,
    STATE_VI_NAMES,
    NienThuAnnouncement,
    WorldChatClient,
    parse_city_chat_config,
)
from .base import (
    RET_CAPTCHA_REQUIRED,
    RET_OK,
    CaptchaRequired,
    TaskContext,
    inspect_general_statuses,
)
from .morale import MoraleTrainer

NGOC_THO_JADE_ITEM_ID = 5001
NIEN_THU_HEAD_ID = 712
NIEN_THU_NAME = "年兽"
MIN_SPEEDUP_REMAINING_SECONDS = 60

MISSION_IDLE = 0
MISSION_MARCHING = 1
MISSION_FIGHTING = 2
MISSION_RETURNING = 3
MISSION_WAITING = 4

MISSION_STATE_NAMES = {
    MISSION_MARCHING: "marching",
    MISSION_FIGHTING: "fighting",
    MISSION_RETURNING: "returning",
    MISSION_WAITING: "waiting",
}


@dataclass(frozen=True)
class NienThuTarget:
    """Thông tin NPC Niên Thú trong Châu Thành (`Common.ashx?id=126`)."""

    state_id: int
    npc_id: int
    head_id: int
    name: str
    status_flag: int = 0


@dataclass(frozen=True)
class NpcCityExpedition:
    """Trạng thái đoàn quân Châu Thành hiện tại của tài khoản (`Common.ashx?id=127`)."""

    state_id: int
    x: int
    y: int
    npc_id: int
    npc_name: str
    mission_state: int
    remaining_seconds: int
    general_id: int
    general_name: str
    battle_id: int = 0

    @property
    def is_idle(self) -> bool:
        return self.mission_state == MISSION_IDLE


def _check_captcha(resp: dict) -> int:
    ret = int(resp.get("ret", RET_OK))
    if ret == RET_CAPTCHA_REQUIRED:
        raise CaptchaRequired()
    return ret


def has_ngoc_tho_jade(gateway: GatewayClient) -> tuple[bool, int]:
    """Kiểm tra túi sự kiện (`Common.ashx?id=142`) xem đã có `玉兔呈祥` (id=5001) chưa."""
    resp = gateway.call("Common.ashx", 142, {}) or {}
    if not resp:
        return False, 0
    ret = _check_captcha(resp)
    if ret != RET_OK:
        return False, 0
    for item in resp.get("list", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                if int(item[0]) == NGOC_THO_JADE_ITEM_ID:
                    return True, int(item[1])
            except (TypeError, ValueError):
                continue
    return False, 0


def find_nien_thu_in_state(gateway: GatewayClient, state_id: int) -> Optional[NienThuTarget]:
    """Kiểm tra một Châu Thành (`Common.ashx?id=126`) có NPC Niên Thú (`年兽` / headid=712) không."""
    resp = gateway.call("Common.ashx", 126, {"lStatID": str(state_id), "_": ""}) or {}
    if not resp:
        return None
    ret = _check_captcha(resp)
    if ret != RET_OK:
        return None
    for entry in resp.get("list", []):
        if not isinstance(entry, (list, tuple)) or len(entry) < 4:
            continue
        try:
            npc_id = int(entry[0])
            head_id = int(entry[1])
            status_flag = int(entry[2])
        except (TypeError, ValueError):
            continue
        name = str(entry[3])
        if name == NIEN_THU_NAME or head_id == NIEN_THU_HEAD_ID:
            return NienThuTarget(
                state_id=int(state_id),
                npc_id=npc_id,
                head_id=head_id,
                name=name,
                status_flag=status_flag,
            )
    return None


def scan_all_states_for_nien_thu(
    gateway: GatewayClient,
    preferred_state_id: Optional[int] = None,
) -> Optional[NienThuTarget]:
    """Tìm Niên Thú theo `preferred_state_id` trước (nếu có), sau đó quét 16 Châu (`1..16`)."""
    if preferred_state_id is not None and 1 <= int(preferred_state_id) <= 16:
        hit = find_nien_thu_in_state(gateway, int(preferred_state_id))
        if hit is not None:
            return hit

    for state_id in range(1, 17):
        if preferred_state_id is not None and state_id == int(preferred_state_id):
            continue
        hit = find_nien_thu_in_state(gateway, state_id)
        if hit is not None:
            return hit
    return None


def get_npc_city_expedition(
    gateway: GatewayClient,
    state_id: int,
    npc_id: int,
) -> Optional[NpcCityExpedition]:
    """Đọc trạng thái đoàn quân Châu Thành (`Common.ashx?id=127` -> `infos`)."""
    resp = (
        gateway.call(
            "Common.ashx",
            127,
            {"lStatID": str(state_id), "lNpcID": str(npc_id)},
        )
        or {}
    )
    if not resp:
        return None
    ret = _check_captcha(resp)
    if ret != RET_OK:
        return None
    infos = resp.get("infos")
    if not isinstance(infos, (list, tuple)) or len(infos) < 14:
        return None
    try:
        return NpcCityExpedition(
            state_id=int(infos[0]),
            x=int(infos[1]),
            y=int(infos[2]),
            npc_id=int(infos[3]),
            npc_name=str(infos[4]),
            mission_state=int(infos[5]),
            remaining_seconds=int(infos[6]),
            general_id=int(infos[7]),
            general_name=str(infos[8]),
            battle_id=int(infos[13]),
        )
    except (TypeError, ValueError):
        return None


def attack_nien_thu(
    gateway: GatewayClient,
    state_id: int,
    npc_id: int,
    general_id: int,
) -> tuple[bool, int]:
    """Xuất quân đánh NPC Châu Thành (`OPT.ashx?id=162`)."""
    resp = (
        gateway.call(
            "OPT.ashx",
            162,
            {
                "lStateID": str(state_id),
                "lNpcID": str(npc_id),
                "lGeneralID": str(general_id),
                "_": "",
            },
        )
        or {}
    )
    ret = _check_captcha(resp)
    return ret == RET_OK, ret


def speedup_npc_expedition(gateway: GatewayClient) -> tuple[bool, int]:
    """Tăng tốc hành quân / rút về bằng `速行军` (`OPT.ashx?id=167`)."""
    resp = gateway.call("OPT.ashx", 167, {}) or {}
    ret = _check_captcha(resp)
    return ret == RET_OK, ret


class NienThuTask:
    """Tác vụ tự động Đánh Niên Thú chuẩn `ExecutableTask` cho `AutomationEngine`."""

    def __init__(
        self,
        ctx: TaskContext,
        general_ids: list[int],
        city_id: int = 0,
        target_army: Optional[TargetArmy] = None,
        auto_recruit: bool = False,
        auto_morale: bool = False,
        min_morale: int = 95,
        speed_up_march: bool = False,
        speed_up_return: bool = False,
        stop_on_jade: bool = False,
        use_world_chat: bool = True,
        run_immediately: bool = True,
        max_speedup_calls: int = 5,
        now_fn: Callable[[], datetime] = datetime.now,
        sleep_fn: Callable[[float], None] = time.sleep,
        chat_client_factory: Optional[Callable[[], WorldChatClient]] = None,
        on_announcement: Optional[Callable[[NienThuAnnouncement], None]] = None,
        on_completed: Optional[Callable[[], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.ctx = ctx
        self.general_ids = [int(g) for g in general_ids if int(g) > 0]
        self.city_id = int(city_id or 0)
        self.target_army = target_army
        self.auto_recruit = bool(auto_recruit)
        self.auto_morale = bool(auto_morale)
        self.min_morale = int(min_morale)
        self.speed_up_march = bool(speed_up_march)
        self.speed_up_return = bool(speed_up_return)
        self.stop_on_jade = bool(stop_on_jade)
        self.use_world_chat = bool(use_world_chat)
        self.run_immediately = bool(run_immediately)
        self.max_speedup_calls = max(1, int(max_speedup_calls))
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn
        self.chat_client_factory = chat_client_factory or WorldChatClient
        self.on_announcement = on_announcement
        self.on_completed = on_completed
        self.stop_event = stop_event

        self._initialized = False
        self._skip_hour_key: Optional[tuple[int, int, int, int]] = None
        self._attacked_hour_key: Optional[tuple[int, int, int, int]] = None
        self._last_ann_key: Optional[tuple[int, str]] = None

    def reset(self) -> None:
        self._initialized = False
        self._skip_hour_key = None
        self._attacked_hour_key = None
        self._last_ann_key = None

    def _notify(self, msg: str) -> None:
        if self.ctx and self.ctx.notify:
            self.ctx.notify(msg)

    def _should_stop(self) -> bool:
        return bool(self.stop_event and self.stop_event.is_set())

    def _fetch_announced_state_id(self) -> Optional[int]:
        try:
            url = f"http://sg{self.ctx.gateway.server_id}.dipan.com/city"
            resp = self.ctx.gateway.session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            html_text = getattr(resp, "text", "") or ""
            creds = parse_city_chat_config(html_text)
            if not creds:
                return None
            ann = self.chat_client_factory().fetch_latest_nien_thu(creds, timeout=3.0)
            if not ann:
                return None
            ann_key = (ann.state_id, ann.server_time)
            if ann_key != self._last_ann_key:
                self._last_ann_key = ann_key
                vi_name = STATE_VI_NAMES.get(ann.state_id, ann.state_name)
                self._notify(
                    f"📢 Kênh thế giới: Niên Thú xuất hiện tại {vi_name} ({ann.state_name}, ID={ann.state_id}) lúc {ann.server_time or '?'}"
                )
                if self.on_announcement:
                    self.on_announcement(ann)
            return ann.state_id
        except Exception as exc:
            self._notify(f"⚠️ Không đọc được kênh thế giới ({exc}), chuyển sang quét 16 Châu...")
            return None

    def _pick_idle_general(self) -> Optional[int]:
        if not self.general_ids:
            return None
        statuses = inspect_general_statuses(self.ctx.gateway, self.general_ids)
        for gid in self.general_ids:
            if statuses.get(gid, 0) == 0:
                return gid
        return None

    def _prepare_general_before_attack(self, general_id: int) -> None:
        if self.city_id == 0:
            return
        need_troops = bool(self.target_army and self.target_army.total > 0)
        if not (need_troops or self.auto_morale):
            return
        roster = fetch_roster(
            self.ctx.gateway,
            only_base_ids=[self.city_id],
            include_civil=False,
        )
        if need_troops and self.target_army is not None:
            provisioner = ArmyProvisioner(self.ctx.gateway, sleep_fn=self.sleep_fn)
            provisioner.adjust_troops(
                base_id=self.city_id,
                general_id=general_id,
                current_army=roster.army_of(general_id),
                target_army=self.target_army,
                auto_recruit=self.auto_recruit,
                on_log=self._notify,
            )
        if self.auto_morale:
            gen = next((g for g in roster.generals_of(self.city_id) if g.id == general_id), None)
            if gen and gen.morale < self.min_morale:
                trainer = MoraleTrainer(self.ctx, sleep_fn=self.sleep_fn)
                trainer.ensure_morale(
                    city_id=self.city_id,
                    general_id=general_id,
                    current_morale=gen.morale,
                    min_morale=self.min_morale,
                )

    def _apply_speedup(self, target: NienThuTarget, expected_state: int) -> int:
        used = 0
        for _ in range(self.max_speedup_calls):
            if self._should_stop():
                break
            exp = get_npc_city_expedition(self.ctx.gateway, target.state_id, target.npc_id)
            if (
                exp is None
                or exp.mission_state != expected_state
                or exp.remaining_seconds <= MIN_SPEEDUP_REMAINING_SECONDS
            ):
                break
            ok, ret = speedup_npc_expedition(self.ctx.gateway)
            if not ok:
                self._notify(f"⚠️ Dùng Tốc Hành Quân thất bại (ret={ret}).")
                break
            used += 1
            self._notify(f"⚡ Đã dùng Tốc Hành Quân lần {used} (còn {exp.remaining_seconds}s).")
            self.sleep_fn(0.5)
        return used

    def run_step(self) -> str:
        now = self.now_fn()
        hour_key = (now.year, now.month, now.day, now.hour)

        if not self.run_immediately and not self._initialized:
            self._initialized = True
            self._skip_hour_key = hour_key
            self._notify("⏳ Đã bật Auto Niên Thú, chờ đến giờ chẵn kế tiếp...")
            return "waiting_next_hour"

        self._initialized = True

        if self._skip_hour_key == hour_key or self._attacked_hour_key == hour_key:
            return "waiting_next_hour"

        if self.stop_on_jade:
            found_jade, count = has_ngoc_tho_jade(self.ctx.gateway)
            if found_jade:
                self._notify(f"🎉 ĐÃ CÓ 玉兔呈祥 ({count})! Dừng Auto Niên Thú.")
                if self.on_completed:
                    self.on_completed()
                return "nien_thu_jade_obtained"

        if not self.general_ids:
            self._notify("⚠️ Chưa chọn võ tướng đánh Niên Thú.")
            return "no_generals"

        preferred_state = self._fetch_announced_state_id() if self.use_world_chat else None
        target = scan_all_states_for_nien_thu(self.ctx.gateway, preferred_state_id=preferred_state)
        if target is None:
            return "nien_thu_not_found"

        vi_name = STATE_VI_NAMES.get(target.state_id, STATE_NAMES.get(target.state_id, str(target.state_id)))
        self._notify(f"🎯 Tìm thấy Niên Thú tại {vi_name} (ID={target.state_id}, NPC={target.npc_id}).")

        exp = get_npc_city_expedition(self.ctx.gateway, target.state_id, target.npc_id)
        if exp is not None and not exp.is_idle:
            if exp.mission_state == MISSION_RETURNING and self.speed_up_return:
                self._apply_speedup(target, expected_state=MISSION_RETURNING)
            state_label = MISSION_STATE_NAMES.get(exp.mission_state, str(exp.mission_state))
            return f"expedition_busy:{state_label}"

        chosen_gid = self._pick_idle_general()
        if chosen_gid is None:
            self._notify("⏳ Tướng đánh Niên Thú đang bận, chờ lượt sau...")
            return "generals_busy"

        self._prepare_general_before_attack(chosen_gid)

        ok, ret = attack_nien_thu(self.ctx.gateway, target.state_id, target.npc_id, chosen_gid)
        if not ok:
            self._notify(f"❌ Xuất quân đánh Niên Thú thất bại (ret={ret}).")
            return f"attack_failed:{ret}"

        self._attacked_hour_key = hour_key
        self._notify(f"⚔️ Đã xuất quân tướng {chosen_gid} đánh Niên Thú tại {vi_name}!")

        if self.speed_up_march:
            self._apply_speedup(target, expected_state=MISSION_MARCHING)

        return f"attacked:{target.state_id}:{target.npc_id}"
