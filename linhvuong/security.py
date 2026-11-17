"""Bảo mật cho Bảng Điều Khiển Web: Phiên Quản Trị Web & Két Mật Khẩu Mã Hóa (ADR-0039)."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .paths import atomic_write_text, get_data_dir, vault_path, web_auth_path

VAULT_KEY_ENV = "LINHVUONG_VAULT_KEY"
WEB_USERNAME_ENV = "LINHVUONG_WEB_USERNAME"
WEB_PASSWORD_ENV = "LINHVUONG_WEB_PASSWORD"
WEB_SECRET_ENV = "LINHVUONG_WEB_SECRET"

DEFAULT_WEB_USERNAME = "admin"
SESSION_COOKIE_NAME = "lv_admin_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600


class VaultError(Exception):
    """Lỗi khi mở khóa hoặc giải mã Két Mật Khẩu Mã Hóa."""


def is_loopback_host(host: str) -> bool:
    """Kiểm tra địa chỉ bind có phải loopback nội bộ hay không."""
    h = (host or "").strip().lower()
    return h in {"127.0.0.1", "localhost", "::1"}


def _hash_password_pbkdf2(password: str, salt: Optional[bytes] = None, iterations: int = 200_000) -> dict:
    raw_salt = salt if salt is not None else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, iterations)
    return {
        "scheme": "pbkdf2_sha256",
        "iterations": iterations,
        "salt": base64.b64encode(raw_salt).decode("ascii"),
        "hash": base64.b64encode(dk).decode("ascii"),
    }


def _verify_password_pbkdf2(password: str, record: dict) -> bool:
    try:
        if record.get("scheme") != "pbkdf2_sha256":
            return False
        iterations = int(record["iterations"])
        salt = base64.b64decode(record["salt"])
        expected = base64.b64decode(record["hash"])
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _derive_fernet_key(master_key: str, salt: bytes) -> bytes:
    """Sinh khóa Fernet 32-byte URL-safe base64 từ `LINHVUONG_VAULT_KEY`."""
    dk = hashlib.pbkdf2_hmac("sha256", master_key.encode("utf-8"), salt, 200_000, dklen=32)
    return base64.urlsafe_b64encode(dk)


class CredentialVault:
    """Két Mật Khẩu Mã Hóa tùy chọn lưu mật khẩu tài khoản game phục vụ khôi phục sau reboot."""

    def __init__(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        master_key: Optional[str] = None,
    ):
        self.data_dir = get_data_dir(data_dir)
        self.path = vault_path(self.data_dir)
        self._master_key = (
            master_key
            if master_key is not None
            else os.environ.get(VAULT_KEY_ENV, "")
        ).strip()

    def is_unlocked(self) -> bool:
        """Trả về True khi đã cung cấp khóa chủ `LINHVUONG_VAULT_KEY`."""
        return bool(self._master_key)

    def has_vault_file(self) -> bool:
        return self.path.exists()

    def _get_fernet_cls(self):
        try:
            from cryptography.fernet import Fernet, InvalidToken
            return Fernet, InvalidToken
        except ImportError as exc:
            raise VaultError(
                "Thiếu thư viện 'cryptography' để sử dụng Két Mật Khẩu Mã Hóa. "
                "Hãy cài đặt bằng: pip install -e '.[web]'"
            ) from exc

    def _load_raw_entries(self) -> dict[str, dict]:
        if not self.is_unlocked():
            raise VaultError(
                f"Két Mật Khẩu Mã Hóa chưa được mở khóa (thiếu biến môi trường {VAULT_KEY_ENV})."
            )
        if not self.path.exists():
            return {}

        Fernet, InvalidToken = self._get_fernet_cls()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            salt = base64.b64decode(payload["salt"])
            token = payload["ciphertext"].encode("ascii")
        except Exception as exc:
            raise VaultError(f"Tệp Két Mật Khẩu Mã Hóa bị hỏng định dạng: {exc}") from exc

        key = _derive_fernet_key(self._master_key, salt)
        try:
            decrypted = Fernet(key).decrypt(token)
            data = json.loads(decrypted.decode("utf-8"))
        except InvalidToken as exc:
            raise VaultError(
                f"Không thể giải mã Két Mật Khẩu Mã Hóa — khóa {VAULT_KEY_ENV} không khớp."
            ) from exc
        except Exception as exc:
            raise VaultError(f"Lỗi đọc Két Mật Khẩu Mã Hóa: {exc}") from exc

        accounts = data.get("accounts", {})
        return dict(accounts) if isinstance(accounts, dict) else {}

    def _save_raw_entries(self, entries: dict[str, dict]) -> None:
        if not self.is_unlocked():
            raise VaultError(
                f"Két Mật Khẩu Mã Hóa chưa được mở khóa (thiếu biến môi trường {VAULT_KEY_ENV})."
            )
        Fernet, _ = self._get_fernet_cls()
        salt = secrets.token_bytes(16)
        key = _derive_fernet_key(self._master_key, salt)
        plaintext = json.dumps({"version": 1, "accounts": entries}, ensure_ascii=False).encode("utf-8")
        ciphertext = Fernet(key).encrypt(plaintext).decode("ascii")
        wrapper = {
            "version": 1,
            "kdf": "pbkdf2_sha256",
            "salt": base64.b64encode(salt).decode("ascii"),
            "ciphertext": ciphertext,
        }
        atomic_write_text(self.path, json.dumps(wrapper, indent=2), mode=0o600)

    def list_saved_keys(self) -> list[str]:
        if not self.is_unlocked() or not self.path.exists():
            return []
        try:
            return list(self._load_raw_entries().keys())
        except VaultError:
            return []

    def get_entry(self, account_key: str) -> Optional[dict]:
        if not self.is_unlocked() or not self.path.exists():
            return None
        entries = self._load_raw_entries()
        entry = entries.get(account_key)
        return dict(entry) if isinstance(entry, dict) else None

    def get_password(self, account_key: str) -> str:
        entry = self.get_entry(account_key)
        return str(entry.get("password", "")) if entry else ""

    def set_entry(self, account_key: str, password: str, auto_resume: bool = True) -> None:
        entries = self._load_raw_entries()
        entries[account_key] = {
            "password": password,
            "auto_resume": bool(auto_resume),
            "updated_at": int(time.time()),
        }
        self._save_raw_entries(entries)

    def remove_entry(self, account_key: str) -> None:
        if not self.is_unlocked() or not self.path.exists():
            return
        entries = self._load_raw_entries()
        if account_key in entries:
            entries.pop(account_key, None)
            self._save_raw_entries(entries)

    def rename_entry(self, old_key: str, new_key: str) -> None:
        if old_key == new_key or not self.is_unlocked() or not self.path.exists():
            return
        entries = self._load_raw_entries()
        if old_key in entries:
            entries[new_key] = entries.pop(old_key)
            self._save_raw_entries(entries)


@dataclass
class AuthStartupInfo:
    auth_enabled: bool
    username: str
    generated_password: Optional[str] = None


class WebAdminAuth:
    """Quản lý xác thực Phiên Quản Trị Web (Single-Admin) theo ADR-0039."""

    def __init__(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        host: str = "127.0.0.1",
        allow_no_auth: bool = False,
        env_username: Optional[str] = None,
        env_password: Optional[str] = None,
        session_secret: Optional[str] = None,
    ):
        self.data_dir = get_data_dir(data_dir)
        self.path = web_auth_path(self.data_dir)
        self.host = host
        self._env_username = (
            env_username if env_username is not None else os.environ.get(WEB_USERNAME_ENV, "")
        ).strip()
        self._env_password = (
            env_password if env_password is not None else os.environ.get(WEB_PASSWORD_ENV, "")
        )
        self._env_secret = (
            session_secret if session_secret is not None else os.environ.get(WEB_SECRET_ENV, "")
        ).strip()

        # Chỉ cho phép tắt auth khi chạy thuần loopback (127.0.0.1 / localhost / ::1)
        self.auth_enabled = not (allow_no_auth and is_loopback_host(host))
        self.username = self._env_username or DEFAULT_WEB_USERNAME
        self._password_record: Optional[dict] = None
        self._secret_key: bytes = b""
        self.generated_password: Optional[str] = None

        self._initialize()

    def _initialize(self) -> None:
        stored = {}
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                stored = {}

        if not self._env_username and isinstance(stored.get("username"), str) and stored["username"].strip():
            self.username = stored["username"].strip()

        secret_str = self._env_secret or str(stored.get("session_secret", "") or "")
        need_save = False
        if not secret_str:
            secret_str = secrets.token_urlsafe(32)
            need_save = True
        self._secret_key = secret_str.encode("utf-8")

        if not self.auth_enabled:
            if need_save:
                self._persist_auth_file(stored.get("password_record"), secret_str)
            return

        if self._env_password:
            self._password_record = _hash_password_pbkdf2(self._env_password)
        elif isinstance(stored.get("password_record"), dict):
            self._password_record = stored["password_record"]
        else:
            # Tự sinh mật khẩu ngẫu nhiên an toàn cho lần khởi động đầu tiên
            gen_pwd = secrets.token_urlsafe(14)
            self.generated_password = gen_pwd
            self._password_record = _hash_password_pbkdf2(gen_pwd)
            need_save = True

        if need_save and not self._env_password:
            self._persist_auth_file(self._password_record, secret_str)
        elif need_save:
            self._persist_auth_file(stored.get("password_record"), secret_str)

    def _persist_auth_file(self, password_record: Optional[dict], secret_str: str) -> None:
        data = {
            "version": 1,
            "username": self.username,
            "session_secret": secret_str,
        }
        if password_record:
            data["password_record"] = password_record
        atomic_write_text(self.path, json.dumps(data, indent=2), mode=0o600)

    def startup_info(self) -> AuthStartupInfo:
        return AuthStartupInfo(
            auth_enabled=self.auth_enabled,
            username=self.username,
            generated_password=self.generated_password,
        )

    def verify_credentials(self, username: str, password: str) -> bool:
        if not self.auth_enabled:
            return True
        if (username or "").strip() != self.username:
            return False
        if not self._password_record:
            return False
        return _verify_password_pbkdf2(password or "", self._password_record)

    def change_password(self, new_password: str, new_username: Optional[str] = None) -> None:
        if not new_password or len(new_password) < 6:
            raise ValueError("Mật khẩu quản trị Web phải có ít nhất 6 ký tự.")
        if new_username and new_username.strip():
            self.username = new_username.strip()
        self._password_record = _hash_password_pbkdf2(new_password)
        self.generated_password = None
        self._persist_auth_file(self._password_record, self._secret_key.decode("utf-8"))

    def create_session_token(self, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
        exp = int(time.time()) + ttl_seconds
        nonce = secrets.token_hex(8)
        payload = f"{self.username}|{exp}|{nonce}"
        sig = hmac.new(self._secret_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        raw = f"{payload}|{sig}"
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    def verify_session_token(self, token: Optional[str]) -> bool:
        if not self.auth_enabled:
            return True
        if not token:
            return False
        try:
            raw_bytes = base64.urlsafe_b64decode(token.encode("ascii"))
            if base64.urlsafe_b64encode(raw_bytes).decode("ascii") != token:
                return False
            decoded = raw_bytes.decode("utf-8")
            user, exp_str, nonce, sig = decoded.split("|", 3)
            if user != self.username:
                return False
            if int(exp_str) < int(time.time()):
                return False
            payload = f"{user}|{exp_str}|{nonce}"
            expected = hmac.new(self._secret_key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, expected)
        except Exception:
            return False
