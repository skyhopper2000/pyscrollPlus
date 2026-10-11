"""
BufferedRenderer behaviour: camera, buffers, zoom, coordinate translation.

Pixel-exact rendering checks live in test_pixels.py.
"""

from __future__ import annotations

import pygame
import pytest
from pygame import Rect
from synthetic_map import SyntheticMapData, diff, expected_screen, screen_colors

from pyscroll.orthographic import BufferedRenderer

SIZE = (40, 24)


# ----------------------------------------------------------------------
# construction / view_rect


def test_initial_state(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    assert r.view_rect.size == SIZE
    assert r.map_rect == Rect(0, 0, 256, 256)
    assert r.zoom == 1.0
    # buffer is one tile larger than the view in each direction (rounded up)
    assert r._buffer.get_size() == (40 + 8, 24 + 8)


def test_center_sets_view_rect_center(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))
    assert r.view_rect.center == (100, 100)
    assert r.view_rect.size == SIZE


def test_center_rounds_floats(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center((100.6, 99.4))
    assert r.view_rect.center == (101, 99)


def test_center_accepts_vector2(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center(pygame.Vector2(120, 80))
    assert r.view_rect.center == (120, 80)


@pytest.mark.parametrize(
    "target, expected_topleft",
    [
        ((0, 0), (0, 0)),
        ((-500, -500), (0, 0)),
        ((10_000, 10_000), (256 - 40, 256 - 24)),
        ((0, 10_000), (0, 256 - 24)),
    ],
)
def test_clamp_camera_on_keeps_view_inside_map(big_map, make_renderer, target, expected_topleft):
    r = make_renderer(big_map, SIZE, clamp_camera=True)
    r.center(target)
    assert r.view_rect.topleft == expected_topleft
    assert r.map_rect.contains(r.view_rect)
    assert r._anchored_view


@pytest.mark.parametrize("target", [(0, 0), (-50, -30), (300, 280), (250, 5)])
def test_clamp_camera_off_allows_view_past_edges(big_map, make_renderer, target):
    r = make_renderer(big_map, SIZE, clamp_camera=False)
    r.center(target)
    assert r.view_rect.center == target
    assert not r._anchored_view


def test_clamp_camera_off_inside_map_is_anchored(big_map, make_renderer):
    r = make_renderer(big_map, SIZE, clamp_camera=False)
    r.center((128, 128))
    assert r._anchored_view


def test_scroll_moves_center(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))
    r.scroll((5, -3))
    assert r.view_rect.center == (105, 97)


def test_get_center_offset(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))
    assert r.get_center_offset() == (-100 + 20, -100 + 12)


# ----------------------------------------------------------------------
# scroll path vs forced redraw path


class RedrawSpy:
    def __init__(self, renderer: BufferedRenderer, monkeypatch) -> None:
        self.calls = 0
        original = renderer.redraw_tiles

        def spy(surface):
            self.calls += 1
            return original(surface)

        monkeypatch.setattr(renderer, "redraw_tiles", spy)


def test_small_move_uses_scroll_path(big_map, make_renderer, monkeypatch):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))
    spy = RedrawSpy(r, monkeypatch)
    tile_view = r._tile_view.copy()

    r.center((108, 100))  # exactly one tile to the right
    assert spy.calls == 0
    assert r._tile_view.topleft == (tile_view.left + 1, tile_view.top)

    r.center((108, 92))  # one tile up
    assert spy.calls == 0
    assert r._tile_view.topleft == (tile_view.left + 1, tile_view.top - 1)


def test_sub_tile_move_touches_nothing(big_map, make_renderer, monkeypatch):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))
    spy = RedrawSpy(r, monkeypatch)
    tile_view = r._tile_view.copy()
    r.center((101, 101))
    assert spy.calls == 0
    assert r._tile_view == tile_view


def test_big_jump_forces_redraw(big_map, make_renderer, monkeypatch):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))
    spy = RedrawSpy(r, monkeypatch)
    r.center((200, 40))
    assert spy.calls == 1


def _assert_frame(r, data, size):
    surface = pygame.Surface(size)
    r.draw(surface, surface.get_rect())
    actual = screen_colors(surface)
    expected = expected_screen(data, r.view_rect, size)
    assert actual == expected, diff(actual, expected)


