# Window settings
SCREEN_WIDTH: int = 820
SCREEN_HEIGHT: int = 860
FPS: int = 60
WINDOW_SCALE: float = 0.75

# Circular arena geometry
ARENA_CENTER_X: float = 395.0
ARENA_CENTER_Y: float = 435.0
ARENA_RADIUS: float = 335.0

# Physics configuration
GRAVITY: float = 1200.0
SUB_STEPS: int = 6
RESTITUTION: float = 0.42
PIN_RESTITUTION: float = 0.58
WALL_RESTITUTION: float = 0.48
SURFACE_FRICTION: float = 0.03
AIR_DRAG: float = 0.9995
SLEEP_SPEED_THRESHOLD: float = 3.5
SLEEP_TIME_REQUIRED: float = 0.6

# Chunky Cartoon Entity Sizes
BALL_RADIUS: float = 13.5
GRID_CELL_SIZE: float = BALL_RADIUS * 2.5
PIN_RADIUS: float = 8.5
SPINNER_RADIUS: float = 30.0
SHOOTER_LANE_WIDTH: float = 40.0

# Economy & Tuned Launcher constants
STARTING_BALANCE: float = 1000.0
BALL_COST: float = 5.0
MIN_LAUNCH_SPEED: float = 780.0
MAX_LAUNCH_SPEED: float = 1480.0
PLUNGER_CHARGE_RATE: float = 1.1
MULTIBALL_CAPACITY: int = 3
MULTIBALL_BURST_COUNT: int = 5

# Seesaw Secret Door & Central Yakumono constants
DOOR_REQUIRED_BALLS: int = 3
DOOR_OPEN_DURATION: float = 14.0
ROULETTE_MULTIPLIERS: list[int] = [2, 5, 10, 3, 20, 5, 50, 3]
ROULETTE_COLORS: list[tuple[int, int, int]] = [
    (239, 68, 68),   # Red
    (249, 115, 22),  # Orange
    (250, 204, 21),  # Gold
    (34, 197, 94),   # Green
    (56, 189, 248),  # Cyan
    (99, 102, 241),  # Indigo
    (168, 85, 247),  # Purple
    (236, 72, 153),  # Hot Pink
]
ROULETTE_SPIN_TIME: float = 2.8

# Bold Peggle Cartoon Palette
INK_OUTLINE: tuple[int, int, int] = (18, 24, 42)
CABINET_BG: tuple[int, int, int] = (24, 32, 56)
BOARD_SKY_TOP: tuple[int, int, int] = (135, 222, 248)
BOARD_MEADOW_BOTTOM: tuple[int, int, int] = (152, 230, 140)
PEG_BLUE: tuple[int, int, int] = (37, 99, 235)
PEG_ORANGE: tuple[int, int, int] = (249, 115, 22)
PEG_GREEN: tuple[int, int, int] = (34, 197, 94)
PEG_PURPLE: tuple[int, int, int] = (168, 85, 247)
PEG_GOLD: tuple[int, int, int] = (250, 204, 21)
BALL_COLOR: tuple[int, int, int] = (45, 212, 191)
BALL_CHROME: tuple[int, int, int] = (226, 232, 240)
