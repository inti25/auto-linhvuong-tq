from linhvuong.gateway import GatewayClient
from linhvuong.roster import fetch_roster

# Payload thật ghi lại từ server 57 (rút gọn)
CITIES = {"ret": 0, "city": [[15230, "NB", 3561, 0, 880, 300, 0, -1180, 24, 0, 0],
                             [15237, "ThienNam", 0, 210, 410, 0, 0, -175, 12, 0, 0]]}
CIVIL = {"ret": 0, "list": [
    [15230, "NB", 193, 202, [[417513, "匡昊毅", "", 1, 1, 0, 84, 100, 980, 980, 104, 16, 120, 840, 73]]],
    [-1085, "Go", 196, 203, [[417514, "邢澎法", "", 1, 0, 0, 1, 100, 110, 110, 10, 13, 10, 10, 0]]],
    [15237, "ThienNam", 230, 244, [[417521, "成籁彩", "", 1, 1, 0, 41, 100, 510, 510, 54, 14, 64, 410, 30]]],
]}
MARTIAL = {"ret": 0, "list": [
    [15230, "NB", 193, 202, [[417506, "廉复卢", "", 2, 0, 0, 3, 97, 230, 230, 12, 11, 29, 30, 3]]],
    [15237, "ThienNam", 230, 244, []],
]}
ARMY = {"ret": 0, "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 102, 95, 102, 0, 100, 0, 501]]]]}


class Resp:
    status_code = 200

    def __init__(self, p):
        self.p = p

    def json(self):
        return self.p


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1]
        self.calls.append((key, dict(data)))
        if key == "Common.ashx?id=29":
            return Resp(CITIES)
        if key == "Common.ashx?id=32":
            return Resp(CIVIL if data["type"] == "1" else MARTIAL)
        if key == "Common.ashx?id=76":
            return Resp(ARMY)
        return Resp(None)


def roster():
    return fetch_roster(GatewayClient(57, FakeSession(), sleep=lambda s: None))


def test_lists_cities_in_server_order():
    r = roster()
    assert [(c.id, c.name) for c in r.cities] == [(15230, "NB"), (15237, "ThienNam")]


def test_city_shows_its_civil_and_martial_generals():
    gens = roster().generals_of(15230)
    assert [(g.id, g.role) for g in gens] == [(417513, "van"), (417506, "vo")]
    assert gens[0].name == "匡昊毅"


def test_camp_generals_are_not_attached_to_cities():
    ids = {g.id for c in roster().cities for g in roster().generals_of(c.id)}
    assert 417514 not in ids


def test_general_stats():
    g = roster().generals_of(15230)[0]
    assert (g.level, g.morale, g.stamina, g.stamina_max) == (84, 100, 980, 980)


def test_martial_general_has_army_composition():
    r = roster()
    army = r.army_of(417506)
    assert (army.infantry, army.cavalry, army.archers) == (102, 95, 102)
    assert army.total == 299


def test_civil_general_has_no_army():
    assert roster().army_of(417513) is None


def test_city_without_generals_is_empty():
    assert roster().generals_of(15237)[0].name == "成籁彩"
    assert [g.role for g in roster().generals_of(15237)] == ["van"]


def test_general_status_and_idleness():
    gens = roster().generals_of(15230)
    g_martial = [g for g in gens if g.role == "vo"][0]
    assert g_martial.status == 0
    assert g_martial.upgrading_time == 0
    assert g_martial.is_idle is True
    assert g_martial.status_text == "Rảnh rỗi"


def test_camps_are_tracked_with_generals():
    r = roster()
    assert len(r.camps) == 1
    camp = r.camps[0]
    assert camp.id == -1085
    assert camp.name == "Go"
    assert camp.type == "Doanh trại"
    assert camp.pos_x == 196 and camp.pos_y == 203
    assert camp.is_camp is True
    assert "[Trại]" in camp.display_name

    camp_gens = r.generals_of(-1085)
    assert len(camp_gens) == 1
    assert camp_gens[0].id == 417514
    assert camp_gens[0].role_text == "Văn quan"

    # r.bases contains both cities and camps
    assert len(r.bases) == 3


