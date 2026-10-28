"""Unit tests cho Nhiệm vụ Chế Tạo Quân Giới Đa Thành (ADR-0031)."""

import pytest
from unittest.mock import MagicMock

from linhvuong.gateway import GatewayClient
from linhvuong.tasks.base import CaptchaRequired
from linhvuong.tasks.crafting import (
    WEAPONS_DATA,
    WeaponCrafter,
    get_required_workshop_gids,
    get_weapon_name,
)


def test_weapons_data_dictionary_and_categories():
    """Kiểm tra danh mục quân giới 67 loại và các nhóm chức năng."""
    assert len(WEAPONS_DATA) == 67

    # Binh khí
    assert get_weapon_name(101) == "Thấu giáp thương"
    assert WEAPONS_DATA[101][1] == "Binh khí"

    # Cung nỗ
    assert get_weapon_name(201) == "Thiết thai cung"
    assert WEAPONS_DATA[201][1] == "Cung nỗ"

    # Khôi giáp
    assert get_weapon_name(301) == "Ngư lân giáp"
    assert WEAPONS_DATA[301][1] == "Khôi giáp"

    # Chiến mã
    assert get_weapon_name(401) == "Tuyệt địa mã"
    assert WEAPONS_DATA[401][1] == "Chiến mã"

    # Xe ném đá
    assert get_weapon_name(501) == "Xe ném đá loại nhẹ"
    assert WEAPONS_DATA[501][1] == "Xe ném đá"


def test_get_required_workshop_gids():
    """Kiểm tra ánh xạ chủng loại quân giới về mã công xưởng sơ cấp & cao cấp."""
    # Binh khí & Cung nỗ -> Xưởng Binh Khí (13 / 66)
    assert get_required_workshop_gids(101) == (13, 66)
    assert get_required_workshop_gids(108) == (13, 66)
    assert get_required_workshop_gids(201) == (13, 66)

    # Khôi giáp -> Xưởng Khôi Giáp (14 / 67)
    assert get_required_workshop_gids(301) == (14, 67)
    assert get_required_workshop_gids(308) == (14, 67)

    # Chiến mã & Xe -> Xưởng Ngựa (15 / 68)
    assert get_required_workshop_gids(401) == (15, 68)
    assert get_required_workshop_gids(501) == (15, 68)


def test_find_workshop_plot_and_find_workshop():
    """Kiểm tra tìm vị trí ô đất (pid) và gid của công xưởng từ City.ashx?id=5 (cả dạng infos list và dict)."""
    fake_gw = MagicMock()
    # Dạng infos thực tế từ server Linh Vương: [pid, gid, name, level, status, finish_time]
    fake_gw.call.return_value = {
        "ret": 0,
        "size": 4,
        "infos": [
            [1, 1, "Quan Phủ", 20, 0, 0],
            [28, 13, "Xưởng Binh Khí", 25, 0, 0],
            [29, 67, "Phòng Cụ Ty", 24, 0, 0],
            [19, 15, "Xưởng Ngựa", 18, 0, 0],
        ],
    }

    crafter = WeaponCrafter(fake_gw)

    # Tìm xưởng binh khí (Thấu giáp thương) -> ô 28, gid 13
    assert crafter.find_workshop(1001, 101) == (28, 13)
    assert crafter.find_workshop_plot(1001, 101) == 28

    # Tìm xưởng khôi giáp (Ngư lân giáp, gid=67) -> ô 29, gid 67
    assert crafter.find_workshop(1001, 301) == (29, 67)
    assert crafter.find_workshop_plot(1001, 301) == 29

    # Tìm xưởng ngựa (Tuyệt địa mã) -> ô 19, gid 15
    assert crafter.find_workshop(1001, 401) == (19, 15)
    assert crafter.find_workshop_plot(1001, 401) == 19

    # Kiểm tra tương thích ngược với định dạng dict trong key "list"
    fake_gw.call.return_value = {
        "ret": 0,
        "list": [
            {"pid": 12, "gid": 13, "level": 15},
        ],
    }
    assert crafter.find_workshop(1001, 101) == (12, 13)
    assert crafter.find_workshop_plot(1001, 101) == 12

    # Thành không có xưởng phù hợp
    fake_gw.call.return_value = {
        "ret": 0,
        "infos": [[1, 1, "Quan Phủ", 20, 0, 0]],
    }
    assert crafter.find_workshop(1001, 101) == (None, None)
    assert crafter.find_workshop_plot(1001, 101) is None


