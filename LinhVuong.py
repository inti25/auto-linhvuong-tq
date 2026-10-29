"""Linh Vương Auto Bot - Điểm khởi chạy ứng dụng GUI."""
import sys
from linhvuong.gui import MultiAccountApp


def main():
    app = MultiAccountApp()
    app.mainloop()


if __name__ == "__main__":
    main()
