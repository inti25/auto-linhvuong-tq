import threading
import time

import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.roster import Army
from linhvuong.tasks.thao_phat import (
    THAOPHAT_MISSIONS,
    TargetArmy,
    ThaoPhatAutoRunner,
    ThaoPhatExecutor,
)


class Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeServer:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        endpoint = url.split("/GateWay/")[1]
        self.calls.append((endpoint, dict(data)))
        payload = self.responses.get(endpoint, {"ret": 0})
        if isinstance(payload, list):
            return Resp(payload.pop(0) if payload else {"ret": 0})
        return Resp(payload)


def make_executor(responses=None):
    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)
    return ThaoPhatExecutor(client), server


def test_missions_defined():
    assert 0 in THAOPHAT_MISSIONS
    assert THAOPHAT_MISSIONS[0]["name"] == "Sơn Tặc"
    assert THAOPHAT_MISSIONS[0]["max_generals"] == 3
    assert THAOPHAT_MISSIONS[2]["name"] == "Đổng Trác"
    assert THAOPHAT_MISSIONS[2]["max_generals"] == 5


def test_adjust_troops_only_adds_when_deficient_never_removes_excess():
    executor, server = make_executor()
    # Hiện có: 100 bộ, 50 kỵ, 200 cung
    # Mục tiêu: 150 bộ (thiếu 50 -> bổ sung), 50 kỵ (đủ -> giữ), 100 cung (thừa 100 -> KHÔNG tháo)
    current = Army(infantry=100, cavalry=50, archers=200)
    target = TargetArmy(infantry=150, cavalry=50, archers=100)

    results = executor.adjust_troops(city_id=15230, general_id=417506, current_army=current, target_army=target)

    # Chỉ gọi API cho Bộ binh (+50), KHÔNG gọi tháo Cung binh (-100)
    recruits = [c for c in server.calls if c[0] == "OPT.ashx?id=6"]
    assert len(recruits) == 1
    assert recruits[0][1]["lSoldierType"] == "1"
    assert recruits[0][1]["lAmount"] == "50"
    assert recruits[0][1]["lGeneralID"] == "417506"
    assert recruits[0][1]["tid"] == "15230"
    assert len(results) == 1
    assert results[0] == (1, 50, True, 0)


def test_adjust_morale_calls_id_47_when_below_min():
    executor, server = make_executor()
    success, ret_code = executor.adjust_morale(city_id=15230, general_id=417506, current_morale=40, min_morale=51)

    assert success is True
    assert ret_code == 0
    morale_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=47"]
    assert len(morale_calls) == 1
    assert morale_calls[0][1]["lGeneralID"] == "417506"
    assert morale_calls[0][1]["tid"] == "15230"
    assert int(morale_calls[0][1]["lAddPoint"]) == 10  # Mỗi lần nâng tăng tối đa 10 điểm


def test_adjust_morale_skips_when_already_sufficient():
    executor, server = make_executor()
    success, ret_code = executor.adjust_morale(city_id=15230, general_id=417506, current_morale=85, min_morale=51)

    assert success is True
    assert ret_code == 0
    morale_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=47"]
    assert len(morale_calls) == 0


def test_send_thaophat_request_builds_correct_payload():
    executor, server = make_executor({"OPT.ashx?id=62": {"ret": 0}})
    res = executor.send_request(city_id=15230, task_id=0, general_ids=[417506, 417507])

    assert res.success is True
    send_call = [c for c in server.calls if c[0] == "OPT.ashx?id=62"][0]
    data = send_call[1]
    assert data["taskid"] == "0"
    assert data["counts"] == "2"
    assert data["general1"] == "417506"
    assert data["general2"] == "417507"
    assert data["general3"] == "0"


