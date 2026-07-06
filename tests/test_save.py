import random

from games import polycule_save
from games.polycule_model import PolyculeModel


def test_serialize_deserialize_round_trips_world_state(model):
    model.week = 5
    model.harmony, model.chaos = 70, 20
    a, b = model.members[0].name, model.members[1].name
    model.get_rel(a, b)["trust"] = 88
    model.calendar[6] = [{"a": a, "b": b, "day": "Fri", "activity": "Park", "is_prospect": False}]

    data = polycule_save.serialize_model(model)
    restored = polycule_save.deserialize_model(data)

    assert restored.week == 5
    assert restored.harmony == 70
    assert restored.chaos == 20
    assert sorted(m.name for m in restored.members) == sorted(m.name for m in model.members)
    assert restored.get_rel(a, b)["trust"] == 88
    assert restored.calendar == model.calendar


def test_round_trip_preserves_rng_continuity():
    m = PolyculeModel(random.Random(99))
    data = polycule_save.serialize_model(m)
    restored = polycule_save.deserialize_model(data)

    # Same rng state in, same draws out - the whole point of persisting it.
    expected = [m.rng.random() for _ in range(20)]
    actual = [restored.rng.random() for _ in range(20)]
    assert actual == expected


def test_round_trip_preserves_hand_cards_by_identity_of_id(model):
    member = model.members[0]
    member.hand = member.deck()[:2]
    data = polycule_save.serialize_model(model)
    restored = polycule_save.deserialize_model(data)
    restored_member = next(m for m in restored.members if m.name == member.name)
    assert [c["id"] for c in restored_member.hand] == [c["id"] for c in member.hand]


def test_round_trip_preserves_prospects(model):
    active = model.active
    from games.polycule_model import Character
    stranger = Character(model.rng, name="Zephyr")
    model.prospects["Zephyr"] = {"char": stranger, "interest": 42, "met_by": active.name}

    data = polycule_save.serialize_model(model)
    restored = polycule_save.deserialize_model(data)

    assert "Zephyr" in restored.prospects
    assert restored.prospects["Zephyr"]["interest"] == 42
    assert restored.prospects["Zephyr"]["met_by"] == active.name
    assert restored.prospects["Zephyr"]["char"].name == "Zephyr"


def test_relationship_keys_round_trip_regardless_of_original_pair_order(model):
    a, b = model.members[0].name, model.members[1].name
    model.get_rel(b, a)  # seed it via the reversed pair order
    data = polycule_save.serialize_model(model)
    restored = polycule_save.deserialize_model(data)
    assert restored.rel_key(a, b) in restored.relationships
