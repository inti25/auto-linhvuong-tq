import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import CaptchaRequired, TaskContext
from linhvuong.tasks.goi_dan import VONG_LINH, GoiDan


class Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class FakeServer:
    def __init__(self, map_views=None, handlers=None):
        self.map_views = map_views or {}
        self.handlers = handlers or {}
        self.calls = []
        self.cookies = {"uid": "95"}

    def _lookup_handler(self, key):
        aliases = {
            "/api/city/list": "Common.ashx?id=29",
            "/api/city/pageofficial": "Common.ashx?id=32",
            "/api/city/pagemytroopslist": "Common.ashx?id=76",
            "/api/city/pagearmament": "Common.ashx?id=27",
            "/api/city/current": "City.ashx?id=50",
        }
        if key in self.handlers:
            return self.handlers[key]
        alias = aliases.get(key)
        if alias and alias in self.handlers:
            return self.handlers[alias]
        return {"ret": 0}

    def get(self, url, params=None, headers=None, timeout=None):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        p = dict(params or {})
        self.calls.append((path, p))
        if path == "/api/map/query":
            return Resp(self.map_views.get(int(p["mid"]), {"npc_tent": []}))
        handler = self._lookup_handler(path)
        if callable(handler):
            return Resp(handler())
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1] if "/GateWay/" in url else "/" + url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
        self.calls.append((key, dict(data or {})))
        handler = self._lookup_handler(key)
        if callable(handler):
            return Resp(handler())
        if isinstance(handler, list):
            return Resp(handler.pop(0))
        return Resp(handler)


def ctx_for(server, locks=None):
    gw = GatewayClient(53, server, sleep=lambda s: None)
    locks = locks or TargetLocks()
    alerts = []
    scanner = Scanner(gw, locks, delay=0.0, sleep=lambda s: None)
    return TaskContext(gw, scanner, locks, notify=alerts.append), alerts


def man(x, y, tid, mtype):
    return [tid, mtype, mid_from_coords(x, y)]


def test_goi_dan_vong_linh_uses_item_268():
    mid = mid_from_coords(2, 2)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(2, 2, 888, VONG_LINH)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(2, 2), radius=5, mode="vong_linh", city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    # Kiểm tra các API đã được gọi
    api_names = [k for k, _ in server.calls if k != "/api/map/query"]
    assert "/api/city/current" in api_names
    assert "OPT.ashx?id=69" in api_names
    assert "OPT.ashx?id=53" in api_names

    # Kiểm tra payload gọi Vong Linh (type 33, param1 268)
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "33"
    assert call_69["param1"] == "268"


def test_goi_dan_thuong_calculates_mid_and_uses_type_63():
    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    terrain_mid = mid_from_coords(21, 20)
    empty_mid = mid_from_coords(19, 20)

    def handle_call_69():
        # Server xóa Man ở vị trí cũ và đặt về ô đất trống sát thành
        server.map_views[far_mid] = {"npc_tent": []}
        server.map_views[origin_mid] = {"npc_tent": [man(19, 20, 999, 10)]}
        return {"ret": 0}

    server = FakeServer(
        map_views={
            origin_mid: {
                "npc_tent": [],
                "infos": [
                    [origin_mid, 73, 0, 0, origin_mid, 123],
                    [terrain_mid, 41, 0, 0, 0, 0],
                    [empty_mid, 1, 0, 0, 0, 0],
                ],
            },
            far_mid: {"npc_tent": [man(34, 20, 999, 10)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": handle_call_69,
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(20, 20), radius=5, mode="dan", target_type=10, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    # Kiểm tra payload kéo Man thật (type 63, param1=target_id, param2=empty_mid sát thành)
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "63"
    assert call_69["param1"] == "999"
    assert call_69["param2"] == str(empty_mid)

    # Đảm bảo chỉ xuất quân (OPT.ashx?id=53) sau khi đã gọi (OPT.ashx?id=69) về sát thành
    api_seq = [k for k, _ in server.calls if k in ("OPT.ashx?id=69", "OPT.ashx?id=53")]
    assert api_seq == ["OPT.ashx?id=69", "OPT.ashx?id=53"]
    call_53 = [d for k, d in server.calls if k == "OPT.ashx?id=53"][0]
    assert call_53["target_id"] == "999"
    assert call_53["lDestID"] == str(empty_mid)


def test_goi_dan_auto_recover_triggers_heal_and_refill():
    mid = mid_from_coords(1, 1)
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(1, 1, 777, VONG_LINH)]}},
        handlers={
            "OPT.ashx?id=53": {"ret": 0},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[15, 16],
        origin=(1, 1),
        radius=5,
        city_id=123,
        auto_recover=True,
        refill_amount=500,
        soldier_type=2,
    )
    out = task.run_once()
    assert out == "attacked"

    # Kiểm tra gọi trị thương (id=31) cho 2 tướng
    heal_calls = [d for k, d in server.calls if k == "OPT.ashx?id=31"]
    assert len(heal_calls) == 2
    assert {c["lGeneralID"] for c in heal_calls} == {"15", "16"}

    # Kiểm tra gọi bổ sung tân binh (id=6)
    refill_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(refill_calls) == 2
    assert refill_calls[0]["lAmount"] == "500"
    assert refill_calls[0]["lSoldierType"] == "2"


def test_goi_dan_stops_on_captcha_at_call():
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 110},
        }
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(0, 0), radius=5, city_id=123)
    with pytest.raises(CaptchaRequired):
        task.run_once()


