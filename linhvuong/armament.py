"""Đồng Bộ Quân Giới: sao chép cấu hình Quân Giới & Trận hình từ một Võ tướng mẫu (ADR-0039).

Công cụ độc lập theo yêu cầu, không lưu vào Hồ Sơ và không gắn vào Thảo Phạt / Bình Man / Gọi Man.

API Server 58:
- Đọc:  Common.ashx?id=12 (lGeneralID, lCityID) -> infantry_equip / cavalry_equip / bowman_equip /
        mangonel / battle_array / ratio_* / withdraw_*.
- Ghi quân giới: OPT.ashx?id=56 (lGeneralID, lInfantryEID1..3, lCavalryEID1..3, lBowmanEID1..3, lMangonelEID).
- Ghi trận hình: OPT.ashx?id=57 (lGeneralID, lRatioAttack, lRatioPK, lRatioStra, lBattleArray,
        lWithdrawLoss, lWithdrawMorale).
"""

import threading
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional

from .gateway import GatewayClient
from .roster import General, Roster

SCOPE_INFANTRY = "infantry"
SCOPE_CAVALRY = "cavalry"
SCOPE_BOWMAN = "bowman"
SCOPE_MANGONEL = "mangonel"
ALL_SCOPES: tuple[str, ...] = (SCOPE_INFANTRY, SCOPE_CAVALRY, SCOPE_BOWMAN, SCOPE_MANGONEL)
SCOPE_NAMES = {
    SCOPE_INFANTRY: "Bộ binh",
    SCOPE_CAVALRY: "Kỵ binh",
    SCOPE_BOWMAN: "Cung binh",
    SCOPE_MANGONEL: "Xe ném đá",
}

ARMAMENT_ERROR_MESSAGES = {
    1: "Thao tác thất bại, vui lòng thử lại sau",
    2: "Không hợp lệ (ID người dùng)",
    20: "Tướng không thuộc căn cứ này",
    40: "Tướng đang bận",
    42: "Kho quân giới của Thành không đủ quân giới của tướng mẫu",
    71: "Tướng đã có lính, bắt buộc phải có quân giới chính (ô 1)",
}


@dataclass(frozen=True)
class ArmamentSnapshot:
    """Cấu hình Quân Giới & tác chiến hiện tại của một Võ tướng."""

    infantry: tuple[int, int, int] = (0, 0, 0)
    cavalry: tuple[int, int, int] = (0, 0, 0)
    bowman: tuple[int, int, int] = (0, 0, 0)
    mangonel: int = 0
    battle_array: int = 1
    ratio_attack: int = 40
    ratio_pk: int = 30
    ratio_stratagem: int = 30
    withdraw_loss: int = 30
    withdraw_morale: int = 30
    names: dict[int, str] = field(default_factory=dict, compare=False)

    def label(self, scope: str) -> str:
        eids = self.eids(scope)
        main = eids[0]
        return self.names.get(main, str(main)) if main else "-"

    def eids(self, scope: str) -> tuple[int, ...]:
        if scope == SCOPE_MANGONEL:
            return (self.mangonel,)
        return getattr(self, scope)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _triple(block: Any, names: dict[int, str]) -> tuple[int, int, int]:
    """infantry_equip = [quân_số, eid1, name1, eid2, name2, eid3, name3, ...]."""
    if not isinstance(block, (list, tuple)):
        return (0, 0, 0)
    out: list[int] = []
    for idx in (1, 3, 5):
        eid = _to_int(block[idx]) if len(block) > idx else 0
        out.append(eid)
        if eid and len(block) > idx + 1 and block[idx + 1]:
            names[eid] = str(block[idx + 1])
    return (out[0], out[1], out[2])


