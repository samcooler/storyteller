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
HAND_CAP = 7
DISCARD_TO = 4
WEEKS_PER_QUARTER = 12
ENERGY_COST = 15
START_MEMBERS = 3
START_OTHERS = 4
EXIT_BREAKUP_TIER = 2

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
    {"id": "trash_tv", "name": "Watch Trash TV", "kind": "bond",
     "blurb": "Marathon something truly terrible with {target}.", "trust": (0, 10), "spark": (-2, 8)},
    {"id": "chore_wheel_intervention", "name": "Chore Wheel Intervention", "kind": "bond",
     "blurb": "Stage a formal intervention about the chore wheel with {target}.", "trust": (-8, 14), "spark": (-6, 2)},
    {"id": "metamour_appreciation", "name": "Metamour Appreciation", "kind": "bond",
     "blurb": "Tell {target} they're an incredible metamour, unprompted.", "trust": (4, 16), "spark": (-2, 6)},
    {"id": "group_chat_add", "name": "Add to the Group Chat", "kind": "bond",
     "blurb": "Add {target} to the group chat named something unhinged.", "trust": (2, 10), "spark": (0, 6)},

    {"id": "flirt", "name": "Flirt", "kind": "court",
     "blurb": "Turn up the charm on {target}.", "interest": (5, 25)},
    {"id": "vulnerable_share", "name": "Vulnerable Share", "kind": "court",
     "blurb": "Open up to {target} about something real.", "interest": (-5, 30)},
    {"id": "go_quiet", "name": "Go Quiet", "kind": "court",
     "blurb": "Don't text {target} back for a few days.", "interest": (-25, 5)},
    {"id": "ask_out", "name": "Ask Them Out", "kind": "court",
     "blurb": "Suggest an actual date with {target}.", "interest": (0, 30)},
    {"id": "voice_memo", "name": "Send a Voice Memo", "kind": "court",
     "blurb": "Send {target} an unnecessarily long voice memo.", "interest": (-10, 25)},
    {"id": "overanalyze_texts", "name": "Overanalyze Their Texts", "kind": "court",
     "blurb": "Spend an hour overanalyzing {target}'s last text.", "interest": (-15, 15)},
    {"id": "meet_the_metamours", "name": "Meet the Metamours", "kind": "court",
     "blurb": "Invite {target} to meet the rest of the polycule.", "interest": (-10, 30)},

    {"id": "overshare_early", "name": "Overshare Early", "kind": "flag",
     "blurb": "Trauma dump on {target} way earlier than you probably should.", "interest": (-25, 20)},
    {"id": "ask_about_the_ex", "name": "Ask About The Ex", "kind": "flag",
     "blurb": "Ask {target} point-blank about their living situation with their ex.", "interest": (-20, 18)},
    {"id": "pitch_your_crypto", "name": "Pitch Your Crypto", "kind": "flag",
     "blurb": "Pitch {target} on your new relationship coin.", "interest": (-28, 10)},
    {"id": "declare_different", "name": "Declare You're Different", "kind": "flag",
     "blurb": "Tell {target} you're not like other people.", "interest": (-22, 16)},
    {"id": "bring_up_money", "name": "Bring Up Money", "kind": "flag",
     "blurb": "Casually bring up how you actually make ends meet.", "interest": (-20, 18)},
    {"id": "read_consent_form_aloud", "name": "Read The Consent Form Aloud", "kind": "flag",
     "blurb": "Actually read the whole consent form out loud before signing anything with {target}.", "interest": (8, 24)},
    {"id": "bring_their_order", "name": "Bring Their Coffee Order", "kind": "flag",
     "blurb": "Show up with {target}'s coffee order, unasked.", "interest": (6, 22)},
    {"id": "mention_your_therapist", "name": "Bring Up Your Therapist", "kind": "flag",
     "blurb": "Mention your therapist to {target}, completely normally.", "interest": (8, 24)},
    {"id": "check_in_on_them", "name": "Check In After Their Hard Day", "kind": "flag",
     "blurb": "Text {target} just to check in after a rough day.", "interest": (6, 20)},
    {"id": "insist_on_splitting", "name": "Insist On Splitting The Bill", "kind": "flag",
     "blurb": "Split the bill before {target} can reach for their wallet.", "interest": (5, 18)},

    {"id": "go_out", "name": "Go Out", "kind": "meet",
     "blurb": "Head out to {venue} and see who's around."},
    {"id": "dating_app", "name": "Match Online", "kind": "meet",
     "blurb": "Swipe through dating apps hoping for a connection."},

    {"id": "house_meeting", "name": "House Meeting", "kind": "group",
     "blurb": "Call a meeting to hash things out.", "harmony": (-10, 20), "chaos": (-15, 10)},
    {"id": "group_dinner", "name": "Group Dinner", "kind": "group",
     "blurb": "Cook a big dinner for everyone.", "harmony": (0, 15), "chaos": (-5, 5)},
    {"id": "calendar_sync", "name": "Calendar Sync", "kind": "group",
     "blurb": "Try to sync everyone's calendars.", "harmony": (-5, 10), "chaos": (-20, 5)},
    {"id": "group_trip", "name": "Plan a Group Trip", "kind": "group",
     "blurb": "Propose a trip for the whole cule.", "harmony": (-8, 18), "chaos": (0, 10)},

    {"id": "blame_mercury", "name": "Blame Mercury Retrograde", "kind": "chaos",
     "blurb": "Announce to the house that Mercury is in retrograde and everyone should lower their expectations this week.",
     "harmony": (-15, 8), "chaos": (8, 28), "stress": (2, 15)},
    {"id": "invite_your_ex", "name": "Invite Your Ex To Brunch", "kind": "chaos",
     "blurb": "Invite your ex to Sunday brunch. On purpose. To 'test the waters.'",
     "harmony": (-20, 5), "chaos": (12, 28), "stress": (5, 20)},
    {"id": "screenshot_the_chat", "name": "Screenshot The Group Chat", "kind": "chaos",
     "blurb": "Screenshot the group chat 'just to keep receipts.'",
     "harmony": (-22, 0), "chaos": (12, 32), "stress": (8, 22)},
    {"id": "ignore_the_water_heater", "name": "Ignore The Water Heater", "kind": "chaos",
     "blurb": "Notice the water heater is making a noise and decide it's Not Your Problem this week.",
     "harmony": (-12, 10), "chaos": (5, 18), "stress": (2, 12)},
    {"id": "surprise_metamour", "name": "Bring Someone New To Game Night", "kind": "chaos",
     "blurb": "Bring a new partner to game night without a heads up.",
     "harmony": (-18, 8), "chaos": (8, 25), "stress": (2, 16)},
    {"id": "full_moon", "name": "Lean Into Full Moon Energy", "kind": "chaos",
     "blurb": "Announce it's a full moon and use that as license to be unhinged all week.",
     "harmony": (-10, 15), "chaos": (10, 25)},

    {"id": "have_the_talk", "name": "Have The Talk", "kind": "exit", "target_scope": "members",
     "blurb": "Sit {target} down and have The Talk about where this is really going.",
     "trust": (-30, 25), "spark": (-20, 18)},
    {"id": "cut_it_off", "name": "Cut It Off", "kind": "exit", "target_scope": "members_and_prospects",
     "guaranteed_exit": True,
     "blurb": "Tell {target} plainly that this isn't going anywhere.",
     "trust": (-40, 10), "spark": (-30, 5)},
]

