"""
CarlaSad ROS2 Bridge Node.

Main node that:
  1. Connects to CARLA server
  2. Spawns sensor rig on the tractor
  3. Publishes sensor data to ROS2 topics (topic_contract.py)
  4. Publishes ground truth, process layer, mission state
  5. Broadcasts TF tree
  6. Supports synchronous and asynchronous CARLA modes
"""
import os
import sys
import time
import threading
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from std_msgs.msg import Header, String
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, PointField, NavSatFix, Imu
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseStamped, TransformStamped, PolygonStamped, Point32
from tf2_ros import TransformBroadcaster, StaticTransformBroadcaster
from rosgraph_msgs.msg import Clock

from . import topic_contract as tc

CARLA_HOST = os.environ.get("CARLA_HOST", "localhost")
CARLA_PORT = int(os.environ.get("CARLA_PORT", "2000"))
CARLA_TIMEOUT = float(os.environ.get("CARLA_TIMEOUT", "10.0"))
SYNC_MODE = os.environ.get("CARLA_SYNC", "false").lower() == "true"
FIXED_DELTA = float(os.environ.get("CARLA_DELTA", "0.05"))

# QoS profiles
QOS_SENSOR = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)
QOS_RELIABLE = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)
QOS_LATCHED = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class CarlaSadBridgeNode(Node):
    def __init__(self):
        super().__init__("carlasad_bridge")
        self.declare_parameter("carla_host", CARLA_HOST)
        self.declare_parameter("carla_port", CARLA_PORT)
        self.declare_parameter("sync_mode", SYNC_MODE)
        self.declare_parameter("fixed_delta", FIXED_DELTA)

        self._host = self.get_parameter("carla_host").value
        self._port = self.get_parameter("carla_port").value
        self._sync = self.get_parameter("sync_mode").value
        self._delta = self.get_parameter("fixed_delta").value

        self._client = None
        self._world = None
        self._tractor = None
        self._sensors: list = []

        # TF broadcasters
        self._tf_broadcaster = TransformBroadcaster(self)
        self._static_tf_broadcaster = StaticTransformBroadcaster(self)

        # Publishers
        self._pub_clock = self.create_publisher(Clock, tc.CLOCK, QOS_RELIABLE)
        self._pub_ego   = self.create_publisher(PoseStamped, tc.GT_EGO_POSE, QOS_RELIABLE)
        self._pub_worked = self.create_publisher(OccupancyGrid, tc.PROCESS_WORKED_MAP, QOS_LATCHED)
        self._pub_boundary = self.create_publisher(PolygonStamped, tc.PROCESS_FIELD_BOUNDARY, QOS_LATCHED)

        self._camera_pubs: dict = {}
        self._lidar_pubs: dict = {}

        # Process layer
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../PythonAPI"))
        try:
            from carlasad.layers import ProcessLayer, TerrainLayer
            from carlasad.layers.field_boundary_layer import FieldBoundaryLayer
            self._process = ProcessLayer()
            self._terrain = TerrainLayer()
            self._field_boundary = FieldBoundaryLayer()
            self.get_logger().info("CarlaSad layers loaded")
        except ImportError as e:
            self.get_logger().warning("Could not import carlasad layers: %s", str(e))
            self._process = None

        # Connect to CARLA
        self._connect()

    # ── CARLA Connection ───────────────────────────────────────────────────

    def _connect(self):
        try:
            import carla
            self._client = carla.Client(self._host, self._port)
            self._client.set_timeout(CARLA_TIMEOUT)
            self._world = self._client.get_world()
            self.get_logger().info("Connected to CARLA at %s:%d", self._host, self._port)

            if self._sync:
                settings = self._world.get_settings()
                settings.synchronous_mode = True
                settings.fixed_delta_seconds = self._delta
                self._world.apply_settings(settings)
                self.get_logger().info("Synchronous mode enabled (delta=%.3f)", self._delta)

            self._find_or_spawn_tractor()
            self._attach_sensors()
            self._publish_static_tf()
            self._start_tick_timer()

        except Exception as e:
            self.get_logger().error("CARLA connection failed: %s", str(e))
            self.create_timer(5.0, self._retry_connect)

    def _retry_connect(self):
        self.get_logger().info("Retrying CARLA connection...")
        self._connect()

    # ── Tractor & Sensors ──────────────────────────────────────────────────

    def _find_or_spawn_tractor(self):
        import carla
        actors = self._world.get_actors()
        for a in actors:
            if "vehicle" in a.type_id and a.attributes.get("role_name") == "tractor":
                self._tractor = a
                self.get_logger().info("Found existing tractor actor: %d", a.id)
                return

        # Spawn fallback vehicle if no tractor found
        bpl = self._world.get_blueprint_library()
        bp = bpl.find("vehicle.carlasad.tractor")
        if bp is None:
            vehicles = list(bpl.filter("vehicle.tesla.*"))
            bp = vehicles[0] if vehicles else None
        if bp:
            bp.set_attribute("role_name", "tractor")
            spawn_points = self._world.get_map().get_spawn_points()
            if spawn_points:
                self._tractor = self._world.try_spawn_actor(bp, spawn_points[0])
                self.get_logger().info("Spawned tractor: %d", self._tractor.id if self._tractor else -1)

    def _attach_sensors(self):
        if not self._tractor or not self._world:
            return
        import carla
        bpl = self._world.get_blueprint_library()

        # Camera publishers
        for cam_name in tc.CAMERAS:
            topic_img  = tc.CAMERA_IMAGE_TOPICS[cam_name]
            topic_info = tc.CAMERA_INFO_TOPICS[cam_name]
            self._camera_pubs[cam_name] = {
                "image": self.create_publisher(Image, topic_img, QOS_SENSOR),
                "info":  self.create_publisher(CameraInfo, topic_info, QOS_RELIABLE),
            }

        # LiDAR publishers
        for lidar_name in ["front", "top"]:
            topic = getattr(tc, f"LIDAR_{lidar_name.upper()}")
            self._lidar_pubs[lidar_name] = self.create_publisher(PointCloud2, topic, QOS_SENSOR)

        # Spawn and attach RGB cameras
        from .sensor_bridge import SensorBridge
        self._sensor_bridge = SensorBridge(self, self._world, self._tractor, bpl)
        self._sensor_bridge.attach_all()

    # ── Main Tick ──────────────────────────────────────────────────────────

    def _start_tick_timer(self):
        rate = self._delta if self._sync else 0.05
        self.create_timer(rate, self._on_tick)

    def _on_tick(self):
        if self._world is None:
            return
        if self._sync:
            frame = self._world.tick()
        else:
            snapshot = self._world.get_snapshot()
            frame = snapshot.frame

        stamp = self.get_clock().now().to_msg()

        # Clock
        clock_msg = Clock()
        clock_msg.clock = stamp
        self._pub_clock.publish(clock_msg)

        # Ego pose
        self._publish_ego_pose(stamp)

        # TF
        self._publish_dynamic_tf(stamp)

        # Process layer at 1 Hz
        if frame % 20 == 0:
            self._publish_process_layer(stamp)

    # ── Publishers ─────────────────────────────────────────────────────────

    def _publish_ego_pose(self, stamp):
        if not self._tractor:
            return
        try:
            t = self._tractor.get_transform()
            import math
            msg = PoseStamped()
            msg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
            msg.pose.position.x = t.location.x
            msg.pose.position.y = -t.location.y  # CARLA uses left-handed Y
            msg.pose.position.z = t.location.z
            yaw_rad = math.radians(-t.rotation.yaw)
            msg.pose.orientation.z = math.sin(yaw_rad / 2)
            msg.pose.orientation.w = math.cos(yaw_rad / 2)
            self._pub_ego.publish(msg)
        except Exception as e:
            self.get_logger().debug("ego pose error: %s", str(e))

    def _publish_process_layer(self, stamp):
        if not self._process:
            return
        # Update worked area from tractor position
        if self._tractor:
            t = self._tractor.get_transform()
            self._process.mark_worked(t.location.x, t.location.y)

        # Worked map OccupancyGrid
        data = self._process.to_worked_occupancy_grid()
        if data:
            msg = OccupancyGrid()
            msg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
            msg.info.resolution = float(data["resolution"])
            msg.info.width  = int(data["width"])
            msg.info.height = int(data["height"])
            msg.info.origin.position.x = float(data["origin_x"])
            msg.info.origin.position.y = float(data["origin_y"])
            msg.data = [int(v) for v in data["data"]]
            self._pub_worked.publish(msg)

        # Field boundary
        boundary = self._process.to_field_boundary_msg()
        if boundary.get("polygon"):
            bmsg = PolygonStamped()
            bmsg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
            for pt in boundary["polygon"]:
                p = Point32(x=float(pt["x"]), y=float(pt["y"]), z=0.0)
                bmsg.polygon.points.append(p)
            self._pub_boundary.publish(bmsg)

    def _publish_static_tf(self):
        import math
        transforms = []

        # Camera static transforms relative to base_link
        # Mount data inlined — carla-fork path not on sys.path in bridge container
        camera_mounts = {
            "front":       {"x": 2.0,  "y": 0.0,  "z": 2.2, "yaw": 0},
            "rear":        {"x":-1.5,  "y": 0.0,  "z": 2.2, "yaw": 180},
            "left":        {"x": 0.0,  "y":-1.2,  "z": 2.2, "yaw":-90},
            "right":       {"x": 0.0,  "y": 1.2,  "z": 2.2, "yaw": 90},
            "front_left":  {"x": 1.5,  "y":-1.0,  "z": 2.2, "yaw":-45},
            "front_right": {"x": 1.5,  "y": 1.0,  "z": 2.2, "yaw": 45},
        }
        lidar_mounts = {
            "front": {"x": 1.8, "y": 0.0, "z": 2.5, "yaw": 0},
            "top":   {"x": 0.0, "y": 0.0, "z": 3.2, "yaw": 0},
        }

        for name, m in camera_mounts.items():
            tf = self._make_static_tf(tc.TF_BASE_LINK, f"camera_{name}", m)
            transforms.append(tf)
        for name, m in lidar_mounts.items():
            tf = self._make_static_tf(tc.TF_BASE_LINK, f"lidar_{name}", m)
            transforms.append(tf)

        # GNSS, IMU, thermal at base_link origin
        for frame in ["gnss", "imu", "thermal", "radar_front"]:
            tf = self._make_static_tf(tc.TF_BASE_LINK, frame, {"x": 0, "y": 0, "z": 0, "yaw": 0})
            transforms.append(tf)

        self._static_tf_broadcaster.sendTransform(transforms)
        self.get_logger().info("Static TF published for %d sensor frames", len(transforms))

    def _make_static_tf(self, parent: str, child: str, mount: dict) -> TransformStamped:
        import math
        tf = TransformStamped()
        tf.header.stamp = self.get_clock().now().to_msg()
        tf.header.frame_id = parent
        tf.child_frame_id = child
        tf.transform.translation.x = float(mount.get("x", 0))
        tf.transform.translation.y = float(mount.get("y", 0))
        tf.transform.translation.z = float(mount.get("z", 0))
        yaw = math.radians(float(mount.get("yaw", 0)))
        tf.transform.rotation.z = math.sin(yaw / 2)
        tf.transform.rotation.w = math.cos(yaw / 2)
        return tf

    def _publish_dynamic_tf(self, stamp):
        if not self._tractor:
            return
        import math
        try:
            t = self._tractor.get_transform()
            tf = TransformStamped()
            tf.header.stamp = stamp
            tf.header.frame_id = tc.TF_ODOM
            tf.child_frame_id = tc.TF_BASE_LINK
            tf.transform.translation.x = t.location.x
            tf.transform.translation.y = -t.location.y
            tf.transform.translation.z = t.location.z
            yaw = math.radians(-t.rotation.yaw)
            tf.transform.rotation.z = math.sin(yaw / 2)
            tf.transform.rotation.w = math.cos(yaw / 2)
            self._tf_broadcaster.sendTransform(tf)
        except Exception:
            pass

    def destroy_node(self):
        for s in self._sensors:
            try:
                s.destroy()
            except Exception:
                pass
        if self._world and self._sync:
            settings = self._world.get_settings()
            settings.synchronous_mode = False
            self._world.apply_settings(settings)
        super().destroy_node()


def main():
    rclpy.init()
    node = CarlaSadBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
