"""Quản lý thư mục dữ liệu (LINHVUONG_DATA_DIR) và khóa tiến trình chống xung đột."""

import os
from pathlib import Path
from typing import Optional, Union

DATA_DIR_ENV = "LINHVUONG_DATA_DIR"
LOCK_FILENAME = ".linhvuong.lock"


class DataDirLockedError(RuntimeError):
    """Ngoại lệ khi một tiến trình khác đang giữ khóa trên cùng thư mục dữ liệu."""


def get_data_dir(override: Optional[Union[str, Path]] = None) -> Path:
    """Trả về thư mục gốc lưu dữ liệu cấu hình, hồ sơ và nhật ký.

    Ưu tiên tham số `override`, kế đến biến môi trường `LINHVUONG_DATA_DIR`,
    và mặc định là `.` để bảo toàn 100% tương thích ngược.
    """
    if override is not None and str(override).strip():
        return Path(str(override).strip())
    env_val = os.environ.get(DATA_DIR_ENV, "").strip()
    if env_val:
        return Path(env_val)
    return Path(".")


def ensure_data_dir(data_dir: Optional[Union[str, Path]] = None) -> Path:
    """Đảm bảo thư mục dữ liệu tồn tại trên đĩa và trả về đối tượng Path."""
    path = get_data_dir(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path(data_dir: Optional[Union[str, Path]] = None) -> Path:
    """Đường dẫn tệp danh bạ tài khoản (`gui_settings.json`)."""
    return get_data_dir(data_dir) / "gui_settings.json"


def vault_path(data_dir: Optional[Union[str, Path]] = None) -> Path:
    """Đường dẫn tệp Két Mật Khẩu Mã Hóa (`vault.enc`)."""
    return get_data_dir(data_dir) / "vault.enc"


def vault_key_path(data_dir: Optional[Union[str, Path]] = None) -> Path:
    """Đường dẫn tệp khóa chủ tự sinh cho Két Mật Khẩu Mã Hóa (`.vault.key`)."""
    return get_data_dir(data_dir) / ".vault.key"


def web_auth_path(data_dir: Optional[Union[str, Path]] = None) -> Path:
    """Đường dẫn tệp cấu hình Phiên Quản Trị Web (`web_auth.json`)."""
    return get_data_dir(data_dir) / "web_auth.json"


def runtime_state_path(data_dir: Optional[Union[str, Path]] = None) -> Path:
    """Đường dẫn tệp lưu trạng thái tác vụ đang chạy để phục hồi sau khởi động lại."""
    return get_data_dir(data_dir) / "runtime_state.json"


def logs_dir(data_dir: Optional[Union[str, Path]] = None) -> Path:
    """Đường dẫn thư mục nhật ký (`logs/`)."""
    return get_data_dir(data_dir) / "logs"


def atomic_write_text(target: Path, content: str, mode: Optional[int] = None) -> Path:
    """Ghi văn bản nguyên tử (atomic write-and-replace) qua tệp tạm `.tmp`."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_target = target.with_suffix(f"{target.suffix}.tmp.{os.getpid()}")
    try:
        tmp_target.write_text(content, encoding="utf-8")
        if mode is not None and os.name == "posix":
            try:
                os.chmod(tmp_target, mode)
            except OSError:
                pass
        os.replace(tmp_target, target)
        if mode is not None and os.name == "posix":
            try:
                os.chmod(target, mode)
            except OSError:
                pass
    except Exception:
        if tmp_target.exists():
            try:
                tmp_target.unlink()
            except OSError:
                pass
        raise
    return target


class DataDirLock:
    """Khóa tiến trình trên `LINHVUONG_DATA_DIR` nhằm ngăn chạy trùng hai bot cùng dữ liệu."""

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        self.data_dir = get_data_dir(data_dir)
        self.lock_file = self.data_dir / LOCK_FILENAME
        self._fh = None
        self._acquired = False

    @property
    def is_acquired(self) -> bool:
        return self._acquired

    def acquire(self) -> None:
        if self._acquired:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        fh = open(self.lock_file, "a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                if self.lock_file.stat().st_size == 0:
                    fh.write(" ")
                    fh.flush()
                fh.seek(0)
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise DataDirLockedError(self._locked_message()) from exc
            else:
                import fcntl

                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise DataDirLockedError(self._locked_message()) from exc

            fh.seek(0)
            fh.truncate()
            fh.write(f"pid={os.getpid()}\n")
            fh.flush()
            self._fh = fh
            self._acquired = True
        except Exception:
            try:
                fh.close()
            except Exception:
                pass
            raise

    def _locked_message(self) -> str:
        holder = ""
        try:
            content = self.lock_file.read_text(encoding="utf-8").strip()
            if content:
                holder = f" ({content})"
        except OSError:
            pass
        return (
            f"Thư mục dữ liệu '{self.data_dir}' đang được sử dụng bởi một tiến trình khác{holder}. "
            "Không thể chạy đồng thời hai tiến trình trên cùng LINHVUONG_DATA_DIR."
        )

    def release(self) -> None:
        if not self._acquired or self._fh is None:
            return
        fh = self._fh
        self._fh = None
        self._acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            try:
                fh.close()
            except Exception:
                pass

    def __enter__(self) -> "DataDirLock":
        self.acquire()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()
