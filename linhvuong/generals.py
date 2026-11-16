"""Dịch vụ quản lý Văn quan & Võ tướng: Ban thưởng, Thiết lập Mưu sĩ và Tự động Trang bị."""

from dataclasses import dataclass, field, replace
import threading
from typing import Any, Callable, Optional

from .gateway import GatewayClient
from .roster import General, Roster, fetch_roster
from .troops import ERROR_MESSAGES as TROOP_ERROR_MESSAGES

TACTICIAN_ERROR_MESSAGES = {
    **TROOP_ERROR_MESSAGES,
    10020: "Văn quan không tồn tại",
    10021: "Võ tướng không tồn tại",
    10022: "Văn quan đang bận",
    10023: "Không cùng thành",
    10024: "Võ tướng đã có mưu sĩ",
}

MODE_BY_LEVEL = "by_level"
MODE_BY_NAME = "by_name"
MODE_SEQUENTIAL = "sequential"
MODE_REMOVE = "remove"
VALID_TACTICIAN_MODES = (MODE_BY_LEVEL, MODE_BY_NAME, MODE_SEQUENTIAL, MODE_REMOVE)

EQUIP_TYPES: tuple[int, ...] = (1, 2, 3, 4)
EQUIP_SLOT_KEYS: dict[int, str] = {1: "helm", 2: "weapon", 3: "armor", 4: "horse"}
EQUIP_SLOT_NAMES: dict[int, str] = {1: "Mũ", 2: "Vũ khí", 3: "Giáp", 4: "Thú cưỡi"}
EQUIP_MODE_ASSIGN = "assign"
EQUIP_MODE_UNEQUIP = "unequip"
VALID_EQUIP_MODES = (EQUIP_MODE_ASSIGN, EQUIP_MODE_UNEQUIP)
RET_EQUIP_FEMALE_OR_BARBARIAN_ONLY = 301
EQUIP_ERROR_MESSAGES = {
    **TROOP_ERROR_MESSAGES,
    RET_EQUIP_FEMALE_OR_BARBARIAN_ONLY: "Trang bị chỉ dành cho nữ danh tướng hoặc tướng Man",
}

ITEM_NAME_MAPPING: dict[int, str] = {
    # Mũ Võ (11xx)
    1101: "防御头盔",
    1102: "青铜头盔",
    1103: "光荣头盔",
    1104: "精铁头盔",
    1105: "黄铜头盔",
    1106: "镏金头盔",
    1107: "羽盔",
    1108: "镔铁盔",
    1109: "将军盔",
    1110: "虎头盔",
    1111: "力神头盔",
    1112: "斗神之盔",
    1113: "兰丸之盔",
    1114: "鲜卑头盔",
    1115: "乌桓头盔",
    1116: "山越头盔",
    1117: "羌氐头盔",
    1118: "南蛮藤盔",
    1119: "匈奴头盔",
    1120: "战神罩帽",
    1121: "霸王狮心盔",
    1122: "白发银盔",
    1123: "武曲星头盔",
    1124: "圣诞头盔",
    1125: "子龙盔",
    1126: "刚侯盔",
    1127: "战舞华冠",
    1128: "王者之刚毅",
    1129: "诸侯战盔",
    1130: "勇者盔",
    1131: "虎威盔",
    1132: "亮银蟠龙盔",
    1133: "武圣战盔",
    1134: "束发金冠",
    1135: "赤金吞天盔",
    1136: "斗神战盔",
    1137: "白银狮盔",
    1138: "凤翎银盔",
    1139: "蝶舞彩冠",
    1180: "良将之慧",
    1181: "虎骑银盔",
    1182: "虎痴冠",
    1183: "草帽",
    1184: "君子之德",
    1185: "英雄面具",
    # Mũ Văn (12xx)
    1201: "粗布头巾",
    1202: "绣花头带",
    1203: "蓝绸头带",
    1204: "珍珠头带",
    1205: "书生冠",
    1206: "文臣冠",
    1207: "状元冠",
    1208: "明珠冠",
    1209: "华彩冠",
    1210: "青龙冠",
    1211: "皓天白玉冠",
    1212: "紫玉冠",
    1213: "圣者礼帽",
    1214: "文曲玉冠",
    1215: "南华星冠",
    1216: "切云冠",
    1217: "文曲星华冠",
    1218: "智多星华冠",
    1219: "雪人礼帽",
    1220: "武侯纶巾",
    1221: "凤雏斗笠",
    1222: "阴阳朝冠",
    1280: "鬼才绸冠",
    1281: "周郎羽盔",
    1282: "文若贤冠",
    # Vũ khí Võ (21xx)
    2101: "梅花亮银枪",
    2102: "水火夺魂枪",
    2103: "七星昆吾剑",
    2104: "落叶青锋剑",
    2105: "青鸿剑",
    2106: "烈焰蛇矛",
    2107: "胆膛枪",
    2108: "盘龙戟",
    2109: "乌龙戟",
    2110: "双翅玲珑戟",
    2111: "七曲凤翅金镋",
    2112: "北斗神锥",
    2113: "村正",
    2114: "回旋苦无",
    2115: "草剃剑",
    2116: "鲜卑长矛",
    2117: "乌桓长矛",
    2118: "山越猎叉",
    2119: "羌氐长戟",
    2120: "南蛮狼牙棒",
    2121: "匈奴长矛",
    2122: "战神三叉戟",
    2123: "霸王之枪",
    2124: "方天画戟",
    2125: "青龙偃月刀",
    2126: "丈八蛇矛",
    2127: "龙胆枪",
    2128: "属镂剑",
    2129: "武曲星大刀",
    2130: "圣诞拐杖",
    2131: "金刚杵",
    2132: "七星龙渊",
    2133: "普天同庆",
    2134: "宝雕落日弓",
    2135: "绝音凝水刃",
    2136: "王者之神威",
    2137: "诸侯长枪",
    2138: "勇者长剑",
    2139: "虎威长弓",
    2140: "霸王",
    2141: "青龙偃月刀",
    2142: "方天画戟",
    2143: "镔铁双戟",
    2144: "丈八蛇矛",
    2145: "涑缨亮银枪",
    2146: "青龙刀",
    2147: "流星追月",
    2151: "黄巾之力",
    2180: "良将之力",
    2181: "虎骑枪刃",
    2182: "蚩尤碎",
    2183: "玄铁重枪",
    2184: "君子之仁",
    2185: "百斤大斧",
    # Vũ khí Văn (22xx)
    2201: "宣纸扇",
    2202: "桐木扇",
    2203: "青竹扇",
    2204: "桃花扇",
    2205: "精钢扇",
    2206: "太极扇",
    2207: "青竹杂毛笔",
    2208: "兔毫硬笔",
    2209: "琉璃狼毫笔",
    2210: "紫檀兔毫笔",
    2211: "象牙紫玉笔",
    2212: "金钢判官笔",
    2213: "圣者凤羽扇",
    2214: "文曲寒玉剑",
    2215: "南华龙皮鞭",
    2216: "陆离剑",
    2217: "文曲星羽扇",
    2218: "智多星羽扇",
    2219: "雪人扫帚",
    2220: "金刚经",
    2251: "太平要术（伪）",
    2252: "太平要术",
    2253: "朱雀羽扇",
    2254: "醉八仙",
    2255: "黑羽扇",
    2280: "折羽扇",
    2281: "江东古琴",
    2282: "文若佩剑",
    # Giáp Võ (31xx)
    3101: "轻护甲",
    3102: "青铜甲",
    3103: "光荣甲",
    3104: "精铁甲",
    3105: "黄铜甲",
    3106: "镏金甲",
    3107: "重甲",
    3108: "镔铁甲",
    3109: "将军甲",
    3110: "龙虎甲",
    3111: "连环黄金甲",
    3112: "紫金兽面甲",
    3113: "胴丸铠",
    3114: "鲜卑盔甲",
    3115: "乌桓盔甲",
    3116: "山越盔甲",
    3117: "羌氐盔甲",
    3118: "南蛮藤甲",
    3119: "匈奴盔甲",
    3120: "战神龙鳞甲",
    3121: "霸王吞天甲",
    3122: "奇谋战圣甲",
    3123: "武曲星铠甲",
    3124: "圣诞铠甲",
    3125: "平民战甲",
    3126: "子龙战甲",
    3127: "刚侯战甲",
    3128: "霓裳羽衣",
    3129: "王者之奋武",
    3130: "诸侯战甲",
    3131: "勇者甲",
    3132: "虎威甲",
    3133: "大叶龙鳞甲",
    3134: "武圣战袍",
    3135: "唐猊铠甲",
    3136: "大叶黄金甲",
    3137: "斗神战甲",
    3138: "兽王白银铠",
    3139: "凤翎银铠",
    3140: "蝶舞羽衣",
    3180: "良将之魄",
    3181: "虎骑金铠",
    3182: "虎痴裸衣",
    3183: "布衣长袍",
    3184: "君子之礼",
    3185: "铜皮铁骨",
    # Giáp Văn (32xx)
    3201: "粗布袍",
    3202: "书生袍",
    3203: "绣花袍",
    3204: "蓝绸袍",
    3205: "文臣袍",
    3206: "状元袍",
    3207: "华彩袍",
    3208: "锦绣珠袍",
    3209: "青龙袍",
    3210: "皓天白玉袍",
    3211: "紫玉袍",
    3212: "混天夺日袍",
    3213: "圣者光芒袍",
    3214: "文曲紫玉甲",
    3215: "南华流光袍",
    3216: "青莲霓裳",
    3217: "文曲星锦袍",
    3218: "智多星锦袍",
    3219: "雪人长袍",
    3220: "武侯素袍",
    3221: "凤雏斗篷",
    3222: "阴阳朝服",
    3280: "御赐锦衣",
    3281: "白衣战袍",
    3282: "文若袍服",
    # Thú cưỡi Võ (41xx)
    4101: "大宛马",
    4102: "惊帆",
    4103: "白鹤",
    4104: "南蛮象",
    4105: "汗血马",
    4106: "龙怯",
    4107: "照夜玉狮子",
    4108: "乌云踏雪",
    4109: "黄爪飞电",
    4110: "绝影",
    4111: "的卢马",
    4112: "赤兔马",
    4113: "黑云",
    4114: "赤牦牛",
    4115: "重甲战虎",
    4116: "西凉战马",
    4117: "藤甲巨象",
    4118: "踏日",
    4119: "乌骓兽",
    4120: "祥瑞金牛",
    4121: "伍牙骑",
    4122: "苍龙",
    4123: "武曲星汗马",
    4124: "圣诞小鹿",
    4125: "祷杌",
    4126: "白光虎",
    4127: "白龙驹",
    4128: "燎原火",
    4129: "踏雪绝尘",
    4130: "王者之无畏",
    4131: "诸侯战车",
    4132: "勇者战马",
    4133: "虎威战马",
    4134: "怒日",
    4135: "真·赤兔",
    4136: "青鬃马",
    4137: "踢云乌骓",
    4138: "里飞沙",
    4139: "小赤兔",
    4140: "青龙驹",
    4180: "良将之骏",
    4181: "虎骑骏骁",
    4182: "御赐战马",
    4183: "羊驼",
    4184: "君子之风",
    4185: "木兽",
    # Thú cưỡi Văn (42xx)
    4201: "松风",
    4202: "飞镰",
    4203: "青牛",
    4204: "仙鹤",
    4205: "快航",
    4206: "穷奇",
    4207: "金龙驹",
    4208: "白玉麒麟",
    4209: "追风白凰",
    4210: "太公驴",
    4211: "四不象",
    4212: "五行八卦车",
    4213: "白石",
    4214: "云鬃马",
    4215: "塞外名驹",
    4216: "皓月神驹",
    4217: "赶月逐星",
    4218: "南华麒麟兽",
    4219: "文曲星汗马",
    4220: "智多星汗马",
    4221: "雪人小牛",
    4222: "苍龙",
    4223: "真·五行八卦",
    4224: "的卢",
    4225: "乌孙天马",
    4280: "白雪",
    4281: "一叶轻舟",
    4282: "文若白驹",
}


