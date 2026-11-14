"""Động Cơ Điều Phối Tác Vụ (AutomationEngine & ExecutableTask).

Module hướng miền độc lập chịu trách nhiệm:
- Chuẩn hóa vòng đời thực thi nền của mọi tác vụ tự động hóa (Thảo Phạt, Xây Dựng, Nghiên Cứu, Bình Man, Gọi Dân).
- Áp dụng Độ Trễ Ngẫu Nhiên (anti-bot jitter) theo ADR-0011.
- Tự động phát hiện và tạm dừng khi gặp Captcha (CaptchaRequired), hỗ trợ resume sau khi giải.
- Giao diện đăng ký và giám sát tập trung: start, stop, stop_all, is_running, get_status, resume.
"""

import logging
import random
import threading
import time
from typing import Any, Callable, Optional, Protocol, Union

from .tasks.base import CaptchaRequired

logger = logging.getLogger("linhvuong.engine")


class TaskStatus:
    STOPPED = "Đã dừng"
    STARTING = "Đang khởi động..."
    RUNNING = "Đang chạy..."
    WAITING = "Đang chờ..."
    STOPPING = "Đang dừng..."
    PAUSED_CAPTCHA = "Cần giải Captcha"
    COMPLETED = "Hoàn tất quy hoạch"
    ERROR = "Lỗi ngoại lệ"


class ExecutableTask(Protocol):
    """Seam chuẩn hóa cho mọi tác vụ tự động hóa."""

    def run_step(self) -> str:
        """Thực thi một bước hoặc một chu kỳ của nhiệm vụ."""
        ...

    def reset(self) -> None:
        """Xóa hoặc đặt lại các trạng thái tạm thời (nếu có)."""
        ...


class TaskRunnerThread(threading.Thread):
    """Luồng thực thi nền chuẩn hóa cho một tác vụ tự động hóa."""

    def __init__(
        self,
        task_id: str,
        task: Any,
        interval: float,
        jitter: float = 2.0,
        log_cb: Optional[Callable[[str, str], None]] = None,
        status_cb: Optional[Callable[[str, str], None]] = None,
    ):
        super().__init__(name=f"AutomationRunner-{task_id}", daemon=True)
        self.task_id = task_id
        self.task = task
        self.interval = max(0.5, float(interval))
        self.jitter = max(0.0, float(jitter))
        self.log_cb = log_cb or (lambda tid, msg: None)
        self.status_cb = status_cb or (lambda tid, status: None)
        self.stop_event = threading.Event()
        self.paused_for_captcha = threading.Event()
        self.status = TaskStatus.STOPPED

    def _set_status(self, new_status: str):
        self.status = new_status
        self.status_cb(self.task_id, new_status)

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_cb(self.task_id, f"[{ts}] {msg}")

    def stop(self):
        self.stop_event.set()
        self.paused_for_captcha.clear()
        self._set_status(TaskStatus.STOPPING)

    def resume(self):
        """Tiếp tục chạy sau khi giải Captcha."""
        if self.paused_for_captcha.is_set():
            self.paused_for_captcha.clear()

    def wait_cycle(self, seconds: float, jitter: float = 2.0) -> bool:
        """Chờ một chu kỳ lặp với Độ Trễ Ngẫu Nhiên (Jitter) chống bot (ADR-0011)."""
        if seconds <= 3.0:
            actual_wait = max(1.0, seconds)
        else:
            actual_wait = max(3.0, seconds + random.uniform(-jitter, jitter))

        # Phân mảnh thời gian chờ để phản ứng nhanh khi nhận tín hiệu dừng
        end_time = time.time() + actual_wait
        while time.time() < end_time and not self.stop_event.is_set():
            time.sleep(min(0.2, max(0.01, end_time - time.time())))

        return self.stop_event.is_set()

    def run(self):
        self._set_status(TaskStatus.RUNNING)
        self._log(f"🚀 Bắt đầu nhiệm vụ '{self.task_id}' (chu kỳ: {self.interval}s, jitter: ±{self.jitter}s)...")
        cycle = 0

        # Trường hợp task là một runner độc lập (như ThaoPhatAutoRunner)
        if hasattr(self.task, "run") and not hasattr(self.task, "run_step") and not hasattr(self.task, "run_once") and not isinstance(self.task, list):
            try:
                # Đồng bộ stop_event nếu task có stop_event
                if hasattr(self.task, "stop_event"):
                    self.task.stop_event = self.stop_event
                self.task.run()
            except Exception as e:
                logger.exception(f"Ngoại lệ trong runner riêng '{self.task_id}': {e}")
                self._log(f"❌ Lỗi ngoại lệ: {e}")
                self._set_status(TaskStatus.ERROR)
            finally:
                self._set_status(TaskStatus.STOPPED)
                self._log(f"⏹️ Nhiệm vụ '{self.task_id}' đã dừng.")
            return

        while not self.stop_event.is_set():
            cycle += 1

            # Kiểm tra trạng thái tạm dừng do Captcha
            if self.paused_for_captcha.is_set():
                time.sleep(0.5)
                continue

            try:
                if hasattr(self.task, "run_step"):
                    res = self.task.run_step()
                elif hasattr(self.task, "run_once"):
                    res = self.task.run_once()
                elif isinstance(self.task, (list, tuple)):
                    all_completed = True
                    for sub in self.task:
                        if self.stop_event.is_set():
                            break
                        if hasattr(sub, "run_step"):
                            sub_res = sub.run_step()
                        elif hasattr(sub, "run_once"):
                            sub_res = sub.run_once()
                        else:
                            sub_res = "ok"
                        if sub_res != "all_buildings_completed":
                            all_completed = False

                    if all_completed and self.task:
                        self._log("🎉 Toàn bộ công trình quy hoạch của tất cả các căn cứ đã hoàn tất!")
                        self._set_status(TaskStatus.COMPLETED)
                        break
                    res = "ok"
                elif callable(self.task):
                    res = str(self.task())
                else:
                    res = "ok"

                if res in ("all_buildings_completed", "nien_thu_jade_obtained", "completed"):
                    self._log(
                        "🎉 Đã nhận 玉兔呈祥 — Hoàn tất Auto Niên Thú!"
                        if res == "nien_thu_jade_obtained"
                        else "🎉 Toàn bộ công trình quy hoạch đã hoàn tất!"
                    )
                    self._set_status(TaskStatus.COMPLETED)
                    break

            except CaptchaRequired:
                logger.warning(f"Server yêu cầu Captcha trong nhiệm vụ '{self.task_id}'!")
                self._log("⚠️ Server yêu cầu Captcha! Tạm dừng tác vụ chờ giải mã.")
                self._set_status(TaskStatus.PAUSED_CAPTCHA)
                self.paused_for_captcha.set()
                continue
            except Exception as e:
                logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ '{self.task_id}': {e}")
                self._log(f"❌ Lỗi ngoại lệ: {e}")
                self._set_status(TaskStatus.ERROR)

            if self.wait_cycle(self.interval, self.jitter):
                break

        if self.status != TaskStatus.COMPLETED:
            self._set_status(TaskStatus.STOPPED)
        self._log(f"⏹️ Nhiệm vụ '{self.task_id}' đã dừng.")


