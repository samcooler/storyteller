"""The member/prospect stamp rows (left panel) and the full roster overlay."""

import pygame

from . import pixel_portrait, ui
from . import polycule_view_network as network
from .polycule_constants import LIFE_STAGE_LABELS, RELATIONAL_INFO, STAT_INFO, STATUSES, TRAITS


def truncate_to_width(font_obj, text, max_width):
    if font_obj.size(text)[0] <= max_width:
        return text
    while text and font_obj.size(text + "…")[0] > max_width:
        text = text[:-1]
    return (text + "…") if text else "…"


def draw_member_row(sim, surface, rect, scale):
    """Stamp-size portraits for every current cule member, active one
    highlighted - the "who's here" row the diagram used to have to carry
    on its own."""
    caption_font = ui.font(13, scale, title=True)
    name_font = ui.font(12, scale)
    caption = caption_font.render("MEMBERS", True, ui.ACCENT)
    surface.blit(caption, (rect.left, rect.top))
    row_y = rect.top + caption.get_height() + int(4 * scale)

    n = max(1, len(sim.members))
    gap = int(8 * scale)
    default_size = int(38 * scale)
    stamp_size = int(min(default_size, max(int(22 * scale), (rect.width - gap * (n - 1)) / n)))
    active_name = sim.active.name
    for i, member in enumerate(sim.members):
        x = rect.left + i * (stamp_size + gap)
        stamp_rect = pygame.Rect(x, row_y, stamp_size, stamp_size)
        is_active = member.name == active_name
        if is_active:
            bg = stamp_rect.inflate(int(6 * scale), int(6 * scale))
            pygame.draw.rect(surface, (110, 70, 130), bg)
        pixel_portrait.draw_bust(surface, stamp_rect, member.seed)
        border_color = ui.ACCENT if is_active else ui.BORDER_OUTER
        border_w = max(2, int(3 * scale)) if is_active else max(1, int(1 * scale))
        pygame.draw.rect(surface, border_color, stamp_rect, width=border_w)
        name_text = truncate_to_width(name_font, member.name, stamp_size + int(4 * scale))
        label = name_font.render(name_text, True, ui.ACCENT if is_active else ui.TEXT_COLOR)
        surface.blit(label, label.get_rect(midtop=(stamp_rect.centerx, stamp_rect.bottom + int(3 * scale))))


def draw_prospect_row(sim, surface, rect, scale):
    """Stamp-size portraits for the active member's own prospects (met_by
    == active) - scoped per-turn since prospects belong to whoever met
    them, not the whole cule."""
    caption_font = ui.font(13, scale, title=True)
    name_font = ui.font(11, scale)
    caption = caption_font.render(f"{sim.active.name}'S PROSPECTS", True, ui.DIM_TEXT)
    surface.blit(caption, (rect.left, rect.top))
    row_y = rect.top + caption.get_height() + int(4 * scale)

    prospects = list(sim._member_prospects(sim.active.name).items())
    if not prospects:
        empty_font = ui.font(12, scale)
        empty = empty_font.render("No prospects yet", True, ui.DIM_TEXT)
        surface.blit(empty, (rect.left, row_y))
        return

    n = len(prospects)
    gap = int(8 * scale)
    default_size = int(30 * scale)
    stamp_size = int(min(default_size, max(int(18 * scale), (rect.width - gap * (n - 1)) / n)))
    highlight = network.current_highlight(sim)
    bar_h = max(3, int(4 * scale))
    for i, (pname, prospect) in enumerate(prospects):
        x = rect.left + i * (stamp_size + gap)
        stamp_rect = pygame.Rect(x, row_y, stamp_size, stamp_size)
        char = prospect["char"]
        pixel_portrait.draw_bust(surface, stamp_rect, char.seed)
        border_color = ui.ACCENT if pname == highlight else network.prospect_color(prospect["interest"] / 100.0)
        pygame.draw.rect(surface, border_color, stamp_rect, width=max(1, int(2 * scale)))
        bar_y = stamp_rect.bottom + int(2 * scale)
        ui.draw_bar(surface, pygame.Rect(stamp_rect.left, bar_y, stamp_size, bar_h),
                    prospect["interest"], 100, RELATIONAL_INFO["interest"]["color"], border_w=0)
        name_text = truncate_to_width(name_font, char.name, stamp_size + int(4 * scale))
        label = name_font.render(name_text, True, ui.DIM_TEXT)
        surface.blit(label, label.get_rect(midtop=(stamp_rect.centerx, bar_y + bar_h + int(2 * scale))))


def stat_grid_height(scale, label_font):
    label_h = label_font.get_height()
    bar_h = max(3, int(6 * scale))
    row_gap = max(1, int(2 * scale))
    return 2 * (label_h + row_gap + bar_h) + row_gap


