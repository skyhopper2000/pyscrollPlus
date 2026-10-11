# Multiple maps

{class}`~pyscroll.data.MapAggregator` is a data adapter that places several
maps side by side and presents them to the renderer as one big map. It is
useful for worlds built from separate rooms or chunks.

```{warning}
`MapAggregator` is experimental. Read the limitations below before you build
on it.
```

`MapAggregator` isn't exported from the top-level package; import it from
`pyscroll.data`. This is a shortened version of `apps/demo/demo-stitched.py`,
which stitches nine 20x20 maps into a 3x3 grid (run it from `apps/demo`):

```python
import pygame
import pyscroll
from pyscroll.data import MapAggregator, TiledMapData
from pytmx.util_pygame import load_pygame

pygame.init()
screen = pygame.display.set_mode((800, 600))

world_data = MapAggregator((16, 16))  # tile size shared by every map
for filename, offset in [
    ("stitched0.tmx", (-20, -20)),
    ("stitched1.tmx", (0, -20)),
    ("stitched2.tmx", (20, -20)),
    ("stitched3.tmx", (-20, 0)),
    ("stitched4.tmx", (0, 0)),
    ("stitched5.tmx", (20, 0)),
    ("stitched6.tmx", (-20, 20)),
    ("stitched7.tmx", (0, 20)),
    ("stitched8.tmx", (20, 20)),
]:
    world_data.add_map(TiledMapData(load_pygame(filename)), offset)

print(world_data.map_size)  # (60, 60) tiles

map_layer = pyscroll.BufferedRenderer(world_data, screen.get_size())
map_layer.zoom = 2
group = pyscroll.PyscrollGroup(map_layer=map_layer)
group.center((480, 480))
group.draw(screen)
```

`add_map(data, offset)` takes any data adapter and the position of its
top-left tile, **in tiles**. Offsets may be negative. The renderer can't use
negative tile coordinates, so whenever a map is added further up or left than
the others, every map is shifted so the top-left-most map starts at tile
`(0, 0)`. In the example above, world pixel `(0, 0)` is the top-left corner of
`stitched0.tmx`, not of `stitched4.tmx`. Add all maps before placing sprites,
or use only non-negative offsets so coordinates never shift.

The combined `visible_tile_layers` is the union of the layers of all maps.
The combined map is the bounding box of all maps; cells no map covers are
empty and drawn in the renderer's clear color (black).

## Limitations

- All maps must have the same tile size; `add_map()` asserts it.
- No tile animations: animated tiles are drawn but don't animate.
- `BufferedRenderer.reload()` doesn't work: it raises `TypeError`.
- Sprites are never covered by tiles. The aggregator can't look up single
  tiles yet, so every sprite is drawn on top of the map whatever its layer.
- Maps can't be removed: `remove_map()` raises `NotImplementedError`.
- It can't be used with `alpha=True`, because it has no `convert_surfaces()`
  method (the renderer raises `AttributeError`).
