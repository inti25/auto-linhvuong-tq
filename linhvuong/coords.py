"""Chuyển đổi giữa tọa độ (x, y) và Mid (mã ô bản đồ) của Linh Vương."""

MAP_MIN = -656
MAP_MAX = 656
MAP_WIDTH = MAP_MAX - MAP_MIN + 1  # 1313
MID_ORIGIN = 861_985  # Mid của (0, 0)


def mid_from_coords(x: int, y: int) -> int:
    return (656 + int(x)) + (656 - int(y)) * MAP_WIDTH + 1


def coords_from_mid(mid: int) -> tuple[int, int]:
    idx = int(mid) - 1
    return (idx % MAP_WIDTH) - 656, 656 - (idx // MAP_WIDTH)

