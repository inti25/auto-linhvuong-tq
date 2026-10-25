"""Danh sách thành, doanh trại, tướng và biên chế quân đội.

Nguồn:
- Common.ashx?id=29: Danh sách Thành chính.
- City.ashx?id=7: Danh sách chi tiết Thành và Doanh trại kèm tọa độ và cấp độ.
- Common.ashx?id=32 type=1 (Văn quan) / type=2 (Võ tướng): Tướng trong Thành và Doanh trại (id âm).
- Common.ashx?id=76: Chi tiết biên chế quân đội (bộ binh, kỵ binh, cung binh).
"""

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .gateway import GatewayClient


@dataclass(frozen=True)
class City:
    id: int
    name: str
    type: str = "Thành"  # "Thành" hoặc "Doanh trại"
    pos_x: int = 0
    pos_y: int = 0
    level: int = 0

    @property
    def is_camp(self) -> bool:
        return self.type == "Doanh trại" or self.id < 0

    @property
    def display_name(self) -> str:
        prefix = "[Trại]" if self.is_camp else "[Thành]"
        coords = f" | {self.pos_x},{self.pos_y}" if (self.pos_x or self.pos_y) else ""
        return f"{prefix} {self.name} (ID: {self.id}{coords})"


GENERAL_STATUS_NAMES = {
    0: "Rảnh rỗi",
    1: "Trọng thương",
    2: "Dưỡng thương",
    16: "Xuất chinh",
    17: "Tăng viện",
    18: "Tỉ võ",
    19: "Tầm phỏng",
    20: "Trinh sát",
    21: "Phái khiển",
    22: "Xây thành",
    23: "Xây doanh trại",
    24: "Nhiệm vụ / Thảo phạt",
    25: "Đang bận",
    26: "Phòng thủ",
    27: "Luyện binh",
    28: "Lôi đài liên minh",
    29: "Trú đóng",
    30: "Đang đấu giá",
    32: "Đang quay về",
    33: "Tầm bảo",
}


@dataclass(frozen=True)
class General:
    id: int
    name: str
    role: str  # "van" (Văn quan) hoặc "vo" (Võ tướng)
    level: int
    morale: int
    stamina: int
    stamina_max: int
    status: int = 0  # 0: rảnh rỗi, != 0: bận
    upgrading_time: int = 0  # thời gian nâng sĩ khí còn lại (giây)

    @property
    def is_idle(self) -> bool:
        return self.status == 0 and self.upgrading_time <= 0

    @property
    def status_text(self) -> str:
        if self.status != 0:
            return GENERAL_STATUS_NAMES.get(self.status, f"Bận ({self.status})")
        if self.upgrading_time > 0:
            return f"Nâng SK ({self.upgrading_time}s)"
        return "Rảnh rỗi"

    @property
    def role_text(self) -> str:
        return "Văn quan" if self.role == "van" else "Võ tướng"


@dataclass(frozen=True)
class Army:
    infantry: int
    cavalry: int
    archers: int

    @property
    def total(self) -> int:
        return self.infantry + self.cavalry + self.archers


@dataclass
class Roster:
    cities: list[City] = field(default_factory=list)
    camps: list[City] = field(default_factory=list)
    _generals: dict[int, list[General]] = field(default_factory=dict)
    _armies: dict[int, Army] = field(default_factory=dict)
    _upgrading_time: dict[int, int] = field(default_factory=dict)

    @property
    def bases(self) -> list[City]:
        """Tất cả căn cứ gồm cả Thành và Doanh trại."""
        return self.cities + self.camps

    def base_by_id(self, base_id: int) -> Optional[City]:
        for b in self.bases:
            if b.id == base_id:
                return b
        return None

    def generals_of(self, base_id: int) -> list[General]:
        return list(self._generals.get(base_id, []))

    def army_of(self, general_id: int) -> Optional[Army]:
        return self._armies.get(general_id)

    def upgrading_time_of(self, general_id: int) -> int:
        return self._upgrading_time.get(general_id, 0)

    def update_camp_position(self, camp_id: int, pos_x: int, pos_y: int) -> None:
        """Cập nhật tọa độ mới cho Doanh trại sau mỗi bước di chuyển thành công."""
        for i, c in enumerate(self.camps):
            if c.id == camp_id:
                self.camps[i] = City(
                    id=c.id, name=c.name, type=c.type, pos_x=pos_x, pos_y=pos_y, level=c.level
                )
                return
        for i, c in enumerate(self.cities):
            if c.id == camp_id:
                self.cities[i] = City(
                    id=c.id, name=c.name, type=c.type, pos_x=pos_x, pos_y=pos_y, level=c.level
                )
                return


_ROLES = {1: "van", 2: "vo"}


