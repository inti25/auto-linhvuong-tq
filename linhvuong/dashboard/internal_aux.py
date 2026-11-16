"""Phân hệ Phụ Trợ Nội Chính: Tài nguyên, Mở rương, DS Kiến trúc, Thám bảo & Lịch Hậu Cần."""

import logging
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox as _default_messagebox
from typing import Any, Callable, Optional

from ..gateway import gateway_city_context
from ..tasks.building import (
    CHEST_MAPPING,
    BuildingTask as _DefaultBuildingTask,
    chest_needs_city_switch,
    parse_boost_remaining_time,
    run_batch_open_chest,
    switch_city_verified,
)
from .shared import resolve_dashboard_symbol

logger = logging.getLogger("linhvuong.dashboard")


class InternalAuxMixin:
    """Quản lý giám sát tài nguyên, mở rương hàng loạt, DS kiến trúc, thám bảo và lệnh chuyển quân."""

    def _collect_resource_profile_dict(self) -> dict:
        return {
            "gold_threshold": self.res_gold_thresh_var.get() if hasattr(self, "res_gold_thresh_var") else "100000000",
            "wood_pct": self.res_wood_pct_var.get() if hasattr(self, "res_wood_pct_var") else "70",
            "iron_pct": self.res_iron_pct_var.get() if hasattr(self, "res_iron_pct_var") else "70",
            "stone_pct": self.res_stone_pct_var.get() if hasattr(self, "res_stone_pct_var") else "70",
            "food_pct": self.res_food_pct_var.get() if hasattr(self, "res_food_pct_var") else "70",
            "gold_box_idx": self.res_gold_box_combo.current() if hasattr(self, "res_gold_box_combo") else 2,
            "tn_box_idx": self.res_tn_box_combo.current() if hasattr(self, "res_tn_box_combo") else 4,
            "auto_open_box": bool(self.bld_open_box_var.get()) if hasattr(self, "bld_open_box_var") else False,
            "resource_cities": sorted(list(self._selected_resource_cities)),
        }

    def _apply_resource_profile_dict(self, res_cfg: dict) -> str:
        if hasattr(self, "res_gold_thresh_var") and "gold_threshold" in res_cfg:
            self.res_gold_thresh_var.set(str(res_cfg["gold_threshold"]))
        if hasattr(self, "res_wood_pct_var") and "wood_pct" in res_cfg:
            self.res_wood_pct_var.set(str(res_cfg["wood_pct"]))
        if hasattr(self, "res_iron_pct_var") and "iron_pct" in res_cfg:
            self.res_iron_pct_var.set(str(res_cfg["iron_pct"]))
        if hasattr(self, "res_stone_pct_var") and "stone_pct" in res_cfg:
            self.res_stone_pct_var.set(str(res_cfg["stone_pct"]))
        if hasattr(self, "res_food_pct_var") and "food_pct" in res_cfg:
            self.res_food_pct_var.set(str(res_cfg["food_pct"]))
        if hasattr(self, "bld_open_box_var") and "auto_open_box" in res_cfg:
            self.bld_open_box_var.set(bool(res_cfg["auto_open_box"]))
        if hasattr(self, "res_gold_box_combo") and "gold_box_idx" in res_cfg:
            try:
                g_idx = int(res_cfg["gold_box_idx"])
                if 0 <= g_idx < len(self.res_gold_box_combo["values"]):
                    self.res_gold_box_combo.current(g_idx)
            except (ValueError, IndexError):
                pass
        if hasattr(self, "res_tn_box_combo") and "tn_box_idx" in res_cfg:
            try:
                tn_idx = int(res_cfg["tn_box_idx"])
                if 0 <= tn_idx < len(self.res_tn_box_combo["values"]):
                    self.res_tn_box_combo.current(tn_idx)
            except (ValueError, IndexError):
                pass
        if "resource_cities" in res_cfg and isinstance(res_cfg["resource_cities"], list):
            self._selected_resource_cities = {int(x) for x in res_cfg["resource_cities"]}
            if hasattr(self, "bld_bases_tree"):
                for iid in self.bld_bases_tree.get_children(""):
                    try:
                        cid = int(iid)
                        vals = list(self.bld_bases_tree.item(iid, "values"))
                        if len(vals) > 1:
                            vals[1] = "☑" if cid in self._selected_resource_cities else "☐"
                            self.bld_bases_tree.item(iid, values=vals)
                    except ValueError:
                        pass
        if hasattr(self, "_append_bld_log"):
            self._append_bld_log(
                f"📂 Đã nạp cấu hình tài nguyên cho {len(self._selected_resource_cities)} thành từ hồ sơ."
            )
        return "Tài Nguyên"

    def _collect_logistics_profile_dict(self) -> dict:
        return {
            "army_type_idx": self.log_army_combo.current() if hasattr(self, "log_army_combo") else 0,
            "amount": self.log_amount_var.get() if hasattr(self, "log_amount_var") else "1000",
            "auto_daily_reward": bool(self.aux_daily_reward_var.get()) if hasattr(self, "aux_daily_reward_var") else True,
            "auto_explore": bool(self.aux_explore_var.get()) if hasattr(self, "aux_explore_var") else False,
            "explore_use_whip": (
                bool(self.aux_explore_whip_var.get()) if hasattr(self, "aux_explore_whip_var") else False
            ),
            "explore_use_coin": (
                bool(self.aux_explore_coin_var.get()) if hasattr(self, "aux_explore_coin_var") else False
            ),
            "explore_turns": self.aux_explore_turns_var.get() if hasattr(self, "aux_explore_turns_var") else "1",
        }

    def _apply_logistics_profile_dict(self, log_data: dict) -> str:
        if hasattr(self, "log_army_combo") and "army_type_idx" in log_data:
            try:
                self.log_army_combo.current(int(log_data["army_type_idx"]))
            except Exception:
                pass
        if hasattr(self, "log_amount_var") and "amount" in log_data:
            self.log_amount_var.set(str(log_data["amount"]))
        if hasattr(self, "aux_daily_reward_var") and "auto_daily_reward" in log_data:
            self.aux_daily_reward_var.set(bool(log_data["auto_daily_reward"]))
        if hasattr(self, "aux_explore_var") and "auto_explore" in log_data:
            self.aux_explore_var.set(bool(log_data["auto_explore"]))
        if "explore_use_whip" in log_data or "explore_use_coin" in log_data:
            use_whip = bool(
                log_data.get(
                    "explore_use_whip",
                    self.aux_explore_whip_var.get() if hasattr(self, "aux_explore_whip_var") else False,
                )
            )
            use_coin = bool(
                log_data.get(
                    "explore_use_coin",
                    self.aux_explore_coin_var.get() if hasattr(self, "aux_explore_coin_var") else False,
                )
            )
            if use_whip and use_coin:
                use_coin = False
            if hasattr(self, "aux_explore_whip_var"):
                self.aux_explore_whip_var.set(use_whip)
            if hasattr(self, "aux_explore_coin_var"):
                self.aux_explore_coin_var.set(use_coin)
        if hasattr(self, "aux_explore_turns_var") and "explore_turns" in log_data:
            self.aux_explore_turns_var.set(str(log_data["explore_turns"]))
        self._update_explore_turns_visibility()
        return "Hậu Cần"

    def _apply_resource_settings(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        gold_th = self.res_gold_thresh_var.get()
        w_pct = self.res_wood_pct_var.get()
        i_pct = self.res_iron_pct_var.get()
        s_pct = self.res_stone_pct_var.get()
        f_pct = self.res_food_pct_var.get()
        g_box = self.res_gold_box_combo.get() if hasattr(self, "res_gold_box_combo") else ""
        tn_box = self.res_tn_box_combo.get() if hasattr(self, "res_tn_box_combo") else ""
        self._append_bld_log(
            f"✅ Áp dụng thiết lập tài nguyên: Vàng<{gold_th}, TN G/S/Đ/T<{w_pct}%/{i_pct}%/{s_pct}%/{f_pct}%, Rương: {g_box.split(':')[0]} / {tn_box.split(':')[0]}"
        )
        try:
            self._save_unified_profile()
        except Exception:
            pass
        messagebox.showinfo("Thành công", "Đã lưu và áp dụng thiết lập ngưỡng tài nguyên & rương!")

    def _toggle_resource_monitor(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if not self._res_monitor_running:
            target_cids = list(self._selected_resource_cities)
            if not target_cids:
                if self._current_bld_city_id:
                    target_cids = [self._current_bld_city_id]
                elif hasattr(self, "bld_bases_tree"):
                    children = self.bld_bases_tree.get_children("")
                    if children:
                        try:
                            target_cids = [int(children[0])]
                        except ValueError:
                            pass
            if not target_cids:
                messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn cột 'Tài nguyên' cho ít nhất 1 thành!")
                return

            self._res_monitor_running = True
            self.res_monitor_btn.configure(text="Đang Giữ TN", style="Success.TButton")
            self._append_bld_log(f"▶️ Bắt đầu giám sát ngưỡng tài nguyên cho {len(target_cids)} thành...")
            self._res_monitor_thread = threading.Thread(target=self._run_resource_monitor_loop, daemon=True)
            self._res_monitor_thread.start()
        else:
            self._res_monitor_running = False
            self.res_monitor_btn.configure(text="Tài Nguyên", style="Danger.TButton")
            self._append_bld_log("⏹️ Đã dừng giám sát tài nguyên.")

    def _check_resource_thresholds_for_city(self, cid: int) -> None:
        """Kiểm tra ngưỡng Vàng/Khoáng sản của đúng một Thành; chuyển focus trước khi mở rương."""
        cname = f"Thành {cid}"
        if self.roster:
            b = self.roster.base_by_id(cid)
            if b:
                cname = b.name

        # 1. Lấy tài nguyên (/api/resource/info) & vàng (/api/city/info) trên Server 58+
        res_data = self.gateway.resource_info(cid)
        city_data = self.gateway.city_info(cid)

        city_ok = (
            isinstance(city_data, dict)
            and int(city_data.get("ret", -1)) == 0
            and ("m_lmoney_balance" in city_data or "money" in city_data)
        )
        res_ok = (
            isinstance(res_data, dict)
            and int(res_data.get("ret", -1)) == 0
            and ("m_lmax_storage" in res_data or "max_storage" in res_data)
        )

        need_gold = False
        money = 0
        gold_th = 100000000
        if city_ok:
            money = int(city_data.get("m_lmoney_balance", city_data.get("money", 0)))
            try:
                gold_th = int(self.res_gold_thresh_var.get().replace(",", "").replace(".", "").strip())
            except ValueError:
                gold_th = 100000000
            need_gold = money < gold_th

        need_tn = False
        max_storage = 0
        if res_ok:
            wood = int(res_data.get("m_lwood_balance", res_data.get("wood", 0)))
            iron = int(res_data.get("m_liron_balance", res_data.get("iron", 0)))
            stone = int(res_data.get("m_lstone_balance", res_data.get("stone", 0)))
            food = int(res_data.get("m_lfood_balance", res_data.get("food", 0)))
            max_storage = int(res_data.get("m_lmax_storage", res_data.get("max_storage", 0)))
            if max_storage > 0:
                try:
                    w_pct = float(self.res_wood_pct_var.get()) / 100.0
                    i_pct = float(self.res_iron_pct_var.get()) / 100.0
                    s_pct = float(self.res_stone_pct_var.get()) / 100.0
                    f_pct = float(self.res_food_pct_var.get()) / 100.0
                except ValueError:
                    w_pct = i_pct = s_pct = f_pct = 0.7

                need_tn = (
                    wood < max_storage * w_pct
                    or iron < max_storage * i_pct
                    or stone < max_storage * s_pct
                    or food < max_storage * f_pct
                )

        if not (need_gold or need_tn):
            return

        def _open_box_for_city(combo_attr: str, default_id: int, icon: str, kind_label: str, reason: str) -> None:
            combo = getattr(self, combo_attr, None)
            box_str = combo.get() if combo is not None else str(default_id)
            try:
                box_id = int(str(box_str).split(":")[0].strip())
            except (ValueError, IndexError):
                box_id = default_id
            r_box = self.gateway.call("Common.ashx", 48, {"lBoxID": str(box_id), "_": ""})
            ret = int(r_box.get("ret", -1)) if isinstance(r_box, dict) else -1
            if ret in (110, 73):
                self._res_monitor_running = False
                self.after(0, self._append_bld_log, f"⚠️ [{cname}] Server yêu cầu Captcha khi mở rương #{box_id}!")
                return
            if ret == 0:
                logger.info(f"[{cname}] (cid={cid}) {reason}: Đã mở {kind_label} #{box_id}.")
                self.after(0, self._append_bld_log, f"{icon} [{cname}] {reason}: Đã mở {kind_label} #{box_id}.")
            else:
                self.after(0, self._append_bld_log, f"⚠️ [{cname}] Mở {kind_label} #{box_id} thất bại (mã {ret}).")

        with gateway_city_context(self.gateway):
            ok_sw, sw_ret, sw_msg = switch_city_verified(self.gateway, cid)
            if not ok_sw:
                logger.warning(f"[{cname}] (cid={cid}) {sw_msg}; bỏ qua mở rương để tránh mở nhầm thành khác.")
                self.after(0, self._append_bld_log, f"⚠️ [{cname}] {sw_msg}; bỏ qua mở rương.")
                if sw_ret in (110, 73):
                    self._res_monitor_running = False
                return

            if need_gold:
                _open_box_for_city(
                    "res_gold_box_combo",
                    11,
                    "💰",
                    "rương vàng",
                    f"Vàng={money:,} < ngưỡng {gold_th:,}",
                )

            if need_tn and self._res_monitor_running:
                _open_box_for_city(
                    "res_tn_box_combo",
                    24,
                    "📦",
                    "rương TN",
                    f"Khoáng sản dưới ngưỡng (Kho {max_storage:,})",
                )

    def _run_resource_monitor_loop(self):
        while self._res_monitor_running:
            target_cids = list(self._selected_resource_cities)
            if not target_cids and self._current_bld_city_id:
                target_cids = [self._current_bld_city_id]

            for cid in target_cids:
                if not self._res_monitor_running:
                    break
                try:
                    self._check_resource_thresholds_for_city(cid)
                except (RuntimeError, tk.TclError):
                    break
                except Exception as e:
                    try:
                        self.after(0, self._append_bld_log, f"❌ Lỗi kiểm tra tài nguyên thành {cid}: {e}")
                    except Exception:
                        pass

            for _ in range(30):
                if not self._res_monitor_running:
                    break
                time.sleep(1)

    def _on_chest_type_selected(self, _event=None):
        """Cập nhật trạng thái chọn Thành theo loại rương (vô hiệu hóa với rương cấp tài khoản)."""
        if not hasattr(self, "chest_type_combo") or not hasattr(self, "chest_city_combo"):
            return
        if getattr(self, "_chest_running", False):
            return
        chest_name = self.chest_type_combo.get().strip()
        if not chest_needs_city_switch(chest_name):
            self.chest_city_combo.configure(state="disabled")
        else:
            self.chest_city_combo.configure(state="readonly")

    def _get_selected_chest_city(self) -> tuple[Optional[int], str]:
        """Lấy Thành hợp lệ (ID dương) đang chọn cho chức năng Mở Rương Hàng Loạt."""
        if not self.roster:
            return None, ""
        sel_text = self.chest_city_combo.get().strip() if hasattr(self, "chest_city_combo") else ""
        if sel_text:
            for c in self.roster.cities:
                if sel_text in (c.display_name, c.name):
                    return c.id, c.name
            for b in self.roster.bases:
                if sel_text in (b.display_name, b.name):
                    return b.id, b.name

        if hasattr(self, "chest_city_combo"):
            sel_idx = self.chest_city_combo.current()
            if 0 <= sel_idx < len(self.roster.cities):
                c = self.roster.cities[sel_idx]
                return c.id, c.name

        cur_cid = getattr(self, "_current_bld_city_id", None)
        if cur_cid and int(cur_cid) > 0:
            b = self.roster.base_by_id(int(cur_cid))
            if b and not b.is_camp:
                return b.id, b.name
        return None, ""

    def _set_chest_controls_running(self, running: bool):
        """Chuyển trạng thái điều khiển của khung Mở Rương Hàng Loạt."""
        self._chest_running = running
        if running:
            if hasattr(self, "chest_start_btn") and self.chest_start_btn.winfo_exists():
                self.chest_start_btn.configure(state="disabled")
            if hasattr(self, "chest_stop_btn") and self.chest_stop_btn.winfo_exists():
                self.chest_stop_btn.configure(state="normal")
            if hasattr(self, "chest_type_combo") and self.chest_type_combo.winfo_exists():
                self.chest_type_combo.configure(state="disabled")
            if hasattr(self, "chest_city_combo") and self.chest_city_combo.winfo_exists():
                self.chest_city_combo.configure(state="disabled")
            if hasattr(self, "chest_times_entry") and self.chest_times_entry.winfo_exists():
                self.chest_times_entry.configure(state="disabled")
        else:
            if hasattr(self, "chest_start_btn") and self.chest_start_btn.winfo_exists():
                self.chest_start_btn.configure(state="normal")
            if hasattr(self, "chest_stop_btn") and self.chest_stop_btn.winfo_exists():
                self.chest_stop_btn.configure(state="disabled")
            if hasattr(self, "chest_type_combo") and self.chest_type_combo.winfo_exists():
                self.chest_type_combo.configure(state="readonly")
            if hasattr(self, "chest_times_entry") and self.chest_times_entry.winfo_exists():
                self.chest_times_entry.configure(state="normal")
            self._on_chest_type_selected()

    def _start_open_chest_batch(self):
        """Khởi chạy tác vụ Mở Rương Hàng Loạt bằng đa luồng."""
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        if getattr(self, "_chest_running", False):
            return
        if self.gateway is None:
            messagebox.showwarning("Cảnh báo", "Chưa kết nối tài khoản game!")
            return

        chest_name = self.chest_type_combo.get().strip() if hasattr(self, "chest_type_combo") else ""
        if chest_name not in CHEST_MAPPING:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn loại rương hợp lệ!")
            return

        times_raw = self.chest_times_var.get().strip() if hasattr(self, "chest_times_var") else ""
        try:
            times = int(times_raw)
            if times <= 0:
                raise ValueError
        except (ValueError, TypeError):
            messagebox.showerror("Lỗi", "Số lượt mở rương phải là số nguyên dương!")
            return

        if times > 5000:
            if not messagebox.askyesno(
                "Xác nhận",
                f"Bạn sắp mở {times} rương. Số lượng lớn có thể mất nhiều thời gian.\nBạn có muốn tiếp tục?",
            ):
                return

        needs_switch = chest_needs_city_switch(chest_name)
        if needs_switch:
            city_id, city_name = self._get_selected_chest_city()
            if city_id is None or city_id <= 0:
                messagebox.showwarning(
                    "Cảnh báo",
                    "Vui lòng chọn một Thành hợp lệ (không phải Doanh trại) để mở loại rương này!",
                )
                return
        else:
            city_id, city_name = None, ""

        self._chest_stop_event = threading.Event()
        q: queue.Queue = queue.Queue()
        self._chest_queue = q
        self._set_chest_controls_running(True)
        if hasattr(self, "chest_progress_bar"):
            self.chest_progress_bar.configure(value=0)
        if hasattr(self, "chest_progress_lbl"):
            self.chest_progress_lbl.configure(text=f"Tiến độ: 0% (0/{times})")

        if needs_switch:
            self._append_bld_log(f"📦 Bắt đầu mở {times}x [{chest_name}] tại Thành [{city_name}]...")
        else:
            self._append_bld_log(f"📦 Bắt đầu mở {times}x [{chest_name}]...")

        stop_ev = self._chest_stop_event

        def _worker():
            summary: dict[str, Any] = {
                "success_count": 0,
                "failed_count": 0,
                "completed": 0,
                "total": times,
                "aborted_reason": None,
                "last_ret": None,
            }
            err_msg: Optional[str] = None
            try:
                summary = run_batch_open_chest(
                    gateway=self.gateway,
                    chest_name=chest_name,
                    times=times,
                    city_id=city_id,
                    city_name=city_name,
                    max_workers=5,
                    stop_event=stop_ev,
                    on_log=lambda m: q.put(("log", m)),
                    on_progress=lambda done, total, pct: q.put(("progress", done, total, pct)),
                )
            except Exception as ex:
                logger.exception(f"Lỗi khi mở rương hàng loạt: {ex}")
                err_msg = str(ex)
                q.put(("log", f"❌ Lỗi mở rương hàng loạt: {ex}"))
            finally:
                q.put(("done", chest_name, times, summary, err_msg))

        self._chest_thread = threading.Thread(target=_worker, name="OpenChestBatchRunner", daemon=True)
        self._chest_thread.start()
        self.after(20, self._poll_chest_queue)

    def _poll_chest_queue(self):
        """Rút tiến độ, log và kết quả Mở Rương Hàng Loạt trên luồng giao diện chính."""
        q = getattr(self, "_chest_queue", None)
        if q is None:
            return
        keep_polling = True
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            kind = item[0]
            if kind == "log":
                self._append_bld_log(item[1])
            elif kind == "progress":
                _, done, total, pct = item
                if hasattr(self, "chest_progress_bar") and self.chest_progress_bar.winfo_exists():
                    self.chest_progress_bar.configure(value=pct)
                if hasattr(self, "chest_progress_lbl") and self.chest_progress_lbl.winfo_exists():
                    self.chest_progress_lbl.configure(text=f"Tiến độ: {pct:.0f}% ({done}/{total})")
            elif kind == "done":
                _, chest_name, times, summary, _err = item
                keep_polling = False
                self._set_chest_controls_running(False)
                succ = summary.get("success_count", 0)
                fail = summary.get("failed_count", 0)
                comp = summary.get("completed", 0)
                tot = summary.get("total", times)
                pct = (comp / tot * 100.0) if tot > 0 else 0.0
                if hasattr(self, "chest_progress_bar") and self.chest_progress_bar.winfo_exists():
                    self.chest_progress_bar.configure(value=pct)
                if hasattr(self, "chest_progress_lbl") and self.chest_progress_lbl.winfo_exists():
                    self.chest_progress_lbl.configure(text=f"Tiến độ: {pct:.0f}% ({comp}/{tot})")
                if summary.get("aborted_reason") == "captcha" and hasattr(self, "status"):
                    self.status.set("Cần giải Captcha")
                self._append_bld_log(
                    f"🏁 Kết thúc mở [{chest_name}]: Thành công {succ}/{tot}, Thất bại {fail}."
                )
        if keep_polling and getattr(self, "_chest_running", False):
            self.after(20, self._poll_chest_queue)

    def _stop_open_chest_batch(self):
        """Dừng tiến trình Mở Rương Hàng Loạt đang chạy."""
        if getattr(self, "_chest_running", False) and getattr(self, "_chest_stop_event", None):
            self._chest_stop_event.set()
            if hasattr(self, "chest_stop_btn") and self.chest_stop_btn.winfo_exists():
                self.chest_stop_btn.configure(state="disabled")
            self._append_bld_log("⏹️ Đang dừng tiến trình mở rương...")

    def _cancel_after_timer(self, attr_name: str):
        """Hủy lịch after đang chờ theo tên thuộc tính nếu có."""
        old_id = getattr(self, attr_name, None)
        if old_id is not None:
            try:
                self.after_cancel(old_id)
            except Exception:
                pass
            setattr(self, attr_name, None)

    def _tick_aux_countdown(
        self,
        *,
        seconds_attr: str,
        after_attr: str,
        label_attr: str,
        zero_text: str,
        zero_fg: str,
        tick_cb: Callable[[], None],
        on_zero: Optional[Callable[[], None]] = None,
    ):
        """Giảm bộ đếm ngược mỗi giây và kích hoạt hành động khi về 0."""
        setattr(self, after_attr, None)
        try:
            lbl = getattr(self, label_attr, None)
            if not (lbl is not None and lbl.winfo_exists()):
                return
            secs = max(0, int(getattr(self, seconds_attr, 0) or 0) - 1)
            setattr(self, seconds_attr, secs)
            if secs > 0:
                lbl.configure(text=f"(Còn: {self._format_explore_countdown(secs)})", fg="#4ade80")
                setattr(self, after_attr, self.after(1000, tick_cb))
            else:
                lbl.configure(text=zero_text, fg=zero_fg)
                if on_zero is not None:
                    on_zero()
        except (RuntimeError, tk.TclError):
            pass

    def _cancel_boost_countdown_timer(self):
        self._cancel_after_timer("_boost_countdown_after_id")

    def _tick_boost_countdown(self):
        self._tick_aux_countdown(
            seconds_attr="_boost_left_seconds",
            after_attr="_boost_countdown_after_id",
            label_attr="aux_boost_time_lbl",
            zero_text="(Hết hạn)",
            zero_fg="#f87171",
            tick_cb=self._tick_boost_countdown,
            on_zero=lambda: self._check_and_update_boost_status(async_check=True)
            if self.aux_boost_var.get()
            else None,
        )

    def _update_boost_countdown_ui(self, remaining: int):
        def _apply():
            try:
                if not (hasattr(self, "aux_boost_time_lbl") and self.aux_boost_time_lbl.winfo_exists()):
                    return
                self._cancel_boost_countdown_timer()
                secs = max(0, int(remaining))
                self._boost_left_seconds = secs
                if secs > 0:
                    self.aux_boost_time_lbl.configure(
                        text=f"(Còn: {self._format_explore_countdown(secs)})",
                        fg="#4ade80",
                    )
                    self._boost_countdown_after_id = self.after(1000, self._tick_boost_countdown)
                else:
                    self.aux_boost_time_lbl.configure(text="(Hết hạn)", fg="#f87171")
            except (RuntimeError, tk.TclError):
                pass

        if threading.current_thread() is threading.main_thread():
            _apply()
        else:
            try:
                self.after(0, _apply)
            except (RuntimeError, tk.TclError):
                pass

    def _check_and_update_boost_status(self, async_check: bool = True):
        """Kiểm tra thời gian còn lại của DS kiến trúc (xây 3 công trình) và tự kích hoạt nếu hết hạn."""
        BuildingTask = resolve_dashboard_symbol("BuildingTask", _DefaultBuildingTask)

        def run_check():
            if not self.gateway:
                return
            try:
                city_id = getattr(self, "_current_bld_city_id", 0) or 0
                resp = self.gateway.page_building(city_id) or {}
                remaining = parse_boost_remaining_time(resp, city_id)
                self._update_boost_countdown_ui(remaining)

                if remaining <= 0:
                    if self.aux_boost_var.get():
                        now_ts = time.time()
                        last_act = max(
                            getattr(self, "_last_boost_act_time", 0),
                            getattr(BuildingTask, "_last_boost_act_time", 0),
                        )
                        if now_ts - last_act > 60:
                            self._last_boost_act_time = now_ts
                            BuildingTask._last_boost_act_time = now_ts
                            msg = "⚡ DS kiến trúc đã hết hạn. Đang tự kích hoạt lại (3 vị trí thi công)..."
                            if threading.current_thread() is threading.main_thread():
                                self._append_bld_log(msg)
                            else:
                                try:
                                    self.after(0, self._append_bld_log, msg)
                                except RuntimeError:
                                    pass
                            act_resp = (
                                self.gateway.call(
                                    "OPT.ashx",
                                    69,
                                    {"type": "3", "param1": "0", "param2": "0", "paytype": "2", "_": ""},
                                )
                                or {}
                            )
                            ret = act_resp.get("ret", 0)
                            if ret == 0:
                                ok_msg = "✅ Kích hoạt thành công DS kiến trúc (3 vị trí thi công)!"
                                if threading.current_thread() is threading.main_thread():
                                    self._append_bld_log(ok_msg)
                                else:
                                    try:
                                        self.after(0, self._append_bld_log, ok_msg)
                                    except RuntimeError:
                                        pass
                                time.sleep(1)
                                self._check_and_update_boost_status(async_check=async_check)
                            else:
                                fail_msg = f"⚠️ Kích hoạt DS kiến trúc thất bại (mã {ret})."
                                if threading.current_thread() is threading.main_thread():
                                    self._append_bld_log(fail_msg)
                                else:
                                    try:
                                        self.after(0, self._append_bld_log, fail_msg)
                                    except RuntimeError:
                                        pass
            except Exception as e:
                logger.debug(f"Lỗi kiểm tra DS kiến trúc: {e}")

        if async_check:
            t = threading.Thread(target=run_check, daemon=True)
            t.start()
            return t
        else:
            run_check()
            return None

    def _update_explore_turns_visibility(self):
        """Ẩn/hiện ô nhập số lượt Thám bảo tùy theo checkbox Dùng Roi / Dùng Coin."""
        if not hasattr(self, "aux_explore_turns_frame"):
            return
        show = bool(self.aux_explore_whip_var.get() or self.aux_explore_coin_var.get())
        if show:
            if not self.aux_explore_turns_frame.winfo_manager():
                self.aux_explore_turns_frame.pack(side="left", padx=2)
        else:
            self.aux_explore_turns_frame.pack_forget()

    def _on_explore_clear_mode_changed(self, source: str):
        """Đảm bảo Dùng Roi và Dùng Coin loại trừ lẫn nhau và đồng bộ ô Số lượt."""
        if source == "whip" and self.aux_explore_whip_var.get():
            self.aux_explore_coin_var.set(False)
        elif source == "coin" and self.aux_explore_coin_var.get():
            self.aux_explore_whip_var.set(False)
        self._update_explore_turns_visibility()
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()
        if self.aux_explore_var.get() and (self.aux_explore_whip_var.get() or self.aux_explore_coin_var.get()):
            self._check_and_run_explore(async_check=True)

    def _on_aux_explore_toggled(self):
        """Kích hoạt hoặc dừng kiểm tra/chạy Thám bảo khi bật tắt checkbox."""
        self._explore_stop_requested = not bool(self.aux_explore_var.get())
        if hasattr(self, "_schedule_auto_save"):
            self._schedule_auto_save()
        self._check_and_run_explore(async_check=True)

    def _log_explore(self, msg: str):
        """Ghi nhật ký Thám bảo an toàn luồng vào Nhật ký Nội Chính."""
        if threading.current_thread() is threading.main_thread():
            self._append_bld_log(msg)
        else:
            try:
                self.after(0, self._append_bld_log, msg)
            except (RuntimeError, tk.TclError):
                pass

    def _reset_explore_clear_mode_ui(self):
        """Bỏ tích Dùng Roi / Dùng Coin và ẩn ô Số lượt sau khi hoàn tất lượt."""

        def _do():
            try:
                if hasattr(self, "aux_explore_whip_var"):
                    self.aux_explore_whip_var.set(False)
                if hasattr(self, "aux_explore_coin_var"):
                    self.aux_explore_coin_var.set(False)
                self._update_explore_turns_visibility()
            except (RuntimeError, tk.TclError):
                pass

        if threading.current_thread() is threading.main_thread():
            _do()
        else:
            try:
                self.after(0, _do)
            except (RuntimeError, tk.TclError):
                pass

    @staticmethod
    def _format_explore_countdown(seconds: int) -> str:
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}:{m:02d}:{s:02d}"

    def _cancel_explore_countdown_timer(self):
        self._cancel_after_timer("_explore_countdown_after_id")

    def _tick_explore_countdown(self):
        self._tick_aux_countdown(
            seconds_attr="_explore_left_seconds",
            after_attr="_explore_countdown_after_id",
            label_attr="aux_explore_time_lbl",
            zero_text="(Sẵn sàng)",
            zero_fg="#4ade80",
            tick_cb=self._tick_explore_countdown,
            on_zero=lambda: self._check_and_run_explore(async_check=True)
            if self.aux_explore_var.get() and not self._explore_worker_running
            else None,
        )

    def _update_explore_countdown_ui(self, left_seconds: Optional[int], error_text: str = "", seq: Optional[int] = None):
        def _apply():
            try:
                if seq is not None and seq != self._explore_seq:
                    return
                if not (hasattr(self, "aux_explore_time_lbl") and self.aux_explore_time_lbl.winfo_exists()):
                    return
                self._cancel_explore_countdown_timer()
                if error_text or left_seconds is None:
                    self._explore_left_seconds = 0
                    self.aux_explore_time_lbl.configure(text=f"({error_text or 'Lỗi'})", fg="#f87171")
                    return
                secs = max(0, int(left_seconds))
                self._explore_left_seconds = secs
                if secs > 0:
                    self.aux_explore_time_lbl.configure(
                        text=f"(Còn: {self._format_explore_countdown(secs)})",
                        fg="#4ade80",
                    )
                    self._explore_countdown_after_id = self.after(1000, self._tick_explore_countdown)
                else:
                    self.aux_explore_time_lbl.configure(text="(Sẵn sàng)", fg="#4ade80")
            except (RuntimeError, tk.TclError):
                pass

        if threading.current_thread() is threading.main_thread():
            _apply()
        else:
            try:
                self.after(0, _apply)
            except (RuntimeError, tk.TclError):
                pass

    def _api_check_explore_status(self) -> tuple[bool, int, str]:
        """Gọi Common.ashx?id=140 (lAction=0) kiểm tra thời gian chờ Thám bảo."""
        try:
            resp = self.gateway.call("Common.ashx", 140, {"lAction": "0", "lParam": "0", "_": ""})
            if not isinstance(resp, dict):
                return False, 0, "Lỗi kết nối"
            ret_val = resp.get("ret", -1)
            if ret_val != 0:
                return False, 0, f"Lỗi API {ret_val}"
            try:
                left_seconds = max(0, int(resp.get("left", 0) or 0))
            except (TypeError, ValueError):
                left_seconds = 0
            return left_seconds == 0, left_seconds, ""
        except Exception as e:
            return False, 0, f"Lỗi: {e}"

    def _api_clear_explore_cooldown(self, clear_type: int) -> bool:
        """Gọi Common.ashx?id=140 (lAction=2) xóa thời gian chờ bằng Roi (1) hoặc Coin (2)."""
        try:
            resp = self.gateway.call("Common.ashx", 140, {"lAction": "2", "lParam": str(clear_type), "_": ""})
            return isinstance(resp, dict) and resp.get("ret", -1) == 0
        except Exception:
            return False

    def _api_perform_explore(self) -> tuple[bool, str]:
        """Gọi Common.ashx?id=140 (lAction=1) thực hiện Thám bảo và trích xuất tên vật phẩm."""
        try:
            resp = self.gateway.call("Common.ashx", 140, {"lAction": "1", "lParam": "0", "_": ""})
            if not isinstance(resp, dict) or resp.get("ret", -1) != 0:
                return False, ""
            bonus = str(resp.get("bonus", "") or "")
            match = re.search(r"获得：([^×<\n]+)", bonus)
            if match:
                item_name = match.group(1).strip()
            else:
                item_name = bonus.strip() or "Vật phẩm"
            return True, item_name
        except Exception:
            return False, ""

    def _check_and_run_explore(self, async_check: bool = True):
        """Kiểm tra thời gian chờ Thám bảo và tự động thám bảo theo chế độ đã chọn."""
        if not self.gateway:
            return None
        if async_check and self._explore_worker_running:
            return None

        on_main = threading.current_thread() is threading.main_thread()
        if on_main:
            auto_explore = bool(self.aux_explore_var.get())
            use_whip = bool(self.aux_explore_whip_var.get())
            use_coin = bool(self.aux_explore_coin_var.get())
            turns_str = self.aux_explore_turns_var.get().strip()
            if auto_explore:
                self._explore_stop_requested = False
        else:
            auto_explore = False
            use_whip = False
            use_coin = False
            turns_str = "1"

        def run_check():
            if not self._explore_lock.acquire(blocking=not async_check):
                return
            try:
                self._explore_worker_running = True
                self._explore_seq += 1
                seq = self._explore_seq

                if auto_explore and (use_whip or use_coin):
                    clear_type = 1 if use_whip else 2
                    mode_name = "Roi" if clear_type == 1 else "Coin"
                    try:
                        turns = int(turns_str)
                    except (TypeError, ValueError):
                        turns = 0

                    if turns <= 0:
                        self._log_explore(
                            "⚠️ Số lượt thám bảo phải là số nguyên dương (> 0). Chuyển về chế độ chờ countdown."
                        )
                        self._reset_explore_clear_mode_ui()
                    else:
                        self._log_explore(f"🧭 Bắt đầu Thám bảo {turns} lượt (Dùng {mode_name})...")
                        success_count = 0
                        for turn_idx in range(1, turns + 1):
                            if self._explore_stop_requested:
                                self._log_explore(f"🛑 Đã dừng Thám bảo ở lượt {turn_idx}/{turns}.")
                                break
                            can_explore, left_seconds, err = self._api_check_explore_status()
                            if err:
                                self._log_explore(f"❌ Lượt {turn_idx}/{turns}: Lỗi kiểm tra Thám bảo ({err}).")
                                break
                            if not can_explore and left_seconds > 0:
                                if not self._api_clear_explore_cooldown(clear_type):
                                    self._log_explore(
                                        f"⚠️ Lượt {turn_idx}/{turns}: Không thể xóa thời gian chờ (hết {mode_name}?), chuyển về chế độ chờ countdown."
                                    )
                                    break
                                can_explore, left_seconds, err = self._api_check_explore_status()
                                if err or not can_explore:
                                    self._log_explore(
                                        f"❌ Lượt {turn_idx}/{turns}: Vẫn còn thời gian chờ sau khi xóa ({err or f'{left_seconds}s'})."
                                    )
                                    break
                            ok, item_name = self._api_perform_explore()
                            if ok:
                                success_count += 1
                                self._log_explore(f"🧭 Thám bảo lượt {turn_idx}/{turns}: Nhận được {item_name}")
                            else:
                                self._log_explore(f"❌ Thám bảo lượt {turn_idx}/{turns} thất bại.")
                                break
                        self._reset_explore_clear_mode_ui()
                        self._log_explore(f"✅ Hoàn tất Thám bảo ({success_count}/{turns} lượt thành công).")
                        can_explore, left_seconds, err = self._api_check_explore_status()
                        self._update_explore_countdown_ui(None if err else left_seconds, err, seq=seq)
                        return

                can_explore, left_seconds, err = self._api_check_explore_status()
                if err:
                    self._update_explore_countdown_ui(None, err, seq=seq)
                    return

                if can_explore and auto_explore and not self._explore_stop_requested:
                    ok, item_name = self._api_perform_explore()
                    if ok:
                        self._log_explore(f"🧭 Thám bảo tự động: Nhận được {item_name}")
                    else:
                        self._log_explore("⚠️ Thám bảo tự động thất bại.")
                    can_explore, left_seconds, err = self._api_check_explore_status()
                    if err:
                        self._update_explore_countdown_ui(None, err, seq=seq)
                        return

                self._update_explore_countdown_ui(left_seconds, "", seq=seq)
            except Exception as e:
                logger.debug(f"Lỗi kiểm tra/chạy Thám bảo: {e}")
            finally:
                self._explore_worker_running = False
                self._explore_lock.release()

        if async_check:
            t = threading.Thread(target=run_check, daemon=True)
            t.start()
            return t
        run_check()
        return None

    def _schedule_periodic_boost_check(self):
        old_id = getattr(self, "_boost_after_id", None)
        if old_id is not None:
            try:
                self.after_cancel(old_id)
            except Exception:
                pass
            self._boost_after_id = None
        try:
            if hasattr(self, "aux_boost_time_lbl") and self.aux_boost_time_lbl.winfo_exists():
                self._check_and_update_boost_status(async_check=True)
                self._check_and_run_explore(async_check=True)
                today_str = time.strftime("%Y-%m-%d")
                if getattr(self, "aux_daily_reward_var", None) and self.aux_daily_reward_var.get():
                    if getattr(self, "_last_daily_claim_date", None) != today_str:
                        self._last_daily_claim_date = today_str
                        self._do_claim_daily()
                self._boost_after_id = self.after(60000, self._schedule_periodic_boost_check)
        except (RuntimeError, tk.TclError):
            pass

    def _add_army_transfer_order(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        f_city = self.log_from_city_combo.get()
        t_city = self.log_to_city_combo.get()
        if not f_city or not t_city or f_city == t_city:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn thành đi và thành đến khác nhau!")
            return
        army = self.log_army_combo.get()
        amount = self.log_amount_var.get().strip() or "1"
        route = f"{f_city} ➔ {t_city}"
        self.log_transfers_tree.insert("", "end", values=(route, amount, army))
        self._append_bld_log(f"➕ Thêm lệnh chuyển quân giới: {route} | SL: {amount} | {army}")

    def _delete_army_transfer_order(self):
        messagebox = resolve_dashboard_symbol("messagebox", _default_messagebox)
        sel = self.log_transfers_tree.selection()
        if not sel:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn 1 lệnh chuyển quân trong bảng để xóa!")
            return
        for item in sel:
            self.log_transfers_tree.delete(item)
        self._append_bld_log("🗑️ Đã xóa lệnh chuyển quân giới đã chọn.")
