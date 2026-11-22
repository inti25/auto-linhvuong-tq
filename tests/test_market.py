from datetime import datetime, timedelta, timezone

import pytest

from linhvuong.gateway import GatewayClient
from linhvuong.market import (
    CityMarketCache,
    MarketListing,
    ResourceMonitorSettings,
    buy_market_order,
    buy_resource_from_market,
    choose_sell_price,
    compute_price_bounds,
    fetch_market_listings,
    fetch_yesterday_avg_price,
    parse_sell_threshold_pct,
    place_sell_order,
    process_city_resource_cycle,
    sell_resource_on_market,
)
from linhvuong.tasks.base import CaptchaRequired


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeMarketServer:
    def __init__(self, handler):
        self._handler = handler
        self.calls: list[tuple[str, dict]] = []

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1]
        payload = dict(data or {})
        self.calls.append((key, payload))
        return _Resp(self._handler(key, payload))


def test_parse_sell_threshold_pct_normalization_and_bounds():
    assert parse_sell_threshold_pct("90") == 90.0
    assert parse_sell_threshold_pct("85,5%") == 85.5
    assert parse_sell_threshold_pct("150") == 100.0
    assert parse_sell_threshold_pct("0") == 90.0
    assert parse_sell_threshold_pct("-10") == 90.0
    assert parse_sell_threshold_pct("abc") == 90.0
    assert parse_sell_threshold_pct(None) == 90.0
    assert parse_sell_threshold_pct(True) == 90.0


def test_compute_price_bounds_and_choose_sell_price():
    cst = timezone(timedelta(hours=8))
    day_time = datetime(2026, 11, 22, 14, 0, tzinfo=cst)
    night_time = datetime(2026, 11, 22, 3, 0, tzinfo=cst)

    # Thực (type=1, base=120 => [60, 240]), hôm qua 239
    assert compute_price_bounds(1, 239, now_cst=day_time) == (216, 240)
    assert compute_price_bounds(1, 239, now_cst=night_time) == (228, 240)

    # Gỗ (type=2, base=480 => [240, 960]), không có giá hôm qua
    assert compute_price_bounds(2, None, now_cst=day_time) == (240, 960)
    assert compute_price_bounds(2, 959, now_cst=day_time) == (864, 960)

    # Chọn giá thấp nhất trên sàn, kẹp biên
    listings = [MarketListing(seqno=1, seller=10, count_dan=50, price=910)]
    assert choose_sell_price(2, listings, 959, now_cst=day_time) == 910
    too_low = [MarketListing(seqno=2, seller=10, count_dan=50, price=500)]
    assert choose_sell_price(2, too_low, 959, now_cst=day_time) == 864
    assert choose_sell_price(1, [], 239, now_cst=day_time) == 239
    assert choose_sell_price(1, [], None, now_cst=day_time) == 120


def test_market_api_non_dict_responses_captcha_and_payloads():
    def _handler(key, payload):
        if key == "Common.ashx?id=38":
            if payload.get("tid") == "99":
                return {"ret": 110}
            return False
        if key == "OPT.ashx?id=29":
            t = payload.get("type")
            if t == "1":
                return 239
            if t == "2":
                return -1
            return {"ret": 110}
        if key == "OPT.ashx?id=9":
            return {"ret": 0}
        if key == "OPT.ashx?id=49":
            return {"ret": 0}
        return {"ret": 0}

    srv = _FakeMarketServer(_handler)
    gw = GatewayClient(57, srv, sleep=lambda _s: None)

    assert fetch_market_listings(gw, 15609, 2) == []
    with pytest.raises(CaptchaRequired):
        fetch_market_listings(gw, 99, 2)

    assert fetch_yesterday_avg_price(gw, 1) == 239
    assert fetch_yesterday_avg_price(gw, 2) is None
    with pytest.raises(CaptchaRequired):
        fetch_yesterday_avg_price(gw, 3)

    listing = MarketListing(seqno=548270, seller=15643, count_dan=3102, price=960)
    ok_buy, ret_buy = buy_market_order(gw, 15609, 3, listing, 5)
    assert ok_buy is True and ret_buy == 0
    buy_payload = [p for k, p in srv.calls if k == "OPT.ashx?id=9"][0]
    assert buy_payload["count"] == "5"
    assert buy_payload["countprice"] == "960"  # đơn giá
    assert buy_payload["type3"] == "3"

    ok_sell, ret_sell = place_sell_order(gw, 15609, 4, 10, 959)
    assert ok_sell is True and ret_sell == 0
    sell_payload = [p for k, p in srv.calls if k == "OPT.ashx?id=49"][0]
    assert sell_payload["sellcount1"] == "10"
    assert sell_payload["sellprice1"] == "959"
    assert sell_payload["countprice1"] == "9590"  # tổng giá


