"""Thành phần giao diện dùng chung, bảng màu và helper điều phối cho Dashboard."""

import sys
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional, Union

from ..battle import parse_attack_action_combo

BG, CARD, FG, MUTED, ACCENT, SUCCESS, DANGER = (
    "#14161f",
    "#1e2130",
    "#e8eaf2",
    "#8a90b0",
    "#6c7bff",
    "#28a745",
    "#dc3545",
)
ROLE_TEXT = {"van": "Văn quan", "vo": "Võ tướng"}

# Cấu hình Cắt Tỉa Nhật Ký Giao Diện (ADR-0030)
DEFAULT_MAX_LOG_LINES = 500  # Ngưỡng dòng tối đa cho các tab tác vụ thông thường
BATCH_TRIM_LINES = 100  # Số dòng cắt tỉa theo khối khi chạm ngưỡng
COMBAT_MAX_LOG_LINES = 300  # Ngưỡng dòng tối đa cho tab Chiến Trường
COMBAT_TRIM_LINES = 60  # Số dòng cắt tỉa theo khối cho tab Chiến Trường


def resolve_dashboard_symbol(name: str, default: Any) -> Any:
    """Truy xuất phụ thuộc qua namespace `linhvuong.dashboard` để giữ tương thích mock/patch."""
    pkg = sys.modules.get("linhvuong.dashboard")
    if pkg is not None and hasattr(pkg, name):
        return getattr(pkg, name)
    return default


def sync_action_mode_from_combo(var: tk.StringVar, combo: ttk.Combobox) -> str:
    """Đồng bộ attack_action_mode từ giá trị đang chọn trên combobox Chiêu tấn công."""
    mode_str, _ = parse_attack_action_combo(combo.get())
    var.set(mode_str)
    return mode_str


def apply_action_mode_widgets(
    var: Optional[tk.StringVar],
    combo: Optional[ttk.Combobox],
    action_mode: Optional[str] = None,
    combo_idx: Optional[int] = None,
) -> None:
    """Khôi phục combobox và StringVar Chiêu tấn công an toàn theo biên."""
    if combo is not None and combo_idx is not None:
        try:
            vals = list(combo["values"])
            idx = int(combo_idx)
            if 0 <= idx < len(vals):
                combo.current(idx)
            elif vals:
                combo.current(0)
        except (ValueError, TypeError, tk.TclError):
            pass
    if var is not None and action_mode is not None:
        var.set(str(action_mode))