def _emit(cb: Optional[Callable[[str], None]], msg: str) -> None:
    if cb:
        cb(msg)


def _emit_progress(cb: Optional[Callable[[int, int], None]], done: int, total: int) -> None:
    if cb:
        cb(done, total)


def reward_money_needed(level: int, loyalty: int) -> int:
    """Tính số Vàng cần để ban thưởng khôi phục Lòng trung thành về 100."""
    if loyalty >= 100 or level <= 0:
        return 0
    return (100 - int(loyalty)) * int(level) * 10


@dataclass(frozen=True)
class RewardTarget:
    city_id: int
    city_name: str
    general: General
    money_needed: int


@dataclass
class RewardSummary:
    total: int = 0
    success: int = 0
    failed: int = 0
    total_gold_spent: int = 0
    stopped: bool = False
    details: list[str] = field(default_factory=list)


def collect_reward_targets(roster: Roster) -> list[RewardTarget]:
    """Lọc toàn bộ Văn quan và Võ tướng ở mọi căn cứ có Lòng trung thành < 100."""
    targets: list[RewardTarget] = []
    seen_ids: set[int] = set()
    for base in roster.bases:
        for gen in roster.generals_of(base.id):
            if gen.id in seen_ids or gen.loyalty >= 100:
                continue
            seen_ids.add(gen.id)
            money = reward_money_needed(gen.level, gen.loyalty)
            targets.append(
                RewardTarget(
                    city_id=base.id,
                    city_name=base.name,
                    general=gen,
                    money_needed=money,
                )
            )
    return targets


def reward_general(
    gateway: GatewayClient,
    city_id: int,
    general_id: int,
    money: int,
) -> tuple[bool, int, int]:
    """Gọi API ban thưởng tướng (OPT.ashx?id=46). Trả về (thành_công, ret, loyalty_mới)."""
    payload = {
        "lCityID": str(int(city_id)),
        "lGeneralID": str(int(general_id)),
        "lMoney": str(int(money)),
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 46, payload) or {}
    ret = int(resp.get("ret", -1)) if isinstance(resp, dict) else -1
    if ret == 0:
        new_loyalty = int(resp.get("loyalty", 100)) if isinstance(resp, dict) else 100
        return True, 0, new_loyalty
    return False, ret, 0


def reward_all_generals(
    gateway: GatewayClient,
    roster: Optional[Roster] = None,
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> RewardSummary:
    """Ban thưởng toàn bộ Văn quan và Võ tướng có Lòng trung thành < 100."""
    if roster is None:
        _emit(on_log, "📡 Đang tải danh sách Văn quan & Võ tướng từ tất cả căn cứ...")
        roster = fetch_roster(gateway, include_civil=True, include_cities=True)

    targets = collect_reward_targets(roster)
    summary = RewardSummary(total=len(targets))
    if not targets:
        _emit(on_log, "🎁 Tất cả Văn quan & Võ tướng đều đã đạt 100 trung thành.")
        return summary

    _emit(on_log, f"🎁 Bắt đầu ban thưởng cho {len(targets)} tướng có trung thành < 100...")
    for idx, item in enumerate(targets, start=1):
        if stop_event and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "🛑 Đã dừng ban thưởng theo yêu cầu.")
            break

        gen = item.general
        _emit_progress(on_progress, idx - 1, len(targets))
        ok, ret, new_loyalty = reward_general(gateway, item.city_id, gen.id, item.money_needed)
        if ok:
            summary.success += 1
            summary.total_gold_spent += item.money_needed
            line = (
                f"   ✅ [{item.city_name}] {gen.name} ({gen.role_text}, Cấp {gen.level}): "
                f"Trung thành {gen.loyalty} -> {new_loyalty} (-{item.money_needed:,} vàng)"
            )
        else:
            summary.failed += 1
            err_msg = TACTICIAN_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")
            line = (
                f"   ❌ [{item.city_name}] {gen.name} ({gen.role_text}, Cấp {gen.level}): "
                f"Thất bại ({err_msg})"
            )
        summary.details.append(line)
        _emit(on_log, line)
        _emit_progress(on_progress, idx, len(targets))

    _emit(
        on_log,
        f"📊 Hoàn tất ban thưởng: {summary.success}/{summary.total} thành công, "
        f"{summary.failed} thất bại (đã chi {summary.total_gold_spent:,} vàng).",
    )
    return summary


