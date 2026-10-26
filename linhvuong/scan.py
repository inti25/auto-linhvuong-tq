"""Quét bản đồ để tìm Mục tiêu (Man) gần nhất."""

import math
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

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
    ) -> Optional[Target]:
        """Trả Mục tiêu hợp lệ gần nhất (đã Khóa) hoặc None."""
        wanted = set(target_types)
        capitals: list[tuple[int, int]] = []
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
                if self.locks.try_lock(target_id, LockReason.CLAIMED):
                    return Target(tx, ty, target_id, man_type)
        return None
