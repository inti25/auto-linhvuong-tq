import json
import logging
import re
import threading
import time
from typing import Any, Callable, Optional

from .auth import USER_AGENT

logger = logging.getLogger("linhvuong.gateway")

RET_SESSION_EXPIRED = 198599


class GatewayClient:
    def __init__(
        self,
        server_id: int,
        session: Any,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
        timeout: float = 30,
        relogin_callback: Optional[Callable[[], bool]] = None,
        proxy_pool: Optional[Any] = None,
        max_failovers: int = 3,
    ):
        self.server_id = server_id
        self.session = session
        self._sleep = sleep
        self.max_retries = max_retries
        self.timeout = timeout
        self.relogin_callback = relogin_callback
        self.proxy_pool = proxy_pool
        self.max_failovers = max(0, int(max_failovers))
        self._relogin_lock = threading.Lock()
        self._proxy_lock = threading.Lock()
        self._last_relogin_time = 0.0
        self._map_cache: dict[int, tuple[float, dict]] = {}
        self._map_cache_lock = threading.Lock()
        self._user_id: Optional[int] = None
        headers_attr = getattr(self.session, "headers", None)
        if headers_attr is not None and hasattr(headers_attr, "update"):
            try:
                headers_attr.update({"User-Agent": USER_AGENT})
            except Exception:
                pass
        self._mount_pool()

    @staticmethod
    def _make_adapter():
        from requests.adapters import HTTPAdapter

        return HTTPAdapter(pool_connections=4, pool_maxsize=32)

    def _mount_pool(self) -> None:
        """Tăng kích thước connection pool để nhiều runner song song không phải tạo lại socket."""
        mount = getattr(self.session, "mount", None)
        if not callable(mount):
            return
        try:
            adapter = self._make_adapter()
            mount("http://", adapter)
            mount("https://", adapter)
        except Exception as e:
            logger.debug(f"Không thể cấu hình connection pool: {e}")

    @property
    def base_url(self) -> str:
        return f"http://sg{self.server_id}.dipan.com"

    def _headers(self, referer: Optional[str] = None) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "text/javascript, text/html, application/xml, text/xml, */*",
            "X-Prototype-Version": "1.5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.base_url,
            "Referer": referer or (self.base_url + "/"),
        }

    def get_user_id(self) -> int:
        """Lấy userId (uid) của tài khoản từ cookie phiên hoặc cache."""
        if self._user_id:
            return self._user_id
        cookies = getattr(self.session, "cookies", None)
        if cookies is not None:
            for name in ("uid", "sg_cur_uid_1"):
                try:
                    raw = cookies.get(name) if hasattr(cookies, "get") else None
                except Exception:
                    raw = None
                if raw is not None and str(raw).isdigit() and int(raw) > 0:
                    self._user_id = int(raw)
                    return self._user_id
        # Fallback khi cookie bị thiếu (ví dụ phiên khôi phục)
        overview = self.rest_get("/api/assistant/overview")
        if isinstance(overview, dict):
            owner_id = overview.get("ownerId")
            if owner_id is not None and str(owner_id).isdigit() and int(owner_id) > 0:
                self._user_id = int(owner_id)
                return self._user_id
        return 0

    @staticmethod
    def _parse_json_body(resp: Any, log_label: str) -> Optional[dict]:
        """Parse JSON từ response, hỗ trợ định dạng không ngoặc kép như {ret:198599}."""
        try:
            return resp.json()
        except ValueError as e:
            raw_sample = getattr(resp, "text", "") or ""
            m = re.search(r"ret:\s*(\d+)", raw_sample)
            if m:
                return {"ret": int(m.group(1))}
            try:
                fixed_json = re.sub(r'([{,])\s*([a-zA-Z_]\w*)\s*:', r'\1"\2":', raw_sample)
                return json.loads(fixed_json)
            except Exception:
                sample = raw_sample[:200]
                logger.warning(
                    f"Không thể parse JSON từ phản hồi {log_label}: {sample} (lỗi: {e})"
                )
                return None

    @staticmethod
    def _unwrap_rest_data(resp: Optional[dict]) -> Optional[dict]:
        """Giải gói trường 'data' của API REST /api/* nếu có, giữ nguyên ret/errMsg."""
        if not isinstance(resp, dict):
            return resp
        if int(resp.get("ret", -1)) == 0 and isinstance(resp.get("data"), dict):
            inner = dict(resp["data"])
            inner.setdefault("ret", 0)
            return inner
        return resp

    def _try_proxy_failover(self) -> bool:
        if not (self.proxy_pool and getattr(self.session, "proxies", None)):
            return False
        logger.warning("Phát hiện sự cố kết nối Proxy/Gateway. Đang kích hoạt Proxy Failover...")
        with self._proxy_lock:
            new_ep = self.proxy_pool.failover(self.session)
        if new_ep:
            logger.info(f"Đã chuyển sang proxy mới: {new_ep.display_name}. Đang thử lại yêu cầu...")
            return True
        return False

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Any = None,
        params: Optional[dict] = None,
        referer: Optional[str] = None,
        log_label: str = "",
        accept_json: bool = False,
    ) -> Optional[dict]:
        """Thực thi HTTP request với retry 502/503/504, proxy failover, HTTP 400 JSON và relogin 198599."""
        headers = self._headers(referer=referer)
        if accept_json:
            headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        if method.upper() == "GET":
            headers.pop("Content-Type", None)

        relogin_attempted = False
        failovers_used = 0
        attempt = 0
        while attempt < self.max_retries:
            attempt += 1
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                else:
                    resp = self.session.post(url, data=data, headers=headers, timeout=self.timeout)
            except Exception as e:
                logger.warning(f"Lỗi mạng khi gọi {log_label} (lần {attempt}/{self.max_retries}): {e}")
                err_str = str(e).lower()
                if (
                    failovers_used < self.max_failovers
                    and any(k in err_str for k in ("proxy", "connect", "timeout", "reset", "refused", "eof"))
                    and self._try_proxy_failover()
                ):
                    failovers_used += 1
                    attempt -= 1
                    self._sleep(0.5)
                    continue
                self._sleep(0.5)
                continue

            if resp.status_code in (502, 504) and failovers_used < self.max_failovers:
                if self._try_proxy_failover():
                    failovers_used += 1
                    attempt -= 1
                    self._sleep(0.5)
                    continue

            if resp.status_code in (502, 503, 504):
                logger.warning(
                    f"Máy chủ trả về HTTP {resp.status_code} cho {log_label} (lần {attempt}/{self.max_retries})"
                )
                if attempt < self.max_retries:
                    self._sleep(0.5 * attempt)
                continue

            if resp.status_code not in (200, 400):
                raw_sample = getattr(resp, "text", "")
                sample = raw_sample[:200] if raw_sample else ""
                logger.warning(f"Máy chủ trả về HTTP {resp.status_code} cho {log_label}: {sample}")
                return None

            result = self._parse_json_body(resp, log_label)
            if resp.status_code == 400:
                if not isinstance(result, dict):
                    return None
                # HTTP 400 JSON từ Server 58 (vd ret=8105, 8599, 8601) giữ nguyên để caller xử lý
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"HTTP 400 JSON từ {log_label}: {result}")
                return result

            if isinstance(result, dict) and result.get("ret") == RET_SESSION_EXPIRED:
                logger.warning(f"Phiên đăng nhập đã hết hạn (mã ret={RET_SESSION_EXPIRED}) khi gọi {log_label}.")
                if self.relogin_callback and not relogin_attempted:
                    relogin_attempted = True
                    relogin_ok = False
                    with self._relogin_lock:
                        now = time.time()
                        if now - self._last_relogin_time > 3.0:
                            logger.info("Đang thử đăng nhập lại tài khoản...")
                            try:
                                relogin_ok = bool(self.relogin_callback())
                                if relogin_ok:
                                    self._last_relogin_time = time.time()
                                    self._user_id = None
                                    logger.info("Đăng nhập lại thành công! Đang gửi lại yêu cầu...")
                                else:
                                    logger.error("Đăng nhập lại thất bại.")
                            except Exception as ex:
                                logger.error(f"Lỗi khi thực hiện đăng nhập lại: {ex}")
                                relogin_ok = False
                        else:
                            logger.info("Phiên vừa được làm mới bởi luồng khác. Đang gửi lại yêu cầu...")
                            self._user_id = None
                            relogin_ok = True

                    if relogin_ok:
                        attempt -= 1
                        self._sleep(0.5)
                        continue
                return result

            if isinstance(result, dict):
                ret = result.get("ret")
                if ret is not None and ret != 0:
                    if log_label.startswith("OPT.ashx?id=63") and ret == 86:
                        logger.info("Phần thưởng chuyên cần đã được nhận hôm nay (mã ret=86).")
                    else:
                        err_msg = result.get("errMsg")
                        extra = f" ({err_msg})" if err_msg else ""
                        logger.warning(
                            f"Máy chủ trả về mã lỗi ret={ret}{extra} cho {log_label} | Data: {data or params} | Response: {result}"
                        )
                elif logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Response {log_label}: {result}")
            return result

        logger.error(f"Thất bại hoàn toàn sau {self.max_retries} lần gọi {log_label}")
        return None

    def call(
        self,
        endpoint: str,
        api_id: int,
        data: Any,
        referer: Optional[str] = None,
        query_suffix: Optional[str] = None,
    ) -> Optional[dict]:
        """POST tới /GateWay/<endpoint>?id=<api_id>."""
        url = f"{self.base_url}/GateWay/{endpoint}?id={api_id}"
        if query_suffix:
            url = f"{url}&{query_suffix}"
        log_label = f"{endpoint}?id={api_id}"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Request: POST {log_label} | Data: {data}")
        return self._request("POST", url, data=data, referer=referer, log_label=log_label)

    def rest_get(
        self,
        path: str,
        params: Optional[dict] = None,
        referer: Optional[str] = None,
    ) -> Optional[dict]:
        """GET tới endpoint REST /api/* của Server 58."""
        url = f"{self.base_url}{path}"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Request: GET {path} | Params: {params}")
        return self._request(
            "GET", url, params=params, referer=referer, log_label=f"GET {path}", accept_json=True
        )

    def rest_post(
        self,
        path: str,
        data: Optional[dict] = None,
        referer: Optional[str] = None,
    ) -> Optional[dict]:
        """POST tới endpoint REST /api/* của Server 58."""
        url = f"{self.base_url}{path}"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Request: POST {path} | Data: {data}")
        return self._request(
            "POST", url, data=data, referer=referer, log_label=f"POST {path}", accept_json=True
        )

    def optimization(
        self,
        action: str,
        data: Optional[dict] = None,
        referer: Optional[str] = None,
    ) -> Optional[dict]:
        """POST tới /GateWay/Optimization.ashx?action=<action> (mở rương lô, phân trang trang bị)."""
        url = f"{self.base_url}/GateWay/Optimization.ashx?action={action}"
        log_label = f"Optimization.ashx?action={action}"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Request: POST {log_label} | Data: {data}")
        return self._request(
            "POST", url, data=data or {}, referer=referer, log_label=log_label, accept_json=True
        )

    def city_list(self) -> Optional[dict]:
        """GET /api/city/list?userId=<uid>."""
        return self.rest_get("/api/city/list", {"userId": self.get_user_id()})

    def city_info(self, city_id: int) -> Optional[dict]:
        """GET /api/city/info?userId=<uid>&cityId=<city_id> -> giải gói data."""
        resp = self.rest_get("/api/city/info", {"userId": self.get_user_id(), "cityId": int(city_id)})
        return self._unwrap_rest_data(resp)

    def resource_info(self, city_id: int) -> Optional[dict]:
        """GET /api/resource/info?userId=<uid>&cityTentId=<city_id> -> giải gói data."""
        resp = self.rest_get("/api/resource/info", {"userId": self.get_user_id(), "cityTentId": int(city_id)})
        return self._unwrap_rest_data(resp)

    def building_list(self, city_id: int) -> Optional[dict]:
        """GET /api/building/list?userId=<uid>&cityTentId=<city_id> -> giải gói data."""
        resp = self.rest_get("/api/building/list", {"userId": self.get_user_id(), "cityTentId": int(city_id)})
        return self._unwrap_rest_data(resp)

    def set_current_city(self, city_id: int) -> Optional[dict]:
        """POST /api/city/current (thay thế City.ashx?id=50)."""
        return self.rest_post("/api/city/current", {"cityTentId": str(int(city_id))})

    def update_building(self, city_id: int, pid: int, gid: int, opt_type: int = 1) -> Optional[dict]:
        """POST /api/building/update (thay thế OPT.ashx?id=65)."""
        return self.rest_post(
            "/api/building/update",
            {
                "userId": str(self.get_user_id()),
                "cityTentId": str(int(city_id)),
                "posId": str(int(pid)),
                "gid": str(int(gid)),
                "type": str(int(opt_type)),
            },
        )

    def page_building(self, city_id: int) -> Optional[dict]:
        """GET /api/city/pagebuilding (thay thế Common.ashx?id=77)."""
        resp = self.rest_get("/api/city/pagebuilding", {"userId": self.get_user_id(), "cityTentId": int(city_id)})
        return self._unwrap_rest_data(resp)

    def page_official(self, hero_type: int = 2) -> Optional[dict]:
        """GET /api/city/pageofficial (thay thế Common.ashx?id=32)."""
        resp = self.rest_get("/api/city/pageofficial", {"userId": self.get_user_id(), "heroType": int(hero_type)})
        return self._unwrap_rest_data(resp)

    def page_mytroops_list(self, city_id: int) -> Optional[dict]:
        """GET /api/city/pagemytroopslist (thay thế Common.ashx?id=76)."""
        resp = self.rest_get("/api/city/pagemytroopslist", {"userId": self.get_user_id(), "cityTentId": int(city_id)})
        return self._unwrap_rest_data(resp)

    def page_armament(self) -> Optional[dict]:
        """GET /api/city/pagearmament (thay thế Common.ashx?id=27)."""
        resp = self.rest_get("/api/city/pagearmament", {"userId": self.get_user_id()})
        return self._unwrap_rest_data(resp)

    def notify_history(self) -> Optional[dict]:
        """GET /api/notify/history (kênh thông báo hệ thống Server 58)."""
        return self.rest_get("/api/notify/history")

    def invalidate_map_cache(self, mid: Optional[int] = None) -> None:
        """Xóa cache /api/map/query cho một mid hoặc toàn bộ bản đồ."""
        with self._map_cache_lock:
            if mid is None:
                self._map_cache.clear()
            else:
                self._map_cache.pop(int(mid), None)

    def map_view(self, mid: int, cache_ttl: float = 0.0) -> Optional[dict]:
        """GET /api/map/query: các thực thể quanh một Mid. Có hỗ trợ TTL cache chia sẻ giữa các runner."""
        mid_int = int(mid)
        if cache_ttl > 0:
            now = time.monotonic()
            with self._map_cache_lock:
                entry = self._map_cache.get(mid_int)
                if entry is not None and (now - entry[0]) < cache_ttl:
                    return entry[1]

        data = self.rest_get("/api/map/query", {"userId": self.get_user_id(), "mid": mid_int})
        if cache_ttl > 0 and data is not None:
            now = time.monotonic()
            with self._map_cache_lock:
                if len(self._map_cache) > 1000:
                    expired = [k for k, (ts, _) in self._map_cache.items() if (now - ts) >= cache_ttl]
                    for k in expired:
                        self._map_cache.pop(k, None)
                    if len(self._map_cache) > 1000:
                        self._map_cache.clear()
                self._map_cache[mid_int] = (now, data)
        return data
