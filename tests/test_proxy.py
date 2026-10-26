from unittest.mock import MagicMock, patch
import pytest
import requests

from linhvuong.gateway import GatewayClient
from linhvuong.proxy import ProxyEndpoint, ProxyPool


def test_proxy_endpoint_from_line_lenient_parsing():
    # 1. ip:port:username:password (mặc định socks5h)
    ep1 = ProxyEndpoint.from_line("103.151.123.45:8080:myuser:mypass")
    assert ep1 is not None
    assert ep1.host == "103.151.123.45"
    assert ep1.port == 8080
    assert ep1.username == "myuser"
    assert ep1.password == "mypass"
    assert ep1.protocol == "socks5h"
    assert ep1.explicit_protocol is False
    assert ep1.url == "socks5h://myuser:mypass@103.151.123.45:8080"
    assert ep1.display_name == "socks5h://myuser@103.151.123.45:8080"

    # 2. ip:port với default_protocol="http"
    ep2 = ProxyEndpoint.from_line("1.2.3.4:3128", default_protocol="http")
    assert ep2 is not None
    assert ep2.host == "1.2.3.4"
    assert ep2.port == 3128
    assert ep2.username is None
    assert ep2.protocol == "http"
    assert ep2.explicit_protocol is False
    assert ep2.url == "http://1.2.3.4:3128"

    # 3. socks5://ip:port:user:pass -> socks5h:// (explicit_protocol=True)
    ep3 = ProxyEndpoint.from_line("socks5://192.168.1.1:1080:usr:pwd")
    assert ep3 is not None
    assert ep3.protocol == "socks5h"
    assert ep3.explicit_protocol is True
    assert ep3.url == "socks5h://usr:pwd@192.168.1.1:1080"

    # 4. user:pass@host:port (explicit_protocol=True)
    ep4 = ProxyEndpoint.from_line("http://admin:secret@45.1.2.3:8000")
    assert ep4 is not None
    assert ep4.username == "admin"
    assert ep4.password == "secret"
    assert ep4.host == "45.1.2.3"
    assert ep4.port == 8000
    assert ep4.protocol == "http"
    assert ep4.explicit_protocol is True

    # 5. Dòng trống, comment, dữ liệu rác
    assert ProxyEndpoint.from_line("") is None
    assert ProxyEndpoint.from_line("   \n") is None
    assert ProxyEndpoint.from_line("# this is comment") is None
    assert ProxyEndpoint.from_line("invalid_line_without_port") is None
    assert ProxyEndpoint.from_line("1.2.3.4:not_a_port") is None


def test_proxy_pool_load_from_text():
    raw_text = """
    # Proxy list
    103.151.123.45:8080:user1:pass1

    103.151.123.46:8080:user2:pass2
    103.151.123.47:8080
    """
    pool = ProxyPool()
    count = pool.load_from_text(raw_text)
    assert count == 3
    assert len(pool.endpoints) == 3
    assert pool.endpoints[0].host == "103.151.123.45"
    assert pool.endpoints[1].host == "103.151.123.46"
    assert pool.endpoints[2].host == "103.151.123.47"


def test_proxy_pool_fetch_from_url():
    pool = ProxyPool(url="http://my-proxy-provider.com/list.txt")
    mock_resp = MagicMock()
    mock_resp.text = "10.0.0.1:8080:u1:p1\n10.0.0.2:8080:u2:p2"
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        count = pool.fetch_from_url()
        assert count == 2
        assert len(pool.endpoints) == 2
        mock_get.assert_called_once()


def test_proxy_pool_check_endpoint():
    pool = ProxyPool()
    ep = ProxyEndpoint(host="1.1.1.1", port=8080)

    # Success case (status 200)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.head", return_value=mock_resp):
        ok = pool.check_endpoint(ep)
        assert ok is True
        assert ep.is_alive is True
        assert ep.latency >= 0.0

    # Failure case (exception)
    with patch("requests.head", side_effect=requests.exceptions.ConnectTimeout("Timeout")):
        ok = pool.check_endpoint(ep)
        assert ok is False
        assert ep.is_alive is False
        assert ep.latency == 999.0


def test_proxy_pool_check_all_sorts_by_latency():
    ep1 = ProxyEndpoint(host="1.1.1.1", port=8080)
    ep2 = ProxyEndpoint(host="2.2.2.2", port=8080)
    ep3 = ProxyEndpoint(host="3.3.3.3", port=8080)
    pool = ProxyPool(endpoints=[ep1, ep2, ep3])

    def mock_check(ep, *args, **kwargs):
        if ep.host == "1.1.1.1":
            ep.is_alive = True
            ep.latency = 0.8
            return True
        elif ep.host == "2.2.2.2":
            ep.is_alive = True
            ep.latency = 0.2
            return True
        else:
            ep.is_alive = False
            ep.latency = 999.0
            return False

    with patch.object(pool, "check_endpoint", side_effect=mock_check):
        alive = pool.check_all()
        assert len(alive) == 2
        # ep2 (0.2s) phải xếp trước ep1 (0.8s)
        assert alive[0].host == "2.2.2.2"
        assert alive[1].host == "1.1.1.1"
        assert pool.get_active() == alive[0]


