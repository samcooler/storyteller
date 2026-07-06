"""Semantic input actions for the engine.

Games and menus should ask "was this a CONFIRM?" rather than hand-checking
every physical key that means confirm. The arrows/WASD/Enter/Space aliasing
lived copy-pasted across every screen; it lives here now, in one table.

Usage:

    from games import input as actions
    act = actions.of(event)
    if act == actions.CONFIRM:
        ...

`of()` returns None for anything that isn't a mapped KEYDOWN (mouse events,
key releases, unmapped keys), so callers can still fall through to their own
raw-event handling for game-specific keys.
"""

import pygame

# Action names. Plain strings so they're trivial to print/debug and compare.
UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"
CONFIRM = "confirm"   # Enter / Space: commit the current choice
CANCEL = "cancel"     # Backspace: back out of a sub-step without leaving
BACK = "back"         # Esc: leave the current screen entirely

_KEYMAP = {
    pygame.K_UP: UP,
    pygame.K_w: UP,
    pygame.K_DOWN: DOWN,
    pygame.K_s: DOWN,
    pygame.K_LEFT: LEFT,
    pygame.K_a: LEFT,
    pygame.K_RIGHT: RIGHT,
    pygame.K_d: RIGHT,
    pygame.K_RETURN: CONFIRM,
    pygame.K_SPACE: CONFIRM,
    pygame.K_BACKSPACE: CANCEL,
    pygame.K_ESCAPE: BACK,
}


def of(event):
    """The semantic action for a pygame event, or None if it maps to nothing."""
    if event.type != pygame.KEYDOWN:
        return None
    return _KEYMAP.get(event.key)
