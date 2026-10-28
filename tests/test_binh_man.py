import pytest

from linhvuong.coords import mid_from_coords
from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import CaptchaRequired, TaskContext
from linhvuong.tasks.binh_man import BinhMan, chebyshev_distance


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


def test_chebyshev_distance():
    assert chebyshev_distance(0, 0, 2, 2) == 2
    assert chebyshev_distance(0, 0, 3, 1) == 3
    assert chebyshev_distance(5, 5, 2, 2) == 3


def test_binh_man_moves_camp_step_by_step_towards_far_target():
    # Mục tiêu tại (5, 5), Trại xuất phát tại (0, 0)
    # Bán kính 10, max_step 2 ô/bước
    target_mid = mid_from_coords(5, 5)
    sleeps = []
    server = FakeServer(
        map_views={
            mid_from_coords(0, 0): {"npc_tent": [man(5, 5, 100, 7)]},
            target_mid: {"npc_tent": [man(5, 5, 100, 7)]},
        },
        handlers={
            "Common.ashx?id=55": {"ret": 0, "frozen": 15},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[1],
        origin=(0, 0),
        radius=10,
        man_types=[7],
        camp_id=9999,
        max_step=2,
        sleep_fn=sleeps.append,
    )

    out = task.run_once()
    assert out == "attacked"

    # Kiểm tra các lần dời Trại qua Common.ashx?id=55
    move_calls = [d for k, d in server.calls if k == "Common.ashx?id=55"]
    # Từ (0,0) -> (2,2) -> (4,4). Khi tại (4,4), khoảng cách tới (5,5) là 1 ô (<= 2 ô) -> dừng dời và tấn công!
    assert len(move_calls) >= 2
    assert sleeps == [15] * len(move_calls)
    assert task.origin == (4, 4)

    # Đã tấn công mục tiêu
    attack_calls = [d for k, d in server.calls if k == "OPT.ashx?id=53"]
    assert len(attack_calls) == 1
    assert attack_calls[0]["target_id"] == "100"


def test_binh_man_handles_obstacle_and_backoff():
    # Mục tiêu tại (4, 4), Trại tại (0, 0)
    # Bước đầu tới (2, 2) bị ret=39 (vướng), bot tự lùi về bước 1 ô (1, 1)
    target_mid = mid_from_coords(4, 4)
    server = FakeServer(
        map_views={mid_from_coords(0, 0): {"npc_tent": [man(4, 4, 101, 7)]}},
        handlers={
            "Common.ashx?id=55": [
                {"ret": 39},  # bước 2 ô thất bại vì vướng
                {"ret": 0, "frozen": 10},  # lùi về 1 ô thành công!
                {"ret": 0, "frozen": 10},  # bước tiếp
            ],
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[1],
        origin=(0, 0),
        radius=10,
        man_types=[7],
        camp_id=8888,
        max_step=2,
        sleep_fn=lambda s: None,
    )
    out = task.run_once()
    assert out == "attacked"


def test_binh_man_retreats_to_parent_city_below_threshold():
    server = FakeServer(
        handlers={
            "OPT.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
        }
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[20, 21],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        camp_id=5555,
        parent_city_id=1001,
        return_threshold=30,
    )

    out = task.run_once(remaining_percent=25.0)
    assert out == "retreated_below_threshold"

    # Kiểm tra điều động về thành mẹ và tái xuất quân
    transit_calls = [d for k, d in server.calls if k == "OPT.ashx?id=50"]
    assert len(transit_calls) == 4  # 2 tướng về thành mẹ + 2 tướng ra lại trại
    # Kiểm tra trị thương và bổ sung lính
    heal_calls = [d for k, d in server.calls if k == "OPT.ashx?id=31"]
    assert len(heal_calls) == 2


def test_binh_man_mode_city_direct_attack():
    # Chế độ 2: Xuất quân thẳng từ Thành đến mục tiêu, hoàn toàn không gọi Common.ashx?id=55 (di trại)
    target_mid = mid_from_coords(12, 12)
    server = FakeServer(
        map_views={
            mid_from_coords(10, 10): {"npc_tent": [man(12, 12, 303, 7)]},
            target_mid: {"npc_tent": [man(12, 12, 303, 7)]},
        },
        handlers={
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,  # MODE_CITY
        city_id=1001,
    )
    out = task.run_once()
    assert out == "attacked"

    # Hoàn toàn không phát sinh request di dời Doanh trại
    move_calls = [d for k, d in server.calls if k == "Common.ashx?id=55"]
    assert len(move_calls) == 0

    # Lệnh tấn công xuất phát thẳng từ thành
    attack_calls = [d for k, d in server.calls if k == "OPT.ashx?id=53"]
    assert len(attack_calls) == 1
    assert attack_calls[0]["target_id"] == "303"


def test_binh_man_mode_city_idle_check_blocks_when_generals_busy():
    # Chế độ 2: Khi tướng đang bận (status != 0), bot tạm dừng và trả về generals_busy
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [
                        1001,
                        "Thành Chủ",
                        10,
                        10,
                        [
                            [10, "Triệu Vân", "vo", 100, 100, 1, 10, 100, 100],  # status = 1 (đang hành quân)
                        ],
                    ]
                ],
            }
        }
    )
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        check_idle=True,
    )
    out = task.run_once()
    assert out == "generals_busy"
    assert any("hành quân" in a or "bận" in a for a in alerts)


