"""
Regression tests for the Phase 1 correctness fixes (B1-B6, B9).

Self-contained: runs headless under both unittest and pytest.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import importlib
import unittest
import warnings
from pathlib import Path

import pygame

import pyscroll
import pyscroll.common
from pyscroll.data import PyscrollDataAdapter, TiledMapData
from pyscroll.orthographic import BufferedRenderer

try:
    import pytmx
except ImportError:  # pragma: no cover
    pytmx = None

DEMO_DIR = Path(__file__).resolve().parents[2] / "apps" / "demo"
DESERT = DEMO_DIR / "desert.tmx"
ANIMATED = DEMO_DIR / "animated.tmx"


class FakeClock:
    """Manually advanced clock, in seconds."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class GridData(PyscrollDataAdapter):
    """Small in-memory adapter: one solid colored tile per cell."""

    tile_size = (16, 16)
    map_size = (8, 8)

    def __init__(self, layers=(0,)) -> None:
        super().__init__()
        self.visible_tile_layers = list(layers)
        self.tile = pygame.Surface(self.tile_size)
        self.tile.fill((10, 20, 30))
        self.reload_animations()

    def get_animations(self):
        return iter(())

    def _get_tile_image(self, x, y, l):
        if 0 <= x < self.map_size[0] and 0 <= y < self.map_size[1]:
            return self.tile
        return None


def setUpModule() -> None:
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


def surface_bytes(surface: pygame.Surface) -> bytes:
    return pygame.image.tobytes(surface, "RGB")


@unittest.skipIf(pytmx is None, "pytmx is required")
class TestZoomRatiosB1(unittest.TestCase):
    """B1: zoom passed to the constructor must compute the translate ratios."""

    size = (320, 240)

    def make(self, **kwargs) -> BufferedRenderer:
        data = TiledMapData(pytmx.load_pygame(str(DESERT)))
        return BufferedRenderer(data, self.size, **kwargs)

    def test_ctor_zoom_matches_setter_zoom(self) -> None:
        via_ctor = self.make(zoom=2)
        via_setter = self.make()
        via_setter.zoom = 2
        for renderer in (via_ctor, via_setter):
            renderer.center((400, 400))

        self.assertEqual(via_ctor.translate_point((400, 400)), (160, 120))
        self.assertEqual(via_setter.translate_point((400, 400)), (160, 120))

        rect = pygame.Rect(390, 380, 32, 48)
        points = [(400, 400), (420, 410)]
        self.assertEqual(via_ctor.translate_rect(rect), via_setter.translate_rect(rect))
        self.assertEqual(
            via_ctor.translate_points(points), via_setter.translate_points(points)
        )
        self.assertEqual(
            via_ctor.translate_rects([rect]), via_setter.translate_rects([rect])
        )

    def test_ratio_follows_set_size(self) -> None:
        renderer = self.make(zoom=2)
        renderer.set_size((640, 480))
        renderer.center((400, 400))
        self.assertEqual(renderer.translate_point((400, 400)), (320, 240))

    def test_zoom_out_ratio(self) -> None:
        renderer = self.make(zoom=0.5)
        renderer.center((400, 400))
        self.assertEqual(renderer.translate_point((400, 400)), (160, 120))
        self.assertEqual(renderer.translate_point((410, 400)), (165, 120))


@unittest.skipIf(pytmx is None, "pytmx is required")
class TestTimeSourceB3(unittest.TestCase):
    """B3: the renderer's time_source drives tile animations."""

    def setUp(self) -> None:
        self.clock = FakeClock(100.0)
        self.data = TiledMapData(pytmx.load_pygame(str(ANIMATED)))
        self.renderer = BufferedRenderer(
            self.data, (240, 240), time_source=self.clock
        )
        self.renderer.center((120, 120))
        self.surface = pygame.Surface((240, 240))

    def draw(self) -> bytes:
        self.renderer.draw(self.surface, self.surface.get_rect())
        return surface_bytes(self.surface)

    def test_time_source_installed_on_adapter(self) -> None:
        self.assertIs(self.data.time_source, self.clock)
        self.assertIs(self.renderer.time_source, self.clock)

    def test_animations_follow_fake_clock(self) -> None:
        first = self.draw()

        # the clock does not move: nothing may animate, however often we draw
        for _ in range(3):
            self.assertEqual(self.draw(), first)

        # animated.tmx frames last 500ms
        self.clock.now += 0.6
        second = self.draw()
        self.assertNotEqual(second, first)

        # frozen again
        self.assertEqual(self.draw(), second)

        self.clock.now += 0.6
        self.assertNotEqual(self.draw(), second)

    def test_replacing_time_source_rebases_schedule(self) -> None:
        self.draw()
        other = FakeClock(5000.0)
        self.renderer.time_source = other
        self.assertIs(self.data.time_source, other)
        before = self.draw()
        self.assertEqual(self.draw(), before)
        other.now += 0.6
        self.assertNotEqual(self.draw(), before)

    def test_adapter_without_super_init_uses_class_clock(self) -> None:
        class Bare(PyscrollDataAdapter):
            def __init__(self) -> None:  # intentionally skips super().__init__
                pass

        bare = Bare()
        bare._update_time()
        self.assertIsInstance(bare._last_time, float)
        clock = FakeClock(2.0)
        bare.set_time_source(clock)
        bare._update_time()
        self.assertEqual(bare._last_time, 2000.0)


