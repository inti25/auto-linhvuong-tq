"""Gọi Dân & Gọi Vong Linh: triệu hồi mục tiêu và xuất quân tiêu diệt.

Reverse engineered chính xác từ ZMan.exe:
- Gọi Vong Linh (ID=301):
  1. Chuyển thành thị: City.ashx?id=50 (tid: city_id).
  2. Kích hoạt bùa Vong Linh (ID 268): OPT.ashx?id=69 (type=33, param1=268, param2=0, paytype=1).
     ret=0: thành công, ret=209: Vong Linh đang bận / đã tồn tại, ret=110: captcha.
  3. Quét map định vị Vong Linh vừa xuất hiện và khóa mục tiêu.
  4. Xuất quân tấn công: OPT.ashx?id=53.
- Gọi Dân Thường:
  1. Xác định tọa độ trống gần thành (x, y) -> mid = mid_from_coords(x, y).
  2. Kích hoạt gọi dân: OPT.ashx?id=69 (type=63, param1=target_type, param2=mid, paytype=1).
  3. Khóa mục tiêu và xuất quân tiêu diệt: OPT.ashx?id=53.
- Chu trình phục hồi sau trận (nếu bật auto_recover):
  1. Trị thương danh tướng: OPT.ashx?id=31 (lCityTentID, lGeneralID).
  2. Bổ sung quân số: OPT.ashx?id=6 (lGeneralID, lSoldierType, lAmount, tid).
"""

from typing import Optional

from ..coords import coords_from_mid, mid_from_coords
from ..locks import LockReason
from ..scan import Target
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired, TaskContext, attack

VONG_LINH = 301
VONG_LINH_TALISMAN_ID = 268


