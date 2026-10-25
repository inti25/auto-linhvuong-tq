import threading
from unittest.mock import MagicMock
import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.tasks.morale import MoraleTrainer


class FakeServer:
    def __init__(self, step_callback=None):
        self.calls = []
        self.step_callback = step_callback

    def post(self, url, data=None, headers=None, proxies=None, timeout=None):
        endpoint = url.split("/")[-1]
        self.calls.append((endpoint, data or {}))
        if self.step_callback:
            return self.step_callback(endpoint, data)
        return MagicMock(status_code=200, json=lambda: {"ret": 0})


def test_train_general_morale_increments_by_ten_until_target():
    # Ban đầu morale = 75, mục tiêu = 100 -> cần 3 đợt: +10 (lên 85), +10 (lên 95), +5 (lên 100)
    server = FakeServer()
    gw = GatewayClient(57, server, sleep=lambda s: None)
    trainer = MoraleTrainer(gw, poll_interval=0.001)

    steps = []
    success, final_morale, msg = trainer.train_general_morale(
        city_id=15230,
        general_id=417506,
        current_morale=75,
        target_morale=100,
        on_step=lambda cur, tgt, m="": steps.append((cur, tgt)),
    )

    assert success is True
    assert final_morale == 100
    morale_calls = [c for c in server.calls if "OPT.ashx" in c[0]]
    assert len(morale_calls) == 3

    # Kiểm tra các điểm cộng qua từng đợt
    add_points = [int(c[1]["lAddPoint"]) for c in morale_calls]
    assert add_points == [10, 10, 5]
    assert steps == [(85, 100), (95, 100), (100, 100)]


def test_train_general_morale_stops_when_error():
    # Đợt 2 server báo lỗi 15 (hết lúa)
    opt_count = 0

    def mock_cb(endpoint, data):
        nonlocal opt_count
        if "OPT.ashx" in endpoint:
            opt_count += 1
            if opt_count == 2:
                return MagicMock(status_code=200, json=lambda: {"ret": 15})
        return MagicMock(status_code=200, json=lambda: {"ret": 0})

    server = FakeServer(step_callback=mock_cb)
    gw = GatewayClient(57, server, sleep=lambda s: None)
    trainer = MoraleTrainer(gw, poll_interval=0.001)

    success, final_morale, msg = trainer.train_general_morale(
        city_id=15230,
        general_id=417506,
        current_morale=70,
        target_morale=100,
    )

    assert success is False
    assert final_morale == 80  # Lên được 1 lần +10 trước khi lỗi
    assert "15" in msg


def test_train_general_morale_respects_stop_event():
    stop_event = threading.Event()
    stop_event.set()

    server = FakeServer()
    gw = GatewayClient(57, server, sleep=lambda s: None)
    trainer = MoraleTrainer(gw, poll_interval=0.001)

    success, final_morale, msg = trainer.train_general_morale(
        city_id=15230,
        general_id=417506,
        current_morale=60,
        target_morale=100,
        stop_event=stop_event,
    )

    assert success is False
    assert final_morale == 60
    assert len(server.calls) == 0


def test_train_multiple_generals_concurrency():
    server = FakeServer()
    gw = GatewayClient(57, server, sleep=lambda s: None)
    trainer = MoraleTrainer(gw, poll_interval=0.001)

    targets = [
        {"city_id": 15230, "general_id": 101, "current_morale": 90, "name": "Triệu Vân"},
        {"city_id": 15230, "general_id": 102, "current_morale": 80, "name": "Quan Vũ"},
        {"city_id": 15237, "general_id": 103, "current_morale": 95, "name": "Trương Phi"},
    ]

    progress_reports = []

    def on_prog(done, total, res):
        progress_reports.append((done, total, res["general_id"]))

    results = trainer.train_multiple_generals(
        targets=targets,
        target_morale=100,
        max_workers=3,
        on_progress=on_prog,
    )

    assert len(results) == 3
    assert all(r["success"] for r in results.values())
    assert results[101]["final_morale"] == 100
    assert results[102]["final_morale"] == 100
    assert results[103]["final_morale"] == 100
    assert len(progress_reports) == 3


def test_train_general_morale_waits_when_upgrading_in_progress():
    """Kiểm tra khi tướng đang luyện dở (upgrading_time > 0):
    - Bot phải đợi hoàn tất lượt đang luyện dở, cập nhật lại sĩ khí mới từ API 76.
    - Tiếp tục gọi API 47 cho các lượt tiếp theo cho đến khi đạt target_morale mới dừng.
    """
    api_76_call_count = 0

    def mock_cb(endpoint, data):
        nonlocal api_76_call_count
        if "Common.ashx" in endpoint and data.get("id") == "76" or "id=76" in endpoint or endpoint == "Common.ashx":
            # API 76
            api_76_call_count += 1
            if api_76_call_count == 1:
                # Lần 1: đang luyện dở, morale 80, upgrading_time 2s
                return MagicMock(status_code=200, json=lambda: {
                    "ret": 0,
                    "list": [[15230, "Thành", [[417506, "Triệu Vân", 0, "", 0, 100, 0, 0, 0, 80, 2, 500]]]]
                })
            elif api_76_call_count == 2:
                # Lần 2: sau khi đợi 2s xong, morale đã lên 90, upgrading_time = 0
                return MagicMock(status_code=200, json=lambda: {
                    "ret": 0,
                    "list": [[15230, "Thành", [[417506, "Triệu Vân", 0, "", 0, 100, 0, 0, 0, 90, 0, 500]]]]
                })
            elif api_76_call_count == 3:
                # Lần 3: sau khi bot gọi API 47 lần 2, đang luyện tiếp lên 100, upgrading_time 2s
                return MagicMock(status_code=200, json=lambda: {
                    "ret": 0,
                    "list": [[15230, "Thành", [[417506, "Triệu Vân", 0, "", 0, 100, 0, 0, 0, 90, 2, 500]]]]
                })
            else:
                # Lần 4: hoàn tất, morale 100, upgrading_time = 0
                return MagicMock(status_code=200, json=lambda: {
                    "ret": 0,
                    "list": [[15230, "Thành", [[417506, "Triệu Vân", 0, "", 0, 100, 0, 0, 0, 100, 0, 500]]]]
                })
        elif "OPT.ashx" in endpoint and (data.get("id") == "47" or "id=47" in endpoint or endpoint == "OPT.ashx"):
            # Nếu gọi API 47 khi đang upgrading_time > 0 (ví dụ api_76_call_count == 1) -> lỗi 40
            if api_76_call_count < 2:
                return MagicMock(status_code=200, json=lambda: {"ret": 40})
            return MagicMock(status_code=200, json=lambda: {"ret": 0})
        return MagicMock(status_code=200, json=lambda: {"ret": 0})

    server = FakeServer(step_callback=mock_cb)
    gw = GatewayClient(57, server, sleep=lambda s: None)
    trainer = MoraleTrainer(gw)

    steps = []
    success, final_morale, msg = trainer.train_general_morale(
        city_id=15230,
        general_id=417506,
        current_morale=80,
        target_morale=100,
        on_step=lambda cur, tgt: steps.append((cur, tgt)),
    )

    assert success is True
    assert final_morale == 100
    assert "Đã luyện thành công" in msg or "đạt mục tiêu" in msg

