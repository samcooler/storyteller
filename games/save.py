"""Generic save/load file I/O: read/write a JSON blob with a version tag.

What goes inside the blob is entirely up to the game - see `Game.serialize`/
`Game.deserialize` in `games/base.py` for that contract. This module only
owns the file format and versioning, so every game's save files look the
same on disk regardless of what they actually store.
"""

import json

SAVE_VERSION = 1


def save_to_path(path, state):
    with open(path, "w") as f:
        json.dump({"version": SAVE_VERSION, "state": state}, f)


def load_from_path(path):
    with open(path) as f:
        payload = json.load(f)
    if payload.get("version") != SAVE_VERSION:
        raise ValueError(f"Unsupported save version: {payload.get('version')!r}")
    return payload["state"]
