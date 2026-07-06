"""Save/load serialization for a PolyculeModel.

Captures the whole simulated world - members, prospects, relationships,
calendar, harmony/chaos, week, and the rng state - so a saved game resumes
with the same future draws it would have had if never quit (the model's rng
drives every card draw, roll, and negotiation, so restoring it without its
exact state would silently diverge from what the player saw). Mid-turn
controller state (the current hand selection, an open target picker, and so
on) is *not* captured - loading a save always resumes at the top of the
active member's turn, the same as a fresh `reset()`, just with the saved
world instead of a freshly generated one.

Relationships are keyed by a frozenset of the two names, which JSON can't
serialize as a dict key - `_rel_key_str` stringifies it as the two names
joined by "|" in sorted order, so the same pair always round-trips to the
same string regardless of which name was passed first.
"""

import random

from .polycule_constants import ARCHETYPE_CARDS, GENERIC_CARDS
from .polycule_model import Character, PolyculeModel


def _find_card(card_id):
    for card in GENERIC_CARDS:
        if card["id"] == card_id:
            return card
    for cards in ARCHETYPE_CARDS.values():
        for card in cards:
            if card["id"] == card_id:
                return card
    raise KeyError(f"Unknown card id in save data: {card_id!r}")


def _serialize_character(char):
    return {
        "name": char.name,
        "archetype": char.archetype,
        "kinks": [list(k) for k in char.kinks],
        "seed": char.seed,
        "traits": dict(char.traits),
        "statuses": dict(char.statuses),
        "preferred_activity": char.preferred_activity,
        "hand": [c["id"] for c in char.hand],
        "joined_week": char.joined_week,
    }


def _deserialize_character(data):
    char = Character.__new__(Character)
    char.name = data["name"]
    char.archetype = data["archetype"]
    char.kinks = [tuple(k) for k in data["kinks"]]
    char.seed = data["seed"]
    char.traits = dict(data["traits"])
    char.statuses = dict(data["statuses"])
    char.preferred_activity = data["preferred_activity"]
    char.hand = [_find_card(cid) for cid in data["hand"]]
    char.joined_week = data["joined_week"]
    return char


def _rel_key_str(key):
    return "|".join(sorted(key))


def serialize_model(model):
    version, state, gauss_next = model.rng.getstate()
    return {
        "week": model.week,
        "harmony": model.harmony,
        "chaos": model.chaos,
        "members": [_serialize_character(m) for m in model.members],
        "prospects": {
            name: {"char": _serialize_character(p["char"]), "interest": p["interest"], "met_by": p["met_by"]}
            for name, p in model.prospects.items()
        },
        "relationships": {_rel_key_str(key): rel for key, rel in model.relationships.items()},
        "calendar": {str(week): events for week, events in model.calendar.items()},
        "rng_state": [version, list(state), gauss_next],
    }


def deserialize_model(data):
    model = PolyculeModel.__new__(PolyculeModel)
    version, state, gauss_next = data["rng_state"]
    rng = random.Random()
    rng.setstate((version, tuple(state), gauss_next))
    model.rng = rng
    model.week = data["week"]
    model.harmony = data["harmony"]
    model.chaos = data["chaos"]
    model.members = [_deserialize_character(m) for m in data["members"]]
    model.prospects = {
        name: {"char": _deserialize_character(p["char"]), "interest": p["interest"], "met_by": p["met_by"]}
        for name, p in data["prospects"].items()
    }
    model.relationships = {frozenset(key.split("|")): rel for key, rel in data["relationships"].items()}
    model.calendar = {int(week): events for week, events in data["calendar"].items()}
    return model
