"""Biên Chế Quân Tự Động & Luyện Sĩ Khí dùng chung.

Trích xuất logic miền tập trung từ Thảo Phạt, phục vụ dùng chung cho:
- Thảo Phạt (ThaoPhatExecutor)
- Gọi Man (GoiDan / GoiMan)
- Bình Man (BinhMan)
- Giao diện Dashboard (Biên chế tức thời)
"""

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .gateway import GatewayClient
from .roster import Army

logger = logging.getLogger("linhvuong.troops")

ERROR_MESSAGES = {
    0: "Thành công",
    1: "Thao tác thất bại, vui lòng thử lại sau",
    6: "Quân số không đủ",
    7: "Sỹ khí không đủ",
    8: "Đang trong thời gian chờ",
    20: "Tướng đang không ở trong thành (hoặc đang bận)",
    31: "Tướng không cần trị thương",
    32: "Tài nguyên không đủ",
    33: "Đồng không đủ",
    34: "Dân số rảnh rỗi không đủ",
    35: "Thành không có tướng khả dụng",
    40: "Tướng đang bận (không ở trong thành)",
    53: "Tân binh không đủ để biên chế",
    55: "Đang trong thời gian chờ an dân",
    78: "Trong thời gian đóng băng không thể xuất binh",
    79: "Tướng đang làm nhiệm vụ chưa về",
    10032: "Tướng không có trong thành",
    10033: "Mưu sĩ không tồn tại trong thành",
    10034: "Tướng không tồn tại trong thành",
    10035: "Tướng đang bận",
    10036: "Tướng bị thương",
    10037: "Mưu sĩ đã được gán cho tướng khác",
    10038: "Quân số không đủ",
    10039: "Sỹ khí không đủ",
    10040: "Đang trong thời gian chờ",
}


@dataclass
class TargetArmy:
    infantry: int = 0
    cavalry: int = 0
    archers: int = 0
    bo_binh: Optional[int] = None
    ky_binh: Optional[int] = None
    cung_binh: Optional[int] = None

    def __post_init__(self):
        if self.bo_binh is not None and self.infantry == 0:
            self.infantry = self.bo_binh
        if self.ky_binh is not None and self.cavalry == 0:
            self.cavalry = self.ky_binh
        if self.cung_binh is not None and self.archers == 0:
            self.archers = self.cung_binh

    @property
    def total(self) -> int:
        return self.infantry + self.cavalry + self.archers


