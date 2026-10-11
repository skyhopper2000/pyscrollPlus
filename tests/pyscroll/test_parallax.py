from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from pathlib import Path

import pygame
import pytest
from pygame import Rect, Surface

from pyscroll.data import PyscrollDataAdapter, TiledMapData
from pyscroll.group import PyscrollGroup
from pyscroll.parallax import Band, ImageBand, LayerFilter, ParallaxRenderer

FIXTURE = Path(__file__).parents[1] / "data" / "parallax" / "parallax_test.tmx"

TILE = 8
MAP_W, MAP_H = 64, 16
VIEW = (80, 40)


@pytest.fixture(scope="module", autouse=True)
def display():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def column_color(x: int) -> tuple[int, int, int]:
    """Back layer tiles encode their column in the red channel."""
    return x * 4, 100, 0


class SolidColorData(PyscrollDataAdapter):
    """
    Two-layer map of solid color tiles.

    Layer 0 is fully covered; the color of each tile encodes its column.
    Layer 1 only has tiles in row 0, colored white.

    """

    tile_size = (TILE, TILE)
    map_size = (MAP_W, MAP_H)
    visible_tile_layers = [0, 1]

    def __init__(self) -> None:
        super().__init__()
        self._tiles: dict[tuple[int, int, int], Surface] = {}
        for x in range(MAP_W):
            back = Surface((TILE, TILE))
            back.fill(column_color(x))
            front = Surface((TILE, TILE), pygame.SRCALPHA)
            front.fill((255, 255, 255))
            for y in range(MAP_H):
                self._tiles[(x, y, 0)] = back
            self._tiles[(x, 0, 1)] = front
        self.reload_animations()

    def get_animations(self):
        return []

    def _get_tile_image(self, x, y, l):
        return self._tiles.get((x, y, l))

    def _get_tile_image_by_id(self, id):
        return None


def back_column_at(surface: Surface, screen_x: int, screen_y: int) -> int:
    r, g, b, *_ = surface.get_at((screen_x, screen_y))
    assert (g, b) == (100, 0), "sampled pixel is not a back-layer tile"
    return r // 4


# --------------------------------------------------------------------------- #
# LayerFilter
# --------------------------------------------------------------------------- #


def test_layer_filter_generic_adapter():
    data = SolidColorData()
    f = LayerFilter(data, [1, 7])
    assert f.visible_tile_layers == [1]
    assert f.tile_size == data.tile_size
    assert f.map_size == data.map_size
    tiles = list(f.get_tile_images_by_rect(Rect(0, 0, 4, 4)))
    assert {(x, y, l) for x, y, l, _ in tiles} == {(x, 0, 1) for x in range(4)}
    assert f.get_tile_image(0, 1, 0) is None  # layer 0 is filtered out
    assert f.get_tile_image(0, 0, 1) is data.get_tile_image(0, 0, 1)


def test_layer_filter_respects_source_visibility():
    data = SolidColorData()
    f = LayerFilter(data, [0, 1])
    data.visible_tile_layers = [0]
    assert f.visible_tile_layers == [0]


def test_layer_filter_custom_batch_adapter_is_filtered():
    class Batch(SolidColorData):
        def get_tile_images_by_rect(self, rect):
            yield from PyscrollDataAdapter.get_tile_images_by_rect(self, rect)

    f = LayerFilter(Batch(), [0])
    tiles = list(f.get_tile_images_by_rect(Rect(0, 0, 2, 2)))
    assert {l for _, _, l, _ in tiles} == {0}
    assert len(tiles) == 4


def test_layer_filter_forwards_unknown_attributes():
    data = SolidColorData()
    data.custom = "value"
    assert LayerFilter(data, [0]).custom == "value"


@pytest.fixture
def tmx():
    from pytmx.util_pygame import load_pygame

    return load_pygame(str(FIXTURE))


def test_layer_filter_tiled(tmx):
    data = TiledMapData(tmx)
    # tile layers in pytmx order: far, hidden, far2, main, main2, front
    f = LayerFilter(data, [3, 4, 1])
    assert f.visible_tile_layers == [3, 4]  # 1 ("hidden") is not visible
    tiles = list(f.get_tile_images_by_rect(Rect(0, 0, 8, 4)))
    assert {(x, y, l) for x, y, l, _ in tiles} == {(1, 1, 3), (6, 1, 3), (2, 2, 4)}


