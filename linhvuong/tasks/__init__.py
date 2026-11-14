"""Các nhiệm vụ tự động: Gọi Dân, Bình Man, Thảo Phạt, Xây Dựng, Nghiên Cứu, Hậu Cần."""

from .binh_man import MAN_TARGET_OPTIONS, MODE_CAMP, MODE_CITY, BinhMan
from .building import BuildingPlan, BuildingTask
from .di_trai import DiTrai
from .goi_dan import GoiDan, GoiMan
from .logistics import ArmyTransferOrder, LogisticsTask
from .nien_thu import NienThuTask
from .research import ResearchTask, TechPlan
from .thao_phat import ThaoPhat

__all__ = [
    "BinhMan",
    "MAN_TARGET_OPTIONS",
    "MODE_CAMP",
    "MODE_CITY",
    "BuildingPlan",
    "BuildingTask",
    "DiTrai",
    "GoiDan",
    "GoiMan",
    "ArmyTransferOrder",
    "LogisticsTask",
    "ResearchTask",
    "TechPlan",
    "ThaoPhat",
]

