import os
import sys
import tkinter as tk
from pathlib import Path
import pytest

from linhvuong.gui import MultiAccountApp, load_coffee_qr_image

try:
    import _tkinter
except ImportError:
    _tkinter = None


def test_qr_code_spec_configuration():
    """Kiểm tra file cấu hình build PyInstaller (LinhVuong.spec và command.md) phải bao gồm mã QR."""
    spec_path = Path("LinhVuong.spec")
    assert spec_path.is_file(), "LinhVuong.spec không tồn tại"
    spec_content = spec_path.read_text(encoding="utf-8")

    # Mã QR phải được thêm vào danh sách datas trong spec
    assert any(qr_file in spec_content for qr_file in ["qrcode.png", "qrcode.webp"]), (
        "LinhVuong.spec chưa thêm file qrcode vào datas"
    )

    cmd_path = Path("command.md")
    if cmd_path.is_file():
        cmd_content = cmd_path.read_text(encoding="utf-8")
        assert any(qr_file in cmd_content for qr_file in ["qrcode.png", "qrcode.webp"]), (
            "command.md chưa có --add-data cho file qrcode"
        )


def test_qr_code_loads_in_frozen_exe_environment(tmp_path, monkeypatch):
    """Mô phỏng môi trường sau khi build EXE (sys.frozen=True, sys._MEIPASS)."""
    if _tkinter is None:
        pytest.skip("tkinter not available")

    # Khởi tạo Tk root trước khi monkeypatch sys.frozen để tránh TclError trong môi trường test
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display error: {e}")

    try:
        fake_meipass = tmp_path / "_MEI_test"
        fake_meipass.mkdir()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

        # Đọc cấu hình datas từ LinhVuong.spec để copy các file được bundle vào fake_meipass
        spec_content = Path("LinhVuong.spec").read_text(encoding="utf-8")
        for f in ["linhvuong.ico", "linhvuong.png", "linhvuong_menu.png", "qrcode.webp", "qrcode.png"]:
            if f in spec_content and Path(f).is_file():
                (fake_meipass / f).write_bytes(Path(f).read_bytes())

        # Nếu LinhVuong.spec exclude PIL/Pillow thì giả lập môi trường không thể import PIL
        if "'PIL'" in spec_content or '"PIL"' in spec_content:
            monkeypatch.setitem(sys.modules, "PIL", None)
            monkeypatch.setitem(sys.modules, "PIL.Image", None)
            monkeypatch.setitem(sys.modules, "PIL.ImageTk", None)

        qr_photo = load_coffee_qr_image(300, 400)
        assert qr_photo is not None, "load_coffee_qr_image trả về None trong môi trường EXE đã build"
    finally:
        root.destroy()


def test_coffee_dialog_has_no_error_label_in_frozen_mode(tmp_path, monkeypatch):
    """Kiểm tra khi mở dialog Buy me a coffee trong môi trường EXE đã build, không bị lỗi thiếu QR."""
    if _tkinter is None:
        pytest.skip("tkinter not available")

    settings_file = tmp_path / "gui_settings.json"
    monkeypatch.setattr("linhvuong.gui.SETTINGS", settings_file)

    try:
        app = MultiAccountApp()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter display error: {e}")

    try:
        fake_meipass = tmp_path / "_MEI_test"
        fake_meipass.mkdir()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

        spec_content = Path("LinhVuong.spec").read_text(encoding="utf-8")
        for f in ["linhvuong.ico", "linhvuong.png", "linhvuong_menu.png", "qrcode.webp", "qrcode.png"]:
            if f in spec_content and Path(f).is_file():
                (fake_meipass / f).write_bytes(Path(f).read_bytes())

        if "'PIL'" in spec_content or '"PIL"' in spec_content:
            monkeypatch.setitem(sys.modules, "PIL", None)
            monkeypatch.setitem(sys.modules, "PIL.Image", None)
            monkeypatch.setitem(sys.modules, "PIL.ImageTk", None)

        app._show_coffee_dialog()
        toplevels = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
        assert len(toplevels) == 1
        dlg = toplevels[0]

        # Lấy text tất cả nhãn trong dialog
        labels = []
        for w in dlg.winfo_children():
            if isinstance(w, tk.Label):
                labels.append(w.cget("text"))
            if hasattr(w, "winfo_children"):
                for child in w.winfo_children():
                    if isinstance(child, tk.Label):
                        labels.append(child.cget("text"))

        assert not any("Không tìm thấy tệp mã QR" in txt for txt in labels), (
            "Dialog hiển thị lỗi 'Không tìm thấy tệp mã QR' do QR không load được"
        )
    finally:
        app.destroy()
