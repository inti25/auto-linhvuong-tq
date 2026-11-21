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

    def post(self, url, data=None, headers=None, timeout=None):
        key = url.split("/GateWay/")[1]
        self.calls.append((key, dict(data or {})))
        if key == "Map.ashx?id=6":
            return Resp(self.map_views.get(int(data["mid"]), {"npc_tent": []}))
        handler = self.handlers.get(key, {"ret": 0})
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
    api_names = [k for k, _ in server.calls if k != "Map.ashx?id=6"]
    assert "City.ashx?id=50" in api_names
    assert "OPT.ashx?id=69" in api_names
    assert "OPT.ashx?id=53" in api_names

    # Kiểm tra payload gọi Vong Linh (type 33, param1 268)
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "33"
    assert call_69["param1"] == "268"


def test_goi_dan_thuong_calculates_mid_and_uses_type_63():
    origin_mid = mid_from_coords(5, 5)
    dest_mid = mid_from_coords(5, 6)
    distant_mid = mid_from_coords(12, 12)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_mid, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            distant_mid: {
                "npc_tent": [man(12, 12, 999, 10)],
            },
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: (
                server.map_views.update(
                    {
                        origin_mid: {
                            "infos": [
                                [origin_mid, 1, 0, 0, 0, 123],
                                [dest_mid, 1, 0, 0, 0, 0],
                            ],
                            "npc_tent": [man(5, 6, 999, 10)],
                        },
                        distant_mid: {"npc_tent": []},
                    }
                )
                or {"ret": 0}
            ),
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(5, 5), radius=5, mode="dan", target_type=10, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    # Kiểm tra payload kéo Man về ô đất trống gần thành (type=63, param1=target_id, param2=dest_mid)
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "63"
    assert call_69["param1"] == "999"
    assert call_69["param2"] == str(dest_mid)


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

    origin_mid = mid_from_coords(3, 3)
    dest_mid = mid_from_coords(4, 3)
    distant_mid = mid_from_coords(10, 10)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_mid, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            distant_mid: {
                "npc_tent": [man(10, 10, 777, 7)],
            },
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: (
                server.map_views.update(
                    {
                        origin_mid: {
                            "infos": [
                                [origin_mid, 1, 0, 0, 0, 123],
                                [dest_mid, 1, 0, 0, 0, 0],
                            ],
                            "npc_tent": [man(4, 3, 777, 7)],
                        },
                        distant_mid: {"npc_tent": []},
                    }
                )
                or {"ret": 0}
            ),
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    # Chọn Cấp 7 - Hung Nô
    task = GoiMan(ctx, generals=[10], origin=(3, 3), radius=5, target_type=7, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "63"
    assert call_69["param1"] == "777"
    assert call_69["param2"] == str(dest_mid)


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

    origin_mid = mid_from_coords(4, 4)
    dest_mid = mid_from_coords(5, 4)
    mid_7 = mid_from_coords(11, 11)
    mid_8 = mid_from_coords(18, 18)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_mid, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            mid_7: {"npc_tent": [man(11, 11, 7001, 7)]},
            mid_8: {"npc_tent": [man(18, 18, 8001, 8)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 0, "new_target_id": 7001, "new_target_mid": dest_mid, "new_target_type": 7},
                {"ret": 0, "new_target_id": 8001, "new_target_mid": dest_mid, "new_target_type": 8},
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(4, 4), radius=5, target_types=[7, 8], city_id=123)

    # Lượt 1: Kéo loại 7 (#7001)
    res1 = task.run_once()
    assert res1 == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert calls_69[0]["param1"] == "7001"
    assert calls_69[0]["param2"] == str(dest_mid)

    # Lượt 2: Xoay vòng kéo loại 8 (#8001)
    res2 = task.run_once()
    assert res2 == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert calls_69[1]["param1"] == "8001"
    assert calls_69[1]["param2"] == str(dest_mid)


def test_goi_man_multiple_target_types_fallback_on_failure():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(4, 4)
    dest_mid = mid_from_coords(5, 4)
    mid_7 = mid_from_coords(25, 25)
    mid_8 = mid_from_coords(18, 18)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_mid, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            mid_7: {"npc_tent": [man(25, 25, 7001, 7)]},
            mid_8: {"npc_tent": [man(18, 18, 8002, 8)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 201},  # Lượt đầu kéo loại 7 thất bại
                {"ret": 0, "new_target_id": 8002, "new_target_mid": dest_mid, "new_target_type": 8},  # Fallback sang loại 8 thành công
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(4, 4), radius=5, target_types=[7, 8], city_id=123)

    out = task.run_once()
    assert out == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls_69) == 2
    assert calls_69[0]["param1"] == "7001"
    assert calls_69[1]["param1"] == "8002"


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
    # Không phát sinh request gọi Man hay đánh
    assert [k for k, _ in server.calls if k != "Common.ashx?id=32"] == []


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
    orig_post = server.post

    def custom_post(url, data=None, headers=None, timeout=None):
        if "Map.ashx?id=6" in url:
            return Resp(delayed_map_view())
        return orig_post(url, data, headers, timeout)

    server.post = custom_post

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


