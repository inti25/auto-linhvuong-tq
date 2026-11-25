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


def test_binh_man_concurrent_morale_training_all_generals():
    """Kiểm tra Bình Man kích hoạt nâng sĩ khí ĐỒNG THỜI cho toàn bộ tướng trong đạo (ADR-0032):
    - Đạo quân gồm 3 tướng [10, 11, 12], cả 3 đều có morale < 95 và up_t = 0.
    - Trong 1 chu kỳ run_once(), cả 3 tướng ĐỀU được gửi lệnh OPT.ashx?id=47 song song (không bị return sớm ở tướng 1).
    - Trả về 'waiting_morale' và chưa xuất quân.
    """
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    c32 = {
        "ret": 0,
        "list": [
            [
                1001,
                "Thành",
                0,
                0,
                [
                    [10, "Tướng 1", "", 2, 0, 0, 4, 80, 240, 240],
                    [11, "Tướng 2", "", 2, 0, 0, 4, 85, 240, 240],
                    [12, "Tướng 3", "", 2, 0, 0, 4, 75, 240, 240],
                ],
            ]
        ],
    }
    c76 = {
        "ret": 0,
        "list": [
            [
                1001,
                "Thành",
                [
                    [10, "Tướng 1", 0, "", 0, 100, 0, 0, 0, 80, 0, 500],
                    [11, "Tướng 2", 0, "", 0, 100, 0, 0, 0, 85, 0, 500],
                    [12, "Tướng 3", 0, "", 0, 100, 0, 0, 0, 75, 0, 500],
                ],
            ]
        ],
    }

    server = FakeServer(
        map_views={mid: {"npc_tent": [man(11, 10, 100, 7)]}},
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
        generals=[10, 11, 12],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(infantry=100),
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
    assert called_gids == {10, 11, 12}

    # Chưa được xuất quân (OPT 53) khi đang chờ sĩ khí
    assert not any(k == "OPT.ashx?id=53" for k, d in server.calls)


def test_binh_man_detects_and_logs_boss_man():
    """Kiểm tra Bình Man nhận diện Boss Man (VD: 卑弥呼 tại vị trí 19 với flag=32)
    và log cảnh báo chính xác ra nhật ký:
    VD: 🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!"""
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [21936, "ThienCo", 280, 237, [[99057, "TP3", "", 2, 0, 16]]],
                ],
            },
            "Common.ashx?id=40": {
                "ret": 0,
                "come": [],
                "goto": [],
                "battle": [[1002, 555, "倭国部队", 281, 237, 10]],
            },
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
                        [19, "", 0, "卑弥呼", 0, "", 0, 0, 4, 100, 0, 5000, 0, 5000, 0, 0, 0, 0, "", 32],
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
    notifies = []
    ctx.notify = lambda m: notifies.append(m)
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
    assert out == "battle_tracked"

    boss_alerts = [m for m in notifies if "🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!" in m]
    assert len(boss_alerts) == 1, f"Bình Man phải log cảnh báo boss đúng 1 lần: {notifies}"
    assert "🐉 PHÁT HIỆN BOSS [卑弥呼] tại vị trí 19!" in boss_alerts[0]


