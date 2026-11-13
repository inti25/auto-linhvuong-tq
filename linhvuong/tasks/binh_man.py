"""Bình Man: Tự động quét và tấn công Man quanh thành hoặc Trại Di Chuyển.

Reverse engineered chính xác từ ZMan.exe:
- Quét tìm Man trong bán kính quanh thành hoặc Trại Di Chuyển.
- Khi sử dụng Trại Di Chuyển (camp_id > 0):
  1. Nếu cự ly tới mục tiêu > 2 ô, tự động dời Trại từng bước: Common.ashx?id=55 (lDestX, lDestY, lTentID).
  2. Bắt lỗi ret=39 (vướng vật cản/địa hình): tự lùi bước nhảy (backoff) tìm ô trống phụ cận.
  3. Sau mỗi bước dời trại thành công (ret=0), đếm lùi thời gian đóng băng (frozen_time).
  4. Khi cự ly <= 2 ô, khóa mục tiêu và xuất kích tấn công: OPT.ashx?id=53.
- Ngưỡng An Toàn (Return Threshold):
  Khi quân số hoặc thể lực rơi xuống dưới ngưỡng quy định:
  1. Rút tướng về thành mẹ: OPT.ashx?id=50.
  2. Trị thương danh tướng: OPT.ashx?id=31.
  3. Chiêu mộ thêm tân binh: OPT.ashx?id=41.
  4. Phối quân vào đạo: OPT.ashx?id=6.
  5. Tái xuất quân ra Trại: OPT.ashx?id=50.
"""

import math
import time
from typing import Any, Callable, Optional

from ..battle import BattleEngine, BattleReport, BattleState, CombatConfig
from ..locks import TargetLocks
from ..roster import Army, fetch_roster
from ..scan import BasePeer, Target
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
from .di_trai import DiTrai, chebyshev_distance
from .morale import MoraleTrainer


MODE_CAMP = 1  # Chế độ 1: Sử dụng Doanh trại di chuyển đến cạnh Man
MODE_CITY = 2  # Chế độ 2: Xuất quân thẳng từ Thành

MAN_TARGET_OPTIONS: list[tuple[int, str]] = [
    (301, "Vong Linh (ID 301)"),
    (1, "Cấp 1 - Uy Quốc"),
    (2, "Cấp 2 - Tiên Ti"),
    (3, "Cấp 3 - Ô Hoàn"),
    (4, "Cấp 4 - Sơn Việt"),
    (5, "Cấp 5 - Khương Để"),
    (6, "Cấp 6 - Mạnh Hoạch"),
    (7, "Cấp 7 - Hung Nô"),
    (8, "Cấp 8 - Đột Quyết"),
    (9, "Cấp 9 - Long Phi"),
    (10, "Cấp 10 - Hổ Báo Kỵ"),
]


