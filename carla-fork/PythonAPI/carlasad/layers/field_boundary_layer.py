"""Field boundary layer — manages field polygon and zone definitions."""
from typing import List, Tuple
import math


Point2D = Tuple[float, float]


class FieldBoundaryLayer:
    """
    Stores and queries field boundary, work zones, and no-go zones.
    Used for: tractor confinement, process layer initialization, dataset placement.
    """

    def __init__(self):
        self._boundary: List[Point2D] = []
        self._work_zones: List[List[Point2D]] = []
        self._no_go_zones: List[List[Point2D]] = []
        self._headland_width: float = 5.0

    def set_boundary(self, polygon: List[Point2D]):
        self._boundary = polygon

    def add_work_zone(self, polygon: List[Point2D]):
        self._work_zones.append(polygon)

    def add_no_go_zone(self, polygon: List[Point2D]):
        self._no_go_zones.append(polygon)

    def is_inside_boundary(self, x: float, y: float) -> bool:
        return self._point_in_polygon(x, y, self._boundary)

    def is_in_no_go_zone(self, x: float, y: float) -> bool:
        return any(self._point_in_polygon(x, y, zone) for zone in self._no_go_zones)

    def is_near_boundary(self, x: float, y: float, threshold: float = 2.0) -> bool:
        """Check if point is within threshold meters of any boundary segment."""
        for i in range(len(self._boundary)):
            p1 = self._boundary[i]
            p2 = self._boundary[(i + 1) % len(self._boundary)]
            if self._point_to_segment_dist(x, y, p1, p2) < threshold:
                return True
        return False

    def get_boundary_polygon(self) -> List[Point2D]:
        return self._boundary.copy()

    def _point_in_polygon(self, x: float, y: float, polygon: List[Point2D]) -> bool:
        if not polygon:
            return False
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def _point_to_segment_dist(self, px: float, py: float,
                                p1: Point2D, p2: Point2D) -> float:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        if dx == 0 and dy == 0:
            return math.hypot(px - p1[0], py - p1[1])
        t = max(0, min(1, ((px - p1[0]) * dx + (py - p1[1]) * dy) / (dx * dx + dy * dy)))
        nearest_x = p1[0] + t * dx
        nearest_y = p1[1] + t * dy
        return math.hypot(px - nearest_x, py - nearest_y)