class AutomationEngine:
    """Động Cơ Điều Phối Tác Vụ Trung Tâm (Automation Coordinator)."""

    def __init__(
        self,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
    ):
        self._runners: dict[str, TaskRunnerThread] = {}
        self._lock = threading.Lock()
        self.on_log = on_log
        self.on_status = on_status

    def subscribe(
        self,
        on_log: Optional[Callable[[str, str], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
    ):
        """Đăng ký callbacks nhận sự kiện từ các tác vụ."""
        if on_log:
            self.on_log = on_log
        if on_status:
            self.on_status = on_status

    def _dispatch_log(self, task_id: str, msg: str):
        if self.on_log:
            try:
                self.on_log(task_id, msg)
            except Exception:
                pass

    def _dispatch_status(self, task_id: str, status: str):
        if self.on_status:
            try:
                self.on_status(task_id, status)
            except Exception:
                pass

    def start(
        self,
        task_id: str,
        task: Any,
        interval: float,
        jitter: float = 2.0,
    ) -> None:
        """Khởi động một tác vụ tự động hóa."""
        with self._lock:
            # Dừng runner cũ nếu đang chạy
            old_runner = self._runners.get(task_id)
            if old_runner and old_runner.is_alive():
                old_runner.stop()
                old_runner.join(timeout=1.0)

            runner = TaskRunnerThread(
                task_id=task_id,
                task=task,
                interval=interval,
                jitter=jitter,
                log_cb=self._dispatch_log,
                status_cb=self._dispatch_status,
            )
            self._runners[task_id] = runner
            runner.start()

    def stop(self, task_id: str, wait_timeout: Optional[float] = None) -> None:
        """Dừng một tác vụ cụ thể."""
        with self._lock:
            runner = self._runners.get(task_id)
            if runner:
                runner.stop()
                if wait_timeout:
                    runner.join(timeout=wait_timeout)

    def stop_all(self, wait_timeout: Optional[float] = None) -> None:
        """Dừng tất cả các tác vụ đang chạy."""
        with self._lock:
            runners = list(self._runners.values())

        for r in runners:
            r.stop()
        if wait_timeout:
            for r in runners:
                r.join(timeout=wait_timeout)

    def resume(self, task_id: str) -> None:
        """Tiếp tục tác vụ đang bị tạm dừng do Captcha."""
        with self._lock:
            runner = self._runners.get(task_id)
            if runner:
                runner.resume()

    def is_running(self, task_id: str) -> bool:
        """Kiểm tra tác vụ có đang hoạt động hay không."""
        with self._lock:
            runner = self._runners.get(task_id)
            return bool(runner and runner.is_alive() and not runner.stop_event.is_set())

    def get_status(self, task_id: str) -> str:
        """Lấy trạng thái hiện tại của tác vụ."""
        with self._lock:
            runner = self._runners.get(task_id)
            if not runner:
                return TaskStatus.STOPPED
            return runner.status

    def get_runner(self, task_id: str) -> Optional[TaskRunnerThread]:
        """Truy xuất runner thread của tác vụ."""
        with self._lock:
            return self._runners.get(task_id)

    def list_tasks(self) -> list[str]:
        """Danh sách định danh các tác vụ đã đăng ký."""
        with self._lock:
            return list(self._runners.keys())

