"""The calendar overlay listing this week's, next week's, and the rest of the
quarter's scheduled dates."""

from . import ui
from .polycule_constants import WEEKS_PER_QUARTER


def draw_calendar(sim, surface, rect, scale):
    ui.draw_panel(surface, rect, scale, corner_style="diamond")
    title_font = ui.font(30, scale, title=True)
    body_font = ui.font(22, scale)
    small_font = ui.font(18, scale)
    surface.blit(title_font.render("Calendar", True, ui.ACCENT), (rect.left + int(20 * scale), rect.top + int(14 * scale)))
    y = rect.top + int(64 * scale)

    def line(text, font_obj=body_font, color=ui.TEXT_COLOR, indent=0):
        nonlocal y
        surface.blit(font_obj.render(text, True, color), (rect.left + int((20 + indent) * scale), y))
        y += int((30 if font_obj is body_font else 24) * scale)

    line(f"Quarter {sim.quarter}, Week {sim.week_in_quarter} of {WEEKS_PER_QUARTER}")
    y += int(10 * scale)
    line(f"This week: {sim.active.name}'s turn")
    next_member = sim.members[sim.week % len(sim.members)] if sim.members else None
    if next_member:
        line(f"Next week: {next_member.name}'s turn")
    next_events = sim.calendar.get(sim.week + 1, [])
    if next_events:
        line("Scheduled:", small_font, ui.DIM_TEXT, indent=10)
        for ev in next_events:
            line(f"{ev['a']} & {ev['b']}: {ev['activity']} on {ev['day']}", small_font, ui.TEXT_COLOR, indent=20)
    y += int(16 * scale)
    line("After that, this quarter:")
    quarter_end = sim.quarter * WEEKS_PER_QUARTER
    found_any = False
    for w in range(sim.week + 2, quarter_end + 1):
        for ev in sim.calendar.get(w, []):
            found_any = True
            line(f"Week {w}: {ev['a']} & {ev['b']} - {ev['activity']} on {ev['day']}",
                 small_font, ui.TEXT_COLOR, indent=20)
    if not found_any:
        line("Nothing else scheduled yet.", small_font, ui.DIM_TEXT, indent=20)
