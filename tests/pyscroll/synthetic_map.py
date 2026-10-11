"""
A tiny, fully synthetic map for pixel-exact tests.

Every tile is a solid colour that encodes its position and layer, so the
expected colour of any screen pixel can be computed analytically -- no
golden image files, no Tiled dependency.

Layer 0 is fully populated.  Layer 1 only has tiles at ``overlay``
positions (the diagonal by default).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pygame

from pyscroll.common import rect_to_bb
from pyscroll.data import PyscrollDataAdapter

Color = tuple[int, int, int]
Position = tuple[int, int]
CLEAR = (0, 0, 0)


def layer0_color(x: int, y: int) -> Color:
    return 20 + x * 7, 20 + y * 7, 60


def layer1_color(x: int, y: int) -> Color:
    return 230, 20 + x * 7, 20 + y * 7


class SyntheticMapData(PyscrollDataAdapter):
    """
    Data adapter with solid-colour tiles.

    Args:
        size: map size in tiles
        tile_size: tile size in pixels
        overlay: positions that have a layer-1 tile (default: diagonal)
        visible_layers: which tile layers are visible
        animations: {(x, y, layer): [(color, duration_ms), ...]}; the tile at
            that position cycles through the given colours.
    """

    def __init__(
        self,
        size: tuple[int, int] = (4, 4),
        tile_size: tuple[int, int] = (8, 8),
        overlay: Iterable[Position] | None = None,
        visible_layers: Iterable[int] = (0, 1),
        animations: dict | None = None,
    ) -> None:
        super().__init__()
        self.map_size = tuple(size)
        self.tile_size = tuple(tile_size)
        w, h = self.map_size
        if overlay is None:
            overlay = [(i, i) for i in range(min(w, h))]
        self.overlay = set(overlay)
        self.visible_tile_layers = list(visible_layers)
        self.animations = dict(animations or {})
        self.color_funcs: dict[int, Callable[[int, int], Color]] = {
            0: layer0_color,
            1: layer1_color,
        }
        self.reload_data()
        self.reload_animations()

    # ------------------------------------------------------------------
    # construction helpers

    def _new_image(self, color: Color) -> pygame.Surface:
        image = pygame.Surface(self.tile_size)
        image.fill(color)
        self.images.append(image)
        return len(self.images) - 1

    def reload_data(self) -> None:
        w, h = self.map_size
        self.images: list[pygame.Surface | None] = [None]  # gid 0 == empty
        self.layers: dict[int, list[list[int]]] = {}
        for layer in (0, 1):
            rows = []
            for y in range(h):
                row = []
                for x in range(w):
                    if layer == 0 or (x, y) in self.overlay:
                        row.append(self._new_image(self.color_funcs[layer](x, y)))
                    else:
                        row.append(0)
                rows.append(row)
            self.layers[layer] = rows

        # animated tiles: the tile's own gid becomes the first frame
        self._animation_frames: dict[int, list[tuple[int, int]]] = {}
        for (x, y, layer), frames in self.animations.items():
            gids = [self._new_image(color) for color, _ in frames]
            self.layers[layer][y][x] = gids[0]
            self._animation_frames[gids[0]] = [
                (gid, duration) for gid, (_, duration) in zip(gids, frames)
            ]

    # ------------------------------------------------------------------
    # PyscrollDataAdapter API

    def get_animations(self):
        return list(self._animation_frames.items())

    def convert_surfaces(self, parent: pygame.Surface, alpha: bool = False) -> None:
        # parent is unused: passing a surface to convert_alpha() is
        # deprecated in pygame-ce >= 2.4
        self.images = [
            None if i is None else (i.convert_alpha() if alpha else i.convert())
            for i in self.images
        ]

    def _gid(self, x: int, y: int, layer: int) -> int:
        w, h = self.map_size
        if 0 <= x < w and 0 <= y < h and layer in self.layers:
            return self.layers[layer][y][x]
        return 0

    def _get_tile_image(self, x: int, y: int, l: int):
        return self.images[self._gid(x, y, l)]

    def _get_tile_image_by_id(self, id):
        return self.images[id]

    def get_tile_images_by_rect(self, rect):
        # mirrors TiledMapData: registers positions of animated tiles
        x1, y1, x2, y2 = rect_to_bb(rect)
        track = bool(self._animation_queue)
        for layer in self.visible_tile_layers:
            for y in range(y1, y2 + 1):
                for x in range(x1, x2 + 1):
                    gid = self._gid(x, y, layer)
                    if not gid:
                        continue
                    if track and gid in self._tracked_gids:
                        self._animation_map[gid].positions.add((x, y, layer))
                    tile = self._animated_tile.get((x, y, layer), self.images[gid])
                    if tile:
                        yield x, y, layer, tile

    # ------------------------------------------------------------------
    # expectations

    def expected_world_color(self, wx: int, wy: int, clear: Color = CLEAR) -> Color:
        """Colour the map *should* have at world pixel (wx, wy)."""
        tw, th = self.tile_size
        x, y = wx // tw, wy // th
        w, h = self.map_size
        if wx < 0 or wy < 0 or not (0 <= x < w and 0 <= y < h):
            return clear
        for layer in sorted(self.visible_tile_layers, reverse=True):
            gid = self._gid(x, y, layer)
            if gid:
                return tuple(self.images[gid].get_at((0, 0)))[:3]
        return clear


def screen_colors(surface: pygame.Surface, rect: pygame.Rect | None = None):
    """Return {(sx, sy): (r, g, b)} for every pixel in ``rect``."""
    rect = rect or surface.get_rect()
    return {
        (sx, sy): tuple(surface.get_at((sx, sy)))[:3]
        for sx in range(rect.left, rect.right)
        for sy in range(rect.top, rect.bottom)
    }


def expected_screen(
    data: SyntheticMapData,
    view_rect: pygame.Rect,
    screen_size: tuple[int, int],
    scale: int = 1,
    clear: Color = CLEAR,
):
    """
    Expected colours for a renderer whose ``view_rect`` is given.

    ``scale`` is the integer zoom factor (nearest-neighbour scaling).
    """
    sw, sh = screen_size
    return {
        (sx, sy): data.expected_world_color(
            view_rect.left + sx // scale, view_rect.top + sy // scale, clear
        )
        for sx in range(sw)
        for sy in range(sh)
    }


def diff(actual: dict, expected: dict, limit: int = 10) -> list:
    """Small, readable list of mismatching pixels for assertion messages."""
    out = []
    for key in sorted(expected):
        if actual.get(key) != expected[key]:
            out.append((key, actual.get(key), expected[key]))
            if len(out) >= limit:
                break
    return out