def test_proxy_pool_failover_and_auto_refetch():
    ep1 = ProxyEndpoint(host="1.1.1.1", port=8080, is_alive=True)
    ep2 = ProxyEndpoint(host="2.2.2.2", port=8080, is_alive=True)
    pool = ProxyPool(url="http://provider.com/api", endpoints=[ep1, ep2])
    sess = requests.Session()
    pool.apply_to_session(sess)
    assert sess.proxies["http"] == ep1.url

    # 1. Failover lần 1: ep1 chết -> đổi sang ep2
    new_ep = pool.failover(sess)
    assert new_ep == ep2
    assert ep1.is_alive is False
    assert sess.proxies["http"] == ep2.url

    # 2. Failover lần 2: ep2 chết -> hết proxy sống -> auto-refetch từ URL
    mock_resp = MagicMock()
    mock_resp.text = "4.4.4.4:8080:u4:p4"
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp), patch.object(
        pool, "check_endpoint", side_effect=lambda ep, *args, **kwargs: setattr(ep, "is_alive", True) or True
    ):
        refetched_ep = pool.failover(sess)
        assert refetched_ep is not None
        assert refetched_ep.host == "4.4.4.4"
        assert sess.proxies["http"] == refetched_ep.url


def test_gateway_triggers_proxy_failover_on_proxy_error():
    ep1 = ProxyEndpoint(host="1.1.1.1", port=8080, is_alive=True)
    ep2 = ProxyEndpoint(host="2.2.2.2", port=8080, is_alive=True)
    pool = ProxyPool(endpoints=[ep1, ep2])

    class MockResp:
        status_code = 200

        def json(self):
            return {"ret": 0, "msg": "success_via_new_proxy"}

    class MockFailingSession:
        def __init__(self):
            self.proxies = {"http": ep1.url}
            self.call_count = 0

        def post(self, url, *args, **kwargs):
            self.call_count += 1
            if self.call_count == 1:
                raise requests.exceptions.ProxyError("Cannot connect to proxy 1.1.1.1:8080")
            return MockResp()

    sess = MockFailingSession()
    client = GatewayClient(53, sess, sleep=lambda s: None, proxy_pool=pool)

    res = client.call("OPT.ashx", 53, {"pid": "1"})

    # Phải tự động đổi sang ep2 và thành công ở lần gọi thứ 2
    assert res is not None
    assert res.get("ret") == 0
    assert res.get("msg") == "success_via_new_proxy"
    assert sess.call_count == 2
    assert ep1.is_alive is False
    assert sess.proxies["http"] == ep2.url


def test_proxy_pool_check_endpoint_rejects_403_and_auto_falls_back():
    pool = ProxyPool()
    # Endpoint không có scheme cứng, ban đầu protocol="http"
    ep = ProxyEndpoint.from_line("45.38.107.97:6014:user:pass", default_protocol="http")
    assert ep.protocol == "http"
    assert ep.explicit_protocol is False

    # Giả lập: khi requests.head gọi với http:// thì trả về 403 (bị proxy chặn)
    # khi gọi với socks5h:// thì trả về 302 (thành công)
    def mock_head(url, proxies=None, **kwargs):
        resp = MagicMock()
        if proxies and "http" in proxies and proxies["http"].startswith("http://"):
            resp.status_code = 403
            return resp
        elif proxies and "http" in proxies and proxies["http"].startswith("socks5h://"):
            resp.status_code = 302
            return resp
        resp.status_code = 500
        return resp

    with patch("requests.head", side_effect=mock_head):
        ok = pool.check_endpoint(ep)
        assert ok is True
        assert ep.is_alive is True
        # Tự động chuyển giao thức sang socks5h!
        assert ep.protocol == "socks5h"
        assert ep.url.startswith("socks5h://")


def test_auth_login_handles_proxy_403_forbidden():
    from linhvuong.auth import LoginError, login

    sess = requests.Session()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "You are forbidden to connect to client_connect_invalid_ip"

    with patch.object(sess, "post", return_value=mock_resp):
        with pytest.raises(LoginError) as exc_info:
            login(sess, 57, "testuser", "testpass", proxy="http://proxy:8080")
        assert "Proxy từ chối kết nối (HTTP 403)" in str(exc_info.value)
        assert "client_connect_invalid_ip" in str(exc_info.value)
