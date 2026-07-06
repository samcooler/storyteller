import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from games import polycule_view_hand as hand
from games.polycule_simulator import PolyculeSimulator


@pytest.fixture(scope="module")
def _pygame_ready():
    # Module-scoped: pygame.quit() between tests invalidates already-cached
    # Font objects in ui.py's module-level font cache, since the cache
    # persists across tests but the native font resources it holds don't
    # survive a quit()/init() cycle - causing spurious "Text has zero
    # width" errors in whichever test runs after the first re-init.
    pygame.init()
    pygame.display.set_mode((1920, 1080))
    yield
    pygame.quit()


@pytest.fixture
def sim(_pygame_ready):
    s = PolyculeSimulator(pygame.display.get_surface())
    s.reset()
    return s


def test_remove_card_records_fx_and_removes_from_hand(sim):
    card = sim.hand[0]
    before = len(sim.hand)
    sim._remove_card(card, "play")
    assert card not in sim.hand
    assert len(sim.hand) == before - 1
    assert len(sim.card_fx) == 1
    assert sim.card_fx[0]["card"] is card
    assert sim.card_fx[0]["kind"] == "play"


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


def test_virtual_order_reserves_the_fading_cards_slot(sim):
    # Regression test for the overlap bug: once a card is removed from
    # sim.hand, the *remaining* cards must not slide into its old slot
    # while it's still fading - the virtual order (used by both the live
    # row and the fx overlay) must have one more entry than the live hand
    # for every card still fading, with the fading card back at its
    # original index.
    original = list(sim.hand)
    fading = original[1]
    sim._remove_card(fading, "play")
    order = hand._virtual_order(sim)
    assert len(order) == len(sim.hand) + 1
    assert order.index(fading) == 1
    assert not hand._is_live(sim, fading)
    for card in sim.hand:
        assert hand._is_live(sim, card)


def test_virtual_order_handles_multiple_simultaneous_fades_without_collision(sim):
    original = list(sim.hand)
    for card in original:
        sim._remove_card(card, "discard")
    assert sim.hand == []
    order = hand._virtual_order(sim)
    # Every faded card gets its own slot - no two fx cards collapse onto
    # the same position, which is exactly the bug that caused overlapping
    # boxes when a second card was removed before the first had faded out.
    assert len(order) == len(original)
    assert sorted(id(c) for c in order) == sorted(id(c) for c in original)


def test_fx_uses_current_row_mode_not_the_mode_at_removal_time(sim):
    # An immediately-resolved play removes the card while sim.state is
    # still "hand" (fan mode), but transitions to "result" (collapsed
    # mode) in that same call - draw_card_fx must follow the row that's
    # actually showing *now*, not whatever was true at removal time, or
    # the fading card renders in a totally different screen region than
    # the live row.
    sim.state = "hand"
    card = sim.hand[0]
    sim._remove_card(card, "play")
    sim.state = "result"
    assert hand.hand_row_selecting(sim) is False
    surface = pygame.display.get_surface()
    sim.draw(surface)  # must not raise, and renders fx in collapsed mode