def test_binh_man_mode_city_recovers_locally_in_city_without_transit():
    # Chế độ 2: Dưới ngưỡng an toàn, trị thương & mua lính tại chỗ, KHÔNG gọi OPT.ashx?id=50
    server = FakeServer(
        handlers={
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
        }
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[15],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        return_threshold=30,
    )
    out = task.run_once(remaining_percent=20.0)
    assert out == "recovered_in_city"

    # Đảm bảo KHÔNG có lệnh chuyển quân (id=50) giữa thành và trại
    transit_calls = [d for k, d in server.calls if k == "OPT.ashx?id=50"]
    assert len(transit_calls) == 0

    # Trị thương và bù lính tại chỗ cho city_id=1001
    heal_calls = [d for k, d in server.calls if k == "OPT.ashx?id=31"]
    assert len(heal_calls) == 1
    assert heal_calls[0]["lCityTentID"] == "1001"
    assert heal_calls[0]["lGeneralID"] == "15"


def test_binh_man_mode_camp_stays_at_current_origin_when_target_lost():
    # Chế độ 1: Doanh trại dời 1 bước tới (2, 2). Mục tiêu bị người khác đánh mất (ret=230).
    # Doanh trại giữ nguyên tại (2, 2) chứ không lùi về (0, 0).
    server = FakeServer(
        map_views={
            mid_from_coords(0, 0): {"npc_tent": [man(3, 3, 202, 7)]},
        },
        handlers={
            "Common.ashx?id=55": {"ret": 0, "frozen": 5},
            "OPT.ashx?id=53": {"ret": 230},  # ret=230: mục tiêu bị cướp
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[1],
        origin=(0, 0),
        radius=10,
        man_types=[7],
        camp_id=9999,
        mode=1,
        max_step=2,
        sleep_fn=lambda s: None,
    )
    out = task.run_once()
    assert out == "taken"
    # Doanh trại dừng tại tọa độ mới đã tiến tới
    assert task.origin == (2, 2)


def test_binh_man_attacks_multiple_batches_for_more_than_3_generals():
    # Chọn 5 tướng: Đợt 1 (3 tướng), Đợt 2 (2 tướng) cùng tấn công mục tiêu 303
    target_mid = mid_from_coords(12, 12)
    server = FakeServer(
        map_views={
            mid_from_coords(10, 10): {"npc_tent": [man(12, 12, 303, 7)]},
            target_mid: {"npc_tent": [man(12, 12, 303, 7)]},
        },
        handlers={
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    delays = []
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[11, 12, 13, 14, 15],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        sleep_fn=delays.append,
    )
    out = task.run_once()
    assert out == "attacked"

    attack_calls = [d for k, d in server.calls if k == "OPT.ashx?id=53"]
    assert len(attack_calls) == 2
    assert attack_calls[0]["generals"] == "11,12,13"
    assert attack_calls[0]["target_id"] == "303"
    assert attack_calls[1]["generals"] == "14,15"
    assert attack_calls[1]["target_id"] == "303"
    assert delays == [0.5]


def test_binh_man_mode_camp_idle_check_blocks_when_generals_busy():
    # Chế độ 1 (Camp): Khi tướng tại trại đang bận (status != 0), bot tạm dừng và trả về generals_busy
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [9999, "Camp", 0, 0, [[21, "General 21", 1, 100, 100, 1]]],
                ],
            }
        }
    )
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[21],
        origin=(0, 0),
        radius=5,
        man_types=[7],
        mode=1,
        camp_id=9999,
        check_idle=True,
    )
    out = task.run_once()
    assert out == "generals_busy"
    assert any("đang bận" in a for a in alerts)


