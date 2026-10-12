# Quickstart

## Install

```text
pip install pyscroll pytmx
```

pyscroll works with either **pygame** (2.0+) or **pygame-ce**. It doesn't
install either one for you, so install the one you use (`pip install
pygame-ce`, for example). Only install one of them: both provide the `pygame`
module and they overwrite each other.

pytmx is optional. You need it to load maps made with the
[Tiled map editor](https://www.mapeditor.org/). Without it, you can still feed
pyscroll your own map data through a [custom data adapter](adapters.md).

## A scrolling map with a sprite

This loads a Tiled map, puts a sprite on it, and lets you walk around with the
arrow keys. It uses `desert.tmx` and `hero.png` from the `apps/demo` folder of
the repository; run it from that folder.

```python
import pygame
import pyscroll
from pytmx.util_pygame import load_pygame

pygame.init()
screen = pygame.display.set_mode((800, 600))

# Load the map with pytmx, then wrap it in pyscroll's adapter for Tiled maps.
# load_pygame needs a display, so call it after set_mode.
tmx_data = load_pygame("desert.tmx")
map_data = pyscroll.TiledMapData(tmx_data)

# The renderer draws the visible part of the map. Give it the size of the
# area it will draw to, in pixels.
map_layer = pyscroll.BufferedRenderer(map_data, screen.get_size())

# PyscrollGroup is a pygame sprite group that draws the map and the sprites.
group = pyscroll.PyscrollGroup(map_layer=map_layer)

hero = pygame.sprite.Sprite()
hero.image = pygame.image.load("hero.png").convert_alpha()
# Sprite rects are in world coordinates: pixels on the map.
hero.rect = hero.image.get_rect(center=map_layer.map_rect.center)
group.add(hero)
```

The game loop moves the sprite, centers the camera on it and draws:

```python
clock = pygame.time.Clock()
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    dx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
    dy = keys[pygame.K_DOWN] - keys[pygame.K_UP]
    hero.rect.move_ip(dx * 4, dy * 4)

    group.center(hero.rect.center)
    group.draw(screen)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

There is no `screen.fill()` in the loop. The map covers the whole screen, so
clearing it first would only cost time. (If the map can be smaller than the
screen, or you turn off camera clamping, see [Camera & coordinates](camera.md).)

## How the pieces fit

- A **data adapter** ({class}`~pyscroll.data.TiledMapData` for Tiled maps)
  tells pyscroll the tile size, the map size, which layers to draw and which
  image goes in each cell.
- The **renderer** ({class}`~pyscroll.orthographic.BufferedRenderer`) keeps a
  buffer slightly larger than the view. When the camera moves, it scrolls the
  buffer and draws only the row or column of tiles that came into view.
- The **group** ({class}`~pyscroll.group.PyscrollGroup`) is optional. It
  converts sprite rects from world coordinates to screen coordinates and hands
  them to the renderer, which draws them between the right tile layers. You
  can also [pass surfaces to the renderer yourself](sprites.md#drawing-surfaces-without-a-group).

## More examples

- `apps/tutorial/quest.py`: a small game with collisions, zoom and sprites that
  walk under tiles.
- `apps/demo/demo.py`: a map viewer that scrolls on its own.
- `apps/demo/demo-stitched.py`: nine maps stitched into one world, see
  [Multiple maps](multiple-maps.md).
