"""
Terrain semantic layer for CarlaSad.

Manages terrain class assignments and traversability metadata.
Semantic label IDs are defined in CLAUDE.md and models/world.py.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np


# Terrain label IDs (must match ROS2 bridge and UE semantic paint)
TERRAIN_LABELS = {
    "normal_field": 100,
    "wet_field": 101,
    "swamp": 102,
    "mochak": 103,
    "rough_terrain": 104,
    "field_boundary": 105,
    "drivable_path": 106,
    "non_drivable": 107,
    "worked_area": 110,
    "unworked_area": 111,
    "worked_edge": 112,
    "active_work_zone": 113,
    "restricted_zone": 114,
}

# Risk levels for traversability (0.0 = safe, 1.0 = impassable)
TERRAIN_RISK = {
    100: 0.0, 101: 0.2, 102: 0.9, 103: 0.8,
    104: 0.4, 105: 1.0, 106: 0.0, 107: 1.0,
    110: 0.0, 111: 0.1, 112: 0.0, 113: 0.0, 114: 1.0,
}


@dataclass
class TerrainCell:
    x: float
    y: float
    label_id: int
    height: float = 0.0
    slope: float = 0.0
    risk: float = 0.0


class TerrainLayer:
    """
    Grid-based terrain semantic layer.
    Provides terrain class queries for any world position.
    """

    def __init__(self, resolution: float = 0.5, width: float = 200.0, height: float = 200.0):
        self._resolution = resolution
        self._width = width
        self._height = height
        self._grid: Optional[np.ndarray] = None
        self._height_map: Optional[np.ndarray] = None
        self._origin = (0.0, 0.0)

    def load_from_map(self, map_path: str):
        """Load terrain grid from exported CARLA map metadata."""
        # TODO: load from .npy / .yaml / heightmap PNG
        pass

    def get_label(self, x: float, y: float) -> int:
        """Get terrain label ID at world position."""
        if self._grid is None:
            return TERRAIN_LABELS["normal_field"]
        gx, gy = self._world_to_grid(x, y)
        if 0 <= gx < self._grid.shape[1] and 0 <= gy < self._grid.shape[0]:
            return int(self._grid[gy, gx])
        return TERRAIN_LABELS["normal_field"]

    def get_risk(self, x: float, y: float) -> float:
        """Get traversability risk at world position."""
        label = self.get_label(x, y)
        return TERRAIN_RISK.get(label, 0.5)

    def is_drivable(self, x: float, y: float) -> bool:
        return self.get_risk(x, y) < 0.5

    def get_height(self, x: float, y: float) -> float:
        """Get terrain height at world position."""
        if self._height_map is None:
            return 0.0
        gx, gy = self._world_to_grid(x, y)
        if 0 <= gx < self._height_map.shape[1] and 0 <= gy < self._height_map.shape[0]:
            return float(self._height_map[gy, gx])
        return 0.0

    def to_occupancy_grid(self) -> dict:
        """Export as ROS2 nav_msgs/OccupancyGrid-compatible dict."""
        if self._grid is None:
            return {}
        return {
            "resolution": self._resolution,
            "width": self._grid.shape[1],
            "height": self._grid.shape[0],
            "origin_x": self._origin[0],
            "origin_y": self._origin[1],
            "data": self._grid.flatten().tolist(),
        }

    def _world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        gx = int((x - self._origin[0]) / self._resolution)
        gy = int((y - self._origin[1]) / self._resolution)
        return gx, gy
