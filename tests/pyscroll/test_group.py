from __future__ import annotations

import pygame
import pytest

from pyscroll.group import PyscrollGroup

SIZE = (40, 24)


class Block(pygame.sprite.Sprite):
    def __init__(self, rect, color=(255, 255, 255)):
        super().__init__()
        self.image = pygame.Surface(pygame.Rect(rect).size)
        self.image.fill(color)
        self.rect = pygame.Rect(rect)


@pytest.fixture
def renderer(big_map, make_renderer):
    r = make_renderer(big_map, SIZE)
    r.center((100, 100))  # view_rect == (80, 88, 40, 24)
    return r


@pytest.fixture
def group(renderer):
    return PyscrollGroup(map_layer=renderer)


@pytest.fixture
def draw_spy(renderer, monkeypatch):
    """Record the `surfaces` list the group hands to the renderer."""
    calls = []
    original = renderer.draw

    def spy(surface, rect, surfaces=None):
        calls.append(list(surfaces or []))
        return original(surface, rect, surfaces)

    monkeypatch.setattr(renderer, "draw", spy)
    return calls


def test_view_is_a_copy_of_renderer_view_rect(group, renderer):
    view = group.view
    assert view == renderer.view_rect == pygame.Rect(80, 88, 40, 24)
    view.move_ip(10, 10)
    assert renderer.view_rect == pygame.Rect(80, 88, 40, 24)


def test_center_delegates_to_renderer(group, renderer):
    group.center((60, 70))
    assert renderer.view_rect.center == (60, 70)
    assert group.view.center == (60, 70)


def test_draw_returns_rect(group):
    group.add(Block((90, 90, 4, 4)))
    result = group.draw(pygame.Surface(SIZE))
    assert isinstance(result, pygame.Rect)


def test_draw_with_no_sprites(group):
    surface = pygame.Surface(SIZE)
    assert isinstance(group.draw(surface), pygame.Rect)


def test_sprite_inside_view_is_drawn_at_screen_position(group, renderer, draw_spy):
    sprite = Block((90, 90, 4, 4), color=(250, 250, 250))
    group.add(sprite)
    surface = pygame.Surface(SIZE)
    group.draw(surface)

    (surfaces,) = draw_spy
    assert len(surfaces) == 1
    image, rect, layer = surfaces[0][:3]
    assert image is sprite.image
    assert rect == pygame.Rect(10, 2, 4, 4) == renderer.translate_rect(sprite.rect)
    assert layer == 0
    # spritedict holds the on-screen rect, the sprite's own rect is untouched
    assert group.spritedict[sprite] == pygame.Rect(10, 2, 4, 4)
    assert sprite.rect == pygame.Rect(90, 90, 4, 4)
    assert tuple(surface.get_at((11, 3)))[:3] == (250, 250, 250)


def test_sprites_outside_view_are_not_drawn(group, draw_spy):
    inside = Block((90, 90, 4, 4))
    outside = [
        Block((0, 0, 4, 4)),
        Block((200, 200, 4, 4)),
        Block((76, 88, 4, 4)),  # touches the left edge but does not overlap
        Block((80, 112, 4, 4)),  # just below the view
    ]
    group.add(inside, *outside)
    group.draw(pygame.Surface(SIZE))
    (surfaces,) = draw_spy
    assert [s[0] for s in surfaces] == [inside.image]


def test_partially_visible_sprite_is_drawn(group, draw_spy):
    edge = Block((78, 86, 4, 4))
    group.add(edge)
    group.draw(pygame.Surface(SIZE))
    (surfaces,) = draw_spy
    assert len(surfaces) == 1


def test_blendmode_sprite_passes_flags(group, draw_spy):
    sprite = Block((90, 90, 4, 4))
    sprite.blendmode = pygame.BLEND_RGB_MULT
    plain = Block((95, 95, 4, 4))
    group.add(sprite, plain)
    group.draw(pygame.Surface(SIZE))
    (surfaces,) = draw_spy
    by_image = {s[0]: s for s in surfaces}
    assert by_image[sprite.image][3] == pygame.BLEND_RGB_MULT
    assert len(by_image[plain.image]) == 3


def test_layers_are_forwarded(group, draw_spy):
    a, b = Block((90, 90, 4, 4)), Block((92, 92, 4, 4))
    group.add(a, layer=3)
    group.add(b, layer=1)
    group.draw(pygame.Surface(SIZE))
    (surfaces,) = draw_spy
    layers = {s[0]: s[2] for s in surfaces}
    assert layers == {a.image: 3, b.image: 1}


def test_many_sprites(group):
    sprites = [Block((80 + (i % 10) * 4, 88 + (i // 10) * 2, 2, 2)) for i in range(100)]
    group.add(*sprites)
    surface = pygame.Surface(SIZE)
    group.draw(surface)
    assert len(group) == 100
