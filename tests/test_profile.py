import json
import pytest
from pathlib import Path

from linhvuong.profile import (
    BuildingProfile,
    CityBuildingConfig,
    CombatProfile,
    Profile,
    ProfileStore,
    ResearchProfile,
    ThaoPhatProfile,
)


def test_profile_default_values():
    prof = Profile()
    assert prof.version == 1
    assert prof.building.slots == 3
    assert prof.building.auto_boost is True
    assert prof.research.interval == "30"
    assert prof.thao_phat.min_morale == "95"
    assert prof.thao_phat.auto_recruit is True
    assert prof.combat.auto_counter_formation is True
    assert prof.combat.formation_window_seconds == "15"


def test_profile_to_dict_and_from_dict_roundtrip():
    prof = Profile()
    prof.building.slots = 5
    prof.building.cities["101"] = CityBuildingConfig(
        name="Thành Chủ",
        enabled=True,
        resource=False,
        plans=[{"pid": 1, "gid": 1, "target_level": 20, "name": "Quan Phủ"}],
    )
    prof.research.techs = [{"id": 1, "target_level": 20, "name": "Khai Khoáng"}]
    prof.thao_phat.target_infantry = "8000"
    prof.thao_phat.target_cavalry = "2000"

    d = prof.to_dict()
    assert d["version"] == 1
    assert d["building"]["slots"] == 5
    assert "101" in d["building"]["cities"]
    assert d["building"]["cities"]["101"]["name"] == "Thành Chủ"

    loaded = Profile.from_dict(d)
    assert loaded.building.slots == 5
    assert "101" in loaded.building.cities
    assert loaded.building.cities["101"].name == "Thành Chủ"
    assert len(loaded.building.cities["101"].plans) == 1
    assert loaded.thao_phat.target_infantry == "8000"
    assert loaded.thao_phat.target_cavalry == "2000"


def test_profile_legacy_format_compatibility():
    legacy_data = {
        "plans": [{"pid": 2, "gid": 2, "target_level": 10}],
        "techs": [{"id": 5, "target_level": 15}],
        "cities": {
            "202": {"name": "Doanh Trại", "enabled": True, "plans": []}
        },
    }
    prof = Profile.from_dict(legacy_data)
    assert len(prof.building.plans) == 1
    assert prof.building.plans[0]["gid"] == 2
    assert len(prof.research.techs) == 1
    assert prof.research.techs[0]["id"] == 5
    assert "202" in prof.building.cities
    assert prof.building.cities["202"].name == "Doanh Trại"


def test_profile_store_default_profile_name():
    assert ProfileStore.default_profile_name() == "auto_profile.json"
    assert ProfileStore.default_profile_name("player1", 10) == "auto_profile_player1_10.json"


def test_profile_store_save_and_load(tmp_path: Path):
    target = tmp_path / "test_profile.json"
    prof = Profile()
    prof.building.slots = 4
    prof.thao_phat.mission_idx = 3

    saved_path = ProfileStore.save(prof, target)
    assert saved_path == target
    assert target.exists()

    # Check tmp files are cleaned up
    tmp_files = list(tmp_path.glob("*.tmp*"))
    assert len(tmp_files) == 0

    loaded = ProfileStore.load(target)
    assert loaded.building.slots == 4
    assert loaded.thao_phat.mission_idx == 3


def test_profile_store_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        ProfileStore.load(Path("non_existent_profile_file_12345.json"))


def test_profile_binh_man_and_goi_man_fields():
    data = {
        "binh_man": {
            "mode": 2,
            "radius": "12",
            "threshold": "40",
            "mantypes": "5,6,7",
        },
        "goi_man": {
            "target_type": 8,  # Đột Quyết
            "radius": "7",
            "interval": "15",
        },
    }
    prof = Profile.from_dict(data)
    assert prof.binh_man.mode == 2
    assert prof.binh_man.radius == "12"
    assert prof.binh_man.threshold == "40"
    assert prof.binh_man.mantypes == "5,6,7"

    assert prof.goi_dan.target_type == 8
    assert prof.goi_dan.radius == "7"
    assert prof.goi_dan.interval == "15"

    d = prof.to_dict()
    assert d["binh_man"]["mode"] == 2
    assert d["goi_dan"]["target_type"] == 8


def test_profile_target_types_multiselect_roundtrip():
    data = {
        "binh_man": {
            "mode": 1,
            "mantypes": "7,8,9,10,301",
            "target_types": [7, 8, 9, 10, 301],
        },
        "goi_man": {
            "target_types": [7, 8, 301],
            "radius": "6",
        },
    }
    prof = Profile.from_dict(data)
    assert prof.binh_man.target_types == [7, 8, 9, 10, 301]
    assert prof.binh_man.mantypes == "7,8,9,10,301"

    assert prof.goi_dan.target_types == [7, 8, 301]
    assert prof.goi_dan.target_type == 7  # first type

    d = prof.to_dict()
    assert d["binh_man"]["target_types"] == [7, 8, 9, 10, 301]
    assert d["goi_dan"]["target_types"] == [7, 8, 301]
    assert d["goi_dan"]["target_type"] == 7


def test_profile_binh_man_and_goi_man_generals_roundtrip():
    data = {
        "binh_man": {
            "mode": 1,
            "generals": [417506, 417520, 99999],
        },
        "goi_dan": {
            "generals": [417506, "invalid", 417513],
        },
    }
    prof = Profile.from_dict(data)
    assert prof.binh_man.generals == [417506, 417520, 99999]
    assert prof.goi_dan.generals == [417506, 417513]

    d = prof.to_dict()
    assert d["binh_man"]["generals"] == [417506, 417520, 99999]
    assert d["goi_dan"]["generals"] == [417506, 417513]


