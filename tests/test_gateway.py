import pytest
from linhvuong.gateway import GatewayClient


class MockRawResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def json(self):
        import json
        return json.loads(self.text)


class MockSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append((url, data))
        if self.responses:
            return self.responses.pop(0)
        return MockRawResponse('{"ret": 0}')


def test_gateway_parses_unquoted_ret_198599():
    # Phản hồi thực tế từ máy chủ Linh Vương khi hết hạn phiên: {ret:198599}
    session = MockSession([MockRawResponse("{ret:198599}")])
    client = GatewayClient(53, session, sleep=lambda s: None)
    res = client.call("OPT.ashx", 65, {"pid": "1"})
    # Phải parse được {"ret": 198599} thay vì bị lỗi Expecting property name enclosed in double quotes và trả về None
    assert res is not None
    assert res.get("ret") == 198599


def test_gateway_triggers_relogin_and_retries_on_198599():
    # Lần 1: {ret:198599} (hết hạn phiên)
    # Lần 2 (sau khi relogin): {"ret": 0, "msg": "success"}
    session = MockSession([
        MockRawResponse("{ret:198599}"),
        MockRawResponse('{"ret": 0, "msg": "success"}')
    ])
    relogin_called = []

    def relogin():
        relogin_called.append(True)
        return True

    client = GatewayClient(53, session, sleep=lambda s: None, relogin_callback=relogin)
    res = client.call("OPT.ashx", 65, {"pid": "1"})

    # 1. Đã gọi hàm relogin
    assert len(relogin_called) == 1
    # 2. Đã tự động gửi lại request và nhận kết quả thành công
    assert res is not None
    assert res.get("ret") == 0
    assert res.get("msg") == "success"
    # Tổng cộng gọi 2 lần post
    assert len(session.calls) == 2


def test_gateway_mounts_connection_pool():
    import requests
    from linhvuong.auth import USER_AGENT
    sess = requests.Session()
    client = GatewayClient(53, sess)
    adapter = sess.get_adapter("http://sg53.dipan.com")
    assert adapter._pool_maxsize == 32
    assert sess.headers.get("User-Agent") == USER_AGENT


def test_gateway_retries_on_502_without_proxy():
    session = MockSession([
        MockRawResponse("<html>502 Bad Gateway</html>", status_code=502),
        MockRawResponse('{"ret": 0, "ok": 1}', status_code=200),
    ])
    sleeps = []
    client = GatewayClient(57, session, sleep=sleeps.append)
    res = client.call("Common.ashx", 29, {"_": ""})
    assert res == {"ret": 0, "ok": 1}
    assert len(session.calls) == 2
    assert sleeps == [0.5]


def test_gateway_relogin_failed_returns_expired_result():
    session = MockSession([MockRawResponse("{ret:198599}")])
    client = GatewayClient(
        53, session, sleep=lambda s: None, relogin_callback=lambda: False
    )
    res = client.call("OPT.ashx", 65, {"pid": "1"})
    assert res is not None
    assert res.get("ret") == 198599
    assert len(session.calls) == 1


def test_gateway_relogin_only_once_per_call_prevents_infinite_loop():
    # Cả lần 1 và lần retry đều trả về 198599
    session = MockSession([
        MockRawResponse("{ret:198599}"),
        MockRawResponse("{ret:198599}"),
    ])
    relogin_count = 0

    def relogin():
        nonlocal relogin_count
        relogin_count += 1
        return True

    client = GatewayClient(
        53, session, sleep=lambda s: None, relogin_callback=relogin
    )
    res = client.call("OPT.ashx", 65, {"pid": "1"})
    # Chỉ gọi relogin đúng 1 lần trong 1 lệnh gọi API
    assert relogin_count == 1
    assert res is not None
    assert res.get("ret") == 198599
    assert len(session.calls) == 2


def test_gateway_relogin_recent_skips_duplicate_relogin():
    import time
    session = MockSession([
        MockRawResponse("{ret:198599}"),
        MockRawResponse('{"ret": 0, "msg": "ok"}'),
    ])
    relogin_called = []

    client = GatewayClient(
        53, session, sleep=lambda s: None, relogin_callback=lambda: relogin_called.append(True) or True
    )
    # Giả lập luồng khác vừa relogin xong 0.5s trước
    client._last_relogin_time = time.time() - 0.5

    res = client.call("OPT.ashx", 65, {"pid": "1"})
    # Không gọi lại relogin callback vì vừa mới làm mới
    assert len(relogin_called) == 0
    assert res is not None
    assert res.get("ret") == 0
    assert len(session.calls) == 2
