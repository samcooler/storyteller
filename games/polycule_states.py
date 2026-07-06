"""The turn/selection state machine as explicit state objects.

`PolyculeSimulator` used to drive its turn flow through one long
if/elif ladder on a `self.state` string ("draw"/"discard"/"hand"/"target"/
"sub_choice"/"result"/"recap"). Each state's input handling is now its own
small class, and `handle_event` just dispatches to the current one.

`self.state` stays the same string it always was - it's the state's `key` -
because the view reads it all over to decide what to render. So these
objects own the *input + transition* side of each state; the drawing side
still lives in the game's view, keyed by the same string. Transitions are
plain `sim.state = "<key>"` assignments, exactly as before.

The state objects are stateless singletons: all mutable data lives on the
`sim` they're handed, so one instance per state is shared across every game.
"""

import pygame

from .polycule_constants import END_WEEK, MAX_HAND
from . import polycule_rules as rules

_LEFT = (pygame.K_LEFT, pygame.K_a)
_RIGHT = (pygame.K_RIGHT, pygame.K_d)
_PREV = (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w)
_NEXT = (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s)
_CONFIRM = (pygame.K_RETURN, pygame.K_SPACE)


class State:
    """One node of the turn FSM. `key` matches the string the view keys off."""

    key = None

    def handle_key(self, sim, event):
        """React to a KEYDOWN event: mutate `sim` and set `sim.state` to move on."""


class DrawState(State):
    """Just drew the top-up hand; press confirm to continue (into a mandatory
    discard if now over the hand cap, otherwise straight to play)."""

    key = "draw"

    def handle_key(self, sim, event):
        if event.key in _CONFIRM:
            sim.state = "discard" if len(sim.hand) > MAX_HAND else "hand"
            sim.hand_index = 0


class DiscardState(State):
    """Over the hand cap: pick cards to pitch until back at MAX_HAND."""

    key = "discard"

    def handle_key(self, sim, event):
        if event.key in _LEFT:
            sim.hand_index = (sim.hand_index - 1) % len(sim.hand)
        elif event.key in _RIGHT:
            sim.hand_index = (sim.hand_index + 1) % len(sim.hand)
        elif event.key in _CONFIRM:
            card = sim.hand[sim.hand_index]
            sim.hand.remove(card)
            sim.hand_index = 0
            if len(sim.hand) <= MAX_HAND:
                sim.state = "hand"


class HandState(State):
    """The main play state: scroll the hand (+ End Week), confirm to play."""

    key = "hand"

    def handle_key(self, sim, event):
        options = sim.hand + [END_WEEK]
        if event.key in _LEFT:
            sim.hand_index = (sim.hand_index - 1) % len(options)
        elif event.key in _RIGHT:
            sim.hand_index = (sim.hand_index + 1) % len(options)
        elif event.key in _CONFIRM:
            card = options[sim.hand_index]
            if card is END_WEEK:
                sim._finish_turn()
            elif card["class"] == "choice" or (card["class"] == "dates" and card.get("scope") == "pair"):
                targets = sim._card_targets(card)
                if not targets:
                    sim.result_text = [f"{card['name']} has no one left to target. It fizzles."]
                    sim.result_tier = None
                    sim.hand.remove(card)
                    sim.hand_index = 0
                    sim.state = "result"
                else:
                    sim.pending_card = card
                    sim.target_options = targets
                    sim.target_index = 0
                    sim.state = "target"
            else:
                outcome = rules.resolve(sim.model, card, None)
                sim.result_text = outcome.lines
                sim.result_tier = outcome.tier
                sim.hand.remove(card)
                sim.hand_index = 0
                sim.state = "result"


class TargetState(State):
    """Choosing who a targeted card lands on; Backspace backs out to the hand."""

    key = "target"

    def handle_key(self, sim, event):
        if event.key in _PREV:
            sim.target_index = (sim.target_index - 1) % len(sim.target_options)
        elif event.key in _NEXT:
            sim.target_index = (sim.target_index + 1) % len(sim.target_options)
        elif event.key == pygame.K_BACKSPACE:
            sim.state = "hand"
        elif event.key in _CONFIRM:
            target = sim.target_options[sim.target_index]
            if sim.pending_card.get("schedulable"):
                sim._start_date_flow(target)
            else:
                outcome = rules.resolve(sim.model, sim.pending_card, target)
                sim.result_text = outcome.lines
                sim.result_tier = outcome.tier
                sim.hand.remove(sim.pending_card)
                sim.hand_index = 0
                sim.state = "result"


class SubChoiceState(State):
    """A step of the multi-step date-scheduling flow (week/day/counter/activity)."""

    key = "sub_choice"

    def handle_key(self, sim, event):
        if event.key in _PREV:
            sim.sub_index = (sim.sub_index - 1) % len(sim.sub_options)
        elif event.key in _NEXT:
            sim.sub_index = (sim.sub_index + 1) % len(sim.sub_options)
        elif event.key == pygame.K_BACKSPACE:
            sim.state = "hand"
        elif event.key in _CONFIRM:
            sim._advance_sub_choice()


class ResultState(State):
    """Showing the outcome of a played card; confirm returns to the hand."""

    key = "result"

    def handle_key(self, sim, event):
        if event.key in _CONFIRM:
            sim.state = "hand"
            if sim.hand_index >= len(sim.hand):
                sim.hand_index = max(0, len(sim.hand) - 1)


class RecapState(State):
    """End-of-week recap of resolved calendar events; confirm starts next turn."""

    key = "recap"

    def handle_key(self, sim, event):
        if event.key in _CONFIRM:
            sim._start_turn(sim.active)


# Singleton registry, keyed by the same strings self.state has always used.
STATES = {
    s.key: s
    for s in (DrawState(), DiscardState(), HandState(), TargetState(),
              SubChoiceState(), ResultState(), RecapState())
}
