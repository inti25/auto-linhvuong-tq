"""Kiểm thử quản lý thư mục dữ liệu (LINHVUONG_DATA_DIR), DataDirLock, Vault và WebAdminAuth."""

import pytest

from linhvuong.logger import get_log_file_path, list_log_files, read_log_tail
from linhvuong.paths import (
    DataDirLock,
    DataDirLockedError,
    get_data_dir,
    logs_dir,
    settings_path,
)
from linhvuong.profile import ProfileStore
from linhvuong.security import CredentialVault, VaultError, WebAdminAuth, is_loopback_host


def test_data_dir_resolution(tmp_path, monkeypatch):
    monkeypatch.delenv("LINHVUONG_DATA_DIR", raising=False)
    assert str(get_data_dir()) == "."

    monkeypatch.setenv("LINHVUONG_DATA_DIR", str(tmp_path))
    assert get_data_dir() == tmp_path
    assert settings_path() == tmp_path / "gui_settings.json"
    assert logs_dir() == tmp_path / "logs"
    assert get_log_file_path("user1", 53) == tmp_path / "logs" / "bot_user1_S53.log"
    assert ProfileStore.resolve_profile_path(username="user1", server_id=53) == tmp_path / "auto_profile_user1_53.json"


def test_data_dir_lock_prevents_concurrent_access(tmp_path):
    lock1 = DataDirLock(tmp_path)
    lock2 = DataDirLock(tmp_path)
    lock1.acquire()
    assert lock1.is_acquired
    with pytest.raises(DataDirLockedError):
        lock2.acquire()
    lock1.release()
    assert not lock1.is_acquired

    with DataDirLock(tmp_path) as lock3:
        assert lock3.is_acquired


def test_credential_vault_encrypt_decrypt_and_wrong_key(tmp_path):
    vault_locked = CredentialVault(data_dir=tmp_path, master_key="")
    assert not vault_locked.is_unlocked()
    with pytest.raises(VaultError):
        vault_locked.set_entry("u1 @ S53", "secret123")

    vault = CredentialVault(data_dir=tmp_path, master_key="super-secret-master-key")
    assert vault.is_unlocked()
    vault.set_entry("u1 @ S53", "game_pass_!@#", auto_resume=True)
    assert vault.path.exists()
    raw_text = vault.path.read_text(encoding="utf-8")
    assert "game_pass_!@#" not in raw_text

    vault_reopened = CredentialVault(data_dir=tmp_path, master_key="super-secret-master-key")
    assert vault_reopened.get_password("u1 @ S53") == "game_pass_!@#"
    assert vault_reopened.list_saved_keys() == ["u1 @ S53"]

    vault_reopened.rename_entry("u1 @ S53", "u1 @ S54")
    assert vault_reopened.get_password("u1 @ S54") == "game_pass_!@#"
    assert vault_reopened.get_password("u1 @ S53") == ""

    vault_wrong = CredentialVault(data_dir=tmp_path, master_key="wrong-key")
    with pytest.raises(VaultError):
        vault_wrong.get_password("u1 @ S54")

    vault_reopened.remove_entry("u1 @ S54")
    assert vault_reopened.list_saved_keys() == []


def test_web_admin_auth_enforcement_and_tokens(tmp_path):
    assert is_loopback_host("127.0.0.1")
    assert is_loopback_host("localhost")
    assert not is_loopback_host("0.0.0.0")

    # Không thể tắt auth khi bind 0.0.0.0 (ADR-0039)
    auth_public = WebAdminAuth(data_dir=tmp_path, host="0.0.0.0", allow_no_auth=True)
    assert auth_public.auth_enabled is True
    info = auth_public.startup_info()
    assert info.generated_password is not None
    assert auth_public.verify_credentials("admin", info.generated_password)
    assert not auth_public.verify_credentials("admin", "wrong")

    token = auth_public.create_session_token()
    assert auth_public.verify_session_token(token)
    assert not auth_public.verify_session_token(token + "tamper")
    assert not auth_public.verify_session_token("")

    auth_public.change_password("new_strong_pass", "operator")
    assert auth_public.verify_credentials("operator", "new_strong_pass")
    assert not auth_public.verify_credentials("admin", info.generated_password)

    # Cho phép tắt auth trên 127.0.0.1
    auth_local = WebAdminAuth(data_dir=tmp_path, host="127.0.0.1", allow_no_auth=True)
    assert auth_local.auth_enabled is False
    assert auth_local.verify_session_token(None)


def test_log_viewer_helpers_and_path_traversal_guard(tmp_path):
    ldir = tmp_path / "logs"
    ldir.mkdir()
    f = ldir / "bot_acc1_S53.log"
    f.write_text("line1\nline2\nline3\n", encoding="utf-8")

    files = list_log_files(ldir)
    assert len(files) == 1
    assert files[0]["name"] == "bot_acc1_S53.log"
    assert read_log_tail("bot_acc1_S53.log", lines=2, log_dir=ldir) == "line2\nline3"

    with pytest.raises(ValueError):
        read_log_tail("../secret.txt", log_dir=ldir)
    with pytest.raises(ValueError):
        read_log_tail("config.json", log_dir=ldir)