def parse_armament(resp: Optional[dict]) -> Optional[ArmamentSnapshot]:
    """Chuyển phản hồi Common.ashx?id=12 thành ArmamentSnapshot (None nếu lỗi)."""
    if not isinstance(resp, dict) or _to_int(resp.get("ret"), -1) != 0:
        return None
    names: dict[int, str] = {}
    infantry = _triple(resp.get("infantry_equip"), names)
    cavalry = _triple(resp.get("cavalry_equip"), names)
    bowman = _triple(resp.get("bowman_equip"), names)
    mang_raw = resp.get("mangonel")
    mangonel = 0
    if isinstance(mang_raw, (list, tuple)) and mang_raw:
        mangonel = _to_int(mang_raw[0])
        if mangonel and len(mang_raw) > 1 and mang_raw[1]:
            names[mangonel] = str(mang_raw[1])
    return ArmamentSnapshot(
        infantry=infantry,
        cavalry=cavalry,
        bowman=bowman,
        mangonel=mangonel,
        battle_array=_to_int(resp.get("battle_array"), 1),
        ratio_attack=_to_int(resp.get("ratio_attack"), 40),
        ratio_pk=_to_int(resp.get("ratio_PK"), 30),
        ratio_stratagem=_to_int(resp.get("ratio_stratagem"), 30),
        withdraw_loss=_to_int(resp.get("withdraw_loss"), 30),
        withdraw_morale=_to_int(resp.get("withdraw_morale"), 30),
        names=names,
    )


def fetch_armament(gateway: GatewayClient, general_id: int, base_id: int) -> Optional[ArmamentSnapshot]:
    resp = gateway.call(
        "Common.ashx",
        12,
        {"lGeneralID": str(int(general_id)), "lCityID": str(int(base_id)), "_": ""},
    )
    return parse_armament(resp)


def normalize_scopes(scopes: Optional[Any]) -> tuple[str, ...]:
    if scopes is None:
        return ALL_SCOPES
    return tuple(s for s in ALL_SCOPES if s in set(scopes))


def merge_armament(
    current: ArmamentSnapshot, template: ArmamentSnapshot, scopes: Any
) -> ArmamentSnapshot:
    """Lấy các binh chủng được tích từ mẫu, giữ nguyên binh chủng còn lại của tướng đích."""
    chosen = set(normalize_scopes(scopes))
    merged = current
    names = dict(current.names)
    for scope in ALL_SCOPES:
        if scope not in chosen:
            continue
        names.update({e: template.names[e] for e in template.eids(scope) if e in template.names})
        if scope == SCOPE_MANGONEL:
            merged = replace(merged, mangonel=template.mangonel)
        else:
            merged = replace(merged, **{scope: getattr(template, scope)})
    return replace(merged, names=names)


def armament_matches(
    current: ArmamentSnapshot,
    template: ArmamentSnapshot,
    scopes: Any,
    sync_formation: bool = False,
) -> bool:
    for scope in normalize_scopes(scopes):
        if current.eids(scope) != template.eids(scope):
            return False
    if sync_formation and current.battle_array != template.battle_array:
        return False
    return True


def _result(resp: Optional[dict]) -> tuple[bool, int]:
    if not isinstance(resp, dict):
        return False, -1
    ret = _to_int(resp.get("ret"), -1)
    return ret == 0, ret


def set_general_armament(
    gateway: GatewayClient, general_id: int, snap: ArmamentSnapshot
) -> tuple[bool, int]:
    """Ghi 10 ô quân giới qua OPT.ashx?id=56."""
    payload = {
        "lGeneralID": str(int(general_id)),
        "lInfantryEID1": str(snap.infantry[0]),
        "lInfantryEID2": str(snap.infantry[1]),
        "lInfantryEID3": str(snap.infantry[2]),
        "lCavalryEID1": str(snap.cavalry[0]),
        "lCavalryEID2": str(snap.cavalry[1]),
        "lCavalryEID3": str(snap.cavalry[2]),
        "lBowmanEID1": str(snap.bowman[0]),
        "lBowmanEID2": str(snap.bowman[1]),
        "lBowmanEID3": str(snap.bowman[2]),
        "lMangonelEID": str(snap.mangonel),
        "_": "",
    }
    return _result(gateway.call("OPT.ashx", 56, payload))


def set_general_formation(
    gateway: GatewayClient, general_id: int, snap: ArmamentSnapshot, battle_array: int
) -> tuple[bool, int]:
    """Ghi Trận hình qua OPT.ashx?id=57, giữ nguyên tỷ lệ đánh và ngưỡng rút quân của tướng."""
    payload = {
        "lGeneralID": str(int(general_id)),
        "lRatioAttack": str(snap.ratio_attack),
        "lRatioPK": str(snap.ratio_pk),
        "lRatioStra": str(snap.ratio_stratagem),
        "lBattleArray": str(int(battle_array)),
        "lWithdrawLoss": str(snap.withdraw_loss),
        "lWithdrawMorale": str(snap.withdraw_morale),
        "_": "",
    }
    return _result(gateway.call("OPT.ashx", 57, payload))