class MultiSelectDropdown(ttk.Menubutton):
    """Dropdown chọn nhiều lựa chọn với checkboxes trong tk.Menu."""

    def __init__(
        self,
        parent,
        options: list[tuple[int, str]],
        default_selected: Optional[list[int]] = None,
        width: int = 22,
        command: Optional[Callable[[list[int]], None]] = None,
        categories: Optional[dict[str, list[int]]] = None,
        **kwargs,
    ):
        super().__init__(parent, width=width, **kwargs)
        self.options = list(options)
        self.command = command
        self.categories = categories
        default_set = set(default_selected if default_selected is not None else [opt[0] for opt in self.options])
        self.vars: dict[int, tk.BooleanVar] = {
            val: tk.BooleanVar(value=(val in default_set)) for val, _ in self.options
        }

        self.menu = tk.Menu(self, tearoff=False)
        self["menu"] = self.menu

        self.menu.add_command(label="✅ Chọn tất cả", command=self.select_all)
        self.menu.add_command(label="❌ Bỏ chọn tất cả", command=self.deselect_all)
        self.menu.add_separator()

        if categories:
            opt_map = dict(self.options)
            for cat_name, item_ids in categories.items():
                sub = tk.Menu(self.menu, tearoff=False)

                def _make_cat_toggle(ids, select: bool):
                    def _fn():
                        for iid in ids:
                            if iid in self.vars:
                                self.vars[iid].set(select)
                        self._on_toggle()
                    return _fn

                sub.add_command(label=f"✅ Chọn tất cả ({len(item_ids)})", command=_make_cat_toggle(item_ids, True))
                sub.add_command(label="❌ Bỏ chọn nhóm", command=_make_cat_toggle(item_ids, False))
                sub.add_separator()

                for val in item_ids:
                    if val in opt_map:
                        sub.add_checkbutton(
                            label=opt_map[val],
                            variable=self.vars[val],
                            onvalue=True,
                            offvalue=False,
                            command=self._on_toggle,
                        )
                self.menu.add_cascade(label=f"{cat_name} ({len(item_ids)}) ‣", menu=sub)
        else:
            for val, label in self.options:
                self.menu.add_checkbutton(
                    label=label,
                    variable=self.vars[val],
                    onvalue=True,
                    offvalue=False,
                    command=self._on_toggle,
                )

        self._update_label()

    def _update_label(self) -> None:
        selected = self.get_selected()
        total = len(self.options)
        if len(selected) == total:
            self.config(text=f"Tất cả ({total}) ▾")
        elif not selected:
            self.config(text="Chưa chọn ▾")
        elif len(selected) <= 2:
            labels = []
            opt_map = dict(self.options)
            for val in selected:
                raw_lbl = opt_map.get(val, str(val))
                if " - " in raw_lbl:
                    labels.append(raw_lbl.split(" - ")[0])
                elif " (" in raw_lbl:
                    cleaned = raw_lbl.split(" (")[0]
                    if ". " in cleaned:
                        cleaned = cleaned.split(". ", 1)[-1]
                    labels.append(cleaned)
                else:
                    labels.append(raw_lbl)
            self.config(text=f"{', '.join(labels)} ▾")
        else:
            self.config(text=f"Đã chọn {len(selected)} loại ▾")

    def _on_toggle(self) -> None:
        self._update_label()
        if self.command:
            self.command(self.get_selected())

    def get_selected(self) -> list[int]:
        return [val for val, _ in self.options if self.vars[val].get()]

    def get_selected_str(self) -> str:
        return ",".join(str(x) for x in self.get_selected())

    def set_selected(self, values: Union[list[int], set[int], tuple[int, ...]]) -> None:
        val_set = {int(x) for x in values if str(x).isdigit()}
        for val, var in self.vars.items():
            var.set(val in val_set)
        self._update_label()
        if self.command:
            self.command(self.get_selected())

    def set_selected_str(self, s: str) -> None:
        if not s:
            self.deselect_all()
            return
        vals = []
        for x in str(s).split(","):
            try:
                vals.append(int(x.strip()))
            except ValueError:
                pass
        self.set_selected(vals)

    def select_all(self) -> None:
        for var in self.vars.values():
            var.set(True)
        self._update_label()
        if self.command:
            self.command(self.get_selected())

    def deselect_all(self) -> None:
        for var in self.vars.values():
            var.set(False)
        self._update_label()
        if self.command:
            self.command(self.get_selected())


class _LegacyComboAdapter:
    """Bộ chuyển đổi tương thích ngược cho code cũ hoặc test truy cập combobox."""

    def __init__(self, dropdown: MultiSelectDropdown):
        self._dropdown = dropdown
        self.values = [lbl for _, lbl in dropdown.options]

    def current(self, idx: Optional[int] = None):
        if idx is None:
            sel = self._dropdown.get_selected()
            if not sel:
                return 0
            for i, (val, _) in enumerate(self._dropdown.options):
                if val == sel[0]:
                    return i
            return 0
        if 0 <= idx < len(self._dropdown.options):
            val = self._dropdown.options[idx][0]
            self._dropdown.set_selected([val])

    def get(self) -> str:
        sel = self._dropdown.get_selected()
        if not sel:
            return ""
        opt_dict = dict(self._dropdown.options)
        return opt_dict.get(sel[0], str(sel[0]))

    def bind(self, sequence, func, add=None):
        pass

    def __getitem__(self, item):
        if item == "values":
            return self.values
        return None

    def __setitem__(self, item, val):
        if item == "values":
            self.values = val