class ArmyProvisioner:
    """Dịch vụ điều phối kiểm tra kho, chiêu mộ tân binh, biên chế lính và luyện sĩ khí."""

    def __init__(self, gateway: GatewayClient, sleep_fn: Callable[[float], None] = time.sleep):
        self.gateway = gateway
        self.sleep_fn = sleep_fn

    def check_recruits(self, city_id: int) -> Optional[int]:
        """Kiểm tra số lượng tân binh có sẵn trong kho của thành từ API Common.ashx?id=27."""
        resp = self.gateway.call("Common.ashx", 27, {"_": ""}) or {}
        if resp.get("ret") == 0:
            for city_data in resp.get("list", []):
                if isinstance(city_data, list) and len(city_data) > 2:
                    try:
                        if int(city_data[0]) == int(city_id):
                            return int(city_data[2])
                    except (ValueError, TypeError):
                        continue
        return None

    def comfort_population(self, city_id: int, ltype: int = 4) -> tuple[bool, int]:
        """Gọi API an dân / tăng nhân khẩu (OPT.ashx?id=4). lType=4: Tăng nhân khẩu."""
        payload = {
            "lType": str(ltype),
            "tid": str(city_id),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 4, payload) or {}
        ret = resp.get("ret", -1)
        return ret == 0, ret

    def buy_recruits(
        self,
        city_id: int,
        amount: int,
        auto_comfort: bool = True,
    ) -> tuple[bool, int]:
        """Chiêu mộ tân binh bằng API OPT.ashx?id=41."""
        if amount <= 0:
            return True, 0

        payload = {
            "lAmount": str(amount),
            "tid": str(city_id),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 41, payload) or {}
        ret = resp.get("ret", -1)

        if ret == 34 and auto_comfort:
            self.comfort_population(city_id, ltype=4)
            self.sleep_fn(1.0)
            resp = self.gateway.call("OPT.ashx", 41, payload) or {}
            ret = resp.get("ret", -1)

        return ret == 0, ret

    def heal_general(self, base_id: int, general_id: int) -> tuple[bool, int]:
        """Trị thương cho danh tướng bằng API OPT.ashx?id=31."""
        payload = {
            "lCityTentID": str(base_id),
            "lGeneralID": str(general_id),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 31, payload) or {}
        ret = resp.get("ret", -1)
        return ret in (0, 31), ret

    def adjust_troops(
        self,
        base_id: int,
        general_id: int,
        current_army: Optional[Army],
        target_army: TargetArmy,
        auto_recruit: bool = True,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> list[tuple[int, int, bool, int]]:
        """Thiết lập biên chế quân cho tướng bằng API OPT.ashx?id=6.

        Chỉ bổ sung phần thiếu hụt (diff > 0), không tháo phần quân vượt mức (diff <= 0).
        Nếu thiếu tân binh (ret=53) và base_id > 0 (Thành) và auto_recruit=True:
            Tự động chiêu mộ tân binh (API id=41) và thử lại biên chế.
        """
        current_inf = current_army.infantry if current_army else 0
        current_cav = current_army.cavalry if current_army else 0
        current_arc = current_army.archers if current_army else 0

        adjustments = [
            (1, target_army.infantry - current_inf),
            (2, target_army.cavalry - current_cav),
            (3, target_army.archers - current_arc),
        ]

        results = []
        for soldier_type, diff in adjustments:
            if diff <= 0:
                continue
            payload = {
                "lGeneralID": str(general_id),
                "lSoldierType": str(soldier_type),
                "lAmount": str(diff),
                "tid": str(base_id),
                "_": "",
            }
            resp = self.gateway.call("OPT.ashx", 6, payload) or {}
            ret = resp.get("ret", -1)

            # Nếu tân binh không đủ để biên chế (ret=53) và căn cứ là Thành (ID > 0)
            if ret == 53 and auto_recruit and int(base_id) > 0:
                tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(soldier_type, "Quân")
                if on_log:
                    on_log(f"   [Chiêu mộ] Tân binh không đủ để bổ sung {tname} +{diff}, tự động chiêu mộ...")
                buy_succ, buy_ret = self.buy_recruits(int(base_id), diff)
                if buy_succ:
                    if on_log:
                        on_log(f"   [Chiêu mộ] ✅ Chiêu mộ thành công {diff} tân binh, tiếp tục biên chế...")
                    resp = self.gateway.call("OPT.ashx", 6, payload) or {}
                    ret = resp.get("ret", -1)
                else:
                    err_desc = ERROR_MESSAGES.get(buy_ret, f"Mã lỗi: {buy_ret}")
                    if on_log:
                        on_log(f"   [Chiêu mộ] ❌ Chiêu mộ thất bại ({err_desc})")

            results.append((soldier_type, diff, ret == 0, ret))
        return results

    def adjust_morale(
        self,
        base_id: int,
        general_id: int,
        current_morale: int,
        min_morale: int = 95,
    ) -> tuple[bool, int]:
        """Nâng sỹ khí cho tướng nếu sỹ khí hiện tại < min_morale bằng API id=47."""
        if current_morale >= min_morale or current_morale >= 100:
            return True, 0
        add_point = min(10, max(1, 100 - current_morale))
        payload = {
            "lAddPoint": str(add_point),
            "lGeneralID": str(general_id),
            "tid": str(base_id),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 47, payload) or {}
        ret = resp.get("ret", -1)
        return ret == 0, ret

    def provision_camp_generals_with_parent_city(
        self,
        camp_id: int,
        parent_city_id: int,
        general_ids: list[int],
        target_army: TargetArmy,
        current_armies: Optional[dict[int, Army]] = None,
        current_morales: Optional[dict[int, int]] = None,
        min_morale: int = 95,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Thực hiện quy trình điều tướng từ Doanh trại về Thành mẹ:

        1. Điều tướng về thành mẹ (OPT.ashx?id=50)
        2. Trị thương danh tướng (OPT.ashx?id=31)
        3. Chiêu mộ & biên chế đủ Định Mức Biên Chế (OPT.ashx?id=41, id=6)
        4. Nâng sĩ khí đạt ngưỡng tối thiểu nếu cần (OPT.ashx?id=47)
        5. Tái phái tướng trở lại Doanh trại (OPT.ashx?id=50)
        """
        if not camp_id or not parent_city_id or not general_ids:
            return False

        current_armies = current_armies or {}
        current_morales = current_morales or {}

        for gid in general_ids:
            if on_log:
                on_log(f"🚚 Điều tướng {gid} từ Doanh trại {camp_id} về Thành mẹ {parent_city_id}...")
            # 1. Điều tướng về Thành mẹ
            self.gateway.call(
                "OPT.ashx",
                50,
                {
                    "lCityID": str(camp_id),
                    "lGeneralID": str(gid),
                    "lDestID": str(parent_city_id),
                    "_": "",
                },
            )

            # 2. Trị thương
            self.heal_general(parent_city_id, gid)

            # 3. Bổ sung quân số
            cur_army = current_armies.get(gid)
            if target_army.total > 0:
                self.adjust_troops(
                    base_id=parent_city_id,
                    general_id=gid,
                    current_army=cur_army,
                    target_army=target_army,
                    auto_recruit=True,
                    on_log=on_log,
                )

            # 4. Tái phái tướng ra Trại (sĩ khí sẽ luyện tại Doanh trại theo ADR-0032)
            if on_log:
                on_log(f"⛺ Phái tướng {gid} từ Thành mẹ {parent_city_id} trở lại Doanh trại {camp_id}...")
            self.gateway.call(
                "OPT.ashx",
                50,
                {
                    "lCityID": str(parent_city_id),
                    "lGeneralID": str(gid),
                    "lDestID": str(camp_id),
                    "_": "",
                },
            )

        return True

