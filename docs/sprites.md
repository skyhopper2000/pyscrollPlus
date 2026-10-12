# Sprites & surfaces

pyscroll draws sprites *between* tile layers: a sprite on layer 1 is drawn
over the tiles of layers 0 and 1 and under the tiles of layer 2 and above. A
character can walk behind a tree top or under a bridge without any extra code.

The examples on this page continue from the [Quickstart](quickstart.md) setup.

## PyscrollGroup

{class}`~pyscroll.group.PyscrollGroup` is a subclass of
`pygame.sprite.LayeredUpdates`, so everything you know about pygame groups
applies: `add()`, `remove()`, `update()`, `sprites()`, collision functions,
`change_layer()`, and so on. The differences:

- It needs a renderer: `PyscrollGroup(map_layer=map_layer)`. Other arguments,
  such as `default_layer`, are passed on to `LayeredUpdates`.
- Sprite rects are in **world coordinates**. The group converts them to screen
  coordinates when drawing; it never changes `sprite.rect`.
- `group.draw(surface)` draws the map *and* the sprites. It skips sprites whose
  rect is outside the view, and returns the rect of the area the map was drawn
  to.
- `group.center(pos)` moves the camera, and `group.view` is a copy of the
  renderer's `view_rect`.

## Layers

The sprite's layer in the group decides which tiles cover it. Layer numbers
are the indices of the map's tile layers. For a Tiled map they are the
positions of the layers in the map's layer list, counting from 0 at the
bottom, as returned by `tmx_data.visible_tile_layers`. Object layers count
too, even though pyscroll doesn't draw them.

Set the layer like in any `LayeredUpdates` group:

```python
group = pyscroll.PyscrollGroup(map_layer=map_layer, default_layer=1)

npc = pygame.sprite.Sprite()
npc.image = pygame.Surface((32, 32))
npc.rect = npc.image.get_rect(topleft=(320, 320))
npc.layer = 2    # read by add(); without it, default_layer is used
group.add(npc)

group.add(hero, layer=0)     # or pass the layer to add()
group.change_layer(npc, 1)   # move a sprite that is already in the group
print(group.get_layer_of_sprite(npc))  # 1
```

How covering works: for every tile cell the sprite's rect overlaps, the
renderer looks at the tiles in that cell. If any of them is on the sprite's
layer or higher, it redraws that cell's tiles and the sprite together, sorted
by layer. Tiles on the sprite's own layer go under it; tiles on higher layers
go over it. Sprites on a layer above the top tile layer skip this work.

Covering works per tile cell and uses the sprite's **rect**, not its pixels.

```{note}
Within the same layer, sprites are not drawn in the order of the group.
The renderer sorts them by layer, then by their screen x position, then by
their y position. If two sprites on the same layer overlap, the one further
right (or, at the same x, further down) is drawn on top. Put sprites on
different layers if you need a fixed order.
```

## Blend modes

If a sprite has a `blendmode` attribute, the group passes it to the renderer,
which uses it as the `special_flags` of the blit. `pygame.sprite.DirtySprite`
already has `blendmode` (default `0`, a normal blit); for a plain `Sprite`,
just set the attribute:

```python
glow = pygame.sprite.Sprite()
glow.image = pygame.Surface((64, 64))
glow.image.fill((60, 40, 0))
glow.rect = glow.image.get_rect(center=hero.rect.center)
glow.blendmode = pygame.BLEND_RGB_ADD  # brightens the tiles under it
group.add(glow, layer=2)

group.draw(screen)
```

## Drawing surfaces without a group

You don't need `PyscrollGroup`. The renderer's
{meth}`~pyscroll.orthographic.BufferedRenderer.draw` takes an optional list
of surfaces and draws them between the tile layers, exactly like the group
does. Each item is a tuple:

```text
(surface, rect, layer)
(surface, rect, layer, blend_flags)
```

- `surface`: the image to draw.
- `rect`: where to draw it, in the renderer's buffer coordinates. Its size
  decides which tiles can cover it. To convert a world rect, move it by
  `map_layer.get_center_offset()`.
- `layer`: the tile layer the surface is on, as above.
- `blend_flags`: optional `special_flags` for the blit, e.g.
  `pygame.BLEND_RGB_ADD`.

```{note}
The docstring of `BufferedRenderer.draw` lists the tuple as
`(layer, surface, rect)`. That is wrong: the code expects
`(surface, rect, layer)`.
```

This is what `PyscrollGroup.draw()` does for you:

```python
coin = pygame.Surface((16, 16))
coin.fill((255, 215, 0))
coin_world_rect = coin.get_rect(topleft=(600, 600))

map_layer.center(coin_world_rect.center)
dx, dy = map_layer.get_center_offset()

surfaces = [
    (coin, coin_world_rect.move(dx, dy), 0),
    (coin, coin_world_rect.move(dx + 32, dy), 0, pygame.BLEND_RGB_ADD),
]
map_layer.draw(screen, screen.get_rect(), surfaces)
```

Use `get_center_offset()` here, not `translate_rect()`: when the map is
zoomed, the surfaces are drawn into the unscaled buffer before it is scaled,
so their rects must not be scaled either.

## sprite_damage_height

`BufferedRenderer` takes a `sprite_damage_height` argument, meant to let only
the bottom part of a tall sprite (its feet) decide which tiles cover it.

```{warning}
`sprite_damage_height` is accepted and stored, but the renderer does not use
it yet: passing it has no effect. The older `tall_sprites` argument does this
today, but it is deprecated and logs a warning when used.
```
