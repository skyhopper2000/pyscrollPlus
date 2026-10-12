"""
Parallax scrolling demo for pyscroll.

parallax.tmx has three tile layers with Tiled parallax factors:

* "water"   0.5   (far away, animated)
* "islands" 1.0   (the sprite band; the hero walks here)
* "canopy"  1.25  (foreground, drawn over the hero)

Arrow keys move the hero (the camera follows), + and - zoom, Esc quits.

Run headless for a few frames:  python parallax.py --frames 60
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pygame
from pytmx.util_pygame import load_pygame

from pyscroll.group import PyscrollGroup
from pyscroll.parallax import ParallaxRenderer

HERE = Path(__file__).parent
SPEED = 200  # pixels per second


class Hero(pygame.sprite.Sprite):
    def __init__(self, position) -> None:
        super().__init__()
        self.image = pygame.image.load(str(HERE / "hero.png")).convert_alpha()
        self.rect = self.image.get_rect(center=position)
        self.position = pygame.Vector2(position)

    def update(self, dt: float, direction: pygame.Vector2, bounds: pygame.Rect):
        self.position += direction * SPEED * dt
        self.position.x = max(bounds.left, min(bounds.right, self.position.x))
        self.position.y = max(bounds.top, min(bounds.bottom, self.position.y))
        self.rect.center = round(self.position.x), round(self.position.y)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=0, help="quit after N frames")
    parser.add_argument("--screenshot", help="save the last frame to this file")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
    pygame.display.set_caption("pyscroll parallax demo")

    tmx = load_pygame(str(HERE / "parallax.tmx"))
    map_center = (tmx.width * tmx.tilewidth / 2, tmx.height * tmx.tileheight / 2)
    # all bands line up when the camera is in the middle of the map
    renderer = ParallaxRenderer.from_tiled(
        tmx, screen.get_size(), origin=map_center, zoom=2.0
    )
    group = PyscrollGroup(map_layer=renderer)
    hero = Hero(map_center)
    # the islands layer is tmx layer 1; put the hero above it
    group.add(hero, layer=1)

    font = pygame.font.Font(None, 22)
    help_text = font.render(
        "arrows: move   +/-: zoom   esc: quit", True, (255, 255, 255), (0, 0, 0)
    )

    clock = pygame.time.Clock()
    frames = 0
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    renderer.zoom = min(renderer.zoom + 0.25, 4.0)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    renderer.zoom = max(renderer.zoom - 0.25, 0.5)
            elif event.type == pygame.VIDEORESIZE:
                renderer.set_size((event.w, event.h))

        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(
            keys[pygame.K_RIGHT] - keys[pygame.K_LEFT],
            keys[pygame.K_DOWN] - keys[pygame.K_UP],
        )
        if args.frames:
            # headless: wander right and down so every band scrolls
            direction = pygame.Vector2(1, 0.5)
        if direction.length_squared():
            direction = direction.normalize()
        group.update(dt, direction, renderer.map_rect)
        group.center(hero.rect.center)
        group.draw(screen)
        screen.blit(help_text, (8, 8))
        pygame.display.flip()

        frames += 1
        if args.frames and frames >= args.frames:
            running = False

    if args.screenshot:
        pygame.image.save(screen, args.screenshot)
    pygame.quit()


if __name__ == "__main__":
    main()
