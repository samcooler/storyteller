"""The relationship-diagram widget: a compact iconographic dot graph showing
the active member's bonds to the rest of the cule and their own prospects.

Free functions taking `sim` (the `PolyculeSimulator`) as their first arg,
rather than methods, so this module has no class of its own to entangle with
the rest of the view - see CLAUDE.md for why the view was split this way.
"""

import math

import pygame

from . import ui


def network_geometry(sim):
    """Left panel = turn/harmony header, then a row of member stamps
    (current cule, active one highlighted), then a row of the active
    member's prospects, then the relationship diagram - now a compact
    iconographic dot graph rather than the main event, since the stamp
    rows above already carry the "who's who" identity work."""
    w, h = sim.screen.get_size()
    scale = ui.scale_factor(sim.screen)
    panel_w = int(w * 0.42)
    panel = pygame.Rect(int(16 * scale), int(16 * scale), panel_w, h - int(32 * scale))
    header_h = int(132 * scale)
    members_row_h = int(74 * scale)
    prospects_row_h = int(70 * scale)
    row_gap = int(8 * scale)
    rows_top = panel.top + header_h
    members_rect = pygame.Rect(panel.left + int(10 * scale), rows_top,
                                panel.width - int(20 * scale), members_row_h)
    prospects_rect = pygame.Rect(panel.left + int(10 * scale), members_rect.bottom + row_gap,
                                  panel.width - int(20 * scale), prospects_row_h)
    diagram_top = prospects_rect.bottom + row_gap
    diagram = pygame.Rect(panel.left + int(10 * scale), diagram_top,
                           panel.width - int(20 * scale), panel.height - (diagram_top - panel.top) - int(10 * scale))
    center = diagram.center
    max_r = min(diagram.width, diagram.height) / 2 - int(20 * scale)
    min_r = int(26 * scale)
    return panel, diagram, center, min_r, max_r, scale, members_rect, prospects_rect


def strength(rel):
    return max(0.0, min(1.0, (rel["trust"] + rel["spark"]) / 200.0))


