"""
Ground Truth Bridge — attaches GT cameras to tractor and publishes to ROS2.

Sensors:
  - semantic segmentation camera → /carlasad/ground_truth/semantic
  - instance segmentation camera → /carlasad/ground_truth/instance
  - depth camera                 → /carlasad/ground_truth/depth
  - actor GT publisher           → /carlasad/ground_truth/objects

All GT data is published in sync with the main sensor tick.
"""
import struct
import numpy as np
from std_msgs.msg import Header
from sensor_msgs.msg import Image, PointCloud2, PointField
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from . import topic_contract as tc

QOS_RELIABLE = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    history=HistoryPolicy.KEEP_LAST,
    depth=5,
)

# CARLA semantic label → CarlaSad terrain label (IDs 100–114 from CLAUDE.md)
CARLA_TO_CARLASAD_LABEL: dict[int, int] = {
    # CARLA default labels
    0:  0,    # unlabeled
    1:  100,  # building → normal_field (fallback)
    4:  106,  # pedestrian → drivable_path
    6:  100,  # vegetation (general) → normal_field
    7:  100,  # terrain → normal_field
    8:  106,  # road → drivable_path
    9:  106,  # sidewalk → drivable_path
    # CarlaSad custom labels are set via UE semantic paint:
    # 100–114 pass through directly when using custom semantic IDs
}


