import pygame

# Display settings
SCREEN_WIDTH: int = 800
SCREEN_HEIGHT: int = 600
FPS: int = 60

# Physics configuration
GRAVITY: pygame.math.Vector2 = pygame.math.Vector2(0.0, 980.0)
SUB_STEPS: int = 8
RESTITUTION: float = 0.2
DAMPING: float = 0.98

# Entity parameters
BALL_RADIUS: float = 20.0
BALL_MASS: float = 1.0
FLOOR_Y: float = float(SCREEN_HEIGHT - 40)

# Spawner settings
SPAWN_INTERVAL: float = 1.0
SPAWN_POS_Y: float = 50.0
SPAWN_X_JITTER: float = 2.0

# Visual theme
COLOR_BG: tuple[int, int, int] = (24, 26, 32)
COLOR_FLOOR: tuple[int, int, int] = (64, 70, 84)
COLOR_FLOOR_ACCENT: tuple[int, int, int] = (90, 100, 120)
COLOR_BALL: tuple[int, int, int] = (235, 87, 87)
COLOR_BALL_OUTLINE: tuple[int, int, int] = (255, 255, 255)