def lerp_color(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def bond_color(t):
    return lerp_color((90, 110, 160), (255, 120, 170), t)


def prospect_color(t):
    return lerp_color((60, 55, 70), (255, 150, 190), t)


def initial(name):
    return name[:1].upper() if name else "?"


def current_highlight(sim):
    if sim.state == "target" and sim.target_options:
        return sim.target_options[sim.target_index]
    if sim.state == "sub_choice" and sim.pending_target:
        return sim.pending_target
    return None


def name_jitter(name):
    # Small deterministic offset so members with near-identical strength
    # don't sit on perfectly even polygon vertices.
    return ((hash(name) % 1000) / 1000.0 - 0.5) * 0.35


def weighted_ring_angles(sim, ring, active):
    if not ring:
        return {}
    strengths = {m.name: strength(sim.get_rel(active.name, m.name)) for m in ring}
    ordered = sorted(ring, key=lambda m: strengths[m.name], reverse=True)
    # Stronger bonds get a narrower angular slice, so close partners cluster
    # a bit near the top while weaker ties spread wider around the rest of
    # the circle - the shape reflects the relationships instead of always
    # forming a regular polygon. Kept gentle (0.75x-1.25x) so nodes don't
    # pile on top of each other.
    weights = [1.25 - strengths[m.name] * 0.5 for m in ordered]
    total = sum(weights)
    span = 2 * math.pi / total
    angles = {}
    cursor = -math.pi / 2
    for member, wgt in zip(ordered, weights):
        slice_w = wgt * span
        angles[member.name] = cursor + slice_w / 2 + name_jitter(member.name)
        cursor += slice_w
    return angles


def relax_ring_positions(positions, center, min_r, max_r, node_diameter):
    # A few iterations of simple pairwise repulsion so nodes never overlap,
    # regardless of how the angle/radius weighting happened to cluster them.
    names = list(positions.keys())
    min_sep = node_diameter * 2.4  # room for the name label under each portrait
    for _ in range(10):
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                ax, ay = positions[names[i]]
                bx, by = positions[names[j]]
                dx, dy = bx - ax, by - ay
                dist = math.hypot(dx, dy) or 0.001
                if dist < min_sep:
                    push = (min_sep - dist) / 2
                    ux, uy = dx / dist, dy / dist
                    positions[names[i]] = (ax - ux * push, ay - uy * push)
                    positions[names[j]] = (bx + ux * push, by + uy * push)
        for name in names:
            x, y = positions[name]
            dx, dy = x - center[0], y - center[1]
            dist = math.hypot(dx, dy) or 0.001
            clamped = max(min_r * 0.85, min(max_r * 1.15, dist))
            if clamped != dist:
                positions[name] = (center[0] + dx / dist * clamped, center[1] + dy / dist * clamped)
    return positions


def clamp_to_rect(pos, rect, margin):
    x = max(rect.left + margin, min(rect.right - margin, pos[0]))
    y = max(rect.top + margin, min(rect.bottom - margin, pos[1]))
    return (x, y)


def draw_glow(sim, surface, pos, base_r, scale):
    pulse = int(6 * scale + 4 * scale * math.sin(sim.anim_t * 5))
    pygame.draw.circle(surface, (255, 255, 255), pos, base_r + pulse, width=max(2, int(3 * scale)))


def draw_network(sim, surface, center, scale):
    active = sim.active
    ring = [m for m in sim.members if m.name != active.name]
    highlight = current_highlight(sim)

    for i in range(len(ring)):
        for j in range(i + 1, len(ring)):
            a, b = ring[i], ring[j]
            pa = sim.node_pos.get(a.name, center)
            pb = sim.node_pos.get(b.name, center)
            t = sim.harmony / 100.0
            color = lerp_color((70, 70, 90), (150, 210, 160), t)
            width = max(1, round((1 + t * 4) * scale))
            pygame.draw.line(surface, color, pa, pb, width)

    for member in ring:
        pos = sim.node_pos.get(member.name, center)
        t = strength(sim.get_rel(active.name, member.name))
        color = bond_color(t)
        width = max(1, round((1 + t * 7) * scale))
        pygame.draw.line(surface, color, center, pos, width)

    for pname, prospect in sim.prospects.items():
        anchor = sim.node_pos.get(prospect["met_by"], center)
        pos = sim.node_pos.get(pname, anchor)
        t = prospect["interest"] / 100.0
        color = prospect_color(t)
        width = max(1, round((1 + t * 5) * scale))
        ui.draw_dashed_line(surface, color, anchor, pos, width, dash=int(8 * scale), gap=int(5 * scale))

    # Iconographic nodes: plain color-coded dots + initials instead of full
    # busts and stat-ring halos - identity and stat detail already live in
    # the stamp rows above, so the diagram itself only needs to read as a
    # small, analytical map of who's connected to whom.
    glyph_font = ui.font(12, scale)
    tiny_font = ui.font(11, scale)

    node_r = int(13 * scale)
    pygame.draw.circle(surface, (255, 220, 120), center, node_r)
    pygame.draw.circle(surface, ui.BORDER_OUTER, center, node_r, width=max(1, int(2 * scale)))
    glyph = glyph_font.render(initial(active.name), True, (40, 30, 20))
    surface.blit(glyph, glyph.get_rect(center=center))
    name_label = tiny_font.render(active.name, True, ui.TEXT_COLOR)
    surface.blit(name_label, name_label.get_rect(midtop=(center[0], center[1] + node_r + int(3 * scale))))

    node_r2 = int(9 * scale)
    for member in ring:
        pos = sim.node_pos.get(member.name, center)
        if member.name == highlight:
            draw_glow(sim, surface, pos, node_r2, scale)
        t = strength(sim.get_rel(active.name, member.name))
        ring_color = bond_color(t)
        pygame.draw.circle(surface, ring_color, pos, node_r2)
        pygame.draw.circle(surface, ui.BORDER_OUTER, pos, node_r2, width=1)
        label = tiny_font.render(member.name, True, ui.TEXT_COLOR)
        surface.blit(label, label.get_rect(midtop=(pos[0], pos[1] + node_r2 + int(3 * scale))))

    node_r3 = int(6 * scale)
    for pname, prospect in sim.prospects.items():
        pos = sim.node_pos.get(pname, center)
        if pname == highlight:
            draw_glow(sim, surface, pos, node_r3, scale)
        t = prospect["interest"] / 100.0
        ring_color = prospect_color(t)
        pygame.draw.circle(surface, ring_color, pos, node_r3, width=max(1, int(2 * scale)))
