"""Mô-đun thông báo đa kênh (Desktop Toast, Sound, Telegram Bot).

Chịu trách nhiệm:
- Phát Windows Desktop Toast Notification native không phụ thuộc thư viện bên ngoài.
- Phát âm thanh chuông cảnh báo hệ thống (winsound.MessageBeep).
- Gửi tin nhắn cảnh báo tới Telegram Bot API khi có cấu hình bot_token và chat_id.
- Cơ chế chống lặp (Deduplication) để mỗi BOSS trên mỗi chiến trường chỉ báo 1 lần duy nhất.
- Chạy bất đồng bộ đa luồng (daemon thread) không gây nghẽn tiến trình tác chiến hoặc giao diện.
"""

import json
import logging
import platform
import subprocess
import threading
from dataclasses import dataclass
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
