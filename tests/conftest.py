import random

import pytest

from games.polycule_model import PolyculeModel


@pytest.fixture
def model():
    """A PolyculeModel with a fixed seed, for deterministic assertions."""
    return PolyculeModel(random.Random(1234))