def test_send_thaophat_truncates_exceeding_generals():
    executor, server = make_executor({"OPT.ashx?id=62": {"ret": 0}})
    # Task 0 (Sơn Tặc) max 3 generals
    res = executor.send_request(city_id=15230, task_id=0, general_ids=[1, 2, 3, 4, 5])
    assert res.success is True
    send_call = [c for c in server.calls if c[0] == "OPT.ashx?id=62"][0]
    data = send_call[1]
    assert data["counts"] == "3"
    assert data["general4"] == "0"


def test_send_thaophat_handles_server_errors():
    executor, _ = make_executor({"OPT.ashx?id=62": {"ret": 10039}})
    res = executor.send_request(city_id=15230, task_id=0, general_ids=[417506])
    assert res.success is False
    assert res.code == 10039
    assert "Sỹ khí" in res.message


def test_auto_runner_execution_and_stop():
    import threading
    import time

    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    c76 = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 95, 0, 95, 0, 100, 0, 501]]]]}
    c32_idle = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 100, 240, 240]]]]}
    c32_busy = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 24, 4, 100, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": c76,
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_busy,
            {"ret": 0, "list": []}, c32_idle,
        ],
        "OPT.ashx?id=6": {"ret": 0},
        "OPT.ashx?id=47": {"ret": 0},
        "OPT.ashx?id=62": {"ret": 0},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)

    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=100, cavalry=0, archers=100),
        min_morale=90,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(100):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    assert runner.completed_cycles == 1
    assert any("BẮT ĐẦU VÒNG LẶP THẢO PHẠT TỰ ĐỘNG" in l for l in logs)
    assert any("Hoàn thành lượt 1" in l for l in logs)


def test_check_recruits_from_common_ashx_27():
    c27 = {
        "ret": 0,
        "list": [
            [15230, "Thành Chính", 250, 10, 20, 30],
            [15231, "Thành Phụ", 100, 5, 10, 15],
        ],
    }
    executor, server = make_executor({"Common.ashx?id=27": c27})
    count = executor.check_recruits(city_id=15230)
    assert count == 250

    calls = [c for c in server.calls if c[0] == "Common.ashx?id=27"]
    assert len(calls) == 1

    # Không tìm thấy thành
    count_missing = executor.check_recruits(city_id=99999)
    assert count_missing is None


def test_buy_recruits_success():
    executor, server = make_executor({"OPT.ashx?id=41": {"ret": 0}})
    succ, ret = executor.buy_recruits(city_id=15230, amount=8)
    assert succ is True
    assert ret == 0

    buy_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=41"]
    assert len(buy_calls) == 1
    assert buy_calls[0][1]["lAmount"] == "8"
    assert buy_calls[0][1]["tid"] == "15230"


def test_buy_recruits_with_auto_comfort_when_ret_34():
    # Lần 1 mua trả về 34 (thiếu dân), sau khi gọi an dân (id=4) lần 2 trả về 0
    responses = {
        "OPT.ashx?id=41": [{"ret": 34}, {"ret": 0}],
        "OPT.ashx?id=4": {"ret": 0},
    }
    executor, server = make_executor(responses)
    succ, ret = executor.buy_recruits(city_id=15230, amount=50, auto_comfort=True)

    assert succ is True
    assert ret == 0

    comfort_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=4"]
    assert len(comfort_calls) == 1
    assert comfort_calls[0][1]["lType"] == "4"
    assert comfort_calls[0][1]["tid"] == "15230"

    buy_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=41"]
    assert len(buy_calls) == 2


