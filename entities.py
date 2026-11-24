import pygame
from config import (
    BALL_RADIUS,
    BALL_MASS,
    FLOOR_Y,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    COLOR_BALL,
    COLOR_BALL_OUTLINE,
    COLOR_FLOOR,
    COLOR_FLOOR_ACCENT,
)

class Ball:
    """Dynamic circular body simulated in 2D space."""

    def __init__(
        self,
        position: pygame.math.Vector2,
        velocity: pygame.math.Vector2 | None = None,
        radius: float = BALL_RADIUS,
        mass: float = BALL_MASS,
        color: tuple[int, int, int] = COLOR_BALL,
        outline_color: tuple[int, int, int] = COLOR_BALL_OUTLINE,
    ) -> None:
        self.position: pygame.math.Vector2 = pygame.math.Vector2(position)
        self.velocity: pygame.math.Vector2 = pygame.math.Vector2(velocity) if velocity is not None else pygame.math.Vector2(0.0, 0.0)
        self.radius: float = radius
        self.mass: float = mass
        self.color: tuple[int, int, int] = color
        self.outline_color: tuple[int, int, int] = outline_color

    @property
    def inv_mass(self) -> float:
        """Calculate inverse mass for physics impulse distribution."""
        return 1.0 / self.mass if self.mass > 0.0 else 0.0

    def update(self, dt: float) -> None:
        """Advance position along current velocity vector."""
        self.position += self.velocity * dt

    def render(self, surface: pygame.Surface) -> None:
        """Render filled circle and contrasting boundary outline."""
        center = (round(self.position.x), round(self.position.y))
        pygame.draw.circle(surface, self.color, center, int(self.radius))
        pygame.draw.circle(surface, self.outline_color, center, int(self.radius), width=1)


class Floor:
    """Static ground plane entity resting at the bottom boundary."""

    def __init__(
        self,
        y: float = FLOOR_Y,
        width: int = SCREEN_WIDTH,
        height: int = SCREEN_HEIGHT,
        color: tuple[int, int, int] = COLOR_FLOOR,
        accent_color: tuple[int, int, int] = COLOR_FLOOR_ACCENT,
    ) -> None:
        self.y: float = y
        self.rect: pygame.Rect = pygame.Rect(0, int(y), width, height - int(y))
        self.color: tuple[int, int, int] = color
        self.accent_color: tuple[int, int, int] = accent_color

    def render(self, surface: pygame.Surface) -> None:
        """Draw solid ground rectangle with decorative top surface line."""
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.line(surface, self.accent_color, (self.rect.left, self.rect.top), (self.rect.right, self.rect.top), width=2)
