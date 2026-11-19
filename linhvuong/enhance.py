"""Lõi nghiệp vụ Cường Hóa Trang Bị (cấp 1->15) và Hủy Trang Bị (tham khảo ZFunction.exe).

Giao thức máy chủ:
- Common.ashx?id=2 (nid=1): Tồn kho nguyên liệu cường hóa (gem_id: 341 Huyền Thiết, 342 Búa Bảo Hộ, 354 Pha Lê).
- Common.ashx?id=24 (lType=1..4): Danh sách trang bị theo loại (chỉ dùng đồ chưa mặc general_id == 0, cấp = row[7] + 1).
- Common.ashx?id=117 (eid=<item_id>): Danh sách Phôi Cường Hóa khả dụng cho trang bị đang chọn.
- OPT.ashx?id=154: Cường hóa cấp 1->9 (lDstEquipID, lSrcEquipID1..3, lPropProtect=342|0, lPropUpgrade=341).
- OPT.ashx?id=188: Cường hóa cấp 9->15 (EquipID), tiêu tốn Pha Lê theo bậc cấp độ.
- OPT.ashx?id=17: Hủy trang bị vĩnh viễn (lEquipID).
"""

from dataclasses import dataclass, field
import random
import threading
import time
from typing import Any, Callable, Optional

from .gateway import GatewayClient
from .generals import (
    EQUIP_SLOT_NAMES,
    EQUIP_TYPES,
    classify_item_role,
    get_item_display_name,
    parse_equipment_level,
)
from .tasks.base import CaptchaRequired

PROP_IRON = 341
PROP_HAMMER = 342
PROP_CRYSTAL = 354

RET_CAPTCHA = 110
RET_ENHANCE_LOW_FAIL = 299
RET_ENHANCE_HIGH_FAIL = 325

MIN_EQUIP_LEVEL = 1
HIGH_ENHANCE_START_LEVEL = 9
MAX_EQUIP_LEVEL = 15
DESTROY_WARN_LEVEL = 7
MAX_LOOP_COUNT = 99999
MAX_NETWORK_RETRIES = 3

CRYSTAL_COST_BY_LEVEL: dict[int, int] = {
    9: 5,
    10: 10,
    11: 20,
    12: 30,
    13: 40,
    14: 50,
}

DEFAULT_DELAY_RANGE: tuple[float, float] = (0.15, 0.30)


def _emit(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if cb:
        cb(msg)


def _emit_progress(cb: Optional[Callable[["EnhanceProgress"], None]], progress: "EnhanceProgress") -> None:
    if cb:
        cb(progress)


def _sleep_interruptible(
    sleep_fn: Callable[[float], None],
    stop_event: Optional[threading.Event],
    seconds: float,
) -> bool:
    """Ngủ có thể ngắt theo stop_event. Trả về False nếu đã có yêu cầu dừng."""
    if stop_event and stop_event.is_set():
        return False
    if seconds > 0:
        if stop_event is not None:
            if stop_event.wait(seconds):
                return False
        else:
            sleep_fn(seconds)
    return not (stop_event and stop_event.is_set())


@dataclass
class EnhanceResources:
    iron: int = 0
    hammer: int = 0
    crystal: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "iron": int(self.iron),
            "hammer": int(self.hammer),
            "crystal": int(self.crystal),
        }


@dataclass(frozen=True)
class WarehouseItem:
    item_id: int
    equip_type: int
    item_type_id: int
    level: int
    quantity: int
    role: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": int(self.item_id),
            "equip_type": int(self.equip_type),
            "item_type_id": int(self.item_type_id),
            "level": int(self.level),
            "quantity": int(self.quantity),
            "role": self.role,
            "name": self.name,
        }


@dataclass
class MaterialEntry:
    item_id: int
    item_type_id: int
    level: int
    quantity: int
    used: int = 0


@dataclass(frozen=True)
class MaterialGroup:
    key: str
    item_type_id: int
    level: int
    name: str
    count: int
    display_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "item_type_id": int(self.item_type_id),
            "level": int(self.level),
            "name": self.name,
            "count": int(self.count),
            "display_label": self.display_label,
        }


@dataclass
class MaterialPool:
    groups: list[MaterialGroup] = field(default_factory=list)
    entries_by_key: dict[str, list[MaterialEntry]] = field(default_factory=dict)

    def label_for(self, key: str) -> str:
        for grp in self.groups:
            if grp.key == key:
                return grp.display_label
        return key

    def to_dict(self) -> dict[str, Any]:
        return {
            "groups": [g.to_dict() for g in self.groups],
            "total_items": sum(g.count for g in self.groups),
        }