def test_binh_man_enters_active_battle_and_switches_formation_when_generals_already_in_battlefield():
    """Khi quân đội đã vào chiến trường (status=16 trong Common.ashx?id=32 và có battle trong Common.ashx?id=40),
    BinhMan.run_once() không được bỏ qua với generals_busy mà phải tự vào chiến trường chỉnh trận hình khắc chế.
    """
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [21936, "ThienCo", 280, 237, [[99057, "TP3", "", 2, 0, 16, 31, 100, 363, 410]]],
                ],
            },
            "Common.ashx?id=40": {
                "ret": 0,
                "come": [],
                "goto": [],
                "battle": [[1002, 1002, "倭国部队", 268, 251, 5]],
            },
            "Common.ashx?id=4": {
                "ret": 0,
                "battle_id": 39304906,
                "next_left": 12,
                "atside": 1,
                "city": [1002, "倭国部队", 268, 251],
                "myside": [[1, 21936, "ThienCo", 280, 237, 738816, "quilia", "TP3", 0, 8919, 0, 0, 100, 99057]],
                "enemy": [],
            },
            "OPT.ashx?id=24": [
                {
                    "ret": 0,
                    "site": "倭国部队",
                    "mapid": 1002,
                    "bout": 1,
                    "bout_left": 12,
                    "attack_total": 1,
                    "defend_total": 1,
                    "troops": [
                        [1, "quilia", 738816, "TP3", 99057, "", 21936, 0, 1, 100, 0, 0, 8919, 8919, 0, 0, 0, 98396, "QV42", 1],
                        [11, "", 0, "倭国部队", 0, "", 0, 0, 4, 100, 0, 5000, 0, 5000, 0, 0, 0, 0, "", 16],
                    ],
                },
                {"ret": 13, "troops": []},
            ],
            "Common.ashx?id=12": {
                "ret": 0,
                "battle_array": 1,
                "ratio_attack": 100,
                "ratio_PK": 0,
                "ratio_stratagem": 0,
                "withdraw_loss": 0,
                "withdraw_morale": 0,
            },
            "OPT.ashx?id=54": {"ret": 0},
            "OPT.ashx?id=57": {"ret": 0},
            "OPT.ashx?id=26": {"ret": 0, "last_tips_id": 0, "tips": []},
        }
    )
    server.cookies = {"uid": "738816"}
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[99057],
        origin=(280, 237),
        radius=20,
        man_types=[1],
        mode=2,
        city_id=21936,
        check_idle=True,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "battle_tracked"

    opt24_calls = [d for k, d in server.calls if k == "OPT.ashx?id=24"]
    opt57_calls = [d for k, d in server.calls if k == "OPT.ashx?id=57"]
    assert len(opt24_calls) >= 1
    assert opt24_calls[0]["battleid"] == "39304906"
    assert len(opt57_calls) == 1
    assert opt57_calls[0]["lGeneralID"] == "99057"
    assert opt57_calls[0]["lBattleArray"] == "2"  # Câu hình (2) khắc Hạc dực (4)


