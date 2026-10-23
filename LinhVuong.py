"""Linh Vương Auto Bot - Điểm khởi chạy ứng dụng GUI."""
import sys
from linhvuong.gui import ask_login
from linhvuong.dashboard import Dashboard


def main():
    login_res = ask_login()
    if login_res:
        session, server_id, *rest = login_res
        username = rest[0] if len(rest) > 0 else ""
        password = rest[1] if len(rest) > 1 else ""
        proxy_raw = rest[2] if len(rest) > 2 else ""
        proxy_user = rest[3] if len(rest) > 3 else ""
        proxy_pass = rest[4] if len(rest) > 4 else ""
        app = Dashboard(
            session,
            server_id,
            username=username,
            password=password,
            proxy_raw=proxy_raw,
            proxy_user=proxy_user,
            proxy_pass=proxy_pass,
        )
        app.mainloop()


if __name__ == "__main__":
    main()
