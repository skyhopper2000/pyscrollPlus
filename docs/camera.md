# Camera & coordinates

pyscroll uses two coordinate systems:

- **World coordinates** are pixels on the map. `(0, 0)` is the top-left
  corner of the map. Sprite rects given to {class}`~pyscroll.PyscrollGroup` are
  in world coordinates.
- **Screen coordinates** are pixels in the area the map is drawn to, relative
  to its top-left corner.

The renderer is the camera. The examples on this page continue from the setup
in the [Quickstart](quickstart.md) (`screen`, `map_data`, `map_layer`,
`group`, `hero`).

## Moving the camera

{meth}`~pyscroll.orthographic.BufferedRenderer.center` puts a world position
in the middle of the view. Floats are rounded to whole pixels.
{meth}`~pyscroll.orthographic.BufferedRenderer.scroll` moves the camera by an
offset instead:

```python
map_layer.center((640, 640))  # look at world pixel (640, 640)
map_layer.scroll((32, 0))     # move the camera 32 pixels to the right
```

`PyscrollGroup.center()` does the same as `map_layer.center()`. Moving the
camera never changes sprite rects.

Two rects describe what the camera sees:

- `map_layer.view_rect`: the part of the map that is visible, in world
  coordinates. `group.view` returns a copy of it.
- `map_layer.map_rect`: the whole map, in world pixels.

```python
map_layer.center((640, 640))
print(map_layer.view_rect)  # Rect(240, 340, 800, 600)
print(map_layer.map_rect)   # Rect(0, 0, 1280, 1280) for the 40x40 desert map
```

Moving the camera a tile or less per frame is cheap: the renderer scrolls its
buffer and draws one new row or column of tiles. Jumping further redraws the
whole buffer, which is slower but fine for occasional jumps.

## Clamping to the map edges

By default (`clamp_camera=True`) the camera stops at the map edges, so the
view never shows anything outside the map. If the map is smaller than the
view, the view is centered on the map.

With `clamp_camera=False` the camera follows the target past the edges and
the area outside the map is left empty:

```python
free_camera = pyscroll.BufferedRenderer(
    map_data, screen.get_size(), clamp_camera=False
)
free_camera.center((0, 0))  # the map's top-left corner is in the middle

screen.fill((40, 40, 60))   # draw your own background first
free_camera.draw(screen, screen.get_rect())
```

The renderer only draws where the map is, so draw (or fill) a background
before the map every frame. Otherwise old frames show through around the map.

```{note}
Known issue: before drawing, the renderer clears the area the map covered on
the previous frame to its clear color (black, unless you use `alpha=True` or
`colorkey`). While the camera moves past an edge, the strip the map just
left can show that color instead of your background for one frame.
```

## Zoom

Pass `zoom` to the constructor or set the
{attr}`~pyscroll.orthographic.BufferedRenderer.zoom` property. Values above
`1.0` zoom in, values below `1.0` zoom out. The default is `1.0`; zero or a
negative value raises `ValueError`.

```python
map_layer.zoom = 2  # each map pixel is drawn as 2x2 screen pixels
map_layer.center(hero.rect.center)
print(map_layer.view_rect.size)  # (400, 300): the view now covers less map
group.draw(screen)
```

How it works: the renderer draws the map at normal size into a smaller (or
larger) buffer and scales that buffer to the target size with
`scaling_function`. The default is `pygame.transform.scale`. Pass
`scaling_function=pygame.transform.smoothscale` to the constructor for
smoother results on 24/32-bit surfaces.

Things to know:

- Setting `zoom` rebuilds the buffers and redraws every visible tile. Avoid
  changing it every frame.
- The view keeps its top-left corner when the zoom changes. Call `center()`
  afterwards to keep the camera on target.
- While zoomed, `draw(surface, rect)` scales the map to `rect.size` and
  writes it into the whole of `surface`, so `rect` must be the same size as
  `surface`. To draw a zoomed map into part of the screen, draw into a
  subsurface:

  ```python
  viewport = screen.subsurface(pygame.Rect(0, 0, 400, 300))
  small_view = pyscroll.BufferedRenderer(map_data, viewport.get_size(), zoom=2)
  small_view.center(hero.rect.center)
  small_view.draw(viewport, viewport.get_rect())
  ```

```{warning}
Known issue: when `zoom` is passed to the constructor, the `translate_*`
methods below ignore it until the `zoom` property is set. Drawing is not
affected. Workaround: set `map_layer.zoom = ...` after creating the renderer.
```

## World to screen coordinates

To draw something yourself at a world position (a health bar, a selection
box, a debug overlay), convert it to screen coordinates. These methods use the
current camera position and zoom:

| Method | Converts |
|---|---|
| `translate_point(point)` | one `(x, y)` |
| `translate_points(points)` | a list of `(x, y)` |
| `translate_rect(rect)` | one rect: position and size |
| `translate_rects(rects)` | a list of rects |

```python
map_layer.center(hero.rect.center)
group.draw(screen)

# outline the hero, in screen coordinates
outline = map_layer.translate_rect(hero.rect)
pygame.draw.rect(screen, (255, 255, 0), outline, 1)

# mark its top-left corner
pygame.draw.circle(screen, (255, 0, 0), map_layer.translate_point(hero.rect.topleft), 3)
```

The results are relative to the top-left of the area the map is drawn to. If
you draw the map into `pygame.Rect(100, 50, ...)`, add `(100, 50)`.

{meth}`~pyscroll.orthographic.BufferedRenderer.get_center_offset` returns the
`(dx, dy)` you add to a world position to get its position in the renderer's
buffer. Without zoom, that is the same as the screen position. With zoom it is
*not* scaled; use the `translate_*` methods to get screen positions. The
unscaled offset is what the renderer's `surfaces` argument expects (see
[Sprites & surfaces](sprites.md#drawing-surfaces-without-a-group)):

```python
map_layer.zoom = 1
map_layer.center(hero.rect.center)
dx, dy = map_layer.get_center_offset()
assert hero.rect.move(dx, dy) == map_layer.translate_rect(hero.rect)
```

To go the other way, from a screen position (such as the mouse) to the world,
there is no helper yet. Without zoom it is:

```python
mx, my = (400, 300)  # e.g. pygame.mouse.get_pos()
dx, dy = map_layer.get_center_offset()
world_x, world_y = mx - dx, my - dy
```

## Resizing

Call {meth}`~pyscroll.orthographic.BufferedRenderer.set_size` when the window
size changes. It rebuilds the buffers, so only call it when the size actually
changes:

```python
screen = pygame.display.set_mode((1024, 768))
map_layer.set_size(screen.get_size())
map_layer.center(hero.rect.center)
```