def test_goi_man_level_selection_uses_correct_target_type():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    empty_mid = mid_from_coords(21, 20)

    def handle_call_69():
        server.map_views[far_mid] = {"npc_tent": []}
        server.map_views[origin_mid] = {"npc_tent": [man(21, 20, 777, 7)]}
        return {"ret": 0}

    server = FakeServer(
        map_views={
            origin_mid: {
                "npc_tent": [],
                "infos": [[empty_mid, 1, 0, 0, 0, 0]],
            },
            far_mid: {"npc_tent": [man(34, 20, 777, 7)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": handle_call_69,
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    # Chọn Cấp 7 - Hung Nô
    task = GoiMan(ctx, generals=[10], origin=(20, 20), radius=5, target_type=7, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "63"
    assert call_69["param1"] == "777"
    assert call_69["param2"] == str(empty_mid)


def test_goi_man_vong_linh_special_type_301():
    from linhvuong.tasks.goi_dan import GoiMan

    mid = mid_from_coords(3, 3)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(3, 3, 3010, 301)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    # Chọn Vong Linh (ID 301)
    task = GoiMan(ctx, generals=[10], origin=(3, 3), radius=5, target_type=301, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "33"
    assert call_69["param1"] == "268"


def test_goi_man_multiple_target_types_round_robin():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    empty_mid = mid_from_coords(21, 20)
    server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(34, 20, 7001, 7), man(34, 20, 8001, 8)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 0, "new_target_id": 7001, "new_target_mid": empty_mid, "new_target_type": 7},
                {"ret": 0, "new_target_id": 8001, "new_target_mid": empty_mid, "new_target_type": 8},
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(20, 20), radius=5, target_types=[7, 8], city_id=123)

    # Lượt 1: Kéo mục tiêu loại 7 (ID 7001)
    res1 = task.run_once()
    assert res1 == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert calls_69[0]["param1"] == "7001"
    assert calls_69[0]["param2"] == str(empty_mid)

    # Lượt 2: Xoay vòng sang loại 8 (ID 8001)
    res2 = task.run_once()
    assert res2 == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert calls_69[1]["param1"] == "8001"
    assert calls_69[1]["param2"] == str(empty_mid)


def test_goi_man_multiple_target_types_fallback_on_failure():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    empty_mid = mid_from_coords(21, 20)
    server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(34, 20, 7002, 7), man(34, 20, 8002, 8)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 208},  # Lượt đầu kéo loại 7 thất bại (mục tiêu không tồn tại)
                {"ret": 0, "new_target_id": 8002, "new_target_mid": empty_mid, "new_target_type": 8},  # Fallback sang loại 8 thành công
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(20, 20), radius=5, target_types=[7, 8], city_id=123)

    out = task.run_once()
    assert out == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls_69) == 2
    assert calls_69[0]["param1"] == "7002"
    assert calls_69[1]["param1"] == "8002"
    assert not ctx.locks.is_locked(7002)


def test_goi_dan_idle_check_returns_generals_busy():
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [123, "City", 0, 0, [[50, "Gen 50", 1, 100, 100, 1]]],  # status=1 (bận)
                ],
            }
        }
    )
    ctx, alerts = ctx_for(server)
    task = GoiDan(ctx, generals=[50], origin=(2, 2), radius=5, city_id=123, check_idle=True)
    out = task.run_once()
    assert out == "generals_busy"
    assert any("đang bận" in a for a in alerts)
    # Không phát sinh request gọi quái hay đánh
    assert [k for k, _ in server.calls if k != "/api/city/pageofficial"] == []


def test_goi_dan_attacks_multiple_batches_for_more_than_3_generals():
    mid = mid_from_coords(2, 2)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(2, 2, 888, VONG_LINH)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    delays = []
    ctx, alerts = ctx_for(server)
    # Chọn 4 tướng: Đợt 1 (3 tướng: 10, 11, 12) -> Đợt 2 (1 tướng: 13)
    task = GoiDan(
        ctx,
        generals=[10, 11, 12, 13],
        origin=(2, 2),
        radius=5,
        mode="vong_linh",
        city_id=123,
        sleep_fn=delays.append,
    )
    out = task.run_once()
    assert out == "called_and_attacked"

    attack_calls = [d for k, d in server.calls if k == "OPT.ashx?id=53"]
    assert len(attack_calls) == 2
    assert attack_calls[0]["generals"] == "10,11,12"
    assert attack_calls[0]["target_id"] == "888"
    assert attack_calls[1]["generals"] == "13"
    assert attack_calls[1]["target_id"] == "888"
    assert delays == [0.5]
    assert any("Đợt 1/2" in a for a in alerts)
    assert any("Đợt 2/2" in a for a in alerts)


def test_goi_dan_enters_active_battle_and_switches_formation_when_generals_in_battlefield():
    """Khi tướng Gọi Man đã ở trong chiến trường (status=16), GoiDan.run_once() tự động vào
    chiến trường điều khiển và đổi trận hình khắc chế thay vì bỏ qua với generals_busy.
    """
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [123, "City", 2, 2, [[50, "Gen 50", "", 2, 0, 16]]],
                ],
            },
            "Common.ashx?id=40": {
                "ret": 0,
                "come": [],
                "goto": [],
                "battle": [[1002, 888, "亡灵部队", 2, 2, 8]],
            },
            "Common.ashx?id=4": {
                "ret": 0,
                "battle_id": 777001,
                "next_left": 8,
                "atside": 1,
                "city": [888, "亡灵部队", 2, 2],
                "myside": [[1, 123, "City", 2, 2, 100, "Player", "Gen 50", 0, 5000, 0, 0, 100, 50]],
                "enemy": [],
            },
            "OPT.ashx?id=24": [
                {
                    "ret": 0,
                    "site": "亡灵部队",
                    "mapid": 888,
                    "bout": 1,
                    "bout_left": 8,
                    "attack_total": 1,
                    "defend_total": 1,
                    "troops": [
                        [1, "Player", 100, "Gen 50", 50, "", 123, 0, 1, 100, 0, 0, 5000, 5000, 0, 0, 0, 0, "", 1],
                        [11, "", 0, "亡灵部队", 0, "", 0, 0, 4, 100, 0, 3000, 0, 3000, 0, 0, 0, 0, "", 16],
                    ],
                },
                {"ret": 13, "troops": []},
            ],
            "OPT.ashx?id=54": {"ret": 0},
            "OPT.ashx?id=57": {"ret": 0},
            "OPT.ashx?id=26": {"ret": 0, "last_tips_id": 0, "tips": []},
        }
    )
    server.cookies = {"uid": "100"}
    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[50],
        origin=(2, 2),
        radius=5,
        city_id=123,
        check_idle=True,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "battle_tracked"
    opt57_calls = [d for k, d in server.calls if k == "OPT.ashx?id=57"]
    assert len(opt57_calls) == 1
    assert opt57_calls[0]["lGeneralID"] == "50"
    assert opt57_calls[0]["lBattleArray"] == "2"


