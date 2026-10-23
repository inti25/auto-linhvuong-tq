"""Các nhiệm vụ tự động: Gọi Dân, Bình Man, Thảo Phạt, Xây Dựng, Nghiên Cứu, Hậu Cần."""

from .binh_man import BinhMan
from .building import BuildingPlan, BuildingTask
from .di_trai import DiTrai
from .goi_dan import GoiDan
from .logistics import ArmyTransferOrder, LogisticsTask
from .research import ResearchTask, TechPlan
from .thao_phat import ThaoPhat

__all__ = [
    "BinhMan",
    "BuildingPlan",
    "BuildingTask",
    "DiTrai",
    "GoiDan",
    "ArmyTransferOrder",
    "LogisticsTask",
    "ResearchTask",
    "TechPlan",
    "ThaoPhat",
]