def test_martial_generals_in_camps_have_army_composition():
    class CampSession(FakeSession):
        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            self.calls.append((key, dict(data or {})))
            if key == "Common.ashx?id=29":
                return Resp({"ret": 0, "city": [[15230, "NB"]]})
            if key == "City.ashx?id=7":
                return Resp({"ret": 0, "infos": [
                    [1, 15230, "NB", 0, 100, 100, 0, 3, 1],
                    [2, -3035, "TienTuyen", 0, 105, 105, 15230, 1, 5], # Doanh trại
                ]})
            if key == "Common.ashx?id=32":
                t = (data or {}).get("type")
                if t == "1":
                    return Resp({"ret": 0, "list": []})
                return Resp({"ret": 0, "list": [
                    [-3035, "TienTuyen", 105, 105, [
                        [97376, "席定韩", "", 2, 0, 0, 5, 100, 150, 150, 17, 14, 19, 50, 0]
                    ]]
                ]})
            if key == "Common.ashx?id=76":
                cid = (data or {}).get("cid")
                if cid == "-3035":
                    return Resp({"ret": 0, "list": [
                        [-3035, "TienTuyen", [
                            [97376, "席定韩", 0, "", 0, 0, 1500, 0, 0, 100, 0, 501]
                        ]]
                    ]})
                return Resp({"ret": 0, "list": []})
            return Resp(None)

    gw = GatewayClient(53, CampSession(), sleep=lambda s: None)
    r = fetch_roster(gw)
    army = r.army_of(97376)
    assert army is not None, "Army of martial general in camp should not be None"
    assert (army.infantry, army.cavalry, army.archers) == (0, 1500, 0)
    assert army.total == 1500

    # Test update_camp_position
    r.update_camp_position(-3035, 120, 130)
    camp = r.base_by_id(-3035)
    assert camp is not None
    assert camp.pos_x == 120
    assert camp.pos_y == 130


def test_fetch_roster_only_queries_specified_base_ids():
    session = FakeSession()
    gw = GatewayClient(57, session, sleep=lambda s: None)
    r = fetch_roster(gw, only_base_ids=[15230])
    c76_calls = [c for c in session.calls if c[0] == "Common.ashx?id=76"]
    assert len(c76_calls) == 1
    assert c76_calls[0][1]["cid"] == "15230"
    gens = r.generals_of(15230)
    assert len(gens) > 0


def test_fetch_roster_resolves_tacticians_for_zero_troop_martial_generals():
    """Common.ashx?id=76 bỏ qua Võ tướng 0 quân -> phải truy vấn Common.ashx?id=14 cho Văn spec 2/3 chưa ánh xạ."""

    class ZeroTroopSession:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            self.calls.append((key, dict(data or {})))
            if key == "Common.ashx?id=29":
                return Resp({"ret": 0, "city": [[15237, "ThienNam"]]})
            if key == "City.ashx?id=7":
                return Resp({"ret": 0, "infos": []})
            if key == "Common.ashx?id=32" and data.get("type") == "1":
                return Resp({
                    "ret": 0,
                    "list": [[15237, "ThienNam", 229, 244, [
                        [6332, "VanCoQuan", "", 1, 3, 0, 100, 100, 1000, 1000, 0, 0, 0, 0, 0],
                        [6331, "VanKhongQuan", "", 1, 3, 0, 101, 100, 1000, 1000, 0, 0, 0, 0, 0],
                        [6333, "VanRanh", "", 1, 0, 0, 90, 100, 900, 900, 0, 0, 0, 0, 0],
                    ]]],
                })
            if key == "Common.ashx?id=32" and data.get("type") == "2":
                return Resp({
                    "ret": 0,
                    "list": [[15237, "ThienNam", 229, 244, [
                        [6330, "VoCoQuan", "", 2, 0, 0, 100, 100, 1000, 1000, 0, 0, 0, 0, 0],
                        [6341, "VoKhongQuan", "", 2, 0, 0, 101, 100, 1000, 1000, 0, 0, 0, 0, 0],
                    ]]],
                })
            if key == "Common.ashx?id=76":
                return Resp({
                    "ret": 0,
                    "list": [[15237, "ThienNam", [[6330, "VoCoQuan", 6332, "VanCoQuan", 0, 100, 0, 0, 0, 100, 0]]]],
                })
            if key == "Common.ashx?id=14":
                return Resp({"ret": 0, "partner_id": 6341})
            return Resp({"ret": 0})

    sess = ZeroTroopSession()
    gw = GatewayClient(57, sess, sleep=lambda s: None)
    r = fetch_roster(gw)
    gens = {g.id: g for g in r.generals_of(15237)}
    assert gens[6330].tactician_id == 6332
    assert gens[6341].tactician_id == 6331
    assert gens[6341].tactician_name == "VanKhongQuan"
    c14_calls = [d for k, d in sess.calls if k == "Common.ashx?id=14"]
    assert [d["lGeneralID"] for d in c14_calls] == ["6331"]


