"""CLI: linhvuong <task> --config config.json

Hỗ trợ đầy đủ các phân hệ tự động hóa:
- Chiến đấu & Thao phạt: thao-phat, binh-man, goi-dan
- Xây dựng & Đại học: build (xay-dung), research (dai-hoc)
- Hậu cần & Điều phối: logistics (hau-can)

Mật khẩu lấy từ biến môi trường LINHVUONG_PASSWORD (ưu tiên) hoặc trường "password" trong config.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

from .auth import LoginError, login
from .gateway import GatewayClient
from .locks import TargetLocks
from .logger import setup_logger
from .profile import Profile, ProfileStore
from .scan import Scanner
from .tasks.base import CaptchaRequired, TaskContext
from .tasks.binh_man import BinhMan
from .tasks.building import BuildingPlan, BuildingTask
from .tasks.goi_dan import GoiDan
from .tasks.logistics import ArmyTransferOrder, LogisticsTask
from .tasks.research import ResearchTask, TechPlan
from .tasks.thao_phat import ThaoPhat


def load_build_task(
    gateway: GatewayClient,
    cfg: dict,
    plan_path_arg: Optional[str] = None,
    profile: Optional[Profile] = None,
) -> BuildingTask:
    plan_path = plan_path_arg or cfg.get("build_plans_file")
    plans = []
    city_id = cfg.get("city_id", 0)
    auto_boost = cfg.get("auto_boost", False)
    auto_speedup = cfg.get("auto_speedup", False)
    auto_comfort = cfg.get("auto_comfort", True)
    auto_open_box = cfg.get("auto_open_box", False)
    even_upgrade = cfg.get("even_upgrade", False)
    max_slots = cfg.get("max_slots", 3)

    if profile and profile.building:
        b_prof = profile.building
        max_slots = b_prof.slots
        auto_boost = b_prof.auto_boost
        auto_speedup = b_prof.auto_speedup
        auto_comfort = b_prof.auto_comfort
        auto_open_box = b_prof.auto_open_box
        even_upgrade = b_prof.even_upgrade

        target_cid_str = str(city_id) if city_id else ""
        if target_cid_str and target_cid_str in b_prof.cities:
            cdata = b_prof.cities[target_cid_str]
            for p in cdata.plans:
                plans.append(
                    BuildingPlan(
                        pid=int(p["pid"]),
                        gid=int(p["gid"]),
                        target_level=int(p["target_level"]),
                        name=p.get("name", ""),
                    )
                )
        elif b_prof.cities:
            for cid_str, cdata in b_prof.cities.items():
                if cdata.enabled and cdata.plans:
                    city_id = int(cid_str)
                    for p in cdata.plans:
                        plans.append(
                            BuildingPlan(
                                pid=int(p["pid"]),
                                gid=int(p["gid"]),
                                target_level=int(p["target_level"]),
                                name=p.get("name", ""),
                            )
                        )
                    break
        elif b_prof.plans:
            for p in b_prof.plans:
                plans.append(
                    BuildingPlan(
                        pid=int(p["pid"]),
                        gid=int(p["gid"]),
                        target_level=int(p["target_level"]),
                        name=p.get("name", ""),
                    )
                )

    if not plans:
        if not plan_path:
            for candidate in ("build_plans.json", "build_plans.example.json"):
                if Path(candidate).exists():
                    plan_path = candidate
                    break

        if plan_path and Path(plan_path).exists():
            with open(plan_path, encoding="utf-8") as f:
                data = json.load(f)
            cities = data.get("cities", {})
            target_cid_str = str(city_id) if city_id else ""
            if target_cid_str and target_cid_str in cities:
                cdata = cities[target_cid_str]
                for p in cdata.get("plans", []):
                    plans.append(
                        BuildingPlan(
                            pid=int(p["pid"]),
                            gid=int(p["gid"]),
                            target_level=int(p["target_level"]),
                            name=p.get("name", ""),
                        )
                    )
            elif cities:
                first_cid, cdata = next(iter(cities.items()))
                city_id = int(first_cid)
                for p in cdata.get("plans", []):
                    plans.append(
                        BuildingPlan(
                            pid=int(p["pid"]),
                            gid=int(p["gid"]),
                            target_level=int(p["target_level"]),
                            name=p.get("name", ""),
                        )
                    )

    return BuildingTask(
        gateway=gateway,
        city_id=city_id,
        plans=plans,
        max_slots=max_slots,
        auto_speedup=auto_speedup,
        paytype=cfg.get("paytype", 1),
        auto_comfort=auto_comfort,
        auto_boost=auto_boost,
        auto_open_box=auto_open_box,
        even_upgrade=even_upgrade,
    )


def load_research_task(
    gateway: GatewayClient,
    cfg: dict,
    plan_path_arg: Optional[str] = None,
    profile: Optional[Profile] = None,
) -> ResearchTask:
    plan_path = plan_path_arg or cfg.get("tech_plans_file")
    plans = []
    city_id = cfg.get("research_city_id", cfg.get("city_id", 0))
    auto_art = cfg.get("auto_art_of_war", False)
    even_research = cfg.get("even_research", False)

    if profile and profile.research:
        r_prof = profile.research
        auto_art = r_prof.art_speedup
        even_research = r_prof.even_research
        if r_prof.city_id:
            city_id = r_prof.city_id
        for p in r_prof.techs:
            if p.get("enabled", True):
                plans.append(
                    TechPlan(
                        tech_id=int(p.get("id") or p.get("tech_id", 1)),
                        target_level=int(p.get("target_level", 20)),
                        name=p.get("name", ""),
                    )
                )

    if not plans:
        if not plan_path:
            for candidate in ("tech_plans.json", "tech_plans.example.json"):
                if Path(candidate).exists():
                    plan_path = candidate
                    break

        if plan_path and Path(plan_path).exists():
            with open(plan_path, encoding="utf-8") as f:
                data = json.load(f)
            city_id = data.get("research_city_id", city_id)
            auto_art = data.get("auto_art_of_war", auto_art)
            for p in data.get("plans", []):
                plans.append(
                    TechPlan(
                        tech_id=int(p["tech_id"]),
                        target_level=int(p["target_level"]),
                        name=p.get("name", ""),
                    )
                )

    return ResearchTask(
        gateway=gateway,
        city_id=city_id,
        plans=plans,
        auto_art_of_war=auto_art,
        even_research=even_research,
    )


def load_logistics_task(gateway: GatewayClient, cfg: dict) -> LogisticsTask:
    transfers = []
    for t in cfg.get("transfer_orders", []):
        transfers.append(
            ArmyTransferOrder(
                from_city_id=int(t["from_city_id"]),
                to_city_id=int(t["to_city_id"]),
                army_id=int(t["army_id"]),
                amount=int(t["amount"]),
            )
        )
    return LogisticsTask(
        gateway=gateway,
        transfer_orders=transfers,
        monitored_city_ids=cfg.get("monitored_city_ids", []),
        auto_comfort=cfg.get("auto_comfort", True),
        auto_daily_reward=cfg.get("auto_daily_reward", True),
    )


def build_task(
    name: str,
    ctx: TaskContext,
    cfg: dict,
    build_plans_path: Optional[str] = None,
    tech_plans_path: Optional[str] = None,
    profile: Optional[Profile] = None,
):
    if name in ("build", "xay-dung"):
        return load_build_task(ctx.gateway, cfg, build_plans_path, profile=profile)

    if name in ("research", "dai-hoc"):
        return load_research_task(ctx.gateway, cfg, tech_plans_path, profile=profile)

    if name in ("logistics", "hau-can"):
        return load_logistics_task(ctx.gateway, cfg)

    common = dict(
        generals=cfg.get("generals", []),
        origin=tuple(cfg.get("origin", (0, 0))),
        radius=cfg.get("radius", 5),
    )
    skip = cfg.get("skip_capital_radius", 0)

    if name == "goi-dan":
        return GoiDan(
            ctx,
            skip_capital_radius=skip,
            mode=cfg.get("mode", "dan"),
            city_id=cfg.get("city_id", 0),
            auto_recover=cfg.get("auto_recover", False),
            refill_amount=cfg.get("refill_amount", 500),
            **common,
        )

    types = cfg.get("man_types", [7])
    if name == "binh-man":
        return BinhMan(
            ctx,
            man_types=types,
            return_threshold=cfg.get("return_threshold", 0),
            skip_capital_radius=skip,
            parent_city_id=cfg.get("parent_city_id") or cfg.get("base_city_id"),
            camp_id=cfg.get("camp_id"),
            max_step=cfg.get("max_step", 2),
            auto_recover=cfg.get("auto_recover", False),
            **common,
        )

    return ThaoPhat(ctx, man_types=types, **common)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="linhvuong")
    ap.add_argument(
        "task",
        choices=[
            "goi-dan",
            "binh-man",
            "thao-phat",
            "build",
            "xay-dung",
            "research",
            "dai-hoc",
            "logistics",
            "hau-can",
        ],
        help="Nhiệm vụ cần thực hiện",
    )
    ap.add_argument("--config", default="config.json", help="File cấu hình chính")
    ap.add_argument("--profile", default=None, help="Hồ Sơ Cấu Hình tổng hợp (auto_profile.json)")
    ap.add_argument("--build-plans", default=None, help="File cấu hình quy hoạch xây dựng (build_plans.json)")
    ap.add_argument("--tech-plans", default=None, help="File cấu hình quy hoạch đại học (tech_plans.json)")
    ap.add_argument("--once", action="store_true", help="Chỉ chạy 1 lượt rồi thoát")
    ap.add_argument("--proxy", default=None, help="Proxy URL (http://, https://, socks5://)")
    ap.add_argument("--proxy-user", default=None, help="Tài khoản xác thực proxy (tùy chọn)")
    ap.add_argument("--proxy-pass", default=None, help="Mật khẩu xác thực proxy (tùy chọn)")
    ap.add_argument("--debug", "-v", action="store_true", help="Bật chế độ ghi log chi tiết (DEBUG)")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)

    username = cfg.get("username", "guest")
    server_id = cfg.get("server", 0)
    setup_logger(username=username, server_id=server_id, debug=args.debug, console=True)
    logger = logging.getLogger(f"linhvuong.cli.{args.task}")

    # Nạp Hồ Sơ Cấu Hình tổng hợp nếu có (ADR-0006 & ADR-0021)
    profile = None
    prof_path = None
    if args.profile:
        prof_path = Path(args.profile)
    else:
        candidate_prof = ProfileStore.resolve_profile_path(username=username, server_id=server_id)
        if candidate_prof.exists():
            prof_path = candidate_prof

    if prof_path and prof_path.exists():
        try:
            profile = ProfileStore.load(prof_path)
            logger.info(f"📂 Đã nạp Hồ Sơ Cấu Hình: {prof_path.name}")
        except Exception as e:
            logger.warning(f"Không thể nạp hồ sơ cấu hình {prof_path}: {e}")

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
        logger.error(f"Đăng nhập thất bại: {e}")
        raise SystemExit(str(e))

    def auto_relogin() -> bool:
        try:
            logger.info(
                f"Đang tự động đăng nhập lại tài khoản {cfg['username']} (Server {cfg['server']})..."
            )
            login(
                session,
                cfg["server"],
                cfg["username"],
                password,
                proxy=proxy,
                proxy_user=proxy_user,
                proxy_pass=proxy_pass,
            )
            return True
        except Exception as ex:
            logger.error(f"Tự động đăng nhập lại thất bại: {ex}")
            return False

    gateway = GatewayClient(cfg["server"], session, relogin_callback=auto_relogin)
    locks = TargetLocks()
    scanner = Scanner(
        gateway, locks, delay=cfg.get("scan_delay", 0.2), step=cfg.get("scan_step", 5)
    )
    ctx = TaskContext(gateway, scanner, locks)
    task = build_task(args.task, ctx, cfg, args.build_plans, args.tech_plans, profile=profile)

    try:
        while True:
            res = task.run_once()
            logger.info(f"{args.task} -> {res}")
            if args.once:
                break
            time.sleep(cfg.get("loop_interval", 5))
    except CaptchaRequired:
        logger.warning("⚠️ Server yêu cầu Captcha! Dừng tác vụ.")
        return 2
    except KeyboardInterrupt:
        logger.info("Người dùng dừng tác vụ qua bàn phím.")
        scanner.stop()
        return 0
    except Exception as e:
        logger.exception(f"Lỗi ngoại lệ trong tác vụ CLI {args.task}: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
