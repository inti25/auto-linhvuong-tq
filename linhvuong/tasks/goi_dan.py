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

import time
from typing import Any, Callable, Optional

from ..battle import BattleEngine, BattleReport, BattleState, CombatConfig
from ..coords import coords_from_mid, mid_from_coords
from ..locks import LockReason
from ..roster import Army, fetch_roster
from ..scan import Target
from ..troops import ArmyProvisioner, TargetArmy
from .base import (
    RET_CAPTCHA_REQUIRED,
    RET_OK,
    WORLD_ACTIVE_STATUSES,
    CaptchaRequired,
    TaskContext,
    attack,
    inspect_general_statuses,
)
from .morale import MoraleTrainer

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
        sleep_fn: Callable[[float], None] = time.sleep,
        check_idle: bool = True,
        combat_config: Optional[CombatConfig] = None,
        stop_event: Optional[Any] = None,
        on_battle_found: Optional[Callable[[int], None]] = None,
        on_battle_state: Optional[Callable[[BattleState], None]] = None,
        target_army: Optional[TargetArmy] = None,
        auto_recruit: bool = True,
        auto_morale: bool = True,
        min_morale: int = 95,
        provisioner: Optional[ArmyProvisioner] = None,
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
        self.sleep_fn = sleep_fn
        self.check_idle = check_idle
        self.combat_config = combat_config
        self.stop_event = stop_event
        self.on_battle_found = on_battle_found
        self.on_battle_state = on_battle_state
        self.target_army = target_army
        self.auto_recruit = auto_recruit
        self.auto_morale = auto_morale
        self.min_morale = min_morale
        self.provisioner = provisioner or ArmyProvisioner(ctx.gateway, sleep_fn=sleep_fn)

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

    def _scan_with_retry(self, curr_type: int) -> Optional[Target]:
        """Quét tìm mục tiêu vừa gọi quanh thành, thử lại với trễ và mở rộng bán kính nếu là Vong Linh."""
        effective_radius = max(self.radius, 10) if curr_type == VONG_LINH else self.radius
        target = None
        for attempt in range(3):
            if attempt > 0:
                self.sleep_fn(1.5)
            r = self.radius if (attempt == 0 and curr_type != VONG_LINH) else effective_radius
            try:
                target = self.ctx.scanner.find_nearest(
                    *self.origin,
                    r,
                    [curr_type],
                    skip_capital_radius=self.skip_capital_radius,
                    owner_id=int(self.city_id or 0),
                    use_cache=False,
                )
            except TypeError:
                target = self.ctx.scanner.find_nearest(
                    *self.origin,
                    r,
                    [curr_type],
                    skip_capital_radius=self.skip_capital_radius,
                    owner_id=int(self.city_id or 0),
                )
            if target is not None:
                break
        return target

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
                invalidate = getattr(self.ctx.gateway, "invalidate_map_cache", None)
                if callable(invalidate):
                    invalidate()
                target = self._scan_with_retry(curr_type)
                if target is None:
                    return None, "target_not_found_after_call"
                return target, None
            elif ret_call == 236:
                if self.ctx.notify:
                    if curr_type == VONG_LINH:
                        self.ctx.notify("⚠️ Gọi Vong Linh thất bại: Máy chủ chưa mở sự kiện Vong Linh (mã lỗi 236: 当前没有相关活动).")
                    else:
                        self.ctx.notify(f"⚠️ Gọi mục tiêu {curr_type} thất bại: Sự kiện chưa mở (mã lỗi 236).")
                last_ret = ret_call
                continue
            elif ret_call == 90:
                if self.ctx.notify:
                    if curr_type == VONG_LINH:
                        self.ctx.notify("❌ Hết Bùa Vong Linh (追风铁令) trong túi đồ (mã lỗi 90)!")
                    else:
                        self.ctx.notify(f"❌ Hết đạo cụ gọi mục tiêu {curr_type} trong túi đồ (mã lỗi 90)!")
                last_ret = ret_call
                continue
            elif ret_call == 39:
                if self.ctx.notify:
                    self.ctx.notify(f"⚠️ Vị trí quanh thành đang bị chiếm dụng (mã lỗi 39) khi gọi mục tiêu {curr_type}.")
                last_ret = ret_call
                continue
            elif ret_call != RET_OK:
                if self.ctx.notify:
                    self.ctx.notify(f"⚠️ Gọi mục tiêu {curr_type} thất bại (mã lỗi: {ret_call}).")
                last_ret = ret_call
                continue

            # Thành công gọi
            self._current_type_idx = (idx + 1) % total_types
            self.target_type = curr_type

            # Nếu server trả về trực tiếp thông tin mục tiêu
            if "new_target_id" in resp_call:
                x, y = coords_from_mid(int(resp_call["new_target_mid"]))
                return Target(x, y, int(resp_call["new_target_id"]), int(resp_call.get("new_target_type", curr_type))), None

            # Quét tìm mục tiêu vừa xuất hiện quanh thành (vô hiệu hóa cache bản đồ vì mới gọi quái)
            invalidate = getattr(self.ctx.gateway, "invalidate_map_cache", None)
            if callable(invalidate):
                invalidate()
            target = self._scan_with_retry(curr_type)
            if target is None:
                if self.ctx.notify:
                    self.ctx.notify(f"⚠️ Đã kích hoạt gọi mục tiêu {curr_type} thành công nhưng chưa định vị được trên bản đồ.")
                return None, "target_not_found_after_call"
            return target, None

        return None, f"call_failed:{last_ret}"

    def recover_generals(self) -> None:
        """Thực hiện chu trình hồi phục sau chiến đấu: trị thương và bổ sung tân binh."""
        roster = None
        if self.target_army and self.target_army.total > 0 and self.auto_recruit and self.city_id:
            try:
                roster = fetch_roster(
                    self.ctx.gateway,
                    only_base_ids=[self.city_id],
                    include_civil=False,
                    include_cities=False,
                )
            except Exception:
                roster = None

        for gid in self.generals:
            # 1. Trị thương
            self.provisioner.heal_general(self.city_id, gid)
            # 2. Bù lính theo TargetArmy hoặc cấu hình legacy
            if self.target_army and self.target_army.total > 0 and self.auto_recruit and self.city_id:
                cur_army = roster.army_of(gid) if roster else None
                self.provisioner.adjust_troops(
                    base_id=self.city_id,
                    general_id=gid,
                    current_army=cur_army,
                    target_army=self.target_army,
                    auto_recruit=True,
                    on_log=self.ctx.notify,
                )
            elif self.refill_amount > 0 and self.city_id:
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

    def check_generals_idle(self) -> bool:
        """Kiểm tra toàn bộ võ tướng có đang rảnh rỗi (status == 0) hay không."""
        statuses = inspect_general_statuses(self.ctx.gateway, self.generals)
        return all(st == 0 for st in statuses.values())

    def _track_active_battle(self) -> Optional[BattleReport]:
        """Tự động dò chiến trường thế giới đang diễn ra (hoặc đang hành quân tới) và vào điều khiển."""
        engine = BattleEngine(self.ctx.gateway, config=self.combat_config)
        return engine.wait_and_track_world_battle(
            generals=self.generals,
            origin_id=int(self.city_id or 0),
            on_log=self.ctx.notify,
            on_boss_alert=self.ctx.notify,
            on_battle_found=self.on_battle_found,
            on_state=self.on_battle_state,
            stop_event=self.stop_event,
            sleep_fn=self.sleep_fn,
            config=self.combat_config,
        )

    def run_once(self) -> str:
        # 0. Kiểm tra tướng rảnh rỗi (Idle Check) nếu bật check_idle
        if self.check_idle and self.city_id:
            statuses = inspect_general_statuses(self.ctx.gateway, self.generals)
            if any(st != 0 for st in statuses.values()):
                if any(st in WORLD_ACTIVE_STATUSES for st in statuses.values()):
                    report = self._track_active_battle()
                    if report is not None:
                        if self.auto_recover:
                            self.recover_generals()
                        return "battle_tracked"
                if self.ctx.notify:
                    self.ctx.notify("⏳ Võ tướng đang bận hoặc hành quân trên đường, chờ hồi thành...")
                return "generals_busy"

        # 1. Chuẩn bị quân lực & Luyện sĩ khí trước khi gọi/xuất quân
        if self.city_id and self.target_army is not None and ((self.target_army.total > 0 and self.auto_recruit) or self.auto_morale):
            try:
                roster = fetch_roster(
                    self.ctx.gateway,
                    only_base_ids=[self.city_id],
                    include_civil=False,
                    include_cities=False,
                )
                city_gens = {g.id: g for g in roster.generals_of(self.city_id)}
            except Exception:
                roster = None
                city_gens = {}

            # Trị thương & Bổ sung lính
            troops_added = False
            for gid in self.generals:
                self.provisioner.heal_general(self.city_id, gid)
                if self.auto_recruit and self.target_army and self.target_army.total > 0 and roster:
                    cur_army = roster.army_of(gid)
                    adj_res = self.provisioner.adjust_troops(
                        base_id=self.city_id,
                        general_id=gid,
                        current_army=cur_army,
                        target_army=self.target_army,
                        auto_recruit=True,
                        on_log=self.ctx.notify,
                    )
                    if any(succ and diff > 0 for _, diff, succ, _ in (adj_res or [])):
                        troops_added = True

            # Luyện sĩ khí đồng loạt và chờ hoàn tất đếm ngược trước khi quét/gọi mục tiêu (ADR-0032)
            if self.auto_morale and city_gens:
                trainer = MoraleTrainer(self.ctx.gateway)
                ready, wait_reasons = trainer.adjust_squad_morale(
                    base_id=self.city_id,
                    general_ids=self.generals,
                    target_morale=self.min_morale,
                    base_gens=city_gens,
                    on_notify=self.ctx.notify,
                    stop_event=getattr(self.ctx, "stop_event", None),
                    refresh_from_server=troops_added,
                )
                if not ready:
                    return "waiting_morale"

        # 2. Tìm mục tiêu có sẵn quanh thành trước
        target = self.ctx.scanner.find_nearest(
            *self.origin,
            self.radius,
            self.target_types,
            skip_capital_radius=self.skip_capital_radius,
            owner_id=int(self.city_id or 0),
        )
        if target is not None:
            self.ctx.locks.try_lock(target.target_id, LockReason.CLAIMED, owner=int(self.city_id or 0))
            result = attack(
                self.ctx,
                target,
                self.generals,
                sleep_fn=self.sleep_fn,
                origin_id=int(self.city_id or 0),
            )
            if result == "attacked" and self.city_id:
                self._track_active_battle()
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
        result = attack(
            self.ctx,
            target,
            self.generals,
            sleep_fn=self.sleep_fn,
            origin_id=int(self.city_id or 0),
        )
        if result == "attacked" and self.city_id:
            self._track_active_battle()
        if self.auto_recover:
            self.recover_generals()
        return "called_and_attacked" if result == "attacked" else result


# Định danh chuẩn theo mô hình miền GLOSSARY
GoiMan = GoiDan

