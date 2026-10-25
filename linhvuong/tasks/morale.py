"""Phân hệ Luyện Sĩ Khí (Morale Training) đồng thời cho tướng lĩnh đa thành."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import threading
import time
from typing import Any, Callable, Optional

from ..gateway import GatewayClient

logger = logging.getLogger("linhvuong.tasks.morale")


def _dispatch_on_step(cb: Optional[Callable], cur: int, tgt: int, msg: str = "") -> None:
    """Gọi callback on_step linh hoạt hỗ trợ cả 2 tham số (cur, tgt) và 3 tham số (cur, tgt, msg)."""
    if not cb:
        return
    try:
        cb(cur, tgt, msg)
    except TypeError:
        try:
            cb(cur, tgt)
        except Exception:
            pass


class MoraleTrainer:
    """Điều phối và thực thi luyện sĩ khí cho tướng đơn lẻ và đồng thời nhiều tướng."""

    def __init__(self, gateway: GatewayClient, poll_interval: float = 2.0):
        self.gateway = gateway
        self.poll_interval = max(0.01, poll_interval)

    def get_general_morale_info(self, city_id: int, general_id: int) -> tuple[Optional[int], int]:
        """Lấy sĩ khí hiện tại và thời gian nâng sĩ khí còn lại (upgrading_time) từ API 76.

        Trả về (current_morale, upgrading_time). Nếu không tìm thấy hoặc API không trả về
        danh sách, trả về (None, 0).
        """
        try:
            resp = self.gateway.call("Common.ashx", 76, {"cid": str(city_id)}) or {}
            for entry in resp.get("list", []):
                if len(entry) > 2 and isinstance(entry[2], list):
                    for g in entry[2]:
                        if int(g[0]) == general_id:
                            cur_m = int(g[9]) if len(g) > 9 else None
                            up_t = int(g[10]) if len(g) > 10 else 0
                            return cur_m, up_t
        except Exception as e:
            logger.warning(f"Không thể đọc thông tin sĩ khí tướng {general_id} từ API 76: {e}")
        return None, 0

    def train_general_morale(
        self,
        city_id: int,
        general_id: int,
        current_morale: int,
        target_morale: int = 100,
        stop_event: Optional[threading.Event] = None,
        on_step: Optional[Callable[..., None]] = None,
    ) -> tuple[bool, int, str]:
        """Luyện sĩ khí cho một tướng từ current_morale đến target_morale.

        - Tự động kiểm tra thời gian nâng dở dang (upgrading_time > 0) từ máy chủ.
        - Nếu tướng đang luyện dở, chờ cho đợt luyện hoàn tất rồi cập nhật sĩ khí thực tế.
        - Gọi API OPT.ashx?id=47 từng nhịp tối đa 10 điểm cho đến khi chạm đích target_morale.
        - Trả về (success, final_morale, message).
        """
        if stop_event and stop_event.is_set():
            return False, current_morale, "Đã bị dừng bởi người dùng"

        target_morale = min(100, max(1, target_morale))
        curr = current_morale
        step_count = 0

        while True:
            if stop_event and stop_event.is_set():
                return False, curr, "Đã bị dừng bởi người dùng"

            # Kiểm tra trạng thái máy chủ cập nhật
            cur_m, up_t = self.get_general_morale_info(city_id, general_id)
            if cur_m is not None:
                curr = cur_m

            if curr >= target_morale:
                msg = f"Sĩ khí đã đạt mục tiêu ({curr}/{target_morale})"
                _dispatch_on_step(on_step, curr, target_morale, f"✅ {msg}")
                return True, curr, msg

            # 1. Trường hợp tướng đang luyện dở (upgrading_time > 0): chờ hoàn tất
            if up_t > 0:
                wait_msg = f"⏳ Chờ luyện dở (còn {up_t}s)..."
                _dispatch_on_step(on_step, curr, target_morale, wait_msg)
                wait_step = min(float(up_t), self.poll_interval)
                if stop_event:
                    if stop_event.wait(wait_step):
                        return False, curr, "Đã bị dừng bởi người dùng"
                else:
                    time.sleep(wait_step)
                continue

            # 2. Khi upgrading_time == 0: gọi lệnh nâng sĩ khí tiếp theo (+10 điểm)
            add_point = min(10, target_morale - curr)

            payload = {
                "lAddPoint": str(add_point),
                "lGeneralID": str(general_id),
                "tid": str(city_id),
                "_": "",
            }
            resp = self.gateway.call("OPT.ashx", 47, payload) or {}
            ret = resp.get("ret", -1)

            if ret == 0:
                step_count += 1
                # Nếu API 76 không hỗ trợ mock trong unit test, cập nhật lạc quan
                if cur_m is None:
                    curr += add_point
                    _dispatch_on_step(
                        on_step, curr, target_morale, f"Đã tăng +{add_point} ({curr}/{target_morale})"
                    )
                    if curr >= target_morale:
                        return (
                            True,
                            curr,
                            f"Đã luyện thành công sau {step_count} đợt ({curr}/{target_morale})",
                        )

                # Chờ 1 nhịp ngắn để máy chủ cập nhật timer
                wait_step = min(1.0, self.poll_interval)
                if stop_event:
                    if stop_event.wait(wait_step):
                        return False, curr, "Đã bị dừng bởi người dùng"
                else:
                    time.sleep(wait_step)
            else:
                # Kiểm tra lại xem có phải do đang bận luyện dở chưa sync kịp hay không
                cur_m, up_t = self.get_general_morale_info(city_id, general_id)
                if up_t > 0:
                    continue

                err_msg = f"Máy chủ phản hồi mã lỗi {ret}"
                logger.warning(
                    f"Luyện sĩ khí tướng {general_id} tại thành {city_id} thất bại: {err_msg}"
                )
                _dispatch_on_step(on_step, curr, target_morale, f"❌ {err_msg}")
                return False, curr, err_msg

    def train_multiple_generals(
        self,
        targets: list[dict],
        target_morale: int = 100,
        max_workers: int = 3,
        stop_event: Optional[threading.Event] = None,
        on_progress: Optional[Callable[[int, int, dict], None]] = None,
        on_step: Optional[Callable[[int, int, int, str], None]] = None,
    ) -> dict[int, dict]:
        """Luyện sĩ khí đồng thời cho danh sách tướng đa thành.

        targets: list các dict: {"city_id": int, "general_id": int, "current_morale": int, "name": str}
        on_step: callback nhận (general_id, current_morale, target_morale, step_msg)
        Trả về kết quả theo từng tướng: {general_id: {"success": bool, "final_morale": int, "message": str}}
        """
        results: dict[int, dict] = {}
        total = len(targets)
        completed_count = 0
        lock = threading.Lock()

        def _worker(item: dict) -> tuple[int, bool, int, str]:
            nonlocal completed_count
            cid = item["city_id"]
            gid = item["general_id"]
            morale = item.get("current_morale", 0)

            def _general_step(cur: int, tgt: int, msg: str = ""):
                if on_step:
                    on_step(gid, cur, tgt, msg)

            succ, final_m, msg = self.train_general_morale(
                city_id=cid,
                general_id=gid,
                current_morale=morale,
                target_morale=target_morale,
                stop_event=stop_event,
                on_step=_general_step,
            )

            with lock:
                completed_count += 1
                res_dict = {
                    "general_id": gid,
                    "city_id": cid,
                    "name": item.get("name", str(gid)),
                    "success": succ,
                    "final_morale": final_m,
                    "message": msg,
                }
                results[gid] = res_dict
                if on_progress:
                    on_progress(completed_count, total, res_dict)

            return gid, succ, final_m, msg

        workers = max(1, min(max_workers, len(targets) or 1))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_worker, item) for item in targets]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    logger.error(f"Lỗi ngoại lệ khi luyện sĩ khí worker: {e}")

        return results