def test_layer_filter_animation_positions_are_per_filter(tmx):
    data = TiledMapData(tmx)
    main = LayerFilter(data, [3])
    far = LayerFilter(data, [0, 2])
    list(main.get_tile_images_by_rect(Rect(0, 0, 8, 4)))
    list(far.get_tile_images_by_rect(Rect(0, 0, 8, 4)))

    (main_token,) = main._animation_queue
    (far_token,) = far._animation_queue
    assert main_token.positions == {(6, 1, 3)}
    assert far_token.positions == {(0, 0, 0), (7, 3, 0)}
    # the wrapped adapter's tokens are not touched
    (source_token,) = data._animation_queue
    assert source_token.positions == set()

    # advancing one filter's animations does not consume the other's
    view = Rect(0, 0, 9, 5)
    main_token.next = far_token.next = 0
    assert {(x, y, l) for x, y, l, _ in main.process_animation_queue(view)} == {
        (6, 1, 3)
    }
    # far2 (layer 2) is empty there, so the column redraw adds nothing
    assert {(x, y, l) for x, y, l, _ in far.process_animation_queue(view)} == {
        (0, 0, 0),
        (7, 3, 0),
    }


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #


def test_band_normalizes_factor():
    assert Band([0], factor=0.5).factor == (0.5, 0.5)
    assert Band((0, 1), factor=[1, 2]).factor == (1.0, 2.0)
    assert Band([0]).layers == (0,)
    with pytest.raises(ValueError):
        Band([])


@pytest.mark.parametrize(
    "bands",
    [
        [],
        [Band([0]), Band([1])],
        [Band([0], sprites=True), Band([1], sprites=True)],
        [Band([0], factor=0.5, sprites=True)],
    ],
)
def test_invalid_bands(bands):
    with pytest.raises(ValueError):
        ParallaxRenderer(SolidColorData(), VIEW, bands)


# --------------------------------------------------------------------------- #
# centering and clamping
# --------------------------------------------------------------------------- #


def make_renderer(factors, origin=(0, 0), clamp=False, **kw):
    bands = [Band([0], factor=f) for f in factors]
    bands.append(Band([1], sprites=True))
    return (
        ParallaxRenderer(
            SolidColorData(), VIEW, bands, clamp_camera=clamp, origin=origin, **kw
        ),
        bands,
    )


@pytest.mark.parametrize("origin", [(0, 0), (40, 20), (256, 64), (-10, 30)])
@pytest.mark.parametrize(
    "factor", [(0.0, 0.0), (0.5, 0.5), (0.25, 1.0), (1.0, 0.0), (1.5, 1.25)]
)
def test_band_centering_math(origin, factor):
    renderer, bands = make_renderer([factor], origin=origin)
    for camera in [(200, 60), (40, 20), (311, 97)]:
        renderer.center(camera)
        expected = (
            origin[0] + (camera[0] - origin[0]) * factor[0],
            origin[1] + (camera[1] - origin[1]) * factor[1],
        )
        assert renderer.band_center(bands[0]) == pytest.approx(expected)
        # unclamped band renderers follow exactly (rounded)
        assert renderer.renderers[0].view_rect.center == (
            round(expected[0]),
            round(expected[1]),
        )
        assert renderer.view_rect.center == camera


def test_sprite_band_is_clamped_and_drives_other_bands():
    renderer, bands = make_renderer([0.5], clamp=True)
    map_rect = renderer.map_rect
    renderer.center((-500, -500))
    assert renderer.view_rect.topleft == (0, 0)
    hw, hh = VIEW[0] // 2, VIEW[1] // 2
    # other bands are positioned from the *clamped* camera
    assert renderer.band_center(bands[0]) == (hw * 0.5, hh * 0.5)
    # ...and then clamp to their own map rect
    assert renderer.renderers[0].view_rect.topleft == (0, 0)

    renderer.center((10_000, 10_000))
    assert renderer.view_rect.bottomright == map_rect.bottomright
    cx, cy = renderer.view_rect.center
    assert renderer.band_center(bands[0]) == (cx * 0.5, cy * 0.5)
    assert map_rect.contains(renderer.renderers[0].view_rect)