@dataclass
class TacticianSummary:
    total_selected: int = 0
    assigned: int = 0
    removed: int = 0
    name_matched: int = 0
    fallback_assigned: int = 0
    skipped_has_tactician: int = 0
    skipped_busy: int = 0
    no_tactician_to_remove: int = 0
    no_available_civilian: int = 0
    failed: int = 0
    stopped: bool = False


def set_tactician(
    gateway: GatewayClient,
    city_id: int,
    civilian_id: int,
    military_id: int = 0,
    remove: bool = False,
) -> tuple[bool, int, str]:
    """Gán hoặc tháo Mưu sĩ cho Võ tướng qua API OPT.ashx?id=5."""
    payload = {
        "lGeneralID": str(int(civilian_id)),
        "lType": "0" if remove else "3",
        "lFollowGeneralID": "0" if remove else str(int(military_id)),
        "lCityID": str(int(city_id)),
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 5, payload) or {}
    if not isinstance(resp, dict):
        return False, -1, "Lỗi kết nối"
    ret = int(resp.get("ret", -1))
    if ret == 0:
        return True, 0, "Thành công"
    return False, ret, TACTICIAN_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")


def _pair_tacticians(
    militaries: list[General],
    civilians: list[General],
    mode: str,
) -> list[tuple[General, Optional[General], str]]:
    """Ghép cặp Võ tướng với Văn quan khả dụng theo chế độ đã chọn."""
    if mode == MODE_SEQUENTIAL:
        return [
            (mil, civilians[idx] if idx < len(civilians) else None, "sequential")
            for idx, mil in enumerate(militaries)
        ]

    if mode == MODE_BY_LEVEL:
        sorted_mils = sorted(militaries, key=lambda g: g.level, reverse=True)
        sorted_civs = sorted(civilians, key=lambda g: g.level, reverse=True)
        return [
            (mil, sorted_civs[idx] if idx < len(sorted_civs) else None, "by_level")
            for idx, mil in enumerate(sorted_mils)
        ]

    # MODE_BY_NAME: ưu tiên match tên (Văn quan/Võ tướng cấp cao trước), fallback cấp cao -> thấp
    sorted_mils = sorted(militaries, key=lambda g: g.level, reverse=True)
    sorted_civs = sorted(civilians, key=lambda g: g.level, reverse=True)
    used_civ_ids: set[int] = set()
    paired: dict[int, tuple[General, Optional[General], str]] = {}

    for mil in sorted_mils:
        mname = mil.name.strip()
        matched_civ = next(
            (c for c in sorted_civs if c.id not in used_civ_ids and c.name.strip() == mname),
            None,
        )
        if matched_civ is not None:
            used_civ_ids.add(matched_civ.id)
            paired[mil.id] = (mil, matched_civ, "name_match")

    remaining_civs = [c for c in sorted_civs if c.id not in used_civ_ids]
    rem_iter = iter(remaining_civs)
    for mil in sorted_mils:
        if mil.id not in paired:
            paired[mil.id] = (mil, next(rem_iter, None), "fallback")

    return [paired[mil.id] for mil in sorted_mils]


def _remove_tacticians_for_city(
    gateway: GatewayClient,
    city_id: int,
    city_name: str,
    militaries: list[General],
    summary: TacticianSummary,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
) -> None:
    """Tháo Mưu sĩ cho các Võ tướng được chọn trong một căn cứ."""
    for mil in militaries:
        if stop_event and stop_event.is_set():
            summary.stopped = True
            return
        if mil.tactician_id <= 0:
            summary.no_tactician_to_remove += 1
            _emit(on_log, f"   ⚠️ [{city_name}] {mil.name}: chưa có mưu sĩ.")
            continue
        if mil.status != 0:
            summary.skipped_busy += 1
            _emit(on_log, f"   ⚠️ [{city_name}] Bỏ qua {mil.name}: đang bận ({mil.status_text}).")
            continue

        ok, _ret, msg = set_tactician(gateway, city_id, mil.tactician_id, remove=True)
        if ok:
            summary.removed += 1
            tname = mil.tactician_name or str(mil.tactician_id)
            _emit(on_log, f"   ✅ [{city_name}] Đã tháo mưu sĩ {tname} khỏi {mil.name}.")
        else:
            summary.failed += 1
            _emit(on_log, f"   ❌ [{city_name}] Tháo mưu sĩ của {mil.name} thất bại: {msg}")


def _assign_tacticians_for_city(
    gateway: GatewayClient,
    roster: Roster,
    city_id: int,
    city_name: str,
    is_camp: bool,
    militaries: list[General],
    mode: str,
    reassign_existing: bool,
    summary: TacticianSummary,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
) -> None:
    """Biên chế (hoặc đổi) Mưu sĩ cho các Võ tướng được chọn trong cùng một thành."""
    if is_camp:
        _emit(on_log, f"   ⚠️ [{city_name}] Đang là Doanh trại (ID {city_id}); sẽ thử ghép nếu có Văn quan cùng căn cứ.")

    eligible_mils: list[General] = []
    for mil in militaries:
        if mil.status != 0:
            summary.skipped_busy += 1
            _emit(on_log, f"   ⚠️ [{city_name}] Bỏ qua {mil.name}: đang bận ({mil.status_text}).")
            continue
        if not reassign_existing and mil.tactician_id > 0:
            summary.skipped_has_tactician += 1
            tname = mil.tactician_name or str(mil.tactician_id)
            _emit(on_log, f"   ℹ️ [{city_name}] Giữ nguyên {mil.name}: đã có mưu sĩ ({tname}).")
            continue
        eligible_mils.append(mil)

    if not eligible_mils:
        return

    freed_civ_ids: set[int] = set()
    ready_mils: list[General] = []
    if reassign_existing:
        for mil in eligible_mils:
            if stop_event and stop_event.is_set():
                summary.stopped = True
                return
            if mil.tactician_id > 0:
                ok, _ret, msg = set_tactician(gateway, city_id, mil.tactician_id, remove=True)
                if ok:
                    summary.removed += 1
                    freed_civ_ids.add(mil.tactician_id)
                    tname = mil.tactician_name or str(mil.tactician_id)
                    _emit(on_log, f"   🔄 [{city_name}] Tháo mưu sĩ cũ {tname} khỏi {mil.name} để biên chế lại.")
                    ready_mils.append(mil)
                else:
                    summary.failed += 1
                    _emit(on_log, f"   ❌ [{city_name}] Không tháo được mưu sĩ cũ của {mil.name}: {msg}")
            else:
                ready_mils.append(mil)
    else:
        ready_mils = eligible_mils

    if not ready_mils:
        return

    # Chỉ lấy Văn quan cùng thành đang rảnh rỗi (hoặc vừa được tháo ra),
    # loại trừ hoàn toàn Thái thú (special_status == 1) và Văn quan đang làm nhiệm vụ khác (status != 0).
    available_civs = [
        c
        for c in roster.generals_of(city_id)
        if c.role == "van"
        and c.status == 0
        and c.special_status != 1
        and (c.special_status == 0 or c.id in freed_civ_ids)
    ]

    _emit(
        on_log,
        f"📌 [{city_name}] {len(ready_mils)} Võ tướng cần biên chế | "
        f"{len(available_civs)} Văn quan khả dụng.",
    )

    pairs = _pair_tacticians(ready_mils, available_civs, mode)
    for mil, civ, match_kind in pairs:
        if stop_event and stop_event.is_set():
            summary.stopped = True
            return
        if civ is None:
            summary.no_available_civilian += 1
            _emit(on_log, f"   ⚠️ [{city_name}] Hết Văn quan khả dụng cho {mil.name} (Cấp {mil.level}).")
            continue

        ok, _ret, msg = set_tactician(gateway, city_id, civ.id, military_id=mil.id, remove=False)
        if ok:
            summary.assigned += 1
            if match_kind == "name_match":
                summary.name_matched += 1
                tag = " [Trùng tên]"
            elif match_kind == "fallback":
                summary.fallback_assigned += 1
                tag = " [Fallback cao→thấp]"
            elif match_kind == "by_level":
                tag = " [Cao→thấp]"
            else:
                tag = ""
            _emit(
                on_log,
                f"   ✅ [{city_name}] Văn: {civ.name} (Lv.{civ.level}) -> Võ: {mil.name} (Lv.{mil.level}){tag}",
            )
        else:
            summary.failed += 1
            _emit(on_log, f"   ❌ [{city_name}] Gán {civ.name} -> {mil.name} thất bại: {msg}")


