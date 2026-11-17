"""Nhiệm vụ Quản lý & Nâng cấp Công trình Thành trì.

Reverse engineered chính xác từ ZBuild.exe:
- Quản lý Hàng Đợi Xây Dựng:
  1. Kiểm tra trạng thái nâng cấp thành phố: Common.ashx?id=77 (cid: city_id).
  2. Kiểm tra tài nguyên khoáng sản (Gỗ, Đá, Sắt, Lúa): City.ashx?id=20 (tid: city_id).
  3. Lấy danh sách công trình thực tế trong thành: City.ashx?id=5 (tid: city_id).
  4. Nâng cấp công trình theo mức ưu tiên cấu hình: OPT.ashx?id=65 (pid, gid, type=1, tid).
  5. Tự động tăng tốc hoàn thành: OPT.ashx?id=69 (type=1, param1=slot, param2=city_id, paytype).
  6. Kích hoạt hiệu ứng tăng tốc 20% khi hết hạn: OPT.ashx?id=69 (type=3, param1=0, param2=0, paytype=2).
  7. Tự động An Dân khôi phục sĩ khí/lòng dân: OPT.ashx?id=4 (lType=1, tid).
"""

import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..gateway import GatewayClient, gateway_city_context
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired

logger = logging.getLogger("linhvuong.tasks.building")

RET_CITY_NOT_FOUND = 4
RET_BULK_OUT_OF_CHESTS = 8108
RET_ITEM_EXHAUSTED = 90
BULK_DEFAULT_ALLOWED_IDS: frozenset[int] = frozenset(
    {1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 21, 23, 24, 25, 26, 28, 35, 36, 37, 44, 72, 73, 75, 76}
)


BUILDING_NAMES = {
    1: "官府 - Quan Phủ",
    2: "城墙 - Tường Thành",
    3: "民房 - Nhà Dân",
    4: "仓库 - Kho",
    5: "鸿胪寺 - Hồng Lư Tự",
    6: "大学殿 - Đại Học Điện",
    7: "客栈 - Quán Trọ",
    8: "酒馆 - Tửu Quán",
    9: "聚贤楼 - Tụ Hiền Lâu",
    10: "点将台 - Điểm Tướng Đài",
    11: "市场 - Chợ",
    12: "驿站 - Dịch Trạm",
    13: "兵器铺 - Xưởng Binh Khí",
    14: "防具铺 - Xưởng Khôi Giáp",
    15: "车马间 - Xưởng Ngựa",
    16: "校场 - Binh Trường",
    17: "营寨栅栏 - Tường",
    18: "中军大帐 - Trung Quân Đại Trướng",
    19: "营寨校场 - Binh Trường",
    20: "营寨驿站 - Dịch Trạm",
    21: "营寨仓库 - Kho",
    54: "宫殿 - Cung Điện",
    55: "壁垒 - Bích Lũy",
    56: "高级民居 - Cao Cấp Dân Cư",
    57: "国库 - Quốc Khố",
    58: "使节殿 - Sứ Tiết Điện",
    59: "太学殿 - Thái Học Điện",
    60: "水镜庐 - Quán Trọ",
    61: "酒肆 - Tửu Quán",
    62: "幕僚邸 - Tụ Hiền Lâu",
    63: "将帅府 - Điểm Tướng Đài",
    64: "集市 - Chợ",
    65: "中央驿所 - Dịch Trạm",
    66: "兵器司 - Xưởng Binh Khí",
    67: "防具司 - Xưởng Khôi Giáp",
    68: "车马司 - Xưởng Ngựa",
    69: "督军场 - Đốc Quân Trường",
}

NON_SPEEDUP_BUILDING_IDS: frozenset[int] = frozenset({1, 2, 54, 55})


def is_speedup_supported_building(gid: Optional[int]) -> bool:
    """Trả về True nếu mã công trình (gid) hỗ trợ tăng tốc bằng OPT.ashx?id=69 (type=1).

    Theo Build.js của máy chủ, Quan Phủ (1), Tường Thành (2), Cung Điện (54), Bích Lũy (55)
    và công trình thành NPC (22..53) không cho phép tăng tốc (máy chủ trả ret=1).
    """
    if gid is None or gid <= 0:
        return True
    if gid in NON_SPEEDUP_BUILDING_IDS:
        return False
    return gid < 22 or gid > 53

RESOURCE_BOX_NAMES = {
    24: "民生之鼎 - Dân Sinh Bảo Đỉnh",
    16: "民生之椟 - Dân Sinh Chi Độc",
    11: "民生之匣 - Dân Sinh Chi Hạp",
    6: "民生之幡 - Dân Sinh Bảo Phiên",
    1: "民生之囊 - Dân Sinh Chi Nang",
    35: "白金资源礼盒 - Bạch Kim Tài Nguyên Lễ Hộp",
}

DEFAULT_FALLBACK_BOX_ORDER = [24, 16, 11, 6, 1]

RET_OUT_OF_CHESTS = 10014

CHEST_MAPPING: dict[str, Any] = {
    "民生之囊 - Dân Sinh Bảo Nang": 1,
    "民生之幡 - Dân Sinh Bảo Phiên": 6,
    "民生之匣 - Dân Sinh Bảo Hạp": 11,
    "民生之椟 - Dân Sinh Bảo Độc": 16,
    "民生之鼎 - Dân Sinh Bảo Đỉnh": 24,
    "白金资源礼盒 - Bạch Kim Tư Nguyên Lễ Hạp": 35,
    "古器之囊 - Cổ Khí Bảo Nang": 2,
    "古器之幡 - Cổ Khí Bảo Phiên": 7,
    "古器之匣 - Cổ Khí Bảo Hạp": 12,
    "古器之椟 - Cổ Khí Bảo Độc": 17,
    "古器之鼎 - Cổ Khí Bảo Đỉnh": 25,
    "神武之囊 - Thần Vũ Bảo Nang": 3,
    "神武之幡 - Thần Vũ Bảo Phiên": 8,
    "神武之匣 - Thần Vũ Bảo Hạp": 13,
    "神武之椟 - Thần Vũ Bảo Độc": 21,
    "神武之鼎 - Thần Vũ Bảo Đỉnh": 26,
    "天宿之囊 - Thiên Túc Bảo Nang": 4,
    "天宿之鼎 - Thiên Túc Bảo Đỉnh": 27,
    "福券之囊 - Phúc Khoán Bảo Nang": 5,
    "福券之幡 - Phúc Khoán Bảo Phiên": 10,
    "福券之匣 - Phúc Khoán Bảo Hạp": 15,
    "福券之椟 - Phúc Khoán Bảo Độc": 23,
    "福券之鼎 - Phúc Khoán Bảo Đỉnh": 28,
    "军械补给礼盒 - Quân Giới Bổ Cấp Bảo Rương": 44,
    "御赐之匣 - Ngự Tứ Bảo Hạp": 53,
    "高级军械礼盒 - Cao Cấp Quân Giới Lễ Rương": 72,
    "古器王鼎 - Cổ Khí Vương Đỉnh": 73,
    "镇国军资 - Long Phi Rương": 75,
    "衣匣 - Thiên Mệnh Rương": 76,
    "金碧辉煌礼包 - Kim Bích Huy Hoàng Lễ Bao": {"id": 33, "api": 69, "param1": 222},
    "万夫莫开礼包 - Vạn Phu Mạc Khai Lễ Bao": {"id": 33, "api": 69, "param1": 221},
    "跃马扬刀礼包 - Dược Mã Dương Đao Lễ Bao": {"id": 33, "api": 69, "param1": 346},
    "虎踞一方礼包 - Hổ Cứ Nhất Phương Lễ Bao": {"id": 33, "api": 69, "param1": 347},
}