def test_craft_once_success():
    """Kiểm tra quy trình chế tạo quân giới thành công qua build.ashx?id=2 và OPT.ashx?id=38."""
    calls = []

    def mock_call(path, aid, payload, **kwargs):
        calls.append((path, aid, payload))
        if path == "City.ashx" and aid == 5:
            return {
                "ret": 0,
                "infos": [
                    [28, 13, "Xưởng Binh Khí", 25, 0, 0],
                ],
            }
        elif path == "City.ashx" and aid == 50:
            return {"ret": 0}
        elif path == "build.ashx" and aid == 2:
            return {"ret": 0}
        elif path == "OPT.ashx" and aid == 38:
            return {"ret": 0}
        return {"ret": 0}

    fake_gw = MagicMock()
    fake_gw.call.side_effect = mock_call

    crafter = WeaponCrafter(fake_gw)
    log_messages = []
    success, ret, msg = crafter.craft_once(
        city_id=15230,
        weapon_id=101,
        amount=500,
        notify=lambda m: log_messages.append(m),
    )

    assert success is True
    assert ret == 0
    assert "Đã đặt lệnh chế tạo thành công: 500x 'Thấu giáp thương' (Xưởng ô 28)" in msg
    assert len(log_messages) == 1

    # Kiểm tra gọi build.ashx?id=2 kích hoạt context xưởng
    build2_calls = [c for c in calls if c[0] == "build.ashx" and c[1] == 2]
    assert len(build2_calls) == 1
    b = build2_calls[0][2]
    assert b["gid"] == "13"
    assert b["pid"] == "28"
    assert b["tab"] == "0"
    assert b["tid"] == "15230"

    # Kiểm tra gọi OPT.ashx?id=38
    opt38_calls = [c for c in calls if c[0] == "OPT.ashx" and c[1] == 38]
    assert len(opt38_calls) == 1
    p = opt38_calls[0][2]
    assert p["count"] == "500"
    assert p["gid"] == "101"
    assert p["pos"] == "28"
    assert p["tid"] == "15230"
    assert p["lFaster"] == "1"
    assert p["num"] == "-1"


def test_craft_once_insufficient_resources():
    """Kiểm tra xử lý an toàn khi thiếu tài nguyên chế tạo (ret=32)."""
    fake_gw = MagicMock()

    def mock_call(path, aid, payload, **kwargs):
        if path == "City.ashx" and aid == 5:
            return {"ret": 0, "infos": [[28, 13, "Xưởng Binh Khí", 10, 0, 0]]}
        if path == "OPT.ashx" and aid == 38:
            return {"ret": 32}  # Mã lỗi thiếu tài nguyên
        return {"ret": 0}

    fake_gw.call.side_effect = mock_call
    crafter = WeaponCrafter(fake_gw)

    success, ret, msg = crafter.craft_once(city_id=15230, weapon_id=101, amount=1000)
    assert success is False
    assert ret == 32
    assert "Không đủ tài nguyên" in msg


def test_craft_once_missing_workshop():
    """Kiểm tra cảnh báo khi thành chưa có xưởng phù hợp."""
    fake_gw = MagicMock()
    fake_gw.call.return_value = {"ret": 0, "infos": [[1, 1, "Quan Phủ", 20, 0, 0]]}
    crafter = WeaponCrafter(fake_gw)

    success, ret, msg = crafter.craft_once(city_id=15230, weapon_id=301, amount=1000)
    assert success is False
    assert ret == -2
    assert "chưa xây dựng công xưởng" in msg


def test_craft_once_captcha():
    """Kiểm tra ngoại lệ CaptchaRequired khi máy chủ yêu cầu xác thực."""
    fake_gw = MagicMock()
    fake_gw.call.return_value = {"ret": 110}
    crafter = WeaponCrafter(fake_gw)

    with pytest.raises(CaptchaRequired):
        crafter.craft_once(city_id=15230, weapon_id=101, amount=100)
