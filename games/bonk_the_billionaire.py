import random

import pygame

from . import ui
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
    description = "They keep popping up. Press 1-9 to bonk them back down."

    HOLES = 9
    COLS = 3

    def __init__(self, screen):
        super().__init__(screen)
        w, h = screen.get_size()
        scale = ui.scale_factor(screen)
        hole_size = int(70 * scale)
        margin_x, margin_y = w // 6, h // 5
        cell_w = (w - 2 * margin_x) // self.COLS
        cell_h = (h - 2 * margin_y) // (self.HOLES // self.COLS)
        self.moles = []
        for i in range(self.HOLES):
            col = i % self.COLS
            row = i // self.COLS
            cx = margin_x + col * cell_w + cell_w // 2
            cy = margin_y + row * cell_h + cell_h // 2
            self.moles.append(Mole(pygame.Rect(0, 0, hole_size, hole_size)))
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

    KEYS = [
        pygame.K_1, pygame.K_2, pygame.K_3,
        pygame.K_4, pygame.K_5, pygame.K_6,
        pygame.K_7, pygame.K_8, pygame.K_9,
    ]

    def handle_event(self, event):
        if self.game_over:
            return
        index = None
        if event.type == pygame.MOUSEBUTTONDOWN:
            for i, m in enumerate(self.moles):
                if m.rect.collidepoint(event.pos):
                    index = i
                    break
        elif event.type == pygame.KEYDOWN and event.key in self.KEYS:
            index = self.KEYS.index(event.key)

        if index is not None:
            m = self.moles[index]
            if m.up and not m.bonked:
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
        scale = ui.scale_factor(surface)
        font = ui.font(40, scale)
        small = ui.font(26, scale)
        inflate = int(20 * scale), int(10 * scale)

        for i, m in enumerate(self.moles):
            hole_color = (20, 20, 25)
            pygame.draw.ellipse(surface, hole_color, m.rect.inflate(*inflate))
            key_label = small.render(str(i + 1), True, (90, 90, 100))
            surface.blit(key_label, key_label.get_rect(center=(m.rect.centerx, int(m.rect.bottom + 16 * scale))))
            if m.up:
                color = (60, 200, 90) if m.bonked else (200, 60, 60)
                pygame.draw.rect(surface, color, m.rect, border_radius=max(2, int(8 * scale)))
                label = small.render("$", True, (255, 255, 255))
                surface.blit(label, label.get_rect(center=m.rect.center))

        hud = font.render(f"Score: {self.score}   Time: {int(self.time_left)}", True, (255, 255, 255))
        surface.blit(hud, (int(20 * scale), int(15 * scale)))

        if self.game_over:
            msg = font.render(f"Wealth redistributed: {self.score}! Press ESC for menu.", True, (255, 220, 100))
            surface.blit(msg, msg.get_rect(center=(surface.get_width() // 2, surface.get_height() - int(40 * scale))))
