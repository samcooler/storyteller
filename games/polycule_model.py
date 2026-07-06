"""Domain state for the Polycule Simulator.

`PolyculeModel` owns the whole simulated world - members, prospects, the
per-pair relationship dicts, the calendar, and the cule-wide harmony/chaos -
plus the *pure queries* over it (whose turn is it, what stage is this pair
at, which cards/targets are eligible). It knows nothing about pygame, input,
or drawing; the game's controller holds one of these and the rules operate
on it.

Constructing a PolyculeModel builds a fresh starting world from an injected
`random.Random`, so a new game is just `PolyculeModel(random.Random())`.
"""

from .polycule_constants import (
    ACTIVITIES,
    ARCHETYPES,
    ARCHETYPE_CARDS,
    COMMIT_THRESHOLD,
    FIRST_NAMES,
    GENERIC_CARDS,
    KINK_POOL,
    LIFE_STAGES,
    LIFE_STAGE_WEEKS,
    MAX_PROSPECTS_PER_MEMBER,
    REL_STAGES,
    START_MEMBERS,
    START_OTHERS,
    STATUSES,
    STAT_ORDER,
    TRAITS,
    WEEKS_PER_QUARTER,
)


class Character:
    def __init__(self, rng, name=None, archetype=None, joined_week=1):
        self.name = name or rng.choice(FIRST_NAMES)
        self.archetype = archetype or rng.choice(ARCHETYPES)
        self.kinks = rng.sample(KINK_POOL, 2)
        self.seed = rng.randint(0, 1 << 30)
        self.traits = {t: rng.randint(20, 90) for t in TRAITS}
        self.statuses = {s: rng.randint(40, 80) for s in STATUSES}
        self.preferred_activity = rng.choice(ACTIVITIES)
        self.hand = []
        self.joined_week = joined_week  # week they became a cule member; drives life stage

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


class PolyculeModel:
    def __init__(self, rng):
        self.rng = rng
        self.week = 1

        names = rng.sample(FIRST_NAMES, START_MEMBERS + START_OTHERS)
        self.members = [Character(rng, name=n, joined_week=1) for n in names[:START_MEMBERS]]
        self.relationships = {}
        for i in range(len(self.members)):
            for j in range(i + 1, len(self.members)):
                a, b = self.members[i], self.members[j]
                self.relationships[self.rel_key(a.name, b.name)] = {
                    "trust": rng.randint(35, 90), "spark": rng.randint(35, 90),
                    "formed_week": 1,
                }

        self.prospects = {}
        for n in names[START_MEMBERS:]:
            c = Character(rng, name=n)
            met_by = rng.choice(self.members).name
            self.prospects[c.name] = {"char": c, "interest": rng.randint(20, 60), "met_by": met_by}

        self.harmony = rng.randint(50, 80)
        self.chaos = rng.randint(10, 40)
        self.calendar = {}

    @property
    def active(self):
        return self.members[(self.week - 1) % len(self.members)]

    @property
    def quarter(self):
        return (self.week - 1) // WEEKS_PER_QUARTER + 1

    @property
    def week_in_quarter(self):
        return (self.week - 1) % WEEKS_PER_QUARTER + 1

    def rel_key(self, name_a, name_b):
        return frozenset((name_a, name_b))

    def get_rel(self, name_a, name_b):
        return self.relationships.setdefault(
            self.rel_key(name_a, name_b), {"trust": 50, "spark": 50, "formed_week": self.week})

    def life_stage(self, member):
        """How long this member has been part of the cule/town - orthogonal
        to any specific relationship they're in."""
        weeks = self.week - getattr(member, "joined_week", 1)
        if weeks < LIFE_STAGE_WEEKS["arriving"]:
            return "arriving"
        if weeks < LIFE_STAGE_WEEKS["settling"]:
            return "settling"
        return "rooted"

    def relationship_stage(self, rel):
        """How far along one specific pair's history is. Time-gated but also
        trust-gated, so a relationship that's stalled out or taken a bad hit
        doesn't keep "aging" into a deeper stage just because weeks passed."""
        weeks = self.week - rel.get("formed_week", 1)
        trust = rel.get("trust", 50)
        if weeks < 6 or trust < 35:
            return "new"
        if weeks < 16 or trust < 55:
            return "building"
        if weeks < 32 or trust < 75:
            return "established"
        return "anchor"

    @staticmethod
    def stage_at_least(order, current, minimum):
        return order.index(current) >= order.index(minimum)

    def member_prospects(self, member_name):
        return {n: p for n, p in self.prospects.items() if p["met_by"] == member_name}

    def targets_for_card(self, card, member):
        """Eligible target names for a card, applying scope/target_scope,
        commit-interest gating, and this card's min_rel_stage/min_life_stage
        (if any). Shared by eligible_cards (just needs "is this nonempty?")
        and the controller's card_targets (needs the actual list) so the two
        never drift."""
        min_life = card.get("min_life_stage")
        if min_life and not self.stage_at_least(LIFE_STAGES, self.life_stage(member), min_life):
            return []

        min_rel = card.get("min_rel_stage")

        def filter_rel_stage(names):
            if not min_rel:
                return names
            return [n for n in names
                    if self.stage_at_least(REL_STAGES, self.relationship_stage(self.get_rel(member.name, n)), min_rel)]

        my_prospects = self.member_prospects(member.name)
        others = [m.name for m in self.members if m.name != member.name]
        cls = card["class"]
        if cls == "dates":
            if card.get("scope") != "pair":
                return []
            if card.get("target_scope") == "members_and_prospects":
                return filter_rel_stage(others) + ([] if min_rel else list(my_prospects.keys()))
            return filter_rel_stage(others)
        if cls == "choice":
            ts = card.get("target_scope", "members")
            prospect_pool = my_prospects
            if card.get("kind") == "commit":
                prospect_pool = {n: p for n, p in my_prospects.items() if p["interest"] >= COMMIT_THRESHOLD}
            if ts == "members_and_prospects":
                return filter_rel_stage(others) + ([] if min_rel else list(prospect_pool.keys()))
            if ts == "prospects":
                return list(prospect_pool.keys())
            return filter_rel_stage(others)
        return []

    def eligible_cards(self, member):
        pool = []
        my_prospects = self.member_prospects(member.name)
        for card in member.deck():
            cls = card["class"]
            if cls == "dates" and card.get("scope") == "pair":
                if not self.targets_for_card(card, member):
                    continue
            elif cls == "choice":
                if not self.targets_for_card(card, member):
                    continue
            elif cls == "events" and card.get("spawns_prospect"):
                if len(my_prospects) >= MAX_PROSPECTS_PER_MEMBER:
                    continue
            min_life = card.get("min_life_stage")
            if min_life and not self.stage_at_least(LIFE_STAGES, self.life_stage(member), min_life):
                continue
            pool.append(card)
        return pool
