"""
Shared pytest fixtures for the pyscroll test suite.

The SDL drivers are forced to "dummy" *before* pygame is imported anywhere,
so the whole suite runs headless (CI, SSH sessions, etc.).
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from pathlib import Path  # noqa: E402

import pygame  # noqa: E402
import pytest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO_ROOT / "apps" / "demo"
DISPLAY_SIZE = (320, 240)


@pytest.fixture(scope="session", autouse=True)
def pygame_session():
    """Initialise pygame once for the whole test session."""
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture(scope="session")
def display(pygame_session) -> pygame.Surface:
    """
    A (headless) display surface.

    Needed because pytmx's pygame loader and ``Surface.convert`` require a
    video mode to be set.
    """
    return pygame.display.set_mode(DISPLAY_SIZE)


def _load_tmx(name: str):
    from pytmx.util_pygame import load_pygame

    return load_pygame(str(DEMO_DIR / name))


@pytest.fixture
def desert_tmx(display):
    """apps/demo/desert.tmx loaded through pytmx (40x40 tiles of 32px)."""
    return _load_tmx("desert.tmx")


@pytest.fixture
def animated_tmx(display):
    """apps/demo/animated.tmx loaded through pytmx (15x15 tiles of 16px, animated)."""
    return _load_tmx("animated.tmx")


@pytest.fixture
def desert_data(desert_tmx):
    from pyscroll.data import TiledMapData

    return TiledMapData(desert_tmx)


@pytest.fixture
def animated_data(animated_tmx):
    from pyscroll.data import TiledMapData

    return TiledMapData(animated_tmx)
