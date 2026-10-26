import pytest

from linhvuong.coords import coords_from_mid, mid_from_coords


def test_top_left_corner_is_mid_1():
    assert mid_from_coords(-656, 656) == 1


def test_origin_is_mid_861985():
    assert mid_from_coords(0, 0) == 861_985


def test_bottom_right_corner_is_last_mid():
    assert mid_from_coords(656, -656) == 1_723_969


def test_live_point_270_208_is_mid_589151():
    assert mid_from_coords(270, 208) == 589_151


@pytest.mark.parametrize(
    "mid,expected",
    [
        (1, (-656, 656)),
        (861_985, (0, 0)),
        (1_723_969, (656, -656)),
        (589_151, (270, 208)),
        (661_415, (319, 153)),
    ],
)
def test_mid_decodes_to_known_coords(mid, expected):
    assert coords_from_mid(mid) == expected


def test_roundtrip_for_sample_points():
    for x, y in [(-12, 40), (300, -500), (656, -656), (-656, 656), (270, 208), (319, 153)]:
        assert coords_from_mid(mid_from_coords(x, y)) == (x, y)

