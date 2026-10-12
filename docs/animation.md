# Animated tiles

## Tiled animations

Tile animations made in Tiled's tileset editor play automatically. There is
nothing to turn on: {class}`~pyscroll.data.TiledMapData` reads the animations
from pytmx, and the renderer advances them each time it draws.

```python
import pygame
import pyscroll
from pytmx.util_pygame import load_pygame

pygame.init()
screen = pygame.display.set_mode((240, 240))

# animated.tmx (in apps/demo) has animated water tiles
tmx_data = load_pygame("animated.tmx")
map_layer = pyscroll.BufferedRenderer(pyscroll.TiledMapData(tmx_data), screen.get_size())

clock = pygame.time.Clock()
for frame in range(120):  # about two seconds
    map_layer.draw(screen, screen.get_rect())
    pygame.display.flip()
    clock.tick(60)
```

Frame durations are in milliseconds, as in Tiled, and are measured with the
wall clock (`time.time()`). Animations loop forever.

Only tiles inside the renderer's buffer are tracked. A tile is registered the
first time it is drawn into the buffer and dropped when it scrolls out, so the
cost depends on what is on screen, not on the size of the map.

```{note}
The `time_source` argument of `BufferedRenderer` is stored but not used:
animations always use `time.time()`.
```

## Hot reload

{meth}`~pyscroll.orthographic.BufferedRenderer.reload` reloads the map data
and the animations, then redraws the view. During development you can edit
the map in Tiled, save it, and see the change without restarting the game:

```python
for event in pygame.event.get():
    if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
        map_layer.reload()

map_layer.reload()  # or call it directly
```

`reload()` calls the adapter's `reload_data()` and then `reload_animations()`.
For `TiledMapData`, `reload_data()` loads the file again with
`pytmx.load_pygame(tmx.filename)`, using pytmx's default options.

Caveats:

- The map must keep its tile size and map size. The renderer doesn't rebuild
  its buffers on reload.
- If the renderer uses `alpha=True`, the reloaded tile images are not
  converted for the alpha buffer again.
- `MapAggregator` doesn't support reload (see [Multiple maps](multiple-maps.md)).

## Animation types

The renderer schedules animations with two small types from
{mod}`pyscroll.animation`. You only need them if you write your own adapter or
want to inspect the animation queue.

{class}`~pyscroll.animation.AnimationFrame`
: A named tuple `(image, duration)`: a pygame `Surface` and how long it is
  shown, in milliseconds. This is not the same as pytmx's `AnimationFrame`,
  which is `(gid, duration)`; adapters convert one into the other.

{class}`~pyscroll.animation.AnimationToken`
: One animated tile: its frames, the set of `(x, y, layer)` positions where it
  is on screen, and the time of the next frame change. Tokens are kept in a
  heap ordered by that time. Creating a token with no frames raises
  `ValueError`.

```python
from pyscroll.animation import AnimationFrame, AnimationToken

red = pygame.Surface((16, 16))
red.fill((255, 0, 0))
blue = pygame.Surface((16, 16))
blue.fill((0, 0, 255))

token = AnimationToken(positions=set(), frames=[AnimationFrame(red, 250), (blue, 250)])
print(token.next)       # 250.0: time of the next frame change
frame = token.advance(token.next)
print(frame.duration)   # 250, and frame.image is blue

try:
    AnimationToken(set(), [])
except ValueError as e:
    print(e)            # Frames sequence cannot be empty
```

To add animations to a custom adapter, see
[Custom data adapters](adapters.md#animations).