@pytest.mark.parametrize("step", [(3, 0), (0, 3), (-3, 0), (0, -3), (5, 7), (-7, -5)])
def test_scroll_path_matches_expected_frames(big_map, make_renderer, step):
    """Walk the camera in small steps; every frame must be pixel exact."""
    r = make_renderer(big_map, SIZE)
    r.center((128, 128))
    for _ in range(12):
        r.scroll(step)
        _assert_frame(r, big_map, SIZE)


@pytest.mark.parametrize("target", [(30, 30), (200, 50), (20, 230), (128, 128)])
def test_redraw_path_matches_expected_frames(big_map, make_renderer, target):
    r = make_renderer(big_map, SIZE)
    r.center((128, 128))
    r.center(target)
    _assert_frame(r, big_map, SIZE)


def test_scroll_and_redraw_paths_agree(big_map, make_renderer):
    """Same camera position reached by scrolling and by jumping."""
    scrolled = make_renderer(big_map, SIZE)
    jumped = make_renderer(big_map, SIZE)
    scrolled.center((60, 60))
    for _ in range(20):
        scrolled.scroll((4, 3))
    jumped.center((60 + 80, 60 + 60))

    a, b = pygame.Surface(SIZE), pygame.Surface(SIZE)
    scrolled.draw(a, a.get_rect())
    jumped.draw(b, b.get_rect())
    assert scrolled.view_rect == jumped.view_rect
    assert screen_colors(a) == screen_colors(b)


def test_scroll_path_with_unclamped_camera_at_edges(big_map, make_renderer):
    r = make_renderer(big_map, SIZE, clamp_camera=False)
    r.center((10, 10))
    for _ in range(10):
        r.scroll((-3, -2))
        _assert_frame(r, big_map, SIZE)


# ----------------------------------------------------------------------
# alpha / colorkey buffers


def test_default_buffer_is_opaque(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (16, 16))
    assert not r._buffer.get_flags() & pygame.SRCALPHA
    assert r._buffer.get_colorkey() is None


def test_alpha_buffer(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (48, 48), alpha=True)
    assert r._buffer.get_flags() & pygame.SRCALPHA
    # inside the map: opaque tile colour (0, 0) has a layer-1 tile
    assert tuple(r._buffer.get_at((1, 1))) == (*tiny_map.expected_world_color(1, 1), 255)
    # outside the 4x4 map (buffer is 7x7 tiles): fully transparent
    assert r._buffer.get_at((50, 50)).a == 0


def test_alpha_zoom_buffer_has_alpha(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (48, 48), alpha=True)
    r.zoom = 2
    assert r._zoom_buffer.get_flags() & pygame.SRCALPHA
    assert r._buffer.get_flags() & pygame.SRCALPHA


def test_colorkey_buffer(tiny_map, make_renderer):
    key = (255, 0, 255)
    r = make_renderer(tiny_map, (48, 48), colorkey=key)
    assert r._buffer.get_colorkey()[:3] == key
    # area outside the map is filled with the colorkey
    assert tuple(r._buffer.get_at((50, 50)))[:3] == key
    assert tuple(r._buffer.get_at((1, 1)))[:3] == tiny_map.expected_world_color(1, 1)


def test_colorkey_and_alpha_together_is_error(tiny_map):
    with pytest.raises(ValueError):
        BufferedRenderer(tiny_map, (16, 16), colorkey=(255, 0, 255), alpha=True)


# ----------------------------------------------------------------------
# set_size / zoom


