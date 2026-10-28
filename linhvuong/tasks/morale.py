"""Phân hệ Luyện Sĩ Khí (Morale Training) đồng thời cho tướng lĩnh đa thành."""

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
    """Điều phối và thực thi luyện sĩ khí cho tướng đơn lẻ và đồng loạt nhiều tướng theo Tick Scheduler."""

    def __init__(
        self,
        gateway: GatewayClient,
        poll_interval: float = 2.0,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ):
        self.gateway = gateway
        self.poll_interval = max(0.001, poll_interval)
        self.sleep_fn = sleep_fn or getattr(gateway, "_sleep", time.sleep)

    def get_city_generals_morale_info(self, city_id: int) -> dict[int, tuple[int, int]]:
        """Lấy sĩ khí hiện tại và thời gian nâng dở (upgrading_time) cho tất cả tướng trong thành từ API 76.

        Trả về {general_id: (current_morale, upgrading_time)}.
        """
        result: dict[int, tuple[int, int]] = {}
        try:
            resp = self.gateway.call("Common.ashx", 76, {"cid": str(city_id)}) or {}
            for entry in resp.get("list", []):
                if len(entry) > 2 and isinstance(entry[2], list):
                    for g in entry[2]:
                        try:
                            gid = int(g[0])
                            cur_m = int(g[9]) if len(g) > 9 else 0
                            up_t = int(g[10]) if len(g) > 10 else 0
                            result[gid] = (cur_m, up_t)
                        except (ValueError, TypeError, IndexError):
                            continue
        except Exception as e:
            logger.warning(f"Không thể đọc thông tin sĩ khí thành {city_id} từ API 76: {e}")
        return result

    def get_general_morale_info(self, city_id: int, general_id: int) -> tuple[Optional[int], int]:
        """Lấy sĩ khí hiện tại và thời gian nâng sĩ khí còn lại (upgrading_time) từ API 76.

        Trả về (current_morale, upgrading_time). Nếu không tìm thấy hoặc API không trả về
        danh sách, trả về (None, 0).
        """
        city_info = self.get_city_generals_morale_info(city_id)
        if general_id in city_info:
            return city_info[general_id]
        return None, 0

    def train_general_morale(
        self,
        city_id: int,
        general_id: int,
        current_morale: int,
        target_morale: int = 100,
        stop_event: Optional[threading.Event] = None,
        on_step: Optional[Callable[..., None]] = None,
        travel_time: float = 0.0,
    ) -> tuple[bool, int, str]:
        """Luyện sĩ khí cho một tướng đơn lẻ từ current_morale đến target_morale.

        - Tự động kiểm tra thời gian nâng dở dang (upgrading_time > 0) từ máy chủ.
        - Nếu tướng đang luyện dở, chờ cho đợt luyện hoàn tất rồi cập nhật sĩ khí thực tế.
        - Hỗ trợ travel_time > 0 cho cơ chế Xuất Quân Sớm Theo Sĩ Khí (Early March).
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

            is_ready_by_travel = (
                travel_time > 0
                and (curr + 10 >= target_morale or curr >= target_morale)
                and 0 < up_t <= travel_time
            )

            if curr >= target_morale or is_ready_by_travel:
                if curr >= target_morale:
                    msg = f"Sĩ khí đã đạt mục tiêu ({curr}/{target_morale})"
                else:
                    msg = f"Sĩ khí đang nâng ({curr} -> {min(100, curr + 10)}) còn {up_t}s <= hành quân {travel_time}s (Sẵn sàng xuất quân)"
                _dispatch_on_step(on_step, curr, target_morale, f"✅ {msg}")
                return True, curr, msg

            # 1. Trường hợp tướng đang luyện dở (upgrading_time > 0): chờ hoàn tất
            if up_t > 0:
                wait_msg = f"⏳ Chờ luyện dở (còn {up_t}s)..."
                _dispatch_on_step(on_step, curr, target_morale, wait_msg)
                wait_step = min(float(up_t), self.poll_interval)
                if self.poll_interval >= 1.0:
                    wait_step = min(float(up_t), max(self.poll_interval, min(up_t / 2.0, 30.0)))
                if stop_event:
                    if stop_event.wait(wait_step):
                        return False, curr, "Đã bị dừng bởi người dùng"
                else:
                    self.sleep_fn(wait_step)
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
                else:
                    cur_m, up_t = self.get_general_morale_info(city_id, general_id)
                    if cur_m is not None:
                        curr = cur_m
                    is_ready_by_travel = (
                        travel_time > 0
                        and (curr + 10 >= target_morale or curr >= target_morale)
                        and 0 < up_t <= travel_time
                    )
                    if curr >= target_morale or is_ready_by_travel:
                        if curr >= target_morale:
                            msg = f"Đã luyện thành công sau {step_count} đợt ({curr}/{target_morale})"
                        else:
                            msg = f"Sĩ khí đang nâng ({curr} -> {min(100, curr + 10)}) còn {up_t}s <= hành quân {travel_time}s (Sẵn sàng xuất quân)"
                        _dispatch_on_step(on_step, curr, target_morale, f"✅ {msg}")
                        return True, curr, msg

                # Chờ 1 nhịp ngắn để máy chủ cập nhật timer
                wait_step = min(1.0, self.poll_interval)
                if stop_event:
                    if stop_event.wait(wait_step):
                        return False, curr, "Đã bị dừng bởi người dùng"
                else:
                    self.sleep_fn(wait_step)
            else:
                # Kiểm tra lại xem có phải do đang bận luyện dở chưa sync kịp hay không
                cur_m, up_t = self.get_general_morale_info(city_id, general_id)
                if up_t > 0:
                    continue

                err_msg = f"Máy chủ phản hồi mã lỗi {ret}"
                if ret == 15:
                    err_msg = "Máy chủ phản hồi mã lỗi 15: Thiếu tài nguyên (lúa/vàng)"
                logger.warning(
                    f"Luyện sĩ khí tướng {general_id} tại thành {city_id} thất bại: {err_msg}"
                )
                _dispatch_on_step(on_step, curr, target_morale, f"❌ {err_msg}")
                return False, curr, err_msg

    def train_multiple_generals(
        self,
        targets: list[dict],
        target_morale: int = 100,
        max_workers: Optional[int] = None,
        stop_event: Optional[threading.Event] = None,
        on_progress: Optional[Callable[[int, int, dict], None]] = None,
        on_step: Optional[Callable[[int, int, int, str], None]] = None,
        travel_time: float = 0.0,
    ) -> dict[int, dict]:
        """Luyện sĩ khí đồng loạt cho danh sách tướng đa thành theo cơ chế Tick Scheduler (Phương án 2).

        Không còn bị giới hạn bởi số worker threads. Toàn bộ tướng được chọn đều được kích hoạt
        nâng sĩ khí đồng thời trên máy chủ và cập nhật đếm ngược song song trong một vòng lặp chu kỳ.

        targets: list các dict: {"city_id": int, "general_id": int, "current_morale": int, "name": str}
        on_step: callback nhận (general_id, current_morale, target_morale, step_msg)
        on_progress: callback nhận (completed_count, total, result_dict)
        travel_time: thời gian hành quân dự kiến (s). Nếu > 0, hỗ trợ xuất quân sớm khi đợt nâng cuối cùng có up_t <= travel_time.
        Trả về kết quả theo từng tướng: {general_id: {"general_id": int, "city_id": int, "name": str, "success": bool, "final_morale": int, "message": str}}
        """
        if not targets:
            return {}

        target_morale = min(100, max(1, target_morale))
        total = len(targets)
        completed_count = 0

        # Khởi tạo bảng trạng thái cho từng tướng
        states: dict[int, dict] = {}
        for item in targets:
            gid = item["general_id"]
            cid = item["city_id"]
            name = item.get("name", str(gid))
            cur_m = item.get("current_morale", 0)
            states[gid] = {
                "general_id": gid,
                "city_id": cid,
                "name": name,
                "current_morale": cur_m,
                "upgrading_time": 0,
                "step_count": 0,
                "completed": False,
                "success": False,
                "message": "",
            }

        def _finish_general(gid: int, success: bool, final_morale: int, msg: str):
            nonlocal completed_count
            st = states[gid]
            if st["completed"]:
                return
            st["completed"] = True
            st["success"] = success
            st["current_morale"] = final_morale
            st["message"] = msg
            completed_count += 1
            icon = "✅" if success else "❌"
            if "dừng" in msg.lower():
                icon = "⏹️"
            if on_step:
                _dispatch_on_step(
                    lambda cur, tgt, m: on_step(gid, cur, tgt, m),
                    final_morale,
                    target_morale,
                    f"{icon} {msg}",
                )
            if on_progress:
                on_progress(completed_count, total, {
                    "general_id": gid,
                    "city_id": st["city_id"],
                    "name": st["name"],
                    "success": success,
                    "final_morale": final_morale,
                    "message": msg,
                })

        # Nếu người dùng đã yêu cầu dừng từ đầu
        if stop_event and stop_event.is_set():
            for gid, st in states.items():
                _finish_general(gid, False, st["current_morale"], "Đã bị dừng bởi người dùng")
            return {
                gid: {
                    "general_id": gid,
                    "city_id": s["city_id"],
                    "name": s["name"],
                    "success": s["success"],
                    "final_morale": s["current_morale"],
                    "message": s["message"],
                }
                for gid, s in states.items()
            }

        # Kiểm tra trước những tướng đã đạt mục tiêu ngay từ đầu
        for gid, st in list(states.items()):
            cur_val = st["current_morale"]
            up_val = st["upgrading_time"]
            is_ready_by_travel = (
                travel_time > 0
                and (cur_val + 10 >= target_morale or cur_val >= target_morale)
                and 0 < up_val <= travel_time
            )
            if cur_val >= target_morale:
                _finish_general(gid, True, cur_val, f"Sĩ khí đã đạt mục tiêu ({cur_val}/{target_morale})")
            elif is_ready_by_travel:
                _finish_general(
                    gid,
                    True,
                    cur_val,
                    f"Sĩ khí đang nâng ({cur_val} -> {min(100, cur_val + 10)}) còn {up_val}s <= hành quân {travel_time}s (Sẵn sàng xuất quân)",
                )

        last_city_sync: dict[int, float] = {}

        # Vòng lặp điều phối Tick Scheduler
        while completed_count < total:
            if stop_event and stop_event.is_set():
                for gid, st in states.items():
                    if not st["completed"]:
                        _finish_general(gid, False, st["current_morale"], "Đã bị dừng bởi người dùng")
                break

            now = time.time()
            active_targets = [st for st in states.values() if not st["completed"]]
            if not active_targets:
                break

            # 1. Đồng bộ thông tin API 76 theo từng Thành có tướng đang hoạt động
            active_cids = {st["city_id"] for st in active_targets}
            for cid in active_cids:
                if stop_event and stop_event.is_set():
                    break
                c_targets = [st for st in active_targets if st["city_id"] == cid]
                needs_sync = (
                    cid not in last_city_sync
                    or (now - last_city_sync[cid] >= self.poll_interval)
                    or any(st["upgrading_time"] <= 0 and st["current_morale"] < target_morale for st in c_targets)
                )

                if needs_sync:
                    city_info = self.get_city_generals_morale_info(cid)
                    last_city_sync[cid] = now
                    if city_info:
                        for st in c_targets:
                            gid = st["general_id"]
                            if gid in city_info:
                                cur_m, up_t = city_info[gid]
                                st["current_morale"] = cur_m
                                st["upgrading_time"] = up_t

            # 2. Xử lý từng tướng trong danh sách active
            for st in active_targets:
                if stop_event and stop_event.is_set():
                    break
                if st["completed"]:
                    continue

                gid = st["general_id"]
                cid = st["city_id"]
                curr = st["current_morale"]
                up_t = st["upgrading_time"]

                is_ready_by_travel = (
                    travel_time > 0
                    and (curr + 10 >= target_morale or curr >= target_morale)
                    and 0 < up_t <= travel_time
                )

                # 2.1. Đã đạt mục tiêu hoặc đủ điều kiện xuất quân sớm
                if curr >= target_morale or is_ready_by_travel:
                    if curr >= target_morale:
                        _finish_general(gid, True, curr, f"Sĩ khí đã đạt mục tiêu ({curr}/{target_morale})")
                    else:
                        _finish_general(
                            gid,
                            True,
                            curr,
                            f"Sĩ khí đang nâng ({curr} -> {min(100, curr + 10)}) còn {up_t}s <= hành quân {travel_time}s (Sẵn sàng xuất quân)",
                        )
                    continue

                # 2.2. Đang trong thời gian đếm ngược (upgrading_time > 0)
                if up_t > 0:
                    wait_msg = f"⏳ Chờ luyện dở (còn {up_t}s)..."
                    if on_step:
                        _dispatch_on_step(
                            lambda c, t, m: on_step(gid, c, t, m),
                            curr,
                            target_morale,
                            wait_msg,
                        )
                    continue

                # 2.3. Sẵn sàng kích hoạt lệnh nâng sĩ khí (up_t == 0 và curr < target_morale)
                add_point = min(10, target_morale - curr)
                payload = {
                    "lAddPoint": str(add_point),
                    "lGeneralID": str(gid),
                    "tid": str(cid),
                    "_": "",
                }
                resp = self.gateway.call("OPT.ashx", 47, payload) or {}
                ret = resp.get("ret", -1)

                if ret == 0:
                    st["step_count"] += 1
                    cur_m, new_up_t = self.get_general_morale_info(cid, gid)
                    if cur_m is None:
                        # Fallback cập nhật lạc quan (dành cho server mock / unit tests)
                        curr += add_point
                        st["current_morale"] = curr
                        if on_step:
                            _dispatch_on_step(
                                lambda c, t, m: on_step(gid, c, t, m),
                                curr,
                                target_morale,
                                f"Đã tăng +{add_point} ({curr}/{target_morale})",
                            )
                        if curr >= target_morale:
                            _finish_general(
                                gid,
                                True,
                                curr,
                                f"Đã luyện thành công sau {st['step_count']} đợt ({curr}/{target_morale})",
                            )
                    else:
                        st["current_morale"] = cur_m
                        st["upgrading_time"] = new_up_t or 1
                        is_ready_by_travel = (
                            travel_time > 0
                            and (cur_m + 10 >= target_morale or cur_m >= target_morale)
                            and 0 < st["upgrading_time"] <= travel_time
                        )
                        if cur_m >= target_morale or is_ready_by_travel:
                            if cur_m >= target_morale:
                                msg = f"Đã luyện thành công sau {st['step_count']} đợt ({cur_m}/{target_morale})"
                            else:
                                msg = f"Sĩ khí đang nâng ({cur_m} -> {min(100, cur_m + 10)}) còn {st['upgrading_time']}s <= hành quân {travel_time}s (Sẵn sàng xuất quân)"
                            _finish_general(gid, True, cur_m, msg)
                        else:
                            if on_step:
                                _dispatch_on_step(
                                    lambda c, t, m: on_step(gid, c, t, m),
                                    cur_m,
                                    target_morale,
                                    f"Đã kích hoạt +{add_point} ({cur_m}/{target_morale})",
                                )
                    # Giãn cách vi mô ngẫu nhiên 100ms - 250ms giữa các request kích hoạt để bảo vệ socket và chống bot
                    if self.poll_interval >= 0.1:
                        import random
                        time.sleep(random.uniform(0.1, 0.25))
                else:
                    # Kiểm tra lại xem có phải do đang bận luyện dở chưa kịp cập nhật (tránh mã lỗi 40 lặp lại)
                    cur_m, new_up_t = self.get_general_morale_info(cid, gid)
                    if new_up_t > 0:
                        st["upgrading_time"] = new_up_t
                        if cur_m is not None:
                            st["current_morale"] = cur_m
                        continue

                    err_msg = f"Máy chủ phản hồi mã lỗi {ret}"
                    if ret == 15:
                        err_msg = "Máy chủ phản hồi mã lỗi 15: Thiếu tài nguyên (lúa/vàng)"
                    logger.warning(
                        f"Luyện sĩ khí tướng {gid} tại thành {cid} thất bại: {err_msg}"
                    )
                    _finish_general(gid, False, curr, err_msg)

            # 3. Tính toán nhịp nghỉ giữa các tick và cập nhật đếm ngược cục bộ
            remaining = [st for st in states.values() if not st["completed"]]
            if not remaining:
                break

            tick_step = min(1.0, self.poll_interval)
            if stop_event:
                if stop_event.wait(tick_step):
                    for gid, st in states.items():
                        if not st["completed"]:
                            _finish_general(gid, False, st["current_morale"], "Đã bị dừng bởi người dùng")
                    break
            else:
                self.sleep_fn(tick_step)

            # Giảm thời gian đếm ngược cục bộ mỗi giây để UI hiển thị mượt mà
            for st in remaining:
                if st["upgrading_time"] > 0:
                    st["upgrading_time"] = max(0, st["upgrading_time"] - int(max(1, tick_step)))

        return {
            gid: {
                "general_id": gid,
                "city_id": s["city_id"],
                "name": s["name"],
                "success": s["success"],
                "final_morale": s["current_morale"],
                "message": s["message"],
            }
            for gid, s in states.items()
        }

    def adjust_squad_morale(
        self,
        base_id: int,
        general_ids: list[int],
        target_morale: int = 100,
        base_gens: Optional[dict[int, Any]] = None,
        on_notify: Optional[Callable[[str], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> tuple[bool, list[str]]:
        """Kiểm tra và kích hoạt nâng sĩ khí đồng loạt cho toàn bộ đạo quân trong 1 bước chu kỳ (run_once).

        - Kích hoạt song song OPT.ashx?id=47 cho TẤT CẢ võ tướng có upgrading_time == 0 và current_morale < target_morale.
        - Giữa các lượt gọi lệnh kích hoạt có khoảng trễ vi mô ngẫu nhiên 100ms - 250ms chống bot.
        - Tuyệt đối không gửi lệnh nếu tướng đang có upgrading_time > 0 (chặn đứng mã lỗi 40).
        - Trả về (is_all_ready, wait_reasons).
        """
        if not general_ids:
            return True, []

        target_morale = min(100, max(1, target_morale))
        wait_reasons: list[str] = []

        # Nếu không truyền base_gens từ ngoài vào, đọc trực tiếp từ API 76
        gens_morale_info = self.get_city_generals_morale_info(base_id) if base_id else {}

        import random

        for gid in general_ids:
            if stop_event and stop_event.is_set():
                return False, ["Đã bị dừng bởi người dùng"]

            g = base_gens.get(gid) if base_gens else None
            gname = getattr(g, "name", str(gid)) if g else str(gid)

            # Ưu tiên thông tin từ API 76 vừa đọc, fallback sang base_gens
            if gid in gens_morale_info:
                cur_m, up_t = gens_morale_info[gid]
            else:
                cur_m = getattr(g, "morale", 0) if g else 0
                up_t = getattr(g, "upgrading_time", 0) if g else 0

            if cur_m >= target_morale and up_t == 0:
                continue

            if up_t > 0:
                msg = f"Tướng {gname} đang đếm ngược nâng sĩ khí ({up_t}s)"
                wait_reasons.append(msg)
                if on_notify:
                    on_notify(f"⏳ {msg}...")
                continue

            # up_t == 0 và cur_m < target_morale -> kích hoạt nâng sĩ khí (+10 điểm)
            add_point = min(10, target_morale - cur_m)
            payload = {
                "lAddPoint": str(add_point),
                "lGeneralID": str(gid),
                "tid": str(base_id),
                "_": "",
            }
            resp = self.gateway.call("OPT.ashx", 47, payload) or {}
            ret = resp.get("ret", -1)

            if ret == 0:
                msg = f"Tướng {gname} (sĩ khí {cur_m}/{target_morale}) bắt đầu nâng sĩ khí (+{add_point})"
                wait_reasons.append(msg)
                if on_notify:
                    on_notify(f"⏳ [Sĩ khí] {msg}...")
                # Giãn cách vi mô ngẫu nhiên 100ms - 250ms giữa các request
                if self.poll_interval >= 0.1:
                    time.sleep(random.uniform(0.1, 0.25))
            else:
                err_msg = f"Máy chủ phản hồi mã lỗi {ret}"
                if ret == 15:
                    err_msg = "Mã lỗi 15: Thiếu tài nguyên (lúa/vàng)"
                msg = f"Tướng {gname} nâng sĩ khí thất bại ({err_msg})"
                wait_reasons.append(msg)
                if on_notify:
                    on_notify(f"❌ [Sĩ khí] {msg}")

        is_all_ready = (len(wait_reasons) == 0)
        return is_all_ready, wait_reasons