NO_SWITCH_CHESTS: set[str] = {
    "福券之囊 - Phúc Khoán Bảo Nang",
    "福券之幡 - Phúc Khoán Bảo Phiên",
    "福券之匣 - Phúc Khoán Bảo Hạp",
    "福券之椟 - Phúc Khoán Bảo Độc",
    "福券之鼎 - Phúc Khoán Bảo Đỉnh",
    "神武之囊 - Thần Vũ Bảo Nang",
    "神武之幡 - Thần Vũ Bảo Phiên",
    "神武之匣 - Thần Vũ Bảo Hạp",
    "神武之椟 - Thần Vũ Bảo Độc",
    "神武之鼎 - Thần Vũ Bảo Đỉnh",
    "御赐之匣 - Ngự Tứ Bảo Hạp",
    "天宿之囊 - Thiên Túc Bảo Nang",
    "天宿之鼎 - Thiên Túc Bảo Đỉnh",
    "金碧辉煌礼包 - Kim Bích Huy Hoàng Lễ Bao",
    "万夫莫开礼包 - Vạn Phu Mạc Khai Lễ Bao",
    "跃马扬刀礼包 - Dược Mã Dương Đao Lễ Bao",
    "虎踞一方礼包 - Hổ Cứ Nhất Phương Lễ Bao",
}


def chest_needs_city_switch(chest_name: str) -> bool:
    """Kiểm tra loại rương có yêu cầu chuyển ngữ cảnh Thành (City.ashx?id=50) trước khi mở không."""
    return chest_name not in NO_SWITCH_CHESTS


def switch_city_verified(gateway: GatewayClient, city_id: int) -> tuple[bool, int, str]:
    """Chuyển ngữ cảnh thành hiện tại (/api/city/current) và xác nhận ret == 0."""
    cid = int(city_id)
    sw_resp = gateway.set_current_city(cid)
    if not isinstance(sw_resp, dict):
        return False, -1, f"Không thể kết nối khi chuyển sang thành {cid}"
    try:
        sw_ret = int(sw_resp.get("ret", -1))
    except (ValueError, TypeError):
        sw_ret = -1
    if sw_ret in (110, RET_CAPTCHA_REQUIRED):
        return False, sw_ret, f"Server yêu cầu giải Captcha khi chuyển thành (mã {sw_ret})"
    if sw_ret != RET_OK:
        return False, sw_ret, f"Không thể chuyển sang thành {cid} (mã {sw_ret})"
    return True, RET_OK, ""


def open_single_chest(
    gateway: GatewayClient,
    chest_name: str,
    city_id: Optional[int] = None,
) -> tuple[bool, int, str]:
    """Mở 1 Rương Đạo Cụ (Common.ashx?id=48) hoặc Lễ Bao Đặc Biệt (OPT.ashx?id=69)."""
    if chest_name not in CHEST_MAPPING:
        return False, -1, f"Loại rương không hợp lệ: {chest_name}"

    chest_info = CHEST_MAPPING[chest_name]
    if isinstance(chest_info, dict):
        box_id = chest_info["id"]
        api_type = chest_info.get("api", 48)
        param1 = chest_info.get("param1", 0)
    else:
        box_id = int(chest_info)
        api_type = 48
        param1 = 0

    needs_switch = chest_needs_city_switch(chest_name)
    cid = 0
    if needs_switch:
        try:
            cid = int(city_id) if city_id is not None else 0
        except (ValueError, TypeError):
            cid = 0
        if cid <= 0:
            return False, -2, "Vui lòng chọn một Thành hợp lệ (ID dương) để nhận vật phẩm từ rương"

    with gateway_city_context(gateway):
        if needs_switch:
            ok_sw, sw_ret, sw_msg = switch_city_verified(gateway, cid)
            if not ok_sw:
                return False, sw_ret, sw_msg

        if api_type == 69:
            resp = gateway.call(
                "OPT.ashx",
                69,
                {
                    "type": str(box_id),
                    "param1": str(param1),
                    "param2": "0",
                    "paytype": "1",
                    "_": "",
                },
            )
        else:
            resp = gateway.call("Common.ashx", 48, {"lBoxID": str(box_id), "_": ""})

    if not isinstance(resp, dict):
        return False, -1, "Mở thất bại (không nhận được phản hồi hợp lệ)"

    try:
        ret = int(resp.get("ret", -1))
    except (ValueError, TypeError):
        ret = -1

    if ret == RET_OK:
        return True, RET_OK, "Mở thành công"
    if ret in (RET_OUT_OF_CHESTS, RET_ITEM_EXHAUSTED):
        return False, RET_OUT_OF_CHESTS, f"Đã hết rương/lễ bao trong túi đồ (mã {ret})"
    if ret in (110, RET_CAPTCHA_REQUIRED):
        return False, ret, f"Server yêu cầu giải Captcha (mã {ret})"
    err_msg = resp.get("errMsg")
    return False, ret, f"Mở thất bại (mã {ret}{f': {err_msg}' if err_msg else ''})"


def _resolve_bulk_policy(
    gateway: GatewayClient, box_id: int, api_type: int
) -> tuple[bool, int]:
    """Kiểm tra box_id có hỗ trợ Optimization.ashx?action=bulk-start hay phải mở từng cái."""
    if api_type != 48 or box_id == 53:
        return False, 1
    caps = gateway.optimization("capabilities")
    if isinstance(caps, dict) and int(caps.get("ret", -1)) == 0:
        if not caps.get("bulkEnabled", False):
            return False, 1
        allowed = caps.get("bulkAllowed")
        bulk_max = max(1, int(caps.get("bulkMax", 99)))
        if isinstance(allowed, list):
            return (box_id in {int(x) for x in allowed}), bulk_max
    return (box_id in BULK_DEFAULT_ALLOWED_IDS), 99


