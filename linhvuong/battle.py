"""Module quản lý và điều khiển chiến trường (BattleEngine / BattleController).

Hỗ trợ:
- Lấy thông tin chiến trường qua OPT.ashx?id=24.
- Nhận diện phe Ta / Phe Địch chính xác theo user_id (tránh nhầm lẫn khi phòng thủ).
- Tác chiến và phân bổ mục tiêu thông minh qua OPT.ashx?id=54 (thích ứng binh chủng, bỏ qua quân hỗn loạn, cô lập BOSS).
- Tự động tính toán ma trận tương khắc ngũ hành toàn cục 5x5 và đổi trận ở 10~15 giây cuối hiệp qua OPT.ashx?id=57.
- Phân tầng mưu lược chiến trường qua OPT.ashx?id=70: Tự động hóa giải Hỗn loạn (96), Rút lui khẩn cấp (92), Mưu kế chủ động (93, 95, 94).
- Ghi nhật ký chiến trường từng hiệp và tổng kết chiến quả sau trận đấu.
"""

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("linhvuong.battle")

FORMATION_NAMES = {
    1: "Trùy hình (锥形)",
    2: "Câu hình (钩形)",
    3: "Kê hình (箕形)",
    4: "Hạc dực (鹤翼)",
    5: "Ngư lân (鱼鳞)",
}

# Quy luật ngũ hành trận pháp Linh Vương (1 khắc 3, 3 khắc 5, 5 khắc 2, 2 khắc 4, 4 khắc 1):
COUNTER_MAP = {
    3: 1,  # Địch là Kê hình (3) -> Ta dùng Trùy hình (1)
    5: 3,  # Địch là Ngư lân (5) -> Ta dùng Kê hình (3)
    2: 5,  # Địch là Câu hình (2) -> Ta dùng Ngư lân (5)
    4: 2,  # Địch là Hạc dực (4) -> Ta dùng Câu hình (2)
    1: 4,  # Địch là Trùy hình (1) -> Ta dùng Hạc dực (4)
}

# Ma trận ngũ hành đối kháng toàn cục 5x5 từ WarFunc.cs trong LVClientCode:
# Hàng là quân ta (1..5), Cột là quân địch (1..5)
# Hệ số: 1.2 (Khắc mạnh), 1.1 (Ưu thế), 1.0 (Ngang bằng), 0.9 (Hơi yếu), 0.8 (Bị khắc)
ARRAY_VALUE = [
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 1.1, 1.2, 0.8, 0.9],  # Trùy (1): khắc Kê (1.2), bị Hạc khắc (0.8)
    [0.0, 0.9, 1.0, 1.1, 1.2, 0.8],  # Câu (2): khắc Hạc (1.2), bị Ngư khắc (0.8)
    [0.0, 0.8, 0.9, 1.0, 1.1, 1.2],  # Kê (3): khắc Ngư (1.2), bị Trùy khắc (0.8)
    [0.0, 1.2, 0.8, 0.9, 1.0, 1.1],  # Hạc (4): khắc Trùy (1.2), bị Câu khắc (0.8)
    [0.0, 1.1, 1.2, 0.8, 0.9, 1.0],  # Ngư (5): khắc Câu (1.2), bị Kê khắc (0.8)
]

ATTACK_ACTIONS = {
    0: "Tùy chọn (Mặc định)",
    1: "Tấn công phổ thông",
    2: "Đơn chiến",
    3: "Phòng ngự",
    4: "Rút lui",
    10: "Đột kích",
    11: "Mãnh công",
    12: "Thủy công",
    13: "Hỏa tiễn",
    14: "Phản kích",
}

STRATAGEMS = {
    0: "Không dùng",
    92: "Kim thiền thoát xác",
    93: "Phản khách vi chủ",
    94: "Quan môn tróc tặc",
    95: "Cầm tặc cầm vương",
    96: "Hủy bỏ trạng thái",
}

KNOWN_BOSS_NAMES = {
    "马超", "张飞", "黄忠", "关羽", "赵云", "宝箱",
    "董卓", "吕布", "袁绍", "曹操", "刘备", "孙权", "BOSS", "Boss",
}

COMMON_MONSTER_NAMES = {
    "山贼", "强盗", "恶霸", "黄巾", "流寇", "土匪",
    "蛮兵", "象兵", "藤甲兵", "狼兵", "叛军", "贼兵", "飞贼",
}


