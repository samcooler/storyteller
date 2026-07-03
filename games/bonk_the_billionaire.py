import random

import pygame

from .base import Game

WHACK_TIME = 0.9
SPAWN_EVERY = (0.5, 1.1)


class Mole:
    def __init__(self, rect):
        self.rect = rect
        self.timer = 0.0
        self.up = False
        self.bonked = False

    def pop_up(self):
        self.up = True
        self.bonked = False
        self.timer = WHACK_TIME

    def update(self, dt):
        if self.up:
            self.timer -= dt
            if self.timer <= 0:
                self.up = False
                self.bonked = False


class BonkTheBillionaire(Game):
    name = "Bonk the Billionaire"
    description = "They keep popping up. Bonk them back down."

    HOLES = 9
    COLS = 3

    def __init__(self, screen):
        super().__init__(screen)
        w, h = screen.get_size()
        margin_x, margin_y = w // 6, h // 5
        cell_w = (w - 2 * margin_x) // self.COLS
        cell_h = (h - 2 * margin_y) // (self.HOLES // self.COLS)
        self.moles = []
        for i in range(self.HOLES):
            col = i % self.COLS
            row = i // self.COLS
            cx = margin_x + col * cell_w + cell_w // 2
            cy = margin_y + row * cell_h + cell_h // 2
            self.moles.append(Mole(pygame.Rect(0, 0, 70, 70)))
            self.moles[-1].rect.center = (cx, cy)
        self.reset()

    def reset(self):
        self.score = 0
        self.time_left = 30.0
        self.spawn_timer = 0.5
        for m in self.moles:
            m.up = False
            m.bonked = False
        self.game_over = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and not self.game_over:
            for m in self.moles:
                if m.up and not m.bonked and m.rect.collidepoint(event.pos):
                    m.bonked = True
                    m.timer = 0.15
                    self.score += 1

    def update(self, dt):
        if self.game_over:
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self.time_left = 0
            self.game_over = True

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = random.uniform(*SPAWN_EVERY)
            candidates = [m for m in self.moles if not m.up]
            if candidates:
                random.choice(candidates).pop_up()

        for m in self.moles:
            m.update(dt)

    def draw(self, surface):
        surface.fill((30, 30, 40))
        font = pygame.font.SysFont(None, 40)
        small = pygame.font.SysFont(None, 26)

        for m in self.moles:
            hole_color = (20, 20, 25)
            pygame.draw.ellipse(surface, hole_color, m.rect.inflate(20, 10))
            if m.up:
                color = (60, 200, 90) if m.bonked else (200, 60, 60)
                pygame.draw.rect(surface, color, m.rect, border_radius=8)
                label = small.render("$", True, (255, 255, 255))
                surface.blit(label, label.get_rect(center=m.rect.center))

        hud = font.render(f"Score: {self.score}   Time: {int(self.time_left)}", True, (255, 255, 255))
        surface.blit(hud, (20, 15))

        if self.game_over:
            msg = font.render(f"Wealth redistributed: {self.score}! Press ESC for menu.", True, (255, 220, 100))
            surface.blit(msg, msg.get_rect(center=(surface.get_width() // 2, surface.get_height() - 40)))
