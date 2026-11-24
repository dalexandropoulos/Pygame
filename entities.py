import math
import random
import pygame
from config import (
    BALL_RADIUS,
    PIN_RADIUS,
    SPINNER_RADIUS,
    SHOOTER_LANE_WIDTH,
    MIN_LAUNCH_SPEED,
    MAX_LAUNCH_SPEED,
    PLUNGER_CHARGE_RATE,
    DOOR_REQUIRED_BALLS,
    DOOR_OPEN_DURATION,
    ROULETTE_MULTIPLIERS,
    ROULETTE_COLORS,
    ROULETTE_SPIN_TIME,
    INK_OUTLINE,
    BALL_COLOR,
    BALL_CHROME,
    PEG_BLUE,
    PEG_ORANGE,
    PEG_GOLD,
    MULTIBALL_CAPACITY,
)

def create_ball_sprites(radius: float = BALL_RADIUS) -> tuple[pygame.Surface, pygame.Surface]:
    """Generate pre-rendered bold cartoon orb surfaces with 2px ink outlines and curved specular shine."""
    size = int(radius * 2) + 8
    center = (size // 2, size // 2)

    awake_sprite = pygame.Surface((size, size), pygame.SRCALPHA)
    # 2px dark ink outline
    pygame.draw.circle(awake_sprite, INK_OUTLINE, center, int(radius))
    # Vibrant turquoise body with darker bottom rim
    pygame.draw.circle(awake_sprite, (13, 148, 136), center, int(radius - 2))
    pygame.draw.circle(awake_sprite, BALL_COLOR, (center[0] - 1, center[1] - 1), int(radius - 3))
    pygame.draw.circle(awake_sprite, (94, 234, 212), (center[0] - 2, center[1] - 2), int(radius - 5))
    # Crisp white specular curved highlight dot
    hl_pos = (center[0] - int(radius * 0.35), center[1] - int(radius * 0.35))
    pygame.draw.circle(awake_sprite, (255, 255, 255), hl_pos, max(2, int(radius * 0.28)))
    pygame.draw.circle(awake_sprite, (255, 255, 255), (hl_pos[0] + 5, hl_pos[1] - 1), max(1, int(radius * 0.14)))

    # Dormant dark turquoise/slate sprite
    sleep_sprite = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(sleep_sprite, INK_OUTLINE, center, int(radius))
    pygame.draw.circle(sleep_sprite, (15, 118, 110), center, int(radius - 2))
    pygame.draw.circle(sleep_sprite, (45, 120, 115), (center[0] - 1, center[1] - 1), int(radius - 3))
    pygame.draw.circle(sleep_sprite, (204, 251, 241), hl_pos, max(1, int(radius * 0.22)))

    if pygame.display.get_surface() is not None:
        awake_sprite = awake_sprite.convert_alpha()
        sleep_sprite = sleep_sprite.convert_alpha()

    return awake_sprite, sleep_sprite


class Ball:
    """Verlet-integrated dynamic chrome body simulated in 2D space."""

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
        pygame.draw.circle(surface, INK_OUTLINE, center, int(self.radius))
        pygame.draw.circle(surface, BALL_COLOR, center, int(self.radius - 2))


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

    def draw(self, screen: pygame.Surface, color: tuple[int, int, int] = (255, 215, 0), width: int = 5) -> None:
        """Render cartoon rail with ink outline and colored core."""
        p1 = (round(self.x1), round(self.y1))
        p2 = (round(self.x2), round(self.y2))
        pygame.draw.line(screen, INK_OUTLINE, p1, p2, width=width + 3)
        pygame.draw.line(screen, color, p1, p2, width=width)


class OneWayGate:
    """Directional brass flap gate allowing counter-clockwise entrance while blocking backward exit."""

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
        """Render cartoon brass gate with directional hinge indicator."""
        p1 = (round(self.x1), round(self.y1))
        p2 = (round(self.x2), round(self.y2))
        pygame.draw.line(screen, INK_OUTLINE, p1, p2, width=7)
        pygame.draw.line(screen, (245, 158, 11), p1, p2, width=5)
        pygame.draw.line(screen, (254, 240, 138), p1, p2, width=2)
        pygame.draw.circle(screen, INK_OUTLINE, p1, 6)
        pygame.draw.circle(screen, (250, 204, 21), p1, 4)


class SpringPlunger:
    """Variable-power cartoon spring plunger with explicit ball lock and compression feedback."""

    def __init__(self, center_x: float = 765.0, base_y: float = 780.0, lane_width: float = SHOOTER_LANE_WIDTH) -> None:
        self.center_x: float = center_x
        self.base_y: float = base_y
        self.lane_width: float = lane_width
        self.charge: float = 0.0
        self.is_charging: bool = False
        self.loaded_ball: Ball | None = None
        self.max_compression: float = 70.0

    @property
    def head_y(self) -> float:
        """Vertical position of the plunger pusher head based on spring compression."""
        return (self.base_y - 75.0) + self.charge * self.max_compression

    def start_charging(self) -> None:
        """Begin accumulating launcher spring compression."""
        self.is_charging = True

    def stop_charging(self) -> None:
        """Signal release of manual compression."""
        self.is_charging = False

    def update(self, dt: float) -> None:
        """Update spring compression and lock loaded ball directly onto pusher head."""
        if self.is_charging:
            self.charge = min(1.0, self.charge + dt * PLUNGER_CHARGE_RATE)
        else:
            self.charge = max(0.0, self.charge - dt * 6.5)

        if self.loaded_ball is not None:
            self.loaded_ball.x = self.center_x
            self.loaded_ball.y = self.head_y - self.loaded_ball.radius - 1.0
            self.loaded_ball.old_x = self.loaded_ball.x
            self.loaded_ball.old_y = self.loaded_ball.y

    def release_launch(self, sub_dt: float) -> tuple[Ball | None, float]:
        """Release compressed spring, propelling loaded ball upward with calculated launch impulse."""
        self.is_charging = False
        if self.loaded_ball is not None:
            speed = MIN_LAUNCH_SPEED + (MAX_LAUNCH_SPEED - MIN_LAUNCH_SPEED) * self.charge
            launched_ball = self.loaded_ball
            self.loaded_ball = None
            launched_ball.old_x = launched_ball.x
            launched_ball.old_y = launched_ball.y + speed * sub_dt
            self.charge = 0.0
            return launched_ball, speed

        self.charge = 0.0
        return None, 0.0

    def draw(self, screen: pygame.Surface) -> None:
        """Draw chunky cartoon spring coils, red-and-gold pusher head, and vertical power meter."""
        curr_head_y = self.head_y
        head_w = self.lane_width - 8.0
        head_rect = pygame.Rect(round(self.center_x - head_w / 2), round(curr_head_y), round(head_w), 14)

        # Draw thick steel spring coils
        num_coils = 6
        coil_top = curr_head_y + 14.0
        coil_bottom = self.base_y
        step_y = (coil_bottom - coil_top) / max(1, num_coils)
        pts = [(self.center_x, coil_top)]
        for i in range(num_coils):
            offset_x = 10.0 if i % 2 == 0 else -10.0
            pts.append((self.center_x + offset_x, coil_top + (i + 0.5) * step_y))
        pts.append((self.center_x, coil_bottom))
        if len(pts) >= 2:
            pygame.draw.lines(screen, INK_OUTLINE, False, pts, width=6)
            pygame.draw.lines(screen, (203, 213, 225), False, pts, width=4)
            pygame.draw.lines(screen, (255, 255, 255), False, pts, width=1)

        # Draw chunky red-and-gold plunger pusher head
        pygame.draw.rect(screen, INK_OUTLINE, head_rect.inflate(4, 4), border_radius=6)
        pygame.draw.rect(screen, (220, 38, 38), head_rect, border_radius=4)
        gold_accent = head_rect.inflate(-8, -6)
        pygame.draw.rect(screen, (250, 204, 21), gold_accent, border_radius=2)

        # Vertical power gauge beside spring
        meter_x = self.center_x + head_w / 2 + 5.0
        meter_w = 9.0
        meter_h = 110.0
        meter_y = self.base_y - 130.0
        meter_rect = pygame.Rect(round(meter_x), round(meter_y), round(meter_w), round(meter_h))
        pygame.draw.rect(screen, INK_OUTLINE, meter_rect.inflate(4, 4), border_radius=4)
        pygame.draw.rect(screen, (30, 41, 59), meter_rect, border_radius=3)
        if self.charge > 0.0:
            fill_h = meter_h * self.charge
            fill_color = (34, 197, 94) if self.charge < 0.55 else ((234, 179, 8) if self.charge < 0.85 else (239, 68, 68))
            fill_rect = pygame.Rect(round(meter_x), round(meter_y + meter_h - fill_h), round(meter_w), round(fill_h))
            pygame.draw.rect(screen, fill_color, fill_rect, border_radius=3)


class Spinner:
    """Rotating 6-petal cartoon flower pinwheel deflecting balls with spinning tangential kick."""

    def __init__(self, x: float, y: float, radius: float = SPINNER_RADIUS, num_petals: int = 6) -> None:
        self.x: float = x
        self.y: float = y
        self.radius: float = radius
        self.num_petals: int = num_petals
        self.angle: float = random.uniform(0.0, math.tau)
        self.angular_vel: float = 0.0

    def update(self, dt: float) -> None:
        """Advance angular rotation and smoothly damp spin velocity."""
        self.angle += self.angular_vel * dt
        self.angular_vel *= (0.985 ** (dt * 60.0))

    def draw(self, screen: pygame.Surface) -> None:
        """Render 6-petal cartoon pinwheel with dark ink outlines and contrasting petal colors."""
        center = (round(self.x), round(self.y))
        petal_dist = self.radius * 0.62
        petal_r = int(self.radius * 0.44)

        for i in range(self.num_petals):
            a = self.angle + (i * math.tau / self.num_petals)
            px = round(self.x + math.cos(a) * petal_dist)
            py = round(self.y + math.sin(a) * petal_dist)
            color = (244, 114, 182) if i % 2 == 0 else (251, 146, 60)
            pygame.draw.circle(screen, INK_OUTLINE, (px, py), petal_r + 2)
            pygame.draw.circle(screen, color, (px, py), petal_r)
            pygame.draw.circle(screen, (255, 255, 255), (px - 2, py - 2), max(1, int(petal_r * 0.35)))

        # Center brass hubcap
        pygame.draw.circle(screen, INK_OUTLINE, center, int(self.radius * 0.44) + 2)
        pygame.draw.circle(screen, (250, 204, 21), center, int(self.radius * 0.44))
        pygame.draw.circle(screen, (254, 240, 138), (center[0] - 2, center[1] - 2), int(self.radius * 0.22))


class MultiballPocket:
    """Lower tulip catcher pocket that accumulates 3 balls and triggers a 5-ball multiball burst."""

    def __init__(self, x: float, y: float, radius: float = 32.0, capacity: int = MULTIBALL_CAPACITY) -> None:
        self.x: float = x
        self.y: float = y
        self.radius: float = radius
        self.capacity: int = capacity
        self.stored_count: int = 0
        self.flash_timer: float = 0.0

    def update(self, dt: float) -> None:
        """Decay trigger flash illumination."""
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def draw(self, screen: pygame.Surface) -> None:
        """Render golden tulip catcher pocket with 3 illuminated storage pip gems."""
        ix = round(self.x)
        iy = round(self.y)

        rim_color = (255, 255, 255) if self.flash_timer > 0.0 else (245, 158, 11)
        pygame.draw.circle(screen, INK_OUTLINE, (ix, iy), int(self.radius + 4))
        pygame.draw.circle(screen, rim_color, (ix, iy), int(self.radius), width=4)
        pygame.draw.circle(screen, (15, 23, 42), (ix, iy), int(self.radius - 4))

        pip_spacing = 12.0
        pip_start_x = self.x - ((self.capacity - 1) * pip_spacing / 2.0)
        for i in range(self.capacity):
            px = round(pip_start_x + i * pip_spacing)
            py = iy - 2
            if i < self.stored_count:
                pygame.draw.circle(screen, INK_OUTLINE, (px, py), 6)
                pygame.draw.circle(screen, (56, 189, 248), (px, py), 5)
                pygame.draw.circle(screen, (255, 255, 255), (px, py), 2)
            else:
                pygame.draw.circle(screen, INK_OUTLINE, (px, py), 5)
                pygame.draw.circle(screen, (71, 85, 105), (px, py), 4)


class OutHole:
    """Bottom-center drain pocket consuming lost balls."""

    def __init__(self, x: float = 395.0, y: float = 760.0, radius: float = 34.0) -> None:
        self.x: float = x
        self.y: float = y
        self.radius: float = radius
        self.flash_timer: float = 0.0

    def update(self, dt: float) -> None:
        """Decay drain flash illumination."""
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def draw(self, screen: pygame.Surface) -> None:
        """Render drain pocket with hazard warning rim and flashing feedback."""
        ix = round(self.x)
        iy = round(self.y)

        rim_color = (239, 68, 68) if self.flash_timer > 0.0 else (185, 28, 28)
        pygame.draw.circle(screen, INK_OUTLINE, (ix, iy), int(self.radius + 5))
        pygame.draw.circle(screen, rim_color, (ix, iy), int(self.radius), width=4)
        pygame.draw.circle(screen, (3, 7, 18), (ix, iy), int(self.radius - 4))

        font = pygame.font.SysFont("arial", 12, bold=True)
        lbl = font.render("DRAIN", True, (248, 113, 113))
        screen.blit(lbl, lbl.get_rect(center=(ix, iy)))


class Pin:
    """Glossy 3D-shaded Peggle peg with 2px ink outline and specular shine."""

    def __init__(self, x: float, y: float, radius: float = PIN_RADIUS, peg_color: tuple[int, int, int] = PEG_BLUE) -> None:
        self.x: float = x
        self.y: float = y
        self.radius: float = radius
        self.peg_color: tuple[int, int, int] = peg_color
        self.flash_timer: float = 0.0

    def update(self, dt: float) -> None:
        """Decay strike flash illumination."""
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def draw(self, screen: pygame.Surface) -> None:
        """Render glossy 3D-shaded Peggle peg with 2px ink outline and specular reflection."""
        ix = round(self.x)
        iy = round(self.y)

        # Drop shadow
        pygame.draw.circle(screen, (15, 23, 42), (ix, iy + 3), int(self.radius + 1.5))

        if self.flash_timer > 0.0:
            pygame.draw.circle(screen, (255, 255, 255), (ix, iy), int(self.radius + 4.0))
            pygame.draw.circle(screen, self.peg_color, (ix, iy), int(self.radius + 2.0))
        else:
            # 2px dark ink outline
            pygame.draw.circle(screen, INK_OUTLINE, (ix, iy), int(self.radius + 1.5))
            pygame.draw.circle(screen, self.peg_color, (ix, iy), int(self.radius))
            # Inner gradient ring
            inner_hl = (min(255, self.peg_color[0] + 50), min(255, self.peg_color[1] + 50), min(255, self.peg_color[2] + 50))
            pygame.draw.circle(screen, inner_hl, (ix - 1, iy - 1), max(2, int(self.radius * 0.65)))
            # Specular dot
            hl_x = ix - int(self.radius * 0.35)
            hl_y = iy - int(self.radius * 0.35)
            pygame.draw.circle(screen, (255, 255, 255), (hl_x, hl_y), max(2, int(self.radius * 0.32)))


class Particle:
    """Lightweight celebratory golden sparkle particle with gravity and fadeout."""

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        color: tuple[int, int, int],
        size: float = 4.0,
        life: float = 0.9,
    ) -> None:
        self.x: float = x
        self.y: float = y
        self.vx: float = vx
        self.vy: float = vy
        self.color: tuple[int, int, int] = color
        self.size: float = size
        self.life: float = life
        self.max_life: float = life

    def update(self, dt: float) -> bool:
        """Advance particle movement and return False once life expires."""
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 320.0 * dt
        self.vx *= (0.97 ** (dt * 60.0))
        return self.life > 0.0

    def draw(self, screen: pygame.Surface) -> None:
        """Render glowing sparkle dot."""
        ratio = max(0.0, min(1.0, self.life / self.max_life))
        cur_r = max(1, int(self.size * ratio))
        pygame.draw.circle(screen, self.color, (round(self.x), round(self.y)), cur_r)


