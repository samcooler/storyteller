"""Polycule Simulator: a no-combat, card-driven relationship sim.

No character is "the player" - you cycle control between everyone in the
cule, one week at a time. Each week the active member draws a hand of
cards (flavored by their archetype) and plays as many as they like against
existing partners, met prospects, or the household as a whole, then passes
control to the next member. Time is tracked as weeks inside quarters, and
some cards (dates) get negotiated and scheduled onto a calendar instead of
resolving immediately.
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
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ACTIVITIES = ["Park", "Movie", "Jog"]
SCHEDULE_OFFSETS = [("This week", 0), ("Next week", 1), ("In two weeks", 2)]

TRAITS = ["extraversion", "openness", "conscientiousness", "security", "empathy"]
STATUSES = ["happiness", "fulfillment", "energy", "stress", "desire"]

COMMIT_THRESHOLD = 70
MAX_PROSPECTS_PER_MEMBER = 3
HAND_SIZE = 5
WEEKS_PER_QUARTER = 12
ENERGY_COST = 15
START_MEMBERS = 3
START_OTHERS = 4

GENERIC_CARDS = [
    {"id": "date_night", "name": "Date Night", "kind": "date",
     "blurb": "Plan a date with {target}."},
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
        self.traits = {t: rng.randint(20, 90) for t in TRAITS}
        self.statuses = {s: rng.randint(40, 80) for s in STATUSES}
        self.preferred_activity = rng.choice(ACTIVITIES)

    def deck(self):
        deck = list(GENERIC_CARDS)
        extra = ARCHETYPE_CARDS.get(self.archetype)
        if extra:
            deck = deck + [extra, extra]
        return deck


class PolyculeSimulator(Game):
    name = "Polycule Simulator"
    description = "A card game about your polycule. Arrows + Enter to play, Tab roster, C calendar."

    def __init__(self, screen):
        super().__init__(screen)
        self.rng = random.Random()

    def reset(self):
        self.rng = random.Random()
        self.week = 1
        self.anim_t = 0.0

        names = self.rng.sample(FIRST_NAMES, START_MEMBERS + START_OTHERS + 2)
        self.members = [Character(self.rng, name=n) for n in names[:START_MEMBERS + START_OTHERS]]
        self.relationships = {}
        for i in range(len(self.members)):
            for j in range(i + 1, len(self.members)):
                a, b = self.members[i], self.members[j]
                self.relationships[self._rel_key(a.name, b.name)] = {
                    "trust": self.rng.randint(35, 90), "spark": self.rng.randint(35, 90),
                }

        self.prospects = {}
        for n in names[START_MEMBERS + START_OTHERS:]:
            c = Character(self.rng, name=n)
            met_by = self.rng.choice(self.members).name
            self.prospects[c.name] = {"char": c, "interest": self.rng.randint(20, 60), "met_by": met_by}

        self.harmony = self.rng.randint(50, 80)
        self.chaos = self.rng.randint(10, 40)
        self.calendar = {}
        self.node_pos = {}
        self.overlay = None
        self.roster_scroll = 0

        self.state = "hand"
        self.hand = []
        self.hand_index = 0
        self.target_options = []
        self.target_index = 0
        self.pending_card = None
        self.result_text = []

        self.pending_target = None
        self.sub_kind = None
        self.sub_options = []
        self.sub_index = 0
        self.date_target_week = None
        self.proposed_day = None
        self.counter_day = None
        self.chosen_day = None
        self.date_is_prospect = False

        self._draw_hand()

    @property
    def active(self):
        return self.members[(self.week - 1) % len(self.members)]

    @property
    def quarter(self):
        return (self.week - 1) // WEEKS_PER_QUARTER + 1

    @property
    def week_in_quarter(self):
        return (self.week - 1) % WEEKS_PER_QUARTER + 1

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
            if card["kind"] in ("bond", "date") and not others and not my_prospects:
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
        my_prospects = self._member_prospects(member.name)
        if card["kind"] == "bond":
            return [m.name for m in self.members if m.name != member.name]
        if card["kind"] == "date":
            return [m.name for m in self.members if m.name != member.name] + list(my_prospects.keys())
        if card["kind"] == "court":
            return list(my_prospects.keys())
        if card["kind"] == "commit":
            return [n for n, p in my_prospects.items() if p["interest"] >= COMMIT_THRESHOLD]
        return []

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

    def _roll(self, lo, hi):
        return self.rng.randint(lo, hi)

    def _unique_name(self):
        existing = set(self.prospects) | {m.name for m in self.members}
        candidates = [n for n in FIRST_NAMES if n not in existing]
        if candidates:
            return self.rng.choice(candidates)
        suffixes = ["Jr.", "II", "the Younger", "from the group chat", "with the other haircut"]
        for _ in range(20):
            name = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(suffixes)}"
            if name not in existing:
                return name
        return f"{self.rng.choice(FIRST_NAMES)} #{self.rng.randint(100, 999)}"

    def _flavor(self, card, target_name=None):
        kwargs = {
            "target": target_name or "",
            "hobby": self.rng.choice(HOBBIES),
            "project": self.rng.choice(PROJECTS),
            "venue": self.rng.choice(VENUES),
        }
        return card["blurb"].format(**kwargs)

    def _spend_energy(self):
        active = self.active
        active.statuses["energy"] = max(0, active.statuses["energy"] - ENERGY_COST)

    def _resolve(self, card, target_name):
        member = self.active
        flavor = self._flavor(card, target_name)
        if card["kind"] == "bond":
            rel = self.get_rel(member.name, target_name)
            t_lo, t_hi = card["trust"]
            s_lo, s_hi = card["spark"]
            trust_d = self._roll(t_lo, t_hi)
            spark_d = self._roll(s_lo, s_hi)
            rel["trust"] = max(0, min(100, rel["trust"] + trust_d))
            rel["spark"] = max(0, min(100, rel["spark"] + spark_d))
            self.result_text = [flavor, f"Trust {trust_d:+d}, Spark {spark_d:+d}."]
        elif card["kind"] == "court":
            prospect = self.prospects[target_name]
            lo, hi = card["interest"]
            delta = self._roll(lo, hi)
            prospect["interest"] = max(0, min(100, prospect["interest"] + delta))
            self.result_text = [flavor, f"({delta:+d} interest)"]
            if prospect["interest"] <= 0:
                del self.prospects[target_name]
                self.result_text.append(f"{target_name} stops responding entirely.")
        elif card["kind"] == "meet":
            venue = self.rng.choice(VENUES)
            name = self._unique_name()
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
            self.result_text = [flavor, f"{new_member.name} joins the cule for real!"]
        elif card["kind"] == "group":
            h_lo, h_hi = card["harmony"]
            c_lo, c_hi = card["chaos"]
            h_d = self._roll(h_lo, h_hi)
            c_d = self._roll(c_lo, c_hi)
            self.harmony = max(0, min(100, self.harmony + h_d))
            self.chaos = max(0, min(100, self.chaos + c_d))
            self.result_text = [flavor, f"Harmony {h_d:+d}, Chaos {c_d:+d}."]
        self._spend_energy()

    def _negotiate_date(self, target_name, day):
        member = self.active
        my_prospects = self._member_prospects(member.name)
        is_prospect = target_name in my_prospects
        willingness = my_prospects[target_name]["interest"] if is_prospect else self.get_rel(member.name, target_name)["trust"]
        busy_days = set(self.rng.sample(DAYS, k=self.rng.randint(1, 3)))
        if day in busy_days:
            if willingness >= 50:
                free_days = [d for d in DAYS if d not in busy_days] or [day]
                return "counter", self.rng.choice(free_days), is_prospect
            return "decline", None, is_prospect
        if willingness >= 30:
            return "accept", None, is_prospect
        return "decline", None, is_prospect

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
        self.hand.remove(self.pending_card)
        self.hand_index = 0
        self._spend_energy()
        self.state = "result"

    def _advance_sub_choice(self):
        label, value = self.sub_options[self.sub_index]
        if self.sub_kind == "week":
            self.date_target_week = self.week + value
            self._enter_sub("day", [(d, d) for d in DAYS])
        elif self.sub_kind == "day":
            self.proposed_day = value
            outcome, counter_day, is_prospect = self._negotiate_date(self.pending_target, value)
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
            self.hand.remove(self.pending_card)
            self.hand_index = 0
            self._spend_energy()
            self.state = "result"

    def _resolve_scheduled_event(self, ev):
        a = next((m for m in self.members if m.name == ev["a"]), None)
        if a is None:
            return [f"Plans between {ev['a']} and {ev['b']} quietly fell through."]
        activity = ev["activity"]
        verb = "go jogging" if activity == "Jog" else f"head to the {activity.lower()}"
        if ev["is_prospect"]:
            prospect = self.prospects.get(ev["b"])
            if prospect is None:
                return [f"{ev['a']}'s plans with {ev['b']} fell through - they'd already drifted apart."]
            match = activity == prospect["char"].preferred_activity
            delta = self.rng.randint(15, 30) if match else self.rng.randint(-5, 10)
            prospect["interest"] = max(0, min(100, prospect["interest"] + delta))
            lines = [
                f"{ev['a']} and {ev['b']} {verb} on {ev['day']}.",
                f"{'This is exactly their thing.' if match else 'They have an okay time, but seem distracted.'} ({delta:+d} interest)",
            ]
            if prospect["interest"] <= 0:
                del self.prospects[ev["b"]]
                lines.append(f"{ev['b']} stops responding entirely.")
            return lines
        b = next((m for m in self.members if m.name == ev["b"]), None)
        if b is None:
            return [f"{ev['a']}'s plans with {ev['b']} fell through."]
        match = activity == b.preferred_activity
        trust_d = self.rng.randint(4, 12) if match else self.rng.randint(-4, 6)
        spark_d = self.rng.randint(6, 16) if match else self.rng.randint(-2, 8)
        rel = self.get_rel(a.name, b.name)
        rel["trust"] = max(0, min(100, rel["trust"] + trust_d))
        rel["spark"] = max(0, min(100, rel["spark"] + spark_d))
        return [
            f"{ev['a']} and {ev['b']} {verb} on {ev['day']}.",
            f"{'A perfect match of interests.' if match else 'Not exactly their favorite, but nice together anyway.'} "
            f"Trust {trust_d:+d}, Spark {spark_d:+d}.",
        ]

    def _end_week(self):
        self.week += 1
        self._draw_hand()
        events = self.calendar.pop(self.week, [])
        if events:
            lines = []
            for ev in events:
                lines.extend(self._resolve_scheduled_event(ev))
            self.result_text = lines
            self.state = "recap"

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
                self.roster_scroll += 1
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.roster_scroll = max(0, self.roster_scroll - 1)
            return
        if self.overlay:
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
                elif card["kind"] in ("bond", "court", "commit", "date"):
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
            if event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
                self.target_index = (self.target_index - 1) % len(self.target_options)
            elif event.key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
                self.target_index = (self.target_index + 1) % len(self.target_options)
            elif event.key == pygame.K_BACKSPACE:
                self.state = "hand"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                target = self.target_options[self.target_index]
                if self.pending_card["kind"] == "date":
                    self._start_date_flow(target)
                else:
                    self._resolve(self.pending_card, target)
                    self.hand.remove(self.pending_card)
                    self.hand_index = 0
                    self.state = "result"
        elif self.state == "sub_choice":
            if event.key in (pygame.K_UP, pygame.K_w):
                self.sub_index = (self.sub_index - 1) % len(self.sub_options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.sub_index = (self.sub_index + 1) % len(self.sub_options)
            elif event.key == pygame.K_BACKSPACE:
                self.state = "hand"
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._advance_sub_choice()
        elif self.state in ("result", "recap"):
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

    def _current_highlight(self):
        if self.state == "target" and self.target_options:
            return self.target_options[self.target_index]
        if self.state == "sub_choice" and self.pending_target:
            return self.pending_target
        return None

    def update(self, dt):
        self.anim_t += dt
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
            if member.name == highlight:
                self._draw_glow(surface, pos, node_r2, scale)
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
            if pname == highlight:
                self._draw_glow(surface, pos, node_r3, scale)
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
        title_font = ui.font(30, scale, title=True)
        body_font = ui.font(20, scale)
        small_font = ui.font(15, scale)
        surface.blit(title_font.render("Roster", True, ui.ACCENT), (rect.left + int(20 * scale), rect.top + int(14 * scale)))
        y = rect.top + int(60 * scale)
        available_h = rect.height - int(60 * scale) - int(50 * scale)
        row_h = int(28 * scale) * 2 + int(38 * scale)
        portrait_r = int(28 * scale)
        max_visible = max(1, available_h // row_h)
        self.roster_scroll = max(0, min(self.roster_scroll, max(0, len(self.members) - max_visible)))
        visible = self.members[self.roster_scroll:self.roster_scroll + max_visible]
        for member in visible:
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
            line_h = int(22 * scale)
            bar_w = rect.width - (tx - rect.left) - int(20 * scale)
            surface.blit(body_font.render(member.archetype, True, ui.DIM_TEXT), (tx, y + line_h))
            bars_y = y + line_h * 2 + int(4 * scale)
            bar_h = max(4, int(8 * scale))
            ui.draw_bar(surface, pygame.Rect(tx, bars_y, bar_w, bar_h), avg_trust, 100, (140, 180, 240))
            ui.draw_bar(surface, pygame.Rect(tx, bars_y + bar_h + 2, bar_w, bar_h), avg_spark, 100, (240, 140, 190))
            half = bar_w // 2 - int(4 * scale)
            status_y = bars_y + (bar_h + 2) * 2 + 2
            ui.draw_bar(surface, pygame.Rect(tx, status_y, half, bar_h),
                        member.statuses["happiness"], 100, (255, 210, 120))
            ui.draw_bar(surface, pygame.Rect(tx + half + int(8 * scale), status_y, half, bar_h),
                        member.statuses["energy"], 100, (150, 220, 255))
            traits_label = (f"Extra {member.traits['extraversion']}  Open {member.traits['openness']}  "
                             f"Empathy {member.traits['empathy']}")
            surface.blit(small_font.render(traits_label, True, ui.DIM_TEXT), (tx, status_y + bar_h + int(6 * scale)))
            y += row_h

    def _draw_calendar(self, surface, rect, scale):
        ui.draw_panel(surface, rect, scale)
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
        surface.fill((26, 18, 32))
        w, h = surface.get_size()
        scale = ui.scale_factor(surface)
        title_font = ui.font(34, scale, title=True)
        body_font = ui.font(24, scale)
        small_font = ui.font(20, scale)

        if self.overlay:
            rect = pygame.Rect(int(40 * scale), int(40 * scale), w - int(80 * scale), h - int(80 * scale))
            if self.overlay == "roster":
                self._draw_roster(surface, rect, scale)
                hint_text = "Up/Down to scroll, Tab to close" if len(self.members) > 1 else "Tab to close"
                hint = small_font.render(hint_text, True, ui.DIM_TEXT)
            else:
                self._draw_calendar(surface, rect, scale)
                hint = small_font.render("C to close", True, ui.DIM_TEXT)
            surface.blit(hint, (rect.left + int(20 * scale), rect.bottom - int(34 * scale)))
            return

        panel, diagram, center, min_r, max_r, _ = self._network_geometry()
        ui.draw_panel(surface, panel, scale)
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

        self._draw_network(surface, center, scale)

        main_rect = pygame.Rect(panel.right + int(16 * scale), int(16 * scale),
                                 w - panel.width - int(48 * scale), h - int(32 * scale))
        ui.draw_panel(surface, main_rect, scale)

        title = title_font.render(self.name, True, ui.ACCENT)
        surface.blit(title, (main_rect.left + int(20 * scale), main_rect.top + int(16 * scale)))

        content_top = main_rect.top + int(70 * scale)
        content_bottom = main_rect.bottom - int(200 * scale)
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
                "activity": f"Where should {self.active.name} and {self.pending_target} go?",
            }
            surface.blit(body_font.render(prompts.get(self.sub_kind, "Choose:"), True, ui.TEXT_COLOR),
                         (content_rect.left, content_rect.top))
            labels = [label for label, _value in self.sub_options]
            list_bottom = self._draw_option_list(surface, content_rect, body_font, labels, self.sub_index)
            hint = small_font.render("Enter to confirm, Backspace to cancel", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, min(list_bottom + int(10 * scale), content_rect.bottom - int(6 * scale))))
        elif self.state in ("result", "recap"):
            for i, text_line in enumerate(self.result_text):
                surface.blit(body_font.render(text_line, True, ui.TEXT_COLOR),
                             (content_rect.left, content_rect.top + i * int(32 * scale)))
            hint = small_font.render("Enter to continue", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, content_rect.top + len(self.result_text) * int(32 * scale) + int(20 * scale)))
        else:
            ui.blit_wrapped(surface, body_font, "Pick a card to play, or End Week when you're done.",
                             ui.TEXT_COLOR, content_rect.left + content_rect.width // 2, content_rect.top,
                             content_rect.width)

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

        half = bar_w // 2 - int(2 * scale)
        ui.draw_bar(surface, pygame.Rect(rect.left + pad, y, half, bar_h), char.statuses["happiness"], 100, (255, 210, 120))
        ui.draw_bar(surface, pygame.Rect(rect.left + pad + half + int(4 * scale), y, half, bar_h),
                    char.statuses["energy"], 100, (150, 220, 255))

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

    def _draw_option_list(self, surface, content_rect, body_font, labels, selected_index):
        scale = ui.scale_factor(self.screen)
        top = content_rect.top + int(50 * scale)
        bottom = content_rect.bottom - int(36 * scale)
        available = max(1, bottom - top)
        n = max(1, len(labels))
        size = 24
        font_obj = body_font
        while size > 12:
            font_obj = ui.font(size, scale)
            if (font_obj.get_height() + int(6 * scale)) * n <= available:
                break
            size -= 2
        spacing = font_obj.get_height() + int(6 * scale)
        for i, text in enumerate(labels):
            color = ui.ACCENT if i == selected_index else ui.TEXT_COLOR
            opt_y = top + i * spacing
            if i == selected_index:
                ui.draw_cursor(surface, (content_rect.left + int(2 * scale), opt_y + spacing // 2), size=int(10 * scale))
            label = font_obj.render(text, True, color)
            surface.blit(label, (content_rect.left + int(24 * scale), opt_y))
        return top + n * spacing

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