def test_adjust_troops_auto_recruits_on_ret_53():
    # Giả lập đúng tình huống của người dùng:
    # Tướng cần bổ sung +8 Bộ binh.
    # Lần đầu gọi id=6 trả về ret 53 (Tân binh không đủ).
    # Với auto_recruit=True: tự động gọi id=41 mua 8 tân binh, rồi gọi lại id=6 thành công.
    responses = {
        "OPT.ashx?id=6": [{"ret": 53}, {"ret": 0}],
        "OPT.ashx?id=41": {"ret": 0},
    }
    executor, server = make_executor(responses)

    current = Army(infantry=100, cavalry=0, archers=0)
    target = TargetArmy(infantry=108, cavalry=0, archers=0)
    logs = []

    results = executor.adjust_troops(
        city_id=15230,
        general_id=417506,
        current_army=current,
        target_army=target,
        auto_recruit=True,
        on_log=lambda m: logs.append(m),
    )

    assert len(results) == 1
    stype, diff, succ, ret_code = results[0]
    assert stype == 1
    assert diff == 8
    assert succ is True
    assert ret_code == 0

    # Kiểm tra API id=41 được gọi để mua đúng 8 tân binh
    buy_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=41"]
    assert len(buy_calls) == 1
    assert buy_calls[0][1]["lAmount"] == "8"

    # Kiểm tra API id=6 được gọi 2 lần (thất bại 53 -> thử lại 0)
    troop_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=6"]
    assert len(troop_calls) == 2

    # Kiểm tra log có thông báo chiêu mộ
    assert any("Tân binh không đủ" in l for l in logs)
    assert any("Chiêu mộ thành công 8 tân binh" in l for l in logs)


def test_adjust_troops_does_not_auto_recruit_when_disabled():
    responses = {
        "OPT.ashx?id=6": {"ret": 53},
        "OPT.ashx?id=41": {"ret": 0},
    }
    executor, server = make_executor(responses)

    current = Army(infantry=100, cavalry=0, archers=0)
    target = TargetArmy(infantry=108, cavalry=0, archers=0)

    results = executor.adjust_troops(
        city_id=15230,
        general_id=417506,
        current_army=current,
        target_army=target,
        auto_recruit=False,
    )

    assert len(results) == 1
    stype, diff, succ, ret_code = results[0]
    assert succ is False
    assert ret_code == 53

    # Không gọi API mua tân binh
    buy_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=41"]
    assert len(buy_calls) == 0


def test_auto_runner_proactive_recruits_when_insufficient():
    import threading
    import time

    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    # Tướng đang có 90 bộ, mục tiêu 100 bộ (thiếu 10 bộ)
    c76 = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 90, 0, 95, 0, 100, 0, 501]]]]}
    c32_idle = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 100, 240, 240]]]]}
    # Kho chỉ có 2 tân binh trong khi cần 10 tân binh -> thiếu 8
    c27 = {"ret": 0, "list": [[15230, "NB", 2]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": c76,
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_idle,
        ],
        "Common.ashx?id=27": c27,
        "OPT.ashx?id=41": {"ret": 0},
        "OPT.ashx?id=6": {"ret": 0},
        "OPT.ashx?id=47": {"ret": 0},
        "OPT.ashx?id=62": {"ret": 0},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)

    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=100, cavalry=0, archers=0),
        min_morale=90,
        auto_recruit=True,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(100):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    # Kiểm tra API mua tân binh đã được gọi chủ động trước khi biên chế
    buy_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=41"]
    assert len(buy_calls) == 1
    assert buy_calls[0][1]["lAmount"] == "8"
    assert any("Đã chiêu mộ thành công 8 tân binh" in l for l in logs)