@unittest.skipIf(pytmx is None, "pytmx is required")
class TestRedrawKeepsAnimationsB4(unittest.TestCase):
    """B4: a full redraw must not reset animated tiles to their base frame."""

    def setUp(self) -> None:
        self.clock = FakeClock(0.0)
        self.data = TiledMapData(pytmx.load_pygame(str(ANIMATED)))

    def assert_in_sync(self) -> int:
        """Every tracked animated tile shows its animation's current frame."""
        tracked = 0
        for token in self.data._animation_map.values():
            current = token.frames[token.index].image
            for position in token.positions:
                tracked += 1
                self.assertIs(self.data.get_tile_image(*position), current)
        return tracked

    def test_full_redraw_and_zoom_keep_frames(self) -> None:
        renderer = BufferedRenderer(self.data, (240, 240), time_source=self.clock)
        renderer.center((120, 120))
        surface = pygame.Surface((240, 240))
        renderer.draw(surface, surface.get_rect())
        base = surface_bytes(surface)

        self.clock.now += 0.6
        renderer.draw(surface, surface.get_rect())
        advanced = surface_bytes(surface)
        self.assertNotEqual(advanced, base)

        renderer.redraw_tiles(renderer._buffer)
        renderer.draw(surface, surface.get_rect())
        self.assertEqual(surface_bytes(surface), advanced)

        renderer.zoom = 2
        renderer.zoom = 1
        renderer.center((120, 120))
        renderer.draw(surface, surface.get_rect())
        self.assertEqual(surface_bytes(surface), advanced)
        self.assertGreater(self.assert_in_sync(), 0)

    def test_tiles_entering_view_use_current_frame(self) -> None:
        # small view: animated tiles leave the buffer, their animation advances
        # while they are off screen, then they re-enter through a full redraw
        renderer = BufferedRenderer(self.data, (64, 64), time_source=self.clock)
        surface = pygame.Surface((64, 64))
        positions = [(120, 120), (200, 32), (120, 120), (32, 200), (120, 120)]
        tracked = 0
        for step in range(10):
            renderer.center(positions[step % len(positions)])  # fast scroll
            renderer.draw(surface, surface.get_rect())
            tracked += self.assert_in_sync()
            self.clock.now += 0.6
            renderer.draw(surface, surface.get_rect())
            tracked += self.assert_in_sync()
        self.assertGreater(tracked, 0)

    def test_reload_animations_drops_stale_substitutions(self) -> None:
        renderer = BufferedRenderer(self.data, (240, 240), time_source=self.clock)
        renderer.center((120, 120))
        surface = pygame.Surface((240, 240))
        renderer.draw(surface, surface.get_rect())
        self.clock.now += 0.6
        renderer.draw(surface, surface.get_rect())
        self.assertTrue(self.data._animated_tile)
        stale = dict(self.data._animated_tile)

        self.data.reload_animations()
        for position, image in stale.items():
            self.assertNotIn(position, self.data._animated_tile)
        renderer.redraw_tiles(renderer._buffer)
        self.assert_in_sync()


class TestNoVisibleTileLayersB5(unittest.TestCase):
    """B5: drawing surfaces with no visible tile layers must not raise."""

    def test_draw_surfaces_without_tile_layers(self) -> None:
        data = GridData(layers=())
        renderer = BufferedRenderer(data, (64, 64))
        renderer.center((64, 64))
        sprite = pygame.Surface((8, 8))
        sprite.fill((255, 0, 0))
        target = pygame.Surface((64, 64))
        renderer.draw(target, target.get_rect(), [(sprite, pygame.Rect(4, 4, 8, 8), 0)])
        self.assertEqual(tuple(target.get_at((6, 6)))[:3], (255, 0, 0))

    def test_surfaces_tuple_order_with_blend_flags(self) -> None:
        # B6: surfaces are (surface, rect, layer[, blend_flags])
        data = GridData(layers=(0,))
        renderer = BufferedRenderer(data, (64, 64))
        renderer.center((64, 64))
        sprite = pygame.Surface((8, 8))
        sprite.fill((100, 0, 0))
        target = pygame.Surface((64, 64))
        surfaces = [(sprite, pygame.Rect(4, 4, 8, 8), 1, pygame.BLEND_RGB_ADD)]
        renderer.draw(target, target.get_rect(), surfaces)
        self.assertEqual(tuple(target.get_at((6, 6)))[:3], (110, 20, 30))


class TestIsometricNotExportedB2(unittest.TestCase):
    """B2: the broken isometric renderer is no longer exported."""

    def test_not_exported(self) -> None:
        self.assertFalse(hasattr(pyscroll, "IsometricBufferedRenderer"))

    def test_helpers_still_importable(self) -> None:
        iso = importlib.import_module("pyscroll.isometric")
        self.assertEqual(iso.vector2_to_iso((2, 1)), (1, 1))
        self.assertEqual(iso.vector3_to_iso((2, 1, 1)), (1, 0))

    def test_instantiation_warns(self) -> None:
        iso = importlib.import_module("pyscroll.isometric")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                iso.IsometricBufferedRenderer(GridData(), (64, 64))
            except Exception:
                pass  # known to be non-functional
        self.assertTrue(
            any("experimental" in str(w.message) for w in caught),
            [str(w.message) for w in caught],
        )


class TestRectDifferenceRemovedB9(unittest.TestCase):
    def test_removed(self) -> None:
        self.assertFalse(hasattr(pyscroll.common, "rect_difference"))


if __name__ == "__main__":
    unittest.main()