@dataclass(frozen=True)
class EnhanceConfig:
    equip_type: int
    role: str
    item_id: int
    item_type_id: int
    start_level: int
    target_level: int
    protect_from_level: Optional[int] = None
    material_from_level: int = 1
    material_keys: tuple[str, str, str] = ("", "", "")
    loop_count: int = 1

    def validate(self) -> None:
        if int(self.equip_type) not in EQUIP_TYPES:
            raise ValueError(f"Loại trang bị không hợp lệ: {self.equip_type}")
        if self.role not in ("vo", "van"):
            raise ValueError(f"Phân hệ không hợp lệ: {self.role}")
        if int(self.item_id) <= 0 or int(self.item_type_id) <= 0:
            raise ValueError("Vui lòng chọn trang bị cần cường hóa.")
        if not (MIN_EQUIP_LEVEL <= int(self.start_level) < int(self.target_level) <= MAX_EQUIP_LEVEL):
            raise ValueError(
                f"Cấp mục tiêu ({self.target_level}) phải lớn hơn cấp hiện tại ({self.start_level}) và nằm trong 2..{MAX_EQUIP_LEVEL}."
            )
        if self.protect_from_level is not None and not (2 <= int(self.protect_from_level) <= 8):
            raise ValueError("Mốc kẹp Búa Bảo Hộ phải nằm trong khoảng cấp 2..8 hoặc Không dùng.")
        if not (1 <= int(self.material_from_level) <= 8):
            raise ValueError("Mốc dùng Phôi Cường Hóa phải nằm trong khoảng cấp 1..8.")
        if not (1 <= int(self.loop_count) <= MAX_LOOP_COUNT):
            raise ValueError(f"Số lượng món phải nằm trong 1..{MAX_LOOP_COUNT}.")


@dataclass
class EnhanceProgress:
    running: bool = False
    mode: str = ""
    status: str = "Sẵn sàng"
    item_name: str = ""
    item_type_id: int = 0
    current_item_id: int = 0
    current_level: int = 0
    target_level: int = 0
    item_index: int = 0
    total_items: int = 0
    item_attempts: int = 0
    total_attempts: int = 0
    success_attempts: int = 0
    fail_attempts: int = 0
    completed_items: int = 0
    pct: int = 0
    iron_used: int = 0
    hammer_used: int = 0
    crystal_used: int = 0
    material_used: int = 0
    destroyed_count: int = 0
    destroy_total: int = 0
    resources: dict[str, int] = field(default_factory=lambda: {"iron": 0, "hammer": 0, "crystal": 0})

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": bool(self.running),
            "mode": self.mode,
            "status": self.status,
            "item_name": self.item_name,
            "item_type_id": int(self.item_type_id),
            "current_item_id": int(self.current_item_id),
            "current_level": int(self.current_level),
            "target_level": int(self.target_level),
            "item_index": int(self.item_index),
            "total_items": int(self.total_items),
            "item_attempts": int(self.item_attempts),
            "total_attempts": int(self.total_attempts),
            "success_attempts": int(self.success_attempts),
            "fail_attempts": int(self.fail_attempts),
            "completed_items": int(self.completed_items),
            "pct": int(self.pct),
            "iron_used": int(self.iron_used),
            "hammer_used": int(self.hammer_used),
            "crystal_used": int(self.crystal_used),
            "material_used": int(self.material_used),
            "destroyed_count": int(self.destroyed_count),
            "destroy_total": int(self.destroy_total),
            "resources": dict(self.resources),
        }


@dataclass
class EnhanceSummary:
    completed_items: int = 0
    requested_items: int = 0
    total_attempts: int = 0
    success_attempts: int = 0
    fail_attempts: int = 0
    iron_used: int = 0
    hammer_used: int = 0
    crystal_used: int = 0
    material_used: int = 0
    final_level: int = 0
    stopped: bool = False
    stop_reason: str = ""
    resources: EnhanceResources = field(default_factory=EnhanceResources)


@dataclass
class DestroySummary:
    destroyed: int = 0
    failed: int = 0
    requested: int = 0
    stopped: bool = False
    stop_reason: str = ""


def _calc_pct(current_level: int, start_level: int, target_level: int) -> int:
    span = max(1, target_level - start_level)
    raw = int(((current_level - start_level) / span) * 100)
    return max(0, min(100, raw))


