"""Polycule Simulator: a no-combat, looping JRPG-menu relationship sim."""

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
CHORES = ["a house budget spreadsheet", "meal prep", "a garden bed", "a group costume"]
GROUP_EVENTS = [
    "a calendar-sync meeting", "a group dinner", "a processing circle after a rough week",
    "planning a group vacation", "the group chat argument about dishes",
]


class Character:
    def __init__(self, rng):
        self.name = rng.choice(FIRST_NAMES)
        self.archetype = rng.choice(ARCHETYPES)
        self.kinks = rng.sample(KINK_POOL, 2)
        self.seed = rng.randint(0, 1 << 30)
        self.trust = 50
        self.spark = 50

    def clamp(self):
        self.trust = max(0, min(100, self.trust))
        self.spark = max(0, min(100, self.spark))


class PolyculeSimulator(Game):
    name = "Polycule Simulator"
    description = "Navigate your polycule, day by day. 1/2 to choose, Enter to confirm."

    PLAYER_SEED = 1337

    def __init__(self, screen):
        super().__init__(screen)
        self.rng = random.Random()
        self.node_pos = {}

    def reset(self):
        self.day = 1
        self.partners = []
        self.prospects = {}
        self.harmony = 60
        self.chaos = 20
        self.state = "idle"
        self.event_text = []
        self.result_text = []
        self.choices = []
        self.selected = 0
        self.pending_effects = None
        self.current_event_kind = None
        self.node_pos = {}

    def _new_stranger(self):
        for _ in range(10):
            c = Character(self.rng)
            if c.name not in self.prospects and not any(p.name == c.name for p in self.partners):
                return c
        return Character(self.rng)

    def _clamp_group(self):
        self.harmony = max(0, min(100, self.harmony))
        self.chaos = max(0, min(100, self.chaos))

    def _start_meet_stranger(self):
        venue = self.rng.choice(VENUES)
        if self.prospects and self.rng.random() < 0.5:
            stranger = self.rng.choice(list(self.prospects.values()))["char"]
            self.current_event_kind = ("meet", stranger)
            self.event_text = [
                f"Day {self.day}: {stranger.name} texts to hang out",
                f"again, this time at {venue}.",
            ]
        else:
            stranger = self._new_stranger()
            self.current_event_kind = ("meet", stranger)
            self.event_text = [
                f"Day {self.day}: {stranger.name}, {stranger.archetype},",
                f"catches your eye at {venue}.",
            ]
        self.choices = ["Flirt", "Play it cool"]

    def _start_activity(self, partner):
        kind = self.rng.choice(["cohabitating", "hobby", "art_project", "chores"])
        if kind == "cohabitating":
            label = "living together"
        elif kind == "hobby":
            label = f"a shared hobby ({self.rng.choice(HOBBIES)})"
        elif kind == "art_project":
            label = f"a joint art project ({self.rng.choice(PROJECTS)})"
        else:
            label = f"splitting chores ({self.rng.choice(CHORES)})"
        self.current_event_kind = ("activity", partner, kind)
        self.event_text = [f"Day {self.day}: {partner.name} wants to spend time on", label + "."]
        self.choices = ["Fully engage", "Keep it light"]

    def _start_kink_check(self):
        a, b = self.rng.sample(self.partners, 2)
        ka = self.rng.choice(a.kinks)
        kb = self.rng.choice(b.kinks)
        gap = abs(ka[1] - kb[1])
        self.current_event_kind = ("kink", a, b, ka, kb, gap)
        if gap >= 2:
            self.event_text = [
                f"Day {self.day}: {a.name} is into {ka[0]}, but {b.name}",
                f"finds it {'too intense' if ka[1] > kb[1] else 'too vanilla'}. Tension simmers.",
            ]
            self.choices = ["Talk it through", "Avoid the topic"]
        else:
            self.event_text = [
                f"Day {self.day}: {a.name} and {b.name} are both into",
                f"{ka[0]} / {kb[0]}. Sparks fly.",
            ]
            self.choices = ["Explore it together", "Keep it simple"]

    def _start_group_event(self):
        label = self.rng.choice(GROUP_EVENTS)
        self.current_event_kind = ("group", label)
        self.event_text = [f"Day {self.day}: the polycule faces", label + "."]
        self.choices = ["Lean in", "Keep it light"]

    def _start_day(self):
        pool = ["meet"]
        if self.partners:
            pool += ["activity", "activity"]
        if len(self.partners) >= 2:
            pool += ["kink", "group"]
        kind = self.rng.choice(pool)
        if kind == "meet":
            self._start_meet_stranger()
        elif kind == "activity":
            self._start_activity(self.rng.choice(self.partners))
        elif kind == "kink":
            self._start_kink_check()
        elif kind == "group":
            self._start_group_event()
        self.state = "choice"
        self.selected = 0

    def _resolve(self, choice_index):
        kind = self.current_event_kind[0]
        if kind == "meet":
            stranger = self.current_event_kind[1]
            if choice_index == 0:
                gain = self.rng.randint(15, 35)
                interest_val = self.prospects.setdefault(stranger.name, {"char": stranger, "interest": 0})
                interest_val["interest"] += gain
                if interest_val["interest"] >= 70:
                    del self.prospects[stranger.name]
                    self.partners.append(stranger)
                    self.result_text = [
                        f"{stranger.name} agrees to become your partner!",
                        "They join the polycule.",
                    ]
                else:
                    self.result_text = [f"{stranger.name} seems interested. (+{gain} interest)"]
            else:
                self.result_text = ["You keep it casual and move on with your day."]
        elif kind == "activity":
            partner = self.current_event_kind[1]
            act = self.current_event_kind[2]
            ranges = {
                "cohabitating": ((-10, 18), (-12, 6), (-15, 12)),
                "hobby": ((-3, 10), (-2, 12), (0, 8)),
                "art_project": ((-6, 12), (0, 14), (-4, 6)),
                "chores": ((-12, 8), (-8, 2), (-14, 10)),
            }[act]
            (t_lo, t_hi), (s_lo, s_hi), (h_lo, h_hi) = ranges
            if choice_index == 0:
                trust_d = self.rng.randint(t_lo, t_hi)
                spark_d = self.rng.randint(s_lo, s_hi)
                harmony_d = self.rng.randint(h_lo, h_hi)
            else:
                trust_d = self.rng.randint(t_lo // 3, t_hi // 3)
                spark_d = self.rng.randint(s_lo // 3, s_hi // 3)
                harmony_d = self.rng.randint(h_lo // 3, h_hi // 3)
            partner.trust += trust_d
            partner.spark += spark_d
            partner.clamp()
            self.harmony += harmony_d
            self._clamp_group()
            self.result_text = [
                f"Trust {trust_d:+d}, Spark {spark_d:+d} with {partner.name}.",
                f"Household Harmony {harmony_d:+d}.",
            ]
        elif kind == "kink":
            _, a, b, ka, kb, gap = self.current_event_kind
            if gap >= 2:
                if choice_index == 0:
                    spark_d = -self.rng.randint(0, 4)
                    trust_d = self.rng.randint(2, 8)
                    text = "They talk it through. Awkward but honest."
                else:
                    spark_d = -self.rng.randint(8, 16)
                    trust_d = -self.rng.randint(2, 6)
                    text = "It goes unspoken. The tension lingers."
                a.spark += spark_d
                b.spark += spark_d
                a.trust += trust_d
                b.trust += trust_d
            else:
                if choice_index == 0:
                    spark_d = self.rng.randint(10, 18)
                    trust_d = self.rng.randint(4, 10)
                    text = "They explore it together. Great chemistry."
                else:
                    spark_d = self.rng.randint(2, 6)
                    trust_d = self.rng.randint(2, 6)
                    text = "They keep it simple, but it still works."
                a.spark += spark_d
                b.spark += spark_d
                a.trust += trust_d
                b.trust += trust_d
            a.clamp()
            b.clamp()
            self.result_text = [text, f"Spark {spark_d:+d}, Trust {trust_d:+d} for both."]
        elif kind == "group":
            label = self.current_event_kind[1]
            if choice_index == 0:
                harmony_d = self.rng.randint(-10, 20)
                chaos_d = self.rng.randint(-15, 10)
            else:
                harmony_d = self.rng.randint(-3, 6)
                chaos_d = self.rng.randint(-3, 3)
            self.harmony += harmony_d
            self.chaos += chaos_d
            self._clamp_group()
            self.result_text = [
                f"The polycule handles {label}.",
                f"Harmony {harmony_d:+d}, Chaos {chaos_d:+d}.",
            ]
        self.state = "result"

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if self.state == "idle":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._start_day()
        elif self.state == "choice":
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.choices)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.choices)
            elif event.key == pygame.K_1:
                self.selected = 0
                self._resolve(0)
            elif event.key == pygame.K_2 and len(self.choices) > 1:
                self.selected = 1
                self._resolve(1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._resolve(self.selected)
        elif self.state == "result":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.day += 1
                self.state = "idle"

    def _network_geometry(self):
        w, h = self.screen.get_size()
        panel_w = 320
        panel = pygame.Rect(10, 10, panel_w, h - 20)
        diagram = pygame.Rect(panel.left + 10, panel.top + 96, panel.width - 20, panel.height - 106)
        center = diagram.center
        max_r = min(diagram.width, diagram.height) / 2 - 26
        min_r = 48
        return panel, diagram, center, min_r, max_r

    @staticmethod
    def _strength(partner):
        return max(0.0, min(1.0, (partner.trust + partner.spark) / 200.0))

    @staticmethod
    def _lerp_color(c0, c1, t):
        return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))

    def _bond_color(self, t):
        return self._lerp_color((90, 110, 160), (255, 120, 170), t)

    def update(self, dt):
        _, _, center, min_r, max_r = self._network_geometry()
        n = len(self.partners)
        for i, partner in enumerate(self.partners):
            angle = (i / n) * 2 * math.pi - math.pi / 2 if n else 0
            strength = self._strength(partner)
            radius = max_r - strength * (max_r - min_r)
            target = (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
            cur = self.node_pos.get(partner.name, target)
            rate = min(1.0, dt * 2.5)
            self.node_pos[partner.name] = (
                cur[0] + (target[0] - cur[0]) * rate,
                cur[1] + (target[1] - cur[1]) * rate,
            )

    def _draw_network(self, surface, panel, diagram, center):
        n = len(self.partners)

        for i in range(n):
            for j in range(i + 1, n):
                a, b = self.partners[i], self.partners[j]
                pa, pb = self.node_pos.get(a.name, center), self.node_pos.get(b.name, center)
                t = self.harmony / 100.0
                color = self._lerp_color((70, 70, 90), (150, 210, 160), t)
                width = 1 + round(t * 4)
                pygame.draw.line(surface, color, pa, pb, width)

        for partner in self.partners:
            pos = self.node_pos.get(partner.name, center)
            t = self._strength(partner)
            color = self._bond_color(t)
            width = 1 + round(t * 7)
            pygame.draw.line(surface, color, center, pos, width)

        player_r = 20
        pygame.draw.circle(surface, (255, 255, 255), center, player_r + 3)
        pixel_portrait.draw_bust(
            surface,
            pygame.Rect(center[0] - player_r, center[1] - player_r, player_r * 2, player_r * 2),
            self.PLAYER_SEED,
        )

        node_r = 16
        for partner in self.partners:
            pos = self.node_pos.get(partner.name, center)
            t = self._strength(partner)
            ring_color = self._bond_color(t)
            pygame.draw.circle(surface, ring_color, pos, node_r + 3)
            pixel_portrait.draw_bust(
                surface,
                pygame.Rect(int(pos[0]) - node_r, int(pos[1]) - node_r, node_r * 2, node_r * 2),
                partner.seed,
            )
            label = pygame.font.SysFont(None, 18).render(partner.name, True, ui.TEXT_COLOR)
            surface.blit(label, label.get_rect(midtop=(pos[0], pos[1] + node_r + 4)))

    def draw(self, surface):
        surface.fill((26, 18, 32))
        w, h = surface.get_size()
        title_font = pygame.font.SysFont(None, 34)
        body_font = pygame.font.SysFont(None, 26)
        small_font = pygame.font.SysFont(None, 20)

        panel, diagram, center, min_r, max_r = self._network_geometry()
        ui.draw_panel(surface, panel)
        y = panel.top + 12
        surface.blit(small_font.render(f"Day {self.day}", True, ui.TEXT_COLOR), (panel.left + 10, y))
        y += 22
        surface.blit(small_font.render("Household", True, ui.DIM_TEXT), (panel.left + 10, y))
        y += 18
        ui.draw_bar(surface, pygame.Rect(panel.left + 10, y, panel.width - 20, 10), self.harmony, 100, (120, 220, 140))
        y += 14
        surface.blit(small_font.render("Harmony", True, ui.DIM_TEXT), (panel.left + 10, y))
        y += 22
        ui.draw_bar(surface, pygame.Rect(panel.left + 10, y, panel.width - 20, 10), self.chaos, 100, (220, 120, 120))
        y += 14
        surface.blit(small_font.render("Chaos", True, ui.DIM_TEXT), (panel.left + 10, y))

        if not self.partners:
            hint = small_font.render("Your polycule will appear here as you meet people.", True, ui.DIM_TEXT)
            surface.blit(hint, hint.get_rect(center=diagram.center))
        self._draw_network(surface, panel, diagram, center)

        main_rect = pygame.Rect(panel.right + 10, 10, w - panel.width - 30, h - 20)
        ui.draw_panel(surface, main_rect)

        title = title_font.render(self.name, True, ui.ACCENT)
        surface.blit(title, (main_rect.left + 20, main_rect.top + 16))

        text_y = main_rect.top + 60
        if self.state == "idle":
            lines = [f"Day {self.day} begins.", "", "Press Enter to see what happens today."]
        elif self.state == "choice":
            lines = list(self.event_text)
        else:
            lines = list(self.result_text) + ["", "Press Enter to continue."]

        for line in lines:
            surface.blit(body_font.render(line, True, ui.TEXT_COLOR), (main_rect.left + 20, text_y))
            text_y += 30

        if self.state == "choice":
            opt_y = main_rect.bottom - 20 - 34 * len(self.choices)
            for i, choice in enumerate(self.choices):
                color = ui.ACCENT if i == self.selected else ui.TEXT_COLOR
                if i == self.selected:
                    ui.draw_cursor(surface, (main_rect.left + 22, opt_y + 12), size=10)
                label = body_font.render(f"{i + 1}. {choice}", True, color)
                surface.blit(label, (main_rect.left + 42, opt_y))
                opt_y += 34