def test_foreground_band_pins_at_edge_when_clamped():
    renderer = ParallaxRenderer(
        SolidColorData(),
        VIEW,
        [Band([0], sprites=True), Band([1], factor=2.0)],
        origin=(VIEW[0] / 2, VIEW[1] / 2),
    )
    renderer.center((10_000, 10_000))
    front = renderer.renderers[1]
    assert front.view_rect.bottomright == renderer.map_rect.bottomright


def test_scroll_and_translate_delegate_to_sprite_band():
    renderer, _ = make_renderer([0.5], origin=(256, 64))
    renderer.center((256, 64))
    renderer.scroll((10, -4))
    assert renderer.view_rect.center == (266, 60)
    ox, oy = renderer.get_center_offset()
    assert (ox, oy) == renderer.sprite_renderer.get_center_offset()
    assert renderer.translate_point((266, 60)) == (VIEW[0] // 2, VIEW[1] // 2)
    assert renderer.translate_rect((266, 60, 8, 8)) == Rect(40, 20, 8, 8)
    assert renderer.translate_points([(0, 0)]) == [(ox, oy)]
    assert renderer.translate_rects([(0, 0, 1, 1)]) == [Rect(ox, oy, 1, 1)]


# --------------------------------------------------------------------------- #
# pixels
# --------------------------------------------------------------------------- #


def test_back_band_moves_at_half_speed():
    origin = (MAP_W * TILE / 2, MAP_H * TILE / 2)
    renderer = ParallaxRenderer(
        SolidColorData(),
        VIEW,
        [Band([0], factor=0.5), Band([1], sprites=True)],
        origin=origin,
    )
    screen = Surface(VIEW)
    probe = (VIEW[0] // 2, VIEW[1] - 1)  # row 0 (front tiles) is off-screen

    renderer.center(origin)
    renderer.draw(screen, screen.get_rect())
    before = back_column_at(screen, *probe)

    renderer.scroll((32, 0))  # four tiles for the camera...
    renderer.draw(screen, screen.get_rect())
    after = back_column_at(screen, *probe)
    assert after - before == 2  # ...two tiles for the back band

    # a full-speed back band for comparison
    full = ParallaxRenderer(
        SolidColorData(), VIEW, [Band([0]), Band([1], sprites=True)], origin=origin
    )
    full.center(origin)
    full.draw(screen, screen.get_rect())
    full_before = back_column_at(screen, *probe)
    full.scroll((32, 0))
    full.draw(screen, screen.get_rect())
    assert back_column_at(screen, *probe) - full_before == 4


def test_front_band_is_drawn_over_back_band():
    renderer = ParallaxRenderer(
        SolidColorData(), VIEW, [Band([0], factor=0.5), Band([1], sprites=True)]
    )
    renderer.center((0, 0))  # clamped: view at the top-left, row 0 visible
    screen = Surface(VIEW)
    renderer.draw(screen, screen.get_rect())
    assert screen.get_at((4, 4))[:3] == (255, 255, 255)
    assert screen.get_at((4, 12))[1:3] == (100, 0)


def test_sprites_only_go_to_sprite_band_and_front_bands_cover_them():
    data = SolidColorData()
    renderer = ParallaxRenderer(
        data, VIEW, [Band([0], sprites=True), Band([1], factor=1.0)]
    )
    renderer.center((0, 0))
    sprite = Surface((8, 8))
    sprite.fill((1, 2, 3))
    screen = Surface(VIEW)
    renderer.draw(
        screen,
        screen.get_rect(),
        [(sprite, Rect(0, 0, 8, 8), 5), (sprite, Rect(16, 16, 8, 8), 5)],
    )
    assert screen.get_at((4, 4))[:3] == (255, 255, 255)  # front band on top
    assert screen.get_at((20, 20))[:3] == (1, 2, 3)


def test_image_band_repeats():
    image = Surface((10, 10))
    image.fill((9, 9, 9))
    image.fill((200, 0, 0), (0, 0, 5, 10))
    renderer = ParallaxRenderer(
        SolidColorData(),
        VIEW,
        [
            ImageBand(image, factor=(0, 0), repeat_x=True, repeat_y=True),
            Band([1], sprites=True),
        ],
        origin=(VIEW[0] / 2, VIEW[1] / 2),
    )
    renderer.center((200, 100))
    screen = Surface(VIEW)
    renderer.draw(screen, screen.get_rect())
    # factor 0: the image stays put and covers the whole view
    for x in range(0, VIEW[0], 10):
        assert screen.get_at((x + 1, 35))[:3] == (200, 0, 0)
        assert screen.get_at((x + 6, 35))[:3] == (9, 9, 9)


def test_zoom_composes_then_scales():
    origin = (MAP_W * TILE / 2, MAP_H * TILE / 2)
    renderer = ParallaxRenderer(
        SolidColorData(),
        VIEW,
        [Band([0], factor=0.5), Band([1], sprites=True)],
        origin=origin,
        zoom=2.0,
    )
    assert renderer.view_rect.size == (VIEW[0] // 2, VIEW[1] // 2)
    renderer.center(origin)
    screen = Surface(VIEW)
    assert renderer.draw(screen, screen.get_rect()) == screen.get_rect()
    assert renderer.translate_point(renderer.view_rect.center) == (40, 20)
    renderer.zoom = 1.0
    assert renderer.view_rect.size == VIEW
    assert renderer.view_rect.center == (round(origin[0]), round(origin[1]))


def test_works_with_pyscroll_group():
    renderer = ParallaxRenderer(
        SolidColorData(), VIEW, [Band([0], factor=0.5), Band([1], sprites=True)]
    )
    group = PyscrollGroup(map_layer=renderer)
    sprite = pygame.sprite.Sprite()
    sprite.image = Surface((8, 8))
    sprite.image.fill((1, 2, 3))
    sprite.rect = Rect(100, 60, 8, 8)
    group.add(sprite, layer=5)
    group.center(sprite.rect.center)
    screen = Surface(VIEW)
    group.draw(screen)
    assert group.view == renderer.view_rect
    assert screen.get_at((VIEW[0] // 2, VIEW[1] // 2))[:3] == (1, 2, 3)


# --------------------------------------------------------------------------- #
# Tiled
# --------------------------------------------------------------------------- #


def test_from_tiled(tmx):
    renderer = ParallaxRenderer.from_tiled(tmx, (32, 16))
    bands = renderer.bands
    assert [type(b) for b in bands] == [ImageBand, Band, Band, Band]

    sky = bands[0]
    assert sky.factor == (0.1, 0.0)
    assert sky.repeat_x and not sky.repeat_y
    assert sky.offset == (4.0, 0.0)
    assert sky.surface.get_size() == (16, 8)

    assert bands[1].layers == (0, 2)  # "hidden" is skipped, no split
    assert bands[1].factor == (0.5, 0.5)
    assert not bands[1].sprites
    assert bands[2].layers == (3, 4)
    assert bands[2].factor == (1.0, 1.0)
    assert bands[2].sprites
    assert bands[3].layers == (5,)
    assert bands[3].factor == (1.25, 1.0)

    assert renderer.origin == (16.0, 8.0)
    screen = Surface((32, 16))
    renderer.center((32, 16))
    renderer.draw(screen, screen.get_rect())


def test_from_tiled_sprite_layer_and_tiled_map_data(tmx):
    data = TiledMapData(tmx)
    renderer = ParallaxRenderer.from_tiled(
        data, (32, 16), sprite_layer=4, origin=(0, 0)
    )
    assert renderer.data is data
    assert renderer.origin == (0.0, 0.0)
    assert [b.sprites for b in renderer.bands if isinstance(b, Band)] == [
        False,
        True,
        False,
    ]
    with pytest.raises(ValueError):
        ParallaxRenderer.from_tiled(tmx, (32, 16), sprite_layer=0)


def test_reload(tmx):
    renderer = ParallaxRenderer.from_tiled(tmx, (32, 16))
    renderer.center((40, 20))
    center = renderer.view_rect.center
    renderer.reload()
    assert renderer.view_rect.center == center
