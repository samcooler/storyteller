import math

from games import tween


def test_approach_moves_toward_target_and_clamps_at_dt_large():
    assert tween.approach(0.0, 100.0, dt=10.0, rate=2.5) == 100.0


def test_approach_is_frame_rate_independent_in_the_limit():
    # Many small steps should land close to one big step over the same total time.
    small_dt = 1 / 240
    steps = int((1 / 30) / small_dt)
    cur = 0.0
    for _ in range(steps):
        cur = tween.approach(cur, 100.0, dt=small_dt, rate=2.5)
    big_step = tween.approach(0.0, 100.0, dt=1 / 30, rate=2.5)
    assert abs(cur - big_step) < 0.5


def test_approach_point_moves_each_axis_independently():
    result = tween.approach_point((0.0, 0.0), (10.0, -10.0), dt=10.0, rate=2.5)
    assert result == (10.0, -10.0)


def test_oscillate_matches_sine_wave():
    assert tween.oscillate(0.0) == 0.0
    assert math.isclose(tween.oscillate(math.pi / 2, freq=1.0), 1.0)
    assert math.isclose(tween.oscillate(1.0, freq=2.0, phase=0.5), math.sin(2.5))