class SeesawTrapdoor:
    """Hinged cartoon seesaw secret door tilted by ball weight to unlock the Yakumono entrance."""

    def __init__(self, x: float = 395.0, y: float = 315.0, beam_width: float = 68.0) -> None:
        self.x: float = x
        self.y: float = y
        self.beam_width: float = beam_width
        self.stored_balls: int = 0
        self.tilt_angle: float = 0.0
        self.is_open: bool = False
        self.open_timer: float = 0.0
        self.flash_timer: float = 0.0
        self.cradle_radius: float = 26.0

    def get_wall_segment(self) -> WallSegment | None:
        """Return blocking line segment when closed, or None when swung open."""
        if self.is_open:
            return None
        cos_a = math.cos(self.tilt_angle)
        sin_a = math.sin(self.tilt_angle)
        half_w = self.beam_width * 0.5
        x1 = self.x - cos_a * half_w
        y1 = self.y - sin_a * half_w
        x2 = self.x + cos_a * half_w
        y2 = self.y + sin_a * half_w
        return WallSegment(x1, y1, x2, y2)

    def add_ball(self) -> bool:
        """Add ball weight, return True if the door unlocks open."""
        self.stored_balls = min(DOOR_REQUIRED_BALLS, self.stored_balls + 1)
        self.flash_timer = 0.3
        if self.stored_balls >= DOOR_REQUIRED_BALLS:
            self.is_open = True
            self.open_timer = DOOR_OPEN_DURATION
            self.flash_timer = 0.9
            return True
        return False

    def close(self) -> None:
        """Reset door to closed position with empty cradle."""
        self.is_open = False
        self.stored_balls = 0
        self.open_timer = 0.0
        self.tilt_angle = 0.0

    def update(self, dt: float) -> None:
        """Update swing angle, open duration timer, and flash feedback."""
        if self.is_open:
            self.open_timer = max(0.0, self.open_timer - dt)
            target = math.radians(72.0)
            if self.open_timer <= 0.0:
                self.close()
        else:
            target = self.stored_balls * math.radians(11.5)

        self.tilt_angle += (target - self.tilt_angle) * min(1.0, dt * 14.0)

        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def draw(self, screen: pygame.Surface) -> None:
        """Render cartoon seesaw fulcrum pivot, tilted beam, weight pips, and open indicator."""
        ix = round(self.x)
        iy = round(self.y)

        # Fulcrum triangular base with ink outline
        base_pts = [(ix, iy), (ix - 12, iy + 16), (ix + 12, iy + 16)]
        pygame.draw.polygon(screen, INK_OUTLINE, [(p[0], p[1] + 1) for p in base_pts])
        pygame.draw.polygon(screen, (71, 85, 105), base_pts)
        pygame.draw.circle(screen, INK_OUTLINE, (ix, iy), 6)
        pygame.draw.circle(screen, (245, 158, 11), (ix, iy), 4)

        # Beam endpoints
        cos_a = math.cos(self.tilt_angle)
        sin_a = math.sin(self.tilt_angle)
        half_w = self.beam_width * 0.5
        p1 = (round(self.x - cos_a * half_w), round(self.y - sin_a * half_w))
        p2 = (round(self.x + cos_a * half_w), round(self.y + sin_a * half_w))

        beam_color = (255, 255, 255) if self.flash_timer > 0.0 else ((34, 197, 94) if self.is_open else (250, 204, 21))
        pygame.draw.line(screen, INK_OUTLINE, p1, p2, width=8)
        pygame.draw.line(screen, beam_color, p1, p2, width=6)
        pygame.draw.circle(screen, INK_OUTLINE, p1, 6)
        pygame.draw.circle(screen, (254, 240, 138), p1, 4)
        pygame.draw.circle(screen, INK_OUTLINE, p2, 6)
        pygame.draw.circle(screen, (254, 240, 138), p2, 4)

        # Weight indicator pips
        pip_spacing = 13.0
        pip_start_x = self.x - ((DOOR_REQUIRED_BALLS - 1) * pip_spacing / 2.0)
        pip_y = iy - 18
        for i in range(DOOR_REQUIRED_BALLS):
            px = round(pip_start_x + i * pip_spacing)
            if self.is_open:
                pygame.draw.circle(screen, INK_OUTLINE, (px, pip_y), 6)
                pygame.draw.circle(screen, (34, 197, 94), (px, pip_y), 5)
                pygame.draw.circle(screen, (255, 255, 255), (px, pip_y), 2)
            elif i < self.stored_balls:
                pygame.draw.circle(screen, INK_OUTLINE, (px, pip_y), 6)
                pygame.draw.circle(screen, (250, 204, 21), (px, pip_y), 5)
                pygame.draw.circle(screen, (255, 255, 255), (px, pip_y), 2)
            else:
                pygame.draw.circle(screen, INK_OUTLINE, (px, pip_y), 5)
                pygame.draw.circle(screen, (51, 65, 85), (px, pip_y), 4)


