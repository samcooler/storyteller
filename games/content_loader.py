"""Generic JSON content loading, shared by games/data/*.json (constants) and
games/data/cards/*.json (via card_loader.py) - one loading mechanism for
every game's data-driven content, so a second game just adds its own JSON
files under games/data/ and reads them the same way.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def load_json(name):
    with open(DATA_DIR / name) as f:
        return json.load(f)
