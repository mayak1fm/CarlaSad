"""
Publishes a traversability/risk OccupancyGrid derived from TerrainLayer.

Topic:  /carlasad/terrain/risk_map  (nav_msgs/OccupancyGrid)
Frame:  map
Rate:   0.5 Hz (static terrain, low update rate is fine)

Cell values:
  0   → free  (risk 0.0)
  100 → fully blocked (risk 1.0)
  -1  → unknown
"""
import sys
sys.path.insert(0, "/carla-fork/PythonAPI")   # adjusted at runtime by bridge launch

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from std_msgs.msg import Header
import numpy as np


class RiskMapPublisher(Node):
    def __init__(self, terrain_layer=None):
        super().__init__("risk_map_publisher")

        self.declare_parameter("publish_rate_hz", 0.5)
        self.declare_parameter("map_frame", "map")

        self._terrain_layer = terrain_layer
        self._pub = self.create_publisher(OccupancyGrid, "/carlasad/terrain/risk_map", 1)

        rate = self.get_parameter("publish_rate_hz").value
        period = 1.0 / max(rate, 0.1)
        self._timer = self.create_timer(period, self._publish)

        self.get_logger().info("RiskMapPublisher ready (%.1f Hz)", rate)

    def set_terrain_layer(self, terrain_layer):
        self._terrain_layer = terrain_layer

    def _publish(self):
        if self._terrain_layer is None:
            return

        try:
            grid_data = self._terrain_layer.to_occupancy_grid()
        except Exception as exc:
            self.get_logger().error("TerrainLayer.to_occupancy_grid failed: %s", exc)
            return

        msg = OccupancyGrid()
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.get_parameter("map_frame").value

        msg.info.resolution      = float(grid_data.get("resolution_m", 1.0))
        msg.info.width           = int(grid_data.get("width", 0))
        msg.info.height          = int(grid_data.get("height", 0))
        msg.info.origin.position.x = float(grid_data.get("origin_x", 0.0))
        msg.info.origin.position.y = float(grid_data.get("origin_y", 0.0))
        msg.info.origin.position.z = 0.0
        msg.info.origin.orientation.w = 1.0

        risk_grid = grid_data.get("risk_grid")  # numpy float32 array [0,1]
        if risk_grid is not None:
            arr = np.asarray(risk_grid, dtype=np.float32).flatten()
            # Convert [0, 1] → [0, 100] OccupancyGrid convention; unknown = -1
            occ = np.where(arr < 0, -1, np.clip(arr * 100.0, 0, 100)).astype(np.int8)
            msg.data = occ.tolist()
        else:
            label_grid = np.asarray(grid_data.get("label_grid", []), dtype=np.uint8).flatten()
            if len(label_grid) == 0:
                return
            from carlasad.layers.terrain_layer import TERRAIN_RISK
            occ = np.array([int(TERRAIN_RISK.get(int(l), 0.0) * 100) for l in label_grid],
                           dtype=np.int8)
            msg.data = occ.tolist()

        self._pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RiskMapPublisher()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