def test_set_size(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.set_size((64, 32))
    assert r.view_rect.size == (64, 32)
    assert r._buffer.get_size() == (64 + 8, 32 + 8)
    r.center((100, 100))
    _assert_frame(r, big_map, (64, 32))


def test_zoom_setter_resizes_buffers(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.zoom = 2
    assert r.zoom == 2
    assert r.view_rect.size == (20, 12)
    assert r._zoom_buffer.get_size() == (20, 12)
    assert (r._real_ratio_x, r._real_ratio_y) == (2.0, 2.0)

    r.zoom = 1
    assert r.view_rect.size == SIZE


@pytest.mark.parametrize("bad", [0, -1, -0.5])
def test_zoom_must_be_positive(big_map, make_renderer, bad):
    r = make_renderer(big_map, SIZE)
    with pytest.raises(ValueError):
        r.zoom = bad


def test_zoom_out(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.zoom = 0.5
    assert r.view_rect.size == (80, 48)
    r.center((128, 128))
    surface = pygame.Surface(SIZE)
    assert isinstance(r.draw(surface, surface.get_rect()), Rect)


# ----------------------------------------------------------------------
# translate_*


def test_translate_at_zoom_1(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))  # view_rect.topleft == (80, 88)
    assert r.translate_point((80, 88)) == (0, 0)
    assert r.translate_point((100, 100)) == (20, 12)
    assert r.translate_rect((90, 90, 8, 8)) == Rect(10, 2, 8, 8)
    assert r.translate_points([(80, 88), (100, 100)]) == [(0, 0), (20, 12)]
    assert r.translate_rects([Rect(90, 90, 8, 8), (80, 88, 1, 2)]) == [
        Rect(10, 2, 8, 8),
        Rect(0, 0, 1, 2),
    ]


def test_translate_point_returns_ints(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))
    x, y = r.translate_point((100.0, 100.0))
    assert (type(x), type(y)) == (int, int)


def test_translate_matches_drawn_pixels(big_map, make_renderer):
    """translate_point must agree with where the map is actually drawn."""
    r = make_renderer(big_map, SIZE)
    r.center((101, 97))
    surface = pygame.Surface(SIZE)
    r.draw(surface, surface.get_rect())
    for world in [(90, 90), (100, 100), (115, 105)]:
        sx, sy = r.translate_point(world)
        assert tuple(surface.get_at((sx, sy)))[:3] == big_map.expected_world_color(*world)


def test_translate_with_zoom_setter(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.zoom = 2
    r.center((100, 100))  # view_rect is 20x12 -> topleft (90, 94)
    assert r.view_rect.topleft == (90, 94)
    assert r.translate_point((90, 94)) == (0, 0)
    assert r.translate_point((100, 100)) == (20, 12)
    assert r.translate_rect((95, 96, 8, 8)) == Rect(10, 4, 16, 16)
    assert r.translate_points([(90, 94), (100, 100)]) == [(0, 0), (20, 12)]
    assert r.translate_rects([(95, 96, 8, 8)]) == [Rect(10, 4, 16, 16)]


@pytest.mark.xfail(
    strict=False,
    reason="B1: zoom passed to the constructor never computes _real_ratio_x/y",
)
def test_translate_with_zoom_constructor_matches_setter(big_map):
    via_ctor = BufferedRenderer(big_map, SIZE, zoom=2)
    via_setter = BufferedRenderer(big_map, SIZE)
    via_setter.zoom = 2
    for r in (via_ctor, via_setter):
        r.center((100, 100))

    assert via_ctor.translate_point((100, 100)) == (20, 12)
    assert via_ctor.translate_point((90, 94)) == via_setter.translate_point((90, 94))
    assert via_ctor.translate_rect((95, 96, 8, 8)) == Rect(10, 4, 16, 16)
    assert via_ctor.translate_points([(100, 100)]) == [(20, 12)]
    assert via_ctor.translate_rects([(95, 96, 8, 8)]) == [Rect(10, 4, 16, 16)]


# ----------------------------------------------------------------------
# reload


def test_reload_picks_up_new_tile_data(tiny_map, make_renderer):
    r = make_renderer(tiny_map, (32, 32))
    r.center((16, 16))
    tiny_map.color_funcs[0] = lambda x, y: (1, 2, 3 + x + y)
    r.reload()
    surface = pygame.Surface((32, 32))
    r.draw(surface, surface.get_rect())
    # (1, 0) has no layer-1 tile, so it shows the new layer-0 colour
    assert tuple(surface.get_at((8 + 1, 1)))[:3] == (1, 2, 4)
    actual = screen_colors(surface)
    expected = expected_screen(tiny_map, r.view_rect, (32, 32))
    assert actual == expected, diff(actual, expected)


def test_reload_keeps_animations_registered(display, make_renderer):
    data = SyntheticMapData(animations={(1, 0, 0): [((9, 9, 9), 1000), ((8, 8, 8), 1000)]})
    r = make_renderer(data, (32, 32))
    r.reload()
    assert len(data._animation_queue) == 1
