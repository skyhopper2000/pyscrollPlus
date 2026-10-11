# Benchmarks

`bench_render.py` measures rendering throughput (frames/second) of
`BufferedRenderer` and `PyscrollGroup` on `apps/demo/desert.tmx`. It runs
headless (`SDL_VIDEODRIVER=dummy`), so it works over SSH and in CI.

```sh
python benchmarks/bench_render.py           # 600 frames per scenario
python benchmarks/bench_render.py --quick   # 60 frames per scenario
python benchmarks/bench_render.py --frames 2000 --size 1280x720
python benchmarks/bench_render.py --map path/to/other.tmx
```

| scenario               | what it exercises                                                    |
|------------------------|----------------------------------------------------------------------|
| `scroll`               | smooth camera movement (3 px/frame): the incremental edge-tile path  |
| `jump (forced redraw)` | camera jumps across the map every frame: `redraw_tiles` every frame  |
| `zoom 2.0`             | `zoom = 2` with smooth scrolling: zoom buffer plus scaling           |
| `200 sprites (group)`  | `PyscrollGroup.draw` with 200 sprites spread over all tile layers    |
| `alpha=True scroll`    | per-pixel-alpha buffers with smooth scrolling                        |

Every scenario renders into an off-screen surface, so the numbers measure
pyscroll and pygame blitting rather than display flipping or vsync.

The numbers only mean something relative to each other on the same machine
and pygame build. To check a change for regressions, run the benchmark on
`master` and on your branch back to back. `--quick` is a smoke run; its
numbers are noisy.

The script is not collected by pytest, because `pytest.ini` restricts
`testpaths` to `tests/`.
