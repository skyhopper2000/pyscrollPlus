from __future__ import annotations

import heapq
import time

import pygame
import pytest
from synthetic_map import SyntheticMapData

from pyscroll.animation import AnimationFrame, AnimationToken
from pyscroll.orthographic import BufferedRenderer

# ----------------------------------------------------------------------
# AnimationToken


def frames(*durations):
    return [AnimationFrame(f"img{i}", d) for i, d in enumerate(durations)]


def test_empty_frames_raise():
    with pytest.raises(ValueError):
        AnimationToken(set(), [])


def test_initial_state():
    token = AnimationToken({(1, 2, 0)}, frames(100, 200), initial_time=1000)
    assert token.index == 0
    assert token.next == 1100
    assert token.positions == {(1, 2, 0)}
    assert isinstance(token.frames, tuple)


def test_frames_accept_plain_tuples():
    token = AnimationToken(set(), [("a", 10), ("b", 20)])
    assert token.frames == (AnimationFrame("a", 10), AnimationFrame("b", 20))


def test_advance_returns_next_frame_and_schedules_it():
    token = AnimationToken(set(), frames(100, 200, 300), initial_time=0)
    frame = token.advance(100)
    assert frame == AnimationFrame("img1", 200)
    assert token.index == 1
    assert token.next == 300  # last_time + duration of the new frame

    frame = token.advance(300)
    assert frame.image == "img2"
    assert token.next == 600


def test_advance_loops():
    token = AnimationToken(set(), frames(10, 20, 30))
    seen = [token.advance(0).image for _ in range(7)]
    assert seen == ["img1", "img2", "img0", "img1", "img2", "img0", "img1"]


def test_single_frame_loops_onto_itself():
    token = AnimationToken(set(), frames(50))
    assert token.advance(10).image == "img0"
    assert token.index == 0
    assert token.next == 60


def test_ordering():
    early = AnimationToken(set(), frames(10))
    late = AnimationToken(set(), frames(20))
    assert early < late
    assert not late < early
    # comparison against plain numbers
    assert early < 11
    assert not early < 10


def test_heap_ordering():
    tokens = [AnimationToken(set(), frames(d)) for d in (50, 10, 30, 20)]
    heap = []
    for t in tokens:
        heapq.heappush(heap, t)
    assert [heapq.heappop(heap).next for _ in range(4)] == [10, 20, 30, 50]


def test_repr():
    assert "AnimationToken" in repr(AnimationToken(set(), frames(10)))


# ----------------------------------------------------------------------
# animated tiles through the renderer

FRAME_A = (11, 22, 33)
FRAME_B = (44, 55, 66)


def tile_color(renderer, size, world):
    surface = pygame.Surface(size)
    renderer.draw(surface, surface.get_rect())
    return tuple(surface.get_at(renderer.translate_point(world)))[:3]


def test_animated_tile_advances_with_real_time(display):
    # first frame lasts 1ms, second effectively forever
    data = SyntheticMapData(animations={(1, 0, 0): [(FRAME_A, 1), (FRAME_B, 10**9)]})
    r = BufferedRenderer(data, (32, 32))
    r.center((16, 16))
    # the tile was registered for animation while the buffer was drawn
    assert data._animation_queue[0].positions == {(1, 0, 0)}
    time.sleep(0.01)
    assert tile_color(r, (32, 32), (12, 4)) == FRAME_B
    assert tile_color(r, (32, 32), (12, 4)) == FRAME_B


def test_animated_tile_initial_frame(display):
    data = SyntheticMapData(animations={(1, 0, 0): [(FRAME_A, 10**9), (FRAME_B, 10)]})
    r = BufferedRenderer(data, (32, 32))
    r.center((16, 16))
    assert tile_color(r, (32, 32), (12, 4)) == FRAME_A


@pytest.mark.xfail(
    strict=False,
    reason="B3: BufferedRenderer ignores time_source; animations always use time.time()",
)
def test_time_source_drives_animations(display):
    now = [time.time()]

    def clock():
        return now[0]

    # 10s per frame: real time cannot advance the animation during the test
    data = SyntheticMapData(
        animations={(1, 0, 0): [(FRAME_A, 10_000), (FRAME_B, 10_000)]}
    )
    r = BufferedRenderer(data, (32, 32), time_source=clock)
    r.center((16, 16))
    assert tile_color(r, (32, 32), (12, 4)) == FRAME_A

    now[0] += 15  # seconds
    assert tile_color(r, (32, 32), (12, 4)) == FRAME_B

    now[0] += 1  # frame B has 9 more seconds to live
    assert tile_color(r, (32, 32), (12, 4)) == FRAME_B

    now[0] += 10
    assert tile_color(r, (32, 32), (12, 4)) == FRAME_A


# ----------------------------------------------------------------------
# animated.tmx (water.tsx carries Tiled animations)


def test_tiled_animations_loaded(animated_data):
    assert animated_data._animation_queue
    assert all(isinstance(t, AnimationToken) for t in animated_data._animation_queue)


def test_tiled_animated_map_renders_over_time(animated_data):
    size = (160, 120)
    r = BufferedRenderer(animated_data, size)
    r.center((120, 120))
    surface = pygame.Surface(size)
    tracked = set()
    for token in animated_data._animation_queue:
        tracked |= token.positions
    assert tracked, "drawing the buffer should register animated tile positions"

    for _ in range(5):
        r.draw(surface, surface.get_rect())
        r.scroll((3, 1))
        time.sleep(0.005)
