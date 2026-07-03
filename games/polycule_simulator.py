"""Polycule Simulator: a no-combat, card-driven relationship sim.

No character is "the player" - you cycle control between everyone in the
cule, one week at a time. Each week the active member draws a hand of
cards (flavored by their archetype) and plays as many as they like against
existing partners, met prospects, or the household as a whole, then passes
control to the next member.
"""

import math
import random

import pygame

from . import pixel_portrait, ui
from .base import Game

FIRST_NAMES = [
    "Jamie", "Steve", "Alex", "Riley", "Sam", "Jordan", "Casey", "Morgan",
    "Skyler", "Devon", "Quinn", "Rowan", "Ash", "Bex", "Theo", "Nico",
    "Frankie", "Wren", "Lior", "Sage",
]

ARCHETYPES = [
    "astrology-pilled barista",
    "crypto bro who found ethical non-monogamy on a podcast",
    "theater kid who never left the theater",
    "crunchy homesteader with three chickens named after exes",
    "spreadsheet person who tracks feelings in a pivot table",
    "yoga instructor who over-shares in savasana",
    "DM who's still mad you missed session 4",
    "vegan chef with strong opinions about cheese",
    "rock climber who talks about 'sending' too much",
    "furry with a very normal day job",
]

VENUES = [
    "the co-op", "a klezmer-punk show", "a polyamory meetup",
    "the dog park", "a plant swap", "queer trivia night",
    "a Discord voice channel at 2am",
]

KINK_POOL = [
    ("hand-holding", 1), ("vanilla missionary", 1), ("dirty talk", 2),
    ("light bondage", 2), ("roleplay", 2), ("praise kink", 2),
    ("degradation", 3), ("impact play", 3), ("exhibitionism", 3),
    ("primal play", 4), ("breath play", 5), ("blood play", 5),
    ("knife play", 5),
]

HOBBIES = ["pottery", "D&D", "birdwatching", "rock climbing", "baking sourdough", "thrifting"]
PROJECTS = ["a zine", "a mural", "a home video", "a diorama", "a podcast"]

COMMIT_THRESHOLD = 70
MAX_PROSPECTS_PER_MEMBER = 3
HAND_SIZE = 5

GENERIC_CARDS = [
    {"id": "date_night", "name": "Date Night", "kind": "bond",
     "blurb": "Plan a night out with {target}.", "trust": (-2, 10), "spark": (0, 14)},
    {"id": "deep_talk", "name": "Deep Talk", "kind": "bond",
     "blurb": "Stay up talking with {target} about feelings.", "trust": (2, 12), "spark": (-2, 4)},
    {"id": "chore_split", "name": "Split Chores", "kind": "bond",
     "blurb": "Divide the week's chores with {target}.", "trust": (-10, 8), "spark": (-6, 2)},
    {"id": "shared_hobby", "name": "Shared Hobby", "kind": "bond",
     "blurb": "Pick up {hobby} with {target}.", "trust": (-2, 8), "spark": (0, 10)},
    {"id": "art_project", "name": "Joint Art Project", "kind": "bond",
     "blurb": "Start {project} with {target}.", "trust": (-4, 10), "spark": (2, 12)},
    {"id": "boundary", "name": "Set a Boundary", "kind": "bond",
     "blurb": "Name something you need with {target}.", "trust": (4, 14), "spark": (-6, 2)},
    {"id": "jealousy_checkin", "name": "Jealousy Check-in", "kind": "bond",
     "blurb": "Talk through a jealous feeling with {target}.", "trust": (0, 12), "spark": (-4, 6)},
    {"id": "cohabit", "name": "Move In Together", "kind": "bond",
     "blurb": "Take the cohabitating leap with {target}.", "trust": (-10, 18), "spark": (-10, 6)},

    {"id": "flirt", "name": "Flirt", "kind": "court",
     "blurb": "Turn up the charm on {target}.", "interest": (5, 25)},
    {"id": "vulnerable_share", "name": "Vulnerable Share", "kind": "court",
     "blurb": "Open up to {target} about something real.", "interest": (-5, 30)},
    {"id": "go_quiet", "name": "Go Quiet", "kind": "court",
     "blurb": "Don't text {target} back for a few days.", "interest": (-25, 5)},
    {"id": "ask_out", "name": "Ask Them Out", "kind": "court",
     "blurb": "Suggest an actual date with {target}.", "interest": (0, 30)},

    {"id": "go_out", "name": "Go Out", "kind": "meet",
     "blurb": "Head out to {venue} and see who's around."},

    {"id": "house_meeting", "name": "House Meeting", "kind": "group",
     "blurb": "Call a meeting to hash things out.", "harmony": (-10, 20), "chaos": (-15, 10)},
    {"id": "group_dinner", "name": "Group Dinner", "kind": "group",
     "blurb": "Cook a big dinner for everyone.", "harmony": (0, 15), "chaos": (-5, 5)},
    {"id": "calendar_sync", "name": "Calendar Sync", "kind": "group",
     "blurb": "Try to sync everyone's calendars.", "harmony": (-5, 10), "chaos": (-20, 5)},
    {"id": "group_trip", "name": "Plan a Group Trip", "kind": "group",
     "blurb": "Propose a trip for the whole cule.", "harmony": (-8, 18), "chaos": (0, 10)},
]

