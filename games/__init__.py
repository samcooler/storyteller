from .base import Game
from .polycule_simulator import PolyculeSimulator

GAMES = [
    PolyculeSimulator,
]

__all__ = ["Game", "GAMES"]
