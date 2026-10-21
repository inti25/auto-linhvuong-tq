"""Linh Vương Auto Bot - Điểm khởi chạy ứng dụng GUI."""
import sys
from linhvuong.gui import ask_login
from linhvuong.dashboard import Dashboard


def main():
    login_res = ask_login()
    if login_res:
        session, server_id, *rest = login_res
        username = rest[0] if rest else ""
        app = Dashboard(session, server_id, username=username)
        app.mainloop()


if __name__ == "__main__":
    main()
