"""Shared FF-style vector menu chrome: gradient boxes, borders, bars, cursors.

Everything here takes a `scale` factor (see `scale_factor`) so the same
drawing code looks right on a small Pi touchscreen and a 4K monitor.
"""

import math
from pathlib import Path

import pygame

THEMES = {
    "dusk_rose": {
        "label": "Dusk Rose",
        "bg": (24, 16, 30),
        "pastel_top": (58, 40, 74),
        "pastel_bottom": (94, 58, 110),
        "border_outer": (245, 225, 250),
        "border_inner": (255, 190, 230),
        "text": (255, 245, 250),
        "dim_text": (200, 180, 205),
        "accent": (255, 200, 235),
    },
    "midnight_azure": {
        "label": "Midnight Azure",
        "bg": (10, 14, 26),
        "pastel_top": (20, 30, 60),
        "pastel_bottom": (35, 55, 95),
        "border_outer": (210, 225, 250),
        "border_inner": (150, 190, 240),
        "text": (235, 240, 255),
        "dim_text": (160, 180, 210),
        "accent": (255, 210, 110),
    },
    "ember": {
        "label": "Ember",
        "bg": (24, 12, 10),
        "pastel_top": (70, 30, 20),
        "pastel_bottom": (110, 50, 25),
        "border_outer": (250, 215, 180),
        "border_inner": (255, 160, 90),
        "text": (255, 240, 220),
        "dim_text": (210, 160, 130),
        "accent": (255, 120, 90),
    },
    "verdant": {
        "label": "Verdant",
        "bg": (10, 18, 14),
        "pastel_top": (25, 55, 35),
        "pastel_bottom": (40, 85, 55),
        "border_outer": (215, 240, 210),
        "border_inner": (150, 220, 160),
        "text": (235, 250, 235),
        "dim_text": (165, 200, 175),
        "accent": (180, 230, 120),
    },
}
THEME_ORDER = ["dusk_rose", "midnight_azure", "ember", "verdant"]

_current_theme_name = None
BG = PASTEL_TOP = PASTEL_BOTTOM = None
BORDER_OUTER = BORDER_INNER = None
TEXT_COLOR = DIM_TEXT = ACCENT = None


def set_theme(name):
    """Swap the active color palette. Every consumer reads these as `ui.X`
    attribute access (never `from games.ui import X`), so reassigning the
    module globals here takes effect immediately everywhere."""
    global _current_theme_name, BG, PASTEL_TOP, PASTEL_BOTTOM
    global BORDER_OUTER, BORDER_INNER, TEXT_COLOR, DIM_TEXT, ACCENT
    theme = THEMES[name]
    _current_theme_name = name
    BG = theme["bg"]
    PASTEL_TOP = theme["pastel_top"]
    PASTEL_BOTTOM = theme["pastel_bottom"]
    BORDER_OUTER = theme["border_outer"]
    BORDER_INNER = theme["border_inner"]
    TEXT_COLOR = theme["text"]
    DIM_TEXT = theme["dim_text"]
    ACCENT = theme["accent"]


def current_theme_name():
    return _current_theme_name


def cycle_theme(step=1):
    """Move to the next (or previous, step=-1) theme in THEME_ORDER and return its name."""
    idx = THEME_ORDER.index(_current_theme_name)
    name = THEME_ORDER[(idx + step) % len(THEME_ORDER)]
    set_theme(name)
    return name


set_theme(THEME_ORDER[0])

REFERENCE_DIM = 540  # short edge of the internal render surface; raise this to shrink text relative to it
_font_cache = {}

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
BODY_FONT_PATH = FONT_DIR / "MPLUS1p-Medium.ttf"
TITLE_FONT_PATH = FONT_DIR / "MPLUS1p-ExtraBold.ttf"
TITLE_SIZE_RATIO = 1.0  # both fonts are normal proportional weights of the same family now
BODY_SIZE_RATIO = 0.8  # MPLUS1p is noticeably wider per glyph than the old VT323; sizes were tuned for that


