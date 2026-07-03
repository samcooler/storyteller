import sys

import pygame

from games import GAMES

SCREEN_SIZE = (800, 480)  # matches the official 7" Raspberry Pi touchscreen
FPS = 60

BG = (18, 18, 24)
FG = (240, 240, 240)
ACCENT = (255, 200, 60)


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
        title_font = pygame.font.SysFont(None, 64)
        item_font = pygame.font.SysFont(None, 40)
        hint_font = pygame.font.SysFont(None, 24)

        title = title_font.render("Silly Game Machine", True, ACCENT)
        surface.blit(title, title.get_rect(center=(surface.get_width() // 2, 60)))

        start_y = 150
        for i, game_cls in enumerate(self.games):
            color = ACCENT if i == self.selected else FG
            label = item_font.render(game_cls.name, True, color)
            surface.blit(label, label.get_rect(center=(surface.get_width() // 2, start_y + i * 50)))

        desc = self.games[self.selected].description
        if desc:
            desc_label = hint_font.render(desc, True, FG)
            surface.blit(desc_label, desc_label.get_rect(
                center=(surface.get_width() // 2, surface.get_height() - 60)))

        hint = hint_font.render("Arrows to choose, Enter to play, Esc to quit", True, (150, 150, 150))
        surface.blit(hint, hint.get_rect(center=(surface.get_width() // 2, surface.get_height() - 25)))


def main():
    pygame.init()
    fullscreen = "--fullscreen" in sys.argv
    flags = pygame.FULLSCREEN if fullscreen else 0
    screen = pygame.display.set_mode(SCREEN_SIZE, flags)
    pygame.display.set_caption("Silly Game Machine")
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
