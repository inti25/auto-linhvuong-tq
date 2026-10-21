import json
from unittest.mock import MagicMock, patch
import pytest

from linhvuong.cli import build_task, main
from linhvuong.gateway import GatewayClient
from linhvuong.locks import TargetLocks
from linhvuong.scan import Scanner
from linhvuong.tasks.base import TaskContext
from linhvuong.tasks.binh_man import BinhMan
from linhvuong.tasks.building import BuildingTask
from linhvuong.tasks.goi_dan import GoiDan
from linhvuong.tasks.logistics import LogisticsTask
from linhvuong.tasks.research import ResearchTask
from linhvuong.tasks.thao_phat import ThaoPhat


@pytest.fixture
def fake_ctx():
    gw = GatewayClient(57, MagicMock(), sleep=lambda s: None)
    locks = TargetLocks()
    scanner = Scanner(gw, locks, delay=0.0, sleep=lambda s: None)
    return TaskContext(gw, scanner, locks)


def test_build_task_returns_correct_types(fake_ctx):
    cfg = {
        "generals": [1, 2],
        "origin": [10, 20],
        "radius": 5,
        "city_id": 1001,
        "research_city_id": 1001,
        "transfer_orders": [{"from_city_id": 1001, "to_city_id": 1002, "army_id": 1, "amount": 500}],
    }

    t_gd = build_task("goi-dan", fake_ctx, cfg)
    assert isinstance(t_gd, GoiDan)

    t_bm = build_task("binh-man", fake_ctx, cfg)
    assert isinstance(t_bm, BinhMan)

    t_tp = build_task("thao-phat", fake_ctx, cfg)
    assert isinstance(t_tp, ThaoPhat)

    t_bld = build_task("build", fake_ctx, cfg)
    assert isinstance(t_bld, BuildingTask)

    t_res = build_task("research", fake_ctx, cfg)
    assert isinstance(t_res, ResearchTask)

    t_log = build_task("logistics", fake_ctx, cfg)
    assert isinstance(t_log, LogisticsTask)


def test_cli_main_once_mode(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "server": 57,
                "username": "user1",
                "password": "pwd",
                "city_id": 1001,
                "generals": [10],
                "origin": [0, 0],
                "radius": 5,
            }
        ),
        encoding="utf-8",
    )

    with patch("linhvuong.cli.login") as mock_login, patch(
        "linhvuong.tasks.building.BuildingTask.run_once", return_value="boost_activated"
    ) as mock_run:
        ret = main(["build", "--config", str(cfg_file), "--once"])
        assert ret == 0
        mock_login.assert_called_once()
        mock_run.assert_called_once()
