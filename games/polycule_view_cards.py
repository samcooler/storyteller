"""Card-facing widgets: character-target tiles, drawn/discard card previews,
the date sub-choice tile pickers, the turn-step breadcrumb, and the outcome
tier meter."""

import pygame

from . import pixel_portrait, ui
from . import polycule_rules as rules
from .polycule_constants import END_WEEK, KIND_COLORS, OUTCOME_TIERS, STAT_INFO, STAT_ORDER, TURN_STEPS


def card_face(card):
    """(display name, display blurb) - Events are random things that happen
    to you, so they stay a mystery in hand/draw/discard previews and only
    reveal their real name and blurb once actually played."""
    if card["class"] == "events":
        return "Event", "Something's about to happen."
    return card["name"], None


def card_label(card):
    if card is END_WEEK:
        return "end"
    if card["class"] == "dates":
        return card.get("scope", "dates")
    if card["class"] == "choice":
        return card.get("kind", "choice")
    return card["class"]


def target_info(sim, name):
    """Returns (character, kind, stat) where kind is 'member' or 'prospect'
    and stat is the relationship dict (member) or interest int (prospect)."""
    for m in sim.members:
        if m.name == name:
            rel = sim.get_rel(sim.active.name, name) if name != sim.active.name else None
            return m, "member", rel
    prospect = sim.prospects.get(name)
    if prospect:
        return prospect["char"], "prospect", prospect["interest"]
    return None, None, None


