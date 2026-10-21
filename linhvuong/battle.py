"""Module quản lý và điều khiển chiến trường (BattleController).

Hỗ trợ:
- Lấy thông tin chiến trường qua OPT.ashx?id=24.
- Phân tích đội hình ta và địch, phát hiện BOSS (để bắt sống).
- Tự động tính toán và đổi trận hình khắc chế có lợi thế qua OPT.ashx?id=57.
- Ghi nhật ký chiến trường từng hiệp: quân số thiệt hại, sĩ khí tướng, quân địch tiêu diệt.
- Tổng kết chiến quả sau trận đấu.
"""

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

FORMATION_NAMES = {
    1: "Trùy hình (锥形)",
    2: "Câu hình (钩形)",
    3: "Kê hình (箕形)",
    4: "Hạc dực (鹤翼)",
    5: "Ngư lân (鱼鳞)",
}

# Quy luật ngũ hành trận pháp Linh Vương:
# 1-Trùy khắc 3-Kê, 3-Kê khắc 5-Ngư, 5-Ngư khắc 2-Câu, 2-Câu khắc 4-Hạc, 4-Hạc khắc 1-Trùy
COUNTER_MAP = {
    3: 1,  # Địch là Kê hình (3) -> Ta dùng Trùy hình (1)
    5: 3,  # Địch là Ngư lân (5) -> Ta dùng Kê hình (3)
    2: 5,  # Địch là Câu hình (2) -> Ta dùng Ngư lân (5)
    4: 2,  # Địch là Hạc dực (4) -> Ta dùng Câu hình (2)
    1: 4,  # Địch là Trùy hình (1) -> Ta dùng Hạc dực (4)
}

KNOWN_BOSS_NAMES = {"马超", "张飞", "黄忠", "关羽", "赵云", "宝箱"}


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
        soldiers = raw[11] if len(raw) > 11 else 0
        init_soldiers = raw[13] if len(raw) > 13 else 0
        flag = raw[19] if len(raw) > 19 else 0

        is_boss = (
            pos == 19
            or bool(flag & 0x30)
            or any(bname in gname for bname in KNOWN_BOSS_NAMES)
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
        )


