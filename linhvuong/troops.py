"""Biên Chế Quân Tự Động & Luyện Sĩ Khí dùng chung.

Trích xuất logic miền tập trung từ Thảo Phạt, phục vụ dùng chung cho:
- Thảo Phạt (ThaoPhatExecutor)
- Gọi Man (GoiDan / GoiMan)
- Bình Man (BinhMan)
- Giao diện Dashboard (Biên chế tức thời)
"""

from collections import Counter
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .armament import fetch_armament
from .gateway import GatewayClient
from .roster import Army

logger = logging.getLogger("linhvuong.troops")

POPULATION_COMFORT_SUCCESS_COOLDOWN = 900.0
POPULATION_COMFORT_RETRY_COOLDOWN = 60.0
MIN_PARTIAL_PROVISION_BATCH = 50
POPULATION_SHORTAGE_RETS = frozenset({34, 53, 55})


def has_population_shortage(results: Optional[list[tuple[int, int, bool, int]]]) -> bool:
    """Kiểm tra kết quả adjust_troops có phản ánh thiếu dân hoặc tân binh hay không."""
    if not results:
        return False
    return any(
        (not succ) and ret_code in POPULATION_SHORTAGE_RETS
        for _, _, succ, ret_code in results
    )


def _raise_if_captcha(ret: Any) -> None:
    if ret in (110, 73):
        from .tasks.base import CaptchaRequired

        raise CaptchaRequired()

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
    42: "Tướng chưa trang bị vũ khí phù hợp cho binh chủng này",
    43: "Điều quân vượt sức chứa thống lĩnh tối đa của tướng",
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


def _weighted_morale(n_cur: int, m_cur: float, x: int, m_in: float) -> float:
    """Tính sĩ khí trung bình có trọng số theo quân số khi nhận thêm x quân có sĩ khí m_in."""
    if n_cur + x <= 0:
        return 0.0
    if n_cur <= 0:
        return float(m_in)
    return (n_cur * m_cur + x * m_in) / (n_cur + x)


def _top_donor_points(pool_desc: list[tuple[float, int]], need: int) -> float:
    """Tổng điểm (quân số * sĩ khí) lớn nhất có thể lấy từ need quân tốt nhất trong pool."""
    rem = max(0, int(need))
    pts = 0.0
    for m_d, sup_d in pool_desc:
        if rem <= 0:
            break
        take = min(rem, sup_d)
        pts += take * m_d
        rem -= take
    return pts


def _tail_donor_points(rem_donors: dict[int, int], sim_morale: dict[int, float], need: int) -> float:
    """Tổng điểm (quân số * sĩ khí) của need quân thấp sĩ khí nhất còn lại trong pool."""
    rem = min(max(0, int(need)), sum(rem_donors.values()))
    pts = 0.0
    for d in sorted(rem_donors, key=lambda g: (sim_morale.get(g, 100.0), g)):
        if rem <= 0:
            break
        take = min(rem, rem_donors[d])
        pts += take * sim_morale.get(d, 100.0)
        rem -= take
    return pts


