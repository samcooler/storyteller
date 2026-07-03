"""Shared FF-style vector menu chrome: gradient boxes, borders, bars, cursors."""

import pygame

PASTEL_TOP = (58, 40, 74)
PASTEL_BOTTOM = (94, 58, 110)
BORDER_OUTER = (245, 225, 250)
BORDER_INNER = (255, 190, 230)
TEXT_COLOR = (255, 245, 250)
DIM_TEXT = (200, 180, 205)
ACCENT = (255, 200, 235)


def draw_panel(surface, rect, top_color=PASTEL_TOP, bottom_color=PASTEL_BOTTOM,
               border_color=BORDER_OUTER, inner_border_color=BORDER_INNER):
    height = rect.height
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3))
        pygame.draw.line(surface, color, (rect.left, rect.top + y), (rect.right, rect.top + y))
    pygame.draw.rect(surface, border_color, rect, width=3)
    pygame.draw.rect(surface, inner_border_color, rect.inflate(-6, -6), width=1)
    tick = 6
    for corner in [rect.topleft, rect.topright, rect.bottomleft, rect.bottomright]:
        pygame.draw.line(surface, border_color, corner, (corner[0], corner[1]), 0)
    pygame.draw.line(surface, inner_border_color, (rect.left + tick, rect.top + 4), (rect.left + 4, rect.top + tick))
    pygame.draw.line(surface, inner_border_color, (rect.right - tick, rect.top + 4), (rect.right - 4, rect.top + tick))


def draw_cursor(surface, pos, color=ACCENT, size=8):
    x, y = pos
    pygame.draw.polygon(surface, color, [(x, y - size // 2), (x, y + size // 2), (x + size, y)])


def draw_bar(surface, rect, value, max_value, fill_color, bg_color=(40, 30, 45), border_color=BORDER_OUTER):
    pygame.draw.rect(surface, bg_color, rect)
    frac = max(0.0, min(1.0, value / max_value))
    fill_rect = pygame.Rect(rect.left, rect.top, int(rect.width * frac), rect.height)
    pygame.draw.rect(surface, fill_color, fill_rect)
    pygame.draw.rect(surface, border_color, rect, width=1)
