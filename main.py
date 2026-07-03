import os
import sys

import pygame

from games import GAMES
from games import ui

FPS = 60

BG = (18, 18, 24)
FG = (240, 240, 240)
ACCENT = (255, 200, 60)


def create_screen():
    """Fill whatever display we're run on (Pi touchscreen, 4K monitor, laptop...).

    --windowed forces a smaller dev-friendly window instead.
    """
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return pygame.display.set_mode((1280, 720))
    if "--windowed" in sys.argv:
        return pygame.display.set_mode((1280, 720))
    return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)


class Menu:
    def __init__(self, screen, games):
        self.screen = screen
        self.games = games
        self.selected = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.games)
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.games)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                return self.games[self.selected]
        return None

    def draw(self, surface):
        surface.fill(BG)
        scale = ui.scale_factor(surface)
        title_font = ui.font(64, scale)
        item_font = ui.font(40, scale)
        hint_font = ui.font(24, scale)

        w, h = surface.get_size()
        title = title_font.render("Silly Game Machine", True, ACCENT)
        surface.blit(title, title.get_rect(center=(w // 2, int(60 * scale))))

        start_y = int(150 * scale)
        spacing = int(50 * scale)
        for i, game_cls in enumerate(self.games):
            color = ACCENT if i == self.selected else FG
            label = item_font.render(game_cls.name, True, color)
            surface.blit(label, label.get_rect(center=(w // 2, start_y + i * spacing)))

        desc = self.games[self.selected].description
        if desc:
            desc_label = hint_font.render(desc, True, FG)
            surface.blit(desc_label, desc_label.get_rect(center=(w // 2, h - int(60 * scale))))

        hint = hint_font.render("Arrows to choose, Enter to play, Esc to quit", True, (150, 150, 150))
        surface.blit(hint, hint.get_rect(center=(w // 2, h - int(25 * scale))))


def main():
    pygame.init()
    screen = create_screen()
    pygame.display.set_caption("Silly Game Machine")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()

    menu = Menu(screen, GAMES)
    active_game = None

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if active_game is None:
                    running = False
                else:
                    active_game = None
            elif active_game is None:
                chosen = menu.handle_event(event)
                if chosen is not None:
                    active_game = chosen(screen)
                    active_game.reset()
            else:
                active_game.handle_event(event)

        if active_game is None:
            menu.draw(screen)
        else:
            active_game.update(dt)
            active_game.draw(screen)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