@dataclass
class BattleState:
    ret: int
    site: str
    map_id: int
    bout: int
    bout_left: int
    attack_total: int
    defend_total: int
    our_troops: list[BattleTroop] = field(default_factory=list)
    enemy_troops: list[BattleTroop] = field(default_factory=list)
    boss_troops: list[BattleTroop] = field(default_factory=list)
    is_ended: bool = False

    @classmethod
    def from_json(cls, data: dict) -> "BattleState":
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
                is_ended=True,
            )

        our_troops = []
        enemy_troops = []
        boss_troops = []

        for raw_t in data.get("troops", []):
            troop = BattleTroop.from_raw(raw_t)
            if troop.position <= 10:
                our_troops.append(troop)
            else:
                enemy_troops.append(troop)
                if troop.is_boss:
                    boss_troops.append(troop)

        is_ended = (ret != 0) or len(our_troops) == 0 or len(enemy_troops) == 0
        return cls(
            ret=ret,
            site=data.get("site", ""),
            map_id=data.get("mapid", 0),
            bout=data.get("bout", 1),
            bout_left=data.get("bout_left", 0),
            attack_total=data.get("attack_total", 0),
            defend_total=data.get("defend_total", 0),
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


class BattleController:
    def __init__(self, gateway: Any):
        self.gateway = gateway

    def get_campaign_status(self) -> Optional[dict]:
        """Lấy thông tin chiến dịch / Thảo Phạt từ Common.ashx?id=3.

        Cấu trúc phản hồi:
        {
            "ret": 0,
            "task": [[task_id, task_name, counts, max_counts, travel_time, max_generals]],
            "status": 0 (rảnh/kết thúc) | 1 (hành quân) | 2 (trong chiến trường),
            "current": [task_id, countdown_left, [[general_id, name, ...]]]
        }
        """
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
                    return BattleState.from_json(resp.json())
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

    def change_formation(self, general_id: int, formation_id: int) -> bool:
        """Đổi trận hình tướng ta qua OPT.ashx?id=57."""
        payload = {
            "lGeneralID": str(general_id),
            "lRatioAttack": "0",
            "lRatioPK": "100",
            "lRatioStra": "0",
            "lBattleArray": str(formation_id),
            "lWithdrawLoss": "0",
            "lWithdrawMorale": "0",
            "_": "",
        }
        headers = self.gateway._headers()
        headers["Referer"] = f"{self.gateway.base_url}/battle/0"
        headers["Origin"] = self.gateway.base_url
        url = f"{self.gateway.base_url}/GateWay/OPT.ashx?id=57"
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

    def pick_counter_formation(
        self,
        our_troop: BattleTroop,
        enemy_troops: list[BattleTroop],
        leave_boss_last: bool = True,
    ) -> tuple[Optional[int], str]:
        """Tính toán trận hình tối ưu để khắc chế quân địch.

        Thứ tự ưu tiên:
        1. Bỏ qua BOSS nếu leave_boss_last=True.
        2. Khắc chế đạo lính địch đối diện trực diện (pos_enemy == pos_our + 10).
        3. Khắc chế trận hình có quân số đông nhất của phe địch.
        """
        targets = [t for t in enemy_troops if not (leave_boss_last and t.is_boss)]
        if not targets:
            # Nếu chỉ còn BOSS thì mới khắc chế BOSS
            targets = enemy_troops

        if not targets:
            return None, "Không tìm thấy quân địch"

        # Ưu tiên 1: Địch đối diện trực tiếp
        direct_enemy = next((t for t in targets if t.position == our_troop.position + 10), None)
        if direct_enemy and direct_enemy.formation_id in COUNTER_MAP:
            chosen = COUNTER_MAP[direct_enemy.formation_id]
            desc = f"Khắc chế đối diện: {direct_enemy.general_name} [{FORMATION_NAMES.get(direct_enemy.formation_id, direct_enemy.formation_id)}]"
            return chosen, desc

        # Ưu tiên 2: Trận hình có tổng quân số địch lớn nhất
        formation_troop_counts: dict[int, int] = {}
        for t in targets:
            if t.formation_id in COUNTER_MAP:
                formation_troop_counts[t.formation_id] = (
                    formation_troop_counts.get(t.formation_id, 0) + t.soldiers
                )

        if formation_troop_counts:
            sorted_formations = sorted(
                formation_troop_counts.items(), key=lambda x: x[1], reverse=True
            )
            top_fid, count = sorted_formations[0]
            chosen = COUNTER_MAP[top_fid]
            desc = f"Khắc chế số đông ({count} quân): [{FORMATION_NAMES.get(top_fid, top_fid)}]"
            return chosen, desc

        return None, "Không xác định được trận hình địch hợp lệ"

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
    ) -> BattleReport:
        """Theo dõi diễn biến trận đánh qua từng hiệp và ghi nhật ký chi tiết."""
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

        def _log(msg: str):
            if on_log:
                on_log(msg)
            logs.append(msg)

        bouts_attempted = 0
        while bouts_attempted < max_bouts:
            if stop_event and stop_event.is_set():
                break

            state = self.get_battle_info(battle_id)
            if state is None or state.is_ended:
                # Nếu chưa bắt đầu hiệp nào và đang khởi tạo hoặc hành quân
                if bouts_count == 0 and initial_check_attempts < 10:
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
                elif bouts_count > 0 and transition_retries < 3:
                    # Kiểm tra lại qua Common.ashx?id=3 xem có phải đang chuyển hiệp hay đã kết thúc thật
                    campaign = self.get_campaign_status()
                    if campaign and campaign.get("status") == 2:
                        transition_retries += 1
                        sleep_fn(2.0)
                        continue
                # Trận chiến đã thực sự kết thúc!
                break

            # Khi phát hiện hiệp đấu mới
            if state.bout != last_processed_bout:
                bouts_attempted += 1
                bouts_count = state.bout
                site_name = state.site or site_name
                last_processed_bout = state.bout
                transition_retries = 0

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

                # Kiểm tra BOSS
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

                # Đổi trận hình khắc chế
                if auto_counter:
                    for our in state.our_troops:
                        opt_fid, desc = self.pick_counter_formation(
                            our, state.enemy_troops, leave_boss_last=leave_boss_last
                        )
                        if opt_fid and opt_fid != our.formation_id:
                            ok = self.change_formation(our.general_id, opt_fid)
                            if ok:
                                _log(
                                    f"   🔄 [Hiệp {state.bout}] Tướng [{our.general_name}] "
                                    f"đổi sang {FORMATION_NAMES.get(opt_fid, opt_fid)} ({desc})"
                                )
                                last_formation_map[our.general_id] = opt_fid

                # Ghi log diễn biến hiệp đấu
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
                    gens_detail.append(
                        f"[{t.general_name} ({fname})]: {t.soldiers}/{base_s} quân (Thiệt hại: {loss_str}) | Sĩ khí: {t.morale}/100{m_diff_str}"
                    )

                _log(f"   ⚔️ [Chiến trường - Hiệp {state.bout}]")
                for g_line in gens_detail:
                    _log(f"      🛡️ Phe ta: {g_line}")

                # Phe địch
                enemy_detail = []
                for e in state.enemy_troops:
                    efname = FORMATION_NAMES.get(e.formation_id, f"Trận {e.formation_id}")
                    boss_tag = " 👑[BOSS]" if e.is_boss else ""
                    enemy_detail.append(
                        f"{e.general_name}{boss_tag} ({e.soldiers} quân, {efname}, Sĩ khí: {e.morale})"
                    )
                enemy_str = ", ".join(enemy_detail)
                _log(
                    f"      🎯 Phe địch: Còn {curr_enemy_soldiers}/{initial_enemy_soldiers} quân "
                    f"(Đã tiêu diệt: {enemy_killed} quân) | Đội hình: {enemy_str}"
                )

                # Cập nhật số quân & sĩ khí hiệp trước
                for t in state.our_troops:
                    prev_soldiers_map[t.general_id] = t.soldiers
                    prev_morale[t.general_id] = t.morale

            # Lấy nhật ký giao chiến chi tiết nếu có
            last_tips_id, new_tips = self.get_battle_tips(battle_id, last_tips_id)
            for tip_text in new_tips:
                _log(f"      📜 {tip_text}")

            # Đợi đến khi hết hiệp đấu
            wait_time = state.bout_left if (state.bout_left and 0 < state.bout_left < 180) else 5
            _log(f"      ⏳ Đếm ngược kết thúc hiệp {state.bout}: còn ~{wait_time}s...")

            # Ngủ theo từng bước nhỏ để phản hồi stop_event
            elapsed = 0.0
            step = 5.0 if wait_time > 10 else 2.0
            while elapsed < wait_time:
                if stop_event and stop_event.is_set():
                    break
                sleep_sec = min(step, wait_time - elapsed)
                sleep_fn(sleep_sec)
                elapsed += sleep_sec

                if elapsed < wait_time:
                    last_tips_id, new_tips = self.get_battle_tips(battle_id, last_tips_id)
                    for tip_text in new_tips:
                        _log(f"      📜 {tip_text}")

        # Lấy các tips cuối cùng
        last_tips_id, new_tips = self.get_battle_tips(battle_id, last_tips_id)
        for tip_text in new_tips:
            _log(f"      📜 {tip_text}")

        # Kết thúc trận đánh -> Tổng kết
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

        # Tổng hợp chỉ số từng tướng
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
