from linhvuong.gateway import GatewayClient
from linhvuong.roster import fetch_roster

# Payload chuẩn Server 58 (/api/city/list, /api/city/pageofficial, /api/city/pagemytroopslist)
CITY_LIST = {
    "ret": 0,
    "data": {
        "items": [
            {
                "m_ltype": 1,
                "m_lid": 15230,
                "m_szname": "NB",
                "m_lmap_id": 738765,
                "m_lx_pos": 193,
                "m_ly_pos": 202,
                "m_lowner_cityid": 0,
                "m_llevel": 4,
            },
            {
                "m_ltype": 1,
                "m_lid": 15237,
                "m_szname": "ThienNam",
                "m_lmap_id": 738800,
                "m_lx_pos": 230,
                "m_ly_pos": 244,
                "m_lowner_cityid": 0,
                "m_llevel": 2,
            },
            {
                "m_ltype": 5,
                "m_lid": -1085,
                "m_szname": "Go",
                "m_lmap_id": 738900,
                "m_lx_pos": 196,
                "m_ly_pos": 203,
                "m_lowner_cityid": 15230,
                "m_llevel": 1,
            },
        ]
    },
}
CIVIL = {
    "ret": 0,
    "data": {
        "ret": 0,
        "list": [
            [15230, "NB", 193, 202, [[417513, "匡昊毅", "", 1, 1, 0, 84, 100, 980, 980, 104, 16, 120, 840, 73]]],
            [-1085, "Go", 196, 203, [[417514, "邢澎法", "", 1, 0, 0, 1, 100, 110, 110, 10, 13, 10, 10, 0]]],
            [15237, "ThienNam", 230, 244, [[417521, "成籁彩", "", 1, 1, 0, 41, 100, 510, 510, 54, 14, 64, 410, 30]]],
        ],
    },
}
MARTIAL = {
    "ret": 0,
    "data": {
        "ret": 0,
        "list": [
            [15230, "NB", 193, 202, [[417506, "廉复卢", "", 2, 0, 0, 3, 97, 230, 230, 12, 11, 29, 30, 3]]],
            [15237, "ThienNam", 230, 244, []],
        ],
    },
}
ARMY = {
    "ret": 0,
    "data": {
        "ret": 0,
        "list": [[15230, "NB", [[417506, "廉复卢", 0, "", 0, 102, 95, 102, 0, 100, 0, 501]]]],
    },
}


class Resp:
    status_code = 200

    def __init__(self, p):
        self.p = p

    def json(self):
        return self.p