ARCHETYPE_CARDS = {
    "astrology-pilled barista": {"id": "chart_reading", "name": "Read Their Chart", "kind": "bond",
                                  "blurb": "Insist on doing {target}'s birth chart.", "trust": (-4, 10), "spark": (2, 10)},
    "crypto bro who found ethical non-monogamy on a podcast": {"id": "pitch_coin", "name": "Pitch a Coin", "kind": "bond",
                                  "blurb": "Explain your new relationship token to {target}.", "trust": (-14, 4), "spark": (-2, 8)},
    "theater kid who never left the theater": {"id": "monologue", "name": "Perform a Monologue", "kind": "bond",
                                  "blurb": "Perform a dramatic monologue at {target}.", "trust": (-4, 8), "spark": (0, 14)},
    "crunchy homesteader with three chickens named after exes": {"id": "name_chicken", "name": "Name a Chicken", "kind": "bond",
                                  "blurb": "Name a new chicken after {target}.", "trust": (2, 12), "spark": (-2, 6)},
    "spreadsheet person who tracks feelings in a pivot table": {"id": "pivot_table", "name": "Share the Pivot Table", "kind": "bond",
                                  "blurb": "Show {target} the feelings spreadsheet.", "trust": (-6, 14), "spark": (-4, 4)},
    "yoga instructor who over-shares in savasana": {"id": "savasana", "name": "Guided Savasana", "kind": "bond",
                                  "blurb": "Lead {target} through an over-sharing savasana.", "trust": (0, 12), "spark": (-2, 8)},
    "DM who's still mad you missed session 4": {"id": "campaign_arc", "name": "Write Them Into the Campaign", "kind": "bond",
                                  "blurb": "Write {target} into the D&D campaign.", "trust": (-2, 10), "spark": (0, 10)},
    "vegan chef with strong opinions about cheese": {"id": "cashew_cheese", "name": "Serve Cashew Cheese", "kind": "bond",
                                  "blurb": "Make {target} try the cashew cheese.", "trust": (-6, 8), "spark": (0, 10)},
    "rock climber who talks about 'sending' too much": {"id": "send_it", "name": "Take Them Climbing", "kind": "bond",
                                  "blurb": "Take {target} climbing and narrate the whole time.", "trust": (-4, 10), "spark": (2, 12)},
    "furry with a very normal day job": {"id": "fursona", "name": "Introduce the Fursona", "kind": "bond",
                                  "blurb": "Introduce {target} to your fursona.", "trust": (-8, 12), "spark": (0, 12)},
}

COMMIT_CARD = {"id": "commit", "name": "Ask Them In", "kind": "commit",
               "blurb": "Invite {target} to join the cule for real."}
END_WEEK = {"id": "end_week", "name": "End Week", "kind": "end", "blurb": "Wrap up and pass it on."}


class Character:
    def __init__(self, rng, name=None, archetype=None):
        self.name = name or rng.choice(FIRST_NAMES)
        self.archetype = archetype or rng.choice(ARCHETYPES)
        self.kinks = rng.sample(KINK_POOL, 2)
        self.seed = rng.randint(0, 1 << 30)

    def deck(self):
        deck = list(GENERIC_CARDS)
        extra = ARCHETYPE_CARDS.get(self.archetype)
        if extra:
            deck = deck + [extra, extra]
        return deck


