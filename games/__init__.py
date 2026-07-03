from .base import Game
from .bonk_the_billionaire import BonkTheBillionaire
from .polycule_simulator import PolyculeSimulator

GAMES = [
    BonkTheBillionaire,
    PolyculeSimulator,
]

__all__ = ["Game", "GAMES"]
