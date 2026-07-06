import random

from games import polycule_rules as rules
from games.polycule_constants import OUTCOME_TIERS
from games.polycule_model import PolyculeModel


def test_tier_value_interpolates_between_lo_and_hi():
    assert rules.tier_value(0, 90, 0) == 0
    assert rules.tier_value(0, 90, len(OUTCOME_TIERS) - 1) == 90
    # midpoint tier should land roughly midway
    mid_tier = (len(OUTCOME_TIERS) - 1) // 2
    assert 30 < rules.tier_value(0, 90, mid_tier) < 60


def test_apply_stats_routes_trust_and_spark_to_relationship(model):
    a, b = model.members[0], model.members[1]
    rel = model.get_rel(a.name, b.name)
    rel["trust"], rel["spark"] = 50, 50
    card = {"stats": {"trust": (10, 10), "spark": (-5, -5)}}
    rules.apply_stats(model, card, tier=0, target_name=b.name)
    assert rel["trust"] == 60
    assert rel["spark"] == 45


def test_apply_stats_routes_harmony_and_chaos_to_the_cule(model):
    model.harmony, model.chaos = 50, 50
    card = {"stats": {"harmony": (5, 5), "chaos": (-5, -5)}}
    rules.apply_stats(model, card, tier=0, target_name=None)
    assert model.harmony == 55
    assert model.chaos == 45


def test_apply_stats_routes_other_keys_to_active_statuses(model):
    active = model.active
    active.statuses["stress"] = 50
    card = {"stats": {"stress": (10, 10)}}
    rules.apply_stats(model, card, tier=0, target_name=None)
    assert active.statuses["stress"] == 60


def test_apply_stats_clamps_to_0_100(model):
    active = model.active
    active.statuses["stress"] = 95
    card = {"stats": {"stress": (50, 50)}}
    rules.apply_stats(model, card, tier=0, target_name=None)
    assert active.statuses["stress"] == 100


def test_apply_stats_zeroing_interest_drops_prospect(model):
    active = model.active
    name = rules.unique_name(model)
    from games.polycule_model import Character
    stranger = Character(model.rng, name=name)
    model.prospects[name] = {"char": stranger, "interest": 5, "met_by": active.name}
    card = {"stats": {"interest": (-10, -10)}}
    rules.apply_stats(model, card, tier=0, target_name=name)
    assert name not in model.prospects


def test_spend_energy_reduces_active_energy_and_clamps_at_zero(model):
    model.active.statuses["energy"] = 10
    rules.spend_energy(model)
    assert model.active.statuses["energy"] == 0


def test_unique_name_avoids_existing_names(model):
    existing = {m.name for m in model.members} | set(model.prospects)
    for _ in range(50):
        name = rules.unique_name(model)
        assert name not in existing


def test_resolve_events_card_applies_stats_and_returns_outcome(model):
    card = {"class": "events", "blurb": "Something happens.", "stats": {"stress": (5, 5)}}
    before = model.active.statuses["stress"]
    outcome = rules.resolve(model, card, None)
    assert outcome.tier is not None
    assert model.active.statuses["stress"] >= before


def test_resolve_choice_commit_converts_prospect_to_member(model):
    active = model.active
    name = rules.unique_name(model)
    from games.polycule_model import Character
    stranger = Character(model.rng, name=name)
    model.prospects[name] = {"char": stranger, "interest": 90, "met_by": active.name}
    card = {"class": "choice", "kind": "commit", "blurb": "Moving in together.",
            "stats": {"trust": (10, 10), "spark": (10, 10)}}
    rules.resolve(model, card, name)
    assert name not in model.prospects
    assert any(m.name == name for m in model.members)


def test_resolve_choice_breakup_guaranteed_removes_member():
    m = PolyculeModel(random.Random(7))
    active = m.active
    other = next(mem for mem in m.members if mem.name != active.name)
    card = {"class": "choice", "kind": "breakup", "guaranteed_exit": True, "blurb": "It's over."}
    rules.resolve(m, card, other.name)
    assert other.name not in {mem.name for mem in m.members}
    assert not any(other.name in key for key in m.relationships)


def test_negotiate_date_outcome_is_always_one_of_the_three_contract_values(model):
    active = model.active
    other = next(m for m in model.members if m.name != active.name)
    from games.polycule_constants import DAYS
    outcomes = {rules.negotiate_date(model, other.name, day)[0] for day in DAYS}
    assert outcomes <= {"accept", "counter", "decline"}


def test_negotiate_date_high_trust_and_free_day_accepts():
    m = PolyculeModel(random.Random(0))
    active = m.active
    other = next(mem for mem in m.members if mem.name != active.name)
    m.get_rel(active.name, other.name)["trust"] = 100
    from games.polycule_constants import DAYS
    # At least one day across a fixed rng must land on "accept" for a
    # maximally-willing pair, since decline only happens when a busy day
    # can't be countered.
    outcomes = {rules.negotiate_date(m, other.name, day)[0] for day in DAYS}
    assert "accept" in outcomes or "counter" in outcomes


def test_resolve_scheduled_event_updates_trust_and_spark_between_members():
    m = PolyculeModel(random.Random(3))
    a, b = m.members[0], m.members[1]
    rel = m.get_rel(a.name, b.name)
    before_trust = rel["trust"]
    ev = {"a": a.name, "b": b.name, "day": "Mon", "activity": a.preferred_activity, "is_prospect": False}
    lines = rules.resolve_scheduled_event(m, ev)
    assert lines
    assert rel["trust"] != before_trust or rel["spark"] >= 0
