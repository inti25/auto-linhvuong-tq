"""Mô-đun thông báo đa kênh (Desktop Toast, Sound, Telegram Bot).

Chịu trách nhiệm:
- Phát Windows Desktop Toast Notification native không phụ thuộc thư viện bên ngoài.
- Phát âm thanh chuông cảnh báo hệ thống (winsound.MessageBeep).
- Gửi tin nhắn cảnh báo tới Telegram Bot API khi có cấu hình bot_token và chat_id.
- Cơ chế chống lặp (Deduplication) để mỗi BOSS trên mỗi chiến trường chỉ báo 1 lần duy nhất.
- Chạy bất đồng bộ đa luồng (daemon thread) không gây nghẽn tiến trình tác chiến hoặc giao diện.
"""

import html
import json
import logging
import platform
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional, Set, Tuple

import requests

logger = logging.getLogger("linhvuong.notifications")
_ = platform.system()  # Warm platform uname cache before tests patch subprocess.Popen

# Bộ nhớ chống lặp: (battle_id, boss_position) -> đã thông báo
_notified_boss_keys: Set[Tuple[int, int]] = set()
_notified_system_keys: Set[Tuple[str, str]] = set()
_lock = threading.Lock()


def reset_notified_bosses() -> None:
    """Xóa bộ nhớ đệm chống lặp (phục vụ test suites hoặc khởi động lại phiên)."""
    with _lock:
        _notified_boss_keys.clear()
        _notified_system_keys.clear()


def reset_system_alert(account_key: str, event_type: Optional[str] = None) -> None:
    """Xóa trạng thái chống lặp cảnh báo hệ thống sau khi người dùng đã xử lý (ví dụ giải Captcha)."""
    with _lock:
        if event_type is None:
            for k in list(_notified_system_keys):
                if k[0] == account_key:
                    _notified_system_keys.discard(k)
        else:
            _notified_system_keys.discard((account_key, event_type))


@dataclass(init=False)
class NotificationConfig:
    desktop_enabled: bool = True
    sound_enabled: bool = True
    web_enabled: bool = True
    telegram_enabled: bool = False
    telegram_alert_captcha: bool = True
    telegram_alert_disconnect: bool = True
    attack_alert_enabled: bool = True
    attack_alert_pvp_only: bool = False
    attack_check_interval_minutes: int = 5
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @staticmethod
    def _parse_attack_interval(val: Any) -> int:
        try:
            iv = int(str(val).strip())
        except (ValueError, TypeError):
            return 5
        return max(1, min(60, iv))

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
        attack_alert_enabled: Optional[bool] = None,
        attack_alert_pvp_only: Optional[bool] = None,
        attack_check_interval_minutes: Optional[int] = None,
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
        self.attack_alert_enabled = True if attack_alert_enabled is None else bool(attack_alert_enabled)
        self.attack_alert_pvp_only = False if attack_alert_pvp_only is None else bool(attack_alert_pvp_only)
        self.attack_check_interval_minutes = (
            5 if attack_check_interval_minutes is None else self._parse_attack_interval(attack_check_interval_minutes)
        )

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
    def from_dict(cls, data: dict) -> "NotificationConfig":
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
            attack_alert_enabled=bool(data.get("attack_alert_enabled", True)),
            attack_alert_pvp_only=bool(data.get("attack_alert_pvp_only", False)),
            attack_check_interval_minutes=cls._parse_attack_interval(
                data.get("attack_check_interval_minutes", 5)
            ),
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
            "attack_alert_enabled": self.attack_alert_enabled,
            "attack_alert_pvp_only": self.attack_alert_pvp_only,
            "attack_check_interval_minutes": self.attack_check_interval_minutes,
            "notify_desktop_toast": self.desktop_enabled,
            "notify_sound": self.sound_enabled,
            "notify_web": self.web_enabled,
            "notify_telegram": self.telegram_enabled,
            "telegram_bot_token": self.telegram_bot_token,
            "telegram_chat_id": self.telegram_chat_id,
        }


