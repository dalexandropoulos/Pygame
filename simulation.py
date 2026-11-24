import math
import random
import pygame
from board_io import BoardData, BoardManager
from entities import (
    Ball,
    Pin,
    WallSegment,
    OneWayGate,
    SpringPlunger,
    Spinner,
    MultiballPocket,
    OutHole,
    FloatingText,
    Particle,
    SeesawTrapdoor,
    YakumonoRoulette,
    create_ball_sprites,
)
from physics import PhysicsEngine
from config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    ARENA_CENTER_X,
    ARENA_CENTER_Y,
    ARENA_RADIUS,
    BALL_RADIUS,
    PIN_RADIUS,
    SPINNER_RADIUS,
    SHOOTER_LANE_WIDTH,
    STARTING_BALANCE,
    BALL_COST,
    FPS,
    SUB_STEPS,
    MULTIBALL_CAPACITY,
    MULTIBALL_BURST_COUNT,
    CABINET_BG,
    BOARD_SKY_TOP,
    BOARD_MEADOW_BOTTOM,
    PEG_BLUE,
    PEG_ORANGE,
    PEG_GREEN,
    PEG_PURPLE,
    PEG_GOLD,
    INK_OUTLINE,
)

class SimulationScreen:
    """Coordinates vintage circular Pachinko playfield from a data-driven BoardData model."""

    def __init__(self, board_data: BoardData | None = None) -> None:
        if board_data is None:
            manager = BoardManager()
            default_path = manager.ensure_default_board()
            board_data = manager.load_board(default_path)

        self.board_data: BoardData = board_data
        self.wants_exit_to_menu: bool = False

        self.balls: list[Ball] = []
        self.pins: list[Pin] = []
        self.spinners: list[Spinner] = []
        self.pockets: list[MultiballPocket] = []
        self.walls: list[WallSegment] = []
        self.out_hole: OutHole = OutHole(x=ARENA_CENTER_X, y=ARENA_CENTER_Y + ARENA_RADIUS - 10.0, radius=34.0)
        self.plunger: SpringPlunger = SpringPlunger(center_x=765.0, base_y=790.0, lane_width=SHOOTER_LANE_WIDTH)
        self.seesaw: SeesawTrapdoor = SeesawTrapdoor(x=ARENA_CENTER_X, y=315.0, beam_width=68.0)
        self.yakumono: YakumonoRoulette = YakumonoRoulette(x=ARENA_CENTER_X, y=415.0, radius=70.0)
        self.floating_texts: list[FloatingText] = []
        self.particles: list[Particle] = []
        self.physics_engine: PhysicsEngine = PhysicsEngine()

        self.balance: float = STARTING_BALANCE
        self.space_held: bool = False
        self.anim_time: float = 0.0

        self.hud_font: pygame.font.Font = pygame.font.SysFont("arial", 18, bold=True)
        self.popup_font: pygame.font.Font = pygame.font.SysFont("arial", 16, bold=True)
        self.awake_sprite, self.sleep_sprite = create_ball_sprites(BALL_RADIUS)
        self.sprite_offset: float = float((int(BALL_RADIUS * 2) + 8) // 2)

        self._arena_surf = pygame.Surface((int(ARENA_RADIUS * 2), int(ARENA_RADIUS * 2)), pygame.SRCALPHA)
        self._draw_arena_background()

        self._build_board()

    def _draw_arena_background(self) -> None:
        """Render two-tone Peggle sky-to-meadow circular playfield texture with dark ink border."""
        r = int(ARENA_RADIUS)
        cx, cy = r, r

        pygame.draw.circle(self._arena_surf, BOARD_MEADOW_BOTTOM, (cx, cy), r)
        pygame.draw.circle(self._arena_surf, BOARD_SKY_TOP, (cx, cy), r)

        meadow_pts = [(0, cy + 40)]
        for x in range(0, r * 2 + 1, 10):
            y_offset = math.sin(x * 0.015) * 25.0
            meadow_pts.append((x, cy + 40 + y_offset))
        meadow_pts.extend([(r * 2, r * 2), (0, r * 2)])
        pygame.draw.polygon(self._arena_surf, BOARD_MEADOW_BOTTOM, meadow_pts)

        mask_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(mask_surf, (255, 255, 255, 255), (cx, cy), r)
        self._arena_surf.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)

    def _build_board(self) -> None:
        """Instantiate all playfield entities from the active BoardData schema."""
        self.pins.clear()
        self.spinners.clear()
        self.pockets.clear()

        color_map = {
            "blue": PEG_BLUE,
            "orange": PEG_ORANGE,
            "gold": PEG_GOLD,
            "green": PEG_GREEN,
            "purple": PEG_PURPLE,
        }

        # 1. Pins
        for p in self.board_data.pins:
            col = color_map.get(p.get("color_type", "blue"), PEG_BLUE)
            self.pins.append(Pin(x=float(p["x"]), y=float(p["y"]), radius=PIN_RADIUS, peg_color=col))

        # 2. Spinners
        for s in self.board_data.spinners:
            self.spinners.append(Spinner(x=float(s["x"]), y=float(s["y"]), radius=SPINNER_RADIUS))

        # 3. Wall segments
        self.walls: list[WallSegment] = []
        for w in self.board_data.walls:
            self.walls.append(WallSegment(x1=float(w["x1"]), y1=float(w["y1"]), x2=float(w["x2"]), y2=float(w["y2"])))

        # 4. Multiball tulip pockets
        for pk in self.board_data.multiball_pockets:
            self.pockets.append(MultiballPocket(x=float(pk["x"]), y=float(pk["y"]), radius=32.0, capacity=MULTIBALL_CAPACITY))

        # 5. Out hole drain
        if self.board_data.out_holes:
            oh_x = float(self.board_data.out_holes[0]["x"])
            oh_y = float(self.board_data.out_holes[0]["y"])
        else:
            oh_x = ARENA_CENTER_X
            oh_y = ARENA_CENTER_Y + ARENA_RADIUS - 10.0
        self.out_hole = OutHole(x=oh_x, y=oh_y, radius=34.0)

        # 6. Spring plunger
        pl_x = float(self.board_data.plunger.get("x", 765.0))
        pl_y = float(self.board_data.plunger.get("y", 790.0))
        self.plunger = SpringPlunger(center_x=pl_x, base_y=pl_y, lane_width=SHOOTER_LANE_WIDTH)

        # 7. Seesaw secret door
        sd_x = float(self.board_data.secret_door.get("x", 395.0))
        sd_y = float(self.board_data.secret_door.get("y", 315.0))
        self.seesaw = SeesawTrapdoor(x=sd_x, y=sd_y, beam_width=68.0)

        # 8. Yakumono roulette wheel
        yk_x = float(self.board_data.yakumono.get("x", 395.0))
        yk_y = float(self.board_data.yakumono.get("y", 415.0))
        self.yakumono = YakumonoRoulette(x=yk_x, y=yk_y, radius=70.0)

        # 9. One-way brass flap gate spanning shooter chute exit
        gate = OneWayGate(79.5, 214.2, 177.7, 176.1)

        self.physics_engine.pins = self.pins
        self.physics_engine.spinners = self.spinners
        self.physics_engine.walls = self.walls
        self.physics_engine.gate = gate
        self.physics_engine.seesaw = self.seesaw
        self.physics_engine.yakumono = self.yakumono

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process plunger charging, manual release, test drop, ESC exit, and reset controls."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.wants_exit_to_menu = True

            elif event.key in (pygame.K_SPACE, pygame.K_DOWN):
                self.space_held = True
                if self.plunger.loaded_ball is None and self.balance >= BALL_COST:
                    self.balance -= BALL_COST
                    new_b = Ball(x=self.plunger.center_x, y=self.plunger.head_y - BALL_RADIUS - 1.0, radius=BALL_RADIUS)
                    self.plunger.loaded_ball = new_b
                    self.balls.append(new_b)
                self.plunger.start_charging()

            elif event.key == pygame.K_t:
                if self.balance >= BALL_COST:
                    self.balance -= BALL_COST
                test_b = Ball(x=ARENA_CENTER_X + random.uniform(-0.5, 0.5), y=240.0, radius=BALL_RADIUS)
                self.balls.append(test_b)

            elif event.key == pygame.K_r:
                self.balls.clear()
                self.floating_texts.clear()
                self.particles.clear()
                self.plunger.loaded_ball = None
                self.plunger.charge = 0.0
                self.plunger.is_charging = False
                self.seesaw.close()
                self.yakumono.is_spinning = False
                self.yakumono.win_flash_timer = 0.0
                for p in self.pockets:
                    p.stored_count = 0
                self.balance = STARTING_BALANCE

            elif event.key == pygame.K_o:
                self.physics_engine.use_spatial_grid = not self.physics_engine.use_spatial_grid

        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_SPACE, pygame.K_DOWN):
                self.space_held = False
                sub_dt = 1.0 / (float(FPS) * float(SUB_STEPS))
                self.plunger.release_launch(sub_dt)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.plunger.loaded_ball is None and self.balance >= BALL_COST:
                self.balance -= BALL_COST
                new_b = Ball(x=self.plunger.center_x, y=self.plunger.head_y - BALL_RADIUS - 1.0, radius=BALL_RADIUS)
                self.plunger.loaded_ball = new_b
                self.balls.append(new_b)
            self.plunger.start_charging()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            sub_dt = 1.0 / (float(FPS) * float(SUB_STEPS))
            self.plunger.release_launch(sub_dt)

    def update(self, dt: float) -> None:
        """Advance plunger, seesaw door, roulette, physics, sensor captures, and celebration effects."""
        self.anim_time += dt

        self.plunger.update(dt)
        self.seesaw.update(dt)

        win_mult = self.yakumono.update(dt)
        if win_mult is not None:
            payout = BALL_COST * float(win_mult)
            self.balance += payout
            self.floating_texts.append(
                FloatingText(x=self.yakumono.x, y=self.yakumono.y - 30.0, text=f"FEVER! +€{int(payout)}", color=(250, 204, 21), duration=2.2)
            )
            for _ in range(40):
                ang = random.uniform(0.0, math.tau)
                spd = random.uniform(80.0, 240.0)
                col = random.choice([(250, 204, 21), (254, 240, 138), (251, 191, 36), (255, 255, 255)])
                self.particles.append(
                    Particle(
                        x=self.yakumono.x,
                        y=self.yakumono.y,
                        vx=math.cos(ang) * spd,
                        vy=math.sin(ang) * spd,
                        color=col,
                        size=random.uniform(3.0, 5.5),
                        life=random.uniform(0.7, 1.2),
                    )
                )

        for pin in self.pins:
            pin.update(dt)
        for sp in self.spinners:
            sp.update(dt)
        for pocket in self.pockets:
            pocket.update(dt)
        self.out_hole.update(dt)

        self.physics_engine.update(self.balls, dt, exclude_ball=self.plunger.loaded_ball)

        self.floating_texts = [ft for ft in self.floating_texts if ft.update(dt)]
        self.particles = [pt for pt in self.particles if pt.update(dt)]

        surviving_balls: list[Ball] = []
        for ball in self.balls:
            if ball is self.plunger.loaded_ball:
                surviving_balls.append(ball)
                continue

            captured = False

            # 1. Check Seesaw Trapdoor cradle capture (when closed)
            if not self.seesaw.is_open:
                if abs(ball.x - self.seesaw.x) <= 30.0 and 270.0 <= ball.y <= self.seesaw.y + 12.0:
                    captured = True
                    just_opened = self.seesaw.add_ball()
                    if just_opened:
                        self.floating_texts.append(
                            FloatingText(x=self.seesaw.x, y=self.seesaw.y - 25.0, text="SECRET DOOR OPEN!", color=(250, 204, 21), duration=1.6)
                        )
                    else:
                        self.floating_texts.append(
                            FloatingText(
                                x=self.seesaw.x,
                                y=self.seesaw.y - 20.0,
                                text=f"+1 WEIGHT ({self.seesaw.stored_balls}/3)",
                                color=(56, 189, 248),
                                duration=0.8,
                            )
                        )
                    continue

            # 2. Check Yakumono top funnel capture (when door is open)
            if self.seesaw.is_open and not self.yakumono.is_spinning:
                if abs(ball.x - self.yakumono.x) <= 28.0 and 340.0 <= ball.y <= 395.0:
                    captured = True
                    self.seesaw.close()
                    self.yakumono.start_spin()
                    self.floating_texts.append(
                        FloatingText(x=self.yakumono.x, y=self.yakumono.y - 40.0, text="ROULETTE ACTIVATED!", color=(250, 204, 21), duration=1.4)
                    )
                    continue

            # 3. Check Multiball tulip pockets
            for pocket in self.pockets:
                dx = ball.x - pocket.x
                dy = ball.y - pocket.y
                if dx * dx + dy * dy < pocket.radius * pocket.radius:
                    captured = True
                    pocket.stored_count += 1
                    pocket.flash_timer = 0.25

                    if pocket.stored_count >= pocket.capacity:
                        pocket.stored_count = 0
                        pocket.flash_timer = 0.6
                        self.balance += 15.0
                        self.floating_texts.append(
                            FloatingText(x=pocket.x, y=pocket.y - 25.0, text="+€15 MULTIBALL!", color=(250, 204, 21), duration=1.2)
                        )
                        self._trigger_multiball_burst()
                    else:
                        self.floating_texts.append(
                            FloatingText(x=pocket.x, y=pocket.y - 20.0, text=f"+1 BALL ({pocket.stored_count}/3)", color=(56, 189, 248))
                        )
                    break

            if captured:
                continue

            # 4. Check OutHole drain pocket
            odx = ball.x - self.out_hole.x
            ody = ball.y - self.out_hole.y
            if odx * odx + ody * ody < self.out_hole.radius * self.out_hole.radius:
                self.out_hole.flash_timer = 0.3
                self.floating_texts.append(
                    FloatingText(x=self.out_hole.x, y=self.out_hole.y - 20.0, text="-€5 DRAIN", color=(248, 113, 113), duration=0.8)
                )
                continue

            if ball.y < float(SCREEN_HEIGHT) + 30.0:
                surviving_balls.append(ball)

        self.balls = surviving_balls

    def _trigger_multiball_burst(self) -> None:
        """Spawn 5 shiny chrome balls cascading down from upper-center arena."""
        sub_dt = 1.0 / (float(FPS) * float(SUB_STEPS))
        spawn_x = ARENA_CENTER_X
        spawn_y = ARENA_CENTER_Y - 240.0

        for i in range(MULTIBALL_BURST_COUNT):
            fan_vx = (i - 2.0) * 110.0
            fan_vy = random.uniform(80.0, 150.0)
            bx = spawn_x + (i - 2.0) * 16.0
            by = spawn_y + random.uniform(-10.0, 10.0)
            b = Ball(x=bx, y=by, radius=BALL_RADIUS)
            b.old_x = bx - fan_vx * sub_dt
            b.old_y = by - fan_vy * sub_dt
            self.balls.append(b)

    def render(self, surface: pygame.Surface, fps: float = 0.0) -> None:
        """Render cabinet frame, Peggle circular playfield, rainbow, badge, entities, and HUD."""
        surface.fill(CABINET_BG)

        # 1. Circular arena playfield
        arena_topleft = (int(ARENA_CENTER_X - ARENA_RADIUS), int(ARENA_CENTER_Y - ARENA_RADIUS))
        surface.blit(self._arena_surf, arena_topleft)

        pygame.draw.circle(surface, INK_OUTLINE, (round(ARENA_CENTER_X), round(ARENA_CENTER_Y)), int(ARENA_RADIUS + 5), width=7)
        pygame.draw.circle(surface, (217, 119, 6), (round(ARENA_CENTER_X), round(ARENA_CENTER_Y)), int(ARENA_RADIUS + 3), width=4)
        pygame.draw.circle(surface, (254, 240, 138), (round(ARENA_CENTER_X), round(ARENA_CENTER_Y)), int(ARENA_RADIUS), width=2)

        # 2. Decorative Peggle rainbow arc in top-left corner
        self._render_rainbow(surface)

        # 3. Glossy "13" cabinet badge in top-right corner
        self._render_badge_13(surface)

        # 4. Clear translucent shooter tube with animated neon chevrons
        self._render_shooter_tube(surface)

        # 5. Central Yakumono Multiplier Roulette
        self.yakumono.draw(surface)

        # 6. Seesaw Secret Door guarding Yakumono entrance
        self.seesaw.draw(surface)

        # 7. Wall segments and shooter lane rails
        for w in self.physics_engine.walls:
            w.draw(surface, color=(245, 158, 11), width=5)

        # One-way brass gate
        if self.physics_engine.gate is not None:
            self.physics_engine.gate.draw(surface)

        # 8. Interactive pockets & drain
        for p in self.pockets:
            p.draw(surface)
        self.out_hole.draw(surface)

        # 9. Rotating flower pinwheel spinners
        for sp in self.spinners:
            sp.draw(surface)

        # 10. Glossy Peggle pins
        for pin in self.pins:
            pin.draw(surface)

        # 11. Variable-power cartoon spring plunger
        self.plunger.draw(surface)

        # 12. Batch blit bold cartoon dynamic balls
        offset = self.sprite_offset
        blit_batch = [(self.awake_sprite, (b.x - offset, b.y - offset)) for b in self.balls]
        if blit_batch:
            surface.blits(blit_batch)

        # 13. Celebration sparkle particles
        for pt in self.particles:
            pt.draw(surface)

        # 14. Floating text popups
        for ft in self.floating_texts:
            ft.draw(surface, self.popup_font)

        # 15. Top HUD bar
        self._render_hud(surface, fps)

    def _render_shooter_tube(self, surface: pygame.Surface) -> None:
        """Render clear translucent glass shooter tube with animated upward neon chevron arrows."""
        tube_rect = pygame.Rect(745, 160, round(SHOOTER_LANE_WIDTH), 630)
        tube_surf = pygame.Surface((tube_rect.width, tube_rect.height), pygame.SRCALPHA)
        tube_surf.fill((186, 230, 253, 30))
        surface.blit(tube_surf, tube_rect.topleft)

        chevron_period = 45.0
        offset_y = (self.anim_time * 95.0) % chevron_period
        center_x = 765
        for y_pos in range(int(tube_rect.bottom - 40 - offset_y), int(tube_rect.top + 20), -int(chevron_period)):
            p_mid = (center_x, y_pos - 6)
            p_left = (center_x - 8, y_pos)
            p_right = (center_x + 8, y_pos)
            pygame.draw.lines(surface, (56, 189, 248), False, [p_left, p_mid, p_right], width=2)

    def _render_rainbow(self, surface: pygame.Surface) -> None:
        """Render vibrant cartoon Peggle rainbow arc across top-left corner."""
        rb_center = (40, 40)
        colors = [
            (239, 68, 68),
            (249, 115, 22),
            (250, 204, 21),
            (34, 197, 94),
            (56, 189, 248),
            (168, 85, 247),
        ]
        base_r = 75
        for i, c in enumerate(colors):
            pygame.draw.circle(surface, INK_OUTLINE, rb_center, base_r - i * 4 + 1, width=5)
            pygame.draw.circle(surface, c, rb_center, base_r - i * 4, width=4)

    def _render_badge_13(self, surface: pygame.Surface) -> None:
        """Render glossy embossed '13' Pachinko medallion in top-right corner."""
        bx, by = 765, 55
        pygame.draw.circle(surface, INK_OUTLINE, (bx, by + 2), 28)
        pygame.draw.circle(surface, (217, 119, 6), (bx, by), 25)
        pygame.draw.circle(surface, (250, 204, 21), (bx, by), 22)
        pygame.draw.circle(surface, (254, 240, 138), (bx - 4, by - 4), 8)

        font = pygame.font.SysFont("arial", 22, bold=True)
        lbl = font.render("13", True, INK_OUTLINE)
        surface.blit(lbl, lbl.get_rect(center=(bx, by + 1)))

    def _render_hud(self, surface: pygame.Surface, fps: float) -> None:
        """Render clean top HUD status bar with board title, balance, controls, and FPS."""
        hud_rect = pygame.Rect(16, 12, SCREEN_WIDTH - 32, 42)
        bar_surf = pygame.Surface((hud_rect.width, hud_rect.height), pygame.SRCALPHA)
        bar_surf.fill((15, 23, 42, 220))
        surface.blit(bar_surf, hud_rect.topleft)
        pygame.draw.rect(surface, INK_OUTLINE, hud_rect.inflate(2, 2), width=2, border_radius=9)
        pygame.draw.rect(surface, (51, 65, 85), hud_rect, width=1, border_radius=8)

        bal_color = (74, 222, 128) if self.balance >= STARTING_BALANCE else ((250, 204, 21) if self.balance > 0.0 else (248, 113, 113))
        bal_surf = self.hud_font.render(f"Balance: €{self.balance:.2f}", True, bal_color)

        guide_font = pygame.font.SysFont("arial", 13, bold=True)
        guide_surf = guide_font.render(f"Board: {self.board_data.name}  |  [ESC] Menu  |  [T] Test Drop  |  [R] Reset", True, (226, 232, 240))

        fps_val = int(round(fps))
        fps_color = (74, 222, 128) if fps >= 55.0 else ((250, 204, 21) if fps >= 30.0 else (248, 113, 113))
        stats_surf = guide_font.render(f"Active: {len(self.balls)}  |  FPS: {fps_val}", True, fps_color)

        surface.blit(bal_surf, (hud_rect.x + 14, hud_rect.y + 11))
        surface.blit(guide_surf, (hud_rect.x + 185, hud_rect.y + 14))
        surface.blit(stats_surf, (hud_rect.right - 145, hud_rect.y + 14))