def configure_tacticians(
    gateway: GatewayClient,
    roster: Roster,
    selected_general_ids: list[int],
    mode: str = MODE_BY_LEVEL,
    reassign_existing: bool = False,
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> TacticianSummary:
    """Thiết lập hoặc tháo Mưu sĩ cho danh sách Võ tướng được chọn theo từng thành."""
    if mode not in VALID_TACTICIAN_MODES:
        raise ValueError(f"Chế độ Mưu sĩ không hợp lệ: {mode}")

    selected_set = {int(gid) for gid in selected_general_ids}
    summary = TacticianSummary(total_selected=len(selected_set))
    if not selected_set:
        return summary

    # Gom Võ tướng được chọn theo từng căn cứ (giữ đúng ranh giới cùng thành)
    city_groups: list[tuple[int, str, bool, list[General]]] = []
    seen_mils: set[int] = set()
    for base in roster.bases:
        mils_in_base = []
        for g in roster.generals_of(base.id):
            if g.id in selected_set and g.id not in seen_mils and g.role == "vo":
                seen_mils.add(g.id)
                mils_in_base.append(g)
        if mils_in_base:
            city_groups.append((base.id, base.name, base.is_camp, mils_in_base))

    total_bases = len(city_groups)
    for idx, (cid, cname, is_camp, mils) in enumerate(city_groups, start=1):
        if stop_event and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "🛑 Đã dừng thiết lập Mưu sĩ theo yêu cầu.")
            break
        _emit_progress(on_progress, idx - 1, total_bases)
        if mode == MODE_REMOVE:
            _remove_tacticians_for_city(gateway, cid, cname, mils, summary, stop_event, on_log)
        else:
            _assign_tacticians_for_city(
                gateway,
                roster,
                cid,
                cname,
                is_camp,
                mils,
                mode,
                reassign_existing,
                summary,
                stop_event,
                on_log,
            )
        _emit_progress(on_progress, idx, total_bases)

    _emit(
        on_log,
        f"📊 Kết quả Mưu sĩ: gán {summary.assigned}, tháo {summary.removed}, "
        f"bỏ qua (đã có {summary.skipped_has_tactician}, bận {summary.skipped_busy}), "
        f"thiếu Văn quan {summary.no_available_civilian}, lỗi {summary.failed}.",
    )
    return summary


# -----------------------------------------------------------------------------
# TỰ ĐỘNG TRANG BỊ QUAN VĂN & VÕ TƯỚNG
# -----------------------------------------------------------------------------
def get_item_display_name(item_type_id: int) -> str:
    """Trả về tên hiển thị của trang bị theo item_type_id."""
    tid = int(item_type_id)
    return ITEM_NAME_MAPPING.get(tid, f"ID:{tid}")


def classify_item_role(item_type_id: int) -> Optional[str]:
    """Phân hệ trang bị theo chữ số thứ hai của mã 4 chữ số: x2xx -> 'van', x1xx -> 'vo'."""
    s = str(int(item_type_id))
    if len(s) >= 2 and s[0] in ("1", "2", "3", "4"):
        return "van" if s[1] == "2" else "vo"
    return None


def civil_priority_tier(gen: General, active_tactician_ids: Optional[set[int]] = None) -> int:
    """Xếp tầng ưu tiên Văn quan: 0 = Thái thú, 1 = Mưu sĩ đang biên chế, 2 = Nhàn rỗi."""
    if gen.is_mayor:
        return 0
    if gen.is_tactician or (active_tactician_ids is not None and gen.id in active_tactician_ids):
        return 1
    return 2


@dataclass(frozen=True)
class EquipmentItem:
    item_id: int
    equip_type: int
    item_type_id: int
    level: int
    quantity: int = 1
    general_id: int = 0
    general_name: str = ""
    politics: int = 0

    @property
    def role(self) -> Optional[str]:
        return classify_item_role(self.item_type_id)

    @property
    def name(self) -> str:
        return get_item_display_name(self.item_type_id)

    @property
    def short_label(self) -> str:
        return f"{self.name} (Lv.{self.level})"

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (-self.level, -self.item_type_id, self.item_id)

    @property
    def mayor_sort_key(self) -> tuple[int, int, int, int]:
        """Khóa sắp xếp ưu tiên cho Thái thú: Nội chính cao nhất trước, rồi cấp và mã loại."""
        return (-self.politics, -self.level, -self.item_type_id, self.item_id)


@dataclass
class EquipmentInventory:
    free_items: dict[tuple[str, int], list[EquipmentItem]] = field(default_factory=dict)
    equipped_by_general: dict[int, dict[int, EquipmentItem]] = field(default_factory=dict)

    def count_free(self, role: str, equip_type: int) -> int:
        return len(self.free_items.get((role, equip_type), []))


@dataclass
class EquipSummary:
    total_selected: int = 0
    equipped: int = 0
    unequipped: int = 0
    skipped_busy: int = 0
    skipped_optimal: int = 0
    no_item_available: int = 0
    failed: int = 0
    stopped: bool = False


def _parse_inventory_rows_for_type(
    equip_type: int,
    rows: list[Any],
) -> tuple[dict[str, list[EquipmentItem]], dict[int, EquipmentItem], dict[int, int]]:
    """Phân tích danh sách hàng kho/trang bị từ Common.ashx?id=24 theo một lType."""
    free_by_role: dict[str, list[EquipmentItem]] = {"vo": [], "van": []}
    equipped_map: dict[int, EquipmentItem] = {}
    free_quantities: dict[int, int] = {}

    for row in rows:
        if not isinstance(row, list) or len(row) < 9:
            continue
        item_id = int(row[0] or 0)
        quantity = max(1, int(row[1] or 1))
        item_type_id = int(row[2] or 0)
        politics = max(0, int(row[6] or 0))
        level = max(1, int(row[7] or 1))
        general_id = int(row[8] or 0)
        general_name = str(row[9] or "") if len(row) > 9 else ""
        if item_id <= 0 or item_type_id <= 0:
            continue

        if general_id > 0:
            equipped_map[general_id] = EquipmentItem(
                item_id=item_id,
                equip_type=equip_type,
                item_type_id=item_type_id,
                level=level,
                quantity=1,
                general_id=general_id,
                general_name=general_name,
                politics=politics,
            )
        else:
            free_quantities[item_id] = quantity
            role = classify_item_role(item_type_id)
            if role in free_by_role:
                bucket = free_by_role[role]
                for copy_idx in range(quantity):
                    bucket.append(
                        EquipmentItem(
                            item_id=item_id,
                            equip_type=equip_type,
                            item_type_id=item_type_id,
                            level=level,
                            quantity=quantity - copy_idx,
                            general_id=0,
                            politics=politics,
                        )
                    )

    for bucket in free_by_role.values():
        bucket.sort(key=lambda it: it.sort_key)

    return free_by_role, equipped_map, free_quantities


