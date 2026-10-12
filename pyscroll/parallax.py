"""
Parallax scrolling by composing several BufferedRenderers.

The speed of :class:`~pyscroll.orthographic.BufferedRenderer` comes from a
single scrolling tile buffer.  Giving each layer its own offset inside that
buffer would defeat it, so parallax is built by *composition* instead:

* :class:`LayerFilter` narrows a data adapter to a subset of its tile layers.
* Each tile :class:`Band` gets its own ``BufferedRenderer`` over a
  ``LayerFilter``.  The bottom band is opaque, the others use per-pixel alpha.
* :class:`ImageBand` draws a (optionally repeating) image, no tile buffer.
* :class:`ParallaxRenderer` centers every band at
  ``origin + (camera - origin) * factor`` and draws them back to front.

``ParallaxRenderer`` implements the same surface as ``BufferedRenderer`` that
:class:`~pyscroll.group.PyscrollGroup` relies on, so it can be passed as the
group's ``map_layer`` unchanged.

Example::

    from pyscroll.parallax import Band, ImageBand, ParallaxRenderer

    renderer = ParallaxRenderer(
        data,
        screen.get_size(),
        bands=[  # back to front
            ImageBand(sky, factor=(0.1, 0.0), repeat_x=True),
            Band(layers=[0], factor=(0.5, 0.5)),
            Band(layers=[1, 2], sprites=True),
            Band(layers=[3], factor=(1.25, 1.0)),
        ],
    )
    group = PyscrollGroup(map_layer=renderer)

Or, for maps made with Tiled >= 1.5::

    renderer = ParallaxRenderer.from_tiled(load_pygame("map.tmx"), size)

This module is not exported from ``pyscroll`` yet; import it directly.

"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Optional, Union
from xml.etree import ElementTree

import pygame
from pygame import Rect, Surface

from .common import (
    RectLike,
    Vector2D,
    Vector2DInt,
    rect_to_bb,
    surface_clipping_context,
)
from .data import PyscrollDataAdapter, TiledMapData
from .orthographic import BufferedRenderer

try:
    # optional pytmx support
    import pytmx
except ImportError:  # pragma: no cover
    pytmx = None

log = logging.getLogger(__file__)

__all__ = (
    "Band",
    "ImageBand",
    "LayerFilter",
    "ParallaxRenderer",
)

Factor = Union[float, tuple[float, float]]


def _as_factor(value: Factor) -> tuple[float, float]:
    """Normalize a scalar or pair to an ``(x, y)`` float pair."""
    if isinstance(value, (int, float)):
        return float(value), float(value)
    x, y = value
    return float(x), float(y)


class LayerFilter(PyscrollDataAdapter):
    """
    Data adapter wrapper that exposes only some tile layers of another adapter.

    ``visible_tile_layers`` is the wrapped adapter's visible layers intersected
    with ``layers`` (in the wrapped adapter's order, re-evaluated on each access
    so toggling visibility on the source still works).  Layer numbers are *not*
    renumbered, so sprite layers passed to the renderer keep their meaning.

    Animations: animation state (tokens, current frames, tracked positions)
    lives on the adapter, and the renderer advances it through
    ``process_animation_queue``.  If several bands shared the wrapped adapter's
    queue, the first band to draw would consume every frame change and the
    others would never see it.  So each ``LayerFilter`` keeps its *own*
    animation queue, built from the wrapped adapter's ``get_animations``, and
    only records token positions ``(x, y, layer)`` for its own layers.  The
    wrapped adapter's animation queue is left alone (it is not advanced).

    Tile lookup paths, fastest first:

    * :class:`~pyscroll.data.TiledMapData`: reads ``tmx.layers[l].data``
      directly, mirroring ``TiledMapData.get_tile_images_by_rect``.
    * adapters using the default ``get_tile_images_by_rect``: per-tile lookups
      over the filtered layers only.
    * adapters with a custom batch ``get_tile_images_by_rect`` (e.g.
      ``MapAggregator``): the batch output is filtered by layer.

    Any other attribute (e.g. ``tmx``) is forwarded to the wrapped adapter.

    Args:
        data: adapter to wrap
        layers: tile layer numbers to expose

    """

    def __init__(self, data: PyscrollDataAdapter, layers: Iterable[int]) -> None:
        super().__init__()
        self._data = data
        self.layers = frozenset(layers)
        self.reload_animations()

    def __getattr__(self, item: str) -> Any:
        # only called when normal lookup fails; guard against recursion
        # before _data exists (e.g. during unpickling)
        if item == "_data":
            raise AttributeError(item)
        return getattr(self._data, item)

    def __repr__(self) -> str:
        return f"<LayerFilter {sorted(self.layers)} of {self._data!r}>"

    @property
    def source(self) -> PyscrollDataAdapter:
        """The wrapped data adapter."""
        return self._data

    @property
    def tile_size(self) -> Vector2DInt:
        return self._data.tile_size

    @property
    def map_size(self) -> Vector2DInt:
        return self._data.map_size

    @property
    def visible_tile_layers(self) -> list[int]:
        layers = self.layers
        return [l for l in self._data.visible_tile_layers if l in layers]

    def reload_data(self) -> None:
        """Reload the wrapped adapter's data, then this filter's animations."""
        self._data.reload_data()
        self.reload_animations()

    def get_animations(self):
        try:
            animations = self._data.get_animations()
        except NotImplementedError:
            return ()
        return animations or ()

    def convert_surfaces(self, parent: Surface, alpha: bool = False) -> None:
        convert = getattr(self._data, "convert_surfaces", None)
        if convert is not None:
            convert(parent, alpha)

    def prepare_tiles(self, tiles: RectLike):
        return self._data.prepare_tiles(tiles)

    def _get_tile_image(self, x: int, y: int, l: int) -> Optional[Surface]:
        if l not in self.layers:
            return None
        return self._data._get_tile_image(x, y, l)

    def _get_tile_image_by_id(self, id) -> Surface:
        return self._data._get_tile_image_by_id(id)

    def get_tile_images_by_rect(
        self, rect: RectLike
    ) -> Iterator[tuple[int, int, int, Surface]]:
        if isinstance(self._data, TiledMapData):
            return self._tiled_tile_images_by_rect(rect)
        method = type(self._data).get_tile_images_by_rect
        if method is PyscrollDataAdapter.get_tile_images_by_rect:
            # default per-tile lookup, but only over our layers
            return PyscrollDataAdapter.get_tile_images_by_rect(self, rect)
        return self._filtered_tile_images_by_rect(rect)

    def _filtered_tile_images_by_rect(self, rect: RectLike):
        layers = self.layers
        at = self._animated_tile
        for x, y, l, tile in self._data.get_tile_images_by_rect(rect):
            if l in layers:
                yield x, y, l, at.get((x, y, l), tile)

    def _tiled_tile_images_by_rect(self, rect: RectLike):
        # mirrors TiledMapData.get_tile_images_by_rect, with our own
        # animation bookkeeping and only our layers
        def rev(seq, start, stop):
            if start < 0:
                start = 0
            return enumerate(seq[start : stop + 1], start)

        x1, y1, x2, y2 = rect_to_bb(rect)
        tmx = self._data.tmx
        images = tmx.images
        tmx_layers = tmx.layers
        at = self._animated_tile
        tracked_gids = self._tracked_gids
        anim_map = self._animation_map
        track = bool(self._animation_queue)

        for l in self.visible_tile_layers:
            for y, row in rev(tmx_layers[l].data, y1, y2):
                for x, gid in [i for i in rev(row, x1, x2) if i[1]]:
                    if track and gid in tracked_gids:
                        anim_map[gid].positions.add((x, y, l))
                    try:
                        tile = at[(x, y, l)]
                    except KeyError:
                        tile = images[gid]
                    if tile:
                        yield x, y, l, tile


@dataclass
class Band:
    """
    A group of tile layers that scroll together.

    Attributes:
        layers: tile layer numbers drawn by this band
        factor: scroll speed relative to the camera, as ``(x, y)`` or a single
            float for both axes.  ``1.0`` moves with the camera, ``0.5`` at half
            speed (further away), ``> 1`` faster (foreground), ``0`` is fixed.
        sprites: if True, sprites are drawn in this band and interleave with
            its tiles.  Exactly one band per renderer must set this.

    """

    layers: Sequence[int]
    factor: Factor = (1.0, 1.0)
    sprites: bool = False

    def __post_init__(self) -> None:
        self.layers = tuple(self.layers)
        self.factor = _as_factor(self.factor)
        if not self.layers:
            raise ValueError("Band needs at least one layer")


@dataclass
class ImageBand:
    """
    A single image, optionally repeated, scrolling with a parallax factor.

    Attributes:
        surface: image to draw
        factor: scroll speed relative to the camera, see :class:`Band`
        repeat_x: tile the image horizontally to fill the view
        repeat_y: tile the image vertically to fill the view
        offset: position of the image's top-left corner, in the band's
            world pixels

    """

    surface: Surface
    factor: Factor = (1.0, 1.0)
    repeat_x: bool = False
    repeat_y: bool = False
    offset: Vector2D = (0, 0)

    def __post_init__(self) -> None:
        self.factor = _as_factor(self.factor)

    def draw(self, surface: Surface, rect: Rect, topleft: Vector2D) -> None:
        """
        Draw the image so that band world pixel ``topleft`` is at ``rect``'s
        top-left corner.

        Args:
            surface: destination
            rect: area of the destination to fill
            topleft: band world coordinates shown at the top-left of ``rect``

        """
        iw, ih = self.surface.get_size()
        if iw == 0 or ih == 0:
            return
        x = round(self.offset[0] - topleft[0]) + rect.left
        y = round(self.offset[1] - topleft[1]) + rect.top
        if self.repeat_x:
            x = rect.left + (x - rect.left) % iw - iw
            xs = range(x, rect.right, iw)
        else:
            xs = (x,)
        if self.repeat_y:
            y = rect.top + (y - rect.top) % ih - ih
            ys = range(y, rect.bottom, ih)
        else:
            ys = (y,)
        image = self.surface
        with surface_clipping_context(surface, rect):
            surface.blits([(image, (bx, by)) for by in ys for bx in xs], False)


class _BandRenderer(BufferedRenderer):
    """
    BufferedRenderer that never clears the *destination* surface.

    When the camera is not clamped, ``BufferedRenderer`` fills the area of
    its previous blit on the destination before drawing.  For a band that sits
    on top of other bands that would erase them (and for an alpha band it
    fills with opaque black, since the destination has no alpha).
    ``ParallaxRenderer`` clears the destination once per frame instead.
    The internal tile buffer is still cleared as normal.

    """

    def _clear_surface(self, surface: Surface, area: RectLike = None) -> None:
        if surface is self._buffer:
            super()._clear_surface(surface, area)


class _TileLayer:
    """Runtime state of one tile band."""

    __slots__ = ("band", "data", "renderer")

    def __init__(self, band: Band, data: LayerFilter, renderer: _BandRenderer):
        self.band = band
        self.data = data
        self.renderer = renderer


class ParallaxRenderer:
    """
    Renderer that composes one BufferedRenderer per parallax band.

    Bands are given back to front and may mix :class:`Band` (tile layers) and
    :class:`ImageBand` (images).  Every tile band gets its own
    ``BufferedRenderer``; the bottom-most tile band is opaque when nothing is
    behind it, every other tile band uses per-pixel alpha.  Cost: one extra
    full-view alpha blit per band, plus one buffer per band.

    Centering: for a camera position ``c`` each band is centered at
    ``origin + (c - origin) * factor``.  ``origin`` is the camera position at
    which all bands line up exactly (Tiled's "parallax origin").  With the
    default ``(0, 0)`` bands are aligned at the map's top-left corner *when
    the view is centered there*; pass ``origin=(view_w / 2, view_h / 2)`` to
    have them line up when the view shows the top-left corner of the map.

    Sprites: exactly one band has ``sprites=True``.  Its factor must be
    ``(1, 1)``; sprite world coordinates, ``view_rect``,
    ``get_center_offset`` and the ``translate_*`` methods all refer to it.
    Surfaces passed to :meth:`draw` go only to that band, so its tiles still
    occlude sprites as with a plain ``BufferedRenderer``; bands after it in
    the list are drawn over sprites.

    Clamping (``clamp_camera=True``):

    * The camera is clamped by the sprite band, exactly like a
      ``BufferedRenderer``; other bands are positioned from the *clamped*
      camera, so all bands stop together at the map edge.
    * Every other tile band then also clamps to its own map rect.  A band
      whose computed center would expose an edge stops at that edge instead
      (it "pins" while the others keep moving) rather than showing void.  With
      ``factor < 1`` and a suitable origin this never happens; with
      ``factor > 1`` it happens near the far edges.
    * Image bands are never clamped; use ``repeat_x``/``repeat_y`` to cover
      the view.

    With ``clamp_camera=False`` nothing is clamped and the view is cleared to
    ``background_color`` each frame.

    Zoom: band renderers always run at zoom 1.0 at the unzoomed view size.
    They are composed into one buffer that is scaled once, so zoom costs one
    scale per frame regardless of band count (and avoids scaling alpha bands).

    Args:
        data: map data adapter; every band reads from it through a LayerFilter
        size: size of the view in pixels
        bands: Band and ImageBand objects, back to front
        clamp_camera: if True, the camera cannot scroll past the map edges
        origin: camera position where all bands are aligned
        zoom: initial zoom, see :attr:`zoom`
        scaling_function: used to scale the composed view when zoomed
        sprite_damage_height: passed to the sprite band's BufferedRenderer
        background_color: fill color when parts of the view are not covered

    """

    def __init__(
        self,
        data: PyscrollDataAdapter,
        size: Vector2DInt,
        bands: Sequence[Union[Band, ImageBand]],
        clamp_camera: bool = True,
        origin: Vector2D = (0, 0),
        zoom: float = 1.0,
        scaling_function: Callable = pygame.transform.scale,
        sprite_damage_height: int = 0,
        background_color=(0, 0, 0),
    ) -> None:
        self.data = data
        self.clamp_camera = clamp_camera
        self.origin = float(origin[0]), float(origin[1])
        self.scaling_function = scaling_function
        self.background_color = background_color
        self.bands = list(bands)
        self._size = tuple(size)
        if zoom <= 0:
            raise ValueError("zoom level cannot be zero or less")
        self._zoom_level = zoom
        self._zoom_buffer: Optional[Surface] = None
        self._real_ratio_x = 1.0
        self._real_ratio_y = 1.0
        # (band, _TileLayer or None, band camera center)
        self._layers: list[list[Any]] = []

        sprite_band = self._validate_bands(self.bands)
        buffer_size = self._buffer_size
        visible = set(data.visible_tile_layers)
        opaque_bottom = isinstance(self.bands[0], Band)

        for index, band in enumerate(self.bands):
            if isinstance(band, ImageBand):
                self._layers.append([band, None, (0.0, 0.0)])
                continue
            if not visible.intersection(band.layers):
                if band is sprite_band:
                    raise ValueError(
                        f"sprite band has no visible tile layers: {band.layers}"
                    )
                log.warning("band %s has no visible tile layers", band.layers)
            band_data = LayerFilter(data, band.layers)
            renderer = _BandRenderer(
                band_data,
                buffer_size,
                clamp_camera=clamp_camera,
                alpha=not (index == 0 and opaque_bottom),
                sprite_damage_height=sprite_damage_height if band.sprites else 0,
            )
            tile_layer = _TileLayer(band, band_data, renderer)
            if band is sprite_band:
                self._sprite_layer = tile_layer
            self._layers.append([band, tile_layer, (0.0, 0.0)])

        # only an opaque tile band at the bottom with a clamped camera is
        # guaranteed to cover the whole view
        self._needs_clear = not (opaque_bottom and clamp_camera)

        self._init_zoom_buffer()
        self.center(self._sprite_renderer.view_rect.center)

    @staticmethod
    def _validate_bands(bands: Sequence[Union[Band, ImageBand]]) -> Band:
        if not bands:
            raise ValueError("at least one band is required")
        for band in bands:
            if not isinstance(band, (Band, ImageBand)):
                raise TypeError(f"expected Band or ImageBand, got {band!r}")
        sprite_bands = [b for b in bands if isinstance(b, Band) and b.sprites]
        if len(sprite_bands) != 1:
            raise ValueError(
                f"exactly one Band must have sprites=True, got {len(sprite_bands)}"
            )
        sprite_band = sprite_bands[0]
        if sprite_band.factor != (1.0, 1.0):
            raise ValueError(
                f"the sprite band must have factor (1, 1), got {sprite_band.factor}"
            )
        seen: set[int] = set()
        for band in bands:
            if isinstance(band, Band):
                dupes = seen.intersection(band.layers)
                if dupes:
                    log.warning("layers %s are drawn by more than one band", dupes)
                seen.update(band.layers)
        return sprite_band

    # ------------------------------------------------------------------ #
    # construction from Tiled
    # ------------------------------------------------------------------ #

    @classmethod
    def from_tiled(
        cls,
        tmx,
        size: Vector2DInt,
        sprite_layer: Optional[int] = None,
        **kwargs,
    ) -> ParallaxRenderer:
        """
        Build a renderer from a Tiled map's layer parallax settings.

        Consecutive visible tile layers with equal ``parallaxx``/``parallaxy``
        are grouped into one :class:`Band`.  Visible image layers become
        :class:`ImageBand` objects using ``repeatx``/``repeaty`` and
        ``offsetx``/``offsety``.  Object layers are ignored and do not split
        bands.  The map's ``parallaxoriginx``/``parallaxoriginy`` become
        ``origin`` unless ``origin`` is passed.

        pytmx keeps these attributes as strings (or omits them), so they are
        cast here.  pytmx also stores layers grouped by type, not in document
        order, so the document order is recovered by re-reading the file.
        Group layer parallax factors and layer opacity are not applied.

        Args:
            tmx: ``pytmx.TiledMap`` or ``TiledMapData``
            size: size of the view in pixels
            sprite_layer: tile layer number whose band gets the sprites.
                Default: the first band with factor ``(1, 1)``.
            **kwargs: passed to :class:`ParallaxRenderer`

        """
        if isinstance(tmx, TiledMapData):
            data = tmx
            tmx = data.tmx
        else:
            data = TiledMapData(tmx)

        bands: list[Union[Band, ImageBand]] = []
        index_of = {id(layer): i for i, layer in enumerate(tmx.layers)}
        current: Optional[Band] = None
        for layer in _document_layer_order(tmx):
            if not _to_bool(getattr(layer, "visible", True)):
                continue
            factor = (
                _float_attr(layer, "parallaxx", 1.0),
                _float_attr(layer, "parallaxy", 1.0),
            )
            if isinstance(layer, pytmx.TiledTileLayer):
                index = index_of[id(layer)]
                if current is not None and current.factor == factor:
                    current.layers = current.layers + (index,)
                else:
                    current = Band(layers=[index], factor=factor)
                    bands.append(current)
            elif isinstance(layer, pytmx.TiledImageLayer):
                current = None
                image = layer.image
                if image is None:
                    log.warning("image layer %r has no image", layer.name)
                    continue
                bands.append(
                    ImageBand(
                        image,
                        factor=factor,
                        repeat_x=_to_bool(getattr(layer, "repeatx", False)),
                        repeat_y=_to_bool(getattr(layer, "repeaty", False)),
                        offset=(
                            _float_attr(layer, "offsetx", 0.0),
                            _float_attr(layer, "offsety", 0.0),
                        ),
                    )
                )

        tile_bands = [b for b in bands if isinstance(b, Band)]
        if sprite_layer is not None:
            candidates = [b for b in tile_bands if sprite_layer in b.layers]
        else:
            candidates = [b for b in tile_bands if b.factor == (1.0, 1.0)]
        if not candidates:
            raise ValueError(
                "no tile band for sprites: need a visible tile layer with "
                "parallax factor (1, 1) or a valid sprite_layer"
            )
        candidates[0].sprites = True

        if "origin" not in kwargs:
            kwargs["origin"] = (
                _float_attr(tmx, "parallaxoriginx", 0.0),
                _float_attr(tmx, "parallaxoriginy", 0.0),
            )
        return cls(data, size, bands, **kwargs)

    # ------------------------------------------------------------------ #
    # renderer interface used by PyscrollGroup
    # ------------------------------------------------------------------ #

    @property
    def _sprite_renderer(self) -> BufferedRenderer:
        return self._sprite_layer.renderer

    @property
    def sprite_renderer(self) -> BufferedRenderer:
        """The BufferedRenderer of the sprite band."""
        return self._sprite_layer.renderer

    @property
    def renderers(self) -> list[BufferedRenderer]:
        """BufferedRenderer of each tile band, back to front."""
        return [entry[1].renderer for entry in self._layers if entry[1]]

    @property
    def view_rect(self) -> Rect:
        """Visible area of the map in world pixels (of the sprite band)."""
        return self._sprite_renderer.view_rect

    @property
    def map_rect(self) -> Rect:
        """Size of the map in pixels."""
        return self._sprite_renderer.map_rect

    def band_center(self, band: Union[Band, ImageBand]) -> tuple[float, float]:
        """
        Return the camera center of a band, before that band's own clamping.

        Args:
            band: one of :attr:`bands`

        """
        for entry in self._layers:
            if entry[0] is band:
                return entry[2]
        raise ValueError(f"{band!r} is not a band of this renderer")

    def center(self, coords: Vector2D) -> None:
        """
        Center the camera on a world pixel.

        The sprite band is centered (and clamped) first; every other band is
        centered at ``origin + (camera - origin) * factor`` using the clamped
        camera.  Tile bands then apply their own clamping.

        Args:
            coords: x, y

        """
        sprite = self._sprite_renderer
        sprite.center(coords)
        if self.clamp_camera:
            cx, cy = sprite.view_rect.center
        else:
            cx, cy = coords[0], coords[1]
        ox, oy = self.origin
        for entry in self._layers:
            band, tile_layer = entry[0], entry[1]
            fx, fy = band.factor
            bc = ox + (cx - ox) * fx, oy + (cy - oy) * fy
            entry[2] = bc
            if tile_layer is not None and tile_layer.renderer is not sprite:
                tile_layer.renderer.center(bc)

    def scroll(self, vector: Vector2DInt) -> None:
        """
        Scroll the camera in pixels.

        Args:
            vector: x, y

        """
        cx, cy = self.view_rect.center
        self.center((cx + vector[0], cy + vector[1]))

    def get_center_offset(self) -> Vector2DInt:
        """Return x, y pair that will change world coords to screen coords."""
        return self._sprite_renderer.get_center_offset()

    def draw(
        self, surface: Surface, rect: RectLike, surfaces: Optional[list] = None
    ) -> Rect:
        """
        Draw all bands, back to front, onto a surface.

        Args:
            surface: surface to draw to
            rect: area to draw to
            surfaces: sprites, as for ``BufferedRenderer.draw``; they are
                drawn only in the sprite band

        Returns:
            the area drawn

        """
        rect = Rect(rect)
        if self._zoom_level == 1.0:
            target, area = surface, rect
        else:
            target = self._zoom_buffer
            area = target.get_rect()

        if self._needs_clear:
            target.fill(self.background_color, area)

        sprite = self._sprite_renderer
        hw, hh = self._buffer_size[0] // 2, self._buffer_size[1] // 2
        for band, tile_layer, (bx, by) in self._layers:
            if tile_layer is None:
                band.draw(target, area, (bx - hw, by - hh))
            elif tile_layer.renderer is sprite:
                tile_layer.renderer.draw(target, area, surfaces)
            else:
                tile_layer.renderer.draw(target, area)

        if self._zoom_level != 1.0:
            self.scaling_function(target, rect.size, surface.subsurface(rect))
        return rect

    @property
    def zoom(self) -> float:
        """
        Zoom the view in or out.

        Values above 1.0 make the map appear closer.  Must be greater than 0.
        Changing it resizes every band, which is expensive.

        """
        return self._zoom_level

    @zoom.setter
    def zoom(self, value: float) -> None:
        if value <= 0:
            raise ValueError("zoom level cannot be zero or less")
        self._zoom_level = value
        self._resize()

    def set_size(self, size: Vector2DInt) -> None:
        """
        Set the size of the view in pixels.

        This is an expensive operation, do only when absolutely needed.

        Args:
            size: pixel size of camera/view

        """
        self._size = tuple(size)
        self._resize()

    @property
    def _buffer_size(self) -> Vector2DInt:
        z = self._zoom_level
        return int(self._size[0] / z), int(self._size[1] / z)

    def _resize(self) -> None:
        camera = self.view_rect.center
        buffer_size = self._buffer_size
        for renderer in self.renderers:
            renderer.set_size(buffer_size)
        self._init_zoom_buffer()
        self.center(camera)

    def _init_zoom_buffer(self) -> None:
        buffer_size = self._buffer_size
        if self._zoom_level == 1.0:
            self._zoom_buffer = None
            self._real_ratio_x = self._real_ratio_y = 1.0
        else:
            self._zoom_buffer = Surface(buffer_size)
            self._real_ratio_x = self._size[0] / buffer_size[0]
            self._real_ratio_y = self._size[1] / buffer_size[1]

    def reload(self) -> None:
        """Reload map data once, then every band's animations and buffers."""
        self.data.reload_data()
        if hasattr(self.data, "reload_animations"):
            self.data.reload_animations()
        for entry in self._layers:
            if entry[1] is not None:
                entry[1].data.reload_animations()
        self._resize()

    def translate_point(self, point: Vector2D) -> Vector2DInt:
        """
        Translate world coordinates of the sprite band to screen coordinates.

        Args:
            point: point to translate

        """
        mx, my = self.get_center_offset()
        if self._zoom_level == 1.0:
            return int(point[0] + mx), int(point[1] + my)
        return (
            int(round((point[0] + mx) * self._real_ratio_x)),
            int(round((point[1] + my) * self._real_ratio_y)),
        )

    def translate_rect(self, rect: RectLike) -> Rect:
        """
        Translate rect position and size to screen coordinates.

        Args:
            rect: rect to translate

        """
        mx, my = self.get_center_offset()
        x, y, w, h = rect
        if self._zoom_level == 1.0:
            return Rect(x + mx, y + my, w, h)
        rx, ry = self._real_ratio_x, self._real_ratio_y
        return Rect(
            round((x + mx) * rx), round((y + my) * ry), round(w * rx), round(h * ry)
        )

    def translate_points(self, points: Iterable[Vector2D]) -> list[Vector2DInt]:
        """
        Translate coordinates and return screen coordinates.

        Args:
            points: points to translate

        """
        return [self.translate_point(p) for p in points]

    def translate_rects(self, rects: Iterable[RectLike]) -> list[Rect]:
        """
        Translate rect position and size to screen coordinates.

        Args:
            rects: rects to translate

        """
        return [self.translate_rect(r) for r in rects]


def _to_bool(value) -> bool:
    """Cast a Tiled boolean attribute that may be a str, int or bool."""
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false")
    return bool(value)


def _float_attr(obj, name: str, default: float) -> float:
    """Read a numeric attribute that pytmx may keep as a string, or omit."""
    value = getattr(obj, name, None)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        log.warning("cannot read %s=%r on %r", name, value, obj)
        return default


def _document_layer_order(tmx) -> list:
    """
    Return the tile and image layers of ``tmx`` in document (drawing) order.

    pytmx appends layers grouped by type (all tile layers, then image layers,
    then object groups), so an image layer placed behind tile layers in Tiled
    ends up after them in ``tmx.layers``.  Within a type the order is kept, so
    the file is re-read and the n-th ``<layer>``/``<imagelayer>`` element is
    matched to the n-th layer of that type.  Falls back to ``tmx.layers``
    order if the file cannot be read.

    """
    tile_layers = [l for l in tmx.layers if isinstance(l, pytmx.TiledTileLayer)]
    image_layers = [l for l in tmx.layers if isinstance(l, pytmx.TiledImageLayer)]
    layer_types = (pytmx.TiledTileLayer, pytmx.TiledImageLayer)
    fallback = [l for l in tmx.layers if isinstance(l, layer_types)]
    try:
        root = ElementTree.parse(tmx.filename).getroot()
    except (AttributeError, OSError, TypeError, ElementTree.ParseError):
        log.warning("cannot re-read map file; using pytmx layer order")
        return fallback

    order = []
    tiles, images = iter(tile_layers), iter(image_layers)
    try:
        for node in root.iter():
            if node.tag == "layer":
                order.append(next(tiles))
            elif node.tag == "imagelayer":
                order.append(next(images))
    except StopIteration:
        order = None
    if order is None or len(order) != len(fallback):
        log.warning("map file does not match loaded map; using pytmx layer order")
        return fallback
    return order
