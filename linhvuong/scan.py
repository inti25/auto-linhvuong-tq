"""Quét bản đồ để tìm Mục tiêu (Man) gần nhất."""

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from .coords import MAP_MAX, MAP_MIN, coords_from_mid, mid_from_coords
from .gateway import GatewayClient
from .locks import LockReason, TargetLocks

THIEN_THANH_MIN_LEVEL = 5

MAN_NAMES = {
    1: "Uy Quốc",
    2: "Tiên Ti",
    3: "Ô Hoàn",
    4: "Sơn Việt",
    5: "Khương Để",
    6: "Mạnh Hoạch",
    7: "Hung Nô",
    8: "Đột Quyết",
    9: "Long Phi",
    10: "Hổ Báo Kỵ",
    101: "Đạo quân lương",
    201: "Thần thú",
    301: "Vong Linh",
}



@dataclass(frozen=True)
class Target:
    x: int
    y: int
    target_id: int
    man_type: int


@dataclass(frozen=True)
class BasePeer:
    base_id: int
    ox: int = 0
    oy: int = 0
    radius: int = 0
    target_types: Iterable[int] = ()
    origin: Optional[tuple[int, int]] = None
    mantypes: Optional[Any] = None
    name: str = ""

    def __post_init__(self):
        if self.origin is not None:
            object.__setattr__(self, "ox", int(self.origin[0]))
            object.__setattr__(self, "oy", int(self.origin[1]))
        if self.mantypes is not None and not self.target_types:
            if isinstance(self.mantypes, str):
                types = [int(x.strip()) for x in self.mantypes.split(",") if x.strip().isdigit()]
            elif isinstance(self.mantypes, (list, tuple, set)):
                types = [int(x) for x in self.mantypes if str(x).isdigit()]
            else:
                types = []
            object.__setattr__(self, "target_types", types)
        if isinstance(self.radius, str):
            try:
                object.__setattr__(self, "radius", int(self.radius))
            except ValueError:
                object.__setattr__(self, "radius", 0)


