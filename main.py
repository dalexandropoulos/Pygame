import sys
import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, WINDOW_SCALE, FPS, CABINET_BG
from board_io import BoardManager, BoardData
from menu import MenuScreen
from simulation import SimulationScreen
from editor import EditorScreen

def main() -> None:
    """Initialize scaled window, screen state manager, and primary application loop."""
    pygame.init()

    # Query desktop resolution for responsive auto-fit on smaller screens
    desktop_sizes = pygame.display.get_desktop_sizes()
    desktop_w, desktop_h = desktop_sizes[0] if desktop_sizes else (1920, 1080)

    initial_h = min(int(SCREEN_HEIGHT * WINDOW_SCALE), int(desktop_h * 0.82))
    initial_w = int(initial_h * (SCREEN_WIDTH / SCREEN_HEIGHT))

    screen = pygame.display.set_mode((initial_w, initial_h), pygame.RESIZABLE)
    pygame.display.set_caption("Peggle Pachinko")
    clock = pygame.time.Clock()

    logical_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    board_manager = BoardManager()
    menu_screen = MenuScreen(board_manager)
    simulation: SimulationScreen | None = None
    editor_screen: EditorScreen | None = None
    app_state: str = "menu"
    running: bool = True

    scale_w = initial_w
    scale_h = initial_h
    offset_x = 0
    offset_y = 0

    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)

        # Calculate aspect-ratio-preserving viewport inside current window
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
                # Map mouse window coordinates to logical board coordinates
                if hasattr(event, "pos") and scale_w > 0 and scale_h > 0:
                    mx, my = event.pos
                    lx = (mx - offset_x) * (SCREEN_WIDTH / scale_w)
                    ly = (my - offset_y) * (SCREEN_HEIGHT / scale_h)
                    ev_dict = event.__dict__.copy()
                    ev_dict["pos"] = (lx, ly)
                    event = pygame.event.Event(event.type, ev_dict)

                if app_state == "menu":
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        running = False
                    else:
                        action = menu_screen.handle_event(event)
                        if action is not None:
                            action_type, board_data = action
                            if action_type == "play" and board_data is not None:
                                simulation = SimulationScreen(board_data)
                                app_state = "game"
                            elif action_type == "edit" and board_data is not None:
                                editor_screen = EditorScreen(board_data=board_data, board_manager=board_manager)
                                app_state = "editor"
                            elif action_type == "new":
                                editor_screen = EditorScreen(board_data=None, board_manager=board_manager)
                                app_state = "editor"

                elif app_state == "game":
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        menu_screen.refresh()
                        app_state = "menu"
                    elif simulation is not None:
                        simulation.handle_event(event)
                        if simulation.wants_exit_to_menu:
                            menu_screen.refresh()
                            app_state = "menu"

                elif app_state == "editor":
                    if editor_screen is not None:
                        editor_screen.handle_event(event)
                        if editor_screen.wants_exit_to_menu:
                            menu_screen.refresh()
                            app_state = "menu"

        # Update active state
        if app_state == "menu":
            menu_screen.update(dt)
            menu_screen.render(logical_surface)
        elif app_state == "game" and simulation is not None:
            simulation.update(dt)
            simulation.render(logical_surface, clock.get_fps())
        elif app_state == "editor" and editor_screen is not None:
            editor_screen.update(dt)
            editor_screen.render(logical_surface)

        # Render logical target scaled onto screen
        scaled_frame = pygame.transform.smoothscale(logical_surface, (scale_w, scale_h))
        screen.fill(CABINET_BG)
        screen.blit(scaled_frame, (offset_x, offset_y))
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
