"""Quét bản đồ để tìm Mục tiêu (Man) gần nhất."""

import math
import threading
import time
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
        step: int = 5,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.gateway = gateway
        self.locks = locks
        self.delay = delay
        self.step = step
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

        for _, x, y in self._scan_points(ox, oy, radius):
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
                if skip_capital_radius and any(
                    math.hypot(tx - cx, ty - cy) <= skip_capital_radius for cx, cy in capitals
                ):
                    continue

                # Ưu tiên căn cứ gần nhất: nếu có căn cứ khác gần Man này hơn, nhường cho căn cứ đó
                if peer_list:
                    my_dist = math.hypot(tx - ox, ty - oy)
                    has_closer_peer = False
                    for p_id, p_ox, p_oy, p_rad, p_wanted in peer_list:
                        if man_type in p_wanted:
                            p_dist = math.hypot(tx - p_ox, ty - p_oy)
                            if p_dist <= p_rad:
                                if p_dist < my_dist or (abs(p_dist - my_dist) < 1e-5 and p_id < (owner_id or 0)):
                                    has_closer_peer = True
                                    break
                    if has_closer_peer:
                        continue

                if self.locks.try_lock(target_id, LockReason.CLAIMED, owner=owner_id):
                    return Target(tx, ty, target_id, man_type)
        return None
