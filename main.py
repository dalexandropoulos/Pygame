import sys
import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from simulation import SimulationScreen

def main() -> None:
    """Initialize application window, game clock, and execute the primary simulation loop."""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Ball Stacking Simulation")
    clock = pygame.time.Clock()

    simulation = SimulationScreen()
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        # Prevent physics explosion on window dragging or momentary lag spikes
        dt = min(dt, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            simulation.handle_event(event)

        simulation.update(dt)
        simulation.render(screen, clock.get_fps())
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