def test_binh_man_waits_for_march_and_tracks_battle_after_attack():
    """Sau khi xuất quân tấn công (OPT.ashx?id=53), BinhMan phải chờ đạo quân hành quân (goto)
    tới nơi rồi tự động vào chiến trường điều khiển và đổi trận hình khắc chế.
    """
    target_mid = mid_from_coords(281, 237)
    server = FakeServer(
        map_views={
            mid_from_coords(280, 237): {"npc_tent": [man(281, 237, 555, 1)]},
            target_mid: {"npc_tent": [man(281, 237, 555, 1)]},
        },
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [21936, "ThienCo", 280, 237, [[99057, "TP3", "", 2, 0, 0, 31, 100, 363, 410]]],
                ],
            },
            "OPT.ashx?id=53": {"ret": 0},
            "Common.ashx?id=40": [
                {
                    "ret": 0,
                    "come": [],
                    "goto": [
                        [7001, 1, 0, "", 555, "倭国部队", 281, 237, [[99057, "TP3"]], 0, 8919, 0, 0, 3, 1]
                    ],
                    "battle": [],
                },
                {
                    "ret": 0,
                    "come": [],
                    "goto": [],
                    "battle": [[1002, 555, "倭国部队", 281, 237, 10]],
                },
            ],
            "Common.ashx?id=4": {
                "ret": 0,
                "battle_id": 39304999,
                "next_left": 10,
                "atside": 1,
                "city": [555, "倭国部队", 281, 237],
                "myside": [[1, 21936, "ThienCo", 280, 237, 738816, "quilia", "TP3", 0, 8919, 0, 0, 100, 99057]],
                "enemy": [],
            },
            "OPT.ashx?id=24": [
                {
                    "ret": 0,
                    "site": "倭国部队",
                    "mapid": 555,
                    "bout": 1,
                    "bout_left": 10,
                    "attack_total": 1,
                    "defend_total": 1,
                    "troops": [
                        [1, "quilia", 738816, "TP3", 99057, "", 21936, 0, 1, 100, 0, 0, 8919, 8919, 0, 0, 0, 0, "", 1],
                        [11, "", 0, "倭国部队", 0, "", 0, 0, 4, 100, 0, 5000, 0, 5000, 0, 0, 0, 0, "", 16],
                    ],
                },
                {"ret": 13, "troops": []},
            ],
            "OPT.ashx?id=54": {"ret": 0},
            "OPT.ashx?id=57": {"ret": 0},
            "OPT.ashx?id=26": {"ret": 0, "last_tips_id": 0, "tips": []},
        },
    )
    server.cookies = {"uid": "738816"}
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[99057],
        origin=(280, 237),
        radius=5,
        man_types=[1],
        mode=2,
        city_id=21936,
        check_idle=True,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "attacked"

    opt57_calls = [d for k, d in server.calls if k == "OPT.ashx?id=57"]
    assert len(opt57_calls) == 1
    assert opt57_calls[0]["lGeneralID"] == "99057"
    assert opt57_calls[0]["lBattleArray"] == "2"