def test_auto_runner_waits_for_morale_upgrade_and_rechecks():
    import threading
    import time

    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    # API 76: ban đầu upgrading_time = 0, sau khi gọi nâng sĩ khí upgrading_time = 5, sau đó = 0
    c76_initial = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 85, 0, 501]]]]}
    c76_upgrading = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 85, 5, 501]]]]}
    c76_done = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 95, 0, 501]]]]}

    # API 32: ban đầu morale = 85 (< min 95), sau khi nâng xong morale = 95
    c32_low_morale = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 85, 240, 240]]]]}
    c32_high_morale = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 95, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": [
            c76_initial,    # Bước 1: kiểm tra rảnh rỗi
            c76_initial,    # Bước 2: chuẩn bị biên chế
            c76_initial,    # Bước 3 iter 1: phát hiện morale 85 < 95 (up_t=0) -> gọi adjust_morale
            c76_upgrading,  # Bước 3 iter 2: kiểm tra nâng sĩ khí (5s <= 300s, 85+10=95 >= 95 -> OK)
            c76_upgrading,  # Kiểm tra lại trước khi xuất quân (5s <= 300s -> sẵn sàng)
            c76_done,       # Bước 5: Theo dõi sau xuất quân
        ],
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_low_morale,  # Bước 1
            {"ret": 0, "list": []}, c32_low_morale,  # Bước 2
            {"ret": 0, "list": []}, c32_low_morale,  # Bước 3 iter 1
            {"ret": 0, "list": []}, c32_low_morale,  # Bước 3 iter 2
            {"ret": 0, "list": []}, c32_low_morale,  # Kiểm tra lại
            {"ret": 0, "list": []}, c32_high_morale, # Bước 5
        ],
        "OPT.ashx?id=47": {"ret": 0},
        "OPT.ashx?id=62": {"ret": 0},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)

    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=100, cavalry=0, archers=0),
        min_morale=95,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(100):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    # Xác minh thứ tự: Nâng sĩ khí -> Kiểm tra lại (nhận thấy 5s <= 300s) -> Xuất quân ngay
    morale_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=47"]
    send_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=62"]
    assert len(morale_calls) == 1
    assert len(send_calls) == 1

    # Kiểm tra log: vì 5s <= 300s nên hoàn tất trên đường đi và xuất phát ngay
    assert any("Bắt đầu nâng thành công" in l for l in logs)
    assert any("còn 5s <= hành quân 300s -> hoàn tất trên đường đi" in l for l in logs)
    assert any("Kiểm tra lại" in l for l in logs)
    assert any("Gửi lệnh Thảo Phạt 'Sơn Tặc'" in l for l in logs)


def test_auto_runner_waits_when_morale_upgrade_exceeds_travel_time():
    import threading
    import time

    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    # Nhiệm vụ 0: travel_time = 300s.
    # Ban đầu upgrading_time = 350s (> 300s, thừa 50s -> phải đợi)
    # Sau đó upgrading_time = 300s (<= 300s -> đạt điều kiện xuất phát)
    c76_initial = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 85, 0, 501]]]]}
    c76_too_long = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 85, 350, 501]]]]}
    c76_ready = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 85, 300, 501]]]]}

    c32_low = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 85, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": [
            c76_initial,   # Bước 1
            c76_initial,   # Bước 2
            c76_too_long,  # Bước 3 wait loop lần 1 (350s > 300s)
            c76_ready,     # Bước 3 wait loop lần 2 (300s <= 300s)
            c76_ready,     # Kiểm tra lại (300s <= 300s)
            c76_ready,     # Bước 5
        ],
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_low,
            {"ret": 0, "list": []}, c32_low,
            {"ret": 0, "list": []}, c32_low,
            {"ret": 0, "list": []}, c32_low,
            {"ret": 0, "list": []}, c32_low,
            {"ret": 0, "list": []}, c32_low,
        ],
        "OPT.ashx?id=47": {"ret": 0},
        "OPT.ashx?id=62": {"ret": 0},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)

    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=100, cavalry=0, archers=0),
        min_morale=95,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(100):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    # Xác minh bot có chờ khi thời gian nâng > travel_time
    assert any("Đang đợi nâng sĩ khí" in l for l in logs)
    assert any("còn 350s > hành quân 300s (cần giảm thêm 50s)" in l for l in logs)
    assert any("còn 300s <= hành quân 300s -> hoàn tất trên đường đi" in l for l in logs)
    assert any("Gửi lệnh Thảo Phạt 'Sơn Tặc'" in l for l in logs)


