"""Nhiệm vụ Đào Tạo Tướng (Điểm Tướng Đài & Tụ Hiền Lâu — lặp lại mỗi 24 giờ, Server 58+).

Xác minh trực tiếp từ `adapter.js` (`_p_marketPassthrough`), `Build/officialgeneral.js`
và máy chủ thực tế (`sg58.dipan.com`, tài khoản `quilia`):
- Phân hệ:
  + `TRAIN_TYPE_VAN = 1`: Tụ Hiền Lâu (`聚贤楼`) / Mạc Liêu Để (`幕僚邸`) — Văn quan (`role == "van"`).
  + `TRAIN_TYPE_VO = 2`: Điểm Tướng Đài (`点将台`) / Tướng Soái Phủ (`将帅府`) — Võ tướng (`role == "vo"`).
- Đọc trạng thái ô đào tạo: `POST /GateWay/Common.ashx?id=141` (`lType`, `tid` > 0).
  Trả về `slots` (0..5), `list` (`[[pos, remaining_seconds, hero_id, img_id, hero_name], ...]`),
  `hero` (tướng trong thành `tid`). Trạng thái ô đào tạo là cấp tài khoản (dùng chung mọi Thành).
- Kích hoạt đào tạo tướng: `POST /GateWay/OPT.ashx?id=178` (`lType`, `lPos=1..5`, `lHeroID`, tùy chọn `tid`).
  Nhận `exp` ngay và ô vào thời gian hồi 24 giờ (86.400 giây); hỗ trợ xuyên thành và tướng đang bận.
  Không bao giờ tự gọi `OPT.ashx?id=177` (tốn `slots * 50` Nguyên bảo mở thêm ô).
"""

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Optional

from ..gateway import GatewayClient
from ..roster import General, Roster
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired

TRAIN_TYPE_VAN = 1
TRAIN_TYPE_VO = 2
ALL_TRAIN_TYPES: tuple[int, ...] = (TRAIN_TYPE_VO, TRAIN_TYPE_VAN)
MAX_TRAIN_SLOTS = 5

TRAIN_ROLE_TO_TYPE: dict[str, int] = {
    "van": TRAIN_TYPE_VAN,
    "vo": TRAIN_TYPE_VO,
}

TRAIN_TYPE_TO_ROLE: dict[int, str] = {
    TRAIN_TYPE_VAN: "van",
    TRAIN_TYPE_VO: "vo",
}

TRAIN_TYPE_LABELS: dict[int, str] = {
    TRAIN_TYPE_VAN: "Tụ Hiền Lâu (Văn quan)",
    TRAIN_TYPE_VO: "Điểm Tướng Đài (Võ tướng)",
}

TRAINING_ERROR_MESSAGES: dict[int, str] = {
    1: "Ô đào tạo đang bận hoặc chưa mở khóa",
    4: "Mã Thành không hợp lệ",
    20: "Tướng không tồn tại hoặc không hợp lệ",
    40: "Tướng đang bận",
    73: "Máy chủ yêu cầu mã xác thực Captcha",
    110: "Máy chủ yêu cầu mã xác thực Captcha",
    315: "Tướng đã đạt cấp độ tối đa",
    316: "Tướng hiện không thể đào tạo (trọng thương/dưỡng thương/đấu giá/phụ thể)",
    198599: "Phiên đăng nhập đã hết hạn",
}

_HERO_LEVEL_SKIP_RETS = frozenset({315, 316, 40, 20})
_TEMP_RETRY_RETS = frozenset({316, 40})


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _dedup_positive_ids(raw_ids: Any) -> list[int]:
    if not isinstance(raw_ids, (list, tuple)):
        return []
    out: list[int] = []
    seen: set[int] = set()
    for item in raw_ids:
        val = _to_int(item, 0)
        if val > 0 and val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _format_ret_message(ret: int, resp: Optional[dict[str, Any]] = None) -> str:
    err_msg = ""
    if isinstance(resp, dict):
        err_msg = str(resp.get("errMsg") or "").strip()
    if ret in TRAINING_ERROR_MESSAGES:
        base = TRAINING_ERROR_MESSAGES[ret]
        return f"{base} ({err_msg})" if err_msg else base
    if err_msg:
        return f"Lỗi ret={ret}: {err_msg}"
    return f"Mã lỗi {ret}"