def _fetch_all_equipment_rows(
    gateway: GatewayClient, equip_type: int
) -> Optional[list[Any]]:
    """Tải toàn bộ các trang trang bị của một lType qua Optimization.ashx?action=equipment (Server 58+)."""
    all_rows: list[Any] = []
    page = 0
    rev1, rev2 = 0, 0
    restarted_on_rev = False

    while True:
        data = gateway.optimization(
            "equipment",
            {
                "kind": "1",
                "type": str(equip_type),
                "target": "0",
                "page": str(page),
                "pageSize": "50",
                "revision1": str(rev1),
                "revision2": str(rev2),
            },
        )
        if not isinstance(data, dict):
            return None
        ret = int(data.get("ret", -1))
        if ret == 8102 and not restarted_on_rev:
            restarted_on_rev = True
            all_rows.clear()
            page = 0
            rev1, rev2 = 0, 0
            continue
        if ret != 0:
            return None

        rows = data.get("list")
        if not isinstance(rows, list):
            return None
        all_rows.extend(rows)

        rev = data.get("revision")
        if isinstance(rev, list) and len(rev) >= 2:
            rev1, rev2 = int(rev[0]), int(rev[1])

        total = int(data.get("total", len(all_rows)))
        page_size = max(1, int(data.get("pageSize", 50)))
        if not rows or (page + 1) * page_size >= total:
            break
        page += 1

    return all_rows


def fetch_equipment_inventory(gateway: GatewayClient) -> EquipmentInventory:
    """Truy vấn toàn bộ kho đồ và trang bị đang mặc của tướng từ Optimization.ashx?action=equipment."""
    free_items: dict[tuple[str, int], list[EquipmentItem]] = {}
    equipped_by_general: dict[int, dict[int, EquipmentItem]] = {}
    error_count = 0

    for equip_type in EQUIP_TYPES:
        rows = _fetch_all_equipment_rows(gateway, equip_type)
        if rows is None:
            error_count += 1
            continue

        free_by_role, equipped_map, _ = _parse_inventory_rows_for_type(equip_type, rows)
        for role_key, bucket in free_by_role.items():
            if bucket:
                free_items[(role_key, equip_type)] = bucket
        for gid, eq_item in equipped_map.items():
            equipped_by_general.setdefault(gid, {})[equip_type] = eq_item

    if error_count == len(EQUIP_TYPES):
        raise RuntimeError(
            "Không thể tải dữ liệu trang bị từ máy chủ (Optimization.ashx?action=equipment)."
        )

    return EquipmentInventory(free_items=free_items, equipped_by_general=equipped_by_general)


def _refresh_free_slot_from_server(
    gateway: GatewayClient,
    inventory: EquipmentInventory,
    equip_type: int,
    consumed_item_id: int = 0,
    prev_quantity: int = 0,
    expected_unequipped_general_ids: Optional[set[int]] = None,
) -> bool:
    """Làm mới kho đồ rảnh và trạng thái mặc của một equip_type từ Optimization.ashx?action=equipment."""
    rows = _fetch_all_equipment_rows(gateway, equip_type)
    if rows is None:
        return False

    free_by_role, equipped_map, free_quantities = _parse_inventory_rows_for_type(equip_type, rows)
    if (
        consumed_item_id > 0
        and prev_quantity > 0
        and free_quantities.get(consumed_item_id) == prev_quantity
    ):
        return False
    if expected_unequipped_general_ids and any(
        gid in equipped_map for gid in expected_unequipped_general_ids
    ):
        return False

    for role_key in ("vo", "van"):
        inventory.free_items[(role_key, equip_type)] = free_by_role[role_key]

    for slots in inventory.equipped_by_general.values():
        slots.pop(equip_type, None)
    for gid, eq_item in equipped_map.items():
        inventory.equipped_by_general.setdefault(gid, {})[equip_type] = eq_item
    return True


def equip_general_item(
    gateway: GatewayClient,
    city_id: int,
    general_id: int,
    equip_type: int,
    item_id: int,
) -> tuple[bool, int, str]:
    """Gọi OPT.ashx?id=58 để mặc (item_id > 0) hoặc tháo (item_id == 0) một món trang bị."""
    payload = {
        "lCityTentID": str(int(city_id)),
        "lGeneralID": str(int(general_id)),
        "lEquipType": str(int(equip_type)),
        "lEquipID": str(int(item_id)),
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 58, payload) or {}
    ret = int(resp.get("ret", -1)) if isinstance(resp, dict) else -1
    if ret == 0:
        return True, 0, "OK"
    server_msg = str(resp.get("errMsg") or "").strip() if isinstance(resp, dict) else ""
    return False, ret, EQUIP_ERROR_MESSAGES.get(ret) or server_msg or f"Mã lỗi {ret}"


def _unequip_selected_generals(
    gateway: GatewayClient,
    targets: list[tuple[int, str, General]],
    inventory: EquipmentInventory,
    summary: EquipSummary,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
    on_progress: Optional[Callable[[int, int], None]] = None,
    log_prefix: str = "✅",
    reason_suffix: str = "",
) -> bool:
    """Tháo trang bị đang mặc trên các tướng mục tiêu và đưa lại về kho khả dụng.

    Trả về True nếu chạy xong (hoặc False nếu bị dừng giữa chừng).
    """
    total = len(targets)
    for idx, (city_id, city_name, gen) in enumerate(targets, start=1):
        if stop_event and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "🛑 Đã dừng thao tác trang bị theo yêu cầu.")
            return False
        equipped_slots = inventory.equipped_by_general.get(gen.id)
        if not equipped_slots:
            _emit_progress(on_progress, idx, total)
            continue

        for equip_type in EQUIP_TYPES:
            if stop_event and stop_event.is_set():
                summary.stopped = True
                _emit(on_log, "🛑 Đã dừng thao tác trang bị theo yêu cầu.")
                return False
            old_item = equipped_slots.get(equip_type)
            if old_item is None:
                continue
            slot_name = EQUIP_SLOT_NAMES[equip_type]
            ok, _ret, msg = equip_general_item(gateway, city_id, gen.id, equip_type, 0)
            if ok:
                summary.unequipped += 1
                equipped_slots.pop(equip_type, None)
                freed_role = old_item.role or gen.role
                if freed_role in ("vo", "van"):
                    pool = inventory.free_items.setdefault((freed_role, equip_type), [])
                    pool.append(replace(old_item, general_id=0, general_name="", quantity=1))
                _emit(
                    on_log,
                    f"   {log_prefix} [{city_name}] Đã tháo {slot_name} ({old_item.short_label}) "
                    f"khỏi {gen.name}{reason_suffix}.",
                )
            else:
                summary.failed += 1
                _emit(
                    on_log,
                    f"   ❌ [{city_name}] Tháo {slot_name} ({old_item.short_label}) "
                    f"của {gen.name} thất bại: {msg}",
                )
        _emit_progress(on_progress, idx, total)
    return True