def _plan_branch_morale_transfers(
    donors: dict[int, int],
    recipients: dict[int, int],
    sim_troops: dict[int, int],
    sim_morale: dict[int, float],
    floor_cap: float,
) -> list[tuple[int, int, int]]:
    """Lập kế hoạch chuyển quân 1 nhịp (thừa -> thiếu) tối đa hóa sĩ khí thấp nhất toàn đội."""
    if not donors or not recipients:
        return []

    rem_d = {d: int(v) for d, v in donors.items() if v > 0}
    rem_r = {r: int(v) for r, v in recipients.items() if v > 0}
    if not rem_d or not rem_r:
        return []

    def _record_transfer(ledger: dict[tuple[int, int], int], d: int, r: int, take: int) -> None:
        if take <= 0:
            return
        ledger[(d, r)] = ledger.get((d, r), 0) + take
        rem_d[d] -= take
        if rem_d[d] <= 0:
            del rem_d[d]
        rem_r[r] -= take
        if rem_r[r] <= 0:
            del rem_r[r]
        n_r = sim_troops.get(r, 0)
        m_r = sim_morale.get(r, 0.0)
        sim_morale[r] = _weighted_morale(n_r, m_r, take, sim_morale.get(d, 100.0))
        sim_troops[r] = n_r + take
        sim_troops[d] = sim_troops.get(d, 0) - take

    # Fast path: khi tất cả tướng cho cùng sĩ khí -> ghép thừa lớn nhất với thiếu lớn nhất (ít request nhất)
    d_morales = [sim_morale.get(d, 100.0) for d in rem_d]
    if max(d_morales) - min(d_morales) <= 1e-9:
        ledger: dict[tuple[int, int], int] = {}
        while rem_d and rem_r:
            d = max(rem_d, key=lambda g: (rem_d[g], -g))
            r = max(rem_r, key=lambda g: (rem_r[g], -g))
            _record_transfer(ledger, d, r, min(rem_d[d], rem_r[r]))
        return [(d, r, amt) for (d, r), amt in ledger.items() if amt > 0]

    # Tìm sàn sĩ khí tối đa L* khả thi bằng tìm kiếm nhị phân
    total_sup = sum(rem_d.values())
    total_def = sum(rem_r.values())
    pool_desc = sorted(
        ((sim_morale.get(d, 100.0), sup) for d, sup in rem_d.items()),
        key=lambda x: -x[0],
    )

    def _feasible(cand_l: float) -> bool:
        reqs = []
        for r, d_r in rem_r.items():
            n_r = sim_troops.get(r, 0)
            m_r = sim_morale.get(r, 0.0)
            p_req = max(0.0, cand_l * (n_r + d_r) - n_r * m_r)
            reqs.append((p_req / d_r, p_req, d_r))
        reqs.sort(key=lambda x: -x[0])
        cum_d = 0
        cum_req = 0.0
        for _, p_req, d_r in reqs:
            cum_d += d_r
            cum_req += p_req
            sup_limit = cum_d if total_sup >= total_def else min(cum_d, total_sup)
            if cum_req > _top_donor_points(pool_desc, sup_limit) + 1e-6:
                return False
        return True

    lo, hi = 0.0, float(floor_cap)
    for _ in range(32):
        mid = 0.5 * (lo + hi)
        if _feasible(mid):
            lo = mid
        else:
            hi = mid
    l_star = lo

    ledger: dict[tuple[int, int], int] = {}

    # Pha A: Cứu các tướng nhận đang dưới sàn L* bằng phần quân sĩ khí cao nhất vừa đủ
    def _need_score(r_gid: int) -> float:
        d_r = rem_r[r_gid]
        n_r = sim_troops.get(r_gid, 0)
        m_r = sim_morale.get(r_gid, 0.0)
        return max(0.0, l_star * (n_r + d_r) - n_r * m_r) / d_r

    needy_order = sorted(rem_r.keys(), key=lambda g: (-_need_score(g), g))
    for r in needy_order:
        if r not in rem_r or _need_score(r) <= 1e-9:
            continue
        while r in rem_r and rem_d:
            d_need = rem_r[r]
            n_r = sim_troops.get(r, 0)
            m_r = sim_morale.get(r, 0.0)
            p_req = max(0.0, l_star * (n_r + d_need) - n_r * m_r)
            tail_take = min(d_need, sum(rem_d.values()))
            if tail_take <= 0:
                break
            tail_pts = _tail_donor_points(rem_d, sim_morale, tail_take)
            if p_req <= tail_pts + 1e-6:
                break
            d_hi = max(rem_d, key=lambda g: (sim_morale.get(g, 100.0), rem_d[g], -g))
            m_hi = sim_morale.get(d_hi, 100.0)
            tail_avg = tail_pts / tail_take
            if m_hi <= tail_avg + 1e-9:
                break
            x_needed = math.ceil((p_req - d_need * tail_avg - 1e-9) / (m_hi - tail_avg))
            take = min(d_need, rem_d[d_hi], max(1, x_needed))
            _record_transfer(ledger, d_hi, r, take)

    # Pha B: Ghép đồng hạng (sĩ khí cao -> cao) cho phần thừa/thiếu an toàn còn lại
    while rem_d and rem_r:
        d = max(rem_d, key=lambda g: (sim_morale.get(g, 100.0), rem_d[g], -g))
        r = max(
            rem_r,
            key=lambda g: (sim_morale.get(g, 0.0) if sim_troops.get(g, 0) > 0 else 0.0, rem_r[g], -g),
        )
        _record_transfer(ledger, d, r, min(rem_d[d], rem_r[r]))

    return [(d, r, amt) for (d, r), amt in ledger.items() if amt > 0]


