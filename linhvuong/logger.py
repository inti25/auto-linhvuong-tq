"""Module cấu hình Logging tập trung cho Linh Vương.

Tuân thủ ADR-0015:
- Lưu vết log vào thư mục logs/, phân tách theo tài khoản: logs/bot_{username}_S{server_id}.log.
- Tự động xoay vòng với RotatingFileHandler (10MB/file, giữ 5 bản sao xoay vòng).
- Bộ lọc SanitizingFilter tự động che mờ mật khẩu game, mật khẩu proxy và token nhạy cảm.
- Định dạng chuẩn thời gian YYYY-MM-DD HH:MM:SS kèm tên module và level.
- Hàm open_logs_directory() mở thư mục log trong trình quản lý tệp tin của hệ điều hành.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Optional

DEFAULT_LOG_DIR = Path("logs")
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Regex nhận diện các thông tin nhạy cảm cần che mờ
SENSITIVE_PATTERNS = [
    re.compile(r"(pass(?:word)?\s*=\s*)([^\s&,;\"']+)", re.IGNORECASE),
    re.compile(r"(proxy_pass\s*=\s*)([^\s&,;\"']+)", re.IGNORECASE),
    re.compile(r"((?:https?|socks5)://[^:]+:)([^@]+)(@)", re.IGNORECASE),
    re.compile(r"('password':\s*')([^']+)(')", re.IGNORECASE),
    re.compile(r"(\"password\":\s*\")([^\"]+)(\")", re.IGNORECASE),
]


class SanitizingFilter(logging.Filter):
    """Bộ lọc tự động che mờ các trường mật khẩu và tài khoản proxy trong thông điệp log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._sanitize_value(v) for v in record.args)
        return True

    @classmethod
    def sanitize(cls, text: str) -> str:
        res = text
        for pat in SENSITIVE_PATTERNS:
            if pat.groups == 3:
                res = pat.sub(r"\g<1>***\g<3>", res)
            elif pat.groups == 2:
                res = pat.sub(r"\g<1>***", res)
        return res

    @classmethod
    def _sanitize_value(cls, val):
        if isinstance(val, str):
            return cls.sanitize(val)
        return val


def get_log_file_path(username: str, server_id: int, log_dir: Optional[Path] = None) -> Path:
    """Trả về đường dẫn tệp log định danh theo tài khoản và máy chủ."""
    folder = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    clean_user = re.sub(r"[^\w\-.]", "_", username) if username else "unknown"
    return folder / f"bot_{clean_user}_S{server_id}.log"


def setup_logger(
    username: str = "guest",
    server_id: int = 0,
    log_dir: Optional[Path] = None,
    debug: bool = False,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console: bool = True,
) -> logging.Logger:
    """Khởi tạo cấu hình logging tập trung cho thư viện `linhvuong`.

    - Tạo thư mục `logs/` nếu chưa tồn tại.
    - Gắn RotatingFileHandler ghi vào `logs/bot_{username}_S{server_id}.log`.
    - Gắn SanitizingFilter lên toàn bộ handler.
    - Cấu hình cấp độ ghi log (DEBUG nếu debug=True, ngược lại INFO).
    """
    target_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    log_file = get_log_file_path(username, server_id, target_dir)
    root_logger = logging.getLogger("linhvuong")
    level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(level)

    # Tránh gắn handler lặp lại nếu gọi setup_logger nhiều lần
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    sanitizer = SanitizingFilter()
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # 1. File Handler xoay vòng
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sanitizer)
    root_logger.addHandler(file_handler)

    # 2. Console Handler (nếu được yêu cầu)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(sanitizer)
        root_logger.addHandler(console_handler)

    root_logger.info(
        f"Đã khởi tạo hệ thống logging: {log_file} (Level: {'DEBUG' if debug else 'INFO'})"
    )
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Lấy logger theo phân hệ con (ví dụ: `linhvuong.gateway`, `linhvuong.tasks.building`)."""
    if not name.startswith("linhvuong"):
        name = f"linhvuong.{name}"
    return logging.getLogger(name)


def open_logs_directory(log_dir: Optional[Path] = None) -> bool:
    """Mở thư mục log trong trình duyệt tệp của hệ điều hành (Explorer trên Windows)."""
    folder = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    folder.mkdir(parents=True, exist_ok=True)
    abs_path = folder.resolve()
    try:
        if sys.platform == "win32":
            os.startfile(str(abs_path))
            return True
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(abs_path)])
            return True
        else:
            subprocess.Popen(["xdg-open", str(abs_path)])
            return True
    except Exception as e:
        get_logger("system").warning(f"Không thể mở thư mục log {abs_path}: {e}")
        return False
