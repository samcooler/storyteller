# Silly Game Machine

A little collection of comical, socially-commentary 2D pygame games for a
Raspberry Pi, with a menu to switch between them.

## Running on your dev machine

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 main.py
```

Add `--fullscreen` to run fullscreen (handy on the Pi's touchscreen).

Note: on macOS, pygame currently only has prebuilt wheels up through
Python 3.12 — if your default `python3` is newer, use `python3.12` to make
the venv.

## Controls

- Menu: Arrow keys to pick a game, Enter/Space to play, Esc to quit.
- In a game: Esc returns to the menu.
- Bonk the Billionaire: press 1-9 to bonk a hole, matching the number under it.
- Polycule Simulator: Enter to advance, Up/Down or 1/2 to pick a choice, Enter to confirm.

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
cd ~/storyteller && python3 main.py --fullscreen
```

To launch automatically on boot, we can add a systemd service or an autostart
entry later once there's more than one game worth showing off.
