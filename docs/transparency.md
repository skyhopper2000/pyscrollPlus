# Transparency & FAQ

## Tile transparency

Transparent pixels in tiles just work, with both per-pixel alpha and colorkey
tilesets. Tiles on higher layers are drawn over lower ones with their
transparency intact. You don't need any renderer option for this.

## Seeing through the map: `alpha` and `colorkey`

The two renderer options `alpha` and `colorkey` are about something else: what
is drawn in cells that have **no tile on any layer**. By default the renderer
uses an opaque buffer and clears those cells to black. That is the fastest
option, and fine if the map has no holes.

To draw the map *over* something else (a background image, another renderer),
make the empty cells transparent:

`alpha=True`
: The buffers get per-pixel alpha and empty cells are fully transparent. The
  renderer calls the adapter's `convert_surfaces(buffer, True)` so the tiles
  match the buffer format. This is the most reliable option, but drawing is
  slower than with an opaque buffer.

`colorkey=(r, g, b)`
: The buffers use this color as their colorkey and empty cells are filled with
  it. Cheaper than alpha, with side effects: pixels of that exact color in your
  tiles become transparent too, and the edges of per-pixel alpha tiles may show
  a fringe of the key color.

You can't use both: passing `alpha=True` and a `colorkey` raises `ValueError`.

```python
import pygame
import pyscroll
from pytmx.util_pygame import load_pygame

pygame.init()
screen = pygame.display.set_mode((800, 600))
map_data = pyscroll.TiledMapData(load_pygame("desert.tmx"))

map_layer = pyscroll.BufferedRenderer(map_data, screen.get_size(), alpha=True)
map_layer.center((640, 640))

screen.fill((30, 30, 50))  # draw what goes under the map first
map_layer.draw(screen, screen.get_rect())
```

## FAQ

### Why are parts of my map black?

Those cells have no tile on any visible layer, and empty cells are cleared to
black. Either fill them in your map (a background layer with a plain tile is
the fastest fix, and extra layers cost very little) or pass `alpha=True` and
draw something under the map.

### Do I need to clear the screen before drawing?

Usually not. With the default `clamp_camera=True` the renderer overwrites every
pixel of the draw area, and if the map is smaller than the view, the area
around it is drawn black. With `clamp_camera=False` the renderer leaves the
area outside the map alone, so draw a background there first (see
[Clamping to the map edges](camera.md#clamping-to-the-map-edges)).

### Can I draw something under the map?

Yes. Create the renderer with `alpha=True` (or a `colorkey`), draw your
background, then draw the map or group on top, as in the example above.

### Can I draw the map into part of the window?

Pass the area as the `rect` argument: `map_layer.draw(screen, rect)`. Create
the renderer with the same size as the rect. Note that a zoomed map must be
drawn into a subsurface instead (see [Zoom](camera.md#zoom)).

### Does pyscroll support parallax?

Not directly yet; see [Parallax](parallax.md) for a workaround.

### Does it work with pygame-ce?

Yes. pyscroll works with pygame 2 and pygame-ce. Install only one of them.

### Is there a minimap or an overview mode?

Make a second renderer with a small size and a zoom below `1.0`, and draw it
into its own surface.