def draw_character_card(sim, surface, rect, name, scale, selected):
    border = ui.ACCENT if selected else ui.BORDER_OUTER
    top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
    bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
    ui.draw_panel(surface, rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=border)
    char, kind, stat = target_info(sim, name)
    if char is None:
        return
    pad = int(8 * scale)
    portrait_size = min(rect.width - pad * 2, int(rect.height * 0.32))
    portrait_rect = pygame.Rect(rect.centerx - portrait_size // 2, rect.top + pad, portrait_size, portrait_size)
    pixel_portrait.draw_bust(surface, portrait_rect, char.seed)

    name_font = ui.font(min(14, max(9, rect.width // 8)), scale)
    small_font = ui.font(10, scale)
    y = portrait_rect.bottom + int(3 * scale)
    name_label = name_font.render(char.name, True, ui.TEXT_COLOR)
    surface.blit(name_label, name_label.get_rect(midtop=(rect.centerx, y)))
    y += name_label.get_height() + int(1 * scale)

    for line in ui.wrap_text(small_font, char.archetype, rect.width - pad * 2)[:1]:
        label = small_font.render(line, True, ui.DIM_TEXT)
        surface.blit(label, label.get_rect(midtop=(rect.centerx, y)))
        y += small_font.get_height()
    y += int(3 * scale)

    bar_w = rect.width - pad * 2
    bar_h = max(3, int(7 * scale))
    if kind == "member" and stat is not None:
        ui.draw_bar(surface, pygame.Rect(rect.left + pad, y, bar_w, bar_h), stat["trust"], 100, (140, 180, 240))
        y += bar_h + int(3 * scale)
        ui.draw_bar(surface, pygame.Rect(rect.left + pad, y, bar_w, bar_h), stat["spark"], 100, (240, 140, 190))
        y += bar_h + int(5 * scale)
    elif kind == "prospect":
        ui.draw_bar(surface, pygame.Rect(rect.left + pad, y, bar_w, bar_h), stat, 100, (255, 150, 190))
        y += bar_h + int(5 * scale)

    # Dense 10-cell strip (all traits+statuses as thin bottom-up bars) -
    # too little room here for labels, so this tile is numbers/color only.
    strip_h = max(10, int(16 * scale))
    n = len(STAT_ORDER)
    gap = max(1, int(1 * scale))
    cell_w = (bar_w - gap * (n - 1)) / n
    values = char.stat_values()
    for i, key in enumerate(STAT_ORDER):
        cx = rect.left + pad + i * (cell_w + gap)
        cell_rect = pygame.Rect(int(cx), y, max(1, int(cell_w)), strip_h)
        ui.draw_bar_vertical(surface, cell_rect, values[i], 100, STAT_INFO[key]["color"], border_w=0)


def draw_target_cards(sim, surface, content_rect, scale):
    names = sim.target_options
    gap = int(10 * scale)
    card_w = int(85 * scale)
    card_h = min(content_rect.height, int(170 * scale))
    max_visible = max(1, (content_rect.width + gap) // (card_w + gap))
    if len(names) <= max_visible:
        start_idx = 0
    else:
        start_idx = max(0, min(sim.target_index - max_visible // 2, len(names) - max_visible))
    visible = names[start_idx:start_idx + max_visible]
    total_w = len(visible) * card_w + (len(visible) - 1) * gap
    start_x = content_rect.left + (content_rect.width - total_w) // 2
    for i, name in enumerate(visible):
        idx = start_idx + i
        rect = pygame.Rect(start_x + i * (card_w + gap), content_rect.top, card_w, card_h)
        draw_character_card(sim, surface, rect, name, scale, selected=(idx == sim.target_index))
    arrow_font = ui.font(20, scale)
    if start_idx > 0:
        label = arrow_font.render("<", True, ui.ACCENT)
        surface.blit(label, label.get_rect(midright=(start_x - int(6 * scale), content_rect.top + card_h // 2)))
    if start_idx + len(visible) < len(names):
        label = arrow_font.render(">", True, ui.ACCENT)
        surface.blit(label, label.get_rect(midleft=(start_x + total_w + int(6 * scale), content_rect.top + card_h // 2)))


def draw_card_tiles(sim, surface, content_rect, cards, scale, badge=None):
    """Full-size previews (name, kind tint, wrapped blurb) for cards without a
    real target yet - used by the draw and discard stages."""
    gap = int(12 * scale)
    card_w = min(int(150 * scale), max(int(90 * scale), (content_rect.width - gap * (len(cards) - 1)) // max(1, len(cards))))
    card_h = content_rect.height
    total_w = len(cards) * card_w + (len(cards) - 1) * gap
    start_x = content_rect.left + max(0, content_rect.width - total_w) // 2
    name_font = ui.font(11, scale)
    kind_font = ui.font(9, scale)
    blurb_font = ui.font(9, scale)
    badge_font = ui.font(10, scale)
    for i, card in enumerate(cards):
        rect = pygame.Rect(start_x + i * (card_w + gap), content_rect.top, card_w, card_h)
        label = card_label(card)
        tint = KIND_COLORS.get(label, ui.ACCENT)
        top_color = tuple(min(255, c // 3 + 40) for c in tint)
        bottom_color = tuple(min(255, c // 5 + 20) for c in tint)
        ui.draw_panel(surface, rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=tint)
        pad = int(8 * scale)
        y = rect.top + pad
        display_name, display_blurb = card_face(card)
        name_lines = ui.wrap_text(name_font, display_name, rect.width - pad * 2)
        ui.blit_wrapped(surface, name_font, display_name, ui.TEXT_COLOR, rect.centerx, y, rect.width - pad * 2)
        y += len(name_lines) * int(name_font.get_height() * 1.15) + int(2 * scale)
        kind_label = kind_font.render(label, True, tint)
        surface.blit(kind_label, kind_label.get_rect(midtop=(rect.centerx, y)))
        y += kind_label.get_height() + int(6 * scale)
        blurb_text = display_blurb if display_blurb is not None else rules.preview_blurb(card)
        for line in ui.wrap_text(blurb_font, blurb_text, rect.width - pad * 2):
            if y + blurb_font.get_height() > rect.bottom - pad:
                break
            label_surf = blurb_font.render(line, True, ui.DIM_TEXT)
            surface.blit(label_surf, label_surf.get_rect(midtop=(rect.centerx, y)))
            y += blurb_font.get_height() + int(1 * scale)
        if badge:
            badge_label = badge_font.render(badge, True, ui.BG)
            badge_rect = badge_label.get_rect()
            badge_rect.topright = (rect.right - int(2 * scale), rect.top + int(2 * scale))
            pad_badge = int(3 * scale)
            bg_rect = badge_rect.inflate(pad_badge * 2, pad_badge * 2)
            pygame.draw.rect(surface, tint, bg_rect)
            surface.blit(badge_label, badge_rect)


def draw_choice_tiles(surface, content_rect, scale, options, selected_index):
    """Horizontal tile picker for the date sub-choice flow (week/counter/activity
    steps) - a handful of options, tinted green/red for accept/decline."""
    gap = int(14 * scale)
    n = max(1, len(options))
    card_w = min(int(170 * scale), max(int(90 * scale), (content_rect.width - gap * (n - 1)) // n))
    card_h = min(content_rect.height, int(90 * scale))
    total_w = n * card_w + (n - 1) * gap
    start_x = content_rect.left + max(0, content_rect.width - total_w) // 2
    label_font = ui.font(16, scale)
    for i, (label, value) in enumerate(options):
        rect = pygame.Rect(start_x + i * (card_w + gap), content_rect.top, card_w, card_h)
        selected = i == selected_index
        if value == "decline":
            tint = (230, 90, 90)
        elif value == "accept":
            tint = (150, 220, 150)
        else:
            tint = ui.ACCENT
        top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
        bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
        ui.draw_panel(surface, rect, scale, top_color=top_color, bottom_color=bottom_color,
                      border_color=tint if selected else ui.BORDER_OUTER)
        ui.blit_wrapped(surface, label_font, label, ui.TEXT_COLOR,
                         rect.centerx, rect.centery - label_font.get_height() // 2, rect.width - int(10 * scale))
    return content_rect.top + card_h


def draw_day_strip(surface, content_rect, scale, options, selected_index):
    """7-cell calendar-style row for picking a day of the week."""
    gap = int(8 * scale)
    n = max(1, len(options))
    card_w = min(int(72 * scale), max(int(36 * scale), (content_rect.width - gap * (n - 1)) // n))
    card_h = min(content_rect.height, int(80 * scale))
    total_w = n * card_w + (n - 1) * gap
    start_x = content_rect.left + max(0, content_rect.width - total_w) // 2
    label_font = ui.font(18, scale)
    for i, (label, _value) in enumerate(options):
        rect = pygame.Rect(start_x + i * (card_w + gap), content_rect.top, card_w, card_h)
        selected = i == selected_index
        top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
        bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
        border = ui.ACCENT if selected else ui.BORDER_OUTER
        ui.draw_panel(surface, rect, scale, top_color=top_color, bottom_color=bottom_color,
                      border_color=border, corner_style="diamond")
        label_surf = label_font.render(label, True, ui.TEXT_COLOR)
        surface.blit(label_surf, label_surf.get_rect(center=rect.center))
    return content_rect.top + card_h


def draw_step_row(surface, rect, scale, current_index):
    """Breadcrumb across the top of the main window showing where this turn
    is in the Draw -> Discard -> Play sequence: done steps filled and dim,
    the current step outlined in the accent color, future steps hollow."""
    n = len(TURN_STEPS)
    dot_r = int(7 * scale)
    label_font = ui.font(15, scale)
    gap = (rect.width - dot_r * 2) / max(1, n - 1)
    cy = rect.top + dot_r
    centers = [rect.left + dot_r + int(i * gap) for i in range(n)]
    for i in range(n - 1):
        line_color = ui.ACCENT if i < current_index else ui.DIM_TEXT
        pygame.draw.line(surface, line_color, (centers[i] + dot_r, cy), (centers[i + 1] - dot_r, cy),
                          max(1, int(2 * scale)))
    for i, label in enumerate(TURN_STEPS):
        cx = centers[i]
        if i == current_index:
            pygame.draw.circle(surface, ui.ACCENT, (cx, cy), dot_r + int(2 * scale))
            pygame.draw.circle(surface, ui.BG, (cx, cy), dot_r)
        elif i < current_index:
            pygame.draw.circle(surface, ui.DIM_TEXT, (cx, cy), dot_r)
        else:
            pygame.draw.circle(surface, ui.BG, (cx, cy), dot_r)
            pygame.draw.circle(surface, ui.DIM_TEXT, (cx, cy), dot_r, width=max(1, int(2 * scale)))
        color = ui.ACCENT if i == current_index else ui.DIM_TEXT
        text = label_font.render(label, True, color)
        surface.blit(text, text.get_rect(midtop=(cx, cy + dot_r + int(4 * scale))))


def draw_tier_meter(surface, content_rect, scale, tier):
    """10-segment red-to-green meter showing where a roll landed on OUTCOME_TIERS,
    with the achieved segment popped forward and outlined."""
    n = len(OUTCOME_TIERS)
    gap = max(1, int(2 * scale))
    seg_w = max(1, (content_rect.width - gap * (n - 1)) // n)
    h = int(14 * scale)
    lo, hi = (200, 80, 80), (110, 210, 130)
    for i in range(n):
        frac = i / (n - 1)
        color = tuple(int(lo[c] + (hi[c] - lo[c]) * frac) for c in range(3))
        achieved = i == tier
        pop = int(3 * scale) if achieved else 0
        rect = pygame.Rect(content_rect.left + i * (seg_w + gap), content_rect.top - pop,
                            seg_w, h + pop * 2)
        fill = color if achieved else tuple(c // 2 + 20 for c in color)
        pygame.draw.rect(surface, fill, rect)
        if achieved:
            pygame.draw.rect(surface, ui.ACCENT, rect, width=max(1, int(2 * scale)))
