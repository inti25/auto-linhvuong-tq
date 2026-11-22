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
    speedup_item: str = "Ngân Bảo"
    speedup_hours: str = "1"
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

    @property
    def speedup_paytype(self) -> int:
        item_lower = self.speedup_item.lower()
        if "coin" in item_lower or "xu" in item_lower:
            return 1
        return 2  # Ngân Bảo (点券) hoặc Lệnh Bài

    @classmethod
    def from_dict(cls, data: dict) -> "BuildingProfile":
        if not isinstance(data, dict):
            return cls()
        cities_map = {}
        raw_cities = data.get("cities")
        if isinstance(raw_cities, dict):
            for cid_str, cinfo in raw_cities.items():
                cities_map[str(cid_str)] = CityBuildingConfig.from_dict(cinfo)

        item = data.get("speedup_item")
        if not item and "speedup_paytype" in data:
            try:
                item = "Coin" if int(data["speedup_paytype"]) == 1 else "Ngân Bảo"
            except (ValueError, TypeError):
                item = "Ngân Bảo"
        elif not item:
            item = "Ngân Bảo"

        return cls(
            slots=int(data.get("slots", 3)),
            auto_speedup=bool(data.get("auto_speedup", False)),
            speedup_item=str(item),
            speedup_hours=str(data.get("speedup_hours", "1")),
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
    gold_box_idx: int = 2
    tn_box_idx: int = 4
    auto_open_box: bool = False
    prefer_market_buy: bool = False
    auto_sell_resource: bool = False
    sell_threshold_pct: str = "90"
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

        raw_sell_pct = data.get("sell_threshold_pct", "90")
        sell_pct_str = str(raw_sell_pct) if raw_sell_pct not in (None, "") else "90"

        return cls(
            gold_threshold=str(data.get("gold_threshold", "100000000")),
            wood_pct=str(data.get("wood_pct", "70")),
            iron_pct=str(data.get("iron_pct", "70")),
            stone_pct=str(data.get("stone_pct", "70")),
            food_pct=str(data.get("food_pct", "70")),
            gold_box_idx=int(data.get("gold_box_idx", 2)),
            tn_box_idx=int(data.get("tn_box_idx", 4)),
            auto_open_box=bool(data.get("auto_open_box", False)),
            prefer_market_buy=bool(data.get("prefer_market_buy", False)),
            auto_sell_resource=bool(data.get("auto_sell_resource", False)),
            sell_threshold_pct=sell_pct_str,
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
    city_id: Optional[int] = None
    generals: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ThaoPhatProfile":
        if not isinstance(data, dict):
            return cls()
        min_army = str(data.get("min_army", data.get("target_infantry", "5000")))
        raw_gens = data.get("generals", [])
        gens = [int(x) for x in raw_gens if str(x).isdigit()] if isinstance(raw_gens, list) else []
        cid = data.get("city_id")
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
            city_id=int(cid) if cid is not None and str(cid).lstrip("-").isdigit() else None,
            generals=gens,
        )


@dataclass
class GoiDanProfile:
    city_id: Optional[int] = None
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
    auto_swap_tactician: bool = False
    min_tactician_stamina: str = "30"
    attack_action_mode: str = "adaptive"
    action_combo_idx: int = 0

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

        raw_cid = data.get("city_id")
        cid = int(raw_cid) if raw_cid is not None and str(raw_cid).isdigit() else None

        first_type = t_types[0] if t_types else 301
        auto_rec = data.get("auto_recruit")
        if auto_rec is None:
            auto_rec = data.get("auto_recover", True)

        return cls(
            city_id=cid,
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
            auto_swap_tactician=bool(data.get("auto_swap_tactician", False)),
            min_tactician_stamina=str(data.get("min_tactician_stamina", "30")),
            attack_action_mode=str(data.get("attack_action_mode", "adaptive")),
            action_combo_idx=int(data.get("action_combo_idx", 0)),
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
    auto_swap_tactician: bool = False
    min_tactician_stamina: str = "30"
    attack_action_mode: str = "adaptive"
    action_combo_idx: int = 0

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
            auto_swap_tactician=bool(data.get("auto_swap_tactician", False)),
            min_tactician_stamina=str(data.get("min_tactician_stamina", "30")),
            attack_action_mode=str(data.get("attack_action_mode", "adaptive")),
            action_combo_idx=int(data.get("action_combo_idx", 0)),
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
    auto_swap_tactician: bool = False
    min_tactician_stamina: str = "30"
    attack_action_mode: str = "adaptive"
    action_combo_idx: int = 0
    bases: dict[str, BaseBinhManConfig] = field(default_factory=dict)
    current_base_id: Optional[int] = None

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

        cbid = data.get("current_base_id")
        current_base_id = int(cbid) if cbid is not None and str(cbid).lstrip("-").isdigit() else None

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
            auto_swap_tactician=bool(data.get("auto_swap_tactician", False)),
            min_tactician_stamina=str(data.get("min_tactician_stamina", "30")),
            attack_action_mode=str(data.get("attack_action_mode", "adaptive")),
            action_combo_idx=int(data.get("action_combo_idx", 0)),
            bases=bases_map,
            current_base_id=current_base_id,
        )



@dataclass
class LogisticsProfile:
    army_type_idx: int = 0
    amount: str = "1000"
    auto_daily_reward: bool = True
    auto_explore: bool = False
    explore_use_whip: bool = False
    explore_use_coin: bool = False
    explore_turns: str = "1"
    # ADR-0042 + Chuyển quân giới 2 chế độ (Chợ / Quân đội)
    transfer_mode: str = "market"  # "market" | "army"
    transfer_orders: list[dict] = field(default_factory=list)  # {from_city_id,to_city_id,army_id,amount}
    transfer_interval: str = "60"
    army_transfer_from_city_id: int = 0
    army_transfer_to_city_id: int = 0
    army_transfer_weapon_id: int = 406
    army_transfer_general_ids: list[int] = field(default_factory=list)
    army_transfer_loop: bool = True
    tribute_enabled: bool = False
    tribute_building_gid: int = 1  # 1: Quan Phủ, 2: Tường Thành

    @classmethod
    def from_dict(cls, data: dict) -> "LogisticsProfile":
        if not isinstance(data, dict):
            return cls()
        use_whip = bool(data.get("explore_use_whip", False))
        use_coin = bool(data.get("explore_use_coin", False))
        if use_whip and use_coin:
            use_coin = False
        raw_mode = str(data.get("transfer_mode", "market")).strip().lower()
        transfer_mode = raw_mode if raw_mode in ("market", "army") else "market"
        orders: list[dict] = []
        raw_orders = data.get("transfer_orders")
        if isinstance(raw_orders, list):
            for o in raw_orders:
                try:
                    orders.append({
                        "from_city_id": int(o["from_city_id"]),
                        "to_city_id": int(o["to_city_id"]),
                        "army_id": int(o["army_id"]),
                        "amount": max(1, int(o["amount"])),
                    })
                except (KeyError, TypeError, ValueError):
                    continue
        raw_gids = data.get("army_transfer_general_ids")
        army_gids: list[int] = []
        if isinstance(raw_gids, list):
            for g in raw_gids:
                try:
                    gi = int(g)
                    if gi > 0 and gi not in army_gids:
                        army_gids.append(gi)
                except (TypeError, ValueError):
                    continue
        try:
            army_from = int(data.get("army_transfer_from_city_id", 0) or 0)
        except (TypeError, ValueError):
            army_from = 0
        try:
            army_to = int(data.get("army_transfer_to_city_id", 0) or 0)
        except (TypeError, ValueError):
            army_to = 0
        try:
            army_wid = int(data.get("army_transfer_weapon_id", 406) or 406)
        except (TypeError, ValueError):
            army_wid = 406
        try:
            t_gid = int(data.get("tribute_building_gid", 1))
        except (TypeError, ValueError):
            t_gid = 1
        if t_gid not in (1, 2):
            t_gid = 1
        return cls(
            transfer_mode=transfer_mode,
            transfer_orders=orders,
            transfer_interval=str(data.get("transfer_interval", "60")),
            army_transfer_from_city_id=army_from,
            army_transfer_to_city_id=army_to,
            army_transfer_weapon_id=army_wid,
            army_transfer_general_ids=army_gids,
            army_transfer_loop=bool(data.get("army_transfer_loop", True)),
            tribute_enabled=bool(data.get("tribute_enabled", False)),
            tribute_building_gid=t_gid,
            army_type_idx=int(data.get("army_type_idx", 0)),
            amount=str(data.get("amount", "1000")),
            auto_daily_reward=bool(data.get("auto_daily_reward", True)),
            auto_explore=bool(data.get("auto_explore", False)),
            explore_use_whip=use_whip,
            explore_use_coin=use_coin,
            explore_turns=str(data.get("explore_turns", "1")),
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


@dataclass(init=False)
class NotificationProfile:
    desktop_enabled: bool = True
    sound_enabled: bool = True
    web_enabled: bool = True
    telegram_enabled: bool = False
    telegram_alert_captcha: bool = True
    telegram_alert_disconnect: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    def __init__(
        self,
        desktop_enabled: Optional[bool] = None,
        sound_enabled: Optional[bool] = None,
        telegram_enabled: Optional[bool] = None,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
        notify_desktop_toast: Optional[bool] = None,
        notify_sound: Optional[bool] = None,
        notify_telegram: Optional[bool] = None,
        web_enabled: Optional[bool] = None,
        notify_web: Optional[bool] = None,
        telegram_alert_captcha: Optional[bool] = None,
        telegram_alert_disconnect: Optional[bool] = None,
        **kwargs,
    ):
        d_val = notify_desktop_toast if notify_desktop_toast is not None else desktop_enabled
        self.desktop_enabled = True if d_val is None else bool(d_val)

        s_val = notify_sound if notify_sound is not None else sound_enabled
        self.sound_enabled = True if s_val is None else bool(s_val)

        w_val = notify_web if notify_web is not None else web_enabled
        self.web_enabled = True if w_val is None else bool(w_val)

        t_val = notify_telegram if notify_telegram is not None else telegram_enabled
        self.telegram_enabled = False if t_val is None else bool(t_val)

        self.telegram_alert_captcha = True if telegram_alert_captcha is None else bool(telegram_alert_captcha)
        self.telegram_alert_disconnect = True if telegram_alert_disconnect is None else bool(telegram_alert_disconnect)

        self.telegram_bot_token = str(kwargs.get("telegram_bot_token", telegram_bot_token)).strip()
        self.telegram_chat_id = str(kwargs.get("telegram_chat_id", telegram_chat_id)).strip()

    @property
    def notify_desktop_toast(self) -> bool:
        return self.desktop_enabled

    @notify_desktop_toast.setter
    def notify_desktop_toast(self, val: bool):
        self.desktop_enabled = bool(val)

    @property
    def notify_sound(self) -> bool:
        return self.sound_enabled

    @notify_sound.setter
    def notify_sound(self, val: bool):
        self.sound_enabled = bool(val)

    @property
    def notify_telegram(self) -> bool:
        return self.telegram_enabled

    @notify_telegram.setter
    def notify_telegram(self, val: bool):
        self.telegram_enabled = bool(val)

    @property
    def notify_web(self) -> bool:
        return self.web_enabled

    @notify_web.setter
    def notify_web(self, val: bool):
        self.web_enabled = bool(val)

    @classmethod
    def from_dict(cls, data: dict) -> "NotificationProfile":
        if not isinstance(data, dict):
            return cls()
        d_val = data.get("notify_desktop_toast")
        if d_val is None:
            d_val = data.get("desktop_enabled", True)

        s_val = data.get("notify_sound")
        if s_val is None:
            s_val = data.get("sound_enabled", True)

        w_val = data.get("notify_web")
        if w_val is None:
            w_val = data.get("web_enabled", True)

        t_val = data.get("notify_telegram")
        if t_val is None:
            t_val = data.get("telegram_enabled", False)

        return cls(
            desktop_enabled=bool(d_val),
            sound_enabled=bool(s_val),
            web_enabled=bool(w_val),
            telegram_enabled=bool(t_val),
            telegram_alert_captcha=bool(data.get("telegram_alert_captcha", True)),
            telegram_alert_disconnect=bool(data.get("telegram_alert_disconnect", True)),
            telegram_bot_token=str(data.get("telegram_bot_token", "")).strip(),
            telegram_chat_id=str(data.get("telegram_chat_id", "")).strip(),
        )

    def to_dict(self) -> dict:
        return {
            "desktop_enabled": self.desktop_enabled,
            "sound_enabled": self.sound_enabled,
            "web_enabled": self.web_enabled,
            "telegram_enabled": self.telegram_enabled,
            "telegram_alert_captcha": self.telegram_alert_captcha,
            "telegram_alert_disconnect": self.telegram_alert_disconnect,
            "notify_desktop_toast": self.desktop_enabled,
            "notify_sound": self.sound_enabled,
            "notify_web": self.web_enabled,
            "notify_telegram": self.telegram_enabled,
            "telegram_bot_token": self.telegram_bot_token,
            "telegram_chat_id": self.telegram_chat_id,
        }


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
    auto_capture_boss: bool = False
    capture_boss_max_morale: str = "60"

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
            auto_capture_boss=bool(data.get("auto_capture_boss", False)),
            capture_boss_max_morale=str(data.get("capture_boss_max_morale", "60")),
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
class NienThuProfile:
    city_id: int = 0
    generals: list[int] = field(default_factory=list)
    target_infantry: str = "0"
    target_cavalry: str = "0"
    target_archers: str = "0"
    auto_recruit: bool = False
    auto_morale: bool = False
    min_morale: str = "95"
    speed_up_march: bool = False
    speed_up_return: bool = False
    stop_on_jade: bool = False
    use_world_chat: bool = True
    run_immediately: bool = True
    enabled: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "NienThuProfile":
        if not isinstance(data, dict):
            return cls()
        raw_gens = data.get("generals", [])
        gens: list[int] = []
        if isinstance(raw_gens, list):
            for g in raw_gens:
                try:
                    gens.append(int(g))
                except (TypeError, ValueError):
                    pass
        try:
            cid = int(data.get("city_id", 0) or 0)
        except (TypeError, ValueError):
            cid = 0
        return cls(
            city_id=cid,
            generals=gens,
            target_infantry=str(data.get("target_infantry", "0")),
            target_cavalry=str(data.get("target_cavalry", "0")),
            target_archers=str(data.get("target_archers", "0")),
            auto_recruit=bool(data.get("auto_recruit", False)),
            auto_morale=bool(data.get("auto_morale", False)),
            min_morale=str(data.get("min_morale", "95")),
            speed_up_march=bool(data.get("speed_up_march", False)),
            speed_up_return=bool(data.get("speed_up_return", False)),
            stop_on_jade=bool(data.get("stop_on_jade", False)),
            use_world_chat=bool(data.get("use_world_chat", True)),
            run_immediately=bool(data.get("run_immediately", True)),
            enabled=bool(data.get("enabled", False)),
        )


def _parse_ordered_positive_ids(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    seen: set[int] = set()
    for item in raw:
        try:
            gid = int(item)
        except (TypeError, ValueError):
            continue
        if gid > 0 and gid not in seen:
            seen.add(gid)
            out.append(gid)
    return out


@dataclass
class TrainingProfile:
    enabled: bool = False
    vo_general_ids: list[int] = field(default_factory=list)
    van_general_ids: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TrainingProfile":
        if not isinstance(data, dict):
            return cls()
        return cls(
            enabled=bool(data.get("enabled", False)),
            vo_general_ids=_parse_ordered_positive_ids(data.get("vo_general_ids")),
            van_general_ids=_parse_ordered_positive_ids(data.get("van_general_ids")),
        )


@dataclass
class BaseSyncResult:
    """Kết quả Đồng Bộ Danh Sách Căn Cứ vào Hồ Sơ Cấu Hình."""

    changed: bool = False
    added_ids: list[int] = field(default_factory=list)
    removed_ids: list[int] = field(default_factory=list)
    renamed_ids: list[int] = field(default_factory=list)
    updated_refs: list[str] = field(default_factory=list)


def _parse_int_id(raw: Any) -> Optional[int]:
    if raw is None or isinstance(raw, bool):
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.lstrip("-").isdigit() and s != "-":
        return int(s)
    return None


def _normalize_bases(bases: Any) -> list[tuple[int, str, bool]]:
    """Chuẩn hóa danh sách Căn Cứ (City hoặc dict) thành (id, name, is_camp)."""
    if not bases:
        return []
    out: list[tuple[int, str, bool]] = []
    seen: set[int] = set()
    for b in bases:
        if isinstance(b, dict):
            bid = _parse_int_id(b.get("id"))
            name = str(b.get("name", ""))
            is_camp = bool(b.get("is_camp", False) or b.get("type") == "Doanh trại" or (bid is not None and bid < 0))
        else:
            bid = _parse_int_id(getattr(b, "id", None))
            name = str(getattr(b, "name", ""))
            is_camp = bool(
                getattr(b, "is_camp", False)
                or getattr(b, "type", "") == "Doanh trại"
                or (bid is not None and bid < 0)
            )
        if bid is None or bid in seen:
            continue
        seen.add(bid)
        out.append((bid, name, is_camp))
    return out


def _prune_id_dict(mapping: dict[str, Any], valid_ids: set[int]) -> tuple[dict[str, Any], list[int], bool]:
    """Lọc bỏ các khóa ID không còn nằm trong tập hợp lệ."""
    kept: dict[str, Any] = {}
    removed: list[int] = []
    changed = False
    for k, v in mapping.items():
        parsed = _parse_int_id(k)
        if parsed is None or parsed not in valid_ids:
            if parsed is not None:
                removed.append(parsed)
            changed = True
            continue
        kept[str(parsed)] = v
        if str(parsed) != k:
            changed = True
    return kept, removed, changed


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
    notifications: NotificationProfile = field(default_factory=NotificationProfile)
    nien_thu: NienThuProfile = field(default_factory=NienThuProfile)
    training: TrainingProfile = field(default_factory=TrainingProfile)

    def sync_with_bases(
        self,
        bases: Any,
        *,
        add_missing_building_cities: bool = True,
    ) -> BaseSyncResult:
        """Đồng bộ toàn bộ Hồ Sơ theo danh sách Căn Cứ thực tế từ máy chủ (ADR-0040).

        Chỉ thanh lọc khi `bases` hợp lệ và khác rỗng; tuyệt đối không xóa dữ liệu khi
        danh sách máy chủ rỗng do lỗi mạng hoặc phiên hết hạn.
        """
        norm = _normalize_bases(bases)
        if not norm:
            return BaseSyncResult(changed=False)

        valid_base_ids = {bid for bid, _, _ in norm}
        valid_city_ids = {bid for bid, _, is_camp in norm if not is_camp}
        base_name_map = {bid: name for bid, name, _ in norm}
        first_base_id = norm[0][0]
        first_city_id = next((bid for bid, _, is_camp in norm if not is_camp), None)

        res = BaseSyncResult()
        removed_set: set[int] = set()

        # 1. Building.cities (áp dụng cho cả Thành và Doanh trại)
        old_bld_cities = self.building.cities
        had_bld_cities = bool(old_bld_cities)
        parsed_old_bld: dict[int, CityBuildingConfig] = {}
        for k, cfg in old_bld_cities.items():
            pid = _parse_int_id(k)
            if pid is None or pid not in valid_base_ids:
                if pid is not None:
                    removed_set.add(pid)
                res.changed = True
                continue
            parsed_old_bld[pid] = cfg

        skip_adding_bld = (not had_bld_cities and bool(self.building.plans)) or not add_missing_building_cities
        if not skip_adding_bld:
            new_bld_cities: dict[str, CityBuildingConfig] = {}
            for idx, (bid, bname, _is_camp) in enumerate(norm):
                if bid in parsed_old_bld:
                    cfg = parsed_old_bld[bid]
                    if cfg.name != bname:
                        cfg.name = bname
                        res.renamed_ids.append(bid)
                        res.changed = True
                    new_bld_cities[str(bid)] = cfg
                else:
                    new_bld_cities[str(bid)] = CityBuildingConfig(
                        name=bname,
                        enabled=(not had_bld_cities and idx == 0),
                        resource=False,
                        plans=[],
                    )
                    res.added_ids.append(bid)
                    res.changed = True
            self.building.cities = new_bld_cities
        else:
            new_bld_cities = {}
            for bid, cfg in parsed_old_bld.items():
                bname = base_name_map[bid]
                if cfg.name != bname:
                    cfg.name = bname
                    res.renamed_ids.append(bid)
                    res.changed = True
                new_bld_cities[str(bid)] = cfg
            self.building.cities = new_bld_cities

        # 2. Resource.resource_cities (cùng tập roster.bases với building.cities)
        old_res_cities = list(self.resource.resource_cities)
        filtered_res_cities = sorted({cid for cid in old_res_cities if cid in valid_base_ids})
        for cid in old_res_cities:
            if cid not in valid_base_ids:
                removed_set.add(cid)
        if filtered_res_cities != old_res_cities:
            self.resource.resource_cities = filtered_res_cities
            res.changed = True

        # 3. BinhMan.bases & tham chiếu current_base_id / parent_city_id / camp_id
        new_bm_bases, bm_removed, bm_changed = _prune_id_dict(self.binh_man.bases, valid_base_ids)
        removed_set.update(bm_removed)
        if bm_changed:
            res.changed = True
        for bid_str, bcfg in new_bm_bases.items():
            bid = int(bid_str)
            bname = base_name_map.get(bid, "")
            if bname and bcfg.name != bname:
                bcfg.name = bname
                if bid not in res.renamed_ids:
                    res.renamed_ids.append(bid)
                res.changed = True
            if bcfg.parent_city_id:
                pcid = _parse_int_id(bcfg.parent_city_id)
                if pcid is None or pcid not in valid_city_ids:
                    bcfg.parent_city_id = str(first_city_id) if first_city_id is not None else ""
                    res.updated_refs.append(f"binh_man.bases.{bid_str}.parent_city_id")
                    res.changed = True
            if bcfg.camp_id:
                camp_id = _parse_int_id(bcfg.camp_id)
                if camp_id is None or camp_id not in valid_base_ids:
                    bcfg.camp_id = ""
                    res.updated_refs.append(f"binh_man.bases.{bid_str}.camp_id")
                    res.changed = True
        self.binh_man.bases = new_bm_bases

        if self.binh_man.current_base_id is not None and self.binh_man.current_base_id not in valid_base_ids:
            self.binh_man.current_base_id = first_base_id
            res.updated_refs.append("binh_man.current_base_id")
            res.changed = True
        if self.binh_man.camp_id:
            flat_camp = _parse_int_id(self.binh_man.camp_id)
            if flat_camp is None or flat_camp not in valid_base_ids:
                self.binh_man.camp_id = ""
                res.updated_refs.append("binh_man.camp_id")
                res.changed = True
        if self.binh_man.parent_city_id:
            flat_parent = _parse_int_id(self.binh_man.parent_city_id)
            if flat_parent is None or flat_parent not in valid_city_ids:
                self.binh_man.parent_city_id = str(first_city_id) if first_city_id is not None else ""
                res.updated_refs.append("binh_man.parent_city_id")
                res.changed = True

        # 4. Crafting.cities (chỉ Thành)
        new_craft_cities, craft_removed, craft_changed = _prune_id_dict(self.crafting.cities, valid_city_ids)
        removed_set.update(craft_removed)
        if craft_changed:
            self.crafting.cities = new_craft_cities
            res.changed = True

        # 5. Các trường tham chiếu đơn theo Thành (roster.cities)
        for attr_name, section in (
            ("research.city_id", self.research),
            ("thao_phat.city_id", self.thao_phat),
            ("goi_dan.city_id", self.goi_dan),
        ):
            cur_val = section.city_id
            if cur_val is not None and cur_val not in valid_city_ids:
                section.city_id = first_city_id
                res.updated_refs.append(attr_name)
                res.changed = True

        if self.nien_thu.city_id != 0 and self.nien_thu.city_id not in valid_city_ids:
            self.nien_thu.city_id = first_city_id if first_city_id is not None else 0
            res.updated_refs.append("nien_thu.city_id")
            res.changed = True

        res.removed_ids = sorted(removed_set)
        return res

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
        if "notifications" in data and hasattr(self.notifications, "to_dict"):
            data["notifications"] = self.notifications.to_dict()
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
            notifications=NotificationProfile.from_dict(data.get("notifications", {})),
            nien_thu=NienThuProfile.from_dict(data.get("nien_thu", {})),
            training=TrainingProfile.from_dict(data.get("training", {})),
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
        data_dir: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Giải quyết đường dẫn file hồ sơ cấu hình phù hợp nhất."""
        if target_path:
            return Path(target_path)

        from .paths import get_data_dir

        base_dir = get_data_dir(data_dir)
        acc_name = cls.default_profile_name(username, server_id)
        if acc_name != cls.DEFAULT_FILENAME and (base_dir / acc_name).exists():
            return base_dir / acc_name

        if (base_dir / cls.DEFAULT_FILENAME).exists():
            return base_dir / cls.DEFAULT_FILENAME

        return base_dir / acc_name

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
