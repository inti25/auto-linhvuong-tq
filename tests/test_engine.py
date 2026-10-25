import time
import pytest

from linhvuong.engine import AutomationEngine, TaskRunnerThread, TaskStatus
from linhvuong.tasks.base import CaptchaRequired


class DummyStepTask:
    def __init__(self, step_responses: list[str] = None):
        self.step_responses = step_responses or ["ok"]
        self.call_count = 0

    def run_step(self) -> str:
        self.call_count += 1
        idx = min(self.call_count - 1, len(self.step_responses) - 1)
        resp = self.step_responses[idx]
        if resp == "captcha":
            raise CaptchaRequired()
        return resp


class DummyOnceTask:
    def __init__(self):
        self.call_count = 0

    def run_once(self) -> str:
        self.call_count += 1
        return "ok"


def test_engine_start_stop_lifecycle():
    engine = AutomationEngine()
    task = DummyStepTask(["ok", "ok"])

    logs = []
    statuses = []
    engine.subscribe(
        on_log=lambda tid, msg: logs.append((tid, msg)),
        on_status=lambda tid, status: statuses.append((tid, status)),
    )

    engine.start("test_task", task, interval=0.1, jitter=0.0)
    time.sleep(0.15)
    assert engine.is_running("test_task")
    assert task.call_count >= 1

    engine.stop("test_task", wait_timeout=1.0)
    assert not engine.is_running("test_task")
    assert engine.get_status("test_task") in (TaskStatus.STOPPED, TaskStatus.STOPPING)
    assert len(logs) > 0


def test_engine_supports_run_once_task():
    engine = AutomationEngine()
    task = DummyOnceTask()

    engine.start("once_task", task, interval=0.1, jitter=0.0)
    time.sleep(0.15)
    assert task.call_count >= 1
    engine.stop("once_task", wait_timeout=1.0)


def test_engine_multi_task_list_completion():
    engine = AutomationEngine()
    task1 = DummyStepTask(["all_buildings_completed"])
    task2 = DummyStepTask(["all_buildings_completed"])

    engine.start("multi_building", [task1, task2], interval=0.1, jitter=0.0)
    time.sleep(0.2)

    assert engine.get_status("multi_building") == TaskStatus.COMPLETED
    assert not engine.is_running("multi_building")


def test_engine_captcha_pause_and_resume():
    engine = AutomationEngine()
    task = DummyStepTask(["captcha", "ok"])

    engine.start("captcha_task", task, interval=0.1, jitter=0.0)
    time.sleep(0.15)

    assert engine.get_status("captcha_task") == TaskStatus.PAUSED_CAPTCHA

    # Resume after captcha solved
    engine.resume("captcha_task")
    time.sleep(0.15)

    assert engine.is_running("captcha_task")
    engine.stop("captcha_task", wait_timeout=1.0)


def test_engine_stop_all():
    engine = AutomationEngine()
    t1 = DummyStepTask(["ok"])
    t2 = DummyStepTask(["ok"])

    engine.start("t1", t1, interval=0.2, jitter=0.0)
    engine.start("t2", t2, interval=0.2, jitter=0.0)
    assert engine.is_running("t1")
    assert engine.is_running("t2")

    engine.stop_all(wait_timeout=1.0)
    assert not engine.is_running("t1")
    assert not engine.is_running("t2")


def test_engine_list_tasks():
    engine = AutomationEngine()
    t1 = DummyStepTask(["ok"])
    t2 = DummyStepTask(["ok"])

    engine.start("task_alpha", t1, interval=0.2, jitter=0.0)
    engine.start("task_beta", t2, interval=0.2, jitter=0.0)

    task_list = engine.list_tasks()
    assert "task_alpha" in task_list
    assert "task_beta" in task_list
    engine.stop_all(wait_timeout=1.0)

