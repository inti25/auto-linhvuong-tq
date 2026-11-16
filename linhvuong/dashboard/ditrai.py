"""Phân hệ Di Trại Độc Lập trên giao diện Dashboard."""

import logging
import threading
import time
from tkinter import messagebox

from ..locks import TargetLocks
from ..roster import City
from ..tasks.base import TaskContext
from ..tasks.di_trai import DiTrai
from .shared import resolve_dashboard_symbol


class DiTraiMixin:
    """Quản lý điều khiển Di Trại Độc Lập và đồng bộ tọa độ Doanh trại."""

    def _collect_ditrai_profile_dict(self) -> dict:
        return {
            "dest_x": self.dt_dest_x_var.get() if hasattr(self, "dt_dest_x_var") else "",
            "dest_y": self.dt_dest_y_var.get() if hasattr(self, "dt_dest_y_var") else "",
        }

    def _apply_ditrai_profile_dict(self, dt_data: dict) -> None:
        if hasattr(self, "dt_dest_x_var") and "dest_x" in dt_data:
            self.dt_dest_x_var.set(str(dt_data["dest_x"]))
        if hasattr(self, "dt_dest_y_var") and "dest_y" in dt_data:
            self.dt_dest_y_var.set(str(dt_data["dest_y"]))

    def _append_dt_log(self, msg: str):
        if hasattr(self, "_append_bld_log"):
            self._append_bld_log(msg)
        if hasattr(self, "_append_bm_log"):
            self._append_bm_log(msg)

    def _on_dt_camp_selected(self, _event=None):
        sel_idx = self.dt_camp_combo.current()
        camps = self.roster.camps if self.roster.camps else self.roster.bases
        if 0 <= sel_idx < len(camps):
            camp = camps[sel_idx]
            self.dt_origin_lbl.configure(text=f"Vị trí: ({camp.pos_x}, {camp.pos_y})")

    def _start_ditrai(self):
        mb = resolve_dashboard_symbol("messagebox", messagebox)
        if self._ditrai_runner and self._ditrai_runner.is_alive():
            mb.showinfo("Thông báo", "Tiến trình Di Trại đang chạy!")
            return

        camps = self.roster.camps if self.roster.camps else self.roster.bases
        sel_idx = self.dt_camp_combo.current()
        if sel_idx < 0 or sel_idx >= len(camps):
            mb.showwarning("Cảnh báo", "Vui lòng chọn Doanh trại cần di chuyển!")
            return
        camp = camps[sel_idx]

        dest_x_str = self.dt_dest_x_var.get().strip()
        dest_y_str = self.dt_dest_y_var.get().strip()
        if not dest_x_str or not dest_y_str:
            mb.showwarning("Cảnh báo", "Vui lòng nhập đầy đủ tọa độ đích X và Y!")
            return

        try:
            dest_x = int(dest_x_str)
            dest_y = int(dest_y_str)
        except ValueError:
            mb.showerror("Lỗi", "Tọa độ đích X và Y phải là số nguyên hợp lệ!")
            return

        self._ditrai_stop_event.clear()
        self.dt_start_btn.configure(state="disabled")
        self.dt_stop_btn.configure(state="normal")
        self.dt_status_lbl.configure(text=f"🚀 Đang di chuyển tới ({dest_x}, {dest_y})...", fg="#38bdf8")
        self._append_dt_log(f"🚀 Bắt đầu Di Trại {camp.name} từ ({camp.pos_x}, {camp.pos_y}) tới ({dest_x}, {dest_y})")

        self._ditrai_runner = threading.Thread(
            target=self._run_ditrai_thread,
            args=(camp, dest_x, dest_y),
            daemon=True,
        )
        self._ditrai_runner.start()

    def _stop_ditrai(self):
        self._ditrai_stop_event.set()
        self.dt_status_lbl.configure(text="⏹️ Đang gửi tín hiệu dừng Di Trại...", fg="#facc15")
        self._append_dt_log("⏹️ Người chơi bấm dừng Di Trại, chờ bước hiện tại kết thúc an toàn...")

    def _run_ditrai_thread(self, camp: City, dest_x: int, dest_y: int):
        def on_step_callback(new_x: int, new_y: int, frozen: int):
            self.roster.update_camp_position(camp.id, new_x, new_y)
            self.after(0, lambda: self.dt_origin_lbl.configure(text=f"Vị trí: ({new_x}, {new_y})"))
            for rem in range(frozen, 0, -1):
                if self._ditrai_stop_event.is_set():
                    break
                self.after(0, lambda r=rem: self.dt_status_lbl.configure(text=f"⏳ Đang đóng băng: {r}s...", fg="#facc15"))
                time.sleep(1)

            if not self._ditrai_stop_event.is_set():
                self.after(0, lambda: self.dt_status_lbl.configure(text="🏃 Đang di chuyển bước tiếp theo...", fg="#38bdf8"))

        ctx = TaskContext(
            self.gateway,
            None,
            TargetLocks(),
            notify=lambda m: self.after(0, self._append_dt_log, m),
        )

        task = DiTrai(
            ctx=ctx,
            camp_id=camp.id,
            origin=(camp.pos_x, camp.pos_y),
            destination=(dest_x, dest_y),
            max_step=2,
            sleep_fn=time.sleep,
            on_step=on_step_callback,
            stop_event=self._ditrai_stop_event,
        )

        try:
            result = task.advance_to_destination()
        except Exception as e:
            logging.getLogger("linhvuong.tasks.DiTrai").exception(f"Lỗi ngoại lệ trong quá trình Di Trại: {e}")
            result = f"error: {e}"
            self.after(0, self._append_dt_log, f"❌ Lỗi ngoại lệ trong quá trình Di Trại: {e}")

        def finalize():
            self.dt_start_btn.configure(state="normal")
            self.dt_stop_btn.configure(state="disabled")
            if result == "arrived":
                self.dt_status_lbl.configure(text=f"🎯 Đã đến đích ({dest_x}, {dest_y}) thành công!", fg="#4ade80")
                self._append_dt_log(f"🎯 Di Trại {camp.name} đã đến đích ({dest_x}, {dest_y}) thành công!")
            elif result == "stopped":
                self.dt_status_lbl.configure(text=f"⏹️ Đã dừng an toàn tại ({task.origin[0]}, {task.origin[1]})", fg="#94a3b8")
                self._append_dt_log(f"⏹️ Di Trại {camp.name} đã dừng an toàn tại ({task.origin[0]}, {task.origin[1]})")
            elif result == "insufficient_resources":
                self.dt_status_lbl.configure(text="❌ Thiếu tài nguyên di chuyển!", fg="#f87171")
                self._append_dt_log(f"❌ Di Trại {camp.name} thiếu tài nguyên để tiếp tục di chuyển!")
            else:
                self.dt_status_lbl.configure(text=f"❌ Dừng: {result}", fg="#f87171")
                self._append_dt_log(f"❌ Di Trại {camp.name} dừng: {result}")

            self._update_all_combos_coordinates()

        self.after(0, finalize)

    def _update_all_combos_coordinates(self):
        camps_items = [c.display_name for c in self.roster.camps] if self.roster.camps else [b.display_name for b in self.roster.bases]
        cities_items = [c.display_name for c in self.roster.cities]
        if hasattr(self, "dt_camp_combo") and camps_items:
            cur_idx = self.dt_camp_combo.current()
            self.dt_camp_combo["values"] = camps_items
            if 0 <= cur_idx < len(camps_items):
                self.dt_camp_combo.current(cur_idx)
                self._on_dt_camp_selected()
        if hasattr(self, "bm_city_combo"):
            mode = self.bm_mode_var.get() if hasattr(self, "bm_mode_var") else 1
            items = cities_items if (mode == 2 and cities_items) else camps_items
            if items:
                bm_idx = self.bm_city_combo.current()
                self.bm_city_combo["values"] = items
                if 0 <= bm_idx < len(items):
                    self.bm_city_combo.current(bm_idx)
                    self._on_bm_city_selected()
