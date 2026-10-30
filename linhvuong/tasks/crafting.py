"""Nhiệm vụ Chế Tạo Quân Giới (Vũ khí, Cung nỗ, Khôi giáp, Chiến mã, Xe ném đá).

Tuân thủ ADR-0031:
- Danh mục chuẩn 68 loại quân giới nguyên bản của Linh Vương.
- Tự động quét và nhận diện ô đất công xưởng (pid) trong thành trì (City.ashx?id=5).
  * Xưởng Binh Khí (gid=13 hoặc gid=66): Binh khí (101-152) và Cung nỗ (201-251).
  * Xưởng Khôi Giáp (gid=14 hoặc gid=67): Khôi giáp (301-350).
  * Xưởng Ngựa / Xa Mã (gid=15 hoặc gid=68): Chiến mã (401-450) và Xe ném đá (501-531).
- Chế tạo quân giới theo mẻ qua API máy chủ OPT.ashx?id=38.
- Cơ chế an toàn tài nguyên: tự động hoãn khi thiếu tài nguyên (ret=32).
"""

import logging
from typing import Callable, Optional

from ..gateway import GatewayClient
from .base import RET_CAPTCHA_REQUIRED, RET_OK, CaptchaRequired

logger = logging.getLogger("linhvuong.tasks.crafting")

# Danh mục 68 loại quân giới nguyên bản của Linh Vương
# Cấu trúc: weapon_id: (Tên quân giới, Loại nhóm)
WEAPONS_DATA: dict[int, tuple[str, str]] = {
    # 1. Binh khí (Đao, Thương, Kiếm, Kích)
    101: ("Thấu giáp thương", "Binh khí"),
    102: ("Hậu bối đao", "Binh khí"),
    103: ("Hổ bí đao", "Binh khí"),
    104: ("Cổ đồng đao", "Binh khí"),
    105: ("Đại khảm đao", "Binh khí"),
    106: ("Khoan nhận kiếm", "Binh khí"),
    107: ("Tam hoàn đại đao", "Binh khí"),
    108: ("Bách thắng trường đao", "Binh khí"),
    111: ("Đoản thiết kiếm", "Binh khí"),
    112: ("Hổ ảnh đao", "Binh khí"),
    121: ("Huyền thiết kiếm", "Binh khí"),
    122: ("Phá thiên kích", "Binh khí"),
    131: ("Thôn nhật trảm", "Binh khí"),
    132: ("Liệt hỏa kiếm", "Binh khí"),
    150: ("Đông dương đao", "Binh khí"),
    151: ("Thú vương thương", "Binh khí"),
    152: ("Đồ mã qua", "Binh khí"),
    # 2. Cung nỗ
    201: ("Thiết thai cung", "Cung nỗ"),
    202: ("Bá vương nỗ", "Cung nỗ"),
    203: ("Ly tần cung", "Cung nỗ"),
    204: ("Bảo điêu cung", "Cung nỗ"),
    205: ("Ngọc giác cung", "Cung nỗ"),
    206: ("Trường huyền giáp cung", "Cung nỗ"),
    207: ("Thần diên cung", "Cung nỗ"),
    208: ("Phá phong cung", "Cung nỗ"),
    211: ("Nhật nguyệt canh cung", "Cung nỗ"),
    212: ("Nhận mộc hồ cung", "Cung nỗ"),
    221: ("Thấu bối cách cung", "Cung nỗ"),
    222: ("Mông cổ cường cung", "Cung nỗ"),
    231: ("Thu nguyệt hành thiên cung", "Cung nỗ"),
    232: ("Sáp huyết vương cung", "Cung nỗ"),
    250: ("Ngưu giác cung", "Cung nỗ"),
    251: ("Xạ ảnh cung", "Cung nỗ"),
    # 3. Khôi giáp
    301: ("Ngư lân giáp", "Khôi giáp"),
    302: ("Tinh cương giáp", "Khôi giáp"),
    303: ("Minh quang chiến giáp", "Khôi giáp"),
    304: ("Địa long chiến giáp", "Khôi giáp"),
    305: ("Thiên hộ giáp", "Khôi giáp"),
    306: ("Thảo nghịch khôi giáp", "Khôi giáp"),
    307: ("Xích nhật chiến giáp", "Khôi giáp"),
    308: ("Lôi đình chiến giáp", "Khôi giáp"),
    311: ("Tướng quân chiến giáp", "Khôi giáp"),
    312: ("Hổ ủng giáp trụ", "Khôi giáp"),
    321: ("Cấm vệ giáp", "Khôi giáp"),
    322: ("Huyền thiết giáp trụ", "Khôi giáp"),
    331: ("Chiến nguyện hộ giáp", "Khôi giáp"),
    332: ("Chiến thần chi trụ", "Khôi giáp"),
    350: ("Đằng du giáp", "Khôi giáp"),
    # 4. Chiến mã
    401: ("Tuyệt địa mã", "Chiến mã"),
    402: ("Phiên vũ mã", "Chiến mã"),
    403: ("Bôn tiêu mã", "Chiến mã"),
    404: ("Dã hành mã", "Chiến mã"),
    405: ("Việt ảnh mã", "Chiến mã"),
    406: ("Du huy mã", "Chiến mã"),
    407: ("Thiết kị mã", "Chiến mã"),
    408: ("Xích ký mã", "Chiến mã"),
    411: ("Siêu quang mã", "Chiến mã"),
    412: ("Đằng vụ mã", "Chiến mã"),
    421: ("Hiệp dực mã", "Chiến mã"),
    422: ("Đạo ly mã", "Chiến mã"),
    431: ("Hoa lưu mã", "Chiến mã"),
    432: ("Truy phong mã", "Chiến mã"),
    450: ("Hung Nô phiêu kị", "Chiến mã"),
    # 5. Xe ném đá
    501: ("Xe ném đá loại nhẹ", "Xe ném đá"),
    511: ("Xe ném đá loại vừa", "Xe ném đá"),
    521: ("Xe ném đá loại nặng", "Xe ném đá"),
    531: ("Xe ném đá hỏa diêm", "Xe ném đá"),
}