class GameFont:
    """Wraps a pygame Font so every render() is anti-aliased, regardless of what
    the antialias argument the caller passes - smooth text instead of the harsh
    forced-jagged look of a bitmap/pixel font blown up to UI size."""

    __slots__ = ("_font",)

    def __init__(self, font_obj):
        self._font = font_obj

    def render(self, text, _antialias, color):
        return self._font.render(text, True, color)

    def size(self, text):
        return self._font.size(text)

    def get_height(self):
        return self._font.get_height()


def scale_factor(surface):
    return min(surface.get_size()) / REFERENCE_DIM


def font(size, scale, title=False):
    path = TITLE_FONT_PATH if title else BODY_FONT_PATH
    point_size = size * (TITLE_SIZE_RATIO if title else BODY_SIZE_RATIO)
    key = (str(path), max(6, int(point_size * scale)))
    cached = _font_cache.get(key)
    if cached is None:
        try:
            raw = pygame.font.Font(str(path), key[1])
        except (FileNotFoundError, OSError):
            raw = pygame.font.SysFont(None, key[1])
        cached = GameFont(raw)
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


def _shade(color, amount):
    """Lighten (amount > 0) or darken (amount < 0) an RGB color, clamped to [0, 255]."""
    return tuple(max(0, min(255, c + amount)) for c in color)


def _draw_corner_bracket(surface, corner, sx, sy, size, width, color):
    """Filled L-shaped corner plate with a diagonal chamfer cut where the two arms
    meet - reads as a distinct metal bracket clipped over the corner rather than a
    plain miter. Used on cards: sharp and game-y."""
    cx, cy = corner
    t = max(2, size * 0.4)
    pts = [
        (cx, cy),
        (cx + sx * size, cy),
        (cx + sx * size, cy + sy * t),
        (cx + sx * t, cy + sy * t),
        (cx + sx * t, cy + sy * size),
        (cx, cy + sy * size),
    ]
    pygame.draw.polygon(surface, _shade(color, 20), pts)
    pygame.draw.polygon(surface, _shade(color, -60), pts, width)


def _draw_corner_diamond(surface, corner, sx, sy, size, width, color):
    """A small gem/diamond set into the corner, like a jeweled window-frame accent.
    Used on display windows (roster, calendar, network panel)."""
    cx, cy = corner
    d = size * 0.55
    r = size * 0.42
    center = (cx + sx * d, cy + sy * d)
    pts = [
        (center[0], center[1] - r),
        (center[0] + r, center[1]),
        (center[0], center[1] + r),
        (center[0] - r, center[1]),
    ]
    pygame.draw.polygon(surface, _shade(color, 25), pts)
    pygame.draw.polygon(surface, color, pts, max(1, width - 1))
    pygame.draw.line(surface, color, corner, (center[0], center[1] - r) if sy == 1 else (center[0], center[1] + r), max(1, width - 1))
    pygame.draw.line(surface, color, corner, (center[0] - r, center[1]) if sx == 1 else (center[0] + r, center[1]), max(1, width - 1))


_CURL_ANGLES = {
    (1, 1): (math.pi, 1.5 * math.pi),
    (-1, 1): (1.5 * math.pi, 2 * math.pi),
    (1, -1): (0.5 * math.pi, math.pi),
    (-1, -1): (0, 0.5 * math.pi),
}


def _draw_corner_curl(surface, corner, sx, sy, size, width, color):
    """Ornate filigree hook: a rounded arc through the corner plus a small curled tail
    past each end, like a wrought-iron frame flourish. Used for the whole-screen frame."""
    cx, cy = corner
    r = size
    center = (cx + sx * r, cy + sy * r)
    arc_rect = pygame.Rect(int(center[0] - r), int(center[1] - r), int(r * 2), int(r * 2))
    start, end = _CURL_ANGLES[(sx, sy)]
    pygame.draw.arc(surface, color, arc_rect, start, end, width)
    tail = size * 0.5
    pygame.draw.line(surface, color, (cx + sx * size, cy), (cx + sx * (size + tail * 0.4), cy - sy * tail * 0.5), max(1, width - 1))
    pygame.draw.line(surface, color, (cx, cy + sy * size), (cx - sx * tail * 0.5, cy + sy * (size + tail * 0.4)), max(1, width - 1))


