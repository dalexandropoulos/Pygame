import random
import pygame
from entities import Ball, Floor
from physics import PhysicsEngine
from config import (
    SCREEN_WIDTH,
    SPAWN_INTERVAL,
    SPAWN_POS_Y,
    SPAWN_X_JITTER,
    COLOR_BG,
)

class SimulationScreen:
    """Coordinates simulation scene, spawning schedule, entity lifecycle, and visual frame dispatch."""

    def __init__(self) -> None:
        self.balls: list[Ball] = []
        self.floor: Floor = Floor()
        self.physics_engine: PhysicsEngine = PhysicsEngine()
        self.spawn_timer: float = 0.0
        self.spawn_interval: float = SPAWN_INTERVAL

        # Spawn initial ball on startup
        self._spawn_ball()

    def _spawn_ball(self) -> None:
        """Instantiate a new ball near the upper horizontal center with minor randomized offset."""
        spawn_x = (float(SCREEN_WIDTH) / 2.0) + random.uniform(-SPAWN_X_JITTER, SPAWN_X_JITTER)
        spawn_pos = pygame.math.Vector2(spawn_x, SPAWN_POS_Y)
        self.balls.append(Ball(position=spawn_pos))

    def update(self, dt: float) -> None:
        """Progress spawner clock and advance physics simulation."""
        self.spawn_timer += dt
        while self.spawn_timer >= self.spawn_interval:
            self.spawn_timer -= self.spawn_interval
            self._spawn_ball()

        self.physics_engine.update(self.balls, dt)

    def render(self, surface: pygame.Surface) -> None:
        """Clear the frame and draw all active entities."""
        surface.fill(COLOR_BG)
        self.floor.render(surface)
        for ball in self.balls:
            ball.render(surface)
