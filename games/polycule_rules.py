"""Game rules for the Polycule Simulator: how a played card resolves.

These are plain functions over a `PolyculeModel` - they read and mutate the
world (stats, membership, prospects, the calendar's downstream effects) and
return the human-readable lines describing what happened, but they never
touch pygame or the controller's UI/FSM state. The controller calls them and
stashes the returned `Outcome` into whatever it's about to draw.

Keeping resolution here (rather than on the Game object) means the rules can
be reasoned about and exercised against a bare model, with no display up.
"""

from .polycule_constants import (
    DAYS,
    ENERGY_COST,
    EXIT_BREAKUP_TIER,
    FIRST_NAMES,
    HOBBIES,
    OUTCOME_TIERS,
    PREVIEW_PLACEHOLDERS,
    PROJECTS,
    REL_STAGES,
    REL_STAGE_LABELS,
    STAT_INFO,
    VENUES,
)
from .polycule_model import Character


class Outcome:
    """The result of resolving a card: the description lines to show, plus the
    outcome tier that was rolled (or None for effects that don't roll on the
    OUTCOME_TIERS ladder, like scheduling a date)."""

    def __init__(self, lines, tier=None):
        self.lines = lines
        self.tier = tier


def roll_tier(rng):
    return rng.randrange(len(OUTCOME_TIERS))


def tier_value(lo, hi, tier):
    frac = tier / (len(OUTCOME_TIERS) - 1)
    return round(lo + frac * (hi - lo))


def spend_energy(model):
    active = model.active
    active.statuses["energy"] = max(0, active.statuses["energy"] - ENERGY_COST)


def unique_name(model):
    existing = set(model.prospects) | {m.name for m in model.members}
    candidates = [n for n in FIRST_NAMES if n not in existing]
    if candidates:
        return model.rng.choice(candidates)
    suffixes = ["Jr.", "II", "the Younger", "from the group chat", "with the other haircut"]
    for _ in range(20):
        name = f"{model.rng.choice(FIRST_NAMES)} {model.rng.choice(suffixes)}"
        if name not in existing:
            return name
    return f"{model.rng.choice(FIRST_NAMES)} #{model.rng.randint(100, 999)}"


def flavor(model, card, target_name=None):
    kwargs = {
        "target": target_name or "",
        "hobby": model.rng.choice(HOBBIES),
        "project": model.rng.choice(PROJECTS),
        "venue": model.rng.choice(VENUES),
    }
    return card["blurb"].format(**kwargs)


def preview_blurb(card):
    """Rng-free blurb rendering for cards that don't have a real target yet,
    safe to call every frame (draw/discard previews)."""
    return card["blurb"].format(**PREVIEW_PLACEHOLDERS)


def apply_stats(model, card, tier, target_name, skip_relational=False):
    """Applies every stat in card['stats'], tier-scaled, routing each key
    by name: trust/spark to the active-target relationship, interest to a
    prospect, harmony/chaos to the cule, everything else (happiness,
    fulfillment, energy, stress, desire) to the active member's own
    statuses. Returns a list of description lines."""
    member = model.active
    notes = []
    for key, (lo, hi) in card.get("stats", {}).items():
        delta = tier_value(lo, hi, tier)
        if key in ("trust", "spark"):
            if skip_relational or target_name is None:
                continue
            rel = model.get_rel(member.name, target_name)
            rel[key] = max(0, min(100, rel[key] + delta))
            notes.append(f"{key.capitalize()} {delta:+d}")
        elif key == "interest":
            if skip_relational or target_name is None:
                continue
            prospect = model.prospects.get(target_name)
            if prospect is None:
                continue
            prospect["interest"] = max(0, min(100, prospect["interest"] + delta))
            notes.append(f"Interest {delta:+d}")
            if prospect["interest"] <= 0:
                del model.prospects[target_name]
                notes.append(f"{target_name} stops responding entirely")
        elif key in ("harmony", "chaos"):
            setattr(model, key, max(0, min(100, getattr(model, key) + delta)))
            notes.append(f"{key.capitalize()} {delta:+d}")
        else:
            member.statuses[key] = max(0, min(100, member.statuses[key] + delta))
            notes.append(f"{STAT_INFO[key]['label']} {delta:+d}")
    return [", ".join(notes) + "."] if notes else []


def spawn_prospect(model, member):
    venue = model.rng.choice(VENUES)
    name = unique_name(model)
    stranger = Character(model.rng, name=name)
    interest = model.rng.randint(10, 30)
    model.prospects[stranger.name] = {"char": stranger, "interest": interest, "met_by": member.name}
    return [f"{member.name} meets {stranger.name} at {venue}.",
            f"({stranger.archetype}, +{interest} interest)"]


def stage_transition_note(model, member, target_name, old_stage):
    new_stage = model.relationship_stage(model.get_rel(member.name, target_name))
    if new_stage == old_stage:
        return []
    order = REL_STAGES
    verb = "deepens" if order.index(new_stage) > order.index(old_stage) else "takes a step back"
    return [f"Something with {target_name} {verb} - this feels {REL_STAGE_LABELS[new_stage]} now."]


def negotiate_date(model, target_name, day):
    member = model.active
    my_prospects = model.member_prospects(member.name)
    is_prospect = target_name in my_prospects
    willingness = my_prospects[target_name]["interest"] if is_prospect else model.get_rel(member.name, target_name)["trust"]
    busy_days = set(model.rng.sample(DAYS, k=model.rng.randint(1, 3)))
    if day in busy_days:
        if willingness >= 50:
            free_days = [d for d in DAYS if d not in busy_days] or [day]
            return "counter", model.rng.choice(free_days), is_prospect
        return "decline", None, is_prospect
    if willingness >= 30:
        return "accept", None, is_prospect
    return "decline", None, is_prospect


