"""Loads card data for the Polycule Simulator from games/data/cards/*.json.

Every card is a flat dict: id, name, class ("dates"/"events"/"choice"),
blurb, and a "stats" dict of {stat_name: [lo, hi]} tier-scaled ranges.
Dates cards also carry a "scope" (solo/pair/group/community); Choice cards
carry a "kind" sub-type (commit/breakup/ask_to_change/share/message) and a
"target_scope" (members/prospects/members_and_prospects).
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "cards"

REQUIRED_FIELDS = ("id", "name", "class", "blurb")
VALID_CLASSES = ("dates", "events", "choice")


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _validate(card, source):
    for field in REQUIRED_FIELDS:
        if field not in card:
            raise ValueError(f"Card missing '{field}' in {source}: {card}")
    if card["class"] not in VALID_CLASSES:
        raise ValueError(f"Card '{card['id']}' has unknown class '{card['class']}' in {source}")
    for lo_hi in card.get("stats", {}).values():
        if len(lo_hi) != 2:
            raise ValueError(f"Card '{card['id']}' has malformed stat range in {source}")


def load_generic_cards():
    cards = []
    for name in ("dates.json", "events.json", "choices.json"):
        path = DATA_DIR / name
        for card in _load_json(path):
            _validate(card, path.name)
            cards.append(card)
    return cards


def load_archetype_cards():
    path = DATA_DIR / "archetype_cards.json"
    raw = _load_json(path)
    for archetype, cards in raw.items():
        for card in cards:
            _validate(card, path.name)
    return raw