class BinhMan:
    def __init__(
        self,
        ctx: TaskContext,
        generals: list[int],
        origin: tuple[int, int],
        radius: int,
        man_types: list[int],
        camp_id: Optional[int] = None,
        parent_city_id: Optional[int] = None,
        return_threshold: int = 0,
        max_step: int = 2,
        skip_capital_radius: int = 0,
        auto_recover: bool = False,
        sleep_fn: Callable[[float], None] = time.sleep,
        mode: Optional[int] = None,
        city_id: Optional[int] = None,
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
        peers: Optional[list[BasePeer]] = None,
        peers_fn: Optional[Callable[[], list[BasePeer]]] = None,
        non_blocking_relocate: bool = False,
        base_name: str = "",
    ):
        self.ctx = ctx
        self.generals = generals
        self.origin = origin
        self.radius = radius
        self.man_types = man_types
        self.camp_id = camp_id
        self.parent_city_id = parent_city_id
        self.return_threshold = return_threshold
        self.max_step = max_step
        self.skip_capital_radius = skip_capital_radius
        self.auto_recover = auto_recover
        self.sleep_fn = sleep_fn
        self.city_id = city_id or parent_city_id
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
        self.peers = peers
        self.peers_fn = peers_fn
        self.non_blocking_relocate = non_blocking_relocate
        self.base_name = base_name
        self._camp_frozen_until: float = 0.0

        # Tự động suy ra mode nếu không chỉ định: có camp_id là Chế độ 1, không có là Chế độ 2
        if mode is not None:
            self.mode = mode
        else:
            self.mode = MODE_CAMP if self.camp_id else MODE_CITY

    @property
    def origin_id(self) -> int:
        if self.mode == MODE_CAMP and self.camp_id:
            return int(self.camp_id)
        return int(self.city_id or 0)

    @property
    def locks(self) -> TargetLocks:
        return self.ctx.locks

    def _evaluate_needs_return(
        self, remaining_percent: Optional[float] = None
    ) -> tuple[bool, Any]:
        """Kiểm tra điều kiện rút quân và trả kèm Roster vừa đọc (nếu có) để tái sử dụng."""
        if remaining_percent is not None and remaining_percent < 100.0:
            return remaining_percent < self.return_threshold, None

        roster = None
        if self.return_threshold > 0 and self.origin_id:
            try:
                roster = fetch_roster(
                    self.ctx.gateway,
                    only_base_ids=[self.origin_id],
                    include_civil=False,
                    include_cities=False,
                )
                gens = {g.id: g for g in roster.generals_of(self.origin_id)}
                for gid in self.generals:
                    g = gens.get(gid)
                    if not g:
                        continue
                    stamina_pct = (g.stamina / g.stamina_max * 100.0) if g.stamina_max > 0 else 100.0
                    if stamina_pct < self.return_threshold:
                        return True, roster
                    if self.target_army and self.target_army.total > 0:
                        army = roster.army_of(gid)
                        army_tot = army.total if army else 0
                        army_pct = (army_tot / self.target_army.total) * 100.0
                        if army_pct < self.return_threshold:
                            return True, roster
            except Exception:
                pass

        if remaining_percent is not None:
            return remaining_percent < self.return_threshold, roster
        return False, roster

    def needs_return(self, remaining_percent: Optional[float] = None) -> bool:
        """Binh lực hoặc thể lực còn lại (%) dưới ngưỡng thì cần rút về thành."""
        need_ret, _ = self._evaluate_needs_return(remaining_percent)
        return need_ret

    def check_generals_idle(self) -> bool:
        """Kiểm tra toàn bộ võ tướng có đang rảnh rỗi (status == 0) hay không."""
        statuses = inspect_general_statuses(self.ctx.gateway, self.generals)
        return all(st == 0 for st in statuses.values())

    def _track_active_battle(self) -> Optional[BattleReport]:
        """Tự động dò chiến trường thế giới đang diễn ra (hoặc đang hành quân tới) và vào điều khiển."""
        engine = BattleEngine(self.ctx.gateway, config=self.combat_config)
        return engine.wait_and_track_world_battle(
            generals=self.generals,
            origin_id=self.origin_id,
            on_log=self.ctx.notify,
            on_boss_alert=self.ctx.notify,
            on_battle_found=self.on_battle_found,
            on_state=self.on_battle_state,
            stop_event=self.stop_event,
            sleep_fn=self.sleep_fn,
            config=self.combat_config,
        )

    def step_towards(self, target_x: int, target_y: int, step_limit: Optional[int] = None) -> tuple[int, int]:
        """Tính tọa độ bước dời kế tiếp hướng về mục tiêu, giới hạn bởi step_limit."""
        mover = DiTrai(
            ctx=self.ctx,
            camp_id=self.camp_id or 0,
            origin=self.origin,
            destination=(target_x, target_y),
            max_step=self.max_step,
            sleep_fn=self.sleep_fn,
        )
        return mover.step_towards(target_x, target_y, step_limit)

    def move_camp(self, dest_x: int, dest_y: int) -> tuple[bool, int, str]:
        """Gửi lệnh dời Trại Di Chuyển qua Common.ashx?id=55."""
        if not self.camp_id:
            self.origin = (dest_x, dest_y)
            return True, 0, "ok"

        mover = DiTrai(
            ctx=self.ctx,
            camp_id=self.camp_id,
            origin=self.origin,
            destination=(dest_x, dest_y),
            max_step=self.max_step,
            sleep_fn=self.sleep_fn,
        )
        success, frozen, reason = mover.move_step(dest_x, dest_y)
        if success:
            self.origin = mover.origin
        return success, frozen, reason

    def advance_camp_to_target(self, target: Target) -> bool:
        """Dời Trại Di Chuyển từng bước hướng tới mục tiêu cho đến khi khoảng cách <= 2 ô."""
        if not self.camp_id:
            return True

        mover = DiTrai(
            ctx=self.ctx,
            camp_id=self.camp_id,
            origin=self.origin,
            destination=(target.x, target.y),
            max_step=self.max_step,
            sleep_fn=self.sleep_fn,
            stop_at_distance=2,
        )
        res = mover.advance_to_destination()
        self.origin = mover.origin
        return res in ("arrived", "stopped")

    def advance_camp_one_step(self, target: Target) -> tuple[bool, int]:
        """Dời Trại Di Chuyển 1 bước hướng tới mục tiêu mà không ngủ chờ frozen_time (non-blocking).
        
        Trả về: (đã_đến_cự_ly_2_ô, frozen_seconds).
        """
        if not self.camp_id:
            return True, 0

        dist = chebyshev_distance(self.origin[0], self.origin[1], target.x, target.y)
        if dist <= 2:
            return True, 0

        mover = DiTrai(
            ctx=self.ctx,
            camp_id=self.camp_id,
            origin=self.origin,
            destination=(target.x, target.y),
            max_step=self.max_step,
            sleep_fn=lambda s: None,
            stop_at_distance=2,
        )
        next_x, next_y = mover.step_towards(target.x, target.y)
        success, frozen, reason = mover.move_step(next_x, next_y)
        if success:
            self.origin = mover.origin
            new_dist = chebyshev_distance(self.origin[0], self.origin[1], target.x, target.y)
            return new_dist <= 2, frozen
        return False, 0

    def retreat_to_safety(self) -> None:
        """Hồi binh về thành mẹ để trị thương và bổ sung quân lực (Chế độ 1 - Doanh trại)."""
        if not self.parent_city_id or not self.camp_id:
            return

        roster = None
        if self.target_army and self.target_army.total > 0 and self.auto_recruit:
            try:
                roster = fetch_roster(
                    self.ctx.gateway,
                    only_base_ids=[self.camp_id, self.parent_city_id],
                    include_civil=False,
                    include_cities=False,
                )
            except Exception:
                roster = None

        for gid in self.generals:
            # 1. Điều tướng về thành mẹ (OPT.ashx?id=50)
            self.ctx.gateway.call(
                "OPT.ashx",
                50,
                {
                    "lCityID": str(self.camp_id),
                    "lGeneralID": str(gid),
                    "lDestID": str(self.parent_city_id),
                    "_": "",
                },
            )
            # 2. Trị thương
            self.provisioner.heal_general(self.parent_city_id, gid)

            # 3. Bổ sung quân số theo TargetArmy hoặc cấu hình legacy
            if self.target_army and self.target_army.total > 0 and self.auto_recruit:
                cur_army = roster.army_of(gid) if roster else None
                self.provisioner.adjust_troops(
                    base_id=self.parent_city_id,
                    general_id=gid,
                    current_army=cur_army,
                    target_army=self.target_army,
                    auto_recruit=True,
                    on_log=self.ctx.notify,
                )
            else:
                self.ctx.gateway.call(
                    "OPT.ashx",
                    41,
                    {"lAmount": "1000", "tid": str(self.parent_city_id), "_": ""},
                )
                self.ctx.gateway.call(
                    "OPT.ashx",
                    6,
                    {
                        "lGeneralID": str(gid),
                        "lSoldierType": "1",
                        "lAmount": "1000",
                        "tid": str(self.parent_city_id),
                        "_": "",
                    },
                )

            # 4. Tái phái tướng trở lại Trại (OPT.ashx?id=50) - Sĩ khí sẽ luyện tại Trại theo ADR-0032
            self.ctx.gateway.call(
                "OPT.ashx",
                50,
                {
                    "lCityID": str(self.parent_city_id),
                    "lGeneralID": str(gid),
                    "lDestID": str(self.camp_id),
                    "_": "",
                },
            )

    def recover_in_city(self) -> None:
        """Trị thương và bổ sung quân tại chỗ trong Thành (Chế độ 2 - Xuất quân từ Thành)."""
        cid = self.city_id or self.parent_city_id or 0
        roster = None
        if self.target_army and self.target_army.total > 0 and self.auto_recruit and cid:
            try:
                roster = fetch_roster(self.ctx.gateway, only_base_ids=[cid])
            except Exception:
                roster = None

        for gid in self.generals:
            # 1. Trị thương
            self.provisioner.heal_general(cid, gid)

            # 2. Bổ sung quân theo TargetArmy hoặc cấu hình legacy
            if self.target_army and self.target_army.total > 0 and self.auto_recruit:
                cur_army = roster.army_of(gid) if roster else None
                self.provisioner.adjust_troops(
                    base_id=cid,
                    general_id=gid,
                    current_army=cur_army,
                    target_army=self.target_army,
                    auto_recruit=True,
                    on_log=self.ctx.notify,
                )
            else:
                self.ctx.gateway.call(
                    "OPT.ashx",
                    41,
                    {"lAmount": "1000", "tid": str(cid), "_": ""},
                )
                self.ctx.gateway.call(
                    "OPT.ashx",
                    6,
                    {
                        "lGeneralID": str(gid),
                        "lSoldierType": "1",
                        "lAmount": "1000",
                        "tid": str(cid),
                        "_": "",
                    },
                )

    def run_once(self, remaining_percent: Optional[float] = None) -> str:
        # 0. Nếu Doanh trại đang trong thời gian đóng băng (frozen_time) từ bước dời trước
        if self.non_blocking_relocate and time.time() < self._camp_frozen_until:
            return "camp_frozen"

        # 1. Kiểm tra ngưỡng an toàn trước tiên
        need_ret, pre_roster = self._evaluate_needs_return(remaining_percent)
        if need_ret:
            if self.mode == MODE_CAMP:
                self.retreat_to_safety()
                return "retreated_below_threshold"
            else:
                self.recover_in_city()
                if self.return_threshold > 0 and self.origin_id:
                    try:
                        roster = pre_roster or fetch_roster(
                            self.ctx.gateway,
                            only_base_ids=[self.origin_id],
                            include_civil=False,
                            include_cities=False,
                        )
                        gens = {g.id: g for g in roster.generals_of(self.origin_id)}
                        for gid in self.generals:
                            g = gens.get(gid)
                            if g and g.stamina_max > 0:
                                stamina_pct = (g.stamina / g.stamina_max * 100.0)
                                if stamina_pct < self.return_threshold:
                                    if self.ctx.notify:
                                        self.ctx.notify(
                                            f"⏳ [Thể lực] Võ tướng {g.name} thể lực ({g.stamina}/{g.stamina_max} = {stamina_pct:.0f}%) "
                                            f"dưới ngưỡng an toàn ({self.return_threshold}%), chờ hồi phục..."
                                        )
                                    return "waiting_stamina"
                    except Exception:
                        pass
                return "recovered_in_city"

        # 2. Kiểm tra tướng rảnh rỗi (Idle Check) nếu bật check_idle (tái sử dụng pre_roster nếu đã đọc)
        if self.check_idle and (self.city_id or self.camp_id):
            if pre_roster is not None:
                wanted = {int(g) for g in self.generals}
                statuses = {
                    g.id: g.status
                    for g in pre_roster.generals_of(self.origin_id)
                    if g.id in wanted
                }
            else:
                statuses = inspect_general_statuses(self.ctx.gateway, self.generals)
            if any(st != 0 for st in statuses.values()):
                if any(st in WORLD_ACTIVE_STATUSES for st in statuses.values()):
                    report = self._track_active_battle()
                    if report is not None:
                        return "battle_tracked"
                if self.ctx.notify:
                    self.ctx.notify("⏳ Võ tướng đang bận hoặc hành quân trên đường, chờ hồi thành...")
                return "generals_busy"

        # 3. Chuẩn bị quân lực & Luyện sĩ khí trước khi xuất quân (tái sử dụng pre_roster nếu có)
        if self.origin_id and self.target_army is not None and ((self.target_army.total > 0 and self.auto_recruit) or self.auto_morale):
            try:
                roster = pre_roster or fetch_roster(
                    self.ctx.gateway,
                    only_base_ids=[self.origin_id],
                    include_civil=False,
                    include_cities=False,
                )
                base_gens = {g.id: g for g in roster.generals_of(self.origin_id)}
            except Exception:
                roster = None
                base_gens = {}

            is_city = (self.mode == MODE_CITY or int(self.origin_id) > 0)
            troops_added = False
            for gid in self.generals:
                self.provisioner.heal_general(self.origin_id, gid)
                if self.auto_recruit and self.target_army.total > 0 and roster:
                    cur_army = roster.army_of(gid)
                    # Thành thì cho phép mua tân binh (auto_recruit=True), Doanh trại chỉ rút đồn trú (auto_recruit=False)
                    adj_res = self.provisioner.adjust_troops(
                        base_id=self.origin_id,
                        general_id=gid,
                        current_army=cur_army,
                        target_army=self.target_army,
                        auto_recruit=is_city,
                        on_log=self.ctx.notify,
                    )
                    if any(succ and diff > 0 for _, diff, succ, _ in (adj_res or [])):
                        troops_added = True

            if self.auto_morale and base_gens:
                trainer = MoraleTrainer(self.ctx.gateway)
                ready, wait_reasons = trainer.adjust_squad_morale(
                    base_id=self.origin_id,
                    general_ids=self.generals,
                    target_morale=self.min_morale,
                    base_gens=base_gens,
                    on_notify=self.ctx.notify,
                    stop_event=getattr(self.ctx, "stop_event", None),
                    refresh_from_server=troops_added,
                )
                if not ready:
                    return "waiting_morale"

        # 4. Quét tìm Man mục tiêu (áp dụng Quy Tắc Ưu Tiên Căn Cứ Gần Nhất - ADR-0029)
        active_peers = self.peers_fn() if self.peers_fn else self.peers
        target = self.ctx.scanner.find_nearest(
            *self.origin,
            self.radius,
            self.man_types,
            skip_capital_radius=self.skip_capital_radius,
            owner_id=self.origin_id,
            peers=active_peers,
        )
        if target is None:
            return "no_target"

        # 5. Nếu ở Chế độ 1 (Doanh trại) và mục tiêu xa hơn 2 ô -> Dời trại
        if self.mode == MODE_CAMP and self.camp_id and chebyshev_distance(self.origin[0], self.origin[1], target.x, target.y) > 2:
            if self.non_blocking_relocate:
                reached, frozen = self.advance_camp_one_step(target)
                if frozen > 0:
                    self._camp_frozen_until = time.time() + frozen
                if not reached:
                    return "camp_relocating"
            else:
                reached = self.advance_camp_to_target(target)
                if not reached:
                    return "relocate_failed"

        # 6. Chốt chặn kiểm tra khóa mục tiêu trước khi xuất kích (ADR-0029)
        if self.ctx.locks.is_locked_by_other(target.target_id, owner=self.origin_id):
            if self.ctx.notify:
                self.ctx.notify(f"⚠️ Mục tiêu {target.target_id} đã bị căn cứ khác nhận. Hủy xuất kích và quét lại.")
            return "target_claimed_by_other"

        # 7. Xuất quân tấn công (hỗ trợ chia nhiều đợt nếu > 3 tướng)
        result = attack(
            self.ctx,
            target,
            self.generals,
            sleep_fn=self.sleep_fn,
            origin_id=self.origin_id,
        )
        if result == "attacked" and (self.city_id or self.camp_id):
            self._track_active_battle()
        elif result == "taken":
            invalidate = getattr(self.ctx.gateway, "invalidate_map_cache", None)
            if callable(invalidate):
                invalidate()
        return result

