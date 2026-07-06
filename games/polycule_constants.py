"""Static content and tuning tables for the Polycule Simulator.

Everything here is data with no behaviour: name pools, the stat catalogue,
stage ladders, outcome text, colour keys, and the numeric knobs. The model
(state + queries), the rules (resolution), and the game (controller + view)
all import from here, so there's one source of truth and no import cycle
between those three layers.
"""

from . import card_loader

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

# Two orthogonal "how far along is this" axes. LIFE_STAGE tracks a member's
# own tenure in the cule/town (independent of any one relationship);
# REL_STAGE tracks a specific pair's history together (independent of how
# long either of them has been around). Both are derived live from weeks
# elapsed + the underlying trust/interest numbers rather than stored
# separately, so there's no extra state to fall out of sync - stages are
# just a human-readable read of stats that already exist.
LIFE_STAGES = ["arriving", "settling", "rooted"]
LIFE_STAGE_LABELS = {
    "arriving": "new to town",
    "settling": "settling in",
    "rooted": "rooted in the scene",
}
LIFE_STAGE_WEEKS = {"arriving": 8, "settling": 24}  # rooted once past "settling"

REL_STAGES = ["new", "building", "established", "anchor"]
REL_STAGE_LABELS = {
    "new": "new",
    "building": "building something",
    "established": "established",
    "anchor": "anchor partners",
}

# Static fill-ins used to preview a card's blurb before it has a real target
# (drawn-card and discard previews render every frame, so this must stay
# rng-free rather than reusing the model rng like `rules.flavor` does).
PREVIEW_PLACEHOLDERS = {"target": "someone", "hobby": "a hobby", "project": "a project", "venue": "a spot"}

# Quick visual kind-coding shared by the drawn-card and discard previews.
# Keyed by the label card_label() returns: Dates scopes, Choice sub-kinds,
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
