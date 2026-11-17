"""Điểm khởi chạy Web Server (`linhvuong-web`) cho Ubuntu Server & Docker."""

import argparse
import os
import signal
import sys
from typing import Optional

import uvicorn

from ..paths import DataDirLockedError, get_data_dir
from ..runtime import WorkspaceManager
from ..security import WebAdminAuth, is_loopback_host
from .app import create_app


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="linhvuong-web",
        description="Khởi chạy Linh Vương Web Server & Bảng Điều Khiển Web.",
    )
    p.add_argument(
        "--host",
        default=os.environ.get("LINHVUONG_WEB_HOST") or "127.0.0.1",
        help="Địa chỉ IP lắng nghe (mặc định: 127.0.0.1; dùng 0.0.0.0 để mở truy cập mạng).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LINHVUONG_WEB_PORT") or "8000"),
        help="Cổng HTTP/WebSocket (mặc định: 8000).",
    )
    p.add_argument(
        "--data-dir",
        default=None,
        help="Thư mục lưu cấu hình, hồ sơ và logs (ưu tiên hơn LINHVUONG_DATA_DIR).",
    )
    p.add_argument(
        "--no-auth",
        action="store_true",
        help="Tắt xác thực Web Admin (chỉ có hiệu lực khi bind 127.0.0.1/localhost).",
    )
    p.add_argument(
        "--no-restore",
        action="store_true",
        help="Không tự động khôi phục đăng nhập từ Két Mật Khẩu Mã Hóa khi khởi động.",
    )
    return p


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: Optional[list[str]] = None) -> int:
    _ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    data_dir = get_data_dir(args.data_dir)

    if args.no_auth and not is_loopback_host(args.host):
        print(
            "⚠️  Cảnh báo bảo mật: Không thể tắt xác thực Phiên Quản Trị Web khi bind "
            f"ra địa chỉ mạng '{args.host}'. Xác thực vẫn được bật bắt buộc (ADR-0039).",
            file=sys.stderr,
        )

    try:
        workspace = WorkspaceManager(data_dir=data_dir, acquire_lock=True)
    except DataDirLockedError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    admin_auth = WebAdminAuth(
        data_dir=workspace.data_dir,
        host=args.host,
        allow_no_auth=bool(args.no_auth),
    )
    info = admin_auth.startup_info()

    print("============================================================")
    print(f"🌐 Linh Vương Web Dashboard: http://{args.host}:{args.port}")
    print(f"📁 Thư mục dữ liệu        : {workspace.data_dir.resolve()}")
    print(f"🔐 Két Mật Khẩu Mã Hóa    : {'Đã mở khóa' if workspace.vault.is_unlocked() else 'Chưa mở khóa (tùy chọn)'}")
    if info.auth_enabled:
        print(f"🛡️  Phiên Quản Trị Web     : Đã bật (Tài khoản: {info.username})")
        if info.generated_password:
            print(f"🔑 Mật khẩu khởi tạo lần đầu: {info.generated_password}")
            print("   (Hãy đổi mật khẩu ngay trên Web Dashboard hoặc đặt LINHVUONG_WEB_PASSWORD)")
    else:
        print("🔓 Phiên Quản Trị Web     : Đã tắt (Localhost only)")
    print("============================================================")

    app = create_app(
        workspace=workspace,
        auth=admin_auth,
        host=args.host,
        allow_no_auth=bool(args.no_auth),
        auto_restore=not args.no_restore,
    )

    def _handle_signal(signum, _frame):
        print(f"\n⏹️ Nhận tín hiệu {signum}, đang dừng an toàn toàn bộ bot...")
        workspace.graceful_shutdown()
        raise SystemExit(0)

    for sig in (signal.SIGINT, getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, _handle_signal)
            except Exception:
                pass

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        workspace.graceful_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
