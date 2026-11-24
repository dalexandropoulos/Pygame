import math
from pathlib import Path
import pygame
from board_io import BoardData, BoardManager
from config import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    CABINET_BG,
    BOARD_SKY_TOP,
    BOARD_MEADOW_BOTTOM,
    INK_OUTLINE,
    PEG_BLUE,
    PEG_ORANGE,
    PEG_GOLD,
    ARENA_CENTER_X,
    ARENA_CENTER_Y,
    ARENA_RADIUS,
    ROULETTE_COLORS,
)

class MenuScreen:
    """Displays available JSON boards with live schematic mini-previews and launch controls."""

    def __init__(self, board_manager: BoardManager | None = None) -> None:
        self.board_manager: BoardManager = board_manager if board_manager is not None else BoardManager()
        self.boards: list[Path] = []
        self.selected_index: int = 0
        self.hover_index: int = -1
        self.cached_preview_data: BoardData | None = None
        self.anim_time: float = 0.0

        # UI Fonts
        self.title_font: pygame.font.Font = pygame.font.SysFont("arial", 32, bold=True)
        self.header_font: pygame.font.Font = pygame.font.SysFont("arial", 20, bold=True)
        self.item_font: pygame.font.Font = pygame.font.SysFont("arial", 16, bold=True)
        self.small_font: pygame.font.Font = pygame.font.SysFont("arial", 13, bold=True)
        self.hint_font: pygame.font.Font = pygame.font.SysFont("arial", 13, bold=True)

        self.play_button_rect: pygame.Rect = pygame.Rect(395, 715, 125, 48)
        self.edit_button_rect: pygame.Rect = pygame.Rect(530, 715, 120, 48)
        self.new_button_rect: pygame.Rect = pygame.Rect(660, 715, 110, 48)
        self.is_hovering_play: bool = False
        self.is_hovering_edit: bool = False
        self.is_hovering_new: bool = False

        self.refresh()

    def refresh(self) -> None:
        """Scan boards directory, reload file list, and refresh preview data."""
        self.boards = self.board_manager.list_boards()
        if not self.boards:
            self.board_manager.ensure_default_board()
            self.boards = self.board_manager.list_boards()

        self.selected_index = max(0, min(self.selected_index, len(self.boards) - 1))
        self._load_selected_preview()

    def _load_selected_preview(self) -> None:
        """Load and cache BoardData for the currently selected board."""
        if 0 <= self.selected_index < len(self.boards):
            try:
                self.cached_preview_data = self.board_manager.load_board(self.boards[self.selected_index])
            except Exception:
                self.cached_preview_data = None
        else:
            self.cached_preview_data = None

    def handle_event(self, event: pygame.event.Event) -> tuple[str, BoardData | None] | None:
        """Process menu navigation and return action tuple ("play" | "edit" | "new", board) if triggered."""
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                if self.boards:
                    self.selected_index = (self.selected_index - 1) % len(self.boards)
                    self._load_selected_preview()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                if self.boards:
                    self.selected_index = (self.selected_index + 1) % len(self.boards)
                    self._load_selected_preview()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.cached_preview_data is not None:
                    return ("play", self.cached_preview_data)
            elif event.key == pygame.K_e:
                if self.cached_preview_data is not None:
                    return ("edit", self.cached_preview_data)
            elif event.key == pygame.K_n:
                return ("new", None)
            elif event.key == pygame.K_r:
                self.refresh()

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.is_hovering_play = self.play_button_rect.collidepoint(mx, my)
            self.is_hovering_edit = self.edit_button_rect.collidepoint(mx, my)
            self.is_hovering_new = self.new_button_rect.collidepoint(mx, my)

            # Check list item hover
            self.hover_index = -1
            list_y_start = 175
            item_h = 56
            for i in range(len(self.boards)):
                item_rect = pygame.Rect(50, list_y_start + i * (item_h + 8), 290, item_h)
                if item_rect.collidepoint(mx, my):
                    self.hover_index = i
                    break

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Play button click
            if self.play_button_rect.collidepoint(mx, my):
                if self.cached_preview_data is not None:
                    return ("play", self.cached_preview_data)

            # Edit button click
            if self.edit_button_rect.collidepoint(mx, my):
                if self.cached_preview_data is not None:
                    return ("edit", self.cached_preview_data)

            # New button click
            if self.new_button_rect.collidepoint(mx, my):
                return ("new", None)

            # Board list item click
            list_y_start = 175
            item_h = 56
            for i in range(len(self.boards)):
                item_rect = pygame.Rect(50, list_y_start + i * (item_h + 8), 290, item_h)
                if item_rect.collidepoint(mx, my):
                    if self.selected_index == i:
                        # Double click / direct launch on active item
                        if self.cached_preview_data is not None:
                            return ("play", self.cached_preview_data)
                    else:
                        self.selected_index = i
                        self._load_selected_preview()
                    break

        return None

    def update(self, dt: float) -> None:
        """Update animation timers for glowing highlights and button pulsing."""
        self.anim_time += dt

    def render(self, surface: pygame.Surface) -> None:
        """Draw complete Peggle cartoon board selection screen with live schematic preview."""
        surface.fill(CABINET_BG)

        # Decorative rainbow arc top-left
        self._render_rainbow(surface)

        # Header Title
        self._render_header(surface)

        # Left Panel: Board Selection List
        self._render_board_list(surface)

        # Right Panel: Live Board Preview
        self._render_preview_panel(surface)

        # Bottom Hint Bar
        self._render_bottom_bar(surface)

    def _render_rainbow(self, surface: pygame.Surface) -> None:
        """Render cartoon Peggle rainbow arc in top-left."""
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

    def _render_header(self, surface: pygame.Surface) -> None:
        """Render embossed golden Peggle Pachinko title."""
        title_y = 38
        cx = SCREEN_WIDTH // 2

        # Shadow and golden core title
        sh_surf = self.title_font.render("PEGGLE PACHINKO", True, INK_OUTLINE)
        t_surf = self.title_font.render("PEGGLE PACHINKO", True, (250, 204, 21))
        surface.blit(sh_surf, sh_surf.get_rect(center=(cx + 2, title_y + 2)))
        surface.blit(t_surf, t_surf.get_rect(center=(cx, title_y)))

        sub_surf = self.small_font.render("SELECT A PACHINKO BOARD", True, (148, 163, 184))
        surface.blit(sub_surf, sub_surf.get_rect(center=(cx, title_y + 32)))

    def _render_board_list(self, surface: pygame.Surface) -> None:
        """Render scrollable board card list with highlight states."""
        panel_rect = pygame.Rect(35, 105, 320, 680)
        # Translucent panel fill
        bg_surf = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        bg_surf.fill((18, 26, 44, 235))
        surface.blit(bg_surf, panel_rect.topleft)
        pygame.draw.rect(surface, INK_OUTLINE, panel_rect.inflate(2, 2), width=3, border_radius=12)
        pygame.draw.rect(surface, (51, 65, 85), panel_rect, width=2, border_radius=11)

        # Header
        hdr_surf = self.header_font.render("BOARDS", True, (255, 255, 255))
        surface.blit(hdr_surf, (panel_rect.x + 20, panel_rect.y + 16))
        cnt_surf = self.small_font.render(f"({len(self.boards)} available)", True, (148, 163, 184))
        surface.blit(cnt_surf, (panel_rect.x + 120, panel_rect.y + 20))

        # Divider line
        pygame.draw.line(surface, (51, 65, 85), (panel_rect.x + 15, panel_rect.y + 48), (panel_rect.right - 15, panel_rect.y + 48), width=2)

        list_y_start = panel_rect.y + 60
        item_h = 56
        for i, b_path in enumerate(self.boards):
            item_rect = pygame.Rect(panel_rect.x + 15, list_y_start + i * (item_h + 10), panel_rect.width - 30, item_h)
            is_selected = i == self.selected_index
            is_hovered = i == self.hover_index

            # Card fill
            if is_selected:
                pulse = (math.sin(self.anim_time * 5.0) + 1.0) * 0.5
                fill_color = (30, 58, 88)
                pygame.draw.rect(surface, fill_color, item_rect, border_radius=8)
                pygame.draw.rect(surface, INK_OUTLINE, item_rect.inflate(2, 2), width=2, border_radius=9)
                border_color = (56, 189, 248) if pulse > 0.5 else (250, 204, 21)
                pygame.draw.rect(surface, border_color, item_rect, width=2, border_radius=8)
            elif is_hovered:
                pygame.draw.rect(surface, (25, 38, 62), item_rect, border_radius=8)
                pygame.draw.rect(surface, (71, 85, 105), item_rect, width=1, border_radius=8)
            else:
                pygame.draw.rect(surface, (15, 23, 42), item_rect, border_radius=8)
                pygame.draw.rect(surface, (30, 41, 59), item_rect, width=1, border_radius=8)

            # Board display title
            b_title = b_path.stem.replace("_", " ").title()
            title_color = (250, 204, 21) if is_selected else (226, 232, 240)
            t_surf = self.item_font.render(b_title, True, title_color)
            surface.blit(t_surf, (item_rect.x + 14, item_rect.y + 10))

            # Sub-info filename
            f_surf = self.small_font.render(b_path.name, True, (100, 116, 139))
            surface.blit(f_surf, (item_rect.x + 14, item_rect.y + 31))

            # Active arrow badge
            if is_selected:
                pygame.draw.polygon(
                    surface,
                    (250, 204, 21),
                    [(item_rect.right - 14, item_rect.centery), (item_rect.right - 24, item_rect.centery - 6), (item_rect.right - 24, item_rect.centery + 6)],
                )

    def _render_preview_panel(self, surface: pygame.Surface) -> None:
        """Render right preview card with schematic playfield and play button."""
        panel_rect = pygame.Rect(380, 105, 405, 680)
        bg_surf = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        bg_surf.fill((18, 26, 44, 235))
        surface.blit(bg_surf, panel_rect.topleft)
        pygame.draw.rect(surface, INK_OUTLINE, panel_rect.inflate(2, 2), width=3, border_radius=12)
        pygame.draw.rect(surface, (51, 65, 85), panel_rect, width=2, border_radius=11)

        b_data = self.cached_preview_data
        b_name = b_data.name if b_data else "No Board Selected"

        # Title
        hdr_surf = self.header_font.render(b_name, True, (250, 204, 21))
        surface.blit(hdr_surf, (panel_rect.x + 20, panel_rect.y + 16))

        # Stats badges
        if b_data:
            stats = f"{len(b_data.pins)} Pegs  •  {len(b_data.spinners)} Spinners  •  {len(b_data.multiball_pockets)} Tulips"
            st_surf = self.small_font.render(stats, True, (148, 163, 184))
            surface.blit(st_surf, (panel_rect.x + 20, panel_rect.y + 42))

        # Divider line
        pygame.draw.line(surface, (51, 65, 85), (panel_rect.x + 15, panel_rect.y + 66), (panel_rect.right - 15, panel_rect.y + 66), width=2)

        # Live schematic mini-preview box
        preview_box = pygame.Rect(panel_rect.x + 22, panel_rect.y + 80, panel_rect.width - 44, 500)
        self._render_mini_preview(surface, preview_box, b_data)

        # Action Buttons: PLAY [ENTER], EDIT [E], NEW [N]
        pulse = (math.sin(self.anim_time * 6.0) + 1.0) * 0.5

        # 1. PLAY Button
        btn_play = self.play_button_rect
        play_col = (34, 197, 94) if not self.is_hovering_play else (74, 222, 128)
        pygame.draw.rect(surface, INK_OUTLINE, btn_play.inflate(4, 4), border_radius=10)
        pygame.draw.rect(surface, play_col, btn_play, border_radius=8)
        if self.is_hovering_play or pulse > 0.6:
            pygame.draw.rect(surface, (254, 240, 138), btn_play, width=2, border_radius=8)
        play_lbl = self.header_font.render("PLAY", True, (15, 23, 42))
        surface.blit(play_lbl, play_lbl.get_rect(center=btn_play.center))

        # 2. EDIT Button
        btn_edit = self.edit_button_rect
        edit_col = (56, 189, 248) if not self.is_hovering_edit else (125, 211, 252)
        pygame.draw.rect(surface, INK_OUTLINE, btn_edit.inflate(4, 4), border_radius=10)
        pygame.draw.rect(surface, edit_col, btn_edit, border_radius=8)
        if self.is_hovering_edit:
            pygame.draw.rect(surface, (255, 255, 255), btn_edit, width=2, border_radius=8)
        edit_lbl = self.item_font.render("EDIT [E]", True, (15, 23, 42))
        surface.blit(edit_lbl, edit_lbl.get_rect(center=btn_edit.center))

        # 3. NEW Button
        btn_new = self.new_button_rect
        new_col = (250, 204, 21) if not self.is_hovering_new else (253, 224, 71)
        pygame.draw.rect(surface, INK_OUTLINE, btn_new.inflate(4, 4), border_radius=10)
        pygame.draw.rect(surface, new_col, btn_new, border_radius=8)
        if self.is_hovering_new:
            pygame.draw.rect(surface, (255, 255, 255), btn_new, width=2, border_radius=8)
        new_lbl = self.item_font.render("NEW [N]", True, (15, 23, 42))
        surface.blit(new_lbl, new_lbl.get_rect(center=btn_new.center))

    def _render_mini_preview(self, surface: pygame.Surface, box: pygame.Rect, board: BoardData | None) -> None:
        """Render scaled cartoon schematic drawing of the board's walls, pegs, spinners, and targets."""
        # Preview background box
        pygame.draw.rect(surface, (12, 16, 28), box, border_radius=8)
        pygame.draw.rect(surface, INK_OUTLINE, box.inflate(2, 2), width=2, border_radius=9)
        pygame.draw.rect(surface, (30, 41, 59), box, width=1, border_radius=8)

        if board is None:
            no_surf = self.item_font.render("Preview Unavailable", True, (100, 116, 139))
            surface.blit(no_surf, no_surf.get_rect(center=box.center))
            return

        # Coordinate transformation: map logical (820, 860) to fit inside box
        scale = min((box.width - 20) / float(SCREEN_WIDTH), (box.height - 20) / float(SCREEN_HEIGHT))
        draw_w = float(SCREEN_WIDTH) * scale
        draw_h = float(SCREEN_HEIGHT) * scale
        origin_x = box.centerx - draw_w * 0.5
        origin_y = box.centery - draw_h * 0.5

        def to_pv(x: float, y: float) -> tuple[int, int]:
            return (round(origin_x + x * scale), round(origin_y + y * scale))

        # Circular arena backdrop
        arena_center = to_pv(ARENA_CENTER_X, ARENA_CENTER_Y)
        arena_r = max(4, round(ARENA_RADIUS * scale))
        pygame.draw.circle(surface, BOARD_MEADOW_BOTTOM, arena_center, arena_r)
        pygame.draw.circle(surface, BOARD_SKY_TOP, arena_center, arena_r)
        # Inner arena border
        pygame.draw.circle(surface, INK_OUTLINE, arena_center, arena_r + 2, width=3)
        pygame.draw.circle(surface, (217, 119, 6), arena_center, arena_r, width=2)

        # Yakumono roulette wheel
        yak_pos = to_pv(board.yakumono.get("x", 395.0), board.yakumono.get("y", 415.0))
        yak_r = max(4, round(70.0 * scale))
        pygame.draw.circle(surface, INK_OUTLINE, yak_pos, yak_r + 2)
        pygame.draw.circle(surface, (245, 158, 11), yak_pos, yak_r)
        # 8 mini slices
        for si in range(8):
            a1 = si * (math.tau / 8.0)
            a2 = a1 + (math.tau / 8.0)
            p1 = (round(yak_pos[0] + math.cos(a1) * (yak_r - 1)), round(yak_pos[1] + math.sin(a1) * (yak_r - 1)))
            pygame.draw.line(surface, (15, 23, 42), yak_pos, p1, width=1)
        pygame.draw.circle(surface, (250, 204, 21), yak_pos, max(2, round(yak_r * 0.3)))

        # Seesaw secret door
        door_pos = to_pv(board.secret_door.get("x", 395.0), board.secret_door.get("y", 315.0))
        door_w = round(68.0 * scale)
        p_left = (door_pos[0] - door_w // 2, door_pos[1])
        p_right = (door_pos[0] + door_w // 2, door_pos[1])
        pygame.draw.line(surface, INK_OUTLINE, p_left, p_right, width=4)
        pygame.draw.line(surface, (250, 204, 21), p_left, p_right, width=3)

        # Walls
        for w in board.walls:
            p1 = to_pv(w["x1"], w["y1"])
            p2 = to_pv(w["x2"], w["y2"])
            pygame.draw.line(surface, INK_OUTLINE, p1, p2, width=3)
            pygame.draw.line(surface, (245, 158, 11), p1, p2, width=2)

        # Multiball pockets
        for pk in board.multiball_pockets:
            pk_pos = to_pv(pk["x"], pk["y"])
            pygame.draw.circle(surface, INK_OUTLINE, pk_pos, max(3, round(32.0 * scale)) + 1)
            pygame.draw.circle(surface, (56, 189, 248), pk_pos, max(3, round(32.0 * scale)))
            pygame.draw.circle(surface, (15, 23, 42), pk_pos, max(1, round(16.0 * scale)))

        # Out holes
        for oh in board.out_holes:
            oh_pos = to_pv(oh["x"], oh["y"])
            pygame.draw.circle(surface, INK_OUTLINE, oh_pos, max(3, round(34.0 * scale)) + 1)
            pygame.draw.circle(surface, (239, 68, 68), oh_pos, max(3, round(34.0 * scale)), width=2)
            pygame.draw.circle(surface, (10, 15, 26), oh_pos, max(2, round(20.0 * scale)))

        # Spinners
        for sp in board.spinners:
            sp_pos = to_pv(sp["x"], sp["y"])
            sp_r = max(3, round(30.0 * scale))
            pygame.draw.circle(surface, INK_OUTLINE, sp_pos, sp_r + 1)
            pygame.draw.circle(surface, (244, 114, 182), sp_pos, sp_r)
            pygame.draw.circle(surface, (250, 204, 21), sp_pos, max(1, round(sp_r * 0.4)))

        # Pins
        color_map = {"blue": PEG_BLUE, "orange": PEG_ORANGE, "gold": PEG_GOLD}
        for pin in board.pins:
            pin_pos = to_pv(pin["x"], pin["y"])
            c = color_map.get(pin.get("color_type", "blue"), PEG_BLUE)
            pr = max(2, round(8.5 * scale))
            pygame.draw.circle(surface, INK_OUTLINE, pin_pos, pr + 1)
            pygame.draw.circle(surface, c, pin_pos, pr)
            pygame.draw.circle(surface, (255, 255, 255), (pin_pos[0] - 1, pin_pos[1] - 1), 1)

        # Plunger knob indicator
        pl_pos = to_pv(board.plunger.get("x", 765.0), board.plunger.get("y", 790.0) - 40.0)
        pygame.draw.rect(surface, (220, 38, 38), (pl_pos[0] - 6, pl_pos[1], 12, 5), border_radius=2)

    def _render_bottom_bar(self, surface: pygame.Surface) -> None:
        """Render bottom status bar with control reminders."""
        bar_rect = pygame.Rect(35, 802, SCREEN_WIDTH - 70, 38)
        bar_surf = pygame.Surface((bar_rect.width, bar_rect.height), pygame.SRCALPHA)
        bar_surf.fill((15, 23, 42, 220))
        surface.blit(bar_surf, bar_rect.topleft)
        pygame.draw.rect(surface, INK_OUTLINE, bar_rect.inflate(2, 2), width=2, border_radius=8)
        pygame.draw.rect(surface, (51, 65, 85), bar_rect, width=1, border_radius=7)

        hint = "[UP / DOWN / CLICK] Select  |  [ENTER] Play  |  [E] Edit Board  |  [N] New Board  |  [R] Refresh"
        h_surf = self.hint_font.render(hint, True, (203, 213, 225))
        surface.blit(h_surf, h_surf.get_rect(center=bar_rect.center))
