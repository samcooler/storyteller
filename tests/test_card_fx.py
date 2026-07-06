import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from games.polycule_simulator import PolyculeSimulator


@pytest.fixture
def sim():
    pygame.init()
    screen = pygame.display.set_mode((1920, 1080))
    s = PolyculeSimulator(screen)
    s.reset()
    yield s
    pygame.quit()


def test_remove_card_records_fx_and_removes_from_hand(sim):
    card = sim.hand[0]
    before = len(sim.hand)
    sim._remove_card(card, "play")
    assert card not in sim.hand
    assert len(sim.hand) == before - 1
    assert len(sim.card_fx) == 1
    assert sim.card_fx[0]["card"] is card
    assert sim.card_fx[0]["kind"] == "play"


def test_remove_card_captures_fan_mode_while_in_hand_or_discard_state(sim):
    sim.state = "hand"
    card_a = sim.hand[0]
    sim._remove_card(card_a, "play")
    assert sim.card_fx[-1]["fan"] is True

    sim.hand.append(card_a)  # put it back so there's something to remove again
    sim.state = "discard"
    sim._remove_card(card_a, "discard")
    assert sim.card_fx[-1]["fan"] is True


def test_remove_card_captures_collapsed_mode_outside_hand_or_discard_state(sim):
    sim.state = "target"
    card = sim.hand[0]
    sim._remove_card(card, "play")
    assert sim.card_fx[-1]["fan"] is False


def test_update_drains_expired_fx(sim):
    card = sim.hand[0]
    sim._remove_card(card, "play")
    assert len(sim.card_fx) == 1
    for _ in range(30):
        sim.update(0.05)
    assert sim.card_fx == []


def test_draw_with_active_fx_does_not_raise(sim):
    card = sim.hand[0]
    sim._remove_card(card, "play")
    surface = pygame.display.get_surface()
    sim.draw(surface)  # should render both the hand row and the fx overlay
