"""Giám sát & phân tích quân tấn công Căn Cứ (Incoming Attack Monitor - ADR-0050).

Thu thập quân tình toàn bộ Thành & Doanh trại theo chiến lược hai tầng:
1. Gọi `Common.ashx?id=41` (`lCityCampID=0`) — 1 request duy nhất lấy tổng hợp toàn bộ căn cứ.
2. Chỉ gọi `Common.ashx?id=40` (`tid=<base_id>`) cho các căn cứ có `lai_pham_count > 0` hoặc cờ đang giao chiến.

Chỉ đọc trạng thái (read-only), lọc chặt các trận đánh Man/Thảo Phạt bên ngoài để không báo giả,
hỗ trợ chống lặp theo chữ ký nguồn + cửa sổ thời gian tới, và tự hẹn mốc đánh thức khẩn cấp (<= 5 phút).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .tasks.base import CaptchaRequired

logger = logging.getLogger("linhvuong.attack_monitor")

URGENT_THRESHOLD_SECONDS = 300
ARRIVAL_MATCH_TOLERANCE_SECONDS = 90.0
MIN_ATTACK_RECHECK_SECONDS = 10.0


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        if val is None or isinstance(val, bool):
            return default
        s = str(val).strip()
        if not s:
            return default
        return int(float(s))
    except (ValueError, TypeError):
        return default


def _check_captcha(resp: Any) -> None:
    if isinstance(resp, dict) and _safe_int(resp.get("ret"), 0) == 110:
        raise CaptchaRequired("Máy chủ yêu cầu giải Captcha (mã 110) khi kiểm tra quân tình.")


@dataclass
class IncomingAttack:
    """Thông tin một đạo quân địch đang hành quân tới tấn công một Căn Cứ."""

    target_base_id: int
    target_base_name: str
    target_x: int = 0
    target_y: int = 0
    target_is_camp: bool = False
    move_type: int = 1
    attacker_uid: int = 0
    attacker_name: str = ""
    source_id: int = 0
    source_name: str = ""
    source_x: int = 0
    source_y: int = 0
    generals: list[tuple[int, str]] = field(default_factory=list)
    infantry: int = -1
    cavalry: int = -1
    archers: int = -1
    siege: int = -1
    remaining_seconds: int = 0
    arrival_epoch: float = 0.0

    @property
    def is_pvp(self) -> bool:
        return self.attacker_uid > 0 or bool(self.attacker_name.strip())

    @property
    def signature(self) -> tuple[int, int, int, int, int]:
        return (
            int(self.target_base_id),
            int(self.attacker_uid),
            int(self.source_id),
            int(self.source_x),
            int(self.source_y),
        )

    def current_remaining_seconds(self, now_epoch: Optional[float] = None) -> int:
        if self.arrival_epoch > 0:
            now = time.time() if now_epoch is None else float(now_epoch)
            return max(0, int(round(self.arrival_epoch - now)))
        return max(0, int(self.remaining_seconds))

    def to_dict(self, now_epoch: Optional[float] = None) -> dict:
        rem = self.current_remaining_seconds(now_epoch=now_epoch)
        return {
            "target_base_id": self.target_base_id,
            "target_base_name": self.target_base_name,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "target_is_camp": self.target_is_camp,
            "move_type": self.move_type,
            "attacker_uid": self.attacker_uid,
            "attacker_name": self.attacker_name,
            "is_pvp": self.is_pvp,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_x": self.source_x,
            "source_y": self.source_y,
            "generals": [{"id": gid, "name": gname} for gid, gname in self.generals],
            "infantry": self.infantry,
            "cavalry": self.cavalry,
            "archers": self.archers,
            "siege": self.siege,
            "remaining_seconds": rem,
            "arrival_epoch": self.arrival_epoch,
        }


@dataclass
class DefensiveBattle:
    """Trận chiến phòng thủ đang diễn ra trực tiếp tại một Căn Cứ."""

    battle_id: int
    target_base_id: int
    target_base_name: str
    target_x: int = 0
    target_y: int = 0
    target_is_camp: bool = False
    next_round_left: int = 0
    server_id: int = 0
    attackers: list[str] = field(default_factory=list)
    is_pvp: Optional[bool] = None

    @property
    def battle_url(self) -> str:
        srv = self.server_id if self.server_id > 0 else 53
        return f"http://sg{srv}.dipan.com/battle/{self.battle_id}"

    def to_dict(self, now_epoch: Optional[float] = None) -> dict:  # noqa: ARG002
        return {
            "battle_id": self.battle_id,
            "target_base_id": self.target_base_id,
            "target_base_name": self.target_base_name,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "target_is_camp": self.target_is_camp,
            "next_round_left": self.next_round_left,
            "battle_url": self.battle_url,
            "attackers": list(self.attackers),
            "is_pvp": self.is_pvp,
        }


@dataclass
class AttackAlertEvent:
    """Sự kiện cảnh báo cần phát qua Thông Báo Đa Kênh."""

    stage: str  # "initial" | "urgent" | "battle"
    attack: Optional[IncomingAttack] = None
    battle: Optional[DefensiveBattle] = None


@dataclass
class AttackSnapshot:
    """Ảnh chụp quân tình tại một thời điểm kiểm tra."""

    checked_at_epoch: float = 0.0
    checked_at_monotonic: float = 0.0
    attacks: list[IncomingAttack] = field(default_factory=list)
    battles: list[DefensiveBattle] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.attacks) + len(self.battles)

    @property
    def under_attack(self) -> bool:
        return self.count > 0

    def to_dict(self, now_epoch: Optional[float] = None) -> dict:
        atk_dicts = [a.to_dict(now_epoch=now_epoch) for a in self.attacks]
        bat_dicts = [b.to_dict(now_epoch=now_epoch) for b in self.battles]
        earliest = min((a["remaining_seconds"] for a in atk_dicts), default=None)
        return {
            "count": len(atk_dicts) + len(bat_dicts),
            "under_attack": bool(atk_dicts or bat_dicts),
            "earliest_remaining_seconds": earliest,
            "attacks": atk_dicts,
            "battles": bat_dicts,
            "checked_at_epoch": self.checked_at_epoch,
        }


def parse_alarm_summary(resp41: Any) -> list[tuple[int, str, int, int, bool]]:
    """Phân tích phản hồi Common.ashx?id=41 (lCityCampID=0).

    Trả về danh sách (base_id, base_name, incoming_count, earliest_sec, is_fighting).
    """
    _check_captcha(resp41)
    if not isinstance(resp41, dict) or _safe_int(resp41.get("ret"), -1) != 0:
        return []
    infos = resp41.get("infos")
    if not isinstance(infos, list):
        return []
    out: list[tuple[int, str, int, int, bool]] = []
    for row in infos:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        base_id = _safe_int(row[0], 0)
        if base_id == 0:
            continue
        base_name = str(row[1] or f"Căn cứ {base_id}")
        lai_pham = row[2]
        incoming_count = 0
        earliest_sec = 0
        if isinstance(lai_pham, (list, tuple)) and len(lai_pham) >= 2:
            incoming_count = max(0, _safe_int(lai_pham[0], 0))
            earliest_sec = max(0, _safe_int(lai_pham[1], 0))
        is_fighting = len(row) > 9 and _safe_int(row[9], 0) == 1
        out.append((base_id, base_name, incoming_count, earliest_sec, is_fighting))
    return out


def parse_base_incoming(
    resp40: Any,
    *,
    target_base_id: int,
    target_base_name: str,
    target_x: int = 0,
    target_y: int = 0,
    target_is_camp: bool = False,
    server_id: int = 0,
    now_epoch: Optional[float] = None,
) -> tuple[list[IncomingAttack], list[DefensiveBattle]]:
    """Phân tích phản hồi Common.ashx?id=40 cho một Căn Cứ cụ thể.

    - Trong `come`: chỉ nhận `p[0] == 1` (Tấn công `攻击`).
    - Trong `battle`: chỉ nhận trận ngay tại căn cứ (`int(p[1]) == int(target_base_id)`),
      bỏ qua các trận đánh Man/Thảo Phạt ngoài dã ngoại.
    """
    _check_captcha(resp40)
    if not isinstance(resp40, dict) or _safe_int(resp40.get("ret"), -1) != 0:
        return [], []

    now = time.time() if now_epoch is None else float(now_epoch)
    attacks: list[IncomingAttack] = []
    for row in resp40.get("come") or []:
        if not isinstance(row, (list, tuple)) or len(row) < 13:
            continue
        move_type = _safe_int(row[0], 0)
        if move_type != 1:
            continue

        attacker_uid = _safe_int(row[1], 0)
        attacker_name = str(row[2] or "").strip()
        source_id = _safe_int(row[3], 0)
        source_name = str(row[4] or "").strip() or "Quân địch"
        source_x = _safe_int(row[5], 0)
        source_y = _safe_int(row[6], 0)

        generals: list[tuple[int, str]] = []
        raw_gens = row[7]
        if isinstance(raw_gens, (list, tuple)):
            for g in raw_gens:
                if isinstance(g, (list, tuple)) and len(g) >= 2:
                    generals.append((_safe_int(g[0], 0), str(g[1] or "").strip()))
                elif isinstance(g, (list, tuple)) and len(g) == 1:
                    generals.append((_safe_int(g[0], 0), ""))

        infantry = _safe_int(row[8], -1)
        cavalry = _safe_int(row[9], -1)
        archers = _safe_int(row[10], -1)
        siege = _safe_int(row[11], -1)
        rem_sec = max(0, _safe_int(row[12], 0))

        attacks.append(
            IncomingAttack(
                target_base_id=int(target_base_id),
                target_base_name=target_base_name,
                target_x=target_x,
                target_y=target_y,
                target_is_camp=target_is_camp,
                move_type=move_type,
                attacker_uid=attacker_uid,
                attacker_name=attacker_name,
                source_id=source_id,
                source_name=source_name,
                source_x=source_x,
                source_y=source_y,
                generals=generals,
                infantry=infantry,
                cavalry=cavalry,
                archers=archers,
                siege=siege,
                remaining_seconds=rem_sec,
                arrival_epoch=now + rem_sec,
            )
        )

    battles: list[DefensiveBattle] = []
    for row in resp40.get("battle") or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        bid = _safe_int(row[0], 0)
        b_city_id = _safe_int(row[1], 0)
        if bid <= 0 or b_city_id != int(target_base_id):
            continue
        next_left = max(0, _safe_int(row[5], 0)) if len(row) > 5 else 0
        battles.append(
            DefensiveBattle(
                battle_id=bid,
                target_base_id=int(target_base_id),
                target_base_name=target_base_name,
                target_x=target_x,
                target_y=target_y,
                target_is_camp=target_is_camp,
                next_round_left=next_left,
                server_id=int(server_id),
            )
        )

    return attacks, battles


@dataclass
class _TrackedMarch:
    signature: tuple[int, int, int, int, int]
    arrival_epoch: float
    initial_was_above_urgent: bool
    alerted_urgent: bool


class IncomingAttackMonitor:
    """Theo dõi quân tấn công theo phiên chạy với chống lặp theo chữ ký & cửa sổ thời gian."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tracked_marches: list[_TrackedMarch] = []
        self._notified_battle_ids: set[int] = set()
        self._last_snapshot = AttackSnapshot()

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._last_snapshot.count

    def get_snapshot(self) -> AttackSnapshot:
        with self._lock:
            return AttackSnapshot(
                checked_at_epoch=self._last_snapshot.checked_at_epoch,
                checked_at_monotonic=self._last_snapshot.checked_at_monotonic,
                attacks=list(self._last_snapshot.attacks),
                battles=list(self._last_snapshot.battles),
            )

    def serialize_snapshot(self, now_epoch: Optional[float] = None) -> dict:
        with self._lock:
            return self._last_snapshot.to_dict(now_epoch=now_epoch)

    def clear(self) -> None:
        with self._lock:
            self._tracked_marches.clear()
            self._notified_battle_ids.clear()
            self._last_snapshot = AttackSnapshot()

    reset = clear

    def next_check_delay(
        self,
        interval_minutes: int = 5,
        now_epoch: Optional[float] = None,
    ) -> float:
        """Tính thời gian chờ đến lần kiểm tra tiếp theo (giây).

        Giữ chu kỳ nền `interval_minutes` phút khi rảnh hoặc địch còn xa (> 5 phút),
        nhưng tự đánh thức sớm đúng mốc <= 5 phút và lúc chạm thành khi đang có địch hành quân.
        """
        base = float(max(1, min(60, int(interval_minutes))) * 60)
        now = time.time() if now_epoch is None else float(now_epoch)
        with self._lock:
            attacks = list(self._last_snapshot.attacks)
        if not attacks:
            return base

        target_delay = base
        for atk in attacks:
            rem = atk.current_remaining_seconds(now_epoch=now)
            if rem > URGENT_THRESHOLD_SECONDS:
                candidate = max(MIN_ATTACK_RECHECK_SECONDS, float(rem - (URGENT_THRESHOLD_SECONDS - 5)))
                target_delay = min(target_delay, candidate)
            elif rem > 0:
                candidate = max(MIN_ATTACK_RECHECK_SECONDS, float(rem + 5))
                target_delay = min(target_delay, candidate)
        return max(MIN_ATTACK_RECHECK_SECONDS, min(base, target_delay))

    def check_once(
        self,
        gateway: Any,
        *,
        roster: Any = None,
        server_id: int = 0,
        pvp_only: bool = False,
        now_epoch: Optional[float] = None,
        now_monotonic: Optional[float] = None,
    ) -> tuple[AttackSnapshot, list[AttackAlertEvent]]:
        """Thực hiện 1 lượt kiểm tra quân tình 2 tầng và trả (snapshot, danh sách cảnh báo mới)."""
        now_ep = time.time() if now_epoch is None else float(now_epoch)
        now_mono = time.monotonic() if now_monotonic is None else float(now_monotonic)
        srv_id = int(server_id or getattr(gateway, "server_id", 0) or 0)

        resp41 = gateway.call("Common.ashx", 41, {"lCityCampID": "0", "_": ""})
        _check_captcha(resp41)
        if not isinstance(resp41, dict) or _safe_int(resp41.get("ret"), -1) != 0:
            return self.get_snapshot(), []

        summary_rows = parse_alarm_summary(resp41)
        base_map: dict[int, Any] = {}
        if roster and getattr(roster, "bases", None):
            for b in roster.bases:
                base_map[int(b.id)] = b

        all_attacks: list[IncomingAttack] = []
        all_battles: list[DefensiveBattle] = []

        for base_id, base_name, incoming_count, _earliest_sec, is_fighting in summary_rows:
            if incoming_count <= 0 and not is_fighting:
                continue

            base_obj = base_map.get(base_id)
            b_name = getattr(base_obj, "name", "") or base_name
            b_x = _safe_int(getattr(base_obj, "pos_x", 0), 0)
            b_y = _safe_int(getattr(base_obj, "pos_y", 0), 0)
            b_camp = bool(getattr(base_obj, "is_camp", False) or base_id < 0)

            resp40 = gateway.call("Common.ashx", 40, {"tid": str(base_id), "_": ""})
            _check_captcha(resp40)
            if not isinstance(resp40, dict) or _safe_int(resp40.get("ret"), -1) != 0:
                continue

            atks, bats = parse_base_incoming(
                resp40,
                target_base_id=base_id,
                target_base_name=b_name,
                target_x=b_x,
                target_y=b_y,
                target_is_camp=b_camp,
                server_id=srv_id,
                now_epoch=now_ep,
            )

            # Fallback khi cờ p[9] == 1 mà battle[i][1] khác base_id -> xác minh atside == 2 qua Common.ashx?id=4
            if is_fighting and not bats:
                for brow in resp40.get("battle") or []:
                    if not isinstance(brow, (list, tuple)) or not brow:
                        continue
                    bid = _safe_int(brow[0], 0)
                    if bid <= 0:
                        continue
                    c4 = gateway.call("Common.ashx", 4, {"lBattleID": str(bid), "_": ""})
                    _check_captcha(c4)
                    if not isinstance(c4, dict) or _safe_int(c4.get("ret"), -1) != 0:
                        continue
                    if _safe_int(c4.get("atside"), 0) != 2:
                        continue
                    enemy_names = _extract_battle_attacker_names(c4.get("enemy"))
                    is_pvp_bat = _infer_battle_is_pvp(c4.get("enemy"))
                    next_left = max(0, _safe_int(brow[5], 0)) if len(brow) > 5 else _safe_int(c4.get("next_left"), 0)
                    bats.append(
                        DefensiveBattle(
                            battle_id=bid,
                            target_base_id=base_id,
                            target_base_name=b_name,
                            target_x=b_x,
                            target_y=b_y,
                            target_is_camp=b_camp,
                            next_round_left=next_left,
                            server_id=srv_id,
                            attackers=enemy_names,
                            is_pvp=is_pvp_bat,
                        )
                    )

            # Bổ sung danh sách chủ công địch cho trận phòng thủ nếu cần phân biệt PvP/NPC
            if bats:
                for bat in bats:
                    if bat.is_pvp is not None:
                        continue
                    c4 = gateway.call("Common.ashx", 4, {"lBattleID": str(bat.battle_id), "_": ""})
                    _check_captcha(c4)
                    if isinstance(c4, dict) and _safe_int(c4.get("ret"), -1) == 0:
                        bat.attackers = _extract_battle_attacker_names(c4.get("enemy"))
                        bat.is_pvp = _infer_battle_is_pvp(c4.get("enemy"))

            if pvp_only:
                atks = [a for a in atks if a.is_pvp]
                bats = [b for b in bats if b.is_pvp is not False]

            all_attacks.extend(atks)
            all_battles.extend(bats)

        all_attacks.sort(key=lambda a: a.current_remaining_seconds(now_epoch=now_ep))

        with self._lock:
            events = self._reconcile_events_locked(all_attacks, all_battles, now_ep)
            self._last_snapshot = AttackSnapshot(
                checked_at_epoch=now_ep,
                checked_at_monotonic=now_mono,
                attacks=all_attacks,
                battles=all_battles,
            )
            snapshot = AttackSnapshot(
                checked_at_epoch=now_ep,
                checked_at_monotonic=now_mono,
                attacks=list(all_attacks),
                battles=list(all_battles),
            )
        return snapshot, events

    def _reconcile_events_locked(
        self,
        attacks: list[IncomingAttack],
        battles: list[DefensiveBattle],
        now_ep: float,
    ) -> list[AttackAlertEvent]:
        events: list[AttackAlertEvent] = []
        used_indices: set[int] = set()
        next_tracked: list[_TrackedMarch] = []

        for atk in attacks:
            rem = atk.current_remaining_seconds(now_epoch=now_ep)
            sig = atk.signature
            best_idx: Optional[int] = None
            best_diff = ARRIVAL_MATCH_TOLERANCE_SECONDS + 1.0

            for idx, tm in enumerate(self._tracked_marches):
                if idx in used_indices or tm.signature != sig:
                    continue
                diff = abs(tm.arrival_epoch - atk.arrival_epoch)
                if diff <= ARRIVAL_MATCH_TOLERANCE_SECONDS and diff < best_diff:
                    best_diff = diff
                    best_idx = idx

            if best_idx is None:
                is_urgent = rem <= URGENT_THRESHOLD_SECONDS
                tm_new = _TrackedMarch(
                    signature=sig,
                    arrival_epoch=atk.arrival_epoch,
                    initial_was_above_urgent=not is_urgent,
                    alerted_urgent=is_urgent,
                )
                next_tracked.append(tm_new)
                events.append(AttackAlertEvent(stage="urgent" if is_urgent else "initial", attack=atk))
            else:
                used_indices.add(best_idx)
                tm_old = self._tracked_marches[best_idx]
                tm_old.arrival_epoch = atk.arrival_epoch
                if tm_old.initial_was_above_urgent and not tm_old.alerted_urgent and rem <= URGENT_THRESHOLD_SECONDS:
                    tm_old.alerted_urgent = True
                    events.append(AttackAlertEvent(stage="urgent", attack=atk))
                next_tracked.append(tm_old)

        # Giữ lại các đợt vừa biến mất nhưng chưa quá giờ tới dự kiến + 120s (tránh mất dấu khi lag mạng ngắn),
        # ngược lại dọn sạch để đợt sau không bị sót.
        for idx, tm in enumerate(self._tracked_marches):
            if idx in used_indices:
                continue
            if now_ep <= tm.arrival_epoch + 120.0:
                next_tracked.append(tm)

        self._tracked_marches = next_tracked

        active_bids = {b.battle_id for b in battles}
        self._notified_battle_ids &= active_bids
        for bat in battles:
            if bat.battle_id not in self._notified_battle_ids:
                self._notified_battle_ids.add(bat.battle_id)
                events.append(AttackAlertEvent(stage="battle", battle=bat))

        return events


def _extract_battle_attacker_names(enemy_rows: Any) -> list[str]:
    if not isinstance(enemy_rows, list):
        return []
    names: list[str] = []
    for row in enemy_rows:
        if not isinstance(row, (list, tuple)):
            continue
        owner = str(row[6] or "").strip() if len(row) > 6 else ""
        site = str(row[2] or "").strip() if len(row) > 2 else ""
        label = owner or site
        if label and label not in names:
            names.append(label)
    return names


def _infer_battle_is_pvp(enemy_rows: Any) -> Optional[bool]:
    if not isinstance(enemy_rows, list) or not enemy_rows:
        return None
    has_owner = any(
        isinstance(row, (list, tuple)) and len(row) > 6 and bool(str(row[6] or "").strip())
        for row in enemy_rows
    )
    return has_owner