def fetch_roster(
    gateway: GatewayClient,
    only_base_ids: Optional[Iterable[int]] = None,
) -> Roster:
    roster = Roster()
    # 1. Lấy danh sách Thành chính từ Common.ashx?id=29
    resp = gateway.call("Common.ashx", 29, {}) or {}
    cities_map = {}
    for c in resp.get("city", []):
        cid = int(c[0])
        cities_map[cid] = City(id=cid, name=str(c[1]), type="Thành")
    roster.cities = list(cities_map.values())

    # 2. Bổ sung Doanh trại và tọa độ từ City.ashx?id=7 nếu có
    camps_map = {}
    resp_c7 = gateway.call("City.ashx", 7, {"_": ""}) or {}
    infos = resp_c7.get("infos") or resp_c7.get("citys", [])
    if isinstance(infos, list):
        for item in infos:
            if isinstance(item, list) and len(item) > 7:
                cid = int(item[1])
                cname = str(item[2])
                cx = int(item[4])
                cy = int(item[5])
                clevel = int(item[7])
                ctype_val = int(item[8]) if len(item) > 8 else 1
                is_camp = ctype_val not in (1, 2, 3, 4)
                if is_camp:
                    camps_map[cid] = City(
                        id=cid, name=cname, type="Doanh trại", pos_x=cx, pos_y=cy, level=clevel
                    )
                elif cid in cities_map:
                    cities_map[cid] = City(
                        id=cid, name=cname, type="Thành", pos_x=cx, pos_y=cy, level=clevel
                    )
        roster.cities = list(cities_map.values())

    # 3. Quét danh sách Văn quan (type=1) và Võ tướng (type=2) từ Common.ashx?id=32
    raw_generals_by_cid: dict[int, list[tuple[int, list]]] = {}
    martial_cids: set[int] = set()
    city_ids = set(cities_map.keys())

    for type_ in (1, 2):
        resp = gateway.call("Common.ashx", 32, {"type": str(type_)}) or {}
        for entry in resp.get("list", []):
            cid = int(entry[0])
            cname = str(entry[1])
            cx = int(entry[2]) if len(entry) > 2 else 0
            cy = int(entry[3]) if len(entry) > 3 else 0

            # Nếu là Doanh trại (cid âm hoặc chưa có trong danh sách thành)
            if cid < 0:
                if cid not in camps_map:
                    camps_map[cid] = City(
                        id=cid, name=cname, type="Doanh trại", pos_x=cx, pos_y=cy
                    )
            elif cid not in city_ids:
                if cid not in cities_map:
                    cities_map[cid] = City(
                        id=cid, name=cname, type="Thành", pos_x=cx, pos_y=cy
                    )
                city_ids.add(cid)

            g_entries = entry[4] if len(entry) > 4 else []
            if g_entries and type_ == 2:
                martial_cids.add(cid)
            for g in g_entries:
                raw_generals_by_cid.setdefault(cid, []).append((type_, g))

    # 4. Lấy thông tin chi tiết biên chế, sĩ khí đội quân và thời gian nâng sĩ khí (API 76)
    # Bao gồm cả Thành và Doanh trại (đặc biệt là các căn cứ có võ tướng)
    morale_map = {}
    upgrading_map = {}
    all_bases = list(cities_map.values()) + list(camps_map.values())
    if only_base_ids is not None:
        target_ids = {int(x) for x in only_base_ids}
        bases_to_query = [b for b in all_bases if b.id in target_ids]
    else:
        bases_to_query = [b for b in all_bases if not martial_cids or b.id in martial_cids or b.is_camp]

    for base in bases_to_query:
        resp = gateway.call("Common.ashx", 76, {"cid": str(base.id)}) or {}
        for entry in resp.get("list", []):
            if len(entry) > 2 and isinstance(entry[2], list):
                for g in entry[2]:
                    gid = int(g[0])
                    roster._armies[gid] = Army(int(g[5]), int(g[6]), int(g[7]))
                    if len(g) > 9:
                        morale_map[gid] = int(g[9])
                    if len(g) > 10:
                        up_t = int(g[10])
                        upgrading_map[gid] = up_t
                        roster._upgrading_time[gid] = up_t

    # 5. Khởi tạo đối tượng General hoàn chỉnh
    for cid, glist in raw_generals_by_cid.items():
        for type_, g in glist:
            gid = int(g[0])
            morale_val = morale_map.get(gid, int(g[7]))
            # Nếu là võ tướng mà chưa có trong API 76, khởi tạo Army(0, 0, 0)
            if type_ == 2 and gid not in roster._armies:
                roster._armies[gid] = Army(0, 0, 0)

            roster._generals.setdefault(cid, []).append(
                General(
                    id=gid,
                    name=str(g[1]),
                    role=_ROLES.get(type_, "vo"),
                    level=int(g[6]),
                    morale=morale_val,
                    stamina=int(g[8]),
                    stamina_max=int(g[9]),
                    status=int(g[5]) if len(g) > 5 else 0,
                    upgrading_time=upgrading_map.get(gid, 0),
                )
            )

    roster.cities = list(cities_map.values())
    roster.camps = list(camps_map.values())
    return roster
