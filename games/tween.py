"""Small reusable animation primitives.

Not a timeline/keyframe system - just the two shapes of motion this
project's views actually use today: smoothing a value toward a moving
target frame by frame (`approach`/`approach_point`), and a repeating
oscillation driven by elapsed time (`oscillate`, for pulses/glows/wobbles).
Add more here only once a concrete animation needs a shape these two don't
cover - this is deliberately not a general tweening library.
"""

import math


def approach(current, target, dt, rate=2.5):
    """Exponential-decay smoothing: move `current` a `rate`-scaled fraction of
    the way to `target` this frame. Frame-rate independent (the fraction is
    dt-scaled and clamped to 1), so it looks the same at 30fps and 144fps."""
    t = min(1.0, dt * rate)
    return current + (target - current) * t


def approach_point(current, target, dt, rate=2.5):
    """`approach` for an (x, y) pair."""
    t = min(1.0, dt * rate)
    return (current[0] + (target[0] - current[0]) * t,
            current[1] + (target[1] - current[1]) * t)


def oscillate(t, freq=1.0, phase=0.0):
    """A -1..1 sine wave over elapsed time `t`, for pulses/glows/wobbles."""
    return math.sin(t * freq + phase)
