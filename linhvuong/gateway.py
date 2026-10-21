"""Client HTTP cho Gateway của server game (sg<id>.dipan.com/GateWay)."""

import time
from typing import Any, Callable, Optional

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class GatewayClient:
    def __init__(
        self,
        server_id: int,
        session: Any,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
        timeout: float = 30,
    ):
        self.server_id = server_id
        self.session = session
        self._sleep = sleep
        self.max_retries = max_retries
        self.timeout = timeout

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
        for attempt in range(self.max_retries):
            try:
                resp = self.session.post(
                    url, data=data, headers=self._headers(), timeout=self.timeout
                )
            except Exception:
                self._sleep(0.5)
                continue
            if resp.status_code == 503:
                if attempt < self.max_retries - 1:
                    self._sleep(0.5 * (attempt + 1))
                continue
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    return None
            return None
        return None

    def map_view(self, mid: int) -> Optional[dict]:
        """Map.ashx?id=6: các thực thể quanh một Mid."""
        return self.call("Map.ashx", 6, {"mid": str(mid), "_": ""})
