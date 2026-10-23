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
