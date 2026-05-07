"""
Process layer ROS2 publisher for CarlaSad bridge.

Publishes process state at 1 Hz to:
  /carlasad/process/worked_map       nav_msgs/OccupancyGrid
  /carlasad/process/worked_edge      carlasad_msgs/WorkedEdge
  /carlasad/process/field_boundary   geometry_msgs/PolygonStamped
  /carlasad/process/terrain_classes  nav_msgs/OccupancyGrid
"""
import sys
import os

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PolygonStamped, Point32
from std_msgs.msg import Header

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../carla-fork/PythonAPI"))
from carlasad.layers import ProcessLayer, TerrainLayer
from . import topic_contract as tc

try:
    from carlasad_msgs.msg import WorkedEdge
    _HAS_WORKED_EDGE_MSG = True
except ImportError:
    _HAS_WORKED_EDGE_MSG = False


class ProcessPublisher(Node):

    def __init__(self, process_layer: ProcessLayer, terrain_layer: TerrainLayer):
        super().__init__("carlasad_process_publisher")
        self._process = process_layer
        self._terrain = terrain_layer

        self._pub_worked   = self.create_publisher(OccupancyGrid,   tc.PROCESS_WORKED_MAP,      10)
        self._pub_boundary = self.create_publisher(PolygonStamped,  tc.PROCESS_FIELD_BOUNDARY,  10)
        self._pub_terrain  = self.create_publisher(OccupancyGrid,   tc.PROCESS_TERRAIN_CLASSES, 10)

        if _HAS_WORKED_EDGE_MSG:
            self._pub_edge = self.create_publisher(WorkedEdge, tc.PROCESS_WORKED_EDGE, 10)
        else:
            self._pub_edge = None
            self.get_logger().warning(
                "carlasad_msgs not built — WorkedEdge topic disabled. "
                "Run: colcon build --packages-select carlasad_msgs"
            )

        self._timer = self.create_timer(1.0, self._publish_all)
        self.get_logger().info("ProcessPublisher started")

    def _publish_all(self):
        stamp = self.get_clock().now().to_msg()
        self._publish_worked_map(stamp)
        self._publish_worked_edge(stamp)
        self._publish_field_boundary(stamp)
        self._publish_terrain_classes(stamp)

    # ── Worked map ────────────────────────────────────────────────────────────

    def _publish_worked_map(self, stamp):
        data = self._process.to_worked_occupancy_grid()
        if not data:
            return
        msg = OccupancyGrid()
        msg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
        msg.info.resolution      = float(data["resolution"])
        msg.info.width           = int(data["width"])
        msg.info.height          = int(data["height"])
        msg.info.origin.position.x = float(data["origin_x"])
        msg.info.origin.position.y = float(data["origin_y"])
        msg.info.origin.orientation.w = 1.0
        msg.data = [int(v) for v in data["data"]]
        self._pub_worked.publish(msg)

    # ── Worked edge ───────────────────────────────────────────────────────────

    def _publish_worked_edge(self, stamp):
        if self._pub_edge is None:
            return
        data = self._process.to_worked_edge_msg()
        if not data.get("points"):
            return

        msg = WorkedEdge()
        msg.header       = Header(stamp=stamp, frame_id=tc.TF_MAP)
        msg.worked_fraction = float(self._process.get_worked_fraction())

        for pt in data["points"]:
            p = Point32()
            p.x = float(pt["x"])
            p.y = float(pt["y"])
            p.z = 0.0
            msg.edge_points.append(p)

        self._pub_edge.publish(msg)

    # ── Field boundary ────────────────────────────────────────────────────────

    def _publish_field_boundary(self, stamp):
        data = self._process.to_field_boundary_msg()
        if not data.get("polygon"):
            return
        msg = PolygonStamped()
        msg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
        for pt in data["polygon"]:
            p = Point32()
            p.x = float(pt["x"])
            p.y = float(pt["y"])
            p.z = 0.0
            msg.polygon.points.append(p)
        self._pub_boundary.publish(msg)

    # ── Terrain classes ───────────────────────────────────────────────────────

    def _publish_terrain_classes(self, stamp):
        try:
            data = self._terrain.to_occupancy_grid()
        except Exception as exc:
            self.get_logger().debug("terrain.to_occupancy_grid: %s", exc)
            return
        if not data:
            return
        msg = OccupancyGrid()
        msg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
        msg.info.resolution      = float(data.get("resolution_m", 1.0))
        msg.info.width           = int(data.get("width", 0))
        msg.info.height          = int(data.get("height", 0))
        msg.info.origin.position.x = float(data.get("origin_x", 0.0))
        msg.info.origin.position.y = float(data.get("origin_y", 0.0))
        msg.info.origin.orientation.w = 1.0
        label_grid = data.get("label_grid", [])
        # Remap CarlaSad IDs (100–114) → [0, 100] for OccupancyGrid convention
        msg.data = [int(v) % 128 for v in label_grid]
        self._pub_terrain.publish(msg)
