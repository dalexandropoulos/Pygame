import math
import pygame
from entities import Ball
from config import (
    GRAVITY,
    SUB_STEPS,
    RESTITUTION,
    DAMPING,
    SCREEN_WIDTH,
    FLOOR_Y,
)

class PhysicsEngine:
    """Physics solver managing gravity, sub-stepped numerical integration, and collision responses."""

    def __init__(
        self,
        gravity: pygame.math.Vector2 = GRAVITY,
        sub_steps: int = SUB_STEPS,
        restitution: float = RESTITUTION,
        damping: float = DAMPING,
        screen_width: float = float(SCREEN_WIDTH),
        floor_y: float = FLOOR_Y,
    ) -> None:
        self.gravity: pygame.math.Vector2 = pygame.math.Vector2(gravity)
        self.sub_steps: int = sub_steps
        self.restitution: float = restitution
        self.damping: float = damping
        self.screen_width: float = screen_width
        self.floor_y: float = floor_y

    def update(self, balls: list[Ball], dt: float) -> None:
        """Advance simulation over multiple discrete sub-steps for stacking stability."""
        if dt <= 0.0 or not balls:
            return

        sub_dt = dt / float(self.sub_steps)
        for _ in range(self.sub_steps):
            self._sub_step(balls, sub_dt)

    def _sub_step(self, balls: list[Ball], sub_dt: float) -> None:
        """Execute one integration step, solving forces, positions, and contact constraints."""
        # Integrate linear acceleration and update positions
        for ball in balls:
            ball.velocity += self.gravity * sub_dt
            ball.update(sub_dt)

        # Resolve inter-ball contacts and containment boundaries
        self._resolve_ball_collisions(balls)
        self._resolve_boundary_collisions(balls)

    def _resolve_ball_collisions(self, balls: list[Ball]) -> None:
        """Detect and resolve pairwise circle overlaps and impulse exchanges."""
        num_balls = len(balls)
        for i in range(num_balls):
            ball_a = balls[i]
            for j in range(i + 1, num_balls):
                ball_b = balls[j]
                delta = ball_b.position - ball_a.position
                dist_sq = delta.length_squared()
                min_dist = ball_a.radius + ball_b.radius

                if dist_sq >= min_dist * min_dist:
                    continue

                dist = math.sqrt(dist_sq)
                if dist < 1e-4:
                    delta = pygame.math.Vector2(0.0, -1.0)
                    dist = 1.0

                normal = delta / dist
                penetration = min_dist - dist
                total_inv_mass = ball_a.inv_mass + ball_b.inv_mass
                if total_inv_mass <= 0.0:
                    continue

                # Positional correction along contact normal proportional to inverse mass
                correction = normal * (penetration / total_inv_mass)
                ball_a.position -= correction * ball_a.inv_mass
                ball_b.position += correction * ball_b.inv_mass

                # Compute relative velocity and project onto contact normal
                rel_vel = ball_b.velocity - ball_a.velocity
                normal_vel = rel_vel.dot(normal)
                if normal_vel >= 0.0:
                    continue

                # Apply restitution above resting threshold to suppress settling jitter
                effective_restitution = self.restitution if abs(normal_vel) > 20.0 else 0.0
                impulse_mag = -(1.0 + effective_restitution) * normal_vel / total_inv_mass
                impulse = normal * impulse_mag

                ball_a.velocity -= impulse * ball_a.inv_mass
                ball_b.velocity += impulse * ball_b.inv_mass

                # Dampen tangential motion across collision plane to model friction
                tangent_vel = rel_vel - normal * normal_vel
                tangent_impulse = tangent_vel * (1.0 - self.damping) / total_inv_mass
                ball_a.velocity += tangent_impulse * ball_a.inv_mass
                ball_b.velocity -= tangent_impulse * ball_b.inv_mass

    def _resolve_boundary_collisions(self, balls: list[Ball]) -> None:
        """Enforce screen perimeter barriers and solid floor contact physics."""
        for ball in balls:
            # Floor collision
            if ball.position.y + ball.radius > self.floor_y:
                penetration = (ball.position.y + ball.radius) - self.floor_y
                ball.position.y -= penetration
                if ball.velocity.y > 0.0:
                    restitution = self.restitution if ball.velocity.y > 20.0 else 0.0
                    ball.velocity.y = -ball.velocity.y * restitution
                    ball.velocity.x *= self.damping
                    if abs(ball.velocity.y) < 1.0:
                        ball.velocity.y = 0.0

            # Left wall collision
            if ball.position.x - ball.radius < 0.0:
                penetration = ball.radius - ball.position.x
                ball.position.x += penetration
                if ball.velocity.x < 0.0:
                    restitution = self.restitution if abs(ball.velocity.x) > 20.0 else 0.0
                    ball.velocity.x = -ball.velocity.x * restitution
                    ball.velocity.y *= self.damping

            # Right wall collision
            if ball.position.x + ball.radius > self.screen_width:
                penetration = (ball.position.x + ball.radius) - self.screen_width
                ball.position.x -= penetration
                if ball.velocity.x > 0.0:
                    restitution = self.restitution if abs(ball.velocity.x) > 20.0 else 0.0
                    ball.velocity.x = -ball.velocity.x * restitution
                    ball.velocity.y *= self.damping
