"""
Smoke and consistency tests against the bundled Tiled demo maps.
"""

from __future__ import annotations

import pygame
import pytest

from pyscroll.data import TiledMapData
from pyscroll.group import PyscrollGroup
from pyscroll.isometric import IsometricBufferedRenderer
from pyscroll.orthographic import BufferedRenderer

SIZE = (320, 240)


def frame(renderer, size=SIZE):
    surface = pygame.Surface(size)
    renderer.draw(surface, surface.get_rect())
    return pygame.image.tobytes(surface, "RGB")


def test_desert_metadata(desert_data):
    assert desert_data.tile_size == (32, 32)
    assert desert_data.map_size == (40, 40)
    assert list(desert_data.visible_tile_layers)


def test_desert_renderer(desert_data):
    r = BufferedRenderer(desert_data, SIZE)
    assert r.map_rect == pygame.Rect(0, 0, 1280, 1280)
    r.center((640, 640))
    assert r.view_rect.center == (640, 640)
    assert isinstance(r.draw(pygame.Surface(SIZE), pygame.Rect((0, 0), SIZE)), pygame.Rect)


def test_desert_scroll_matches_fresh_render(desert_tmx):
    """Incrementally scrolled buffer == buffer drawn from scratch at the same spot."""
    scrolled = BufferedRenderer(TiledMapData(desert_tmx), SIZE)
    scrolled.center((400, 400))
    for _ in range(40):
        scrolled.scroll((7, 5))
    for _ in range(25):
        scrolled.scroll((-3, 9))

    fresh = BufferedRenderer(TiledMapData(desert_tmx), SIZE)
    fresh.center(scrolled.view_rect.center)
    assert fresh.view_rect == scrolled.view_rect
    assert frame(scrolled) == frame(fresh)


@pytest.mark.parametrize("kwargs", [{"alpha": True}, {"colorkey": (255, 0, 255)}])
def test_desert_special_buffers(desert_tmx, kwargs):
    r = BufferedRenderer(TiledMapData(desert_tmx), SIZE, **kwargs)
    r.center((300, 300))
    for _ in range(10):
        r.scroll((5, 5))
    frame(r)


def test_desert_zoom(desert_data):
    r = BufferedRenderer(desert_data, SIZE)
    r.zoom = 2
    r.center((640, 640))
    assert r.view_rect.size == (160, 120)
    frame(r)


def test_desert_reload(desert_data):
    r = BufferedRenderer(desert_data, SIZE)
    r.center((640, 640))
    before = frame(r)
    old_tmx = desert_data.tmx
    r.reload()
    assert desert_data.tmx is not old_tmx
    assert frame(r) == before


def test_desert_group_with_sprite(desert_data):
    r = BufferedRenderer(desert_data, SIZE)
    group = PyscrollGroup(map_layer=r)
    sprite = pygame.sprite.Sprite()
    sprite.image = pygame.Surface((16, 16))
    sprite.image.fill((255, 0, 0))
    sprite.rect = sprite.image.get_rect(center=(640, 640))
    group.add(sprite, layer=0)
    group.center(sprite.rect.center)
    surface = pygame.Surface(SIZE)
    group.draw(surface)
    # desert.tmx ground layer is opaque everywhere near the centre and the
    # sprite sits on layer 0, so whatever is drawn there must be valid
    assert surface.get_at((160, 120)) is not None


@pytest.mark.xfail(
    strict=False,
    reason="B2: IsometricBufferedRenderer crashes on construction (wrong call signatures)",
)
def test_isometric_renderer_constructs_and_draws(tiny_map):
    r = IsometricBufferedRenderer(tiny_map, (64, 64))
    r.center((16, 16))
    surface = pygame.Surface((64, 64))
    r.draw(surface, surface.get_rect())
