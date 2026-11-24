import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path

@dataclass
class BoardData:
    """Structured data container for Pachinko playfield layouts and entity placement."""
    name: str
    pins: list[dict] = field(default_factory=list)
    spinners: list[dict] = field(default_factory=list)
    walls: list[dict] = field(default_factory=list)
    multiball_pockets: list[dict] = field(default_factory=list)
    out_holes: list[dict] = field(default_factory=list)
    plunger: dict = field(default_factory=lambda: {"x": 765.0, "y": 790.0, "height": 70.0})
    secret_door: dict = field(default_factory=lambda: {"x": 395.0, "y": 315.0})
    yakumono: dict = field(default_factory=lambda: {"x": 395.0, "y": 415.0})

    def to_dict(self) -> dict:
        """Serialize board model to standard dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BoardData":
        """Instantiate board model from parsed dictionary."""
        return cls(
            name=data.get("name", "Untitled Board"),
            pins=data.get("pins", []),
            spinners=data.get("spinners", []),
            walls=data.get("walls", []),
            multiball_pockets=data.get("multiball_pockets", []),
            out_holes=data.get("out_holes", []),
            plunger=data.get("plunger", {"x": 765.0, "y": 790.0, "height": 70.0}),
            secret_door=data.get("secret_door", {"x": 395.0, "y": 315.0}),
            yakumono=data.get("yakumono", {"x": 395.0, "y": 415.0}),
        )


class BoardManager:
    """Manages file persistence, discovery, and starter board generation in the boards directory."""

    def __init__(self, boards_dir: Path = Path("boards")) -> None:
        self.boards_dir: Path = boards_dir
        self.boards_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_default_board()

    def ensure_default_board(self) -> Path:
        """Create a default Peggle board with generous clearances if the directory is empty."""
        existing = list(self.boards_dir.glob("*.json"))
        default_path = self.boards_dir / "classic_peggle.json"
        if not existing:
            board = self._generate_starter_board("Classic Peggle")
            self.save_board(board, "classic_peggle.json")
        return default_path

    def _generate_starter_board(self, name: str) -> BoardData:
        """Construct balanced default playfield layout with clearances >= 58px and a 104px shooter exit."""
        cx, cy = 395.0, 435.0
        walls: list[dict] = []

        # 1. Wide vertical shooter lane rails (40px wide channel)
        lane_right_x = 785.0
        lane_left_x = 745.0
        walls.append({"x1": lane_right_x, "y1": 790.0, "x2": lane_right_x, "y2": 260.0})
        walls.append({"x1": lane_left_x, "y1": 790.0, "x2": lane_left_x, "y2": 340.0})

        # 2. Outer and inner curved guide tracks over top arc (104px wide exit funnel)
        guide_steps = 14
        outer_r = 385.0
        start_a = math.radians(-32.0)
        end_a = math.radians(-145.0)
        prev_gx = lane_right_x
        prev_gy = 260.0
        for i in range(1, guide_steps + 1):
            t = i / guide_steps
            ang = start_a + t * (end_a - start_a)
            gx = cx + math.cos(ang) * outer_r
            gy = cy + math.sin(ang) * outer_r
            walls.append({"x1": prev_gx, "y1": prev_gy, "x2": gx, "y2": gy})
            prev_gx, prev_gy = gx, gy

        inner_steps = 10
        inner_r = 338.0
        start_ia = math.radians(-50.0)
        end_ia = math.radians(-130.0)
        prev_ix = cx + math.cos(start_ia) * inner_r
        prev_iy = cy + math.sin(start_ia) * inner_r
        for i in range(1, inner_steps + 1):
            t = i / inner_steps
            ang = start_ia + t * (end_ia - start_ia)
            ix = cx + math.cos(ang) * inner_r
            iy = cy + math.sin(ang) * inner_r
            walls.append({"x1": prev_ix, "y1": prev_iy, "x2": ix, "y2": iy})
            prev_ix, prev_iy = ix, iy

        # 3. Funnel guide walls directing balls toward lower pockets (wide entrances)
        walls.append({"x1": 175.0, "y1": 560.0, "x2": 210.0, "y2": 605.0})
        walls.append({"x1": 290.0, "y1": 560.0, "x2": 250.0, "y2": 605.0})
        walls.append({"x1": 500.0, "y1": 560.0, "x2": 540.0, "y2": 605.0})
        walls.append({"x1": 615.0, "y1": 560.0, "x2": 580.0, "y2": 605.0})

        # 4. Funnel guides for bottom drain hole
        walls.append({"x1": 335.0, "y1": 715.0, "x2": 365.0, "y2": 755.0})
        walls.append({"x1": 455.0, "y1": 715.0, "x2": 425.0, "y2": 755.0})

        # 5. Funnel guide walls leading from seesaw door into Yakumono receptor
        walls.append({"x1": 355.0, "y1": 325.0, "x2": 365.0, "y2": 355.0})
        walls.append({"x1": 435.0, "y1": 325.0, "x2": 425.0, "y2": 355.0})

        # Symmetrical pins spaced >= 58px apart (minimum clearance 64px)
        pins: list[dict] = [
            # Top arch crown
            {"x": 275.0, "y": 210.0, "color_type": "gold"},
            {"x": 330.0, "y": 175.0, "color_type": "orange"},
            {"x": 395.0, "y": 150.0, "color_type": "gold"},
            {"x": 460.0, "y": 175.0, "color_type": "orange"},
            {"x": 515.0, "y": 210.0, "color_type": "gold"},
            # Funnel above seesaw door
            {"x": 350.0, "y": 255.0, "color_type": "gold"},
            {"x": 440.0, "y": 255.0, "color_type": "gold"},
            # Upper flankers
            {"x": 210.0, "y": 310.0, "color_type": "blue"},
            {"x": 580.0, "y": 310.0, "color_type": "blue"},
            # Flanking mid arcs
            {"x": 245.0, "y": 365.0, "color_type": "blue"},
            {"x": 260.0, "y": 430.0, "color_type": "gold"},
            {"x": 295.0, "y": 490.0, "color_type": "blue"},
            {"x": 545.0, "y": 365.0, "color_type": "blue"},
            {"x": 530.0, "y": 430.0, "color_type": "gold"},
            {"x": 495.0, "y": 490.0, "color_type": "blue"},
            # Tulip guides
            {"x": 225.0, "y": 540.0, "color_type": "orange"},
            {"x": 565.0, "y": 540.0, "color_type": "orange"},
            # Scatter above drain
            {"x": 355.0, "y": 645.0, "color_type": "blue"},
            {"x": 435.0, "y": 645.0, "color_type": "blue"},
            {"x": 395.0, "y": 695.0, "color_type": "gold"},
        ]

        # Spinners
        spinners = [
            {"x": 260.0, "y": 285.0},
            {"x": 530.0, "y": 285.0},
            {"x": 195.0, "y": 435.0},
            {"x": 595.0, "y": 435.0},
        ]

        # Multiball pockets
        pockets = [
            {"x": 230.0, "y": 605.0},
            {"x": 560.0, "y": 605.0},
        ]

        # Out hole
        out_holes = [{"x": 395.0, "y": 760.0}]

        return BoardData(
            name=name,
            pins=pins,
            spinners=spinners,
            walls=walls,
            multiball_pockets=pockets,
            out_holes=out_holes,
            plunger={"x": 765.0, "y": 790.0, "height": 70.0},
            secret_door={"x": 395.0, "y": 315.0},
            yakumono={"x": 395.0, "y": 415.0},
        )

    def list_boards(self) -> list[Path]:
        """Return sorted list of all available JSON board files."""
        return sorted(list(self.boards_dir.glob("*.json")))

    def load_board(self, path: Path) -> BoardData:
        """Load and parse board layout from disk."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BoardData.from_dict(data)

    def save_board(self, board: BoardData, filename: str) -> Path:
        """Serialize board layout to JSON on disk."""
        target_path = self.boards_dir / filename
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(board.to_dict(), f, indent=2)
        return target_path
