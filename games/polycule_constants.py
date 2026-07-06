"""Static content and tuning tables for the Polycule Simulator.

Content (name pools, the stat catalogue, stage ladders, colour keys) lives in
games/data/*.json and is loaded below via content_loader, the same JSON-in
pattern card_loader.py already used for cards - so a second game can bring
its own games/data/*.json rather than hand-picking which tables to bother
externalizing. The remaining plain Python constants here are numeric tuning
knobs and small fixed vocabularies (days, activities, schedule offsets) that
aren't really "content" a second game would reuse or a designer would tweak
independently of the code that consumes them.

The model (state + queries), the rules (resolution), and the game
(controller + view) all import from here, so there's one source of truth and
no import cycle between those three layers.
"""

from . import card_loader, content_loader

_names = content_loader.load_json("names.json")
_archetypes = content_loader.load_json("archetypes.json")
_kinks = content_loader.load_json("kinks.json")
_stats = content_loader.load_json("stats.json")
_stages = content_loader.load_json("stages.json")
_card_visuals = content_loader.load_json("card_visuals.json")

FIRST_NAMES = _names["first_names"]

ARCHETYPES = _archetypes["archetypes"]
VENUES = _archetypes["venues"]
HOBBIES = _archetypes["hobbies"]
PROJECTS = _archetypes["projects"]

KINK_POOL = [tuple(k) for k in _kinks["kinks"]]

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ACTIVITIES = ["Park", "Movie", "Jog"]
SCHEDULE_OFFSETS = [("This week", 0), ("Next week", 1), ("In two weeks", 2)]

TRAITS = _stats["traits"]
STATUSES = _stats["statuses"]

# Single source of truth for every character-owned stat (5 traits + 5
# statuses). Every display tier (dossier, roster row, selector tile, ring)
# reads from this table instead of hand-picking which stats it bothers to
# show, so all ten stay visually equal citizens even though only a couple
# are hooked into card resolution today.
STAT_INFO = _stats["stat_info"]
STAT_ORDER = TRAITS + STATUSES
STAT_COLORS = [STAT_INFO[k]["color"] for k in STAT_ORDER]

# Relational stats live per-pair (member/member or member/prospect), not on
# a single Character, but share the same color/label idiom as STAT_INFO.
RELATIONAL_INFO = _stats["relational_info"]


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
LIFE_STAGES = _stages["life_stages"]
LIFE_STAGE_LABELS = _stages["life_stage_labels"]
LIFE_STAGE_WEEKS = _stages["life_stage_weeks"]  # rooted once past "settling"

REL_STAGES = _stages["rel_stages"]
REL_STAGE_LABELS = _stages["rel_stage_labels"]

# Static fill-ins used to preview a card's blurb before it has a real target
# (drawn-card and discard previews render every frame, so this must stay
# rng-free rather than reusing the model rng like `rules.flavor` does).
PREVIEW_PLACEHOLDERS = {"target": "someone", "hobby": "a hobby", "project": "a project", "venue": "a spot"}

# Quick visual kind-coding shared by the drawn-card and discard previews.
# Keyed by the label card_label() returns: Dates scopes, Choice sub-kinds,
# the "events" class, and the "end" sentinel.
KIND_COLORS = _card_visuals["kind_colors"]

# Every action card resolves against this ladder: one outcome tier is rolled
# per play, and the same tier drives every stat delta the card defines, so a
# single roll reads as one coherent outcome instead of independent stats.
OUTCOME_TIERS = _card_visuals["outcome_tiers"]

GENERIC_CARDS = card_loader.load_generic_cards()
ARCHETYPE_CARDS = card_loader.load_archetype_cards()

END_WEEK = {"id": "end_week", "name": "End Week", "blurb": "Wrap up and pass it on."}
