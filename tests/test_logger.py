"""Unit tests cho hệ thống logging tập trung, xoay vòng file và thu thập vết lỗi (ADR-0015)."""

import logging
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from linhvuong.gateway import GatewayClient
from linhvuong.logger import (
    DEFAULT_BACKUP_COUNT,
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_MAX_BYTES,
    SanitizingFilter,
    clean_old_logs,
    get_log_file_path,
    get_logger,
    open_logs_directory,
    setup_logger,
)


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.temp_dir.name)

    def tearDown(self):
        # Đóng toàn bộ handlers trước khi dọn dẹp thư mục tạm
        logger = logging.getLogger("linhvuong")
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()
        self.temp_dir.cleanup()

    def test_log_file_path_generation(self):
        p = get_log_file_path("test_user", 53, self.log_dir)
        self.assertEqual(p.name, "bot_test_user_S53.log")
        self.assertEqual(p.parent, self.log_dir)

        # Ký tự đặc biệt trong username được sanitize
        p2 = get_log_file_path("user/name:1", 57, self.log_dir)
        self.assertEqual(p2.name, "bot_user_name_1_S57.log")

    def test_setup_logger_creates_file_and_writes(self):
        logger = setup_logger(
            username="player1",
            server_id=53,
            log_dir=self.log_dir,
            debug=False,
            console=False,
        )
        self.assertEqual(logger.level, logging.INFO)

        log_file = get_log_file_path("player1", 53, self.log_dir)
        self.assertTrue(log_file.exists())

        test_msg = "Kiểm tra ghi log bình thường"
        logger.info(test_msg)

        content = log_file.read_text(encoding="utf-8")
        self.assertIn("[INFO]", content)
        self.assertIn("linhvuong", content)
        self.assertIn(test_msg, content)

    def test_sanitizing_filter_masks_credentials(self):
        f = SanitizingFilter()

        # 1. Password trong chuỗi text
        text1 = "Gửi request đăng nhập với password=SecretPassword123 và server=53"
        sanitized1 = f.sanitize(text1)
        self.assertNotIn("SecretPassword123", sanitized1)
        self.assertIn("password=***", sanitized1)

        # 2. Proxy pass
        text2 = "proxy_pass=MyProxyPass999 proxy_user=admin"
        sanitized2 = f.sanitize(text2)
        self.assertNotIn("MyProxyPass999", sanitized2)
        self.assertIn("proxy_pass=***", sanitized2)

        # 3. URL có user:pass
        text3 = "Kết nối tới http://user:my_secret_proxy_pass@127.0.0.1:8080"
        sanitized3 = f.sanitize(text3)
        self.assertNotIn("my_secret_proxy_pass", sanitized3)
        self.assertIn("http://user:***@127.0.0.1:8080", sanitized3)

        # 4. JSON password
        text4 = 'Payload {"username": "foo", "password": "super_secret"}'
        sanitized4 = f.sanitize(text4)
        self.assertNotIn("super_secret", sanitized4)
        self.assertIn('"password": "***"', sanitized4)

    def test_traceback_captured_on_exception(self):
        logger = setup_logger(
            username="player_exc",
            server_id=53,
            log_dir=self.log_dir,
            console=False,
        )
        sub_logger = get_logger("tasks.building")

        try:
            # Gây ngoại lệ cố ý
            1 / 0
        except ZeroDivisionError as e:
            sub_logger.exception(f"Lỗi chia cho 0 xảy ra: {e}")

        log_file = get_log_file_path("player_exc", 53, self.log_dir)
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("ZeroDivisionError: division by zero", content)
        self.assertIn("Traceback (most recent call last):", content)
        self.assertIn("linhvuong.tasks.building", content)

    def test_gateway_logging_on_network_error(self):
        setup_logger(
            username="gw_test",
            server_id=53,
            log_dir=self.log_dir,
            console=False,
        )
        fake_session = MagicMock()
        fake_session.post.side_effect = ConnectionError("Proxy connection refused")

        gw = GatewayClient(53, fake_session, sleep=lambda s: None, max_retries=2)
        res = gw.call("City.ashx", 5, {"tid": 100})
        self.assertIsNone(res)

        log_file = get_log_file_path("gw_test", 53, self.log_dir)
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("Lỗi mạng khi gọi City.ashx?id=5", content)
        self.assertIn("Proxy connection refused", content)
        self.assertIn("Thất bại hoàn toàn sau 2 lần gọi", content)

    def test_gateway_logging_on_server_error_code(self):
        setup_logger(
            username="gw_ret_test",
            server_id=53,
            log_dir=self.log_dir,
            console=False,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ret": 39, "msg": "Vật cản địa hình"}
        fake_session = MagicMock()
        fake_session.post.return_value = mock_resp

        gw = GatewayClient(53, fake_session, sleep=lambda s: None)
        res = gw.call("OPT.ashx", 65, {"pid": 1, "gid": 2})
        self.assertEqual(res, {"ret": 39, "msg": "Vật cản địa hình"})

        log_file = get_log_file_path("gw_ret_test", 53, self.log_dir)
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("Máy chủ trả về mã lỗi ret=39", content)
        self.assertIn("OPT.ashx?id=65", content)

    def test_default_rotation_parameters(self):
        """Kiểm tra cấu hình xoay vòng mặc định 2MB và 3 bản sao theo ADR-0030."""
        self.assertEqual(DEFAULT_MAX_BYTES, 2 * 1024 * 1024)
        self.assertEqual(DEFAULT_BACKUP_COUNT, 3)
        self.assertEqual(DEFAULT_MAX_AGE_DAYS, 7)

        logger = setup_logger(
            username="rot_test",
            server_id=53,
            log_dir=self.log_dir,
            console=False,
        )
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        self.assertEqual(len(file_handlers), 1)
        fh = file_handlers[0]
        self.assertEqual(fh.maxBytes, 2 * 1024 * 1024)
        self.assertEqual(fh.backupCount, 3)

    def test_clean_old_logs(self):
        """Kiểm tra clean_old_logs chỉ xóa tệp log quá hạn và giữ lại tệp mới / tệp khác."""
        now = time.time()
        # 1. Tệp log cũ 10 ngày
        old_log = self.log_dir / "bot_old_S53.log"
        old_log.write_text("old content", encoding="utf-8")
        os.utime(old_log, (now - 10 * 86400, now - 10 * 86400))

        # 2. Tệp backup xoay vòng cũ 8 ngày
        old_bak = self.log_dir / "bot_old_S53.log.1"
        old_bak.write_text("old bak content", encoding="utf-8")
        os.utime(old_bak, (now - 8 * 86400, now - 8 * 86400))

        # 3. Tệp log mới 1 ngày
        new_log = self.log_dir / "bot_new_S53.log"
        new_log.write_text("new content", encoding="utf-8")
        os.utime(new_log, (now - 1 * 86400, now - 1 * 86400))

        # 4. Tệp không phải đuôi log (dù cũ cũng không xóa)
        other_file = self.log_dir / "notes.txt"
        other_file.write_text("important notes", encoding="utf-8")
        os.utime(other_file, (now - 15 * 86400, now - 15 * 86400))

        deleted = clean_old_logs(self.log_dir, max_age_days=7)
        self.assertEqual(deleted, 2)
        self.assertFalse(old_log.exists())
        self.assertFalse(old_bak.exists())
        self.assertTrue(new_log.exists())
        self.assertTrue(other_file.exists())

    def test_setup_logger_invokes_cleanup(self):
        """Kiểm tra setup_logger tự động kích hoạt dọn dẹp log quá hạn khi khởi động."""
        now = time.time()
        stale_log = self.log_dir / "bot_stale_S53.log"
        stale_log.write_text("stale", encoding="utf-8")
        os.utime(stale_log, (now - 12 * 86400, now - 12 * 86400))

        setup_logger(username="user1", server_id=53, log_dir=self.log_dir, console=False)
        self.assertFalse(stale_log.exists())

    def test_text_buffer_trimming_to_max_lines(self):
        root = tk.Tk()
        root.withdraw()
        try:
            txt = tk.Text(root)
            # Giả lập hàm _append_text_buffer theo cơ chế batch trimming (ADR-0030)
            def append_buf(widget, line, max_lines=10, trim_batch=4):
                widget.insert("end", line)
                try:
                    line_count = int(widget.index("end-1c").split(".")[0])
                    if line_count > max_lines:
                        target_lines = max(1, max_lines - trim_batch)
                        lines_to_delete = line_count - target_lines
                        widget.delete("1.0", f"{lines_to_delete + 1}.0")
                except Exception:
                    pass

            for i in range(25):
                append_buf(txt, f"Dòng thứ {i + 1}\n", max_lines=10, trim_batch=4)

            line_count = int(txt.index("end-1c").split(".")[0])
            self.assertLessEqual(line_count, 11)
            content = txt.get("1.0", "end")
            self.assertIn("Dòng thứ 25", content)
            self.assertNotIn("Dòng thứ 1\n", content)
        finally:
            root.destroy()

    def test_open_logs_directory(self):
        with patch("sys.platform", "win32"), patch("os.startfile") as mock_start:
            res = open_logs_directory(self.log_dir)
            self.assertTrue(res)
            mock_start.assert_called_once_with(str(self.log_dir.resolve()))
