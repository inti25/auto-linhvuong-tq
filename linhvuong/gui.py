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
        self.accounts_dict = {}

        # Dòng 1: Chọn tài khoản đã lưu (Account Switcher)
        ttk.Label(card, text="Đã lưu").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 14))
        acc_frame = tk.Frame(card, bg=CARD)
        acc_frame.grid(row=1, column=1, sticky="ew", pady=4)
        self.saved_acc_combo = ttk.Combobox(acc_frame, state="readonly", width=22)
        self.saved_acc_combo.pack(side="left", fill="x", expand=True)
        self.saved_acc_combo.bind("<<ComboboxSelected>>", self._on_saved_acc_selected)
        ttk.Button(acc_frame, text="🗑️", width=3, command=self._delete_saved_acc).pack(side="left", padx=(4, 0))

        fields = [
            ("Server ID", self.server_var, ""),
            ("Tài khoản", self.user_var, ""),
            ("Mật khẩu", self.pass_var, "•"),
            ("Proxy", self.proxy_var, ""),
            ("Proxy User", self.proxy_user_var, ""),
            ("Proxy Pass", self.proxy_pass_var, "•"),
        ]
        for row, (label, var, show) in enumerate(fields, start=2):
            ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            ttk.Entry(card, textvariable=var, show=show, width=28).grid(row=row, column=1, pady=4)

        proxy_hint = ttk.Label(
            card,
            text="Hỗ trợ: http, https, socks5. Dán nhanh: ip:port hoặc ip:port:user:pass",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
            wraplength=310,
        )
        proxy_hint.grid(row=8, column=0, columnspan=2, sticky="w", pady=(2, 4))

        ttk.Label(
            card,
            text="Địa chỉ: http://sg<Server ID>.dipan.com/",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
        ).grid(row=9, column=0, columnspan=2, sticky="w")
        self.url_hint = card.grid_slaves(row=9)[0]
        self.server_var.trace_add("write", self._update_hint)
        self.proxy_var.trace_add("write", self._on_proxy_change)

        self.btn = ttk.Button(card, text="Đăng nhập", style="Login.TButton", command=self._submit)
        self.btn.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(14, 6))
        self.status = tk.StringVar()
        tk.Label(
            card,
            textvariable=self.status,
            bg=CARD,
            fg="#ff8a8a",
            wraplength=320,
            font=("Segoe UI", 9),
        ).grid(row=11, column=0, columnspan=2)

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

    def _refresh_saved_accounts_combo(self, select_key=None):
        if not hasattr(self, "saved_acc_combo"):
            return
        keys = list(self.accounts_dict.keys())
        self.saved_acc_combo["values"] = keys
        if keys:
            if select_key and select_key in keys:
                self.saved_acc_combo.set(select_key)
            else:
                self.saved_acc_combo.current(0)
        else:
            self.saved_acc_combo.set("")

    def _on_saved_acc_selected(self, *_):
        key = self.saved_acc_combo.get().strip()
        if not key or key not in self.accounts_dict:
            return
        acc = self.accounts_dict[key]
        self.server_var.set(str(acc.get("server", "")))
        self.user_var.set(acc.get("username", ""))
        self.proxy_var.set(acc.get("proxy", ""))
        self.proxy_user_var.set(acc.get("proxy_user", ""))
        self.proxy_pass_var.set(acc.get("proxy_pass", ""))

    def _delete_saved_acc(self):
        key = self.saved_acc_combo.get().strip()
        if not key or key not in self.accounts_dict:
            return
        del self.accounts_dict[key]
        self._refresh_saved_accounts_combo()
        if self.saved_acc_combo.get():
            self._on_saved_acc_selected()
        else:
            self.user_var.set("")
            self.proxy_var.set("")
            self.proxy_user_var.set("")
            self.proxy_pass_var.set("")
        self._persist_current_accounts()

    def _persist_current_accounts(self):
        data = {
            "server": self.server_var.get().strip(),
            "username": self.user_var.get().strip(),
            "proxy": self.proxy_var.get().strip(),
            "proxy_user": self.proxy_user_var.get().strip(),
            "proxy_pass": self.proxy_pass_var.get(),
            "last_account": self.saved_acc_combo.get().strip() if hasattr(self, "saved_acc_combo") else "",
            "accounts": self.accounts_dict,
        }
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_settings(self):
        self.accounts_dict = {}
        if SETTINGS.exists():
            try:
                data = json.loads(SETTINGS.read_text(encoding="utf-8"))
                raw_accounts = data.get("accounts")
                if isinstance(raw_accounts, dict) and raw_accounts:
                    self.accounts_dict = dict(raw_accounts)
                elif data.get("username"):
                    srv = data.get("server", "")
                    usr = data.get("username", "")
                    k = f"{usr} @ S{srv}"
                    self.accounts_dict[k] = {
                        "server": srv,
                        "username": usr,
                        "proxy": data.get("proxy", ""),
                        "proxy_user": data.get("proxy_user", ""),
                        "proxy_pass": data.get("proxy_pass", ""),
                    }

                last_key = data.get("last_account", "")
                self._refresh_saved_accounts_combo(last_key)

                if last_key and last_key in self.accounts_dict:
                    self._on_saved_acc_selected()
                elif self.accounts_dict:
                    self._on_saved_acc_selected()
                else:
                    self.server_var.set(str(data.get("server", "")))
                    self.user_var.set(data.get("username", ""))
                    self.proxy_var.set(data.get("proxy", ""))
                    self.proxy_user_var.set(data.get("proxy_user", ""))
                    self.proxy_pass_var.set(data.get("proxy_pass", ""))

                pwd = data.get("password") or data.get("passwrod")
                if pwd:
                    self.pass_var.set(pwd)
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
            password,
        )

    def _failed(self, msg):
        self.status.set(msg)
        self.btn.state(["!disabled"])

    def _succeeded(
        self, session, server_id, username, proxy_raw, proxy_user, proxy_pass, password=""
    ):
        acc_key = f"{username} @ S{server_id}"
        if not hasattr(self, "accounts_dict") or not isinstance(self.accounts_dict, dict):
            self.accounts_dict = {}
        self.accounts_dict[acc_key] = {
            "server": server_id,
            "username": username,
            "proxy": proxy_raw or "",
            "proxy_user": proxy_user or "",
            "proxy_pass": proxy_pass or "",
        }
        data = {
            "server": server_id,
            "username": username,
            "proxy": proxy_raw or "",
            "proxy_user": proxy_user or "",
            "proxy_pass": proxy_pass or "",
            "last_account": acc_key,
            "accounts": self.accounts_dict,
        }
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.session, self.server_id, self.username = session, server_id, username
        self.password = password
        self.proxy_raw = proxy_raw
        self.proxy_user = proxy_user
        self.proxy_pass = proxy_pass
        self.destroy()


