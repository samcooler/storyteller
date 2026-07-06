import os
import sys

import pygame

from games import GAMES
from games import input as actions
from games import ui
from games.scene import GameScene, Push, Pop, Quit, Scene, SceneStack

FPS = 60
INTERNAL_SIZE = (1920, 1080)  # native 1080p render target, smooth-scaled to fit whatever display we're on


def create_screen():
    """Fill whatever display we're run on (Pi touchscreen, 4K monitor, laptop...).

    --windowed forces a smaller dev-friendly window instead.
    """
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return pygame.display.set_mode((1920, 1080))
    if "--windowed" in sys.argv:
        return pygame.display.set_mode((1920, 1080))
    return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)


def fit_rect(display_size, internal_size):
    """Largest same-aspect rect of internal_size that fits centered in display_size.

    We render smooth 2D graphics now, not pixel art, so this fills the display
    edge-to-edge with a continuous scale factor (no whole-number snapping) -
    the final blit uses smoothscale, so fractional scale looks clean rather
    than introducing pixel-art artifacts."""
    dw, dh = display_size
    iw, ih = internal_size
    raw_scale = min(dw / iw, dh / ih)
    tw, th = max(1, int(iw * raw_scale)), max(1, int(ih * raw_scale))
    return pygame.Rect((dw - tw) // 2, (dh - th) // 2, tw, th)


class MenuScene(Scene):
    """The game picker - the bottom of the scene stack. Enter launches the
    selected game (pushed as a GameScene), O opens the options modal, and Esc
    quits the whole app (popping the last scene empties the stack)."""

    def __init__(self, render_surface, games):
        self.render_surface = render_surface
        self.games = games
        self.selected = 0

    def handle_event(self, event):
        act = actions.of(event)
        if act == actions.DOWN:
            self.selected = (self.selected + 1) % len(self.games)
        elif act == actions.UP:
            self.selected = (self.selected - 1) % len(self.games)
        elif act == actions.BACK:
            return Quit()
        elif act == actions.CONFIRM:
            game = self.games[self.selected](self.render_surface)
            return Push(GameScene(game))
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_o:
            return Push(OptionsScene())
        return None

    def draw(self, surface):
        surface.fill(ui.BG)
        scale = ui.scale_factor(surface)
        title_font = ui.font(64, scale, title=True)
        item_font = ui.font(40, scale)
        hint_font = ui.font(24, scale)

        w, h = surface.get_size()
        title = title_font.render("Silly Game Machine", True, ui.ACCENT)
        surface.blit(title, title.get_rect(center=(w // 2, int(60 * scale))))

        start_y = int(150 * scale)
        spacing = int(50 * scale)
        for i, game_cls in enumerate(self.games):
            color = ui.ACCENT if i == self.selected else ui.TEXT_COLOR
            label = item_font.render(game_cls.name, True, color)
            surface.blit(label, label.get_rect(center=(w // 2, start_y + i * spacing)))

        desc = self.games[self.selected].description
        if desc:
            desc_label = hint_font.render(desc, True, ui.TEXT_COLOR)
            surface.blit(desc_label, desc_label.get_rect(center=(w // 2, h - int(60 * scale))))

        hint = hint_font.render("Arrows to choose, Enter to play, O for Options, Esc to quit", True, ui.DIM_TEXT)
        surface.blit(hint, hint.get_rect(center=(w // 2, h - int(25 * scale))))


class OptionsScene(Scene):
    """Centered modal dialog for app-wide settings (currently just the color
    theme). Non-opaque so the menu stays visible underneath it."""

    opaque = False

    def __init__(self):
        self.selected = 0
        self.rows = ["theme"]

    def handle_event(self, event):
        act = actions.of(event)
        if act in (actions.BACK, actions.CONFIRM):
            return Pop()
        if act == actions.LEFT:
            ui.cycle_theme(-1)
        elif act == actions.RIGHT:
            ui.cycle_theme(1)
        return None

    def draw(self, surface):
        scale = ui.scale_factor(surface)
        w, h = surface.get_size()
        dialog = pygame.Rect(0, 0, int(420 * scale), int(200 * scale))
        dialog.center = (w // 2, h // 2)
        ui.draw_panel(surface, dialog, scale, corner_style="diamond")

        title_font = ui.font(30, scale, title=True)
        body_font = ui.font(24, scale)
        hint_font = ui.font(18, scale)

        title = title_font.render("Options", True, ui.ACCENT)
        surface.blit(title, title.get_rect(midtop=(dialog.centerx, dialog.top + int(18 * scale))))

        label = body_font.render("Theme", True, ui.TEXT_COLOR)
        theme_label = ui.THEMES[ui.current_theme_name()]["label"]
        value = body_font.render(f"< {theme_label} >", True, ui.ACCENT)
        row_y = dialog.top + int(90 * scale)
        surface.blit(label, label.get_rect(midleft=(dialog.left + int(30 * scale), row_y)))
        surface.blit(value, value.get_rect(midright=(dialog.right - int(30 * scale), row_y)))

        hint = hint_font.render("Left/Right to change, Enter or Esc to close", True, ui.DIM_TEXT)
        surface.blit(hint, hint.get_rect(midbottom=(dialog.centerx, dialog.bottom - int(16 * scale))))


def main():
    pygame.init()
    screen = create_screen()
    pygame.display.set_caption("Silly Game Machine")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    render_surface = pygame.Surface(INTERNAL_SIZE).convert()
    dest_rect = fit_rect(screen.get_size(), INTERNAL_SIZE)
    render_scale = dest_rect.width / INTERNAL_SIZE[0]

    stack = SceneStack(MenuScene(render_surface, GAMES))

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                ex, ey = event.pos
                ix = (ex - dest_rect.left) / render_scale
                iy = (ey - dest_rect.top) / render_scale
                event = pygame.event.Event(event.type, {**event.dict, "pos": (ix, iy)})

            stack.handle_event(event)

        # A Quit command (or Esc at the root menu) empties the stack: exit.
        if stack.quit or stack.empty:
            running = False
            break

        stack.update(dt)
        stack.draw(render_surface)

        screen.fill((0, 0, 0))
        pygame.transform.smoothscale(render_surface, dest_rect.size, screen.subsurface(dest_rect))
        frame_scale = min(dest_rect.size) / ui.REFERENCE_DIM
        ui.draw_screen_frame(screen, dest_rect, frame_scale)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