def _run_server_bulk_open(
    gateway: GatewayClient,
    chest_name: str,
    box_id: int,
    times: int,
    bulk_max: int,
    city_id: Optional[int],
    city_name: str,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
    on_progress: Optional[Callable[[int, int, float], None]],
) -> dict[str, Any]:
    """Mở rương theo lô qua Optimization.ashx?action=bulk-start + bulk-status (Server 58+)."""
    target_cid = int(city_id or 0)
    if target_cid > 0:
        gateway.set_current_city(target_cid)

    success_count = 0
    failed_count = 0
    aborted_reason: Optional[str] = None
    last_ret: Optional[int] = RET_OK
    city_tag = f" tại [{city_name}]" if city_name else ""
    sleep_fn = getattr(gateway, "_sleep", time.sleep)

    while success_count < times and not (stop_event and stop_event.is_set()):
        chunk = min(bulk_max, times - success_count)
        req_id = str(uuid.uuid4())
        payload = {
            "requestId": req_id,
            "boxId": str(box_id),
            "limit": str(chunk),
            "cityId": str(target_cid),
        }
        data = gateway.optimization("bulk-start", payload)
        if not isinstance(data, dict):
            failed_count += 1
            last_ret = -1
            break

        ret = int(data.get("ret", -1))
        last_ret = ret
        if ret in (110, RET_CAPTCHA_REQUIRED):
            aborted_reason = "captcha"
            if stop_event is not None:
                stop_event.set()
            break
        if ret in (RET_BULK_OUT_OF_CHESTS, RET_OUT_OF_CHESTS, RET_ITEM_EXHAUSTED):
            aborted_reason = "out_of_stock"
            break

        # Nếu trạng thái admit chưa rõ ràng (8104/8105/8107/>=8600), poll bulk-status cùng requestId
        if ret in (8104, 8105, 8107) or ret >= 8600 or int(data.get("state", -1)) == 0:
            delay = 0.25
            for _ in range(24):
                if stop_event and stop_event.is_set():
                    break
                sleep_fn(delay)
                delay = min(1.5, delay * 2)
                st = gateway.optimization("bulk-status", {"requestId": req_id})
                if not isinstance(st, dict):
                    continue
                st_ret = int(st.get("ret", -1))
                last_ret = st_ret
                if st_ret == 0:
                    data = st
                    if int(st.get("state", 0)) != 0:
                        break
                elif st_ret == 8109:
                    # Job chưa được Server tiếp nhận
                    break

        ret = int(data.get("ret", -1))
        last_ret = ret
        if ret != 0:
            failed_count += 1
            if on_log:
                err_msg = data.get("errMsg") or f"mã {ret}"
                on_log(f"❌ Mở lô [{chest_name}]{city_tag} thất bại ({err_msg}).")
            break

        opened = max(0, int(data.get("completed", 0)))
        planned = max(0, int(data.get("planned", chunk)))
        success_count += opened
        if on_log and opened > 0:
            on_log(f"✅ Mở lô [{chest_name}]{city_tag}: đã mở {opened} rương ({success_count}/{times}).")
        if on_progress:
            on_progress(success_count, times, min(100.0, (success_count / times) * 100.0))

        if opened == 0 or (planned > 0 and opened < planned) or int(data.get("state", 1)) == 2:
            aborted_reason = "out_of_stock"
            break

    if aborted_reason == "out_of_stock" and on_log:
        on_log(f"🛑 Dừng mở rương: Đã hết [{chest_name}] trong túi đồ.")
    elif aborted_reason == "captcha" and on_log:
        on_log(f"⚠️ Dừng mở rương: Server yêu cầu giải Captcha (mã {last_ret})!")
    elif stop_event is not None and stop_event.is_set() and aborted_reason is None:
        aborted_reason = "stopped"
        if on_log:
            on_log("⏹️ Đã dừng tiến trình mở rương theo yêu cầu.")

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "completed": success_count,
        "total": times,
        "aborted_reason": aborted_reason,
        "last_ret": last_ret,
    }


def run_batch_open_chest(
    gateway: GatewayClient,
    chest_name: str,
    times: int,
    city_id: Optional[int] = None,
    city_name: str = "",
    max_workers: int = 5,
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int, float], None]] = None,
) -> dict[str, Any]:
    """Mở Rương Đạo Cụ / Lễ Bao Đặc Biệt: ưu tiên bulk-start (Server 58+) nếu box_id hỗ trợ."""
    if times <= 0:
        return {
            "success_count": 0,
            "failed_count": 0,
            "completed": 0,
            "total": 0,
            "aborted_reason": None,
            "last_ret": None,
        }

    needs_switch = chest_needs_city_switch(chest_name)
    if needs_switch:
        try:
            valid_cid = int(city_id) if city_id is not None else 0
        except (ValueError, TypeError):
            valid_cid = 0
        if valid_cid <= 0:
            err_msg = "Vui lòng chọn một Thành hợp lệ (ID dương) để nhận vật phẩm từ rương"
            if on_log:
                on_log(f"❌ {err_msg}")
            return {
                "success_count": 0,
                "failed_count": 0,
                "completed": 0,
                "total": times,
                "aborted_reason": "invalid_city",
                "last_ret": -2,
            }

    chest_info = CHEST_MAPPING.get(chest_name)
    if chest_info is not None and times > 1:
        if isinstance(chest_info, dict):
            box_id = int(chest_info["id"])
            api_type = int(chest_info.get("api", 48))
        else:
            box_id = int(chest_info)
            api_type = 48
        use_bulk, bulk_max = _resolve_bulk_policy(gateway, box_id, api_type)
        if use_bulk:
            return _run_server_bulk_open(
                gateway=gateway,
                chest_name=chest_name,
                box_id=box_id,
                times=times,
                bulk_max=bulk_max,
                city_id=city_id,
                city_name=city_name if needs_switch else "",
                stop_event=stop_event,
                on_log=on_log,
                on_progress=on_progress,
            )

    task_queue: queue.Queue[int] = queue.Queue()
    for i in range(1, times + 1):
        task_queue.put(i)

    state_lock = threading.RLock()
    abort_flag = threading.Event()
    completed_count = 0
    success_count = 0
    failed_count = 0
    aborted_reason: Optional[str] = None
    last_ret: Optional[int] = None
    next_to_report = 1
    completed_results: dict[int, tuple[bool, int, str]] = {}

    city_tag = f" tại [{city_name}]" if (needs_switch and city_name) else ""

    def _drain_queue() -> None:
        while True:
            try:
                task_queue.get_nowait()
                task_queue.task_done()
            except queue.Empty:
                break

    def _emit_turn_log(turn_idx: int, ok: bool, ret_code: int, message: str) -> None:
        if not on_log:
            return
        if ok:
            on_log(f"✅ Lượt {turn_idx}/{times}: Mở [{chest_name}]{city_tag} thành công.")
        else:
            on_log(f"❌ Lượt {turn_idx}/{times}: Mở [{chest_name}]{city_tag} - {message}")

    def _worker() -> None:
        nonlocal completed_count, success_count, failed_count, aborted_reason, last_ret, next_to_report
        while not abort_flag.is_set() and not (stop_event and stop_event.is_set()):
            try:
                turn_idx = task_queue.get_nowait()
            except queue.Empty:
                break

            try:
                if abort_flag.is_set() or (stop_event and stop_event.is_set()):
                    continue

                ok, ret_code, message = open_single_chest(gateway, chest_name, city_id=city_id)

                with state_lock:
                    completed_count += 1
                    last_ret = ret_code
                    if ok:
                        success_count += 1
                    else:
                        failed_count += 1

                    completed_results[turn_idx] = (ok, ret_code, message)
                    while next_to_report in completed_results:
                        r_ok, r_code, r_msg = completed_results.pop(next_to_report)
                        _emit_turn_log(next_to_report, r_ok, r_code, r_msg)
                        next_to_report += 1

                    if ret_code == RET_OUT_OF_CHESTS:
                        if aborted_reason is None:
                            aborted_reason = "out_of_stock"
                        abort_flag.set()
                        _drain_queue()
                    elif ret_code in (110, RET_CAPTCHA_REQUIRED):
                        if aborted_reason is None:
                            aborted_reason = "captcha"
                        abort_flag.set()
                        if stop_event is not None:
                            stop_event.set()
                        _drain_queue()

                    if on_progress:
                        pct = (completed_count / times) * 100.0
                        on_progress(completed_count, times, pct)
            finally:
                task_queue.task_done()

    worker_count = min(max(1, int(max_workers)), times)
    threads = [
        threading.Thread(target=_worker, name=f"OpenChestWorker-{idx + 1}", daemon=True)
        for idx in range(worker_count)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Flush bất kỳ kết quả nào còn lại do thứ tự nhảy cóc khi dừng giữa chừng
    with state_lock:
        for rem_idx in sorted(completed_results.keys()):
            r_ok, r_code, r_msg = completed_results.pop(rem_idx)
            _emit_turn_log(rem_idx, r_ok, r_code, r_msg)

        if aborted_reason == "out_of_stock":
            if on_log:
                on_log(f"🛑 Dừng mở rương: Đã hết [{chest_name}] trong túi đồ (mã 10014).")
        elif aborted_reason == "captcha":
            if on_log:
                on_log(f"⚠️ Dừng mở rương: Server yêu cầu giải Captcha (mã {last_ret})!")
        elif stop_event is not None and stop_event.is_set() and aborted_reason is None:
            aborted_reason = "stopped"
            if on_log:
                on_log("⏹️ Đã dừng tiến trình mở rương theo yêu cầu.")

    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "completed": completed_count,
        "total": times,
        "aborted_reason": aborted_reason,
        "last_ret": last_ret,
    }