def fetch_enhance_resources(gateway: GatewayClient) -> EnhanceResources:
    """Đọc số lượng Huyền Thiết (341), Búa Bảo Hộ (342) và Pha Lê (354) từ Common.ashx?id=2."""
    data = gateway.call("Common.ashx", 2, {"nid": "1", "_": ""})
    if not isinstance(data, dict):
        raise RuntimeError("Không thể tải tài nguyên cường hóa (Common.ashx?id=2).")
    ret = int(data.get("ret", 0))
    if ret == RET_CAPTCHA:
        raise CaptchaRequired("Tải tài nguyên cường hóa gặp Captcha (mã 110).")
    if ret != 0:
        raise RuntimeError(f"Lỗi tải tài nguyên cường hóa (ret={ret}).")

    table = data.get("Table")
    if not table:
        table = data.get("table") or []
    res = EnhanceResources()
    if isinstance(table, list):
        for item in table:
            if not isinstance(item, dict):
                continue
            gem_id = int(item.get("gem_id") or 0)
            counts = max(0, int(item.get("counts") or 0))
            if gem_id == PROP_IRON:
                res.iron = counts
            elif gem_id == PROP_HAMMER:
                res.hammer = counts
            elif gem_id == PROP_CRYSTAL:
                res.crystal = counts
    return res


def fetch_warehouse_equipment(
    gateway: GatewayClient,
    equip_type: int,
) -> dict[str, list[WarehouseItem]]:
    """Tải danh sách trang bị chưa mặc trong kho từ Common.ashx?id=24 theo lType (1..4)."""
    eq_type = int(equip_type)
    if eq_type not in EQUIP_TYPES:
        raise ValueError(f"Loại trang bị không hợp lệ: {equip_type}")

    data = gateway.call("Common.ashx", 24, {"lType": str(eq_type), "_": ""})
    if not isinstance(data, dict):
        raise RuntimeError(f"Không thể tải kho {EQUIP_SLOT_NAMES.get(eq_type, eq_type)} (Common.ashx?id=24).")
    ret = int(data.get("ret", -1))
    if ret == RET_CAPTCHA:
        raise CaptchaRequired("Tải kho trang bị gặp Captcha (mã 110).")
    if ret != 0:
        raise RuntimeError(f"Lỗi tải kho trang bị (ret={ret}).")

    rows = data.get("list") or []
    grouped: dict[str, list[WarehouseItem]] = {"vo": [], "van": []}
    if not isinstance(rows, list):
        return grouped

    for row in rows:
        if not isinstance(row, list) or len(row) < 9:
            continue
        general_id = int(row[8] or 0)
        if general_id != 0:
            continue
        item_id = int(row[0] or 0)
        quantity = max(1, int(row[1] or 1))
        item_type_id = int(row[2] or 0)
        if item_id <= 0 or item_type_id <= 0:
            continue
        role = classify_item_role(item_type_id)
        if role not in grouped:
            continue
        level = parse_equipment_level(row[7])
        grouped[role].append(
            WarehouseItem(
                item_id=item_id,
                equip_type=eq_type,
                item_type_id=item_type_id,
                level=level,
                quantity=quantity,
                role=role,
                name=get_item_display_name(item_type_id),
            )
        )

    for bucket in grouped.values():
        bucket.sort(key=lambda it: (it.item_type_id, it.level, it.item_id))
    return grouped


def fetch_enhance_materials(gateway: GatewayClient, item_id: int) -> MaterialPool:
    """Tải danh sách Phôi Cường Hóa khả dụng cho món trang bị từ Common.ashx?id=117."""
    data = gateway.call("Common.ashx", 117, {"eid": str(int(item_id)), "_": ""})
    if not isinstance(data, dict):
        raise RuntimeError("Không thể tải danh sách Phôi Cường Hóa (Common.ashx?id=117).")
    ret = int(data.get("ret", -1))
    if ret == RET_CAPTCHA:
        raise CaptchaRequired("Tải Phôi Cường Hóa gặp Captcha (mã 110).")
    if ret != 0:
        raise RuntimeError(f"Lỗi tải danh sách Phôi Cường Hóa (ret={ret}).")

    rows = data.get("list") or []
    entries_by_key: dict[str, list[MaterialEntry]] = {}
    counts_by_key: dict[str, tuple[int, int, int]] = {}  # key -> (item_type_id, level, count)

    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, list) or len(row) < 3:
                continue
            mat_id = int(row[0] or 0)
            qty = int(row[1] or 0)
            mat_type = int(row[2] or 0)
            if mat_id <= 0 or qty <= 0 or mat_type <= 0:
                continue
            level = parse_equipment_level(row[7]) if len(row) > 7 else 1
            key = f"{mat_type}:{level}"
            entries_by_key.setdefault(key, []).append(
                MaterialEntry(
                    item_id=mat_id,
                    item_type_id=mat_type,
                    level=level,
                    quantity=qty,
                    used=0,
                )
            )
            prev = counts_by_key.get(key)
            counts_by_key[key] = (mat_type, level, (prev[2] if prev else 0) + qty)

    groups: list[MaterialGroup] = []
    for key, (mat_type, level, count) in counts_by_key.items():
        name = get_item_display_name(mat_type)
        groups.append(
            MaterialGroup(
                key=key,
                item_type_id=mat_type,
                level=level,
                name=name,
                count=count,
                display_label=f"{name} (Lv.{level}) (x{count})",
            )
        )
    groups.sort(key=lambda g: (g.item_type_id, g.level))
    return MaterialPool(groups=groups, entries_by_key=entries_by_key)