class Scanner:
    def __init__(
        self,
        gateway: GatewayClient,
        locks: TargetLocks,
        delay: float = 0.2,
        step: int = 7,
        workers: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.gateway = gateway
        self.locks = locks
        self.delay = delay
        self.step = step
        self.workers = max(1, int(workers))
        self._sleep = sleep
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def _scan_points(self, ox: int, oy: int, radius: int) -> list[tuple[float, int, int]]:
        points = []
        reach = (radius // self.step) * self.step
        offsets = range(-reach, reach + 1, self.step)
        for dx in offsets:
            for dy in offsets:
                x, y = ox + dx, oy + dy
                if not (MAP_MIN <= x <= MAP_MAX and MAP_MIN <= y <= MAP_MAX):
                    continue
                d = math.hypot(dx, dy)
                if d <= radius:
                    points.append((d, x, y))
        points.sort(key=lambda p: p[0])
        return points

    def find_nearest(
        self,
        ox: int,
        oy: int,
        radius: int,
        target_types: Iterable[int],
        skip_capital_radius: int = 0,
        owner_id: Optional[int] = None,
        peers: Optional[list[BasePeer]] = None,
    ) -> Optional[Target]:
        """Trả Mục tiêu hợp lệ gần nhất (đã Khóa) hoặc None.
        
        Áp dụng Quy Tắc Ưu Tiên Căn Cứ Gần Nhất (ADR-0029) khi cung cấp danh sách peers.
        """
        wanted = set(target_types)
        capitals: list[tuple[int, int]] = []
        peer_list = []
        if peers:
            for p in peers:
                if p.base_id != owner_id:
                    peer_list.append((p.base_id, p.ox, p.oy, p.radius, set(p.target_types)))

        points = self._scan_points(ox, oy, radius)
        if not points or self._stop.is_set():
            return None

        def is_valid_target(dist: float, tx: int, ty: int, man_type: int) -> bool:
            if skip_capital_radius and any(
                math.hypot(tx - cx, ty - cy) <= skip_capital_radius for cx, cy in capitals
            ):
                return False
            if peer_list:
                for p_id, p_ox, p_oy, p_rad, p_wanted in peer_list:
                    if man_type in p_wanted:
                        p_dist = math.hypot(tx - p_ox, ty - p_oy)
                        if p_dist <= p_rad:
                            if p_dist < dist or (abs(p_dist - dist) < 1e-5 and p_id < (owner_id or 0)):
                                return False
            return True

        # Khi workers <= 1, chạy tuần tự để tiết kiệm tài nguyên
        if self.workers <= 1:
            for _, x, y in points:
                if self._stop.is_set():
                    return None
                data = self.gateway.map_view(mid_from_coords(x, y))
                if self.delay:
                    self._sleep(self.delay)
                if not data:
                    continue
                for city in data.get("citys", []):
                    if int(city[2]) >= THIEN_THANH_MIN_LEVEL:
                        capitals.append(coords_from_mid(int(city[3])))
                for npc in data.get("npc_tent", []):
                    target_id, man_type, m_mid = int(npc[0]), int(npc[1]), int(npc[2])
                    if man_type not in wanted:
                        continue
                    tx, ty = coords_from_mid(m_mid)
                    dist = math.hypot(tx - ox, ty - oy)
                    if not is_valid_target(dist, tx, ty, man_type):
                        continue
                    if self.locks.try_lock(target_id, LockReason.CLAIMED, owner=owner_id):
                        return Target(tx, ty, target_id, man_type)
            return None

        # Quét song song đa luồng (workers) theo từng lô điểm
        candidates: dict[int, tuple[float, int, int, int, int]] = {}

        def fetch_point(pt: tuple[float, int, int]):
            if self._stop.is_set():
                return None
            _, px, py = pt
            data = self.gateway.map_view(mid_from_coords(px, py))
            if self.delay:
                self._sleep(self.delay)
            return pt, data

        batch_size = self.workers
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            for i in range(0, len(points), batch_size):
                if self._stop.is_set():
                    return None
                batch = points[i : i + batch_size]
                # Sử dụng executor.map để giữ thứ tự kết quả đồng nhất với batch
                results = list(executor.map(fetch_point, batch))
                for res in results:
                    if not res:
                        continue
                    _, data = res
                    if not data:
                        continue
                    for city in data.get("citys", []):
                        if int(city[2]) >= THIEN_THANH_MIN_LEVEL:
                            capitals.append(coords_from_mid(int(city[3])))
                    for npc in data.get("npc_tent", []):
                        target_id, man_type, m_mid = int(npc[0]), int(npc[1]), int(npc[2])
                        if man_type not in wanted:
                            continue
                        tx, ty = coords_from_mid(m_mid)
                        dist = math.hypot(tx - ox, ty - oy)
                        if dist <= radius:
                            candidates[target_id] = (dist, tx, ty, target_id, man_type)

                # Lọc và sắp xếp các ứng viên hợp lệ đã tìm thấy
                valid_cands = [
                    cand for cand in candidates.values()
                    if is_valid_target(cand[0], cand[1], cand[2], cand[4])
                ]
                valid_cands.sort(key=lambda c: c[0])

                if valid_cands:
                    best_dist = valid_cands[0][0]
                    next_idx = i + batch_size
                    # Bất đẳng thức tam giác: Điểm quét tại cự ly d_next chỉ có thể thấy mục tiêu
                    # ở cự ly tối thiểu (d_next - 6). Do đó nếu d_next >= best_dist + 6,
                    # không điểm nào phía sau có thể chứa mục tiêu gần hơn best_dist!
                    no_closer_possible = (next_idx >= len(points)) or (points[next_idx][0] >= best_dist + 6.0)
                    if no_closer_possible:
                        for cand in valid_cands:
                            tid = cand[3]
                            if self.locks.try_lock(tid, LockReason.CLAIMED, owner=owner_id):
                                return Target(cand[1], cand[2], tid, cand[4])
                            else:
                                candidates.pop(tid, None)

        # Quét hết toàn bộ các điểm mà chưa khóa được: thử lại các ứng viên còn lại
        final_valid = [
            cand for cand in candidates.values()
            if is_valid_target(cand[0], cand[1], cand[2], cand[4])
        ]
        final_valid.sort(key=lambda c: c[0])
        for cand in final_valid:
            tid = cand[3]
            if self.locks.try_lock(tid, LockReason.CLAIMED, owner=owner_id):
                return Target(cand[1], cand[2], tid, cand[4])

        return None