class ArmyProvisioner:
    """Dịch vụ điều phối kiểm tra kho, chiêu mộ tân binh, biên chế lính và luyện sĩ khí."""

    def __init__(
        self,
        gateway: GatewayClient,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ):
        self.gateway = gateway
        self.sleep_fn = sleep_fn
        self.clock_fn = clock_fn
        self._comfort_next_allowed: dict[int, float] = {}
        self._waiting_population: dict[int, bool] = {}

    def _fetch_city_stock(self, city_id: int) -> tuple[Optional[int], dict[str, int]]:
        """Đọc số tân binh và tồn kho quân giới theo tên từ API /api/city/pagearmament."""
        resp = self.gateway.page_armament() or {}
        if resp.get("ret") != 0:
            return None, {}
        target_cid = int(city_id)
        for city_data in resp.get("list", []):
            if not isinstance(city_data, list) or len(city_data) <= 2:
                continue
            try:
                if int(city_data[0]) != target_cid:
                    continue
                recruits = int(city_data[2])
            except (ValueError, TypeError):
                continue
            equip_by_name: dict[str, int] = {}
            for group in city_data[3:]:
                if not isinstance(group, list):
                    continue
                for entry in group:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        try:
                            qty = int(entry[0])
                        except (ValueError, TypeError):
                            continue
                        name = str(entry[1] or "").strip()
                        if name:
                            equip_by_name[name] = max(equip_by_name.get(name, 0), qty)
            return recruits, equip_by_name
        return None, {}

    def check_recruits(self, city_id: int) -> Optional[int]:
        """Kiểm tra số lượng tân binh có sẵn trong kho của thành từ API /api/city/pagearmament."""
        recruits, _ = self._fetch_city_stock(city_id)
        return recruits

    def _estimate_equipment_caps(
        self,
        city_id: int,
        general_id: int,
        soldier_type: int,
        equip_by_name: dict[str, int],
    ) -> list[int]:
        """Ước lượng các mức quân tối đa theo quân giới hiện có trong kho Thành."""
        if not equip_by_name:
            return []
        snap = fetch_armament(self.gateway, int(general_id), int(city_id))
        if snap is None:
            return []
        scope_map = {1: snap.infantry, 2: snap.cavalry, 3: snap.bowman}
        eids = scope_map.get(soldier_type, ())
        slot_counts = Counter(e for e in eids if e > 0)
        if not slot_counts:
            return []
        for eid in slot_counts:
            if not snap.names.get(eid, "").strip():
                return []
        cap_unique = min(equip_by_name.get(snap.names[eid].strip(), 0) for eid in slot_counts)
        cap_per_slot = min(
            equip_by_name.get(snap.names[eid].strip(), 0) // cnt
            for eid, cnt in slot_counts.items()
        )
        caps: list[int] = []
        for c in (cap_unique, cap_per_slot):
            if c > 0 and c not in caps:
                caps.append(c)
        return caps

    def _provision_partial_by_equipment(
        self,
        cid: int,
        base_id: int,
        general_id: int,
        soldier_type: int,
        diff: int,
        *,
        auto_recruit: bool,
        comfort_attempted: Optional[set[int]],
        exhausted_cities: Optional[set[int]],
        apply_min_batch_guard: bool,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> Optional[list[tuple[int, int, bool, int]]]:
        """Biên chế từng phần tối đa theo lượng quân giới hiện có khi OPT.ashx?id=6 báo ret=42."""
        _, equip_stock = self._fetch_city_stock(cid)
        caps = [
            c
            for c in self._estimate_equipment_caps(cid, general_id, soldier_type, equip_stock)
            if 0 < c < diff
        ]
        if not caps:
            return None

        tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(soldier_type, "Quân")
        for cap in caps:
            payload = {
                "lGeneralID": str(general_id),
                "lSoldierType": str(soldier_type),
                "lAmount": str(cap),
                "tid": str(base_id),
                "_": "",
            }
            resp_eq = self.gateway.call("OPT.ashx", 6, payload) or {}
            ret_eq = resp_eq.get("ret", -1)
            _raise_if_captcha(ret_eq)
            if ret_eq == 0:
                remaining = diff - cap
                if on_log:
                    on_log(
                        f"   [Biên chế từng phần] 📦 Kho quân giới chỉ đủ {tname} +{cap}/{diff} (còn thiếu {remaining} do thiếu quân giới)"
                    )
                return [(soldier_type, cap, True, 0), (soldier_type, remaining, False, 42)]
            if ret_eq == 42:
                continue
            if ret_eq == 53 and auto_recruit:
                was_waiting = bool(self._waiting_population.get(cid, False))
                avail = self.check_recruits(cid)
                if avail is not None and 0 <= avail < cap:
                    known_avail = avail
                    missing = cap - avail
                else:
                    known_avail = 0
                    missing = cap
                bought, buy_ret = self.buy_recruits_partial(
                    cid,
                    missing,
                    auto_comfort=True,
                    comfort_attempted=comfort_attempted,
                    warehouse_avail=known_avail,
                    total_needed_for_branch=cap,
                    apply_min_batch_guard=apply_min_batch_guard,
                    on_log=on_log,
                )
                assignable = min(cap, known_avail + bought)
                if assignable <= 0:
                    return None
                if (
                    apply_min_batch_guard
                    and was_waiting
                    and bought == 0
                    and assignable < min(cap, MIN_PARTIAL_PROVISION_BATCH)
                ):
                    return None
                sub_payload = {
                    "lGeneralID": str(general_id),
                    "lSoldierType": str(soldier_type),
                    "lAmount": str(assignable),
                    "tid": str(base_id),
                    "_": "",
                }
                resp_sub = self.gateway.call("OPT.ashx", 6, sub_payload) or {}
                ret_sub = resp_sub.get("ret", -1)
                _raise_if_captcha(ret_sub)
                if ret_sub == 0:
                    remaining = diff - assignable
                    if assignable < cap and (buy_ret in POPULATION_SHORTAGE_RETS or buy_ret == 0):
                        rem_ret = buy_ret if buy_ret in POPULATION_SHORTAGE_RETS else 34
                        self._waiting_population[cid] = True
                        if exhausted_cities is not None:
                            exhausted_cities.add(cid)
                    else:
                        rem_ret = 42 if assignable == cap else buy_ret
                    if on_log:
                        on_log(
                            f"   [Biên chế từng phần] 📦 Đã biên chế {tname} +{assignable}/{diff} theo quân giới hiện có (còn thiếu {remaining})"
                        )
                    return [
                        (soldier_type, assignable, True, 0),
                        (soldier_type, remaining, False, rem_ret),
                    ]
                if ret_sub == 42:
                    continue
                return None
            return None
        return None

    def check_idle_population(self, city_id: int) -> Optional[int]:
        """Đọc số dân nhàn rỗi hiện có của Thành từ API /api/city/info (S58)."""
        resp = self.gateway.city_info(int(city_id)) or {}
        if not isinstance(resp, dict):
            return None
        ret = resp.get("ret", 0)
        _raise_if_captcha(ret)
        if ret != 0:
            return None
        data = (
            resp.get("data")
            if isinstance(resp.get("data"), dict) and resp.get("data")
            else resp
        )
        if "m_lpopulation_idle_man" in data:
            try:
                return max(0, int(data["m_lpopulation_idle_man"]))
            except (ValueError, TypeError):
                return None
        pop = data.get("population")
        if isinstance(pop, list) and len(pop) > 4:
            try:
                return max(0, int(pop[4]))
            except (ValueError, TypeError):
                return None
        return None

    def comfort_population(
        self,
        city_id: int,
        ltype: int = 4,
        respect_cooldown: bool = False,
    ) -> tuple[bool, int]:
        """Gọi API an dân / tăng nhân khẩu (OPT.ashx?id=4). lType=4: Tăng nhân khẩu."""
        cid = int(city_id)
        if respect_cooldown and int(ltype) == 4 and cid in self._comfort_next_allowed:
            if self.clock_fn() < self._comfort_next_allowed[cid]:
                return False, 55
        payload = {
            "lType": str(ltype),
            "tid": str(cid),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 4, payload) or {}
        ret = resp.get("ret", -1)
        _raise_if_captcha(ret)
        if int(ltype) == 4:
            now = self.clock_fn()
            if ret == 0:
                self._comfort_next_allowed[cid] = now + POPULATION_COMFORT_SUCCESS_COOLDOWN
            elif ret == 55:
                self._comfort_next_allowed[cid] = now + POPULATION_COMFORT_RETRY_COOLDOWN
        return ret == 0, ret

    def _buy_partial_from_idle_pop(
        self,
        cid: int,
        amount: int,
        *,
        idle_pop: int,
        warehouse_avail: int,
        need_total: int,
        apply_min_batch_guard: bool,
        guard_active: bool,
        just_comforted: bool,
        comfort_on_cd: bool,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, int]:
        """Mua tối đa theo dân nhàn rỗi hiện có và áp dụng ngưỡng gộp chống nhỏ giọt."""
        if idle_pop <= 0:
            return 0, 34
        to_buy = min(amount, idle_pop)
        if (
            apply_min_batch_guard
            and guard_active
            and to_buy < amount
            and (warehouse_avail + to_buy)
            < min(need_total, MIN_PARTIAL_PROVISION_BATCH)
        ):
            return 0, 34
        resp_part = (
            self.gateway.call(
                "OPT.ashx", 41, {"lAmount": str(to_buy), "tid": str(cid), "_": ""}
            )
            or {}
        )
        ret_part = resp_part.get("ret", -1)
        _raise_if_captcha(ret_part)
        if ret_part == 0:
            if to_buy >= amount:
                if just_comforted or (
                    not comfort_on_cd and amount >= MIN_PARTIAL_PROVISION_BATCH
                ):
                    self._waiting_population[cid] = False
                return to_buy, 0
            if on_log:
                on_log(
                    f"   [Chiêu mộ] 📦 Dân chưa đủ ({to_buy}/{amount}), đã chiêu mộ hết {to_buy} dân nhàn rỗi!"
                )
            return to_buy, 34
        return 0, ret_part

    def buy_recruits_partial(
        self,
        city_id: int,
        amount: int,
        *,
        auto_comfort: bool = True,
        comfort_attempted: Optional[set[int]] = None,
        warehouse_avail: int = 0,
        total_needed_for_branch: Optional[int] = None,
        apply_min_batch_guard: bool = True,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, int]:
        """Chiêu mộ tân binh (OPT.ashx?id=41), tự Tăng Nhân Khẩu và vét 100% dân nhàn rỗi nếu thiếu.

        Trả về (bought_amount, status_ret):
          - Mua đủ `amount`: (amount, 0)
          - Thiếu dân nhưng mua được một phần `to_buy < amount`: (to_buy, 34)
          - Không mua được do thiếu dân / lỗi khác: (0, ret)
        """
        if amount <= 0:
            return 0, 0

        cid = int(city_id)
        need_total = (
            total_needed_for_branch if total_needed_for_branch is not None else amount
        )
        was_waiting = bool(self._waiting_population.get(cid, False))
        comfort_on_cd = (
            cid in self._comfort_next_allowed
            and self.clock_fn() < self._comfort_next_allowed[cid]
        )

        # Khi đang chờ hồi Quan Phủ giữa các chu kỳ, đọc dân nhàn rỗi trước để tránh spam OPT.ashx?id=41 với số quá lớn
        if was_waiting and (
            comfort_on_cd
            or not auto_comfort
            or (comfort_attempted is not None and cid in comfort_attempted)
        ):
            idle_pop = self.check_idle_population(cid)
            if idle_pop is not None and idle_pop < amount:
                return self._buy_partial_from_idle_pop(
                    cid,
                    amount,
                    idle_pop=idle_pop,
                    warehouse_avail=warehouse_avail,
                    need_total=need_total,
                    apply_min_batch_guard=apply_min_batch_guard,
                    guard_active=True,
                    just_comforted=False,
                    comfort_on_cd=comfort_on_cd,
                    on_log=on_log,
                )

        payload = {
            "lAmount": str(amount),
            "tid": str(cid),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 41, payload) or {}
        ret = resp.get("ret", -1)
        _raise_if_captcha(ret)
        if ret == 0:
            if not was_waiting or (
                not comfort_on_cd and amount >= MIN_PARTIAL_PROVISION_BATCH
            ):
                self._waiting_population[cid] = False
            return amount, 0
        if ret != 34:
            return 0, ret

        just_comforted = False
        if auto_comfort and (comfort_attempted is None or cid not in comfort_attempted):
            if comfort_attempted is not None:
                comfort_attempted.add(cid)
            c_ok, c_ret = self.comfort_population(cid, ltype=4, respect_cooldown=True)
            if c_ok:
                just_comforted = True
                if on_log:
                    on_log(
                        f"   [Quan Phủ] ✅ Tăng Nhân Khẩu thành công tại Thành {cid}, thử chiêu mộ lại {amount} tân binh..."
                    )
                self.sleep_fn(1.0)
                resp = self.gateway.call("OPT.ashx", 41, payload) or {}
                ret = resp.get("ret", -1)
                _raise_if_captcha(ret)
                if ret == 0:
                    self._waiting_population[cid] = False
                    return amount, 0
                if ret != 34:
                    return 0, ret
            elif on_log:
                err_desc = ERROR_MESSAGES.get(c_ret, f"Mã lỗi: {c_ret}")
                on_log(
                    f"   [Quan Phủ] ⏳ Không thể Tăng Nhân Khẩu ({err_desc}), kiểm tra dân nhàn rỗi hiện có..."
                )

        # Fallback Biên Chế Từng Phần: chiêu mộ hết 100% dân nhàn rỗi đang có
        self._waiting_population[cid] = True
        idle_pop = self.check_idle_population(cid)
        if idle_pop is None:
            return 0, 34
        return self._buy_partial_from_idle_pop(
            cid,
            amount,
            idle_pop=idle_pop,
            warehouse_avail=warehouse_avail,
            need_total=need_total,
            apply_min_batch_guard=apply_min_batch_guard,
            guard_active=was_waiting and not just_comforted,
            just_comforted=just_comforted,
            comfort_on_cd=comfort_on_cd,
            on_log=on_log,
        )

    def buy_recruits(
        self,
        city_id: int,
        amount: int,
        auto_comfort: bool = True,
        *,
        comfort_attempted: Optional[set[int]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, int]:
        """Chiêu mộ tân binh bằng API OPT.ashx?id=41."""
        if amount <= 0:
            return True, 0
        bought, ret = self.buy_recruits_partial(
            city_id,
            amount,
            auto_comfort=auto_comfort,
            comfort_attempted=comfort_attempted,
            apply_min_batch_guard=True,
            on_log=on_log,
        )
        return bought >= amount and ret == 0, ret

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
        *,
        comfort_attempted: Optional[set[int]] = None,
        exhausted_cities: Optional[set[int]] = None,
        apply_min_batch_guard: bool = True,
    ) -> list[tuple[int, int, bool, int]]:
        """Thiết lập biên chế quân cho tướng bằng API OPT.ashx?id=6.

        Chỉ bổ sung phần thiếu hụt (diff > 0), không tháo phần quân vượt mức (diff <= 0).
        Nếu thiếu tân binh (ret=53) và base_id > 0 (Thành) và auto_recruit=True:
            Tự động chiêu mộ tân binh (API id=41), gọi Tăng Nhân Khẩu (id=4, lType=4) nếu cần,
            và nếu dân vẫn chưa đủ thì Biên Chế Từng Phần hết tân binh/dân nhàn rỗi hiện có.
        """
        current_inf = current_army.infantry if current_army else 0
        current_cav = current_army.cavalry if current_army else 0
        current_arc = current_army.archers if current_army else 0

        adjustments = [
            (1, target_army.infantry - current_inf),
            (2, target_army.cavalry - current_cav),
            (3, target_army.archers - current_arc),
        ]

        cid = int(base_id)
        results = []
        for soldier_type, diff in adjustments:
            if diff <= 0:
                continue

            if (
                auto_recruit
                and cid > 0
                and exhausted_cities is not None
                and cid in exhausted_cities
            ):
                results.append((soldier_type, diff, False, 34))
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
            _raise_if_captcha(ret)

            if ret == 0:
                results.append((soldier_type, diff, True, 0))
                continue

            if ret == 42 and cid > 0:
                eq_res = self._provision_partial_by_equipment(
                    cid,
                    base_id,
                    general_id,
                    soldier_type,
                    diff,
                    auto_recruit=auto_recruit,
                    comfort_attempted=comfort_attempted,
                    exhausted_cities=exhausted_cities,
                    apply_min_batch_guard=apply_min_batch_guard,
                    on_log=on_log,
                )
                if eq_res is not None:
                    results.extend(eq_res)
                    continue

            # Nếu tân binh không đủ để biên chế (ret=53) và căn cứ là Thành (ID > 0)
            if ret == 53 and auto_recruit and cid > 0:
                tname = {1: "Bộ", 2: "Kỵ", 3: "Cung"}.get(soldier_type, "Quân")
                was_waiting = bool(self._waiting_population.get(cid, False))
                avail = self.check_recruits(cid)
                if avail is not None and 0 <= avail < diff:
                    known_avail = avail
                    missing = diff - avail
                else:
                    known_avail = 0
                    missing = diff

                if on_log:
                    on_log(
                        f"   [Chiêu mộ] Tân binh không đủ để bổ sung {tname} +{diff}, tự động chiêu mộ..."
                    )
                bought, buy_ret = self.buy_recruits_partial(
                    cid,
                    missing,
                    auto_comfort=True,
                    comfort_attempted=comfort_attempted,
                    warehouse_avail=known_avail,
                    total_needed_for_branch=diff,
                    apply_min_batch_guard=apply_min_batch_guard,
                    on_log=on_log,
                )
                total_avail = known_avail + bought

                if bought >= missing and buy_ret == 0:
                    if on_log:
                        on_log(
                            f"   [Chiêu mộ] ✅ Chiêu mộ thành công {missing} tân binh, tiếp tục biên chế..."
                        )
                    resp2 = self.gateway.call("OPT.ashx", 6, payload) or {}
                    ret2 = resp2.get("ret", -1)
                    _raise_if_captcha(ret2)
                    if ret2 == 42:
                        eq_res = self._provision_partial_by_equipment(
                            cid,
                            base_id,
                            general_id,
                            soldier_type,
                            diff,
                            auto_recruit=auto_recruit,
                            comfort_attempted=comfort_attempted,
                            exhausted_cities=exhausted_cities,
                            apply_min_batch_guard=apply_min_batch_guard,
                            on_log=on_log,
                        )
                        if eq_res is not None:
                            results.extend(eq_res)
                            continue
                    results.append((soldier_type, diff, ret2 == 0, ret2))
                    continue

                assignable = min(diff, total_avail)
                if assignable > 0:
                    if (
                        apply_min_batch_guard
                        and was_waiting
                        and bought == 0
                        and assignable < min(diff, MIN_PARTIAL_PROVISION_BATCH)
                    ):
                        shortage_ret = buy_ret if buy_ret != 0 else 34
                        results.append((soldier_type, diff, False, shortage_ret))
                        continue

                    part_payload = {
                        "lGeneralID": str(general_id),
                        "lSoldierType": str(soldier_type),
                        "lAmount": str(assignable),
                        "tid": str(base_id),
                        "_": "",
                    }
                    resp_part = self.gateway.call("OPT.ashx", 6, part_payload) or {}
                    ret_part = resp_part.get("ret", -1)
                    _raise_if_captcha(ret_part)
                    if ret_part == 0:
                        remaining = diff - assignable
                        if remaining > 0:
                            is_pop_shortage = (
                                buy_ret in POPULATION_SHORTAGE_RETS or buy_ret == 0
                            )
                            if is_pop_shortage:
                                shortage_ret = (
                                    buy_ret
                                    if buy_ret in POPULATION_SHORTAGE_RETS
                                    else 34
                                )
                                self._waiting_population[cid] = True
                                if exhausted_cities is not None:
                                    exhausted_cities.add(cid)
                                if on_log:
                                    on_log(
                                        f"   [Biên chế từng phần] 📦 Đã biên chế {tname} +{assignable}/{diff} (còn thiếu {remaining}, luyện sĩ khí trước và chờ hồi Tăng Nhân Khẩu)"
                                    )
                            else:
                                shortage_ret = buy_ret
                                err_desc = ERROR_MESSAGES.get(
                                    shortage_ret, f"Mã lỗi: {shortage_ret}"
                                )
                                if on_log:
                                    on_log(
                                        f"   [Biên chế từng phần] 📦 Đã biên chế {tname} +{assignable}/{diff} (còn thiếu {remaining}: {err_desc})"
                                    )
                            results.append((soldier_type, assignable, True, 0))
                            results.append(
                                (soldier_type, remaining, False, shortage_ret)
                            )
                        else:
                            if on_log:
                                on_log(
                                    f"   [Biên chế] ✅ Đã biên chế {tname} +{assignable}"
                                )
                            results.append((soldier_type, assignable, True, 0))
                        continue
                    results.append((soldier_type, diff, False, ret_part))
                    continue

                shortage_ret = buy_ret if buy_ret != 0 else 53
                if shortage_ret in POPULATION_SHORTAGE_RETS:
                    self._waiting_population[cid] = True
                    if exhausted_cities is not None:
                        exhausted_cities.add(cid)
                err_desc = ERROR_MESSAGES.get(shortage_ret, f"Mã lỗi: {shortage_ret}")
                if on_log:
                    on_log(f"   [Chiêu mộ] ❌ Chiêu mộ thất bại ({err_desc})")
                results.append((soldier_type, diff, False, shortage_ret))
                continue

            results.append((soldier_type, diff, False, ret))
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

    def transfer_troops_between_generals(
        self,
        base_id: int,
        from_general_id: int,
        to_general_id: int,
        infantry: int = 0,
        cavalry: int = 0,
        archers: int = 0,
        mangonel: int = 0,
    ) -> tuple[bool, int]:
        """Điều động quân trực tiếp giữa 2 võ tướng qua Binh trường (OPT.ashx?id=39)."""
        from_gid = int(from_general_id)
        to_gid = int(to_general_id)
        inf = int(infantry)
        cav = int(cavalry)
        arc = int(archers)
        catapult = int(mangonel)

        if from_gid == to_gid or (inf == 0 and cav == 0 and arc == 0 and catapult == 0):
            return True, 0

        payload = {
            "lFromGeneralID": str(from_gid),
            "lToGeneralID": str(to_gid),
            "infantry": str(inf),
            "cavalry": str(cav),
            "bowman": str(arc),
            "mangonel": str(catapult),
            "tid": str(int(base_id)),
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 39, payload) or {}
        ret = resp.get("ret", -1)
        _raise_if_captcha(ret)
        return ret == 0, ret

    def balance_troops(
        self,
        base_id: int,
        general_ids: list[int],
        current_armies: dict[int, Optional[Army]],
        base_gens: Optional[dict[int, Any]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> tuple[dict[int, Army], bool]:
        """San đều quân hiện có theo từng binh chủng giữa các võ tướng rảnh rỗi (OPT.ashx?id=39)."""
        unique_gids: list[int] = []
        seen: set[int] = set()
        for gid in general_ids:
            igid = int(gid)
            if igid not in seen:
                seen.add(igid)
                unique_gids.append(igid)

        working: dict[int, Army] = {}
        for gid in unique_gids:
            army = current_armies.get(gid)
            working[gid] = (
                Army(int(army.infantry), int(army.cavalry), int(army.archers))
                if army is not None
                else Army(0, 0, 0)
            )

        if base_gens is not None:
            eligible = [
                gid
                for gid in unique_gids
                if gid in base_gens
                and getattr(base_gens[gid], "role", "vo") == "vo"
                and getattr(base_gens[gid], "status", 0) == 0
                and getattr(base_gens[gid], "upgrading_time", 0) <= 0
            ]
        else:
            eligible = list(unique_gids)

        if len(eligible) < 2:
            return working, False

        branches = (("infantry", "Bộ"), ("cavalry", "Kỵ"), ("archers", "Cung"))
        working_morale: dict[int, float] = {
            gid: (
                float(getattr(base_gens[gid], "morale", 100))
                if (base_gens is not None and gid in base_gens)
                else 100.0
            )
            for gid in eligible
        }
        surplus: dict[str, dict[int, int]] = {attr: {} for attr, _ in branches}
        deficit: dict[str, dict[int, int]] = {attr: {} for attr, _ in branches}

        for attr, _ in branches:
            counts = [getattr(working[gid], attr) for gid in eligible]
            if max(counts) - min(counts) <= 1:
                continue
            total = sum(counts)
            base_share = total // len(eligible)
            rem = total % len(eligible)
            ranked = sorted(
                range(len(eligible)),
                key=lambda idx: (
                    -getattr(working[eligible[idx]], attr),
                    -working_morale.get(eligible[idx], 100.0),
                    idx,
                ),
            )
            targets: dict[int, int] = {}
            for rank_pos, orig_idx in enumerate(ranked):
                gid = eligible[orig_idx]
                targets[gid] = base_share + (1 if rank_pos < rem else 0)
            for gid in eligible:
                cur_val = getattr(working[gid], attr)
                tgt_val = targets[gid]
                if cur_val > tgt_val:
                    surplus[attr][gid] = cur_val - tgt_val
                elif tgt_val > cur_val:
                    deficit[attr][gid] = tgt_val - cur_val

        blocked: dict[str, set[int]] = {attr: set() for attr, _ in branches}
        transferred = False

        def _gen_name(gid: int) -> str:
            if base_gens and gid in base_gens:
                return getattr(base_gens[gid], "name", str(gid)) or str(gid)
            return str(gid)

        def _apply_transfer(d: int, r: int, d_inf: int, d_cav: int, d_arc: int) -> None:
            wd = working[d]
            wr = working[r]
            prev_r_total = wr.total
            moved_total = d_inf + d_cav + d_arc
            if moved_total > 0:
                working_morale[r] = _weighted_morale(
                    prev_r_total,
                    working_morale.get(r, 0.0),
                    moved_total,
                    working_morale.get(d, 100.0),
                )
            working[d] = Army(wd.infantry - d_inf, wd.cavalry - d_cav, wd.archers - d_arc)
            working[r] = Army(wr.infantry + d_inf, wr.cavalry + d_cav, wr.archers + d_arc)
            deltas = {"infantry": d_inf, "cavalry": d_cav, "archers": d_arc}
            parts = []
            for attr, label in branches:
                amt = deltas[attr]
                if amt <= 0:
                    continue
                parts.append(f"{label} {amt}")
                if d in surplus[attr]:
                    rem_s = surplus[attr][d] - amt
                    if rem_s > 0:
                        surplus[attr][d] = rem_s
                    else:
                        del surplus[attr][d]
                if r in deficit[attr]:
                    rem_d = deficit[attr][r] - amt
                    if rem_d > 0:
                        deficit[attr][r] = rem_d
                    else:
                        del deficit[attr][r]
            if on_log and parts:
                on_log(
                    f"⚖️ [San đều quân] Chuyển từ {_gen_name(d)} → {_gen_name(r)}: {', '.join(parts)} ✅"
                )

        def _log_fail(label: str, amt: int, d: int, r: int, ret_code: int) -> None:
            if not on_log:
                return
            err_desc = ERROR_MESSAGES.get(ret_code, f"Mã lỗi: {ret_code}")
            on_log(
                f"⚠️ [San đều quân] Chuyển {label} {amt} từ {_gen_name(d)} → {_gen_name(r)} "
                f"thất bại ({err_desc}), bỏ qua tướng nhận."
            )

        max_iters = len(eligible) * len(eligible) * 3 + 10
        for _ in range(max_iters):
            fixed_morales: list[float] = []
            for g in eligible:
                has_active_deficit = any(
                    deficit[attr].get(g, 0) > 0 and g not in blocked[attr]
                    for attr, _ in branches
                )
                post_surplus_total = working[g].total - sum(surplus[attr].get(g, 0) for attr, _ in branches)
                if not has_active_deficit and post_surplus_total > 0:
                    fixed_morales.append(working_morale.get(g, 100.0))
            floor_cap = min(fixed_morales) if fixed_morales else 100.0

            sim_troops = {g: working[g].total for g in eligible}
            sim_morale = dict(working_morale)
            pair_amounts: dict[tuple[int, int], list[int]] = {}
            for b_idx, (attr, _) in enumerate(branches):
                active_donors = {g: amt for g, amt in surplus[attr].items() if amt > 0}
                active_recips = {
                    g: amt
                    for g, amt in deficit[attr].items()
                    if amt > 0 and g not in blocked[attr]
                }
                for d, r, amt in _plan_branch_morale_transfers(
                    active_donors, active_recips, sim_troops, sim_morale, floor_cap
                ):
                    slot = pair_amounts.setdefault((d, r), [0, 0, 0])
                    slot[b_idx] += amt

            if not pair_amounts:
                break

            replan_needed = False
            for (d, r), (d_inf, d_cav, d_arc) in pair_amounts.items():
                amounts = {"infantry": d_inf, "cavalry": d_cav, "archers": d_arc}
                active_branches = [attr for attr, _ in branches if amounts[attr] > 0]
                if not active_branches:
                    continue

                succ, ret = self.transfer_troops_between_generals(
                    base_id=base_id,
                    from_general_id=d,
                    to_general_id=r,
                    infantry=d_inf,
                    cavalry=d_cav,
                    archers=d_arc,
                )
                if succ:
                    _apply_transfer(d, r, d_inf, d_cav, d_arc)
                    transferred = True
                    continue

                if len(active_branches) > 1:
                    for attr in active_branches:
                        amt = amounts[attr]
                        s_succ, s_ret = self.transfer_troops_between_generals(
                            base_id=base_id,
                            from_general_id=d,
                            to_general_id=r,
                            infantry=amt if attr == "infantry" else 0,
                            cavalry=amt if attr == "cavalry" else 0,
                            archers=amt if attr == "archers" else 0,
                        )
                        if s_succ:
                            _apply_transfer(
                                d,
                                r,
                                amt if attr == "infantry" else 0,
                                amt if attr == "cavalry" else 0,
                                amt if attr == "archers" else 0,
                            )
                            transferred = True
                        else:
                            blocked[attr].add(r)
                            label = dict(branches)[attr]
                            _log_fail(label, amt, d, r, s_ret)
                else:
                    attr = active_branches[0]
                    blocked[attr].add(r)
                    label = dict(branches)[attr]
                    _log_fail(label, amounts[attr], d, r, ret)
                replan_needed = True
                break

            if not replan_needed:
                break

        return working, transferred

    def provision_camp_generals_with_parent_city(
        self,
        camp_id: int,
        parent_city_id: int,
        general_ids: list[int],
        target_army: TargetArmy,
        current_armies: Optional[dict[int, Optional[Army]]] = None,
        current_morales: Optional[dict[int, int]] = None,
        min_morale: int = 95,
        on_log: Optional[Callable[[str], None]] = None,
        apply_min_batch_guard: bool = True,
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
        comfort_attempted: set[int] = set()
        exhausted_cities: set[int] = set()

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
                    comfort_attempted=comfort_attempted,
                    exhausted_cities=exhausted_cities,
                    apply_min_batch_guard=apply_min_batch_guard,
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