def _equip_single_slot(
    gateway: GatewayClient,
    inventory: EquipmentInventory,
    summary: EquipSummary,
    city_id: int,
    city_name: str,
    gen: General,
    equip_type: int,
    pool: list[EquipmentItem],
    candidate: EquipmentItem,
    current_item: Optional[EquipmentItem],
    on_log: Optional[Callable[[str], None]],
    role_note: str = "",
) -> str:
    """Thực hiện mặc/nâng cấp một ứng viên vào ô trang bị và đồng bộ kho/server.

    Trả về ``"equipped"`` nếu thành công, ``"restricted"`` nếu máy chủ từ chối
    theo điều kiện giới/tộc tướng (``ret=301``, giữ lại trong ``pool``), hoặc
    ``"failed"`` cho các lỗi khác.
    """
    slot_name = EQUIP_SLOT_NAMES[equip_type]
    ok, ret, msg = equip_general_item(gateway, city_id, gen.id, equip_type, candidate.item_id)
    if ok:
        for idx, item in enumerate(pool):
            if item is candidate or item.item_id == candidate.item_id:
                pool.pop(idx)
                break
        summary.equipped += 1
        if current_item is not None:
            replaced_role = current_item.role or gen.role
            if replaced_role in ("vo", "van"):
                back_pool = inventory.free_items.setdefault((replaced_role, equip_type), [])
                back_pool.append(replace(current_item, general_id=0, general_name="", quantity=1))
                back_pool.sort(key=lambda it: it.sort_key)
        inventory.equipped_by_general.setdefault(gen.id, {})[equip_type] = replace(
            candidate,
            quantity=1,
            general_id=gen.id,
            general_name=gen.name,
        )
        upgrade_note = f" (thay {current_item.short_label})" if current_item is not None else ""
        _emit(
            on_log,
            f"   ✅ [{city_name}] {gen.name}{role_note} (Lv.{gen.level}) mặc {slot_name}: "
            f"{candidate.short_label}{upgrade_note}",
        )
        if candidate.quantity > 1 or current_item is not None:
            _refresh_free_slot_from_server(
                gateway,
                inventory,
                equip_type,
                consumed_item_id=candidate.item_id,
                prev_quantity=candidate.quantity,
            )
        return "equipped"

    if ret == RET_EQUIP_FEMALE_OR_BARBARIAN_ONLY:
        _emit(
            on_log,
            f"   ⏭️ [{city_name}] {gen.name}{role_note} bỏ qua {slot_name} "
            f"({candidate.short_label}): {msg} — thử món kế tiếp",
        )
        return "restricted"

    summary.failed += 1
    pool[:] = [it for it in pool if it.item_id != candidate.item_id]
    _emit(
        on_log,
        f"   ❌ [{city_name}] {gen.name}{role_note} mặc {slot_name} ({candidate.short_label}) thất bại: {msg}",
    )
    return "failed"


def _is_standard_upgrade(candidate: EquipmentItem, current_item: EquipmentItem) -> bool:
    return (candidate.level, candidate.item_type_id) > (current_item.level, current_item.item_type_id)


def _is_mayor_upgrade(candidate: EquipmentItem, current_item: EquipmentItem) -> bool:
    return (candidate.politics, candidate.level, candidate.item_type_id) > (
        current_item.politics,
        current_item.level,
        current_item.item_type_id,
    )


def _equip_best_candidate(
    gateway: GatewayClient,
    inventory: EquipmentInventory,
    summary: EquipSummary,
    city_id: int,
    city_name: str,
    gen: General,
    equip_type: int,
    pool: list[EquipmentItem],
    candidates: list[EquipmentItem],
    current_item: Optional[EquipmentItem],
    is_upgrade: Callable[[EquipmentItem, EquipmentItem], bool],
    on_log: Optional[Callable[[str], None]],
    role_note: str = "",
    count_empty_slot: bool = True,
    restricted_ids: Optional[set[int]] = None,
) -> str:
    """Thử mặc ứng viên tốt nhất cho một ô; nếu gặp ret=301 thì thử món kế tiếp."""

    def _finish_without_equip() -> str:
        if count_empty_slot:
            if current_item is None:
                summary.no_item_available += 1
                return "empty"
            summary.skipped_optimal += 1
            return "optimal"
        if current_item is not None and current_item.politics > 0:
            summary.skipped_optimal += 1
            return "optimal"
        return "unresolved"

    eligible = [it for it in candidates if restricted_ids is None or it.item_id not in restricted_ids]
    if not eligible:
        return _finish_without_equip()

    upgradable = [it for it in eligible if current_item is None or is_upgrade(it, current_item)]
    if not upgradable:
        summary.skipped_optimal += 1
        return "optimal"

    for candidate in upgradable:
        status = _equip_single_slot(
            gateway,
            inventory,
            summary,
            city_id,
            city_name,
            gen,
            equip_type,
            pool,
            candidate,
            current_item,
            on_log,
            role_note=role_note,
        )
        if status in ("equipped", "failed"):
            return status
        if restricted_ids is not None:
            restricted_ids.add(candidate.item_id)

    return _finish_without_equip()


def _assign_standard_targets(
    gateway: GatewayClient,
    inventory: EquipmentInventory,
    summary: EquipSummary,
    targets: list[tuple[int, str, General]],
    processed: int,
    total_targets: int,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
    on_progress: Optional[Callable[[int, int], None]],
    role_note: str = "",
) -> tuple[bool, int]:
    """Phân bổ trang bị theo thứ tự bậc phẩm chất giảm dần (sort_key) cho một nhóm tướng."""
    for city_id, city_name, gen in targets:
        if stop_event and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "🛑 Đã dừng Tự động trang bị theo yêu cầu.")
            return False, processed

        for equip_type in EQUIP_TYPES:
            if stop_event and stop_event.is_set():
                summary.stopped = True
                _emit(on_log, "🛑 Đã dừng Tự động trang bị theo yêu cầu.")
                return False, processed

            pool = inventory.free_items.setdefault((gen.role, equip_type), [])
            pool.sort(key=lambda it: it.sort_key)
            current_item = inventory.equipped_by_general.get(gen.id, {}).get(equip_type)

            _equip_best_candidate(
                gateway,
                inventory,
                summary,
                city_id,
                city_name,
                gen,
                equip_type,
                pool,
                pool,
                current_item,
                _is_standard_upgrade,
                on_log,
                role_note=role_note,
            )

        processed += 1
        _emit_progress(on_progress, processed, total_targets)

    return True, processed