ARCHETYPE_CARDS = {
    "astrology-pilled barista": [
        {"id": "chart_reading", "name": "Read Their Chart", "kind": "bond",
         "blurb": "Insist on doing {target}'s birth chart.", "trust": (-4, 10), "spark": (2, 10)},
        {"id": "mercury_blame", "name": "Blame Mercury", "kind": "bond",
         "blurb": "Explain to {target} that the fight was actually Mercury's fault.", "trust": (-2, 12), "spark": (-4, 6)},
    ],
    "crypto bro who found ethical non-monogamy on a podcast": [
        {"id": "pitch_coin", "name": "Pitch a Coin", "kind": "bond",
         "blurb": "Explain your new relationship token to {target}.", "trust": (-14, 4), "spark": (-2, 8)},
        {"id": "podcast_quote", "name": "Quote the Podcast", "kind": "bond",
         "blurb": "Quote the ethical non-monogamy podcast at {target}, again.", "trust": (-10, 6), "spark": (-2, 6)},
    ],
    "theater kid who never left the theater": [
        {"id": "monologue", "name": "Perform a Monologue", "kind": "bond",
         "blurb": "Perform a dramatic monologue at {target}.", "trust": (-4, 8), "spark": (0, 14)},
        {"id": "blocking_notes", "name": "Give Blocking Notes", "kind": "bond",
         "blurb": "Give {target} unsolicited blocking notes during a normal conversation.", "trust": (-8, 6), "spark": (-2, 10)},
    ],
    "crunchy homesteader with three chickens named after exes": [
        {"id": "name_chicken", "name": "Name a Chicken", "kind": "bond",
         "blurb": "Name a new chicken after {target}.", "trust": (2, 12), "spark": (-2, 6)},
        {"id": "raw_honey_gift", "name": "Gift Raw Honey", "kind": "bond",
         "blurb": "Gift {target} a jar of suspiciously unlabeled raw honey.", "trust": (0, 14), "spark": (-2, 4)},
    ],
    "spreadsheet person who tracks feelings in a pivot table": [
        {"id": "pivot_table", "name": "Share the Pivot Table", "kind": "bond",
         "blurb": "Show {target} the feelings spreadsheet.", "trust": (-6, 14), "spark": (-4, 4)},
        {"id": "conditional_formatting", "name": "Add Conditional Formatting", "kind": "bond",
         "blurb": "Color-code {target}'s row in the feelings spreadsheet red.", "trust": (-10, 6), "spark": (-4, 4)},
    ],
    "yoga instructor who over-shares in savasana": [
        {"id": "savasana", "name": "Guided Savasana", "kind": "bond",
         "blurb": "Lead {target} through an over-sharing savasana.", "trust": (0, 12), "spark": (-2, 8)},
        {"id": "chakra_read", "name": "Read Their Chakras", "kind": "bond",
         "blurb": "Tell {target} their heart chakra seems blocked.", "trust": (-6, 10), "spark": (-2, 6)},
    ],
    "DM who's still mad you missed session 4": [
        {"id": "campaign_arc", "name": "Write Them Into the Campaign", "kind": "bond",
         "blurb": "Write {target} into the D&D campaign.", "trust": (-2, 10), "spark": (0, 10)},
        {"id": "session_4_callback", "name": "Bring Up Session 4 Again", "kind": "bond",
         "blurb": "Bring up how {target} missed session 4. Still not over it.", "trust": (-10, 4), "spark": (-4, 4)},
    ],
    "vegan chef with strong opinions about cheese": [
        {"id": "cashew_cheese", "name": "Serve Cashew Cheese", "kind": "bond",
         "blurb": "Make {target} try the cashew cheese.", "trust": (-6, 8), "spark": (0, 10)},
        {"id": "dairy_lecture", "name": "Deliver the Dairy Lecture", "kind": "bond",
         "blurb": "Deliver the full lecture on dairy to {target}, unprompted.", "trust": (-12, 2), "spark": (-4, 4)},
    ],
    "rock climber who talks about 'sending' too much": [
        {"id": "send_it", "name": "Take Them Climbing", "kind": "bond",
         "blurb": "Take {target} climbing and narrate the whole time.", "trust": (-4, 10), "spark": (2, 12)},
        {"id": "beta_unsolicited", "name": "Give Unsolicited Beta", "kind": "bond",
         "blurb": "Give {target} unsolicited beta on an entirely unrelated life problem.", "trust": (-8, 6), "spark": (-2, 8)},
    ],
    "furry with a very normal day job": [
        {"id": "fursona", "name": "Introduce the Fursona", "kind": "bond",
         "blurb": "Introduce {target} to your fursona.", "trust": (-8, 12), "spark": (0, 12)},
        {"id": "con_photos", "name": "Show Con Photos", "kind": "bond",
         "blurb": "Show {target} photos from the last con at work, on the work laptop.", "trust": (-6, 10), "spark": (-2, 8)},
    ],
    "raw milk enthusiast with a lot of opinions": [
        {"id": "raw_milk_pitch", "name": "Explain Raw Milk", "kind": "bond",
         "blurb": "Explain to {target}, at length, why raw milk changed your life.", "trust": (-10, 6), "spark": (-2, 6)},
        {"id": "farmer_intro", "name": "Introduce Them to Your Farmer", "kind": "bond",
         "blurb": "Introduce {target} to 'your' farmer like it's a serious relationship.", "trust": (-4, 10), "spark": (0, 8)},
    ],
    "person who met their metamour on a raid night": [
        {"id": "raid_night_invite", "name": "Invite to Raid Night", "kind": "bond",
         "blurb": "Invite {target} to raid night to meet everyone properly.", "trust": (0, 12), "spark": (0, 10)},
        {"id": "loot_drama", "name": "Relitigate Loot Drama", "kind": "bond",
         "blurb": "Relitigate old guild loot drama with {target} for no reason.", "trust": (-8, 8), "spark": (-4, 6)},
    ],
    "tarot reader who overcharges everyone including their partners": [
        {"id": "pull_a_card", "name": "Pull a Card on Them", "kind": "bond",
         "blurb": "Pull a tarot card on {target} mid-argument.", "trust": (-6, 10), "spark": (-2, 8)},
        {"id": "invoice_partner", "name": "Send an Invoice", "kind": "bond",
         "blurb": "Actually send {target} an invoice for the reading.", "trust": (-14, 2), "spark": (-4, 4)},
    ],
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
            if card["kind"] in ("bond", "date") and not others and not my_prospects:
                continue
            if card["kind"] in ("court", "flag") and not my_prospects:
                continue
            if card["kind"] == "meet" and len(my_prospects) >= MAX_PROSPECTS_PER_MEMBER:
                continue
            if card["kind"] == "exit":
                if card.get("target_scope") == "members_and_prospects":
                    if not others and not my_prospects:
                        continue
                elif not others:
                    continue
            pool.append(card)
        if eligible_prospects:
            pool.append(COMMIT_CARD)
        return pool

    def _start_turn(self, member):
        pool = self._eligible_cards(member)
        available = [c for c in pool if not any(c is h for h in member.hand)]
        room = HAND_CAP - len(member.hand)
        n = max(0, min(DRAW_MAX, room, len(available)))
        drawn = self.rng.sample(available, n) if n else []
        member.hand.extend(drawn)
        self.hand = member.hand
        self.drawn_cards = drawn
        self.hand_index = 0
        self.state = "draw"

    def _card_targets(self, card):
        member = self.active
        my_prospects = self._member_prospects(member.name)
        if card["kind"] == "bond":
            return [m.name for m in self.members if m.name != member.name]
        if card["kind"] == "date":
            return [m.name for m in self.members if m.name != member.name] + list(my_prospects.keys())
        if card["kind"] == "exit":
            if card.get("target_scope") == "members_and_prospects":
                return [m.name for m in self.members if m.name != member.name] + list(my_prospects.keys())
            return [m.name for m in self.members if m.name != member.name]
        if card["kind"] in ("court", "flag"):
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

    def _spend_energy(self):
        active = self.active
        active.statuses["energy"] = max(0, active.statuses["energy"] - ENERGY_COST)

    def _resolve(self, card, target_name):
        member = self.active
        flavor = self._flavor(card, target_name)
        if card["kind"] == "bond":
            rel = self.get_rel(member.name, target_name)
            tier = self._roll_tier()
            trust_d = self._tier_value(*card["trust"], tier)
            spark_d = self._tier_value(*card["spark"], tier)
            rel["trust"] = max(0, min(100, rel["trust"] + trust_d))
            rel["spark"] = max(0, min(100, rel["spark"] + spark_d))
            self.result_text = [flavor, OUTCOME_TIERS[tier], f"Trust {trust_d:+d}, Spark {spark_d:+d}."]
        elif card["kind"] in ("court", "flag"):
            prospect = self.prospects[target_name]
            tier = self._roll_tier()
            delta = self._tier_value(*card["interest"], tier)
            prospect["interest"] = max(0, min(100, prospect["interest"] + delta))
            self.result_text = [flavor, OUTCOME_TIERS[tier], f"({delta:+d} interest)"]
            if prospect["interest"] <= 0:
                del self.prospects[target_name]
                self.result_text.append(f"{target_name} stops responding entirely.")
        elif card["kind"] == "exit":
            tier = self._roll_tier()
            is_prospect = target_name in self.prospects
            guaranteed = card.get("guaranteed_exit", False)
            if is_prospect:
                self.prospects.pop(target_name)
                self.result_text = [flavor, OUTCOME_TIERS[tier], f"{target_name} is out of the picture."]
            elif guaranteed or tier <= EXIT_BREAKUP_TIER:
                self.members = [m for m in self.members if m.name != target_name]
                self.relationships = {k: v for k, v in self.relationships.items() if target_name not in k}
                self.result_text = [flavor, OUTCOME_TIERS[tier], f"{target_name} moves out for good."]
            else:
                rel = self.get_rel(member.name, target_name)
                trust_d = self._tier_value(*card["trust"], tier)
                spark_d = self._tier_value(*card["spark"], tier)
                rel["trust"] = max(0, min(100, rel["trust"] + trust_d))
                rel["spark"] = max(0, min(100, rel["spark"] + spark_d))
                self.result_text = [flavor, OUTCOME_TIERS[tier], f"Trust {trust_d:+d}, Spark {spark_d:+d}."]
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
        elif card["kind"] in ("group", "chaos"):
            tier = self._roll_tier()
            h_d = self._tier_value(*card["harmony"], tier)
            c_d = self._tier_value(*card["chaos"], tier)
            self.harmony = max(0, min(100, self.harmony + h_d))
            self.chaos = max(0, min(100, self.chaos + c_d))
            lines = [flavor, OUTCOME_TIERS[tier], f"Harmony {h_d:+d}, Chaos {c_d:+d}."]
            if "stress" in card:
                victim = self.rng.choice(self.members)
                s_d = self._tier_value(*card["stress"], tier)
                victim.statuses["stress"] = max(0, min(100, victim.statuses["stress"] + s_d))
                lines.append(f"{victim.name}'s stress {s_d:+d}.")
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

    def _request_end_turn(self):
        if len(self.hand) > DISCARD_TO:
            self.state = "discard"
            self.hand_index = 0
        else:
            self._finish_turn()

    def _finish_turn(self):
        self.week += 1
        events = self.calendar.pop(self.week, [])
        if events:
            lines = []
            for ev in events:
                lines.extend(self._resolve_scheduled_event(ev))
            self.result_text = lines
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
                if len(self.hand) <= DISCARD_TO:
                    self._finish_turn()
        elif self.state == "hand":
            options = self.hand + [END_WEEK]
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.hand_index = (self.hand_index - 1) % len(options)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.hand_index = (self.hand_index + 1) % len(options)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                card = options[self.hand_index]
                if card["kind"] == "end":
                    self._request_end_turn()
                elif card["kind"] in ("bond", "court", "commit", "date", "flag", "exit"):
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
        min_sep = node_diameter * 1.8  # room for the name label under each portrait
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
            sat_max, sat_min = 52 * scale, 36 * scale
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
        label = name_font.render(f"{active.name} (active)", True, ui.TEXT_COLOR)
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

        main_rect = pygame.Rect(panel.right + int(16 * scale), int(16 * scale),
                                 w - panel.width - int(48 * scale), h - int(32 * scale))
        ui.draw_panel(surface, main_rect, scale, corner_style="diamond")

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
        elif self.state == "draw":
            if self.drawn_cards:
                names = ", ".join(c["name"] for c in self.drawn_cards)
                msg = f"{self.active.name} draws: {names}."
            elif len(self.active.hand) >= HAND_CAP:
                msg = f"{self.active.name}'s hand is full ({HAND_CAP} cards) - nothing new to draw."
            else:
                msg = f"{self.active.name} has no new cards to draw right now."
            ui.blit_wrapped(surface, body_font, msg, ui.TEXT_COLOR,
                             content_rect.left + content_rect.width // 2, content_rect.top, content_rect.width)
            hint = small_font.render("Enter to continue", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, content_rect.top + int(60 * scale)))
        elif self.state == "discard":
            msg = f"Hand over the limit - discard down to {DISCARD_TO}. ({len(self.hand)}/{DISCARD_TO})"
            ui.blit_wrapped(surface, body_font, msg, ui.TEXT_COLOR,
                             content_rect.left + content_rect.width // 2, content_rect.top, content_rect.width)
            hint = small_font.render("Enter to discard the selected card", True, ui.DIM_TEXT)
            surface.blit(hint, (content_rect.left, content_rect.top + int(40 * scale)))
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
        options = list(self.hand) if self.state == "discard" else self.hand + [END_WEEK]
        if not options:
            return
        gap = int(14 * scale)
        available = main_rect.width - int(40 * scale) - gap * (len(options) - 1)
        card_w = min(int(150 * scale), available // len(options))
        card_h = card_w + int(25 * scale)
        total_w = len(options) * card_w + (len(options) - 1) * gap
        start_x = main_rect.centerx - total_w // 2
        y = main_rect.bottom - card_h - int(20 * scale)

        for i, card in enumerate(options):
            rect = pygame.Rect(start_x + i * (card_w + gap), y, card_w, card_h)
            selected = self.state in ("hand", "discard") and i == self.hand_index
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
