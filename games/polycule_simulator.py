"""Polycule Simulator: a no-combat, card-driven relationship sim.

No character is "the player" - you cycle control between everyone in the
cule, one week at a time. Each week the active member draws a hand of
cards (flavored by their archetype) and plays as many as they like against
existing partners, met prospects, or the household as a whole, then passes
control to the next member. Time is tracked as weeks inside quarters, and
some cards (dates) get negotiated and scheduled onto a calendar instead of
resolving immediately.

This module is the game's controller: it owns input handling, the
turn/selection state machine, and the top-level draw() layout. The simulated
world itself lives in `polycule_model.PolyculeModel`, how a played card
resolves lives in `polycule_rules`, and each drawn widget (network diagram,
roster, dossier, calendar, card tiles, hand row) lives in its own
`polycule_view_*` module as free functions taking this object (`sim`) as
their first argument - see CLAUDE.md for why the view was split that way.
Domain state is reached through the thin read-proxies just below `reset`
(self.members -> self.model.members, etc.) so both the controller and the
view modules stay terse.
"""

import math
import random
from pathlib import Path

import pygame

from . import save
from . import tween
from . import ui
from . import polycule_rules as rules
from . import polycule_save
from . import polycule_view_calendar as calendar_view
from . import polycule_view_cards as cards
from . import polycule_view_dossier as dossier
from . import polycule_view_hand as hand
from . import polycule_view_network as network
from . import polycule_view_roster as roster
from .base import Game
from .polycule_constants import (
    ACTIVITIES,
    DAYS,
    DRAW_MAX,
    MAX_HAND,
    SCHEDULE_OFFSETS,
    WEEKS_PER_QUARTER,
)
from .polycule_model import PolyculeModel
from .polycule_states import STATES

SAVE_PATH = Path(__file__).resolve().parent.parent / "saves" / "polycule.json"


