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
        if "/GateWay/" in url:
            key = url.split("/GateWay/")[1]
            payload = dict(data or {})
        else:
            key = url
            payload = dict(data or {})
        self.calls.append((key, payload))
        return _Resp(self._handler(key, payload))

    def get(self, url, params=None, headers=None, timeout=None):
        payload = dict(params or {})
        self.calls.append((url, payload))
        return _Resp(self._handler(url, payload))


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


def test_market_api_payloads_captcha110_and_ret73_busy():
    def _handler(key, payload):
        if key == "Common.ashx?id=38":
            if payload.get("tid") == "99":
                return {"ret": 110}
            return False
        if key == "OPT.ashx?id=29":
            t = payload.get("type")
            if t == "1":
                return 480
            if t == "2":
                return -1
            return {"ret": 110}
        if key == "OPT.ashx?id=9":
            if payload.get("seqno") == "73":
                # ret=73 trên sàn Chợ là đơn đang giao dịch (RET_ORDER_BUSY), không phải Captcha
                return {"ret": 73}
            if payload.get("seqno") == "110":
                return {"ret": 110}
            return {"ret": 0}
        if key == "OPT.ashx?id=49":
            return {"ret": 0}
        return {"ret": 0}

    srv = _FakeMarketServer(_handler)
    gw = GatewayClient(58, srv, sleep=lambda _s: None)

    assert fetch_market_listings(gw, 10129, 2) == []
    with pytest.raises(CaptchaRequired):
        fetch_market_listings(gw, 99, 2)

    assert fetch_yesterday_avg_price(gw, 1) == 480
    assert fetch_yesterday_avg_price(gw, 2) is None
    with pytest.raises(CaptchaRequired):
        fetch_yesterday_avg_price(gw, 3)

    listing = MarketListing(seqno=80, seller=10544, count_dan=32968, price=500)
    ok_buy, ret_buy = buy_market_order(gw, 10129, 4, listing, 5)
    assert ok_buy is True and ret_buy == 0
    buy_payload = [p for k, p in srv.calls if k == "OPT.ashx?id=9"][0]
    assert buy_payload["count"] == "5"
    assert buy_payload["countprice"] == "500"  # đơn giá
    assert buy_payload["type3"] == "4"

    # ret=73 trả (False, 73), không nâng CaptchaRequired
    busy_listing = MarketListing(seqno=73, seller=10544, count_dan=10, price=500)
    ok_busy, ret_busy = buy_market_order(gw, 10129, 4, busy_listing, 2)
    assert ok_busy is False and ret_busy == 73

    with pytest.raises(CaptchaRequired):
        cap_listing = MarketListing(seqno=110, seller=10544, count_dan=10, price=500)
        buy_market_order(gw, 10129, 4, cap_listing, 2)

    ok_sell, ret_sell = place_sell_order(gw, 10129, 2, 10, 480)
    assert ok_sell is True and ret_sell == 0
    sell_payload = [p for k, p in srv.calls if k == "OPT.ashx?id=49"][0]
    assert sell_payload["sellcount1"] == "10"
    assert sell_payload["sellprice1"] == "480"
    assert sell_payload["countprice1"] == "4800"  # tổng giá