def test_goi_dan_target_army_provisioning_and_morale_waiting():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(2, 2)
    # Giả lập:
    # 1. Common.ashx?id=32: Tướng rảnh rỗi (status=0), morale=80, upgrading_time=0
    # 2. Common.ashx?id=76: Tướng có 200 lính bộ
    # 3. Server handlers cho OPT.ashx:
    #    id=31: trị thương
    #    id=41: chiêu mộ tân binh
    #    id=6: biên chế lính
    #    id=47: nâng sĩ khí
    #    id=69: gọi quái
    #    id=53: xuất quân
    c32 = {
        "ret": 0,
        "list": [
            [123, "City", 0, 0, [[50, "Gen 50", "", 2, 0, 0, 4, 80, 240, 240, 0]]]
        ],
    }
    c76 = {
        "ret": 0,
        "list": [
            [123, "City", [[50, "Gen 50", 0, "", 0, 200, 0, 0, 0, 80, 0, 200]]]
        ],
    }
    server = FakeServer(
        map_views={mid: {"npc_tent": []}},
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "Common.ashx?id=27": {"ret": 0, "list": [[123, "City", 10000]]},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=47": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(2, 2, 999, VONG_LINH)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[50],
        origin=(2, 2),
        radius=5,
        city_id=123,
        target_army=TargetArmy(infantry=1000, cavalry=0, archers=0),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    # Lần chạy 1: Morale hiện tại là 80 < 95 -> Bổ sung quân (+800), kích hoạt nâng sĩ khí (+10), trả về waiting_morale và CHƯA xuất quân
    out1 = task.run_once()
    assert out1 == "waiting_morale"

    # Kiểm tra đã trị thương (id=31)
    assert any(k == "OPT.ashx?id=31" for k, d in server.calls)
    # Kiểm tra đã biên chế +800 lính bộ (id=6)
    opt6_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(opt6_calls) == 1
    assert opt6_calls[0]["lAmount"] == "800"
    assert opt6_calls[0]["lSoldierType"] == "1"

    # Kiểm tra đã kích hoạt nâng sĩ khí (id=47)
    opt47_calls = [d for k, d in server.calls if k == "OPT.ashx?id=47"]
    assert len(opt47_calls) == 1
    assert opt47_calls[0]["lAddPoint"] == "10"

    # Không được gọi quái (id=69) hay xuất quân (id=53) khi sĩ khí chưa hoàn tất
    assert not any(k == "OPT.ashx?id=69" for k, d in server.calls)
    assert not any(k == "OPT.ashx?id=53" for k, d in server.calls)

    # Giả lập lần chạy 2: Morale đã đạt 95 và upgrading_time = 0
    server.calls.clear()
    c32["list"][0][4][0][7] = 95
    c76["list"][0][2][0][5] = 1000  # Đã đủ 1000 lính bộ
    c76["list"][0][2][0][9] = 95    # Morale đạt 95

    out2 = task.run_once()
    assert out2 in ("attacked", "called_and_attacked")
    assert any(k == "OPT.ashx?id=69" for k, d in server.calls)
    assert any(k == "OPT.ashx?id=53" for k, d in server.calls)


def test_goi_dan_concurrent_morale_training_all_generals():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(2, 2)
    # Giả lập 3 tướng trong đội Gọi Dân/Gọi Man đều có sĩ khí thấp (80, 85, 75 < 95)
    c32 = {
        "ret": 0,
        "list": [
            [
                123,
                "City",
                0,
                0,
                [
                    [50, "Gen 50", "", 2, 0, 0, 4, 80, 240, 240, 0],
                    [51, "Gen 51", "", 2, 0, 0, 4, 85, 240, 240, 0],
                    [52, "Gen 52", "", 2, 0, 0, 4, 75, 240, 240, 0],
                ],
            ]
        ],
    }
    c76 = {
        "ret": 0,
        "list": [
            [
                123,
                "City",
                [
                    [50, "Gen 50", 0, "", 0, 1000, 0, 0, 0, 80, 0, 200],
                    [51, "Gen 51", 0, "", 0, 1000, 0, 0, 0, 85, 0, 200],
                    [52, "Gen 52", 0, "", 0, 1000, 0, 0, 0, 75, 0, 200],
                ],
            ]
        ],
    }
    server = FakeServer(
        map_views={mid: {"npc_tent": []}},
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "Common.ashx?id=27": {"ret": 0, "list": [[123, "City", 10000]]},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=47": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(2, 2, 999, VONG_LINH)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[50, 51, 52],
        origin=(2, 2),
        radius=5,
        city_id=123,
        target_army=TargetArmy(infantry=1000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "waiting_morale"

    # Kiểm tra: CẢ 3 TƯỚNG đều được gửi lệnh nâng sĩ khí OPT 47 trong cùng chu kỳ!
    opt47_calls = [d for k, d in server.calls if k == "OPT.ashx?id=47"]
    assert len(opt47_calls) == 3
    called_gids = {int(d["lGeneralID"]) for d in opt47_calls}
    assert called_gids == {50, 51, 52}

    # Chưa được gọi quái (id=69) hay xuất quân (id=53) khi đang chờ sĩ khí
    assert not any(k == "OPT.ashx?id=69" for k, d in server.calls)
    assert not any(k == "OPT.ashx?id=53" for k, d in server.calls)


def test_goi_dan_detects_and_logs_boss_man():
    """Kiểm tra Gọi Man nhận diện Boss Man (VD: 卑弥呼 tại vị trí 19 với flag=32)
    và log cảnh báo chính xác ra nhật ký:
    VD: 🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!"""
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [123, "City", 2, 2, [[50, "Gen 50", "", 2, 0, 16]]],
                ],
            },
            "Common.ashx?id=40": {
                "ret": 0,
                "come": [],
                "goto": [],
                "battle": [[1002, 888, "倭国部队", 2, 2, 8]],
            },
            "Common.ashx?id=4": {
                "ret": 0,
                "battle_id": 777001,
                "next_left": 8,
                "atside": 1,
                "city": [888, "倭国部队", 2, 2],
                "myside": [[1, 123, "City", 2, 2, 100, "Player", "Gen 50", 0, 5000, 0, 0, 100, 50]],
                "enemy": [],
            },
            "OPT.ashx?id=24": [
                {
                    "ret": 0,
                    "site": "倭国部队",
                    "mapid": 888,
                    "bout": 1,
                    "bout_left": 8,
                    "attack_total": 1,
                    "defend_total": 1,
                    "troops": [
                        [1, "Player", 100, "Gen 50", 50, "", 123, 0, 1, 100, 0, 0, 5000, 5000, 0, 0, 0, 0, "", 1],
                        [19, "", 0, "卑弥呼", 0, "", 0, 0, 4, 100, 0, 3000, 0, 3000, 0, 0, 0, 0, "", 32],
                    ],
                },
                {"ret": 13, "troops": []},
            ],
            "OPT.ashx?id=54": {"ret": 0},
            "OPT.ashx?id=57": {"ret": 0},
            "OPT.ashx?id=26": {"ret": 0, "last_tips_id": 0, "tips": []},
        }
    )
    server.cookies = {"uid": "100"}
    ctx, _ = ctx_for(server)
    notifies = []
    ctx.notify = lambda m: notifies.append(m)

    task = GoiDan(
        ctx,
        generals=[50],
        origin=(2, 2),
        radius=5,
        city_id=123,
        check_idle=True,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "battle_tracked"

    boss_alerts = [m for m in notifies if "🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!" in m]
    assert len(boss_alerts) == 1, f"Gọi Man phải log cảnh báo boss đúng 1 lần: {notifies}"
    assert "🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!" in boss_alerts[0]


def test_goi_dan_vong_linh_call_error_notifications():
    """Kiểm tra gọi Vong Linh (ID 301) thông báo chính xác mã lỗi 236, 90, 39."""
    # 1. Mã 236: Chưa mở sự kiện Vong Linh
    server236 = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 236},
        }
    )
    ctx236, alerts236 = ctx_for(server236)
    task236 = GoiDan(ctx236, generals=[10], origin=(2, 2), radius=5, mode="vong_linh", city_id=123)
    out236 = task236.run_once()
    assert out236 == "call_failed:236"
    assert any("chưa mở sự kiện Vong Linh" in a and "236" in a for a in alerts236)

    # 2. Mã 90: Hết đạo cụ
    server90 = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 90},
        }
    )
    ctx90, alerts90 = ctx_for(server90)
    task90 = GoiDan(ctx90, generals=[10], origin=(2, 2), radius=5, mode="vong_linh", city_id=123)
    out90 = task90.run_once()
    assert out90 == "call_failed:90"
    assert any("Hết Bùa Vong Linh" in a and "90" in a for a in alerts90)


