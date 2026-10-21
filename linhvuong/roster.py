"""Danh sách thành trì, tướng và biên chế quân đội (chỉ đọc).

Nguồn: Common.ashx?id=29 (thành), id=32 type=1/2 (văn/võ tướng theo thành), id=76 (biên chế).
Ý nghĩa các cột là SUY RA từ dữ liệu server 57, chưa có tài liệu chính thức:
- tướng: [id, tên, _, loại, _, _, cấp, sĩ khí, thể lực, thể lực tối đa, ...]
- biên chế (id=76): [id, tên, _, _, _, bộ binh, kỵ binh, cung binh, ...]; thứ tự bộ/kỵ/cung theo
  tên ref_bo_binh, ref_ky_binh, ref_cung_binh trong ZMan, cần đối chiếu với giao diện game.
"""

from dataclasses import dataclass, field
from typing import Optional

from .gateway import GatewayClient


@dataclass(frozen=True)
class City:
    id: int
    name: str


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
    role: str  # "van" (văn tướng/mưu sĩ) hoặc "vo" (võ tướng)
    level: int
    morale: int
    stamina: int
    stamina_max: int
    status: int = 0  # 0: rảnh rỗi, != 0: bận (di chuyển / chiến đấu / thảo phạt...)
    upgrading_time: int = 0  # thời gian nâng sỹ khí còn lại (giây)

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
    _generals: dict[int, list[General]] = field(default_factory=dict)
    _armies: dict[int, Army] = field(default_factory=dict)
    _upgrading_time: dict[int, int] = field(default_factory=dict)

    def generals_of(self, city_id: int) -> list[General]:
        return list(self._generals.get(city_id, []))

    def army_of(self, general_id: int) -> Optional[Army]:
        return self._armies.get(general_id)

    def upgrading_time_of(self, general_id: int) -> int:
        return self._upgrading_time.get(general_id, 0)


_ROLES = {1: "van", 2: "vo"}


def fetch_roster(gateway: GatewayClient) -> Roster:
    roster = Roster()
    resp = gateway.call("Common.ashx", 29, {}) or {}
    roster.cities = [City(int(c[0]), str(c[1])) for c in resp.get("city", [])]
    city_ids = {c.id for c in roster.cities}

    # Lấy thông tin chi tiết biên chế, sĩ khí đội quân và thời gian nâng sỹ khí (API 76)
    morale_map = {}
    upgrading_map = {}
    for city in roster.cities:
        resp = gateway.call("Common.ashx", 76, {"cid": str(city.id)}) or {}
        for entry in resp.get("list", []):
            for g in entry[2]:
                gid = int(g[0])
                roster._armies[gid] = Army(int(g[5]), int(g[6]), int(g[7]))
                if len(g) > 9:
                    morale_map[gid] = int(g[9])
                if len(g) > 10:
                    up_t = int(g[10])
                    upgrading_map[gid] = up_t
                    roster._upgrading_time[gid] = up_t

    for type_ in (1, 2):
        resp = gateway.call("Common.ashx", 32, {"type": str(type_)}) or {}
        for entry in resp.get("list", []):
            cid = int(entry[0])
            if cid not in city_ids:  # bỏ Trại (id âm)
                continue
            for g in entry[4]:
                gid = int(g[0])
                morale_val = morale_map.get(gid, int(g[7]))
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

    return roster
