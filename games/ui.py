"""Shared FF-style vector menu chrome: gradient boxes, borders, bars, cursors.

Everything here takes a `scale` factor (see `scale_factor`) so the same
drawing code looks right on a small Pi touchscreen and a 4K monitor.
"""

from pathlib import Path

import pygame

PASTEL_TOP = (58, 40, 74)
PASTEL_BOTTOM = (94, 58, 110)
BORDER_OUTER = (245, 225, 250)
BORDER_INNER = (255, 190, 230)
TEXT_COLOR = (255, 245, 250)
DIM_TEXT = (200, 180, 205)
ACCENT = (255, 200, 235)

REFERENCE_DIM = 540  # short edge of the internal render surface; raise this to shrink text relative to it
_font_cache = {}

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
BODY_FONT_PATH = FONT_DIR / "VT323-Regular.ttf"
TITLE_FONT_PATH = FONT_DIR / "PressStart2P-Regular.ttf"
TITLE_SIZE_RATIO = 0.4  # Press Start 2P is much wider per glyph than VT323


class PixelFont:
    """Wraps a pygame Font so every render() is hard-edged (no anti-aliasing),
    regardless of what the antialias argument the caller passes."""

    __slots__ = ("_font",)

    def __init__(self, font_obj):
        self._font = font_obj

    def render(self, text, _antialias, color):
        return self._font.render(text, False, color)

    def size(self, text):
        return self._font.size(text)

    def get_height(self):
        return self._font.get_height()


def scale_factor(surface):
    return min(surface.get_size()) / REFERENCE_DIM


def font(size, scale, title=False):
    path = TITLE_FONT_PATH if title else BODY_FONT_PATH
    point_size = size * TITLE_SIZE_RATIO if title else size
    key = (str(path), max(6, int(point_size * scale)))
    cached = _font_cache.get(key)
    if cached is None:
        try:
            raw = pygame.font.Font(str(path), key[1])
        except (FileNotFoundError, OSError):
            raw = pygame.font.SysFont(None, key[1])
        cached = PixelFont(raw)
        _font_cache[key] = cached
    return cached


_gradient_cache = {}


def _gradient_surface(width, height, top_color, bottom_color):
    key = (width, height, top_color, bottom_color)
    cached = _gradient_cache.get(key)
    if cached is not None:
        return cached
    if len(_gradient_cache) > 500:
        _gradient_cache.clear()
    grad = pygame.Surface((width, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3))
        pygame.draw.line(grad, color, (0, y), (width, y))
    _gradient_cache[key] = grad
    return grad


def draw_panel(surface, rect, scale=1.0, top_color=PASTEL_TOP, bottom_color=PASTEL_BOTTOM,
               border_color=BORDER_OUTER, inner_border_color=BORDER_INNER):
    if rect.width > 0 and rect.height > 0:
        grad = _gradient_surface(rect.width, rect.height, top_color, bottom_color)
        surface.blit(grad, rect.topleft)
    border_w = max(1, round(3 * scale))
    inner_w = max(1, round(1 * scale))
    inset = max(2, round(6 * scale))
    tick = max(3, round(6 * scale))
    pygame.draw.rect(surface, border_color, rect, width=border_w)
    pygame.draw.rect(surface, inner_border_color, rect.inflate(-inset, -inset), width=inner_w)
    pygame.draw.line(surface, inner_border_color, (rect.left + tick, rect.top + 4), (rect.left + 4, rect.top + tick))
    pygame.draw.line(surface, inner_border_color, (rect.right - tick, rect.top + 4), (rect.right - 4, rect.top + tick))


def draw_dashed_line(surface, color, start, end, width=1, dash=10, gap=6):
    x1, y1 = start
    x2, y2 = end
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if length < 1:
        return
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0.0
    while pos < length:
        seg_end = min(pos + dash, length)
        p1 = (x1 + dx * pos, y1 + dy * pos)
        p2 = (x1 + dx * seg_end, y1 + dy * seg_end)
        pygame.draw.line(surface, color, p1, p2, width)
        pos += dash + gap


def wrap_text(font_obj, text, max_width):
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font_obj.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def blit_wrapped(surface, font_obj, text, color, center_x, top_y, max_width, line_spacing=1.15):
    for i, line in enumerate(wrap_text(font_obj, text, max_width)):
        label = font_obj.render(line, True, color)
        surface.blit(label, label.get_rect(midtop=(center_x, top_y + int(i * font_obj.get_height() * line_spacing))))


def draw_cursor(surface, pos, color=ACCENT, size=8):
    x, y = pos
    pygame.draw.polygon(surface, color, [(x, y - size // 2), (x, y + size // 2), (x + size, y)])


def draw_bar(surface, rect, value, max_value, fill_color, bg_color=(40, 30, 45), border_color=BORDER_OUTER, border_w=1):
    pygame.draw.rect(surface, bg_color, rect)
    frac = max(0.0, min(1.0, value / max_value))
    fill_rect = pygame.Rect(rect.left, rect.top, int(rect.width * frac), rect.height)
    pygame.draw.rect(surface, fill_color, fill_rect)
    pygame.draw.rect(surface, border_color, rect, width=border_w)
