"""Khóa mục tiêu: tránh nhiều nhiệm vụ đánh trùng cùng một Mục tiêu."""

import enum
import threading
import time
from typing import Callable


class LockReason(enum.Enum):
    CLAIMED = 300  # nhiệm vụ này đã nhận Mục tiêu (giây)
    TAKEN_BY_OTHER = 600  # server báo (ret=230) đã có người đánh (giây)


class TargetLocks:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._expiry: dict[int, float] = {}
        self._mutex = threading.Lock()

    def is_locked(self, target_id: int) -> bool:
        with self._mutex:
            return self._expiry.get(target_id, 0.0) > self._clock()

    def try_lock(self, target_id: int, reason: LockReason) -> bool:
        with self._mutex:
            if self._expiry.get(target_id, 0.0) > self._clock():
                return False
            self._expiry[target_id] = self._clock() + reason.value
            return True

    def mark(self, target_id: int, reason: LockReason) -> None:
        """Đặt/gia hạn khóa, không bao giờ rút ngắn khóa hiện có."""
        with self._mutex:
            new_expiry = self._clock() + reason.value
            self._expiry[target_id] = max(self._expiry.get(target_id, 0.0), new_expiry)