def should_use_protect(current_level: int, protect_from_level: Optional[int]) -> bool:
    """Quyết định có kẹp Búa Bảo Hộ (342) ở lượt ép hiện tại hay không."""
    if protect_from_level is None or int(current_level) >= HIGH_ENHANCE_START_LEVEL:
        return False
    return int(current_level) >= int(protect_from_level)


def level_after_low_failure(current_level: int, used_protect: bool) -> int:
    """Tính cấp độ sau khi cường hóa cấp 1->9 thất bại (ret=299)."""
    lvl = int(current_level)
    if used_protect:
        return lvl
    if lvl <= 2:
        return lvl
    if lvl <= 5:
        return lvl - 1
    return 1


def call_enhance_low(
    gateway: GatewayClient,
    item_id: int,
    material_ids: tuple[int, int, int],
    use_protect: bool,
) -> tuple[bool, int, str]:
    """Gọi OPT.ashx?id=154 cường hóa chặng cấp 1->9."""
    m1, m2, m3 = (int(x or 0) for x in material_ids[:3])
    payload = {
        "lDstEquipID": str(int(item_id)),
        "lSrcEquipID1": str(m1),
        "lSrcEquipID2": str(m2),
        "lSrcEquipID3": str(m3),
        "lPropProtect": str(PROP_HAMMER if use_protect else 0),
        "lPropUpgrade": str(PROP_IRON),
        "_": "",
    }
    data = gateway.call("OPT.ashx", 154, payload)
    if not isinstance(data, dict):
        return False, -1, "Lỗi kết nối API"
    ret = int(data.get("ret", -1))
    if ret == RET_CAPTCHA:
        raise CaptchaRequired("Cường hóa trang bị gặp Captcha (mã 110).")
    if ret == 0:
        return True, 0, "Thành công"
    if ret == RET_ENHANCE_LOW_FAIL:
        return False, RET_ENHANCE_LOW_FAIL, "Thất bại"
    return False, ret, f"Lỗi API {ret}"


def call_enhance_high(gateway: GatewayClient, item_id: int) -> tuple[bool, int, str]:
    """Gọi OPT.ashx?id=188 cường hóa chặng cấp 9->15 bằng Pha Lê."""
    payload = {
        "EquipID": str(int(item_id)),
        "_": "",
    }
    data = gateway.call("OPT.ashx", 188, payload)
    if not isinstance(data, dict):
        return False, -1, "Lỗi kết nối API"
    ret = int(data.get("ret", -1))
    if ret == RET_CAPTCHA:
        raise CaptchaRequired("Cường hóa cấp cao gặp Captcha (mã 110).")
    if ret == 0:
        return True, 0, "Thành công"
    if ret == RET_ENHANCE_HIGH_FAIL:
        return False, RET_ENHANCE_HIGH_FAIL, "Thất bại"
    return False, ret, f"Lỗi API {ret}"


def call_destroy_equipment(gateway: GatewayClient, equip_id: int) -> tuple[bool, int, str]:
    """Gọi OPT.ashx?id=17 để hủy vĩnh viễn một trang bị trong kho."""
    payload = {
        "lEquipID": str(int(equip_id)),
        "_": "",
    }
    data = gateway.call("OPT.ashx", 17, payload)
    if not isinstance(data, dict):
        return False, -1, "Lỗi kết nối API"
    ret = int(data.get("ret", -1))
    if ret == RET_CAPTCHA:
        raise CaptchaRequired("Hủy trang bị gặp Captcha (mã 110).")
    if ret == 0:
        return True, 0, "Thành công"
    return False, ret, f"Mã lỗi {ret}"


def rollback_materials(used_entries: list[MaterialEntry]) -> None:
    """Hoàn trả bộ đếm phôi đã giữ chỗ khi lượt gọi API không thành công ở tầng kết nối."""
    for entry in used_entries:
        entry.used = max(0, entry.used - 1)


