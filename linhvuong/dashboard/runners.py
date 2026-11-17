"""Các Runner chạy ngầm đa luồng (Thread-Safe Background Runners)."""

import logging
import threading
import time
from typing import Callable, Optional, Union

from ..tasks.base import CaptchaRequired
from ..tasks.binh_man import BinhMan
from ..tasks.building import BuildingTask
from ..tasks.goi_dan import GoiDan
from ..tasks.research import ResearchTask


class BaseTaskRunner(threading.Thread):
    def __init__(self, task_name: str, log_cb: Callable[[str], None], status_cb: Callable[[str], None]):
        super().__init__(daemon=True)
        self.task_name = task_name
        self.logger = logging.getLogger(f"linhvuong.tasks.{task_name}")
        self.log_cb = log_cb
        self.status_cb = status_cb
        self.stop_event = threading.Event()

    def log(self, msg: str):
        self.logger.info(msg)
        self.log_cb(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def is_running(self) -> bool:
        return self.is_alive() and not self.stop_event.is_set()

    def stop(self):
        self.stop_event.set()
        self.log(f"⏹️ Đang dừng nhiệm vụ {self.task_name}...")
        self.status_cb("Đang dừng...")

    def wait(self, seconds: float) -> bool:
        return self.stop_event.wait(seconds)

    def wait_cycle(self, seconds: float, jitter: float = 2.0) -> bool:
        """Chờ một chu kỳ lặp với cơ chế giãn cách ngẫu nhiên nhẹ (Jitter) chống phát hiện bot.

        Nếu seconds <= 3.0, giữ nguyên (tối thiểu 1.0s).
        Nếu seconds > 3.0, thêm ngẫu nhiên trong khoảng [-jitter, +jitter], đảm bảo tối thiểu 3.0s.
        Trả về True nếu stop_event được kích hoạt.
        """
        if seconds <= 3.0:
            actual_wait = max(1.0, seconds)
        else:
            import random
            actual_wait = max(3.0, seconds + random.uniform(-jitter, jitter))
        return self.stop_event.wait(actual_wait)


class GoiDanAutoRunner(BaseTaskRunner):
    def __init__(self, task: GoiDan, interval: float, log_cb, status_cb):
        super().__init__("Gọi Dân", log_cb, status_cb)
        self.task = task
        self.interval = interval

    def run(self):
        self.task.stop_event = self.stop_event
        if getattr(self.task, "sleep_fn", None) is time.sleep:
            self.task.sleep_fn = lambda s: self.wait(s)
        self.status_cb("Đang chạy...")
        self.log(f"🚀 Bắt đầu nhiệm vụ Gọi Dân (chế độ: {self.task.mode})...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            try:
                res = self.task.run_once()
                self.log(f"Lượt {cycle}: Kết quả -> {res}")
                if res == "call_failed:236":
                    self.log("⚠️ Máy chủ chưa mở sự kiện Gọi Vong Linh (mã lỗi 236: 当前没有相关活动). Tạm dừng nhiệm vụ Gọi Man.")
                    self.status_cb("Sự kiện chưa mở")
                    break
                elif res == "call_failed:90":
                    self.log("❌ Hết đạo cụ gọi mục tiêu trong túi đồ (mã lỗi 90). Tạm dừng nhiệm vụ Gọi Man.")
                    self.status_cb("Hết đạo cụ")
                    break
            except CaptchaRequired:
                self.logger.warning("Server yêu cầu Captcha! Dừng nhiệm vụ Gọi Dân.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nhiệm vụ để giải thủ công.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Gọi Dân: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait_cycle(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Gọi Dân đã dừng.")


class BinhManAutoRunner(BaseTaskRunner):
    def __init__(self, task_or_tasks: Union[BinhMan, list[BinhMan]], interval: float, log_cb, status_cb):
        super().__init__("Bình Man", log_cb, status_cb)
        if isinstance(task_or_tasks, list):
            self.tasks: list[BinhMan] = task_or_tasks
        else:
            self.tasks: list[BinhMan] = [task_or_tasks]
        self.interval = interval
        self.worker_threads: list[threading.Thread] = []

    @property
    def task(self) -> Optional[BinhMan]:
        return self.tasks[0] if self.tasks else None

    @task.setter
    def task(self, val: BinhMan):
        self.tasks = [val]

    def _run_base_worker(self, task: BinhMan):
        base_label = getattr(task, "base_name", "") or f"Căn cứ {task.origin_id}"
        cycle = 0
        consec_no_target = 0
        while not self.stop_event.is_set():
            cycle += 1
            has_action = False
            res = None
            try:
                res = task.run_once()
                prefix = f"[{base_label}] " if len(self.tasks) > 1 else ""
                self.log(f"{prefix}Lượt {cycle}: Kết quả -> {res}")
                if res not in ("no_target", "generals_busy", "camp_frozen", "waiting_morale", "target_claimed_by_other", "waiting_stamina"):
                    has_action = True
            except CaptchaRequired:
                self.logger.warning(f"Server yêu cầu Captcha tại [{base_label}]! Dừng nhiệm vụ Bình Man.")
                self.log(f"⚠️ [{base_label}] Server yêu cầu Captcha! Dừng nhiệm vụ.")
                self.status_cb("Cần giải Captcha")
                self.stop_event.set()
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ tại [{base_label}]: {e}")
                self.log(f"❌ [{base_label}] Lỗi ngoại lệ: {e}")

            if self.stop_event.is_set():
                break

            if res == "no_target":
                consec_no_target += 1
                backoff_factor = 1.5 ** min(consec_no_target - 1, 3)
                wait_time = min(60.0, self.interval * backoff_factor)
            else:
                consec_no_target = 0
                wait_time = 1.0 if has_action else self.interval

            if self.wait_cycle(wait_time if not has_action else min(wait_time, 2.0)):
                break

    def run(self):
        for t in self.tasks:
            t.stop_event = self.stop_event
            if getattr(t, "sleep_fn", None) is time.sleep:
                t.sleep_fn = lambda s: self.wait(s)
        self.status_cb("Đang chạy...")
        num_bases = len(self.tasks)
        if num_bases > 1:
            self.log(f"🚀 Bắt đầu điều phối Bình Man Đa Căn Cứ Đa Luồng cho {num_bases} căn cứ...")
        else:
            self.log("🚀 Bắt đầu nhiệm vụ Bình Man...")

        self.worker_threads = []
        for t in self.tasks:
            base_label = getattr(t, "base_name", "") or f"Căn cứ {t.origin_id}"
            w = threading.Thread(
                target=self._run_base_worker,
                args=(t,),
                name=f"BMWorker-{base_label}",
                daemon=True,
            )
            self.worker_threads.append(w)
            w.start()

        while not self.stop_event.is_set() and any(w.is_alive() for w in self.worker_threads):
            for w in self.worker_threads:
                w.join(timeout=0.2)

        for w in self.worker_threads:
            w.join(timeout=1.0)

        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Bình Man đã dừng.")


class BuildingAutoRunner(BaseTaskRunner):
    def __init__(
        self,
        task_or_tasks: Union[BuildingTask, list[BuildingTask]],
        interval: float,
        log_cb,
        status_cb,
        sync_cb: Optional[Callable[[int, dict], None]] = None,
    ):
        super().__init__("Xây Dựng", log_cb, status_cb)
        if isinstance(task_or_tasks, list):
            self.tasks: list[BuildingTask] = task_or_tasks
        else:
            self.tasks: list[BuildingTask] = [task_or_tasks]
        self.interval = interval
        self.sync_cb = sync_cb
        if sync_cb:
            for t in self.tasks:
                if not getattr(t, "on_sync_data", None):
                    t.on_sync_data = sync_cb

    @property
    def task(self) -> Optional[BuildingTask]:
        return self.tasks[0] if self.tasks else None

    @task.setter
    def task(self, val: BuildingTask):
        self.tasks = [val]

    def run(self):
        self.status_cb("Đang chạy...")
        num_bases = len(self.tasks)
        self.log(f"🚀 Bắt đầu giám sát & nâng cấp công trình cho {num_bases} căn cứ...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            all_completed = True
            try:
                now_mono = time.monotonic()
                tasks_needing_c77 = [
                    t for t in self.tasks
                    if getattr(t, "gateway", None) is not None
                    and hasattr(t, "set_c77_cache")
                    and (
                        getattr(t, "auto_boost", False)
                        or getattr(t, "auto_speedup", False)
                        or not getattr(t, "_synced_once", False)
                        or now_mono >= getattr(t, "_busy_until", 0.0)
                    )
                ]
                if len(tasks_needing_c77) > 1:
                    shared_resp = tasks_needing_c77[0].gateway.call(
                        "Common.ashx", 77, {"cid": str(tasks_needing_c77[0].city_id), "_": ""}
                    ) or {}
                    if shared_resp.get("ret", 0) in (110, 73):
                        raise CaptchaRequired()
                    if shared_resp and shared_resp.get("ret", -1) == 0:
                        fetched_at = time.time()
                        for t in tasks_needing_c77:
                            t.set_c77_cache(shared_resp, fetched_at)

                missing_tasks = []
                for t in list(self.tasks):
                    if self.stop_event.is_set():
                        break
                    res = t.run_once()
                    if res == "city_not_found":
                        missing_tasks.append(t)
                        continue
                    if res != "all_buildings_completed":
                        all_completed = False

                if missing_tasks:
                    self.tasks = [t for t in self.tasks if t not in missing_tasks]
                    if not self.tasks:
                        self.log("⚠️ Không còn căn cứ hợp lệ nào trong hàng đợi xây dựng.")
                        self.status_cb("Hoàn tất quy hoạch")
                        break

                if all_completed and self.tasks:
                    self.log("🎉 Toàn bộ công trình quy hoạch của tất cả các căn cứ đã hoàn tất!")
                    self.status_cb("Hoàn tất quy hoạch")
                    break
            except CaptchaRequired:
                self.logger.warning("Server yêu cầu Captcha! Dừng nâng cấp Xây Dựng.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nâng cấp.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Xây Dựng: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait_cycle(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Xây Dựng đã dừng.")


class ResearchAutoRunner(BaseTaskRunner):
    def __init__(
        self,
        task: ResearchTask,
        interval: float,
        log_cb,
        status_cb,
        sync_cb: Optional[Callable[[int, dict, Optional[tuple]], None]] = None,
    ):
        super().__init__("Nghiên Cứu", log_cb, status_cb)
        self.task = task
        self.interval = interval
        self.sync_cb = sync_cb
        if sync_cb and not getattr(self.task, "on_sync_data", None):
            self.task.on_sync_data = sync_cb

    def run(self):
        self.status_cb("Đang chạy...")
        self.log("🚀 Bắt đầu giám sát viện Đại Học & nghiên cứu kỹ thuật...")
        cycle = 0
        while not self.stop_event.is_set():
            cycle += 1
            try:
                res = self.task.run_once()
                self.log(f"Chu kỳ {cycle}: Trạng thái -> {res}")
                if res == "all_techs_completed":
                    self.log("🎉 Toàn bộ 29 kỹ thuật mục tiêu đã hoàn tất!")
                    self.status_cb("Hoàn tất 29 kỹ thuật")
                    break
            except CaptchaRequired:
                self.logger.warning("Server yêu cầu Captcha! Dừng nghiên cứu Viện Đại Học.")
                self.log("⚠️ Server yêu cầu Captcha! Dừng nghiên cứu.")
                self.status_cb("Cần giải Captcha")
                break
            except Exception as e:
                self.logger.exception(f"Lỗi ngoại lệ trong nhiệm vụ Nghiên Cứu: {e}")
                self.log(f"❌ Lỗi ngoại lệ: {e}")

            if self.wait_cycle(self.interval):
                break
        self.status_cb("Đã dừng")
        self.log("⏹️ Nhiệm vụ Nghiên Cứu đã dừng.")
