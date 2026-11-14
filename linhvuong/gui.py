"""Giao diện đăng nhập (Tkinter): nhập server ID, tài khoản, mật khẩu, và cấu hình proxy."""

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

import requests

from .auth import LoginError, login, normalize_proxy_url, parse_server_id
from .proxy import DEFAULT_FREE_PROXY_URL, ProxyPool

SETTINGS = Path("gui_settings.json")  # chỉ lưu server, tài khoản, cấu hình proxy; không lưu mật khẩu game
BG, CARD, FG, ACCENT = "#14161f", "#1e2130", "#e8eaf2", "#6c7bff"


def set_app_icon(win: tk.Tk | tk.Toplevel):
    """Đặt icon cho cửa sổ ứng dụng và taskbar Windows thuần Tkinter (không phụ thuộc PIL/NumPy)."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("linhvuong.autobot.multiaccount.v1")
    except Exception:
        pass

    try:
        import sys
        base_dir = Path(getattr(sys, "_MEIPASS", "."))
        candidates = [
            base_dir / "linhvuong.ico",
            Path("linhvuong.ico"),
            Path(__file__).resolve().parent.parent / "linhvuong.ico",
        ]
        for p in candidates:
            if p.is_file():
                try:
                    win.iconbitmap(str(p))
                except Exception:
                    pass
                break

        # Đặt iconphoto bằng PNG thuần Tkinter để hiển thị trên Taskbar & Alt-Tab
        png_candidates = [
            base_dir / "linhvuong.png",
            Path("linhvuong.png"),
            Path(__file__).resolve().parent.parent / "linhvuong.png",
        ]
        for png_p in png_candidates:
            if png_p.is_file():
                try:
                    photo = tk.PhotoImage(file=str(png_p))
                    win.iconphoto(True, photo)
                    win._app_icon_photo = photo
                    break
                except Exception:
                    pass
    except Exception:
        pass


def load_coffee_qr_image(max_w: int = 300, max_h: int = 400):
    """Tải mã QR ủng hộ tác giả từ file PNG thuần Tkinter hoặc file WEBP (hỗ trợ cả Tkinter thuần và PIL)."""
    try:
        import sys
        base_dir = Path(getattr(sys, "_MEIPASS", "."))

        # 1. Ưu tiên load qrcode.png bằng tk.PhotoImage thuần (không phụ thuộc PIL/Pillow khi build exe)
        png_candidates = [
            base_dir / "qrcode.png",
            Path("qrcode.png"),
            Path(__file__).resolve().parent.parent / "qrcode.png",
        ]
        for p in png_candidates:
            if p.is_file():
                try:
                    return tk.PhotoImage(file=str(p))
                except Exception:
                    pass

        # 2. Fallback dùng PIL nếu có cài đặt (để load định dạng .webp hoặc tự động co giãn)
        try:
            from PIL import Image, ImageTk
            all_candidates = png_candidates + [
                base_dir / "qrcode.webp",
                Path("qrcode.webp"),
                Path(__file__).resolve().parent.parent / "qrcode.webp",
            ]
            for p in all_candidates:
                if p.is_file():
                    img = Image.open(str(p))
                    img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                    return ImageTk.PhotoImage(img)
        except Exception:
            pass
    except Exception:
        pass
    return None


def load_app_image():
    """Tải hình ảnh icon menu từ file PNG thuần Tkinter (không phụ thuộc PIL/NumPy)."""
    try:
        import sys
        base_dir = Path(getattr(sys, "_MEIPASS", "."))
        candidates = [
            base_dir / "linhvuong_menu.png",
            Path("linhvuong_menu.png"),
            Path(__file__).resolve().parent.parent / "linhvuong_menu.png",
            base_dir / "linhvuong.png",
            Path("linhvuong.png"),
            Path(__file__).resolve().parent.parent / "linhvuong.png",
        ]
        for p in candidates:
            if p.is_file():
                try:
                    return tk.PhotoImage(file=str(p))
                except Exception:
                    pass
    except Exception:
        pass
    return None


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LinhVuong - Đăng nhập")
        set_app_icon(self)
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
        self.proxy_url_var = tk.StringVar()
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

        basic_fields = [
            ("Server ID", self.server_var, ""),
            ("Tài khoản", self.user_var, ""),
            ("Mật khẩu", self.pass_var, "•"),
        ]
        for row, (label, var, show) in enumerate(basic_fields, start=2):
            ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            ttk.Entry(card, textvariable=var, show=show, width=28).grid(row=row, column=1, pady=4)

        # Dòng 5: URL Proxy List
        ttk.Label(card, text="URL Proxy List").grid(row=5, column=0, sticky="w", pady=4, padx=(0, 14))
        purl_frame = tk.Frame(card, bg=CARD)
        purl_frame.grid(row=5, column=1, sticky="ew", pady=4)
        ttk.Entry(purl_frame, textvariable=self.proxy_url_var, width=15).pack(side="left", fill="x", expand=True)
        ttk.Button(purl_frame, text="⚡ Free", width=6, command=self._fill_free_proxy).pack(side="left", padx=(4, 0))
        ttk.Button(purl_frame, text="🔄 Test", width=6, command=self._test_proxy_url).pack(side="left", padx=(4, 0))

        proxy_fields = [
            ("Proxy", self.proxy_var, ""),
            ("Proxy User", self.proxy_user_var, ""),
            ("Proxy Pass", self.proxy_pass_var, "•"),
        ]
        for row, (label, var, show) in enumerate(proxy_fields, start=6):
            ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            ttk.Entry(card, textvariable=var, show=show, width=28).grid(row=row, column=1, pady=4)

        proxy_hint = ttk.Label(
            card,
            text="Hỗ trợ: URL tải proxy list hoặc thủ công ip:port / ip:port:user:pass",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
            wraplength=310,
        )
        proxy_hint.grid(row=9, column=0, columnspan=2, sticky="w", pady=(2, 4))

        ttk.Label(
            card,
            text="Địa chỉ: http://sg<Server ID>.dipan.com/",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
        ).grid(row=10, column=0, columnspan=2, sticky="w")
        self.url_hint = card.grid_slaves(row=10)[0]
        self.server_var.trace_add("write", self._update_hint)
        self.proxy_var.trace_add("write", self._on_proxy_change)

        self.btn = ttk.Button(card, text="Đăng nhập", style="Login.TButton", command=self._submit)
        self.btn.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(14, 6))
        self.status = tk.StringVar()
        tk.Label(
            card,
            textvariable=self.status,
            bg=CARD,
            fg="#ff8a8a",
            wraplength=320,
            font=("Segoe UI", 9),
        ).grid(row=12, column=0, columnspan=2)

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
        self.proxy_url_var.set(acc.get("proxy_url", ""))
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
            self.proxy_url_var.set("")
            self.proxy_var.set("")
            self.proxy_user_var.set("")
            self.proxy_pass_var.set("")
        self._persist_current_accounts()

    def _persist_current_accounts(self):
        data = {
            "server": self.server_var.get().strip(),
            "username": self.user_var.get().strip(),
            "proxy_url": self.proxy_url_var.get().strip(),
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
                        "proxy_url": data.get("proxy_url", ""),
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
                    self.proxy_url_var.set(data.get("proxy_url", ""))
                    self.proxy_var.set(data.get("proxy", ""))
                    self.proxy_user_var.set(data.get("proxy_user", ""))
                    self.proxy_pass_var.set(data.get("proxy_pass", ""))

                pwd = data.get("password") or data.get("passwrod")
                if pwd:
                    self.pass_var.set(pwd)
            except Exception:
                pass

    def _fill_free_proxy(self):
        self.proxy_url_var.set(DEFAULT_FREE_PROXY_URL)
        self.status.set("Đã điền ProxyScrape SOCKS5 Free. Bấm '🔄 Test' để kiểm tra.")

    def _test_proxy_url(self):
        url = self.proxy_url_var.get().strip()
        if not url:
            self.status.set("Vui lòng nhập URL danh sách Proxy trước khi kiểm tra.")
            return
        self.status.set("🔄 Đang tải và kiểm tra danh sách proxy...")

        def run_test():
            try:
                pool = ProxyPool(url=url)
                count = pool.fetch_from_url()
                if count == 0:
                    self.after(0, self.status.set, "⚠️ Không tìm thấy proxy hợp lệ trong file tải về.")
                    return
                alive = pool.check_all()
                if alive:
                    best = alive[0]
                    self.after(
                        0,
                        self.status.set,
                        f"✅ Tìm thấy {len(alive)}/{count} proxy sống (Tốt nhất: {best.display_name} - {best.latency}s)",
                    )
                else:
                    self.after(
                        0,
                        self.status.set,
                        f"❌ Đã tải {count} proxy nhưng toàn bộ đều không kết nối được game.",
                    )
            except Exception as ex:
                self.after(0, self.status.set, f"❌ Lỗi kiểm tra proxy: {ex}")

        threading.Thread(target=run_test, daemon=True).start()

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

        proxy_url = self.proxy_url_var.get().strip()
        proxy_raw = self.proxy_var.get().strip()
        proxy_user = self.proxy_user_var.get().strip()
        proxy_pass = self.proxy_pass_var.get()
        normalized_proxy = None
        if not proxy_url and proxy_raw:
            try:
                normalized_proxy = normalize_proxy_url(
                    proxy_raw, username=proxy_user, password=proxy_pass
                )
            except ValueError as e:
                self.status.set(f"Proxy không hợp lệ: {e}")
                return

        self.btn.state(["disabled"])
        self.status.set("Đang chuẩn bị kết nối...")
        threading.Thread(
            target=self._do_login,
            args=(
                server_id,
                username,
                password,
                proxy_url,
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
        proxy_url,
        proxy_raw,
        proxy_user,
        proxy_pass,
        normalized_proxy,
    ):
        session = requests.Session()
        proxy_pool = None
        if proxy_url:
            self.after(0, self.status.set, "🔄 Đang tải và kiểm tra danh sách proxy...")
            try:
                proxy_pool = ProxyPool(url=proxy_url)
                count = proxy_pool.fetch_from_url()
                alive = proxy_pool.check_all()
                if not alive:
                    self.after(
                        0,
                        self._failed,
                        f"Tải được {count} proxy từ URL nhưng toàn bộ đều không kết nối được.",
                    )
                    return
                proxy_pool.apply_to_session(session)
            except Exception as ex:
                self.after(0, self._failed, f"Lỗi nạp proxy từ URL: {ex}")
                return

        self.after(0, self.status.set, "🔑 Đang đăng nhập máy chủ Linh Vương...")
        try:
            if not proxy_url and normalized_proxy:
                login(session, server_id, username, password, proxy=normalized_proxy)
            else:
                login(session, server_id, username, password)
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
            proxy_url,
            proxy_pool,
        )

    def _failed(self, msg):
        self.status.set(msg)
        self.btn.state(["!disabled"])

    def _succeeded(
        self,
        session,
        server_id,
        username,
        proxy_raw,
        proxy_user,
        proxy_pass,
        password="",
        proxy_url="",
        proxy_pool=None,
    ):
        acc_key = f"{username} @ S{server_id}"
        p_url = proxy_url or (self.proxy_url_var.get().strip() if hasattr(self, "proxy_url_var") else "")
        if not hasattr(self, "accounts_dict") or not isinstance(self.accounts_dict, dict):
            self.accounts_dict = {}
        self.accounts_dict[acc_key] = {
            "server": server_id,
            "username": username,
            "proxy_url": p_url or "",
            "proxy": proxy_raw or "",
            "proxy_user": proxy_user or "",
            "proxy_pass": proxy_pass or "",
        }
        data = {
            "server": server_id,
            "username": username,
            "proxy_url": p_url or "",
            "proxy": proxy_raw or "",
            "proxy_user": proxy_user or "",
            "proxy_pass": proxy_pass or "",
            "last_account": acc_key,
            "accounts": self.accounts_dict,
        }
        SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.session, self.server_id, self.username = session, server_id, username
        self.password = password
        self.proxy_url = p_url
        self.proxy_raw = proxy_raw
        self.proxy_user = proxy_user
        self.proxy_pass = proxy_pass
        self.proxy_pool = proxy_pool
        self.destroy()


class AccountLoginFrame(tk.Frame):
    """Khung đăng nhập cục bộ cho một tài khoản cụ thể trong Không Gian Đa Tài Khoản."""

    def __init__(
        self,
        master,
        account_data: Optional[dict] = None,
        on_login_success: Optional[Callable] = None,
        on_delete: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, bg=CARD, padx=32, pady=24, **kwargs)
        self.account_data = dict(account_data or {})
        self.on_login_success = on_login_success
        self.on_delete = on_delete
        self._updating_proxy = False

        self.server_var = tk.StringVar(value=str(self.account_data.get("server", "")))
        self.user_var = tk.StringVar(value=self.account_data.get("username", ""))
        self.pass_var = tk.StringVar()  # Không lưu mật khẩu ra đĩa
        self.proxy_url_var = tk.StringVar(value=self.account_data.get("proxy_url", ""))
        self.proxy_var = tk.StringVar(value=self.account_data.get("proxy", "") or self.account_data.get("proxy_raw", ""))
        self.proxy_user_var = tk.StringVar(value=self.account_data.get("proxy_user", ""))
        self.proxy_pass_var = tk.StringVar(value=self.account_data.get("proxy_pass", ""))
        self.status = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        card = self
        ttk.Label(card, text="Đăng Nhập Tài Khoản", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, pady=(0, 16)
        )

        basic_fields = [
            ("Server ID", self.server_var, ""),
            ("Tài khoản", self.user_var, ""),
            ("Mật khẩu", self.pass_var, "•"),
        ]
        for row, (label, var, show) in enumerate(basic_fields, start=1):
            ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            ttk.Entry(card, textvariable=var, show=show, width=28).grid(row=row, column=1, pady=4)

        # URL Proxy List
        ttk.Label(card, text="URL Proxy List").grid(row=4, column=0, sticky="w", pady=4, padx=(0, 14))
        purl_frame = tk.Frame(card, bg=CARD)
        purl_frame.grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Entry(purl_frame, textvariable=self.proxy_url_var, width=15).pack(side="left", fill="x", expand=True)
        ttk.Button(purl_frame, text="⚡ Free", width=6, command=self._fill_free_proxy).pack(side="left", padx=(4, 0))
        ttk.Button(purl_frame, text="🔄 Test", width=6, command=self._test_proxy_url).pack(side="left", padx=(4, 0))

        proxy_fields = [
            ("Proxy", self.proxy_var, ""),
            ("Proxy User", self.proxy_user_var, ""),
            ("Proxy Pass", self.proxy_pass_var, "•"),
        ]
        for row, (label, var, show) in enumerate(proxy_fields, start=5):
            ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
            ttk.Entry(card, textvariable=var, show=show, width=28).grid(row=row, column=1, pady=4)

        proxy_hint = ttk.Label(
            card,
            text="Hỗ trợ: URL tải proxy list hoặc thủ công ip:port / ip:port:user:pass",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
            wraplength=310,
        )
        proxy_hint.grid(row=8, column=0, columnspan=2, sticky="w", pady=(2, 4))

        self.url_hint = ttk.Label(
            card,
            text="Địa chỉ: http://sg<Server ID>.dipan.com/",
            foreground="#8a90b0",
            font=("Segoe UI", 8),
        )
        self.url_hint.grid(row=9, column=0, columnspan=2, sticky="w")
        self.server_var.trace_add("write", self._update_hint)
        self.proxy_var.trace_add("write", self._on_proxy_change)
        self._update_hint()

        self.btn = ttk.Button(card, text="🔑 Đăng nhập", style="Login.TButton", command=self._submit)
        self.btn.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(14, 6))

        tk.Label(
            card,
            textvariable=self.status,
            bg=CARD,
            fg="#ff8a8a",
            wraplength=320,
            font=("Segoe UI", 9),
        ).grid(row=11, column=0, columnspan=2)

    def _update_hint(self, *_):
        sid = self.server_var.get().strip() or "<Server ID>"
        self.url_hint.configure(text=f"Địa chỉ: http://sg{sid}.dipan.com/")

    def _on_proxy_change(self, *_):
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

    def _fill_free_proxy(self):
        self.proxy_url_var.set(DEFAULT_FREE_PROXY_URL)
        self.status.set("Đã điền ProxyScrape SOCKS5 Free. Bấm '🔄 Test' để kiểm tra.")

    def _test_proxy_url(self):
        url = self.proxy_url_var.get().strip()
        if not url:
            self.status.set("Vui lòng nhập URL danh sách Proxy trước khi kiểm tra.")
            return
        self.status.set("🔄 Đang tải và kiểm tra danh sách proxy...")

        def run_test():
            try:
                pool = ProxyPool(url=url)
                count = pool.fetch_from_url()
                if count == 0:
                    self.after(0, self.status.set, "⚠️ Không tìm thấy proxy hợp lệ trong file tải về.")
                    return
                alive = pool.check_all()
                if alive:
                    best = alive[0]
                    self.after(
                        0,
                        self.status.set,
                        f"✅ Tìm thấy {len(alive)}/{count} proxy sống (Tốt nhất: {best.display_name} - {best.latency}s)",
                    )
                else:
                    self.after(
                        0,
                        self.status.set,
                        f"❌ Đã tải {count} proxy nhưng toàn bộ đều không kết nối được game.",
                    )
            except Exception as ex:
                self.after(0, self.status.set, f"❌ Lỗi kiểm tra proxy: {ex}")

        threading.Thread(target=run_test, daemon=True).start()

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

        proxy_url = self.proxy_url_var.get().strip()
        proxy_raw = self.proxy_var.get().strip()
        proxy_user = self.proxy_user_var.get().strip()
        proxy_pass = self.proxy_pass_var.get()
        normalized_proxy = None
        if not proxy_url and proxy_raw:
            try:
                normalized_proxy = normalize_proxy_url(
                    proxy_raw, username=proxy_user, password=proxy_pass
                )
            except ValueError as e:
                self.status.set(f"Proxy không hợp lệ: {e}")
                return

        self.btn.state(["disabled"])
        self.status.set("Đang chuẩn bị kết nối...")
        threading.Thread(
            target=self._do_login,
            args=(
                server_id,
                username,
                password,
                proxy_url,
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
        proxy_url,
        proxy_raw,
        proxy_user,
        proxy_pass,
        normalized_proxy,
    ):
        session = requests.Session()
        proxy_pool = None
        if proxy_url:
            self.after(0, self.status.set, "🔄 Đang tải và kiểm tra danh sách proxy...")
            try:
                proxy_pool = ProxyPool(url=proxy_url)
                count = proxy_pool.fetch_from_url()
                alive = proxy_pool.check_all()
                if not alive:
                    self.after(
                        0,
                        self._failed,
                        f"Tải được {count} proxy từ URL nhưng toàn bộ đều không kết nối được.",
                    )
                    return
                proxy_pool.apply_to_session(session)
            except Exception as ex:
                self.after(0, self._failed, f"Lỗi nạp proxy từ URL: {ex}")
                return

        self.after(0, self.status.set, "🔑 Đang đăng nhập máy chủ Linh Vương...")
        try:
            if not proxy_url and normalized_proxy:
                login(session, server_id, username, password, proxy=normalized_proxy)
            else:
                login(session, server_id, username, password)
        except LoginError as e:
            self.after(0, self._failed, str(e))
            return

        self.after(
            0,
            self._succeeded,
            session,
            server_id,
            username,
            password,
            proxy_raw,
            proxy_user,
            proxy_pass,
            proxy_url,
            proxy_pool,
        )

    def _failed(self, msg):
        self.status.set(msg)
        self.btn.state(["!disabled"])

    def reset(self):
        """Khôi phục trạng thái ban đầu của khung đăng nhập sau khi đăng xuất."""
        self.pass_var.set("")
        self.status.set("")
        self.btn.state(["!disabled"])

    def _succeeded(
        self,
        session,
        server_id,
        username,
        password,
        proxy_raw,
        proxy_user,
        proxy_pass,
        proxy_url,
        proxy_pool,
    ):
        self.btn.state(["!disabled"])
        self.status.set("✅ Đăng nhập thành công!")
        if self.on_login_success:
            self.on_login_success(
                session=session,
                server_id=server_id,
                username=username,
                password=password,
                proxy_raw=proxy_raw,
                proxy_user=proxy_user,
                proxy_pass=proxy_pass,
                proxy_url=proxy_url,
                proxy_pool=proxy_pool,
            )


class AccountCard(tk.Frame):
    """Thẻ đại diện cho một tài khoản trên Thanh Điều Hướng (menu trái)."""

    def __init__(
        self,
        master,
        account_key: str,
        server_id: int | str,
        username: str,
        on_select: Callable[[str], None],
        on_logout: Optional[Callable[[str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, bg=CARD, padx=12, pady=10, cursor="hand2", **kwargs)
        self.account_key = account_key
        self.server_id = server_id
        self.username = username
        self.on_select = on_select
        self.on_logout = on_logout
        self.on_delete = on_delete
        self.is_selected = False
        self.is_connected = False
        self._status_type = "disconnected"

        self._build_ui()
        self._bind_clicks(self)

    def _build_ui(self):
        # Dòng 1: Tên tài khoản & Server ID
        self.header_frame = tk.Frame(self, bg=CARD)
        self.header_frame.pack(fill="x", expand=True)

        srv_str = f"S{self.server_id}" if self.server_id else ""
        title_text = f"[{srv_str}] {self.username}" if self.username else "Tài khoản mới"
        self.title_lbl = tk.Label(
            self.header_frame,
            text=title_text,
            font=("Segoe UI", 10, "bold"),
            fg=FG,
            bg=CARD,
            anchor="w",
        )
        self.title_lbl.pack(side="left", fill="x", expand=True)

        # Dòng 2: Trạng thái kết nối
        self.status_frame = tk.Frame(self, bg=CARD)
        self.status_frame.pack(fill="x", expand=True, pady=(3, 0))

        self.badge_lbl = tk.Label(
            self.status_frame,
            text="⚪ Chưa đăng nhập",
            font=("Segoe UI", 8),
            fg="#8a90b0",
            bg=CARD,
            anchor="w",
        )
        self.badge_lbl.pack(side="left")

        # Dòng 3: Tóm tắt tác vụ bot đang chạy
        self.task_lbl = tk.Label(
            self,
            text="Nghỉ",
            font=("Segoe UI", 8),
            fg="#6c7bff",
            bg=CARD,
            anchor="w",
        )
        self.task_lbl.pack(fill="x", expand=True, pady=(2, 0))

    def _bind_clicks(self, widget):
        widget.bind("<Button-1>", lambda e: self.on_select(self.account_key))
        widget.bind("<Button-3>", self._show_context_menu)
        for child in widget.winfo_children():
            self._bind_clicks(child)

    def _show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg=CARD, fg=FG, activebackground=ACCENT, activeforeground="white")
        if self.is_connected and self.on_logout:
            menu.add_command(label="🚪 Đăng xuất", command=lambda: self.on_logout(self.account_key))
        if self.on_delete:
            menu.add_command(label="🗑️ Xóa tài khoản", command=lambda: self.on_delete(self.account_key))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def update_info(self, server_id, username):
        self.server_id = server_id
        self.username = username
        srv_str = f"S{self.server_id}" if self.server_id else ""
        title_text = f"[{srv_str}] {self.username}" if self.username else "Tài khoản mới"
        self.title_lbl.config(text=title_text)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        bg_col = "#2a2e45" if selected else CARD
        border_col = ACCENT if selected else CARD
        self.configure(bg=bg_col, highlightbackground=border_col, highlightthickness=2 if selected else 0)
        self.header_frame.configure(bg=bg_col)
        self.title_lbl.configure(bg=bg_col)
        self.status_frame.configure(bg=bg_col)
        self.badge_lbl.configure(bg=bg_col)
        self.task_lbl.configure(bg=bg_col)

    def set_status(self, status_type: str, status_text: str):
        self._status_type = status_type
        colors = {
            "disconnected": ("⚪", "#8a90b0"),
            "connecting": ("🟡", "#ffc107"),
            "connected": ("🟢", "#28a745"),
            "captcha": ("⚠️", "#ffc107"),
            "error": ("🔴", "#dc3545"),
        }
        icon, col = colors.get(status_type, ("⚪", "#8a90b0"))
        self.badge_lbl.configure(text=f"{icon} {status_text}", fg=col)
        self.is_connected = status_type in ("connected", "captcha")

    def set_tasks_summary(self, summary_text: str):
        self.task_lbl.configure(text=summary_text or "Nghỉ")


class MultiAccountApp(tk.Tk):
    """Cửa sổ ứng dụng hợp nhất quản lý và chạy đồng thời nhiều tài khoản Linh Vương."""

    def __init__(self):
        super().__init__()
        self.title("LinhVuong - Quản Lý Đa Tài Khoản")
        set_app_icon(self)
        self.geometry("1280x750")
        self.minsize(1100, 650)
        self.configure(bg=BG)

        self.accounts: dict[str, dict] = {}
        self.cards: dict[str, AccountCard] = {}
        self.login_frames: dict[str, AccountLoginFrame] = {}
        self.dashboards: dict[str, Any] = {}
        self.current_key: Optional[str] = None
        self._is_closing = False

        self._init_styles()
        self._build_ui()
        self._load_accounts()

        from tkinter import messagebox
        self.messagebox = messagebox

        self.protocol("WM_DELETE_WINDOW", self._on_close_app)
        self.after(1000, self._poll_statuses)

    def _init_styles(self):
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
        style.configure("Sidebar.TButton", font=("Segoe UI", 9, "bold"), padding=6)
        style.configure("StartAll.TButton", background="#28a745", foreground="white", font=("Segoe UI", 9, "bold"), padding=6)
        style.map("StartAll.TButton", background=[("active", "#34c759"), ("disabled", "#444a70")])
        style.configure("StopAll.TButton", background="#dc3545", foreground="white", font=("Segoe UI", 9, "bold"), padding=6)
        style.map("StopAll.TButton", background=[("active", "#ff453a"), ("disabled", "#444a70")])
        style.configure("Coffee.TButton", background="#c89666", foreground="white", font=("Segoe UI", 9, "bold"), padding=6)
        style.map("Coffee.TButton", background=[("active", "#d4a373"), ("disabled", "#444a70")])

    def _build_ui(self):
        # 1. Thanh điều hướng bên trái (Sidebar)
        self.sidebar_frame = tk.Frame(self, bg=CARD, width=250)
        self.sidebar_frame.pack(side="left", fill="y", padx=(0, 2))
        self.sidebar_frame.pack_propagate(False)

        # Header của sidebar
        sidebar_header = tk.Frame(self.sidebar_frame, bg=CARD, padx=12, pady=12)
        sidebar_header.pack(fill="x")

        self.brand_icon = load_app_image()
        self.brand_lbl = tk.Label(
            sidebar_header,
            text=" Linh Vương" if self.brand_icon else "Linh Vương",
            image=self.brand_icon if self.brand_icon else "",
            compound="left" if self.brand_icon else "none",
            font=("Segoe UI", 13, "bold"),
            fg=ACCENT,
            bg=CARD,
        )
        self.brand_lbl.pack(anchor="w")

        add_btn = ttk.Button(
            sidebar_header,
            text="➕ Thêm tài khoản",
            style="Sidebar.TButton",
            command=self._on_add_account,
        )
        add_btn.pack(fill="x", pady=(10, 0))

        # Danh sách thẻ tài khoản có thanh cuộn
        list_container = tk.Frame(self.sidebar_frame, bg=CARD)
        list_container.pack(fill="both", expand=True)

        self.cards_canvas = tk.Canvas(list_container, bg=CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.cards_canvas.yview)
        self.cards_inner = tk.Frame(self.cards_canvas, bg=CARD)

        self.cards_inner.bind(
            "<Configure>",
            lambda e: self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all")),
        )
        self.cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_inner, anchor="nw")
        self.cards_canvas.configure(yscrollcommand=scrollbar.set)

        self.cards_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.cards_canvas.bind("<Configure>", self._on_canvas_configure)

        # Thanh tiện ích / ủng hộ ở dưới đáy sidebar
        bottom_bar = tk.Frame(self.sidebar_frame, bg=CARD, padx=12, pady=12)
        bottom_bar.pack(fill="x", side="bottom")

        self.coffee_btn = ttk.Button(
            bottom_bar,
            text="☕ Buy me a coffee",
            style="Coffee.TButton",
            command=self._show_coffee_dialog,
        )
        self.coffee_btn.pack(fill="x", pady=2)

        # 2. Khung làm việc bên phải (Workspace)
        self.workspace_frame = tk.Frame(self, bg=BG)
        self.workspace_frame.pack(side="right", fill="both", expand=True)

        # Thanh header của Workspace
        self.workspace_header = tk.Frame(self.workspace_frame, bg="#181b27", height=46, padx=16)
        self.workspace_header.pack(fill="x")
        self.workspace_header.pack_propagate(False)

        header_left = tk.Frame(self.workspace_header, bg="#181b27")
        header_left.pack(side="left", fill="y")

        self.header_title = tk.Label(
            header_left,
            text="Chưa chọn tài khoản",
            font=("Segoe UI", 12, "bold"),
            fg=FG,
            bg="#181b27",
        )
        self.header_title.pack(side="left", pady=10)

        self.header_status = tk.Label(
            header_left,
            text="",
            font=("Segoe UI", 9),
            fg="#8a90b0",
            bg="#181b27",
        )
        self.header_status.pack(side="left", padx=(14, 0), pady=10)

        self.header_logout_btn = ttk.Button(
            self.workspace_header,
            text="🚪 Đăng xuất",
            command=self._on_current_logout,
        )

        # Thân của Workspace (chứa Login Frame hoặc Dashboard)
        self.workspace_content = tk.Frame(self.workspace_frame, bg=BG)
        self.workspace_content.pack(fill="both", expand=True)

    def _on_canvas_configure(self, event):
        self.cards_canvas.itemconfig(self.cards_window, width=event.width)

    def _load_accounts(self):
        accounts_dict = {}
        last_account = ""
        if SETTINGS.exists():
            try:
                data = json.loads(SETTINGS.read_text(encoding="utf-8"))
                raw_accounts = data.get("accounts")
                if isinstance(raw_accounts, dict) and raw_accounts:
                    accounts_dict = dict(raw_accounts)
                elif data.get("username"):
                    srv = data.get("server", "")
                    usr = data.get("username", "")
                    k = f"{usr} @ S{srv}"
                    accounts_dict[k] = {
                        "server": srv,
                        "username": usr,
                        "proxy_url": data.get("proxy_url", ""),
                        "proxy": data.get("proxy", ""),
                        "proxy_user": data.get("proxy_user", ""),
                        "proxy_pass": data.get("proxy_pass", ""),
                    }
                last_account = data.get("last_account", "")
            except Exception:
                pass

        for k, v in accounts_dict.items():
            self._add_account_entry(k, v)

        if not self.accounts:
            self._on_add_account()
        else:
            select_key = last_account if last_account in self.accounts else next(iter(self.accounts.keys()))
            self._select_account(select_key)

    def _add_account_entry(self, key: str, data: dict):
        self.accounts[key] = {
            "server": data.get("server", ""),
            "username": data.get("username", ""),
            "proxy_url": data.get("proxy_url", ""),
            "proxy": data.get("proxy", "") or data.get("proxy_raw", ""),
            "proxy_user": data.get("proxy_user", ""),
            "proxy_pass": data.get("proxy_pass", ""),
            "password": "",  # RAM ONLY
            "session": None,
            "proxy_pool": None,
        }
        card = AccountCard(
            self.cards_inner,
            account_key=key,
            server_id=data.get("server", ""),
            username=data.get("username", ""),
            on_select=self._select_account,
            on_logout=self._on_logout,
            on_delete=self._on_delete_account,
        )
        card.pack(fill="x", expand=True, padx=6, pady=4)
        self.cards[key] = card

    def _select_account(self, key: str):
        if key not in self.accounts:
            return

        # Bỏ chọn thẻ cũ
        if self.current_key and self.current_key in self.cards:
            self.cards[self.current_key].set_selected(False)
        if self.current_key in self.login_frames:
            self.login_frames[self.current_key].pack_forget()
        if self.current_key in self.dashboards:
            self.dashboards[self.current_key].pack_forget()

        self.current_key = key
        card = self.cards.get(key)
        if card:
            card.set_selected(True)

        acc = self.accounts[key]
        dash = self.dashboards.get(key)

        if dash and getattr(dash, "winfo_exists", lambda: False)():
            dash.pack(fill="both", expand=True)
            srv_str = f"S{acc.get('server')}" if acc.get('server') else ""
            self.header_title.config(text=f"[{srv_str}] {acc.get('username')}")
            self.header_status.config(text="🟢 Đã kết nối", fg="#28a745")
            self.header_logout_btn.pack(side="right", padx=12, pady=8)
        else:
            lf = self.login_frames.get(key)
            if not lf or not getattr(lf, "winfo_exists", lambda: False)():
                captured_key = key
                lf = AccountLoginFrame(
                    self.workspace_content,
                    account_data=acc,
                    on_login_success=lambda **kw: self._on_login_success(captured_key, **kw),
                )
                self.login_frames[key] = lf
            lf.pack(fill="none", expand=True, pady=20)
            srv_str = f"S{acc.get('server')}" if acc.get('server') else ""
            usr = acc.get("username")
            title_text = f"[{srv_str}] {usr}" if usr else "Tài khoản mới"
            self.header_title.config(text=title_text)
            self.header_status.config(text="⚪ Chưa đăng nhập", fg="#8a90b0")
            self.header_logout_btn.pack_forget()

    def _on_add_account(self):
        draft_idx = 1
        draft_key = f"Tài khoản mới #{draft_idx}"
        while draft_key in self.accounts:
            draft_idx += 1
            draft_key = f"Tài khoản mới #{draft_idx}"

        self._add_account_entry(draft_key, {"server": "", "username": "", "proxy": ""})
        self._select_account(draft_key)

    def _on_login_success(
        self,
        account_key: str,
        session: requests.Session,
        server_id: int,
        username: str,
        password: str,
        proxy_raw: str,
        proxy_user: str,
        proxy_pass: str,
        proxy_url: str,
        proxy_pool: Optional[Any],
    ):
        canonical_key = f"{username} @ S{server_id}"

        # Nếu là tài khoản mới hoặc key thay đổi
        if canonical_key != account_key:
            old_card = self.cards.pop(account_key, None)
            if old_card:
                old_card.destroy()
            old_lf = self.login_frames.pop(account_key, None)
            if old_lf:
                old_lf.destroy()
            self.accounts.pop(account_key, None)

            if canonical_key not in self.cards:
                self._add_account_entry(canonical_key, {
                    "server": server_id,
                    "username": username,
                    "proxy_url": proxy_url,
                    "proxy": proxy_raw,
                    "proxy_user": proxy_user,
                    "proxy_pass": proxy_pass,
                })
            self.current_key = canonical_key

        acc = self.accounts[self.current_key]
        acc.update({
            "server": server_id,
            "username": username,
            "proxy_url": proxy_url,
            "proxy": proxy_raw,
            "proxy_user": proxy_user,
            "proxy_pass": proxy_pass,
            "password": password,  # RAM ONLY
            "session": session,
            "proxy_pool": proxy_pool,
        })
        self._persist_settings()

        card = self.cards.get(self.current_key)
        if card:
            card.account_key = self.current_key
            card.update_info(server_id, username)
            card.set_status("connected", "Đã kết nối")
            card.set_selected(True)

        if self.current_key in self.login_frames:
            self.login_frames[self.current_key].pack_forget()

        if self.current_key in self.dashboards:
            try:
                self.dashboards[self.current_key].destroy()
            except Exception:
                pass

        from .dashboard import Dashboard

        dash = Dashboard(
            session=session,
            server_id=server_id,
            username=username,
            password=password,
            proxy_raw=proxy_raw,
            proxy_user=proxy_user,
            proxy_pass=proxy_pass,
            proxy_pool=proxy_pool,
            master=self.workspace_content,
        )
        self.dashboards[self.current_key] = dash
        dash.pack(fill="both", expand=True)

        srv_str = f"S{server_id}"
        self.header_title.config(text=f"[{srv_str}] {username}")
        self.header_status.config(text="🟢 Đã kết nối", fg="#28a745")
        self.header_logout_btn.pack(side="right", padx=12, pady=8)

    def _on_current_logout(self):
        if self.current_key:
            self._on_logout(self.current_key)

    def _on_logout(self, account_key: str):
        dash = self.dashboards.pop(account_key, None)
        if dash:
            try:
                dash.destroy()
            except Exception:
                pass

        acc = self.accounts.get(account_key)
        if acc:
            acc["password"] = ""  # Xóa sạch mật khẩu trong RAM
            acc["session"] = None

        lf = self.login_frames.get(account_key)
        if lf and getattr(lf, "winfo_exists", lambda: False)():
            lf.reset()

        card = self.cards.get(account_key)
        if card:
            card.set_status("disconnected", "Chưa đăng nhập")
            card.set_tasks_summary("Nghỉ")

        if self.current_key == account_key:
            self._select_account(account_key)

    def _on_delete_account(self, account_key: str):
        from tkinter import messagebox
        if not messagebox.askyesno("Xác nhận xóa", f"Bạn có chắc muốn xóa tài khoản '{account_key}' khỏi danh bạ?"):
            return

        self._on_logout(account_key)
        self.accounts.pop(account_key, None)
        self._persist_settings()

        card = self.cards.pop(account_key, None)
        if card:
            card.destroy()

        lf = self.login_frames.pop(account_key, None)
        if lf:
            lf.destroy()

        if self.current_key == account_key:
            self.current_key = None
            remaining = list(self.accounts.keys())
            if remaining:
                self._select_account(remaining[0])
            else:
                self._on_add_account()

    def _persist_settings(self):
        clean_accounts = {}
        for k, v in self.accounts.items():
            u = v.get("username", "")
            s = v.get("server", "")
            if not u or not s:
                continue
            clean_accounts[k] = {
                "server": s,
                "username": u,
                "proxy_url": v.get("proxy_url", ""),
                "proxy": v.get("proxy", "") or v.get("proxy_raw", ""),
                "proxy_user": v.get("proxy_user", ""),
                "proxy_pass": v.get("proxy_pass", ""),
            }
        last_acc = self.current_key if (self.current_key and self.current_key in clean_accounts) else ""
        first_acc = next(iter(clean_accounts.values()), {})
        data = {
            "server": first_acc.get("server", ""),
            "username": first_acc.get("username", ""),
            "proxy_url": first_acc.get("proxy_url", ""),
            "proxy": first_acc.get("proxy", ""),
            "proxy_user": first_acc.get("proxy_user", ""),
            "proxy_pass": first_acc.get("proxy_pass", ""),
            "last_account": last_acc,
            "accounts": clean_accounts,
        }
        try:
            SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _batch_start_all(self):
        from tkinter import messagebox
        started_count = 0
        for key, dash in self.dashboards.items():
            if dash and getattr(dash, "winfo_exists", lambda: False)():
                try:
                    if hasattr(dash, "engine"):
                        dash.engine.start_all()
                    started_count += 1
                except Exception:
                    pass
        if started_count > 0:
            messagebox.showinfo("Bắt đầu tất cả", f"Đã gửi lệnh kích hoạt tự động hóa cho {started_count} tài khoản đang kết nối.")
        else:
            messagebox.showwarning("Thông báo", "Không có tài khoản nào đang kết nối để kích hoạt.")

    def _batch_stop_all(self):
        from tkinter import messagebox
        stopped_count = 0
        for key, dash in self.dashboards.items():
            if dash and getattr(dash, "winfo_exists", lambda: False)():
                try:
                    if hasattr(dash, "engine"):
                        dash.engine.stop_all()
                    if hasattr(dash, "_tp_runner") and dash._tp_runner:
                        dash._tp_runner.stop()
                    stopped_count += 1
                except Exception:
                    pass
        if stopped_count > 0:
            messagebox.showinfo("Dừng tất cả", f"Đã tạm dừng tự động hóa cho {stopped_count} tài khoản.")

    def _show_coffee_dialog(self):
        """Hiển thị cửa sổ modal Buy me a coffee kèm mã QR và lời cảm ơn."""
        dialog = tk.Toplevel(self)
        dialog.title("Ủng Hộ Tác Giả - Buy Me A Coffee")
        dialog.configure(bg=CARD)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Tiêu đề & lời cảm ơn
        header_frame = tk.Frame(dialog, bg=CARD, padx=20, pady=12)
        header_frame.pack(fill="x")

        tk.Label(
            header_frame,
            text="☕ Buy Me A Coffee",
            font=("Segoe UI", 13, "bold"),
            fg="#e0a96d",
            bg=CARD,
        ).pack(pady=(0, 4))

        tk.Label(
            header_frame,
            text="Cảm ơn bạn đã tin tưởng và đồng hành cùng Auto Linh Vương!\nSự ủng hộ của bạn là động lực lớn để dự án tiếp tục phát triển.",
            font=("Segoe UI", 9),
            fg=FG,
            bg=CARD,
            justify="center",
        ).pack()

        # Ảnh QR Code
        qr_photo = load_coffee_qr_image(300, 400)
        if qr_photo:
            qr_frame = tk.Frame(dialog, bg="#181b27", padx=8, pady=8)
            qr_frame.pack(padx=20, pady=8)

            qr_lbl = tk.Label(qr_frame, image=qr_photo, bg="#181b27")
            qr_lbl.image = qr_photo  # Giữ tham chiếu tránh bị Garbage Collection thu hồi
            qr_lbl.pack()
        else:
            tk.Label(
                dialog,
                text="Không tìm thấy tệp mã QR (qrcode.png)",
                fg="#dc3545",
                bg=CARD,
                font=("Segoe UI", 9, "italic"),
            ).pack(padx=20, pady=20)

        # Nút Đóng
        btn_frame = tk.Frame(dialog, bg=CARD, padx=20, pady=10)
        btn_frame.pack(fill="x")

        close_btn = ttk.Button(
            btn_frame,
            text="Đóng",
            style="Sidebar.TButton",
            command=dialog.destroy,
        )
        close_btn.pack(ipadx=16)

        # Căn giữa cửa sổ dialog so với cửa sổ cha
        dialog.update_idletasks()
        try:
            x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_width()) // 2
            y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_height()) // 2
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _poll_statuses(self):
        try:
            for key, dash in list(self.dashboards.items()):
                if not dash or not getattr(dash, "winfo_exists", lambda: False)():
                    continue

                needs_captcha = False
                if hasattr(dash, "engine") and hasattr(dash.engine, "tasks"):
                    for task in dash.engine.tasks.values():
                        err = str(getattr(task, "last_error", "") or "")
                        msg = str(getattr(task, "status_message", "") or "")
                        if "Captcha" in err or "Captcha" in msg:
                            needs_captcha = True
                            break

                active = []
                if getattr(dash, "_tp_running", False):
                    active.append("⚔️ Thảo Phạt")
                if getattr(dash, "_bm_runner", None) and getattr(dash._bm_runner, "is_running", lambda: True)():
                    active.append("🏕️ Bình Man")
                if getattr(dash, "_bld_runner", None) and getattr(dash._bld_runner, "is_running", lambda: True)():
                    active.append("🏗️ Xây Dựng")
                if getattr(dash, "_res_runner", None) and getattr(dash._res_runner, "is_running", lambda: True)():
                    active.append("🔬 Nghiên Cứu")
                if getattr(dash, "_morale_runner", None) and getattr(dash._morale_runner, "is_running", lambda: True)():
                    active.append("🧘 Sĩ Khí")
                if getattr(dash, "_craft_running", False):
                    active.append("🛡️ Rèn Quân")
                if getattr(dash, "_gd_runner", None) and getattr(dash._gd_runner, "is_running", lambda: True)():
                    active.append("🧛 Gọi Dân")

                card = self.cards.get(key)
                if card:
                    if needs_captcha:
                        card.set_status("captcha", "Cần giải Captcha")
                    else:
                        card.set_status("connected", "Đang chạy" if active else "Đã kết nối")
                    card.set_tasks_summary(" | ".join(active) if active else "Nghỉ")

                if key == self.current_key:
                    if needs_captcha:
                        self.header_status.config(text="⚠️ Cần giải Captcha", fg="#ffc107")
                    else:
                        st_text = "🟢 Đang chạy" if active else "🟢 Đã kết nối"
                        self.header_status.config(text=st_text, fg="#28a745")
        except Exception:
            pass
        finally:
            if not self._is_closing:
                self.after(1000, self._poll_statuses)

    def _on_close_app(self):
        from tkinter import messagebox
        running_accounts = []
        for key, dash in self.dashboards.items():
            if dash and getattr(dash, "winfo_exists", lambda: False)():
                is_running = (
                    getattr(dash, "_tp_running", False)
                    or (getattr(dash, "_bm_runner", None) and getattr(dash._bm_runner, "is_running", lambda: True)())
                    or (getattr(dash, "_bld_runner", None) and getattr(dash._bld_runner, "is_running", lambda: True)())
                    or (getattr(dash, "_res_runner", None) and getattr(dash._res_runner, "is_running", lambda: True)())
                    or (getattr(dash, "_morale_runner", None) and getattr(dash._morale_runner, "is_running", lambda: True)())
                )
                if is_running:
                    running_accounts.append(key)

        if running_accounts:
            msg = (
                f"Đang có {len(running_accounts)} tài khoản đang chạy tác vụ tự động ngầm:\n"
                + "\n".join(f"• {acc}" for acc in running_accounts[:5])
                + ("\n..." if len(running_accounts) > 5 else "")
                + "\n\nBạn có chắc chắn muốn dừng toàn bộ và thoát ứng dụng?"
            )
            if not messagebox.askyesno("Xác nhận thoát", msg):
                return

        self._is_closing = True
        for dash in list(self.dashboards.values()):
            try:
                dash.destroy()
            except Exception:
                pass

        self.destroy()


def ask_login():
    """Hiện cửa sổ đăng nhập; trả (session, server_id, username, password, proxy_raw, proxy_user, proxy_pass, proxy_pool) hoặc None nếu đóng cửa sổ."""
    win = LoginWindow()
    win.mainloop()
    if win.session:
        user = getattr(win, "username", win.user_var.get().strip())
        pwd = getattr(win, "password", win.pass_var.get())
        p_raw = getattr(win, "proxy_raw", win.proxy_var.get().strip())
        p_user = getattr(win, "proxy_user", win.proxy_user_var.get().strip())
        p_pass = getattr(win, "proxy_pass", win.proxy_pass_var.get())
        p_pool = getattr(win, "proxy_pool", None)
        return (win.session, win.server_id, user, pwd, p_raw, p_user, p_pass, p_pool)
    return None


if __name__ == "__main__":
    app = MultiAccountApp()
    app.mainloop()