CRAFT_ERROR_MESSAGES = {
    0: "Chế tạo thành công",
    1: "Thao tác thất bại, vui lòng thử lại sau",
    32: "Tài nguyên không đủ để chế tạo",
    33: "Đồng không đủ",
    34: "Dân số rảnh rỗi không đủ",
    110: "Yêu cầu mã xác thực Captcha",
}


def get_weapon_name(weapon_id: int) -> str:
    """Lấy tên hiển thị của quân giới theo mã ID."""
    info = WEAPONS_DATA.get(weapon_id)
    return info[0] if info else f"Quân giới #{weapon_id}"


def get_required_workshop_gids(weapon_id: int) -> tuple[int, int]:
    """Trả về cặp mã ID công xưởng sơ cấp và cao cấp tương ứng với loại quân giới.

    - Binh khí & Cung nỗ: gid 13 (Xưởng Binh Khí) & 66 (Binh Khí Ty).
    - Khôi giáp: gid 14 (Xưởng Khôi Giáp) & 67 (Phòng Cụ Ty).
    - Chiến mã & Xe ném đá: gid 15 (Xưởng Ngựa) & 68 (Xa Mã Ty).
    """
    if 100 <= weapon_id < 300:
        return (13, 66)
    elif 300 <= weapon_id < 400:
        return (14, 67)
    elif 400 <= weapon_id < 600:
        return (15, 68)
    return (13, 66)