def test_city_market_cache_s58_building_list_and_legacy_fallback():
    responses = {
        101: {"ret": 0, "items": [{"m_lpos": 24, "m_lgid": 11, "m_llevel": 30}]},
        102: {"ret": 0, "items": [{"m_lpos": 26, "m_lgid": 64, "m_llevel": 1}]},
        103: {"ret": 0, "items": [{"m_lpos": 1, "m_lgid": 1, "m_llevel": 10}]},
        104: {"ret": 0, "items": [{"m_lpos": 24, "m_lgid": 11, "m_llevel": 0}]},
        105: [{"ret": 1}, {"ret": 0, "items": [{"m_lpos": 24, "m_lgid": 11, "m_llevel": 5}]}],
        106: {"ret": 110},
    }
    b_calls: list[int] = []

    class _FakeS58Gw:
        def building_list(self, cid):
            b_calls.append(int(cid))
            r = responses[int(cid)]
            return r.pop(0) if isinstance(r, list) else r

    gw = _FakeS58Gw()
    cache = CityMarketCache(ttl_seconds=300.0)

    assert cache.has_market(gw, -1083) is False  # Doanh trại không gọi API
    assert b_calls == []

    assert cache.has_market(gw, 101) is True
    assert cache.has_market(gw, 101) is True  # dùng cache
    assert b_calls.count(101) == 1

    assert cache.has_market(gw, 102) is True
    assert cache.has_market(gw, 103) is False
    assert cache.has_market(gw, 104) is False

    # Lỗi tạm thời ret=1 không được cache False
    assert cache.has_market(gw, 105) is False
    assert cache.has_market(gw, 105) is True

    cache.mark_no_market(101)
    assert cache.has_market(gw, 101) is False

    with pytest.raises(CaptchaRequired):
        cache.has_market(gw, 106)

    # Fallback City.ashx?id=5 khi gateway đời cũ không có building_list
    class _LegacyGw:
        def call(self, ep, api_id, params=None):
            assert ep == "City.ashx" and api_id == 5
            return {"ret": 0, "infos": [[26, 64, "集市", 1, 0, 0]]}

    assert CityMarketCache().has_market(_LegacyGw(), 15609) is True


def test_buy_resource_from_market_multi_order_cap_and_ret73_skip():
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
                return {"ret": 73}  # đơn đang giao dịch -> bỏ qua thử đơn kế, KHÔNG ngắt Captcha
            return {"ret": 0}
        return {"ret": 0}

    srv = _FakeMarketServer(_handler)
    gw = GatewayClient(58, srv, sleep=lambda _s: None)

    # Thiếu 500 (< 1000) -> không gọi API
    res_small = buy_resource_from_market(gw, 101, "K5", 2, "wood", 500, 100_000, 50_000, notify=logs.append)
    assert res_small["satisfied"] is True
    assert srv.calls == []

    # Thiếu 8000 (8 đản), sức chứa còn 6500 (tối đa 6 đản), vàng đủ mua 3 đản@200 + 3 đản@220 (bỏ qua seqno=2 ret=73)
    res = buy_resource_from_market(gw, 101, "K5", 2, "wood", 8000, 6500, 10_000, notify=logs.append)
    assert res["bought_dan"] == 6
    assert res["spent_gold"] == 3 * 200 + 3 * 220
    assert res["remaining_gold"] == 10_000 - (3 * 200 + 3 * 220)
    assert res["satisfied"] is True

    # Thiếu Vàng dừng giữa chừng -> satisfied=False, out_of_gold=True
    res_gold = buy_resource_from_market(gw, 101, "K5", 2, "wood", 5000, 10_000, 500, notify=logs.append)
    assert res_gold["bought_dan"] == 2
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
    gw = GatewayClient(58, srv, sleep=lambda _s: None)

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
    assert srv.calls[-1][1]["sellcount1"] == "700"

    # 4. Ngưỡng bán 100% kích hoạt ở >= 100%, gặp ret=232
    r_100 = sell_resource_on_market(
        gw, 101, "K5", 4, "iron", 10_000_000, 10_000_000, 70.0, 100.0, notify=logs.append
    )
    assert r_100["no_market"] is True
    assert srv.calls[-1][1]["sellcount1"] == "1000"