def play_alert_sound() -> None:
    """Phát âm thanh chuông cảnh báo hệ thống qua winsound (Windows)."""
    if platform.system().lower() != "windows":
        return
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception as e:
        logger.debug(f"Không thể phát âm thanh cảnh báo: {e}")


def send_desktop_toast(title: str, message: str, sound: bool = True) -> bool:
    """Hiển thị Windows Desktop Toast Notification qua PowerShell Native."""
    if sound:
        play_alert_sound()

    if platform.system().lower() != "windows":
        logger.info(f"[{title}] {message}")
        return False

    # Làm sạch ký tự nháy kép hoặc xuống dòng để truyền an toàn vào PowerShell
    safe_title = title.replace('"', '""').replace("'", "''").replace("\r", " ").replace("\n", " ")
    safe_msg = message.replace('"', '""').replace("'", "''").replace("\r", " ").replace("\n", " ")

    ps_code = f"""
try {{
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName('text')
    $textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) | Out-Null
    $textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_msg}')) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('LinhVuong').Show($toast)
}} catch {{}}
"""
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_code],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        logger.debug(f"Lỗi gửi Windows Desktop Toast: {e}")
        return False


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    message: str,
    timeout: float = 6.0,
) -> tuple[bool, str]:
    """Gửi tin nhắn thông báo tới Telegram Bot."""
    token = bot_token.strip()
    cid = chat_id.strip()
    if not token or not cid:
        return False, "Thiếu Telegram Bot Token hoặc Chat ID"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return True, "Gửi tin nhắn Telegram thành công!"
        try:
            err_data = resp.json()
            desc = err_data.get("description", resp.text)
        except Exception:
            desc = resp.text
        return False, f"Telegram API lỗi (HTTP {resp.status_code}): {desc}"
    except requests.exceptions.Timeout:
        return False, "Hết thời gian chờ kết nối tới Telegram API (Timeout)"
    except Exception as e:
        return False, f"Không thể kết nối tới Telegram: {e}"


def dispatch_boss_alert(
    boss_name: str,
    position: int = 11,
    site: str = "Chiến trường",
    battle_id: int = 0,
    server_id: int = 0,
    map_coords: Optional[Tuple[int, int]] = None,
    config: Optional[NotificationConfig] = None,
    on_log: Optional[Callable[[str], None]] = None,
    bypass_dedup: bool = False,
    on_web_event: Optional[Callable[[dict], None]] = None,
    **kwargs,
) -> bool:
    """Điều phối thông báo BOSS đa kênh bất đồng bộ kèm cơ chế chống lặp (Deduplication)."""
    if "boss_position" in kwargs:
        position = kwargs["boss_position"]
    cfg = config or NotificationConfig()
    key = (battle_id, position)

    if not bypass_dedup and battle_id != 9999:
        with _lock:
            if key in _notified_boss_keys:
                return False  # Đã thông báo cho Boss này trên chiến trường này
            _notified_boss_keys.add(key)

    coords_str = f"({map_coords[0]}, {map_coords[1]})" if map_coords else ""
    srv = server_id if server_id > 0 else 53
    battle_url = f"http://sg{srv}.dipan.com/battle/{battle_id}"

    # Định dạng tin nhắn văn bản
    plain_title = f"🐉 PHÁT HIỆN BOSS [{boss_name}]!"
    plain_body = f"Ô {position} | {site} {coords_str}\nLink: {battle_url}"

    telegram_msg = (
        f"🐉 <b>[Linh Vương] PHÁT HIỆN BOSS CHIẾN TRƯỜNG!</b>\n"
        f"👑 <b>Boss:</b> {boss_name} (Vị trí: Ô {position})\n"
        f"🗺️ <b>Thế lực:</b> {site} {coords_str}\n"
        f"⚔️ <b>Chiến trường:</b> <a href=\"{battle_url}\">{battle_url}</a>\n"
        f"🛡️ <i>Bot đang chuyển thế thủ để giữ Boss an toàn!</i>"
    )

    if on_log:
        try:
            on_log(f"🔔 [THÔNG BÁO] Phát hiện BOSS [{boss_name}] tại vị trí {position} ({site})! Đang phát cảnh báo đa kênh...")
        except Exception:
            pass

    if on_web_event and cfg.web_enabled:
        try:
            on_web_event({
                "kind": "boss",
                "title": plain_title,
                "body": plain_body,
                "sound": cfg.sound_enabled,
                "battle_id": battle_id,
                "battle_url": battle_url,
            })
        except Exception:
            pass

    def _worker():
        # 1. Desktop Toast & Sound
        if cfg.desktop_enabled:
            send_desktop_toast(plain_title, plain_body, sound=cfg.sound_enabled)
        elif cfg.sound_enabled:
            play_alert_sound()

        # 2. Telegram Webhook
        if cfg.telegram_enabled and cfg.telegram_bot_token and cfg.telegram_chat_id:
            ok, res_msg = send_telegram_message(
                bot_token=cfg.telegram_bot_token,
                chat_id=cfg.telegram_chat_id,
                message=telegram_msg,
            )
            if not ok and on_log:
                try:
                    on_log(f"⚠️ [Telegram] {res_msg}")
                except Exception:
                    pass

    t = threading.Thread(target=_worker, name="BossNotificationWorker", daemon=True)
    t.start()
    return True