def select_materials_for_attempt(
    pool: MaterialPool,
    material_keys: tuple[str, str, str],
    target_item_id: int,
) -> tuple[bool, tuple[int, int, int], list[MaterialEntry], Optional[str]]:
    """Chọn tối đa 3 ID Phôi Cường Hóa chưa dùng hết, không trùng nhau và không trùng đồ đang ép."""
    slots = [0, 0, 0]
    chosen_ids: set[int] = set()
    used_entries: list[MaterialEntry] = []

    for idx, raw_key in enumerate(material_keys[:3]):
        key = str(raw_key or "").strip()
        if not key:
            continue
        entries = pool.entries_by_key.get(key, [])
        picked: Optional[MaterialEntry] = None
        for entry in entries:
            if entry.used >= entry.quantity:
                continue
            if entry.item_id == int(target_item_id) or entry.item_id in chosen_ids:
                continue
            picked = entry
            break
        if picked is None:
            rollback_materials(used_entries)
            return False, (0, 0, 0), [], pool.label_for(key)
        picked.used += 1
        chosen_ids.add(picked.item_id)
        slots[idx] = picked.item_id
        used_entries.append(picked)

    return True, (slots[0], slots[1], slots[2]), used_entries, None


def pick_next_enhance_item(
    items: list[WarehouseItem],
    item_type_id: int,
    start_level: int,
    target_level: int,
    failed_ids: Optional[set[int]] = None,
) -> Optional[WarehouseItem]:
    """Tìm món tiếp theo cùng item_type_id còn cấp < target_level (ưu tiên bằng start_level trước)."""
    excluded = failed_ids or set()
    candidates = [
        it
        for it in items
        if it.item_type_id == int(item_type_id)
        and it.level < int(target_level)
        and it.item_id not in excluded
    ]
    if not candidates:
        return None
    same_start = [it for it in candidates if it.level == int(start_level)]
    if same_start:
        return min(same_start, key=lambda it: it.item_id)
    return min(candidates, key=lambda it: (it.level, it.item_id))


def sync_item_level_from_server(
    gateway: GatewayClient,
    equip_type: int,
    role: str,
    item_id: int,
) -> Optional[int]:
    """Đọc lại cấp thực tế của item_id từ Common.ashx?id=24 khi retry lỗi mạng."""
    warehouse = fetch_warehouse_equipment(gateway, equip_type)
    for item in warehouse.get(role, []):
        if item.item_id == int(item_id):
            return item.level
    return None


def _sync_resources_best_effort(gateway: GatewayClient, current: EnhanceResources) -> EnhanceResources:
    try:
        return fetch_enhance_resources(gateway)
    except CaptchaRequired:
        raise
    except Exception:
        return current