CORNER_STYLES = {
    "bracket": _draw_corner_bracket,
    "diamond": _draw_corner_diamond,
    "curl": _draw_corner_curl,
}


def draw_corners(surface, rect, scale=1.0, color=None, style="bracket", size=14, width=2):
    """Draw the four corner ornaments for `style` around `rect`."""
    if color is None:
        color = BORDER_INNER
    draw_fn = CORNER_STYLES.get(style, _draw_corner_bracket)
    corner_size = max(4, round(size * scale))
    corner_w = max(1, round(width * scale))
    draw_fn(surface, (rect.left, rect.top), 1, 1, corner_size, corner_w, color)
    draw_fn(surface, (rect.right, rect.top), -1, 1, corner_size, corner_w, color)
    draw_fn(surface, (rect.left, rect.bottom), 1, -1, corner_size, corner_w, color)
    draw_fn(surface, (rect.right, rect.bottom), -1, -1, corner_size, corner_w, color)


def draw_panel(surface, rect, scale=1.0, top_color=None, bottom_color=None,
               border_color=None, inner_border_color=None, corner_style="bracket"):
    top_color = PASTEL_TOP if top_color is None else top_color
    bottom_color = PASTEL_BOTTOM if bottom_color is None else bottom_color
    border_color = BORDER_OUTER if border_color is None else border_color
    inner_border_color = BORDER_INNER if inner_border_color is None else inner_border_color
    if rect.width > 0 and rect.height > 0:
        grad = _gradient_surface(rect.width, rect.height, top_color, bottom_color)
        surface.blit(grad, rect.topleft)
    border_w = max(1, round(3 * scale))
    inner_w = max(1, round(1 * scale))
    inset = max(2, round(6 * scale))
    pygame.draw.rect(surface, border_color, rect, width=border_w)

    # Inset bevel: light edge top/left, dark edge bottom/right, faking a top-left light source.
    bevel = border_w + max(1, round(2 * scale))
    light, dark = _shade(border_color, 45), _shade(border_color, -70)
    tl = (rect.left + bevel, rect.top + bevel)
    tr = (rect.right - bevel, rect.top + bevel)
    bl = (rect.left + bevel, rect.bottom - bevel)
    br = (rect.right - bevel, rect.bottom - bevel)
    pygame.draw.line(surface, light, tl, tr, inner_w)
    pygame.draw.line(surface, light, tl, bl, inner_w)
    pygame.draw.line(surface, dark, bl, br, inner_w)
    pygame.draw.line(surface, dark, tr, br, inner_w)

    pygame.draw.rect(surface, inner_border_color, rect.inflate(-inset, -inset), width=inner_w)
    draw_corners(surface, rect, scale, color=inner_border_color, style=corner_style)


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