@dataclass
class BattleTroop:
    position: int
    player_name: str
    user_id: int
    general_name: str
    general_id: int
    city_id: int
    formation_id: int
    morale: int
    soldiers: int
    initial_soldiers: int
    flag: int
    is_boss: bool = False
    status: int = 0  # 0: Bình thường, 1: Hỗn loạn, 2/3: Khác
    infantry: int = 0
    cavalry: int = 0
    archers: int = 0
    siege: int = 0
    attack_action: int = 0
    target_id: int = 0
    tactician_id: int = 0
    tactician_name: str = ""

    @classmethod
    def from_raw(cls, raw: list) -> "BattleTroop":
        pos = raw[0] if len(raw) > 0 else 0
        pname = raw[1] if len(raw) > 1 else ""
        uid = raw[2] if len(raw) > 2 else 0
        gname = raw[3] if len(raw) > 3 else ""
        gid = raw[4] if len(raw) > 4 else 0
        cid = raw[6] if len(raw) > 6 else 0
        fid = raw[8] if len(raw) > 8 else 0
        morale = raw[9] if len(raw) > 9 else 0
        status = raw[10] if len(raw) > 10 else 0
        infantry = raw[11] if len(raw) > 11 else 0
        cavalry = raw[12] if len(raw) > 12 else 0
        archers = raw[13] if len(raw) > 13 else 0
        siege = raw[14] if len(raw) > 14 else 0
        attack_action = raw[15] if len(raw) > 15 else 0
        target_id = raw[16] if len(raw) > 16 else 0
        tactician_id = raw[17] if len(raw) > 17 else 0
        tactician_name = str(raw[18]) if len(raw) > 18 and raw[18] else ""
        flag = raw[19] if len(raw) > 19 else 0

        # Số quân thực tế
        total_army = infantry + cavalry + archers + siege
        soldiers = raw[11] if len(raw) > 11 else 0
        init_soldiers = raw[13] if len(raw) > 13 else 0
        if soldiers == 0 and total_army > 0:
            soldiers = total_army
        if init_soldiers == 0:
            init_soldiers = soldiers

        # Nhận diện BOSS chiến trường:
        # 1. Quái thường dã ngoại (Sơn tặc, Cường đạo, Ác bá...) không bao giờ là BOSS.
        # 2. Cờ flag & 0x20 đại diện cho tướng danh / BOSS (flag & 0x10 là quân thủ bình thường).
        # 3. Tên thuộc danh sách danh tướng / BOSS / Bảo rương.
        # 4. Tướng ở vị trí 19 (chủ soái) trong các phụ bản thảo phạt lớn (không thuộc quái thường).
        is_common_monster = any(mname in gname for mname in COMMON_MONSTER_NAMES)
        is_known_boss = any(bname in gname for bname in KNOWN_BOSS_NAMES)

        if is_common_monster and not is_known_boss:
            is_boss = False
        else:
            is_boss = (
                is_known_boss
                or bool(flag & 0x20)
                or (pos == 19 and uid == 0 and not is_common_monster)
            )
        return cls(
            position=pos,
            player_name=pname,
            user_id=uid,
            general_name=gname,
            general_id=gid,
            city_id=cid,
            formation_id=fid,
            morale=morale,
            soldiers=soldiers,
            initial_soldiers=init_soldiers,
            flag=flag,
            is_boss=is_boss,
            status=status,
            infantry=infantry,
            cavalry=cavalry,
            archers=archers,
            siege=siege,
            attack_action=attack_action,
            target_id=target_id,
            tactician_id=tactician_id,
            tactician_name=tactician_name,
        )

    def dominant_soldier_type(self) -> str:
        """Xác định loại binh chủng chiếm đa số của đạo quân."""
        counts = {
            "archers": self.archers,
            "cavalry": self.cavalry,
            "infantry": self.infantry,
            "siege": self.siege,
        }
        max_type = max(counts, key=counts.get)
        if counts[max_type] == 0:
            return "infantry"
        return max_type

    def optimal_action_for_unit(self) -> int:
        """Trả về phương thức tấn công tối ưu theo binh chủng chiếm đa số."""
        dom = self.dominant_soldier_type()
        if dom == "archers":
            return 13  # Hỏa tiễn
        elif dom == "cavalry":
            return 10  # Đột kích
        elif dom in ("infantry", "siege"):
            return 11  # Mãnh công
        return 1  # Tấn công phổ thông


@dataclass
class BattleState:
    ret: int
    site: str
    map_id: int
    bout: int
    bout_left: int
    attack_total: int
    defend_total: int
    is_attacker: bool = True
    our_troops: list[BattleTroop] = field(default_factory=list)
    enemy_troops: list[BattleTroop] = field(default_factory=list)
    boss_troops: list[BattleTroop] = field(default_factory=list)
    is_ended: bool = False

    @classmethod
    def from_json(cls, data: dict, current_user_id: int = 0) -> "BattleState":
        ret = data.get("ret", -1)
        if ret == 13:
            return cls(
                ret=13,
                site="",
                map_id=0,
                bout=0,
                bout_left=0,
                attack_total=0,
                defend_total=0,
                is_attacker=True,
                is_ended=True,
            )

        all_troops = [BattleTroop.from_raw(raw_t) for raw_t in data.get("troops", [])]

        is_attacker = True
        our_troops = []
        enemy_troops = []
        boss_troops = []

        if current_user_id > 0:
            my_attack = [t for t in all_troops if t.position <= 10 and t.user_id == current_user_id]
            my_defend = [t for t in all_troops if t.position > 10 and t.user_id == current_user_id]
            if len(my_defend) > len(my_attack):
                # Người chơi thuộc phe Thủ
                is_attacker = False
                our_troops = [t for t in all_troops if t.position > 10]
                enemy_troops = [t for t in all_troops if t.position <= 10]
            else:
                # Người chơi thuộc phe Công
                is_attacker = True
                our_troops = [t for t in all_troops if t.position <= 10]
                enemy_troops = [t for t in all_troops if t.position > 10]
        else:
            # Fallback mặc định
            for t in all_troops:
                if t.position <= 10:
                    our_troops.append(t)
                else:
                    enemy_troops.append(t)

        for t in enemy_troops:
            if t.is_boss:
                boss_troops.append(t)

        is_ended = (ret != 0) or len(our_troops) == 0 or len(enemy_troops) == 0
        return cls(
            ret=ret,
            site=data.get("site", ""),
            map_id=data.get("mapid", 0),
            bout=data.get("bout", 1),
            bout_left=data.get("bout_left", 0),
            attack_total=data.get("attack_total", 0),
            defend_total=data.get("defend_total", 0),
            is_attacker=is_attacker,
            our_troops=our_troops,
            enemy_troops=enemy_troops,
            boss_troops=boss_troops,
            is_ended=is_ended,
        )


@dataclass
class GeneralBattleStats:
    general_id: int
    general_name: str
    initial_soldiers: int
    final_soldiers: int
    loss_soldiers: int
    initial_morale: int
    final_morale: int
    loss_morale: int
    formation_name: str = ""


@dataclass
class BattleReport:
    battle_id: int
    site: str
    total_bouts: int
    is_victory: bool
    initial_our_soldiers: int
    final_our_soldiers: int
    our_losses: int
    initial_morale: int
    final_morale: int
    initial_enemy_soldiers: int
    final_enemy_soldiers: int
    enemy_losses: int
    boss_detected: bool = False
    boss_name: str = ""
    general_stats: list[GeneralBattleStats] = field(default_factory=list)
    log_messages: list[str] = field(default_factory=list)


@dataclass
class CombatConfig:
    auto_counter_formation: bool = True
    formation_window_seconds: int = 15  # Đổi trận ở 10~15s cuối hiệp
    attack_action_mode: str = "adaptive"  # "adaptive" | "fixed" | "default"
    fixed_action_id: int = 13  # Mặc định Hỏa tiễn nếu fixed
    target_selection_mode: str = "most_troops"  # "most_troops" | "counter_formation"
    skip_confused_enemy: bool = True
    leave_boss_last: bool = True
    auto_cleanse_confusion: bool = True
    emergency_retreat_threshold: int = 0  # % quân số để rút lui khẩn cấp (0 = tắt)
    offensive_stratagem_id: int = 0  # 0: Không dùng, 93: Phản khách, 95: Cầm tặc...
    focus_fire_ratio: int = 1  # Số tướng đánh 1 mục tiêu (1, 2, 3)


