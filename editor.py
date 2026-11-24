import math
import sys
from pathlib import Path
import pygame
from board_io import BoardData, BoardManager
from config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    WINDOW_SCALE,
    FPS,
    CABINET_BG,
    BOARD_SKY_TOP,
    BOARD_MEADOW_BOTTOM,
    INK_OUTLINE,
    ARENA_CENTER_X,
    ARENA_CENTER_Y,
    ARENA_RADIUS,
    BALL_RADIUS,
    PIN_RADIUS,
    SPINNER_RADIUS,
    PEG_BLUE,
    PEG_ORANGE,
    PEG_GOLD,
    ROULETTE_COLORS,
)
from simulation import SimulationScreen

class EditorScreen:
    """Visual Pachinko Board Editor with real-time clearance guides, mirror symmetry, and test play."""

    def __init__(self, board_data: BoardData | None = None, board_manager: BoardManager | None = None) -> None:
        self.board_manager: BoardManager = board_manager if board_manager is not None else BoardManager()
        if board_data is None:
            self.board_data: BoardData = self._create_empty_template("Custom Board")
        else:
            self.board_data = board_data

        self.wants_exit_to_menu: bool = False
        self.test_simulation: SimulationScreen | None = None

        # Editor tool modes: 1=Blue, 2=Orange, 3=Gold, 4=Spinner, 5=Wall, 6=Pocket, 7=OutHole, 8=MoveCore
        self.current_tool: int = 1
        self.mirror_mode: bool = True
        self.grid_snap: bool = True
        self.grid_size: float = 16.0
        self.mirror_center_x: float = ARENA_CENTER_X  # 395.0

        # Wall tool state
        self.pending_wall_start: tuple[float, float] | None = None

        # Drag state for tool 8 (Move Core Mechanics)
        self.dragging_entity: str | None = None  # "plunger", "secret_door", "yakumono"
        self.drag_offset: tuple[float, float] = (0.0, 0.0)

        # UI & modal state
        self.save_modal_open: bool = False
        self.save_input_text: str = self.board_data.name
        self.status_notification: str = "Ready. Press 1-8 for tools, S to save, T to test-play."
        self.notification_timer: float = 4.0
        self.anim_time: float = 0.0
        self.mouse_logical_pos: tuple[float, float] = (0.0, 0.0)

        # UI fonts
        self.title_font: pygame.font.Font = pygame.font.SysFont("arial", 20, bold=True)
        self.ui_font: pygame.font.Font = pygame.font.SysFont("arial", 14, bold=True)
        self.small_font: pygame.font.Font = pygame.font.SysFont("arial", 12, bold=True)
        self.hint_font: pygame.font.Font = pygame.font.SysFont("arial", 13, bold=True)

        # Right-side tool palette rects
        self.palette_rect: pygame.Rect = pygame.Rect(SCREEN_WIDTH - 150, 48, 142, 345)
        self.tool_buttons: list[tuple[int, str, pygame.Rect, tuple[int, int, int]]] = []
        self._init_tool_buttons()

        # Top toolbar action buttons
        self.action_buttons: list[tuple[str, str, pygame.Rect]] = []
        self._init_action_buttons()

    def _init_tool_buttons(self) -> None:
        """Define right-side tool palette button rectangles and theme colors."""
        tools = [
            (1, "1: Blue Peg", PEG_BLUE),
            (2, "2: Orange Peg", PEG_ORANGE),
            (3, "3: Gold Peg", PEG_GOLD),
            (4, "4: Spinner", (244, 114, 182)),
            (5, "5: Wall", (245, 158, 11)),
            (6, "6: Pocket", (56, 189, 248)),
            (7, "7: Out-Hole", (239, 68, 68)),
            (8, "8: Move Core", (168, 85, 247)),
        ]
        btn_y = self.palette_rect.y + 34
        for tool_id, label, col in tools:
            rect = pygame.Rect(self.palette_rect.x + 8, btn_y, self.palette_rect.width - 16, 32)
            self.tool_buttons.append((tool_id, label, rect, col))
            btn_y += 37

    def _init_action_buttons(self) -> None:
        """Define top toolbar action pills."""
        actions = [
            ("mirror", "M: Mirror", pygame.Rect(12, 10, 92, 28)),
            ("grid", "G: Grid 16", pygame.Rect(110, 10, 88, 28)),
            ("test", "T: Test Play", pygame.Rect(204, 10, 94, 28)),
            ("save", "S: Save", pygame.Rect(304, 10, 78, 28)),
            ("load", "L: Cycle", pygame.Rect(388, 10, 80, 28)),
            ("new", "N: New", pygame.Rect(474, 10, 76, 28)),
            ("exit", "ESC: Exit", pygame.Rect(556, 10, 86, 28)),
        ]
        self.action_buttons = actions

    def _create_empty_template(self, name: str) -> BoardData:
        """Construct a clean template with standard outer shooter guide rails and empty inner targets."""
        starter = self.board_manager._generate_starter_board(name)
        return BoardData(
            name=name,
            pins=[],
            spinners=[],
            walls=list(starter.walls),
            multiball_pockets=[],
            out_holes=[{"x": 395.0, "y": 760.0}],
            plunger={"x": 765.0, "y": 790.0, "height": 70.0},
            secret_door={"x": 395.0, "y": 315.0},
            yakumono={"x": 395.0, "y": 415.0},
        )

    def _snap(self, val: float) -> float:
        """Snap coordinate to 16px grid if enabled."""
        if self.grid_snap:
            return round(val / self.grid_size) * self.grid_size
        return round(val, 1)

    def _get_mirrored_x(self, x: float) -> float:
        """Compute symmetrical X position across arena centerline (395.0)."""
        return 2.0 * self.mirror_center_x - x

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route input events to test simulation, save modal, tool placement, or drag interactions."""
        # 1. If currently in test play mode, pass events to SimulationScreen
        if self.test_simulation is not None:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.test_simulation = None
                self.status_notification = "Exited test session. Returned to editor."
                self.notification_timer = 3.0
                return
            self.test_simulation.handle_event(event)
            if self.test_simulation.wants_exit_to_menu:
                self.test_simulation = None
                self.status_notification = "Exited test session. Returned to editor."
                self.notification_timer = 3.0
            return

        # 2. Save Modal Text Dialog input capture
        if self.save_modal_open:
            self._handle_save_modal_event(event)
            return

        # Track logical mouse coordinates
        if hasattr(event, "pos"):
            self.mouse_logical_pos = event.pos

        # 3. Keyboard Shortcuts
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_1, pygame.K_KP1):
                self.current_tool = 1
            elif event.key in (pygame.K_2, pygame.K_KP2):
                self.current_tool = 2
            elif event.key in (pygame.K_3, pygame.K_KP3):
                self.current_tool = 3
            elif event.key in (pygame.K_4, pygame.K_KP4):
                self.current_tool = 4
            elif event.key in (pygame.K_5, pygame.K_KP5):
                self.current_tool = 5
                self.pending_wall_start = None
            elif event.key in (pygame.K_6, pygame.K_KP6):
                self.current_tool = 6
            elif event.key in (pygame.K_7, pygame.K_KP7):
                self.current_tool = 7
            elif event.key in (pygame.K_8, pygame.K_KP8):
                self.current_tool = 8
            elif event.key == pygame.K_m:
                self.mirror_mode = not self.mirror_mode
                self.status_notification = f"Mirror Symmetry: {'ENABLED' if self.mirror_mode else 'DISABLED'}"
                self.notification_timer = 2.5
            elif event.key == pygame.K_g:
                self.grid_snap = not self.grid_snap
                self.status_notification = f"16px Grid Snap: {'ENABLED' if self.grid_snap else 'DISABLED'}"
                self.notification_timer = 2.5
            elif event.key == pygame.K_s:
                self.save_modal_open = True
                self.save_input_text = self.board_data.name
            elif event.key == pygame.K_t:
                self._launch_test_play()
            elif event.key == pygame.K_l:
                self._cycle_load_board()
            elif event.key == pygame.K_n:
                self.board_data = self._create_empty_template("New Board")
                self.pending_wall_start = None
                self.status_notification = "Clean board template created."
                self.notification_timer = 3.0
            elif event.key == pygame.K_ESCAPE:
                if self.pending_wall_start is not None:
                    self.pending_wall_start = None
                    self.status_notification = "Pending wall segment cancelled."
                    self.notification_timer = 2.0
                else:
                    self.wants_exit_to_menu = True

        # 4. Mouse Button Clicks & Drags
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            # Left Click
            if event.button == 1:
                # Check top action buttons
                for act_id, _, r in self.action_buttons:
                    if r.collidepoint(mx, my):
                        self._trigger_action(act_id)
                        return

                # Check tool palette buttons
                if self.palette_rect.collidepoint(mx, my):
                    for tool_id, _, r, _ in self.tool_buttons:
                        if r.collidepoint(mx, my):
                            self.current_tool = tool_id
                            self.pending_wall_start = None
                            return
                    return

                # Ignore clicks inside header or footer
                if my < 45 or my > 825:
                    return

                # Tool placement or drag initiation
                self._handle_canvas_left_click(mx, my)

            # Right Click: cancel pending wall or delete nearest object
            elif event.button == 3:
                if self.current_tool == 5 and self.pending_wall_start is not None:
                    self.pending_wall_start = None
                    self.status_notification = "Wall start point cancelled."
                    self.notification_timer = 2.0
                else:
                    self._delete_nearest_object(mx, my)

        # Mouse Motion during drag
        elif event.type == pygame.MOUSEMOTION:
            if self.current_tool == 8 and self.dragging_entity is not None:
                mx, my = event.pos
                nx = self._snap(mx - self.drag_offset[0])
                ny = self._snap(my - self.drag_offset[1])
                if self.dragging_entity == "plunger":
                    self.board_data.plunger["x"] = nx
                    self.board_data.plunger["y"] = ny
                elif self.dragging_entity == "secret_door":
                    self.board_data.secret_door["x"] = nx
                    self.board_data.secret_door["y"] = ny
                elif self.dragging_entity == "yakumono":
                    self.board_data.yakumono["x"] = nx
                    self.board_data.yakumono["y"] = ny

        # Mouse Button Release
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging_entity is not None:
                self.dragging_entity = None
                self.status_notification = "Repositioned core mechanic."
                self.notification_timer = 2.0

    def _trigger_action(self, action_id: str) -> None:
        """Trigger action button by identifier."""
        if action_id == "mirror":
            self.mirror_mode = not self.mirror_mode
            self.status_notification = f"Mirror Symmetry: {'ENABLED' if self.mirror_mode else 'DISABLED'}"
            self.notification_timer = 2.0
        elif action_id == "grid":
            self.grid_snap = not self.grid_snap
            self.status_notification = f"16px Grid Snap: {'ENABLED' if self.grid_snap else 'DISABLED'}"
            self.notification_timer = 2.0
        elif action_id == "test":
            self._launch_test_play()
        elif action_id == "save":
            self.save_modal_open = True
            self.save_input_text = self.board_data.name
        elif action_id == "load":
            self._cycle_load_board()
        elif action_id == "new":
            self.board_data = self._create_empty_template("New Board")
            self.pending_wall_start = None
            self.status_notification = "Clean board template created."
            self.notification_timer = 3.0
        elif action_id == "exit":
            self.wants_exit_to_menu = True

    def _handle_save_modal_event(self, event: pygame.event.Event) -> None:
        """Handle keyboard input in save modal dialog."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.save_modal_open = False
                self.status_notification = "Save cancelled."
                self.notification_timer = 2.0
            elif event.key == pygame.K_RETURN:
                name = self.save_input_text.strip()
                if name:
                    self.board_data.name = name
                    slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.lower().replace(" ", "_"))
                    filename = f"{slug}.json"
                    saved_path = self.board_manager.save_board(self.board_data, filename)
                    self.save_modal_open = False
                    self.status_notification = f"Saved successfully to {saved_path.name}!"
                    self.notification_timer = 4.0
            elif event.key == pygame.K_BACKSPACE:
                self.save_input_text = self.save_input_text[:-1]
            else:
                if len(event.unicode) > 0 and event.unicode.isprintable() and len(self.save_input_text) < 32:
                    self.save_input_text += event.unicode

    def _launch_test_play(self) -> None:
        """Instantiate SimulationScreen with current board data for immediate test play."""
        try:
            self.test_simulation = SimulationScreen(self.board_data)
            self.status_notification = "Test play active. Press ESC to return to editor."
        except Exception as e:
            self.status_notification = f"Cannot test play: {e}"
            self.notification_timer = 4.0

    def _cycle_load_board(self) -> None:
        """Cycle through existing board files in the boards directory."""
        boards = self.board_manager.list_boards()
        if not boards:
            self.status_notification = "No saved boards found."
            self.notification_timer = 2.5
            return

        current_slug = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in self.board_data.name.lower().replace(" ", "_")
        )
        curr_idx = -1
        for i, b in enumerate(boards):
            if b.stem == current_slug:
                curr_idx = i
                break

        next_idx = (curr_idx + 1) % len(boards)
        target = boards[next_idx]
        try:
            self.board_data = self.board_manager.load_board(target)
            self.pending_wall_start = None
            self.status_notification = f"Loaded board: {target.name}"
            self.notification_timer = 3.0
        except Exception as err:
            self.status_notification = f"Error loading {target.name}: {err}"
            self.notification_timer = 3.0

    def _handle_canvas_left_click(self, mx: float, my: float) -> None:
        """Commit entity placement or start dragging core mechanic according to active tool."""
        sx = self._snap(mx)
        sy = self._snap(my)
        mx_sym = self._get_mirrored_x(sx)

        # Tool 1, 2, 3: Pins
        if self.current_tool in (1, 2, 3):
            col_map = {1: "blue", 2: "orange", 3: "gold"}
            c_type = col_map[self.current_tool]
            self.board_data.pins.append({"x": sx, "y": sy, "color_type": c_type})
            if self.mirror_mode and abs(sx - mx_sym) > 1.0:
                self.board_data.pins.append({"x": mx_sym, "y": sy, "color_type": c_type})
            self.status_notification = f"Placed {c_type.title()} Pin."
            self.notification_timer = 1.5

        # Tool 4: Flower Spinner
        elif self.current_tool == 4:
            self.board_data.spinners.append({"x": sx, "y": sy})
            if self.mirror_mode and abs(sx - mx_sym) > 1.0:
                self.board_data.spinners.append({"x": mx_sym, "y": sy})
            self.status_notification = "Placed Spinner."
            self.notification_timer = 1.5

        # Tool 5: Wall Segment (two-click commit)
        elif self.current_tool == 5:
            if self.pending_wall_start is None:
                self.pending_wall_start = (sx, sy)
                self.status_notification = "Wall start point set. Click to commit end point."
                self.notification_timer = 4.0
            else:
                x1, y1 = self.pending_wall_start
                if math.hypot(sx - x1, sy - y1) > 6.0:
                    self.board_data.walls.append({"x1": x1, "y1": y1, "x2": sx, "y2": sy})
                    if self.mirror_mode:
                        mx1 = self._get_mirrored_x(x1)
                        mx2 = self._get_mirrored_x(sx)
                        self.board_data.walls.append({"x1": mx1, "y1": y1, "x2": mx2, "y2": sy})
                    self.status_notification = "Placed Wall segment."
                    self.notification_timer = 2.0
                self.pending_wall_start = None

        # Tool 6: Multiball Pocket
        elif self.current_tool == 6:
            self.board_data.multiball_pockets.append({"x": sx, "y": sy})
            if self.mirror_mode and abs(sx - mx_sym) > 1.0:
                self.board_data.multiball_pockets.append({"x": mx_sym, "y": sy})
            self.status_notification = "Placed Multiball Pocket."
            self.notification_timer = 1.5

        # Tool 7: Out-Hole Drain
        elif self.current_tool == 7:
            self.board_data.out_holes.append({"x": sx, "y": sy})
            if self.mirror_mode and abs(sx - mx_sym) > 1.0:
                self.board_data.out_holes.append({"x": mx_sym, "y": sy})
            self.status_notification = "Placed Out-Hole Drain."
            self.notification_timer = 1.5

        # Tool 8: Move Core Mechanics
        elif self.current_tool == 8:
            # Check plunger
            pl = self.board_data.plunger
            if math.hypot(mx - pl.get("x", 765.0), my - pl.get("y", 790.0)) < 42.0:
                self.dragging_entity = "plunger"
                self.drag_offset = (mx - pl.get("x", 765.0), my - pl.get("y", 790.0))
                return

            # Check secret door
            sd = self.board_data.secret_door
            if math.hypot(mx - sd.get("x", 395.0), my - sd.get("y", 315.0)) < 42.0:
                self.dragging_entity = "secret_door"
                self.drag_offset = (mx - sd.get("x", 395.0), my - sd.get("y", 315.0))
                return

            # Check yakumono
            yk = self.board_data.yakumono
            if math.hypot(mx - yk.get("x", 395.0), my - yk.get("y", 415.0)) < 75.0:
                self.dragging_entity = "yakumono"
                self.drag_offset = (mx - yk.get("x", 395.0), my - yk.get("y", 415.0))
                return

    def _delete_nearest_object(self, mx: float, my: float) -> None:
        """Find and remove closest entity or wall within deletion radius, including mirrored twin if mirror mode is ON."""
        deleted_count = self._remove_single_nearest(mx, my)
        if self.mirror_mode:
            mx_sym = self._get_mirrored_x(mx)
            deleted_count += self._remove_single_nearest(mx_sym, my)

        if deleted_count > 0:
            self.status_notification = f"Deleted {deleted_count} object(s)."
            self.notification_timer = 2.0

    def _remove_single_nearest(self, px: float, py: float) -> int:
        """Delete closest single pin, spinner, pocket, out-hole, or wall segment within selection threshold."""
        best_dist = 28.0
        target_kind: str | None = None
        target_idx: int = -1

        # Check pins
        for i, pin in enumerate(self.board_data.pins):
            d = math.hypot(px - pin["x"], py - pin["y"])
            if d < best_dist:
                best_dist = d
                target_kind = "pin"
                target_idx = i

        # Check spinners
        for i, sp in enumerate(self.board_data.spinners):
            d = math.hypot(px - sp["x"], py - sp["y"])
            if d < best_dist and d < 36.0:
                best_dist = d
                target_kind = "spinner"
                target_idx = i

        # Check pockets
        for i, pk in enumerate(self.board_data.multiball_pockets):
            d = math.hypot(px - pk["x"], py - pk["y"])
            if d < best_dist and d < 38.0:
                best_dist = d
                target_kind = "pocket"
                target_idx = i

        # Check out-holes
        for i, oh in enumerate(self.board_data.out_holes):
            d = math.hypot(px - oh["x"], py - oh["y"])
            if d < best_dist and d < 38.0:
                best_dist = d
                target_kind = "out_hole"
                target_idx = i

        # Check wall segments (point-to-segment distance)
        for i, w in enumerate(self.board_data.walls):
            x1, y1 = w["x1"], w["y1"]
            x2, y2 = w["x2"], w["y2"]
            dx = x2 - x1
            dy = y2 - y1
            l2 = dx * dx + dy * dy
            if l2 == 0.0:
                d = math.hypot(px - x1, py - y1)
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                d = math.hypot(px - proj_x, py - proj_y)

            if d < best_dist and d < 18.0:
                best_dist = d
                target_kind = "wall"
                target_idx = i

        if target_kind == "pin" and 0 <= target_idx < len(self.board_data.pins):
            self.board_data.pins.pop(target_idx)
            return 1
        elif target_kind == "spinner" and 0 <= target_idx < len(self.board_data.spinners):
            self.board_data.spinners.pop(target_idx)
            return 1
        elif target_kind == "pocket" and 0 <= target_idx < len(self.board_data.multiball_pockets):
            self.board_data.multiball_pockets.pop(target_idx)
            return 1
        elif target_kind == "out_hole" and 0 <= target_idx < len(self.board_data.out_holes):
            self.board_data.out_holes.pop(target_idx)
            return 1
        elif target_kind == "wall" and 0 <= target_idx < len(self.board_data.walls):
            self.board_data.walls.pop(target_idx)
            return 1

        return 0

    def update(self, dt: float) -> None:
        """Update animation pulses, timers, and test simulation if running."""
        self.anim_time += dt
        if self.test_simulation is not None:
            self.test_simulation.update(dt)
            return

        if self.notification_timer > 0.0:
            self.notification_timer -= dt

    def render(self, surface: pygame.Surface) -> None:
        """Render complete visual editor with circular arena, guides, clearance ghost, and palette."""
        # If in test mode, delegate rendering to test simulation
        if self.test_simulation is not None:
            self.test_simulation.render(surface, FPS)
            # Overlay return reminder banner
            banner_rect = pygame.Rect(SCREEN_WIDTH // 2 - 160, 12, 320, 32)
            pygame.draw.rect(surface, (15, 23, 42), banner_rect, border_radius=6)
            pygame.draw.rect(surface, (250, 204, 21), banner_rect, width=2, border_radius=6)
            msg_surf = self.ui_font.render("[ESC] Return to Editor", True, (250, 204, 21))
            surface.blit(msg_surf, msg_surf.get_rect(center=banner_rect.center))
            return

        # 1. Background Fill
        surface.fill(CABINET_BG)

        # 2. Circular Arena Backdrop
        arena_c = (round(ARENA_CENTER_X), round(ARENA_CENTER_Y))
        pygame.draw.circle(surface, BOARD_MEADOW_BOTTOM, arena_c, round(ARENA_RADIUS))
        pygame.draw.circle(surface, BOARD_SKY_TOP, arena_c, round(ARENA_RADIUS))
        pygame.draw.circle(surface, INK_OUTLINE, arena_c, round(ARENA_RADIUS) + 3, width=4)
        pygame.draw.circle(surface, (217, 119, 6), arena_c, round(ARENA_RADIUS), width=3)

        # 3. Grid Visualization (Subtle dots if grid snap is active)
        if self.grid_snap:
            self._render_grid_dots(surface)

        # 4. Mirror Symmetry Centerline
        if self.mirror_mode:
            mx_i = round(self.mirror_center_x)
            for y_dot in range(50, 810, 16):
                pygame.draw.line(surface, (250, 204, 21, 100), (mx_i, y_dot), (mx_i, y_dot + 8), width=1)

        # 5. Core Mechanics (Yakumono, Seesaw Door, Plunger)
        self._render_core_mechanics(surface)

        # 6. Placed Walls
        for w in self.board_data.walls:
            p1 = (round(w["x1"]), round(w["y1"]))
            p2 = (round(w["x2"]), round(w["y2"]))
            pygame.draw.line(surface, INK_OUTLINE, p1, p2, width=5)
            pygame.draw.line(surface, (245, 158, 11), p1, p2, width=3)

        # 7. Placed Out-Holes
        for oh in self.board_data.out_holes:
            pos = (round(oh["x"]), round(oh["y"]))
            pygame.draw.circle(surface, INK_OUTLINE, pos, 35)
            pygame.draw.circle(surface, (239, 68, 68), pos, 33, width=3)
            pygame.draw.circle(surface, (10, 15, 26), pos, 22)

        # 8. Placed Multiball Pockets
        for pk in self.board_data.multiball_pockets:
            pos = (round(pk["x"]), round(pk["y"]))
            pygame.draw.circle(surface, INK_OUTLINE, pos, 33)
            pygame.draw.circle(surface, (56, 189, 248), pos, 31)
            pygame.draw.circle(surface, (15, 23, 42), pos, 16)
            pygame.draw.circle(surface, (255, 255, 255), (pos[0] - 6, pos[1] - 6), 4)

        # 9. Placed Spinners
        for sp in self.board_data.spinners:
            pos = (round(sp["x"]), round(sp["y"]))
            pygame.draw.circle(surface, INK_OUTLINE, pos, round(SPINNER_RADIUS) + 2)
            pygame.draw.circle(surface, (244, 114, 182), pos, round(SPINNER_RADIUS))
            # 6 petals
            for i in range(6):
                ang = i * (math.tau / 6.0)
                px = pos[0] + round(math.cos(ang) * (SPINNER_RADIUS - 6))
                py = pos[1] + round(math.sin(ang) * (SPINNER_RADIUS - 6))
                pygame.draw.circle(surface, (255, 255, 255), (px, py), 5)
            pygame.draw.circle(surface, (250, 204, 21), pos, 10)

        # 10. Placed Pins
        col_map = {"blue": PEG_BLUE, "orange": PEG_ORANGE, "gold": PEG_GOLD}
        for pin in self.board_data.pins:
            pos = (round(pin["x"]), round(pin["y"]))
            c = col_map.get(pin.get("color_type", "blue"), PEG_BLUE)
            pr = round(PIN_RADIUS)
            pygame.draw.circle(surface, INK_OUTLINE, pos, pr + 2)
            pygame.draw.circle(surface, c, pos, pr)
            pygame.draw.circle(surface, (255, 255, 255), (pos[0] - 2, pos[1] - 2), 2)

        # 11. Interactive Ghost Placement Preview & Clearance Ring
        self._render_ghost_preview(surface)

        # 12. Top Toolbar & Header
        self._render_top_toolbar(surface)

        # 13. Right-Side Tool Palette
        self._render_tool_palette(surface)

        # 14. Bottom Status & Hint Bar
        self._render_bottom_status(surface)

        # 15. Modal Save Dialog (if open)
        if self.save_modal_open:
            self._render_save_modal(surface)

    def _render_grid_dots(self, surface: pygame.Surface) -> None:
        """Render faint grid dots for 16px snapping guidance."""
        step = int(self.grid_size)
        for gx in range(50, SCREEN_WIDTH - 60, step * 2):
            for gy in range(60, SCREEN_HEIGHT - 60, step * 2):
                if math.hypot(gx - ARENA_CENTER_X, gy - ARENA_CENTER_Y) <= ARENA_RADIUS:
                    surface.set_at((gx, gy), (100, 116, 139))

    def _render_core_mechanics(self, surface: pygame.Surface) -> None:
        """Render Yakumono roulette wheel, Seesaw secret door, and plunger launcher."""
        # Yakumono Roulette
        yk = self.board_data.yakumono
        yk_pos = (round(yk.get("x", 395.0)), round(yk.get("y", 415.0)))
        yk_r = 70
        pygame.draw.circle(surface, INK_OUTLINE, yk_pos, yk_r + 3)
        pygame.draw.circle(surface, (245, 158, 11), yk_pos, yk_r)
        # 8 color segments
        for si in range(8):
            a1 = si * (math.tau / 8.0)
            p_end = (round(yk_pos[0] + math.cos(a1) * (yk_r - 2)), round(yk_pos[1] + math.sin(a1) * (yk_r - 2)))
            pygame.draw.line(surface, INK_OUTLINE, yk_pos, p_end, width=2)
        pygame.draw.circle(surface, (250, 204, 21), yk_pos, 22)
        pygame.draw.circle(surface, INK_OUTLINE, yk_pos, 23, width=2)
        yk_lbl = self.small_font.render("YAKUMONO", True, INK_OUTLINE)
        surface.blit(yk_lbl, yk_lbl.get_rect(center=yk_pos))

        # Seesaw Secret Door
        sd = self.board_data.secret_door
        sd_pos = (round(sd.get("x", 395.0)), round(sd.get("y", 315.0)))
        door_w = 68
        p_left = (sd_pos[0] - door_w // 2, sd_pos[1])
        p_right = (sd_pos[0] + door_w // 2, sd_pos[1])
        pygame.draw.line(surface, INK_OUTLINE, p_left, p_right, width=8)
        pygame.draw.line(surface, (250, 204, 21), p_left, p_right, width=5)
        sd_lbl = self.small_font.render("SEESAW DOOR", True, (254, 240, 138))
        surface.blit(sd_lbl, sd_lbl.get_rect(center=(sd_pos[0], sd_pos[1] - 12)))

        # Plunger Launcher
        pl = self.board_data.plunger
        pl_x = round(pl.get("x", 765.0))
        pl_y = round(pl.get("y", 790.0))
        pygame.draw.rect(surface, (30, 41, 59), (pl_x - 18, pl_y - 65, 36, 75), border_radius=4)
        pygame.draw.rect(surface, INK_OUTLINE, (pl_x - 18, pl_y - 65, 36, 75), width=2, border_radius=4)
        # Spring coil
        for cy in range(pl_y - 55, pl_y - 15, 8):
            pygame.draw.line(surface, (148, 163, 184), (pl_x - 10, cy), (pl_x + 10, cy + 4), width=2)
        # Red knob
        pygame.draw.circle(surface, (220, 38, 38), (pl_x, pl_y - 8), 12)
        pygame.draw.circle(surface, INK_OUTLINE, (pl_x, pl_y - 8), 13, width=2)
        pl_lbl = self.small_font.render("PLUNGER", True, (203, 213, 225))
        surface.blit(pl_lbl, pl_lbl.get_rect(center=(pl_x, pl_y + 14)))

    def _render_ghost_preview(self, surface: pygame.Surface) -> None:
        """Render transparent placement ghost with subtle ball-clearance ring (radius + BALL_RADIUS * 2.1)."""
        mx, my = self.mouse_logical_pos
        if my < 45 or my > 825 or self.palette_rect.collidepoint(mx, my):
            return

        sx = self._snap(mx)
        sy = self._snap(my)
        points = [(sx, sy)]
        if self.mirror_mode and self.current_tool != 8:
            mx_sym = self._get_mirrored_x(sx)
            if abs(sx - mx_sym) > 1.0:
                points.append((mx_sym, sy))

        # Tool 5: Wall placement ghost
        if self.current_tool == 5:
            if self.pending_wall_start is not None:
                p1 = self.pending_wall_start
                pygame.draw.line(surface, (250, 204, 21), p1, (sx, sy), width=3)
                pygame.draw.circle(surface, (250, 204, 21), (round(sx), round(sy)), 5)
                if self.mirror_mode:
                    mp1 = (self._get_mirrored_x(p1[0]), p1[1])
                    mp2 = (self._get_mirrored_x(sx), sy)
                    pygame.draw.line(surface, (250, 204, 21), mp1, mp2, width=3)
                    pygame.draw.circle(surface, (250, 204, 21), (round(mp2[0]), round(mp2[1])), 5)
            else:
                pygame.draw.circle(surface, (245, 158, 11), (round(sx), round(sy)), 6)
                if self.mirror_mode:
                    pygame.draw.circle(surface, (245, 158, 11), (round(self._get_mirrored_x(sx)), round(sy)), 6)
            return

        # Tools 1-4, 6-7: Circular entities with clearance ring
        tool_specs = {
            1: (PIN_RADIUS, PEG_BLUE),
            2: (PIN_RADIUS, PEG_ORANGE),
            3: (PIN_RADIUS, PEG_GOLD),
            4: (SPINNER_RADIUS, (244, 114, 182)),
            6: (32.0, (56, 189, 248)),
            7: (34.0, (239, 68, 68)),
        }

        if self.current_tool in tool_specs:
            entity_r, col = tool_specs[self.current_tool]
            # Clearance ring: entity_radius + BALL_RADIUS * 2.1 (BALL_RADIUS = 13.5, so +28.35px)
            clearance_r = round(entity_r + BALL_RADIUS * 2.1)

            for px, py in points:
                pos = (round(px), round(py))
                # Outer ball-clearance ring (subtle dashed/faint ring showing clearance to avoid jams)
                pygame.draw.circle(surface, (56, 189, 248), pos, clearance_r, width=1)
                # Entity ghost body
                pygame.draw.circle(surface, col, pos, round(entity_r), width=2)
                pygame.draw.circle(surface, (255, 255, 255), (pos[0] - 2, pos[1] - 2), 2)

    def _render_top_toolbar(self, surface: pygame.Surface) -> None:
        """Render top toolbar with board title and action shortcuts."""
        bar_rect = pygame.Rect(0, 0, SCREEN_WIDTH, 44)
        pygame.draw.rect(surface, (15, 23, 42), bar_rect)
        pygame.draw.line(surface, (51, 65, 85), (0, 44), (SCREEN_WIDTH, 44), width=2)

        # Action pills
        mx, my = self.mouse_logical_pos
        for act_id, label, r in self.action_buttons:
            is_hover = r.collidepoint(mx, my)
            is_active = (act_id == "mirror" and self.mirror_mode) or (act_id == "grid" and self.grid_snap)

            if is_active:
                bg_col = (30, 58, 88)
                border_col = (56, 189, 248)
                text_col = (250, 204, 21)
            elif is_hover:
                bg_col = (30, 41, 59)
                border_col = (148, 163, 184)
                text_col = (255, 255, 255)
            else:
                bg_col = (18, 26, 44)
                border_col = (51, 65, 85)
                text_col = (203, 213, 225)

            pygame.draw.rect(surface, bg_col, r, border_radius=6)
            pygame.draw.rect(surface, border_col, r, width=1, border_radius=6)
            lbl_surf = self.small_font.render(label, True, text_col)
            surface.blit(lbl_surf, lbl_surf.get_rect(center=r.center))

        # Current board title display
        title_txt = f"Board: {self.board_data.name}"
        t_surf = self.ui_font.render(title_txt, True, (250, 204, 21))
        surface.blit(t_surf, (SCREEN_WIDTH - t_surf.get_width() - 16, 12))

    def _render_tool_palette(self, surface: pygame.Surface) -> None:
        """Render floating tool palette on the right side."""
        p_rect = self.palette_rect
        # Panel background
        bg_surf = pygame.Surface((p_rect.width, p_rect.height), pygame.SRCALPHA)
        bg_surf.fill((15, 23, 42, 235))
        surface.blit(bg_surf, p_rect.topleft)
        pygame.draw.rect(surface, INK_OUTLINE, p_rect.inflate(2, 2), width=2, border_radius=8)
        pygame.draw.rect(surface, (51, 65, 85), p_rect, width=1, border_radius=7)

        # Header
        hdr = self.small_font.render("TOOLS (1-8)", True, (250, 204, 21))
        surface.blit(hdr, (p_rect.x + 10, p_rect.y + 10))

        # Tool buttons
        mx, my = self.mouse_logical_pos
        for tool_id, label, r, col in self.tool_buttons:
            is_active = tool_id == self.current_tool
            is_hover = r.collidepoint(mx, my)

            if is_active:
                bg = (30, 58, 88)
                border_c = (250, 204, 21)
                txt_c = (255, 255, 255)
            elif is_hover:
                bg = (25, 38, 62)
                border_c = (100, 116, 139)
                txt_c = (226, 232, 240)
            else:
                bg = (18, 26, 44)
                border_c = (30, 41, 59)
                txt_c = (148, 163, 184)

            pygame.draw.rect(surface, bg, r, border_radius=6)
            pygame.draw.rect(surface, border_c, r, width=2 if is_active else 1, border_radius=6)
            # Color pip indicator
            pygame.draw.circle(surface, col, (r.x + 12, r.centery), 5)
            txt_surf = self.small_font.render(label, True, txt_c)
            surface.blit(txt_surf, (r.x + 24, r.centery - txt_surf.get_height() // 2))

    def _render_bottom_status(self, surface: pygame.Surface) -> None:
        """Render bottom status notification bar with tool instructions and feedback."""
        bar_rect = pygame.Rect(12, SCREEN_HEIGHT - 36, SCREEN_WIDTH - 24, 28)
        pygame.draw.rect(surface, (15, 23, 42), bar_rect, border_radius=6)
        pygame.draw.rect(surface, (51, 65, 85), bar_rect, width=1, border_radius=6)

        # Stats summary on the left
        stats = f"{len(self.board_data.pins)} Pegs | {len(self.board_data.spinners)} Spinners | {len(self.board_data.walls)} Walls"
        st_surf = self.small_font.render(stats, True, (148, 163, 184))
        surface.blit(st_surf, (bar_rect.x + 12, bar_rect.y + 6))

        # Main active notification message
        msg_col = (250, 204, 21) if self.notification_timer > 0.0 else (203, 213, 225)
        msg_surf = self.hint_font.render(self.status_notification, True, msg_col)
        surface.blit(msg_surf, (bar_rect.x + 240, bar_rect.y + 5))

    def _render_save_modal(self, surface: pygame.Surface) -> None:
        """Render modal text input dialog to rename and save board layout."""
        # Backdrop dimming
        dim_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, 180))
        surface.blit(dim_surf, (0, 0))

        # Modal box
        modal_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT // 2 - 90, 400, 180)
        pygame.draw.rect(surface, (18, 26, 44), modal_rect, border_radius=12)
        pygame.draw.rect(surface, INK_OUTLINE, modal_rect.inflate(4, 4), width=3, border_radius=14)
        pygame.draw.rect(surface, (250, 204, 21), modal_rect, width=2, border_radius=12)

        # Header
        hdr = self.title_font.render("SAVE PACHINKO BOARD", True, (250, 204, 21))
        surface.blit(hdr, hdr.get_rect(center=(modal_rect.centerx, modal_rect.y + 30)))

        # Subtitle
        sub = self.small_font.render("Enter board display name below:", True, (148, 163, 184))
        surface.blit(sub, sub.get_rect(center=(modal_rect.centerx, modal_rect.y + 58)))

        # Text Input Box
        input_rect = pygame.Rect(modal_rect.x + 30, modal_rect.y + 78, modal_rect.width - 60, 38)
        pygame.draw.rect(surface, (10, 15, 26), input_rect, border_radius=6)
        pygame.draw.rect(surface, (56, 189, 248), input_rect, width=2, border_radius=6)

        # Blinking cursor
        cursor = "_" if int(self.anim_time * 2.5) % 2 == 0 else ""
        txt_surf = self.ui_font.render(self.save_input_text + cursor, True, (255, 255, 255))
        surface.blit(txt_surf, (input_rect.x + 10, input_rect.centery - txt_surf.get_height() // 2))

        # Hints
        hint = self.small_font.render("[ENTER] Save to boards/  |  [ESC] Cancel", True, (148, 163, 184))
        surface.blit(hint, hint.get_rect(center=(modal_rect.centerx, modal_rect.y + 145)))


def main() -> None:
    """Standalone entry point for launching board editor directly via `uv run editor.py`."""
    pygame.init()

    desktop_sizes = pygame.display.get_desktop_sizes()
    desktop_w, desktop_h = desktop_sizes[0] if desktop_sizes else (1920, 1080)

    initial_h = min(int(SCREEN_HEIGHT * WINDOW_SCALE), int(desktop_h * 0.82))
    initial_w = int(initial_h * (SCREEN_WIDTH / SCREEN_HEIGHT))

    screen = pygame.display.set_mode((initial_w, initial_h), pygame.RESIZABLE)
    pygame.display.set_caption("Peggle Pachinko - Board Editor")
    clock = pygame.time.Clock()

    logical_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    editor = EditorScreen()
    running = True

    scale_w = initial_w
    scale_h = initial_h
    offset_x = 0
    offset_y = 0

    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)

        # Preserve aspect ratio
        win_w, win_h = screen.get_size()
        target_aspect = float(SCREEN_WIDTH) / float(SCREEN_HEIGHT)
        win_aspect = float(win_w) / float(win_h) if win_h > 0 else target_aspect

        if win_aspect > target_aspect:
            scale_h = win_h
            scale_w = int(scale_h * target_aspect)
            offset_x = (win_w - scale_w) // 2
            offset_y = 0
        else:
            scale_w = win_w
            scale_h = int(scale_w / target_aspect)
            offset_x = 0
            offset_y = (win_h - scale_h) // 2

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            else:
                if hasattr(event, "pos") and scale_w > 0 and scale_h > 0:
                    mx, my = event.pos
                    lx = (mx - offset_x) * (SCREEN_WIDTH / scale_w)
                    ly = (my - offset_y) * (SCREEN_HEIGHT / scale_h)
                    ev_dict = event.__dict__.copy()
                    ev_dict["pos"] = (lx, ly)
                    event = pygame.event.Event(event.type, ev_dict)

                editor.handle_event(event)
                if editor.wants_exit_to_menu:
                    running = False

        editor.update(dt)
        editor.render(logical_surface)

        scaled_frame = pygame.transform.smoothscale(logical_surface, (scale_w, scale_h))
        screen.fill(CABINET_BG)
        screen.blit(scaled_frame, (offset_x, offset_y))
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
