from games.fsm import State, states


class _Idle(State):
    key = "idle"

    def handle_key(self, ctx, event):
        ctx.state = "active"
        ctx.log.append(("idle", event))


class _Active(State):
    key = "active"

    def handle_key(self, ctx, event):
        ctx.state = "idle"
        ctx.log.append(("active", event))


class _Ctx:
    def __init__(self):
        self.state = "idle"
        self.log = []


def test_states_registry_is_keyed_by_state_key():
    registry = states(_Idle(), _Active())
    assert set(registry) == {"idle", "active"}
    assert isinstance(registry["idle"], _Idle)


def test_states_are_shared_singletons_not_rebuilt_per_lookup():
    idle_a, active_a = _Idle(), _Active()
    registry = states(idle_a, active_a)
    assert registry["idle"] is idle_a
    assert registry["active"] is active_a


def test_dispatch_by_key_mutates_context_and_transitions():
    registry = states(_Idle(), _Active())
    ctx = _Ctx()
    registry[ctx.state].handle_key(ctx, "ev1")
    assert ctx.state == "active"
    registry[ctx.state].handle_key(ctx, "ev2")
    assert ctx.state == "idle"
    assert ctx.log == [("idle", "ev1"), ("active", "ev2")]


def test_base_state_handle_key_is_a_noop():
    ctx = _Ctx()
    State().handle_key(ctx, "ev")
    assert ctx.state == "idle"
    assert ctx.log == []
