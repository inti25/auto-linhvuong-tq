"""Tab Chiến Trường, Mưu Lược và Cài Đặt Thông Báo & Bắt Sống BOSS."""

import threading
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..battle import (
    ATTACK_ACTION_COMBO_OPTIONS,
    ATTACK_ACTIONS,
    FORMATION_NAMES,
    STRATAGEMS,
    BattleController,
    BattleState,
    CombatConfig,
    parse_attack_action_combo,
)
from ..notifications import NotificationConfig, dispatch_boss_alert as _default_dispatch_boss_alert
from .shared import (
    BG,
    CARD,
    COMBAT_MAX_LOG_LINES,
    COMBAT_TRIM_LINES,
    FG,
    MUTED,
    SUCCESS,
    apply_action_mode_widgets,
    resolve_dashboard_symbol,
    sync_action_mode_from_combo,
)


class BattleMixin:
    """Quản lý tác chiến chiến trường, cấu hình thông báo đa kênh và bắt sống BOSS."""

    def _collect_combat_profile_dict(self) -> dict:
        return {
            "auto_counter_formation": bool(self.bt_auto_counter_var.get()) if hasattr(self, "bt_auto_counter_var") else True,
            "formation_window_seconds": self.bt_window_var.get() if hasattr(self, "bt_window_var") else "15",
            "attack_action_mode": self.bt_action_mode_var.get() if hasattr(self, "bt_action_mode_var") else "adaptive",
            "action_combo_idx": self.bt_action_mode_combo.current() if hasattr(self, "bt_action_mode_combo") else 0,
            "skip_confused_enemy": bool(self.bt_skip_confused_var.get()) if hasattr(self, "bt_skip_confused_var") else True,
            "leave_boss_last": bool(self.bt_leave_boss_var.get()) if hasattr(self, "bt_leave_boss_var") else True,
            "auto_cleanse_confusion": bool(self.bt_cleanse_var.get()) if hasattr(self, "bt_cleanse_var") else True,
            "emergency_retreat_threshold": self.bt_retreat_var.get() if hasattr(self, "bt_retreat_var") else "0",
            "stratagem_combo_idx": self.bt_stratagem_combo.current() if hasattr(self, "bt_stratagem_combo") else 0,
            "auto_capture_boss": bool(self.bt_auto_capture_boss_var.get()) if hasattr(self, "bt_auto_capture_boss_var") else False,
            "capture_boss_max_morale": self.bt_capture_morale_var.get() if hasattr(self, "bt_capture_morale_var") else "60",
        }

    def _apply_combat_profile_dict(self, cb_data: dict) -> None:
        if hasattr(self, "bt_auto_counter_var") and "auto_counter_formation" in cb_data:
            self.bt_auto_counter_var.set(bool(cb_data["auto_counter_formation"]))
        if hasattr(self, "bt_window_var") and "formation_window_seconds" in cb_data:
            self.bt_window_var.set(str(cb_data["formation_window_seconds"]))
        apply_action_mode_widgets(
            getattr(self, "bt_action_mode_var", None),
            getattr(self, "bt_action_mode_combo", None),
            cb_data.get("attack_action_mode") if "attack_action_mode" in cb_data else None,
            cb_data.get("action_combo_idx") if "action_combo_idx" in cb_data else None,
        )
        if hasattr(self, "bt_skip_confused_var") and "skip_confused_enemy" in cb_data:
            self.bt_skip_confused_var.set(bool(cb_data["skip_confused_enemy"]))
        if hasattr(self, "bt_leave_boss_var") and "leave_boss_last" in cb_data:
            self.bt_leave_boss_var.set(bool(cb_data["leave_boss_last"]))
        if hasattr(self, "bt_cleanse_var") and "auto_cleanse_confusion" in cb_data:
            self.bt_cleanse_var.set(bool(cb_data["auto_cleanse_confusion"]))
        if hasattr(self, "bt_retreat_var") and "emergency_retreat_threshold" in cb_data:
            self.bt_retreat_var.set(str(cb_data["emergency_retreat_threshold"]))
        if hasattr(self, "bt_stratagem_combo") and "stratagem_combo_idx" in cb_data:
            try:
                self.bt_stratagem_combo.current(int(cb_data["stratagem_combo_idx"]))
            except Exception:
                pass
        if hasattr(self, "bt_auto_capture_boss_var") and "auto_capture_boss" in cb_data:
            self.bt_auto_capture_boss_var.set(bool(cb_data["auto_capture_boss"]))
        if hasattr(self, "bt_capture_morale_var") and "capture_boss_max_morale" in cb_data:
            self.bt_capture_morale_var.set(str(cb_data["capture_boss_max_morale"]))

    def _open_notification_settings_dialog(self):
        """Mở cửa sổ cài đặt Thông Báo Đa Kênh & Tự Động Bắt Sống BOSS (Coin) (ADR-0036)."""
        if hasattr(self, "_notify_win") and self._notify_win and self._notify_win.winfo_exists():
            self._notify_win.lift()
            self._notify_win.focus_force()
            return

        win = tk.Toplevel(self)
        win.title("🔔 Cài Đặt Thông Báo & Bắt Sống BOSS (Coin)")
        win.geometry("520x480")
        win.configure(bg=BG)
        win.resizable(False, False)
        self._notify_win = win

        # Khởi tạo biến từ self.notification_config và combat vars
        v_toast = tk.BooleanVar(value=self.notification_config.notify_desktop_toast)
        v_sound = tk.BooleanVar(value=self.notification_config.notify_sound)
        v_tele = tk.BooleanVar(value=self.notification_config.notify_telegram)
        v_token = tk.StringVar(value=self.notification_config.telegram_bot_token)
        v_chat_id = tk.StringVar(value=self.notification_config.telegram_chat_id)

        v_capture = tk.BooleanVar(value=self.bt_auto_capture_boss_var.get() if hasattr(self, "bt_auto_capture_boss_var") else False)
        v_morale = tk.StringVar(value=self.bt_capture_morale_var.get() if hasattr(self, "bt_capture_morale_var") else "60")

        # Tiêu đề
        top_frame = tk.Frame(win, bg=BG)
        top_frame.pack(fill="x", padx=16, pady=(12, 6))
        tk.Label(
            top_frame,
            text="🔔 Cấu Hình Thông Báo & Bắt Sống BOSS",
            bg=BG,
            fg=FG,
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            top_frame,
            text="Cảnh báo tức thời khi phát hiện BOSS & Tự động bắt sống bằng Coin",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w")

        # Khung 1: Các kênh thông báo
        f_channels = ttk.LabelFrame(win, text="Kênh Thông Báo Cảnh Báo", style="Card.TLabelframe")
        f_channels.pack(fill="x", padx=16, pady=6)

        c1 = tk.Frame(f_channels, bg=CARD)
        c1.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(c1, text="🖥️ Thông báo Windows Native Desktop Toast", variable=v_toast, style="TCheckbutton").pack(anchor="w")

        c2 = tk.Frame(f_channels, bg=CARD)
        c2.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(c2, text="🔊 Chuông cảnh báo hệ thống (System Beep/Sound)", variable=v_sound, style="TCheckbutton").pack(anchor="w")

        c3 = tk.Frame(f_channels, bg=CARD)
        c3.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(c3, text="✈️ Gửi tin nhắn qua Telegram Bot", variable=v_tele, style="TCheckbutton").pack(anchor="w")

        f_tele = tk.Frame(f_channels, bg=CARD)
        f_tele.pack(fill="x", padx=8, pady=(2, 8))

        r_tok = tk.Frame(f_tele, bg=CARD)
        r_tok.pack(fill="x", pady=2)
        tk.Label(r_tok, text="Bot Token:", bg=CARD, fg=FG, font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
        e_token = ttk.Entry(r_tok, textvariable=v_token, width=38, show="*")
        e_token.pack(side="left", fill="x", expand=True)

        r_cid = tk.Frame(f_tele, bg=CARD)
        r_cid.pack(fill="x", pady=2)
        tk.Label(r_cid, text="Chat ID:", bg=CARD, fg=FG, font=("Segoe UI", 9), width=12, anchor="w").pack(side="left")
        e_cid = ttk.Entry(r_cid, textvariable=v_chat_id, width=38)
        e_cid.pack(side="left", fill="x", expand=True)

        # Khung 2: Tự Động Bắt Sống BOSS
        f_boss = ttk.LabelFrame(win, text="Tự Động Bắt Sống BOSS Bằng Coin", style="Card.TLabelframe")
        f_boss.pack(fill="x", padx=16, pady=6)

        b1 = tk.Frame(f_boss, bg=CARD)
        b1.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(
            b1,
            text="Tự động bắt sống BOSS bằng Coin khi chỉ còn BOSS",
            variable=v_capture,
            style="TCheckbutton",
        ).pack(anchor="w")

        b2 = tk.Frame(f_boss, bg=CARD)
        b2.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(b2, text="Ngưỡng sĩ khí kích hoạt bắt (Sĩ khí < ):", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        ttk.Entry(b2, textvariable=v_morale, width=6).pack(side="left", padx=(0, 4))
        tk.Label(b2, text="điểm (Mặc định 60)", bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")

        # Nhãn hiển thị trạng thái test
        status_lbl = tk.Label(win, text="", bg=BG, fg="#4da3ff", font=("Segoe UI", 9))
        status_lbl.pack(fill="x", padx=16, pady=(2, 2))

        # Khung nút thao tác
        btn_frame = tk.Frame(win, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=(8, 12))

        def on_test():
            dispatch_boss_alert_fn = resolve_dashboard_symbol("dispatch_boss_alert", _default_dispatch_boss_alert)
            status_lbl.config(text="Đang gửi thử nghiệm thông báo...", fg="#ff9f43")
            test_cfg = NotificationConfig(
                notify_desktop_toast=v_toast.get(),
                notify_sound=v_sound.get(),
                notify_telegram=v_tele.get(),
                telegram_bot_token=v_token.get().strip(),
                telegram_chat_id=v_chat_id.get().strip(),
            )
            server_id = getattr(self.roster, "server_id", 0) if getattr(self, "roster", None) else 0
            if not server_id and hasattr(self, "gateway") and hasattr(self.gateway, "server_id"):
                server_id = getattr(self.gateway, "server_id", 0)

            dispatch_boss_alert_fn(
                boss_name="[Thử Nghiệm] Tào Tháo",
                position=11,
                site="Chiến trường",
                battle_id=9999,
                server_id=int(server_id) if str(server_id).isdigit() else 0,
                config=test_cfg,
            )
            status_lbl.config(text="✅ Đã gửi tín hiệu thông báo thử nghiệm!", fg=SUCCESS)

        def on_save():
            self.notification_config.notify_desktop_toast = bool(v_toast.get())
            self.notification_config.notify_sound = bool(v_sound.get())
            self.notification_config.notify_telegram = bool(v_tele.get())
            self.notification_config.telegram_bot_token = v_token.get().strip()
            self.notification_config.telegram_chat_id = v_chat_id.get().strip()

            if hasattr(self, "bt_auto_capture_boss_var"):
                self.bt_auto_capture_boss_var.set(bool(v_capture.get()))
            m_val = v_morale.get().strip()
            if hasattr(self, "bt_capture_morale_var"):
                self.bt_capture_morale_var.set(m_val if m_val.isdigit() else "60")

            if hasattr(self, "_append_bt_log"):
                self._append_bt_log("🔔 Đã lưu cài đặt Thông báo và Tự động bắt sống BOSS bằng Coin.")
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()
            win.destroy()

        ttk.Button(btn_frame, text="🧪 Thử Nghiệm Thông Báo", style="Action.TButton", command=on_test).pack(side="left")
        ttk.Button(btn_frame, text="💾 Lưu Cấu Hình", style="Success.TButton", command=on_save).pack(side="right")
        ttk.Button(btn_frame, text="Đóng", command=win.destroy).pack(side="right", padx=(0, 6))

    # =========================================================================
    # TAB 6: CHIẾN TRƯỜNG & MƯU LƯỢC
    # =========================================================================
    def _build_battle_tab(self, parent):
        top_ctrl = tk.Frame(parent, bg=BG)
        top_ctrl.pack(fill="x", pady=6)

        # Hàng 1: Mã Chiến Trường, Nút Nạp, Nút Bắt đầu/Dừng Theo dõi tự động, Hiệp đấu, Đếm ngược
        row1 = tk.Frame(top_ctrl, bg=BG)
        row1.pack(fill="x", pady=(0, 4))

        tk.Label(row1, text="Mã Chiến Trường (ID):", bg=BG, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
        self.bt_id_var = tk.StringVar(value="0")
        ttk.Entry(row1, textvariable=self.bt_id_var, width=10).pack(side="left", padx=(0, 8))

        ttk.Button(row1, text="🔍 Nạp Chiến Trường", style="Action.TButton", command=self._bt_load_battle).pack(side="left", padx=(0, 6))

        self.bt_start_btn = ttk.Button(row1, text="▶️ Theo Dõi & Tác Chiến", style="Success.TButton", command=self._bt_toggle_auto)
        self.bt_start_btn.pack(side="left", padx=(0, 16))

        self.bt_bout_var = tk.StringVar(value="Hiệp: -")
        tk.Label(row1, textvariable=self.bt_bout_var, bg=BG, fg="#4da3ff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 12))

        self.bt_countdown_var = tk.StringVar(value="Đếm ngược: -s")
        tk.Label(row1, textvariable=self.bt_countdown_var, bg=BG, fg="#ff9f43", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))

        # Khung cấu hình tác chiến
        cfg_frame = ttk.LabelFrame(top_ctrl, text="Thiết lập Tác chiến & Mưu lược", style="Card.TLabelframe")
        cfg_frame.pack(fill="x", pady=4, padx=2)

        cfg_r1 = tk.Frame(cfg_frame, bg=CARD)
        cfg_r1.pack(fill="x", pady=2, padx=4)

        self.bt_auto_counter_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r1, text="Tự đổi trận ngũ hành", variable=self.bt_auto_counter_var, style="TCheckbutton").pack(side="left", padx=(0, 12))

        tk.Label(cfg_r1, text="Cửa sổ đổi trận:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 2))
        self.bt_window_var = tk.StringVar(value="15")
        ttk.Entry(cfg_r1, textvariable=self.bt_window_var, width=4).pack(side="left", padx=(0, 2))
        tk.Label(cfg_r1, text="s cuối hiệp", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 12))

        self.bt_leave_boss_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r1, text="Giữ BOSS bắt sống (Thủ khi chỉ còn BOSS)", variable=self.bt_leave_boss_var, style="TCheckbutton").pack(side="left", padx=(0, 12))

        self.bt_cleanse_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r1, text="Tự giải Hỗn loạn (mưu kế 96)", variable=self.bt_cleanse_var, style="TCheckbutton").pack(side="left", padx=(0, 10))

        cfg_r2 = tk.Frame(cfg_frame, bg=CARD)
        cfg_r2.pack(fill="x", pady=2, padx=4)

        tk.Label(cfg_r2, text="Chiêu tấn công:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bt_action_mode_var = tk.StringVar(value="adaptive")
        self.bt_action_mode_combo = ttk.Combobox(cfg_r2, state="readonly", width=24)
        self.bt_action_mode_combo["values"] = list(ATTACK_ACTION_COMBO_OPTIONS)
        self.bt_action_mode_combo.current(0)
        self.bt_action_mode_combo.pack(side="left", padx=(0, 12))
        self.bt_action_mode_combo.bind("<<ComboboxSelected>>", self._on_bt_action_mode_changed)

        self.bt_skip_confused_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg_r2, text="Bỏ qua địch hỗn loạn", variable=self.bt_skip_confused_var, style="TCheckbutton").pack(side="left", padx=(0, 12))

        tk.Label(cfg_r2, text="Mưu kế Hiệp 1:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.bt_stratagem_combo = ttk.Combobox(cfg_r2, state="readonly", width=18)
        self.bt_stratagem_combo["values"] = [
            "0. Không dùng",
            "93. Phản khách vi chủ",
            "95. Cầm tặc cầm vương",
            "94. Quan môn tróc tặc",
        ]
        self.bt_stratagem_combo.current(0)
        self.bt_stratagem_combo.pack(side="left", padx=(0, 12))

        tk.Label(cfg_r2, text="Rút lui khẩn cấp (mưu 92 khi lính < %):", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.bt_retreat_var = tk.StringVar(value="0")
        ttk.Entry(cfg_r2, textvariable=self.bt_retreat_var, width=4).pack(side="left", padx=(0, 6))

        cfg_r3 = tk.Frame(cfg_frame, bg=CARD)
        cfg_r3.pack(fill="x", pady=2, padx=4)

        ttk.Checkbutton(
            cfg_r3,
            text="Tự động bắt sống BOSS bằng Coin",
            variable=self.bt_auto_capture_boss_var,
            style="TCheckbutton",
        ).pack(side="left", padx=(0, 8))

        tk.Label(cfg_r3, text="khi Sĩ khí <", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 2))
        ttk.Entry(cfg_r3, textvariable=self.bt_capture_morale_var, width=4).pack(side="left", padx=(0, 2))
        tk.Label(cfg_r3, text="điểm", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=(0, 16))

        ttk.Button(
            cfg_r3,
            text="🔔 Cài Đặt Thông Báo & Bắt Sống BOSS",
            style="Action.TButton",
            command=self._open_notification_settings_dialog,
        ).pack(side="left", padx=(0, 6))

        # Thân giao diện: 2 Bảng (Trái: Phe Ta, Phải: Phe Địch)
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure((0, 1), weight=1, uniform="bt")
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)

        # Trái: Bảng Quân Ta
        f_left = ttk.LabelFrame(body, text="🛡️ Phe Ta (Quân đội & Tướng lĩnh)", style="Card.TLabelframe")
        f_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))

        self.bt_our_tree = ttk.Treeview(
            f_left,
            columns=("pos", "army", "morale", "fid", "status", "action", "target"),
            show="tree headings",
            selectmode="browse",
        )
        self.bt_our_tree.heading("#0", text="Tên tướng")
        self.bt_our_tree.heading("pos", text="Vị trí")
        self.bt_our_tree.heading("army", text="Quân số")
        self.bt_our_tree.heading("morale", text="Sĩ khí")
        self.bt_our_tree.heading("fid", text="Trận hình")
        self.bt_our_tree.heading("status", text="Trạng thái")
        self.bt_our_tree.heading("action", text="Lệnh đánh")
        self.bt_our_tree.heading("target", text="Mục tiêu")

        self.bt_our_tree.column("#0", width=120)
        self.bt_our_tree.column("pos", width=40, anchor="center")
        self.bt_our_tree.column("army", width=75, anchor="e")
        self.bt_our_tree.column("morale", width=55, anchor="center")
        self.bt_our_tree.column("fid", width=85, anchor="center")
        self.bt_our_tree.column("status", width=75, anchor="center")
        self.bt_our_tree.column("action", width=85, anchor="center")
        self.bt_our_tree.column("target", width=55, anchor="center")

        our_scroll = ttk.Scrollbar(f_left, orient="vertical", command=self.bt_our_tree.yview)
        self.bt_our_tree.configure(yscrollcommand=our_scroll.set)
        self.bt_our_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        our_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)

        # Phải: Bảng Quân Địch
        f_right = ttk.LabelFrame(body, text="🎯 Phe Địch", style="Card.TLabelframe")
        f_right.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))

        self.bt_enemy_tree = ttk.Treeview(
            f_right,
            columns=("pos", "army", "morale", "fid", "status", "target"),
            show="tree headings",
            selectmode="browse",
        )
        self.bt_enemy_tree.heading("#0", text="Tên địch")
        self.bt_enemy_tree.heading("pos", text="Vị trí")
        self.bt_enemy_tree.heading("army", text="Quân số")
        self.bt_enemy_tree.heading("morale", text="Sĩ khí")
        self.bt_enemy_tree.heading("fid", text="Trận hình")
        self.bt_enemy_tree.heading("status", text="Trạng thái")
        self.bt_enemy_tree.heading("target", text="Mục tiêu")

        self.bt_enemy_tree.column("#0", width=120)
        self.bt_enemy_tree.column("pos", width=40, anchor="center")
        self.bt_enemy_tree.column("army", width=75, anchor="e")
        self.bt_enemy_tree.column("morale", width=55, anchor="center")
        self.bt_enemy_tree.column("fid", width=85, anchor="center")
        self.bt_enemy_tree.column("status", width=75, anchor="center")
        self.bt_enemy_tree.column("target", width=55, anchor="center")

        en_scroll = ttk.Scrollbar(f_right, orient="vertical", command=self.bt_enemy_tree.yview)
        self.bt_enemy_tree.configure(yscrollcommand=en_scroll.set)
        self.bt_enemy_tree.tag_configure("boss", foreground="#ff6b6b")
        self.bt_enemy_tree.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        en_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)

        # Khung nhật ký chiến trường & Hàng nút thao tác nhanh
        f_bottom = ttk.LabelFrame(body, text="Nhật ký chiến trường & Thao tác thủ công", style="Card.TLabelframe")
        f_bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(4, 0))

        # Hàng thao tác thủ công nhanh
        manual_bar = tk.Frame(f_bottom, bg=CARD)
        manual_bar.pack(fill="x", padx=6, pady=(4, 2))

        tk.Label(manual_bar, text="Đổi Trận:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bt_manual_formation_combo = ttk.Combobox(manual_bar, state="readonly", width=12)
        self.bt_manual_formation_combo["values"] = ["1. Trùy hình", "2. Câu hình", "3. Kê hình", "4. Hạc dực", "5. Ngư lân"]
        self.bt_manual_formation_combo.current(0)
        self.bt_manual_formation_combo.pack(side="left", padx=(0, 4))
        ttk.Button(manual_bar, text="🔄 Đổi ngay", style="Action.TButton", command=self._bt_manual_change_formation).pack(side="left", padx=(0, 12))

        tk.Label(manual_bar, text="Mưu kế:", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.bt_manual_stratagem_combo = ttk.Combobox(manual_bar, state="readonly", width=18)
        self.bt_manual_stratagem_combo["values"] = [
            "96. Hủy bỏ trạng thái",
            "92. Kim thiền thoát xác",
            "93. Phản khách vi chủ",
            "95. Cầm tặc cầm vương",
            "94. Quan môn tróc tặc",
        ]
        self.bt_manual_stratagem_combo.current(0)
        self.bt_manual_stratagem_combo.pack(side="left", padx=(0, 4))
        ttk.Button(manual_bar, text="✨ Kích hoạt", style="Action.TButton", command=self._bt_manual_cast_stratagem).pack(side="left", padx=(0, 12))

        ttk.Button(manual_bar, text="🛡️ Phòng ngự toàn quân", style="Action.TButton", command=self._bt_manual_defend_all).pack(side="left", padx=(0, 8))
        ttk.Button(manual_bar, text="🗑️ Xóa log", style="Action.TButton", command=self._bt_clear_log).pack(side="right", padx=4)

        # Log Text box
        log_frame = tk.Frame(f_bottom, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        self.bt_log_text = tk.Text(log_frame, bg="#0d0e15", fg="#dcdde1", font=("Consolas", 9), wrap="word")
        bt_log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.bt_log_text.yview)
        self.bt_log_text.configure(yscrollcommand=bt_log_scroll.set)
        self.bt_log_text.pack(side="left", fill="both", expand=True)
        bt_log_scroll.pack(side="right", fill="y")

    def _on_bt_action_mode_changed(self, event=None):
        sync_action_mode_from_combo(self.bt_action_mode_var, self.bt_action_mode_combo)

    def _append_bt_log(self, msg: str):
        if hasattr(self, "bt_log_text") and self.bt_log_text:
            line = msg if msg.endswith("\n") else (msg + "\n")
            self._append_text_buffer(
                self.bt_log_text,
                line,
                max_lines=COMBAT_MAX_LOG_LINES,
                trim_batch=COMBAT_TRIM_LINES,
            )

    def _bt_clear_log(self):
        if hasattr(self, "bt_log_text"):
            self.bt_log_text.delete("1.0", "end")

    def _bt_load_battle(self):
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0
        engine = BattleController(self.gateway)
        state = engine.get_battle_info(battle_id)
        if not state or state.ret != 0:
            self._append_bt_log(f"❌ Không tải được thông tin chiến trường (ID: {battle_id}, ret: {state.ret if state else 'None'})")
            return
        self._bt_render_state(state)
        self._append_bt_log(f"✅ Đã tải thông tin chiến trường '{state.site}' (ID: {battle_id}, Hiệp: {state.bout}, Còn lại: {state.bout_left}s)")
        if state.boss_troops:
            boss = state.boss_troops[0]
            extra = " Đang giữ lại để người chơi vào bắt sống!" if getattr(self.bt_leave_boss_var, "get", lambda: True)() else ""
            self._append_bt_log(f"🐉 PHÁT HIỆN BOSS [{boss.general_name}] tại vị trí {boss.position}!{extra}")

    def _bt_render_state(self, state: BattleState):
        self.bt_bout_var.set(f"Hiệp: {state.bout}")
        self.bt_countdown_var.set(f"Đếm ngược: {state.bout_left}s")

        # Cập nhật bảng quân ta
        self.bt_our_tree.delete(*self.bt_our_tree.get_children())
        for t in state.our_troops:
            fname = FORMATION_NAMES.get(t.formation_id, f"Trận {t.formation_id}")
            status_str = "Hỗn loạn" if t.status == 1 else "Bình thường"
            act_name = ATTACK_ACTIONS.get(t.attack_action, str(t.attack_action))
            target_str = str(t.target_id) if t.target_id != 0 else "Tùy chọn"
            self.bt_our_tree.insert(
                "", "end", iid=str(t.position), text=t.general_name,
                values=(t.position, f"{t.soldiers}/{t.initial_soldiers}", t.morale, fname, status_str, act_name, target_str)
            )

        # Cập nhật bảng quân địch
        self.bt_enemy_tree.delete(*self.bt_enemy_tree.get_children())
        for e in state.enemy_troops:
            fname = FORMATION_NAMES.get(e.formation_id, f"Trận {e.formation_id}")
            status_str = "Hỗn loạn" if e.status == 1 else ("BOSS" if e.is_boss else "Bình thường")
            target_str = str(e.target_id) if e.target_id != 0 else "Tùy chọn"
            self.bt_enemy_tree.insert(
                "", "end", iid=str(e.position), text=f"{e.general_name} {'👑' if e.is_boss else ''}",
                values=(e.position, f"{e.soldiers}/{e.initial_soldiers}", e.morale, fname, status_str, target_str),
                tags=("boss",) if e.is_boss else (),
            )

    def _bt_toggle_auto(self):
        if getattr(self, "_bt_running", False):
            self._bt_running = False
            if hasattr(self, "_bt_stop_event"):
                self._bt_stop_event.set()
            self.bt_start_btn.configure(text="▶️ Theo Dõi & Tác Chiến", style="Success.TButton")
            self._append_bt_log("⏹️ Đã dừng tiến trình theo dõi tác chiến tự động.")
        else:
            self._bt_running = True
            self._bt_stop_event = threading.Event()
            self.bt_start_btn.configure(text="⏹️ Dừng Theo Dõi", style="Danger.TButton")
            threading.Thread(target=self._bt_auto_thread, daemon=True).start()

    def _build_combat_config(self, action_combo_val: Optional[str] = None) -> CombatConfig:
        if action_combo_val is None:
            combo_val = self.bt_action_mode_combo.get() if hasattr(self, "bt_action_mode_combo") else ""
        else:
            combo_val = action_combo_val
        action_mode, fixed_id = parse_attack_action_combo(combo_val)

        s_val = self.bt_stratagem_combo.get() if hasattr(self, "bt_stratagem_combo") else ""
        s_id = int(s_val.split(".")[0]) if "." in s_val and s_val.split(".")[0].isdigit() else 0

        win_raw = self.bt_window_var.get() if hasattr(self, "bt_window_var") else "15"
        retreat_raw = self.bt_retreat_var.get() if hasattr(self, "bt_retreat_var") else "0"
        morale_raw = self.bt_capture_morale_var.get() if hasattr(self, "bt_capture_morale_var") else "60"
        server_id = getattr(self.roster, "server_id", 0) if getattr(self, "roster", None) else 0
        if not server_id and hasattr(self, "gateway") and hasattr(self.gateway, "server_id"):
            server_id = getattr(self.gateway, "server_id", 0)

        return CombatConfig(
            auto_counter_formation=bool(self.bt_auto_counter_var.get()) if hasattr(self, "bt_auto_counter_var") else True,
            formation_window_seconds=int(win_raw) if win_raw.isdigit() else 15,
            attack_action_mode=action_mode,
            fixed_action_id=fixed_id,
            skip_confused_enemy=bool(self.bt_skip_confused_var.get()) if hasattr(self, "bt_skip_confused_var") else True,
            leave_boss_last=bool(self.bt_leave_boss_var.get()) if hasattr(self, "bt_leave_boss_var") else True,
            auto_cleanse_confusion=bool(self.bt_cleanse_var.get()) if hasattr(self, "bt_cleanse_var") else True,
            emergency_retreat_threshold=int(retreat_raw) if retreat_raw.isdigit() else 0,
            offensive_stratagem_id=s_id,
            auto_capture_boss=bool(self.bt_auto_capture_boss_var.get()) if hasattr(self, "bt_auto_capture_boss_var") else False,
            capture_boss_max_morale=int(morale_raw) if str(morale_raw).isdigit() else 60,
            notification_config=getattr(self, "notification_config", None),
            server_id=int(server_id) if str(server_id).isdigit() else 0,
        )

    def _bt_auto_thread(self):
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0

        cfg = self._build_combat_config()

        self._append_bt_log(f"🚀 Bắt đầu động cơ tác chiến tự động cho chiến trường ID {battle_id}...")
        engine = BattleController(self.gateway, config=cfg)

        try:
            engine.track_battle(
                battle_id=battle_id,
                on_log=self._append_bt_log,
                on_boss_alert=self._append_bt_log,
                on_state=lambda st: self.after(0, lambda s=st: self._bt_render_state(s)),
                stop_event=self._bt_stop_event,
                config=cfg,
            )
            self._append_bt_log("🏁 Đã hoàn tất phiên theo dõi chiến trường.")
        except Exception as ex:
            self._append_bt_log(f"❌ Lỗi tác chiến: {ex}")
        finally:
            self._bt_running = False
            self.after(0, lambda: self.bt_start_btn.configure(text="▶️ Theo Dõi & Tác Chiến", style="Success.TButton"))

    def _bt_manual_change_formation(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.bt_our_tree.selection()
        if not sel:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn một tướng ta từ bảng danh sách bên trái để đổi trận hình!")
            return
        pos_id = int(sel[0])
        fid_str = self.bt_manual_formation_combo.get()
        fid = int(fid_str.split(".")[0]) if "." in fid_str else 1
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0

        engine = BattleController(self.gateway)
        st = engine.get_battle_info(battle_id)
        if not st:
            return
        target_troop = next((t for t in st.our_troops if t.position == pos_id), None)
        if not target_troop:
            return
        ok = engine._change_formation_preserving_plan(target_troop, fid, battle_id=battle_id)
        if ok:
            self._append_bt_log(f"🔄 Đã gửi lệnh đổi tướng [{target_troop.general_name}] sang {FORMATION_NAMES.get(fid, fid)}")
            self._bt_load_battle()
        else:
            self._append_bt_log(f"❌ Đổi trận hình thất bại cho tướng [{target_troop.general_name}]")

    def _bt_manual_cast_stratagem(self):
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.bt_our_tree.selection()
        if not sel:
            msgbox.showwarning("Cảnh báo", "Vui lòng chọn một tướng ta từ bảng danh sách bên trái để thi triển mưu kế!")
            return
        pos_id = int(sel[0])
        s_str = self.bt_manual_stratagem_combo.get()
        sid = int(s_str.split(".")[0]) if "." in s_str else 96
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0

        engine = BattleController(self.gateway)
        ok = engine.cast_stratagem(battle_id, pos_id, sid)
        s_name = STRATAGEMS.get(sid, f"Mưu kế {sid}")
        if ok:
            self._append_bt_log(f"✨ Đã thi triển mưu kế [{s_name}] lên vị trí {pos_id}")
            self._bt_load_battle()
        else:
            self._append_bt_log(f"❌ Thi triển mưu kế thất bại (vị trí {pos_id}, mưu kế {sid})")

    def _bt_manual_defend_all(self):
        raw_id = self.bt_id_var.get().strip() if hasattr(self, "bt_id_var") else "0"
        battle_id = int(raw_id) if raw_id.isdigit() else 0
        engine = BattleController(self.gateway)
        st = engine.get_battle_info(battle_id)
        if not st:
            return
        for our in st.our_troops:
            dest = our.target_id if our.target_id != 0 else (st.enemy_troops[0].position if st.enemy_troops else 0)
            engine.change_target_attack(battle_id, our.position, dest, action=3)
        self._append_bt_log("🛡️ Đã chuyển toàn bộ quân ta sang thế Phòng ngự (action 3)")
        self._bt_load_battle()
