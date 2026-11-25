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


def test_gateway_parses_http_400_json_and_resolves_uid_and_rest():
    class _RestSession:
        def __init__(self):
            self.cookies = {"uid": "95"}
            self.get_calls = []
            self.post_calls = []

        def get(self, url, params=None, headers=None, timeout=None):
            self.get_calls.append((url, dict(params or {})))
            return MockRawResponse('{"ret": 0, "data": {"items": [{"m_lid": 10129}]}}')

        def post(self, url, data=None, headers=None, timeout=None):
            self.post_calls.append((url, dict(data or {})))
            return MockRawResponse('{"ret": 8105, "errMsg": "请求参数不一致或无效"}', status_code=400)

    sess = _RestSession()
    gw = GatewayClient(58, sess, sleep=lambda s: None)
    assert gw.get_user_id() == 95

    cl = gw.city_list()
    assert cl["data"]["items"][0]["m_lid"] == 10129
    assert sess.get_calls[0][1]["userId"] == 95

    err = gw.optimization("bulk-start", {"boxId": "1"})
    assert err == {"ret": 8105, "errMsg": "请求参数不一致或无效"}
    assert "Optimization.ashx?action=bulk-start" in sess.post_calls[0][0]


def test_gateway_parses_relaxed_json_table_payload():
    """Phản hồi relaxed-JSON dạng {ret:0,Table:[...]} giữ nguyên Table thay vì bị fallback cắt cụt."""
    session = MockSession([
        MockRawResponse("{ret:0,Table:[{gem_id:341,counts:12},{gem_id:342,counts:3},{gem_id:354,counts:40}]}")
    ])
    client = GatewayClient(58, session, sleep=lambda s: None)
    res = client.call("Common.ashx", 2, {"nid": "1", "_": ""})
    assert isinstance(res, dict)
    assert res["ret"] == 0
    assert len(res["Table"]) == 3
    assert res["Table"][0] == {"gem_id": 341, "counts": 12}


def test_gateway_does_not_retry_non_idempotent_opt6_opt41_opt39_on_network_or_502():
    class FlakyNetSession:
        def __init__(self, exc=None, resp=None):
            self.exc = exc
            self.resp = resp
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            self.calls.append((url, data))
            if self.exc is not None:
                raise self.exc
            return self.resp

    for ep, api_id in (("OPT.ashx", 6), ("OPT.ashx", 41), ("OPT.ashx", 39)):
        s_net = FlakyNetSession(exc=TimeoutError("read timed out"))
        gw_net = GatewayClient(58, s_net, sleep=lambda s: None, max_retries=3)
        assert gw_net.call(ep, api_id, {"tid": "22040"}) is None
        assert len(s_net.calls) == 1

        s_502 = FlakyNetSession(resp=MockRawResponse("502 Bad Gateway", status_code=502))
        gw_502 = GatewayClient(58, s_502, sleep=lambda s: None, max_retries=3)
        assert gw_502.call(ep, api_id, {"tid": "22040"}) is None
        assert len(s_502.calls) == 1

    # Phiên hết hạn (ret=198599) vẫn relogin & gửi lại được bình thường
    s_exp = MockSession([MockRawResponse("{ret:198599}"), MockRawResponse('{"ret": 0}')])
    gw_exp = GatewayClient(58, s_exp, sleep=lambda s: None, relogin_callback=lambda: True)
    assert gw_exp.call("OPT.ashx", 6, {"tid": "22040"}) == {"ret": 0}
    assert len(s_exp.calls) == 2