def test_city_market_cache_gid11_gid64_no_market_camp_and_transient_error():
    responses = {
        "101": {"ret": 0, "infos": [[24, 11, "市场", 30, 0, 0]]},
        "102": {"ret": 0, "infos": [[26, 64, "集市", 1, 0, 0]]},
        "103": {"ret": 0, "infos": [[1, 1, "官府", 10, 0, 0]]},
        "104": {"ret": 0, "infos": [[24, 11, "市场", 0, 0, 0]]},
        "105": [{"ret": 1}, {"ret": 0, "infos": [[24, 11, "市场", 5, 0, 0]]}],
        "106": {"ret": 110},
    }

    def _handler(key, payload):
        assert key == "City.ashx?id=5"
        r = responses[payload["tid"]]
        return r.pop(0) if isinstance(r, list) else r

    srv = _FakeMarketServer(_handler)
    gw = GatewayClient(57, srv, sleep=lambda _s: None)
    cache = CityMarketCache(ttl_seconds=300.0)

    assert cache.has_market(gw, -1083) is False  # Doanh trại không gọi API
    assert srv.calls == []

    assert cache.has_market(gw, 101) is True
    assert cache.has_market(gw, 101) is True  # dùng cache
    assert len([c for c in srv.calls if c[1]["tid"] == "101"]) == 1

    assert cache.has_market(gw, 102) is True
    assert cache.has_market(gw, 103) is False
    assert cache.has_market(gw, 104) is False

    # Lỗi tạm thời ret=1 không được cache False
    assert cache.has_market(gw, 105) is False
    assert cache.has_market(gw, 105) is True

    # mark_no_market ghi đè cache
    cache.mark_no_market(101)
    assert cache.has_market(gw, 101) is False

    with pytest.raises(CaptchaRequired):
        cache.has_market(gw, 106)


def test_buy_resource_from_market_multi_order_cap_and_errors():
    logs: list[str] = []

    def _handler(key, payload):
        if key == "Common.ashx?id=38":
            return {
                "infos": [
                    {"seqno": "1", "seller": "10", "count": "3", "price": "200"},
                    {"seqno": "2", "seller": "11", "count": "2", "price": "210"},
                    {"seqno": "3", "seller": "12", "count": "10", "price": "220"},
                ]
            }
        if key == "OPT.ashx?id=9":
            if payload["seqno"] == "2":
                return {"ret": 26}  # đơn đã hết -> thử đơn kế
            return {"ret": 0}
        return {"ret": 0}

    srv = _FakeMarketServer(_handler)
    gw = GatewayClient(57, srv, sleep=lambda _s: None)

    # Thiếu 500 (< 1000) -> không gọi API
    res_small = buy_resource_from_market(gw, 101, "K5", 2, "wood", 500, 100_000, 50_000, notify=logs.append)
    assert res_small["satisfied"] is True
    assert srv.calls == []

    # Thiếu 8000 (8 đản), sức chứa còn 6500 (tối đa 6 đản), vàng đủ mua 3 đản@200 + 3 đản@220
    res = buy_resource_from_market(gw, 101, "K5", 2, "wood", 8000, 6500, 10_000, notify=logs.append)
    assert res["bought_dan"] == 6
    assert res["spent_gold"] == 3 * 200 + 3 * 220
    assert res["remaining_gold"] == 10_000 - (3 * 200 + 3 * 220)
    assert res["satisfied"] is True

    # Kiểm tra thiếu Vàng dừng giữa chừng -> satisfied=False, out_of_gold=True
    res_gold = buy_resource_from_market(gw, 101, "K5", 2, "wood", 5000, 10_000, 500, notify=logs.append)
    assert res_gold["bought_dan"] == 2  # 2 * 200 = 400 <= 500
    assert res_gold["out_of_gold"] is True
    assert res_gold["satisfied"] is False


