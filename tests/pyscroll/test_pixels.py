"""
Pixel-exact ("golden") rendering tests on the synthetic map.

Expected colours are computed analytically from the tile layout
(see synthetic_map.SyntheticMapData.expected_world_color), so there are
no reference images to keep in sync.
"""

from __future__ import annotations

import pygame
import pytest
from synthetic_map import (
    CLEAR,
    SyntheticMapData,
    diff,
    expected_screen,
    layer0_color,
    layer1_color,
    screen_colors,
)

from pyscroll.group import PyscrollGroup


def render(renderer, size, fill=CLEAR):
    surface = pygame.Surface(size)
    surface.fill(fill)
    renderer.draw(surface, surface.get_rect())
    return surface


def assert_matches(surface, data, view_rect, scale=1):
    actual = screen_colors(surface)
    expected = expected_screen(data, view_rect, surface.get_size(), scale)
    assert actual == expected, diff(actual, expected)


# ----------------------------------------------------------------------
# map only


def test_whole_tiny_map_fits_view(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (32, 32))
    r.center((16, 16))
    surface = render(r, (32, 32))
    # spot checks, computed by hand
    assert tuple(surface.get_at((0, 0)))[:3] == layer1_color(0, 0)  # diagonal
    assert tuple(surface.get_at((8, 0)))[:3] == layer0_color(1, 0)
    assert tuple(surface.get_at((31, 0)))[:3] == layer0_color(3, 0)
    assert tuple(surface.get_at((31, 31)))[:3] == layer1_color(3, 3)
    assert tuple(surface.get_at((12, 20)))[:3] == layer0_color(1, 2)
    assert_matches(surface, tiny_map, r.view_rect)


@pytest.mark.parametrize("center", [(8, 8), (12, 20), (9, 15), (24, 24)])
def test_partial_view_of_tiny_map(tiny_map, make_renderer, center):
    r = make_renderer(tiny_map, (16, 16))
    r.center(center)
    assert r.view_rect.center == center
    assert_matches(render(r, (16, 16)), tiny_map, r.view_rect)


def test_clamped_view_at_corner(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (16, 16))
    r.center((0, 0))
    assert r.view_rect.topleft == (0, 0)
    surface = render(r, (16, 16))
    assert tuple(surface.get_at((0, 0)))[:3] == layer1_color(0, 0)
    assert tuple(surface.get_at((15, 0)))[:3] == layer0_color(1, 0)
    assert_matches(surface, tiny_map, r.view_rect)


@pytest.mark.parametrize("center", [(0, 0), (-4, 20), (16, 16), (4, -6)])
def test_unclamped_view_shows_clear_color_past_edges(tiny_map, make_renderer, center):
    r = make_renderer(tiny_map, (16, 16), clamp_camera=False)
    r.center(center)
    assert r.view_rect.center == center
    assert_matches(render(r, (16, 16)), tiny_map, r.view_rect)


@pytest.mark.parametrize("center", [(32, 32), (36, 10), (10, 36)])
def test_unclamped_view_past_far_edges_settled(tiny_map, make_renderer, center):
    # NOTE: centred twice on purpose.  The *first* center() that crosses the
    # right/bottom edge currently produces a frame shifted by whole tiles
    # (reported separately); the second call at the same spot is correct.
    r = make_renderer(tiny_map, (16, 16), clamp_camera=False)
    r.center(center)
    r.center(center)
    assert_matches(render(r, (16, 16)), tiny_map, r.view_rect)


def test_view_larger_than_map_unclamped(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (48, 48), clamp_camera=False)
    r.center((16, 16))  # map occupies screen pixels 8..39
    surface = render(r, (48, 48))
    assert tuple(surface.get_at((7, 7)))[:3] == CLEAR
    assert tuple(surface.get_at((8, 8)))[:3] == layer1_color(0, 0)
    assert tuple(surface.get_at((40, 40)))[:3] == CLEAR
    assert_matches(surface, tiny_map, r.view_rect)


