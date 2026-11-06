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
    mid = mid_from_coords(5, 5)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(5, 5, 999, 10)]}}) or {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiDan(ctx, generals=[10], origin=(5, 5), radius=5, mode="dan", target_type=10, city_id=123)
    out = task.run_once()
    assert out == "called_and_attacked"

    # Kiểm tra payload gọi dân thường (type 63, param1 target_type, param2 mid)
    call_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"][0]
    assert call_69["type"] == "63"
    assert call_69["param1"] == "10"
    assert call_69["param2"] == str(mid)


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

    mid = mid_from_coords(3, 3)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": lambda: server.map_views.update({mid: {"npc_tent": [man(3, 3, 777, 7)]}}) or {"ret": 0},
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
    assert call_69["param1"] == "7"


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

    mid = mid_from_coords(4, 4)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 0, "new_target_id": 7001, "new_target_mid": mid, "new_target_type": 7},
                {"ret": 0, "new_target_id": 8001, "new_target_mid": mid, "new_target_type": 8},
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = GoiMan(ctx, generals=[10], origin=(4, 4), radius=5, target_types=[7, 8], city_id=123)

    # Lượt 1: Triệu hồi loại 7
    res1 = task.run_once()
    assert res1 == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert calls_69[0]["param1"] == "7"

    # Lượt 2: Triệu hồi xoay vòng sang loại 8
    res2 = task.run_once()
    assert res2 == "called_and_attacked"
    calls_69 = [d for k, d in server.calls if k == "OPT.ashx?id=69"]
    assert calls_69[1]["param1"] == "8"


def test_goi_man_multiple_target_types_fallback_on_failure():
    from linhvuong.tasks.goi_dan import GoiMan

    mid = mid_from_coords(4, 4)
    server = FakeServer(
        handlers={
            "City.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=69": [
                {"ret": 201},  # Lượt đầu gọi loại 7 thất bại (hết lệnh bài)
                {"ret": 0, "new_target_id": 8002, "new_target_mid": mid, "new_target_type": 8},  # Fallback sang loại 8 thành công
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
    assert calls_69[0]["param1"] == "7"
    assert calls_69[1]["param1"] == "8"


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