def resolve(model, card, target_name):
    """Resolve a non-date card immediately, mutating the model and returning
    an Outcome. Date cards go through the calendar/negotiation flow in the
    controller instead and don't come here."""
    member = model.active
    lines = [flavor(model, card, target_name)]
    cls = card["class"]
    result_tier = None

    if cls == "events":
        tier = roll_tier(model.rng)
        result_tier = tier
        lines.append(OUTCOME_TIERS[tier])
        lines.extend(apply_stats(model, card, tier, None))
        if card.get("spawns_prospect"):
            lines.extend(spawn_prospect(model, member))

    elif cls == "dates":
        tier = roll_tier(model.rng)
        result_tier = tier
        old_stage = model.relationship_stage(model.get_rel(member.name, target_name)) if target_name in {m.name for m in model.members} else None
        lines.append(OUTCOME_TIERS[tier])
        lines.extend(apply_stats(model, card, tier, target_name))
        if old_stage:
            lines.extend(stage_transition_note(model, member, target_name, old_stage))

    elif cls == "choice":
        kind = card.get("kind")
        is_prospect = target_name in model.prospects
        tier = roll_tier(model.rng)
        result_tier = tier
        if kind == "commit" and is_prospect:
            prospect = model.prospects.pop(target_name)
            trust_lo_hi = card.get("stats", {}).get("trust", (10, 10))
            spark_lo_hi = card.get("stats", {}).get("spark", (10, 10))
            trust_d = tier_value(*trust_lo_hi, tier)
            spark_d = tier_value(*spark_lo_hi, tier)
            new_member = prospect["char"]
            new_member.joined_week = model.week
            model.members.append(new_member)
            model.get_rel(member.name, new_member.name).update({
                "trust": max(0, min(100, prospect["interest"] + trust_d)),
                "spark": max(0, min(100, prospect["interest"] + spark_d)),
            })
            for other in model.members:
                if other.name not in (member.name, new_member.name):
                    model.get_rel(new_member.name, other.name)  # seeds formed_week for the rest of the cule too
            if "desire" in card.get("stats", {}):
                d = tier_value(*card["stats"]["desire"], tier)
                member.statuses["desire"] = max(0, min(100, member.statuses["desire"] + d))
            lines.append(f"{new_member.name} joins the cule for real!")
        elif kind == "breakup":
            guaranteed = card.get("guaranteed_exit", False)
            if is_prospect:
                model.prospects.pop(target_name)
                lines += [OUTCOME_TIERS[tier], f"{target_name} is out of the picture."]
                lines.extend(apply_stats(model, card, tier, None, skip_relational=True))
            elif guaranteed or tier <= EXIT_BREAKUP_TIER:
                model.members = [m for m in model.members if m.name != target_name]
                model.relationships = {k: v for k, v in model.relationships.items() if target_name not in k}
                lines += [OUTCOME_TIERS[tier], f"{target_name} moves out for good."]
                lines.extend(apply_stats(model, card, tier, None, skip_relational=True))
            else:
                lines.append(OUTCOME_TIERS[tier])
                lines.extend(apply_stats(model, card, tier, target_name))
        else:
            # ask_to_change, share, message, or a commit card whose
            # target is already a member (deepening, not converting).
            old_stage = model.relationship_stage(model.get_rel(member.name, target_name)) if target_name in {m.name for m in model.members} else None
            lines.append(OUTCOME_TIERS[tier])
            lines.extend(apply_stats(model, card, tier, target_name))
            if old_stage:
                lines.extend(stage_transition_note(model, member, target_name, old_stage))

    spend_energy(model)
    return Outcome(lines, result_tier)


def resolve_scheduled_event(model, ev):
    """Resolve one calendar entry when its week arrives; returns recap lines."""
    a = next((m for m in model.members if m.name == ev["a"]), None)
    if a is None:
        return [f"Plans between {ev['a']} and {ev['b']} quietly fell through."]
    activity = ev["activity"]
    verb = "go jogging" if activity == "Jog" else f"head to the {activity.lower()}"
    if ev["is_prospect"]:
        prospect = model.prospects.get(ev["b"])
        if prospect is None:
            return [f"{ev['a']}'s plans with {ev['b']} fell through - they'd already drifted apart."]
        match = activity == prospect["char"].preferred_activity
        delta = model.rng.randint(15, 30) if match else model.rng.randint(-5, 10)
        prospect["interest"] = max(0, min(100, prospect["interest"] + delta))
        lines = [
            f"{ev['a']} and {ev['b']} {verb} on {ev['day']}.",
            f"{'This is exactly their thing.' if match else 'They have an okay time, but seem distracted.'} ({delta:+d} interest)",
        ]
        if prospect["interest"] <= 0:
            del model.prospects[ev["b"]]
            lines.append(f"{ev['b']} stops responding entirely.")
        return lines
    b = next((m for m in model.members if m.name == ev["b"]), None)
    if b is None:
        return [f"{ev['a']}'s plans with {ev['b']} fell through."]
    match = activity == b.preferred_activity
    trust_d = model.rng.randint(4, 12) if match else model.rng.randint(-4, 6)
    spark_d = model.rng.randint(6, 16) if match else model.rng.randint(-2, 8)
    rel = model.get_rel(a.name, b.name)
    rel["trust"] = max(0, min(100, rel["trust"] + trust_d))
    rel["spark"] = max(0, min(100, rel["spark"] + spark_d))
    return [
        f"{ev['a']} and {ev['b']} {verb} on {ev['day']}.",
        f"{'A perfect match of interests.' if match else 'Not exactly their favorite, but nice together anyway.'} "
        f"Trust {trust_d:+d}, Spark {spark_d:+d}.",
    ]
