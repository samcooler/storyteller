import random

from games.polycule_model import PolyculeModel


def test_rel_key_is_symmetric(model):
    assert model.rel_key("Alex", "Sam") == model.rel_key("Sam", "Alex")


def test_get_rel_creates_and_reuses_same_entry(model):
    a, b = model.members[0].name, model.members[1].name
    rel = model.get_rel(a, b)
    rel["trust"] = 99
    assert model.get_rel(b, a) is rel
    assert model.get_rel(b, a)["trust"] == 99


def test_active_cycles_by_week(model):
    n = len(model.members)
    seen = {model.active.name}
    for _ in range(n * 2):
        model.week += 1
        seen.add(model.active.name)
    assert seen == {m.name for m in model.members}


def test_life_stage_progresses_with_tenure(model):
    member = model.members[0]
    member.joined_week = 1
    model.week = 1
    assert model.life_stage(member) == "arriving"
    model.week = 20
    assert model.life_stage(member) == "settling"
    model.week = 40
    assert model.life_stage(member) == "rooted"


def test_relationship_stage_gated_by_time_and_trust(model):
    rel = {"trust": 20, "spark": 50, "formed_week": 1}
    model.week = 1
    assert model.relationship_stage(rel) == "new"
    model.week = 11
    # low trust holds it back even though enough weeks have passed
    assert model.relationship_stage(rel) == "new"
    rel["trust"] = 60
    assert model.relationship_stage(rel) == "building"
    model.week = 40
    assert model.relationship_stage(rel) == "established"


def test_targets_for_card_dates_scope_pair_excludes_self():
    m = PolyculeModel(random.Random(1))
    active = m.active
    card = {"class": "dates", "scope": "pair"}
    targets = m.targets_for_card(card, active)
    assert active.name not in targets
    assert set(targets) == {mem.name for mem in m.members if mem.name != active.name}


def test_targets_for_card_dates_non_pair_scope_is_empty(model):
    card = {"class": "dates", "scope": "solo"}
    assert model.targets_for_card(card, model.active) == []


def test_targets_for_card_empty_when_sole_member():
    # A model with a single member has nobody to target a pair date with, so
    # eligible_cards (which relies on this same query) would filter it out.
    m = PolyculeModel(random.Random(2))
    m.members = [m.members[0]]
    card = {"class": "dates", "scope": "pair"}
    assert m.targets_for_card(card, m.members[0]) == []