def test_sell_resource_on_market_q5b_conflict_ret74_and_ret249():
    logs: list[str] = []
    sell_rets = [{"ret": 74}, {"ret": 0}, {"ret": 249}, {"ret": 232}]

    def _handler(key, payload):
        if key == "Common.ashx?id=38":
            return {"infos": [{"seqno": "1", "seller": "10", "count": "50", "price": "940"}]}
        if key == "OPT.ashx?id=29":
            return 959
        if key == "OPT.ashx?id=49":
            return sell_rets.pop(0)
        return {"ret": 0}

    srv = _FakeMarketServer(_handler)
    gw = GatewayClient(57, srv, sleep=lambda _s: None)

    # 1. Q5=B: > 90% bán gộp 1 đơn đưa về max(80%, buy_pct=70%) = 80%; gặp ret=74 -> retry giá TB 959
    r1 = sell_resource_on_market(
        gw, 101, "K5", 2, "wood", 9_500_000, 10_000_000, 70.0, 90.0, notify=logs.append
    )
    assert r1["sold_dan"] == 1500
    assert r1["price"] == 959
    sell_calls = [p for k, p in srv.calls if k == "OPT.ashx?id=49"]
    assert len(sell_calls) == 2
    assert sell_calls[0]["sellcount1"] == "1500"
    assert sell_calls[1]["sellprice1"] == "959"

    # 2. Xung đột buy_pct >= sell_pct -> bỏ qua không bán
    before_calls = len(srv.calls)
    r_conflict = sell_resource_on_market(
        gw, 101, "K5", 2, "wood", 9_500_000, 10_000_000, 90.0, 90.0, notify=logs.append
    )
    assert r_conflict["skipped_conflict"] is True
    assert len(srv.calls) == before_calls

    # 3. ret=249 giới hạn số đơn treo
    r_max = sell_resource_on_market(
        gw, 101, "K5", 3, "stone", 9_200_000, 10_000_000, 85.0, 90.0, notify=logs.append
    )
    assert r_max["max_orders"] is True
    # Khi buy_pct=85 > 90-10=80 -> target là 85% -> (9.2M - 8.5M)/1000 = 700 đản
    assert srv.calls[-1][1]["sellcount1"] == "700"

    # 4. Ngưỡng bán 100% kích hoạt ở >= 100%, gặp ret=232
    r_100 = sell_resource_on_market(
        gw, 101, "K5", 4, "iron", 10_000_000, 10_000_000, 70.0, 100.0, notify=logs.append
    )
    assert r_100["no_market"] is True
    assert srv.calls[-1][1]["sellcount1"] == "1000"


