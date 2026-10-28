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


def test_profile_binh_man_and_goi_man_army_provisioning_fields():
    # Kiểm tra giá trị mặc định chuẩn: 0 / 0 / 0
    prof = Profile()
    assert prof.binh_man.target_infantry == "0"
    assert prof.binh_man.target_cavalry == "0"
    assert prof.binh_man.target_archers == "0"
    assert prof.binh_man.auto_recruit is True
    assert prof.binh_man.auto_morale is True
    assert prof.binh_man.min_morale == "95"

    assert prof.goi_dan.target_infantry == "0"
    assert prof.goi_dan.target_cavalry == "0"
    assert prof.goi_dan.target_archers == "0"
    assert prof.goi_dan.auto_recruit is True
    assert prof.goi_dan.auto_morale is True
    assert prof.goi_dan.min_morale == "95"

    # Kiểm tra roundtrip to_dict và from_dict
    data = {
        "binh_man": {
            "target_infantry": "3000",
            "target_cavalry": "1000",
            "target_archers": "500",
            "auto_recruit": False,
            "auto_morale": True,
            "min_morale": "90",
        },
        "goi_dan": {
            "target_infantry": "1500",
            "target_cavalry": "2500",
            "target_archers": "0",
            "auto_recruit": True,
            "auto_morale": False,
            "min_morale": "85",
        },
    }
    loaded = Profile.from_dict(data)
    assert loaded.binh_man.target_infantry == "3000"
    assert loaded.binh_man.target_cavalry == "1000"
    assert loaded.binh_man.target_archers == "500"
    assert loaded.binh_man.auto_recruit is False
    assert loaded.binh_man.auto_morale is True
    assert loaded.binh_man.min_morale == "90"

    assert loaded.goi_dan.target_infantry == "1500"
    assert loaded.goi_dan.target_cavalry == "2500"
    assert loaded.goi_dan.target_archers == "0"
    assert loaded.goi_dan.auto_recruit is True
    assert loaded.goi_dan.auto_morale is False
    assert loaded.goi_dan.min_morale == "85"

    d = loaded.to_dict()
    assert d["binh_man"]["target_infantry"] == "3000"
    assert d["goi_dan"]["target_cavalry"] == "2500"


def test_binh_man_multi_base_profile():
    from linhvuong.profile import BaseBinhManConfig
    prof = Profile()
    prof.binh_man.bases["101"] = BaseBinhManConfig(
        name="Thành Chủ",
        enabled=True,
        mode=2,
        radius="8",
        target_types=[1, 2, 3],
        generals=[10, 11, 12],
        target_infantry="5000",
    )
    prof.binh_man.bases["-999"] = BaseBinhManConfig(
        name="Doanh Trại Tiền Tuyến",
        enabled=False,
        mode=1,
        radius="15",
        camp_id="999",
        parent_city_id="101",
        target_types=[7, 8, 9, 10],
        generals=[20, 21],
        target_cavalry="8000",
    )

    d = prof.to_dict()
    assert "101" in d["binh_man"]["bases"]
    assert "-999" in d["binh_man"]["bases"]
    assert d["binh_man"]["bases"]["101"]["name"] == "Thành Chủ"
    assert d["binh_man"]["bases"]["101"]["enabled"] is True
    assert d["binh_man"]["bases"]["101"]["mode"] == 2
    assert d["binh_man"]["bases"]["-999"]["mode"] == 1
    assert d["binh_man"]["bases"]["-999"]["target_cavalry"] == "8000"

    loaded = Profile.from_dict(d)
    assert len(loaded.binh_man.bases) == 2
    b101 = loaded.binh_man.bases["101"]
    assert b101.name == "Thành Chủ"
    assert b101.enabled is True
    assert b101.generals == [10, 11, 12]
    assert b101.target_infantry == "5000"

    b999 = loaded.binh_man.bases["-999"]
    assert b999.name == "Doanh Trại Tiền Tuyến"
    assert b999.enabled is False
    assert b999.camp_id == "999"
    assert b999.parent_city_id == "101"
    assert b999.target_cavalry == "8000"