def test_auto_runner_waits_when_morale_upgrade_does_not_reach_min():
    """Kiểm tra trường hợp nâng lần 1 chưa đủ sĩ khí (ví dụ 84 -> 94 < 95):
    - Dù thời gian nâng còn lại <= travel_time, bot KHÔNG xuất quân vội mà chờ hoàn tất lần 1.
    - Sau khi lần 1 xong (lên 94), bot nâng tiếp lần 2 (94 -> 100 >= 95).
    - Ở lần 2 này đảm bảo đủ sĩ khí nên mới tính upgrading_time <= travel_time để xuất phát.
    """
    import threading
    import time

    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    # Lần 1: sĩ khí 84, nâng lần 1 (upgrading_time=100s <= 300s nhưng projected=94 < 95 -> phải chờ)
    c76_initial = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 84, 0, 501]]]]}
    c76_up1_active = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 84, 100, 501]]]]}
    c76_up1_done = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 94, 0, 501]]]]}
    # Lần 2: sau khi nâng lần 2, upgrading_time=100s <= 300s và projected=100 >= 95 -> Đủ điều kiện!
    c76_up2_active = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 94, 100, 501]]]]}
    c76_done = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 100, 0, 0, 0, 100, 0, 501]]]]}

    c32_m84 = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 84, 240, 240]]]]}
    c32_m94 = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 94, 240, 240]]]]}
    c32_m100 = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 100, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": [
            c76_initial,     # Bước 1
            c76_initial,     # Bước 2
            c76_initial,     # Bước 3 iter 1: phát hiện 84 < 95 (up_t=0) -> kích hoạt nâng lần 1
            c76_up1_active,  # Bước 3 iter 2: đang nâng lần 1 (100s, projected=94 < 95 -> chờ)
            c76_up1_done,    # Bước 3 iter 3: lần 1 xong (up_t=0, sĩ khí 94) -> kích hoạt nâng lần 2
            c76_up2_active,  # Bước 3 iter 4: đang nâng lần 2 (100s <= 300s, projected=100 >= 95 -> OK)
            c76_up2_active,  # Kiểm tra lại (100s <= 300s, 94+10=100 >= 95 -> Sẵn sàng)
            c76_done,        # Bước 5
        ],
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_m84,   # Bước 1
            {"ret": 0, "list": []}, c32_m84,   # Bước 2
            {"ret": 0, "list": []}, c32_m84,   # Bước 3 iter 1
            {"ret": 0, "list": []}, c32_m84,   # Bước 3 iter 2
            {"ret": 0, "list": []}, c32_m94,   # Bước 3 iter 3 (sĩ khí đã lên 94)
            {"ret": 0, "list": []}, c32_m94,   # Bước 3 iter 4
            {"ret": 0, "list": []}, c32_m94,   # Kiểm tra lại
            {"ret": 0, "list": []}, c32_m100,  # Bước 5
        ],
        "OPT.ashx?id=47": {"ret": 0},
        "OPT.ashx?id=62": {"ret": 0},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)

    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=100, cavalry=0, archers=0),
        min_morale=95,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(100):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    morale_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=47"]
    send_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=62"]

    # Phải gọi nâng sĩ khí 2 lần (lần 1 từ 84 -> 94, lần 2 từ 94 -> 100)
    assert len(morale_calls) == 2
    assert len(send_calls) == 1

    # Kiểm tra log phản ánh chính xác:
    # Lần 1: báo đạt 94 < 95 (cần nâng tiếp)
    assert any("chờ đạt 94 để nâng tiếp lượt sau" in l for l in logs)
    # Lần 2: báo đạt 100 >= 95 (đạt điều kiện xuất phát)
    assert any("lần nâng này đạt 100 >= 95" in l or "100 >= 95" in l for l in logs)
    assert any("Gửi lệnh Thảo Phạt 'Sơn Tặc'" in l for l in logs)