def test_draw_into_sub_rect(tiny_map, make_renderer):
    """The map is clipped to, and positioned at, the rect passed to draw()."""
    r = make_renderer(tiny_map, (16, 16))
    r.center((16, 16))
    surface = pygame.Surface((40, 40))
    surface.fill((1, 1, 1))
    area = pygame.Rect(10, 20, 16, 16)
    r.draw(surface, area)
    assert tuple(surface.get_at((9, 20)))[:3] == (1, 1, 1)
    assert tuple(surface.get_at((10, 19)))[:3] == (1, 1, 1)
    assert tuple(surface.get_at((26, 20)))[:3] == (1, 1, 1)
    for sx in range(16):
        for sy in range(16):
            expected = tiny_map.expected_world_color(r.view_rect.left + sx, r.view_rect.top + sy)
            assert tuple(surface.get_at((area.x + sx, area.y + sy)))[:3] == expected


def test_hidden_layer_not_drawn(display, make_renderer):
    data = SyntheticMapData(visible_layers=(0,))
    r = make_renderer(data, (32, 32))
    r.center((16, 16))
    surface = render(r, (32, 32))
    assert tuple(surface.get_at((0, 0)))[:3] == layer0_color(0, 0)
    assert_matches(surface, data, r.view_rect)


def test_zoom_2_via_setter(big_map, make_renderer):
    r = make_renderer(big_map, (32, 32))
    r.zoom = 2
    r.center((100, 100))
    assert r.view_rect.size == (16, 16)
    assert_matches(render(r, (32, 32)), big_map, r.view_rect, scale=2)


def test_zoom_2_scrolling(big_map, make_renderer):
    r = make_renderer(big_map, (32, 32))
    r.zoom = 2
    r.center((100, 100))
    for _ in range(6):
        r.scroll((3, 2))
        assert_matches(render(r, (32, 32)), big_map, r.view_rect, scale=2)


def test_alpha_renderer_pixels(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (16, 16), alpha=True)
    r.center((12, 20))
    assert_matches(render(r, (16, 16)), tiny_map, r.view_rect)


def test_colorkey_renderer_pixels(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (16, 16), colorkey=(255, 0, 255))
    r.center((12, 20))
    assert_matches(render(r, (16, 16)), tiny_map, r.view_rect)


def test_draw_returns_blit_rect(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (16, 16))
    r.center((12, 20))
    surface = pygame.Surface((16, 16))
    result = r.draw(surface, surface.get_rect())
    assert isinstance(result, pygame.Rect)
    assert surface.get_rect().contains(result)


# ----------------------------------------------------------------------
# sprites interleaved with tile layers (PyscrollGroup -> _draw_surfaces)

SPRITE_COLOR = (255, 255, 255)


class Block(pygame.sprite.Sprite):
    def __init__(self, rect, color=SPRITE_COLOR, blendmode=None):
        super().__init__()
        self.image = pygame.Surface(pygame.Rect(rect).size)
        self.image.fill(color)
        self.rect = pygame.Rect(rect)
        if blendmode is not None:
            self.blendmode = blendmode


