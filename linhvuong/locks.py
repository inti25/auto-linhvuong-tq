"""Khóa mục tiêu: tránh nhiều nhiệm vụ đánh trùng cùng một Mục tiêu."""

import enum
import threading
import time
from typing import Callable, Optional


class LockReason(enum.Enum):
    CLAIMED = 300  # nhiệm vụ này đã nhận Mục tiêu (giây)
    TAKEN_BY_OTHER = 600  # server báo (ret=230) đã có người đánh (giây)


class TargetLocks:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._expiry: dict[int, float] = {}
        self._owners: dict[int, int] = {}
        self._mutex = threading.Lock()

    _PRUNE_THRESHOLD = 256

    def _prune_locked(self, now: float) -> None:
        """Dọn các khóa đã hết hạn (gọi khi đang giữ mutex) để tránh rò rỉ bộ nhớ khi chạy dài."""
        if len(self._expiry) > self._PRUNE_THRESHOLD:
            self._expiry = {k: v for k, v in self._expiry.items() if v > now}
            self._owners = {k: v for k, v in self._owners.items() if k in self._expiry}

    def is_locked(self, target_id: int) -> bool:
        with self._mutex:
            return self._expiry.get(target_id, 0.0) > self._clock()

    def is_locked_by_other(self, target_id: int, owner: Optional[int] = None) -> bool:
        """Kiểm tra xem mục tiêu có đang bị khóa bởi căn cứ/nhiệm vụ khác hay không."""
        with self._mutex:
            if self._expiry.get(target_id, 0.0) <= self._clock():
                return False
            if owner is None:
                return True
            return self._owners.get(target_id) != owner

    def try_lock(self, target_id: int, reason: LockReason, owner: Optional[int] = None) -> bool:
        with self._mutex:
            now = self._clock()
            if self._expiry.get(target_id, 0.0) > now:
                # Nếu cùng một chủ sở hữu (owner) thì cho phép gia hạn khóa
                if owner is not None and self._owners.get(target_id) == owner:
                    self._expiry[target_id] = now + reason.value
                    return True
                return False
            self._prune_locked(now)
            self._expiry[target_id] = now + reason.value
            if owner is not None:
                self._owners[target_id] = owner
            elif target_id in self._owners:
                del self._owners[target_id]
            return True

    def mark(self, target_id: int, reason: LockReason, owner: Optional[int] = None) -> None:
        """Đặt/gia hạn khóa, không bao giờ rút ngắn khóa hiện có."""
        with self._mutex:
            now = self._clock()
            new_expiry = now + reason.value
            self._expiry[target_id] = max(self._expiry.get(target_id, 0.0), new_expiry)
            if owner is not None:
                self._owners[target_id] = owner

    def release(self, target_id: int, owner: Optional[int] = None) -> bool:
        """Giải phóng khóa mục tiêu (nếu là chủ sở hữu hoặc không chỉ định chủ sở hữu)."""
        with self._mutex:
            if self._expiry.get(target_id, 0.0) <= self._clock():
                self._expiry.pop(target_id, None)
                self._owners.pop(target_id, None)
                return True
            if owner is None or self._owners.get(target_id) == owner:
                self._expiry.pop(target_id, None)
                self._owners.pop(target_id, None)
                return True
            return False