def test_goi_dan_vong_linh_retries_scanning_with_delay_after_call():
    """Khi OPT.ashx?id=69 thành công (ret=0), Vong Linh cần 1-2s mới xuất hiện trên map.
    GoiDan phải thử quét lại có trễ và mở rộng bán kính quét tìm Vong Linh.
    """
    sleeps = []

    def delayed_map_view():
        if len(sleeps) >= 1:
            return {"npc_tent": [man(2, 4, 888, VONG_LINH)]}
        return {"npc_tent": []}

    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        }
    )
    orig_get = server.get

    def custom_get(url, params=None, headers=None, timeout=None):
        if "/api/map/query" in url:
            return Resp(delayed_map_view())
        return orig_get(url, params, headers, timeout)

    server.get = custom_get

    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[10],
        origin=(2, 2),
        radius=5,
        mode="vong_linh",
        city_id=123,
        sleep_fn=sleeps.append,
    )
    out = task.run_once()
    assert out == "called_and_attacked"
    assert len(sleeps) >= 1  # Có gọi sleep giữa các lượt quét


def test_goi_dan_locks_existing_target_before_attack():
    """Mục tiêu có sẵn quanh thành phải được khóa (TargetLocks) trước khi tấn công."""
    mid = mid_from_coords(2, 2)
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(2, 2, 777, VONG_LINH)]}},
        handlers={"OPT.ashx?id=53": {"ret": 0}},
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(2, 2), radius=5, mode="vong_linh", city_id=123)
    out = task.run_once()
    assert out == "attacked"
    assert ctx.locks.is_locked(777)


def test_goi_dan_runner_stops_on_call_failed_236_and_90():
    """GoiDanAutoRunner phải dừng nhiệm vụ khi gặp mã lỗi 236 (chưa mở sự kiện) hoặc 90 (hết bùa)
    thay vì spam vòng lặp vô hạn lên server.
    """
    from linhvuong.dashboard import GoiDanAutoRunner

    class MockTask:
        mode = "vong_linh"
        stop_event = None

        def __init__(self, ret_err):
            self.ret_err = ret_err
            self.calls = 0

        def run_once(self):
            self.calls += 1
            return self.ret_err

    # 1. Thử nghiệm mã lỗi 236
    task236 = MockTask("call_failed:236")
    logs236, statuses236 = [], []
    runner236 = GoiDanAutoRunner(task236, interval=0.01, log_cb=logs236.append, status_cb=statuses236.append)
    runner236.run()
    assert task236.calls == 1
    assert any("236" in l for l in logs236)
    assert "Sự kiện chưa mở" in statuses236

    # 2. Thử nghiệm mã lỗi 90
    task90 = MockTask("call_failed:90")
    logs90, statuses90 = [], []
    runner90 = GoiDanAutoRunner(task90, interval=0.01, log_cb=logs90.append, status_cb=statuses90.append)
    runner90.run()
    assert task90.calls == 1
    assert any("90" in l for l in logs90)
    assert "Hết đạo cụ" in statuses90


