pyscroll
========

A simple and fast module for animated scrolling maps for your new or existing
pygame game.

pyscroll draws a tile map into an off-screen buffer and only redraws the tiles
that scroll into view, so drawing speed does not depend on map size. It doesn't
load images or map files itself: maps made with the `Tiled map editor
<https://www.mapeditor.org/>`_ work out of the box through `pytmx
<https://github.com/bitcraft/pytmx>`_, and any other map format can be plugged
in with a small adapter class.

Features
--------

- Fast, with a small footprint. Speed is not affected by map size.
- Layered drawing: sprites and plain surfaces are drawn between tile layers, so
  tiles on higher layers cover them.
- :class:`~pyscroll.PyscrollGroup`, a drop-in replacement for pygame's
  ``LayeredUpdates`` that works like a camera.
- Zoom in and out, and translate world coordinates to screen coordinates.
- Optional camera clamping to the map edges.
- Animated tiles from Tiled, and hot reload of the map while the game runs.
- Per-sprite blend modes.
- Pixel-alpha and colorkey tilesets; transparent map buffers for drawing the
  map over a background.
- Several maps stitched into one world with ``MapAggregator`` (experimental).

Requirements: Python 3.9+, and pygame 2 or pygame-ce. pytmx is only needed to
load Tiled maps.

.. code-block:: text

   pip install pyscroll pytmx

.. toctree::
   :maxdepth: 2
   :caption: Guide

   quickstart
   camera
   sprites
   animation
   adapters
   multiple-maps
   transparency
   parallax
   isometric

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api

* :ref:`genindex`
* :ref:`modindex`
