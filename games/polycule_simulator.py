"""Polycule Simulator: a no-combat, card-driven relationship sim.

No character is "the player" - you cycle control between everyone in the
cule, one week at a time. Each week the active member draws a hand of
cards (flavored by their archetype) and plays as many as they like against
existing partners, met prospects, or the household as a whole, then passes
control to the next member. Time is tracked as weeks inside quarters, and
some cards (dates) get negotiated and scheduled onto a calendar instead of
resolving immediately.

This module is the game's controller + view: it owns input handling, the
turn/selection state machine, and all the pygame drawing. The simulated
world itself lives in `polycule_model.PolyculeModel`, and how a played card
resolves lives in `polycule_rules`. Domain state is reached through the thin
read-proxies just below `reset` (self.members -> self.model.members, etc.)
so the drawing code stays terse.
"""

import math
import random

import pygame

from . import pixel_portrait, ui
from . import polycule_rules as rules
from .base import Game
from .polycule_constants import (
    ACTIVITIES,
    DAYS,
    DRAW_MAX,
    END_WEEK,
    KIND_COLORS,
    LIFE_STAGE_LABELS,
    MAX_HAND,
    OUTCOME_TIERS,
    RELATIONAL_INFO,
    REL_STAGE_LABELS,
    SCHEDULE_OFFSETS,
    STAT_COLORS,
    STAT_INFO,
    STAT_ORDER,
    STATUSES,
    TRAITS,
    TURN_STEPS,
    WEEKS_PER_QUARTER,
    stat_flavor,
)
from .polycule_model import PolyculeModel


