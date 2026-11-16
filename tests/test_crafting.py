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
    """Kiểm tra tìm vị trí ô đất (pid) và gid của công xưởng từ /api/building/list."""
    fake_gw = MagicMock()
    fake_gw.building_list.return_value = {
        "ret": 0,
        "items": [
            {"m_lpos": 1, "m_lgid": 1, "m_szname": "Quan Phủ", "m_llevel": 20},
            {"m_lpos": 28, "m_lgid": 13, "m_szname": "Xưởng Binh Khí", "m_llevel": 25},
            {"m_lpos": 29, "m_lgid": 67, "m_szname": "Phòng Cụ Ty", "m_llevel": 24},
            {"m_lpos": 19, "m_lgid": 15, "m_szname": "Xưởng Ngựa", "m_llevel": 18},
        ],
    }

    crafter = WeaponCrafter(fake_gw)

    assert crafter.find_workshop(1001, 101) == (28, 13)
    assert crafter.find_workshop_plot(1001, 101) == 28

    assert crafter.find_workshop(1001, 301) == (29, 67)
    assert crafter.find_workshop_plot(1001, 301) == 29

    assert crafter.find_workshop(1001, 401) == (19, 15)
    assert crafter.find_workshop_plot(1001, 401) == 19

    fake_gw.building_list.return_value = {
        "ret": 0,
        "items": [{"pid": 12, "gid": 13, "level": 15}],
    }
    assert crafter.find_workshop(1001, 101) == (12, 13)
    assert crafter.find_workshop_plot(1001, 101) == 12

    fake_gw.building_list.return_value = {
        "ret": 0,
        "items": [{"m_lpos": 1, "m_lgid": 1, "m_szname": "Quan Phủ", "m_llevel": 20}],
    }
    assert crafter.find_workshop(1001, 101) == (None, None)
    assert crafter.find_workshop_plot(1001, 101) is None


def test_craft_once_success():
    """Kiểm tra quy trình chế tạo quân giới thành công qua Build.ashx?id=2 và OPT.ashx?id=38."""
    calls = []

    def mock_call(path, aid, payload, **kwargs):
        calls.append((path, aid, payload))
        return {"ret": 0}

    fake_gw = MagicMock()
    fake_gw.building_list.return_value = {
        "ret": 0,
        "items": [{"m_lpos": 28, "m_lgid": 13, "m_szname": "Xưởng Binh Khí", "m_llevel": 25}],
    }
    fake_gw.set_current_city.return_value = {"ret": 0}
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
    fake_gw.set_current_city.assert_called_once_with(15230)

    build2_calls = [c for c in calls if c[0] == "Build.ashx" and c[1] == 2]
    assert len(build2_calls) == 1
    b = build2_calls[0][2]
    assert b["gid"] == "13"
    assert b["pid"] == "28"
    assert b["tab"] == "0"
    assert b["tid"] == "15230"

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
    fake_gw.building_list.return_value = {
        "ret": 0,
        "items": [{"m_lpos": 28, "m_lgid": 13, "m_szname": "Xưởng Binh Khí", "m_llevel": 10}],
    }

    def mock_call(path, aid, payload, **kwargs):
        if path == "OPT.ashx" and aid == 38:
            return {"ret": 32}
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
    fake_gw.building_list.return_value = {
        "ret": 0,
        "items": [{"m_lpos": 1, "m_lgid": 1, "m_szname": "Quan Phủ", "m_llevel": 20}],
    }
    crafter = WeaponCrafter(fake_gw)

    success, ret, msg = crafter.craft_once(city_id=15230, weapon_id=301, amount=1000)
    assert success is False
    assert ret == -2
    assert "chưa xây dựng công xưởng" in msg


def test_craft_once_captcha():
    """Kiểm tra ngoại lệ CaptchaRequired khi máy chủ yêu cầu xác thực."""
    fake_gw = MagicMock()
    fake_gw.building_list.return_value = {"ret": 110}
    crafter = WeaponCrafter(fake_gw)

    with pytest.raises(CaptchaRequired):
        crafter.craft_once(city_id=15230, weapon_id=101, amount=100)
