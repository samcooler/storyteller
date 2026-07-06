"""The full-screen single-character dossier overlay."""

import pygame

from . import pixel_portrait, ui
from .polycule_constants import (
    LIFE_STAGE_LABELS,
    REL_STAGE_LABELS,
    STAT_COLORS,
    STAT_INFO,
    STAT_ORDER,
    STATUSES,
    TRAITS,
    stat_flavor,
)


def join_flavor(char, keys):
    phrases = [stat_flavor(k, char.stat_value(k)) for k in keys]
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


def blit_left_wrapped(surface, font_obj, text, color, left_x, top_y, max_width, line_spacing=1.15):
    y = top_y
    for line in ui.wrap_text(font_obj, text, max_width):
        surface.blit(font_obj.render(line, True, color), (left_x, y))
        y += int(font_obj.get_height() * line_spacing)
    return y


def draw_dossier(sim, surface, rect, scale):
    """Full-screen single-character view: flavor text and portrait lead,
    exact numbers are secondary support underneath - the opposite
    emphasis from the roster row and selector tile."""
    ui.draw_panel(surface, rect, scale)
    member = next((m for m in sim.members if m.name == sim.dossier_name), None)
    title_font = ui.font(32, scale, title=True)
    body_font = ui.font(22, scale)
    small_font = ui.font(16, scale)
    label_font = ui.font(14, scale)
    pad = int(20 * scale)
    if member is None:
        surface.blit(body_font.render("They've moved on.", True, ui.DIM_TEXT), (rect.left + pad, rect.top + pad))
        return

    surface.blit(title_font.render(member.name, True, ui.ACCENT), (rect.left + pad, rect.top + pad))
    sub_y = rect.top + pad + int(40 * scale)
    life_stage = LIFE_STAGE_LABELS[sim._life_stage(member)]
    surface.blit(body_font.render(f"{member.archetype} - {life_stage}", True, ui.TEXT_COLOR),
                 (rect.left + pad, sub_y))

    content_top = sub_y + int(38 * scale)
    content_bottom = rect.bottom - int(50 * scale)
    left_w = int(rect.width * 0.34)
    left_rect = pygame.Rect(rect.left + pad, content_top, left_w - pad, content_bottom - content_top)
    right_rect = pygame.Rect(rect.left + pad + left_w, content_top,
                              rect.width - left_w - pad * 2, content_bottom - content_top)

    portrait_r = min(left_rect.width, left_rect.height) // 4
    center = (left_rect.left + left_rect.width // 2, left_rect.top + portrait_r + int(10 * scale))
    pixel_portrait.draw_bust(surface, pygame.Rect(center[0] - portrait_r, center[1] - portrait_r,
                                                    portrait_r * 2, portrait_r * 2), member.seed)
    ring_r = portrait_r + int(16 * scale)
    ui.draw_ring_segments(surface, center, ring_r, member.stat_values(), STAT_COLORS,
                           thickness=max(3, int(5 * scale)))

    y = center[1] + ring_r + int(16 * scale)
    kink_names = ", ".join(k for k, _level in member.kinks)
    y = blit_left_wrapped(surface, small_font, f"Into: {kink_names}", ui.DIM_TEXT,
                           left_rect.left, y, left_rect.width)
    y += int(4 * scale)
    surface.blit(small_font.render(f"Prefers: {member.preferred_activity}", True, ui.DIM_TEXT),
                 (left_rect.left, y))
    y += small_font.get_height() + int(14 * scale)

    bar_h = max(3, int(5 * scale))
    for key in STAT_ORDER:
        info = STAT_INFO[key]
        val = member.stat_value(key)
        if y + label_font.get_height() + bar_h > left_rect.bottom:
            break
        surface.blit(label_font.render(f"{info['label']} {val}", True, ui.TEXT_COLOR), (left_rect.left, y))
        y += label_font.get_height() + int(2 * scale)
        ui.draw_bar(surface, pygame.Rect(left_rect.left, y, left_rect.width, bar_h), val, 100, info["color"], border_w=0)
        y += bar_h + int(4 * scale)

    ry = right_rect.top
    trait_line = f"{member.name} {join_flavor(member, TRAITS)}."
    status_line = f"Right now they're {join_flavor(member, STATUSES)}."
    ry = blit_left_wrapped(surface, body_font, trait_line, ui.TEXT_COLOR, right_rect.left, ry, right_rect.width)
    ry += int(8 * scale)
    ry = blit_left_wrapped(surface, body_font, status_line, ui.TEXT_COLOR, right_rect.left, ry, right_rect.width)
    ry += int(18 * scale)

    others = [m for m in sim.members if m.name != member.name]
    if others:
        surface.blit(small_font.render("Household bonds:", True, ui.ACCENT), (right_rect.left, ry))
        ry += small_font.get_height() + int(4 * scale)
        for other in others:
            rel = sim.get_rel(member.name, other.name)
            stage_label = REL_STAGE_LABELS[sim._relationship_stage(rel)]
            line = f"{other.name}: Trust {rel['trust']}  Spark {rel['spark']}  ({stage_label})"
            surface.blit(small_font.render(line, True, ui.TEXT_COLOR), (right_rect.left, ry))
            ry += small_font.get_height() + int(3 * scale)
        ry += int(10 * scale)

    my_prospects = [(n, p) for n, p in sim.prospects.items() if p["met_by"] == member.name]
    if my_prospects:
        surface.blit(small_font.render("Prospects:", True, ui.ACCENT), (right_rect.left, ry))
        ry += small_font.get_height() + int(4 * scale)
        for name, prospect in my_prospects:
            line = f"{name}: Interest {prospect['interest']}"
            surface.blit(small_font.render(line, True, ui.TEXT_COLOR), (right_rect.left, ry))
            ry += small_font.get_height() + int(3 * scale)