class PolyculeSimulator(Game):
    name = "Polycule Simulator"
    description = "A card game about your polycule. Arrows + Enter to play, Tab roster, C calendar."

    def __init__(self, screen):
        super().__init__(screen)

    def reset(self):
        # The whole simulated world - members, prospects, relationships,
        # calendar, harmony/chaos - lives on the model, built fresh from an
        # injected rng. Everything set below is view/controller state only.
        self.model = PolyculeModel(random.Random())
        self.anim_t = 0.0

        self.node_pos = {}
        self.overlay = None
        self.roster_scroll = 0
        self.roster_index = 0
        self.dossier_name = None

        self.state = "hand"
        self.hand = []
        self.hand_index = 0
        self.drawn_cards = []
        self.target_options = []
        self.target_index = 0
        self.pending_card = None
        self.result_text = []
        self.result_tier = None

        self.pending_target = None
        self.sub_kind = None
        self.sub_options = []
        self.sub_index = 0
        self.date_target_week = None
        self.proposed_day = None
        self.counter_day = None
        self.chosen_day = None
        self.date_is_prospect = False

        self._start_turn(self.model.active)

    # --- Domain read-proxies -------------------------------------------------
    # Domain state and queries live on self.model; these keep the controller
    # and the ~800 lines of drawing code terse (self.members, self.get_rel,
    # ...) without each having to reach through self.model. Reads only -
    # mutation goes through the model or the rules module.

    @property
    def members(self):
        return self.model.members

    @property
    def prospects(self):
        return self.model.prospects

    @property
    def relationships(self):
        return self.model.relationships

    @property
    def calendar(self):
        return self.model.calendar

    @property
    def week(self):
        return self.model.week

    @property
    def harmony(self):
        return self.model.harmony

    @property
    def chaos(self):
        return self.model.chaos

    @property
    def active(self):
        return self.model.active

    @property
    def quarter(self):
        return self.model.quarter

    @property
    def week_in_quarter(self):
        return self.model.week_in_quarter

    def get_rel(self, name_a, name_b):
        return self.model.get_rel(name_a, name_b)

    def _life_stage(self, member):
        return self.model.life_stage(member)

    def _relationship_stage(self, rel):
        return self.model.relationship_stage(rel)

    def _member_prospects(self, member_name):
        return self.model.member_prospects(member_name)

    def _targets_for_card(self, card, member):
        return self.model.targets_for_card(card, member)

    def _eligible_cards(self, member):
        return self.model.eligible_cards(member)

    # --- Turn / selection flow ----------------------------------------------

    def _start_turn(self, member):
        # Always draw up to DRAW_MAX regardless of current hand size - the
        # mandatory discard step right after draw brings the hand back down
        # to MAX_HAND before play, so there's no need to cap the draw itself.
        pool = self._eligible_cards(member)
        available = [c for c in pool if not any(c is h for h in member.hand)]
        n = max(0, min(DRAW_MAX, len(available)))
        drawn = self.model.rng.sample(available, n) if n else []
        member.hand.extend(drawn)
        self.hand = member.hand
        self.drawn_cards = drawn
        self.hand_index = 0
        self.state = "draw"

    def _card_targets(self, card):
        return self.model.targets_for_card(card, self.model.active)

    def _target_info(self, name):
        """Returns (character, kind, stat) where kind is 'member' or 'prospect'
        and stat is the relationship dict (member) or interest int (prospect)."""
        for m in self.members:
            if m.name == name:
                rel = self.get_rel(self.active.name, name) if name != self.active.name else None
                return m, "member", rel
        prospect = self.prospects.get(name)
        if prospect:
            return prospect["char"], "prospect", prospect["interest"]
        return None, None, None

    @staticmethod
    def _card_face(card):
        """(display name, display blurb) - Events are random things that happen
        to you, so they stay a mystery in hand/draw/discard previews and only
        reveal their real name and blurb once actually played."""
        if card["class"] == "events":
            return "???", "Something's about to happen."
        return card["name"], None

    @staticmethod
    def _card_label(card):
        if card is END_WEEK:
            return "end"
        if card["class"] == "dates":
            return card.get("scope", "dates")
        if card["class"] == "choice":
            return card.get("kind", "choice")
        return card["class"]

    def _enter_sub(self, kind, options):
        self.sub_kind = kind
        self.sub_options = options
        self.sub_index = 0
        self.state = "sub_choice"

    def _start_date_flow(self, target_name):
        self.pending_target = target_name
        self._enter_sub("week", list(SCHEDULE_OFFSETS))

    def _finish_card_fizzle(self, message):
        self.result_text = [message]
        self.result_tier = None
        self.hand.remove(self.pending_card)
        self.hand_index = 0
        rules.spend_energy(self.model)
        self.state = "result"

    def _advance_sub_choice(self):
        label, value = self.sub_options[self.sub_index]
        if self.sub_kind == "week":
            self.date_target_week = self.week + value
            self._enter_sub("day", [(d, d) for d in DAYS])
        elif self.sub_kind == "day":
            self.proposed_day = value
            outcome, counter_day, is_prospect = rules.negotiate_date(self.model, self.pending_target, value)
            self.date_is_prospect = is_prospect
            if outcome == "accept":
                self.chosen_day = value
                self._enter_sub("activity", [(a, a) for a in ACTIVITIES])
            elif outcome == "counter":
                self.counter_day = counter_day
                self._enter_sub("counter", [(f"Accept {counter_day}", "accept"), ("Decline", "decline")])
            else:
                self._finish_card_fizzle(f"{self.pending_target} isn't up for plans that day.")
        elif self.sub_kind == "counter":
            if value == "accept":
                self.chosen_day = self.counter_day
                self._enter_sub("activity", [(a, a) for a in ACTIVITIES])
            else:
                self._finish_card_fizzle(f"{self.pending_target} passes this time.")
        elif self.sub_kind == "activity":
            self.calendar.setdefault(self.date_target_week, []).append({
                "a": self.active.name, "b": self.pending_target, "day": self.chosen_day,
                "activity": value, "is_prospect": self.date_is_prospect,
            })
            self.result_text = [
                f"{self.pending_target} is in for {value.lower()} on {self.chosen_day}.",
                f"(scheduled for week {self.date_target_week})",
            ]
            self.result_tier = None
            self.hand.remove(self.pending_card)
            self.hand_index = 0
            rules.spend_energy(self.model)
            self.state = "result"

    def _finish_turn(self):
        self.model.week += 1
        events = self.calendar.pop(self.week, [])
        if events:
            lines = []
            for ev in events:
                lines.extend(rules.resolve_scheduled_event(self.model, ev))
            self.result_text = lines
            self.result_tier = None
            self.state = "recap"
        else:
            self._start_turn(self.active)

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_TAB:
            self.overlay = None if self.overlay == "roster" else "roster"
            return
        if event.key == pygame.K_c:
            self.overlay = None if self.overlay == "calendar" else "calendar"
            return
        if self.overlay == "roster":
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.roster_index = min(len(self.members) - 1, self.roster_index + 1)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.roster_index = max(0, self.roster_index - 1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.members:
                    self.dossier_name = self.members[self.roster_index].name
                    self.overlay = "dossier"
            return
        if self.overlay == "dossier":
            if event.key in (pygame.K_BACKSPACE, pygame.K_RETURN, pygame.K_SPACE):
                self.overlay = "roster"
            return
        if self.overlay:
            return
        if self.state == "draw":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if len(self.hand) > MAX_HAND:
                    self.state = "discard"
                else:
                    self.state = "hand"
                self.hand_index = 0
        elif self.state == "discard":
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.hand_index = (self.hand_index - 1) % len(self.hand)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.hand_index = (self.hand_index + 1) % len(self.hand)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                card = self.hand[self.hand_index]
                self.hand.remove(card)
                self.hand_index = 0
                if len(self.hand) <= MAX_HAND:
                    self.state = "hand"
        elif self.state == "hand":
            options = self.hand + [END_WEEK]
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.hand_index = (self.hand_index - 1) % len(options)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.hand_index = (self.hand_index + 1) % len(options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                card = options[self.hand_index]
                if card is END_WEEK:
                    self._finish_turn()
                elif card["class"] == "choice" or (card["class"] == "dates" and card.get("scope") == "pair"):
                    targets = self._card_targets(card)
                    if not targets:
                        self.result_text = [f"{card['name']} has no one left to target. It fizzles."]
                        self.result_tier = None
                        self.hand.remove(card)
                        self.hand_index = 0
                        self.state = "result"
                    else:
                        self.pending_card = card
                        self.target_options = targets
                        self.target_index = 0
                        self.state = "target"
                else:
                    outcome = rules.resolve(self.model, card, None)
                    self.result_text = outcome.lines
                    self.result_tier = outcome.tier
                    self.hand.remove(card)
                    self.hand_index = 0
                    self.state = "result"
        elif self.state == "target":
            if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
                self.target_index = (self.target_index - 1) % len(self.target_options)
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
                self.target_index = (self.target_index + 1) % len(self.target_options)
            elif event.key == pygame.K_BACKSPACE:
                self.state = "hand"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                target = self.target_options[self.target_index]
                if self.pending_card.get("schedulable"):
                    self._start_date_flow(target)
                else:
                    outcome = rules.resolve(self.model, self.pending_card, target)
                    self.result_text = outcome.lines
                    self.result_tier = outcome.tier
                    self.hand.remove(self.pending_card)
                    self.hand_index = 0
                    self.state = "result"
        elif self.state == "sub_choice":
            if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
                self.sub_index = (self.sub_index - 1) % len(self.sub_options)
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
                self.sub_index = (self.sub_index + 1) % len(self.sub_options)
            elif event.key == pygame.K_BACKSPACE:
                self.state = "hand"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._advance_sub_choice()
        elif self.state == "result":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "hand"
                if self.hand_index >= len(self.hand):
                    self.hand_index = max(0, len(self.hand) - 1)
        elif self.state == "recap":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._start_turn(self.active)

    def _network_geometry(self):
        """Left panel = turn/harmony header, then a row of member stamps
        (current cule, active one highlighted), then a row of the active
        member's prospects, then the relationship diagram - now a compact
        iconographic dot graph rather than the main event, since the stamp
        rows above already carry the "who's who" identity work."""
        w, h = self.screen.get_size()
        scale = ui.scale_factor(self.screen)
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

    @staticmethod
    def _strength(rel):
        return max(0.0, min(1.0, (rel["trust"] + rel["spark"]) / 200.0))

    @staticmethod
    def _lerp_color(c0, c1, t):
        return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))

    def _bond_color(self, t):
        return self._lerp_color((90, 110, 160), (255, 120, 170), t)

    def _prospect_color(self, t):
        return self._lerp_color((60, 55, 70), (255, 150, 190), t)

    @staticmethod
    def _initial(name):
        return name[:1].upper() if name else "?"

    @staticmethod
    def _truncate_to_width(font_obj, text, max_width):
        if font_obj.size(text)[0] <= max_width:
            return text
        while text and font_obj.size(text + "…")[0] > max_width:
            text = text[:-1]
        return (text + "…") if text else "…"

    def _current_highlight(self):
        if self.state == "target" and self.target_options:
            return self.target_options[self.target_index]
        if self.state == "sub_choice" and self.pending_target:
            return self.pending_target
        return None

    @staticmethod
    def _name_jitter(name):
        # Small deterministic offset so members with near-identical strength
        # don't sit on perfectly even polygon vertices.
        return ((hash(name) % 1000) / 1000.0 - 0.5) * 0.35

    def _weighted_ring_angles(self, ring, active):
        if not ring:
            return {}
        strengths = {m.name: self._strength(self.get_rel(active.name, m.name)) for m in ring}
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
            angles[member.name] = cursor + slice_w / 2 + self._name_jitter(member.name)
            cursor += slice_w
        return angles

    def _relax_ring_positions(self, positions, center, min_r, max_r, node_diameter):
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

    @staticmethod
    def _clamp_to_rect(pos, rect, margin):
        x = max(rect.left + margin, min(rect.right - margin, pos[0]))
        y = max(rect.top + margin, min(rect.bottom - margin, pos[1]))
        return (x, y)

    def update(self, dt):
        self.anim_t += dt
        _, diagram, center, min_r, max_r, scale, _, _ = self._network_geometry()
        active = self.active
        ring = [m for m in self.members if m.name != active.name]
        rate = min(1.0, dt * 2.5)

        ring_angles = self._weighted_ring_angles(ring, active)
        ring_positions = {}
        for member in ring:
            angle = ring_angles[member.name]
            strength = self._strength(self.get_rel(active.name, member.name))
            radius = max_r - strength * (max_r - min_r)
            ring_positions[member.name] = (center[0] + radius * math.cos(angle),
                                            center[1] + radius * math.sin(angle))
        node_diameter = 2 * int(9 * scale)
        ring_positions = self._relax_ring_positions(ring_positions, center, min_r, max_r, node_diameter)

        # Bond-strength radii tend to pull everyone in close to the center, leaving
        # most of the panel empty. Auto-zoom the whole layout back out from center
        # so it always fills the available diagram radius - same-size faces, just
        # spread further apart - instead of scaling with however tight the bonds are.
        if ring_positions:
            current_max = max(math.hypot(x - center[0], y - center[1]) for x, y in ring_positions.values())
            if current_max > 1:
                zoom = max_r / current_max
                for name, (x, y) in ring_positions.items():
                    ring_positions[name] = (center[0] + (x - center[0]) * zoom, center[1] + (y - center[1]) * zoom)

        ring_margin = int(9 * scale) + int(16 * scale)  # node radius + label line
        for name, pos in ring_positions.items():
            ring_positions[name] = self._clamp_to_rect(pos, diagram, ring_margin)

        target_positions = {active.name: center, **ring_positions}
        for name, target in target_positions.items():
            cur = self.node_pos.get(name, target)
            self.node_pos[name] = (cur[0] + (target[0] - cur[0]) * rate, cur[1] + (target[1] - cur[1]) * rate)

        prospect_margin = int(6 * scale) + int(14 * scale)
        for pname, prospect in self.prospects.items():
            anchor = self.node_pos.get(prospect["met_by"], center)
            siblings = [n for n, p in self.prospects.items() if p["met_by"] == prospect["met_by"]]
            idx = siblings.index(pname)
            angle = (idx / max(1, len(siblings))) * 2 * math.pi + 0.6
            strength = prospect["interest"] / 100.0
            sat_max, sat_min = 50 * scale, 36 * scale
            radius = sat_max - strength * (sat_max - sat_min)
            target = (anchor[0] + radius * math.cos(angle), anchor[1] + radius * math.sin(angle))
            target = self._clamp_to_rect(target, diagram, prospect_margin)
            cur = self.node_pos.get(pname, target)
            self.node_pos[pname] = (cur[0] + (target[0] - cur[0]) * rate, cur[1] + (target[1] - cur[1]) * rate)

    def _draw_glow(self, surface, pos, base_r, scale):
        pulse = int(6 * scale + 4 * scale * math.sin(self.anim_t * 5))
        pygame.draw.circle(surface, (255, 255, 255), pos, base_r + pulse, width=max(2, int(3 * scale)))

    def _draw_network(self, surface, center, scale):
        active = self.active
        ring = [m for m in self.members if m.name != active.name]
        highlight = self._current_highlight()

        for i in range(len(ring)):
            for j in range(i + 1, len(ring)):
                a, b = ring[i], ring[j]
                pa = self.node_pos.get(a.name, center)
                pb = self.node_pos.get(b.name, center)
                t = self.harmony / 100.0
                color = self._lerp_color((70, 70, 90), (150, 210, 160), t)
                width = max(1, round((1 + t * 4) * scale))
                pygame.draw.line(surface, color, pa, pb, width)

        for member in ring:
            pos = self.node_pos.get(member.name, center)
            t = self._strength(self.get_rel(active.name, member.name))
            color = self._bond_color(t)
            width = max(1, round((1 + t * 7) * scale))
            pygame.draw.line(surface, color, center, pos, width)

        for pname, prospect in self.prospects.items():
            anchor = self.node_pos.get(prospect["met_by"], center)
            pos = self.node_pos.get(pname, anchor)
            t = prospect["interest"] / 100.0
            color = self._prospect_color(t)
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
        glyph = glyph_font.render(self._initial(active.name), True, (40, 30, 20))
        surface.blit(glyph, glyph.get_rect(center=center))
        name_label = tiny_font.render(active.name, True, ui.TEXT_COLOR)
        surface.blit(name_label, name_label.get_rect(midtop=(center[0], center[1] + node_r + int(3 * scale))))

        node_r2 = int(9 * scale)
        for member in ring:
            pos = self.node_pos.get(member.name, center)
            if member.name == highlight:
                self._draw_glow(surface, pos, node_r2, scale)
            t = self._strength(self.get_rel(active.name, member.name))
            ring_color = self._bond_color(t)
            pygame.draw.circle(surface, ring_color, pos, node_r2)
            pygame.draw.circle(surface, ui.BORDER_OUTER, pos, node_r2, width=1)
            label = tiny_font.render(member.name, True, ui.TEXT_COLOR)
            surface.blit(label, label.get_rect(midtop=(pos[0], pos[1] + node_r2 + int(3 * scale))))

        node_r3 = int(6 * scale)
        for pname, prospect in self.prospects.items():
            pos = self.node_pos.get(pname, center)
            if pname == highlight:
                self._draw_glow(surface, pos, node_r3, scale)
            t = prospect["interest"] / 100.0
            ring_color = self._prospect_color(t)
            pygame.draw.circle(surface, ring_color, pos, node_r3, width=max(1, int(2 * scale)))

    def _draw_member_row(self, surface, rect, scale):
        """Stamp-size portraits for every current cule member, active one
        highlighted - the "who's here" row the diagram used to have to carry
        on its own."""
        caption_font = ui.font(13, scale, title=True)
        name_font = ui.font(12, scale)
        caption = caption_font.render("MEMBERS", True, ui.ACCENT)
        surface.blit(caption, (rect.left, rect.top))
        row_y = rect.top + caption.get_height() + int(4 * scale)

        n = max(1, len(self.members))
        gap = int(8 * scale)
        default_size = int(38 * scale)
        stamp_size = int(min(default_size, max(int(22 * scale), (rect.width - gap * (n - 1)) / n)))
        active_name = self.active.name
        for i, member in enumerate(self.members):
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
            name_text = self._truncate_to_width(name_font, member.name, stamp_size + int(4 * scale))
            label = name_font.render(name_text, True, ui.ACCENT if is_active else ui.TEXT_COLOR)
            surface.blit(label, label.get_rect(midtop=(stamp_rect.centerx, stamp_rect.bottom + int(3 * scale))))

    def _draw_prospect_row(self, surface, rect, scale):
        """Stamp-size portraits for the active member's own prospects (met_by
        == active) - scoped per-turn since prospects belong to whoever met
        them, not the whole cule."""
        caption_font = ui.font(13, scale, title=True)
        name_font = ui.font(11, scale)
        caption = caption_font.render(f"{self.active.name}'S PROSPECTS", True, ui.DIM_TEXT)
        surface.blit(caption, (rect.left, rect.top))
        row_y = rect.top + caption.get_height() + int(4 * scale)

        prospects = list(self._member_prospects(self.active.name).items())
        if not prospects:
            empty_font = ui.font(12, scale)
            empty = empty_font.render("No prospects yet", True, ui.DIM_TEXT)
            surface.blit(empty, (rect.left, row_y))
            return

        n = len(prospects)
        gap = int(8 * scale)
        default_size = int(30 * scale)
        stamp_size = int(min(default_size, max(int(18 * scale), (rect.width - gap * (n - 1)) / n)))
        highlight = self._current_highlight()
        bar_h = max(3, int(4 * scale))
        for i, (pname, prospect) in enumerate(prospects):
            x = rect.left + i * (stamp_size + gap)
            stamp_rect = pygame.Rect(x, row_y, stamp_size, stamp_size)
            char = prospect["char"]
            pixel_portrait.draw_bust(surface, stamp_rect, char.seed)
            border_color = ui.ACCENT if pname == highlight else self._prospect_color(prospect["interest"] / 100.0)
            pygame.draw.rect(surface, border_color, stamp_rect, width=max(1, int(2 * scale)))
            bar_y = stamp_rect.bottom + int(2 * scale)
            ui.draw_bar(surface, pygame.Rect(stamp_rect.left, bar_y, stamp_size, bar_h),
                        prospect["interest"], 100, RELATIONAL_INFO["interest"]["color"], border_w=0)
            name_text = self._truncate_to_width(name_font, char.name, stamp_size + int(4 * scale))
            label = name_font.render(name_text, True, ui.DIM_TEXT)
            surface.blit(label, label.get_rect(midtop=(stamp_rect.centerx, bar_y + bar_h + int(2 * scale))))

    def _stat_grid_height(self, scale, label_font):
        label_h = label_font.get_height()
        bar_h = max(3, int(6 * scale))
        row_gap = max(1, int(2 * scale))
        return 2 * (label_h + row_gap + bar_h) + row_gap

    def _draw_stat_grid(self, surface, x, y, width, scale, char, label_font):
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

    def _draw_roster(self, surface, rect, scale):
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
        grid_h = self._stat_grid_height(scale, small_font)
        content_h = line_h * 2 + int(4 * scale) + (rel_bar_h + 2) * 2 + int(6 * scale) + grid_h
        row_h = max(portrait_r * 2 + int(6 * scale), content_h) + int(10 * scale)
        max_visible = max(1, available_h // row_h)
        self.roster_index = max(0, min(self.roster_index, len(self.members) - 1))
        if self.roster_index < self.roster_scroll:
            self.roster_scroll = self.roster_index
        elif self.roster_index >= self.roster_scroll + max_visible:
            self.roster_scroll = self.roster_index - max_visible + 1
        self.roster_scroll = max(0, min(self.roster_scroll, max(0, len(self.members) - max_visible)))
        visible = self.members[self.roster_scroll:self.roster_scroll + max_visible]
        for row_i, member in enumerate(visible):
            if self.roster_scroll + row_i == self.roster_index:
                sel_rect = pygame.Rect(rect.left + int(8 * scale), y - int(4 * scale),
                                        rect.width - int(16 * scale), row_h - int(2 * scale))
                pygame.draw.rect(surface, (110, 70, 130), sel_rect)
                pygame.draw.rect(surface, ui.ACCENT, sel_rect, width=max(1, int(2 * scale)))
            others = [m for m in self.members if m.name != member.name]
            if others:
                avg_trust = sum(self.get_rel(member.name, o.name)["trust"] for o in others) / len(others)
                avg_spark = sum(self.get_rel(member.name, o.name)["spark"] for o in others) / len(others)
            else:
                avg_trust = avg_spark = 50
            px = rect.left + int(20 * scale)
            pixel_portrait.draw_bust(surface, pygame.Rect(px, y, portrait_r * 2, portrait_r * 2), member.seed)
            tx = px + portrait_r * 2 + int(12 * scale)
            name_tag = f"{member.name} (active)" if member.name == self.active.name else member.name
            surface.blit(body_font.render(name_tag, True, ui.TEXT_COLOR), (tx, y))
            bar_w = rect.width - (tx - rect.left) - int(20 * scale)
            archetype_line = f"{member.archetype} - {LIFE_STAGE_LABELS[self._life_stage(member)]}"
            surface.blit(body_font.render(archetype_line, True, ui.DIM_TEXT), (tx, y + line_h))
            bars_y = y + line_h * 2 + int(4 * scale)
            ui.draw_bar(surface, pygame.Rect(tx, bars_y, bar_w, rel_bar_h), avg_trust, 100, RELATIONAL_INFO["trust"]["color"])
            ui.draw_bar(surface, pygame.Rect(tx, bars_y + rel_bar_h + 2, bar_w, rel_bar_h), avg_spark, 100, RELATIONAL_INFO["spark"]["color"])
            grid_y = bars_y + (rel_bar_h + 2) * 2 + int(6 * scale)
            self._draw_stat_grid(surface, tx, grid_y, bar_w, scale, member, small_font)
            y += row_h

    def _join_flavor(self, char, keys):
        phrases = [stat_flavor(k, char.stat_value(k)) for k in keys]
        if len(phrases) == 1:
            return phrases[0]
        return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"

    def _blit_left_wrapped(self, surface, font_obj, text, color, left_x, top_y, max_width, line_spacing=1.15):
        y = top_y
        for line in ui.wrap_text(font_obj, text, max_width):
            surface.blit(font_obj.render(line, True, color), (left_x, y))
            y += int(font_obj.get_height() * line_spacing)
        return y

    def _draw_dossier(self, surface, rect, scale):
        """Full-screen single-character view: flavor text and portrait lead,
        exact numbers are secondary support underneath - the opposite
        emphasis from the roster row and selector tile."""
        ui.draw_panel(surface, rect, scale)
        member = next((m for m in self.members if m.name == self.dossier_name), None)
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
        life_stage = LIFE_STAGE_LABELS[self._life_stage(member)]
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
        y = self._blit_left_wrapped(surface, small_font, f"Into: {kink_names}", ui.DIM_TEXT,
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
        trait_line = f"{member.name} {self._join_flavor(member, TRAITS)}."
        status_line = f"Right now they're {self._join_flavor(member, STATUSES)}."
        ry = self._blit_left_wrapped(surface, body_font, trait_line, ui.TEXT_COLOR, right_rect.left, ry, right_rect.width)
        ry += int(8 * scale)
        ry = self._blit_left_wrapped(surface, body_font, status_line, ui.TEXT_COLOR, right_rect.left, ry, right_rect.width)
        ry += int(18 * scale)

        others = [m for m in self.members if m.name != member.name]
        if others:
            surface.blit(small_font.render("Household bonds:", True, ui.ACCENT), (right_rect.left, ry))
            ry += small_font.get_height() + int(4 * scale)
            for other in others:
                rel = self.get_rel(member.name, other.name)
                stage_label = REL_STAGE_LABELS[self._relationship_stage(rel)]
                line = f"{other.name}: Trust {rel['trust']}  Spark {rel['spark']}  ({stage_label})"
                surface.blit(small_font.render(line, True, ui.TEXT_COLOR), (right_rect.left, ry))
                ry += small_font.get_height() + int(3 * scale)
            ry += int(10 * scale)

        my_prospects = [(n, p) for n, p in self.prospects.items() if p["met_by"] == member.name]
        if my_prospects:
            surface.blit(small_font.render("Prospects:", True, ui.ACCENT), (right_rect.left, ry))
            ry += small_font.get_height() + int(4 * scale)
            for name, prospect in my_prospects:
                line = f"{name}: Interest {prospect['interest']}"
                surface.blit(small_font.render(line, True, ui.TEXT_COLOR), (right_rect.left, ry))
                ry += small_font.get_height() + int(3 * scale)

    def _draw_calendar(self, surface, rect, scale):
        ui.draw_panel(surface, rect, scale, corner_style="diamond")
        title_font = ui.font(30, scale, title=True)
        body_font = ui.font(22, scale)
        small_font = ui.font(18, scale)
        surface.blit(title_font.render("Calendar", True, ui.ACCENT), (rect.left + int(20 * scale), rect.top + int(14 * scale)))
        y = rect.top + int(64 * scale)

        def line(text, font_obj=body_font, color=ui.TEXT_COLOR, indent=0):
            nonlocal y
            surface.blit(font_obj.render(text, True, color), (rect.left + int((20 + indent) * scale), y))
            y += int((30 if font_obj is body_font else 24) * scale)

        line(f"Quarter {self.quarter}, Week {self.week_in_quarter} of {WEEKS_PER_QUARTER}")
        y += int(10 * scale)
        line(f"This week: {self.active.name}'s turn")
        next_member = self.members[self.week % len(self.members)] if self.members else None
        if next_member:
            line(f"Next week: {next_member.name}'s turn")
        next_events = self.calendar.get(self.week + 1, [])
        if next_events:
            line("Scheduled:", small_font, ui.DIM_TEXT, indent=10)
            for ev in next_events:
                line(f"{ev['a']} & {ev['b']}: {ev['activity']} on {ev['day']}", small_font, ui.TEXT_COLOR, indent=20)
        y += int(16 * scale)
        line("After that, this quarter:")
        quarter_end = self.quarter * WEEKS_PER_QUARTER
        found_any = False
        for w in range(self.week + 2, quarter_end + 1):
            for ev in self.calendar.get(w, []):
                found_any = True
                line(f"Week {w}: {ev['a']} & {ev['b']} - {ev['activity']} on {ev['day']}",
                     small_font, ui.TEXT_COLOR, indent=20)
        if not found_any:
            line("Nothing else scheduled yet.", small_font, ui.DIM_TEXT, indent=20)

    def draw(self, surface):
        surface.fill(ui.BG)
        w, h = surface.get_size()
        scale = ui.scale_factor(surface)
        title_font = ui.font(34, scale, title=True)
        body_font = ui.font(24, scale)
        small_font = ui.font(20, scale)

        if self.overlay:
            rect = pygame.Rect(int(40 * scale), int(40 * scale), w - int(80 * scale), h - int(80 * scale))
            if self.overlay == "roster":
                self._draw_roster(surface, rect, scale)
                hint_text = "Up/Down to select, Enter for dossier, Tab to close" if len(self.members) > 1 else "Enter for dossier, Tab to close"
                hint = small_font.render(hint_text, True, ui.DIM_TEXT)
            elif self.overlay == "dossier":
                self._draw_dossier(surface, rect, scale)
                hint = small_font.render("Backspace to roster, Tab to close", True, ui.DIM_TEXT)
            else:
                self._draw_calendar(surface, rect, scale)
                hint = small_font.render("C to close", True, ui.DIM_TEXT)
            surface.blit(hint, (rect.left + int(20 * scale), rect.bottom - int(34 * scale)))
            return

        panel, diagram, center, min_r, max_r, _, members_rect, prospects_rect = self._network_geometry()
        ui.draw_panel(surface, panel, scale, corner_style="diamond")
        y = panel.top + int(12 * scale)
        surface.blit(small_font.render(
            f"Q{self.quarter} W{self.week_in_quarter}/{WEEKS_PER_QUARTER} - {self.active.name}'s turn",
            True, ui.TEXT_COLOR), (panel.left + int(10 * scale), y))
        y += int(26 * scale)
        bar_w = panel.width - int(20 * scale)
        ui.draw_bar(surface, pygame.Rect(panel.left + int(10 * scale), y, bar_w, int(12 * scale)), self.harmony, 100, (120, 220, 140))
        surface.blit(small_font.render("Harmony", True, ui.DIM_TEXT), (panel.left + int(10 * scale), y + int(14 * scale)))
        y += int(34 * scale)
        ui.draw_bar(surface, pygame.Rect(panel.left + int(10 * scale), y, bar_w, int(12 * scale)), self.chaos, 100, (220, 120, 120))
        surface.blit(small_font.render("Chaos", True, ui.DIM_TEXT), (panel.left + int(10 * scale), y + int(14 * scale)))

        self._draw_member_row(surface, members_rect, scale)
        self._draw_prospect_row(surface, prospects_rect, scale)
        self._draw_network(surface, center, scale)

        title_h = title_font.get_height()
        title_gap = int(10 * scale)
        main_top = int(16 * scale) + title_h + title_gap
        main_rect = pygame.Rect(panel.right + int(16 * scale), main_top,
                                 w - panel.width - int(48 * scale), h - int(32 * scale) - title_h - title_gap)

        title = title_font.render(self.name, True, ui.ACCENT)
        surface.blit(title, (main_rect.left, int(16 * scale)))

        ui.draw_panel(surface, main_rect, scale, corner_style="diamond")

        step_index = {"draw": 0, "discard": 1}.get(self.state, 2 if self.state in ("hand", "target", "sub_choice", "result") else None)
        content_top = main_rect.top + int(20 * scale)
        if step_index is not None:
            step_row_h = int(30 * scale)
            self._draw_step_row(surface, pygame.Rect(main_rect.left + int(20 * scale), content_top,
                                                       main_rect.width - int(40 * scale), step_row_h), scale, step_index)
            content_top += step_row_h + int(14 * scale)
        content_bottom = main_rect.bottom - self._hand_row_reserved_height(scale)
        content_rect = pygame.Rect(main_rect.left + int(20 * scale), content_top,
                                    main_rect.width - int(40 * scale), max(0, content_bottom - content_top))

        if self.state == "target":
            ui.blit_wrapped(surface, body_font, f"Target for {self.pending_card['name']}:",
                             ui.TEXT_COLOR, content_rect.left + content_rect.width // 2, content_rect.top, content_rect.width)
            cards_top = content_rect.top + int(32 * scale)
            cards_rect = pygame.Rect(content_rect.left, cards_top,
                                      content_rect.width, max(0, content_rect.bottom - cards_top - int(22 * scale)))
            self._draw_target_cards(surface, cards_rect, scale)
            ui.blit_wrapped(surface, small_font, "Enter confirm, Backspace cancel",
                             ui.DIM_TEXT, content_rect.left + content_rect.width // 2,
                             content_rect.bottom - int(16 * scale), content_rect.width)
        elif self.state == "sub_choice":
            prompts = {
                "week": f"When should {self.active.name} plan with {self.pending_target}?",
                "day": f"What day works for {self.pending_target}?",
                "counter": f"{self.pending_target} can't do {self.proposed_day}.",
                "activity": f"Where should {self.active.name} and {self.pending_target} go on {self.chosen_day}?",
            }
            ui.blit_wrapped(surface, body_font, prompts.get(self.sub_kind, "Choose:"), ui.TEXT_COLOR,
                             content_rect.left + content_rect.width // 2, content_rect.top, content_rect.width)
            tiles_top = content_rect.top + int(40 * scale)
            tiles_rect = pygame.Rect(content_rect.left, tiles_top, content_rect.width,
                                      max(0, content_rect.bottom - tiles_top))
            if self.sub_kind == "day":
                list_bottom = self._draw_day_strip(surface, tiles_rect, scale, self.sub_options, self.sub_index)
            else:
                list_bottom = self._draw_choice_tiles(surface, tiles_rect, scale, self.sub_options, self.sub_index)
            hint = small_font.render("Enter to confirm, Backspace to cancel", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, min(list_bottom + int(10 * scale), content_rect.bottom - int(6 * scale))))
        elif self.state in ("result", "recap"):
            text_top = content_rect.top
            if self.result_tier is not None:
                self._draw_tier_meter(surface, content_rect, scale, self.result_tier)
                text_top += int(34 * scale)
            for i, text_line in enumerate(self.result_text):
                surface.blit(body_font.render(text_line, True, ui.TEXT_COLOR),
                             (content_rect.left, text_top + i * int(32 * scale)))
            hint = small_font.render("Enter to continue", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, text_top + len(self.result_text) * int(32 * scale) + int(20 * scale)))
        elif self.state == "draw":
            if self.drawn_cards:
                msg = f"{self.active.name} draws {len(self.drawn_cards)} card(s):"
            else:
                msg = f"{self.active.name} has no new cards to draw right now."
            ui.blit_wrapped(surface, body_font, msg, ui.TEXT_COLOR,
                             content_rect.left + content_rect.width // 2, content_rect.top, content_rect.width)
            if self.drawn_cards:
                tiles_top = content_rect.top + int(36 * scale)
                tiles_rect = pygame.Rect(content_rect.left, tiles_top,
                                          content_rect.width, max(0, content_rect.bottom - tiles_top - int(22 * scale)))
                self._draw_card_tiles(surface, tiles_rect, self.drawn_cards, scale, badge="NEW")
            if len(self.hand) > MAX_HAND:
                hint_text = f"Enter to continue - discard down to {MAX_HAND} cards next."
            else:
                hint_text = "Enter to continue to your turn."
            hint = small_font.render(hint_text, True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, content_rect.bottom - int(16 * scale)))
        elif self.state == "discard":
            over_by = len(self.hand) - MAX_HAND
            msg = f"Hand over the limit - discard {over_by} more down to {MAX_HAND}."
            ui.blit_wrapped(surface, body_font, msg, ui.TEXT_COLOR,
                             content_rect.left + content_rect.width // 2, content_rect.top, content_rect.width)
            bar_top = content_rect.top + int(28 * scale)
            bar_rect = pygame.Rect(content_rect.left, bar_top, content_rect.width, max(4, int(10 * scale)))
            bar_color = (230, 90, 90) if over_by > 0 else (150, 220, 150)
            bar_max = MAX_HAND + DRAW_MAX
            ui.draw_bar(surface, bar_rect, len(self.hand), bar_max, bar_color)
            tick_x = bar_rect.left + int(bar_rect.width * (MAX_HAND / bar_max))
            pygame.draw.line(surface, ui.ACCENT, (tick_x, bar_rect.top - int(3 * scale)),
                              (tick_x, bar_rect.bottom + int(3 * scale)), max(1, int(2 * scale)))
            if self.hand:
                card_top = bar_rect.bottom + int(14 * scale)
                card_rect = pygame.Rect(content_rect.left, card_top,
                                         content_rect.width, max(0, content_rect.bottom - card_top - int(22 * scale)))
                self._draw_card_tiles(surface, card_rect, [self.hand[self.hand_index]], scale, badge="DISCARD?")
            hint = small_font.render("Enter to discard the selected card", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, content_rect.bottom - int(16 * scale)))
        else:
            ui.blit_wrapped(surface, body_font, "Pick a card to play, or End Week when you're done.",
                             ui.TEXT_COLOR, content_rect.left + content_rect.width // 2, content_rect.top,
                             content_rect.width)

        if self.state != "draw":
            # The "draw" announcement above already reveals the newly drawn cards as
            # its own tiles; self.hand already includes them (added in _start_turn),
            # so showing the fanned hand here too would just duplicate the reveal.
            self._draw_hand_row(surface, main_rect, scale, body_font, small_font)

    def _draw_character_card(self, surface, rect, name, scale, selected):
        border = ui.ACCENT if selected else ui.BORDER_OUTER
        top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
        bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
        ui.draw_panel(surface, rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=border)
        char, kind, stat = self._target_info(name)
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

    def _draw_target_cards(self, surface, content_rect, scale):
        names = self.target_options
        gap = int(10 * scale)
        card_w = int(85 * scale)
        card_h = min(content_rect.height, int(170 * scale))
        max_visible = max(1, (content_rect.width + gap) // (card_w + gap))
        if len(names) <= max_visible:
            start_idx = 0
        else:
            start_idx = max(0, min(self.target_index - max_visible // 2, len(names) - max_visible))
        visible = names[start_idx:start_idx + max_visible]
        total_w = len(visible) * card_w + (len(visible) - 1) * gap
        start_x = content_rect.left + (content_rect.width - total_w) // 2
        for i, name in enumerate(visible):
            idx = start_idx + i
            rect = pygame.Rect(start_x + i * (card_w + gap), content_rect.top, card_w, card_h)
            self._draw_character_card(surface, rect, name, scale, selected=(idx == self.target_index))
        arrow_font = ui.font(20, scale)
        if start_idx > 0:
            label = arrow_font.render("<", True, ui.ACCENT)
            surface.blit(label, label.get_rect(midright=(start_x - int(6 * scale), content_rect.top + card_h // 2)))
        if start_idx + len(visible) < len(names):
            label = arrow_font.render(">", True, ui.ACCENT)
            surface.blit(label, label.get_rect(midleft=(start_x + total_w + int(6 * scale), content_rect.top + card_h // 2)))

    def _draw_card_tiles(self, surface, content_rect, cards, scale, badge=None):
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
            label = self._card_label(card)
            tint = KIND_COLORS.get(label, ui.ACCENT)
            top_color = tuple(min(255, c // 3 + 40) for c in tint)
            bottom_color = tuple(min(255, c // 5 + 20) for c in tint)
            ui.draw_panel(surface, rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=tint)
            pad = int(8 * scale)
            y = rect.top + pad
            display_name, display_blurb = self._card_face(card)
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
                label = blurb_font.render(line, True, ui.DIM_TEXT)
                surface.blit(label, label.get_rect(midtop=(rect.centerx, y)))
                y += blurb_font.get_height() + int(1 * scale)
            if badge:
                badge_label = badge_font.render(badge, True, ui.BG)
                badge_rect = badge_label.get_rect()
                badge_rect.topright = (rect.right - int(2 * scale), rect.top + int(2 * scale))
                pad_badge = int(3 * scale)
                bg_rect = badge_rect.inflate(pad_badge * 2, pad_badge * 2)
                pygame.draw.rect(surface, tint, bg_rect)
                surface.blit(badge_label, badge_rect)

    def _draw_choice_tiles(self, surface, content_rect, scale, options, selected_index):
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

    def _draw_day_strip(self, surface, content_rect, scale, options, selected_index):
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

    def _draw_step_row(self, surface, rect, scale, current_index):
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

    def _draw_tier_meter(self, surface, content_rect, scale, tier):
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

    def _hand_card_surface(self, card, card_w, card_h, scale, selected):
        """Renders one hand card onto its own per-pixel-alpha surface so it can
        be rotated for the fan layout without leaving black corners."""
        card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, card_w, card_h)
        top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
        bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
        border = ui.ACCENT if selected else ui.BORDER_OUTER
        ui.draw_panel(card_surf, rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=border)
        display_name, _blurb = self._card_face(card)
        name_font = ui.font(min(13, max(9, card_w // 13)), scale)
        ui.blit_wrapped(card_surf, name_font, display_name, ui.TEXT_COLOR,
                         rect.centerx, rect.top + int(10 * scale), card_w - int(12 * scale))
        kind_font = ui.font(12, scale)
        kind_label = kind_font.render(self._card_label(card), True, ui.DIM_TEXT)
        card_surf.blit(kind_label, kind_label.get_rect(midbottom=(rect.centerx, rect.bottom - int(8 * scale))))
        return card_surf

    def _hand_row_selecting(self):
        """Whether the bottom hand row is the thing driving input right now -
        only true during the actual card-selection steps (playing or
        discarding). The "draw" state hides the row entirely elsewhere; every
        other state (target/sub_choice/result/recap) just wants a quiet
        reminder of what's in hand, not a full interactive fan."""
        return self.state in ("hand", "discard")

    def _hand_row_reserved_height(self, scale):
        """Vertical space to leave for the bottom hand row. Full-size while it's
        an active selector; collapsed to a title strip otherwise (or nearly
        nothing during "draw", where the row isn't drawn at all), so other
        stages get more room for their own content above."""
        if self.state == "draw":
            return int(20 * scale)
        if self._hand_row_selecting():
            return int(200 * scale)
        return int(60 * scale)

    def _draw_hand_row_collapsed(self, surface, main_rect, scale, cards):
        """Title-only strip shown while the hand isn't the active selector -
        just enough to remind you what's in hand without eating the space a
        full fanned row would reserve."""
        margin = int(20 * scale)
        gap = int(8 * scale)
        n = len(cards)
        card_h = int(30 * scale)
        available = main_rect.width - margin * 2 - gap * (n - 1)
        card_w = min(int(120 * scale), max(int(40 * scale), available // n))
        total_w = n * card_w + (n - 1) * gap
        start_x = main_rect.centerx - total_w // 2
        y = main_rect.bottom - margin - card_h
        name_font = ui.font(min(13, max(9, card_w // 11)), scale)
        for i, card in enumerate(cards):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            ui.draw_panel(surface, rect, scale, border_color=ui.BORDER_OUTER)
            display_name, _ = self._card_face(card)
            ui.blit_wrapped(surface, name_font, display_name, ui.DIM_TEXT,
                             rect.centerx, rect.centery - name_font.get_height() // 2, card_w - int(8 * scale))

    def _draw_hand_row(self, surface, main_rect, scale, body_font, small_font):
        cards = list(self.hand)
        if not self._hand_row_selecting():
            if cards:
                self._draw_hand_row_collapsed(surface, main_rect, scale, cards)
            return
        show_end_button = self.state != "discard"
        nav_options = cards + [END_WEEK] if show_end_button else cards
        if not cards and not show_end_button:
            return

        card_w = int(150 * scale)
        card_h = card_w + int(25 * scale)
        shadow_off = (int(6 * scale), int(8 * scale))
        margin = int(20 * scale)

        button_h = int(46 * scale) if show_end_button else 0
        button_gap = int(14 * scale) if show_end_button else 0
        row_bottom = main_rect.bottom - margin - button_h - button_gap
        row_base_y = row_bottom - card_h

        n = len(cards)
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
            selected_i = self.hand_index if self.state in ("hand", "discard") and self.hand_index < n else None

            draw_order = [i for i in range(n) if i != selected_i] + ([selected_i] if selected_i is not None else [])
            for i in draw_order:
                card = cards[i]
                t = (i - (n - 1) / 2) / max(1, (n - 1) / 2) if n > 1 else 0.0
                cx = start_x + i * step + card_w / 2
                cy = row_base_y + arc * (t ** 2) + card_h / 2
                angle = -t * max_rot
                selected = i == selected_i
                if selected:
                    cy -= int(16 * scale)
                card_surf = self._hand_card_surface(card, card_w, card_h, scale, selected)
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
            selected = self.state == "hand" and self.hand_index == n
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