def test_process_city_resource_cycle_order_and_fallback():
    logs: list[str] = []
    gold_reads = [100, 50_000_000]  # ban đầu thiếu vàng (< 10k), sau khi mở rương vàng có 50M

    def _handler(key, payload):
        tid = payload.get("tid", "")
        if key == "City.ashx?id=20":
            if tid == "101":  # Thành có Chợ: food dư 95%, wood thiếu 50% (5M), stone/iron đủ
                return {
                    "ret": 0,
                    "wood": [5_000_000, 10],
                    "iron": [8_000_000, 10],
                    "stone": [8_000_000, 10],
                    "food": [9_500_000, 10],
                    "max_storage": 10_000_000,
                }
            if tid == "102":  # Thành không có Chợ: wood thiếu
                return {
                    "ret": 0,
                    "wood": [5_000_000, 10],
                    "iron": [8_000_000, 10],
                    "stone": [8_000_000, 10],
                    "food": [8_000_000, 10],
                    "max_storage": 10_000_000,
                }
        if key == "City.ashx?id=6":
            return {"ret": 0, "money": [gold_reads.pop(0) if gold_reads else 50_000_000, 0]}
        if key == "City.ashx?id=5":
            if tid == "101":
                return {"ret": 0, "infos": [[26, 64, "集市", 1, 0, 0]]}
            return {"ret": 0, "infos": [[1, 1, "官府", 10, 0, 0]]}
        if key == "Common.ashx?id=38":
            if payload.get("type") == "1":  # Food
                return {"infos": [{"seqno": "10", "seller": "1", "count": "100", "price": "238"}]}
            if payload.get("type") == "2":  # Wood: đủ 2000 đản (2M) để mua đủ 7M
                return {"infos": [{"seqno": "20", "seller": "2", "count": "2000", "price": "950"}]}
            return False
        if key == "OPT.ashx?id=29":
            return 239
        return {"ret": 0}

    srv = _FakeMarketServer(_handler)
    gw = GatewayClient(57, srv, sleep=lambda _s: None)
    cache = CityMarketCache()
    warned: set[tuple[int, str]] = set()
    settings = ResourceMonitorSettings(
        gold_threshold=10_000,
        buy_pcts={"wood": 70.0, "iron": 70.0, "stone": 70.0, "food": 70.0},
        gold_box_id=11,
        tn_box_id=24,
        prefer_market_buy=True,
        auto_sell_resource=True,
        sell_threshold_pct=90.0,
    )

    # 1. Thành có Tập Thị (101): Bán Food (95% -> 80% = 1500 đản) -> Mở Rương Vàng -> Refresh Vàng -> Mua 2000 đản Wood (đủ) -> KHÔNG mở Rương TN
    res1 = process_city_resource_cycle(
        gw, 101, "ThienNam", settings, cache, notify=logs.append, warned_conflicts=warned
    )
    assert res1 == {
        "city_missing": False,
        "sold_types": 1,
        "bought_dan": 2000,
        "opened_gold_box": True,
        "opened_tn_box": False,
    }
    call_keys = [k for k, _ in srv.calls]
    assert call_keys.index("OPT.ashx?id=49") < call_keys.index("Common.ashx?id=48")
    assert call_keys.index("Common.ashx?id=48") < call_keys.index("OPT.ashx?id=9")
    assert [p for k, p in srv.calls if k == "Common.ashx?id=48"] == [{"lBoxID": "11", "_": ""}]

    # 2. Thành không có Chợ (102): Bỏ qua mua Chợ -> mở Rương TN mặc định
    srv.calls.clear()
    res2 = process_city_resource_cycle(
        gw, 102, "NB", settings, cache, notify=logs.append, warned_conflicts=warned
    )
    assert res2["bought_dan"] == 0
    assert res2["opened_tn_box"] is True
    assert not any(k in ("OPT.ashx?id=9", "OPT.ashx?id=49") for k, _ in srv.calls)
    assert [p for k, p in srv.calls if k == "Common.ashx?id=48"] == [{"lBoxID": "24", "_": ""}]

    # 3. Thành có Chợ (101) nhưng sàn hết hàng -> fallback mở đúng 1 Rương TN
    srv.calls.clear()
    settings.auto_sell_resource = False
    settings.gold_threshold = 100
    def _empty_market_handler(key, payload):
        if key == "Common.ashx?id=38":
            return False
        return _handler(key, payload)
    srv._handler = _empty_market_handler
    res3 = process_city_resource_cycle(
        gw, 101, "ThienNam", settings, cache, notify=logs.append, warned_conflicts=warned
    )
    assert res3["bought_dan"] == 0
    assert res3["opened_tn_box"] is True
    assert any("fallback sau mua Chợ" in msg for msg in logs)