class PolyculeSimulator(Game):
    name = "Polycule Simulator"
    description = ("A card game about your polycule. Arrows + Enter to play, Tab roster, C calendar, "
                    "F5 save, F9 load.")

    def __init__(self, screen):
        super().__init__(screen)

    def reset(self):
        # The whole simulated world - members, prospects, relationships,
        # calendar, harmony/chaos - lives on the model, built fresh from an
        # injected rng. Everything else is view/controller state only.
        self.model = PolyculeModel(random.Random())
        self._reset_controller_state()
        self._start_turn(self.model.active)

    def _reset_controller_state(self):
        """(Re)initialize everything that isn't the model itself - shared by
        `reset` (fresh world) and `deserialize` (loaded world)."""
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

        self.card_fx = []

    def _remove_card(self, card, kind):
        """Removes `card` from the hand, recording an outgoing fade/shrink
        animation (games/polycule_view_hand.py:draw_card_fx) at whatever
        position it currently occupies - fan row (`kind` != "discard") or
        collapsed strip - so it doesn't just vanish between frames. Every
        card-removal call site (discard, an immediately-resolved play, a
        played card that needed a target, a scheduled date going through)
        goes through here instead of touching self.hand directly."""
        self.card_fx.append({
            "card": card,
            "index": self.hand.index(card),
            "n": len(self.hand),
            "fan": hand.hand_row_selecting(self),
            "elapsed": 0.0,
            "kind": kind,
        })
        self.hand.remove(card)

    # --- Save / load -----------------------------------------------------
    # Only the model (the simulated world) is captured - loading a save
    # always resumes at the top of the active member's turn, same as reset,
    # just with the saved world instead of a freshly generated one. See
    # polycule_save.py for why and what that leaves out.

    def serialize(self):
        return polycule_save.serialize_model(self.model)

    def deserialize(self, data):
        self.model = polycule_save.deserialize_model(data)
        self._reset_controller_state()
        self._start_turn(self.model.active)

    def _save_to_disk(self):
        SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        save.save_to_path(SAVE_PATH, self.serialize())

    def _load_from_disk(self):
        if SAVE_PATH.exists():
            self.deserialize(save.load_from_path(SAVE_PATH))

    # --- Domain read-proxies -------------------------------------------------
    # Domain state and queries live on self.model; these keep the controller
    # and the view modules terse (self.members, self.get_rel, ...) without
    # each having to reach through self.model. Reads only - mutation goes
    # through the model or the rules module.

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
        self._remove_card(self.pending_card, "play")
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
            self._remove_card(self.pending_card, "play")
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
        if event.key == pygame.K_F5:
            self._save_to_disk()
            return
        if event.key == pygame.K_F9:
            self._load_from_disk()
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
        # Turn/selection FSM: each state's input handling lives in its own
        # object (see polycule_states); self.state is that object's key.
        handler = STATES.get(self.state)
        if handler is not None:
            handler.handle_key(self, event)

    def update(self, dt):
        self.anim_t += dt

        for fx in self.card_fx:
            fx["elapsed"] += dt
        self.card_fx = [fx for fx in self.card_fx if fx["elapsed"] < hand.FX_DURATION]

        _, diagram, center, min_r, max_r, scale, _, _ = network.network_geometry(self)
        active = self.active
        ring = [m for m in self.members if m.name != active.name]

        ring_angles = network.weighted_ring_angles(self, ring, active)
        ring_positions = {}
        for member in ring:
            angle = ring_angles[member.name]
            strength = network.strength(self.get_rel(active.name, member.name))
            radius = max_r - strength * (max_r - min_r)
            ring_positions[member.name] = (center[0] + radius * math.cos(angle),
                                            center[1] + radius * math.sin(angle))
        node_diameter = 2 * int(9 * scale)
        ring_positions = network.relax_ring_positions(ring_positions, center, min_r, max_r, node_diameter)

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
            ring_positions[name] = network.clamp_to_rect(pos, diagram, ring_margin)

        target_positions = {active.name: center, **ring_positions}
        for name, target in target_positions.items():
            cur = self.node_pos.get(name, target)
            self.node_pos[name] = tween.approach_point(cur, target, dt)

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
            target = network.clamp_to_rect(target, diagram, prospect_margin)
            cur = self.node_pos.get(pname, target)
            self.node_pos[pname] = tween.approach_point(cur, target, dt)

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
                roster.draw_roster(self, surface, rect, scale)
                hint_text = "Up/Down to select, Enter for dossier, Tab to close" if len(self.members) > 1 else "Enter for dossier, Tab to close"
                hint = small_font.render(hint_text, True, ui.DIM_TEXT)
            elif self.overlay == "dossier":
                dossier.draw_dossier(self, surface, rect, scale)
                hint = small_font.render("Backspace to roster, Tab to close", True, ui.DIM_TEXT)
            else:
                calendar_view.draw_calendar(self, surface, rect, scale)
                hint = small_font.render("C to close", True, ui.DIM_TEXT)
            surface.blit(hint, (rect.left + int(20 * scale), rect.bottom - int(34 * scale)))
            return

        panel, diagram, center, min_r, max_r, _, members_rect, prospects_rect = network.network_geometry(self)
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

        roster.draw_member_row(self, surface, members_rect, scale)
        roster.draw_prospect_row(self, surface, prospects_rect, scale)
        network.draw_network(self, surface, center, scale)

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
            cards.draw_step_row(surface, pygame.Rect(main_rect.left + int(20 * scale), content_top,
                                                       main_rect.width - int(40 * scale), step_row_h), scale, step_index)
            content_top += step_row_h + int(14 * scale)
        content_bottom = main_rect.bottom - hand.hand_row_reserved_height(self, scale)
        content_rect = pygame.Rect(main_rect.left + int(20 * scale), content_top,
                                    main_rect.width - int(40 * scale), max(0, content_bottom - content_top))

        if self.state == "target":
            ui.blit_wrapped(surface, body_font, f"Target for {self.pending_card['name']}:",
                             ui.TEXT_COLOR, content_rect.left + content_rect.width // 2, content_rect.top, content_rect.width)
            cards_top = content_rect.top + int(32 * scale)
            cards_rect = pygame.Rect(content_rect.left, cards_top,
                                      content_rect.width, max(0, content_rect.bottom - cards_top - int(22 * scale)))
            cards.draw_target_cards(self, surface, cards_rect, scale)
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
                list_bottom = cards.draw_day_strip(surface, tiles_rect, scale, self.sub_options, self.sub_index)
            else:
                list_bottom = cards.draw_choice_tiles(surface, tiles_rect, scale, self.sub_options, self.sub_index)
            hint = small_font.render("Enter to confirm, Backspace to cancel", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, min(list_bottom + int(10 * scale), content_rect.bottom - int(6 * scale))))
        elif self.state in ("result", "recap"):
            text_top = content_rect.top
            if self.result_tier is not None:
                cards.draw_tier_meter(surface, content_rect, scale, self.result_tier)
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
                             content_rect.left + content_rect.width // 2, content_rect.top,
                             content_rect.width)
            if self.drawn_cards:
                tiles_top = content_rect.top + int(36 * scale)
                tiles_rect = pygame.Rect(content_rect.left, tiles_top,
                                          content_rect.width, max(0, content_rect.bottom - tiles_top - int(22 * scale)))
                cards.draw_card_tiles(self, surface, tiles_rect, self.drawn_cards, scale, badge="NEW")
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
                cards.draw_card_tiles(self, surface, card_rect, [self.hand[self.hand_index]], scale, badge="DISCARD?")
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
            hand.draw_hand_row(self, surface, main_rect, scale, body_font, small_font)
            hand.draw_card_fx(self, surface, main_rect, scale)