def ask_login():
    """Hiện cửa sổ đăng nhập; trả (session, server_id, username, password, proxy_raw, proxy_user, proxy_pass) hoặc None nếu đóng cửa sổ."""
    win = LoginWindow()
    win.mainloop()
    if win.session:
        user = getattr(win, "username", win.user_var.get().strip())
        pwd = getattr(win, "password", win.pass_var.get())
        p_raw = getattr(win, "proxy_raw", win.proxy_var.get().strip())
        p_user = getattr(win, "proxy_user", win.proxy_user_var.get().strip())
        p_pass = getattr(win, "proxy_pass", win.proxy_pass_var.get())
        return (win.session, win.server_id, user, pwd, p_raw, p_user, p_pass)
    return None


if __name__ == "__main__":
    result = ask_login()
    if result:
        from .dashboard import Dashboard

        session, server_id, *rest = result
        username = rest[0] if len(rest) > 0 else ""
        password = rest[1] if len(rest) > 1 else ""
        proxy_raw = rest[2] if len(rest) > 2 else ""
        proxy_user = rest[3] if len(rest) > 3 else ""
        proxy_pass = rest[4] if len(rest) > 4 else ""
        Dashboard(
            session,
            server_id,
            username=username,
            password=password,
            proxy_raw=proxy_raw,
            proxy_user=proxy_user,
            proxy_pass=proxy_pass,
        ).mainloop()
