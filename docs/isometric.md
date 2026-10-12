# Isometric maps

```{warning}
Isometric rendering is **experimental and does not work** in this version.
Creating an `IsometricBufferedRenderer` raises `TypeError`, and the class has
known gaps (no edge-tile queuing, no depth sorting, no sprite covering). It is
being removed from the top-level `pyscroll` package; if you want to work on it,
import it from {mod}`pyscroll.isometric`.
```

For now, pyscroll only renders orthogonal (top-down, square-grid) maps.

## Coordinate helpers

{mod}`pyscroll.isometric` has two small helpers that convert grid
coordinates to isometric screen coordinates. They work on integers and don't
depend on the renderer:

```python
from pyscroll.isometric import vector2_to_iso, vector3_to_iso

# x' = x - y,  y' = (x + y) // 2
print(vector2_to_iso((4, 2)))            # (2, 3)

# a third coordinate, z (height), moves the point up
print(vector3_to_iso((4, 2, 1)))         # (2, 2)

# an optional offset is added to the result
print(vector2_to_iso((4, 2), (10, 10)))  # (12, 13)
```

Both raise `ValueError` if the tuple has the wrong number of elements.