def test_binh_man_tracks_marching_countdown_and_enters_battle_when_arrived():
    """Khi võ tướng đang trên đường hành quân (status=16, goto có countdown),
    Binh Man theo dõi đếm lùi sắp tới nơi, grace period khi vừa tới và tự động vào chỉ huy trận đánh."""
    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [21936, "ThienCo", 280, 237, [[99056, "TC8", "", 2, 0, 16, 76, 100, 860, 860]]],
                ],
            },
            "Common.ashx?id=40": [
                # Poll 1: Đang hành quân, còn 4s (sắp tới nơi)
                {
                    "ret": 0,
                    "come": [],
                    "goto": [
                        [7001, 1, 0, "", 555, "鲜卑部队", 269, 211, [[99056, "TC8"]], 0, 16000, 0, 0, 4, 1]
                    ],
                    "battle": [],
                },
                # Poll 2: Vừa tới nơi (goto rỗng, grace period chờ chiến trường)
                {"ret": 0, "come": [], "goto": [], "battle": []},
                {"ret": 0, "come": [], "goto": [], "battle": []},
                # Poll 3: Chiến trường xuất hiện
                {
                    "ret": 0,
                    "come": [],
                    "goto": [],
                    "battle": [[1054, 555, "鲜卑部队", 269, 211, 10]],
                },
            ],
            "Common.ashx?id=4": [
                {"ret": 0, "battle_id": 0, "myside": []},
                {
                    "ret": 0,
                    "battle_id": 1054,
                    "next_left": 10,
                    "atside": 1,
                    "city": [555, "鲜卑部队", 269, 211],
                    "myside": [[1, 21936, "ThienCo", 280, 237, 738816, "quilia", "TC8", 0, 16000, 0, 0, 100, 99056]],
                    "enemy": [],
                },
            ],
            "OPT.ashx?id=24": [
                {
                    "ret": 0,
                    "site": "鲜卑部队",
                    "mapid": 555,
                    "bout": 1,
                    "bout_left": 10,
                    "attack_total": 1,
                    "defend_total": 1,
                    "troops": [
                        [1, "quilia", 738816, "TC8", 99056, "", 21936, 0, 5, 100, 0, 0, 16000, 0, 0, 0, 0, 0, "", 1],
                        [11, "", 0, "鲜卑千夫长", 0, "", 0, 0, 2, 100, 0, 2154, 1569, 0, 0, 0, 0, 0, "", 16],
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
    notifies = []
    ctx.notify = lambda m: notifies.append(m)
    task = BinhMan(
        ctx,
        generals=[99056],
        origin=(280, 237),
        radius=5,
        man_types=[2],
        mode=2,
        city_id=21936,
        check_idle=True,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "battle_tracked"
    assert any("⚡ Quân ta sắp tới nơi (còn ~4s), chuẩn bị tiếp chiến..." in m for m in notifies)
    assert any("⚔️ Quân ta đã tới vị trí mục tiêu, đang kết nối chiến trường..." in m for m in notifies)
    assert any("⚔️ Phát hiện chiến trường đang diễn ra (ID: 1054)" in m for m in notifies)









def test_binh_man_recover_in_city_does_not_recruit_when_army_already_sufficient():
    # Khi quân số đã đủ 20000 kỵ, recover_in_city không được nhét thêm 20000 kỵ hay gọi chiêu mộ id=41
    server = FakeServer(
        handlers={
            "Common.ashx?id=29": {"ret": 0, "city": [[1001, "ThienCo", 0, 0, 0, 0, 0, 0, 0, 0, 0]]},
            "Common.ashx?id=32": {"ret": 0, "list": [[1001, "ThienCo", 10, 10, [[15, "TC1_01", "", 2, 0, 0, 10, 100, 20, 100, 10, 10, 10, 10, 0]]]]},
            "Common.ashx?id=76": {"ret": 0, "list": [[1001, "ThienCo", [[15, "TC1_01", 0, "", 0, 0, 20000, 0, 0, 100, 0]]]]},
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
        target_army=__import__("linhvuong.troops", fromlist=["TargetArmy"]).TargetArmy(cavalry=20000),
        auto_recruit=True,
    )
    out = task.run_once()
    assert out == "waiting_stamina"

    # Tướng đã có đủ 20000 kỵ, tuyệt đối không được gọi id=6 với amount=20000 hoặc id=41 để chiêu mộ
    troop_add_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(troop_add_calls) == 0, f"Bị gọi lệnh phối quân lãng phí: {troop_add_calls}"
    recruit_calls = [d for k, d in server.calls if k == "OPT.ashx?id=41"]
    assert len(recruit_calls) == 0, f"Bị gọi lệnh chiêu mộ lãng phí: {recruit_calls}"


def test_binh_man_recover_in_city_refills_only_missing_troops():
    # Khi tướng đang có 15000 kỵ và target là 20000 kỵ, chỉ bổ sung đúng 5000 kỵ
    server = FakeServer(
        handlers={
            "Common.ashx?id=29": {"ret": 0, "city": [[1001, "ThienCo", 0, 0, 0, 0, 0, 0, 0, 0, 0]]},
            "Common.ashx?id=32": {"ret": 0, "list": [[1001, "ThienCo", 10, 10, [[15, "TC1_01", "", 2, 0, 0, 10, 100, 20, 100, 10, 10, 10, 10, 0]]]]},
            "Common.ashx?id=76": {"ret": 0, "list": [[1001, "ThienCo", [[15, "TC1_01", 0, "", 0, 0, 15000, 0, 0, 100, 0]]]]},
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
        target_army=__import__("linhvuong.troops", fromlist=["TargetArmy"]).TargetArmy(cavalry=20000),
        auto_recruit=True,
    )
    task.run_once()

    troop_add_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(troop_add_calls) == 1
    assert troop_add_calls[0]["lAmount"] == "5000"


def test_binh_man_auto_swap_tactician_before_attack_without_target_army():
    """Khi bật auto_swap_tactician (dù target_army=None), Bình Man đổi Mưu sĩ dưới ngưỡng theo cấp cao -> thấp rồi xuất kích."""
    origin_mid = mid_from_coords(10, 10)
    man_mid = mid_from_coords(11, 10)

    def _c32(body):
        t = body.get("type")
        if t == "1":
            return {
                "ret": 0,
                "list": [
                    [
                        1001,
                        "ThienCo",
                        10,
                        10,
                        [
                            # [0]id, [1]name, ..., [4]special, [5]status, [6]lv, [7]loy, [8]stam, [9]stam_max
                            [201, "MSCu", "", 1, 2, 0, 70, 100, 15, 100, 0, 0, 0, 0, 0],       # 15% < 30%
                            [202, "ThaiThu", "", 1, 1, 0, 99, 100, 100, 100, 0, 0, 0, 0, 0],   # Thái thú -> bỏ qua
                            [203, "VanThap", "", 1, 0, 0, 40, 100, 90, 100, 0, 0, 0, 0, 0],    # 90% >= 30%, lv 40
                            [204, "VanCao", "", 1, 0, 0, 85, 100, 50, 100, 0, 0, 0, 0, 0],     # 50% >= 30%, lv 85 -> ưu tiên chọn
                        ],
                    ]
                ],
            }
        return {
            "ret": 0,
            "list": [[1001, "ThienCo", 10, 10, [[15, "TrieuVan", "", 2, 0, 0, 80, 100, 90, 100, 0, 0, 0, 0, 0]]]],
        }

    # Note: FakeServer handler callable takes no args, so inspect server.calls[-1]
    server = FakeServer(
        map_views={origin_mid: {"npc_tent": [man(11, 10, 777, 7)]}, man_mid: {"npc_tent": [man(11, 10, 777, 7)]}},
        handlers={
            "Common.ashx?id=32": lambda: _c32(server.calls[-1][1]),
            "Common.ashx?id=76": {"ret": 0, "list": [[1001, "ThienCo", [[15, "TrieuVan", 201, "MSCu", 0, 0, 5000, 0, 0, 100, 0]]]]},
            "OPT.ashx?id=5": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[15],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        check_idle=False,
        auto_swap_tactician=True,
        min_tactician_stamina=30,
    )
    out = task.run_once()
    assert out == "attacked"

    tac_calls = [d for k, d in server.calls if k == "OPT.ashx?id=5"]
    assert [(d["lType"], d["lGeneralID"], d["lFollowGeneralID"], d["lCityID"]) for d in tac_calls] == [
        ("0", "201", "0", "1001"),   # Tháo MSCu
        ("3", "204", "15", "1001"),  # Gán VanCao (lv 85) -> TrieuVan
    ]
    assert any("MSCu" in m and "VanCao" in m for m in alerts)


def test_binh_man_mode1_camp_swaps_only_within_camp_and_continues_when_no_replacement():
    """ADR-0044: Bình Man Chế độ 1 chỉ đổi trong phạm vi Doanh trại, không kéo từ Thành mẹ và vẫn xuất quân nếu hết ứng viên."""
    origin_mid = mid_from_coords(10, 10)

    def _c32(body):
        t = body.get("type")
        if t == "1":
            return {
                "ret": 0,
                "list": [
                    [-500, "TienDon", 10, 10, [[201, "MSYeu", "", 1, 2, 0, 60, 100, 10, 100, 0, 0, 0, 0, 0]]],
                    # Thành mẹ 1001 có Văn quan khỏe nhưng ở Chế độ 1 KHÔNG được rút từ Thành mẹ
                    [1001, "ThanhMe", 5, 5, [[299, "VanThanhMe", "", 1, 0, 0, 99, 100, 100, 100, 0, 0, 0, 0, 0]]],
                ],
            }
        return {
            "ret": 0,
            "list": [[-500, "TienDon", 10, 10, [[15, "QuanVu", "", 2, 0, 0, 70, 100, 90, 100, 0, 0, 0, 0, 0]]]],
        }

    server = FakeServer(
        map_views={origin_mid: {"npc_tent": [man(10, 11, 888, 7)]}},
        handlers={
            "Common.ashx?id=32": lambda: _c32(server.calls[-1][1]),
            "Common.ashx?id=76": {"ret": 0, "list": [[-500, "TienDon", [[15, "QuanVu", 201, "MSYeu", 0, 0, 5000, 0, 0, 100, 0]]]]},
            "OPT.ashx?id=5": {"ret": 0},
            "OPT.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[15],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        camp_id=-500,
        parent_city_id=1001,
        mode=1,
        check_idle=False,
        auto_swap_tactician=True,
        min_tactician_stamina=30,
    )
    out = task.run_once()
    assert out == "attacked"
    assert [d for k, d in server.calls if k == "OPT.ashx?id=5"] == []
    assert [d for k, d in server.calls if k == "OPT.ashx?id=50"] == []
    assert any("không có Văn quan đủ thể lực" in m for m in alerts)


def test_binh_man_mode_city_provisions_and_trains_morale_while_waiting_stamina():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    c32 = {
        "ret": 0,
        "list": [[1001, "Thành", 10, 10, [[15, "TC1_01", "", 2, 0, 0, 10, 80, 20, 100, 0]]]],
    }
    c76 = {
        "ret": 0,
        "list": [[1001, "Thành", [[15, "TC1_01", 0, "", 0, 0, 15000, 0, 0, 80, 0, 500]]]],
    }
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(10, 11, 404, 7)]}},
        handlers={
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "Common.ashx?id=27": {"ret": 0, "list": [[1001, "Thành", 10000]]},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=47": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, alerts = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[15],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        return_threshold=30,
        target_army=TargetArmy(cavalry=20000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    # Lượt 1: Thể lực 20/100 < 30% -> vẫn ưu tiên trị thương, bù +5000 kỵ và nâng sĩ khí trước
    out1 = task.run_once()
    assert out1 == "waiting_morale"
    assert any(k == "OPT.ashx?id=31" for k, _ in server.calls)
    opt6_1 = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(opt6_1) == 1
    assert opt6_1[0]["lAmount"] == "5000"
    opt47_1 = [d for k, d in server.calls if k == "OPT.ashx?id=47"]
    assert len(opt47_1) == 1
    assert opt47_1[0]["lGeneralID"] == "15"
    assert opt47_1[0]["lAddPoint"] == "10"
    assert not any(k == "OPT.ashx?id=53" for k, _ in server.calls)

    # Lượt 2: Quân đủ 20000, sĩ khí đạt 95, thể lực vẫn 25/100 < 30% -> chờ hồi thể lực
    server.calls.clear()
    alerts.clear()
    c32["list"][0][4][0][7] = 95
    c32["list"][0][4][0][8] = 25
    c76["list"][0][2][0][6] = 20000
    c76["list"][0][2][0][9] = 95
    c76["list"][0][2][0][10] = 0

    out2 = task.run_once()
    assert out2 == "waiting_stamina"
    assert any("Thể lực" in a for a in alerts)
    assert not any(k in ("OPT.ashx?id=6", "OPT.ashx?id=47", "OPT.ashx?id=53") for k, _ in server.calls)

    # Lượt 3: Thể lực hồi lên 35/100 >= 30% -> xuất kích
    server.calls.clear()
    c32["list"][0][4][0][8] = 35
    out3 = task.run_once()
    assert out3 == "attacked"
    assert len([d for k, d in server.calls if k == "OPT.ashx?id=53"]) == 1


def test_binh_man_mode_city_trains_morale_when_troop_refill_dilutes_morale_under_low_stamina():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    c32 = {
        "ret": 0,
        "list": [[1001, "Thành", 10, 10, [[15, "TC1_01", "", 2, 0, 0, 10, 100, 20, 100, 0]]]],
    }
    c76_responses = [
        {"ret": 0, "list": [[1001, "Thành", [[15, "TC1_01", 0, "", 0, 0, 15000, 0, 0, 100, 0, 500]]]]},
        {"ret": 0, "list": [[1001, "Thành", [[15, "TC1_01", 0, "", 0, 0, 20000, 0, 0, 85, 0, 500]]]]},
    ]
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(10, 11, 404, 7)]}},
        handlers={
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76_responses,
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=47": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
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
        target_army=TargetArmy(cavalry=20000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "waiting_morale"
    opt6_calls = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert len(opt6_calls) == 1
    assert opt6_calls[0]["lAmount"] == "5000"
    assert len([k for k, _ in server.calls if k == "Common.ashx?id=76"]) == 2
    opt47_calls = [d for k, d in server.calls if k == "OPT.ashx?id=47"]
    assert len(opt47_calls) == 1
    assert opt47_calls[0]["lAddPoint"] == "10"
    assert not any(k == "OPT.ashx?id=53" for k, _ in server.calls)


def test_binh_man_mode_city_zero_target_army_trains_morale_without_legacy_infantry_spam():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(10, 11, 404, 7)]}},
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [[1001, "Thành", 10, 10, [[15, "TC1_01", "", 2, 0, 0, 10, 80, 20, 100, 0]]]],
            },
            "Common.ashx?id=76": {
                "ret": 0,
                "list": [[1001, "Thành", [[15, "TC1_01", 0, "", 0, 0, 20000, 0, 0, 80, 0, 500]]]],
            },
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
        generals=[15],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        return_threshold=30,
        target_army=TargetArmy(0, 0, 0),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "waiting_morale"
    assert len([d for k, d in server.calls if k == "OPT.ashx?id=47"]) == 1
    assert not any(k in ("OPT.ashx?id=41", "OPT.ashx?id=6", "OPT.ashx?id=53") for k, _ in server.calls)


def test_binh_man_mode_camp_low_stamina_trains_morale_at_camp_without_ping_pong_retreat():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    c32 = {
        "ret": 0,
        "list": [[-501, "Trại", 10, 10, [[20, "Quan Vũ", "", 2, 0, 0, 10, 80, 20, 100, 0]]]],
    }
    c76 = {
        "ret": 0,
        "list": [[-501, "Trại", [[20, "Quan Vũ", 0, "", 0, 0, 20000, 0, 0, 80, 0, 500]]]],
    }
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(10, 11, 404, 7)]}},
        handlers={
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "OPT.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=47": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[20],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=1,
        camp_id=-501,
        parent_city_id=1001,
        return_threshold=30,
        target_army=TargetArmy(cavalry=20000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    out1 = task.run_once()
    assert out1 == "waiting_morale"
    assert not any(k == "OPT.ashx?id=50" for k, _ in server.calls)
    opt47_calls = [d for k, d in server.calls if k == "OPT.ashx?id=47"]
    assert len(opt47_calls) == 1
    assert opt47_calls[0]["tid"] == "-501"
    assert not any(k == "OPT.ashx?id=53" for k, _ in server.calls)

    # Lượt 2: Sĩ khí đã đủ 95, thể lực vẫn 20/100 -> chờ thể lực tại Trại, không rút về Thành mẹ
    server.calls.clear()
    c32["list"][0][4][0][7] = 95
    c76["list"][0][2][0][9] = 95
    out2 = task.run_once()
    assert out2 == "waiting_stamina"
    assert not any(k in ("OPT.ashx?id=50", "OPT.ashx?id=53") for k, _ in server.calls)


def test_binh_man_mode_camp_low_army_retreats_first_then_trains_morale_under_low_stamina():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    c32 = {
        "ret": 0,
        "list": [[-501, "Trại", 10, 10, [[20, "Quan Vũ", "", 2, 0, 0, 10, 80, 20, 100, 0]]]],
    }
    c76 = {
        "ret": 0,
        "list": [[-501, "Trại", [[20, "Quan Vũ", 0, "", 0, 0, 4000, 0, 0, 80, 0, 500]]]],
    }

    def _opt6():
        payload = server.calls[-1][1]
        if payload.get("tid") == "-501":
            return {"ret": 53}
        return {"ret": 0}

    server = FakeServer(
        map_views={mid: {"npc_tent": [man(10, 11, 404, 7)]}},
        handlers={
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "OPT.ashx?id=50": {"ret": 0},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": _opt6,
            "OPT.ashx?id=47": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[20],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=1,
        camp_id=-501,
        parent_city_id=1001,
        return_threshold=30,
        target_army=TargetArmy(cavalry=20000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        sleep_fn=lambda s: None,
    )

    # Lượt 1: Quân số 4000/20000 = 20% < 30% và trại hết quân đồn trú -> rút về thành mẹ bổ sung rồi quay lại trại
    out1 = task.run_once()
    assert out1 == "retreated_below_threshold"
    opt50_1 = [d for k, d in server.calls if k == "OPT.ashx?id=50"]
    assert [(d["lCityID"], d["lDestID"]) for d in opt50_1] == [("-501", "1001"), ("1001", "-501")]
    opt6_parent = [d for k, d in server.calls if k == "OPT.ashx?id=6" and d["tid"] == "1001"]
    assert len(opt6_parent) == 1
    assert opt6_parent[0]["lAmount"] == "16000"

    # Lượt 2: Đã đủ 20000 quân tại trại, sĩ khí 70, thể lực vẫn 21/100 < 30% -> luyện sĩ khí tại trại, không rút nữa
    server.calls.clear()
    c32["list"][0][4][0][8] = 21
    c76["list"][0][2][0][6] = 20000
    c76["list"][0][2][0][9] = 70
    out2 = task.run_once()
    assert out2 == "waiting_morale"
    assert not any(k == "OPT.ashx?id=50" for k, _ in server.calls)
    opt47_2 = [d for k, d in server.calls if k == "OPT.ashx?id=47"]
    assert len(opt47_2) == 1
    assert opt47_2[0]["tid"] == "-501"


def test_binh_man_active_battle_tracked_even_when_stamina_below_threshold():
    from linhvuong.troops import TargetArmy

    server = FakeServer(
        handlers={
            "Common.ashx?id=32": {
                "ret": 0,
                "list": [
                    [21936, "ThienCo", 280, 237, [[99057, "TP3", "", 2, 0, 16, 31, 100, 20, 100, 0]]],
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
            "OPT.ashx?id=54": {"ret": 0},
            "OPT.ashx?id=57": {"ret": 0},
            "OPT.ashx?id=26": {"ret": 0, "last_tips_id": 0, "tips": []},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=41": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
        }
    )
    server.cookies = {"uid": "738816"}
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[99057],
        origin=(280, 237),
        radius=20,
        man_types=[1],
        mode=2,
        city_id=21936,
        return_threshold=30,
        target_army=TargetArmy(cavalry=20000),
        check_idle=True,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "battle_tracked"
    assert not any(k in ("OPT.ashx?id=6", "OPT.ashx?id=31", "OPT.ashx?id=41") for k, _ in server.calls)


def test_binh_man_even_troops_balances_before_recruit_and_refreshes_morale():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    c32 = {
        "ret": 0,
        "list": [
            [
                1001,
                "Thành",
                10,
                10,
                [
                    [10, "Tướng A", "", 2, 0, 0, 4, 100, 240, 240, 0],
                    [11, "Tướng B", "", 2, 0, 0, 4, 100, 240, 240, 0],
                ],
            ]
        ],
    }
    # A có 1500 Kỵ, B có 500 Kỵ -> sau san đều mỗi tướng 1000 Kỵ, định mức 1200 -> mỗi tướng chỉ bù thêm 200 (không phải B bù 700!)
    c76 = {
        "ret": 0,
        "list": [
            [
                1001,
                "Thành",
                [
                    [10, "Tướng A", 0, "", 0, 0, 1500, 0, 0, 100, 0, 0],
                    [11, "Tướng B", 0, "", 0, 0, 500, 0, 0, 100, 0, 0],
                ],
            ]
        ],
    }
    server = FakeServer(
        map_views={mid: {"npc_tent": [man(10, 11, 405, 7)]}},
        handlers={
            "Common.ashx?id=32": c32,
            "Common.ashx?id=76": c76,
            "Common.ashx?id=27": {"ret": 0, "list": [[1001, "Thành", 5000]]},
            "OPT.ashx?id=31": {"ret": 0},
            "OPT.ashx?id=39": {"ret": 0},
            "OPT.ashx?id=6": {"ret": 0},
            "OPT.ashx?id=53": {"ret": 0},
        },
    )
    ctx, _ = ctx_for(server)
    task = BinhMan(
        ctx,
        generals=[10, 11],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(cavalry=1200),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        even_troops=True,
        sleep_fn=lambda s: None,
    )

    out = task.run_once()
    assert out == "attacked"
    eps = [k for k, _ in server.calls]
    opt39_idx = eps.index("OPT.ashx?id=39")
    opt6_indices = [i for i, k in enumerate(eps) if k == "OPT.ashx?id=6"]
    assert len(opt6_indices) == 2
    assert opt39_idx < opt6_indices[0]

    opt39 = [d for k, d in server.calls if k == "OPT.ashx?id=39"]
    assert len(opt39) == 1
    assert opt39[0]["lFromGeneralID"] == "10"
    assert opt39[0]["lToGeneralID"] == "11"
    assert opt39[0]["cavalry"] == "500"

    opt6 = [d for k, d in server.calls if k == "OPT.ashx?id=6"]
    assert [(d["lGeneralID"], d["lAmount"]) for d in opt6] == [("10", "200"), ("11", "200")]
    assert sum(1 for k, _ in server.calls if k == "Common.ashx?id=76") >= 2

    # Khi target_army = 0/0/0 và auto_recruit=False vẫn chạy san đều quân nếu even_troops=True
    server.calls.clear()
    task_zero = BinhMan(
        ctx,
        generals=[10, 11],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(),
        auto_recruit=False,
        auto_morale=False,
        even_troops=True,
        sleep_fn=lambda s: None,
    )
    assert task_zero.run_once() == "attacked"
    assert sum(1 for k, _ in server.calls if k == "OPT.ashx?id=39") == 1
    assert not any(k == "OPT.ashx?id=6" for k, _ in server.calls)

    # Khi even_troops=False -> không bao giờ gọi OPT.ashx?id=39
    server.calls.clear()
    task_off = BinhMan(
        ctx,
        generals=[10, 11],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(cavalry=1200),
        auto_recruit=True,
        auto_morale=False,
        even_troops=False,
        sleep_fn=lambda s: None,
    )
    assert task_off.run_once() == "attacked"
    assert not any(k == "OPT.ashx?id=39" for k, _ in server.calls)


def test_binh_man_city_partial_provision_trains_morale_and_waits_for_100pct_before_marching():
    from linhvuong.troops import ArmyProvisioner, TargetArmy

    mid = mid_from_coords(10, 10)
    state = {"recruits": 0, "idle_pop": 1000, "troops": 4000, "morale": 85, "comfort_ok": False}

    class StatefulServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            self.calls.append((key, dict(data or {})))
            if key == "Map.ashx?id=6":
                return Resp({"npc_tent": [man(10, 10, 999, 7)]})
            if key == "Common.ashx?id=32":
                return Resp({"ret": 0, "list": [[1001, "C", 0, 0, [[10, "G10", "", 2, 0, 0, 4, 100, 240, 240, 0]]]]})
            if key == "Common.ashx?id=76":
                return Resp({"ret": 0, "list": [[1001, "C", [[10, "G10", 0, "", 0, 0, state["troops"], 0, 0, state["morale"], 0, 0]]]]})
            if key == "Common.ashx?id=27":
                return Resp({"ret": 0, "list": [[1001, "C", state["recruits"]]]})
            if key == "City.ashx?id=6":
                return Resp({"ret": 0, "population": [10000, 10000, 2000, 0, state["idle_pop"]]})
            if key == "OPT.ashx?id=4":
                if not state["comfort_ok"]:
                    return Resp({"ret": 55})
                state["idle_pop"] += 1500
                return Resp({"ret": 0})
            if key == "OPT.ashx?id=41":
                amt = int(data["lAmount"])
                if amt <= state["idle_pop"]:
                    state["idle_pop"] -= amt
                    state["recruits"] += amt
                    if key == "OPT.ashx?id=6" and str((data or {}).get("tid")) == "-2001":
                        return Resp({"ret": 53})
                    return Resp({"ret": 0})
                return Resp({"ret": 34})
            if key == "OPT.ashx?id=6":
                amt = int(data["lAmount"])
                if amt <= state["recruits"]:
                    state["recruits"] -= amt
                    state["troops"] += amt
                    return Resp({"ret": 0})
                return Resp({"ret": 53})
            if key == "OPT.ashx?id=47":
                state["morale"] = min(100, state["morale"] + int(data["lAddPoint"]))
                return Resp({"ret": 0})
            if key == "OPT.ashx?id=53":
                return Resp({"ret": 0})
            return Resp({"ret": 0})

    clock = [0.0]
    srv = StatefulServer()
    ctx, alerts = ctx_for(srv)
    prov = ArmyProvisioner(ctx.gateway, sleep_fn=lambda s: None, clock_fn=lambda: clock[0])
    task = BinhMan(
        ctx,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(cavalry=6000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        return_threshold=30,  # Dù 5000/6000 = 83% > 30% vẫn phải chờ đủ 100%
        sleep_fn=lambda s: None,
        provisioner=prov,
    )

    # Chu kỳ 1: chỉ có 1000 dân nhàn rỗi -> lên 5000/6000, luyện sĩ khí (85->95) xong trả waiting_troops, KHÔNG xuất quân
    out1 = task.run_once()
    assert out1 in ("waiting_morale", "waiting_troops")
    assert state["troops"] == 5000
    assert any(k == "OPT.ashx?id=47" for k, _ in srv.calls)
    assert not any(k == "OPT.ashx?id=53" for k, _ in srv.calls)

    # Giả sử MoraleTrainer vừa nâng từ 85 -> 95 (waiting_morale), lượt kế tiếp đã 95 nhưng vẫn thiếu 1000 quân -> vẫn giữ waiting_troops
    if out1 == "waiting_morale":
        out1b = task.run_once()
        assert out1b == "waiting_troops"
        assert not any(k == "OPT.ashx?id=53" for k, _ in srv.calls)

    # Chu kỳ 2: hết cooldown Tăng Nhân Khẩu -> bổ sung đủ 6000 -> đủ sĩ khí -> xuất quân
    clock[0] = 100.0
    state["comfort_ok"] = True
    state["morale"] = 96
    out2 = task.run_once()
    assert out2 == "attacked"
    assert state["troops"] == 6000
    assert any(k == "OPT.ashx?id=53" for k, _ in srv.calls)


def test_binh_man_recover_in_city_partial_provision_still_trains_morale_below_threshold():
    from linhvuong.troops import ArmyProvisioner, TargetArmy

    state = {"recruits": 0, "idle_pop": 1000, "troops": 0, "morale": 85}

    class BelowThreshServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            self.calls.append((key, dict(data or {})))
            if key == "Common.ashx?id=32":
                return Resp({"ret": 0, "list": [[1001, "C", 0, 0, [[10, "G10", "", 2, 0, 0, 4, 100, 240, 240, 0]]]]})
            if key == "Common.ashx?id=76":
                return Resp({"ret": 0, "list": [[1001, "C", [[10, "G10", 0, "", 0, 0, state["troops"], 0, 0, state["morale"], 0, 0]]]]})
            if key == "Common.ashx?id=27":
                return Resp({"ret": 0, "list": [[1001, "C", state["recruits"]]]})
            if key == "City.ashx?id=6":
                return Resp({"ret": 0, "population": [10000, 10000, 2000, 0, state["idle_pop"]]})
            if key == "OPT.ashx?id=4":
                return Resp({"ret": 55})
            if key == "OPT.ashx?id=41":
                amt = int(data["lAmount"])
                if amt <= state["idle_pop"]:
                    state["idle_pop"] -= amt
                    state["recruits"] += amt
                    return Resp({"ret": 0})
                return Resp({"ret": 34})
            if key == "OPT.ashx?id=6":
                amt = int(data["lAmount"])
                if amt <= state["recruits"]:
                    state["recruits"] -= amt
                    state["troops"] += amt
                    return Resp({"ret": 0})
                return Resp({"ret": 53})
            if key == "OPT.ashx?id=47":
                state["morale"] = min(100, state["morale"] + int(data["lAddPoint"]))
                return Resp({"ret": 0})
            return Resp({"ret": 0})

    srv = BelowThreshServer()
    ctx, _ = ctx_for(srv)
    prov = ArmyProvisioner(ctx.gateway, sleep_fn=lambda s: None)
    task = BinhMan(
        ctx,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(cavalry=6000),
        auto_recruit=True,
        auto_morale=True,
        min_morale=95,
        return_threshold=30,
        sleep_fn=lambda s: None,
        provisioner=prov,
    )

    out = task.run_once(remaining_percent=10.0)
    assert out == "recovered_in_city"
    assert state["troops"] == 1000
    assert any(k == "OPT.ashx?id=47" for k, _ in srv.calls)
    assert not any(k == "OPT.ashx?id=53" for k, _ in srv.calls)


def test_binh_man_recover_in_city_trains_morale_when_auto_recruit_false():
    from linhvuong.troops import ArmyProvisioner, TargetArmy

    calls_morale = []

    class RecruitOffServer:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, headers=None, timeout=None):
            key = url.split("/GateWay/")[1]
            self.calls.append((key, dict(data or {})))
            if key == "Common.ashx?id=32":
                return Resp({"ret": 0, "list": [[1001, "C", 0, 0, [[10, "G10", "", 2, 0, 0, 4, 100, 240, 240, 0]]]]})
            if key == "Common.ashx?id=76":
                return Resp({"ret": 0, "list": [[1001, "C", [[10, "G10", 0, "", 0, 0, 2000, 0, 0, 80, 0, 0]]]]})
            if key == "OPT.ashx?id=47":
                calls_morale.append(dict(data or {}))
                return Resp({"ret": 0})
            return Resp({"ret": 0})

    srv = RecruitOffServer()
    ctx, _ = ctx_for(srv)
    task = BinhMan(
        ctx,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(cavalry=2000),
        auto_recruit=False,
        even_troops=False,
        auto_morale=True,
        min_morale=95,
        return_threshold=30,
        sleep_fn=lambda s: None,
        provisioner=ArmyProvisioner(ctx.gateway, sleep_fn=lambda s: None),
    )

    out = task.run_once(remaining_percent=10.0)
    assert out == "recovered_in_city"
    assert len(calls_morale) == 1
    assert calls_morale[0]["lGeneralID"] == "10"


def test_binh_man_independent_stamina_and_army_thresholds():
    from linhvuong.troops import TargetArmy

    mid = mid_from_coords(10, 10)
    state = {"stamina": 40, "troops": 2000}

    def _make_server():
        class SplitServer:
            def __init__(self):
                self.calls = []

            def post(self, url, data=None, headers=None, timeout=None):
                key = url.split("/GateWay/")[1]
                self.calls.append((key, dict(data or {})))
                if key == "Map.ashx?id=6":
                    return Resp({"npc_tent": [man(10, 10, 999, 7)]})
                if key == "Common.ashx?id=32":
                    return Resp(
                        {
                            "ret": 0,
                            "list": [
                                [1001, "C", 0, 0, [[10, "G10", "", 2, 0, 0, 4, 100, state["stamina"], 100, 0]]],
                                [-2001, "T", 0, 0, [[10, "G10", "", 2, 0, 0, 4, 100, state["stamina"], 100, 0]]],
                            ],
                        }
                    )
                if key == "Common.ashx?id=76":
                    return Resp(
                        {
                            "ret": 0,
                            "list": [
                                [1001, "C", [[10, "G10", 0, "", 0, 0, state["troops"], 0, 0, 100, 0, 0]]],
                                [-2001, "T", [[10, "G10", 0, "", 0, 0, state["troops"], 0, 0, 100, 0, 0]]],
                            ],
                        }
                    )
                if key == "OPT.ashx?id=6" and str((data or {}).get("tid")) == "-2001":
                    return Resp({"ret": 53})
                return Resp({"ret": 0})

        return SplitServer()

    # Case 1: stamina_threshold=50, army_threshold=10 (thể lực 40% < 50%, quân 20% > 10%)
    # -> phải chờ thể lực ("waiting_stamina") và KHÔNG rút Doanh trại về Thành mẹ
    srv1 = _make_server()
    ctx1, _ = ctx_for(srv1)
    t1 = BinhMan(
        ctx1,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=1,
        camp_id=-2001,
        parent_city_id=1001,
        target_army=TargetArmy(cavalry=10000),
        auto_recruit=True,
        auto_morale=False,
        stamina_threshold=50,
        army_threshold=10,
        sleep_fn=lambda s: None,
    )
    assert t1.run_once() == "waiting_stamina"
    assert not any(k == "OPT.ashx?id=50" for k, _ in srv1.calls)

    # Case 2: stamina_threshold=0, army_threshold=50 trong Doanh trại (Mode 1)
    # 2a. Thể lực 10%, quân 40% (< 50%) -> rút Doanh trại về Thành mẹ
    state["stamina"] = 10
    state["troops"] = 4000
    srv2 = _make_server()
    ctx2, _ = ctx_for(srv2)
    t2 = BinhMan(
        ctx2,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=1,
        camp_id=-2001,
        parent_city_id=1001,
        target_army=TargetArmy(cavalry=10000),
        auto_recruit=True,
        auto_morale=False,
        stamina_threshold=0,
        army_threshold=50,
        sleep_fn=lambda s: None,
    )
    assert t2.run_once() == "retreated_below_threshold"
    assert any(k == "OPT.ashx?id=50" for k, _ in srv2.calls)

    # 2b. Thể lực vẫn 10%, quân 80% (>= 50%) -> xuất kích bình thường vì stamina_threshold=0
    state["troops"] = 8000
    srv2.calls.clear()
    assert t2.run_once() == "attacked"

    # Case 3: Mode 2 Thành với auto_recruit=False, stamina_threshold=0, army_threshold=50
    state["stamina"] = 10
    state["troops"] = 4000
    srv3 = _make_server()
    ctx3, _ = ctx_for(srv3)
    t3 = BinhMan(
        ctx3,
        generals=[10],
        origin=(10, 10),
        radius=5,
        man_types=[7],
        mode=2,
        city_id=1001,
        target_army=TargetArmy(cavalry=10000),
        auto_recruit=False,
        auto_morale=False,
        stamina_threshold=0,
        army_threshold=50,
        sleep_fn=lambda s: None,
    )
    assert t3.run_once() == "waiting_troops"
    state["troops"] = 6000
    assert t3.run_once() == "attacked"


def test_binh_man_skips_provisioning_when_c76_fails_preventing_over_provision():
    from linhvuong.troops import TargetArmy

    for bad_c76 in ({"ret": 198599}, {"ret": 1}):
        server = FakeServer(
            handlers={
                "Common.ashx?id=32": {
                    "ret": 0,
                    "list": [[22040, "ThienCo5", 10, 10, [[104488, "TC5_10", "", 2, 0, 0, 10, 100, 1750, 1750, 0]]]],
                },
                "Common.ashx?id=76": bad_c76,
            }
        )
        ctx, logs = ctx_for(server)
        task = BinhMan(
            ctx,
            generals=[104488],
            origin=(10, 10),
            radius=5,
            man_types=[7],
            mode=2,
            city_id=22040,
            target_army=TargetArmy(cavalry=37000),
            auto_recruit=True,
            auto_morale=True,
            even_troops=True,
            sleep_fn=lambda s: None,
        )
        out = task.run_once()
        assert out == "waiting_troops"
        assert not any(k in ("OPT.ashx?id=6", "OPT.ashx?id=39", "OPT.ashx?id=41") for k, _ in server.calls)
        assert any("Common.ashx?id=76" in msg for msg in logs)


