import json
import logging
import re
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger("linhvuong.gateway")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

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
    ):
        self.server_id = server_id
        self.session = session
        self._sleep = sleep
        self.max_retries = max_retries
        self.timeout = timeout
        self.relogin_callback = relogin_callback
        self._relogin_lock = threading.Lock()
        self._last_relogin_time = 0.0
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
        """POST tới <endpoint>?id=<api_id>. Retry tuyến tính khi HTTP 503."""
        url = f"{self.base_url}/GateWay/{endpoint}?id={api_id}"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Request: POST {endpoint}?id={api_id} | Data: {data}")

        for attempt in range(self.max_retries):
            try:
                resp = self.session.post(
                    url, data=data, headers=self._headers(), timeout=self.timeout
                )
            except Exception as e:
                logger.warning(
                    f"Lỗi mạng khi gọi {endpoint}?id={api_id} (lần {attempt + 1}/{self.max_retries}): {e}"
                )
                self._sleep(0.5)
                continue

            if resp.status_code == 503:
                logger.warning(
                    f"Máy chủ trả về HTTP 503 cho {endpoint}?id={api_id} (lần {attempt + 1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    self._sleep(0.5 * (attempt + 1))
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
                if self.relogin_callback:
                    with self._relogin_lock:
                        now = time.time()
                        relogin_ok = True
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

                        if relogin_ok:
                            try:
                                retry_resp = self.session.post(
                                    url, data=data, headers=self._headers(), timeout=self.timeout
                                )
                                if retry_resp.status_code == 200:
                                    try:
                                        retry_res = retry_resp.json()
                                    except ValueError:
                                        raw_retry = getattr(retry_resp, "text", "") or ""
                                        m_retry = re.search(r"ret:\s*(\d+)", raw_retry)
                                        retry_res = {"ret": int(m_retry.group(1))} if m_retry else None
                                    if retry_res is not None:
                                        return retry_res
                            except Exception as ex:
                                logger.warning(f"Lỗi khi gửi lại yêu cầu sau relogin: {ex}")
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
