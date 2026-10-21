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

