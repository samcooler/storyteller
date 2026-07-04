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
fullscreen). Pass `--windowed` for a 1600x1200 dev window instead.
Everything renders internally at a fixed 1600x1200 and is upscaled with square
pixels (integer scale only, so it stays crisp) — keeps it fast on the Pi
regardless of the actual display resolution.

Note: on macOS, pygame currently only has prebuilt wheels up through
Python 3.12 — if your default `python3` is newer, use `python3.12` to make
the venv.

## Controls

- Menu: Arrow keys to pick a game, Enter/Space to play, Esc to quit.
- In a game: Esc returns to the menu.
- Bonk the Billionaire: press 1-9 to bonk a hole, matching the number under it.
- Polycule Simulator: Left/Right to pick a card, Enter to play it (then
  Up/Down + Enter to choose a target if needed, Backspace to cancel), Tab for
  the roster window, C for the calendar.

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

`fit_rect` in `main.py` only ever scales the internal 1600x1200 render surface
by a whole number (so pixel art stays crisp), so whatever the actual display
resolution is, the game fills it exactly only when that resolution is a clean
multiple of 1600x1200. Left at the monitor's native 4K (3840x2160), the best
whole-number fit is 2x (3200x2400), leaving a visible black letterboxed
border on all sides.

This is a physical Pi setting, not part of the repo. The Pi runs the modern
`labwc` (Wayland) desktop with full KMS (`vc4-kms-v3d`), so the classic
`hdmi_group`/`hdmi_mode` firmware options in `config.txt` don't apply here —
output mode is instead managed by `kanshi`, the Wayland output daemon labwc
already runs. Force the lower resolution with a `kanshi` profile:

`~/.config/kanshi/config`:
```
profile {
	output HDMI-A-1 mode 1600x1200@60.00Hz position 0,0
}
```

That's exactly 1x the 1600x1200 internal render size (confirmed available via
`wlr-randr` on the Dell U3219Q here), so the game fills the screen
edge-to-edge with no letterboxing — and at 1x scale there's no upscaling
blur at all, just native pixels. Apply it immediately with
`pkill -HUP kanshi` (no reboot needed) — it also takes effect automatically
on future logins since kanshi re-reads this file on start.
