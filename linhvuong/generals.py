"""Dịch vụ quản lý Văn quan & Võ tướng: Ban thưởng Lòng trung thành và Thiết lập Mưu sĩ."""

from dataclasses import dataclass, field
import threading
from typing import Callable, Optional

from .gateway import GatewayClient
from .roster import General, Roster, fetch_roster
from .troops import ERROR_MESSAGES as TROOP_ERROR_MESSAGES

TACTICIAN_ERROR_MESSAGES = {
    **TROOP_ERROR_MESSAGES,
    10020: "Văn quan không tồn tại",
    10021: "Võ tướng không tồn tại",
    10022: "Văn quan đang bận",
    10023: "Không cùng thành",
    10024: "Võ tướng đã có mưu sĩ",
}

MODE_BY_LEVEL = "by_level"
MODE_BY_NAME = "by_name"
MODE_SEQUENTIAL = "sequential"
MODE_REMOVE = "remove"
VALID_TACTICIAN_MODES = (MODE_BY_LEVEL, MODE_BY_NAME, MODE_SEQUENTIAL, MODE_REMOVE)


def _emit(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if cb:
        cb(msg)


def _emit_progress(cb: Optional[Callable[[int, int], None]], done: int, total: int) -> None:
    if cb:
        cb(done, total)


def reward_money_needed(level: int, loyalty: int) -> int:
    """Tính số Vàng cần để ban thưởng khôi phục Lòng trung thành về 100."""
    if loyalty >= 100 or level <= 0:
        return 0
    return (100 - int(loyalty)) * int(level) * 10


@dataclass(frozen=True)
class RewardTarget:
    city_id: int
    city_name: str
    general: General
    money_needed: int


@dataclass
class RewardSummary:
    total: int = 0
    success: int = 0
    failed: int = 0
    total_gold_spent: int = 0
    stopped: bool = False
    details: list[str] = field(default_factory=list)


def collect_reward_targets(roster: Roster) -> list[RewardTarget]:
    """Lọc toàn bộ Văn quan và Võ tướng ở mọi căn cứ có Lòng trung thành < 100."""
    targets: list[RewardTarget] = []
    seen_ids: set[int] = set()
    for base in roster.bases:
        for gen in roster.generals_of(base.id):
            if gen.id in seen_ids or gen.loyalty >= 100:
                continue
            seen_ids.add(gen.id)
            money = reward_money_needed(gen.level, gen.loyalty)
            targets.append(
                RewardTarget(
                    city_id=base.id,
                    city_name=base.name,
                    general=gen,
                    money_needed=money,
                )
            )
    return targets


def reward_general(
    gateway: GatewayClient,
    city_id: int,
    general_id: int,
    money: int,
) -> tuple[bool, int, int]:
    """Gọi API ban thưởng tướng (OPT.ashx?id=46). Trả về (thành_công, ret, loyalty_mới)."""
    payload = {
        "lCityID": str(int(city_id)),
        "lGeneralID": str(int(general_id)),
        "lMoney": str(int(money)),
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 46, payload) or {}
    ret = int(resp.get("ret", -1)) if isinstance(resp, dict) else -1
    if ret == 0:
        new_loyalty = int(resp.get("loyalty", 100)) if isinstance(resp, dict) else 100
        return True, 0, new_loyalty
    return False, ret, 0


def reward_all_generals(
    gateway: GatewayClient,
    roster: Optional[Roster] = None,
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> RewardSummary:
    """Ban thưởng toàn bộ Văn quan và Võ tướng có Lòng trung thành < 100."""
    if roster is None:
        _emit(on_log, "📡 Đang tải danh sách Văn quan & Võ tướng từ tất cả căn cứ...")
        roster = fetch_roster(gateway, include_civil=True, include_cities=True)

    targets = collect_reward_targets(roster)
    summary = RewardSummary(total=len(targets))
    if not targets:
        _emit(on_log, "🎁 Tất cả Văn quan & Võ tướng đều đã đạt 100 trung thành.")
        return summary

    _emit(on_log, f"🎁 Bắt đầu ban thưởng cho {len(targets)} tướng có trung thành < 100...")
    for idx, item in enumerate(targets, start=1):
        if stop_event and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "🛑 Đã dừng ban thưởng theo yêu cầu.")
            break

        gen = item.general
        _emit_progress(on_progress, idx - 1, len(targets))
        ok, ret, new_loyalty = reward_general(gateway, item.city_id, gen.id, item.money_needed)
        if ok:
            summary.success += 1
            summary.total_gold_spent += item.money_needed
            line = (
                f"   ✅ [{item.city_name}] {gen.name} ({gen.role_text}, Cấp {gen.level}): "
                f"Trung thành {gen.loyalty} -> {new_loyalty} (-{item.money_needed:,} vàng)"
            )
        else:
            summary.failed += 1
            err_msg = TACTICIAN_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")
            line = (
                f"   ❌ [{item.city_name}] {gen.name} ({gen.role_text}, Cấp {gen.level}): "
                f"Thất bại ({err_msg})"
            )
        summary.details.append(line)
        _emit(on_log, line)
        _emit_progress(on_progress, idx, len(targets))

    _emit(
        on_log,
        f"📊 Hoàn tất ban thưởng: {summary.success}/{summary.total} thành công, "
        f"{summary.failed} thất bại (đã chi {summary.total_gold_spent:,} vàng).",
    )
    return summary


@dataclass
class TacticianSummary:
    total_selected: int = 0
    assigned: int = 0
    removed: int = 0
    name_matched: int = 0
    fallback_assigned: int = 0
    skipped_has_tactician: int = 0
    skipped_busy: int = 0
    no_tactician_to_remove: int = 0
    no_available_civilian: int = 0
    failed: int = 0
    stopped: bool = False


def set_tactician(
    gateway: GatewayClient,
    city_id: int,
    civilian_id: int,
    military_id: int = 0,
    remove: bool = False,
) -> tuple[bool, int, str]:
    """Gán hoặc tháo Mưu sĩ cho Võ tướng qua API OPT.ashx?id=5."""
    payload = {
        "lGeneralID": str(int(civilian_id)),
        "lType": "0" if remove else "3",
        "lFollowGeneralID": "0" if remove else str(int(military_id)),
        "lCityID": str(int(city_id)),
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 5, payload) or {}
    if not isinstance(resp, dict):
        return False, -1, "Lỗi kết nối"
    ret = int(resp.get("ret", -1))
    if ret == 0:
        return True, 0, "Thành công"
    return False, ret, TACTICIAN_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")


def _pair_tacticians(
    militaries: list[General],
    civilians: list[General],
    mode: str,
) -> list[tuple[General, Optional[General], str]]:
    """Ghép cặp Võ tướng với Văn quan khả dụng theo chế độ đã chọn."""
    if mode == MODE_SEQUENTIAL:
        return [
            (mil, civilians[idx] if idx < len(civilians) else None, "sequential")
            for idx, mil in enumerate(militaries)
        ]

    if mode == MODE_BY_LEVEL:
        sorted_mils = sorted(militaries, key=lambda g: g.level, reverse=True)
        sorted_civs = sorted(civilians, key=lambda g: g.level, reverse=True)
        return [
            (mil, sorted_civs[idx] if idx < len(sorted_civs) else None, "by_level")
            for idx, mil in enumerate(sorted_mils)
        ]

    # MODE_BY_NAME: ưu tiên match tên (Văn quan/Võ tướng cấp cao trước), fallback cấp cao -> thấp
    sorted_mils = sorted(militaries, key=lambda g: g.level, reverse=True)
    sorted_civs = sorted(civilians, key=lambda g: g.level, reverse=True)
    used_civ_ids: set[int] = set()
    paired: dict[int, tuple[General, Optional[General], str]] = {}

    for mil in sorted_mils:
        mname = mil.name.strip()
        matched_civ = next(
            (c for c in sorted_civs if c.id not in used_civ_ids and c.name.strip() == mname),
            None,
        )
        if matched_civ is not None:
            used_civ_ids.add(matched_civ.id)
            paired[mil.id] = (mil, matched_civ, "name_match")

    remaining_civs = [c for c in sorted_civs if c.id not in used_civ_ids]
    rem_iter = iter(remaining_civs)
    for mil in sorted_mils:
        if mil.id not in paired:
            paired[mil.id] = (mil, next(rem_iter, None), "fallback")

    return [paired[mil.id] for mil in sorted_mils]


def _remove_tacticians_for_city(
    gateway: GatewayClient,
    city_id: int,
    city_name: str,
    militaries: list[General],
    summary: TacticianSummary,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
) -> None:
    """Tháo Mưu sĩ cho các Võ tướng được chọn trong một căn cứ."""
    for mil in militaries:
        if stop_event and stop_event.is_set():
            summary.stopped = True
            return
        if mil.tactician_id <= 0:
            summary.no_tactician_to_remove += 1
            _emit(on_log, f"   ⚠️ [{city_name}] {mil.name}: chưa có mưu sĩ.")
            continue
        if mil.status != 0:
            summary.skipped_busy += 1
            _emit(on_log, f"   ⚠️ [{city_name}] Bỏ qua {mil.name}: đang bận ({mil.status_text}).")
            continue

        ok, _ret, msg = set_tactician(gateway, city_id, mil.tactician_id, remove=True)
        if ok:
            summary.removed += 1
            tname = mil.tactician_name or str(mil.tactician_id)
            _emit(on_log, f"   ✅ [{city_name}] Đã tháo mưu sĩ {tname} khỏi {mil.name}.")
        else:
            summary.failed += 1
            _emit(on_log, f"   ❌ [{city_name}] Tháo mưu sĩ của {mil.name} thất bại: {msg}")


def _assign_tacticians_for_city(
    gateway: GatewayClient,
    roster: Roster,
    city_id: int,
    city_name: str,
    is_camp: bool,
    militaries: list[General],
    mode: str,
    reassign_existing: bool,
    summary: TacticianSummary,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
) -> None:
    """Biên chế (hoặc đổi) Mưu sĩ cho các Võ tướng được chọn trong cùng một thành."""
    if is_camp:
        _emit(on_log, f"   ⚠️ [{city_name}] Đang là Doanh trại (ID {city_id}); sẽ thử ghép nếu có Văn quan cùng căn cứ.")

    eligible_mils: list[General] = []
    for mil in militaries:
        if mil.status != 0:
            summary.skipped_busy += 1
            _emit(on_log, f"   ⚠️ [{city_name}] Bỏ qua {mil.name}: đang bận ({mil.status_text}).")
            continue
        if not reassign_existing and mil.tactician_id > 0:
            summary.skipped_has_tactician += 1
            tname = mil.tactician_name or str(mil.tactician_id)
            _emit(on_log, f"   ℹ️ [{city_name}] Giữ nguyên {mil.name}: đã có mưu sĩ ({tname}).")
            continue
        eligible_mils.append(mil)

    if not eligible_mils:
        return

    freed_civ_ids: set[int] = set()
    ready_mils: list[General] = []
    if reassign_existing:
        for mil in eligible_mils:
            if stop_event and stop_event.is_set():
                summary.stopped = True
                return
            if mil.tactician_id > 0:
                ok, _ret, msg = set_tactician(gateway, city_id, mil.tactician_id, remove=True)
                if ok:
                    summary.removed += 1
                    freed_civ_ids.add(mil.tactician_id)
                    tname = mil.tactician_name or str(mil.tactician_id)
                    _emit(on_log, f"   🔄 [{city_name}] Tháo mưu sĩ cũ {tname} khỏi {mil.name} để biên chế lại.")
                    ready_mils.append(mil)
                else:
                    summary.failed += 1
                    _emit(on_log, f"   ❌ [{city_name}] Không tháo được mưu sĩ cũ của {mil.name}: {msg}")
            else:
                ready_mils.append(mil)
    else:
        ready_mils = eligible_mils

    if not ready_mils:
        return

    # Chỉ lấy Văn quan cùng thành đang rảnh rỗi (hoặc vừa được tháo ra),
    # loại trừ hoàn toàn Thái thú (special_status == 1) và Văn quan đang làm nhiệm vụ khác (status != 0).
    available_civs = [
        c
        for c in roster.generals_of(city_id)
        if c.role == "van"
        and c.status == 0
        and c.special_status != 1
        and (c.special_status == 0 or c.id in freed_civ_ids)
    ]

    _emit(
        on_log,
        f"📌 [{city_name}] {len(ready_mils)} Võ tướng cần biên chế | "
        f"{len(available_civs)} Văn quan khả dụng.",
    )

    pairs = _pair_tacticians(ready_mils, available_civs, mode)
    for mil, civ, match_kind in pairs:
        if stop_event and stop_event.is_set():
            summary.stopped = True
            return
        if civ is None:
            summary.no_available_civilian += 1
            _emit(on_log, f"   ⚠️ [{city_name}] Hết Văn quan khả dụng cho {mil.name} (Cấp {mil.level}).")
            continue

        ok, _ret, msg = set_tactician(gateway, city_id, civ.id, military_id=mil.id, remove=False)
        if ok:
            summary.assigned += 1
            if match_kind == "name_match":
                summary.name_matched += 1
                tag = " [Trùng tên]"
            elif match_kind == "fallback":
                summary.fallback_assigned += 1
                tag = " [Fallback cao→thấp]"
            elif match_kind == "by_level":
                tag = " [Cao→thấp]"
            else:
                tag = ""
            _emit(
                on_log,
                f"   ✅ [{city_name}] Văn: {civ.name} (Lv.{civ.level}) -> Võ: {mil.name} (Lv.{mil.level}){tag}",
            )
        else:
            summary.failed += 1
            _emit(on_log, f"   ❌ [{city_name}] Gán {civ.name} -> {mil.name} thất bại: {msg}")


def configure_tacticians(
    gateway: GatewayClient,
    roster: Roster,
    selected_general_ids: list[int],
    mode: str = MODE_BY_LEVEL,
    reassign_existing: bool = False,
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> TacticianSummary:
    """Thiết lập hoặc tháo Mưu sĩ cho danh sách Võ tướng được chọn theo từng thành."""
    if mode not in VALID_TACTICIAN_MODES:
        raise ValueError(f"Chế độ Mưu sĩ không hợp lệ: {mode}")

    selected_set = {int(gid) for gid in selected_general_ids}
    summary = TacticianSummary(total_selected=len(selected_set))
    if not selected_set:
        return summary

    # Gom Võ tướng được chọn theo từng căn cứ (giữ đúng ranh giới cùng thành)
    city_groups: list[tuple[int, str, bool, list[General]]] = []
    seen_mils: set[int] = set()
    for base in roster.bases:
        mils_in_base = []
        for g in roster.generals_of(base.id):
            if g.id in selected_set and g.id not in seen_mils and g.role == "vo":
                seen_mils.add(g.id)
                mils_in_base.append(g)
        if mils_in_base:
            city_groups.append((base.id, base.name, base.is_camp, mils_in_base))

    total_bases = len(city_groups)
    for idx, (cid, cname, is_camp, mils) in enumerate(city_groups, start=1):
        if stop_event and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "🛑 Đã dừng thiết lập Mưu sĩ theo yêu cầu.")
            break
        _emit_progress(on_progress, idx - 1, total_bases)
        if mode == MODE_REMOVE:
            _remove_tacticians_for_city(gateway, cid, cname, mils, summary, stop_event, on_log)
        else:
            _assign_tacticians_for_city(
                gateway,
                roster,
                cid,
                cname,
                is_camp,
                mils,
                mode,
                reassign_existing,
                summary,
                stop_event,
                on_log,
            )
        _emit_progress(on_progress, idx, total_bases)

    _emit(
        on_log,
        f"📊 Kết quả Mưu sĩ: gán {summary.assigned}, tháo {summary.removed}, "
        f"bỏ qua (đã có {summary.skipped_has_tactician}, bận {summary.skipped_busy}), "
        f"thiếu Văn quan {summary.no_available_civilian}, lỗi {summary.failed}.",
    )
    return summary