class YakumonoRoulette:
    """Central dome centerpiece housing the 8-slice Multiplier Roulette wheel."""

    def __init__(self, x: float = 395.0, y: float = 415.0, radius: float = 70.0) -> None:
        self.x: float = x
        self.y: float = y
        self.radius: float = radius
        self.funnel_y: float = y - radius + 10.0
        self.funnel_radius: float = 28.0

        self.is_spinning: bool = False
        self.wheel_angle: float = 0.0
        self.angular_speed: float = 0.0
        self.spin_timer: float = 0.0
        self.initial_spin_time: float = ROULETTE_SPIN_TIME
        self.last_win_mult: int = 0
        self.last_win_text: str = ""
        self.win_flash_timer: float = 0.0

        self.font: pygame.font.Font = pygame.font.SysFont("arial", 13, bold=True)
        self.fever_font: pygame.font.Font = pygame.font.SysFont("arial", 18, bold=True)

    def start_spin(self) -> None:
        """Trigger rapid roulette spin cycle."""
        self.is_spinning = True
        self.spin_timer = ROULETTE_SPIN_TIME
        self.initial_spin_time = ROULETTE_SPIN_TIME
        self.angular_speed = random.uniform(26.0, 36.0)
        self.last_win_mult = 0
        self.last_win_text = ""
        self.win_flash_timer = 0.0

    def update(self, dt: float) -> int | None:
        """Advance wheel rotation, apply smooth deceleration, and return multiplier when finished."""
        if self.is_spinning:
            self.wheel_angle = (self.wheel_angle + self.angular_speed * dt) % math.tau
            self.spin_timer = max(0.0, self.spin_timer - dt)
            self.angular_speed *= (0.988 ** (dt * 60.0))

            if self.spin_timer <= 0.0 or self.angular_speed < 0.25:
                self.is_spinning = False
                self.angular_speed = 0.0

                num_slices = len(ROULETTE_MULTIPLIERS)
                slice_arc = math.tau / num_slices
                rel_angle = (-math.pi * 0.5 - self.wheel_angle) % math.tau
                winning_idx = int(rel_angle // slice_arc) % num_slices
                winning_mult = ROULETTE_MULTIPLIERS[winning_idx]
                self.last_win_mult = winning_mult
                self.last_win_text = f"{winning_mult}x"
                self.win_flash_timer = 2.2
                return winning_mult

        if self.win_flash_timer > 0.0:
            self.win_flash_timer = max(0.0, self.win_flash_timer - dt)

        return None

    def draw(self, screen: pygame.Surface) -> None:
        """Render 8-slice roulette wheel, numbers, pointer needle, and celebration feedback."""
        cx = round(self.x)
        cy = round(self.y)
        r = int(self.radius)

        pygame.draw.circle(screen, INK_OUTLINE, (cx, cy + 4), r + 8)
        pygame.draw.circle(screen, (180, 83, 9), (cx, cy), r + 6)
        pygame.draw.circle(screen, (245, 158, 11), (cx, cy), r + 4, width=3)
        pygame.draw.circle(screen, (254, 240, 138), (cx, cy), r + 2, width=1)

        num_slices = len(ROULETTE_MULTIPLIERS)
        slice_arc = math.tau / num_slices
        arc_steps = 7

        for i in range(num_slices):
            a1 = self.wheel_angle + i * slice_arc
            a2 = a1 + slice_arc
            pts = [(cx, cy)]
            for s in range(arc_steps + 1):
                t = s / arc_steps
                ang = a1 + t * (a2 - a1)
                pts.append((cx + round(math.cos(ang) * (r - 2)), cy + round(math.sin(ang) * (r - 2))))
            color = ROULETTE_COLORS[i % len(ROULETTE_COLORS)]
            pygame.draw.polygon(screen, color, pts)
            pygame.draw.polygon(screen, INK_OUTLINE, pts, width=1)

            mid_a = a1 + slice_arc * 0.5
            text_dist = r * 0.62
            tx = cx + round(math.cos(mid_a) * text_dist)
            ty = cy + round(math.sin(mid_a) * text_dist)
            lbl = self.font.render(f"{ROULETTE_MULTIPLIERS[i]}x", True, (255, 255, 255))
            screen.blit(lbl, lbl.get_rect(center=(tx, ty)))

        # Golden center boss medallion
        pygame.draw.circle(screen, INK_OUTLINE, (cx, cy), 22)
        pygame.draw.circle(screen, (217, 119, 6), (cx, cy), 20)
        pygame.draw.circle(screen, (250, 204, 21), (cx, cy), 17)
        pygame.draw.circle(screen, (254, 240, 138), (cx - 2, cy - 2), 6)

        if self.win_flash_timer > 0.0:
            flash_lbl = self.fever_font.render(self.last_win_text, True, (255, 255, 255))
            screen.blit(flash_lbl, flash_lbl.get_rect(center=(cx, cy)))

        # Top clicker needle pointing downward with ink outline
        needle_top = (cx, cy - r - 6)
        needle_left = (cx - 7, cy - r + 8)
        needle_right = (cx + 7, cy - r + 8)
        needle_tip = (cx, cy - r + 15)
        pygame.draw.polygon(screen, INK_OUTLINE, [needle_top, needle_left, needle_tip, needle_right])
        pygame.draw.polygon(screen, (254, 240, 138), [(needle_top[0], needle_top[1] + 1), (needle_left[0] + 1, needle_left[1]), (needle_tip[0], needle_tip[1] - 1), (needle_right[0] - 1, needle_right[1])])


class FloatingText:
    """Animated text popup drifting upward with smooth alpha fadeout."""

    def __init__(self, x: float, y: float, text: str, color: tuple[int, int, int], duration: float = 0.85) -> None:
        self.x: float = x
        self.y: float = y
        self.text: str = text
        self.color: tuple[int, int, int] = color
        self.timer: float = duration
        self.max_timer: float = duration

    def update(self, dt: float) -> bool:
        """Advance position upward and decay timer."""
        self.timer -= dt
        self.y -= 44.0 * dt
        return self.timer > 0.0

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        """Render floating text with alpha fade."""
        alpha = int(max(0.0, min(1.0, self.timer / self.max_timer)) * 255)
        text_surf = font.render(self.text, True, self.color)
        text_surf.set_alpha(alpha)
        rect = text_surf.get_rect(center=(round(self.x), round(self.y)))
        screen.blit(text_surf, rect)
