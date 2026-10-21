"""CLI: linhvuong <goi-dan|binh-man|thao-phat> --config config.json

Mật khẩu lấy từ biến môi trường LINHVUONG_PASSWORD (ưu tiên) hoặc trường "password" trong config.
Đăng nhập theo báo cáo ZMan (pass.dipan.com/aspx/LoginAPI.aspx); chưa kiểm chứng trên server thật.
"""

import argparse
import json
import os
import sys
import time

import requests

from .auth import LoginError, login
from .gateway import GatewayClient
from .locks import TargetLocks
from .scan import Scanner
from .tasks.base import CaptchaRequired, TaskContext
from .tasks.binh_man import BinhMan
from .tasks.goi_dan import GoiDan
from .tasks.thao_phat import ThaoPhat


def build_task(name: str, ctx: TaskContext, cfg: dict):
    common = dict(generals=cfg["generals"], origin=tuple(cfg["origin"]), radius=cfg["radius"])
    skip = cfg.get("skip_capital_radius", 0)
    if name == "goi-dan":
        return GoiDan(ctx, skip_capital_radius=skip, **common)
    types = cfg.get("man_types", [7])
    if name == "binh-man":
        return BinhMan(
            ctx,
            man_types=types,
            return_threshold=cfg.get("return_threshold", 0),
            skip_capital_radius=skip,
            **common,
        )
    return ThaoPhat(ctx, man_types=types, **common)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="linhvuong")
    ap.add_argument("task", choices=["goi-dan", "binh-man", "thao-phat"])
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--proxy", default=None, help="Proxy URL (http://, https://, socks5://)")
    ap.add_argument("--proxy-user", default=None, help="Tài khoản xác thực proxy (tùy chọn)")
    ap.add_argument("--proxy-pass", default=None, help="Mật khẩu xác thực proxy (tùy chọn)")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    password = os.environ.get("LINHVUONG_PASSWORD") or cfg.get("password")
    if not password:
        raise SystemExit("Thiếu mật khẩu (LINHVUONG_PASSWORD hoặc config).")

    proxy = args.proxy or cfg.get("proxy")
    proxy_user = args.proxy_user or cfg.get("proxy_user")
    proxy_pass = args.proxy_pass or cfg.get("proxy_pass")
    session = requests.Session()
    try:
        login(
            session,
            cfg["server"],
            cfg["username"],
            password,
            proxy=proxy,
            proxy_user=proxy_user,
            proxy_pass=proxy_pass,
        )
    except (LoginError, ValueError) as e:
        raise SystemExit(str(e))
    gateway = GatewayClient(cfg["server"], session)
    locks = TargetLocks()
    scanner = Scanner(
        gateway, locks, delay=cfg.get("scan_delay", 0.2), step=cfg.get("scan_step", 5)
    )
    ctx = TaskContext(gateway, scanner, locks)
    task = build_task(args.task, ctx, cfg)

    try:
        while True:
            print(args.task, "->", task.run_once())
            time.sleep(cfg.get("loop_interval", 5))
    except CaptchaRequired:
        return 2
    except KeyboardInterrupt:
        scanner.stop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
