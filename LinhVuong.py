"""Linh Vương Auto Bot - Điểm khởi chạy ứng dụng GUI."""
import sys
from linhvuong.gui import MultiAccountApp


def main():
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("linhvuong.autobot.multiaccount.v1")
    except Exception:
        pass
    app = MultiAccountApp()
    app.mainloop()


if __name__ == "__main__":
    main()
