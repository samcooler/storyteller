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

from . import card_loader, pixel_portrait, ui
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
    "raw milk enthusiast with a lot of opinions",
    "person who met their metamour on a raid night",
    "tarot reader who overcharges everyone including their partners",
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

# Single source of truth for every character-owned stat (5 traits + 5
# statuses). Every display tier (dossier, roster row, selector tile, ring)
# reads from this table instead of hand-picking which stats it bothers to
# show, so all ten stay visually equal citizens even though only a couple
# are hooked into card resolution today.
STAT_INFO = {
    "extraversion": {
        "label": "Extraversion", "abbr": "EXT", "color": (255, 170, 90), "category": "trait",
        "flavor": ("keeps to themself", "comfortable either way", "lights up every room"),
    },
    "openness": {
        "label": "Openness", "abbr": "OPN", "color": (150, 210, 255), "category": "trait",
        "flavor": ("set in their ways", "open to some new things", "always chasing something new"),
    },
    "conscientiousness": {
        "label": "Conscientiousness", "abbr": "CON", "color": (180, 220, 140), "category": "trait",
        "flavor": ("flies by the seat of their pants", "reasonably organized", "meticulously on top of everything"),
    },
    "security": {
        "label": "Security", "abbr": "SEC", "color": (200, 170, 255), "category": "trait",
        "flavor": ("easily rattled", "generally steady", "unshakeable"),
    },
    "empathy": {
        "label": "Empathy", "abbr": "EMP", "color": (255, 150, 190), "category": "trait",
        "flavor": ("not exactly attuned to others", "reads the room fine", "deeply tuned in to everyone around them"),
    },
    "happiness": {
        "label": "Happiness", "abbr": "HAP", "color": (255, 210, 120), "category": "status",
        "flavor": ("having a rough time lately", "doing okay", "genuinely thriving"),
    },
    "fulfillment": {
        "label": "Fulfillment", "abbr": "FUL", "color": (140, 200, 200), "category": "status",
        "flavor": ("feeling pretty unfulfilled", "getting some of what they need", "deeply fulfilled right now"),
    },
    "energy": {
        "label": "Energy", "abbr": "NRG", "color": (150, 220, 255), "category": "status",
        "flavor": ("running on empty", "holding steady", "full of energy"),
    },
    "stress": {
        "label": "Stress", "abbr": "STR", "color": (220, 120, 120), "category": "status",
        "flavor": ("totally relaxed", "a little tense", "stretched thin"),
    },
    "desire": {
        "label": "Desire", "abbr": "DES", "color": (230, 140, 220), "category": "status",
        "flavor": ("not feeling it lately", "simmering", "burning for it"),
    },
}
STAT_ORDER = TRAITS + STATUSES
STAT_COLORS = [STAT_INFO[k]["color"] for k in STAT_ORDER]

# Relational stats live per-pair (member/member or member/prospect), not on
# a single Character, but share the same color/label idiom as STAT_INFO.
RELATIONAL_INFO = {
    "trust": {"label": "Trust", "color": (140, 180, 240)},
    "spark": {"label": "Spark", "color": (240, 140, 190)},
    "interest": {"label": "Interest", "color": (255, 150, 190)},
}


def stat_flavor(key, value):
    """Threshold-based prose fragment for a stat value, for dossier-level text."""
    low, mid, high = STAT_INFO[key]["flavor"]
    if value < 34:
        return low
    if value < 67:
        return mid
    return high


COMMIT_THRESHOLD = 70
MAX_PROSPECTS_PER_MEMBER = 3
DRAW_MAX = 3
MAX_HAND = 5
TURN_STEPS = ["Draw", "Discard", "Play"]
WEEKS_PER_QUARTER = 12
ENERGY_COST = 15
START_MEMBERS = 2
START_OTHERS = 4
EXIT_BREAKUP_TIER = 2