def resolve_training_city_id(
    roster: Optional[Roster],
    fallback_city_id: Optional[int] = None,
) -> Optional[int]:
    """Lấy ID một Thành hợp lệ (> 0) dùng để truy vấn Common.ashx?id=141."""
    if roster is not None:
        for city in getattr(roster, "cities", ()) or ():
            cid = _to_int(getattr(city, "id", 0), 0)
            if cid > 0:
                return cid
        for base in getattr(roster, "bases", ()) or ():
            cid = _to_int(getattr(base, "id", 0), 0)
            if cid > 0:
                return cid
    fb = _to_int(fallback_city_id, 0)
    return fb if fb > 0 else None


@dataclass
class TrainSlotStatus:
    pos: int
    unlocked: bool
    remaining_seconds: int = 0
    hero_id: int = 0
    img_id: int = 0
    hero_name: str = ""

    def effective_remaining(self, elapsed: int = 0) -> int:
        if self.remaining_seconds <= 0:
            return 0
        return max(0, int(self.remaining_seconds) - max(0, int(elapsed)))

    def to_dict(self, elapsed: int = 0) -> dict[str, Any]:
        rem = self.effective_remaining(elapsed)
        active = self.unlocked and rem > 0
        return {
            "pos": self.pos,
            "unlocked": self.unlocked,
            "remaining_seconds": rem,
            "hero_id": self.hero_id if active else 0,
            "img_id": self.img_id if active else 0,
            "hero_name": self.hero_name if active else "",
        }


@dataclass
class TrainingHallState:
    train_type: int
    unlocked_slots: int
    slots: list[TrainSlotStatus]
    checked_at: float

    def active_hero_ids(self, elapsed: int = 0) -> set[int]:
        return {
            s.hero_id
            for s in self.slots
            if s.unlocked and s.effective_remaining(elapsed) > 0 and s.hero_id > 0
        }

    def free_slots(self, elapsed: int = 0) -> list[TrainSlotStatus]:
        return [
            s
            for s in self.slots
            if s.unlocked and s.effective_remaining(elapsed) <= 0
        ]

    def min_active_remaining(self, elapsed: int = 0) -> int:
        active_rems = [
            s.effective_remaining(elapsed)
            for s in self.slots
            if s.unlocked and s.effective_remaining(elapsed) > 0
        ]
        return min(active_rems) if active_rems else 0

    def to_dict(self, now_mono: Optional[float] = None) -> dict[str, Any]:
        cur = time.monotonic() if now_mono is None else float(now_mono)
        elapsed = max(0, int(cur - self.checked_at))
        return {
            "train_type": self.train_type,
            "label": TRAIN_TYPE_LABELS.get(self.train_type, f"Loại {self.train_type}"),
            "unlocked_slots": self.unlocked_slots,
            "slots": [s.to_dict(elapsed) for s in self.slots],
            "free_count": len(self.free_slots(elapsed)),
            "next_ready_seconds": self.min_active_remaining(elapsed),
        }


@dataclass(frozen=True)
class TrainAttemptResult:
    train_type: int
    pos: int
    hero_id: int
    hero_name: str
    success: bool
    ret: int
    exp: int
    message: str


@dataclass
class TrainingCycleSummary:
    trained: list[TrainAttemptResult] = field(default_factory=list)
    skipped: list[int] = field(default_factory=list)
    failed: list[TrainAttemptResult] = field(default_factory=list)
    states: dict[int, TrainingHallState] = field(default_factory=dict)
    next_check_seconds: float = 3600.0


