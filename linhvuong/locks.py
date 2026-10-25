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

    _PRUNE_THRESHOLD = 256

    def _prune_locked(self, now: float) -> None:
        """Dọn các khóa đã hết hạn (gọi khi đang giữ mutex) để tránh rò rỉ bộ nhớ khi chạy dài."""
        if len(self._expiry) > self._PRUNE_THRESHOLD:
            self._expiry = {k: v for k, v in self._expiry.items() if v > now}

    def is_locked(self, target_id: int) -> bool:
        with self._mutex:
            return self._expiry.get(target_id, 0.0) > self._clock()

    def try_lock(self, target_id: int, reason: LockReason) -> bool:
        with self._mutex:
            now = self._clock()
            if self._expiry.get(target_id, 0.0) > now:
                return False
            self._prune_locked(now)
            self._expiry[target_id] = now + reason.value
            return True

    def mark(self, target_id: int, reason: LockReason) -> None:
        """Đặt/gia hạn khóa, không bao giờ rút ngắn khóa hiện có."""
        with self._mutex:
            new_expiry = self._clock() + reason.value
            self._expiry[target_id] = max(self._expiry.get(target_id, 0.0), new_expiry)
