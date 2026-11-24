import math
import pygame
from entities import Ball, Pin, WallSegment, OneWayGate, Spinner, SeesawTrapdoor, YakumonoRoulette
from config import (
    GRAVITY,
    SUB_STEPS,
    RESTITUTION,
    PIN_RESTITUTION,
    WALL_RESTITUTION,
    SURFACE_FRICTION,
    AIR_DRAG,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    ARENA_CENTER_X,
    ARENA_CENTER_Y,
    ARENA_RADIUS,
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
    """Position-Based Dynamics (Verlet) solver managing circular arena, pins, spinners, seesaw door, and Yakumono."""

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
        screen_height: float = float(SCREEN_HEIGHT),
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
        self.screen_height: float = screen_height
        self.use_spatial_grid: bool = use_spatial_grid
        self.sleep_speed_threshold: float = sleep_speed_threshold
        self.sleep_time_required: float = sleep_time_required

        self.arena_cx: float = ARENA_CENTER_X
        self.arena_cy: float = ARENA_CENTER_Y
        self.arena_radius: float = ARENA_RADIUS

        self.grid: SpatialGrid = SpatialGrid()
        self.pins: list[Pin] = []
        self.spinners: list[Spinner] = []
        self.walls: list[WallSegment] = []
        self.gate: OneWayGate | None = None
        self.seesaw: SeesawTrapdoor | None = None
        self.yakumono: YakumonoRoulette | None = None

    def update(self, balls: list[Ball], dt: float, exclude_ball: Ball | None = None) -> None:
        """Advance simulation using Position-Based Dynamics across discrete sub-steps."""
        if dt <= 0.0 or not balls:
            return

        active_balls = [b for b in balls if b is not exclude_ball]
        if not active_balls:
            return

        sub_dt = dt / float(self.sub_steps)
        gravity_step = self.gravity * sub_dt * sub_dt

        for _ in range(self.sub_steps):
            self._sub_step(active_balls, sub_dt, gravity_step)

        self._update_sleep_states(active_balls, dt, sub_dt)

    def _sub_step(self, balls: list[Ball], sub_dt: float, gravity_step: float) -> None:
        """Execute one Verlet PBD integration step across all bodies, obstacles, and secret doors."""
        # 1. Integrate position using Verlet displacement with air drag and gravity
        for b in balls:
            if not b.is_sleeping:
                vx = (b.x - b.old_x) * self.air_drag
                vy = (b.y - b.old_y) * self.air_drag + gravity_step
                b.old_x, b.old_y = b.x, b.y
                b.x += vx
                b.y += vy

        # 2. Solve static circular arena outer containment
        self._resolve_circular_arena(balls, sub_dt)

        # 3. Solve static pin deflections
        self._resolve_pin_collisions(balls, self.pins, sub_dt)

        # 4. Solve rotating flower spinner kicks and deflections
        self._resolve_spinner_collisions(balls, self.spinners, sub_dt)

        # 5. Solve Seesaw Secret Door blocking beam (only when closed)
        if self.seesaw is not None:
            seesaw_seg = self.seesaw.get_wall_segment()
            if seesaw_seg is not None:
                self._resolve_wall_collisions(balls, [seesaw_seg], sub_dt)

        # 6. Solve central Yakumono dome bumper collisions (outside top funnel)
        if self.yakumono is not None:
            self._resolve_yakumono_collision(balls, self.yakumono, sub_dt)

        # 7. Solve rigid wall segments (shooter lane, dividers, guides)
        self._resolve_wall_collisions(balls, self.walls, sub_dt)

        # 8. Solve directional one-way brass gate
        if self.gate is not None:
            self._resolve_gate_collision(balls, self.gate, sub_dt)

        # 9. Solve inter-ball collisions with cascade wake-up
        if self.use_spatial_grid:
            self._resolve_collisions_spatial(balls, sub_dt)
        else:
            self._resolve_collisions_naive(balls, sub_dt)

        # 10. Absolute boundary fallback
        self._resolve_boundary_collisions(balls, sub_dt)

    def _resolve_circular_arena(self, balls: list[Ball], sub_dt: float) -> None:
        """Confine dynamic bodies within circular cabinet boundary, respecting shooter entry and drain gaps."""
        cx = self.arena_cx
        cy = self.arena_cy
        r = self.arena_radius
        refl_factor = 1.0 + self.wall_restitution

        for ball in balls:
            if ball.is_sleeping:
                continue

            dx = ball.x - cx
            dy = ball.y - cy
            dist_sq = dx * dx + dy * dy
            limit_r = r - ball.radius

            if dist_sq < limit_r * limit_r:
                continue

            # Allow ball to enter via top-left entrance opening
            if ball.y < cy - 250.0 and (ball.x < cx - 40.0):
                continue

            # Allow ball to exit through bottom-center drain hole
            if ball.y > cy + r - 35.0 and abs(ball.x - cx) < 46.0:
                continue

            dist = math.sqrt(dist_sq) if dist_sq > 1e-8 else 1e-4
            inv_dist = 1.0 / dist
            nx = dx * inv_dist
            ny = dy * inv_dist

            overlap = dist - limit_r
            ball.x -= nx * overlap
            ball.y -= ny * overlap

            vx = ball.x - ball.old_x
            vy = ball.y - ball.old_y
            vn = vx * nx + vy * ny

            if vn > 0.0:
                refl_mag = -refl_factor * vn
                ball.old_x -= nx * refl_mag
                ball.old_y -= ny * refl_mag

            tx = -ny
            ty = nx
            vt = vx * tx + vy * ty
            fric_shift = vt * self.surface_friction
            ball.old_x += tx * fric_shift
            ball.old_y += ty * fric_shift

    def _resolve_yakumono_collision(self, balls: list[Ball], yak: YakumonoRoulette, sub_dt: float) -> None:
        """Resolve dynamic bounces off the central Yakumono dome, keeping the top funnel open for entry."""
        for ball in balls:
            if ball.is_sleeping:
                continue

            # Top funnel receptor opening (accessible when door is open)
            if ball.y < yak.y - 25.0 and abs(ball.x - yak.x) < 30.0:
                continue

            dx = ball.x - yak.x
            dy = ball.y - yak.y
            min_dist = yak.radius + ball.radius
            dist_sq = dx * dx + dy * dy

            if dist_sq >= min_dist * min_dist or dist_sq <= 1e-8:
                continue

            dist = math.sqrt(dist_sq)
            inv_dist = 1.0 / dist
            nx = dx * inv_dist
            ny = dy * inv_dist
            overlap = min_dist - dist

            ball.x += nx * overlap
            ball.y += ny * overlap

            vx = ball.x - ball.old_x
            vy = ball.y - ball.old_y
            vn = vx * nx + vy * ny

            if vn < 0.0:
                refl_mag = -(1.0 + self.pin_restitution) * vn
                ball.old_x -= nx * refl_mag
                ball.old_y -= ny * refl_mag

            tx = -ny
            ty = nx
            vt = vx * tx + vy * ty
            fric_shift = vt * self.surface_friction
            ball.old_x += tx * fric_shift
            ball.old_y += ty * fric_shift

    def _resolve_spinner_collisions(self, balls: list[Ball], spinners: list[Spinner], sub_dt: float) -> None:
        """Resolve dynamic collisions against rotating flower wheels with spin deflection."""
        if not balls or not spinners:
            return

        for ball in balls:
            if ball.is_sleeping:
                continue

            bx = ball.x
            by = ball.y
            br = ball.radius

            for sp in spinners:
                dx = bx - sp.x
                dy = by - sp.y
                min_dist = br + sp.radius

                if abs(dx) > min_dist or abs(dy) > min_dist:
                    continue

                dist_sq = dx * dx + dy * dy
                if dist_sq >= min_dist * min_dist:
                    continue

                dist = math.sqrt(dist_sq) if dist_sq > 1e-8 else 1e-4
                inv_dist = 1.0 / dist
                nx = dx * inv_dist
                ny = dy * inv_dist

                overlap = min_dist - dist
                ball.x += nx * overlap
                ball.y += ny * overlap

                vx = ball.x - ball.old_x
                vy = ball.y - ball.old_y
                vn = vx * nx + vy * ny

                if vn < 0.0:
                    refl_mag = -(1.0 + self.wall_restitution) * vn
                    ball.old_x -= nx * refl_mag
                    ball.old_y -= ny * refl_mag

                tx = -ny
                ty = nx
                vt = vx * tx + vy * ty

                spin_impulse = vt * 0.35
                if abs(spin_impulse) < 2.0:
                    spin_impulse = 18.0 if (dx * vy - dy * vx) >= 0.0 else -18.0
                sp.angular_vel = max(-45.0, min(45.0, sp.angular_vel + spin_impulse))

                spin_kick = sp.angular_vel * sp.radius * 0.06
                ball.old_x -= tx * spin_kick
                ball.old_y -= ty * spin_kick

    def _resolve_gate_collision(self, balls: list[Ball], gate: OneWayGate, sub_dt: float) -> None:
        """Allow counter-clockwise entrance into the arena while acting as a rigid block against backward exit."""
        refl_factor = 1.0 + self.wall_restitution

        for ball in balls:
            if ball.is_sleeping:
                continue

            vx = ball.x - ball.old_x
            if vx < -1.0:
                continue

            wpx = ball.x - gate.x1
            wpy = ball.y - gate.y1
            t = max(0.0, min(1.0, (wpx * gate.dx + wpy * gate.dy) * gate.inv_len_sq))

            cx = gate.x1 + t * gate.dx
            cy = gate.y1 + t * gate.dy
            sep_x = ball.x - cx
            sep_y = ball.y - cy
            dist_sq = sep_x * sep_x + sep_y * sep_y

            if dist_sq >= ball.radius * ball.radius:
                continue

            dist = math.sqrt(dist_sq) if dist_sq > 1e-8 else 1e-4
            inv_dist = 1.0 / dist
            nx = sep_x * inv_dist
            ny = sep_y * inv_dist

            overlap = ball.radius - dist
            ball.x += nx * overlap
            ball.y += ny * overlap

            vy = ball.y - ball.old_y
            vn = vx * nx + vy * ny
            if vn < 0.0:
                refl_mag = -refl_factor * vn
                ball.old_x -= nx * refl_mag
                ball.old_y -= ny * refl_mag

    def _resolve_wall_collisions(self, balls: list[Ball], walls: list[WallSegment], sub_dt: float) -> None:
        """Resolve dynamic ball collisions against rigid line-segment walls."""
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

                pin.flash_timer = 0.14

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

    def _resolve_boundary_collisions(self, balls: list[Ball], sub_dt: float) -> None:
        """Constrain bodies within screen bounds as fallback containment."""
        min_x = 0.0
        max_x = self.screen_width
        max_y = self.screen_height + 40.0

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

        if b1.is_sleeping:
            b1.wake()
        if b2.is_sleeping:
            b2.wake()

        half_overlap = overlap * 0.5
        b1.x += nx * half_overlap
        b1.y += ny * half_overlap
        b2.x -= nx * half_overlap
        b2.y -= ny * half_overlap

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