def test_auto_runner_detects_diluted_morale_after_troop_recruitment():
    """Kiểm tra khi bổ sung tân binh vào đội hình làm sĩ khí giảm (ví dụ từ 97 xuống 85):
    - Ban đầu tướng có sĩ khí 97/95.
    - Sau khi bổ sung biên chế quân, Common.ashx?id=76 cập nhật sĩ khí thực tế còn 85.
    - Bot phát hiện sĩ khí bị giảm (85 < 95) và kích hoạt nâng sĩ khí chứ không vội xuất quân.
    """
    import threading
    import time

    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    # Ban đầu trước biên chế: 0 quân, sĩ khí 97
    c76_before_recruit = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 0, 0, 0, 0, 97, 0, 501]]]]}
    # Sau biên chế 15 bộ + 15 cung: sĩ khí giảm xuống 85!
    c76_after_recruit = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 15, 0, 15, 0, 85, 0, 501]]]]}
    # Đang nâng sĩ khí (5s <= 300s)
    c76_upgrading = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 15, 0, 15, 0, 85, 5, 501]]]]}
    c76_done = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 15, 0, 15, 0, 95, 0, 501]]]]}

    c32_stale_97 = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 97, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": [
            c76_before_recruit,  # Bước 1
            c76_before_recruit,  # Bước 2
            c76_after_recruit,   # Bước 3 iter 1: phát hiện sĩ khí thực tế trong id=76 đã giảm còn 85 < 95!
            c76_upgrading,       # Bước 3 iter 2: sau khi gọi nâng sĩ khí (5s <= 300s)
            c76_upgrading,       # Kiểm tra lại (5s <= 300s -> Sẵn sàng)
            c76_done,            # Bước 5
        ],
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_stale_97,  # Bước 1
            {"ret": 0, "list": []}, c32_stale_97,  # Bước 2
            {"ret": 0, "list": []}, c32_stale_97,  # Bước 3 iter 1 (trong id=32 vẫn là 97 cũ)
            {"ret": 0, "list": []}, c32_stale_97,  # Bước 3 iter 2
            {"ret": 0, "list": []}, c32_stale_97,  # Kiểm tra lại
            {"ret": 0, "list": []}, c32_stale_97,  # Bước 5
        ],
        "Common.ashx?id=27": {"ret": 0, "list": [[15230, "NB", 100]]},
        "OPT.ashx?id=6": {"ret": 0},
        "OPT.ashx?id=47": {"ret": 0},
        "OPT.ashx?id=62": {"ret": 0},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)

    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=15, cavalry=0, archers=15),
        min_morale=95,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(100):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    # Xác minh: Có biên chế lính, và sau đó PHẢI gọi nâng sĩ khí do sĩ khí giảm còn 85 < 95
    troop_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=6"]
    morale_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=47"]
    send_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=62"]

    assert len(troop_calls) == 2  # Bổ sung bộ + cung
    assert len(morale_calls) == 1  # Bắt buộc phải nâng sĩ khí do giảm còn 85
    assert len(send_calls) == 1

    assert any("Bổ sung Bộ +15" in l for l in logs)
    assert any("Bổ sung Cung +15" in l for l in logs)
    assert any("Sĩ khí hiện tại là 85/95" in l for l in logs)
    assert any("Sĩ khí 85 < 95" in l for l in logs)
    assert any("Gửi lệnh Thảo Phạt 'Sơn Tặc'" in l for l in logs)