def parse_remaining_seconds(raw_val) -> int:
    """Chuyển đổi giá trị thời gian còn lại (giây, HH:MM:SS, MM:SS, hoặc Unix timestamp) sang số giây."""
    if raw_val in (None, "", 0, "0"):
        return 0

    if isinstance(raw_val, str) and ":" in raw_val:
        parts = [p.strip() for p in raw_val.split(":")]
        if len(parts) == 3:
            try:
                return max(0, int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
            except ValueError:
                return 0
        if len(parts) == 2:
            try:
                return max(0, int(parts[0]) * 60 + int(parts[1]))
            except ValueError:
                return 0
        return 0

    try:
        val = int(float(raw_val))
    except (ValueError, TypeError):
        return 0

    if val > 1_000_000_000:
        return max(0, int(val - time.time()))
    return max(0, val)


def parse_boost_remaining_time(resp: dict, city_id: int = 0) -> int:
    """Trích xuất thời gian còn lại (giây) của DS kiến trúc từ /api/city/pagebuilding.

    Trên Server 58+, plus_finish luôn nằm ở root của khối pagebuilding (list[i][2] là map_id).
    """
    if not isinstance(resp, dict):
        return 0
    _ = city_id
    plus_finish = resp.get("plus_finish")
    return parse_remaining_seconds(plus_finish)


@dataclass
class BuildingPlan:
    pid: int  # Vị trí ô đất trong thành (1..32)
    gid: int  # Loại công trình (1: Thái Phủ, 8: Đại Học, 21: Ruộng...)
    target_level: int  # Cấp độ mục tiêu cần đạt (0..33, 0 nghĩa là dỡ bỏ hoàn toàn)
    name: str = ""
    enabled: bool = True

    def __post_init__(self):
        if not self.name:
            self.name = BUILDING_NAMES.get(self.gid, f"Công trình {self.gid}")


class BuildingTask:
    _last_boost_act_time: float = 0.0

    def __init__(
        self,
        gateway: GatewayClient,
        city_id: int,
        plans: list[BuildingPlan],
        max_slots: int = 3,
        auto_speedup: bool = False,
        speedup_hours: float = 1.0,
        paytype: int = 2,
        auto_comfort: bool = True,
        auto_boost: bool = False,
        auto_open_box: bool = False,
        box_id: int = 24,
        max_boxes_per_round: int = 5,
        auto_fallback_box: bool = True,
        even_upgrade: bool = False,
        notify: Callable[[str], None] = print,
        city_name: str = "",
        on_sync_data: Optional[Callable[[int, dict[int, dict]], None]] = None,
        on_city_missing: Optional[Callable[[int], None]] = None,
    ):
        self.gateway = gateway
        self.city_id = city_id
        self.city_name = city_name
        self.plans = plans
        self.max_slots = max_slots
        self.auto_speedup = auto_speedup
        try:
            self.speedup_hours = max(0.0, float(speedup_hours))
        except (ValueError, TypeError):
            self.speedup_hours = 1.0
        self.paytype = int(paytype)
        self.auto_comfort = auto_comfort
        self.auto_boost = auto_boost
        self.auto_open_box = auto_open_box
        self.box_id = box_id
        self.max_boxes_per_round = max_boxes_per_round
        self.auto_fallback_box = auto_fallback_box
        self.even_upgrade = even_upgrade
        self.notify = notify
        self.on_sync_data = on_sync_data
        self.on_city_missing = on_city_missing
        self.skipped_pids: set[int] = set()
        self.deferred_pids: set[int] = set()
        self.comfort_interval: float = 300.0
        self.resource_cooldown: float = 90.0
        self._busy_until: float = 0.0
        self._boost_until: float = 0.0
        self._comfort_next_check: float = 0.0
        self._resource_cooldown_until: float = 0.0
        self._c77_cache_external: bool = False
        self._c77_from_shared_cache: bool = False
        self._non_speedup_logged: set[tuple[int, int]] = set()

    def reset_skipped(self):
        """Xóa danh sách các slot công trình tạm thời bị bỏ qua."""
        self.skipped_pids.clear()

    def reset_deferred(self):
        """Xóa danh sách các slot công trình bị hoãn kiểm tra (mã lỗi 261, 245)."""
        self.deferred_pids.clear()

    def _log(self, msg: str):
        if self.city_name:
            self.notify(f"[{self.city_name}] {msg}")
        else:
            self.notify(msg)

    def _fetch_c77(self, force: bool = False) -> dict:
        """Đọc và cache kết quả /api/city/pagebuilding trong chu kỳ ngắn để tránh gọi trùng."""
        now = time.time()
        cached = getattr(self, "_c77_cache", None)
        cached_time = getattr(self, "_c77_cache_time", 0.0)
        if not force and cached is not None and (now - cached_time < 3.0):
            return cached

        resp = self.gateway.page_building(self.city_id)
        self._c77_from_shared_cache = False
        if not isinstance(resp, dict) or not resp:
            self._c77_cache = None
            return {}

        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        if ret == RET_OK:
            self._c77_cache = resp
            self._c77_cache_time = now
        else:
            self._c77_cache = None
        return resp

    def set_c77_cache(self, resp: dict, fetched_at: Optional[float] = None) -> None:
        """Tiêm kết quả Common.ashx?id=77 dùng chung giữa các thành trong cùng chu kỳ."""
        self._c77_cache = resp
        self._c77_cache_time = fetched_at if fetched_at is not None else time.time()
        self._c77_cache_external = True
        self._c77_from_shared_cache = True

    @staticmethod
    def _extract_slot_remaining_seconds(item: Any) -> int:
        if isinstance(item, (list, tuple)):
            return parse_remaining_seconds(item[4]) if len(item) >= 5 else 0
        if isinstance(item, dict):
            raw_time = item.get("time_left") if item.get("time_left") is not None else item.get("time")
            return parse_remaining_seconds(raw_time)
        return 0

    def check_and_activate_boost(self) -> bool:
        """Kiểm tra thời gian DS kiến trúc (xây 3 nhà), kích hoạt nếu hết hạn."""
        if not self.auto_boost:
            return True

        resp = self._fetch_c77()
        remaining = parse_boost_remaining_time(resp, self.city_id)
        if remaining > 0:
            self._boost_until = time.monotonic() + min(float(remaining), 1800.0)
            return True
        if remaining <= 0:
            now_ts = time.time()
            if now_ts - BuildingTask._last_boost_act_time < 60:
                # Đang trong thời gian chờ sau lần kích hoạt gần nhất (tránh kích hoạt lặp giữa các thành)
                return True

            BuildingTask._last_boost_act_time = now_ts
            self._log("⚡ DS kiến trúc đã hết hạn. Đang tự kích hoạt lại (3 vị trí thi công)...")
            boost_resp = self.gateway.call(
                "OPT.ashx",
                69,
                {"type": "3", "param1": "0", "param2": "0", "paytype": "2", "_": ""},
            ) or {}
            self._c77_cache = None
            ret = boost_resp.get("ret", RET_OK)
            if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
                raise CaptchaRequired()
            if ret == RET_OK:
                self._log("✅ Kích hoạt thành công DS kiến trúc (3 vị trí thi công)!")
                self._boost_until = time.monotonic() + 1800.0
                return True
            else:
                self._log(f"⚠️ Kích hoạt DS kiến trúc thất bại (mã {ret}).")
                return False
        return True

    def check_and_comfort_city(self) -> bool:
        """Kiểm tra sĩ khí / dân nộ qua /api/city/info, tự động Tế Trời An Dân nếu cần."""
        data = self.gateway.city_info(self.city_id) or {}
        ret = data.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        morale = int(data.get("m_lmorale_current", data.get("morale", 100)))
        anger = int(data.get("m_lmorale_complaint", data.get("anger", 0)))

        now_mono = time.monotonic()
        if morale < 90 or anger > 0:
            self._log(f"🕊️ Sĩ khí ({morale}%) thấp hoặc dân nộ ({anger}), tiến hành An Dân...")
            comfort_resp = self.gateway.call(
                "OPT.ashx",
                4,
                {"lType": "1", "tid": str(self.city_id), "_": ""},
            ) or {}
            self._comfort_next_check = now_mono + 30.0
            return comfort_resp.get("ret", RET_OK) == RET_OK
        self._comfort_next_check = now_mono + self.comfort_interval
        return True

    def _parse_c77_slots(self, resp: dict) -> Optional[list]:
        """Trích xuất danh sách slot nâng cấp cho city_id từ Common.ashx?id=77, trả về None nếu không tìm thấy/lỗi."""
        if not isinstance(resp, dict) or not resp or resp.get("ret", -1) != RET_OK:
            return None

        city_list = resp.get("list")
        if not isinstance(city_list, list):
            return None

        for city_info in city_list:
            if isinstance(city_info, dict):
                # Hỗ trợ cấu trúc mock trong test
                return city_list
            if isinstance(city_info, (list, tuple)) and len(city_info) >= 5:
                if str(city_info[0]) == str(self.city_id):
                    upgrades = city_info[4]
                    if isinstance(upgrades, list):
                        return upgrades
        return None

    def _fetch_active_upgrade_slots(self, force: bool = False) -> tuple[list, bool]:
        """Đọc danh sách slot đang thi công kèm cờ thành công để tránh gửi trùng lệnh khi API lỗi."""
        was_shared = bool(getattr(self, "_c77_from_shared_cache", False))
        resp = self._fetch_c77(force=force)
        slots = self._parse_c77_slots(resp)
        if slots is not None:
            return slots, True

        # Nếu cache dùng chung từ thành khác không chứa thành này (hoặc lỗi), hỏi trực tiếp theo city_id
        if was_shared and not force:
            resp = self._fetch_c77(force=True)
            slots = self._parse_c77_slots(resp)
            if slots is not None:
                return slots, True

        # Fallback qua Build.ashx?id=2
        fb_resp = self.gateway.call(
            "Build.ashx", 2, {"pid": "8", "gid": "1", "tab": "2", "tid": str(self.city_id), "_": ""}
        )
        if not isinstance(fb_resp, dict) or not fb_resp:
            return [], False
        fb_ret = fb_resp.get("ret", -1)
        if fb_ret == 110 or fb_ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        if fb_ret != RET_OK:
            return [], False
        fb_list = fb_resp.get("list", [])
        return (fb_list if isinstance(fb_list, list) else []), True

    def get_active_upgrade_slots(self, force: bool = False) -> list:
        """Lấy danh sách các slot đang nâng cấp dở trong thành."""
        slots, _ = self._fetch_active_upgrade_slots(force=force)
        return slots

    @staticmethod
    def _parse_buildings_map(resp: dict) -> dict[int, dict]:
        buildings_list = resp.get("items") or resp.get("infos") or []
        buildings_map: dict[int, dict] = {}
        for b in buildings_list:
            if not isinstance(b, dict):
                continue
            pid = int(b.get("m_lpos") if b.get("m_lpos") is not None else b.get("pid", 0))
            buildings_map[pid] = {
                "gid": int(b.get("m_lgid") or b.get("gid", 0)),
                "level": int(b.get("m_llevel") if b.get("m_llevel") is not None else b.get("level", 0)),
                "name": str(b.get("m_szname") or b.get("name") or ""),
            }
        return buildings_map

    def _fetch_real_buildings_checked(self) -> tuple[dict[int, dict], Optional[int], bool]:
        """Đọc danh sách công trình thực tế kèm mã ret và cờ thành công để tránh suy diễn cấp 0 khi API lỗi."""
        resp = self.gateway.building_list(self.city_id)
        if not isinstance(resp, dict) or not resp:
            return {}, None, False
        try:
            ret = int(resp.get("ret", RET_OK))
        except (ValueError, TypeError):
            ret = -1
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        if ret != RET_OK:
            return {}, ret, False
        buildings_map = self._parse_buildings_map(resp)
        if not buildings_map:
            return {}, RET_OK, False
        return buildings_map, RET_OK, True

    def get_real_buildings(self) -> dict[int, dict]:
        """Lấy danh sách công trình hiện có từ /api/building/list: {pid: {"gid": gid, "level": level, "name": name}}."""
        resp = self.gateway.building_list(self.city_id) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        if ret != RET_OK:
            return {}
        return self._parse_buildings_map(resp)

    def speedup_slot(self, slot_id: int, paytype: Optional[int] = None, kind: int = 1) -> bool:
        """Sử dụng vật phẩm tăng tốc xây dựng (kind=1: giảm 50%, kind=2: giảm 1 giờ)."""
        pt = paytype if paytype is not None else self.paytype
        resp = self.gateway.call(
            "OPT.ashx",
            69,
            {
                "type": str(int(kind)),
                "param1": str(slot_id),
                "param2": str(self.city_id),
                "paytype": str(pt),
                "_": "",
            },
        ) or {}
        self._c77_cache = None
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()
        if ret != RET_OK:
            err_map = {
                1: "Công trình không thể tăng tốc (Quan Phủ/Tường Thành) hoặc thao tác thất bại",
                4: "Mã thành trì không hợp lệ",
                8: "Vị trí công trình không hợp lệ",
                30: "Không đủ Coin (元宝)",
                31: "Không có nhà đang xây ở slot này",
                45: "Không đủ Ngân Bảo (点券)",
                999: "Lỗi không xác định",
            }
            server_msg = str(resp.get("errMsg") or "").strip() if isinstance(resp, dict) else ""
            msg = err_map.get(ret) or server_msg or f"Lỗi mã {ret}"
            self._log(f"❌ Tăng tốc thất bại cho slot {slot_id}: {msg}")
            return False
        return True

    @staticmethod
    def _extract_slot_gid_and_time(item) -> Optional[tuple[int, Optional[int], int]]:
        """Trích xuất (slot_id, gid, time_left_seconds) từ phần tử hàng đợi nâng cấp."""
        if isinstance(item, (list, tuple)):
            if len(item) < 1:
                return None
            try:
                slot = int(item[0])
            except (ValueError, TypeError):
                return None
            gid: Optional[int] = None
            if len(item) >= 2 and item[1] is not None:
                try:
                    gid = int(item[1])
                except (ValueError, TypeError):
                    gid = None
            time_left = parse_remaining_seconds(item[4]) if len(item) >= 5 else 0
            return slot, gid, time_left
        if isinstance(item, dict):
            try:
                slot = int(item.get("slot") or item.get("pid") or 1)
            except (ValueError, TypeError):
                return None
            raw_gid = item.get("gid") if item.get("gid") is not None else item.get("m_lgid")
            gid = None
            if raw_gid is not None:
                try:
                    gid = int(raw_gid)
                except (ValueError, TypeError):
                    gid = None
            raw_time = item.get("time_left") if item.get("time_left") is not None else item.get("time")
            time_left = parse_remaining_seconds(raw_time)
            return slot, gid, time_left
        return None

    def _slot_time_left(self, slot: int) -> int:
        """Đọc lại thời gian còn lại thực tế của slot từ máy chủ (0 nếu đã xong)."""
        slots, ok = self._fetch_active_upgrade_slots(force=True)
        if not ok:
            return 0
        for item in slots:
            parsed = self._extract_slot_gid_and_time(item)
            if parsed is not None and parsed[0] == slot:
                return parsed[2]
        return 0

    def _speedup_slot_instant(self, slot: int, time_left: int) -> int:
        """Xây Xong Ngay: giảm 50% đến <= 1 giờ rồi dùng giảm 1 giờ để hoàn tất. Trả về số lần dùng đạo cụ."""
        hour = 3600
        count = 0
        current = time_left
        self._log(f"   ⚡ Slot {slot}: còn {time_left // 60} phút, xây xong ngay")
        while current > hour and count < 10:
            if not self.speedup_slot(slot, kind=1):
                self._log(f"      ❌ Tăng tốc 50% thất bại ở lần {count + 1}")
                return count
            count += 1
            current //= 2
            self._log(f"      ✅ Giảm 50% lần {count}: còn ~{current // 60} phút")
        for _ in range(3):
            if current <= 0:
                break
            if not self.speedup_slot(slot, kind=2):
                self._log("      ❌ Giảm 1 giờ thất bại")
                return count
            count += 1
            self._log("      ✅ Đã giảm 1 giờ")
            current = self._slot_time_left(slot)
            if current > hour:
                # Ước lượng lệch lớn: tiếp tục giảm 50% theo thời gian thật
                if not self.speedup_slot(slot, kind=1):
                    return count
                count += 1
                current = self._slot_time_left(slot)
        if count:
            self._log(f"   ✅ Đã tăng tốc {count} lần cho slot {slot}")
        return count

    def process_speedup(self) -> int:
        """Tăng tốc các công trình đang thi công theo cơ chế chuẩn ZBuild.

        Mỗi lần gọi OPT.ashx?id=69 giảm 50% thời gian thi công còn lại.
        Vòng lặp giảm thời gian cho mỗi slot chạy cho đến khi thời gian còn lại
        < target_hours * 3600 (mặc định 1h = 3600s) hoặc tối đa 10 lần.
        Bỏ qua Quan Phủ (1), Tường Thành (2), Cung Điện (54), Bích Lũy (55) và công trình NPC (22..53).
        """
        target_seconds = int(self.speedup_hours * 3600)
        active_slots = self.get_active_upgrade_slots()
        if not active_slots:
            return 0

        total_speedups = 0
        for item in active_slots:
            parsed = self._extract_slot_gid_and_time(item)
            if parsed is None:
                continue
            slot, gid, time_left = parsed

            if not is_speedup_supported_building(gid):
                gid_key = int(gid or 0)
                if (slot, gid_key) not in self._non_speedup_logged:
                    self._non_speedup_logged.add((slot, gid_key))
                    bname = BUILDING_NAMES.get(gid_key, f"GID {gid_key}")
                    self._log(f"   ⏭️ Slot {slot} ({bname}): công trình không hỗ trợ tăng tốc, bỏ qua")
                continue

            instant = self.speedup_hours <= 0
            if instant:
                if time_left <= 0:
                    continue
                total_speedups += self._speedup_slot_instant(slot, time_left)
                continue

            if time_left <= target_seconds:
                self._log(f"   ✓ Slot {slot}: còn {time_left // 60} phút (< {self.speedup_hours:g}h), không cần tăng tốc")
                continue

            self._log(f"   🔄 Slot {slot}: còn {time_left // 60} phút, cần giảm xuống < {self.speedup_hours:g}h")
            current_time = time_left
            speedup_count = 0

            while current_time > target_seconds and speedup_count < 10:
                success = self.speedup_slot(slot)
                if not success:
                    self._log(f"      ❌ Tăng tốc thất bại ở lần {speedup_count + 1}")
                    break
                speedup_count += 1
                current_time //= 2
                self._log(f"      ✅ Lần {speedup_count}: còn {current_time // 60} phút")

            if speedup_count > 0:
                self._log(f"   ✅ Đã tăng tốc {speedup_count} lần cho slot {slot}")
                total_speedups += speedup_count

        if total_speedups > 0:
            self._c77_cache = None

        return total_speedups

    def _order_plans_by_type_even(
        self, plans_list: list[BuildingPlan], real_buildings: dict[int, dict]
    ) -> list[BuildingPlan]:
        """Sắp xếp danh sách thi công bảo toàn thứ tự Loại công trình, trong đó các ô cùng loại được nâng đồng đều."""
        groups: dict[int, list[BuildingPlan]] = {}
        for p in plans_list:
            groups.setdefault(p.gid, []).append(p)

        ordered = []
        for gid, group_plans in groups.items():
            upgrades = []
            downgrades = []
            completed = []
            for p in group_plans:
                cur = real_buildings.get(p.pid, {"gid": p.gid, "level": 0})
                cur_lvl = cur.get("level", 0)
                if cur_lvl < p.target_level:
                    upgrades.append(p)
                elif cur_lvl > p.target_level:
                    downgrades.append(p)
                else:
                    completed.append(p)
            # Cùng loại: nâng các ô cấp thấp hơn lên trước để đồng đều
            upgrades.sort(key=lambda p: real_buildings.get(p.pid, {}).get("level", 0))
            downgrades.sort(key=lambda p: real_buildings.get(p.pid, {}).get("level", 0), reverse=True)
            ordered.extend(upgrades + downgrades + completed)
        return ordered

    def _open_one_resource_box(self) -> bool:
        """Mở đúng 1 đạo cụ tài nguyên qua Common.ashx?id=48 khi toàn bộ công trình thiếu tài nguyên."""
        if getattr(self, "_storage_full", False):
            self._log("⚠️ Kho tài nguyên đã đầy sức chứa tối đa, ngừng mở thêm đạo cụ.")
            return False

        boxes_to_try = [self.box_id]
        if self.auto_fallback_box:
            for bid in DEFAULT_FALLBACK_BOX_ORDER:
                if bid not in boxes_to_try:
                    boxes_to_try.append(bid)

        with gateway_city_context(self.gateway):
            # 1. Chuyển ngữ cảnh về thành trì đang thi công và xác nhận thành công trước khi mở rương
            ok_sw, sw_ret, sw_msg = switch_city_verified(self.gateway, self.city_id)
            if sw_ret in (110, RET_CAPTCHA_REQUIRED):
                raise CaptchaRequired()
            if not ok_sw:
                self._log(f"⚠️ {sw_msg}; bỏ qua mở rương để tránh mở nhầm thành.")
                logger.warning(f"[city={self.city_id}] Chuyển thành thất bại trước khi mở rương: {sw_msg}")
                return False

            for cur_box_id in boxes_to_try:
                box_label = RESOURCE_BOX_NAMES.get(cur_box_id, f"Rương {cur_box_id}")
                resp = self.gateway.call("Common.ashx", 48, {"lBoxID": str(cur_box_id), "_": ""}) or {}
                ret = resp.get("ret", RET_OK)
                if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
                    raise CaptchaRequired()

                if ret in (10014, RET_ITEM_EXHAUSTED):
                    self._log(f"ℹ️ Đã hết {box_label} trong túi đồ (mã {ret}).")
                    continue

                if ret != RET_OK:
                    self._log(f"⚠️ Mở {box_label} thất bại (mã {ret}).")
                    continue

                logger.info(f"[city={self.city_id}] Mở thành công 1 {box_label} (box_id={cur_box_id}) khi thiếu tài nguyên.")
                self._log(f"🎁 Đã mở thành công 1 {box_label} (toàn bộ công trình thiếu tài nguyên).")

                # Kiểm tra sức chứa tối đa của kho tài nguyên qua /api/resource/info để tránh tràn kho
                res_data = self.gateway.resource_info(self.city_id) or {}
                if res_data:
                    max_storage = int(res_data.get("m_lmax_storage", res_data.get("max_storage", 0)))
                    if max_storage > 0:
                        balances = (
                            res_data.get("m_lwood_balance", res_data.get("wood", 0)),
                            res_data.get("m_lstone_balance", res_data.get("stone", 0)),
                            res_data.get("m_liron_balance", res_data.get("iron", 0)),
                            res_data.get("m_lfood_balance", res_data.get("food", 0)),
                        )
                        if all(int(v) >= max_storage for v in balances):
                            self._log("⚠️ Kho tài nguyên đã đầy sức chứa tối đa, ngừng mở thêm đạo cụ.")
                            self._storage_full = True
                return True

        self._log("⚠️ Không còn rương tài nguyên nào trong túi đồ có thể mở.")
        return False

    def _handle_city_not_found(self) -> str:
        self._log("⚠️ Căn cứ không còn tồn tại trên máy chủ (mã 4), dừng theo dõi căn cứ này.")
        if self.on_city_missing:
            try:
                self.on_city_missing(self.city_id)
            except Exception:
                pass
        return "city_not_found"

    def _sync_once_when_busy(self) -> Optional[str]:
        if getattr(self, "_synced_once", False):
            return None
        try:
            rb, rb_ret, rb_ok = self._fetch_real_buildings_checked()
            if rb_ret == RET_CITY_NOT_FOUND:
                return self._handle_city_not_found()
            if rb_ok or rb_ret == RET_OK:
                self._synced_once = True
            if rb_ok and self.on_sync_data:
                self.on_sync_data(self.city_id, {k: dict(v) for k, v in rb.items()})
        except CaptchaRequired:
            raise
        except Exception:
            pass
        return None

    def run_once(self) -> str:
        now_mono = time.monotonic()
        if self._c77_cache_external:
            self._c77_cache_external = False
        else:
            self._c77_cache = None
            self._c77_from_shared_cache = False
        self._storage_full = False

        # Bỏ qua cục bộ thông minh khi tất cả slot đều đang thi công và chưa bật tăng tốc
        if not self.auto_speedup and getattr(self, "_synced_once", False) and now_mono < self._busy_until:
            if self.auto_comfort and now_mono >= self._comfort_next_check:
                self.check_and_comfort_city()
            if self.auto_boost and now_mono >= self._boost_until:
                self.check_and_activate_boost()
            return "slots_busy"

        # 1. Kích hoạt Boost nếu được cấu hình
        if self.auto_boost and now_mono >= self._boost_until:
            self.check_and_activate_boost()

        # 2. An dân nếu sĩ khí thấp (giới hạn tần suất bằng comfort_interval)
        if self.auto_comfort and now_mono >= self._comfort_next_check:
            self.check_and_comfort_city()

        # 3. Tự động tăng tốc các slot đang thi công theo cơ chế ZBuild
        if self.auto_speedup:
            self.process_speedup()

        # 4. Kiểm tra các slot nâng cấp đang bận
        active_slots, slots_ok = self._fetch_active_upgrade_slots()
        if not slots_ok:
            self._log("⚠️ Không đọc được danh sách công trình đang thi công từ máy chủ, bỏ qua lượt xây này.")
            return "slots_read_failed"
        if len(active_slots) >= self.max_slots:
            self._update_busy_until(active_slots)
            missing_res = self._sync_once_when_busy()
            if missing_res:
                return missing_res
            return "slots_busy"

        self._busy_until = 0.0
        available_slots = self.max_slots - len(active_slots)
        if available_slots <= 0:
            missing_res = self._sync_once_when_busy()
            if missing_res:
                return missing_res
            return "slots_busy"

        # Nếu vừa thiếu tài nguyên toàn thành (không tự mở rương), nghỉ cooldown trước khi spam lại id=65
        if (
            not self.auto_open_box
            and getattr(self, "_synced_once", False)
            and now_mono < self._resource_cooldown_until
        ):
            return "insufficient_resources"

        # 4. Lấy danh sách công trình thực tế (tuyệt đối không suy diễn cấp 0 khi API lỗi/rỗng)
        real_buildings, rb_ret, rb_ok = self._fetch_real_buildings_checked()
        if not rb_ok:
            if rb_ret == RET_CITY_NOT_FOUND:
                return self._handle_city_not_found()
            self._log("⚠️ Không đọc được danh sách công trình thực tế từ máy chủ, bỏ qua lượt xây này.")
            return "buildings_read_failed"
        self._synced_once = True
        if self.on_sync_data:
            try:
                self.on_sync_data(self.city_id, {k: dict(v) for k, v in real_buildings.items()})
            except Exception:
                pass

        # Trích xuất danh sách pid đang được nâng cấp dở
        busy_pids = set()
        for s in active_slots:
            if isinstance(s, (list, tuple)) and len(s) > 0:
                try:
                    busy_pids.add(int(s[0]))
                except (ValueError, TypeError):
                    pass
            elif isinstance(s, dict):
                if "pid" in s:
                    busy_pids.add(int(s["pid"]))
                elif "bid" in s:
                    busy_pids.add(int(s["bid"]))

        # 5. Duyệt danh sách quy hoạch và gửi lệnh nâng/hạ cấp cho tới khi lấp đầy available_slots
        processed_count = 0
        has_uncompleted = False
        has_eligible_candidate = False
        last_error = None
        opened_boxes_count = 0

        # Sắp xếp danh sách duyệt: Công trình bình thường duyệt trước, các ô lỗi 261/245 kiểm tra sau cùng
        normal_plans = [p for p in self.plans if p.pid not in self.deferred_pids]
        deferred_plans = [p for p in self.plans if p.pid in self.deferred_pids]

        if self.even_upgrade:
            # Cân bằng cấp độ toàn thành phố (toàn cục)
            def sort_even(plans_list):
                upgrades = []
                downgrades = []
                for p in plans_list:
                    cur = real_buildings.get(p.pid, {"gid": p.gid, "level": 0})
                    if cur["level"] < p.target_level:
                        upgrades.append(p)
                    else:
                        downgrades.append(p)
                upgrades.sort(key=lambda p: real_buildings.get(p.pid, {}).get("level", 0))
                return upgrades + downgrades

            normal_plans = sort_even(normal_plans)
            deferred_plans = sort_even(deferred_plans)
        else:
            # Mặc định: Bảo toàn thứ tự Loại công trình, nâng đồng đều nội bộ loại (ADR-0016)
            normal_plans = self._order_plans_by_type_even(normal_plans, real_buildings)
            deferred_plans = self._order_plans_by_type_even(deferred_plans, real_buildings)

        ordered_plans = normal_plans + deferred_plans

        abort_loop = False
        while processed_count < available_slots and not abort_loop:
            starved_pids = set()
            built_any_in_pass = False

            for plan in ordered_plans:
                if not getattr(plan, "enabled", True):
                    continue
                cur = real_buildings.get(plan.pid, {"gid": plan.gid, "level": 0})
                cur_lvl = cur["level"]
                if cur_lvl == plan.target_level:
                    self.deferred_pids.discard(plan.pid)
                    continue

                has_uncompleted = True

                if plan.pid in busy_pids:
                    continue

                if plan.pid in self.skipped_pids:
                    continue

                if plan.pid in starved_pids:
                    continue

                has_eligible_candidate = True
                action_type = 1 if cur_lvl < plan.target_level else 2
                bname = plan.name or BUILDING_NAMES.get(plan.gid, f"Công trình {plan.gid}")
                action_verb = "nâng cấp" if action_type == 1 else "hạ cấp"
                next_lvl = cur_lvl + 1 if action_type == 1 else cur_lvl - 1
                icon = "🏗️" if action_type == 1 else "🏚️"

                resp = self.gateway.update_building(
                    self.city_id, plan.pid, plan.gid, action_type
                )
                ret = resp.get("ret", RET_OK) if isinstance(resp, dict) and resp else -1
                if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
                    raise CaptchaRequired()

                if ret == RET_OK:
                    if plan.pid in self.deferred_pids:
                        self._log(f"🎉 Slot {plan.pid} ({bname}) đã được gỡ hoãn và {action_verb} thành công!")
                        self.deferred_pids.discard(plan.pid)
                    self._log(f"{icon} Đang {action_verb} slot {plan.pid} ({bname}) từ cấp {cur_lvl} {'lên' if action_type == 1 else 'xuống'} {next_lvl}")
                    if self.auto_speedup:
                        self._c77_cache = None
                        self.process_speedup()
                    processed_count += 1
                    busy_pids.add(plan.pid)
                    built_any_in_pass = True
                    real_buildings[plan.pid] = {"gid": plan.gid, "level": next_lvl, "name": bname}
                    if processed_count >= available_slots:
                        break
                elif ret == 261:
                    self._log(f"⚠️ {action_verb.capitalize()} slot {plan.pid} ({bname}) bị chặn (mã 261). Bỏ qua, nâng cấp công trình khác (hoãn kiểm tra cuối ở vòng sau)...")
                    self.skipped_pids.add(plan.pid)
                    self.deferred_pids.add(plan.pid)
                    if not last_error:
                        last_error = "blocked_error_261"
                    continue
                elif ret == 245:
                    self._log(f"⚠️ Chưa đủ điều kiện tiên quyết để {action_verb} slot {plan.pid} ({bname}) (mã 245). Bỏ qua, nâng cấp công trình khác (hoãn kiểm tra cuối ở vòng sau)...")
                    self.skipped_pids.add(plan.pid)
                    self.deferred_pids.add(plan.pid)
                    if not last_error:
                        last_error = "prerequisites_not_met"
                    continue
                elif ret == 36:
                    self._log(f"⚠️ Không thể hạ cấp slot {plan.pid} ({bname}) (đã đến cấp tối thiểu)")
                    self.skipped_pids.add(plan.pid)
                    if not last_error:
                        last_error = "cannot_downgrade_min_level"
                    continue
                elif ret in (32, 37):
                    self._log(f"ℹ️ Không đủ tài nguyên để {action_verb} slot {plan.pid} ({bname}), chuyển qua công trình khác...")
                    starved_pids.add(plan.pid)
                    if not last_error:
                        last_error = "insufficient_resources"
                    continue
                elif ret == RET_CITY_NOT_FOUND:
                    return self._handle_city_not_found()
                else:
                    self._log(f"❌ {action_verb.capitalize()} slot {plan.pid} ({bname}) thất bại (mã {ret}). Bỏ qua, nâng cấp công trình khác...")
                    self.skipped_pids.add(plan.pid)
                    if not last_error:
                        last_error = f"{'upgrade' if action_type == 1 else 'downgrade'}_failed:{ret}"
                    # Kiểm tra lại số slot đang thi công từ máy chủ: nếu hàng đợi thực tế đã đầy thì dừng ngay
                    recheck_slots, recheck_ok = self._fetch_active_upgrade_slots(force=True)
                    if not recheck_ok:
                        abort_loop = True
                        break
                    if len(recheck_slots) >= self.max_slots:
                        self._update_busy_until(recheck_slots)
                        if processed_count > 0:
                            abort_loop = True
                            break
                        return "slots_busy"
                    continue

            if abort_loop or processed_count >= available_slots:
                break

            if built_any_in_pass:
                continue

            if starved_pids:
                if self.auto_open_box:
                    if opened_boxes_count < self.max_boxes_per_round:
                        opened = self._open_one_resource_box()
                        if opened:
                            opened_boxes_count += 1
                            continue
                        else:
                            break
                    else:
                        self._log(f"⚠️ Đã đạt giới hạn mở tối đa {self.max_boxes_per_round} rương/đợt mà vẫn chưa đủ tài nguyên.")
                        break
                else:
                    self._log("⚠️ Toàn bộ công trình khả dụng đều thiếu tài nguyên (chế độ tự mở rương đang Tắt).")
                    break
            else:
                break

        # 6. Tổng kết kết quả sau vòng lặp
        if processed_count > 0:
            self._resource_cooldown_until = 0.0
            self.skipped_pids.clear()
            return "upgrading"

        if not has_uncompleted:
            self._resource_cooldown_until = 0.0
            return "all_buildings_completed"

        if not has_eligible_candidate and self.skipped_pids:
            self.skipped_pids.clear()
            if not last_error:
                last_error = "all_eligible_buildings_skipped"

        if last_error == "insufficient_resources" and not self.auto_open_box:
            self._resource_cooldown_until = time.monotonic() + self.resource_cooldown

        if last_error:
            return last_error

        return "slots_busy"

    def _update_busy_until(self, active_slots: list) -> None:
        if self.auto_speedup or not active_slots:
            return
        remaining_times = [
            t for t in (self._extract_slot_remaining_seconds(s) for s in active_slots) if t > 0
        ]
        if remaining_times:
            self._busy_until = time.monotonic() + min(float(min(remaining_times)), 1800.0)