@pytest.mark.parametrize("err_code", [208, 209])
def test_goi_man_pull_errors_208_209_never_attack_distant_target_and_release_lock(err_code):
    """Lỗi 208/209 khi dùng type=63 không được xuất quân đánh mục tiêu ở xa và phải nhả khóa."""
    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    empty_mid = mid_from_coords(21, 20)
    server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(34, 20, 1105, 1)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": {"ret": err_code},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, alerts = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(20, 20), radius=5, mode="dan", target_type=1, city_id=123)
    out = task.run_once()

    assert out == f"call_failed:{err_code}"
    assert not [k for k, _ in server.calls if k == "OPT.ashx?id=53"]
    assert not ctx.locks.is_locked(1105)
    assert any(str(err_code) in msg for msg in alerts)


def test_goi_man_retries_next_empty_tile_on_39():
    """Nếu ô trống đầu tiên sát thành trả lỗi 39 (bị chiếm), phải thử ô trống kế tiếp trước khi bỏ qua."""
    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    tile1 = mid_from_coords(21, 20)
    tile2 = mid_from_coords(20, 22)

    calls_69 = []

    def handle_call_69():
        calls_69.append(len(calls_69))
        if len(calls_69) == 1:
            return {"ret": 39}
        server.map_views[far_mid] = {"npc_tent": []}
        server.map_views[origin_mid] = {"npc_tent": [man(20, 22, 1106, 1)]}
        return {"ret": 0}

    server = FakeServer(
        map_views={
            origin_mid: {
                "npc_tent": [],
                "infos": [
                    [tile1, 1, 0, 0, 0, 0],
                    [tile2, 1, 0, 0, 0, 0],
                ],
            },
            far_mid: {"npc_tent": [man(34, 20, 1106, 1)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": handle_call_69,
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(20, 20), radius=5, mode="dan", target_type=1, city_id=123)
    out = task.run_once()

    assert out == "called_and_attacked"
    sent_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert [d["param2"] for d in sent_69] == [str(tile1), str(tile2)]
    assert len([k for k, _ in server.calls if k == "OPT.ashx?id=53"]) == 1


def test_goi_man_no_source_on_map_does_not_call_api_with_type_id():
    """Không tìm thấy Man trên bản đồ thì không gửi OPT.ashx?id=69 với param1=t_type giả."""
    origin_mid = mid_from_coords(20, 20)
    server = FakeServer(
        map_views={origin_mid: {"npc_tent": [], "infos": [[mid_from_coords(21, 20), 1, 0, 0, 0, 0]]}},
        handlers={"City.ashx?id=50": {"ret": 0}},
    )
    ctx, alerts = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(20, 20), radius=5, mode="dan", target_type=1, city_id=123)
    out = task.run_once()

    assert out == "no_target"
    assert not [k for k, _ in server.calls if k == "OPT.ashx?id=69"]
    assert not [k for k, _ in server.calls if k == "OPT.ashx?id=53"]
    assert any("1" in msg for msg in alerts)


def test_goi_man_refuses_attack_if_pulled_target_not_near_city():
    """Chỉ xuất quân sau khi đã xác nhận Man thực sự nằm sát thành (dist <= 6)."""
    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    empty_mid = mid_from_coords(21, 20)
    server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(34, 20, 1107, 1)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            # Server báo ret=0 nhưng trả tọa độ vẫn ở xa thành
            "OPT.ashx?id=69": {"ret": 0, "new_target_id": 1107, "new_target_mid": far_mid, "new_target_type": 1},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(20, 20), radius=5, mode="dan", target_type=1, city_id=123)
    out = task.run_once()

    assert out == "target_not_found_after_call"
    assert not [k for k, _ in server.calls if k == "OPT.ashx?id=53"]
    assert not ctx.locks.is_locked(1107)


def test_goi_dan_large_radius_pulls_distant_man_to_city_before_attack():
    """Khi đặt bán kính quét lớn (vd radius=100), phải dùng đạo cụ kéo Man ở xa về sát thành rồi mới xuất quân."""
    origin_mid = mid_from_coords(180, 67)
    far_mid = mid_from_coords(250, 67)  # 70 ô (10 * step=7)
    empty_mid = mid_from_coords(181, 67)

    def handle_call_69():
        server.map_views[far_mid] = {"npc_tent": []}
        server.map_views[origin_mid] = {"npc_tent": [man(181, 67, 2201, 1)]}
        return {"ret": 0}

    server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(250, 67, 2201, 1)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": handle_call_69,
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[6330], origin=(180, 67), radius=100, mode="dan", target_type=1, city_id=10254)
    out = task.run_once()

    assert out == "called_and_attacked"
    api_seq = [k for k, _ in server.calls if k in ("OPT.ashx?id=69", "OPT.ashx?id=53")]
    assert api_seq == ["OPT.ashx?id=69", "OPT.ashx?id=53"]
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["param1"] == "2201"
    assert call_69["param2"] == str(empty_mid)
    call_53 = [d for k, d in server.calls if k == "OPT.ashx?id=53"][0]
    assert call_53["lDestID"] == str(empty_mid)


