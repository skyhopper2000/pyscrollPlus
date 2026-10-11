"""
Headless rendering benchmark for pyscroll.

Measures frames/second of BufferedRenderer (and PyscrollGroup) in a few
typical situations, using the bundled apps/demo/desert.tmx map.

    python benchmarks/bench_render.py            # full run
    python benchmarks/bench_render.py --quick    # smoke run (CI / sanity)

Numbers are only comparable on the same machine and pygame build; compare a
branch against master by running both back to back.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pygame  # noqa: E402
from pytmx.util_pygame import load_pygame  # noqa: E402

from pyscroll.data import TiledMapData  # noqa: E402
from pyscroll.group import PyscrollGroup  # noqa: E402
from pyscroll.orthographic import BufferedRenderer  # noqa: E402

DEFAULT_MAP = REPO_ROOT / "apps" / "demo" / "desert.tmx"
FULL_FRAMES = 600
QUICK_FRAMES = 60
WARMUP_FRAMES = 10


def circle_path(center, radius, speed):
    """Endless smooth camera path: `speed` pixels per frame around a circle."""
    cx, cy = center
    step = speed / radius
    t = 0.0
    while True:
        yield cx + radius * math.cos(t), cy + radius * math.sin(t)
        t += step


def jump_path(map_px, view):
    """Endless path of far-apart points; every frame forces a full redraw."""
    w, h = map_px
    vw, vh = view
    xs = [vw // 2, w // 2, w - vw // 2]
    ys = [vh // 2, h // 2, h - vh // 2]
    points = [(x, y) for x in xs for y in ys]
    # reorder so consecutive points are never neighbours
    points = points[::2] + points[1::2]
    while True:
        yield from points


class Block(pygame.sprite.Sprite):
    def __init__(self, rect, color):
        super().__init__()
        self.image = pygame.Surface(rect.size)
        self.image.fill(color)
        self.rect = rect


def make_renderer(tmx, size, **kwargs):
    return BufferedRenderer(TiledMapData(tmx), size, **kwargs)


def scenario_scroll(tmx, size, **kwargs):
    renderer = make_renderer(tmx, size, **kwargs)
    path = circle_path(renderer.map_rect.center, 300, 3)
    surface = pygame.Surface(size)
    rect = surface.get_rect()

    def frame():
        renderer.center(next(path))
        renderer.draw(surface, rect)

    return frame


def scenario_jump(tmx, size):
    renderer = make_renderer(tmx, size)
    path = jump_path(renderer.map_rect.size, size)
    surface = pygame.Surface(size)
    rect = surface.get_rect()

    def frame():
        renderer.center(next(path))
        renderer.draw(surface, rect)

    return frame


def scenario_zoom(tmx, size, zoom=2.0):
    renderer = make_renderer(tmx, size)
    renderer.zoom = zoom
    path = circle_path(renderer.map_rect.center, 300, 3)
    surface = pygame.Surface(size)
    rect = surface.get_rect()

    def frame():
        renderer.center(next(path))
        renderer.draw(surface, rect)

    return frame


def scenario_sprites(tmx, size, count=200):
    renderer = make_renderer(tmx, size)
    group = PyscrollGroup(map_layer=renderer)
    rng = random.Random(1234)
    cx, cy = renderer.map_rect.center
    layers = list(TiledMapData(tmx).visible_tile_layers) or [0]
    for _ in range(count):
        rect = pygame.Rect(0, 0, 16, 24)
        rect.center = cx + rng.randint(-400, 400), cy + rng.randint(-400, 400)
        color = rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)
        # spread over all tile layers so the occlusion path is exercised
        group.add(Block(rect, color), layer=rng.choice(layers))
    path = circle_path((cx, cy), 300, 3)
    surface = pygame.Surface(size)

    def frame():
        group.center(next(path))
        group.draw(surface)

    return frame


def run(name, factory, frames):
    frame = factory()
    for _ in range(WARMUP_FRAMES):
        frame()
    start = time.perf_counter()
    for _ in range(frames):
        frame()
    elapsed = time.perf_counter() - start
    return name, frames, elapsed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--quick", action="store_true", help=f"{QUICK_FRAMES} frames per scenario")
    parser.add_argument("--frames", type=int, help=f"frames per scenario (default {FULL_FRAMES})")
    parser.add_argument("--size", default="800x600", help="view size, WxH (default 800x600)")
    parser.add_argument("--map", default=str(DEFAULT_MAP), help="TMX map to render")
    args = parser.parse_args(argv)

    frames = args.frames or (QUICK_FRAMES if args.quick else FULL_FRAMES)
    size = tuple(int(i) for i in args.size.lower().split("x"))

    pygame.init()
    pygame.display.set_mode((64, 64))  # pytmx needs a video mode to convert images
    tmx = load_pygame(args.map)

    scenarios = [
        ("scroll", lambda: scenario_scroll(tmx, size)),
        ("jump (forced redraw)", lambda: scenario_jump(tmx, size)),
        ("zoom 2.0", lambda: scenario_zoom(tmx, size, 2.0)),
        ("200 sprites (group)", lambda: scenario_sprites(tmx, size, 200)),
        ("alpha=True scroll", lambda: scenario_scroll(tmx, size, alpha=True)),
    ]

    print(
        f"pyscroll benchmark | pygame {pygame.version.ver} | SDL "
        f"{'.'.join(map(str, pygame.get_sdl_version()))} | Python {sys.version.split()[0]}"
    )
    print(f"map {Path(args.map).name} | view {size[0]}x{size[1]} | {frames} frames/scenario\n")
    header = f"{'scenario':<22} {'frames':>7} {'seconds':>9} {'fps':>9} {'ms/frame':>9}"
    print(header)
    print("-" * len(header))
    for name, factory in scenarios:
        name, n, elapsed = run(name, factory, frames)
        fps = n / elapsed if elapsed else float("inf")
        print(f"{name:<22} {n:>7} {elapsed:>9.3f} {fps:>9.1f} {1000 * elapsed / n:>9.3f}")

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