# Static fill-ins used to preview a card's blurb before it has a real target
# (drawn-card and discard previews render every frame, so this must stay
# rng-free rather than reusing self.rng like `_flavor` does).
PREVIEW_PLACEHOLDERS = {"target": "someone", "hobby": "a hobby", "project": "a project", "venue": "a spot"}

# Quick visual kind-coding shared by the drawn-card and discard previews.
# Keyed by the label _card_label() returns: Dates scopes, Choice sub-kinds,
# the "events" class, and the "end" sentinel.
KIND_COLORS = {
    "solo": (150, 220, 255),
    "pair": (140, 180, 240),
    "group": (180, 230, 120),
    "community": (120, 220, 180),
    "events": (255, 210, 110),
    "commit": (200, 160, 255),
    "breakup": (255, 90, 90),
    "ask_to_change": (255, 180, 120),
    "share": (255, 150, 190),
    "message": (230, 120, 120),
    "end": (180, 180, 180),
}

# Every action card resolves against this ladder: one outcome tier is rolled
# per play, and the same tier drives every stat delta the card defines, so a
# single roll reads as one coherent outcome instead of independent stats.
OUTCOME_TIERS = [
    "Total disaster.",
    "That really did not land.",
    "Rough going. It shows.",
    "A little awkward, honestly.",
    "Mixed bag, more miss than hit.",
    "Mixed bag, more hit than miss.",
    "That lands better than expected.",
    "Genuinely good moment.",
    "One for the highlight reel.",
    "About as good as it gets.",
]

GENERIC_CARDS = card_loader.load_generic_cards()
ARCHETYPE_CARDS = card_loader.load_archetype_cards()

END_WEEK = {"id": "end_week", "name": "End Week", "blurb": "Wrap up and pass it on."}


