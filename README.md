# Silly Game Machine

A little collection of comical, socially-commentary 2D pygame games for a
Raspberry Pi, with a menu to switch between them.

## Running on your dev machine

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 main.py
```

By default it fills whatever display it's run on (auto-detected, true
fullscreen). Pass `--windowed` for a 1920x1080 dev window instead.
Everything renders internally at a fixed 1920x1080 (16:9, matching the Pi's
monitor) and is upscaled with square pixels (integer scale only, so it stays
crisp) — keeps it fast on the Pi regardless of the actual display resolution.

Note: on macOS, pygame currently only has prebuilt wheels up through
Python 3.12 — if your default `python3` is newer, use `python3.12` to make
the venv.

## Running the tests

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

The model (`polycule_model.py`) and rules (`polycule_rules.py`) are plain
Python with no pygame/display dependency by design, so `tests/` exercises
them headlessly — no display driver or `SDL_VIDEODRIVER` workaround needed.

## Controls

- Menu: Arrow keys to pick a game, Enter/Space to play, Esc to quit.
- In a game: Esc returns to the menu.
- Polycule Simulator: Left/Right to pick a card, Enter to play it (then
  Up/Down + Enter to choose a target if needed, Backspace to cancel), Tab for
  the roster window, C for the calendar, F5 to save, F9 to load.

## Character portraits

`assets/portraits/` holds pre-sliced character bust art (see
`assets/images_younger.png` / `images_older.png` for the original AI-generated
grids and their `data_*.rtf` attribute tables). `games/pixel_portrait.py`
picks a portrait deterministically per character seed; if the folder is ever
empty it falls back to a tiny procedural pixel-art bust instead, so the game
still runs without the art assets.

To regenerate `assets/portraits/` from a new grid image + attribute table,
see `scripts/slice_portraits.py`.

## Adding a new game

1. Create `games/your_game.py` with a class that subclasses `games.base.Game`
   and implements `reset`, `handle_event`, `update`, `draw`, plus `name` and
   `description` class attributes.
2. Register it in `games/__init__.py` by adding it to the `GAMES` list.

That's it — it shows up in the menu automatically.

## Deploying to the Raspberry Pi

The Pi (`storyteller-pi` in `~/.ssh/config`) has a bare git repo at
`~/git_repos/storyteller.git` and a working copy checked out at
`~/storyteller`, with `python3-pygame` already installed via apt.

To ship local changes over:

```
./deploy.sh
```

This pushes the current branch to the Pi and pulls it into the working copy
there. Then, from the Pi's own desktop (not over SSH, since pygame needs the
local display), run:

```
cd ~/storyteller && python3 main.py
```

To launch automatically on boot, we can add a systemd service or an autostart
entry later once there's more than one game worth showing off.

### Matching the Pi's HDMI output to the 4K monitor

`fit_rect` in `main.py` only ever scales the internal render surface by a
whole number (so pixel art stays crisp), so the game fills the display
exactly only when the display resolution is a clean multiple of the internal
size. The internal size is 1920x1080 (16:9) specifically because the Dell
U3219Q's native 4K output, 3840x2160, is exactly 2x that — so running at the
monitor's native resolution already gives a perfect edge-to-edge fit with no
letterboxing and no kanshi/`config.txt` workaround needed.

(Earlier the internal size was a 4:3 resolution, which either got pillarboxed
or stretched on this 16:9 panel and needed a `kanshi` profile forcing a
non-native mode to fit cleanly. That's no longer necessary — if a `kanshi`
profile forcing a custom mode is still present in
`~/.config/kanshi/config` on the Pi from that era, it can be removed so the
display just runs at its native 3840x2160.)