def dispatch_system_alert(
    event_type: str,
    account_key: str,
    title: str,
    message: str,
    config: Optional[NotificationConfig] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_web_event: Optional[Callable[[dict], None]] = None,
    bypass_dedup: bool = False,
) -> bool:
    """Phát cảnh báo sự kiện hệ thống (CaptchaRequired, mất kết nối/proxy) qua Web & Telegram."""
    cfg = config or NotificationConfig()
    if not bypass_dedup:
        dedup_key = (account_key, event_type)
        with _lock:
            if dedup_key in _notified_system_keys:
                return False
            _notified_system_keys.add(dedup_key)

    if on_web_event and cfg.web_enabled:
        try:
            on_web_event({
                "kind": event_type,
                "account_key": account_key,
                "title": title,
                "body": message,
                "sound": cfg.sound_enabled,
            })
        except Exception:
            pass

    should_telegram = (
        cfg.telegram_enabled
        and cfg.telegram_bot_token
        and cfg.telegram_chat_id
        and (
            (event_type == "captcha" and cfg.telegram_alert_captcha)
            or (event_type == "disconnect" and cfg.telegram_alert_disconnect)
            or event_type not in ("captcha", "disconnect")
        )
    )
    if not should_telegram:
        return True

    icon = "⚠️" if event_type == "captcha" else "🔴"
    telegram_msg = (
        f"{icon} <b>[Linh Vương] {title}</b>\n"
        f"👤 <b>Tài khoản:</b> {account_key}\n"
        f"📝 {message}"
    )

    def _worker():
        ok, res_msg = send_telegram_message(
            bot_token=cfg.telegram_bot_token,
            chat_id=cfg.telegram_chat_id,
            message=telegram_msg,
        )
        if not ok and on_log:
            try:
                on_log(f"⚠️ [Telegram] {res_msg}")
            except Exception:
                pass

    threading.Thread(target=_worker, name="SystemNotificationWorker", daemon=True).start()
    return True


_VN_TZ = timezone(timedelta(hours=7))


def format_duration_hms(seconds: int) -> str:
    """Định dạng thời lượng (giây) thành HH:MM:SS (hoặc MM:SS nếu dưới 1 giờ)."""
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _format_attack_forces(attack: Any) -> str:
    gens = list(getattr(attack, "generals", None) or [])
    gen_names = [str(g[1] or f"Tướng #{g[0]}").strip() for g in gens if g]
    parts: list[str] = []
    if gen_names:
        parts.append(", ".join(gen_names))
    inf = int(getattr(attack, "infantry", -1))
    cav = int(getattr(attack, "cavalry", -1))
    arc = int(getattr(attack, "archers", -1))
    sie = int(getattr(attack, "siege", -1))
    if any(v >= 0 for v in (inf, cav, arc, sie)):
        fmt = lambda v: f"{v:,}" if v >= 0 else "?"
        parts.append(f"Bộ {fmt(inf)} / Kỵ {fmt(cav)} / Cung {fmt(arc)} / Xe {fmt(sie)}")
    return " | ".join(parts) if parts else "Chưa lộ"