def test_binh_man_mode_city_provisioning_and_morale_waiting():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    c32 = {
        "ret": 0,
        "list": [
            [1001, "Thành", 0, 0, [[10, "Triệu Vân", "", 2, 0, 0, 4, 85, 240, 240, 0]]]
        ],
    }
    c76 = {
        "ret": 0,
        "list": [
            [1001, "Thành", [[10, "Triệu Vân", 0, "", 0, 100, 0, 0, 0, 85, 0, 100]]]
        ],
    }
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(10, 11, 404, 7)]}},
        handlers={
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "Common.ashx?id=27": {"ret": 0, "list": [[1001, "Thành", 5000]]},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=47": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(infantry=1000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "waiting_morale"
    # Đã trị thương
    assert any(k == "OPT.ashx?id=31" for k, d in server.calls)
    # Đã bổ sung +900 lính bộ tại thành
    opt6_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(opt6_calls) == 1
    assert opt6_calls[0]["lAmount"] == "900"
    assert opt6_calls[0]["tid"] == "1001"
    # Đã kích hoạt nâng sĩ khí
    opt47_calls = [d for k, d in server.calls if k == "OPT.ashx?id=47"]
    assert len(opt47_calls) == 1
    assert opt47_calls[0]["lAddPoint"] == "10"
    # Chưa xuất quân khi chưa đủ sĩ khí
    assert not any(k == "OPT.ashx?id=53" for k, d in server.calls)


def test_binh_man_mode_camp_provisioning_from_garrison_only():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(20, 20)
    c32 = {
        "ret": 0,
        "list": [
            [-501, "Trại", 0, 0, [[20, "Quan Vũ", "", 2, 0, 0, 4, 100, 240, 240, 0]]]
        ],
    }
    c76 = {
        "ret": 0,
        "list": [
            [-501, "Trại", [[20, "Quan Vũ", 0, "", 0, 500, 0, 0, 0, 100, 0, 500]]]
        ],
    }
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(20, 21, 505, 8)]}},
        handlers={
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[20],
        origin=(20, 20),
        radius=5,
        man_types=[8],
        mode=1,
        camp_id=-501,
        parent_city_id=1001,
        target_army=TargetArmy(infantry=1000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "attacked"
    # Gọi OPT.ashx?id=6 với tid=-501 (Trại)
    opt6_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(opt6_calls) == 1
    assert opt6_calls[0]["tid"] == "-501"
    assert opt6_calls[0]["lAmount"] == "500"
    # KHÔNG gọi chiêu mộ (id=41) tại Trại
    assert not any(k == "OPT.ashx?id=41" for k, d in server.calls)


def test_binh_man_nearest_base_priority_in_multi_base():
    from linhvuong.scan import BasePeer
    shared_locks = TargetLocks()
    # Man 100 tại (7, 0) - Man cấp 7
    # Man 200 tại (2, 0) - Man cấp 7
    mid0 = mid_from_coords(0, 0)
    server = FakeServer(
        map_views={
            mid0: {"npc_tent": [man(7, 0, 100, 7), man(2, 0, 200, 7)]},
            mid_from_coords(8, 0): {"npc_tent": [man(7, 0, 100, 7)]},
        },
        handlers={
            "OPT.ashx?id=53": {"ret": 0},
            "Common.ashx?id=32": {"generals": [{"id": 1, "status": 0}, {"id": 2, "status": 0}]},
        },
    )
    ctx_a, alerts_a = ctx_for(server, locks=shared_locks)
    ctx_b, alerts_b = ctx_for(server, locks=shared_locks)

    peer_b = BasePeer(base_id=200, ox=8, oy=0, radius=5, target_types=[7])
    peer_a = BasePeer(base_id=100, ox=0, oy=0, radius=10, target_types=[7])

    task_a = BinhMan(
        ctx_a,
        generals=[1],
        origin=(0, 0),
        radius=10,
        man_types=[7],
        mode=2,
        city_id=100,
        peers=[peer_b],
    )

    task_b = BinhMan(
        ctx_b,
        generals=[2],
        origin=(8, 0),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=200,
        peers=[peer_a],
    )

    # Base A quét trước: Man 100 ở gần Base B hơn nên Base A bỏ qua và đánh Man 200
    res_a = task_a.run_once()
    assert res_a == "attacked"
    calls_a = [d for k, d in server.calls if k == "OPT.ashx?id=53" and d["target_id"] == "200"]
    assert len(calls_a) == 1

    # Base B quét: Base B gần Man 100 nhất nên đánh Man 100
    res_b = task_b.run_once()
    assert res_b == "attacked"
    calls_b = [d for k, d in server.calls if k == "OPT.ashx?id=53" and d["target_id"] == "100"]
    assert len(calls_b) == 1


def test_binh_man_pre_flight_lock_check_aborts_when_claimed_by_other():
    shared_locks = TargetLocks()
    # Khóa mục tiêu 77 bởi Base khác (999)
    from linhvuong.locks import LockReason
    shared_locks.try_lock(77, LockReason.CLAIMED, owner=999)

    server = FakeServer(
        map_views={
            mid_from_coords(0, 0): {"npc_tent": [man(1, 0, 77, 7)]},
        },
        handlers={
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, alerts = ctx_for(server, locks=shared_locks)
    task = BinhMan(
        ctx,
        generals=[1],
        origin=(0, 0),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=100,
    )
    # Vì mục tiêu 77 đã bị khóa bởi owner=999, scanner sẽ không tìm thấy hoặc nếu bị tranh chấp, pre-flight chặn
    res = task.run_once()
    assert res == "no_target"
    # Không có cuộc tấn công nào được gửi
    assert not any(k == "OPT.ashx?id=53" for k, _ in server.calls)


def test_binh_man_non_blocking_relocate():
    server = FakeServer(
        map_views={
            mid_from_coords(0, 0): {"npc_tent": [man(6, 6, 88, 7)]},
        },
        handlers={
            "Common.ashx?id=55": {"ret": 0, "frozen": 20},
        },
    )
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[1],
        origin=(0, 0),
        radius=10,
        man_types=[7],
        mode=1,
        camp_id=5555,
        max_step=2,
        non_blocking_relocate=True,
    )

    # Lượt 1: Dời 1 bước không chặn luồng, trả về camp_relocating
    res1 = task.run_once()
    assert res1 == "camp_relocating"
    assert task.origin == (2, 2)
    assert task._camp_frozen_until > 0

    # Lượt 2: Chưa hết frozen_time -> trả về camp_frozen ngay lập tức
    res2 = task.run_once()
    assert res2 == "camp_frozen"