class BattleEngine:
    def __init__(self, gateway: Any, config: Optional[CombatConfig] = None):
        self.gateway = gateway
        self.config = config or CombatConfig()
        self._general_plan_cache: dict[int, dict[str, int]] = {}

    @staticmethod
    def _parse_resp_json(resp: Any) -> Optional[dict]:
        try:
            data = resp.json()
            return data if isinstance(data, dict) else None
        except ValueError:
            raw = getattr(resp, "text", "") or ""
            m = re.search(r"ret:\s*(\d+)", raw)
            if m and "{" in raw and raw.count(":") == 1:
                return {"ret": int(m.group(1))}
            try:
                fixed = re.sub(r'([{,])\s*([a-zA-Z_]\w*)\s*:', r'\1"\2":', raw)
                parsed = json.loads(fixed)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None

    def _post_gateway(
        self,
        endpoint: str,
        api_id: int,
        payload: dict[str, Any],
        referer_path: str = "/",
    ) -> Optional[dict]:
        headers = self.gateway._headers()
        headers["Referer"] = f"{self.gateway.base_url}{referer_path}"
        headers["Origin"] = self.gateway.base_url
        url = f"{self.gateway.base_url}/GateWay/{endpoint}?id={api_id}"
        max_retries = getattr(self.gateway, "max_retries", 3)
        timeout = getattr(self.gateway, "timeout", 15)
        for _ in range(max_retries):
            try:
                resp = self.gateway.session.post(
                    url, data=payload, headers=headers, timeout=timeout
                )
                if resp.status_code == 200:
                    return self._parse_resp_json(resp)
            except Exception:
                pass
        return None

    @property
    def current_user_id(self) -> int:
        """Trích xuất user_id của tài khoản hiện tại từ gateway session."""
        if hasattr(self.gateway, "user_id") and self.gateway.user_id:
            return int(self.gateway.user_id)
        session = getattr(self.gateway, "session", None)
        if session and hasattr(session, "cookies"):
            for cookie_name in ("uid", "sg_cur_uid_1"):
                val = session.cookies.get(cookie_name)
                if val and str(val).isdigit():
                    return int(val)
        return 0

    def get_campaign_status(self) -> Optional[dict]:
        """Lấy thông tin chiến dịch / Thảo Phạt từ Common.ashx?id=3."""
        r = random.random()
        url = f"{self.gateway.base_url}/GateWay/Common.ashx?id=3&{r}"
        headers = self.gateway._headers()
        headers["Referer"] = f"{self.gateway.base_url}/report"
        headers["Origin"] = self.gateway.base_url

        max_retries = getattr(self.gateway, "max_retries", 3)
        timeout = getattr(self.gateway, "timeout", 15)
        for _ in range(max_retries):
            try:
                resp = self.gateway.session.post(url, data="", headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        return None

    def get_battle_info(self, battle_id: int = 0) -> Optional[BattleState]:
        """Lấy thông tin chi tiết chiến trường từ OPT.ashx?id=24."""
        headers = self.gateway._headers()
        headers["Referer"] = f"{self.gateway.base_url}/battle/{battle_id}"
        headers["Origin"] = self.gateway.base_url

        url = f"{self.gateway.base_url}/GateWay/OPT.ashx?id=24"
        max_retries = getattr(self.gateway, "max_retries", 3)
        timeout = getattr(self.gateway, "timeout", 15)
        for _ in range(max_retries):
            try:
                resp = self.gateway.session.post(
                    url, data={"battleid": str(battle_id), "_": ""}, headers=headers, timeout=timeout
                )
                if resp.status_code == 200:
                    return BattleState.from_json(resp.json(), current_user_id=self.current_user_id)
            except Exception:
                pass
        return None

    def get_battle_tips(self, battle_id: int = 0, last_tips_id: int = 0) -> tuple[int, list[str]]:
        """Lấy nhật ký chiến sự từ OPT.ashx?id=26."""
        headers = self.gateway._headers()
        headers["Referer"] = f"{self.gateway.base_url}/battle/{battle_id}"
        headers["Origin"] = self.gateway.base_url
        url = f"{self.gateway.base_url}/GateWay/OPT.ashx?id=26"
        max_retries = getattr(self.gateway, "max_retries", 3)
        timeout = getattr(self.gateway, "timeout", 15)
        for _ in range(max_retries):
            try:
                resp = self.gateway.session.post(
                    url,
                    data={"battleid": str(battle_id), "lasttipsid": str(last_tips_id), "_": ""},
                    headers=headers,
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ret") == 0:
                        new_tips_id = data.get("last_tips_id", last_tips_id)
                        lines = []
                        for tip in data.get("tips", []):
                            if len(tip) > 2 and tip[2]:
                                text = str(tip[2]).strip()
                                if text:
                                    lines.append(text)
                        return new_tips_id, lines
            except Exception:
                pass
        return last_tips_id, []

    def change_target_attack(
        self, battle_id: int, pos_id: int, dest_pos_id: int, action: int = 0
    ) -> bool:
        """Ra lệnh tác chiến & đổi mục tiêu qua OPT.ashx?id=54."""
        headers = self.gateway._headers()
        headers["Referer"] = f"{self.gateway.base_url}/battle/{battle_id}"
        headers["Origin"] = self.gateway.base_url
        url = f"{self.gateway.base_url}/GateWay/OPT.ashx?id=54"
        payload = {
            "action": str(action),
            "battleid": str(battle_id),
            "destposid": str(dest_pos_id),
            "posid": str(pos_id),
            "_": "",
        }
        max_retries = getattr(self.gateway, "max_retries", 3)
        timeout = getattr(self.gateway, "timeout", 15)
        for _ in range(max_retries):
            try:
                resp = self.gateway.session.post(url, data=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("ret") == 0
            except Exception:
                pass
        return False

    def cast_stratagem(self, battle_id: int, pos_id: int, stratagem_id: int) -> bool:
        """Thi triển mưu kế chiến trường qua OPT.ashx?id=70."""
        headers = self.gateway._headers()
        headers["Referer"] = f"{self.gateway.base_url}/battle/{battle_id}"
        headers["Origin"] = self.gateway.base_url
        url = f"{self.gateway.base_url}/GateWay/OPT.ashx?id=70"
        payload = {
            "lBattleID": str(battle_id),
            "lDestPosID": str(pos_id),
            "lPlusFunc": str(stratagem_id),
            "_": "",
        }
        max_retries = getattr(self.gateway, "max_retries", 3)
        timeout = getattr(self.gateway, "timeout", 15)
        for _ in range(max_retries):
            try:
                resp = self.gateway.session.post(url, data=payload, headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("ret") == 0
            except Exception:
                pass
        return False

    def get_general_military_info(self, general_id: int, city_id: int = 0) -> Optional[dict]:
        """Lấy thông tin cấu hình tác chiến của võ tướng từ Common.ashx?id=12."""
        data = self._post_gateway(
            "Common.ashx",
            12,
            {"lGeneralID": str(general_id), "lCityID": str(city_id), "_": ""},
            referer_path="/",
        )
        if data and data.get("ret") == 0:
            return data
        return None

    def change_formation(
        self,
        general_id: int,
        formation_id: int,
        ratio_attack: int = 100,
        ratio_pk: int = 0,
        ratio_stra: int = 0,
        withdraw_loss: int = 0,
        withdraw_morale: int = 0,
        battle_id: int = 0,
    ) -> bool:
        """Đổi trận hình tướng ta qua OPT.ashx?id=57 (bảo toàn tỷ lệ gốc)."""
        if ratio_attack + ratio_pk + ratio_stra != 100:
            ratio_attack = 100
            ratio_pk = 0
            ratio_stra = 0

        payload = {
            "lGeneralID": str(general_id),
            "lRatioAttack": str(ratio_attack),
            "lRatioPK": str(ratio_pk),
            "lRatioStra": str(ratio_stra),
            "lBattleArray": str(formation_id),
            "lWithdrawLoss": str(withdraw_loss),
            "lWithdrawMorale": str(withdraw_morale),
            "_": "",
        }
        data = self._post_gateway(
            "OPT.ashx",
            57,
            payload,
            referer_path=f"/battle/{battle_id}",
        )
        return bool(data and data.get("ret") == 0)

    def _change_formation_preserving_plan(
        self,
        our: BattleTroop,
        formation_id: int,
        battle_id: int = 0,
    ) -> bool:
        """Đọc và cache tỷ lệ tác chiến gốc (Common.ashx?id=12) trước khi gửi OPT.ashx?id=57."""
        if our.general_id <= 0:
            return False

        plan = self._general_plan_cache.get(our.general_id)
        if plan is None:
            info = self.get_general_military_info(our.general_id, city_id=our.city_id or 0)
            if info:
                r_att = int(info.get("ratio_attack", 100) or 0)
                r_pk = int(info.get("ratio_PK", 0) or 0)
                r_stra = int(info.get("ratio_stratagem", 0) or 0)
                w_loss = int(info.get("withdraw_loss", 0) or 0)
                w_morale = int(info.get("withdraw_morale", 0) or 0)
                if r_att + r_pk + r_stra != 100:
                    r_att, r_pk, r_stra = 100, 0, 0
                plan = {
                    "ratio_attack": r_att,
                    "ratio_pk": r_pk,
                    "ratio_stra": r_stra,
                    "withdraw_loss": w_loss,
                    "withdraw_morale": w_morale,
                }
            else:
                plan = {
                    "ratio_attack": 100,
                    "ratio_pk": 0,
                    "ratio_stra": 0,
                    "withdraw_loss": 0,
                    "withdraw_morale": 0,
                }
            self._general_plan_cache[our.general_id] = plan

        return self.change_formation(
            our.general_id,
            formation_id,
            ratio_attack=plan["ratio_attack"],
            ratio_pk=plan["ratio_pk"],
            ratio_stra=plan["ratio_stra"],
            withdraw_loss=plan["withdraw_loss"],
            withdraw_morale=plan["withdraw_morale"],
            battle_id=battle_id,
        )

    def pick_counter_formation(
        self,
        our_troop: BattleTroop,
        enemy_troops: list[BattleTroop],
        leave_boss_last: bool = True,
    ) -> tuple[Optional[int], str]:
        """Tính toán trận hình tối ưu bằng Ma trận tương khắc ngũ hành toàn cục 5x5."""
        targets = [t for t in enemy_troops if not (leave_boss_last and t.is_boss)]
        if not targets:
            targets = enemy_troops

        if not targets:
            return None, "Không tìm thấy quân địch"

        # Ưu tiên 1: Địch đối diện trực tiếp (pos_enemy == pos_our + 10)
        direct_enemy = next((t for t in targets if t.position == our_troop.position + 10), None)
        if direct_enemy and direct_enemy.formation_id in COUNTER_MAP:
            chosen = COUNTER_MAP[direct_enemy.formation_id]
            desc = f"Khắc chế đối diện: {direct_enemy.general_name} [{FORMATION_NAMES.get(direct_enemy.formation_id, direct_enemy.formation_id)}]"
            return chosen, desc

        # Ma trận ngũ hành đối kháng toàn cục
        formation_scores = {fid: 0.0 for fid in range(1, 6)}
        formation_counts = {fid: 0 for fid in range(1, 6)}

        for t in targets:
            if 1 <= t.formation_id <= 5:
                formation_counts[t.formation_id] += t.soldiers
                coeff = 0.5 if t.status == 1 else 1.0  # Quân địch hỗn loạn bị giảm trọng số
                weight = t.soldiers * (t.morale / 100.0) * coeff
                for my_fid in range(1, 6):
                    formation_scores[my_fid] += ARRAY_VALUE[my_fid][t.formation_id] * weight

        best_fid = max(formation_scores, key=formation_scores.get)
        top_count = max(formation_counts.values()) if formation_counts else 0

        desc = f"Khắc chế số đông ({top_count} quân): [{FORMATION_NAMES.get(best_fid, best_fid)}]"
        return best_fid, desc

    def assign_combat_orders(
        self,
        state: BattleState,
        battle_id: int = 0,
        config: Optional[CombatConfig] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> list[str]:
        """Phân bổ mục tiêu và phương thức tấn công thông minh qua OPT.ashx?id=54."""
        cfg = config or self.config
        logs = []
        if not state.our_troops or not state.enemy_troops:
            return logs

        # Kiểm tra điều kiện chỉ còn lại duy nhất BOSS
        non_boss_enemies = [e for e in state.enemy_troops if not e.is_boss]
        only_boss_left = bool(state.boss_troops and not non_boss_enemies)

        if only_boss_left and cfg.leave_boss_last:
            # Cô lập BOSS: Chuyển toàn bộ quân ta về thế Phòng ngự (3)
            boss = state.boss_troops[0]
            for our in state.our_troops:
                if our.attack_action != 3 or our.target_id != boss.position:
                    ok = self.change_target_attack(battle_id, our.position, boss.position, action=3)
                    if ok:
                        our.attack_action = 3
                        our.target_id = boss.position
                        msg = (
                            f"      🛡️ [Bắt sống BOSS] Tướng [{our.general_name}] "
                            f"chuyển thế Phòng ngự (3) đối diện BOSS [{boss.general_name}]"
                        )
                        if on_log:
                            on_log(msg)
                        logs.append(msg)
            return logs

        # Danh sách mục tiêu hợp lệ
        valid_targets = [e for e in state.enemy_troops if not (cfg.leave_boss_last and e.is_boss)]
        if not valid_targets:
            valid_targets = state.enemy_troops

        # Sắp xếp mục tiêu: ưu tiên đạo quân chưa bị hỗn loạn, sau đó tới quân số lớn nhất
        def _target_priority(e: BattleTroop) -> tuple[int, int]:
            is_confused = 1 if (e.status == 1 and cfg.skip_confused_enemy) else 0
            return (is_confused, -e.soldiers)

        sorted_targets = sorted(valid_targets, key=_target_priority)

        # Phân bổ tướng ta vào mục tiêu
        for idx, our in enumerate(state.our_troops):
            target_idx = (idx // max(1, cfg.focus_fire_ratio)) % len(sorted_targets)
            target = sorted_targets[target_idx]

            # Xác định action
            if cfg.attack_action_mode == "adaptive":
                action = our.optimal_action_for_unit()
            elif cfg.attack_action_mode == "fixed" and cfg.fixed_action_id > 0:
                action = cfg.fixed_action_id
            else:
                action = 1  # Phổ thông

            # Gửi lệnh nếu mục tiêu hoặc phương thức thay đổi
            if our.target_id != target.position or our.attack_action != action:
                ok = self.change_target_attack(battle_id, our.position, target.position, action=action)
                if not ok and action >= 10:
                    # Tướng không có mưu sĩ đi kèm (tactician_id == 0) không dùng được chiêu 10..14 -> lùi về Tấn công phổ thông (1)
                    if self.change_target_attack(battle_id, our.position, target.position, action=1):
                        ok = True
                        action = 1
                if ok:
                    our.target_id = target.position
                    our.attack_action = action
                    action_name = ATTACK_ACTIONS.get(action, f"Chiêu {action}")
                    msg = (
                        f"      🎯 Tướng [{our.general_name}] ({our.dominant_soldier_type()}) "
                        f"ra đòn [{action_name}] nhắm vào [{target.general_name}] (vị trí {target.position})"
                    )
                    if on_log:
                        on_log(msg)
                    logs.append(msg)

        return logs

    def execute_stratagems(
        self,
        state: BattleState,
        battle_id: int = 0,
        config: Optional[CombatConfig] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> list[str]:
        """Phân tầng thi triển mưu lược chiến trường qua OPT.ashx?id=70."""
        cfg = config or self.config
        logs = []
        for our in state.our_troops:
            # 1. Phản xạ tự giải Hỗn loạn (mưu kế 96)
            if cfg.auto_cleanse_confusion and our.status == 1:
                ok = self.cast_stratagem(battle_id, our.position, 96)
                if ok:
                    our.status = 0
                    msg = (
                        f"      ✨ Tướng [{our.general_name}] tự động thi triển mưu kế "
                        f"[Hủy bỏ trạng thái (96)], giải phóng Hỗn loạn!"
                    )
                    if on_log:
                        on_log(msg)
                    logs.append(msg)
                continue

            # 2. Rút lui khẩn cấp (mưu kế 92) khi quân số < ngưỡng an toàn
            if cfg.emergency_retreat_threshold > 0 and our.initial_soldiers > 0:
                health_pct = (our.soldiers / our.initial_soldiers) * 100
                if health_pct < cfg.emergency_retreat_threshold:
                    ok = self.cast_stratagem(battle_id, our.position, 92)
                    if ok:
                        msg = (
                            f"      🚨 Tướng [{our.general_name}] quân số rơi xuống {health_pct:.1f}% "
                            f"(< {cfg.emergency_retreat_threshold}%), kích hoạt [Kim thiền thoát xác (92)] rút lui an toàn!"
                        )
                        if on_log:
                            on_log(msg)
                        logs.append(msg)
                    continue

            # 3. Mưu kế chủ động ở hiệp 1 (93, 94, 95...)
            if state.bout == 1 and cfg.offensive_stratagem_id > 0:
                s_name = STRATAGEMS.get(cfg.offensive_stratagem_id, f"Mưu kế {cfg.offensive_stratagem_id}")
                ok = self.cast_stratagem(battle_id, our.position, cfg.offensive_stratagem_id)
                if ok:
                    msg = f"      📜 [Hiệp 1] Tướng [{our.general_name}] chủ động thi triển mưu kế [{s_name}]!"
                    if on_log:
                        on_log(msg)
                    logs.append(msg)

        return logs

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def inspect_world_movements(
        self,
        generals: list[int],
        origin_id: int = 0,
    ) -> tuple[Optional[int], Optional[BattleState], Optional[int]]:
        """Kiểm tra quân đội thế giới qua Common.ashx?id=40 và Common.ashx?id=4.

        Trả về bộ 3:
        - active_battle_id: Mã chiến trường thực tế (nếu tướng trong danh sách đang giao chiến).
        - prefetched_state: Trạng thái chiến trường lấy sẵn (nếu đã gọi OPT.ashx?id=24 để xác minh).
        - outbound_march_left: Số giây còn lại của đạo quân đang hành quân tới mục tiêu (goto), hoặc None.
        """
        wanted = {int(g) for g in generals if g}
        tids_to_check = [origin_id or 0]
        if origin_id and origin_id != 0:
            tids_to_check.append(0)

        march_left: Optional[int] = None

        for idx, tid in enumerate(tids_to_check):
            resp40 = self._post_gateway(
                "Common.ashx", 40, {"tid": str(tid), "_": ""}, referer_path="/"
            )
            if not resp40 or resp40.get("ret", 0) != 0:
                continue
            if idx == 0 and "battle" not in resp40 and "goto" not in resp40:
                # Server mock đơn giản không mô phỏng Common.ashx?id=40 -> thoát ngay
                return None, None, None

            battles = resp40.get("battle") or []
            for b in battles:
                if not isinstance(b, list) or not b:
                    continue
                raw_bid = self._safe_int(b[0])
                if raw_bid <= 0:
                    continue

                c4 = self._post_gateway(
                    "Common.ashx", 4, {"lBattleID": str(raw_bid), "_": ""}, referer_path="/"
                )
                real_bid = (
                    self._safe_int(c4.get("battle_id"), raw_bid)
                    if isinstance(c4, dict) and c4.get("battle_id")
                    else raw_bid
                )

                myside = c4.get("myside") if isinstance(c4, dict) else None
                if isinstance(myside, list) and myside:
                    matched = False
                    for row in myside:
                        if not isinstance(row, list):
                            continue
                        row_gids: set[int] = set()
                        if len(row) > 13:
                            gid13 = self._safe_int(row[13])
                            if gid13 > 0:
                                row_gids.add(gid13)
                        if len(row) > 4 and isinstance(row[1], str):
                            gid4 = self._safe_int(row[4])
                            if gid4 > 0:
                                row_gids.add(gid4)
                        if not wanted or (row_gids & wanted):
                            matched = True
                            break
                    if matched:
                        return real_bid, None, None
                    continue

                # Fallback khi myside trống: kiểm tra trực tiếp OPT.ashx?id=24
                st = self.get_battle_info(real_bid)
                if st and not st.is_ended:
                    if not wanted or any(t.general_id in wanted for t in st.our_troops):
                        return real_bid, st, None

            gotos = resp40.get("goto") or []
            for p in gotos:
                if not isinstance(p, list) or len(p) < 8:
                    continue
                # Trong barracks_ot.js: p[1] == 12 là đạo quân đang triệu hồi quay về (召回)
                if len(p) >= 14 and self._safe_int(p[1]) == 12:
                    continue

                gen_pairs = None
                if len(p) > 8 and isinstance(p[8], list):
                    gen_pairs = p[8]
                elif isinstance(p[7], list):
                    gen_pairs = p[7]

                march_gids: set[int] = set()
                if gen_pairs is not None:
                    for pair in gen_pairs:
                        if isinstance(pair, list) and pair:
                            gid = self._safe_int(pair[0])
                            if gid > 0:
                                march_gids.add(gid)

                if not wanted or (march_gids & wanted):
                    rem = (
                        self._safe_int(p[13], 3)
                        if len(p) > 13
                        else (self._safe_int(p[12], 3) if len(p) > 12 else 3)
                    )
                    rem = max(0, rem)
                    if march_left is None or rem < march_left:
                        march_left = rem

            if march_left is not None:
                break

        return None, None, march_left

    def wait_and_track_world_battle(
        self,
        generals: list[int],
        origin_id: int = 0,
        on_log: Optional[Callable[[str], None]] = None,
        on_boss_alert: Optional[Callable[[str], None]] = None,
        on_battle_found: Optional[Callable[[int], None]] = None,
        on_state: Optional[Callable[[BattleState], None]] = None,
        stop_event: Optional[Any] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        config: Optional[CombatConfig] = None,
        max_wait_polls: int = 120,
    ) -> Optional[BattleReport]:
        """Tự động phát hiện chiến trường thế giới (hoặc chờ hành quân goto tới nơi) rồi vào điều khiển."""
        cfg = config or self.config
        polls = 0
        while polls < max_wait_polls:
            if stop_event and stop_event.is_set():
                return None

            bid, prefetched_state, march_left = self.inspect_world_movements(
                generals=generals, origin_id=origin_id
            )
            if bid is not None:
                if on_battle_found:
                    on_battle_found(bid)
                if on_log:
                    on_log(
                        f"⚔️ Phát hiện chiến trường đang diễn ra (ID: {bid}), tự động vào chỉ huy & chỉnh trận hình..."
                    )
                return self.track_battle(
                    battle_id=bid,
                    on_log=on_log,
                    on_boss_alert=on_boss_alert,
                    auto_counter=cfg.auto_counter_formation,
                    leave_boss_last=cfg.leave_boss_last,
                    stop_event=stop_event,
                    sleep_fn=sleep_fn,
                    config=cfg,
                    initial_state=prefetched_state,
                    on_state=on_state,
                )

            if march_left is not None:
                if on_log:
                    on_log(f"⏳ Quân ta đang hành quân tới mục tiêu (còn ~{march_left}s)...")
                sleep_fn(min(5.0, max(1.0, float(march_left))))
                polls += 1
                continue

            return None
        return None

    def track_battle(
        self,
        battle_id: int = 0,
        on_log: Optional[Callable[[str], None]] = None,
        on_boss_alert: Optional[Callable[[str], None]] = None,
        auto_counter: bool = True,
        leave_boss_last: bool = True,
        max_bouts: int = 30,
        stop_event: Optional[Any] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        config: Optional[CombatConfig] = None,
        initial_state: Optional[BattleState] = None,
        on_state: Optional[Callable[[BattleState], None]] = None,
    ) -> BattleReport:
        """Theo dõi diễn biến trận đánh qua từng hiệp và chỉ huy tác chiến toàn diện."""
        cfg = config or self.config
        cfg.auto_counter_formation = auto_counter
        cfg.leave_boss_last = leave_boss_last

        initial_our_soldiers = 0
        initial_enemy_soldiers = 0
        initial_soldiers_map: dict[int, int] = {}
        prev_soldiers_map: dict[int, int] = {}
        last_soldiers_map: dict[int, int] = {}
        general_names_map: dict[int, str] = {}
        last_formation_map: dict[int, int] = {}

        initial_morale: dict[int, int] = {}
        prev_morale: dict[int, int] = {}
        last_morale: dict[int, int] = {}

        last_our_soldiers = 0
        last_enemy_soldiers = 0
        bouts_count = 0
        site_name = ""
        boss_detected = False
        boss_name = ""
        last_tips_id = 0
        last_processed_bout = 0
        transition_retries = 0
        initial_check_attempts = 0
        logs: list[str] = []
        formation_switched_this_bout = False

        def _log(msg: str):
            if on_log:
                on_log(msg)
            logs.append(msg)

        bouts_attempted = 0
        pending_initial_state = initial_state
        while bouts_attempted < max_bouts:
            if stop_event and stop_event.is_set():
                break

            if pending_initial_state is not None:
                state = pending_initial_state
                pending_initial_state = None
            else:
                state = self.get_battle_info(battle_id)
            if state is None or state.is_ended:
                if battle_id == 0 and bouts_count == 0 and initial_check_attempts < 10:
                    campaign = self.get_campaign_status()
                    if campaign:
                        c_status = campaign.get("status", 0)
                        curr = campaign.get("current", [])
                        countdown = curr[1] if len(curr) > 1 else 0
                        if c_status == 1:
                            _log(f"      ⏳ Quân ta đang di chuyển tới chiến trường (còn {countdown}s)...")
                            sleep_fn(min(5.0, max(1.0, float(countdown))))
                            initial_check_attempts += 1
                            continue
                        elif c_status == 2:
                            _log("      ⏳ Đang kết nối vào chiến trường...")
                            sleep_fn(2.0)
                            initial_check_attempts += 1
                            continue
                elif battle_id == 0 and bouts_count > 0 and transition_retries < 3:
                    campaign = self.get_campaign_status()
                    if campaign and campaign.get("status") == 2:
                        transition_retries += 1
                        sleep_fn(2.0)
                        continue
                break

            # Khi phát hiện hiệp đấu mới
            if state.bout != last_processed_bout:
                bouts_attempted += 1
                bouts_count = state.bout
                site_name = state.site or site_name
                last_processed_bout = state.bout
                transition_retries = 0
                formation_switched_this_bout = False

                curr_our_soldiers = sum(t.soldiers for t in state.our_troops)
                curr_enemy_soldiers = sum(t.soldiers for t in state.enemy_troops)

                if initial_our_soldiers == 0 and curr_our_soldiers > 0:
                    initial_our_soldiers = sum(
                        t.initial_soldiers or t.soldiers for t in state.our_troops
                    )
                    initial_enemy_soldiers = sum(
                        t.initial_soldiers or t.soldiers for t in state.enemy_troops
                    )
                    for t in state.our_troops:
                        init_s = t.initial_soldiers or t.soldiers
                        initial_soldiers_map[t.general_id] = init_s
                        prev_soldiers_map[t.general_id] = init_s
                        initial_morale[t.general_id] = t.morale
                        prev_morale[t.general_id] = t.morale

                last_our_soldiers = curr_our_soldiers
                last_enemy_soldiers = curr_enemy_soldiers

                for t in state.our_troops:
                    last_soldiers_map[t.general_id] = t.soldiers
                    last_morale[t.general_id] = t.morale
                    general_names_map[t.general_id] = t.general_name
                    last_formation_map[t.general_id] = t.formation_id

                # Phát hiện BOSS
                if state.boss_troops and not boss_detected:
                    boss_detected = True
                    boss = state.boss_troops[0]
                    boss_name = boss.general_name
                    alert_msg = (
                        f"🐉 PHÁT HIỆN BOSS [{boss_name}] tại vị trí {boss.position}! "
                        f"Đang giữ lại để người chơi vào bắt sống!"
                    )
                    if on_boss_alert:
                        on_boss_alert(alert_msg)
                    _log(f"   {alert_msg}")

                _log(f"   ⚔️ [Chiến trường - Hiệp {state.bout}]")

                # 1. Thực thi Mưu lược chiến trường (OPT 70)
                self.execute_stratagems(state, battle_id, cfg, _log)

                # 2. Phân bổ mục tiêu và phương án tấn công (OPT 54)
                self.assign_combat_orders(state, battle_id, cfg, _log)

                if on_state:
                    on_state(state)

                # 3. Ghi log diễn biến hiệp đấu
                enemy_killed = max(0, initial_enemy_soldiers - curr_enemy_soldiers)
                gens_detail = []
                for t in state.our_troops:
                    base_s = initial_soldiers_map.get(t.general_id, t.soldiers)
                    loss = max(0, base_s - t.soldiers)
                    round_loss = max(
                        0, prev_soldiers_map.get(t.general_id, t.soldiers) - t.soldiers
                    )
                    init_m = initial_morale.get(t.general_id, t.morale)
                    m_diff = t.morale - init_m
                    m_diff_str = f" ({m_diff:+d})" if m_diff != 0 else ""
                    loss_str = f"-{loss}"
                    if round_loss > 0:
                        loss_str += f" (hiệp này: -{round_loss})"
                    fname = FORMATION_NAMES.get(t.formation_id, f"Trận {t.formation_id}")
                    status_str = " ⚠️[Hỗn loạn]" if t.status == 1 else ""
                    gens_detail.append(
                        f"[{t.general_name} ({fname}){status_str}]: {t.soldiers}/{base_s} quân (Thiệt hại: {loss_str}) | Sĩ khí: {t.morale}/100{m_diff_str}"
                    )

                for g_line in gens_detail:
                    _log(f"      🛡️ Phe ta: {g_line}")

                enemy_detail = []
                for e in state.enemy_troops:
                    efname = FORMATION_NAMES.get(e.formation_id, f"Trận {e.formation_id}")
                    boss_tag = " 👑[BOSS]" if e.is_boss else ""
                    confused_tag = " ⚠️[Hỗn loạn]" if e.status == 1 else ""
                    enemy_detail.append(
                        f"{e.general_name}{boss_tag}{confused_tag} ({e.soldiers} quân, {efname}, Sĩ khí: {e.morale})"
                    )
                enemy_str = ", ".join(enemy_detail)
                _log(
                    f"      🎯 Phe địch: Còn {curr_enemy_soldiers}/{initial_enemy_soldiers} quân "
                    f"(Đã tiêu diệt: {enemy_killed} quân) | Đội hình: {enemy_str}"
                )

                for t in state.our_troops:
                    prev_soldiers_map[t.general_id] = t.soldiers
                    prev_morale[t.general_id] = t.morale

            # Lấy nhật ký chiến sự
            last_tips_id, new_tips = self.get_battle_tips(battle_id, last_tips_id)
            for tip_text in new_tips:
                _log(f"      📜 {tip_text}")

            wait_time = state.bout_left if (state.bout_left and 0 < state.bout_left < 180) else 5
            _log(f"      ⏳ Đếm ngược kết thúc hiệp {state.bout}: còn ~{wait_time}s...")

            def _try_switch_formations(curr_left: int) -> None:
                nonlocal formation_switched_this_bout
                if (
                    cfg.auto_counter_formation
                    and not formation_switched_this_bout
                    and curr_left <= cfg.formation_window_seconds
                ):
                    formation_switched_this_bout = True
                    for our in state.our_troops:
                        opt_fid, desc = self.pick_counter_formation(
                            our, state.enemy_troops, leave_boss_last=cfg.leave_boss_last
                        )
                        if opt_fid and opt_fid != our.formation_id:
                            ok = self._change_formation_preserving_plan(
                                our, opt_fid, battle_id=battle_id
                            )
                            if ok:
                                _log(
                                    f"   🔄 [Cửa sổ cuối hiệp {state.bout} (~{curr_left}s)] Tướng [{our.general_name}] "
                                    f"đổi sang {FORMATION_NAMES.get(opt_fid, opt_fid)} ({desc})"
                                )
                                our.formation_id = opt_fid
                                last_formation_map[our.general_id] = opt_fid
                    if on_state:
                        on_state(state)

            # Nếu vào trận khi thời gian còn lại đã nằm trong cửa sổ cuối hiệp -> đổi trận ngay lập tức
            _try_switch_formations(wait_time)

            # Vòng lặp đếm ngược và kiểm tra Cửa Sổ Đổi Trận Cuối Hiệp
            elapsed = 0.0
            step = 3.0 if wait_time > 10 else 1.5
            while elapsed < wait_time:
                if stop_event and stop_event.is_set():
                    break
                sleep_sec = min(step, wait_time - elapsed)
                sleep_fn(sleep_sec)
                elapsed += sleep_sec

                curr_left = max(0, wait_time - int(elapsed))

                # Đổi trận hình ở cửa sổ cuối hiệp (bout_left <= formation_window_seconds)
                _try_switch_formations(curr_left)

                if elapsed < wait_time:
                    last_tips_id, new_tips = self.get_battle_tips(battle_id, last_tips_id)
                    for tip_text in new_tips:
                        _log(f"      📜 {tip_text}")

        # Hoàn tất trận đấu
        last_tips_id, new_tips = self.get_battle_tips(battle_id, last_tips_id)
        for tip_text in new_tips:
            _log(f"      📜 {tip_text}")

        is_victory = (last_our_soldiers > 0 and last_enemy_soldiers == 0) or (
            bouts_count > 0 and last_our_soldiers > 0
        )
        if bouts_count > 0 and last_our_soldiers > 0:
            last_enemy_soldiers = 0
            total_enemy_killed = initial_enemy_soldiers
        else:
            total_enemy_killed = max(0, initial_enemy_soldiers - last_enemy_soldiers)

        total_our_loss = max(0, initial_our_soldiers - last_our_soldiers)
        loss_pct = (
            round((total_our_loss / initial_our_soldiers * 100), 1)
            if initial_our_soldiers > 0
            else 0
        )
        kill_pct = (
            round((total_enemy_killed / initial_enemy_soldiers * 100), 1)
            if initial_enemy_soldiers > 0
            else 100
        )

        final_morale = (
            sum(last_morale.values()) // max(1, len(last_morale)) if last_morale else 0
        )
        init_morale = (
            sum(initial_morale.values()) // max(1, len(initial_morale)) if initial_morale else 0
        )
        morale_diff = final_morale - init_morale
        morale_diff_str = f"{morale_diff:+d}" if morale_diff != 0 else "0"

        gen_stats_list: list[GeneralBattleStats] = []
        for gid, init_s in initial_soldiers_map.items():
            fin_s = last_soldiers_map.get(gid, init_s)
            loss_s = max(0, init_s - fin_s)
            init_m = initial_morale.get(gid, 100)
            fin_m = last_morale.get(gid, init_m)
            loss_m = init_m - fin_m
            gname = general_names_map.get(gid, str(gid))
            fname = FORMATION_NAMES.get(last_formation_map.get(gid, 0), "Chưa rõ")
            gen_stats_list.append(
                GeneralBattleStats(
                    general_id=gid,
                    general_name=gname,
                    initial_soldiers=init_s,
                    final_soldiers=fin_s,
                    loss_soldiers=loss_s,
                    initial_morale=init_m,
                    final_morale=fin_m,
                    loss_morale=loss_m,
                    formation_name=fname,
                )
            )

        if bouts_count > 0:
            vic_title = (
                "🏆 [KẾT QUẢ CHIẾN ĐẤU] CHIẾN THẮNG!"
                if is_victory
                else "🏁 [KẾT QUẢ CHIẾN ĐẤU] TRẬN ĐẤU KẾT THÚC"
            )
            _log("   ==================================================")
            _log(f"   {vic_title} (Sau {bouts_count} hiệp giao chiến)")
            _log("   🛡️ THIỆT HẠI QUÂN TA:")
            _log(
                f"      - Tổng quân số: {last_our_soldiers}/{initial_our_soldiers} quân "
                f"(Thiệt hại: -{total_our_loss} quân, -{loss_pct}%)"
            )
            _log(
                f"      - Sĩ khí trung bình: {final_morale}/100 "
                f"(Ban đầu: {init_morale}/100, Biến động: {morale_diff_str})"
            )
            for gs in gen_stats_list:
                g_loss_pct = (
                    round((gs.loss_soldiers / gs.initial_soldiers * 100), 1)
                    if gs.initial_soldiers > 0
                    else 0
                )
                _log(
                    f"      👉 Tướng [{gs.general_name}]: Quân số {gs.final_soldiers}/{gs.initial_soldiers} "
                    f"(Thiệt hại: -{gs.loss_soldiers} quân, -{g_loss_pct}%) | Sĩ khí: {gs.final_morale}/100 (Giảm: -{gs.loss_morale})"
                )
            _log("   💀 KẾT QUẢ TIÊU DIỆT ĐỊCH:")
            _log(
                f"      - Đã tiêu diệt: {total_enemy_killed}/{initial_enemy_soldiers} quân ({kill_pct}%) "
                f"| Địch còn sống: {last_enemy_soldiers} quân"
            )
            if boss_detected:
                boss_status = (
                    "ĐÃ TIÊU DIỆT"
                    if last_enemy_soldiers == 0
                    else "CÒN SỐNG (SẴN SÀNG BẮT SỐNG)"
                )
                _log(f"   🐉 BOSS CHIẾN TRƯỜNG: [{boss_name}] -> Trạng thái: {boss_status}")
            _log("   ==================================================")

        return BattleReport(
            battle_id=battle_id,
            site=site_name,
            total_bouts=bouts_count,
            is_victory=is_victory,
            initial_our_soldiers=initial_our_soldiers,
            final_our_soldiers=last_our_soldiers,
            our_losses=total_our_loss,
            initial_morale=init_morale,
            final_morale=final_morale,
            initial_enemy_soldiers=initial_enemy_soldiers,
            final_enemy_soldiers=last_enemy_soldiers,
            enemy_losses=total_enemy_killed,
            boss_detected=boss_detected,
            boss_name=boss_name,
            general_stats=gen_stats_list,
            log_messages=logs,
        )


# Alias tương thích ngược
BattleController = BattleEngine