def draw_cursor(surface, pos, color=None, size=8):
    color = ACCENT if color is None else color
    x, y = pos
    pygame.draw.polygon(surface, color, [(x, y - size // 2), (x, y + size // 2), (x + size, y)])


def draw_bar(surface, rect, value, max_value, fill_color, bg_color=(40, 30, 45), border_color=None, border_w=1):
    border_color = BORDER_OUTER if border_color is None else border_color
    pygame.draw.rect(surface, bg_color, rect)
    frac = max(0.0, min(1.0, value / max_value))
    fill_rect = pygame.Rect(rect.left, rect.top, int(rect.width * frac), rect.height)
    pygame.draw.rect(surface, fill_color, fill_rect)
    if border_w > 0:
        pygame.draw.rect(surface, border_color, rect, width=border_w)


def draw_bar_vertical(surface, rect, value, max_value, fill_color, bg_color=(40, 30, 45), border_color=None, border_w=1):
    """Bottom-up filled bar, for dense side-by-side stat strips."""
    border_color = BORDER_OUTER if border_color is None else border_color
    pygame.draw.rect(surface, bg_color, rect)
    frac = max(0.0, min(1.0, value / max_value))
    fill_h = int(rect.height * frac)
    fill_rect = pygame.Rect(rect.left, rect.bottom - fill_h, rect.width, fill_h)
    pygame.draw.rect(surface, fill_color, fill_rect)
    if border_w > 0:
        pygame.draw.rect(surface, border_color, rect, width=border_w)


def draw_ring_segments(surface, center, radius, values, colors, thickness=4, gap_deg=6,
                        bg_color=(60, 50, 65), max_value=100):
    """Draw a multi-stat gauge as N arc segments around a circle.

    Segments are laid out clockwise starting at 12 o'clock, one per entry in
    `values`/`colors`. Each segment's full angular span is drawn dim first,
    then overdrawn with the live color out to `value / max_value` of that
    span, so partial fill reads at a glance without needing numbers.
    """
    n = len(values)
    if n == 0 or radius <= 0:
        return
    rect = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
    sector = 2 * math.pi / n
    gap = math.radians(gap_deg)
    for i in range(n):
        lo = math.pi / 2 - (i + 1) * sector + gap / 2
        hi = math.pi / 2 - i * sector - gap / 2
        if hi <= lo:
            continue
        pygame.draw.arc(surface, bg_color, rect, lo, hi, thickness)
        frac = max(0.0, min(1.0, values[i] / max_value))
        if frac <= 0:
            continue
        fill_hi = lo + (hi - lo) * frac
        pygame.draw.arc(surface, colors[i], rect, lo, fill_hi, thickness)


_vignette_cache = {}


def build_vignette(size, max_alpha=70):
    """A soft edge-darkening overlay, cached by size since it's expensive to rebuild
    per-pixel. Built from four small 1D gradient strips scaled up rather than a full
    per-pixel loop, which would be too slow in pure Python at 1080p+."""
    cached = _vignette_cache.get(size)
    if cached is not None:
        return cached
    w, h = size
    band = max(8, min(w, h) // 6)
    overlay = pygame.Surface(size, pygame.SRCALPHA)

    strip_w = pygame.Surface((band, 1), pygame.SRCALPHA)
    for x in range(band):
        t = 1 - x / max(band - 1, 1)
        strip_w.set_at((x, 0), (0, 0, 0, int(max_alpha * t * t)))
    left = pygame.transform.scale(strip_w, (band, h))
    overlay.blit(left, (0, 0))
    overlay.blit(pygame.transform.flip(left, True, False), (w - band, 0))

    strip_h = pygame.Surface((1, band), pygame.SRCALPHA)
    for y in range(band):
        t = 1 - y / max(band - 1, 1)
        strip_h.set_at((0, y), (0, 0, 0, int(max_alpha * t * t)))
    top = pygame.transform.scale(strip_h, (w, band))
    overlay.blit(top, (0, 0), special_flags=pygame.BLEND_RGBA_MAX)
    overlay.blit(pygame.transform.flip(top, False, True), (0, h - band), special_flags=pygame.BLEND_RGBA_MAX)

    _vignette_cache[size] = overlay
    return overlay


def draw_screen_frame(surface, rect, scale=1.0, color=None, vignette_alpha=70):
    """Full-screen ornate chrome: a soft vignette plus a curl-cornered frame line just
    inside the display edge. Call once per frame, after everything else has been drawn
    and scaled onto the real display surface."""
    color = BORDER_OUTER if color is None else color
    surface.blit(build_vignette(rect.size, vignette_alpha), rect.topleft)
    inset = max(3, round(10 * scale))
    frame_rect = rect.inflate(-inset * 2, -inset * 2)
    border_w = max(1, round(2 * scale))
    pygame.draw.rect(surface, color, frame_rect, width=border_w)
    draw_corners(surface, frame_rect, scale, color=color, style="curl", size=30, width=3)