def test_goi_man_returns_no_target_when_no_pullable_man_exists():
    from linhvuong.tasks.goi_dan import GoiMan

    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 0},
        },
    )
    ctx, alerts = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(5, 5), radius=5, target_type=10, city_id=123)
    out = task.run_once()
    assert out == "no_target"
    assert [d for k, d in server.calls if k == "OPT.ashx?id=69"] == []
    assert any("Không tìm thấy Man cấp 10" in a for a in alerts)


def test_goi_man_retries_another_empty_tile_when_ret_39():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(5, 5)
    dest_1 = mid_from_coords(5, 6)
    dest_2 = mid_from_coords(6, 5)
    dest_3 = mid_from_coords(5, 4)
    dest_4 = mid_from_coords(4, 5)
    distant_mid = mid_from_coords(12, 12)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_1, 1, 0, 0, 0, 0],
                    [dest_2, 1, 0, 0, 0, 0],
                    [dest_3, 1, 0, 0, 0, 0],
                    [dest_4, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            distant_mid: {"npc_tent": [man(12, 12, 999, 10)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 39},
                {"ret": 39},
                {"ret": 39},
                {"ret": 0, "new_target_id": 999, "new_target_mid": dest_4, "new_target_type": 10},
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(5, 5), radius=5, target_type=10, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert len(calls_69) == 4
    assert {c["param2"] for c in calls_69} == {str(dest_1), str(dest_2), str(dest_3), str(dest_4)}


def test_goi_man_releases_pull_lock_when_pull_fails():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(5, 5)
    dest_mid = mid_from_coords(5, 6)
    distant_mid = mid_from_coords(12, 12)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_mid, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            distant_mid: {"npc_tent": [man(12, 12, 7001, 7)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 90},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(5, 5), radius=5, target_type=7, city_id=123)
    out = task.run_once()
    assert out == "call_failed:90"
    assert not ctx.locks.is_locked(7001)


def test_goi_man_round_robin_falls_back_when_target_not_found_after_call():
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(4, 4)
    dest_mid = mid_from_coords(5, 4)
    mid_7 = mid_from_coords(25, 25)
    mid_8 = mid_from_coords(18, 18)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_mid, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            mid_7: {"npc_tent": [man(25, 25, 7001, 7)]},
            mid_8: {"npc_tent": [man(18, 18, 8002, 8)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 0},  # Loại 7 gọi xong nhưng không thấy Man trên bản đồ
                {"ret": 0, "new_target_id": 8002, "new_target_mid": dest_mid, "new_target_type": 8},
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(4, 4), radius=5, target_types=[7, 8], city_id=123, sleep_fn=lambda _: None)
    out = task.run_once()
    assert out == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert [c["param1"] for c in calls_69] == ["7001", "8002"]


def test_goi_man_fallback_empty_tiles_respect_map_bounds():
    from linhvuong.coords import MAP_MAX, MAP_MIN, coords_from_mid
    from linhvuong.tasks.goi_dan import GoiMan

    server = FakeServer()
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(MAP_MAX, MAP_MAX), radius=5, city_id=123)
    mids = task._find_empty_mids_near_origin()
    assert mids
    for mid in mids:
        x, y = coords_from_mid(mid)
        assert MAP_MIN <= x <= MAP_MAX
        assert MAP_MIN <= y <= MAP_MAX


def test_goi_man_taken_invalidates_map_cache_and_locks_with_owner():
    from linhvuong.tasks.base import RET_TAKEN_BY_OTHER
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(4, 4)
    dest_mid = mid_from_coords(5, 4)
    distant_mid = mid_from_coords(11, 11)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [
                    [origin_mid, 1, 0, 0, 0, 123],
                    [dest_mid, 1, 0, 0, 0, 0],
                ],
                "npc_tent": [],
            },
            distant_mid: {"npc_tent": [man(11, 11, 8002, 8)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": {"ret": 0, "new_target_id": 8002, "new_target_mid": dest_mid, "new_target_type": 8},
            "OPT.ashx?id=53": {"ret": RET_TAKEN_BY_OTHER},
        },
    )
    ctx, _ = ctx_for(server)
    invalidate_calls = []
    ctx.gateway.invalidate_map_cache = lambda: invalidate_calls.append(True)

    task = GoiMan(ctx, generals=[10], origin=(4, 4), radius=5, target_type=8, city_id=123)
    out = task.run_once()
    assert out == "taken"
    assert len(invalidate_calls) == 1
    # Chủ sở hữu khóa phải là city_id=123 -> owner=999 bị coi là đang khóa bởi người khác
    assert ctx.locks.is_locked_by_other(8002, owner=999)
    assert not ctx.locks.is_locked_by_other(8002, owner=123)


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


