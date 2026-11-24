import math
import random
import pygame
from entities import Ball, Pin, Slot, WallSegment, FloatingText, create_ball_sprites
from physics import PhysicsEngine
from config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    BALL_RADIUS,
    PIN_RADIUS,
    PIN_ROWS,
    PIN_SPACING_X,
    PIN_SPACING_Y,
    RAIL_OFFSET_X,
    STARTING_BALANCE,
    BALL_COST,
    DROP_COOLDOWN,
    SLOT_MULTIPLIERS,
    BG_COLOR,
    BOARD_BG_COLOR,
    RAIL_COLOR,
    RAIL_GLOW_COLOR,
)

class SimulationScreen:
    """Coordinates Pachinko board geometry, rails, wagering lifecycle, visual effects, and HUD."""

    def __init__(self) -> None:
        self.balls: list[Ball] = []
        self.pins: list[Pin] = []
        self.slots: list[Slot] = []
        self.walls: list[WallSegment] = []
        self.floating_texts: list[FloatingText] = []
        self.board_polygon: list[tuple[int, int]] = []
        self.physics_engine: PhysicsEngine = PhysicsEngine()

        self.balance: float = STARTING_BALANCE
        self.drop_cooldown_timer: float = 0.0
        self.space_held: bool = False
        self.anim_time: float = 0.0

        self.hud_font: pygame.font.Font = pygame.font.SysFont("arial", 18, bold=True)
        self.popup_font: pygame.font.Font = pygame.font.SysFont("arial", 16, bold=True)
        self.awake_sprite, self.sleep_sprite = create_ball_sprites(BALL_RADIUS)
        self.sprite_offset: float = float((int(BALL_RADIUS * 2) + 4) // 2)

        self._build_board()

    def _build_board(self) -> None:
        """Construct triangular pin pyramid, seamless side rails, slots, and trapezoid background."""
        self.pins.clear()
        self.slots.clear()
        self.walls.clear()

        # Triangular pin layout starting at y = 95 with 3 pins on row 0 to 12 pins on row 9
        start_y = 95.0
        for row in range(PIN_ROWS):
            num_pins = row + 3
            row_width = (num_pins - 1) * PIN_SPACING_X
            start_x = (float(SCREEN_WIDTH) / 2.0) - (row_width / 2.0)
            py = start_y + row * PIN_SPACING_Y
            for col in range(num_pins):
                px = start_x + col * PIN_SPACING_X
                self.pins.append(Pin(x=px, y=py, radius=PIN_RADIUS))

        # Bottom row geometry
        row9_num_pins = (PIN_ROWS - 1) + 3
        row9_width = (row9_num_pins - 1) * PIN_SPACING_X
        row9_start_x = (float(SCREEN_WIDTH) / 2.0) - (row9_width / 2.0)
        row9_end_x = row9_start_x + row9_width
        row9_y = start_y + (PIN_ROWS - 1) * PIN_SPACING_Y

        # Rail coordinates parallel to outer pins offset outward by RAIL_OFFSET_X
        # Outer left pins: (348.0, 95.0) -> (114.0, 455.0)
        # Outer right pins: (452.0, 95.0) -> (686.0, 455.0)
        # Slope dx/dy = -234.0 / 360.0 = -0.65
        top_rail_y = 65.0
        # Line from (348, 95) at y=65: x = 348 + (65 - 95)*(-0.65) = 367.5 -> offset by 34 = 333.5
        rail_top_lx = (348.0 + (top_rail_y - start_y) * (-0.65)) - RAIL_OFFSET_X
        rail_top_rx = (452.0 - (top_rail_y - start_y) * (-0.65)) + RAIL_OFFSET_X

        rail_bot_lx = row9_start_x - RAIL_OFFSET_X  # 114.0 - 34.0 = 80.0
        rail_bot_rx = row9_end_x + RAIL_OFFSET_X    # 686.0 + 34.0 = 720.0
        slot_floor_y = 590.0
        slot_y = 544
        slot_height = 46

        # 1. Dropper funnel neck rails
        self.walls.append(WallSegment(380.0, 34.0, rail_top_lx, top_rail_y))
        self.walls.append(WallSegment(420.0, 34.0, rail_top_rx, top_rail_y))

        # 2. Angled side containment rails
        self.walls.append(WallSegment(rail_top_lx, top_rail_y, rail_bot_lx, row9_y))
        self.walls.append(WallSegment(rail_top_rx, top_rail_y, rail_bot_rx, row9_y))

        # 3. Vertical drop rails to floor
        self.walls.append(WallSegment(rail_bot_lx, row9_y, rail_bot_lx, slot_floor_y))
        self.walls.append(WallSegment(rail_bot_rx, row9_y, rail_bot_rx, slot_floor_y))

        # Closed board polygon background
        self.board_polygon = [
            (380, 34),
            (420, 34),
            (round(rail_top_rx), round(top_rail_y)),
            (round(rail_bot_rx), round(row9_y)),
            (round(rail_bot_rx), round(slot_floor_y)),
            (round(rail_bot_lx), round(slot_floor_y)),
            (round(rail_bot_lx), round(row9_y)),
            (round(rail_top_lx), round(top_rail_y)),
        ]

        # 11 bottom slots: widen outer 10x slots to meet vertical rails seamlessly
        for i, mult in enumerate(SLOT_MULTIPLIERS):
            gap_left = row9_start_x + i * PIN_SPACING_X
            gap_right = gap_left + PIN_SPACING_X

            if i == 0:
                # Widen left edge to meet left vertical rail at rail_bot_lx (80.0)
                s_left = int(rail_bot_lx) + 2
                s_width = int(gap_right - rail_bot_lx) - 4
            elif i == len(SLOT_MULTIPLIERS) - 1:
                # Widen right edge to meet right vertical rail at rail_bot_rx (720.0)
                s_left = int(gap_left) + 2
                s_width = int(rail_bot_rx - gap_left) - 4
            else:
                s_left = int(gap_left) + 2
                s_width = int(PIN_SPACING_X) - 4

            slot_rect = pygame.Rect(s_left, slot_y, s_width, slot_height)
            self.slots.append(Slot(rect=slot_rect, multiplier=mult))

        # Divider x coordinates separating the 11 slots
        divider_x_coords = [row9_start_x + i * PIN_SPACING_X for i in range(row9_num_pins)]
        self.physics_engine.pins = self.pins
        self.physics_engine.walls = self.walls
        self.physics_engine.divider_x_coords = divider_x_coords

    def _try_drop_ball(self) -> None:
        """Deduct ball cost and release a single ball from top nozzle if affordable."""
        if self.drop_cooldown_timer <= 0.0 and self.balance >= BALL_COST:
            self.balance -= BALL_COST
            self.drop_cooldown_timer = DROP_COOLDOWN
            drop_x = (float(SCREEN_WIDTH) / 2.0) + random.uniform(-4.0, 4.0)
            drop_y = 44.0
            self.balls.append(Ball(x=drop_x, y=drop_y, radius=BALL_RADIUS))

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process keyboard wagering inputs and board controls."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.space_held = True
                self._try_drop_ball()
            elif event.key == pygame.K_r:
                self.balls.clear()
                self.floating_texts.clear()
                self.balance = STARTING_BALANCE
            elif event.key == pygame.K_o:
                self.physics_engine.use_spatial_grid = not self.physics_engine.use_spatial_grid
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE:
                self.space_held = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._try_drop_ball()

    def update(self, dt: float) -> None:
        """Step cooldowns, entity animations, physics, popups, and prize payouts."""
        self.anim_time += dt

        if self.drop_cooldown_timer > 0.0:
            self.drop_cooldown_timer = max(0.0, self.drop_cooldown_timer - dt)

        if self.space_held:
            self._try_drop_ball()

        for pin in self.pins:
            pin.update(dt)
        for slot in self.slots:
            slot.update(dt)

        self.physics_engine.update(self.balls, dt)

        # Update floating payout texts
        self.floating_texts = [ft for ft in self.floating_texts if ft.update(dt)]

        # Evaluate score payout upon ball entry into slot buckets
        surviving_balls: list[Ball] = []
        for ball in self.balls:
            scored = False
            for slot in self.slots:
                if slot.rect.collidepoint(ball.x, ball.y):
                    payout = BALL_COST * slot.multiplier
                    self.balance += payout
                    slot.flash_timer = 0.25
                    scored = True

                    # Spawn floating payout popup
                    if payout >= 10.0 and payout == int(payout):
                        txt = f"+€{int(payout)}"
                    elif payout > 0.0:
                        txt = f"+€{payout:.2f}"
                    else:
                        txt = "€0"
                    self.floating_texts.append(
                        FloatingText(x=ball.x, y=float(slot.rect.top - 6), text=txt, color=slot.base_color)
                    )
                    break

            if not scored and ball.y < float(SCREEN_HEIGHT) + 20.0:
                surviving_balls.append(ball)

        self.balls = surviving_balls

    def render(self, surface: pygame.Surface, fps: float = 0.0) -> None:
        """Render dark slate background, neon board rails, dropper nozzle, entities, and HUD."""
        surface.fill(BG_COLOR)

        # Draw inner board polygon
        if len(self.board_polygon) >= 3:
            pygame.draw.polygon(surface, BOARD_BG_COLOR, self.board_polygon)

        # Draw glowing containment rails
        for wall in self.walls:
            wall.draw(surface)

        # Draw slot containers
        for slot in self.slots:
            slot.draw(surface)

        # Draw channel dividers between adjacent buckets
        for div_x in self.physics_engine.divider_x_coords:
            pygame.draw.line(surface, (70, 85, 115), (div_x, 485), (div_x, 590), width=2)
            pygame.draw.circle(surface, (120, 140, 175), (round(div_x), 485), 3)

        # Draw board pins
        for pin in self.pins:
            pin.draw(surface)

        # Render top dropper nozzle with pulsing readiness indicator
        self._render_dropper_nozzle(surface)

        # Batch blit shaded dynamic balls
        offset = self.sprite_offset
        blit_batch = [(self.awake_sprite, (b.x - offset, b.y - offset)) for b in self.balls]
        if blit_batch:
            surface.blits(blit_batch)

        # Draw floating payout popups
        for ft in self.floating_texts:
            ft.draw(surface, self.popup_font)

        self._render_hud(surface, fps)

    def _render_dropper_nozzle(self, surface: pygame.Surface) -> None:
        """Render metallic top-center dropper housing with animated drop-ready status light."""
        center_x = SCREEN_WIDTH // 2
        nozzle_rect = pygame.Rect(center_x - 22, 24, 44, 22)

        # Metallic housing
        pygame.draw.rect(surface, (30, 40, 60), nozzle_rect, border_radius=6)
        pygame.draw.rect(surface, (56, 189, 248), nozzle_rect, width=2, border_radius=6)

        # Pulsing status LED
        ready = self.drop_cooldown_timer <= 0.0 and self.balance >= BALL_COST
        if ready:
            pulse = (math.sin(self.anim_time * 8.0) + 1.0) * 0.5
            glow_r = int(4.0 + pulse * 2.0)
            pygame.draw.circle(surface, (34, 197, 94), (center_x, 35), glow_r)
            pygame.draw.circle(surface, (187, 247, 208), (center_x, 35), 2)
        else:
            pygame.draw.circle(surface, (239, 68, 68), (center_x, 35), 4)

    def _render_hud(self, surface: pygame.Surface, fps: float) -> None:
        """Render compact, stylized top-left status card with balance, wager, and controls."""
        hud_rect = pygame.Rect(14, 14, 240, 86)
        # Semi-transparent dark card background
        card_surf = pygame.Surface((hud_rect.width, hud_rect.height), pygame.SRCALPHA)
        card_surf.fill((18, 24, 38, 220))
        surface.blit(card_surf, hud_rect.topleft)
        pygame.draw.rect(surface, (45, 60, 90), hud_rect, width=1, border_radius=8)

        # Balance coloring
        if self.balance >= STARTING_BALANCE:
            bal_color = (74, 222, 128)  # Bright neon emerald
        elif self.balance > 0.0:
            bal_color = (250, 204, 21)  # Radiant amber
        else:
            bal_color = (248, 113, 113)  # Bright red

        fps_val = int(round(fps))
        fps_color = (74, 222, 128) if fps >= 55.0 else ((250, 204, 21) if fps >= 30.0 else (248, 113, 113))

        bal_surf = self.hud_font.render(f"Balance: €{self.balance:.2f}", True, bal_color)
        bet_surf = self.hud_font.render("Bet: €5", True, (203, 213, 225))
        guide_surf = pygame.font.SysFont("arial", 13, bold=True).render("[SPACE / CLICK] Drop  |  [R] Reset", True, (148, 163, 184))
        fps_surf = pygame.font.SysFont("arial", 13, bold=True).render(f"FPS: {fps_val}", True, fps_color)

        surface.blit(bal_surf, (hud_rect.x + 12, hud_rect.y + 10))
        surface.blit(bet_surf, (hud_rect.x + 12, hud_rect.y + 35))
        surface.blit(guide_surf, (hud_rect.x + 12, hud_rect.y + 60))
        surface.blit(fps_surf, (hud_rect.right - 62, hud_rect.y + 12))