class GTBridge:
    """
    Attaches ground truth cameras to tractor actor and publishes GT topics.
    Should be initialized after the tractor is available.
    """

    def __init__(self, node: Node, world, tractor, bpl):
        self._node = node
        self._world = world
        self._tractor = tractor
        self._bpl = bpl
        self._actors: list = []

        self._pub_semantic = node.create_publisher(Image, tc.GT_SEMANTIC, QOS_RELIABLE)
        self._pub_instance = node.create_publisher(Image, tc.GT_INSTANCE, QOS_RELIABLE)
        self._pub_depth    = node.create_publisher(Image, tc.GT_DEPTH,    QOS_RELIABLE)

    def attach_all(self):
        self._attach_semantic_camera()
        self._attach_instance_camera()
        self._attach_depth_camera()

    def destroy(self):
        for a in self._actors:
            try:
                a.destroy()
            except Exception:
                pass

    # ── Semantic Segmentation ──────────────────────────────────────────────

    def _attach_semantic_camera(self):
        import carla
        bp = self._bpl.find("sensor.camera.semantic_segmentation")
        if bp is None:
            return
        bp.set_attribute("image_size_x", "960")
        bp.set_attribute("image_size_y", "540")
        bp.set_attribute("fov", "90")
        bp.set_attribute("sensor_tick", "0.1")

        # Mount at same position as front camera
        transform = carla.Transform(
            carla.Location(x=2.0, y=0.0, z=2.2),
            carla.Rotation(yaw=0),
        )
        sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
        self._actors.append(sensor)
        sensor.listen(self._on_semantic)

    def _on_semantic(self, data):
        stamp = self._node.get_clock().now().to_msg()
        # CARLA semantic image: BGRA where R channel = semantic label ID
        raw = np.frombuffer(data.raw_data, dtype=np.uint8).reshape(data.height, data.width, 4)
        labels = raw[:, :, 2].copy()  # R channel has label ID in CARLA format

        # Remap to CarlaSad labels
        remapped = np.zeros_like(labels)
        for carla_id, sad_id in CARLA_TO_CARLASAD_LABEL.items():
            remapped[labels == carla_id] = sad_id
        # Labels >= 100 are already CarlaSad custom — pass through
        custom_mask = labels >= 100
        remapped[custom_mask] = labels[custom_mask]

        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera_front")
        msg.height   = data.height
        msg.width    = data.width
        msg.encoding = "mono8"
        msg.step     = data.width
        msg.data     = remapped.tobytes()
        self._pub_semantic.publish(msg)

    # ── Instance Segmentation ──────────────────────────────────────────────

    def _attach_instance_camera(self):
        import carla
        bp = self._bpl.find("sensor.camera.instance_segmentation")
        if bp is None:
            # Fallback to semantic if instance not available
            self._node.get_logger().info(
                "Instance segmentation camera not available, using semantic fallback"
            )
            return
        bp.set_attribute("image_size_x", "960")
        bp.set_attribute("image_size_y", "540")
        bp.set_attribute("fov", "90")
        bp.set_attribute("sensor_tick", "0.1")

        transform = carla.Transform(
            carla.Location(x=2.0, y=0.0, z=2.2),
            carla.Rotation(yaw=0),
        )
        sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
        self._actors.append(sensor)
        sensor.listen(self._on_instance)

    def _on_instance(self, data):
        stamp = self._node.get_clock().now().to_msg()
        # Instance image: BGRA where G=instance_id_high, B=instance_id_low, R=semantic
        raw = np.frombuffer(data.raw_data, dtype=np.uint8).reshape(data.height, data.width, 4)

        # Encode instance ID as 16-bit per pixel (G*256 + B)
        instance_16 = (raw[:, :, 1].astype(np.uint16) << 8) | raw[:, :, 0].astype(np.uint16)
        # Publish as 16UC1
        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera_front")
        msg.height   = data.height
        msg.width    = data.width
        msg.encoding = "16UC1"
        msg.step     = data.width * 2
        msg.data     = instance_16.tobytes()
        self._pub_instance.publish(msg)

    # ── Depth ──────────────────────────────────────────────────────────────

    def _attach_depth_camera(self):
        import carla
        bp = self._bpl.find("sensor.camera.depth")
        if bp is None:
            return
        bp.set_attribute("image_size_x", "960")
        bp.set_attribute("image_size_y", "540")
        bp.set_attribute("fov", "90")
        bp.set_attribute("sensor_tick", "0.1")

        transform = carla.Transform(
            carla.Location(x=2.0, y=0.0, z=2.2),
            carla.Rotation(yaw=0),
        )
        sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
        self._actors.append(sensor)
        sensor.listen(self._on_depth)

    def _on_depth(self, data):
        stamp = self._node.get_clock().now().to_msg()
        # CARLA depth encoding: depth_m = (R + G*256 + B*256^2) / (256^3 - 1) * 1000
        raw = np.frombuffer(data.raw_data, dtype=np.uint8).reshape(data.height, data.width, 4)
        r = raw[:, :, 0].astype(np.float32)
        g = raw[:, :, 1].astype(np.float32)
        b = raw[:, :, 2].astype(np.float32)
        depth_m = (r + g * 256.0 + b * 256.0 * 256.0) / (256.0 ** 3 - 1.0) * 1000.0

        # Publish as 32FC1 (meters)
        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera_front")
        msg.height   = data.height
        msg.width    = data.width
        msg.encoding = "32FC1"
        msg.step     = data.width * 4
        msg.data     = depth_m.astype(np.float32).tobytes()
        self._pub_depth.publish(msg)

    # ── Object GT Publisher ────────────────────────────────────────────────

    def publish_objects_gt(self, stamp, terrain_layer=None):
        """Publish all actor ground truth as ObjectArray."""
        from std_msgs.msg import Header as Hdr
        actors = self._world.get_actors()

        try:
            from carlasad_msgs.msg import ObjectArray, ObjectState
            msg = ObjectArray()
            msg.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
            for actor in actors:
                if "vehicle" not in actor.type_id and "walker" not in actor.type_id:
                    continue
                t = actor.get_transform()
                v = actor.get_velocity()
                obj = ObjectState()
                obj.header = Header(stamp=stamp, frame_id=tc.TF_MAP)
                obj.id       = actor.id
                obj.type_id  = actor.type_id
                obj.role_name = actor.attributes.get("role_name", "")
                obj.pose.position.x =  t.location.x
                obj.pose.position.y = -t.location.y
                obj.pose.position.z =  t.location.z
                obj.twist.linear.x =  v.x
                obj.twist.linear.y = -v.y
                obj.twist.linear.z =  v.z
                if terrain_layer:
                    obj.terrain_label_id = terrain_layer.get_label(t.location.x, t.location.y)
                    obj.terrain_risk      = terrain_layer.get_risk(t.location.x, t.location.y)
                msg.objects.append(obj)

            if not hasattr(self._node, "_pub_objects_gt"):
                self._node._pub_objects_gt = self._node.create_publisher(
                    ObjectArray, tc.GT_OBJECTS, QOS_RELIABLE
                )
            self._node._pub_objects_gt.publish(msg)
        except ImportError:
            pass  # carlasad_msgs not built yet