def dispatch_attack_alert(
    *,
    account_key: str,
    server_id: int = 0,
    stage: str = "initial",
    attack: Optional[Any] = None,
    battle: Optional[Any] = None,
    config: Optional[NotificationConfig] = None,
    on_log: Optional[Callable[[str], None]] = None,
    on_web_event: Optional[Callable[[dict], None]] = None,
) -> bool:
    """Điều phối cảnh báo quân tấn công (initial / urgent / battle) qua Thông Báo Đa Kênh."""
    cfg = config or NotificationConfig()
    srv = int(server_id) if int(server_id or 0) > 0 else 53
    acc_label = account_key or f"S{srv}"

    if stage == "battle" and battle is not None:
        title = "⚔️ ĐANG GIAO CHIẾN TẠI CĂN CỨ!"
        b_prefix = "[Trại]" if getattr(battle, "target_is_camp", False) else "[Thành]"
        b_name = getattr(battle, "target_base_name", "") or f"ID {getattr(battle, 'target_base_id', 0)}"
        bx = int(getattr(battle, "target_x", 0) or 0)
        by = int(getattr(battle, "target_y", 0) or 0)
        b_coords = f" ({bx}, {by})" if (bx or by) else ""
        target_label = f"{b_prefix} {b_name}{b_coords}"

        attackers = [str(x).strip() for x in (getattr(battle, "attackers", None) or []) if str(x).strip()]
        attacker_label = ", ".join(attackers) if attackers else "Địch đang giao chiến"
        next_left = int(getattr(battle, "next_round_left", 0) or 0)
        battle_id = int(getattr(battle, "battle_id", 0) or 0)
        battle_url = getattr(battle, "battle_url", "") or f"http://sg{srv}.dipan.com/battle/{battle_id}"

        plain_body = (
            f"Tài khoản: {acc_label} | Căn cứ: {target_label}\n"
            f"Địch: {attacker_label} | Hiệp tiếp theo: {format_duration_hms(next_left)}\n"
            f"Link: {battle_url}"
        )
        telegram_msg = (
            f"⚔️ <b>[Linh Vương] ĐANG GIAO CHIẾN TẠI CĂN CỨ!</b>\n"
            f"👤 <b>Tài khoản:</b> {html.escape(acc_label)}\n"
            f"🏰 <b>Căn cứ:</b> {html.escape(target_label)}\n"
            f"🎯 <b>Địch:</b> {html.escape(attacker_label)}\n"
            f"⏱️ <b>Hiệp tiếp theo:</b> {format_duration_hms(next_left)}\n"
            f"🔗 <b>Chiến trường:</b> <a href=\"{html.escape(battle_url)}\">{html.escape(battle_url)}</a>"
        )
        log_line = (
            f"⚔️ [QUÂN TẤN CÔNG] {target_label} đang giao chiến ({attacker_label})! "
            f"Chiến trường: {battle_url}"
        )
    elif attack is not None:
        title = (
            "🚨 KHẨN CẤP: QUÂN ĐỊCH SẮP TỚI (≤ 5 PHÚT)!"
            if stage == "urgent"
            else "🚨 CẢNH BÁO QUÂN TẤN CÔNG!"
        )
        b_prefix = "[Trại]" if getattr(attack, "target_is_camp", False) else "[Thành]"
        b_name = getattr(attack, "target_base_name", "") or f"ID {getattr(attack, 'target_base_id', 0)}"
        bx = int(getattr(attack, "target_x", 0) or 0)
        by = int(getattr(attack, "target_y", 0) or 0)
        b_coords = f" ({bx}, {by})" if (bx or by) else ""
        target_label = f"{b_prefix} {b_name}{b_coords}"

        is_pvp = bool(getattr(attack, "is_pvp", False))
        src_name = str(getattr(attack, "source_name", "") or "Quân địch")
        sx = int(getattr(attack, "source_x", 0) or 0)
        sy = int(getattr(attack, "source_y", 0) or 0)
        atk_name = str(getattr(attack, "attacker_name", "") or "").strip()
        if is_pvp and atk_name:
            attacker_label = f"[PvP] {atk_name} — {src_name} ({sx}, {sy})"
        elif is_pvp:
            attacker_label = f"[PvP] {src_name} ({sx}, {sy})"
        else:
            attacker_label = f"[NPC] {src_name} ({sx}, {sy})"

        forces_label = _format_attack_forces(attack)
        now_ep = time.time()
        rem = int(attack.current_remaining_seconds(now_epoch=now_ep)) if hasattr(attack, "current_remaining_seconds") else int(getattr(attack, "remaining_seconds", 0) or 0)
        arr_ep = float(getattr(attack, "arrival_epoch", 0.0) or 0.0) or (now_ep + rem)
        eta_str = datetime.fromtimestamp(arr_ep, tz=_VN_TZ).strftime("%H:%M:%S")
        time_label = f"Còn {format_duration_hms(rem)} (dự kiến ~{eta_str})"
        battle_url = ""

        plain_body = (
            f"Tài khoản: {acc_label} | Căn cứ: {target_label}\n"
            f"Kẻ tấn công: {attacker_label}\n"
            f"Quân lực: {forces_label}\n"
            f"Thời gian: {time_label}"
        )
        header_tg = (
            "🚨 <b>[Linh Vương] KHẨN CẤP: QUÂN ĐỊCH SẮP TỚI!</b>"
            if stage == "urgent"
            else "🚨 <b>[Linh Vương] CẢNH BÁO QUÂN TẤN CÔNG!</b>"
        )
        telegram_msg = (
            f"{header_tg}\n"
            f"👤 <b>Tài khoản:</b> {html.escape(acc_label)}\n"
            f"🏰 <b>Căn cứ bị đánh:</b> {html.escape(target_label)}\n"
            f"🏴 <b>Kẻ tấn công:</b> {html.escape(attacker_label)}\n"
            f"🪖 <b>Quân lực:</b> {html.escape(forces_label)}\n"
            f"⏳ <b>Thời gian:</b> {html.escape(time_label)}"
        )
        tag = "KHẨN CẤP" if stage == "urgent" else "CẢNH BÁO"
        log_line = (
            f"🚨 [{tag} QUÂN TẤN CÔNG] {attacker_label} đang tiến đánh {target_label} | "
            f"{time_label} | Quân lực: {forces_label}"
        )
    else:
        return False

    if on_log:
        try:
            on_log(log_line)
        except Exception:
            pass

    if on_web_event and cfg.web_enabled:
        try:
            on_web_event({
                "kind": "attack",
                "stage": stage,
                "account_key": acc_label,
                "title": title,
                "body": plain_body,
                "sound": cfg.sound_enabled,
                "battle_url": battle_url,
            })
        except Exception:
            pass

    def _worker():
        if cfg.desktop_enabled:
            send_desktop_toast(title, plain_body, sound=cfg.sound_enabled)
        elif cfg.sound_enabled:
            play_alert_sound()

        if cfg.telegram_enabled and cfg.telegram_bot_token and cfg.telegram_chat_id:
            ok, res_msg = send_telegram_message(
                bot_token=cfg.telegram_bot_token,
                chat_id=cfg.telegram_chat_id,
                message=telegram_msg,
            )
            if not ok and on_log:
                try:
                    on_log(f"⚠️ [Telegram] {res_msg}")
                except Exception:
                    pass

    threading.Thread(target=_worker, name="AttackNotificationWorker", daemon=True).start()
    return True