def test_process_city_resource_cycle_s58_order_switch_verify_and_fallback():
    logs: list[str] = []
    gold_reads = [100, 50_000_000]
    switched: list[int] = []
    events: list[str] = []

    class _FakeS58Gateway:
        def __init__(self):
            self.market_listings_mode = "normal"
            self.switch_ret = 0

        def resource_info(self, cid: int):
            if int(cid) == 404:
                return {"ret": 4}
            if int(cid) == 10129:  # Thành có Tập Thị: food dư 95%, wood thiếu 5M
                return {
                    "ret": 0,
                    "m_lwood_balance": 5_000_000,
                    "m_liron_balance": 8_000_000,
                    "m_lstone_balance": 8_000_000,
                    "m_lfood_balance": 9_500_000,
                    "m_lmax_storage": 10_000_000,
                }
            # Thành không có Chợ: thiếu gỗ
            return {
                "ret": 0,
                "m_lwood_balance": 5_000_000,
                "m_liron_balance": 8_000_000,
                "m_lstone_balance": 8_000_000,
                "m_lfood_balance": 8_000_000,
                "m_lmax_storage": 10_000_000,
            }

        def city_info(self, cid: int):
            if int(cid) == 404:
                return {"ret": 4}
            return {"ret": 0, "m_lmoney_balance": gold_reads.pop(0) if gold_reads else 50_000_000}

        def building_list(self, cid: int):
            if int(cid) == 10129:
                return {"ret": 0, "items": [{"m_lpos": 26, "m_lgid": 64, "m_llevel": 1}]}
            return {"ret": 0, "items": [{"m_lpos": 1, "m_lgid": 1, "m_llevel": 10}]}

        def set_current_city(self, cid: int):
            switched.append(int(cid))
            events.append(f"switch:{cid}")
            return {"ret": self.switch_ret}

        def call(self, ep: str, api_id: int, payload=None):
            p = dict(payload or {})
            events.append(f"{ep}?id={api_id}")
            if ep == "Common.ashx" and api_id == 38:
                if self.market_listings_mode == "empty":
                    return False
                if p.get("type") == "1":
                    return {"infos": [{"seqno": "10", "seller": "1", "count": "100", "price": "238"}]}
                if p.get("type") == "2":
                    return {"infos": [{"seqno": "20", "seller": "2", "count": "2000", "price": "480"}]}
                return False
            if ep == "OPT.ashx" and api_id == 29:
                return 239
            if ep == "Common.ashx" and api_id == 48:
                events.append(f"chest:{p.get('lBoxID')}")
                return {"ret": 0}
            return {"ret": 0}

    gw = _FakeS58Gateway()
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

    # 1. Thành có Tập Thị (10129): Bán Food -> Đổi thành mở Rương Vàng -> Refresh Vàng -> Mua 2000 đản Wood -> KHÔNG mở Rương TN
    res1 = process_city_resource_cycle(
        gw, 10129, "ThienNam", settings, cache, notify=logs.append, warned_conflicts=warned
    )
    assert res1 == {
        "city_missing": False,
        "sold_types": 1,
        "bought_dan": 2000,
        "opened_gold_box": True,
        "opened_tn_box": False,
    }
    assert events.index("OPT.ashx?id=49") < events.index("chest:11") < events.index("OPT.ashx?id=9")
    assert "chest:24" not in events
    assert switched == [10129]

    # 2. Thành không có Chợ (10254): Bỏ qua mua Chợ -> mở Rương TN mặc định
    events.clear()
    switched.clear()
    res2 = process_city_resource_cycle(
        gw, 10254, "NB", settings, cache, notify=logs.append, warned_conflicts=warned
    )
    assert res2["bought_dan"] == 0
    assert res2["opened_tn_box"] is True
    assert "OPT.ashx?id=9" not in events and "OPT.ashx?id=49" not in events
    assert switched == [10254]
    assert "chest:24" in events

    # 3. Thành có Chợ (10129) nhưng sàn hết hàng -> fallback mở đúng 1 Rương TN
    events.clear()
    switched.clear()
    settings.auto_sell_resource = False
    settings.gold_threshold = 100
    gw.market_listings_mode = "empty"
    res3 = process_city_resource_cycle(
        gw, 10129, "ThienNam", settings, cache, notify=logs.append, warned_conflicts=warned
    )
    assert res3["bought_dan"] == 0
    assert res3["opened_tn_box"] is True
    assert switched == [10129]
    assert any("fallback sau mua Chợ" in msg for msg in logs)

    # 4. Căn cứ mã 4 -> trả city_missing=True, không mở rương
    events.clear()
    res4 = process_city_resource_cycle(gw, 404, "DaHuy", settings, cache, notify=logs.append)
    assert res4["city_missing"] is True
    assert events == []

    # 5. set_current_city thất bại -> không mở rương
    events.clear()
    gw.switch_ret = 8600
    res5 = process_city_resource_cycle(gw, 10254, "NB", settings, cache, notify=logs.append)
    assert res5["opened_tn_box"] is False
    assert not any(e.startswith("chest:") for e in events)

    # 6. Captcha ret=110 từ resource_info -> nâng CaptchaRequired
    gw.resource_info = lambda _cid: {"ret": 110}
    with pytest.raises(CaptchaRequired):
        process_city_resource_cycle(gw, 10129, "ThienNam", settings, cache, notify=logs.append)
