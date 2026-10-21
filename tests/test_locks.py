from linhvuong.locks import LockReason, TargetLocks


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make():
    clock = FakeClock()
    return TargetLocks(clock=clock), clock


def test_unlocked_target_can_be_locked_once():
    locks, _ = make()
    assert locks.try_lock(7, LockReason.CLAIMED) is True
    assert locks.try_lock(7, LockReason.CLAIMED) is False
    assert locks.is_locked(7)


def test_claimed_lock_expires_after_300_seconds():
    locks, clock = make()
    locks.try_lock(7, LockReason.CLAIMED)
    clock.now += 299
    assert locks.is_locked(7)
    clock.now += 2
    assert not locks.is_locked(7)
    assert locks.try_lock(7, LockReason.CLAIMED) is True


def test_taken_by_other_lock_expires_after_600_seconds():
    locks, clock = make()
    locks.try_lock(9, LockReason.TAKEN_BY_OTHER)
    clock.now += 599
    assert locks.is_locked(9)
    clock.now += 2
    assert not locks.is_locked(9)


def test_longer_lock_is_not_shortened_by_new_claim():
    locks, clock = make()
    locks.try_lock(5, LockReason.TAKEN_BY_OTHER)
    locks.mark(5, LockReason.CLAIMED)
    clock.now += 400
    assert locks.is_locked(5)


def test_other_targets_are_independent():
    locks, _ = make()
    locks.try_lock(1, LockReason.CLAIMED)
    assert not locks.is_locked(2)
