# Parallax

pyscroll has no parallax support built in yet. A `ParallaxRenderer` that
composes one renderer per group of layers, configured from Tiled's layer
parallax settings, is planned.

Until then, you can build the effect yourself: use one renderer per layer,
move the background renderers more slowly than the foreground, and draw them
back to front. Every renderer above the bottom one needs `alpha=True` so the
layers behind it show through.

A renderer draws every visible tile layer of its data, so give each renderer a
copy of the map with only its layer visible. With pytmx, load the map once per
renderer and hide the other layers:

```python
import pygame
import pyscroll
from pytmx.util_pygame import load_pygame

pygame.init()
screen = pygame.display.set_mode((200, 200))


def load_layer(filename, layer_index):
    tmx_data = load_pygame(filename)
    for i, layer in enumerate(tmx_data.layers):
        layer.visible = i == layer_index
    return pyscroll.TiledMapData(tmx_data)


size = screen.get_size()
back = pyscroll.BufferedRenderer(load_layer("animated.tmx", 0), size)
front = pyscroll.BufferedRenderer(load_layer("animated.tmx", 1), size, alpha=True)

camera = pygame.Vector2(120, 120)
back.center(camera * 0.5)  # moves at half speed
front.center(camera)
back.draw(screen, screen.get_rect())
front.draw(screen, screen.get_rect())
```

Each extra layer costs one more full-screen alpha blit per frame, and alpha
buffers are slower than opaque ones. Sprites are covered only by tiles of the
renderer they are drawn with.