def test_find_empty_mids_near_s1_s57_sparse_infos_falls_back_excluding_occupied():
    """Trên S1-S57 nếu Map.ashx?id=6 chỉ trả infos thưa (các ô bận/mỏ) mà không liệt kê ô trống tile_type=1, vẫn phải fallback bỏ qua ô đã chiếm."""
    from linhvuong.coords import coords_from_mid

    ox, oy = 50, 50
    origin_mid = mid_from_coords(ox, oy)
    occupied_mid_info = mid_from_coords(51, 50)
    occupied_mid_city = mid_from_coords(50, 51)
    occupied_mid_man = mid_from_coords(49, 50)
    server = FakeServer(
        map_views={
            origin_mid: {
                "infos": [[occupied_mid_info, 3, 0, 0, 0, 0]],
                "citys": [[1, "Other", 5, occupied_mid_city]],
                "npc_tent": [man(49, 50, 5001, 7)],
            }
        }
    )
    ctx, _ = ctx_for(server)
    mids = ctx.scanner.find_empty_mids_near(ox, oy, max_dist=5)

    assert mids
    assert occupied_mid_info not in mids
    assert occupied_mid_city not in mids
    assert occupied_mid_man not in mids
    assert origin_mid not in mids
    assert mid_from_coords(50, 49) in mids
    assert all(coords_from_mid(m) != (ox, oy) for m in mids)


def test_goi_man_marks_busy_target_on_209_and_tries_next_candidate():
    """Khi kéo một Man gặp ret=209 (đang đóng băng/giao chiến), phải đánh dấu khóa nó và thử Man khác."""
    from linhvuong.tasks.goi_dan import GoiMan

    origin_mid = mid_from_coords(20, 20)
    empty_mid = mid_from_coords(21, 20)
    near_far_mid = mid_from_coords(34, 20)
    farther_mid = mid_from_coords(41, 20)
    server = FakeServer(
        map_views={
            origin_mid: {"npc_tent": [], "infos": [[empty_mid, 1, 0, 0, 0, 0]]},
            near_far_mid: {"npc_tent": [man(34, 20, 1184, 1)]},
            farther_mid: {"npc_tent": [man(41, 20, 1054, 1)]},
        },
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 209},
                {"ret": 0, "new_target_id": 1054, "new_target_mid": empty_mid, "new_target_type": 1},
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(20, 20), radius=5, target_type=1, city_id=123)
    out = task.run_once()

    assert out == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert [c["param1"] for c in calls_69] == ["1184", "1054"]
    assert ctx.locks.is_locked_by_other(1184, owner=123)


