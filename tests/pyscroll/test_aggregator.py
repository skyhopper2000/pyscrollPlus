from __future__ import annotations

import pygame
import pytest
from synthetic_map import SyntheticMapData

from pyscroll.data import MapAggregator
from pyscroll.orthographic import BufferedRenderer


def make_map(size=(4, 4), shade=0):
    data = SyntheticMapData(size=size)
    # give each sub-map its own palette so their tiles are distinguishable
    data.color_funcs = {
        0: lambda x, y: (20 + x * 7, 20 + y * 7, 60 + shade),
        1: lambda x, y: (230, 20 + x * 7, 20 + y * 7 + shade),
    }
    data.reload_data()
    return data


@pytest.fixture
def agg(display):
    return MapAggregator((8, 8))


def rects(aggregator):
    return [rect for _, rect in aggregator.maps]


def test_empty_aggregator(agg):
    assert agg.map_size == (0, 0)
    assert agg.visible_tile_layers == []
    assert list(agg.get_tile_images_by_rect((0, 0, 10, 10))) == []


def test_single_map_at_origin(agg):
    agg.add_map(make_map(), (0, 0))
    assert agg.map_size == (4, 4)
    assert rects(agg) == [pygame.Rect(0, 0, 4, 4)]


def test_single_map_positive_offset(agg):
    agg.add_map(make_map(), (2, 3))
    assert agg.map_size == (6, 7)
    assert rects(agg) == [pygame.Rect(2, 3, 4, 4)]


def test_second_map_positive_offset_grows_map(agg):
    agg.add_map(make_map(), (0, 0))
    agg.add_map(make_map(), (4, 2))
    assert agg.map_size == (8, 6)
    assert rects(agg) == [pygame.Rect(0, 0, 4, 4), pygame.Rect(4, 2, 4, 4)]


def test_negative_offset_shifts_existing_maps(agg):
    agg.add_map(make_map(), (0, 0))
    agg.add_map(make_map(), (-2, -3))
    # everything is moved so that tile coordinates stay >= 0
    assert rects(agg) == [pygame.Rect(2, 3, 4, 4), pygame.Rect(0, 0, 4, 4)]
    assert agg.map_size == (6, 7)


def test_negative_then_positive_offsets(agg):
    agg.add_map(make_map(), (0, 0))
    agg.add_map(make_map(), (-4, -4))
    agg.add_map(make_map(), (4, 4))  # in the original coordinate system
    assert rects(agg) == [
        pygame.Rect(4, 4, 4, 4),
        pygame.Rect(0, 0, 4, 4),
        pygame.Rect(8, 8, 4, 4),
    ]
    assert agg.map_size == (12, 12)


def test_tile_size_mismatch_rejected(agg):
    with pytest.raises(AssertionError):
        agg.add_map(SyntheticMapData(tile_size=(16, 16)), (0, 0))


def test_visible_tile_layers_is_union(agg):
    agg.add_map(SyntheticMapData(visible_layers=(0,)), (0, 0))
    agg.add_map(SyntheticMapData(visible_layers=(1,)), (4, 0))
    assert agg.visible_tile_layers == [0, 1]


def test_get_tile_images_by_rect_applies_offsets(agg):
    a, b = make_map(shade=0), make_map(shade=100)
    agg.add_map(a, (0, 0))
    agg.add_map(b, (-4, -4))  # a -> (4, 4), b -> (0, 0)

    tiles = {(x, y, l): image for x, y, l, image in agg.get_tile_images_by_rect((0, 0, 8, 8))}
    # 16 layer-0 + 4 diagonal layer-1 tiles per map
    assert len(tiles) == 2 * (16 + 4)
    assert tiles[(4, 4, 0)] is a.images[a._gid(0, 0, 0)]
    assert tiles[(7, 6, 0)] is a.images[a._gid(3, 2, 0)]
    assert tiles[(5, 5, 1)] is a.images[a._gid(1, 1, 1)]
    assert tiles[(0, 0, 0)] is b.images[b._gid(0, 0, 0)]
    assert tiles[(3, 3, 1)] is b.images[b._gid(3, 3, 1)]
    # gap between the maps is empty
    assert (0, 5, 0) not in tiles and (5, 0, 0) not in tiles


def test_get_tile_images_by_rect_clips_to_view(agg):
    a, b = make_map(shade=0), make_map(shade=100)
    agg.add_map(a, (0, 0))
    agg.add_map(b, (-4, -4))
    tiles = {(x, y, l) for x, y, l, _ in agg.get_tile_images_by_rect((3, 3, 2, 2))}
    # tiles (3..4, 3..4): (3, 3) belongs to b, (4, 4) to a, the rest is gap
    assert tiles == {(3, 3, 0), (3, 3, 1), (4, 4, 0), (4, 4, 1)}


def test_renderer_draws_aggregated_maps(agg):
    a, b = make_map(shade=0), make_map(shade=100)
    agg.add_map(a, (0, 0))
    agg.add_map(b, (-4, -4))
    r = BufferedRenderer(agg, (64, 64))
    r.center((32, 32))
    surface = pygame.Surface((64, 64))
    r.draw(surface, surface.get_rect())

    def color(px):
        return tuple(surface.get_at(px))[:3]

    # b at tiles (0..3, 0..3), a at tiles (4..7, 4..7)
    assert color((1, 1)) == b.expected_world_color(1, 1)
    assert color((9, 1)) == b.expected_world_color(9, 1)
    assert color((33, 33)) == a.expected_world_color(1, 1)
    assert color((60, 41)) == a.expected_world_color(60 - 32, 41 - 32)
    assert color((40, 4)) == (0, 0, 0)  # gap
    assert color((4, 40)) == (0, 0, 0)  # gap