def test_goi_dan_existing_man_outside_near_city_radius_is_pulled_not_marched():
    """Man nằm trong viewport gốc nhưng ngoài ngưỡng sát thành (dist > 6) cũng phải kéo về sát thành trước khi đánh."""
    origin_mid = mid_from_coords(180, 67)
    empty_mid = mid_from_coords(181, 67)

    def handle_call_69():
        server.map_views[origin_mid] = {"npc_tent": [man(181, 67, 2202, 1)]}
        return {"ret": 0}

    server = FakeServer(
        map_views={
            origin_mid: {
                "npc_tent": [man(189, 67, 2202, 1)],  # Cách 9 ô (> 6 ô)
                "infos": [[empty_mid, 1, 0, 0, 0, 0]],
            },
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": handle_call_69,
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    ctx.scanner.workers = 1
    task = GoiDan(ctx, generals=[6330], origin=(180, 67), radius=5, mode="dan", target_type=1, city_id=10254)
    out = task.run_once()

    assert out == "called_and_attacked"
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["param1"] == "2202"
    assert call_69["param2"] == str(empty_mid)
    call_53 = [d for k, d in server.calls if k == "OPT.ashx?id=53"][0]
    assert call_53["lDestID"] == str(empty_mid)


def test_find_empty_mids_near_supports_negative_coordinates():
    """Fallback ô trống khi map_view không trả infos phải hỗ trợ tọa độ âm hợp lệ (MAP_MIN..MAP_MAX)."""
    from linhvuong.coords import coords_from_mid

    server = FakeServer(map_views={mid_from_coords(-1, -1): {"npc_tent": []}})
    ctx, _ = ctx_for(server)
    mids = ctx.scanner.find_empty_mids_near(-1, -1, max_dist=5)

    assert mids
    coords = {coords_from_mid(m) for m in mids}
    assert (-2, -1) in coords
    assert (-1, -2) in coords


def test_goi_man_vong_linh_209_not_found_falls_back_to_next_type():
    """ADR-0024 §5: Khi Vong Linh (301) trả ret=209 nhưng không quét thấy quanh thành, phải fallback sang loại kế tiếp."""
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    empty_mid = mid_from_coords(21, 20)
    server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(34, 20, 3301, 1)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 209},  # Vong Linh (301) báo 209 nhưng quanh thành không có mục tiêu
                {"ret": 0, "new_target_id": 3301, "new_target_mid": empty_mid, "new_target_type": 1},
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(
        ctx,
        generals=[10],
        origin=(20, 20),
        radius=5,
        target_types=[301, 1],
        city_id=123,
        sleep_fn=lambda _s: None,
    )
    out = task.run_once()

    assert out == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls_69) == 2
    assert calls_69[0]["type"] == "33"
    assert calls_69[1]["type"] == "63"
    assert calls_69[1]["param1"] == "3301"


def test_goi_man_auto_swap_tactician_and_fallback_when_no_replacement():
    """GoiDan tự động đổi mưu sĩ thể lực thấp khi đủ điều kiện và giữ nguyên khi không có người thay thế."""
    origin_mid = mid_from_coords(180, 67)
    empty_mid = mid_from_coords(181, 67)

    def _pageofficial():
        hero_type = str(server.calls[-1][1].get("heroType", "2"))
        if hero_type == "1":
            gens = [
                [701, "VanThap", 100, 100, 2, 0, 20, 100, 15, 100],
                [702, "VanKhoe", 100, 100, 0, 0, 50, 100, 90, 100],
            ]
        else:
            gens = [[6330, "VoChinh", 100, 100, 0, 0, 60, 100, 95, 100]]
        return {"ret": 0, "data": {"ret": 0, "list": [[10254, "TT", 180, 67, gens]]}}

    def handle_call_69():
        server.map_views[origin_mid] = {"npc_tent": [man(181, 67, 2299, 1)], "infos": [[empty_mid, 1, 0, 0, 0, 0]]}
        return {"ret": 0}

    server = FakeServer(
        map_views={origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]}},
        handlers={
            "/api/city/list": {
                "ret": 0,
                "data": {"items": [{"m_ltype": 1, "m_lid": 10254, "m_szname": "TT", "m_lx_pos": 180, "m_ly_pos": 67, "m_llevel": 1}]},
            },
            "/api/city/pageofficial": _pageofficial,
            "/api/city/pagemytroopslist": {
                "ret": 0,
                "data": {"ret": 0, "list": [[10254, "TT", [[6330, "VoChinh", 701, "VanThap", 0, 100, 0, 0, 0, 100, 0]]]]},
            },
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=5": {"ret": 0},
            "OPT.ashx?id=69": handle_call_69,
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[6330],
        origin=(180, 67),
        radius=5,
        mode="dan",
        target_type=1,
        city_id=10254,
        auto_swap_tactician=True,
        min_tactician_stamina=30.0,
    )
    out = task.run_once()
    assert out == "called_and_attacked"
    post_seq = [k for k, _ in server.calls if k in ("OPT.ashx?id=5", "OPT.ashx?id=69", "OPT.ashx?id=53")]
    assert post_seq == ["OPT.ashx?id=5", "OPT.ashx?id=5", "OPT.ashx?id=69", "OPT.ashx?id=53"]

    # Ngưỡng 95%: VanKhoe 90% không đạt -> không gọi id=5 (giữ VanThap) và vẫn gọi đánh
    server.calls.clear()
    server.map_views[origin_mid] = {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]}
    alerts2 = []
    task_high = GoiDan(
        ctx_for(server)[0],
        generals=[6330],
        origin=(180, 67),
        radius=5,
        mode="dan",
        target_type=1,
        city_id=10254,
        auto_swap_tactician=True,
        min_tactician_stamina=95.0,
    )
    task_high.ctx.notify = alerts2.append
    out2 = task_high.run_once()
    assert out2 == "called_and_attacked"
    assert not any(k == "OPT.ashx?id=5" for k, _ in server.calls)
    assert any("giữ nguyên" in a.lower() for a in alerts2)


