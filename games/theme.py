"""A color theme as a typed value, rather than a bag of dict keys.

`ui.py` still exposes the active theme's colors as `ui.BG`/`ui.ACCENT`/etc.
module globals for every existing call site to keep reading unchanged, but
`ui.set_theme` now builds one of these first and reads its fields to fill
those globals in one place. New code - especially anything doing real
graphics work, like swapping in a second visual style or rendering two
themes side by side - should take a `Theme` as an explicit argument instead
of reaching for the globals, since a `Theme` (unlike the globals) can vary
per call rather than being one process-wide mutable value.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    bg: tuple
    pastel_top: tuple
    pastel_bottom: tuple
    border_outer: tuple
    border_inner: tuple
    text: tuple
    dim_text: tuple
    accent: tuple

    @classmethod
    def from_dict(cls, name, data):
        return cls(
            name=name,
            label=data["label"],
            bg=tuple(data["bg"]),
            pastel_top=tuple(data["pastel_top"]),
            pastel_bottom=tuple(data["pastel_bottom"]),
            border_outer=tuple(data["border_outer"]),
            border_inner=tuple(data["border_inner"]),
            text=tuple(data["text"]),
            dim_text=tuple(data["dim_text"]),
            accent=tuple(data["accent"]),
        )
