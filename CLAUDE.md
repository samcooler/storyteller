# Architecture

This is a pygame "game switcher": `main.py` runs a scene stack that shows a
menu of games (`games/__init__.py:GAMES`) and pushes a `GameScene` wrapping
whichever one is selected. It's meant to grow into a small reusable engine
for more than one turn-based, card/hand-driven sim, so the codebase draws a
line between engine pieces and game-specific ones even though (for now, by
design - see below) they all still live flat in `games/`.

## Engine vs game

**Engine** (game-agnostic, reusable as-is by a second game):
- `games/base.py` - `Game` base class contract: `reset`/`handle_event`/`update`/`draw`.
- `games/scene.py` - scene stack (`Scene`, `Push`/`Pop`/`Quit`, `SceneStack`, `GameScene`).
- `games/input.py` - semantic input layer (`UP`/`DOWN`/`LEFT`/`RIGHT`/`CONFIRM`/`CANCEL`/`BACK`).
- `games/fsm.py` - generic turn/selection state-machine base (`State`, `states()`).
- `games/ui.py` - "juicy 2D menu/HUD" rendering toolkit (panels, corners, bars,
  gauges, fonts). Reusable, but currently commits to one visual style (gradient
  panels + corner ornaments) via mutable module-level theme globals
  (`ui.BG`, `ui.ACCENT`, ...) rather than a passed-in theme object - a second
  game inherits this exact look rather than bringing its own, until that's
  reworked.
- `games/card_loader.py` / a future `games/content_loader.py` - JSON-in,
  Python-constants-out loading pattern for data-driven content.

**Game-specific** (Polycule Simulator only): everything prefixed `polycule_*`
(`polycule_model.py`, `polycule_rules.py`, `polycule_states.py`,
`polycule_simulator.py`, `polycule_constants.py`, and the `polycule_view_*.py`
widget modules), plus `pixel_portrait.py` and `games/data/`.

## Why no `engine/` package yet

A physical `engine/` vs `games/<name>/` directory split is deliberately
deferred until a second game actually exists. Splitting now would be guesswork
about where the boundary really falls; splitting once a second game is being
built is mechanical, because by then real usage - not speculation - shows
what's actually shared. Until then, keep the modules above import-clean of
`polycule_*` concepts so that future split stays a pure file-move.

## What a second game needs to bring

- A `Game` subclass (`games/base.py`) registered in `games/__init__.py:GAMES`.
- Its own constants/content module and `games/data/*.json` files, loaded
  through the same JSON-loader pattern as `card_loader.py`.
- Its own `fsm.State` subclasses for its turn/selection flow (see
  `polycule_states.py` for the pattern: stateless singletons keyed by the
  same string the view reads to decide what to render).
- `serialize()`/`deserialize()` on its model if it wants save/load - `games/save.py`
  only handles the file I/O/versioning contract, not per-game serialization.

## Model/rules/view split (per game)

Each game keeps its simulated world in a plain-Python model
(`polycule_model.py`) with no pygame/UI imports, resolution logic as plain
functions over that model (`polycule_rules.py`) so it's testable headlessly,
and pygame drawing/input in the `Game` subclass plus per-widget view modules.
Don't build a generic ECS for this - the model/rules split above is deliberately
scoped to "turn-based sim with entities + stats + relationships," matching
what this project's games actually need.
