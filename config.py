# Display settings
SCREEN_WIDTH: int = 800
SCREEN_HEIGHT: int = 600
FPS: int = 60

# Physics configuration
GRAVITY: float = 1200.0
SUB_STEPS: int = 6
RESTITUTION: float = 0.35
PIN_RESTITUTION: float = 0.52
WALL_RESTITUTION: float = 0.45
SURFACE_FRICTION: float = 0.03
AIR_DRAG: float = 0.9995
SLEEP_SPEED_THRESHOLD: float = 3.5
SLEEP_TIME_REQUIRED: float = 0.6

# Pachinko & Board parameters
BALL_RADIUS: float = 8.0
GRID_CELL_SIZE: float = BALL_RADIUS * 2.5
PIN_RADIUS: float = 4.5
PIN_ROWS: int = 10
PIN_SPACING_X: float = 52.0
PIN_SPACING_Y: float = 40.0
RAIL_OFFSET_X: float = 34.0

# Economy configuration
STARTING_BALANCE: float = 1000.0
BALL_COST: float = 5.0
DROP_COOLDOWN: float = 0.14
SLOT_MULTIPLIERS: list[float] = [10.0, 4.0, 2.0, 1.2, 0.5, 0.0, 0.5, 1.2, 2.0, 4.0, 10.0]

# Visual theme
BG_COLOR: tuple[int, int, int] = (13, 18, 30)
BOARD_BG_COLOR: tuple[int, int, int] = (22, 30, 48)
RAIL_COLOR: tuple[int, int, int] = (56, 189, 248)
RAIL_GLOW_COLOR: tuple[int, int, int] = (28, 95, 130)
BALL_COLOR: tuple[int, int, int] = (251, 191, 36)
BALL_HIGHLIGHT: tuple[int, int, int] = (254, 243, 199)
PIN_COLOR: tuple[int, int, int] = (203, 213, 225)
PIN_FLASH_COLOR: tuple[int, int, int] = (255, 255, 255)
