"""Lõi tự động mua và bán tài nguyên qua Chợ cho Server 58+ (dùng chung cho Desktop & Web/Headless).

API đã kiểm chứng trên Server 58 (`sg58.dipan.com`, `adapter.js` `_p_marketPassthrough` + REST):
- Nhận diện Thành có Chợ qua REST `GET /api/building/list` (`m_lgid in {11 (Chợ), 64 (Tập Thị)}`, `m_llevel > 0`),
  kèm fallback `City.ashx?id=5` cho gateway/mock đời cũ.
- Đọc vàng & tài nguyên qua REST `/api/city/info` và `/api/resource/info`.
- Đọc top 10 đơn bán rẻ nhất trên sàn: `Common.ashx?id=38` (`stab=1`, `type=1..4`, `tid`).
  Lưu ý: Trả về boolean `False` khi sàn trống, và vẫn trả danh sách ngay cả khi Thành không có Chợ.
- Đọc giá trung bình hôm qua: `OPT.ashx?id=29` (`type=1..4`), trả số nguyên thô (vd `480` hoặc `-1`).
- Mua ngay trên sàn: `OPT.ashx?id=9` (`tid`, `buyinprice`, `count`, `buyincount`, `seqno`, `seller`,
  `countprice` = đơn giá, `type3`). Lưu ý: `ret=73` trên sàn Chợ là đơn hàng đang bận (`RET_ORDER_BUSY`),
  **không phải** Captcha (`ret=110`).
- Treo đơn bán trên sàn: `OPT.ashx?id=49` (`tid`, `type1`, `sellcount1`, `sellprice1`,
  `countprice1` = tổng giá).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import time
from typing import Any, Callable, Optional

from .gateway import gateway_city_context
from .tasks.base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired
from .tasks.building import RET_CITY_NOT_FOUND, switch_city_verified

MARKET_BUILDING_GIDS = frozenset({11, 64})
UNIT_DAN = 1000

RESOURCE_KEY_TO_MARKET_TYPE: dict[str, int] = {
    "food": 1,
    "wood": 2,
    "stone": 3,
    "iron": 4,
}
RESOURCE_VI_NAMES: dict[str, str] = {
    "wood": "Gỗ",
    "iron": "Sắt",
    "stone": "Đá",
    "food": "Thực",
}
RESOURCE_BASE_PRICE: dict[int, int] = {
    1: 120,
    2: 480,
    3: 480,
    4: 480,
}
RESOURCE_CHECK_ORDER: tuple[str, ...] = ("wood", "iron", "stone", "food")
BOX_OPTION_IDS: tuple[int, ...] = (1, 6, 11, 16, 24, 35)

RET_ORDER_GONE = 26
RET_INSUFFICIENT_RESOURCE = 32
RET_INSUFFICIENT_GOLD = 33
RET_ORDER_BUSY = 73
RET_PRICE_OUT_OF_RANGE = 74
RET_NO_MARKET = 232
RET_MAX_SELL_ORDERS = 249
RET_INSUFFICIENT_GOLD_ALT = 1217

MARKET_ERROR_MESSAGES: dict[int, str] = {
    RET_ORDER_GONE: "Đơn treo bán không còn tồn tại",
    RET_INSUFFICIENT_RESOURCE: "Kho tài nguyên không đủ",
    RET_INSUFFICIENT_GOLD: "Không đủ Vàng (đồng tiền)",
    RET_INSUFFICIENT_GOLD_ALT: "Không đủ Vàng (đồng tiền)",
    RET_ORDER_BUSY: "Đơn hàng đang được xử lý",
    RET_PRICE_OUT_OF_RANGE: "Giá treo vượt ngoài biên độ cho phép",
    RET_NO_MARKET: "Thành chưa xây Chợ/Tập Thị",
    RET_MAX_SELL_ORDERS: "Đã đạt giới hạn số đơn treo bán tối đa",
}

_CST_TZ = timezone(timedelta(hours=8))


def _to_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            if not cleaned:
                return default
            return int(float(cleaned))
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _check_market_captcha_ret(ret: int) -> None:
    """Trên endpoint Chợ, `ret=73` là `RET_ORDER_BUSY` (đang giao dịch), chỉ `110` là Captcha."""
    if ret == 110:
        raise CaptchaRequired()


def _check_chest_captcha_ret(ret: int) -> None:
    if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
        raise CaptchaRequired()


def parse_sell_threshold_pct(raw: Any, default: float = 90.0) -> float:
    """Chuẩn hóa ngưỡng bán (%) thành số thực nằm trong [1.0, 100.0]."""
    if raw is None or isinstance(raw, bool):
        return default
    try:
        s = str(raw).replace("%", "").replace(",", ".").strip()
        if not s:
            return default
        val = float(s)
    except (TypeError, ValueError):
        return default
    if math.isnan(val) or math.isinf(val) or val <= 0.0:
        return default
    return max(1.0, min(100.0, val))


@dataclass(frozen=True)
class MarketListing:
    """Một đơn rao bán tài nguyên trên sàn Chợ."""

    seqno: int
    seller: int
    count_dan: int
    price: int


@dataclass
class ResourceMonitorSettings:
    """Thiết lập cấu hình giám sát tài nguyên & giao dịch Chợ cho một chu kỳ."""

    gold_threshold: int
    buy_pcts: dict[str, float]
    gold_box_id: int
    tn_box_id: int
    prefer_market_buy: bool = False
    auto_sell_resource: bool = False
    sell_threshold_pct: float = 90.0


class CityMarketCache:
    """Cache nhận diện Thành có Chợ (`gid in {11, 64}`) theo TTL."""

    def __init__(self, ttl_seconds: float = 300.0):
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self._cache: dict[int, tuple[bool, float]] = {}

    def invalidate(self, city_id: int) -> None:
        self._cache.pop(int(city_id), None)

    def mark_no_market(self, city_id: int) -> None:
        self._cache[int(city_id)] = (False, time.monotonic())

    def has_market(self, gateway: Any, city_id: int) -> bool:
        """Kiểm tra Căn Cứ có Chợ/Tập Thị cấp >= 1 hay không (Doanh trại luôn False)."""
        cid = int(city_id)
        if cid <= 0:
            return False

        now = time.monotonic()
        cached = self._cache.get(cid)
        if cached is not None and (now - cached[1]) < self.ttl_seconds:
            return cached[0]

        bld_list_fn = getattr(gateway, "building_list", None)
        if callable(bld_list_fn):
            resp = bld_list_fn(cid)
        else:
            resp = gateway.call("City.ashx", 5, {"tid": str(cid), "_": ""})

        if not isinstance(resp, dict) or not resp:
            return False

        ret = _to_int(resp.get("ret"), RET_OK)
        _check_chest_captcha_ret(ret)
        if ret != RET_OK:
            return False

        raw_buildings = None
        for key in ("items", "infos", "buildings", "build"):
            if key in resp and resp[key] is not None:
                raw_buildings = resp[key]
                break
        if raw_buildings is None or not isinstance(raw_buildings, (list, tuple, dict)):
            return False

        items = raw_buildings.values() if isinstance(raw_buildings, dict) else raw_buildings
        has_mkt = False
        for item in items:
            if isinstance(item, dict):
                gid = _to_int(item.get("m_lgid", item.get("gid", 0)))
                lvl = _to_int(item.get("m_llevel", item.get("level", 0)))
            elif isinstance(item, (list, tuple)) and len(item) >= 4:
                gid = _to_int(item[1])
                lvl = _to_int(item[3])
            else:
                continue
            if gid in MARKET_BUILDING_GIDS and lvl > 0:
                has_mkt = True
                break

        self._cache[cid] = (has_mkt, now)
        return has_mkt


def compute_price_bounds(
    res_type: int,
    yesterday_avg: Optional[int],
    now_cst: Optional[datetime] = None,
) -> tuple[int, int]:
    """Tính biên độ giá treo bán hợp lệ (kết hợp ±10%/±5% giá TB hôm qua và trần/sàn giá gốc)."""
    base = RESOURCE_BASE_PRICE.get(int(res_type), 480)
    base_lo = base // 2
    base_hi = base * 2

    if yesterday_avg is None or yesterday_avg <= 0:
        return base_lo, base_hi

    if now_cst is None:
        cst = datetime.now(_CST_TZ)
    elif now_cst.tzinfo is not None:
        cst = now_cst.astimezone(_CST_TZ)
    else:
        cst = now_cst

    band_pct = 0.05 if 0 <= cst.hour < 8 else 0.10
    y_lo = math.ceil(yesterday_avg * (1.0 - band_pct))
    y_hi = math.floor(yesterday_avg * (1.0 + band_pct))

    lo = max(base_lo, y_lo)
    hi = min(base_hi, y_hi)
    if lo > hi:
        clamped = max(base_lo, min(base_hi, int(yesterday_avg)))
        return clamped, clamped
    return lo, hi


def choose_sell_price(
    res_type: int,
    listings: list[MarketListing],
    yesterday_avg: Optional[int],
    now_cst: Optional[datetime] = None,
) -> int:
    """Chọn giá treo bán khớp nhanh theo đơn rẻ nhất trên sàn, kẹp trong biên độ hợp lệ."""
    lo, hi = compute_price_bounds(res_type, yesterday_avg, now_cst=now_cst)
    if listings:
        target = min(item.price for item in listings)
    elif yesterday_avg is not None and yesterday_avg > 0:
        target = int(yesterday_avg)
    else:
        target = RESOURCE_BASE_PRICE.get(int(res_type), 480)
    return max(lo, min(hi, int(target)))


def fetch_market_listings(gateway: Any, city_id: int, res_type: int) -> list[MarketListing]:
    """Đọc top 10 đơn bán rẻ nhất trên sàn Chợ (`Common.ashx?id=38`, `stab=1`)."""
    resp = gateway.call(
        "Common.ashx",
        38,
        {"stab": "1", "type": str(int(res_type)), "tid": str(int(city_id)), "_": ""},
    )
    if not isinstance(resp, dict):
        return []

    ret = _to_int(resp.get("ret"), RET_OK)
    _check_market_captcha_ret(ret)
    if ret != RET_OK:
        return []

    raw_infos = resp.get("infos")
    if not isinstance(raw_infos, list):
        return []

    listings: list[MarketListing] = []
    for entry in raw_infos:
        if not isinstance(entry, dict):
            continue
        seqno = _to_int(entry.get("seqno"))
        seller = _to_int(entry.get("seller"))
        count_dan = _to_int(entry.get("count"))
        price = _to_int(entry.get("price"))
        if seqno > 0 and count_dan > 0 and price > 0:
            listings.append(
                MarketListing(seqno=seqno, seller=seller, count_dan=count_dan, price=price)
            )
    listings.sort(key=lambda item: (item.price, item.seqno))
    return listings


def fetch_yesterday_avg_price(gateway: Any, res_type: int) -> Optional[int]:
    """Đọc giá trung bình hôm qua của một loại tài nguyên (`OPT.ashx?id=29`)."""
    resp = gateway.call("OPT.ashx", 29, {"type": str(int(res_type)), "_": ""})
    if isinstance(resp, dict):
        ret = _to_int(resp.get("ret"), RET_OK)
        _check_market_captcha_ret(ret)
        raw_price = resp.get("price", resp.get("avg"))
        if raw_price is None:
            return None
        val = _to_int(raw_price, 0)
        return val if val > 0 else None
    val = _to_int(resp, 0)
    return val if val > 0 else None


def buy_market_order(
    gateway: Any,
    city_id: int,
    res_type: int,
    listing: MarketListing,
    count_dan: int,
) -> tuple[bool, int]:
    """Mua `count_dan` đản từ một đơn bán trên sàn (`OPT.ashx?id=9`)."""
    qty = int(count_dan)
    if qty <= 0:
        return False, -1

    payload = {
        "tid": str(int(city_id)),
        "buyinprice": str(int(listing.price)),
        "count": str(qty),
        "buyincount": str(int(listing.count_dan)),
        "seqno": str(int(listing.seqno)),
        "seller": str(int(listing.seller)),
        "countprice": str(int(listing.price)),
        "type3": str(int(res_type)),
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 9, payload)
    if not isinstance(resp, dict):
        return False, -1
    ret = _to_int(resp.get("ret"), -1)
    _check_market_captcha_ret(ret)
    return ret == RET_OK, ret


def place_sell_order(
    gateway: Any,
    city_id: int,
    res_type: int,
    count_dan: int,
    price: int,
) -> tuple[bool, int]:
    """Treo 1 đơn bán tài nguyên lên sàn Chợ (`OPT.ashx?id=49`)."""
    qty = int(count_dan)
    unit_price = int(price)
    if qty <= 0 or unit_price <= 0:
        return False, -1

    payload = {
        "tid": str(int(city_id)),
        "type1": str(int(res_type)),
        "sellcount1": str(qty),
        "sellprice1": str(unit_price),
        "countprice1": str(qty * unit_price),
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 49, payload)
    if not isinstance(resp, dict):
        return False, -1
    ret = _to_int(resp.get("ret"), -1)
    _check_market_captcha_ret(ret)
    return ret == RET_OK, ret


def buy_resource_from_market(
    gateway: Any,
    city_id: int,
    city_name: str,
    res_type: int,
    res_key: str,
    deficit_amount: float,
    remaining_capacity: float,
    current_gold: Optional[int],
    *,
    notify: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Gom mua tài nguyên thiếu từ top 10 đơn rẻ nhất trên sàn Chợ."""
    res_label = RESOURCE_VI_NAMES.get(res_key, res_key)
    rem_gold = int(current_gold) if current_gold is not None else None

    if deficit_amount < UNIT_DAN:
        return {
            "bought_dan": 0,
            "spent_gold": 0,
            "remaining_gold": rem_gold,
            "satisfied": True,
            "no_market": False,
            "out_of_gold": False,
            "no_supply": False,
        }

    max_fit_dan = max(0, int(remaining_capacity // UNIT_DAN))
    need_dan = min(math.ceil(deficit_amount / UNIT_DAN), max_fit_dan)
    if need_dan <= 0:
        return {
            "bought_dan": 0,
            "spent_gold": 0,
            "remaining_gold": rem_gold,
            "satisfied": True,
            "no_market": False,
            "out_of_gold": False,
            "no_supply": False,
        }

    listings = fetch_market_listings(gateway, city_id, res_type)
    if not listings:
        notify(f"ℹ️ [{city_name}] Sàn Chợ hết {res_label} để mua (thiếu {need_dan:,} đản).")
        return {
            "bought_dan": 0,
            "spent_gold": 0,
            "remaining_gold": rem_gold,
            "satisfied": False,
            "no_market": False,
            "out_of_gold": False,
            "no_supply": True,
        }

    bought_dan = 0
    spent_gold = 0
    remaining_dan = need_dan
    no_market = False
    out_of_gold = False

    for listing in listings:
        if remaining_dan <= 0:
            break
        if rem_gold is not None:
            affordable = rem_gold // listing.price
            if affordable <= 0:
                out_of_gold = True
                break
            qty = min(remaining_dan, listing.count_dan, affordable)
        else:
            qty = min(remaining_dan, listing.count_dan)
        if qty <= 0:
            continue

        ok, ret = buy_market_order(gateway, city_id, res_type, listing, qty)
        if ok:
            cost = qty * listing.price
            bought_dan += qty
            remaining_dan -= qty
            spent_gold += cost
            if rem_gold is not None:
                rem_gold = max(0, rem_gold - cost)
        elif ret == RET_NO_MARKET:
            no_market = True
            break
        elif ret in (RET_INSUFFICIENT_GOLD, RET_INSUFFICIENT_GOLD_ALT):
            out_of_gold = True
            break
        elif ret in (RET_ORDER_GONE, RET_ORDER_BUSY):
            continue
        else:
            continue

    satisfied = remaining_dan <= 0 and not no_market
    no_supply = not no_market and not out_of_gold and not satisfied

    if bought_dan > 0:
        notify(
            f"🏪 [{city_name}] Đã mua {bought_dan:,} đản {res_label} "
            f"({bought_dan * UNIT_DAN:,}) từ Chợ, tốn {spent_gold:,} Vàng."
        )
    if no_market:
        notify(f"ℹ️ [{city_name}] Thành chưa có Chợ (mã {RET_NO_MARKET}), chuyển sang mở rương mặc định.")
    elif out_of_gold and not satisfied:
        notify(
            f"ℹ️ [{city_name}] Không đủ Vàng mua thêm {res_label} trên Chợ "
            f"(còn thiếu {remaining_dan:,} đản)."
        )
    elif no_supply:
        notify(
            f"ℹ️ [{city_name}] Sàn Chợ không đủ nguồn {res_label} "
            f"(còn thiếu {remaining_dan:,} đản)."
        )

    return {
        "bought_dan": bought_dan,
        "spent_gold": spent_gold,
        "remaining_gold": rem_gold,
        "satisfied": satisfied,
        "no_market": no_market,
        "out_of_gold": out_of_gold,
        "no_supply": no_supply,
    }


def _compute_sell_target_and_dan(
    current_amount: int,
    max_storage: int,
    buy_pct: float,
    sell_pct: float,
) -> tuple[bool, float, int]:
    """Kiểm tra điều kiện kích hoạt bán và tính (triggered, target_pct, sell_dan)."""
    if buy_pct >= sell_pct or max_storage <= 0:
        return False, 0.0, 0
    triggered = (
        current_amount >= max_storage
        if sell_pct >= 100.0
        else current_amount > max_storage * (sell_pct / 100.0)
    )
    if not triggered:
        return False, 0.0, 0
    target_pct = max(sell_pct - 10.0, buy_pct, 0.0)
    excess = current_amount - max_storage * (target_pct / 100.0)
    sell_dan = int(excess // UNIT_DAN)
    return True, target_pct, max(0, sell_dan)


def sell_resource_on_market(
    gateway: Any,
    city_id: int,
    city_name: str,
    res_type: int,
    res_key: str,
    current_amount: int,
    max_storage: int,
    buy_pct: float,
    sell_pct: float,
    *,
    notify: Callable[[str], None] = print,
    now_cst: Optional[datetime] = None,
) -> dict[str, Any]:
    """Treo 1 đơn bán phần tài nguyên dôi dư đưa tồn kho về `max(S - 10%, buy_pct)`."""
    if buy_pct >= sell_pct:
        return {
            "sold_dan": 0,
            "price": 0,
            "skipped_conflict": True,
            "no_market": False,
            "max_orders": False,
            "failed_ret": None,
        }

    triggered, target_pct, sell_dan = _compute_sell_target_and_dan(
        current_amount, max_storage, buy_pct, sell_pct
    )
    if not triggered or sell_dan <= 0:
        return {
            "sold_dan": 0,
            "price": 0,
            "skipped_conflict": False,
            "no_market": False,
            "max_orders": False,
            "failed_ret": None,
        }

    res_label = RESOURCE_VI_NAMES.get(res_key, res_key)
    listings = fetch_market_listings(gateway, city_id, res_type)
    yesterday_avg = fetch_yesterday_avg_price(gateway, res_type)
    price = choose_sell_price(res_type, listings, yesterday_avg, now_cst=now_cst)

    ok, ret = place_sell_order(gateway, city_id, res_type, sell_dan, price)
    if not ok and ret == RET_PRICE_OUT_OF_RANGE and yesterday_avg is not None and yesterday_avg > 0:
        base = RESOURCE_BASE_PRICE.get(int(res_type), 480)
        fallback_price = max(base // 2, min(base * 2, int(yesterday_avg)))
        if fallback_price != price:
            price = fallback_price
            ok, ret = place_sell_order(gateway, city_id, res_type, sell_dan, price)

    if ok:
        notify(
            f"🏷️ [{city_name}] Đã treo bán {sell_dan:,} đản {res_label} "
            f"({sell_dan * UNIT_DAN:,}) giá {price:,}/đản (đưa kho về ~{target_pct:g}%)."
        )
        return {
            "sold_dan": sell_dan,
            "price": price,
            "skipped_conflict": False,
            "no_market": False,
            "max_orders": False,
            "failed_ret": None,
        }

    if ret == RET_NO_MARKET:
        notify(f"ℹ️ [{city_name}] Thành chưa có Chợ (mã {RET_NO_MARKET}), bỏ qua bán tài nguyên.")
        return {
            "sold_dan": 0,
            "price": price,
            "skipped_conflict": False,
            "no_market": True,
            "max_orders": False,
            "failed_ret": RET_NO_MARKET,
        }

    if ret == RET_MAX_SELL_ORDERS:
        notify(f"⚠️ [{city_name}] Đã đạt giới hạn đơn treo bán tối đa (mã {RET_MAX_SELL_ORDERS}), bỏ qua bán.")
        return {
            "sold_dan": 0,
            "price": price,
            "skipped_conflict": False,
            "no_market": False,
            "max_orders": True,
            "failed_ret": RET_MAX_SELL_ORDERS,
        }

    err_desc = MARKET_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")
    notify(f"⚠️ [{city_name}] Treo bán {res_label} thất bại (mã {ret}: {err_desc}).")
    return {
        "sold_dan": 0,
        "price": price,
        "skipped_conflict": False,
        "no_market": False,
        "max_orders": False,
        "failed_ret": ret,
    }


def fetch_city_resources_s58(gateway: Any, city_id: int) -> dict[str, Any]:
    """Đọc số dư tài nguyên, sức chứa kho & Vàng của một Thành/Trại trên Server 58+."""
    res_data = gateway.resource_info(city_id)
    city_data = gateway.city_info(city_id)

    res_ret = _to_int(res_data.get("ret"), -1) if isinstance(res_data, dict) else -1
    city_ret = _to_int(city_data.get("ret"), -1) if isinstance(city_data, dict) else -1
    _check_chest_captcha_ret(res_ret)
    _check_chest_captcha_ret(city_ret)

    if city_ret == RET_CITY_NOT_FOUND or res_ret == RET_CITY_NOT_FOUND:
        return {
            "ret": RET_CITY_NOT_FOUND,
            "money": None,
            "has_resources": False,
            "max_storage": 0,
        }

    city_ok = (
        isinstance(city_data, dict)
        and city_ret == RET_OK
        and ("m_lmoney_balance" in city_data or "money" in city_data)
    )
    money: Optional[int] = None
    if city_ok:
        money = _to_int(city_data.get("m_lmoney_balance", city_data.get("money", 0)))

    res_ok = (
        isinstance(res_data, dict)
        and res_ret == RET_OK
        and ("m_lmax_storage" in res_data or "max_storage" in res_data)
    )
    max_storage = 0
    wood: Optional[int] = None
    iron: Optional[int] = None
    stone: Optional[int] = None
    food: Optional[int] = None
    if res_ok:
        wood = _to_int(res_data.get("m_lwood_balance", res_data.get("wood", 0)))
        iron = _to_int(res_data.get("m_liron_balance", res_data.get("iron", 0)))
        stone = _to_int(res_data.get("m_lstone_balance", res_data.get("stone", 0)))
        food = _to_int(res_data.get("m_lfood_balance", res_data.get("food", 0)))
        max_storage = _to_int(res_data.get("m_lmax_storage", res_data.get("max_storage", 0)))

    return {
        "ret": RET_OK,
        "money": money,
        "has_resources": bool(res_ok and max_storage > 0),
        "max_storage": max_storage,
        "wood": wood,
        "iron": iron,
        "stone": stone,
        "food": food,
    }


def _fetch_city_gold_s58(gateway: Any, city_id: int) -> Optional[int]:
    city_data = gateway.city_info(city_id)
    if (
        isinstance(city_data, dict)
        and _to_int(city_data.get("ret"), -1) == RET_OK
        and ("m_lmoney_balance" in city_data or "money" in city_data)
    ):
        return _to_int(city_data.get("m_lmoney_balance", city_data.get("money", 0)))
    return None


def _open_chest_for_city(gateway: Any, box_id: int) -> int:
    resp = gateway.call("Common.ashx", 48, {"lBoxID": str(int(box_id)), "_": ""}) or {}
    if not isinstance(resp, dict):
        return -1
    ret = _to_int(resp.get("ret"), -1)
    _check_chest_captcha_ret(ret)
    return ret


def process_city_resource_cycle(
    gateway: Any,
    city_id: int,
    city_name: str,
    settings: ResourceMonitorSettings,
    market_cache: CityMarketCache,
    *,
    notify: Callable[[str], None] = print,
    warned_conflicts: Optional[set[tuple[int, str]]] = None,
) -> dict[str, Any]:
    """Thực thi 1 chu kỳ giám sát tài nguyên cho Thành/Trại: Bán dư -> Vàng -> Mua Chợ -> Fallback Rương."""
    snap = fetch_city_resources_s58(gateway, city_id)
    if snap.get("ret") == RET_CITY_NOT_FOUND:
        return {
            "city_missing": True,
            "sold_types": 0,
            "bought_dan": 0,
            "opened_gold_box": False,
            "opened_tn_box": False,
        }

    money: Optional[int] = snap.get("money")
    max_storage = int(snap.get("max_storage") or 0)
    has_resources = bool(snap.get("has_resources"))
    cur_amounts: dict[str, Optional[int]] = {k: snap.get(k) for k in RESOURCE_CHECK_ORDER}

    # Xác định nhu cầu bán & nhu cầu mua trước khi gọi building_list kiểm tra Chợ (lazy check)
    sell_candidates: list[str] = []
    if settings.auto_sell_resource and has_resources:
        for k in RESOURCE_CHECK_ORDER:
            val = cur_amounts.get(k)
            if val is None:
                continue
            buy_p = float(settings.buy_pcts.get(k, 70.0))
            if buy_p >= settings.sell_threshold_pct:
                over_sell = (
                    val >= max_storage
                    if settings.sell_threshold_pct >= 100.0
                    else val > max_storage * (settings.sell_threshold_pct / 100.0)
                )
                if over_sell and (warned_conflicts is None or (city_id, k) not in warned_conflicts):
                    notify(
                        f"⚠️ [{city_name}] Bỏ qua bán {RESOURCE_VI_NAMES[k]}: "
                        f"ngưỡng mua ({buy_p:g}%) ≥ ngưỡng bán ({settings.sell_threshold_pct:g}%)."
                    )
                    if warned_conflicts is not None:
                        warned_conflicts.add((city_id, k))
                continue
            triggered, _, sell_dan = _compute_sell_target_and_dan(
                val, max_storage, buy_p, settings.sell_threshold_pct
            )
            if triggered and sell_dan > 0:
                sell_candidates.append(k)

    def _collect_deficits() -> dict[str, float]:
        if not has_resources:
            return {}
        out: dict[str, float] = {}
        for k in RESOURCE_CHECK_ORDER:
            val = cur_amounts.get(k)
            if val is None:
                continue
            target_amt = max_storage * (max(0.0, float(settings.buy_pcts.get(k, 70.0))) / 100.0)
            if val < target_amt:
                out[k] = target_amt - val
        return out

    initial_deficits = _collect_deficits()
    need_gold = money is not None and money < settings.gold_threshold

    has_market = False
    need_market_check = bool(sell_candidates) or (
        settings.prefer_market_buy and any(d >= UNIT_DAN for d in initial_deficits.values())
    )
    if need_market_check:
        has_market = market_cache.has_market(gateway, city_id)

    sold_types = 0
    bought_dan = 0
    opened_gold_box = False
    opened_tn_box = False

    def _open_selected_chests(open_gold: bool, open_tn: bool, tn_fb_note: str = "") -> bool:
        nonlocal opened_gold_box, opened_tn_box
        with gateway_city_context(gateway):
            ok_sw, sw_ret, sw_msg = switch_city_verified(gateway, city_id)
            if not ok_sw:
                notify(f"⚠️ [{city_name}] {sw_msg}; bỏ qua mở rương.")
                _check_chest_captcha_ret(sw_ret)
                return False
            if open_gold:
                ret_g = _open_chest_for_city(gateway, settings.gold_box_id)
                if ret_g == RET_OK:
                    opened_gold_box = True
                    notify(
                        f"💰 [{city_name}] Vàng={money:,} < ngưỡng {settings.gold_threshold:,}: "
                        f"Đã mở rương vàng #{settings.gold_box_id}."
                    )
                else:
                    notify(f"⚠️ [{city_name}] Mở rương vàng #{settings.gold_box_id} thất bại (mã {ret_g}).")
            if open_tn:
                ret_tn = _open_chest_for_city(gateway, settings.tn_box_id)
                if ret_tn == RET_OK:
                    opened_tn_box = True
                    notify(
                        f"📦 [{city_name}] Khoáng sản dưới ngưỡng: "
                        f"Đã mở rương TN #{settings.tn_box_id} (Kho {max_storage:,}){tn_fb_note}."
                    )
                else:
                    notify(f"⚠️ [{city_name}] Mở rương TN #{settings.tn_box_id} thất bại (mã {ret_tn}).")
        return True

    # 1. Bán tài nguyên dư trước để giải phóng sức chứa kho
    if sell_candidates and has_market:
        for k in sell_candidates:
            val = cur_amounts.get(k)
            if val is None:
                continue
            buy_p = float(settings.buy_pcts.get(k, 70.0))
            res_sell = sell_resource_on_market(
                gateway,
                city_id,
                city_name,
                RESOURCE_KEY_TO_MARKET_TYPE[k],
                k,
                val,
                max_storage,
                buy_p,
                settings.sell_threshold_pct,
                notify=notify,
            )
            if res_sell["sold_dan"] > 0:
                cur_amounts[k] = max(0, val - res_sell["sold_dan"] * UNIT_DAN)
                sold_types += 1
            if res_sell["no_market"]:
                market_cache.mark_no_market(city_id)
                has_market = False
                break
            if res_sell["max_orders"]:
                break

    deficits = _collect_deficits()
    will_attempt_market_buy = bool(
        deficits and settings.prefer_market_buy and has_market and any(d >= UNIT_DAN for d in deficits.values())
    )

    # 2. Nếu KHÔNG mua Chợ nhưng cần mở rương: gộp chung 1 gateway_city_context + 1 switch_city_verified
    if not will_attempt_market_buy:
        if need_gold or deficits:
            _open_selected_chests(open_gold=need_gold, open_tn=bool(deficits))
        return {
            "city_missing": False,
            "sold_types": sold_types,
            "bought_dan": bought_dan,
            "opened_gold_box": opened_gold_box,
            "opened_tn_box": opened_tn_box,
        }

    # 3. Khi có mua Chợ: mở Rương Vàng trước (nếu thiếu vàng) rồi làm mới số vàng trước khi mua Chợ
    if need_gold:
        switched_ok = _open_selected_chests(open_gold=True, open_tn=False)
        if switched_ok and opened_gold_box:
            refreshed_gold = _fetch_city_gold_s58(gateway, city_id)
            if refreshed_gold is not None:
                money = refreshed_gold

    # 4. Bù tài nguyên thiếu qua Chợ; fallback mở 1 Rương TN nếu còn thiếu
    still_need_box = False
    attempted_market = False
    for k, deficit in deficits.items():
        if deficit < UNIT_DAN:
            continue
        cur_val = cur_amounts.get(k) or 0
        attempted_market = True
        res_buy = buy_resource_from_market(
            gateway,
            city_id,
            city_name,
            RESOURCE_KEY_TO_MARKET_TYPE[k],
            k,
            deficit,
            max_storage - cur_val,
            money,
            notify=notify,
        )
        if res_buy["bought_dan"] > 0:
            cur_amounts[k] = cur_val + res_buy["bought_dan"] * UNIT_DAN
            bought_dan += res_buy["bought_dan"]
        if res_buy["remaining_gold"] is not None:
            money = res_buy["remaining_gold"]
        if res_buy["no_market"]:
            market_cache.mark_no_market(city_id)
            has_market = False
            still_need_box = True
            break
        if not res_buy["satisfied"]:
            still_need_box = True

    if still_need_box:
        fb_note = " (fallback sau mua Chợ)" if attempted_market else ""
        _open_selected_chests(open_gold=False, open_tn=True, tn_fb_note=fb_note)

    return {
        "city_missing": False,
        "sold_types": sold_types,
        "bought_dan": bought_dan,
        "opened_gold_box": opened_gold_box,
        "opened_tn_box": opened_tn_box,
    }