def test_thao_phat_auto_runner_tracks_battle_logs():
    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    c76 = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 95, 0, 95, 0, 100, 0, 501]]]]}
    c32_idle = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 100, 240, 240]]]]}
    c32_busy = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 24, 4, 100, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": c76,
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_busy,
            {"ret": 0, "list": []}, c32_idle,
        ],
        "Common.ashx?id=27": {"ret": 0, "list": [[15230, "Thành Chính", 500, 10, 20, 30]]},
        "OPT.ashx?id=62": {"ret": 0},
        "OPT.ashx?id=24": [
            # Hiệp 1
            {
                "ret": 0,
                "site": "Thảo Phạt - Tiên Phong Doanh",
                "bout": 1,
                "bout_left": 1,
                "troops": [
                    [1, "inti00", 1, "Triệu Vân", 417506, "", 15230, 0, 1, 100, 0, 100, 0, 100, 0, 0, 0, 0, "", 1],
                    [11, "", 0, "Sơn Tặc", 0, "", 0, 0, 4, 100, 0, 50, 0, 50, 0, 0, 0, 0, "", 16],
                ],
            },
            # Hiệp 2
            {
                "ret": 0,
                "site": "Thảo Phạt - Tiên Phong Doanh",
                "bout": 2,
                "bout_left": 1,
                "troops": [
                    [1, "inti00", 1, "Triệu Vân", 417506, "", 15230, 0, 2, 94, 0, 95, 0, 100, 0, 0, 0, 0, "", 1],
                    [11, "", 0, "Sơn Tặc", 0, "", 0, 0, 4, 80, 0, 0, 0, 50, 0, 0, 0, 0, "", 16],
                ],
            },
            # Trận kết thúc
            {"ret": 13},
        ],
        "OPT.ashx?id=57": {"ret": 0},
        "OPT.ashx?id=26": {"ret": 0, "last_tips_id": 1, "tips": [[1, 100, "Triệu Vân quét sạch đạo quân Sơn Tặc!"]]},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)

    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=100, cavalry=0, archers=100),
        min_morale=95,
        track_battle=True,
        auto_counter=True,
        leave_boss_last=True,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(100):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    assert runner.completed_cycles == 1
    # Kiểm tra log chiến trường hiệp đấu
    assert any("Chiến trường - Hiệp 1" in l for l in logs)
    assert any("Chiến trường - Hiệp 2" in l for l in logs)
    assert any("Triệu Vân quét sạch đạo quân Sơn Tặc!" in l for l in logs)

    # Kiểm tra log kết quả chiến đấu (quân số thiệt hại và sĩ khí)
    assert any("🏆 [KẾT QUẢ CHIẾN ĐẤU] CHIẾN THẮNG!" in l for l in logs)
    assert any("THIỆT HẠI QUÂN TA:" in l for l in logs)
    assert any("Tổng quân số: 95/100 quân (Thiệt hại: -5 quân, -5.0%)" in l for l in logs)
    assert any("Sĩ khí trung bình: 94/100 (Ban đầu: 100/100, Biến động: -6)" in l for l in logs)
    assert any("Triệu Vân" in l and "Quân số 95/100 (Thiệt hại: -5 quân, -5.0%) | Sĩ khí: 94/100 (Giảm: -6)" in l for l in logs)
    assert any("KẾT QUẢ TIÊU DIỆT ĐỊCH:" in l for l in logs)
    assert any("Đã tiêu diệt: 50/50 quân (100.0%)" in l for l in logs)


def test_target_army_vietnamese_aliases():
    target = TargetArmy(bo_binh=1000, ky_binh=500, cung_binh=250)
    assert target.infantry == 1000
    assert target.cavalry == 500
    assert target.archers == 250


def test_thao_phat_runner_skips_troop_refill_when_auto_recruit_false():
    c29 = {"ret": 0, "generals": []}
    c76 = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 95, 0, 95, 0, 100, 0, 501]]]]}
    c32_idle = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 100, 240, 240]]]]}
    c32_busy = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 24, 4, 100, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": c76,
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_busy,
            {"ret": 0, "list": []}, c32_idle,
        ],
        "OPT.ashx?id=6": {"ret": 0},
        "OPT.ashx?id=47": {"ret": 0},
        "OPT.ashx?id=62": {"ret": 0},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)
    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=1000),
        min_morale=90,
        auto_recruit=False,
        stop_event=stop_event,
        log_callback=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        for _ in range(50):
            if runner.completed_cycles >= 1:
                stop_event.set()
                break
            time.sleep(0.01)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    # Xác nhận không có bất kỳ lệnh bổ sung quân lính nào (id=6 hay id=41) được gửi đi
    troop_calls = [c for c in server.calls if c[0] == "OPT.ashx?id=6" or c[0] == "OPT.ashx?id=41"]
    assert len(troop_calls) == 0
    assert any("Tự động bổ sung lính đang tắt" in l for l in logs)


