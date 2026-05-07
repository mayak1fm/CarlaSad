"""
Process layer ROS2 publisher for CarlaSad bridge.

Publishes process state at configurable rate to:
  /carlasad/process/worked_map
  /carlasad/process/worked_edge
  /carlasad/process/field_boundary
  /carlasad/process/terrain_classes
  /carlasad/process/risk_map
"""
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PolygonStamped, Point32
from std_msgs.msg import Header
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../carla-fork/PythonAPI"))
from carlasad.layers import ProcessLayer, TerrainLayer
from . import topic_contract as tc


class ProcessPublisher(Node):

    def __init__(self, process_layer: ProcessLayer, terrain_layer: TerrainLayer):
        super().__init__("carlasad_process_publisher")
        self._process = process_layer
        self._terrain = terrain_layer

        self._pub_worked = self.create_publisher(OccupancyGrid, tc.PROCESS_WORKED_MAP, 10)
        self._pub_boundary = self.create_publisher(PolygonStamped, tc.PROCESS_FIELD_BOUNDARY, 10)
        self._pub_terrain = self.create_publisher(OccupancyGrid, tc.PROCESS_TERRAIN_CLASSES, 10)
        self._pub_risk = self.create_publisher(OccupancyGrid, tc.PROCESS_RISK_MAP, 10)

        self._timer = self.create_timer(1.0, self._publish_all)
        self.get_logger().info("ProcessPublisher started")

    def _publish_all(self):
        stamp = self.get_clock().now().to_msg()
        self._publish_worked_map(stamp)
        self._publish_field_boundary(stamp)

    def _publish_worked_map(self, stamp):
        data = self._process.to_worked_occupancy_grid()
        if not data:
            return
        msg = OccupancyGrid()
        msg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
        msg.info.resolution = float(data["resolution"])
        msg.info.width = int(data["width"])
        msg.info.height = int(data["height"])
        msg.info.origin.position.x = float(data["origin_x"])
        msg.info.origin.position.y = float(data["origin_y"])
        msg.data = [int(v) for v in data["data"]]
        self._pub_worked.publish(msg)

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
