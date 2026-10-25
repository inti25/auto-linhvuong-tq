"""Nhiệm vụ Logistics Hậu Cần & Điều Chuyển Binh Lực Liên Thành.

Reverse engineered chính xác từ ZBuild.exe:
- Chuyển quân liên thành:
  1. Kiểm tra số lượng quân đồn trú tại thành xuất phát: Common.ashx?id=16 (tid: from_city_id).
  2. Điều chuyển binh lực sang thành đích: OPT.ashx?id=52 (dest, tid, gid, gamount, times=1, Food=0, Wood=0, Stone=0, Iron=0, Money=0).
- An Dân toàn bộ các thành:
  1. Kiểm tra độ sĩ khí/lòng dân: City.ashx?id=6 (tid: city_id).
  2. An dân khôi phục sĩ khí nếu < 90%: OPT.ashx?id=4 (lType=1: Tế Trời, tid).
- Nhận thưởng chuyên cần hằng ngày: OPT.ashx?id=63.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from ..gateway import GatewayClient
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired


@dataclass
class ArmyTransferOrder:
    from_city_id: int
    to_city_id: int
    army_id: int  # 1: Bộ binh, 2: Kỵ binh, 3: Cung binh
    amount: int


class LogisticsTask:
    def __init__(
        self,
        gateway: GatewayClient,
        transfer_orders: Optional[list[ArmyTransferOrder]] = None,
        monitored_city_ids: Optional[list[int]] = None,
        auto_comfort: bool = True,
        auto_daily_reward: bool = True,
        notify: Callable[[str], None] = print,
    ):
        self.gateway = gateway
        self.transfer_orders = transfer_orders or []
        self.monitored_city_ids = monitored_city_ids or []
        self.auto_comfort = auto_comfort
        self.auto_daily_reward = auto_daily_reward
        self.notify = notify

    def get_garrison_troops(self, city_id: int) -> dict[int, int]:
        """Lấy số lượng quân đồn trú trong thành qua Common.ashx?id=16: {army_id: count}."""
        resp = self.gateway.call("Common.ashx", 16, {"tid": str(city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        troops_map = {}
        for item in resp.get("list", []):
            if isinstance(item, dict):
                gid = int(item.get("gid", 0))
                count = int(item.get("count", 0))
                troops_map[gid] = count
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                try:
                    troops_map[int(item[0])] = int(item[2])
                except (ValueError, TypeError):
                    pass
        return troops_map

    def transfer_army(self, order: ArmyTransferOrder) -> bool:
        """Thực hiện chuyển quân từ thành này sang thành khác qua OPT.ashx?id=52."""
        payload = {
            "dest": str(order.to_city_id),
            "tid": str(order.from_city_id),
            "gid": str(order.army_id),
            "gamount": str(order.amount),
            "times": "1",
            "Food": "0",
            "Wood": "0",
            "Stone": "0",
            "Iron": "0",
            "Money": "0",
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 52, payload) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        if ret == RET_OK:
            self.notify(f"🚚 Đã chuyển {order.amount} quân (loại {order.army_id}) từ Thành {order.from_city_id} -> {order.to_city_id}")
            return True
        return False

    def comfort_city_if_needed(self, city_id: int) -> bool:
        """Kiểm tra và An Dân nếu sĩ khí thành tụt xuống dưới 90%."""
        resp = self.gateway.call("City.ashx", 6, {"tid": str(city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        data = resp.get("data", {})
        morale = int(data.get("morale", 100))
        anger = int(data.get("anger", 0))

        if morale < 90 or anger > 0:
            self.notify(f"🕊️ Sĩ khí Thành {city_id} tụt ({morale}%), tiến hành An Dân...")
            c_resp = self.gateway.call("OPT.ashx", 4, {"lType": "1", "tid": str(city_id), "_": ""}) or {}
            return c_resp.get("ret", RET_OK) == RET_OK
        return True

    def claim_daily_reward(self) -> bool:
        """Nhận điểm danh / phần thưởng hằng ngày qua OPT.ashx?id=63."""
        resp = self.gateway.call("OPT.ashx", 63, {"_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            self.notify("⚠️ Nhận thưởng chuyên cần: Máy chủ yêu cầu mã Captcha!")
            raise CaptchaRequired()
        if ret == RET_OK:
            self.notify("🎁 Nhận phần thưởng chuyên cần hằng ngày thành công!")
            return True
        elif ret == 86:
            self.notify("ℹ️ Hôm nay bạn đã nhận thưởng chuyên cần rồi (mã 86: đã nhận trong ngày).")
            return True
        else:
            self.notify(f"❌ Nhận thưởng chuyên cần thất bại (mã phản hồi từ máy chủ: {ret})")
            return False

    def run_once(self) -> str:
        # 1. Nhận điểm danh hằng ngày
        if self.auto_daily_reward:
            self.claim_daily_reward()

        # 2. An Dân cho các thành trong danh sách giám sát
        if self.auto_comfort:
            for cid in self.monitored_city_ids:
                self.comfort_city_if_needed(cid)

        # 3. Thực hiện các lệnh chuyển quân liên thành
        transferred_count = 0
        for order in self.transfer_orders:
            garrison = self.get_garrison_troops(order.from_city_id)
            available = garrison.get(order.army_id, 0)
            if available >= order.amount:
                if self.transfer_army(order):
                    transferred_count += 1
            else:
                self.notify(f"⚠️ Thành {order.from_city_id} không đủ quân loại {order.army_id} để chuyển ({available}/{order.amount})")

        return f"transferred:{transferred_count}" if self.transfer_orders else "logistics_idle"