class Character:
    def __init__(self, rng, name=None, archetype=None):
        self.name = name or rng.choice(FIRST_NAMES)
        self.archetype = archetype or rng.choice(ARCHETYPES)
        self.kinks = rng.sample(KINK_POOL, 2)
        self.seed = rng.randint(0, 1 << 30)
        self.traits = {t: rng.randint(20, 90) for t in TRAITS}
        self.statuses = {s: rng.randint(40, 80) for s in STATUSES}
        self.preferred_activity = rng.choice(ACTIVITIES)
        self.hand = []

    def stat_value(self, key):
        return self.traits[key] if key in self.traits else self.statuses[key]

    def stat_values(self, order=STAT_ORDER):
        return [self.stat_value(k) for k in order]

    def deck(self):
        deck = list(GENERIC_CARDS)
        extra = ARCHETYPE_CARDS.get(self.archetype)
        if extra:
            deck = deck + list(extra)
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

        names = self.rng.sample(FIRST_NAMES, START_MEMBERS + START_OTHERS)
        self.members = [Character(self.rng, name=n) for n in names[:START_MEMBERS]]
        self.relationships = {}
        for i in range(len(self.members)):
            for j in range(i + 1, len(self.members)):
                a, b = self.members[i], self.members[j]
                self.relationships[self._rel_key(a.name, b.name)] = {
                    "trust": self.rng.randint(35, 90), "spark": self.rng.randint(35, 90),
                }

        self.prospects = {}
        for n in names[START_MEMBERS:]:
            c = Character(self.rng, name=n)
            met_by = self.rng.choice(self.members).name
            self.prospects[c.name] = {"char": c, "interest": self.rng.randint(20, 60), "met_by": met_by}

        self.harmony = self.rng.randint(50, 80)
        self.chaos = self.rng.randint(10, 40)
        self.calendar = {}
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

        self._start_turn(self.active)

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
            cls = card["class"]
            if cls == "dates" and card.get("scope") == "pair":
                ts = card.get("target_scope", "members")
                if ts == "members_and_prospects":
                    if not others and not my_prospects:
                        continue
                elif not others:
                    continue
            elif cls == "choice":
                ts = card.get("target_scope", "members")
                pool_prospects = eligible_prospects if card.get("kind") == "commit" else my_prospects
                if ts == "members_and_prospects":
                    if not others and not pool_prospects:
                        continue
                elif ts == "prospects":
                    if not pool_prospects:
                        continue
                elif not others:
                    continue
            elif cls == "events" and card.get("spawns_prospect"):
                if len(my_prospects) >= MAX_PROSPECTS_PER_MEMBER:
                    continue
            pool.append(card)
        return pool

    def _start_turn(self, member):
        # Always draw up to DRAW_MAX regardless of current hand size - the
        # mandatory discard step right after draw brings the hand back down
        # to MAX_HAND before play, so there's no need to cap the draw itself.
        pool = self._eligible_cards(member)
        available = [c for c in pool if not any(c is h for h in member.hand)]
        n = max(0, min(DRAW_MAX, len(available)))
        drawn = self.rng.sample(available, n) if n else []
        member.hand.extend(drawn)
        self.hand = member.hand
        self.drawn_cards = drawn
        self.hand_index = 0
        self.state = "draw"

    def _card_targets(self, card):
        member = self.active
        my_prospects = self._member_prospects(member.name)
        others = [m.name for m in self.members if m.name != member.name]
        cls = card["class"]
        if cls == "dates":
            if card.get("scope") != "pair":
                return []
            if card.get("target_scope") == "members_and_prospects":
                return others + list(my_prospects.keys())
            return others
        if cls == "choice":
            ts = card.get("target_scope", "members")
            prospect_pool = my_prospects
            if card.get("kind") == "commit":
                prospect_pool = {n: p for n, p in my_prospects.items() if p["interest"] >= COMMIT_THRESHOLD}
            if ts == "members_and_prospects":
                return others + list(prospect_pool.keys())
            if ts == "prospects":
                return list(prospect_pool.keys())
            return others
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

    def _roll_tier(self):
        return self.rng.randrange(len(OUTCOME_TIERS))

    def _tier_value(self, lo, hi, tier):
        frac = tier / (len(OUTCOME_TIERS) - 1)
        return round(lo + frac * (hi - lo))

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

    def _preview_blurb(self, card):
        """Rng-free blurb rendering for cards that don't have a real target yet,
        safe to call every frame (draw/discard previews)."""
        return card["blurb"].format(**PREVIEW_PLACEHOLDERS)

    @staticmethod
    def _card_face(card):
        """(display name, display blurb) - Events are random things that happen
        to you, so they stay a mystery in hand/draw/discard previews and only
        reveal their real name and blurb once actually played."""
        if card["class"] == "events":
            return "???", "Something's about to happen."
        return card["name"], None

    def _spend_energy(self):
        active = self.active
        active.statuses["energy"] = max(0, active.statuses["energy"] - ENERGY_COST)

    @staticmethod
    def _card_label(card):
        if card is END_WEEK:
            return "end"
        if card["class"] == "dates":
            return card.get("scope", "dates")
        if card["class"] == "choice":
            return card.get("kind", "choice")
        return card["class"]

    def _apply_stats(self, card, tier, target_name, skip_relational=False):
        """Applies every stat in card['stats'], tier-scaled, routing each key
        by name: trust/spark to the active-target relationship, interest to a
        prospect, harmony/chaos to the cule, everything else (happiness,
        fulfillment, energy, stress, desire) to the active member's own
        statuses. Returns a list of description lines."""
        member = self.active
        notes = []
        for key, (lo, hi) in card.get("stats", {}).items():
            delta = self._tier_value(lo, hi, tier)
            if key in ("trust", "spark"):
                if skip_relational or target_name is None:
                    continue
                rel = self.get_rel(member.name, target_name)
                rel[key] = max(0, min(100, rel[key] + delta))
                notes.append(f"{key.capitalize()} {delta:+d}")
            elif key == "interest":
                if skip_relational or target_name is None:
                    continue
                prospect = self.prospects.get(target_name)
                if prospect is None:
                    continue
                prospect["interest"] = max(0, min(100, prospect["interest"] + delta))
                notes.append(f"Interest {delta:+d}")
                if prospect["interest"] <= 0:
                    del self.prospects[target_name]
                    notes.append(f"{target_name} stops responding entirely")
            elif key in ("harmony", "chaos"):
                setattr(self, key, max(0, min(100, getattr(self, key) + delta)))
                notes.append(f"{key.capitalize()} {delta:+d}")
            else:
                member.statuses[key] = max(0, min(100, member.statuses[key] + delta))
                notes.append(f"{STAT_INFO[key]['label']} {delta:+d}")
        return [", ".join(notes) + "."] if notes else []

    def _spawn_prospect(self, member):
        venue = self.rng.choice(VENUES)
        name = self._unique_name()
        stranger = Character(self.rng, name=name)
        interest = self._roll(10, 30)
        self.prospects[stranger.name] = {"char": stranger, "interest": interest, "met_by": member.name}
        return [f"{member.name} meets {stranger.name} at {venue}.",
                f"({stranger.archetype}, +{interest} interest)"]

    def _resolve(self, card, target_name):
        member = self.active
        flavor = self._flavor(card, target_name)
        cls = card["class"]
        lines = [flavor]
        self.result_tier = None

        if cls == "events":
            tier = self._roll_tier()
            self.result_tier = tier
            lines.append(OUTCOME_TIERS[tier])
            lines.extend(self._apply_stats(card, tier, None))
            if card.get("spawns_prospect"):
                lines.extend(self._spawn_prospect(member))
            self.result_text = lines

        elif cls == "dates":
            tier = self._roll_tier()
            self.result_tier = tier
            lines.append(OUTCOME_TIERS[tier])
            lines.extend(self._apply_stats(card, tier, target_name))
            self.result_text = lines

        elif cls == "choice":
            kind = card.get("kind")
            is_prospect = target_name in self.prospects
            tier = self._roll_tier()
            self.result_tier = tier
            if kind == "commit" and is_prospect:
                prospect = self.prospects.pop(target_name)
                trust_lo_hi = card.get("stats", {}).get("trust", (10, 10))
                spark_lo_hi = card.get("stats", {}).get("spark", (10, 10))
                trust_d = self._tier_value(*trust_lo_hi, tier)
                spark_d = self._tier_value(*spark_lo_hi, tier)
                new_member = prospect["char"]
                self.members.append(new_member)
                self.get_rel(member.name, new_member.name).update({
                    "trust": max(0, min(100, prospect["interest"] + trust_d)),
                    "spark": max(0, min(100, prospect["interest"] + spark_d)),
                })
                if "desire" in card.get("stats", {}):
                    d = self._tier_value(*card["stats"]["desire"], tier)
                    member.statuses["desire"] = max(0, min(100, member.statuses["desire"] + d))
                lines.append(f"{new_member.name} joins the cule for real!")
                self.result_text = lines
            elif kind == "breakup":
                guaranteed = card.get("guaranteed_exit", False)
                if is_prospect:
                    self.prospects.pop(target_name)
                    lines += [OUTCOME_TIERS[tier], f"{target_name} is out of the picture."]
                    lines.extend(self._apply_stats(card, tier, None, skip_relational=True))
                elif guaranteed or tier <= EXIT_BREAKUP_TIER:
                    self.members = [m for m in self.members if m.name != target_name]
                    self.relationships = {k: v for k, v in self.relationships.items() if target_name not in k}
                    lines += [OUTCOME_TIERS[tier], f"{target_name} moves out for good."]
                    lines.extend(self._apply_stats(card, tier, None, skip_relational=True))
                else:
                    lines.append(OUTCOME_TIERS[tier])
                    lines.extend(self._apply_stats(card, tier, target_name))
                self.result_text = lines
            else:
                # ask_to_change, share, message, or a commit card whose
                # target is already a member (deepening, not converting).
                lines.append(OUTCOME_TIERS[tier])
                lines.extend(self._apply_stats(card, tier, target_name))
                self.result_text = lines

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
        self.result_tier = None
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
            self.result_tier = None
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

    def _finish_turn(self):
        self.week += 1
        events = self.calendar.pop(self.week, [])
        if events:
            lines = []
            for ev in events:
                lines.extend(self._resolve_scheduled_event(ev))
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
                if self.pending_card.get("schedulable"):
                    self._start_date_flow(target)
                else:
                    self._resolve(self.pending_card, target)
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
        w, h = self.screen.get_size()
        scale = ui.scale_factor(self.screen)
        panel_w = int(w * 0.42)
        panel = pygame.Rect(int(16 * scale), int(16 * scale), panel_w, h - int(32 * scale))
        header_h = int(110 * scale)
        diagram = pygame.Rect(panel.left + int(10 * scale), panel.top + header_h,
                               panel.width - int(20 * scale), panel.height - header_h - int(10 * scale))
        center = diagram.center
        max_r = min(diagram.width, diagram.height) / 2 - int(34 * scale)
        min_r = int(45 * scale)
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
        _, diagram, center, min_r, max_r, scale = self._network_geometry()
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
        node_diameter = 2 * int(19 * scale)
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

        ring_margin = int(19 * scale) + int(22 * scale)  # node radius + label line
        for name, pos in ring_positions.items():
            ring_positions[name] = self._clamp_to_rect(pos, diagram, ring_margin)

        target_positions = {active.name: center, **ring_positions}
        for name, target in target_positions.items():
            cur = self.node_pos.get(name, target)
            self.node_pos[name] = (cur[0] + (target[0] - cur[0]) * rate, cur[1] + (target[1] - cur[1]) * rate)

        prospect_margin = int(12 * scale) + int(18 * scale)
        for pname, prospect in self.prospects.items():
            anchor = self.node_pos.get(prospect["met_by"], center)
            siblings = [n for n, p in self.prospects.items() if p["met_by"] == prospect["met_by"]]
            idx = siblings.index(pname)
            angle = (idx / max(1, len(siblings))) * 2 * math.pi + 0.6
            strength = prospect["interest"] / 100.0
            sat_max, sat_min = 74 * scale, 54 * scale
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

        node_r = int(23 * scale)
        pygame.draw.circle(surface, (255, 220, 120), center, node_r + int(4 * scale))
        pixel_portrait.draw_bust(surface, pygame.Rect(int(center[0] - node_r), int(center[1] - node_r),
                                                        node_r * 2, node_r * 2), active.seed)
        stat_ring_r = node_r + int(4 * scale) + int(6 * scale)
        ui.draw_ring_segments(surface, center, stat_ring_r, active.stat_values(), STAT_COLORS,
                               thickness=max(2, int(4 * scale)))
        name_font = ui.font(20, scale)
        label = name_font.render(active.name, True, ui.TEXT_COLOR)
        surface.blit(label, label.get_rect(midtop=(center[0], center[1] + stat_ring_r + int(6 * scale))))

        node_r2 = int(19 * scale)
        stat_ring_r2 = node_r2 + int(3 * scale) + int(5 * scale)
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
            ui.draw_ring_segments(surface, pos, stat_ring_r2, member.stat_values(), STAT_COLORS,
                                   thickness=max(2, int(3 * scale)))
            label = ring_font.render(member.name, True, ui.TEXT_COLOR)
            surface.blit(label, label.get_rect(midtop=(pos[0], pos[1] + stat_ring_r2 + int(4 * scale))))

        node_r3 = int(12 * scale)
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
            surface.blit(body_font.render(member.archetype, True, ui.DIM_TEXT), (tx, y + line_h))
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
        surface.blit(body_font.render(member.archetype, True, ui.TEXT_COLOR), (rect.left + pad, sub_y))

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
                line = f"{other.name}: Trust {rel['trust']}  Spark {rel['spark']}"
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

        panel, diagram, center, min_r, max_r, _ = self._network_geometry()
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
            blurb_text = display_blurb if display_blurb is not None else self._preview_blurb(card)
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

    def _draw_hand_row(self, surface, main_rect, scale, body_font, small_font):
        cards = list(self.hand)
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