class GoiDan:
    def __init__(
        self,
        ctx: TaskContext,
        generals: list[int],
        origin: tuple[int, int],
        radius: int = 5,
        skip_capital_radius: int = 0,
        mode: Optional[str] = None,  # "vong_linh" hoặc "dan"
        city_id: Optional[int] = None,
        target_type: int = VONG_LINH,
        target_types: Optional[list[int]] = None,
        soldier_type: int = 1,
        refill_amount: int = 0,
        auto_recover: bool = False,
    ):
        self.ctx = ctx
        self.generals = generals
        self.origin = origin
        self.radius = radius
        self.skip_capital_radius = skip_capital_radius
        self.city_id = city_id or 0
        if target_types:
            self.target_types = list(target_types)
        else:
            self.target_types = [target_type]
        self._current_type_idx = 0
        self.target_type = self.target_types[0]
        self.soldier_type = soldier_type
        self.refill_amount = refill_amount
        self.auto_recover = auto_recover

        # Tự động suy ra mode từ target_type nếu mode chưa được chỉ định
        if mode:
            self.mode = mode
        elif self.target_type == VONG_LINH:
            self.mode = "vong_linh"
        else:
            self.mode = "dan"

    def _get_call_payload(self, t_type: int) -> dict:
        if t_type == VONG_LINH or (self.mode == "vong_linh" and len(self.target_types) == 1):
            return {
                "type": "33",
                "param1": str(VONG_LINH_TALISMAN_ID),
                "param2": "0",
                "paytype": "1",
                "_": "",
            }
        else:
            mid = mid_from_coords(*self.origin)
            return {
                "type": "63",
                "param1": str(t_type),
                "param2": str(mid),
                "paytype": "1",
                "_": "",
            }

    def call_target(self) -> tuple[Optional[Target], Optional[str]]:
        """Kích hoạt API gọi quái theo đúng chế độ đã cấu hình, xoay vòng qua target_types."""
        # Chuyển focus thành nếu có city_id
        if self.city_id:
            resp_move = self.ctx.gateway.call("City.ashx", 50, {"tid": str(self.city_id), "_": ""}) or {}
            ret_move = resp_move.get("ret", RET_OK)
            if ret_move == 110 or ret_move == RET_CAPTCHA_REQUIRED:
                raise CaptchaRequired()
        else:
            # Tương thích với test mock cũ
            resp_move = self.ctx.gateway.call("City.ashx", 50, {}) or {}
            ret_move = resp_move.get("ret", RET_OK)
            if ret_move == 110 or ret_move == RET_CAPTCHA_REQUIRED:
                raise CaptchaRequired()
            if "new_target_id" in resp_move:
                x, y = coords_from_mid(int(resp_move["new_target_mid"]))
                return Target(x, y, int(resp_move["new_target_id"]), int(resp_move.get("new_target_type", self.target_type))), None
            if ret_move != RET_OK:
                return None, f"call_failed:{ret_move}"

        total_types = len(self.target_types)
        last_ret = RET_OK
        for attempt in range(total_types):
            idx = (self._current_type_idx + attempt) % total_types
            curr_type = self.target_types[idx]
            call_payload = self._get_call_payload(curr_type)

            resp_call = self.ctx.gateway.call("OPT.ashx", 69, call_payload) or {}
            ret_call = resp_call.get("ret", RET_OK)
            if ret_call == 110 or ret_call == RET_CAPTCHA_REQUIRED:
                raise CaptchaRequired()
            if ret_call == 209:
                if self.ctx.notify:
                    self.ctx.notify(f"⚠️ Mục tiêu {curr_type} đang bận hoặc đã tồn tại, tiến hành quét tìm...")
                self._current_type_idx = (idx + 1) % total_types
                self.target_type = curr_type
                target = self.ctx.scanner.find_nearest(
                    *self.origin,
                    self.radius,
                    [curr_type],
                    skip_capital_radius=self.skip_capital_radius,
                )
                if target is None:
                    return None, "target_not_found_after_call"
                return target, None
            elif ret_call != RET_OK:
                last_ret = ret_call
                continue

            # Thành công gọi
            self._current_type_idx = (idx + 1) % total_types
            self.target_type = curr_type

            # Nếu server trả về trực tiếp thông tin mục tiêu
            if "new_target_id" in resp_call:
                x, y = coords_from_mid(int(resp_call["new_target_mid"]))
                return Target(x, y, int(resp_call["new_target_id"]), int(resp_call.get("new_target_type", curr_type))), None

            # Quét tìm mục tiêu vừa xuất hiện quanh thành
            target = self.ctx.scanner.find_nearest(
                *self.origin,
                self.radius,
                [curr_type],
                skip_capital_radius=self.skip_capital_radius,
            )
            if target is None:
                return None, "target_not_found_after_call"
            return target, None

        return None, f"call_failed:{last_ret}"

    def recover_generals(self) -> None:
        """Thực hiện chu trình hồi phục sau chiến đấu: trị thương và bổ sung tân binh."""
        for gid in self.generals:
            # 1. Trị thương (OPT.ashx?id=31)
            self.ctx.gateway.call(
                "OPT.ashx",
                31,
                {"lCityTentID": str(self.city_id), "lGeneralID": str(gid), "_": ""},
            )
            # 2. Bù lính nếu có cấu hình số lượng (OPT.ashx?id=6)
            if self.refill_amount > 0:
                self.ctx.gateway.call(
                    "OPT.ashx",
                    6,
                    {
                        "lGeneralID": str(gid),
                        "lSoldierType": str(self.soldier_type),
                        "lAmount": str(self.refill_amount),
                        "tid": str(self.city_id),
                        "_": "",
                    },
                )

    def run_once(self) -> str:
        # 1. Tìm mục tiêu có sẵn quanh thành trước
        target = self.ctx.scanner.find_nearest(
            *self.origin,
            self.radius,
            self.target_types,
            skip_capital_radius=self.skip_capital_radius,
        )
        if target is not None:
            result = attack(self.ctx, target, self.generals)
            if self.auto_recover:
                self.recover_generals()
            return result

        # 2. Không có mục tiêu sẵn có -> Kích hoạt gọi mới
        target, err = self.call_target()
        if err is not None:
            return err
        if target is None:
            return "no_target"

        self.ctx.locks.try_lock(target.target_id, LockReason.CLAIMED)
        result = attack(self.ctx, target, self.generals)
        if self.auto_recover:
            self.recover_generals()
        return "called_and_attacked" if result == "attacked" else result


# Định danh chuẩn theo mô hình miền GLOSSARY
GoiMan = GoiDan