class WeaponCrafter:
    """Dịch vụ điều phối chế tạo quân giới tại thành trì."""

    def __init__(self, gateway: GatewayClient):
        self.gateway = gateway

    def find_workshop(self, city_id: int, weapon_id: int) -> tuple[Optional[int], Optional[int]]:
        """Truy vấn danh sách công trình trong thành (City.ashx?id=5) và tìm (pid, gid) của xưởng."""
        resp = self.gateway.call("City.ashx", 5, {"tid": str(city_id), "_": ""}) or {}
        ret = resp.get("ret", RET_OK)
        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        allowed_gids = get_required_workshop_gids(weapon_id)

        # Định dạng danh sách công trình từ City.ashx?id=5:
        # Máy chủ Linh Vương trả về 'infos': [[pid, gid, name, level, status, finish_time], ...]
        # Hoặc fallback sang 'buildings', 'list', 'build'
        buildings = (
            resp.get("infos")
            or resp.get("buildings")
            or resp.get("list")
            or resp.get("build")
            or []
        )
        for b in buildings:
            if isinstance(b, dict):
                gid = int(b.get("gid", 0))
                pid = int(b.get("pid", 0))
                if gid in allowed_gids and pid > 0:
                    return pid, gid
            elif isinstance(b, (list, tuple)) and len(b) >= 2:
                try:
                    # Cấu trúc list từ 'infos': [pid, gid, ...]
                    pid = int(b[0])
                    gid = int(b[1])
                    if gid in allowed_gids and pid > 0:
                        return pid, gid
                except (ValueError, TypeError):
                    continue

        return None, None

    def find_workshop_plot(self, city_id: int, weapon_id: int) -> Optional[int]:
        """Truy vấn vị trí ô đất (pid) của xưởng phù hợp."""
        pid, _ = self.find_workshop(city_id, weapon_id)
        return pid

    def craft_once(
        self,
        city_id: int,
        weapon_id: int,
        amount: int,
        faster: int = 1,
        notify: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, int, str]:
        """Thực hiện 1 lượt chế tạo quân giới tại thành qua OPT.ashx?id=38.

        Trả về tuple (thành_công, mã_lỗi_ret, thông_điệp).
        """
        if amount <= 0:
            return False, -1, "Số lượng chế tạo phải lớn hơn 0"

        w_name = get_weapon_name(weapon_id)

        # 1. Chuyển tiêu điểm thành phố qua City.ashx?id=50
        self.gateway.call("City.ashx", 50, {"tid": str(city_id), "_": ""})

        # 2. Tìm vị trí ô đất và mã xưởng phù hợp trong thành
        plot_id, workshop_gid = self.find_workshop(city_id, weapon_id)
        if plot_id is None or workshop_gid is None:
            err_msg = f"❌ Thành (ID: {city_id}) chưa xây dựng công xưởng phù hợp để chế tạo '{w_name}'!"
            if notify:
                notify(err_msg)
            return False, -2, err_msg

        # 3. Kích hoạt ngữ cảnh công xưởng qua build.ashx?id=2 trước khi gửi lệnh chế tạo
        self.gateway.call(
            "build.ashx",
            2,
            {
                "gid": str(workshop_gid),
                "pid": str(plot_id),
                "tab": "0",
                "tid": str(city_id),
                "_": "",
            },
        )

        # 4. Gửi lệnh chế tạo quân giới qua OPT.ashx?id=38
        # Máy chủ yêu cầu lFaster >= 1 (1: bình thường, 3: tăng tốc)
        faster_val = max(1, faster) if faster is not None else 1
        payload = {
            "count": str(amount),
            "gid": str(weapon_id),
            "lFaster": str(faster_val),
            "pos": str(plot_id),
            "tid": str(city_id),
            "num": "-1",
            "_": "",
        }
        resp = self.gateway.call("OPT.ashx", 38, payload) or {}
        ret = resp.get("ret", -1)

        if ret == 110 or ret == RET_CAPTCHA_REQUIRED:
            raise CaptchaRequired()

        if ret == RET_OK:
            msg = f"✅ Đã đặt lệnh chế tạo thành công: {amount}x '{w_name}' (Xưởng ô {plot_id})"
            if notify:
                notify(msg)
            return True, 0, msg
        elif ret == 32:
            msg = f"⚠️ Không đủ tài nguyên (Gỗ/Đá/Sắt/Lúa) để chế tạo {amount} '{w_name}', hoãn sang chu kỳ sau"
            if notify:
                notify(msg)
            return False, 32, msg
        else:
            err_desc = CRAFT_ERROR_MESSAGES.get(ret, f"Mã lỗi máy chủ {ret}")
            msg = f"❌ Chế tạo '{w_name}' thất bại: {err_desc}"
            if notify:
                notify(msg)
            return False, ret, msg

