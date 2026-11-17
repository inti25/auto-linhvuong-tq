"""Linh Vương Web Dashboard - Điểm khởi chạy đóng gói binary (PyInstaller)."""

import sys
from linhvuong.web.server import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
