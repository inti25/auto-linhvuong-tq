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
    ):
        self.server_id = server_id
        self.session = session
        self._sleep = sleep
        self.max_retries = max_retries
        self.timeout = timeout
        self.relogin_callback = relogin_callback
        self.proxy_pool = proxy_pool
        self._relogin_lock = threading.Lock()
        self._last_relogin_time = 0.0
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

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "text/javascript, text/html, application/xml, text/xml, */*",
            "X-Prototype-Version": "1.5.0",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.base_url,
            "Referer": self.base_url + "/",
        }

    def call(self, endpoint: str, api_id: int, data: dict[str, Any]) -> Optional[dict]:
        """POST tới <endpoint>?id=<api_id>. Retry tuyến tính khi HTTP 502/503/504."""
        url = f"{self.base_url}/GateWay/{endpoint}?id={api_id}"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Request: POST {endpoint}?id={api_id} | Data: {data}")

        relogin_attempted = False
        attempt = 0
        while attempt < self.max_retries:
            attempt += 1
            try:
                resp = self.session.post(
                    url, data=data, headers=self._headers(), timeout=self.timeout
                )
            except Exception as e:
                logger.warning(
                    f"Lỗi mạng khi gọi {endpoint}?id={api_id} (lần {attempt}/{self.max_retries}): {e}"
                )
                if self.proxy_pool and getattr(self.session, "proxies", None):
                    err_str = str(e).lower()
                    if any(k in err_str for k in ("proxy", "connect", "timeout", "reset", "refused", "eof")):
                        logger.info("Phát hiện sự cố kết nối Proxy. Đang kích hoạt Proxy Failover...")
                        new_ep = self.proxy_pool.failover(self.session)
                        if new_ep:
                            logger.info(f"Đã chuyển sang proxy mới: {new_ep.display_name}. Đang thử lại yêu cầu...")
                            attempt -= 1
                            self._sleep(0.5)
                            continue
                self._sleep(0.5)
                continue

            if resp.status_code in (502, 504):
                if self.proxy_pool and getattr(self.session, "proxies", None):
                    logger.warning(f"Máy chủ/Proxy trả về HTTP {resp.status_code}. Đang kích hoạt Proxy Failover...")
                    new_ep = self.proxy_pool.failover(self.session)
                    if new_ep:
                        logger.info(f"Đã chuyển sang proxy mới: {new_ep.display_name}. Đang thử lại yêu cầu...")
                        attempt -= 1
                        self._sleep(0.5)
                        continue

            if resp.status_code in (502, 503, 504):
                logger.warning(
                    f"Máy chủ trả về HTTP {resp.status_code} cho {endpoint}?id={api_id} (lần {attempt}/{self.max_retries})"
                )
                if attempt < self.max_retries:
                    self._sleep(0.5 * attempt)
                continue

            if resp.status_code != 200:
                raw_sample = getattr(resp, "text", "")
                sample = raw_sample[:200] if raw_sample else ""
                logger.warning(
                    f"Máy chủ trả về HTTP {resp.status_code} cho {endpoint}?id={api_id}: {sample}"
                )
                return None

            try:
                result = resp.json()
            except ValueError as e:
                raw_sample = getattr(resp, "text", "") or ""
                # Hỗ trợ định dạng JSON không chuẩn từ server game (e.g. {ret:198599})
                m = re.search(r"ret:\s*(\d+)", raw_sample)
                if m:
                    result = {"ret": int(m.group(1))}
                else:
                    try:
                        fixed_json = re.sub(r'([{,])\s*([a-zA-Z_]\w*)\s*:', r'\1"\2":', raw_sample)
                        result = json.loads(fixed_json)
                    except Exception:
                        sample = raw_sample[:200]
                        logger.warning(
                            f"Không thể parse JSON từ phản hồi {endpoint}?id={api_id}: {sample} (lỗi: {e})"
                        )
                        return None

            # Xử lý phiên hết hạn (ret=198599): tự động đăng nhập lại và gửi lại yêu cầu
            if isinstance(result, dict) and result.get("ret") == RET_SESSION_EXPIRED:
                logger.warning(
                    f"Phiên đăng nhập đã hết hạn (mã ret={RET_SESSION_EXPIRED}) khi gọi {endpoint}?id={api_id}."
                )
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
                                    logger.info("Đăng nhập lại thành công! Đang gửi lại yêu cầu...")
                                else:
                                    logger.error("Đăng nhập lại thất bại.")
                            except Exception as ex:
                                logger.error(f"Lỗi khi thực hiện đăng nhập lại: {ex}")
                                relogin_ok = False
                        else:
                            logger.info("Phiên vừa được làm mới bởi luồng khác. Đang gửi lại yêu cầu...")
                            relogin_ok = True

                    if relogin_ok:
                        # Thử lại yêu cầu với phiên mới đã được làm mới
                        attempt -= 1
                        self._sleep(0.5)
                        continue
                return result

            # Kiểm tra mã ret từ game server
            if isinstance(result, dict):
                ret = result.get("ret")
                if ret is not None and ret != 0:
                    if endpoint == "OPT.ashx" and api_id == 63 and ret == 86:
                        logger.info(f"Phần thưởng chuyên cần đã được nhận hôm nay (mã ret=86).")
                    else:
                        logger.warning(
                            f"Máy chủ trả về mã lỗi ret={ret} cho {endpoint}?id={api_id} | Data: {data} | Response: {result}"
                        )
                elif logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Response {endpoint}?id={api_id}: {result}")
            return result

        logger.error(
            f"Thất bại hoàn toàn sau {self.max_retries} lần gọi {endpoint}?id={api_id} | Data: {data}"
        )
        return None

    def map_view(self, mid: int) -> Optional[dict]:
        """Map.ashx?id=6: các thực thể quanh một Mid."""
        return self.call("Map.ashx", 6, {"mid": str(mid), "_": ""})