@dataclass
class ArmamentSyncSummary:
    synced: int = 0
    skipped_same: int = 0
    skipped_busy: int = 0
    skipped_template: int = 0
    failed: int = 0
    stopped: bool = False


def _emit(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if cb:
        cb(msg)


def _error_text(ret: int) -> str:
    return ARMAMENT_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")


def find_general_base(roster: Roster, general_id: int) -> Optional[tuple[int, General]]:
    for base in roster.bases:
        for gen in roster.generals_of(base.id):
            if gen.id == general_id:
                return base.id, gen
    return None


def sync_armament(
    gateway: GatewayClient,
    roster: Roster,
    template_general_id: int,
    target_general_ids: list[int],
    scopes: Any = ALL_SCOPES,
    sync_formation: bool = False,
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> ArmamentSyncSummary:
    """Nhân bản Quân Giới (và Trận hình nếu chọn) từ Võ tướng mẫu sang các Võ tướng đích."""
    summary = ArmamentSyncSummary()
    chosen = normalize_scopes(scopes)
    if not chosen and not sync_formation:
        _emit(on_log, "⚠️ Chưa chọn binh chủng hoặc Trận hình để đồng bộ.")
        return summary

    located = find_general_base(roster, int(template_general_id))
    if located is None:
        _emit(on_log, "❌ Không tìm thấy Võ tướng mẫu trong danh sách.")
        summary.failed += 1
        return summary
    template_base_id, template_gen = located
    template = fetch_armament(gateway, template_gen.id, template_base_id)
    if template is None:
        _emit(on_log, f"❌ Không đọc được cấu hình quân giới của tướng mẫu {template_gen.name}.")
        summary.failed += 1
        return summary
    _emit(on_log, f"📋 Tướng mẫu {template_gen.name}: " + describe_armament(template))

    seen: set[int] = set()
    for gid in target_general_ids:
        if stop_event is not None and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "⏹ Đã dừng đồng bộ quân giới.")
            return summary
        gid = int(gid)
        if gid in seen:
            continue
        seen.add(gid)
        if gid == template_gen.id:
            summary.skipped_template += 1
            continue
        found = find_general_base(roster, gid)
        if found is None:
            summary.failed += 1
            _emit(on_log, f"   ❌ Không tìm thấy tướng {gid}.")
            continue
        base_id, gen = found
        if gen.role != "vo":
            continue
        if gen.status != 0:
            summary.skipped_busy += 1
            _emit(on_log, f"   ⚠️ Bỏ qua {gen.name}: đang bận ({gen.status_text}).")
            continue

        current = fetch_armament(gateway, gen.id, base_id)
        if current is None:
            summary.failed += 1
            _emit(on_log, f"   ❌ {gen.name}: không đọc được cấu hình hiện tại.")
            continue
        if armament_matches(current, template, chosen, sync_formation):
            summary.skipped_same += 1
            _emit(on_log, f"   ✅ {gen.name}: đã khớp tướng mẫu.")
            continue

        ok_all = True
        merged = merge_armament(current, template, chosen)
        if chosen and any(current.eids(s) != template.eids(s) for s in chosen):
            ok, ret = set_general_armament(gateway, gen.id, merged)
            if not ok:
                ok_all = False
                _emit(on_log, f"   ❌ {gen.name}: ghi quân giới thất bại ({_error_text(ret)}).")
        if ok_all and sync_formation and current.battle_array != template.battle_array:
            ok, ret = set_general_formation(gateway, gen.id, current, template.battle_array)
            if not ok:
                ok_all = False
                _emit(on_log, f"   ❌ {gen.name}: ghi Trận hình thất bại ({_error_text(ret)}).")
        if ok_all:
            summary.synced += 1
            _emit(on_log, f"   🔄 {gen.name}: đã đồng bộ theo tướng mẫu.")
        else:
            summary.failed += 1
    return summary


def describe_armament(snap: ArmamentSnapshot) -> str:
    parts = [f"{SCOPE_NAMES[s]}: {snap.label(s)}" for s in ALL_SCOPES]
    parts.append(f"Trận hình: {snap.battle_array}")
    return " | ".join(parts)
