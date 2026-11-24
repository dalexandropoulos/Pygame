import math
import pygame
from config import (
    BALL_RADIUS,
    PIN_RADIUS,
    BALL_COLOR,
    BALL_HIGHLIGHT,
    PIN_COLOR,
    PIN_FLASH_COLOR,
    RAIL_COLOR,
    RAIL_GLOW_COLOR,
)

def create_ball_sprites(radius: float = BALL_RADIUS) -> tuple[pygame.Surface, pygame.Surface]:
    """Generate pre-rendered alpha surfaces with specular lighting highlights for depth."""
    size = int(radius * 2) + 4
    center = (size // 2, size // 2)

    # Awake gold ball with specular highlight
    awake_sprite = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(awake_sprite, BALL_COLOR, center, int(radius))
    # Top-left specular highlight dot
    hl_x = center[0] - int(radius * 0.32)
    hl_y = center[1] - int(radius * 0.32)
    hl_r = max(1, int(radius * 0.28))
    pygame.draw.circle(awake_sprite, BALL_HIGHLIGHT, (hl_x, hl_y), hl_r)

    # Dormant dark-gold ball
    sleep_sprite = pygame.Surface((size, size), pygame.SRCALPHA)
    sleep_color = (max(0, BALL_COLOR[0] - 80), max(0, BALL_COLOR[1] - 80), max(0, BALL_COLOR[2] - 20))
    pygame.draw.circle(sleep_sprite, sleep_color, center, int(radius))
    sleep_hl = (max(0, BALL_HIGHLIGHT[0] - 60), max(0, BALL_HIGHLIGHT[1] - 60), max(0, BALL_HIGHLIGHT[2] - 40))
    pygame.draw.circle(sleep_sprite, sleep_hl, (hl_x, hl_y), hl_r)

    if pygame.display.get_surface() is not None:
        awake_sprite = awake_sprite.convert_alpha()
        sleep_sprite = sleep_sprite.convert_alpha()

    return awake_sprite, sleep_sprite


class Ball:
    """Verlet-integrated dynamic circular body simulated in 2D space."""

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        radius: float = BALL_RADIUS,
        is_sleeping: bool = False,
        position: pygame.math.Vector2 | None = None,
    ) -> None:
        if position is not None:
            self.x: float = float(position.x)
            self.y: float = float(position.y)
        else:
            self.x = float(x)
            self.y = float(y)
        self.old_x: float = self.x
        self.old_y: float = self.y
        self.radius: float = radius
        self.is_sleeping: bool = is_sleeping
        self.sleep_timer: float = 0.0

    @property
    def position(self) -> pygame.math.Vector2:
        return pygame.math.Vector2(self.x, self.y)

    @position.setter
    def position(self, pos: pygame.math.Vector2) -> None:
        self.x = float(pos.x)
        self.y = float(pos.y)

    def wake(self) -> None:
        """Awaken body from sleeping state and reset dormancy timer."""
        self.is_sleeping = False
        self.sleep_timer = 0.0

    def render(self, surface: pygame.Surface) -> None:
        """Fallback direct render."""
        center = (round(self.x), round(self.y))
        pygame.draw.circle(surface, BALL_COLOR, center, int(self.radius))