class PolyculeSimulator(Game):
    name = "Polycule Simulator"
    description = "A card game about your polycule. Arrows + Enter to play cards, Tab for roster."

    def __init__(self, screen):
        super().__init__(screen)
        self.rng = random.Random()

    def reset(self):
        self.week = 1
        self.rng = random.Random()
        first = Character(self.rng)
        self.members = [first]
        self.relationships = {}
        self.prospects = {}
        self.harmony = 60
        self.chaos = 20
        self.node_pos = {}
        self.state = "hand"
        self.hand = []
        self.hand_index = 0
        self.target_options = []
        self.target_index = 0
        self.pending_card = None
        self.result_text = []
        self.show_roster = False
        self._draw_hand()

    @property
    def active(self):
        return self.members[(self.week - 1) % len(self.members)]

    def _rel_key(self, name_a, name_b):
        return frozenset((name_a, name_b))

    def get_rel(self, name_a, name_b):
        return self.relationships.setdefault(self._rel_key(name_a, name_b), {"trust": 50, "spark": 50})

    def _member_prospects(self, member_name):
        return {n: p for n, p in self.prospects.items() if p["met_by"] == member_name}

    def _eligible_cards(self, member):
        pool = []
        others = [m for m in self.members if m.name != member.name]
        my_prospects = self._member_prospects(member.name)
        eligible_prospects = {n: p for n, p in my_prospects.items() if p["interest"] >= COMMIT_THRESHOLD}
        for card in member.deck():
            if card["kind"] == "bond" and not others:
                continue
            if card["kind"] == "court" and not my_prospects:
                continue
            if card["kind"] == "meet" and len(my_prospects) >= MAX_PROSPECTS_PER_MEMBER:
                continue
            pool.append(card)
        if eligible_prospects:
            pool.append(COMMIT_CARD)
        return pool

    def _draw_hand(self):
        member = self.active
        pool = self._eligible_cards(member)
        n = min(HAND_SIZE, len(pool))
        self.hand = self.rng.sample(pool, n) if n else []
        self.hand_index = 0
        self.state = "hand"

    def _card_targets(self, card):
        member = self.active
        if card["kind"] == "bond":
            return [m.name for m in self.members if m.name != member.name]
        if card["kind"] == "court":
            return list(self._member_prospects(member.name).keys())
        if card["kind"] == "commit":
            my_prospects = self._member_prospects(member.name)
            return [n for n, p in my_prospects.items() if p["interest"] >= COMMIT_THRESHOLD]
        return []

    def _roll(self, lo, hi):
        return self.rng.randint(lo, hi)

    def _resolve(self, card, target_name):
        member = self.active
        if card["kind"] == "bond":
            rel = self.get_rel(member.name, target_name)
            t_lo, t_hi = card["trust"]
            s_lo, s_hi = card["spark"]
            trust_d = self._roll(t_lo, t_hi)
            spark_d = self._roll(s_lo, s_hi)
            rel["trust"] = max(0, min(100, rel["trust"] + trust_d))
            rel["spark"] = max(0, min(100, rel["spark"] + spark_d))
            self.result_text = [
                f"{member.name} + {target_name}: {card['name']}",
                f"Trust {trust_d:+d}, Spark {spark_d:+d}.",
            ]
        elif card["kind"] == "court":
            prospect = self.prospects[target_name]
            lo, hi = card["interest"]
            delta = self._roll(lo, hi)
            prospect["interest"] = max(0, min(100, prospect["interest"] + delta))
            self.result_text = [f"{member.name} -> {target_name}: {card['name']} ({delta:+d} interest)"]
            if prospect["interest"] <= 0:
                del self.prospects[target_name]
                self.result_text.append(f"{target_name} stops responding entirely.")
        elif card["kind"] == "meet":
            venue = self.rng.choice(VENUES)
            existing = set(self.prospects) | {m.name for m in self.members}
            candidates = [n for n in FIRST_NAMES if n not in existing]
            name = self.rng.choice(candidates) if candidates else self.rng.choice(FIRST_NAMES)
            stranger = Character(self.rng, name=name)
            interest = self._roll(10, 30)
            self.prospects[stranger.name] = {"char": stranger, "interest": interest, "met_by": member.name}
            self.result_text = [f"{member.name} meets {stranger.name} at {venue}.",
                                 f"({stranger.archetype}, +{interest} interest)"]
        elif card["kind"] == "commit":
            prospect = self.prospects.pop(target_name)
            new_member = prospect["char"]
            start = min(90, prospect["interest"] + 10)
            self.members.append(new_member)
            self.get_rel(member.name, new_member.name).update({"trust": start, "spark": start})
            self.result_text = [f"{new_member.name} joins the cule for real!"]
        elif card["kind"] == "group":
            h_lo, h_hi = card["harmony"]
            c_lo, c_hi = card["chaos"]
            h_d = self._roll(h_lo, h_hi)
            c_d = self._roll(c_lo, c_hi)
            self.harmony = max(0, min(100, self.harmony + h_d))
            self.chaos = max(0, min(100, self.chaos + c_d))
            self.result_text = [f"{member.name}: {card['name']}", f"Harmony {h_d:+d}, Chaos {c_d:+d}."]

    def _end_week(self):
        self.week += 1
        self._draw_hand()

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_TAB:
            self.show_roster = not self.show_roster
            return
        if self.show_roster:
            return
        if self.state == "hand":
            options = self.hand + [END_WEEK]
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.hand_index = (self.hand_index - 1) % len(options)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.hand_index = (self.hand_index + 1) % len(options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                card = options[self.hand_index]
                if card["kind"] == "end":
                    self._end_week()
                elif card["kind"] in ("bond", "court", "commit"):
                    targets = self._card_targets(card)
                    if not targets:
                        self.result_text = [f"{card['name']} has no one left to target. It fizzles."]
                        self.hand.remove(card)
                        self.hand_index = 0
                        self.state = "result"
                    else:
                        self.pending_card = card
                        self.target_options = targets
                        self.target_index = 0
                        self.state = "target"
                else:
                    self._resolve(card, None)
                    self.hand.remove(card)
                    self.hand_index = 0
                    self.state = "result"
        elif self.state == "target":
            if event.key in (pygame.K_UP, pygame.K_w):
                self.target_index = (self.target_index - 1) % len(self.target_options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.target_index = (self.target_index + 1) % len(self.target_options)
            elif event.key == pygame.K_BACKSPACE:
                self.state = "hand"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                target = self.target_options[self.target_index]
                self._resolve(self.pending_card, target)
                self.hand.remove(self.pending_card)
                self.hand_index = 0
                self.state = "result"
        elif self.state == "result":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.state = "hand"
                if self.hand_index >= len(self.hand):
                    self.hand_index = max(0, len(self.hand) - 1)

    def _network_geometry(self):
        w, h = self.screen.get_size()
        scale = ui.scale_factor(self.screen)
        panel_w = int(w * 0.42)
        panel = pygame.Rect(int(16 * scale), int(16 * scale), panel_w, h - int(32 * scale))
        header_h = int(110 * scale)
        diagram = pygame.Rect(panel.left + int(10 * scale), panel.top + header_h,
                               panel.width - int(20 * scale), panel.height - header_h - int(10 * scale))
        center = diagram.center
        max_r = min(diagram.width, diagram.height) / 2 - int(60 * scale)
        min_r = int(110 * scale)
        return panel, diagram, center, min_r, max_r, scale

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

    def update(self, dt):
        _, _, center, min_r, max_r, scale = self._network_geometry()
        active = self.active
        ring = [m for m in self.members if m.name != active.name]
        n = len(ring)
        rate = min(1.0, dt * 2.5)

        target_positions = {active.name: center}
        for i, member in enumerate(ring):
            angle = (i / n) * 2 * math.pi - math.pi / 2 if n else 0
            strength = self._strength(self.get_rel(active.name, member.name))
            radius = max_r - strength * (max_r - min_r)
            target_positions[member.name] = (center[0] + radius * math.cos(angle),
                                              center[1] + radius * math.sin(angle))

        for name, target in target_positions.items():
            cur = self.node_pos.get(name, target)
            self.node_pos[name] = (cur[0] + (target[0] - cur[0]) * rate, cur[1] + (target[1] - cur[1]) * rate)

        for pname, prospect in self.prospects.items():
            anchor = self.node_pos.get(prospect["met_by"], center)
            siblings = [n for n, p in self.prospects.items() if p["met_by"] == prospect["met_by"]]
            idx = siblings.index(pname)
            angle = (idx / max(1, len(siblings))) * 2 * math.pi + 0.6
            strength = prospect["interest"] / 100.0
            sat_max, sat_min = 130 * scale, 60 * scale
            radius = sat_max - strength * (sat_max - sat_min)
            target = (anchor[0] + radius * math.cos(angle), anchor[1] + radius * math.sin(angle))
            cur = self.node_pos.get(pname, target)
            self.node_pos[pname] = (cur[0] + (target[0] - cur[0]) * rate, cur[1] + (target[1] - cur[1]) * rate)

    def _draw_network(self, surface, center, scale):
        active = self.active
        ring = [m for m in self.members if m.name != active.name]

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

        node_r = int(26 * scale)
        pygame.draw.circle(surface, (255, 220, 120), center, node_r + int(4 * scale))
        pixel_portrait.draw_bust(surface, pygame.Rect(int(center[0] - node_r), int(center[1] - node_r),
                                                        node_r * 2, node_r * 2), active.seed)
        name_font = ui.font(20, scale)
        label = name_font.render(f"{active.name} (active)", True, ui.TEXT_COLOR)
        surface.blit(label, label.get_rect(midtop=(center[0], center[1] + node_r + int(6 * scale))))

        node_r2 = int(22 * scale)
        ring_font = ui.font(16, scale)
        for member in ring:
            pos = self.node_pos.get(member.name, center)
            t = self._strength(self.get_rel(active.name, member.name))
            ring_color = self._bond_color(t)
            pygame.draw.circle(surface, ring_color, pos, node_r2 + int(3 * scale))
            pixel_portrait.draw_bust(surface, pygame.Rect(int(pos[0] - node_r2), int(pos[1] - node_r2),
                                                             node_r2 * 2, node_r2 * 2), member.seed)
            label = ring_font.render(member.name, True, ui.TEXT_COLOR)
            surface.blit(label, label.get_rect(midtop=(pos[0], pos[1] + node_r2 + int(4 * scale))))

        node_r3 = int(14 * scale)
        for pname, prospect in self.prospects.items():
            pos = self.node_pos.get(pname, center)
            t = prospect["interest"] / 100.0
            ring_color = self._prospect_color(t)
            pygame.draw.circle(surface, ring_color, pos, node_r3 + int(2 * scale))
            char = prospect["char"]
            pixel_portrait.draw_bust(surface, pygame.Rect(int(pos[0] - node_r3), int(pos[1] - node_r3),
                                                             node_r3 * 2, node_r3 * 2), char.seed)
            small_font = ui.font(16, scale)
            label = small_font.render(char.name, True, ui.DIM_TEXT)
            surface.blit(label, label.get_rect(midtop=(pos[0], pos[1] + node_r3 + int(3 * scale))))

    def _draw_roster(self, surface, rect, scale):
        ui.draw_panel(surface, rect, scale)
        title_font = ui.font(30, scale)
        body_font = ui.font(20, scale)
        surface.blit(title_font.render("Roster", True, ui.ACCENT), (rect.left + int(20 * scale), rect.top + int(14 * scale)))
        y = rect.top + int(60 * scale)
        portrait_r = int(28 * scale)
        for member in self.members:
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
            surface.blit(body_font.render(member.archetype, True, ui.DIM_TEXT), (tx, y + int(22 * scale)))
            bar_w = rect.width - (tx - rect.left) - int(20 * scale)
            ui.draw_bar(surface, pygame.Rect(tx, y + int(46 * scale), bar_w, int(10 * scale)), avg_trust, 100, (140, 180, 240))
            ui.draw_bar(surface, pygame.Rect(tx, y + int(60 * scale), bar_w, int(10 * scale)), avg_spark, 100, (240, 140, 190))
            y += portrait_r * 2 + int(24 * scale)

    def draw(self, surface):
        surface.fill((26, 18, 32))
        w, h = surface.get_size()
        scale = ui.scale_factor(surface)
        title_font = ui.font(34, scale)
        body_font = ui.font(24, scale)
        small_font = ui.font(20, scale)

        if self.show_roster:
            rect = pygame.Rect(int(40 * scale), int(40 * scale), w - int(80 * scale), h - int(80 * scale))
            self._draw_roster(surface, rect, scale)
            hint = small_font.render("Tab to close", True, ui.DIM_TEXT)
            surface.blit(hint, (rect.left + int(20 * scale), rect.bottom - int(34 * scale)))
            return

        panel, diagram, center, min_r, max_r, _ = self._network_geometry()
        ui.draw_panel(surface, panel, scale)
        y = panel.top + int(12 * scale)
        surface.blit(small_font.render(f"Week {self.week} - {self.active.name}'s turn", True, ui.TEXT_COLOR),
                     (panel.left + int(10 * scale), y))
        y += int(26 * scale)
        bar_w = panel.width - int(20 * scale)
        ui.draw_bar(surface, pygame.Rect(panel.left + int(10 * scale), y, bar_w, int(12 * scale)), self.harmony, 100, (120, 220, 140))
        surface.blit(small_font.render("Harmony", True, ui.DIM_TEXT), (panel.left + int(10 * scale), y + int(14 * scale)))
        y += int(34 * scale)
        ui.draw_bar(surface, pygame.Rect(panel.left + int(10 * scale), y, bar_w, int(12 * scale)), self.chaos, 100, (220, 120, 120))
        surface.blit(small_font.render("Chaos", True, ui.DIM_TEXT), (panel.left + int(10 * scale), y + int(14 * scale)))

        self._draw_network(surface, center, scale)

        main_rect = pygame.Rect(panel.right + int(16 * scale), int(16 * scale),
                                 w - panel.width - int(48 * scale), h - int(32 * scale))
        ui.draw_panel(surface, main_rect, scale)

        title = title_font.render(self.name, True, ui.ACCENT)
        surface.blit(title, (main_rect.left + int(20 * scale), main_rect.top + int(16 * scale)))

        content_top = main_rect.top + int(70 * scale)
        content_bottom = main_rect.bottom - int(180 * scale)
        content_rect = pygame.Rect(main_rect.left + int(20 * scale), content_top,
                                    main_rect.width - int(40 * scale), max(0, content_bottom - content_top))

        if self.state == "target":
            member = self.active
            surface.blit(body_font.render(f"Choose a target for {self.pending_card['name']}:", True, ui.TEXT_COLOR),
                         (content_rect.left, content_rect.top))
            for i, name in enumerate(self.target_options):
                color = ui.ACCENT if i == self.target_index else ui.TEXT_COLOR
                opt_y = content_rect.top + int(50 * scale) + i * int(36 * scale)
                if i == self.target_index:
                    ui.draw_cursor(surface, (content_rect.left + int(2 * scale), opt_y + int(12 * scale)), size=int(10 * scale))
                label = body_font.render(name, True, color)
                surface.blit(label, (content_rect.left + int(24 * scale), opt_y))
            hint = small_font.render("Enter to confirm, Backspace to cancel", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, content_rect.bottom - int(30 * scale)))
        elif self.state == "result":
            for i, line in enumerate(self.result_text):
                surface.blit(body_font.render(line, True, ui.TEXT_COLOR),
                             (content_rect.left, content_rect.top + i * int(32 * scale)))
            hint = small_font.render("Enter to continue", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, content_rect.top + len(self.result_text) * int(32 * scale) + int(20 * scale)))
        else:
            hint = body_font.render("Pick a card to play, or End Week when you're done.", True, ui.TEXT_COLOR)
            surface.blit(hint, (content_rect.left, content_rect.top))

        self._draw_hand_row(surface, main_rect, scale, body_font, small_font)

    def _draw_hand_row(self, surface, main_rect, scale, body_font, small_font):
        options = self.hand + [END_WEEK]
        gap = int(14 * scale)
        available = main_rect.width - int(40 * scale) - gap * (len(options) - 1)
        card_w = min(int(150 * scale), available // len(options))
        card_h = card_w + int(25 * scale)
        total_w = len(options) * card_w + (len(options) - 1) * gap
        start_x = main_rect.centerx - total_w // 2
        y = main_rect.bottom - card_h - int(20 * scale)

        for i, card in enumerate(options):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            selected = self.state == "hand" and i == self.hand_index
            top_color = (110, 70, 130) if selected else ui.PASTEL_TOP
            bottom_color = (150, 90, 160) if selected else ui.PASTEL_BOTTOM
            border = ui.ACCENT if selected else ui.BORDER_OUTER
            ui.draw_panel(surface, rect, scale, top_color=top_color, bottom_color=bottom_color, border_color=border)
            name_font = ui.font(min(15, max(10, card_w // 11)), scale)
            ui.blit_wrapped(surface, name_font, card["name"], ui.TEXT_COLOR,
                             rect.centerx, rect.top + int(10 * scale), card_w - int(12 * scale))
            kind_font = ui.font(14, scale)
            kind_label = kind_font.render(card["kind"], True, ui.DIM_TEXT)
            surface.blit(kind_label, kind_label.get_rect(midbottom=(rect.centerx, rect.bottom - int(8 * scale))))
