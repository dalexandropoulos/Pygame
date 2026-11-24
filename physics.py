import math
import pygame
from entities import Ball, Pin, WallSegment
from config import (
    GRAVITY,
    SUB_STEPS,
    RESTITUTION,
    PIN_RESTITUTION,
    WALL_RESTITUTION,
    SURFACE_FRICTION,
    AIR_DRAG,
    SCREEN_WIDTH,
    GRID_CELL_SIZE,
    SLEEP_SPEED_THRESHOLD,
    SLEEP_TIME_REQUIRED,
)

class SpatialGrid:
    """Broad-phase spatial partition dividing 2D space into discrete grid buckets."""

    def __init__(self, cell_size: float = GRID_CELL_SIZE) -> None:
        self.cell_size: float = cell_size
        self.cells: dict[tuple[int, int], list[Ball]] = {}

    def clear(self) -> None:
        """Clear all bucket contents."""
        self.cells.clear()

    def insert(self, ball: Ball) -> None:
        """Map ball into corresponding grid bucket based on position."""
        cell_coord = (int(ball.x // self.cell_size), int(ball.y // self.cell_size))
        if cell_coord not in self.cells:
            self.cells[cell_coord] = [ball]
        else:
            self.cells[cell_coord].append(ball)

    def rebuild(self, balls: list[Ball]) -> None:
        """Repopulate grid buckets with updated ball coordinates."""
        self.cells.clear()
        for ball in balls:
            self.insert(ball)


class PhysicsEngine:
    """Position-Based Dynamics (Verlet) solver managing gravity, pins, rails, dividers, and collisions."""

    def __init__(
        self,
        gravity: float = GRAVITY,
        sub_steps: int = SUB_STEPS,
        restitution: float = RESTITUTION,
        pin_restitution: float = PIN_RESTITUTION,
        wall_restitution: float = WALL_RESTITUTION,
        surface_friction: float = SURFACE_FRICTION,
        air_drag: float = AIR_DRAG,
        screen_width: float = float(SCREEN_WIDTH),
        use_spatial_grid: bool = True,
        sleep_speed_threshold: float = SLEEP_SPEED_THRESHOLD,
        sleep_time_required: float = SLEEP_TIME_REQUIRED,
    ) -> None:
        self.gravity: float = gravity
        self.sub_steps: int = sub_steps
        self.restitution: float = restitution
        self.pin_restitution: float = pin_restitution
        self.wall_restitution: float = wall_restitution
        self.surface_friction: float = surface_friction
        self.air_drag: float = air_drag
        self.screen_width: float = screen_width
        self.use_spatial_grid: bool = use_spatial_grid
        self.sleep_speed_threshold: float = sleep_speed_threshold
        self.sleep_time_required: float = sleep_time_required
        self.grid: SpatialGrid = SpatialGrid()
        self.pins: list[Pin] = []
        self.walls: list[WallSegment] = []
        self.divider_x_coords: list[float] = []

    def update(self, balls: list[Ball], dt: float) -> None:
        """Advance simulation using Position-Based Dynamics across discrete sub-steps."""
        if dt <= 0.0 or not balls:
            return

        sub_dt = dt / float(self.sub_steps)
        gravity_step = self.gravity * sub_dt * sub_dt

        for _ in range(self.sub_steps):
            self._sub_step(balls, sub_dt, gravity_step)

        self._update_sleep_states(balls, dt, sub_dt)

    def _sub_step(self, balls: list[Ball], sub_dt: float, gravity_step: float) -> None:
        """Execute one Verlet PBD integration step for positions, pin bounces, contacts, and bounds."""
        # 1. Integrate position using Verlet displacement with air drag and gravity
        for b in balls:
            if not b.is_sleeping:
                vx = (b.x - b.old_x) * self.air_drag
                vy = (b.y - b.old_y) * self.air_drag + gravity_step
                b.old_x, b.old_y = b.x, b.y
                b.x += vx
                b.y += vy

        # 2. Solve static pin deflections
        self._resolve_pin_collisions(balls, self.pins, sub_dt)

        # 3. Solve inter-ball collisions with cascade wake-up
        if self.use_spatial_grid:
            self._resolve_collisions_spatial(balls, sub_dt)
        else:
            self._resolve_collisions_naive(balls, sub_dt)

        # 4. Solve rigid line-segment containment walls (angled side rails)
        self._resolve_wall_collisions(balls, self.walls, sub_dt)

        # 5. Solve vertical channel dividers and screen boundaries
        self._resolve_divider_collisions(balls, sub_dt)
        self._resolve_boundary_collisions(balls, sub_dt)

    def _resolve_wall_collisions(self, balls: list[Ball], walls: list[WallSegment], sub_dt: float) -> None:
        """Resolve dynamic ball collisions against angled and vertical rigid line-segment rails."""
        if not balls or not walls:
            return

        refl_factor = 1.0 + self.wall_restitution

        for ball in balls:
            if ball.is_sleeping:
                continue

            bx = ball.x
            by = ball.y
            br = ball.radius
            br_sq = br * br

            for wall in walls:
                wpx = bx - wall.x1
                wpy = by - wall.y1

                # Project ball center onto segment clamped to [0.0, 1.0]
                t = (wpx * wall.dx + wpy * wall.dy) * wall.inv_len_sq
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0

                cx = wall.x1 + t * wall.dx
                cy = wall.y1 + t * wall.dy

                sep_x = bx - cx
                sep_y = by - cy
                dist_sq = sep_x * sep_x + sep_y * sep_y

                if dist_sq >= br_sq:
                    continue

                dist = math.sqrt(dist_sq) if dist_sq > 1e-8 else 1e-4
                if dist < 1e-4:
                    inv_len = math.sqrt(wall.inv_len_sq)
                    nx = -wall.dy * inv_len
                    ny = wall.dx * inv_len
                    dist = 1.0
                else:
                    inv_dist = 1.0 / dist
                    nx = sep_x * inv_dist
                    ny = sep_y * inv_dist

                overlap = br - dist
                ball.x += nx * overlap
                ball.y += ny * overlap

                # Reflect Verlet step velocity along collision normal
                vx = ball.x - ball.old_x
                vy = ball.y - ball.old_y
                vn = vx * nx + vy * ny

                if vn < 0.0:
                    refl_mag = -refl_factor * vn
                    ball.old_x -= nx * refl_mag
                    ball.old_y -= ny * refl_mag

                # Tangential surface friction
                tx = -ny
                ty = nx
                vt = vx * tx + vy * ty
                fric_shift = vt * self.surface_friction
                ball.old_x += tx * fric_shift
                ball.old_y += ty * fric_shift

    def _resolve_pin_collisions(self, balls: list[Ball], pins: list[Pin], sub_dt: float) -> None:
        """Resolve dynamic ball collisions against static circular board pins."""
        if not balls or not pins:
            return

        refl_factor = 1.0 + self.pin_restitution

        for ball in balls:
            if ball.is_sleeping:
                continue

            bx = ball.x
            by = ball.y
            br = ball.radius

            for pin in pins:
                dx = bx - pin.x
                dy = by - pin.y
                min_dist = br + pin.radius

                if abs(dx) > min_dist or abs(dy) > min_dist:
                    continue

                dist_sq = dx * dx + dy * dy
                if dist_sq >= min_dist * min_dist:
                    continue

                dist = math.sqrt(dist_sq) if dist_sq > 1e-8 else 1e-4
                if dist < 1e-4:
                    nx = 0.0
                    ny = -1.0
                    dist = 1.0
                else:
                    inv_dist = 1.0 / dist
                    nx = dx * inv_dist
                    ny = dy * inv_dist

                overlap = min_dist - dist
                ball.x += nx * overlap
                ball.y += ny * overlap

                pin.flash_timer = 0.12

                vx = ball.x - ball.old_x
                vy = ball.y - ball.old_y
                vn = vx * nx + vy * ny

                if vn < 0.0:
                    refl_mag = -refl_factor * vn
                    ball.old_x -= nx * refl_mag
                    ball.old_y -= ny * refl_mag

                tx = -ny
                ty = nx
                vt = vx * tx + vy * ty
                fric_shift = vt * self.surface_friction
                ball.old_x += tx * fric_shift
                ball.old_y += ty * fric_shift

    def _resolve_divider_collisions(self, balls: list[Ball], sub_dt: float) -> None:
        """Confine balls to entered slot channels by resolving vertical dividers."""
        y_top = 480.0

        for ball in balls:
            if ball.is_sleeping or ball.y < y_top - ball.radius:
                continue

            for div_x in self.divider_x_coords:
                dx = ball.x - div_x
                if abs(dx) >= ball.radius:
                    continue

                if ball.y >= y_top:
                    if dx < 0.0:
                        ball.x = div_x - ball.radius
                        vx = ball.x - ball.old_x
                        if vx > 0.0:
                            ball.old_x = ball.x + self.restitution * vx
                    else:
                        ball.x = div_x + ball.radius
                        vx = ball.x - ball.old_x
                        if vx < 0.0:
                            ball.old_x = ball.x - self.restitution * abs(vx)
                else:
                    dy = ball.y - y_top
                    dist_sq = dx * dx + dy * dy
                    if dist_sq < ball.radius * ball.radius:
                        dist = math.sqrt(dist_sq) if dist_sq > 1e-8 else 1e-4
                        nx = dx / dist
                        ny = dy / dist
                        overlap = ball.radius - dist
                        ball.x += nx * overlap
                        ball.y += ny * overlap

    def _resolve_boundary_collisions(self, balls: list[Ball], sub_dt: float) -> None:
        """Constrain bodies within screen bounds as fallback containment."""
        min_x = 0.0
        max_x = self.screen_width

        for ball in balls:
            if ball.is_sleeping:
                continue

            if ball.x - ball.radius < min_x:
                ball.x = min_x + ball.radius
                vx = ball.x - ball.old_x
                if vx < 0.0:
                    ball.old_x = ball.x - self.wall_restitution * vx

            elif ball.x + ball.radius > max_x:
                ball.x = max_x - ball.radius
                vx = ball.x - ball.old_x
                if vx > 0.0:
                    ball.old_x = ball.x - self.wall_restitution * vx

    def _resolve_collisions_spatial(self, balls: list[Ball], sub_dt: float) -> None:
        """Resolve ball-ball contacts using spatial partitioning."""
        self.grid.rebuild(balls)
        checked_pairs: set[tuple[int, int]] = set()

        for cell_coord, cell_balls in self.grid.cells.items():
            cx, cy = cell_coord
            for i in range(len(cell_balls)):
                b1 = cell_balls[i]
                id1 = id(b1)

                for j in range(i + 1, len(cell_balls)):
                    b2 = cell_balls[j]
                    id2 = id(b2)
                    pair_key = (id1, id2) if id1 < id2 else (id2, id1)
                    if pair_key not in checked_pairs:
                        checked_pairs.add(pair_key)
                        self._resolve_pair(b1, b2, sub_dt)

                for nx in (cx + 1,):
                    for ny in (cy - 1, cy, cy + 1):
                        neighbor_balls = self.grid.cells.get((nx, ny))
                        if neighbor_balls:
                            for b2 in neighbor_balls:
                                id2 = id(b2)
                                pair_key = (id1, id2) if id1 < id2 else (id2, id1)
                                if pair_key not in checked_pairs:
                                    checked_pairs.add(pair_key)
                                    self._resolve_pair(b1, b2, sub_dt)

                neighbor_balls = self.grid.cells.get((cx, cy + 1))
                if neighbor_balls:
                    for b2 in neighbor_balls:
                        id2 = id(b2)
                        pair_key = (id1, id2) if id1 < id2 else (id2, id1)
                        if pair_key not in checked_pairs:
                            checked_pairs.add(pair_key)
                            self._resolve_pair(b1, b2, sub_dt)

    def _resolve_collisions_naive(self, balls: list[Ball], sub_dt: float) -> None:
        """Resolve ball-ball contacts using brute-force pair iteration."""
        n = len(balls)
        for i in range(n):
            b1 = balls[i]
            for j in range(i + 1, n):
                self._resolve_pair(b1, balls[j], sub_dt)

    def _resolve_pair(self, b1: Ball, b2: Ball, sub_dt: float) -> None:
        """Resolve overlap, momentum transfer, and contact friction between two dynamic bodies."""
        if b1.is_sleeping and b2.is_sleeping:
            return

        dx = b1.x - b2.x
        dy = b1.y - b2.y
        min_dist = b1.radius + b2.radius

        if abs(dx) > min_dist or abs(dy) > min_dist:
            return

        dist_sq = dx * dx + dy * dy
        if dist_sq >= min_dist * min_dist or dist_sq <= 1e-8:
            return

        dist = math.sqrt(dist_sq)
        inv_dist = 1.0 / dist
        nx = dx * inv_dist
        ny = dy * inv_dist
        overlap = min_dist - dist

        # Wake up sleeping partner on dynamic contact
        if b1.is_sleeping:
            b1.wake()
        if b2.is_sleeping:
            b2.wake()

        # Positional displacement
        half_overlap = overlap * 0.5
        b1.x += nx * half_overlap
        b1.y += ny * half_overlap
        b2.x -= nx * half_overlap
        b2.y -= ny * half_overlap

        # Restitution along normal
        v1x = b1.x - b1.old_x
        v1y = b1.y - b1.old_y
        v2x = b2.x - b2.old_x
        v2y = b2.y - b2.old_y

        rel_vx = v1x - v2x
        rel_vy = v1y - v2y
        vn = rel_vx * nx + rel_vy * ny

        if vn < 0.0:
            refl_mag = -(1.0 + self.restitution) * vn * 0.5
            b1.old_x -= nx * refl_mag
            b1.old_y -= ny * refl_mag
            b2.old_x += nx * refl_mag
            b2.old_y += ny * refl_mag

        # Tangential surface friction
        tx = -ny
        ty = nx
        vt = rel_vx * tx + rel_vy * ty
        fric_shift = vt * self.surface_friction * 0.5
        b1.old_x += tx * fric_shift
        b1.old_y += ty * fric_shift
        b2.old_x -= tx * fric_shift
        b2.old_y -= ty * fric_shift

    def _update_sleep_states(self, balls: list[Ball], dt: float, sub_dt: float) -> None:
        """Update body dormancy timer and deactivate stationary entities."""
        inv_sub_dt = 1.0 / sub_dt
        thresh_disp = self.sleep_speed_threshold * sub_dt
        thresh_disp_sq = thresh_disp * thresh_disp

        for ball in balls:
            dx = ball.x - ball.old_x
            dy = ball.y - ball.old_y
            disp_sq = dx * dx + dy * dy

            if disp_sq < thresh_disp_sq:
                ball.sleep_timer += dt
                if ball.sleep_timer >= self.sleep_time_required:
                    ball.is_sleeping = True
                    ball.old_x = ball.x
                    ball.old_y = ball.y
            else:
                ball.sleep_timer = 0.0
                ball.is_sleeping = False