def run_enhance_batch(
    gateway: GatewayClient,
    config: EnhanceConfig,
    stop_event: Optional[threading.Event] = None,
    sleep: Callable[[float], None] = time.sleep,
    delay_range: tuple[float, float] = DEFAULT_DELAY_RANGE,
    rng: Optional[random.Random] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[EnhanceProgress], None]] = None,
) -> EnhanceSummary:
    """Thực thi chuỗi Cường Hóa Trang Bị theo cấu hình, nối liền cấp 1->9 và 9->15."""
    config.validate()
    rand = rng or random.Random()
    item_name = get_item_display_name(config.item_type_id)
    has_materials = any(bool(str(k or "").strip()) for k in config.material_keys[:3])

    resources = fetch_enhance_resources(gateway)
    summary = EnhanceSummary(
        requested_items=int(config.loop_count),
        final_level=int(config.start_level),
        resources=resources,
    )
    progress = EnhanceProgress(
        running=True,
        mode="enhance",
        status="Đang khởi tạo...",
        item_name=item_name,
        item_type_id=int(config.item_type_id),
        current_item_id=int(config.item_id),
        current_level=int(config.start_level),
        target_level=int(config.target_level),
        item_index=1,
        total_items=int(config.loop_count),
        pct=_calc_pct(config.start_level, config.start_level, config.target_level),
        resources=resources.to_dict(),
    )
    _emit_progress(on_progress, progress)

    _emit(
        on_log,
        f"🔨 Bắt đầu cường hóa {item_name}: Cấp {config.start_level} → {config.target_level}, "
        f"số lượng {config.loop_count} món"
        + (f", Búa từ cấp {config.protect_from_level}" if config.protect_from_level else ", Không dùng Búa")
        + (f", Phôi từ cấp {config.material_from_level}" if has_materials else ", Không dùng Phôi")
        + ".",
    )
    _emit(
        on_log,
        f"📦 Tồn kho ban đầu: Huyền Thiết={resources.iron}, Búa Bảo Hộ={resources.hammer}, Pha Lê={resources.crystal}",
    )

    current_item_id = int(config.item_id)
    current_level = int(config.start_level)
    material_pool: Optional[MaterialPool] = None
    if has_materials and current_level < HIGH_ENHANCE_START_LEVEL:
        material_pool = fetch_enhance_materials(gateway, current_item_id)

    try:
        for item_idx in range(1, int(config.loop_count) + 1):
            if stop_event and stop_event.is_set():
                summary.stopped = True
                summary.stop_reason = "Đã dừng theo yêu cầu"
                _emit(on_log, f"🛑 Đã dừng trước món {item_idx}/{config.loop_count}.")
                break

            item_start_level = current_level
            item_attempts = 0
            network_retries = 0
            progress.item_index = item_idx
            progress.current_item_id = current_item_id
            progress.current_level = current_level
            progress.item_attempts = 0
            progress.pct = _calc_pct(current_level, item_start_level, config.target_level)
            progress.status = f"Đang ép món {item_idx}/{config.loop_count} (ID={current_item_id})"
            _emit_progress(on_progress, progress)
            _emit(
                on_log,
                f"▶ Món [{item_idx}/{config.loop_count}] ID={current_item_id} — Bắt đầu từ cấp {current_level}/{config.target_level}",
            )

            while current_level < int(config.target_level):
                if stop_event and stop_event.is_set():
                    summary.stopped = True
                    summary.stop_reason = "Đã dừng theo yêu cầu"
                    _emit(on_log, f"🛑 Đã dừng ở cấp {current_level}.")
                    break

                if current_level < HIGH_ENHANCE_START_LEVEL:
                    use_protect = should_use_protect(current_level, config.protect_from_level)
                    if resources.iron <= 0:
                        summary.stop_reason = "Hết Huyền Thiết"
                        _emit(on_log, "🛑 Dừng ngay: đã hết Huyền Thiết (341).")
                        break
                    if use_protect and resources.hammer <= 0:
                        summary.stop_reason = "Hết Búa Bảo Hộ"
                        _emit(on_log, "🛑 Dừng ngay: hết Búa Bảo Hộ (342) ở mốc bảo hộ — không ép trần.")
                        break

                    used_entries: list[MaterialEntry] = []
                    material_ids: tuple[int, int, int] = (0, 0, 0)
                    if has_materials and current_level >= int(config.material_from_level):
                        if material_pool is None:
                            material_pool = fetch_enhance_materials(gateway, current_item_id)
                        mat_ok, material_ids, used_entries, missing_label = select_materials_for_attempt(
                            material_pool, config.material_keys, current_item_id
                        )
                        if not mat_ok:
                            summary.stop_reason = f"Hết phôi {missing_label}"
                            _emit(on_log, f"🛑 Dừng ngay: hết Phôi Cường Hóa ({missing_label}).")
                            break

                    ok, ret, msg = call_enhance_low(gateway, current_item_id, material_ids, use_protect)
                    if ret == -1:
                        rollback_materials(used_entries)
                        network_retries += 1
                        _emit(
                            on_log,
                            f"⚠️ Lỗi mạng khi ép cấp {current_level} (lần {network_retries}/{MAX_NETWORK_RETRIES}), đang đồng bộ cấp thật...",
                        )
                        if network_retries >= MAX_NETWORK_RETRIES:
                            summary.stop_reason = "Lỗi mạng liên tiếp"
                            _emit(on_log, "🛑 Dừng do lỗi kết nối máy chủ liên tiếp.")
                            break
                        synced = sync_item_level_from_server(gateway, config.equip_type, config.role, current_item_id)
                        if synced is not None:
                            current_level = synced
                            summary.final_level = current_level
                            progress.current_level = current_level
                        if not _sleep_interruptible(sleep, stop_event, 0.5):
                            summary.stopped = True
                            summary.stop_reason = "Đã dừng theo yêu cầu"
                            break
                        continue

                    network_retries = 0
                    if ret not in (0, RET_ENHANCE_LOW_FAIL):
                        rollback_materials(used_entries)
                        summary.stop_reason = f"Lỗi API {ret}"
                        _emit(on_log, f"❌ Dừng do máy chủ báo lỗi (ret={ret}): {msg}")
                        break

                    item_attempts += 1
                    summary.total_attempts += 1
                    resources.iron = max(0, resources.iron - 1)
                    summary.iron_used += 1
                    if use_protect:
                        resources.hammer = max(0, resources.hammer - 1)
                        summary.hammer_used += 1
                    if used_entries:
                        summary.material_used += len(used_entries)

                    if ok:
                        summary.success_attempts += 1
                        current_level += 1
                        _emit(
                            on_log,
                            f"   ✅ Lượt #{item_attempts}: Thành công → Cấp {current_level}"
                            + (" (có Búa)" if use_protect else ""),
                        )
                    else:
                        summary.fail_attempts += 1
                        current_level = level_after_low_failure(current_level, use_protect)
                        note = "giữ cấp nhờ Búa Bảo Hộ" if use_protect else f"xuống cấp {current_level}"
                        _emit(on_log, f"   ❌ Lượt #{item_attempts}: Thất bại ({note})")

                else:
                    crystal_cost = CRYSTAL_COST_BY_LEVEL.get(current_level, 50)
                    if resources.crystal < crystal_cost:
                        summary.stop_reason = "Thiếu Pha Lê"
                        _emit(
                            on_log,
                            f"🛑 Dừng ngay: thiếu Pha Lê (354) để ép cấp {current_level}→{current_level + 1} "
                            f"(cần {crystal_cost}, còn {resources.crystal}).",
                        )
                        break

                    ok, ret, msg = call_enhance_high(gateway, current_item_id)
                    if ret == -1:
                        network_retries += 1
                        _emit(
                            on_log,
                            f"⚠️ Lỗi mạng khi ép Pha Lê cấp {current_level} (lần {network_retries}/{MAX_NETWORK_RETRIES}), đang đồng bộ cấp thật...",
                        )
                        if network_retries >= MAX_NETWORK_RETRIES:
                            summary.stop_reason = "Lỗi mạng liên tiếp"
                            _emit(on_log, "🛑 Dừng do lỗi kết nối máy chủ liên tiếp.")
                            break
                        synced = sync_item_level_from_server(gateway, config.equip_type, config.role, current_item_id)
                        if synced is not None:
                            current_level = synced
                            summary.final_level = current_level
                            progress.current_level = current_level
                        if not _sleep_interruptible(sleep, stop_event, 0.5):
                            summary.stopped = True
                            summary.stop_reason = "Đã dừng theo yêu cầu"
                            break
                        continue

                    network_retries = 0
                    if ret not in (0, RET_ENHANCE_HIGH_FAIL):
                        summary.stop_reason = f"Lỗi API {ret}"
                        _emit(on_log, f"❌ Dừng do máy chủ báo lỗi (ret={ret}): {msg}")
                        break

                    item_attempts += 1
                    summary.total_attempts += 1
                    resources.crystal = max(0, resources.crystal - crystal_cost)
                    summary.crystal_used += crystal_cost

                    if ok:
                        summary.success_attempts += 1
                        current_level += 1
                        _emit(
                            on_log,
                            f"   ✅ Lượt #{item_attempts}: Thành công (-{crystal_cost} Pha Lê) → Cấp {current_level}",
                        )
                    else:
                        summary.fail_attempts += 1
                        _emit(
                            on_log,
                            f"   ❌ Lượt #{item_attempts}: Thất bại (-{crystal_cost} Pha Lê, giữ cấp {current_level})",
                        )

                summary.final_level = current_level
                progress.current_level = current_level
                progress.item_attempts = item_attempts
                progress.total_attempts = summary.total_attempts
                progress.success_attempts = summary.success_attempts
                progress.fail_attempts = summary.fail_attempts
                progress.iron_used = summary.iron_used
                progress.hammer_used = summary.hammer_used
                progress.crystal_used = summary.crystal_used
                progress.material_used = summary.material_used
                progress.pct = _calc_pct(current_level, item_start_level, config.target_level)
                progress.resources = resources.to_dict()
                _emit_progress(on_progress, progress)

                if current_level < int(config.target_level):
                    if not _sleep_interruptible(sleep, stop_event, rand.uniform(*delay_range)):
                        summary.stopped = True
                        summary.stop_reason = "Đã dừng theo yêu cầu"
                        break

            if current_level < int(config.target_level):
                break

            summary.completed_items += 1
            summary.final_level = current_level
            progress.completed_items = summary.completed_items
            progress.pct = 100
            _emit(
                on_log,
                f"🏆 Món [{item_idx}/{config.loop_count}] đạt cấp {current_level} sau {item_attempts} lượt ép!",
            )
            _emit_progress(on_progress, progress)

            if item_idx >= int(config.loop_count):
                break
            if stop_event and stop_event.is_set():
                summary.stopped = True
                summary.stop_reason = "Đã dừng theo yêu cầu"
                break

            warehouse = fetch_warehouse_equipment(gateway, config.equip_type)
            next_item = pick_next_enhance_item(
                warehouse.get(config.role, []),
                config.item_type_id,
                config.start_level,
                config.target_level,
            )
            if next_item is None:
                summary.stop_reason = "Hết món cùng loại trong kho"
                _emit(
                    on_log,
                    f"📭 Không còn {item_name} (< cấp {config.target_level}) trong kho để ép tiếp.",
                )
                break

            current_item_id = next_item.item_id
            current_level = next_item.level
            summary.final_level = current_level
            if has_materials and current_level < HIGH_ENHANCE_START_LEVEL:
                material_pool = fetch_enhance_materials(gateway, current_item_id)
            else:
                material_pool = None
            _emit(on_log, f"📌 Chuyển sang món kế tiếp: ID={current_item_id}, Cấp={current_level}")

        if not summary.stop_reason:
            summary.stop_reason = "Hoàn tất"
        _emit(
            on_log,
            f"📊 Kết thúc cường hóa: xong {summary.completed_items}/{summary.requested_items} món | "
            f"{summary.total_attempts} lượt ({summary.success_attempts} thành công / {summary.fail_attempts} thất bại) | "
            f"Tiêu hao: Sắt={summary.iron_used}, Búa={summary.hammer_used}, Pha Lê={summary.crystal_used}, Phôi={summary.material_used}.",
        )
    finally:
        resources = _sync_resources_best_effort(gateway, resources)
        summary.resources = resources
        progress.running = False
        progress.status = summary.stop_reason or "Đã hoàn tất"
        progress.resources = resources.to_dict()
        _emit_progress(on_progress, progress)

    return summary