def test_goi_man_helper_caller_pulls_via_alt_gateway_and_main_attacks():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(180, 67)
    far_mid = mid_from_coords(194, 67)
    empty_mid = mid_from_coords(181, 67)

    main_server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(194, 67, 5501, 1)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )

    def alt_handle_call_69():
        main_server.map_views[far_mid] = {"npc_tent": []}
        main_server.map_views[origin_mid] = {
            "npc_tent": [man(181, 67, 5501, 1)],
            "infos": [[empty_mid, 1, 0, 0, 0, 0]],
        }
        return {"ret": 0}

    alt_server = FakeServer(
        handlers={
            "OPT.ashx?id=69": alt_handle_call_69,
        }
    )
    alt_gw = GatewayClient(58, alt_server, sleep=lambda _s: None)
    ctx, alerts = ctx_for(main_server)

    task = GoiMan(
        ctx,
        generals=[6330],
        origin=(180, 67),
        radius=5,
        target_types=[1, 2],
        city_id=10254,
        caller_gateway=alt_gw,
        caller_username="inti00",
        sleep_fn=lambda _s: None,
    )
    out = task.run_once()
    assert out == "called_and_attacked"

    # Tài khoản chính chỉ chuyển thành & xuất quân, không gọi id=69
    assert any(k == "/api/city/current" for k, _ in main_server.calls)
    assert not any(k == "OPT.ashx?id=69" for k, _ in main_server.calls)
    assert any(k == "OPT.ashx?id=53" and d["target_id"] == "5501" for k, d in main_server.calls)

    # Tài khoản gọi hộ chỉ gọi OPT.ashx?id=69 (type=63), không đổi thành sang thành tài khoản chính
    assert not any(k == "/api/city/current" for k, _ in alt_server.calls)
    alt_69 = [d for k, d in alt_server.calls if k == "OPT.ashx?id=69"]
    assert len(alt_69) == 1
    assert alt_69[0]["type"] == "63"
    assert alt_69[0]["param1"] == "5501"
    assert alt_69[0]["param2"] == str(empty_mid)
    assert any("[inti00]" in m for m in alerts)


def test_goi_man_helper_caller_blocks_vong_linh_301():
    import pytest
    from linhvuong.tasks.goi_dan import GoiMan

    main_server = FakeServer()
    alt_gw = GatewayClient(58, FakeServer(), sleep=lambda _s: None)
    ctx, _ = ctx_for(main_server)

    with pytest.raises(ValueError, match="Vong Linh"):
        GoiMan(ctx, generals=[10], origin=(10, 10), target_types=[301], city_id=101, caller_gateway=alt_gw)

    with pytest.raises(ValueError, match="Vong Linh"):
        GoiMan(ctx, generals=[10], origin=(10, 10), target_types=[1, 301], city_id=101, caller_gateway=alt_gw)


def test_goi_man_helper_caller_errors_stop_without_fallback_and_near_man_skips_alt():
    from linhvuong.helper_caller import HelperCallerLoginError
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(20, 20)
    far_mid = mid_from_coords(34, 20)
    empty_mid = mid_from_coords(21, 20)

    # 1. Đã có Man sát thành -> tài khoản chính tự đánh không đụng tới tài khoản gọi hộ
    near_server = FakeServer(
        map_views={origin_mid: {"npc_tent": [man(21, 20, 4444, 1)], "infos": [[empty_mid, 1, 0, 0, 0, 0]]}},
        handlers={"OPT.ashx?id=53": {"ret": 0}},
    )
    alt_server = FakeServer()
    alt_gw = GatewayClient(58, alt_server, sleep=lambda _s: None)
    ctx_near, _ = ctx_for(near_server)
    assert GoiMan(ctx_near, generals=[10], origin=(20, 20), radius=5, target_types=[1], city_id=123, caller_gateway=alt_gw).run_once() == "attacked"
    assert alt_server.calls == []

    # 2. Hết đạo cụ (ret=90) -> trả call_failed:90, nhả khóa, không fallback sang main
    main_server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            far_mid: {"npc_tent": [man(34, 20, 5555, 1)]},
        },
        handlers={"City.ashx?id=50": {"ret": 0}},
    )
    alt_90 = FakeServer(handlers={"OPT.ashx?id=69": {"ret": 90}})
    ctx, alerts = ctx_for(main_server)
    caller_alerts = []
    t90 = GoiMan(
        ctx,
        generals=[10],
        origin=(20, 20),
        radius=5,
        target_types=[1, 2],
        city_id=123,
        caller_gateway=GatewayClient(58, alt_90, sleep=lambda _s: None),
        caller_username="inti00",
        on_caller_alert=lambda kind, msg: caller_alerts.append((kind, msg)),
    )
    assert t90.run_once() == "call_failed:90"
    assert not ctx.locks.is_locked(5555)
    assert not any(k == "OPT.ashx?id=69" for k, _ in main_server.calls)
    assert any("inti00" in m and "90" in m for m in alerts)
    assert caller_alerts and caller_alerts[0][0] == "out_of_items"

    # 3. Captcha ở tài khoản gọi hộ -> caller_captcha (không raise CaptchaRequired khóa tài khoản chính)
    alt_cap = FakeServer(handlers={"OPT.ashx?id=69": {"ret": 110}})
    caller_alerts.clear()
    t_cap = GoiMan(
        ctx,
        generals=[10],
        origin=(20, 20),
        radius=5,
        target_types=[1],
        city_id=123,
        caller_gateway=GatewayClient(58, alt_cap, sleep=lambda _s: None),
        caller_username="inti00",
        on_caller_alert=lambda kind, msg: caller_alerts.append((kind, msg)),
    )
    assert t_cap.run_once() == "caller_captcha"
    assert not ctx.locks.is_locked(5555)
    assert caller_alerts and caller_alerts[0][0] == "captcha"

    # 4. Lỗi đăng nhập tài khoản gọi hộ -> caller_login_failed & nhả khóa
    class BadProvider:
        username = "inti00"

        def acquire_gateway(self):
            raise HelperCallerLoginError("Sai mật khẩu")

    caller_alerts.clear()
    t_bad = GoiMan(
        ctx,
        generals=[10],
        origin=(20, 20),
        radius=5,
        target_types=[1],
        city_id=123,
        caller_provider=BadProvider(),
        caller_username="inti00",
        on_caller_alert=lambda kind, msg: caller_alerts.append((kind, msg)),
    )
    assert t_bad.run_once() == "caller_login_failed"
    assert not ctx.locks.is_locked(5555)
    assert caller_alerts and caller_alerts[0][0] == "login_failed"