def expected_with_sprite(data, view_rect, size, sprite_rect, sprite_layer, color=SPRITE_COLOR):
    """Tiles on layers *above* the sprite cover it; same-layer tiles do not."""
    tw, th = data.tile_size
    expected = expected_screen(data, view_rect, size)
    for (sx, sy) in expected:
        wx, wy = view_rect.left + sx, view_rect.top + sy
        if not sprite_rect.collidepoint(wx, wy):
            continue
        covering = [
            layer
            for layer in data.visible_tile_layers
            if layer > sprite_layer and data._gid(wx // tw, wy // th, layer)
        ]
        if not covering:
            expected[(sx, sy)] = color
    return expected


def draw_group(renderer, data, size, sprites):
    group = PyscrollGroup(map_layer=renderer)
    for sprite, layer in sprites:
        group.add(sprite, layer=layer)
    surface = pygame.Surface(size)
    group.draw(surface)
    return group, surface


def test_sprite_under_higher_layer_is_occluded(big_map, make_renderer):
    # (10, 10) is the only tile with a layer-1 overlay that the sprite touches
    assert big_map._gid(10, 10, 1)
    assert not any(big_map._gid(x, y, 1) for x, y in [(9, 9), (10, 9), (9, 10)])

    r = make_renderer(big_map, (40, 24))
    r.center((80, 80))
    sprite_rect = pygame.Rect(76, 76, 8, 8)
    _, surface = draw_group(r, big_map, (40, 24), [(Block(sprite_rect), 0)])

    # pixel in the overlay tile (world 82,82) shows the layer-1 tile
    sx, sy = r.translate_point((82, 82))
    assert tuple(surface.get_at((sx, sy)))[:3] == layer1_color(10, 10)
    # pixel of the sprite outside the overlay tile shows the sprite
    sx, sy = r.translate_point((77, 77))
    assert tuple(surface.get_at((sx, sy)))[:3] == SPRITE_COLOR

    expected = expected_with_sprite(big_map, r.view_rect, (40, 24), sprite_rect, 0)
    actual = screen_colors(surface)
    assert actual == expected, diff(actual, expected)


@pytest.mark.parametrize("layer", [1, 2])
def test_sprite_on_or_above_top_layer_is_visible(big_map, make_renderer, layer):
    r = make_renderer(big_map, (40, 24))
    r.center((80, 80))
    sprite_rect = pygame.Rect(76, 76, 8, 8)
    _, surface = draw_group(r, big_map, (40, 24), [(Block(sprite_rect), layer)])
    sx, sy = r.translate_point((82, 82))
    assert tuple(surface.get_at((sx, sy)))[:3] == SPRITE_COLOR
    expected = expected_with_sprite(big_map, r.view_rect, (40, 24), sprite_rect, layer)
    actual = screen_colors(surface)
    assert actual == expected, diff(actual, expected)


def test_sprite_occlusion_on_tiny_map_diagonal(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (32, 32))
    r.center((16, 16))
    # spans tiles (0..2, 1); only (1, 1) has a layer-1 tile
    sprite_rect = pygame.Rect(4, 10, 16, 4)
    _, surface = draw_group(r, tiny_map, (32, 32), [(Block(sprite_rect), 0)])
    assert tuple(surface.get_at((5, 11)))[:3] == SPRITE_COLOR
    assert tuple(surface.get_at((10, 11)))[:3] == layer1_color(1, 1)
    assert tuple(surface.get_at((17, 11)))[:3] == SPRITE_COLOR
    expected = expected_with_sprite(tiny_map, r.view_rect, (32, 32), sprite_rect, 0)
    actual = screen_colors(surface)
    assert actual == expected, diff(actual, expected)


def test_sprite_layer_order(big_map, make_renderer):
    r = make_renderer(big_map, (40, 24))
    r.center((60, 60))
    low = Block((50, 50, 10, 10), color=(1, 2, 3))
    high = Block((55, 55, 10, 10), color=(4, 5, 6))
    # added high first to make sure ordering is by layer, not insertion
    _, surface = draw_group(r, big_map, (40, 24), [(high, 2), (low, 1)])
    assert tuple(surface.get_at(r.translate_point((57, 57))))[:3] == (4, 5, 6)
    assert tuple(surface.get_at(r.translate_point((51, 51))))[:3] == (1, 2, 3)


def test_blendmode_sprite(big_map, make_renderer):
    r = make_renderer(big_map, (40, 24))
    r.center((60, 60))
    # (6, 6): 6 + 12 = 18 -> no overlay, so the tile colour is layer 0
    assert not big_map._gid(6, 6, 1)
    sprite = Block((50, 50, 4, 4), color=(10, 10, 10), blendmode=pygame.BLEND_RGB_ADD)
    _, surface = draw_group(r, big_map, (40, 24), [(sprite, 2)])
    base = layer0_color(6, 6)
    assert tuple(surface.get_at(r.translate_point((51, 51))))[:3] == tuple(c + 10 for c in base)


@pytest.mark.xfail(
    strict=False,
    reason="B5: _draw_surfaces raises IndexError when no tile layers are visible",
)
def test_sprites_with_no_visible_tile_layers(display, make_renderer):
    data = SyntheticMapData(visible_layers=())
    r = make_renderer(data, (32, 32))
    r.center((16, 16))
    _, surface = draw_group(r, data, (32, 32), [(Block((4, 4, 4, 4)), 0)])
    assert tuple(surface.get_at((5, 5)))[:3] == SPRITE_COLOR
    assert tuple(surface.get_at((20, 20)))[:3] == CLEAR