def test_fetch_roster_parses_stat123_and_skill_point_with_short_row_fallback():
    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class _StatSession:
        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            if key == "Common.ashx?id=29":
                return _Resp({"ret": 0, "city": [[15230, "NB"]]})
            if key == "City.ashx?id=7":
                return _Resp({"ret": 0, "infos": []})
            if key == "Common.ashx?id=32" and data.get("type") == "1":
                return _Resp({
                    "ret": 0,
                    "list": [[15230, "NB", 193, 202, [
                        [514181, "NB07", "", 1, 3, 0, 103, 100, 1130, 1130, 89, 120, 43, 1030, 80],
                        [514180, "VanCu", "", 1, 0, 0, 10, 100, 100, 100],
                    ]]],
                })
            if key == "Common.ashx?id=32" and data.get("type") == "2":
                return _Resp({
                    "ret": 0,
                    "list": [[15230, "NB", 193, 202, [
                        [514167, "Vo07", "", 2, 0, 0, 104, 100, 1140, 1140, 112, 17, 109, 1040, 75],
                    ]]],
                })
            return _Resp({"ret": 0, "list": []})

    gw = GatewayClient(57, _StatSession(), sleep=lambda s: None)
    r = fetch_roster(gw)
    by_id = {g.id: g for g in r.generals_of(15230)}
    assert (by_id[514181].stat1, by_id[514181].stat2, by_id[514181].stat3, by_id[514181].skill_point) == (89, 120, 43, 80)
    assert (by_id[514167].stat1, by_id[514167].stat2, by_id[514167].stat3, by_id[514167].skill_point) == (112, 17, 109, 75)
    assert (by_id[514180].stat1, by_id[514180].stat2, by_id[514180].stat3, by_id[514180].skill_point) == (0, 0, 0, 0)


def test_fetch_roster_marks_unreliable_armies_when_c76_fails():
    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class _FailC76Session:
        def __init__(self, c76_resp):
            self.c76_resp = c76_resp

        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            if key == "Common.ashx?id=29":
                return _Resp({"ret": 0, "city": [[22040, "ThienCo5"]]})
            if key == "City.ashx?id=7":
                return _Resp({"ret": 0, "infos": []})
            if key == "Common.ashx?id=32":
                if data.get("type") == "2":
                    return _Resp(
                        {
                            "ret": 0,
                            "list": [[22040, "ThienCo5", 10, 10, [[104488, "TC5_10", "", 2, 0, 0, 10, 100, 1750, 1750, 0]]]],
                        }
                    )
                return _Resp({"ret": 0, "list": []})
            if key == "Common.ashx?id=76":
                if self.c76_resp is None:
                    return _Resp(None)
                return _Resp(self.c76_resp)
            return _Resp({"ret": 0})

    for bad_resp in ({"ret": 198599}, {"ret": 1}):
        gw = GatewayClient(53, _FailC76Session(bad_resp), sleep=lambda s: None)
        r = fetch_roster(gw, only_base_ids=[22040], include_civil=False, include_cities=False)
        assert r.has_reliable_armies(22040) is False
        assert r.army_of(104488) is None

    # Mạng lỗi hoàn toàn (gateway.call trả về None)
    gw_none = GatewayClient(53, _FailC76Session(None), sleep=lambda s: None)
    gw_none.call = lambda ep, aid, d=None, **_kw: None if (ep == "Common.ashx" and aid == 76) else {
        "ret": 0,
        "list": [[22040, "ThienCo5", 10, 10, [[104488, "TC5_10", "", 2, 0, 0, 10, 100, 1750, 1750, 0]]]],
    } if (ep == "Common.ashx" and aid == 32) else {"ret": 0, "city": [[22040, "ThienCo5"]], "infos": []}
    r_none = fetch_roster(gw_none, only_base_ids=[22040], include_civil=False, include_cities=False)
    assert r_none.has_reliable_armies(22040) is False
    assert r_none.army_of(104488) is None


