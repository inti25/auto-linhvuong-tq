"""Cửa sổ Đào Tạo Tướng (Điểm Tướng Đài & Tụ Hiền Lâu — lặp lại hàng ngày) trên Dashboard."""

import logging
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox, ttk
from typing import Callable, Optional

from ..gui import set_app_icon
from ..tasks.base import CaptchaRequired
from ..tasks.training import (
    ALL_TRAIN_TYPES,
    MAX_TRAIN_SLOTS,
    TRAIN_TYPE_VAN,
    TRAIN_TYPE_VO,
    TrainingHallState,
    fetch_training_state,
    resolve_training_city_id,
    run_training_cycle,
)
from .shared import ACCENT, BG, CARD, FG, MUTED, ROLE_TEXT, resolve_dashboard_symbol

logger = logging.getLogger("linhvuong.dashboard")


def _format_hms(seconds: int) -> str:
    secs = max(0, int(seconds))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h}:{m:02d}:{s:02d}"


def _dedup_ids(raw_ids) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for x in raw_ids or ():
        try:
            gid = int(x)
        except (TypeError, ValueError):
            continue
        if gid > 0 and gid not in seen:
            seen.add(gid)
            out.append(gid)
    return out


class TrainingDialogMixin:
    """Quản lý tính năng Đào Tạo Tướng (Điểm Tướng Đài & Tụ Hiền Lâu) và tự động lặp 24h."""

    def _collect_training_profile_dict(self) -> dict:
        return {
            "enabled": bool(self.aux_training_var.get()) if hasattr(self, "aux_training_var") else False,
            "vo_general_ids": list(getattr(self, "_training_vo_ids", [])),
            "van_general_ids": list(getattr(self, "_training_van_ids", [])),
        }

    def _apply_training_profile_dict(self, train_data: dict) -> None:
        if not isinstance(train_data, dict):
            return
        if hasattr(self, "aux_training_var") and "enabled" in train_data:
            self.aux_training_var.set(bool(train_data["enabled"]))
        if "vo_general_ids" in train_data and isinstance(train_data["vo_general_ids"], list):
            self._training_vo_ids = _dedup_ids(train_data["vo_general_ids"])
        if "van_general_ids" in train_data and isinstance(train_data["van_general_ids"], list):
            self._training_van_ids = _dedup_ids(train_data["van_general_ids"])
        self._training_next_check_at = 0.0
        self._refresh_training_countdown_widgets()
        self._refresh_training_dialog_all()

    def _on_aux_training_toggled(self) -> None:
        self._training_next_check_at = 0.0
        self._refresh_training_countdown_widgets()
        if getattr(self, "aux_training_var", None) and self.aux_training_var.get():
            self._check_and_run_training(async_check=True)

    def _append_trn_log(self, msg: str, *, forward_to_bld: bool = False) -> None:
        if forward_to_bld and hasattr(self, "_append_bld_log"):
            try:
                if threading.current_thread() is threading.main_thread():
                    self._append_bld_log(msg)
                else:
                    self.after(0, self._append_bld_log, msg)
            except Exception:
                pass
        widget = getattr(self, "trn_log_text", None)
        if widget is not None and hasattr(widget, "winfo_exists"):
            try:
                if widget.winfo_exists():
                    self._append_text_buffer(widget, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            except Exception:
                pass

    def _summarize_hall_countdown(self, train_type: int) -> Optional[tuple[str, bool]]:
        state: Optional[TrainingHallState] = getattr(self, "_training_states", {}).get(train_type)
        if state is None:
            return None
        elapsed = max(0, int(time.monotonic() - state.checked_at))
        if state.unlocked_slots <= 0:
            return ("Chưa mở", False)
        if state.free_slots(elapsed):
            return ("Sẵn sàng", True)
        rem = state.min_active_remaining(elapsed)
        if rem > 0:
            return (_format_hms(rem), False)
        return ("--", False)

    def _refresh_training_countdown_widgets(self) -> None:
        if getattr(self, "_destroyed", False):
            return
        lbl = getattr(self, "aux_training_time_lbl", None)
        if lbl is not None:
            try:
                if lbl.winfo_exists():
                    vo_sum = self._summarize_hall_countdown(TRAIN_TYPE_VO)
                    van_sum = self._summarize_hall_countdown(TRAIN_TYPE_VAN)
                    if vo_sum or van_sum:
                        vo_txt = vo_sum[0] if vo_sum else "--"
                        van_txt = van_sum[0] if van_sum else "--"
                        any_ready = bool((vo_sum and vo_sum[1]) or (van_sum and van_sum[1]))
                        lbl.configure(
                            text=f"(Võ: {vo_txt} | Văn: {van_txt})",
                            fg="#fbbf24" if any_ready else "#4ade80",
                        )
                    else:
                        enabled = bool(getattr(self, "aux_training_var", None) and self.aux_training_var.get())
                        lbl.configure(
                            text="(Chờ kiểm tra)" if enabled else "(Tắt)",
                            fg="#94a3b8",
                        )
            except (RuntimeError, tk.TclError):
                pass

        # Cập nhật thẻ 5 ô trong hộp thoại nếu đang mở
        win = getattr(self, "_trn_dialog", None)
        slot_vars = getattr(self, "_trn_slot_vars", None)
        if win is not None and slot_vars:
            try:
                if win.winfo_exists():
                    hall_role = self.trn_hall_var.get() if hasattr(self, "trn_hall_var") else "vo"
                    ttype = TRAIN_TYPE_VAN if hall_role == "van" else TRAIN_TYPE_VO
                    state: Optional[TrainingHallState] = getattr(self, "_training_states", {}).get(ttype)
                    if state is None:
                        for pos in range(1, MAX_TRAIN_SLOTS + 1):
                            if pos in slot_vars:
                                slot_vars[pos].set("Chưa tải")
                    else:
                        elapsed = max(0, int(time.monotonic() - state.checked_at))
                        for slot in state.slots:
                            var = slot_vars.get(slot.pos)
                            if var is None:
                                continue
                            if not slot.unlocked:
                                var.set("🔒 Chưa mở")
                            else:
                                rem = slot.effective_remaining(elapsed)
                                if rem > 0:
                                    hname = slot.hero_name or f"#{slot.hero_id}"
                                    var.set(f"🎓 {hname}\nCòn {_format_hms(rem)}")
                                else:
                                    var.set("✅ Sẵn sàng")
            except (RuntimeError, tk.TclError):
                pass

    def _schedule_training_countdown_tick(self) -> None:
        old_id = getattr(self, "_training_countdown_after_id", None)
        if old_id is not None:
            try:
                self.after_cancel(old_id)
            except Exception:
                pass
            self._training_countdown_after_id = None
        if getattr(self, "_destroyed", False):
            return
        self._refresh_training_countdown_widgets()
        states = getattr(self, "_training_states", {})
        has_active = any(
            st.min_active_remaining(max(0, int(time.monotonic() - st.checked_at))) > 0
            for st in states.values()
        )
        win = getattr(self, "_trn_dialog", None)
        win_open = bool(win is not None and win.winfo_exists()) if win is not None else False
        if has_active or win_open:
            try:
                self._training_countdown_after_id = self.after(1000, self._schedule_training_countdown_tick)
            except (RuntimeError, tk.TclError):
                pass

    def _fetch_training_status_async(self) -> None:
        if not self.gateway:
            return
        cid = resolve_training_city_id(getattr(self, "roster", None), getattr(self, "_current_bld_city_id", None))
        if not cid:
            return
        if hasattr(self, "trn_status_var"):
            self.trn_status_var.set("Đang tải trạng thái đào tạo...")

        def _worker():
            try:
                states: dict[int, TrainingHallState] = {}
                for ttype in ALL_TRAIN_TYPES:
                    states[ttype] = fetch_training_state(self.gateway, ttype, cid)
                self._training_states.update(states)
                msg = f"Đã đồng bộ trạng thái ({time.strftime('%H:%M:%S')})"
            except CaptchaRequired:
                msg = "⚠️ Cần giải Captcha (mã 110)"
                self._append_trn_log("⚠️ Tải trạng thái đào tạo gặp Captcha (mã 110).")
                try:
                    self.after(0, lambda: hasattr(self, "status") and self.status.set("Cần giải Captcha"))
                except Exception:
                    pass
            except Exception as exc:
                msg = f"❌ Lỗi: {exc}"
                self._append_trn_log(f"❌ Lỗi tải trạng thái đào tạo: {exc}")

            def _apply_ui():
                if getattr(self, "_destroyed", False):
                    return
                if hasattr(self, "trn_status_var"):
                    self.trn_status_var.set(msg)
                self._schedule_training_countdown_tick()
                self._refresh_training_dialog_all()

            try:
                self.after(0, _apply_ui)
            except (RuntimeError, tk.TclError):
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _check_and_run_training(
        self,
        async_check: bool = True,
        force_run: bool = False,
        types_to_run: tuple[int, ...] = ALL_TRAIN_TYPES,
    ):
        if not self.gateway or getattr(self, "_destroyed", False):
            return None
        vo_ids = list(getattr(self, "_training_vo_ids", []))
        van_ids = list(getattr(self, "_training_van_ids", []))

        if not force_run:
            enabled = bool(getattr(self, "aux_training_var", None) and self.aux_training_var.get())
            if not enabled:
                return None
            if not vo_ids and not van_ids:
                return None
            if time.monotonic() < getattr(self, "_training_next_check_at", 0.0):
                return None

        cid = resolve_training_city_id(getattr(self, "roster", None), getattr(self, "_current_bld_city_id", None))
        if not cid:
            return None

        if not hasattr(self, "_training_lock"):
            self._training_lock = threading.Lock()

        def _run():
            if not self._training_lock.acquire(blocking=not async_check):
                return
            status_msg = "Sẵn sàng"
            try:
                self._training_running = True
                summary = run_training_cycle(
                    self.gateway,
                    cid,
                    vo_ids,
                    van_ids,
                    roster=getattr(self, "roster", None),
                    on_log=lambda m: self._append_trn_log(m, forward_to_bld=m.startswith("🎓")),
                    types_to_run=types_to_run,
                )
                self._training_states.update(summary.states)
                if types_to_run == ALL_TRAIN_TYPES:
                    self._training_next_check_at = time.monotonic() + summary.next_check_seconds
                if summary.trained:
                    status_msg = f"Đã đào tạo {len(summary.trained)} tướng ({time.strftime('%H:%M:%S')})"
                elif summary.failed:
                    status_msg = f"Kiểm tra xong ({len(summary.failed)} lỗi)"
                else:
                    status_msg = f"Các ô đang hồi ({time.strftime('%H:%M:%S')})"
            except CaptchaRequired:
                status_msg = "⚠️ Cần giải Captcha (mã 110)"
                self._append_trn_log("⚠️ Đào tạo tướng gặp Captcha (mã 110).")
                try:
                    self.after(0, lambda: hasattr(self, "status") and self.status.set("Cần giải Captcha"))
                except Exception:
                    pass
            except Exception as exc:
                status_msg = f"❌ Lỗi: {exc}"
                self._append_trn_log(f"❌ Lỗi đào tạo tướng: {exc}")
            finally:
                self._training_running = False
                self._training_lock.release()

                def _update_ui():
                    if getattr(self, "_destroyed", False):
                        return
                    if hasattr(self, "trn_status_var"):
                        self.trn_status_var.set(status_msg)
                    self._schedule_training_countdown_tick()
                    self._refresh_training_dialog_all()

                if threading.current_thread() is threading.main_thread():
                    _update_ui()
                else:
                    try:
                        self.after(0, _update_ui)
                    except (RuntimeError, tk.TclError):
                        pass

        if async_check:
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            return t
        _run()
        return None

    def _on_trn_run_now(self) -> None:
        msgbox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if not self.gateway:
            msgbox.showwarning("Đào Tạo Tướng", "Chưa kết nối tài khoản game.", parent=getattr(self, "_trn_dialog", self))
            return
        if not getattr(self, "_training_vo_ids", []) and not getattr(self, "_training_van_ids", []):
            msgbox.showwarning(
                "Đào Tạo Tướng",
                "Vui lòng chọn ít nhất 1 Võ tướng (Điểm Tướng Đài) hoặc Văn quan (Tụ Hiền Lâu).",
                parent=getattr(self, "_trn_dialog", self),
            )
            return
        if hasattr(self, "trn_status_var"):
            self.trn_status_var.set("Đang kiểm tra & đào tạo tướng...")
        self._check_and_run_training(async_check=True, force_run=True, types_to_run=ALL_TRAIN_TYPES)

    def _open_training_dialog(self) -> None:
        existing = getattr(self, "_trn_dialog", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            self._refresh_training_dialog_all()
            self._fetch_training_status_async()
            return

        win = tk.Toplevel(self)
        win.title("🎓 Đào Tạo Tướng (Điểm Tướng Đài & Tụ Hiền Lâu)")
        win.geometry("960x700")
        win.minsize(820, 560)
        win.configure(bg=BG)
        win.transient(self)
        set_app_icon(win)
        self._trn_dialog = win
        self._trn_base_by_name: dict[str, int] = {}

        def _on_close():
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # Thanh trên cùng
        top_bar = tk.Frame(win, bg=BG)
        top_bar.pack(fill="x", padx=12, pady=(10, 6))

        tk.Checkbutton(
            top_bar,
            text="🔄 Tự động đào tạo hàng ngày (tự lặp lại mỗi 24h)",
            variable=self.aux_training_var,
            command=self._on_aux_training_toggled,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        ttk.Button(top_bar, text="🎓 Đào tạo ngay", style="Success.TButton", command=self._on_trn_run_now).pack(side="right", padx=(4, 0))
        ttk.Button(top_bar, text="🔄 Tải trạng thái", style="Action.TButton", command=self._fetch_training_status_async).pack(side="right", padx=4)

        # Thanh chọn phân hệ: Điểm Tướng Đài (Võ) / Tụ Hiền Lâu (Văn)
        hall_bar = tk.Frame(win, bg=BG)
        hall_bar.pack(fill="x", padx=12, pady=(0, 6))
        self.trn_hall_var = tk.StringVar(value="vo")
        tk.Radiobutton(
            hall_bar,
            text="⚔️ Điểm Tướng Đài (Võ tướng)",
            variable=self.trn_hall_var,
            value="vo",
            command=self._refresh_training_dialog_all,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left", padx=(0, 14))
        tk.Radiobutton(
            hall_bar,
            text="📜 Tụ Hiền Lâu (Văn quan)",
            variable=self.trn_hall_var,
            value="van",
            command=self._refresh_training_dialog_all,
            bg=BG,
            fg=FG,
            selectcolor=CARD,
            activebackground=BG,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        # 5 ô đào tạo
        slots_frame = ttk.LabelFrame(win, text="Trạng thái 5 ô đào tạo (Hồi 24h)", style="Card.TLabelframe")
        slots_frame.pack(fill="x", padx=12, pady=(0, 6))
        slots_row = tk.Frame(slots_frame, bg=CARD)
        slots_row.pack(fill="x", padx=6, pady=6)
        self._trn_slot_vars: dict[int, tk.StringVar] = {}
        for pos in range(1, MAX_TRAIN_SLOTS + 1):
            slots_row.columnconfigure(pos - 1, weight=1, uniform="trn_slot")
            cell = tk.Frame(slots_row, bg=BG, bd=1, relief="solid", padx=6, pady=6)
            cell.grid(row=0, column=pos - 1, sticky="nsew", padx=3)
            tk.Label(cell, text=f"Ô {pos}", bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack()
            var = tk.StringVar(value="Chưa tải")
            self._trn_slot_vars[pos] = var
            tk.Label(cell, textvariable=var, bg=BG, fg=FG, font=("Segoe UI", 9), justify="center").pack(pady=(2, 0))

        # Danh sách thứ tự ưu tiên đã chọn
        prio_frame = ttk.LabelFrame(win, text="Thứ tự ưu tiên đã chọn (Ô trống lấy từ trên xuống; tự chuyển tiếp nếu max cấp/bận)", style="Card.TLabelframe")
        prio_frame.pack(fill="x", padx=12, pady=(0, 6))
        prio_inner = tk.Frame(prio_frame, bg=CARD)
        prio_inner.pack(fill="x", padx=6, pady=6)

        self.trn_prio_listbox = tk.Listbox(
            prio_inner, height=4, bg=BG, fg=FG, selectbackground=ACCENT, relief="flat", font=("Segoe UI", 9)
        )
        self.trn_prio_listbox.pack(side="left", fill="x", expand=True)

        prio_btns = tk.Frame(prio_inner, bg=CARD)
        prio_btns.pack(side="right", padx=(6, 0))
        ttk.Button(prio_btns, text="↑ Lên", width=8, style="Action.TButton", command=lambda: self._trn_move_priority(-1)).pack(pady=1)
        ttk.Button(prio_btns, text="↓ Xuống", width=8, style="Action.TButton", command=lambda: self._trn_move_priority(1)).pack(pady=1)
        ttk.Button(prio_btns, text="✕ Xóa", width=8, style="Danger.TButton", command=self._trn_remove_priority).pack(pady=1)

        # Bộ lọc & bảng chọn tướng
        filter_bar = tk.Frame(win, bg=BG)
        filter_bar.pack(fill="x", padx=12, pady=(0, 4))
        tk.Label(filter_bar, text="Thành / Trại:", bg=BG, fg=FG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.trn_city_combo = ttk.Combobox(filter_bar, state="readonly", width=24)
        self.trn_city_combo.pack(side="left", padx=(0, 10))
        self.trn_city_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_trn_tree())

        tk.Label(filter_bar, text="Tìm:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.trn_search_var = tk.StringVar(value="")
        self.trn_search_var.trace_add("write", lambda *_a: self._refresh_trn_tree())
        ttk.Entry(filter_bar, textvariable=self.trn_search_var, width=16).pack(side="left", padx=(0, 10))

        tk.Label(filter_bar, text="Sắp xếp:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self.trn_sort_combo = ttk.Combobox(filter_bar, state="readonly", width=16, values=["Cấp Cao → Thấp", "Cấp Thấp → Cao"])
        self.trn_sort_combo.current(0)
        self.trn_sort_combo.pack(side="left", padx=(0, 8))
        self.trn_sort_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_trn_tree())

        ttk.Button(filter_bar, text="☐ Bỏ chọn mục này", style="Action.TButton", command=self._trn_clear_current_hall).pack(side="right")

        self.trn_summary_var = tk.StringVar(value="")
        tk.Label(win, textvariable=self.trn_summary_var, bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(0, 4))

        tree_frame = ttk.LabelFrame(win, text="Danh sách tướng", style="Card.TLabelframe")
        tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self.trn_tree = ttk.Treeview(
            tree_frame,
            columns=("sel", "city", "lv", "role", "status"),
            show="tree headings",
            selectmode="browse",
        )
        for col, text, w, anchor in (
            ("#0", "Tên tướng", 160, "w"),
            ("sel", "Chọn", 50, "center"),
            ("city", "Thành / Trại", 150, "w"),
            ("lv", "Cấp", 55, "center"),
            ("role", "Chức vụ", 100, "center"),
            ("status", "Trạng thái", 150, "center"),
        ):
            self.trn_tree.heading(col, text=text)
            self.trn_tree.column(col, width=w, anchor=anchor)

        trn_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.trn_tree.yview)
        self.trn_tree.configure(yscrollcommand=trn_scroll.set)
        self.trn_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        trn_scroll.pack(side="right", fill="y", padx=(0, 6), pady=6)

        self.trn_tree.bind("<Button-1>", self._on_trn_tree_click)
        self.trn_tree.bind("<space>", self._on_trn_tree_space)

        bottom_bar = tk.Frame(win, bg=BG)
        bottom_bar.pack(fill="x", padx=12, pady=(0, 4))
        self.trn_status_var = tk.StringVar(value="Sẵn sàng")
        tk.Label(bottom_bar, textvariable=self.trn_status_var, bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Button(bottom_bar, text="Đóng", style="Action.TButton", command=_on_close).pack(side="right")

        log_frame = ttk.LabelFrame(win, text="Nhật ký Đào Tạo Tướng", style="Card.TLabelframe")
        log_frame.pack(fill="x", padx=12, pady=(0, 10))
        self.trn_log_text = tk.Text(
            log_frame, height=5, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=("Consolas", 9)
        )
        self.trn_log_text.pack(fill="x", padx=6, pady=6)

        self._sync_trn_city_combo()
        self._refresh_training_dialog_all()
        self._schedule_training_countdown_tick()
        self._fetch_training_status_async()

    def _get_trn_active_role(self) -> str:
        return "van" if (hasattr(self, "trn_hall_var") and self.trn_hall_var.get() == "van") else "vo"

    def _get_trn_selected_list(self) -> list[int]:
        role = self._get_trn_active_role()
        if role == "van":
            return self._training_van_ids
        return self._training_vo_ids

    def _set_trn_selected_list(self, new_ids: list[int]) -> None:
        cleaned = _dedup_ids(new_ids)
        if self._get_trn_active_role() == "van":
            self._training_van_ids = cleaned
        else:
            self._training_vo_ids = cleaned
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _sync_trn_city_combo(self) -> None:
        if not hasattr(self, "trn_city_combo") or not self.trn_city_combo.winfo_exists():
            return
        all_lbl = "🌟 Tất cả các thành"
        values = [all_lbl]
        self._trn_base_by_name = {}
        cur = self.trn_city_combo.get()
        if getattr(self, "roster", None):
            for base in self.roster.bases:
                values.append(base.display_name)
                self._trn_base_by_name[base.display_name] = base.id
        self.trn_city_combo["values"] = values
        self.trn_city_combo.set(cur if cur in values else all_lbl)

    def _refresh_training_dialog_all(self) -> None:
        win = getattr(self, "_trn_dialog", None)
        if win is None or not win.winfo_exists():
            return
        self._sync_trn_city_combo()
        self._refresh_training_countdown_widgets()
        self._refresh_trn_priority_list()
        self._refresh_trn_tree()

    def _refresh_trn_priority_list(self) -> None:
        if not hasattr(self, "trn_prio_listbox") or not self.trn_prio_listbox.winfo_exists():
            return
        cur_sel = self.trn_prio_listbox.curselection()
        sel_idx = cur_sel[0] if cur_sel else None
        self.trn_prio_listbox.delete(0, "end")

        role = self._get_trn_active_role()
        gen_map = {}
        if getattr(self, "roster", None):
            for b in self.roster.bases:
                for g in self.roster.generals_of(b.id):
                    if g.role == role:
                        gen_map.setdefault(g.id, g)

        sel_ids = self._get_trn_selected_list()
        for idx, gid in enumerate(sel_ids, start=1):
            g = gen_map.get(gid)
            label = f"{idx}. {g.name} (Lv.{g.level})" if g else f"{idx}. Tướng #{gid}"
            self.trn_prio_listbox.insert("end", label)
        if sel_idx is not None and 0 <= sel_idx < len(sel_ids):
            self.trn_prio_listbox.selection_set(sel_idx)

    def _trn_move_priority(self, delta: int) -> None:
        if not hasattr(self, "trn_prio_listbox"):
            return
        cur = self.trn_prio_listbox.curselection()
        if not cur:
            return
        idx = cur[0]
        sel_ids = list(self._get_trn_selected_list())
        nxt = idx + delta
        if not (0 <= nxt < len(sel_ids)):
            return
        sel_ids[idx], sel_ids[nxt] = sel_ids[nxt], sel_ids[idx]
        self._set_trn_selected_list(sel_ids)
        self._refresh_trn_priority_list()
        self.trn_prio_listbox.selection_clear(0, "end")
        self.trn_prio_listbox.selection_set(nxt)

    def _trn_remove_priority(self) -> None:
        if not hasattr(self, "trn_prio_listbox"):
            return
        cur = self.trn_prio_listbox.curselection()
        if not cur:
            return
        idx = cur[0]
        sel_ids = list(self._get_trn_selected_list())
        if 0 <= idx < len(sel_ids):
            sel_ids.pop(idx)
            self._set_trn_selected_list(sel_ids)
            self._refresh_training_dialog_all()

    def _trn_clear_current_hall(self) -> None:
        self._set_trn_selected_list([])
        self._refresh_training_dialog_all()

    def _refresh_trn_tree(self) -> None:
        if not hasattr(self, "trn_tree") or not self.trn_tree.winfo_exists():
            return
        self.trn_tree.delete(*self.trn_tree.get_children())
        if not getattr(self, "roster", None):
            self.trn_summary_var.set("Chưa có dữ liệu Roster.")
            return

        role = self._get_trn_active_role()
        ttype = TRAIN_TYPE_VAN if role == "van" else TRAIN_TYPE_VO
        filter_cid = self._trn_base_by_name.get(self.trn_city_combo.get()) if hasattr(self, "trn_city_combo") else None
        q = (self.trn_search_var.get() if hasattr(self, "trn_search_var") else "").strip().lower()
        asc = bool(hasattr(self, "trn_sort_combo") and self.trn_sort_combo.current() == 1)

        state: Optional[TrainingHallState] = getattr(self, "_training_states", {}).get(ttype)
        active_ids = state.active_hero_ids(max(0, int(time.monotonic() - state.checked_at))) if state else set()

        rows = []
        seen: set[int] = set()
        for base in self.roster.bases:
            if filter_cid is not None and base.id != filter_cid:
                continue
            for g in self.roster.generals_of(base.id):
                if g.id in seen or g.role != role:
                    continue
                seen.add(g.id)
                if q and q not in g.name.lower():
                    continue
                rows.append((g, base.name))

        rows.sort(key=lambda pair: (pair[0].level if asc else -pair[0].level, pair[0].id))
        sel_set = set(self._get_trn_selected_list())

        for g, bname in rows:
            chk = "☑" if g.id in sel_set else "☐"
            role_txt = "Thái thú" if g.is_mayor else ROLE_TEXT.get(g.role, g.role)
            st_txt = "🎓 Đang đào tạo" if g.id in active_ids else g.status_text
            self.trn_tree.insert(
                "", "end", iid=str(g.id), text=g.name, values=(chk, bname, g.level, role_txt, st_txt)
            )
        self.trn_summary_var.set(f"Hiển thị: {len(rows)} tướng • Đã chọn ưu tiên: {len(sel_set)} tướng")

    def _toggle_trn_item(self, iid: str) -> None:
        if not self.trn_tree.exists(iid):
            return
        gid = int(iid)
        cur = list(self._get_trn_selected_list())
        if gid in cur:
            cur = [x for x in cur if x != gid]
        else:
            cur.append(gid)
        self._set_trn_selected_list(cur)
        self._refresh_trn_priority_list()
        vals = list(self.trn_tree.item(iid, "values"))
        if vals:
            vals[0] = "☑" if gid in cur else "☐"
            self.trn_tree.item(iid, values=vals)
        self.trn_summary_var.set(
            f"Hiển thị: {len(self.trn_tree.get_children())} tướng • Đã chọn ưu tiên: {len(cur)} tướng"
        )

    def _on_trn_tree_click(self, event) -> None:
        item = self.trn_tree.identify_row(event.y)
        col = self.trn_tree.identify_column(event.x)
        if not item or not self.trn_tree.exists(item):
            return
        if col in ("#1", "#0") or not col:
            self._toggle_trn_item(item)

    def _on_trn_tree_space(self, _event=None) -> None:
        sel = self.trn_tree.selection()
        if sel:
            self._toggle_trn_item(sel[0])