def fetch_training_state(
    gateway: GatewayClient,
    train_type: int,
    city_id: int,
) -> TrainingHallState:
    """Đọc trạng thái 5 ô đào tạo của Điểm Tướng Đài (2) hoặc Tụ Hiền Lâu (1) trên S58+."""
    ttype = int(train_type)
    if ttype not in (TRAIN_TYPE_VAN, TRAIN_TYPE_VO):
        raise ValueError(f"Loại đào tạo không hợp lệ: {train_type}")
    cid = int(city_id)
    if cid <= 0:
        raise ValueError("Cần ID Thành hợp lệ (> 0) để truy vấn trạng thái đào tạo.")

    resp = gateway.call("Common.ashx", 141, {"lType": str(ttype), "tid": str(cid), "_": ""})
    if not isinstance(resp, dict):
        raise RuntimeError("Không nhận được phản hồi hợp lệ từ Common.ashx?id=141.")

    ret = _to_int(resp.get("ret"), -1)
    if ret in (110, RET_CAPTCHA_REQUIRED):
        raise CaptchaRequired()
    if ret != RET_OK:
        detail = _format_ret_message(ret, resp)
        raise RuntimeError(f"Đọc trạng thái đào tạo thất bại (ret={ret}): {detail}")

    unlocked_slots = max(0, min(MAX_TRAIN_SLOTS, _to_int(resp.get("slots"), 0)))
    slot_map: dict[int, TrainSlotStatus] = {
        pos: TrainSlotStatus(pos=pos, unlocked=(pos <= unlocked_slots))
        for pos in range(1, MAX_TRAIN_SLOTS + 1)
    }

    for item in resp.get("list") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            pos = _to_int(item[0], 0)
            if 1 <= pos <= MAX_TRAIN_SLOTS:
                rem = max(0, _to_int(item[1], 0))
                hid = _to_int(item[2], 0)
                img_id = _to_int(item[3], 0) if len(item) > 3 else 0
                hname = str(item[4]) if len(item) > 4 and item[4] is not None else ""
                slot_map[pos] = TrainSlotStatus(
                    pos=pos,
                    unlocked=(pos <= unlocked_slots or rem > 0),
                    remaining_seconds=rem,
                    hero_id=hid,
                    img_id=img_id,
                    hero_name=hname,
                )

    return TrainingHallState(
        train_type=ttype,
        unlocked_slots=unlocked_slots,
        slots=[slot_map[pos] for pos in range(1, MAX_TRAIN_SLOTS + 1)],
        checked_at=time.monotonic(),
    )


def start_general_training(
    gateway: GatewayClient,
    train_type: int,
    pos: int,
    hero_id: int,
    city_id: Optional[int] = None,
) -> tuple[bool, int, int, str]:
    """Gửi lệnh đào tạo tướng qua OPT.ashx?id=178. Trả về (ok, ret, exp, message)."""
    ttype = int(train_type)
    if ttype not in (TRAIN_TYPE_VAN, TRAIN_TYPE_VO):
        raise ValueError(f"Loại đào tạo không hợp lệ: {train_type}")
    slot_pos = int(pos)
    if not (1 <= slot_pos <= MAX_TRAIN_SLOTS):
        raise ValueError(f"Vị trí ô đào tạo không hợp lệ: {pos}")
    hid = int(hero_id)
    if hid <= 0:
        raise ValueError(f"Mã tướng không hợp lệ: {hero_id}")

    payload: dict[str, str] = {
        "lType": str(ttype),
        "lPos": str(slot_pos),
        "lHeroID": str(hid),
        "_": "",
    }
    if city_id is not None and int(city_id) > 0:
        payload["tid"] = str(int(city_id))

    resp = gateway.call("OPT.ashx", 178, payload)
    if not isinstance(resp, dict):
        return False, -1, 0, "Không nhận được phản hồi hợp lệ từ máy chủ"

    ret = _to_int(resp.get("ret"), -1)
    if ret in (110, RET_CAPTCHA_REQUIRED):
        raise CaptchaRequired()
    if ret == RET_OK:
        exp = max(0, _to_int(resp.get("exp"), 0))
        return True, RET_OK, exp, "Thành công"

    return False, ret, 0, _format_ret_message(ret, resp)


def compute_next_training_check_seconds(
    states: dict[int, TrainingHallState],
    vo_general_ids: list[int],
    van_general_ids: list[int],
    failed_results: list[TrainAttemptResult],
    *,
    max_poll_seconds: float = 3600.0,
    retry_temp_error_seconds: float = 300.0,
) -> float:
    """Tính thời gian chờ đến lần kiểm tra kế tiếp mà không spam API khi ô/tướng đang hồi."""
    max_poll = max(10.0, float(max_poll_seconds))
    temp_retry = max(10.0, float(retry_temp_error_seconds))
    candidates: list[float] = []

    configured_by_type = {
        TRAIN_TYPE_VO: _dedup_positive_ids(vo_general_ids),
        TRAIN_TYPE_VAN: _dedup_positive_ids(van_general_ids),
    }

    for ttype, state in states.items():
        cfg_ids = configured_by_type.get(ttype, [])
        if not cfg_ids or state.unlocked_slots <= 0:
            continue

        min_rem = state.min_active_remaining()
        if min_rem > 0:
            candidates.append(min(float(min_rem) + 2.0, max_poll))

        has_temp_fail = any(
            r.train_type == ttype and r.ret in _TEMP_RETRY_RETS
            for r in failed_results
        )
        if has_temp_fail and state.free_slots():
            candidates.append(min(temp_retry, max_poll))

    return min(candidates) if candidates else max_poll