def _assign_civil_generals(
    gateway: GatewayClient,
    roster: Roster,
    inventory: EquipmentInventory,
    summary: EquipSummary,
    civil_targets: list[tuple[int, str, General]],
    processed: int,
    total_targets: int,
    stop_event: Optional[threading.Event],
    on_log: Optional[Callable[[str], None]],
    on_progress: Optional[Callable[[int, int], None]],
) -> tuple[bool, int]:
    """Biên chế đồ thông minh cho Văn quan: Thái thú (Nội chính) -> Mưu sĩ -> Nhàn rỗi -> Vét Thái thú."""
    active_tac_ids = roster.active_tactician_ids()
    mayor_targets: list[tuple[int, str, General]] = []
    tactician_targets: list[tuple[int, str, General]] = []
    idle_civil_targets: list[tuple[int, str, General]] = []

    for target in civil_targets:
        tier = civil_priority_tier(target[2], active_tac_ids)
        if tier == 0:
            mayor_targets.append(target)
        elif tier == 1:
            tactician_targets.append(target)
        else:
            idle_civil_targets.append(target)

    mayor_resolved_slots: set[tuple[int, int]] = set()
    restricted_by_mayor_slot: dict[tuple[int, int], set[int]] = {}

    # Lượt 1: Thái thú ưu tiên đồ tăng Nội chính (politics > 0); nhường đồ politics == 0 cho Mưu sĩ
    if mayor_targets:
        _emit(
            on_log,
            f"📌 Đang phân bổ trang bị Nội chính cho Thái thú ({len(mayor_targets)} tướng, ưu tiên Cao → Thấp)...",
        )
        for city_id, city_name, gen in mayor_targets:
            if stop_event and stop_event.is_set():
                summary.stopped = True
                _emit(on_log, "🛑 Đã dừng Tự động trang bị theo yêu cầu.")
                return False, processed

            for equip_type in EQUIP_TYPES:
                if stop_event and stop_event.is_set():
                    summary.stopped = True
                    _emit(on_log, "🛑 Đã dừng Tự động trang bị theo yêu cầu.")
                    return False, processed

                pool = inventory.free_items.setdefault(("van", equip_type), [])
                current_item = inventory.equipped_by_general.get(gen.id, {}).get(equip_type)
                pol_candidates = sorted(
                    (it for it in pool if it.politics > 0),
                    key=lambda it: it.mayor_sort_key,
                )
                restricted_ids = restricted_by_mayor_slot.setdefault((gen.id, equip_type), set())
                status = _equip_best_candidate(
                    gateway,
                    inventory,
                    summary,
                    city_id,
                    city_name,
                    gen,
                    equip_type,
                    pool,
                    pol_candidates,
                    current_item,
                    _is_mayor_upgrade,
                    on_log,
                    role_note=" [Thái thú]",
                    count_empty_slot=False,
                    restricted_ids=restricted_ids,
                )
                if status in ("equipped", "optimal", "failed"):
                    mayor_resolved_slots.add((gen.id, equip_type))

    # Lượt 2: Mưu sĩ đang biên chế rồi mới đến Quan văn nhàn rỗi
    if tactician_targets:
        _emit(
            on_log,
            f"📌 Đang phân bổ trang bị Mưu sĩ đang biên chế ({len(tactician_targets)} tướng, ưu tiên Cao → Thấp)...",
        )
        ok, processed = _assign_standard_targets(
            gateway,
            inventory,
            summary,
            tactician_targets,
            processed,
            total_targets,
            stop_event,
            on_log,
            on_progress,
            role_note=" [Mưu sĩ]",
        )
        if not ok:
            return False, processed

    if idle_civil_targets:
        _emit(
            on_log,
            f"📌 Đang phân bổ trang bị Quan văn nhàn rỗi ({len(idle_civil_targets)} tướng, ưu tiên Cao → Thấp)...",
        )
        ok, processed = _assign_standard_targets(
            gateway,
            inventory,
            summary,
            idle_civil_targets,
            processed,
            total_targets,
            stop_event,
            on_log,
            on_progress,
        )
        if not ok:
            return False, processed

    # Lượt 3: Vét đồ còn dư trong kho vào các ô chưa xử lý của Thái thú
    if mayor_targets:
        has_unresolved = any(
            (gen.id, eq_type) not in mayor_resolved_slots
            for _, _, gen in mayor_targets
            for eq_type in EQUIP_TYPES
        )
        if has_unresolved:
            _emit(on_log, f"📌 Đang vét trang bị còn dư vào ô trống cho Thái thú ({len(mayor_targets)} tướng)...")
        for city_id, city_name, gen in mayor_targets:
            if stop_event and stop_event.is_set():
                summary.stopped = True
                _emit(on_log, "🛑 Đã dừng Tự động trang bị theo yêu cầu.")
                return False, processed

            for equip_type in EQUIP_TYPES:
                if (gen.id, equip_type) in mayor_resolved_slots:
                    continue
                if stop_event and stop_event.is_set():
                    summary.stopped = True
                    _emit(on_log, "🛑 Đã dừng Tự động trang bị theo yêu cầu.")
                    return False, processed

                pool = inventory.free_items.setdefault(("van", equip_type), [])
                pool.sort(key=lambda it: it.sort_key)
                current_item = inventory.equipped_by_general.get(gen.id, {}).get(equip_type)

                _equip_best_candidate(
                    gateway,
                    inventory,
                    summary,
                    city_id,
                    city_name,
                    gen,
                    equip_type,
                    pool,
                    pool,
                    current_item,
                    _is_mayor_upgrade,
                    on_log,
                    role_note=" [Thái thú]",
                    restricted_ids=restricted_by_mayor_slot.get((gen.id, equip_type)),
                )

            processed += 1
            _emit_progress(on_progress, processed, total_targets)

    return True, processed


