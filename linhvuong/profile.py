"""Kho Lưu Trữ Hồ Sơ Cấu Hình (ProfileStore & Profile).

Module hướng miền độc lập chịu trách nhiệm:
- Lưu trữ toàn bộ quy hoạch và thiết lập tự động hóa trong một Hồ Sơ Cấu Hình duy nhất.
- Hỗ trợ Hồ Sơ Tài Khoản Riêng Biệt (auto_profile_{username}_{server_id}.json) theo ADR-0006 và ADR-0012.
- Ghi nguyên tử (atomic write-and-replace) bảo vệ toàn vẹn dữ liệu chống crash.
- Cung cấp mô hình dataclass thuần túy không phụ thuộc Tkinter cho cả GUI, CLI và test suites.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Union


@dataclass
class CityBuildingConfig:
    name: str = ""
    enabled: bool = True
    resource: bool = False
    plans: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "CityBuildingConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            name=str(data.get("name", "")),
            enabled=bool(data.get("enabled", True)),
            resource=bool(data.get("resource", False)),
            plans=list(data.get("plans", [])),
        )


@dataclass
class BuildingProfile:
    slots: int = 3
    auto_speedup: bool = False
    auto_boost: bool = True
    auto_comfort: bool = True
    even_upgrade: bool = False
    auto_open_box: bool = False
    box_type_idx: int = 0
    box_max: str = "5"
    auto_fallback_box: bool = True
    interval: str = "20"
    plans: list[dict] = field(default_factory=list)
    cities: dict[str, CityBuildingConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "BuildingProfile":
        if not isinstance(data, dict):
            return cls()
        cities_map = {}
        raw_cities = data.get("cities")
        if isinstance(raw_cities, dict):
            for cid_str, cinfo in raw_cities.items():
                cities_map[str(cid_str)] = CityBuildingConfig.from_dict(cinfo)

        return cls(
            slots=int(data.get("slots", 3)),
            auto_speedup=bool(data.get("auto_speedup", False)),
            auto_boost=bool(data.get("auto_boost", True)),
            auto_comfort=bool(data.get("auto_comfort", True)),
            even_upgrade=bool(data.get("even_upgrade", False)),
            auto_open_box=bool(data.get("auto_open_box", False)),
            box_type_idx=int(data.get("box_type_idx", 0)),
            box_max=str(data.get("box_max", "5")),
            auto_fallback_box=bool(data.get("auto_fallback_box", True)),
            interval=str(data.get("interval", "20")),
            plans=list(data.get("plans", [])),
            cities=cities_map,
        )


@dataclass
class ResearchProfile:
    art_speedup: bool = False
    even_research: bool = False
    interval: str = "30"
    city_id: Optional[int] = None
    techs: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchProfile":
        if not isinstance(data, dict):
            return cls()
        cid = data.get("city_id")
        return cls(
            art_speedup=bool(data.get("art_speedup", False)),
            even_research=bool(data.get("even_research", False)),
            interval=str(data.get("interval", "30")),
            city_id=int(cid) if cid is not None and str(cid).isdigit() else None,
            techs=list(data.get("techs") or data.get("plans") or []),
        )


@dataclass
class ResourceProfile:
    gold_threshold: str = "100000000"
    wood_pct: str = "70"
    iron_pct: str = "70"
    stone_pct: str = "70"
    food_pct: str = "70"
    gold_box_idx: int = 1
    tn_box_idx: int = 3
    auto_open_box: bool = False
    resource_cities: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceProfile":
        if not isinstance(data, dict):
            return cls()
        res_cities = []
        raw_rc = data.get("resource_cities", [])
        if isinstance(raw_rc, list):
            for x in raw_rc:
                try:
                    res_cities.append(int(x))
                except (ValueError, TypeError):
                    pass

        return cls(
            gold_threshold=str(data.get("gold_threshold", "100000000")),
            wood_pct=str(data.get("wood_pct", "70")),
            iron_pct=str(data.get("iron_pct", "70")),
            stone_pct=str(data.get("stone_pct", "70")),
            food_pct=str(data.get("food_pct", "70")),
            gold_box_idx=int(data.get("gold_box_idx", 1)),
            tn_box_idx=int(data.get("tn_box_idx", 3)),
            auto_open_box=bool(data.get("auto_open_box", False)),
            resource_cities=sorted(res_cities),
        )


@dataclass
class ThaoPhatProfile:
    min_army: str = "5000"
    target_infantry: str = "5000"
    target_cavalry: str = "0"
    target_archers: str = "0"
    mission_idx: int = 0
    auto_recruit: bool = True
    auto_morale: bool = True
    min_morale: str = "95"
    interval: str = "10"

    @classmethod
    def from_dict(cls, data: dict) -> "ThaoPhatProfile":
        if not isinstance(data, dict):
            return cls()
        min_army = str(data.get("min_army", data.get("target_infantry", "5000")))
        return cls(
            min_army=min_army,
            target_infantry=str(data.get("target_infantry", min_army)),
            target_cavalry=str(data.get("target_cavalry", "0")),
            target_archers=str(data.get("target_archers", "0")),
            mission_idx=int(data.get("mission_idx", 0)),
            auto_recruit=bool(data.get("auto_recruit", True)),
            auto_morale=bool(data.get("auto_morale", True)),
            min_morale=str(data.get("min_morale", "95")),
            interval=str(data.get("interval", "10")),
        )


@dataclass
class GoiDanProfile:
    mode_idx: int = 0
    radius: str = "5"
    auto_recover: bool = True
    interval: str = "10"
    target_type: int = 301  # 301: Vong Linh, 1..10: Uy Quốc..Hổ Báo Kỵ
    target_types: list[int] = field(default_factory=lambda: [301])
    generals: list[int] = field(default_factory=list)
    target_infantry: str = "0"
    target_cavalry: str = "0"
    target_archers: str = "0"
    auto_recruit: bool = True
    auto_morale: bool = True
    min_morale: str = "95"

    @classmethod
    def from_dict(cls, data: dict) -> "GoiDanProfile":
        if not isinstance(data, dict):
            return cls()
        raw_types = data.get("target_types")
        if isinstance(raw_types, list) and raw_types:
            t_types = [int(x) for x in raw_types]
        elif isinstance(raw_types, str) and raw_types.strip():
            t_types = [int(x.strip()) for x in raw_types.split(",") if x.strip()]
        elif "target_type" in data:
            t_types = [int(data["target_type"])]
        else:
            t_types = [301]

        raw_gens = data.get("generals", [])
        gens = [int(x) for x in raw_gens if str(x).isdigit()] if isinstance(raw_gens, list) else []

        first_type = t_types[0] if t_types else 301
        auto_rec = data.get("auto_recruit")
        if auto_rec is None:
            auto_rec = data.get("auto_recover", True)

        return cls(
            mode_idx=int(data.get("mode_idx", 0)),
            radius=str(data.get("radius", "5")),
            auto_recover=bool(data.get("auto_recover", auto_rec)),
            interval=str(data.get("interval", "10")),
            target_type=int(data.get("target_type", first_type)),
            target_types=t_types,
            generals=gens,
            target_infantry=str(data.get("target_infantry", "0")),
            target_cavalry=str(data.get("target_cavalry", "0")),
            target_archers=str(data.get("target_archers", "0")),
            auto_recruit=bool(auto_rec),
            auto_morale=bool(data.get("auto_morale", True)),
            min_morale=str(data.get("min_morale", "95")),
        )


GoiManProfile = GoiDanProfile


@dataclass
class BaseBinhManConfig:
    name: str = ""
    enabled: bool = False
    mode: int = 1  # 1: Di Doanh trại đến cạnh Man, 2: Xuất quân thẳng từ Thành
    radius: str = "5"
    min_army: str = "3000"
    min_hp: str = "50"
    auto_comfort: bool = True
    interval: str = "15"
    camp_id: str = ""
    parent_city_id: str = ""
    threshold: str = "30"
    mantypes: str = "7,8,9,10"
    target_types: list[int] = field(default_factory=lambda: [7, 8, 9, 10])
    generals: list[int] = field(default_factory=list)
    target_infantry: str = "0"
    target_cavalry: str = "0"
    target_archers: str = "0"
    auto_recruit: bool = True
    auto_morale: bool = True
    min_morale: str = "95"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BaseBinhManConfig":
        if not isinstance(data, dict):
            return cls()
        raw_types = data.get("target_types")
        if isinstance(raw_types, list) and raw_types:
            t_types = [int(x) for x in raw_types]
            mantypes = ",".join(str(x) for x in t_types)
        elif "mantypes" in data:
            mantypes = str(data["mantypes"])
            t_types = [int(x.strip()) for x in mantypes.split(",") if x.strip()]
        else:
            mantypes = "7,8,9,10"
            t_types = [7, 8, 9, 10]

        raw_gens = data.get("generals", [])
        gens = [int(x) for x in raw_gens if str(x).isdigit()] if isinstance(raw_gens, list) else []

        return cls(
            name=str(data.get("name", "")),
            enabled=bool(data.get("enabled", False)),
            mode=int(data.get("mode", 1)),
            radius=str(data.get("radius", "5")),
            min_army=str(data.get("min_army", "3000")),
            min_hp=str(data.get("min_hp", "50")),
            auto_comfort=bool(data.get("auto_comfort", True)),
            interval=str(data.get("interval", "15")),
            camp_id=str(data.get("camp_id", "")),
            parent_city_id=str(data.get("parent_city_id", "")),
            threshold=str(data.get("threshold", "30")),
            mantypes=mantypes,
            target_types=t_types,
            generals=gens,
            target_infantry=str(data.get("target_infantry", "0")),
            target_cavalry=str(data.get("target_cavalry", "0")),
            target_archers=str(data.get("target_archers", "0")),
            auto_recruit=bool(data.get("auto_recruit", True)),
            auto_morale=bool(data.get("auto_morale", True)),
            min_morale=str(data.get("min_morale", "95")),
        )


@dataclass
class BinhManProfile:
    mode: int = 1  # 1: Di Doanh trại đến cạnh Man, 2: Xuất quân thẳng từ Thành
    radius: str = "5"
    min_army: str = "3000"
    min_hp: str = "50"
    auto_comfort: bool = True
    interval: str = "15"
    camp_id: str = ""
    parent_city_id: str = ""
    threshold: str = "30"
    mantypes: str = "7,8,9,10"
    target_types: list[int] = field(default_factory=lambda: [7, 8, 9, 10])
    generals: list[int] = field(default_factory=list)
    target_infantry: str = "0"
    target_cavalry: str = "0"
    target_archers: str = "0"
    auto_recruit: bool = True
    auto_morale: bool = True
    min_morale: str = "95"
    bases: dict[str, BaseBinhManConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "BinhManProfile":
        if not isinstance(data, dict):
            return cls()
        raw_types = data.get("target_types")
        if isinstance(raw_types, list) and raw_types:
            t_types = [int(x) for x in raw_types]
            mantypes = ",".join(str(x) for x in t_types)
        elif "mantypes" in data:
            mantypes = str(data["mantypes"])
            t_types = [int(x.strip()) for x in mantypes.split(",") if x.strip()]
        else:
            mantypes = "7,8,9,10"
            t_types = [7, 8, 9, 10]

        raw_gens = data.get("generals", [])
        gens = [int(x) for x in raw_gens if str(x).isdigit()] if isinstance(raw_gens, list) else []

        bases_map = {}
        raw_bases = data.get("bases")
        if isinstance(raw_bases, dict):
            for bid_str, binfo in raw_bases.items():
                bases_map[str(bid_str)] = BaseBinhManConfig.from_dict(binfo)

        return cls(
            mode=int(data.get("mode", 1)),
            radius=str(data.get("radius", "5")),
            min_army=str(data.get("min_army", "3000")),
            min_hp=str(data.get("min_hp", "50")),
            auto_comfort=bool(data.get("auto_comfort", True)),
            interval=str(data.get("interval", "15")),
            camp_id=str(data.get("camp_id", "")),
            parent_city_id=str(data.get("parent_city_id", "")),
            threshold=str(data.get("threshold", "30")),
            mantypes=mantypes,
            target_types=t_types,
            generals=gens,
            target_infantry=str(data.get("target_infantry", "0")),
            target_cavalry=str(data.get("target_cavalry", "0")),
            target_archers=str(data.get("target_archers", "0")),
            auto_recruit=bool(data.get("auto_recruit", True)),
            auto_morale=bool(data.get("auto_morale", True)),
            min_morale=str(data.get("min_morale", "95")),
            bases=bases_map,
        )



@dataclass
class LogisticsProfile:
    army_type_idx: int = 0
    amount: str = "1000"
    auto_daily_reward: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "LogisticsProfile":
        if not isinstance(data, dict):
            return cls()
        return cls(
            army_type_idx=int(data.get("army_type_idx", 0)),
            amount=str(data.get("amount", "1000")),
            auto_daily_reward=bool(data.get("auto_daily_reward", True)),
        )


@dataclass
class DiTraiProfile:
    dest_x: str = ""
    dest_y: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "DiTraiProfile":
        if not isinstance(data, dict):
            return cls()
        return cls(
            dest_x=str(data.get("dest_x", "")),
            dest_y=str(data.get("dest_y", "")),
        )


@dataclass
class CombatProfile:
    auto_counter_formation: bool = True
    formation_window_seconds: str = "15"
    attack_action_mode: str = "adaptive"
    action_combo_idx: int = 0
    skip_confused_enemy: bool = True
    leave_boss_last: bool = True
    auto_cleanse_confusion: bool = True
    emergency_retreat_threshold: str = "0"
    stratagem_combo_idx: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "CombatProfile":
        if not isinstance(data, dict):
            return cls()
        return cls(
            auto_counter_formation=bool(data.get("auto_counter_formation", True)),
            formation_window_seconds=str(data.get("formation_window_seconds", "15")),
            attack_action_mode=str(data.get("attack_action_mode", "adaptive")),
            action_combo_idx=int(data.get("action_combo_idx", 0)),
            skip_confused_enemy=bool(data.get("skip_confused_enemy", True)),
            leave_boss_last=bool(data.get("leave_boss_last", True)),
            auto_cleanse_confusion=bool(data.get("auto_cleanse_confusion", True)),
            emergency_retreat_threshold=str(data.get("emergency_retreat_threshold", "0")),
            stratagem_combo_idx=int(data.get("stratagem_combo_idx", 0)),
        )


@dataclass
class CityCraftConfig:
    city_id: int = 0
    weapon_id: int = 101  # Tương thích ngược: quân giới đầu tiên
    weapon_ids: list[int] = field(default_factory=lambda: [101])  # Danh sách quân giới được chọn chế tạo
    amount: str = "1000"
    interval: str = "5"  # Chu kỳ lặp lại (phút)
    enabled: bool = False

    def __post_init__(self):
        # Đồng bộ giữa weapon_id và weapon_ids
        if not self.weapon_ids and self.weapon_id:
            self.weapon_ids = [self.weapon_id]
        elif self.weapon_ids:
            if self.weapon_id != 101 and self.weapon_id not in self.weapon_ids and self.weapon_ids == [101]:
                self.weapon_ids = [self.weapon_id]
            else:
                self.weapon_id = self.weapon_ids[0]
        elif not self.weapon_ids:
            self.weapon_ids = [101]
            self.weapon_id = 101

    @classmethod
    def from_dict(cls, data: dict) -> "CityCraftConfig":
        if not isinstance(data, dict):
            return cls()
        raw_wids = data.get("weapon_ids")
        if raw_wids and isinstance(raw_wids, list):
            wids = [int(x) for x in raw_wids if str(x).isdigit()]
            wid = wids[0] if wids else int(data.get("weapon_id", 101))
            if not wids:
                wids = [wid]
        else:
            wid = int(data.get("weapon_id", 101))
            wids = [wid]
        return cls(
            city_id=int(data.get("city_id", 0)),
            weapon_id=wid,
            weapon_ids=wids,
            amount=str(data.get("amount", "1000")),
            interval=str(data.get("interval", "5")),
            enabled=bool(data.get("enabled", False)),
        )


@dataclass
class CraftProfile:
    cities: dict[str, CityCraftConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "CraftProfile":
        if not isinstance(data, dict):
            return cls()
        cities_map = {}
        raw_cities = data.get("cities")
        if isinstance(raw_cities, dict):
            for cid_str, cinfo in raw_cities.items():
                cities_map[str(cid_str)] = CityCraftConfig.from_dict(cinfo)
        return cls(cities=cities_map)


@dataclass
class Profile:
    version: int = 1
    building: BuildingProfile = field(default_factory=BuildingProfile)
    research: ResearchProfile = field(default_factory=ResearchProfile)
    resource: ResourceProfile = field(default_factory=ResourceProfile)
    thao_phat: ThaoPhatProfile = field(default_factory=ThaoPhatProfile)
    goi_dan: GoiDanProfile = field(default_factory=GoiDanProfile)
    binh_man: BinhManProfile = field(default_factory=BinhManProfile)
    logistics: LogisticsProfile = field(default_factory=LogisticsProfile)
    ditrai: DiTraiProfile = field(default_factory=DiTraiProfile)
    combat: CombatProfile = field(default_factory=CombatProfile)
    crafting: CraftProfile = field(default_factory=CraftProfile)

    def to_dict(self) -> dict:
        data = asdict(self)
        # Chuyển cities thành dict thuần
        if "building" in data and "cities" in data["building"]:
            data["building"]["cities"] = {
                k: asdict(v) if not isinstance(v, dict) else v
                for k, v in self.building.cities.items()
            }
        # Chuyển bases của binh_man thành dict thuần
        if "binh_man" in data and "bases" in data["binh_man"]:
            data["binh_man"]["bases"] = {
                k: asdict(v) if not isinstance(v, dict) else v
                for k, v in self.binh_man.bases.items()
            }
        # Chuyển cities của crafting thành dict thuần
        if "crafting" in data and "cities" in data["crafting"]:
            data["crafting"]["cities"] = {
                k: asdict(v) if not isinstance(v, dict) else v
                for k, v in self.crafting.cities.items()
            }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        if not isinstance(data, dict):
            return cls()

        # Hỗ trợ cấu hình legacy
        bld_raw = data.get("building") or {}
        if "plans" in data and "plans" not in bld_raw:
            bld_raw["plans"] = data["plans"]
        if "cities" in data and "cities" not in bld_raw:
            bld_raw["cities"] = data["cities"]

        res_raw = data.get("research") or {}
        if "techs" in data and "techs" not in res_raw:
            res_raw["techs"] = data["techs"]

        craft_raw = data.get("crafting") or data.get("weapon_crafting") or {}

        return cls(
            version=int(data.get("version", 1)),
            building=BuildingProfile.from_dict(bld_raw),
            research=ResearchProfile.from_dict(res_raw),
            resource=ResourceProfile.from_dict(data.get("resource", {})),
            thao_phat=ThaoPhatProfile.from_dict(data.get("thao_phat", {})),
            goi_dan=GoiDanProfile.from_dict(data.get("goi_man") or data.get("goi_dan", {})),
            binh_man=BinhManProfile.from_dict(data.get("binh_man", {})),
            logistics=LogisticsProfile.from_dict(data.get("logistics", {})),
            ditrai=DiTraiProfile.from_dict(data.get("ditrai", {})),
            combat=CombatProfile.from_dict(data.get("combat", {})),
            crafting=CraftProfile.from_dict(craft_raw),
        )


class ProfileStore:
    """Kho Lưu Trữ Hồ Sơ Cấu Hình (Domain Repository)."""

    DEFAULT_FILENAME = "auto_profile.json"

    @classmethod
    def default_profile_name(cls, username: str = "", server_id: int = 0) -> str:
        """Tạo tên file cấu hình riêng biệt theo tài khoản và server (ADR-0012)."""
        if username and server_id:
            return f"auto_profile_{username}_{server_id}.json"
        return cls.DEFAULT_FILENAME

    @classmethod
    def resolve_profile_path(
        cls,
        target_path: Optional[Union[str, Path]] = None,
        username: str = "",
        server_id: int = 0,
    ) -> Path:
        """Giải quyết đường dẫn file hồ sơ cấu hình phù hợp nhất."""
        if target_path:
            return Path(target_path)

        acc_name = cls.default_profile_name(username, server_id)
        if acc_name != cls.DEFAULT_FILENAME and Path(acc_name).exists():
            return Path(acc_name)

        if Path(cls.DEFAULT_FILENAME).exists():
            return Path(cls.DEFAULT_FILENAME)

        return Path(acc_name)

    @classmethod
    def load(cls, filepath: Union[str, Path]) -> Profile:
        """Nạp hồ sơ cấu hình từ tập tin JSON."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy tập tin hồ sơ: {path.name}")

        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        return Profile.from_dict(data)

    @classmethod
    def save(cls, profile: Profile, filepath: Union[str, Path]) -> Path:
        """Lưu hồ sơ cấu hình nguyên tử (atomic write-and-replace)."""
        target = Path(filepath)
        data = profile.to_dict()
        json_content = json.dumps(data, ensure_ascii=False, indent=2)

        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(f"{target.suffix}.tmp.{os.getpid()}")
        try:
            tmp_target.write_text(json_content, encoding="utf-8")
            # Atomic replace
            os.replace(tmp_target, target)
        except Exception:
            if tmp_target.exists():
                try:
                    tmp_target.unlink()
                except Exception:
                    pass
            raise

        return target
