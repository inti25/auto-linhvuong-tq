"""Unit tests cho hệ thống logging tập trung, xoay vòng file và thu thập vết lỗi (ADR-0015)."""

import logging
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from linhvuong.gateway import GatewayClient
from linhvuong.logger import (
    SanitizingFilter,
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

    def test_text_buffer_trimming_to_max_lines(self):
        root = tk.Tk()
        root.withdraw()
        try:
            txt = tk.Text(root)
            # Giả lập hàm _append_text_buffer
            def append_buf(widget, line, max_lines=10):
                widget.insert("end", line)
                try:
                    line_count = int(widget.index("end-1c").split(".")[0])
                    if line_count > max_lines:
                        diff = line_count - max_lines
                        widget.delete("1.0", f"{diff + 1}.0")
                except Exception:
                    pass

            for i in range(25):
                append_buf(txt, f"Dòng thứ {i + 1}\n", max_lines=10)

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