class FakeSession:
    def __init__(self):
        self.calls = []
        self.cookies = {"uid": "95"}

    def get(self, url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        p = dict(params or {})
        self.calls.append((path, p))
        if path == "/api/city/list":
            return Resp(CITY_LIST)
        if path == "/api/city/pageofficial":
            return Resp(CIVIL if int(p.get("heroType", 2)) == 1 else MARTIAL)
        if path == "/api/city/pagemytroopslist":
            return Resp(ARMY)
        return Resp(None)


def roster():
    return fetch_roster(GatewayClient(58, FakeSession(), sleep=lambda s: None))


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
        def get(self, url, params=None, headers=None, timeout=None):
            path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
            p = dict(params or {})
            self.calls.append((path, p))
            if path == "/api/city/list":
                return Resp({
                    "ret": 0,
                    "data": {
                        "items": [
                            {"m_ltype": 1, "m_lid": 15230, "m_szname": "NB", "m_lx_pos": 100, "m_ly_pos": 100, "m_llevel": 3},
                            {"m_ltype": 5, "m_lid": -3035, "m_szname": "TienTuyen", "m_lx_pos": 105, "m_ly_pos": 105, "m_llevel": 1},
                        ]
                    },
                })
            if path == "/api/city/pageofficial":
                if int(p.get("heroType", 2)) == 1:
                    return Resp({"ret": 0, "data": {"ret": 0, "list": []}})
                return Resp({
                    "ret": 0,
                    "data": {
                        "ret": 0,
                        "list": [
                            [-3035, "TienTuyen", 105, 105, [
                                [97376, "席定韩", "", 2, 0, 0, 5, 100, 150, 150, 17, 14, 19, 50, 0]
                            ]]
                        ],
                    },
                })
            if path == "/api/city/pagemytroopslist":
                if str(p.get("cityTentId")) == "-3035":
                    return Resp({
                        "ret": 0,
                        "data": {
                            "ret": 0,
                            "list": [
                                [-3035, "TienTuyen", [
                                    [97376, "席定韩", 0, "", 0, 0, 1500, 0, 0, 100, 0, 501]
                                ]]
                            ],
                        },
                    })
                return Resp({"ret": 0, "data": {"ret": 0, "list": []}})
            return Resp(None)

    gw = GatewayClient(58, CampSession(), sleep=lambda s: None)
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
    gw = GatewayClient(58, session, sleep=lambda s: None)
    r = fetch_roster(gw, only_base_ids=[15230])
    troop_calls = [c for c in session.calls if c[0] == "/api/city/pagemytroopslist"]
    assert len(troop_calls) == 1
    assert str(troop_calls[0][1]["cityTentId"]) == "15230"
    gens = r.generals_of(15230)
    assert len(gens) > 0


def test_fetch_roster_resolves_tacticians_for_zero_troop_martial_generals():
    """Server 58 pagemytroopslist bỏ qua Võ tướng không có lính -> phải truy vấn Common.ashx?id=14 qua Văn quan special_status=3."""
    class TacticianSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.post_calls = []

        def get(self, url, params=None, headers=None, timeout=None):
            path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
            p = dict(params or {})
            self.calls.append((path, p))
            if path == "/api/city/list":
                return Resp({
                    "ret": 0,
                    "data": {
                        "items": [
                            {"m_ltype": 1, "m_lid": 10254, "m_szname": "TT", "m_lx_pos": 180, "m_ly_pos": 67, "m_llevel": 4},
                        ]
                    },
                })
            if path == "/api/city/pageofficial":
                if int(p.get("heroType", 2)) == 1:
                    return Resp({
                        "ret": 0,
                        "list": [[10254, "TT", 180, 67, [
                            [15061, "TT", "公孙渊", 1, 1, 0, 77, 100, 312, 870, 58, 70, 75, 770, 219],
                            [6201, "I_01", "吕蒙", 1, 0, 0, 233, 100, 2600, 2600, 166, 234, 192, 2330, 765],
                            [6331, "I_05", "神魔·诸葛亮", 1, 3, 0, 101, 100, 1978, 1978, 343, 732, 600, 1010, 0],
                            [6332, "I_06", "神魔·诸葛亮", 1, 3, 0, 101, 100, 1988, 1988, 350, 694, 620, 1010, 0],
                        ]]],
                    })
                return Resp({
                    "ret": 0,
                    "list": [[10254, "TT", 180, 67, [
                        [6330, "I_01", "神魔·曹操", 2, 0, 0, 102, 100, 2160, 2160, 890, 136, 746, 1020, 3],
                        [6341, "I_06", "神魔·曹操", 2, 0, 0, 101, 100, 2070, 2070, 864, 145, 710, 1010, 0],
                        [6346, "I_08", "神魔·曹操", 2, 0, 0, 101, 100, 1800, 1800, 815, 113, 720, 1010, 0],
                    ]]],
                })
            if path == "/api/city/pagemytroopslist":
                # Võ 6330 có lính và đã gắn 6332 -> không cần hỏi id=14 cho 6332;
                # Võ 6346 có 0 lính nên vắng mặt trong pagemytroopslist, nhưng Văn 6331 (special_status=3) đang theo 6346.
                return Resp({
                    "ret": 0,
                    "list": [[10254, "TT", [
                        [6330, "I_01", 6332, "I_06", 0, 149, 99, 149, 0, 100, 0],
                    ]]],
                })
            return Resp(None)

        def post(self, url, data=None, headers=None, timeout=None):
            self.post_calls.append((url, dict(data or {})))
            if "Common.ashx?id=14" in url:
                gid = str((data or {}).get("lGeneralID", ""))
                if gid == "6331":
                    return Resp({"ret": 0, "type": 1, "job": 3, "partner_id": 6346, "partner_name": "I_08"})
                if gid == "6332":
                    return Resp({"ret": 0, "type": 1, "job": 3, "partner_id": 6330, "partner_name": "I_01"})
            return Resp({"ret": 1})

    session = TacticianSession()
    gw = GatewayClient(58, session, sleep=lambda s: None)
    r = fetch_roster(gw)
    by_id = {g.id: g for g in r.generals_of(10254)}

    assert by_id[6330].tactician_id == 6332
    assert by_id[6330].tactician_name == "I_06"
    assert by_id[6346].tactician_id == 6331
    assert by_id[6346].tactician_name == "I_05"
    assert by_id[6341].tactician_id == 0
    assert r.active_tactician_ids() == {6331, 6332}
    # Chỉ gọi Common.ashx?id=14 cho Văn quan chưa xuất hiện trong pagemytroopslist (6331)
    assert [d["lGeneralID"] for _, d in session.post_calls] == ["6331"]