def draw_stat_grid(surface, x, y, width, scale, char, label_font):
    """Two rows of 5 abbreviated bars: traits on top, statuses below.
    Shared by the roster row and (a denser variant of) the dossier."""
    n = 5
    gap = max(1, int(4 * scale))
    cell_w = (width - gap * (n - 1)) / n
    bar_h = max(3, int(6 * scale))
    row_gap = max(1, int(2 * scale))
    label_h = label_font.get_height()
    for row, keys in enumerate((TRAITS, STATUSES)):
        row_y = y + row * (label_h + row_gap + bar_h + row_gap)
        for i, key in enumerate(keys):
            cx = x + i * (cell_w + gap)
            info = STAT_INFO[key]
            label = label_font.render(info["abbr"], True, ui.DIM_TEXT)
            surface.blit(label, (int(cx), int(row_y)))
            bar_rect = pygame.Rect(int(cx), int(row_y + label_h + row_gap), max(1, int(cell_w)), bar_h)
            ui.draw_bar(surface, bar_rect, char.stat_value(key), 100, info["color"], border_w=0)


def draw_roster(sim, surface, rect, scale):
    ui.draw_panel(surface, rect, scale, corner_style="diamond")
    title_font = ui.font(30, scale, title=True)
    body_font = ui.font(20, scale)
    small_font = ui.font(15, scale)
    surface.blit(title_font.render("Roster", True, ui.ACCENT), (rect.left + int(20 * scale), rect.top + int(14 * scale)))
    y = rect.top + int(60 * scale)
    available_h = rect.height - int(60 * scale) - int(50 * scale)
    portrait_r = int(28 * scale)
    line_h = int(22 * scale)
    rel_bar_h = max(4, int(8 * scale))
    grid_h = stat_grid_height(scale, small_font)
    content_h = line_h * 2 + int(4 * scale) + (rel_bar_h + 2) * 2 + int(6 * scale) + grid_h
    row_h = max(portrait_r * 2 + int(6 * scale), content_h) + int(10 * scale)
    max_visible = max(1, available_h // row_h)
    sim.roster_index = max(0, min(sim.roster_index, len(sim.members) - 1))
    if sim.roster_index < sim.roster_scroll:
        sim.roster_scroll = sim.roster_index
    elif sim.roster_index >= sim.roster_scroll + max_visible:
        sim.roster_scroll = sim.roster_index - max_visible + 1
    sim.roster_scroll = max(0, min(sim.roster_scroll, max(0, len(sim.members) - max_visible)))
    visible = sim.members[sim.roster_scroll:sim.roster_scroll + max_visible]
    for row_i, member in enumerate(visible):
        if sim.roster_scroll + row_i == sim.roster_index:
            sel_rect = pygame.Rect(rect.left + int(8 * scale), y - int(4 * scale),
                                    rect.width - int(16 * scale), row_h - int(2 * scale))
            pygame.draw.rect(surface, (110, 70, 130), sel_rect)
            pygame.draw.rect(surface, ui.ACCENT, sel_rect, width=max(1, int(2 * scale)))
        others = [m for m in sim.members if m.name != member.name]
        if others:
            avg_trust = sum(sim.get_rel(member.name, o.name)["trust"] for o in others) / len(others)
            avg_spark = sum(sim.get_rel(member.name, o.name)["spark"] for o in others) / len(others)
        else:
            avg_trust = avg_spark = 50
        px = rect.left + int(20 * scale)
        pixel_portrait.draw_bust(surface, pygame.Rect(px, y, portrait_r * 2, portrait_r * 2), member.seed)
        tx = px + portrait_r * 2 + int(12 * scale)
        name_tag = f"{member.name} (active)" if member.name == sim.active.name else member.name
        surface.blit(body_font.render(name_tag, True, ui.TEXT_COLOR), (tx, y))
        bar_w = rect.width - (tx - rect.left) - int(20 * scale)
        archetype_line = f"{member.archetype} - {LIFE_STAGE_LABELS[sim._life_stage(member)]}"
        surface.blit(body_font.render(archetype_line, True, ui.DIM_TEXT), (tx, y + line_h))
        bars_y = y + line_h * 2 + int(4 * scale)
        ui.draw_bar(surface, pygame.Rect(tx, bars_y, bar_w, rel_bar_h), avg_trust, 100, RELATIONAL_INFO["trust"]["color"])
        ui.draw_bar(surface, pygame.Rect(tx, bars_y + rel_bar_h + 2, bar_w, rel_bar_h), avg_spark, 100, RELATIONAL_INFO["spark"]["color"])
        grid_y = bars_y + (rel_bar_h + 2) * 2 + int(6 * scale)
        draw_stat_grid(surface, tx, grid_y, bar_w, scale, member, small_font)
        y += row_h
