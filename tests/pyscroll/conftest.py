from __future__ import annotations

import pygame
import pytest
from synthetic_map import SyntheticMapData

from pyscroll.orthographic import BufferedRenderer


@pytest.fixture
def tiny_map(display) -> SyntheticMapData:
    """4x4 tiles of 8px, two layers; layer 1 has tiles on the diagonal."""
    return SyntheticMapData(size=(4, 4), tile_size=(8, 8))


@pytest.fixture
def big_map(display) -> SyntheticMapData:
    """32x32 tiles of 8px (256x256 px) -- room to scroll around."""
    overlay = [(x, y) for x in range(32) for y in range(32) if (x + 2 * y) % 5 == 0]
    return SyntheticMapData(size=(32, 32), tile_size=(8, 8), overlay=overlay)


@pytest.fixture
def make_renderer():
    """Factory: make_renderer(data, size, **kwargs) -> BufferedRenderer."""

    def factory(data, size=(40, 24), **kwargs):
        return BufferedRenderer(data, size, **kwargs)

    return factory


@pytest.fixture
def screen():
    """Factory for an off-screen target surface, pre-filled with a colour."""

    def factory(size=(40, 24), fill=(0, 0, 0)):
        surface = pygame.Surface(size)
        surface.fill(fill)
        return surface

    return factory
