pyscroll
========

For Python 3.9+ and pygame 2.0+

__pygame-ce is supported__

A simple and fast module for animated scrolling maps for your new or existing
game.

If you find this useful, please consider making a donation to help support it
https://liberapay.com/ltheden/donate

Discord! https://discord.gg/2taTP4aYR6

Documentation: https://pyscrollplus.readthedocs.io


Introduction
============

pyscroll is a generic module for making a fast scrolling image with pygame.  It
uses a lot of magic to get great framerates out of pygame.  It only exists to
draw a map.  It doesn't load images or data, so you can use your own custom
data structures, tile storage, ect.

pyscroll is compatible with pytmx (https://github.com/bitcraft/pytmx), so you
can use your Tiled maps.  It also has out-of-the-box support for pygame
sprites.


Features
========

- Reload the map tiles and data without closing the game
- Sprites or plain surfaces can be drawn in layers
- Animated tiles
- Zoom in and out
- Translate world coordinates to screen coordinates (`translate_point`,
  `translate_rect`, ...)
- Optional camera clamping: stop at the map edges, or scroll past them
- Per-sprite blend modes
- Includes optional drop-in replacement for pygame LayeredGroup
- Pixel alpha and colorkey tilesets are supported
- Stitch several maps into one world with `MapAggregator` (experimental)
- Fast and small footprint
- Speed is not affected by map size
- Support for pytmx loaded maps from Tiled Map Editor
- Plug in your own map format with a small adapter class


Use It Like a Camera
====================

In order to further simplify using scrolling maps, pyscroll includes a pygame
sprite group that will render all sprites on the map and will correctly draw
them over or under tiles.  Sprites can use their rect in world coordinates, and
the group will work like a camera, translating world coordinates to screen
coordinates while rendering sprites and map layers.

It's also useful to make minimaps or create simple chunky graphics.


Installation
===============================================================================

Install from pip

    pip install pyscroll

pyscroll needs pygame 2.0+ or pygame-ce, and doesn't install either for you.
Install the one you use (`pip install pygame-ce` or `pip install pygame`), but
not both: they share the `pygame` module and overwrite each other.

pytmx is optional. Install it to load maps from the Tiled Map Editor:

    pip install pytmx

You can also install it from a clone of the source

    pip install .


New Game Tutorial
=================

This is a quick guide on building a new game with pyscroll and pygame.  It uses
the PyscrollGroup for efficient rendering.  You are free to use any other
pygame techniques and functions.

Open apps/tutorial/quest.py for a gentle introduction to pyscroll and the
PyscrollGroup for pygame.  There are plenty of comments to get you started.

The Quest demo shows how you can use a pyscroll group for drawing, how to load
maps with pytmx, and how pyscroll can quickly render layers.  Moving under some
tiles will cause the Hero to be covered.

The repo wiki has more in-depth explanations of the tutorial code, including
one way to implement sprite animation.  Be sure to check it out.  Anyone is
welcome to make additions or improvements.

https://github.com/bitcraft/pyscroll/wiki


Example Use with pytmx
======================

pyscroll and pytmx can load your maps from Tiled and use your pygame sprites.
The following is a very basic way to load a map onto the screen.  It uses
`desert.tmx` and `hero.png` from `apps/demo`.

```python
from pytmx.util_pygame import load_pygame
import pygame
import pyscroll


class Sprite(pygame.sprite.Sprite):
    """
    Simple Sprite class for on-screen things
    
    """
    def __init__(self, surface) -> None:
        super().__init__()
        self.image = surface
        self.rect = surface.get_rect()


pygame.init()
screen = pygame.display.set_mode((400, 400))

# Load TMX data
tmx_data = load_pygame("desert.tmx")

# Make the scrolling layer
map_layer = pyscroll.BufferedRenderer(
    data=pyscroll.TiledMapData(tmx_data),
    size=(400,400),
)

# make the pygame SpriteGroup with a scrolling map
group = pyscroll.PyscrollGroup(map_layer=map_layer)

# Add sprite(s) to the group
surface = pygame.image.load("hero.png").convert_alpha()
sprite = Sprite(surface)
group.add(sprite)

# Center the camera on the sprite
group.center(sprite.rect.center)

# Draw map and sprites using the group
# Notice I did not `screen.fill` here!  Clearing the screen is not
# needed since the map will clear it when drawn
group.draw(screen)
pygame.display.flip()
```

The documentation has a complete game loop, and covers zoom, translating
coordinates, layers, animated tiles and more:
https://pyscrollplus.readthedocs.io


Adapting Existing Games / Map Data
==================================

pyscroll can be used with existing map data, but you will have to create a
class to interact with pyscroll or adapt your data handler.  Subclass
`pyscroll.PyscrollDataAdapter`; the "Custom data adapters" page of the
documentation lists what it needs.

#### Give pyscroll surface to layer into the map

pyscroll can use a list of surfaces and render them on the map, taking account
their layer position.

```python
map_layer = pyscroll.BufferedRenderer(map_data, map_size)

# just an example for clarity.  here's a made up game engine:

def game_engine_draw():
   surfaces = list()
   for game_object in my_game_engine:

      # pyscroll uses normal pygame surfaces.
      surface = game_object.get_surface()

      # pyscroll will draw surfaces in screen coordinates, so move the
      # world rect by the camera offset.
      # you need to use a rect to handle tiles that cover surfaces.
      rect = game_object.get_world_rect().move(map_layer.get_center_offset())

      # the list called 'surfaces' is required for pyscroll
      # notice the layer.  this determines which layers the sprite will cover.
      # layer numbers higher than this will cover the surface
      # an optional 4th item sets blend flags, e.g. pygame.BLEND_RGB_ADD
      surfaces.append((surface, rect, game_object.layer))

   # tell pyscroll to draw to the screen, and use the surfaces supplied
   map_layer.draw(screen, screen.get_rect(), surfaces)
```


FAQ
===

More answers are in the "Transparency & FAQ" page of the documentation.

## Why are parts of my map black?
Pyscroll is fastest with maps that are completely filled with tiles.  You can
have several layers, some layers without tiles, and that is fine; but where
there are empty spaces in all the layers, the renderer clears the gap to
black.  There are two ways to fix this, with the 1st solution being the best
performance wise:

##### 1. In Tiled (or your data), fill in the empty spots with a tile
For best performance, you must have a tile in each part of the map.  You can
create a simple background layer, and fill with single color tiles where there
are gaps.  Pyscroll is very fast even with several layers, so there is
virtually no penalty.

##### 2. Pass "alpha=True" to the BufferedRenderer constructor.
All internal buffers will now support 'per-pixel alpha' and the areas without
tiles will be fully transparent, so draw something under the map first.
Since per-pixel alpha buffers are used, overall performance will be reduced.


## Can I blit anything 'under' the scrolling map layer?
Yes!  There are two ways to handle this situation...both are experimental, but
should work.  These options will cause the renderer to do more housekeeping,
actively clearing empty spaces in the buffer, so overall performance will be
reduced.

##### 1. Pass "alpha=True" to the constructor.
When drawing the screen, first blit what you want to be under the map (like
a background, or parallax layer), then draw the pyscroll renderer or group.
Since per-pixel alpha buffers are used, overall performance will be reduced.

##### 2. Set a colorkey.
Pass "colorkey=theColorYouWant" to the BufferedRenderer constructor.  In
theory, you can now blit the map layer over other surfaces with transparency,
but beware that it will produce some nasty side effects:

1. Overall, performance will be reduced, as empty ares are being filled.
2. If mixing 'per-pixel alpha' tilesets, tile edges may show the colorkey.

## Does the map layer support transparency?
Yes...and no.  By default, pyscroll handles all transparency types very well
for the tiles and you should not have issues with that.  However, if you are
trying to blit/draw the map *over* existing graphics and "see through"
transparent areas under the map, then you will have to use the "alpha", or
"colorkey" methods described above.

## Does pyscroll support parallax layers?
Not directly yet (it is planned).  However, you can build you own parallax
effects by passing "alpha=True" to the BufferedRenderer constructor and using
one renderer for each layer. Then it is just a matter of scrolling at
different speeds.  The "Parallax" page of the documentation has an example.
