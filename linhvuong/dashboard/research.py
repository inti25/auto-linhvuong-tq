"""Phân hệ Nghiên Cứu Viện Đại Học & Hậu Cần trên Dashboard."""

import json
import logging
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox as _default_messagebox, ttk
from typing import Optional

from ..tasks.logistics import ArmyTransferOrder, LogisticsTask as _DefaultLogisticsTask
from ..tasks.research import ResearchTask as _DefaultResearchTask, TECH_NAMES, TechPlan
from .runners import ResearchAutoRunner as _DefaultResearchAutoRunner
from .shared import BG, CARD, FG, resolve_dashboard_symbol


class ResearchMixin:
    """Quản lý Viện Đại Học (29 kỹ thuật) và các thao tác Hậu cần nhanh."""

    def _collect_research_profile_dict(self) -> dict:
        techs = []
        if hasattr(self, "res_tree"):
            for iid in self.res_tree.get_children(""):
                name = self.res_tree.item(iid, "text")
                vals = self.res_tree.item(iid, "values")
                if len(vals) >= 4:
                    techs.append(
                        {
                            "id": int(vals[1]),
                            "target_level": int(vals[2]),
                            "name": name,
                            "enabled": vals[0] == "☑",
                        }
                    )
        return {
            "art_speedup": bool(self.res_art_var.get()) if hasattr(self, "res_art_var") else False,
            "even_research": bool(self.res_even_var.get()) if hasattr(self, "res_even_var") else False,
            "interval": self.res_interval_var.get() if hasattr(self, "res_interval_var") else "30",
            "city_id": self._research_city_id,
            "techs": techs,
        }

    def _apply_research_profile_dict(self, data: dict) -> Optional[str]:
        techs_list = None
        if "techs" in data and isinstance(data["techs"], list):
            techs_list = data["techs"]
        elif "research" in data and isinstance(data["research"], dict):
            res_data = data["research"]
            if hasattr(self, "res_art_var") and "art_speedup" in res_data:
                self.res_art_var.set(bool(res_data["art_speedup"]))
            if hasattr(self, "res_even_var") and "even_research" in res_data:
                self.res_even_var.set(bool(res_data["even_research"]))
            if hasattr(self, "res_interval_var") and "interval" in res_data:
                self.res_interval_var.set(str(res_data["interval"]))
            if "city_id" in res_data and res_data["city_id"] is not None:
                try:
                    self._research_city_id = int(res_data["city_id"])
                    if hasattr(self, "bld_bases_tree"):
                        for iid in self.bld_bases_tree.get_children(""):
                            vals = list(self.bld_bases_tree.item(iid, "values"))
                            if len(vals) > 2:
                                vals[2] = "★" if int(iid) == self._research_city_id else "☐"
                                self.bld_bases_tree.item(iid, values=vals)
                except (ValueError, TypeError):
                    pass
            techs_list = res_data.get("techs") or res_data.get("plans")

        if techs_list and hasattr(self, "res_tree"):
            self.res_tree.delete(*self.res_tree.get_children(""))
            for t in techs_list:
                tid = int(t.get("id", 1))
                tname = t.get("name") or TECH_NAMES.get(tid, f"Kỹ thuật {tid}")
                en = "☑" if t.get("enabled", True) else "☐"
                target_lvl = int(t.get("target_level", 20))
                cur_lvl = t.get("current_level", "-")
                try:
                    cur_int = int(cur_lvl) if str(cur_lvl) != "-" else None
                    tag = ("completed" if cur_int >= target_lvl else "upgrade") if cur_int is not None else "upgrade"
                except (ValueError, TypeError):
                    tag = "upgrade"
                self.res_tree.insert(
                    "",
                    "end",
                    iid=str(tid),
                    text=tname,
                    values=(en, tid, target_lvl, cur_lvl),
                    tags=(tag,),
                )
            if hasattr(self, "_append_logis_log"):
                self._append_logis_log(f"📂 Đã nạp cấu hình {len(techs_list)} kỹ thuật từ hồ sơ.")
            return f"Đại Học ({len(techs_list)} kỹ thuật)"
        return None

    def _append_logis_log(self, msg: str):
        logging.getLogger("linhvuong.tasks.HauCan").info(msg)
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        for w in list(self._active_log_texts):
            self._append_text_buffer(w, line)

    def _logis_clear_log(self):
        """Xóa trắng nội dung khung nhật ký Hậu Cần & Điều Chuyển."""
        if hasattr(self, "logis_log_text") and self.logis_log_text:
            self.logis_log_text.delete("1.0", "end")

    def _build_research_and_logistics_tab(self, parent):
        body = tk.Frame(parent, bg=BG)
        body.pack(fill="both", expand=True, pady=6)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Cột trái: Nghiên Cứu Viện Đại Học
        f_res = ttk.LabelFrame(body, text="Viện Đại Học (29 Kỹ Thuật)", style="Card.TLabelframe")
        f_res.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        res_top = tk.Frame(f_res, bg=CARD, padx=8, pady=4)
        res_top.pack(fill="x")
        tk.Label(res_top, text="Thành:", bg=CARD, fg=FG, font=("Segoe UI", 10, "bold")).pack(side="left", padx=4)
        self.res_city_combo = ttk.Combobox(res_top, state="readonly", width=18)
        self.res_city_combo.pack(side="left", padx=4)
        self.res_city_combo.bind("<<ComboboxSelected>>", lambda _e: self._fetch_city_techs())

        self.res_art_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            res_top,
            text="📜 Binh Pháp tăng tốc",
            variable=self.res_art_var,
            bg=CARD,
            fg=FG,
            selectcolor=BG,
            activebackground=CARD,
        ).pack(side="left", padx=6)

        self.res_even_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            res_top,
            text="⚖️ Nghiên cứu đồng đều",
            variable=self.res_even_var,
            bg=CARD,
            fg=FG,
            selectcolor=BG,
            activebackground=CARD,
        ).pack(side="left", padx=6)

        tk.Label(res_top, text="Chu kỳ (s):", bg=CARD, fg=FG, font=("Segoe UI", 9, "bold")).pack(
            side="left", padx=(6, 2)
        )
        self.res_interval_var = tk.StringVar(value="30")
        ttk.Entry(res_top, textvariable=self.res_interval_var, width=4).pack(side="left", padx=(0, 6))

        self.res_start_btn = ttk.Button(
            res_top, text="▶️ Bắt đầu", style="Success.TButton", command=self._toggle_research
        )
        self.res_start_btn.pack(side="right", padx=4)

        res_bar = tk.Frame(f_res, bg=CARD, padx=8, pady=4)
        res_bar.pack(fill="x")
        ttk.Button(res_bar, text="⬆️ Lên", style="Action.TButton", command=self._move_res_up).pack(side="left", padx=2)
        ttk.Button(res_bar, text="⬇️ Xuống", style="Action.TButton", command=self._move_res_down).pack(
            side="left", padx=2
        )
        ttk.Button(
            res_bar, text="☑ Tất cả", style="Action.TButton", command=lambda: self._select_all_res(True)
        ).pack(side="left", padx=2)
        ttk.Button(
            res_bar, text="☐ Bỏ chọn", style="Action.TButton", command=lambda: self._select_all_res(False)
        ).pack(side="left", padx=2)

        tk.Label(res_bar, text="Cấp MT:", bg=CARD, fg=FG, font=("Segoe UI", 9)).pack(side="left", padx=(6, 2))
        self.res_target_lvl_var = tk.StringVar(value="20")
        ttk.Entry(res_bar, textvariable=self.res_target_lvl_var, width=5).pack(side="left", padx=2)
        ttk.Button(res_bar, text="✏️ Đặt cấp", style="Action.TButton", command=self._set_res_target_lvl).pack(
            side="left", padx=2
        )
        ttk.Button(res_bar, text="🌟 Đặt tất cả", style="Action.TButton", command=self._set_res_target_lvl_all).pack(
            side="left", padx=2
        )
        ttk.Button(res_bar, text="🔄 Tải kỹ thuật", style="Action.TButton", command=self._fetch_city_techs).pack(
            side="left", padx=2
        )

        self.res_tree = ttk.Treeview(
            f_res, columns=("select", "id", "target_lvl", "current_lvl"), show="tree headings", selectmode="browse"
        )
        self.res_tree.heading("#0", text="Tên Kỹ Thuật Đại Học")
        self.res_tree.heading("select", text="Chọn")
        self.res_tree.heading("id", text="Mã ID")
        self.res_tree.heading("target_lvl", text="Cấp MT")
        self.res_tree.heading("current_lvl", text="Cấp HT")

        self.res_tree.column("#0", width=135)
        self.res_tree.column("select", width=45, anchor="center")
        self.res_tree.column("id", width=50, anchor="center")
        self.res_tree.column("target_lvl", width=55, anchor="center")
        self.res_tree.column("current_lvl", width=55, anchor="center")

        self.res_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.res_tree.bind("<ButtonRelease-1>", self._on_res_tree_click)
        self._populate_all_techs()

        # Cột phải: Hậu Cần & Chuyển Quân Giới
        f_logis = ttk.LabelFrame(body, text="Hậu Cần & Chuyển Quân Giới", style="Card.TLabelframe")
        f_logis.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        logis_form = tk.Frame(f_logis, bg=CARD, padx=12, pady=10)
        logis_form.pack(fill="x", padx=6, pady=6)

        tk.Label(logis_form, text="Từ Căn Cứ:", bg=CARD, fg=FG).grid(row=0, column=0, sticky="w", pady=4)
        self.log_from_city_combo = ttk.Combobox(logis_form, state="readonly", width=18)
        self.log_from_city_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        tk.Label(logis_form, text="Đến Căn Cứ:", bg=CARD, fg=FG).grid(row=0, column=2, sticky="w", pady=4)
        self.log_to_city_combo = ttk.Combobox(logis_form, state="readonly", width=18)
        self.log_to_city_combo.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        tk.Label(logis_form, text="Loại quân:", bg=CARD, fg=FG).grid(row=1, column=0, sticky="w", pady=4)
        self.log_army_combo = ttk.Combobox(logis_form, state="readonly", width=18)
        self.log_army_combo["values"] = ["1: Bộ binh", "2: Kỵ binh", "3: Cung binh"]
        self.log_army_combo.current(0)
        self.log_army_combo.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        tk.Label(logis_form, text="Số lượng:", bg=CARD, fg=FG).grid(row=1, column=2, sticky="w", pady=4)
        self.log_amount_var = tk.StringVar(value="1000")
        ttk.Entry(logis_form, textvariable=self.log_amount_var, width=12).grid(
            row=1, column=3, sticky="w", padx=4, pady=4
        )

        act_row = tk.Frame(logis_form, bg=CARD)
        act_row.grid(row=2, column=0, columnspan=4, pady=10, sticky="ew")
        ttk.Button(
            act_row, text="🚚 Chuyển Quân Giới Ngay", style="Action.TButton", command=self._do_transfer_army
        ).pack(side="left", padx=4)
        ttk.Button(act_row, text="🕊️ An Dân Ngay", style="Action.TButton", command=self._do_comfort_now).pack(
            side="left", padx=4
        )
        ttk.Button(
            act_row, text="🎁 Nhận Thưởng Chuyên Cần", style="Success.TButton", command=self._do_claim_daily
        ).pack(side="left", padx=4)

        f_log_tab6 = tk.Frame(f_logis, bg=CARD)
        f_log_tab6.pack(fill="both", expand=True, padx=6, pady=6)
        log_bar = tk.Frame(f_log_tab6, bg=CARD)
        log_bar.pack(side="top", fill="x", pady=(0, 2))
        ttk.Button(log_bar, text="🗑️ Xóa", style="Action.TButton", command=self._logis_clear_log).pack(side="right")
        self.logis_log_text = tk.Text(
            f_log_tab6, bg=CARD, fg=FG, insertbackground=FG, font=("Consolas", 9), borderwidth=0
        )
        self.logis_log_text.pack(fill="both", expand=True)

    def _populate_all_techs(self):
        self.res_tree.delete(*self.res_tree.get_children())
        for tid, tname in sorted(TECH_NAMES.items()):
            self.res_tree.insert("", "end", iid=str(tid), text=tname, values=("☐", tid, 20, "-"), tags=("upgrade",))
        children = self.res_tree.get_children("")
        if children:
            sel = self.res_tree.selection()
            if not sel or not self.res_tree.exists(sel[0]):
                self.res_tree.selection_set(children[0])
            self._on_res_tree_selected()

    def _fetch_city_techs(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel_idx = self.res_city_combo.current()
        cities = self.roster.cities if self.roster.cities else self.roster.bases
        if sel_idx < 0 or sel_idx >= len(cities):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì cần tải kỹ thuật!")
            return
        city = cities[sel_idx]
        self._append_logis_log(f"🔄 Đang tải dữ liệu kỹ thuật thực tế cho thành {city.name}...")
        threading.Thread(target=self._fetch_city_techs_thread, args=(city.id,), daemon=True).start()

    def _fetch_city_techs_thread(self, city_id: int):
        try:
            # 1. Chuyển focus thành thị về city_id qua /api/city/current
            self.gateway.set_current_city(city_id)

            # 2. Tìm Đại Học Điện (gid=6) hoặc Thái Học Điện (gid=59) qua /api/building/list
            resp_bld = self.gateway.building_list(city_id) or {}
            b_list = resp_bld.get("items") or resp_bld.get("infos") or []
            univ_pid = None
            univ_gid = 6
            for b in b_list:
                if isinstance(b, dict):
                    bgid = int(b.get("m_lgid") or b.get("gid") or 0)
                    if bgid in (6, 59):
                        univ_pid = int(b.get("m_lpos") if b.get("m_lpos") is not None else b.get("pid", 0))
                        univ_gid = bgid
                        break

            # Nếu thành hiện tại không có Viện Đại Học / Thái Học Điện, tự động tìm thành có
            if univ_pid is None:
                found_city = None
                for c in self.roster.cities if self.roster.cities else []:
                    if c.id == city_id:
                        continue
                    r = self.gateway.building_list(c.id) or {}
                    for b in r.get("items") or r.get("infos") or []:
                        if isinstance(b, dict) and int(b.get("m_lgid") or b.get("gid") or 0) in (6, 59):
                            found_city = c
                            break
                    if found_city:
                        break

                if found_city:
                    self.after(
                        0,
                        lambda: self._append_logis_log(
                            f"ℹ️ Thành được chọn không có Đại Học / Thái Học Điện. Tự động chuyển sang thành '{found_city.name}'..."
                        ),
                    )

                    def update_combo_and_refetch():
                        city_items = [c.display_name for c in self.roster.cities]
                        for idx, item in enumerate(city_items):
                            if str(found_city.id) in item:
                                self.res_city_combo.current(idx)
                                break
                        threading.Thread(
                            target=self._fetch_city_techs_thread, args=(found_city.id,), daemon=True
                        ).start()

                    self.after(0, update_combo_and_refetch)
                    return
                else:
                    self.after(
                        0,
                        lambda: self._append_logis_log(
                            "⚠️ Không tìm thấy Viện Đại Học / Thái Học Điện ở bất kỳ thành nào!"
                        ),
                    )
                    return

            # 3. Lấy cấp độ 29 kỹ thuật
            resp_tech = (
                self.gateway.call(
                    "Build.ashx", 2, {"pid": str(univ_pid), "gid": str(univ_gid), "tab": "1", "tid": str(city_id), "_": ""}
                )
                or {}
            )
            ret = resp_tech.get("ret", 0)
            if ret != 0:
                self.after(0, lambda: self._append_logis_log(f"⚠️ Server trả về mã lỗi {ret} khi đọc kỹ thuật."))
                return

            levels = {}
            for item in resp_tech.get("list", []):
                if isinstance(item, dict):
                    levels[int(item.get("id", 0))] = int(item.get("level", 0))
                elif isinstance(item, (list, tuple)) and len(item) >= 3:
                    try:
                        levels[int(item[0])] = int(item[2])
                    except (ValueError, TypeError):
                        pass

            self.after(0, self._update_city_techs_ui, levels)
            curr = resp_tech.get("current")
            if curr and isinstance(curr, (list, tuple)) and len(curr) >= 5:
                t_name, cur_l, next_l, t_left = curr[1], curr[2], curr[3], curr[4]
                self.after(
                    0,
                    lambda: self._append_logis_log(
                        f"🔬 Đang nghiên cứu: {t_name} (Cấp {cur_l} ➔ {next_l}), còn {t_left}s."
                    ),
                )
            elif levels:
                self.after(0, lambda: self._append_logis_log(f"✅ Đã tải cấp độ {len(levels)} kỹ thuật thành công."))
        except Exception as e:
            self.after(0, lambda: self._append_logis_log(f"❌ Lỗi tải kỹ thuật thành: {e}"))

    def _sync_city_techs_data(
        self, city_id: int, levels_map: dict, tech_status: Optional[tuple] = None, from_auto_cycle: bool = False
    ):
        if not levels_map:
            if not from_auto_cycle:
                self._append_logis_log("ℹ️ Server không trả về dữ liệu kỹ thuật.")
            return

        cache = getattr(self, "_last_synced_tech_snapshot", None)
        if cache is None:
            cache = {}
            self._last_synced_tech_snapshot = cache
        prev_snapshot = cache.get(city_id)
        if from_auto_cycle and prev_snapshot == levels_map:
            return
        cache[city_id] = dict(levels_map)

        level_changes = []
        for iid in self.res_tree.get_children(""):
            try:
                tid = int(iid)
                if tid in levels_map:
                    cur_lvl = int(levels_map[tid])
                    vals = list(self.res_tree.item(iid, "values"))
                    tname = self.res_tree.item(iid, "text")
                    if len(vals) >= 3:
                        old_lvl = int(vals[3]) if len(vals) > 3 and str(vals[3]) != "-" else 0
                        if len(vals) == 3:
                            vals.append(cur_lvl)
                        else:
                            vals[3] = cur_lvl
                        if old_lvl != cur_lvl and old_lvl > 0:
                            level_changes.append((tid, tname, old_lvl, cur_lvl))
                        target_lvl = int(vals[2]) if len(vals) > 2 else 20
                        tag = "completed" if cur_lvl >= target_lvl else "upgrade"
                        self.res_tree.item(iid, values=vals, tags=(tag,))
            except (ValueError, IndexError):
                pass

        if level_changes:
            ch_str = ", ".join([f"{name} (cấp {ol}➔{nl})" for _, name, ol, nl in level_changes[:3]])
            if len(level_changes) > 3:
                ch_str += f", +{len(level_changes)-3} kỹ thuật khác"
            self._append_logis_log(f"🔄 Đã đồng bộ kỹ thuật thực tế: {ch_str}")
        elif not from_auto_cycle:
            self._append_logis_log(
                f"🔄 Đã nạp thành công cấp độ thực tế của {len(levels_map)} kỹ thuật (bảo toàn thứ tự ưu tiên)."
            )

        if tech_status and tech_status[0]:
            tid = tech_status[1]
            tname = TECH_NAMES.get(tid, f"Kỹ thuật {tid}")
            if not from_auto_cycle:
                self._append_logis_log(f"🔬 Viện Đại Học đang nghiên cứu: {tname}")

    def _update_city_techs_ui(self, levels_map: dict):
        sel_idx = self.res_city_combo.current() if hasattr(self, "res_city_combo") else -1
        city_id = 0
        if self.roster and self.roster.cities and 0 <= sel_idx < len(self.roster.cities):
            city_id = self.roster.cities[sel_idx].id
        self._sync_city_techs_data(city_id, levels_map, tech_status=None, from_auto_cycle=False)

    def _move_res_up(self):
        sel = self.res_tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.res_tree.index(item)
        if idx > 0:
            self.res_tree.move(item, "", idx - 1)
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()

    def _move_res_down(self):
        sel = self.res_tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.res_tree.index(item)
        children = self.res_tree.get_children("")
        if idx < len(children) - 1:
            self.res_tree.move(item, "", idx + 1)
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()

    def _select_all_res(self, state: bool):
        sym = "☑" if state else "☐"
        for iid in self.res_tree.get_children(""):
            vals = list(self.res_tree.item(iid, "values"))
            vals[0] = sym
            self.res_tree.item(iid, values=vals)
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _set_res_target_lvl(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.res_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 kỹ thuật trong bảng!")
            return
        try:
            lvl = int(self.res_target_lvl_var.get())
            if lvl < 1 or lvl > 39:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 1 đến 39!")
            return
        for iid in sel:
            vals = list(self.res_tree.item(iid, "values"))
            vals[2] = lvl
            try:
                cur = int(vals[3]) if len(vals) > 3 and str(vals[3]) != "-" else None
                tag = ("completed" if cur >= lvl else "upgrade") if cur is not None else "upgrade"
                self.res_tree.item(iid, values=vals, tags=(tag,))
            except (ValueError, TypeError):
                self.res_tree.item(iid, values=vals)
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _set_res_target_lvl_all(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        try:
            lvl = int(self.res_target_lvl_var.get())
            if lvl < 1 or lvl > 39:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Cấp mục tiêu phải là số nguyên từ 1 đến 39!")
            return
        count = 0
        for iid in self.res_tree.get_children(""):
            vals = list(self.res_tree.item(iid, "values"))
            if len(vals) > 2:
                vals[2] = lvl
                try:
                    cur = int(vals[3]) if len(vals) > 3 and str(vals[3]) != "-" else None
                    tag = ("completed" if cur >= lvl else "upgrade") if cur is not None else "upgrade"
                    self.res_tree.item(iid, values=vals, tags=(tag,))
                except (ValueError, TypeError):
                    self.res_tree.item(iid, values=vals)
                count += 1
        self._append_logis_log(f"🎯 Đã đặt Cấp mục tiêu = {lvl} cho tất cả {count} kỹ thuật.")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _on_res_tree_selected(self, _event=None):
        sel = self.res_tree.selection()
        if not sel:
            return
        item = sel[0]
        if not self.res_tree.exists(item):
            return
        vals = self.res_tree.item(item, "values")
        if len(vals) > 2:
            try:
                self.res_target_lvl_var.set(str(vals[2]))
            except Exception:
                pass

    def _on_res_tree_click(self, event):
        item = self.res_tree.identify_row(event.y)
        col = self.res_tree.identify_column(event.x)
        if not item or not self.res_tree.exists(item):
            return
        vals = list(self.res_tree.item(item, "values"))
        # displaycolumns=("current_lvl", "target_lvl", "select")
        # identify_column: #0 (text), #1 (current_lvl - "Cấp HT"), #2 (target_lvl - "Cấp MT"), #3 (select - "Chạy")
        if col == "#3":
            vals[0] = "☑" if vals[0] == "☐" else "☐"
            self.res_tree.item(item, values=vals)
            if hasattr(self, "_schedule_auto_save"):
                self._schedule_auto_save()
        else:
            self.res_tree.selection_set(item)
        if len(vals) > 2:
            self.res_target_lvl_var.set(str(vals[2]))

    def _load_tech_plans(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        plan_path = Path("tech_plans.json") if Path("tech_plans.json").exists() else Path("tech_plans.example.json")
        if not plan_path.exists():
            messagebox.showerror("Lỗi", "Không tìm thấy file tech_plans.json hoặc tech_plans.example.json!")
            return
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        plans = data.get("plans", [])
        if plans:
            plan_map = {int(p["tech_id"]): p for p in plans}
            for iid in self.res_tree.get_children(""):
                tid = int(iid)
                vals = list(self.res_tree.item(iid, "values"))
                cur_lvl = vals[3] if len(vals) > 3 else "-"
                if tid in plan_map:
                    p = plan_map[tid]
                    en = "☑" if p.get("enabled", True) else "☐"
                    target_lvl = p.get("target_level", 20)
                else:
                    en = "☐"
                    target_lvl = int(vals[2]) if len(vals) > 2 else 20
                try:
                    cur_int = int(cur_lvl) if str(cur_lvl) != "-" else None
                    tag = ("completed" if cur_int >= target_lvl else "upgrade") if cur_int is not None else "upgrade"
                except (ValueError, TypeError):
                    tag = "upgrade"
                self.res_tree.item(iid, values=(en, tid, target_lvl, cur_lvl), tags=(tag,))
        self._append_logis_log(f"📂 Đã nạp cấu hình {len(plans)} kỹ thuật.")
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()

    def _save_tech_plans(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        plans = []
        for iid in self.res_tree.get_children(""):
            name = self.res_tree.item(iid, "text")
            vals = self.res_tree.item(iid, "values")
            plans.append(
                {
                    "tech_id": int(vals[1]),
                    "target_level": int(vals[2]),
                    "name": name,
                    "enabled": vals[0] == "☑",
                }
            )
        Path("tech_plans.json").write_text(json.dumps({"plans": plans}, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_logis_log(f"💾 Đã lưu cấu hình {len(plans)} kỹ thuật ra tech_plans.json")
        messagebox.showinfo("Thành công", "Đã lưu cấu hình ra tech_plans.json!")

    def _toggle_research(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        ResearchTask = resolve_dashboard_symbol("ResearchTask", _DefaultResearchTask)
        ResearchAutoRunner = resolve_dashboard_symbol("ResearchAutoRunner", _DefaultResearchAutoRunner)

        if not self._res_runner or not self._res_runner.is_alive():
            sel_idx = self.res_city_combo.current()
            cities = self.roster.cities if self.roster.cities else self.roster.bases
            if sel_idx < 0 or sel_idx >= len(cities):
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành trì nghiên cứu!")
                return
            city_id = cities[sel_idx].id
            plans = []
            for iid in self.res_tree.get_children(""):
                name = self.res_tree.item(iid, "text")
                vals = self.res_tree.item(iid, "values")
                if vals[0] == "☑":
                    plans.append(TechPlan(tech_id=int(vals[1]), target_level=int(vals[2]), name=name, enabled=True))

            if not plans:
                messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất 1 kỹ thuật cần nghiên cứu!")
                return

            task = ResearchTask(
                gateway=self.gateway,
                city_id=city_id,
                plans=plans,
                auto_art_of_war=self.res_art_var.get(),
                even_research=bool(self.res_even_var.get()) if hasattr(self, "res_even_var") else False,
                notify=lambda m: self.after(0, self._append_logis_log, m),
                on_sync_data=lambda target_cid, levels, t_stat: self.after(
                    0, self._sync_city_techs_data, target_cid, levels, t_stat, True
                ),
            )
            try:
                res_interval = max(3.0, float(self.res_interval_var.get() or "30"))
            except ValueError:
                res_interval = 30.0

            self._res_runner = ResearchAutoRunner(
                task,
                interval=res_interval,
                log_cb=lambda m: self.after(0, self._append_logis_log, m),
                status_cb=lambda _s: None,
                sync_cb=lambda target_cid, levels, t_stat: self.after(
                    0, self._sync_city_techs_data, target_cid, levels, t_stat, True
                ),
            )
            self._res_runner.start()
            self.res_start_btn.configure(text="Đang NC", style="Success.TButton")
        else:
            self._res_runner.stop()
            self.res_start_btn.configure(text="Nghiên Cứu", style="Danger.TButton")

    def _do_transfer_army(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        LogisticsTask = resolve_dashboard_symbol("LogisticsTask", _DefaultLogisticsTask)
        f_idx = self.log_from_city_combo.current()
        t_idx = self.log_to_city_combo.current()
        bases = self.roster.bases
        if f_idx < 0 or t_idx < 0 or f_idx >= len(bases) or t_idx >= len(bases):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn đầy đủ Căn cứ gửi và Căn cứ nhận!")
            return
        from_id = bases[f_idx].id
        to_id = bases[t_idx].id
        army_id = self.log_army_combo.current() + 1
        amount = int(self.log_amount_var.get() or "1000")

        task = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_logis_log, m))
        order = ArmyTransferOrder(from_city_id=from_id, to_city_id=to_id, army_id=army_id, amount=amount)
        threading.Thread(target=lambda: task.transfer_army(order), daemon=True).start()

    def _do_comfort_now(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        LogisticsTask = resolve_dashboard_symbol("LogisticsTask", _DefaultLogisticsTask)
        f_idx = self.log_from_city_combo.current()
        bases = self.roster.bases
        if f_idx < 0 or f_idx >= len(bases):
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn căn cứ cần An Dân!")
            return
        city_id = bases[f_idx].id
        task = LogisticsTask(self.gateway, notify=lambda m: self.after(0, self._append_logis_log, m))
        threading.Thread(target=lambda: task.comfort_city_if_needed(city_id), daemon=True).start()

    def _do_claim_daily(self):
        LogisticsTask = resolve_dashboard_symbol("LogisticsTask", _DefaultLogisticsTask)
        try:
            self._append_logis_log("🎁 Đang gửi yêu cầu nhận thưởng chuyên cần hàng ngày...")
            if hasattr(self, "_append_bld_log"):
                self._append_bld_log("🎁 Đang gửi yêu cầu nhận thưởng chuyên cần hàng ngày...")
        except (RuntimeError, tk.TclError):
            pass

        def _on_notify(m: str):
            try:
                self.after(0, self._append_logis_log, m)
                if hasattr(self, "_append_bld_log"):
                    self.after(0, self._append_bld_log, m)
            except (RuntimeError, tk.TclError):
                pass

        task = LogisticsTask(self.gateway, notify=_on_notify)
        threading.Thread(target=lambda: task.claim_daily_reward(), daemon=True).start()