def test_helper_caller_session_lifecycle_and_runner_stop():
    from linhvuong.dashboard.runners import GoiDanAutoRunner
    from linhvuong.engine import AutomationEngine
    from linhvuong.helper_caller import HelperCallerSession

    # 1. Tái sử dụng phiên từ workspace không gọi login_fn và không đóng phiên khi close()
    reused_gw = GatewayClient(58, FakeServer(), sleep=lambda _s: None)
    login_calls = []
    p_reuse = HelperCallerSession(
        server_id=58,
        username="inti00",
        password="",
        session_lookup=lambda sid, usr: reused_gw if sid == 58 and usr == "inti00" else None,
        login_fn=lambda *a, **kw: login_calls.append((a, kw)),
    )
    assert p_reuse.acquire_gateway() is reused_gw
    assert p_reuse.reused is True
    assert login_calls == []
    p_reuse.close()

    # 2. Mở phiên độc lập kế thừa proxy và đóng sạch requests.Session khi close()
    p_own = HelperCallerSession(
        server_id=58,
        username="inti00",
        password="secret",
        proxy_raw="1.2.3.4:8080",
        login_fn=lambda sess, sid, u, p, proxy=None: login_calls.append((sess, sid, u, p, proxy)),
    )
    gw_own = p_own.acquire_gateway()
    assert gw_own is not None
    assert p_own.reused is False
    assert len(login_calls) == 1
    assert login_calls[0][1:5] == (58, "inti00", "secret", "http://1.2.3.4:8080")
    assert p_own._session is not None
    p_own.close()
    assert p_own._session is None
    assert p_own._gateway is None

    # 3. AutomationEngine và GoiDanAutoRunner dừng ngay trên caller_captcha và gọi task.close()
    closed = []

    class DummyTask:
        mode = "dan"

        def run_once(self):
            return "caller_captcha"

        def close(self):
            closed.append("closed")

    eng = AutomationEngine()
    eng.start("goidan", DummyTask(), interval=30.0, jitter=0.0)
    eng.get_runner("goidan").join(timeout=2.0)
    assert not eng.is_running("goidan")
    assert closed == ["closed"]

    runner = GoiDanAutoRunner(DummyTask(), interval=30.0, log_cb=lambda _m: None, status_cb=lambda _s: None)
    runner.start()
    runner.join(timeout=2.0)
    assert not runner.is_alive()
    assert closed == ["closed", "closed"]


def test_goi_man_helper_caller_fallback_scans_around_helper_city():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(180, 67)
    empty_mid = mid_from_coords(179, 67)
    alt_city_mid = mid_from_coords(412, 204)
    alt_man_mid = mid_from_coords(426, 204)

    main_server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            alt_city_mid: {"npc_tent": []},
            alt_man_mid: {"npc_tent": [man(426, 204, 8802, 2)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )

    def alt_call_69():
        main_server.map_views[alt_man_mid] = {"npc_tent": []}
        main_server.map_views[origin_mid] = {
            "npc_tent": [man(179, 67, 8802, 2)],
            "infos": [[empty_mid, 1, 0, 0, 0, 0]],
        }
        return {"ret": 0}

    alt_server = FakeServer(
        handlers={
            "/api/city/list": {
                "ret": 0,
                "data": {"items": [{"m_lid": 11082, "m_szname": "inca", "m_lx_pos": 412, "m_ly_pos": 204}]},
            },
            "OPT.ashx?id=69": alt_call_69,
        }
    )
    alt_gw = GatewayClient(58, alt_server, sleep=lambda _s: None)
    ctx, _ = ctx_for(main_server)
    task = GoiMan(
        ctx,
        generals=[6330],
        origin=(180, 67),
        radius=5,
        target_types=[2],
        city_id=10254,
        caller_gateway=alt_gw,
        caller_username="inti00",
        sleep_fn=lambda _s: None,
    )
    assert task.run_once() == "called_and_attacked"
    alt_69 = [d for k, d in alt_server.calls if k == "OPT.ashx?id=69"]
    assert len(alt_69) == 1
    assert alt_69[0]["param1"] == "8802"
    assert alt_69[0]["param2"] == str(empty_mid)
    assert len([k for k, _ in alt_server.calls if k == "/api/city/list"]) == 1


def test_goi_dan_even_troops_balances_before_recruit_and_refreshes_morale():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(2, 2)
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(2, 2, 777, VONG_LINH)]}},
        handlers={
            "/api/city/list": {"ret": 0, "data": {"items": [{"m_ltype": 1, "m_lid": 123, "m_szname": "City", "m_lx_pos": 2, "m_ly_pos": 2, "m_llevel": 1}]}},
            "/api/city/pageofficial": {
                "ret": 0,
                "data": {
                    "ret": 0,
                    "list": [[123, "City", 2, 2, [
                        [50, "Gen 50", "", 2, 0, 0, 4, 100, 240, 240, 0],
                        [51, "Gen 51", "", 2, 0, 0, 4, 100, 240, 240, 0],
                    ]]],
                },
            },
            "/api/city/pagemytroopslist": {
                "ret": 0,
                "data": {
                    "ret": 0,
                    "list": [[123, "City", [
                        [50, "Gen 50", 0, "", 0, 2000, 0, 0, 0, 100, 0, 0],
                        [51, "Gen 51", 0, "", 0, 1000, 0, 0, 0, 100, 0, 0],
                    ]]],
                },
            },
            "/api/city/pagearmament": {"ret": 0, "data": {"ret": 0, "list": [[123, "City", 5000]]}},
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=39": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(
        ctx,
        generals=[50, 51],
        origin=(2, 2),
        radius=5,
        city_id=123,
        target_army=TargetArmy(infantry=1800),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        even_troops=True,
        sleep_fn=lambda s: None,
    )
    assert task.run_once() == "attacked"
    eps = [k for k, _ in server.calls]
    assert eps.index("OPT.ashx?id=39") < eps.index("OPT.ashx?id=6")
    opt39 = [d for k, d in server.calls if k == "OPT.ashx?id=39"]
    assert len(opt39) == 1
    assert opt39[0]["lFromGeneralID"] == "50"
    assert opt39[0]["lToGeneralID"] == "51"
    assert opt39[0]["infantry"] == "500"
    opt6 = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert [(d["lGeneralID"], d["lAmount"]) for d in opt6] == [("50", "300"), ("51", "300")]
    assert sum(1 for k, _ in server.calls if k == "/api/city/pagemytroopslist") >= 2










