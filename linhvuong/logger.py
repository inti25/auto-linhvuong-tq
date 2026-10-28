"""Module cấu hình Logging tập trung cho Linh Vương.

Tuân thủ ADR-0015 và ADR-0030:
- Lưu vết log vào thư mục logs/, phân tách theo tài khoản: logs/bot_{username}_S{server_id}.log.
- Tự động xoay vòng với RotatingFileHandler (2MB/file, giữ 3 bản sao xoay vòng, tối đa ~6MB/tài khoản).
- Tự động thanh lý các tệp log lịch sử cũ quá 7 ngày với clean_old_logs().
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
import time
from typing import Optional

DEFAULT_LOG_DIR = Path("logs")
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_MAX_BYTES = 2 * 1024 * 1024  # 2MB/tệp theo ADR-0030
DEFAULT_BACKUP_COUNT = 3  # Giữ tối đa 3 bản sao (~6MB/tài khoản)
DEFAULT_MAX_AGE_DAYS = 7  # Tự động dọn dẹp nhật ký cũ quá 7 ngày

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


def clean_old_logs(
    log_dir: Optional[Path] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> int:
    """Quét và xóa các tệp nhật ký đã cũ quá max_age_days trong thư mục log.

    Tuân thủ ADR-0030:
    - Quét các tệp *.log và các bản sao xoay vòng *.log.* trong thư mục log_dir.
    - So sánh thời gian sửa đổi cuối cùng (st_mtime) với thời gian hiện tại.
    - Xóa an toàn với try/except để tránh gián đoạn nếu tệp đang bị tiến trình khác giữ khóa.
    - Trả về số lượng tệp đã được xóa thành công.
    """
    folder = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    if not folder.exists() or not folder.is_dir():
        return 0

    now = time.time()
    cutoff_seconds = max_age_days * 86400
    deleted_count = 0

    try:
        for f in folder.iterdir():
            if not f.is_file():
                continue
            # Chỉ xử lý các tệp log: đuôi .log hoặc có dạng .log.1, .log.2...
            if f.suffix == ".log" or ".log." in f.name:
                try:
                    if (now - f.stat().st_mtime) > cutoff_seconds:
                        f.unlink()
                        deleted_count += 1
                except Exception:
                    pass
    except Exception:
        pass

    return deleted_count


def setup_logger(
    username: str = "guest",
    server_id: int = 0,
    log_dir: Optional[Path] = None,
    debug: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    console: bool = True,
    clean_history_days: Optional[int] = DEFAULT_MAX_AGE_DAYS,
) -> logging.Logger:
    """Khởi tạo cấu hình logging tập trung cho thư viện `linhvuong`.

    Tuân thủ ADR-0015 và ADR-0030:
    - Tạo thư mục `logs/` nếu chưa tồn tại.
    - Tự động thanh lý các tệp nhật ký cũ hơn clean_history_days (mặc định 7 ngày).
    - Gắn RotatingFileHandler ghi vào `logs/bot_{username}_S{server_id}.log` (2MB/tệp, 3 bản sao).
    - Gắn SanitizingFilter lên toàn bộ handler.
    - Cấu hình cấp độ ghi log (DEBUG nếu debug=True, ngược lại INFO).
    """
    target_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    if clean_history_days is not None and clean_history_days > 0:
        clean_old_logs(target_dir, max_age_days=clean_history_days)

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