class WallSegment:
    """Rigid line-segment rail boundary confining dynamic bodies."""

    def __init__(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.x1: float = float(x1)
        self.y1: float = float(y1)
        self.x2: float = float(x2)
        self.y2: float = float(y2)
        self.dx: float = self.x2 - self.x1
        self.dy: float = self.y2 - self.y1
        self.len_sq: float = self.dx * self.dx + self.dy * self.dy
        self.inv_len_sq: float = 1.0 / self.len_sq if self.len_sq > 1e-8 else 0.0

    def draw(self, screen: pygame.Surface) -> None:
        """Render glowing rail boundary with dual-stroke neon styling."""
        p1 = (round(self.x1), round(self.y1))
        p2 = (round(self.x2), round(self.y2))
        pygame.draw.line(screen, RAIL_GLOW_COLOR, p1, p2, width=7)
        pygame.draw.line(screen, RAIL_COLOR, p1, p2, width=3)


class Pin:
    """Static triangular grid obstacle deflecting falling balls with multi-layer depth."""

    def __init__(self, x: float, y: float, radius: float = PIN_RADIUS) -> None:
        self.x: float = x
        self.y: float = y
        self.radius: float = radius
        self.flash_timer: float = 0.0

    def update(self, dt: float) -> None:
        """Decay strike flash illumination."""
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def draw(self, screen: pygame.Surface) -> None:
        """Render static pin with drop shadow, metallic core, and impact flash."""
        ix = round(self.x)
        iy = round(self.y)

        # Drop shadow ring beneath pin
        pygame.draw.circle(screen, (10, 14, 22), (ix, iy + 2), int(self.radius + 1.0))

        if self.flash_timer > 0.0:
            # Impact glow bloom
            pygame.draw.circle(screen, (120, 200, 255), (ix, iy), int(self.radius + 3.0))
            pygame.draw.circle(screen, PIN_FLASH_COLOR, (ix, iy), int(self.radius + 1.0))
        else:
            # Crisp pin body and specular dot
            pygame.draw.circle(screen, (70, 85, 110), (ix, iy), int(self.radius + 0.5))
            pygame.draw.circle(screen, PIN_COLOR, (ix, iy), int(self.radius))
            pygame.draw.circle(screen, (245, 250, 255), (ix - 1, iy - 1), max(1, int(self.radius * 0.35)))


class Slot:
    """Bottom scoring bucket with multiplier value, bevel styling, and pulse feedback."""

    def __init__(self, rect: pygame.Rect, multiplier: float) -> None:
        self.rect: pygame.Rect = rect
        self.multiplier: float = multiplier
        self.flash_timer: float = 0.0

        # Tiered visual colors by multiplier range
        if self.multiplier >= 10.0:
            self.base_color: tuple[int, int, int] = (245, 195, 35)  # Radiant gold
            self.text_color: tuple[int, int, int] = (20, 20, 20)
        elif self.multiplier >= 4.0:
            self.base_color = (34, 197, 94)  # Emerald green
            self.text_color = (255, 255, 255)
        elif self.multiplier >= 2.0:
            self.base_color = (249, 115, 22)  # Bright amber
            self.text_color = (255, 255, 255)
        elif self.multiplier >= 0.5:
            self.base_color = (217, 90, 40)  # Warm orange
            self.text_color = (255, 255, 255)
        else:
            self.base_color = (185, 28, 48)  # Crimson for 0x
            self.text_color = (255, 255, 255)

        self.font: pygame.font.Font = pygame.font.SysFont("arial", 13, bold=True)
        label = f"{int(self.multiplier)}x" if self.multiplier == int(self.multiplier) else f"{self.multiplier}x"
        self.text_surf: pygame.Surface = self.font.render(label, True, self.text_color)
        self.text_rect: pygame.Rect = self.text_surf.get_rect(center=self.rect.center)

    def update(self, dt: float) -> None:
        """Decay strike flash illumination."""
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def draw(self, screen: pygame.Surface) -> None:
        """Render beveled rounded bucket with bounce displacement and brightness pulse."""
        # Pulse and slight upward bounce when scored
        bounce_y = -3 if self.flash_timer > 0.08 else 0
        draw_rect = self.rect.move(0, bounce_y)

        if self.flash_timer > 0.0:
            color = (255, 255, 255)
            pygame.draw.rect(screen, color, draw_rect, border_radius=6)
        else:
            color = self.base_color
            # Outer beveled container
            pygame.draw.rect(screen, color, draw_rect, border_radius=6)
            inner_rect = draw_rect.inflate(-4, -4)
            darkened = (max(0, color[0] - 30), max(0, color[1] - 30), max(0, color[2] - 30))
            pygame.draw.rect(screen, darkened, inner_rect, border_radius=4)

        # Reposition text if bounced
        text_pos = self.text_rect.move(0, bounce_y)
        screen.blit(self.text_surf, text_pos)


class FloatingText:
    """Animated text popup that drifts upward and fades out on scoring."""

    def __init__(self, x: float, y: float, text: str, color: tuple[int, int, int], duration: float = 0.85) -> None:
        self.x: float = x
        self.y: float = y
        self.text: str = text
        self.color: tuple[int, int, int] = color
        self.timer: float = duration
        self.max_timer: float = duration

    def update(self, dt: float) -> bool:
        """Advance popup position upward and decay lifetime timer. Returns False when expired."""
        self.timer -= dt
        self.y -= 42.0 * dt
        return self.timer > 0.0

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Render floating text with smooth alpha fadeout."""
        alpha = int(max(0.0, min(1.0, self.timer / self.max_timer)) * 255)
        text_surf = font.render(self.text, True, self.color)
        text_surf.set_alpha(alpha)
        rect = text_surf.get_rect(center=(round(self.x), round(self.y)))
        screen.blit(text_surf, rect)