def test_goi_man_auto_swap_tactician_and_fallback_when_no_replacement():
    """Gọi Man tự động đổi Mưu sĩ dưới ngưỡng (kể cả khi target_army=None) và giữ nguyên nếu không có Văn quan thay thế."""
    mid = mid_from_coords(2, 2)

    # Case 1: Có Văn quan đạt ngưỡng -> tháo cũ, gán mới (cao -> thấp), sau đó gọi & đánh
    def _c32_ok(body):
        if body.get("type") == "1":
            return {
                "ret": 0,
                "list": [[123, "ThanhA", 2, 2, [
                    [301, "MSYeu", "", 1, 2, 0, 60, 100, 20, 100, 0, 0, 0, 0, 0],
                    [302, "VanThap", "", 1, 0, 0, 30, 100, 100, 100, 0, 0, 0, 0, 0],
                    [303, "VanCao", "", 1, 0, 0, 90, 100, 35, 100, 0, 0, 0, 0, 0],
                ]]],
            }
        return {"ret": 0, "list": [[123, "ThanhA", 2, 2, [[10, "TrieuVan", "", 2, 0, 0, 80, 100, 90, 100, 0, 0, 0, 0, 0]]]]}

    server1 = FakeServer(
        handlers={
            "Common.ashx?id=32": lambda: _c32_ok(server1.calls[-1][1]),
            "Common.ashx?id=76": {"ret": 0, "list": [[123, "ThanhA", [[10, "TrieuVan", 301, "MSYeu", 0, 0, 5000, 0, 0, 100, 0]]]]},
            "OPT.ashx?id=5": {"ret": 0},
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server1.map_views.update({mid: {"npc_tent": [man(2, 2, 888, VONG_LINH)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        }
    )
    ctx1, alerts1 = ctx_for(server1)
    task1 = GoiDan(
        ctx1,
        generals=[10],
        origin=(2, 2),
        radius=5,
        mode="vong_linh",
        city_id=123,
        check_idle=False,
        auto_swap_tactician=True,
        min_tactician_stamina=30,
    )
    assert task1.run_once() == "called_and_attacked"
    tac_calls1 = [d for k, d in server1.calls if k == "OPT.ashx?id=5"]
    assert [(d["lType"], d["lGeneralID"], d["lFollowGeneralID"]) for d in tac_calls1] == [
        ("0", "301", "0"),
        ("3", "303", "10"),
    ]
    assert any("VanCao" in m for m in alerts1)

    # Case 2: Không có Văn quan nào >= 40% -> không gọi OPT.ashx?id=5, vẫn gọi & đánh bình thường
    def _c32_none(body):
        if body.get("type") == "1":
            return {
                "ret": 0,
                "list": [[123, "ThanhA", 2, 2, [
                    [301, "MSYeu", "", 1, 2, 0, 60, 100, 20, 100, 0, 0, 0, 0, 0],
                    [302, "VanYeu", "", 1, 0, 0, 90, 100, 35, 100, 0, 0, 0, 0, 0],
                ]]],
            }
        return {"ret": 0, "list": [[123, "ThanhA", 2, 2, [[10, "TrieuVan", "", 2, 0, 0, 80, 100, 90, 100, 0, 0, 0, 0, 0]]]]}

    server2 = FakeServer(
        handlers={
            "Common.ashx?id=32": lambda: _c32_none(server2.calls[-1][1]),
            "Common.ashx?id=76": {"ret": 0, "list": [[123, "ThanhA", [[10, "TrieuVan", 301, "MSYeu", 0, 0, 5000, 0, 0, 100, 0]]]]},
            "OPT.ashx?id=5": {"ret": 0},
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server2.map_views.update({mid: {"npc_tent": [man(2, 2, 889, VONG_LINH)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        }
    )
    ctx2, alerts2 = ctx_for(server2)
    task2 = GoiDan(
        ctx2,
        generals=[10],
        origin=(2, 2),
        radius=5,
        mode="vong_linh",
        city_id=123,
        check_idle=False,
        auto_swap_tactician=True,
        min_tactician_stamina=40,
    )
    assert task2.run_once() == "called_and_attacked"
    assert [d for k, d in server2.calls if k == "OPT.ashx?id=5"] == []
    assert any("không có Văn quan đủ thể lực" in m for m in alerts2)












