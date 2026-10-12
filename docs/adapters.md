# Custom data adapters

pyscroll doesn't read map files itself. The renderer asks a **data adapter**
for everything it needs. {class}`~pyscroll.data.TiledMapData` is the adapter
for Tiled maps loaded with pytmx. For any other source (your own level format,
a procedurally generated world, a 2D list) write a subclass of
{class}`~pyscroll.data.PyscrollDataAdapter`.

## A minimal adapter

A static map needs three attributes and one method:

```python
import pygame
import pyscroll


class GridData(pyscroll.PyscrollDataAdapter):
    """A one-layer map stored as a list of strings, one character per tile."""

    def __init__(self, rows, colors, tile_size=(32, 32)):
        super().__init__()  # required: sets up the animation bookkeeping
        self.rows = rows
        self.tile_size = tile_size                  # tile size in pixels
        self.map_size = len(rows[0]), len(rows)     # map size in tiles
        self.visible_tile_layers = [0]              # layers to draw
        self.images = {}
        for key, color in colors.items():
            image = pygame.Surface(tile_size)
            image.fill(color)
            self.images[key] = image

    def _get_tile_image(self, x, y, l):
        # The renderer can ask for cells outside the map, including negative
        # ones: return None for those (and for empty cells).
        if 0 <= x < self.map_size[0] and 0 <= y < self.map_size[1]:
            return self.images.get(self.rows[y][x])
        return None


pygame.init()
screen = pygame.display.set_mode((320, 240))

rows = [
    "~~~~~~~~~~~~~~~~",
    "~..........#...~",
    "~..##......#...~",
    "~..##..........~",
    "~.......~~~....~",
    "~.......~~~....~",
    "~..............~",
    "~~~~~~~~~~~~~~~~",
]
colors = {"~": (40, 90, 200), ".": (90, 170, 70), "#": (110, 110, 110)}
data = GridData(rows, colors)

map_layer = pyscroll.BufferedRenderer(data, screen.get_size())
map_layer.center((256, 128))
map_layer.draw(screen, screen.get_rect())
```

`tile_size`, `map_size` and `visible_tile_layers` can be plain attributes or
properties. Pass `alpha=True` to the renderer if your map has cells with no
tile in any layer; see [Transparency & FAQ](transparency.md).

## The adapter contract

### Required

`tile_size`
: `(width, height)` of one tile, in pixels. All tiles have the same size.

`map_size`
: `(width, height)` of the map, in tiles.

`visible_tile_layers`
: The layer numbers to draw, lowest first. Layer numbers are also what sprites
  use to decide which tiles cover them.

`_get_tile_image(x, y, l)`
: The `Surface` for tile column `x`, row `y` on layer `l`, or `None` if the
  cell is empty. It must return `None` (not raise) for coordinates outside the
  map. Don't apply animations here; the base class does that in
  `get_tile_image()`.

Call `super().__init__()` in your constructor.

### Needed for some features

`reload_data()`
: Reload the map from its source. Called by `BufferedRenderer.reload()`.

`get_animations()`
: Yield `(tile_id, frames)` for every animated tile, where `frames` is a list
  of `(frame_id, duration_ms)`. Called by `reload_animations()`, which
  `BufferedRenderer.reload()` calls. A static map that wants to support
  `reload()` can return an empty list.

`_get_tile_image_by_id(id)`
: Return the `Surface` for an id used in `get_animations()`.

`convert_surfaces(parent, alpha)`
: Called by the renderer when it is created with `alpha=True`, so you can
  convert your tile images to match the buffer (e.g. with
  `image.convert_alpha()`). The base class doesn't define it, so an
  adapter without it can't be used with `alpha=True`.

### Optional

`get_tile_images_by_rect(rect)`
: The renderer calls this to fill its buffer. `rect` is an area in tiles, and
  unlike Python ranges **its right and bottom edges are included**. Yield
  `(x, y, layer, surface)` for every non-empty tile in it. The default
  implementation calls `get_tile_image()` for every cell of every visible
  layer. Override it if your data can be read faster in bulk;
  `TiledMapData` does, reading row slices straight from pytmx.

  The order you yield tiles in is the order they are drawn on the buffer, so
  yield lower layers first.

`prepare_tiles(tiles)`
: Called just before the renderer draws tiles into its buffer, with a `Rect`
  of the tile area the buffer covers. Use it to load or generate the tiles
  that are about to be needed. A draw happens right after it returns. Don't
  keep or change the rect. The default does nothing.

The base class also implements `get_tile_image()`, `process_animation_queue()`
and `reload_animations()`. You normally don't override these.

### Adding the optional methods

Continuing the example, a version of `GridData` that supports `reload()` and
`alpha=True`:

```python
class ReloadableGridData(GridData):
    def reload_data(self):
        pass  # re-read self.rows from disk, a level editor, ...

    def get_animations(self):
        return []  # no animated tiles

    def convert_surfaces(self, parent, alpha=False):
        for key, image in self.images.items():
            self.images[key] = image.convert_alpha() if alpha else image.convert(parent)


data = ReloadableGridData(rows, colors)
map_layer = pyscroll.BufferedRenderer(data, screen.get_size(), alpha=True)
map_layer.reload()
map_layer.draw(screen, screen.get_rect())
```

## Animations

Animated tiles in custom adapters work, but need more than the contract above,
and use private attributes that may change. The base class only animates
positions that were registered on the animation's token, and only
`TiledMapData` does that registering. Your adapter has to do it in
`get_tile_images_by_rect()`:

```python
class AnimatedGridData(GridData):
    def __init__(self, rows, colors, tile_size=(32, 32)):
        super().__init__(rows, colors, tile_size)
        foam = pygame.Surface(tile_size)
        foam.fill((200, 220, 255))
        self.images["foam"] = foam
        self.reload_animations()  # builds self._animation_map from get_animations()

    def get_animations(self):
        # water tiles alternate between water and foam, 500 ms each
        yield "~", [("~", 500), ("foam", 500)]

    def _get_tile_image_by_id(self, id):
        return self.images[id]

    def get_tile_images_by_rect(self, rect):
        for x, y, l, image in super().get_tile_images_by_rect(rect):
            token = self._animation_map.get(self.rows[y][x])
            if token is not None:
                token.positions.add((x, y, l))  # animate this cell
            yield x, y, l, image


data = AnimatedGridData(rows, colors)
map_layer = pyscroll.BufferedRenderer(data, screen.get_size())
clock = pygame.time.Clock()
for frame in range(90):
    map_layer.draw(screen, screen.get_rect())
    clock.tick(60)
```

See {doc}`animation` for how the animation types work.
