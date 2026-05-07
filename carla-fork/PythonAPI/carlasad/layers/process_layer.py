"""
Process state layer for CarlaSad.

Tracks worked/unworked areas, the active working edge,
work zones, and processing history over time.

Published to ROS2 as:
  /carlasad/process/worked_map      nav_msgs/OccupancyGrid
  /carlasad/process/worked_edge     carlasad_msgs/WorkedEdge
  /carlasad/process/field_boundary  geometry_msgs/PolygonStamped
  /carlasad/process/terrain_classes nav_msgs/OccupancyGrid
  /carlasad/process/risk_map        nav_msgs/OccupancyGrid
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import time
import numpy as np


UNWORKED = 0
WORKED = 100
WORKED_EDGE = 50
ACTIVE_ZONE = 75
RESTRICTED = 200


@dataclass
class WorkedEdgePoint:
    x: float
    y: float
    timestamp: float


class ProcessLayer:
    """
    Dynamic process state layer.
    Updated in real-time as the tractor moves through the field.
    """

    def __init__(self, resolution: float = 0.5, width: float = 200.0, height: float = 200.0):
        self._resolution = resolution
        self._origin = (-width / 2, -height / 2)
        nx = int(width / resolution)
        ny = int(height / resolution)
        self._worked_grid = np.zeros((ny, nx), dtype=np.uint8)
        self._field_boundary: List[Tuple[float, float]] = []
        self._work_zones: List[List[Tuple[float, float]]] = []
        self._restricted_zones: List[List[Tuple[float, float]]] = []
        self._process_history: List[dict] = []
        self._worked_edge: List[WorkedEdgePoint] = []

    def mark_worked(self, x: float, y: float, radius: float = 1.5):
        """Mark a circular area as worked (tractor passed through)."""
        gx, gy = self._world_to_grid(x, y)
        r = int(radius / self._resolution)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    nx = gx + dx
                    ny = gy + dy
                    if 0 <= nx < self._worked_grid.shape[1] and \
                       0 <= ny < self._worked_grid.shape[0]:
                        self._worked_grid[ny, nx] = WORKED
        self._update_worked_edge(x, y)
        self._process_history.append({
            "x": x, "y": y, "radius": radius, "t": time.time()
        })

    def _update_worked_edge(self, x: float, y: float):
        """Update the worked edge with new point."""
        self._worked_edge.append(WorkedEdgePoint(x=x, y=y, timestamp=time.time()))
        if len(self._worked_edge) > 1000:
            self._worked_edge = self._worked_edge[-500:]

    def set_field_boundary(self, polygon: List[Tuple[float, float]]):
        """Set field boundary polygon (world coordinates)."""
        self._field_boundary = polygon

    def set_work_zone(self, polygon: List[Tuple[float, float]]):
        """Add a work zone polygon."""
        self._work_zones.append(polygon)

    def set_restricted_zone(self, polygon: List[Tuple[float, float]]):
        """Add a restricted zone polygon (no-go area)."""
        self._restricted_zones.append(polygon)

    def get_worked_fraction(self) -> float:
        """Return fraction of field that has been worked (0.0–1.0)."""
        total = self._worked_grid.size
        if total == 0:
            return 0.0
        worked = np.sum(self._worked_grid == WORKED)
        return float(worked) / total

    def to_worked_occupancy_grid(self) -> dict:
        return {
            "resolution": self._resolution,
            "width": self._worked_grid.shape[1],
            "height": self._worked_grid.shape[0],
            "origin_x": self._origin[0],
            "origin_y": self._origin[1],
            "data": self._worked_grid.flatten().tolist(),
        }

    def to_worked_edge_msg(self) -> dict:
        return {
            "points": [{"x": p.x, "y": p.y, "t": p.timestamp} for p in self._worked_edge[-100:]],
        }

    def to_field_boundary_msg(self) -> dict:
        return {
            "polygon": [{"x": p[0], "y": p[1]} for p in self._field_boundary],
        }

    def reset(self):
        self._worked_grid[:] = 0
        self._worked_edge = []
        self._process_history = []

    def _world_to_grid(self, x: float, y: float) -> Tuple[int, int]:
        gx = int((x - self._origin[0]) / self._resolution)
        gy = int((y - self._origin[1]) / self._resolution)
        return gx, gy
