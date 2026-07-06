"""The bottom fanned hand row: full interactive fan while it's the active
selector (playing/discarding), collapsed to a title strip otherwise."""

import pygame

from . import ui
from . import polycule_view_cards as cards
from .polycule_constants import END_WEEK


def hand_card_surface(sim, card, card_w, card_h, scale, selected):
    """Renders one hand card onto its own per-pixel-alpha surface so it can
    be rotated for the fan layout without leaving black corners."""
    card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    rect = pygame.Rect(0, 0, card_w, card_h)
    top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
    bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
    border = ui.ACCENT if selected else ui.BORDER_OUTER
    ui.draw_panel(card_surf, rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=border)
    display_name, _blurb = cards.card_face(card)
    name_font = ui.font(min(13, max(9, card_w // 13)), scale)
    ui.blit_wrapped(card_surf, name_font, display_name, ui.TEXT_COLOR,
                     rect.centerx, rect.top + int(10 * scale), card_w - int(12 * scale))
    kind_font = ui.font(12, scale)
    kind_label = kind_font.render(cards.card_label(card), True, ui.DIM_TEXT)
    card_surf.blit(kind_label, kind_label.get_rect(midbottom=(rect.centerx, rect.bottom - int(8 * scale))))
    return card_surf


def hand_row_selecting(sim):
    """Whether the bottom hand row is the thing driving input right now -
    only true during the actual card-selection steps (playing or
    discarding). The "draw" state hides the row entirely elsewhere; every
    other state (target/sub_choice/result/recap) just wants a quiet
    reminder of what's in hand, not a full interactive fan."""
    return sim.state in ("hand", "discard")


def hand_row_reserved_height(sim, scale):
    """Vertical space to leave for the bottom hand row. Full-size while it's
    an active selector; collapsed to a title strip otherwise (or nearly
    nothing during "draw", where the row isn't drawn at all), so other
    stages get more room for their own content above."""
    if sim.state == "draw":
        return int(20 * scale)
    if hand_row_selecting(sim):
        return int(200 * scale)
    return int(60 * scale)


def draw_hand_row_collapsed(sim, surface, main_rect, scale, hand):
    """Title-only strip shown while the hand isn't the active selector -
    just enough to remind you what's in hand without eating the space a
    full fanned row would reserve."""
    margin = int(20 * scale)
    gap = int(8 * scale)
    n = len(hand)
    card_h = int(30 * scale)
    available = main_rect.width - margin * 2 - gap * (n - 1)
    card_w = min(int(120 * scale), max(int(40 * scale), available // n))
    total_w = n * card_w + (n - 1) * gap
    start_x = main_rect.centerx - total_w // 2
    y = main_rect.bottom - margin - card_h
    name_font = ui.font(min(13, max(9, card_w // 11)), scale)
    for i, card in enumerate(hand):
        rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
        ui.draw_panel(surface, rect, scale, border_color=ui.BORDER_OUTER)
        display_name, _ = cards.card_face(card)
        ui.blit_wrapped(surface, name_font, display_name, ui.DIM_TEXT,
                         rect.centerx, rect.centery - name_font.get_height() // 2, card_w - int(8 * scale))


def draw_hand_row(sim, surface, main_rect, scale, body_font, small_font):
    hand = list(sim.hand)
    if not hand_row_selecting(sim):
        if hand:
            draw_hand_row_collapsed(sim, surface, main_rect, scale, hand)
        return
    show_end_button = sim.state != "discard"
    if not hand and not show_end_button:
        return

    card_w = int(150 * scale)
    card_h = card_w + int(25 * scale)
    shadow_off = (int(6 * scale), int(8 * scale))
    margin = int(20 * scale)

    button_h = int(46 * scale) if show_end_button else 0
    button_gap = int(14 * scale) if show_end_button else 0
    row_bottom = main_rect.bottom - margin - button_h - button_gap
    row_base_y = row_bottom - card_h

    n = len(hand)
    if n:
        max_spread = main_rect.width - int(40 * scale)
        step = card_w if n == 1 else min(
            card_w + int(14 * scale),
            max(card_w * 0.34, (max_spread - card_w) / (n - 1)),
        )
        total_w = card_w + step * (n - 1)
        start_x = main_rect.centerx - total_w / 2
        arc = int(14 * scale)
        max_rot = 6.0
        selected_i = sim.hand_index if sim.state in ("hand", "discard") and sim.hand_index < n else None

        draw_order = [i for i in range(n) if i != selected_i] + ([selected_i] if selected_i is not None else [])
        for i in draw_order:
            card = hand[i]
            t = (i - (n - 1) / 2) / max(1, (n - 1) / 2) if n > 1 else 0.0
            cx = start_x + i * step + card_w / 2
            cy = row_base_y + arc * (t ** 2) + card_h / 2
            angle = -t * max_rot
            selected = i == selected_i
            if selected:
                cy -= int(16 * scale)
            card_surf = hand_card_surface(sim, card, card_w, card_h, scale, selected)
            rotated = pygame.transform.rotate(card_surf, angle)
            shadow = pygame.Surface(card_surf.get_size(), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 100))
            shadow = pygame.transform.rotate(shadow, angle)
            shadow_rect = shadow.get_rect(center=(cx + shadow_off[0], cy + shadow_off[1]))
            surface.blit(shadow, shadow_rect)
            rotated_rect = rotated.get_rect(center=(cx, cy))
            surface.blit(rotated, rotated_rect)

    if show_end_button:
        btn_w = int(150 * scale)
        btn_rect = pygame.Rect(main_rect.centerx - btn_w // 2, main_rect.bottom - margin - button_h,
                                btn_w, button_h)
        selected = sim.state == "hand" and sim.hand_index == n
        shadow_rect = btn_rect.move(shadow_off[0], shadow_off[1])
        shadow_surf = pygame.Surface(btn_rect.size, pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 100))
        surface.blit(shadow_surf, shadow_rect)
        top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
        bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
        border = ui.ACCENT if selected else ui.BORDER_OUTER
        ui.draw_panel(surface, btn_rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=border)
        label_font = ui.font(18, scale)
        label = label_font.render(END_WEEK["name"], True, ui.TEXT_COLOR)
        surface.blit(label, label.get_rect(center=btn_rect.center))