def run_destroy_batch(
    gateway: GatewayClient,
    equip_type: int,
    role: str,
    start_item_id: int,
    item_type_id: int,
    target_level: int,
    quantity: int,
    stop_event: Optional[threading.Event] = None,
    sleep: Callable[[float], None] = time.sleep,
    delay_range: tuple[float, float] = DEFAULT_DELAY_RANGE,
    rng: Optional[random.Random] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[EnhanceProgress], None]] = None,
) -> DestroySummary:
    """Hủy hàng loạt tối đa `quantity` trang bị chưa mặc cùng loại & cấp qua OPT.ashx?id=17."""
    qty = int(quantity)
    if qty < 1:
        raise ValueError("Số lượng hủy phải >= 1.")
    if int(equip_type) not in EQUIP_TYPES:
        raise ValueError(f"Loại trang bị không hợp lệ: {equip_type}")
    if role not in ("vo", "van"):
        raise ValueError(f"Phân hệ không hợp lệ: {role}")

    rand = rng or random.Random()
    item_name = get_item_display_name(item_type_id)
    summary = DestroySummary(requested=qty)
    failed_ids: set[int] = set()
    current_item_id = int(start_item_id)

    progress = EnhanceProgress(
        running=True,
        mode="destroy",
        status=f"Đang hủy {item_name} (Cấp {target_level})...",
        item_name=item_name,
        item_type_id=int(item_type_id),
        current_item_id=current_item_id,
        current_level=int(target_level),
        target_level=int(target_level),
        destroyed_count=0,
        destroy_total=qty,
        pct=0,
    )
    _emit_progress(on_progress, progress)
    _emit(on_log, f"🔥 Bắt đầu hủy {qty}x {item_name} (Cấp {target_level})...")

    try:
        for step_idx in range(1, qty + 1):
            if stop_event and stop_event.is_set():
                summary.stopped = True
                summary.stop_reason = "Đã dừng theo yêu cầu"
                _emit(on_log, f"🛑 Đã dừng hủy đồ ở lượt {step_idx}/{qty}.")
                break

            ok, ret, msg = call_destroy_equipment(gateway, current_item_id)
            if ok:
                summary.destroyed += 1
                _emit(
                    on_log,
                    f"   🔥 Đã hủy [{summary.destroyed}/{qty}] {item_name} (Cấp {target_level}, ID={current_item_id})",
                )
            else:
                summary.failed += 1
                failed_ids.add(current_item_id)
                _emit(on_log, f"   ❌ Hủy thất bại ID={current_item_id}: {msg}")

            progress.destroyed_count = summary.destroyed
            progress.pct = int((step_idx / qty) * 100)
            progress.current_item_id = current_item_id
            _emit_progress(on_progress, progress)

            if step_idx >= qty:
                break
            if not _sleep_interruptible(sleep, stop_event, rand.uniform(*delay_range)):
                summary.stopped = True
                summary.stop_reason = "Đã dừng theo yêu cầu"
                _emit(on_log, f"🛑 Đã dừng hủy đồ sau {summary.destroyed}/{qty} món.")
                break

            warehouse = fetch_warehouse_equipment(gateway, equip_type)
            candidates = [
                it
                for it in warehouse.get(role, [])
                if it.item_type_id == int(item_type_id)
                and it.level == int(target_level)
                and it.item_id not in failed_ids
            ]
            if not candidates:
                summary.stop_reason = "Hết món cùng loại trong kho"
                _emit(on_log, f"📭 Không còn {item_name} (Cấp {target_level}) trong kho để hủy tiếp.")
                break
            next_item = min(candidates, key=lambda it: it.item_id)
            current_item_id = next_item.item_id

        if not summary.stop_reason:
            summary.stop_reason = "Hoàn tất"
        _emit(on_log, f"📊 Hoàn tất hủy đồ: {summary.destroyed}/{qty} thành công, {summary.failed} thất bại.")
    finally:
        progress.running = False
        progress.status = summary.stop_reason or "Hoàn tất"
        _emit_progress(on_progress, progress)

    return summary