def test_thao_phat_runner_skips_morale_upgrade_when_auto_morale_false():
    c29 = {"ret": 0, "generals": []}
    c76 = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 95, 0, 95, 0, 50, 0, 501]]]]}
    c32_idle = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 100, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": c76,
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_idle,
        ],
    }
    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)
    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=500),
        min_morale=95,
        auto_morale=False,
        stop_event=stop_event,
        log_callback=lambda m: logs.append(m),
        check_interval=0.01,
    )

    def stopper():
        time.sleep(0.05)
        stop_event.set()

    t = threading.Thread(target=stopper)
    t.start()
    runner.run()
    t.join()

    # Không gọi API id=47 khi auto_morale=False
    morale_calls = [c for c in server.calls if "OPT.ashx?id=47" in c[0]]
    assert len(morale_calls) == 0
    assert any("tự động nâng sĩ khí đang tắt" in l for l in logs)


def test_thao_phat_runner_start_thread_and_is_alive():
    server = FakeServer()
    client = GatewayClient(57, server, sleep=lambda s: None)
    stop_event = threading.Event()

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[],
        target_army=TargetArmy(),
        stop_event=stop_event,
        check_interval=0.01,
    )
    stop_event.set()
    t = runner.start()
    t.join(timeout=1.0)
    assert not runner.is_alive()


def test_thao_phat_battle_track_real_interval_regression_time_import():
    """Kiểm tra hồi quy: Chạy Thảo Phạt với check_interval thực tế (>= 1.0) khi vào chiến trường không bị NameError 'time'."""
    c29 = {"ret": 0, "city": [[15230, "NB"]]}
    c76 = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 95, 0, 95, 0, 100, 0, 501]]]]}
    c32_idle = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 0, 4, 100, 240, 240]]]]}
    c32_busy = {"ret": 0, "list": [[15230, "NB", 0, 0, [[417506, "廉复卢", "", 2, 0, 24, 4, 100, 240, 240]]]]}

    responses = {
        "Common.ashx?id=29": c29,
        "Common.ashx?id=76": c76,
        "Common.ashx?id=32": [
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_idle,
            {"ret": 0, "list": []}, c32_busy,
            {"ret": 0, "list": []}, c32_idle,
        ],
        "Common.ashx?id=27": {"ret": 0, "list": [[15230, "Thành Chính", 500, 10, 20, 30]]},
        "OPT.ashx?id=62": {"ret": 0},
        "Common.ashx?id=3": {"ret": 0, "status": 2, "current": [0, 0]},
        "OPT.ashx?id=24": {"ret": 13},
    }

    server = FakeServer(responses)
    client = GatewayClient(57, server, sleep=lambda s: None)
    stop_event = threading.Event()
    logs = []

    runner = ThaoPhatAutoRunner(
        gateway=client,
        city_id=15230,
        task_id=0,
        general_ids=[417506],
        target_army=TargetArmy(infantry=100, cavalry=0, archers=100),
        min_morale=95,
        track_battle=True,
        auto_counter=True,
        leave_boss_last=True,
        stop_event=stop_event,
        log_fn=lambda m: logs.append(m),
        check_interval=10.0,
    )
    # Chỉ dừng sau khi đã vào chiến trường và theo dõi xong
    wait_calls = []
    def mock_wait(s):
        wait_calls.append(s)
        if len(wait_calls) >= 2:
            stop_event.set()
            return True
        return False

    runner.wait = mock_wait
    runner.wait_cycle = lambda s: True

    runner.run()

    # Kiểm tra log xem có dòng ngoại lệ NameError: name 'time' is not defined không
    error_logs = [l for l in logs if "❌ Ngoại lệ trong vòng lặp Thảo Phạt" in l]
    assert not any("name 'time' is not defined" in l for l in error_logs)