def _build_general_lookup(roster: Optional[Roster]) -> dict[int, General]:
    lookup: dict[int, General] = {}
    if roster is None:
        return lookup
    for base in getattr(roster, "bases", ()) or ():
        for gen in roster.generals_of(base.id):
            lookup.setdefault(gen.id, gen)
    return lookup


def run_training_cycle(
    gateway: GatewayClient,
    city_id: int,
    vo_general_ids: list[int],
    van_general_ids: list[int],
    *,
    roster: Optional[Roster] = None,
    on_log: Optional[Callable[[str], None]] = None,
    types_to_run: tuple[int, ...] = ALL_TRAIN_TYPES,
) -> TrainingCycleSummary:
    """Kiểm tra trạng thái các ô đào tạo và tự động đào tạo các tướng ưu tiên vào ô trống."""
    summary = TrainingCycleSummary()
    gen_lookup = _build_general_lookup(roster)
    cid = _to_int(city_id, 0)
    configured_by_type = {
        TRAIN_TYPE_VO: _dedup_positive_ids(vo_general_ids),
        TRAIN_TYPE_VAN: _dedup_positive_ids(van_general_ids),
    }

    def _emit(msg: str) -> None:
        if on_log:
            on_log(msg)

    for ttype in types_to_run:
        if ttype not in (TRAIN_TYPE_VAN, TRAIN_TYPE_VO):
            continue
        label = TRAIN_TYPE_LABELS.get(ttype, f"Loại {ttype}")
        expected_role = TRAIN_TYPE_TO_ROLE[ttype]
        configured = configured_by_type.get(ttype, [])

        state = fetch_training_state(gateway, ttype, cid)
        summary.states[ttype] = state

        if not configured:
            continue

        free_slots = state.free_slots()
        if not free_slots:
            continue

        active_ids = state.active_hero_ids()
        candidates: list[tuple[int, str]] = []
        for gid in configured:
            if gid in active_ids:
                summary.skipped.append(gid)
                continue
            gen = gen_lookup.get(gid)
            if roster is not None:
                if gen is None or gen.role != expected_role:
                    summary.skipped.append(gid)
                    continue
                gname = gen.name
            else:
                gname = gen.name if gen is not None else f"Tướng #{gid}"
            candidates.append((gid, gname))

        if not candidates:
            continue

        failed_ids: set[int] = set()
        trained_any = False

        for slot in free_slots:
            for gid, gname in candidates:
                if gid in active_ids or gid in failed_ids:
                    continue
                ok, ret, exp, msg = start_general_training(
                    gateway,
                    ttype,
                    slot.pos,
                    gid,
                    city_id=cid if cid > 0 else None,
                )
                attempt = TrainAttemptResult(
                    train_type=ttype,
                    pos=slot.pos,
                    hero_id=gid,
                    hero_name=gname,
                    success=ok,
                    ret=ret,
                    exp=exp,
                    message=msg,
                )
                if ok:
                    trained_any = True
                    active_ids.add(gid)
                    summary.trained.append(attempt)
                    _emit(f"🎓 [{label}] Ô {slot.pos}: Đào tạo {gname} thành công (+{exp:,} kinh nghiệm)!")
                    break

                summary.failed.append(attempt)
                if ret in _HERO_LEVEL_SKIP_RETS:
                    failed_ids.add(gid)
                    _emit(f"⚠️ [{label}] Ô {slot.pos}: {gname} không thể đào tạo ({msg}) — chuyển sang tướng kế tiếp.")
                    continue

                _emit(f"⚠️ [{label}] Ô {slot.pos}: Đào tạo {gname} thất bại ({msg}).")
                break

        if trained_any:
            summary.states[ttype] = fetch_training_state(gateway, ttype, cid)

    summary.next_check_seconds = compute_next_training_check_seconds(
        summary.states,
        configured_by_type[TRAIN_TYPE_VO],
        configured_by_type[TRAIN_TYPE_VAN],
        summary.failed,
    )
    return summary