def configure_equipment(
    gateway: GatewayClient,
    roster: Roster,
    selected_general_ids: list[int],
    mode: str = EQUIP_MODE_ASSIGN,
    reassign_existing: bool = False,
    inventory: Optional[EquipmentInventory] = None,
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> EquipSummary:
    """Tự động trang bị hoặc tháo trang bị cho Quan văn & Võ tướng theo ưu tiên vai trò và cấp độ."""
    if mode not in VALID_EQUIP_MODES:
        raise ValueError(f"Chế độ trang bị không hợp lệ: {mode}")

    selected_set = {int(gid) for gid in selected_general_ids}
    summary = EquipSummary(total_selected=len(selected_set))
    if not selected_set:
        return summary

    selected_targets: list[tuple[int, str, General]] = []
    seen_ids: set[int] = set()
    for base in roster.bases:
        for gen in roster.generals_of(base.id):
            if gen.id in selected_set and gen.id not in seen_ids and gen.role in ("vo", "van"):
                seen_ids.add(gen.id)
                selected_targets.append((base.id, base.name, gen))

    if not selected_targets:
        return summary

    if inventory is None:
        inventory = fetch_equipment_inventory(gateway)

    idle_targets: list[tuple[int, str, General]] = []
    for city_id, city_name, gen in selected_targets:
        if gen.status != 0:
            summary.skipped_busy += 1
            _emit(on_log, f"   ⚠️ [{city_name}] Bỏ qua {gen.name}: đang bận ({gen.status_text}).")
            continue
        idle_targets.append((city_id, city_name, gen))

    if not idle_targets:
        return summary

    if mode == EQUIP_MODE_UNEQUIP:
        idle_sorted = sorted(idle_targets, key=lambda item: (-item[2].level, item[2].id))
        _emit_progress(on_progress, 0, len(idle_sorted))
        _unequip_selected_generals(
            gateway,
            idle_sorted,
            inventory,
            summary,
            stop_event,
            on_log,
            on_progress=on_progress,
        )
        _emit(
            on_log,
            f"📊 Kết quả tháo trang bị: đã tháo {summary.unequipped}, "
            f"bỏ qua bận {summary.skipped_busy}, lỗi {summary.failed}.",
        )
        return summary

    # Chế độ mặc / nâng cấp trang bị (EQUIP_MODE_ASSIGN):
    # Bước 1: Nếu chọn 'Đổi trang bị', tháo đồ của các tướng rảnh đã chọn về kho trước
    idle_sorted_all = sorted(idle_targets, key=lambda item: (-item[2].level, item[2].id))
    if reassign_existing:
        before_equipped = {
            (gen.id, eq_type)
            for _, _, gen in idle_sorted_all
            for eq_type in inventory.equipped_by_general.get(gen.id, {})
        }
        _emit(on_log, "🔄 Đang thu hồi trang bị hiện tại của các tướng đã chọn về kho...")
        ok_unequip = _unequip_selected_generals(
            gateway,
            idle_sorted_all,
            inventory,
            summary,
            stop_event,
            on_log,
            on_progress=None,
            log_prefix="🔄",
            reason_suffix=" về kho",
        )
        if not ok_unequip:
            return summary
        if summary.unequipped > 0:
            unequipped_by_type: dict[int, set[int]] = {}
            for gid, eq_type in before_equipped:
                if eq_type not in inventory.equipped_by_general.get(gid, {}):
                    unequipped_by_type.setdefault(eq_type, set()).add(gid)
            for eq_type, gids in unequipped_by_type.items():
                _refresh_free_slot_from_server(
                    gateway,
                    inventory,
                    eq_type,
                    expected_unequipped_general_ids=gids,
                )
        for bucket in inventory.free_items.values():
            bucket.sort(key=lambda it: it.sort_key)

    # Bước 2: Tách Võ tướng (Cao -> Thấp) và Văn quan (Thái thú -> Mưu sĩ -> Nhàn rỗi)
    vo_targets = [t for t in idle_sorted_all if t[2].role == "vo"]
    van_targets = [t for t in idle_sorted_all if t[2].role == "van"]

    total_targets = len(idle_sorted_all)
    processed = 0
    _emit_progress(on_progress, 0, total_targets)

    if vo_targets:
        _emit(on_log, f"📌 Đang phân bổ trang bị Võ tướng ({len(vo_targets)} tướng, ưu tiên Cao → Thấp)...")
        ok, processed = _assign_standard_targets(
            gateway,
            inventory,
            summary,
            vo_targets,
            processed,
            total_targets,
            stop_event,
            on_log,
            on_progress,
        )
        if not ok:
            return summary

    if van_targets:
        ok, processed = _assign_civil_generals(
            gateway,
            roster,
            inventory,
            summary,
            van_targets,
            processed,
            total_targets,
            stop_event,
            on_log,
            on_progress,
        )
        if not ok:
            return summary

    _emit(
        on_log,
        f"📊 Kết quả Trang bị: mặc mới/nâng cấp {summary.equipped}, tháo {summary.unequipped}, "
        f"giữ tối ưu {summary.skipped_optimal}, hết đồ {summary.no_item_available}, "
        f"bỏ qua bận {summary.skipped_busy}, lỗi {summary.failed}.",
    )
    return summary


# ---------------------------------------------------------------------------
# ĐỔI TÊN TƯỚNG (OPT.ashx?id=43)
# ---------------------------------------------------------------------------

RENAME_STATUS_BLOCKED = 35  # 0x23 trong character.js
RENAME_MAX_WIDTH = 17  # Server yêu cầu > 0 và < 18 (chữ không phải ASCII tính 2)
RENAME_ERROR_MESSAGES = {
    **TROOP_ERROR_MESSAGES,
    15: "Tên mới rỗng hoặc vượt giới hạn độ dài (< 18 ký tự; chữ Hán/có dấu tính 2)",
}


def sanitize_general_name(raw: str) -> str:
    """Làm sạch tên tướng trước khi gửi lên server (bỏ khoảng trắng đầu/cuối, thay dấu nháy)."""
    return (raw or "").strip().replace("'", "’").replace('"', "’")


def general_name_width(name: str) -> int:
    """Tính độ dài tên theo quy tắc máy chủ Linh Vương (ASCII = 1, non-ASCII = 2)."""
    return sum(1 if ord(ch) < 128 else 2 for ch in name)


def validate_general_name(name: str) -> tuple[bool, str]:
    """Kiểm tra tên tướng hợp lệ theo giới hạn máy chủ (0 < width <= 17)."""
    cleaned = sanitize_general_name(name)
    if not cleaned:
        return False, "Tên mới không được để trống."
    width = general_name_width(cleaned)
    if width > RENAME_MAX_WIDTH:
        return False, f"Tên '{cleaned}' quá dài ({width}/{RENAME_MAX_WIDTH} đơn vị)."
    return True, ""


def format_numbered_general_name(prefix: str, number: int, pad_width: int = 2) -> str:
    """Ghép tiền tố với số thứ tự có đệm số 0 phía trước (01, 02, ...)."""
    return f"{prefix}{number:0{max(2, pad_width)}d}"


def build_rename_plan(
    generals: list[tuple[int, General]],
    prefix_or_name: str,
    numbered: bool = True,
    start_index: int = 1,
) -> list[tuple[int, General, str]]:
    """Tạo danh sách (city_id, general, new_name) theo thứ tự hiển thị hiện tại."""
    base_text = sanitize_general_name(prefix_or_name)
    if not base_text or not generals:
        return [(cid, gen, base_text) for cid, gen in generals]
    if not numbered:
        return [(cid, gen, base_text) for cid, gen in generals]
    start = max(1, int(start_index))
    max_num = start + len(generals) - 1
    pad_width = max(2, len(str(max_num)))
    return [
        (cid, gen, format_numbered_general_name(base_text, start + idx, pad_width=pad_width))
        for idx, (cid, gen) in enumerate(generals)
    ]


@dataclass
class RenameSummary:
    renamed: int = 0
    skipped_same: int = 0
    skipped_blocked: int = 0
    invalid_name: int = 0
    failed: int = 0
    stopped: bool = False


def rename_general(
    gateway: GatewayClient,
    city_id: int,
    general_id: int,
    new_name: str,
) -> tuple[bool, int, str]:
    """Đổi tên một Văn quan hoặc Võ tướng qua API OPT.ashx?id=43."""
    cleaned = sanitize_general_name(new_name)
    ok_valid, err_valid = validate_general_name(cleaned)
    if not ok_valid:
        return False, 15, err_valid

    payload = {
        "lCityID": str(int(city_id)),
        "lGeneralID": str(int(general_id)),
        "szNewName": cleaned,
        "_": "",
    }
    resp = gateway.call("OPT.ashx", 43, payload) or {}
    if not isinstance(resp, dict):
        return False, -1, "Lỗi kết nối"
    ret = int(resp.get("ret", -1))
    if ret == 0:
        return True, 0, "Thành công"
    return False, ret, RENAME_ERROR_MESSAGES.get(ret, f"Mã lỗi {ret}")


def rename_generals(
    gateway: GatewayClient,
    roster: Roster,
    rename_items: list[tuple[int, str]],
    stop_event: Optional[threading.Event] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> RenameSummary:
    """Thực thi đổi tên hàng loạt cho các tướng theo danh sách (general_id, new_name)."""
    summary = RenameSummary()
    if not rename_items:
        return summary

    by_id: dict[int, tuple[int, str, General]] = {}
    for base in roster.bases:
        for gen in roster.generals_of(base.id):
            if gen.id not in by_id:
                by_id[gen.id] = (base.id, base.name, gen)

    total = len(rename_items)
    _emit_progress(on_progress, 0, total)
    seen: set[int] = set()
    for idx, (gid_raw, raw_new_name) in enumerate(rename_items, start=1):
        if stop_event is not None and stop_event.is_set():
            summary.stopped = True
            _emit(on_log, "⏹️ Đã dừng tác vụ Đổi tên tướng theo yêu cầu.")
            return summary

        gid = int(gid_raw)
        if gid in seen:
            _emit_progress(on_progress, idx, total)
            continue
        seen.add(gid)

        found = by_id.get(gid)
        if found is None:
            summary.failed += 1
            _emit(on_log, f"   ❌ Không tìm thấy tướng ID {gid}.")
            _emit_progress(on_progress, idx, total)
            continue

        base_id, base_name, gen = found
        if gen.status == RENAME_STATUS_BLOCKED:
            summary.skipped_blocked += 1
            _emit(on_log, f"   ⚠️ [{base_name}] Bỏ qua {gen.name}: trạng thái không cho phép đổi tên ({gen.status}).")
            _emit_progress(on_progress, idx, total)
            continue

        new_name = sanitize_general_name(raw_new_name)
        ok_valid, err_valid = validate_general_name(new_name)
        if not ok_valid:
            summary.invalid_name += 1
            _emit(on_log, f"   ❌ [{base_name}] {gen.name}: {err_valid}")
            _emit_progress(on_progress, idx, total)
            continue

        if new_name == gen.name:
            summary.skipped_same += 1
            _emit(on_log, f"   ℹ️ [{base_name}] {gen.name}: tên mới trùng tên hiện tại, bỏ qua.")
            _emit_progress(on_progress, idx, total)
            continue

        ok, _ret, msg = rename_general(gateway, base_id, gen.id, new_name)
        if ok:
            summary.renamed += 1
            _emit(on_log, f"   ✅ [{base_name}] {gen.name} → {new_name}")
        else:
            summary.failed += 1
            _emit(on_log, f"   ❌ [{base_name}] Đổi tên {gen.name} → {new_name} thất bại: {msg}")
        _emit_progress(on_progress, idx, total)

    _emit(
        on_log,
        f"✏️ Kết quả Đổi tên: thành công {summary.renamed}, trùng tên {summary.skipped_same}, "
        f"không hợp lệ {summary.invalid_name}, khóa trạng thái {summary.skipped_blocked}, lỗi {summary.failed}.",
    )
    return summary
