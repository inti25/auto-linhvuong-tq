import threading
import time
from unittest.mock import MagicMock
import pytest

from linhvuong.dashboard import BinhManAutoRunner
from linhvuong.scan import BasePeer
from linhvuong.tasks.base import CaptchaRequired


def test_binh_man_multi_base_runs_concurrently():
    """Tái hiện và xác nhận: Khi 1 thành đang xuất quân / xử lý (run_once bị block), các thành khác hoạt động song song."""
    task1_in_run_once = threading.Event()
    task2_executed_concurrently = threading.Event()

    task1 = MagicMock()
    task1.origin_id = 101
    task1.base_name = "Thành 1"
    task1.stop_event = threading.Event()

    task2 = MagicMock()
    task2.origin_id = 102
    task2.base_name = "Thành 2"
    task2.stop_event = threading.Event()

    def task1_run_once():
        task1_in_run_once.set()
        # Giả lập Thành 1 xuất quân và đang theo dõi trận đánh (bị block)
        # Nhờ đa luồng, Thành 2 chạy đồng thời trong lúc Thành 1 còn đang chờ
        for _ in range(50):
            if task2_executed_concurrently.is_set():
                break
            time.sleep(0.02)
        return "attacked"

    def task2_run_once():
        # Kiểm tra xem Thành 2 có chạy trong lúc Thành 1 đang trong run_once không
        if task1_in_run_once.is_set():
            task2_executed_concurrently.set()
        return "attacked"

    task1.run_once.side_effect = task1_run_once
    task2.run_once.side_effect = task2_run_once

    logs = []
    runner = BinhManAutoRunner(
        [task1, task2],
        interval=5.0,
        log_cb=lambda m: logs.append(m),
        status_cb=lambda s: None,
    )

    try:
        runner.start()
        # Xác nhận Thành 2 chạy song song trong khi Thành 1 đang bận
        assert task2_executed_concurrently.wait(timeout=1.0), (
            "Thành 2 không chạy song song trong khi Thành 1 đang xuất quân / theo dõi trận!"
        )
    finally:
        runner.stop()
        runner.join(timeout=1.0)
    assert not runner.is_alive()


def test_binh_man_runner_stops_all_workers_on_captcha():
    """Khi bất kỳ thành nào gặp CaptchaRequired, toàn bộ runner phải dừng và thông báo trạng thái."""
    task1 = MagicMock()
    task1.origin_id = 101
    task1.base_name = "Thành 1"
    task1.run_once.side_effect = CaptchaRequired()

    task2 = MagicMock()
    task2.origin_id = 102
    task2.base_name = "Thành 2"
    task2.run_once.return_value = "no_target"

    statuses = []
    logs = []
    runner = BinhManAutoRunner(
        [task1, task2],
        interval=10.0,
        log_cb=lambda m: logs.append(m),
        status_cb=lambda s: statuses.append(s),
    )

    runner.start()
    runner.join(timeout=2.0)
    assert not runner.is_alive()
    assert "Cần giải Captcha" in statuses
    assert runner.stop_event.is_set()


def test_binh_man_runner_single_task_backward_compatibility():
    """Tương thích ngược: Khi truyền 1 task đơn lẻ, runner chạy bình thường và prefix không bị trùng lặp."""
    task = MagicMock()
    task.origin_id = 201
    task.base_name = "Thành Đơn"
    task.run_once.return_value = "attacked"

    logs = []
    runner = BinhManAutoRunner(
        task,
        interval=5.0,
        log_cb=lambda m: logs.append(m),
        status_cb=lambda s: None,
    )

    assert runner.task == task
    runner.start()
    time.sleep(0.1)
    runner.stop()
    runner.join(timeout=1.0)

    assert any("Lượt 1: Kết quả -> attacked" in m for m in logs)
    assert runner.is_running() is False


def test_binh_man_dynamic_peers_origin_update():
    """Kiểm tra peers_fn cập nhật tọa độ động khi một Doanh Trại di chuyển."""
    task1 = MagicMock()
    task1.origin_id = 101
    task1.origin = (10, 10)
    task1.radius = 5
    task1.man_types = [7, 8]
    task1.base_name = "Trại 1"

    task2 = MagicMock()
    task2.origin_id = 102
    task2.origin = (20, 20)
    task2.radius = 8
    task2.man_types = [9, 10]
    task2.base_name = "Thành 2"

    tasks = [task1, task2]

    def _make_peers_fn(for_task_id: int):
        def _get_peers() -> list[BasePeer]:
            result = []
            for other in tasks:
                if other.origin_id != for_task_id:
                    result.append(
                        BasePeer(
                            base_id=other.origin_id,
                            ox=other.origin[0],
                            oy=other.origin[1],
                            radius=other.radius,
                            target_types=other.man_types,
                            origin=other.origin,
                            mantypes=other.man_types,
                            name=getattr(other, "base_name", ""),
                        )
                    )
            return result
        return _get_peers

    peers_for_task2 = _make_peers_fn(task2.origin_id)
    initial_peers = peers_for_task2()
    assert len(initial_peers) == 1
    assert initial_peers[0].ox == 10 and initial_peers[0].oy == 10

    # Trại 1 di chuyển tới tọa độ mới
    task1.origin = (12, 11)
    updated_peers = peers_for_task2()
    assert updated_peers[0].ox == 12 and updated_peers[0].oy == 11
