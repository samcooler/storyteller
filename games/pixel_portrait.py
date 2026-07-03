"""Character bust portraits.

Prefers the hand-picked portrait art in assets/portraits/ (sliced from
AI-generated grids), assigned deterministically per character seed. Falls
back to a tiny procedural pixel-art bust, drawn on a grid and scaled with
nearest-neighbor so it stays chunky, if no portrait art is available.
"""

import random
from pathlib import Path

import pygame

PORTRAITS_DIR = Path(__file__).resolve().parent.parent / "assets" / "portraits"

_portrait_files = None
_portrait_cache = {}
_scaled_cache = {}

GRID = 16

SKIN_TONES = [
    (255, 219, 172), (240, 184, 135), (198, 134, 66),
    (141, 85, 36), (255, 205, 148), (120, 70, 40),
]
HAIR_COLORS = [
    (40, 30, 30), (90, 50, 20), (230, 210, 60), (200, 60, 60),
    (60, 60, 200), (30, 160, 160), (230, 230, 230), (160, 40, 160),
]
SHIRT_COLORS = [
    (200, 90, 120), (90, 150, 200), (120, 190, 120), (220, 160, 60),
    (160, 110, 200), (90, 90, 90),
]
HAIR_STYLES = ["short", "long", "mohawk", "buzz", "bun"]


def _draw_hair(px, style, hair_color):
    if style == "short":
        for y in range(0, 3):
            for x in range(3, 13):
                px[y][x] = hair_color
        for x in (3, 4, 11, 12):
            px[3][x] = hair_color
    elif style == "long":
        for y in range(0, 3):
            for x in range(2, 14):
                px[y][x] = hair_color
        for y in range(3, 9):
            px[y][2] = hair_color
            px[y][13] = hair_color
    elif style == "mohawk":
        for y in range(0, 4):
            for x in range(7, 9):
                px[y][x] = hair_color
        for x in (5, 6, 9, 10):
            px[3][x] = hair_color
    elif style == "buzz":
        for x in range(4, 12):
            px[1][x] = hair_color
            px[2][x] = hair_color
    elif style == "bun":
        for y in range(0, 3):
            for x in range(3, 13):
                px[y][x] = hair_color
        for x in (7, 8):
            px[0][x] = hair_color


def _list_portrait_files():
    global _portrait_files
    if _portrait_files is None:
        if PORTRAITS_DIR.is_dir():
            _portrait_files = sorted(p for p in PORTRAITS_DIR.glob("*.png"))
        else:
            _portrait_files = []
    return _portrait_files


def _load_portrait(path):
    surface = _portrait_cache.get(path)
    if surface is None:
        surface = pygame.image.load(str(path)).convert()
        _portrait_cache[path] = surface
    return surface


def draw_bust(surface, rect, seed, hair_style=None, hair_color=None,
              skin_tone=None, shirt_color=None):
    files = _list_portrait_files()
    if files:
        path = files[seed % len(files)]
        cache_key = (path, rect.size)
        scaled = _scaled_cache.get(cache_key)
        if scaled is None:
            art = _load_portrait(path)
            scaled = pygame.transform.smoothscale(art, rect.size)
            _scaled_cache[cache_key] = scaled
        surface.blit(scaled, rect.topleft)
        return
    _draw_procedural_bust(surface, rect, seed, hair_style, hair_color, skin_tone, shirt_color)


def _draw_procedural_bust(surface, rect, seed, hair_style, hair_color, skin_tone, shirt_color):
    rng = random.Random(seed)
    skin = skin_tone or rng.choice(SKIN_TONES)
    hair = hair_color or rng.choice(HAIR_COLORS)
    shirt = shirt_color or rng.choice(SHIRT_COLORS)
    style = hair_style or rng.choice(HAIR_STYLES)
    eye_color = (30, 30, 30)

    px = [[None] * GRID for _ in range(GRID)]

    for y in range(4, 12):
        for x in range(3, 13):
            px[y][x] = skin

    _draw_hair(px, style, hair)

    px[7][5] = eye_color
    px[7][6] = eye_color
    px[7][9] = eye_color
    px[7][10] = eye_color

    for x in range(6, 10):
        px[10][x] = (150, 90, 90)

    for y in range(12, GRID):
        for x in range(2, 14):
            px[y][x] = shirt

    cell = rect.width / GRID
    cell_h = rect.height / GRID
    for y in range(GRID):
        for x in range(GRID):
            color = px[y][x]
            if color is None:
                continue
            cell_rect = pygame.Rect(
                rect.left + int(x * cell), rect.top + int(y * cell_h),
                int(cell) + 1, int(cell_h) + 1,
            )
            surface.fill(color, cell_rect)
