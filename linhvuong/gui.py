"""Giao diện đăng nhập (Tkinter): nhập server ID, tài khoản, mật khẩu, và cấu hình proxy."""

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import requests

from .auth import LoginError, login, normalize_proxy_url, parse_server_id

SETTINGS = Path("gui_settings.json")  # chỉ lưu server, tài khoản, cấu hình proxy; không lưu mật khẩu game
BG, CARD, FG, ACCENT = "#14161f", "#1e2130", "#e8eaf2", "#6c7bff"


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinhVuong - Đăng nhập")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.session = None
        self.server_id = None
        self._updating_proxy = False

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TLabel", background=CARD, foreground=FG, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"), foreground=ACCENT)
        style.configure("TEntry", fieldbackground="#2a2e45", foreground=FG, insertcolor=FG)
        style.configure(
            "Login.TButton",
            background=ACCENT,
            foreground="white",
            font=("Segoe UI", 10, "bold"),
            padding=8,
        )
        style.map("Login.TButton", background=[("active", "#8591ff"), ("disabled", "#444a70")])

        card = tk.Frame(self, bg=CARD, padx=32, pady=24)
        card.pack(padx=24, pady=24)
        ttk.Label(card, text="Linh Vương", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, pady=(0, 16)
        )

        self.server_var = tk.StringVar()
        self.user_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.proxy_var = tk.StringVar()
        self.proxy_user_var = tk.StringVar()
        self.proxy_pass_var = tk.StringVar()

        fields = [
            ("Server ID", self.server_var, ""),
            ("Tài khoản", self.user_var, ""),
            ("Mật khẩu", self.pass_var, "•"),
            ("Proxy", self.proxy_var, ""),
            ("Proxy User", self.proxy_user_var, ""),
            ("Proxy Pass", self.proxy_pass_var, "•"),
        ]
        for row, (label, var, show) in enumerate(fields, start=1):
            ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            ttk.Entry(card, textvariable=var, show=show, width=28).grid(row=row, column=1, pady=4)

        proxy_hint = ttk.Label(
            card,
            text="Hỗ trợ: http, https, socks5. Dán nhanh: ip:port hoặc ip:port:user:pass",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
            wraplength=310,
        )
        proxy_hint.grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 4))

        ttk.Label(
            card,
            text="Địa chỉ: http://sg<Server ID>.dipan.com/",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
        ).grid(row=8, column=0, columnspan=2, sticky="w")
        self.url_hint = card.grid_slaves(row=8)[0]
        self.server_var.trace_add("write", self._update_hint)
        self.proxy_var.trace_add("write", self._on_proxy_change)

        self.btn = ttk.Button(card, text="Đăng nhập", style="Login.TButton", command=self._submit)
        self.btn.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(14, 6))
        self.status = tk.StringVar()
        tk.Label(
            card,
            textvariable=self.status,
            bg=CARD,
            fg="#ff8a8a",
            wraplength=320,
            font=("Segoe UI", 9),
        ).grid(row=10, column=0, columnspan=2)

        self._load_settings()
        self.bind("<Return>", lambda e: self._submit())

    def _update_hint(self, *_):
        sid = self.server_var.get().strip() or "<Server ID>"
        self.url_hint.configure(text=f"Địa chỉ: http://sg{sid}.dipan.com/")

    def _on_proxy_change(self, *_):
        """Tự động phân tách chuỗi dán nhanh dạng ip:port:user:pass thành các ô tương ứng."""
        if self._updating_proxy:
            return
        raw = self.proxy_var.get().strip()
        if "@" not in raw and ":" in raw:
            scheme = ""
            rest = raw
            if "://" in raw:
                scheme, rest = raw.split("://", 1)
            parts = rest.split(":")
            if len(parts) == 4:
                host, port, u, p = parts
                if host and port.isdigit():
                    self._updating_proxy = True
                    try:
                        prefix = f"{scheme}://" if scheme else ""
                        self.proxy_var.set(f"{prefix}{host}:{port}")
                        self.proxy_user_var.set(u)
                        self.proxy_pass_var.set(p)
                    finally:
                        self._updating_proxy = False

    def _load_settings(self):
        if SETTINGS.exists():
            try:
                data = json.loads(SETTINGS.read_text(encoding="utf-8"))
                self.server_var.set(str(data.get("server", "")))
                self.user_var.set(data.get("username", ""))
                pwd = data.get("password") or data.get("passwrod")
                if pwd:
                    self.pass_var.set(pwd)
                self.proxy_var.set(data.get("proxy", ""))
                self.proxy_user_var.set(data.get("proxy_user", ""))
                self.proxy_pass_var.set(data.get("proxy_pass", ""))
            except Exception:
                pass

    def _submit(self):
        try:
            server_id = parse_server_id(self.server_var.get())
        except ValueError as e:
            self.status.set(str(e))
            return
        username, password = self.user_var.get().strip(), self.pass_var.get()
        if not username or not password:
            self.status.set("Nhập tài khoản và mật khẩu.")
            return

        proxy_raw = self.proxy_var.get().strip()
        proxy_user = self.proxy_user_var.get().strip()
        proxy_pass = self.proxy_pass_var.get()
        try:
            normalized_proxy = normalize_proxy_url(
                proxy_raw, username=proxy_user, password=proxy_pass
            )
        except ValueError as e:
            self.status.set(f"Proxy không hợp lệ: {e}")
            return

        self.btn.state(["disabled"])
        self.status.set("")
        threading.Thread(
            target=self._do_login,
            args=(
                server_id,
                username,
                password,
                proxy_raw,
                proxy_user,
                proxy_pass,
                normalized_proxy,
            ),
            daemon=True,
        ).start()

    def _do_login(
        self,
        server_id,
        username,
        password,
        proxy_raw,
        proxy_user,
        proxy_pass,
        normalized_proxy,
    ):
        session = requests.Session()
        try:
            login(session, server_id, username, password, proxy=normalized_proxy)
        except LoginError as e:
            self.after(0, self._failed, str(e))
            return
        self.after(
            0,
            self._succeeded,
            session,
            server_id,
            username,
            proxy_raw,
            proxy_user,
            proxy_pass,
        )

    def _failed(self, msg):
        self.status.set(msg)
        self.btn.state(["!disabled"])

    def _succeeded(self, session, server_id, username, proxy_raw, proxy_user, proxy_pass):
        data = {"server": server_id, "username": username}
        if proxy_raw:
            data["proxy"] = proxy_raw
        if proxy_user:
            data["proxy_user"] = proxy_user
        if proxy_pass:
            data["proxy_pass"] = proxy_pass
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.session, self.server_id = session, server_id
        self.destroy()


def ask_login():
    """Hiện cửa sổ đăng nhập; trả (session, server_id) hoặc None nếu đóng cửa sổ."""
    win = LoginWindow()
    win.mainloop()
    return (win.session, win.server_id) if win.session else None


if __name__ == "__main__":
    result = ask_login()
    if result:
        from .dashboard import Dashboard

        Dashboard(*result).mainloop()
