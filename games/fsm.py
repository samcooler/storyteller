"""Generic turn/selection state-machine base.

A `State` is one node of a turn/selection flow: `key` is the string the
owning game's `self.state` holds, and `handle_key` reacts to a KEYDOWN event
by mutating the context object it's handed and reassigning its `state`
attribute to move on. States are stateless singletons - all mutable data
lives on the context, not the state object - so `states()` below builds one
shared instance per state, reusable across every game.

This is deliberately tiny: no enter/exit hooks, no transition table, no event
filtering beyond "here's a KEYDOWN, do something." Individual games (see
`games/polycule_states.py`) define their own concrete `State` subclasses and
context objects; this module only owns the shared shape.
"""


class State:
    """One node of a turn/selection FSM. `key` matches the string the owning
    game's context keys off of (e.g. to decide what to render)."""

    key = None

    def handle_key(self, ctx, event):
        """React to a KEYDOWN event: mutate `ctx` and set `ctx.state` to move on."""


def states(*instances):
    """Build the key->instance registry from a list of State singletons."""
    return {s.key: s for s in instances}
