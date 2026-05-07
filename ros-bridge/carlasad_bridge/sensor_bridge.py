"""
Sensor bridge — attaches CARLA sensors to the tractor and publishes to ROS2.

For each sensor:
  - Creates CARLA blueprint with correct parameters
  - Spawns actor attached to tractor
  - Registers callback that converts CARLA data → ROS2 message
  - Publishes on the canonical topic
"""
import math
import time
import numpy as np
from std_msgs.msg import Header
from sensor_msgs.msg import Image, CameraInfo, PointCloud2, PointField, NavSatFix, Imu
from geometry_msgs.msg import Vector3, Quaternion
from rclpy.node import Node

from . import topic_contract as tc

# Camera mounting positions relative to base_link (x fwd, y left, z up)
CAMERA_MOUNTS = {
    "front":       {"x": 2.0,  "y": 0.0,  "z": 2.2, "pitch": 0,   "yaw": 0},
    "rear":        {"x":-1.5,  "y": 0.0,  "z": 2.2, "pitch": 0,   "yaw": 180},
    "left":        {"x": 0.0,  "y":-1.2,  "z": 2.2, "pitch": 0,   "yaw":-90},
    "right":       {"x": 0.0,  "y": 1.2,  "z": 2.2, "pitch": 0,   "yaw": 90},
    "front_left":  {"x": 1.5,  "y":-1.0,  "z": 2.2, "pitch": 0,   "yaw":-45},
    "front_right": {"x": 1.5,  "y": 1.0,  "z": 2.2, "pitch": 0,   "yaw": 45},
}

CAMERA_ATTRS = {
    "image_size_x": "1920", "image_size_y": "1080",
    "fov": "90", "sensor_tick": "0.05",
}

LIDAR_MOUNTS = {
    "front": {"x": 1.8, "y": 0.0, "z": 2.5, "pitch": 0, "yaw": 0},
    "top":   {"x": 0.0, "y": 0.0, "z": 3.2, "pitch": 0, "yaw": 0},
}

LIDAR_ATTRS = {
    "channels": "64", "range": "100",
    "points_per_second": "1000000",
    "rotation_frequency": "20",
    "upper_fov": "10", "lower_fov": "-30",
    "sensor_tick": "0.05",
}


class SensorBridge:
    def __init__(self, node: Node, world, tractor, bpl):
        self._node = node
        self._world = world
        self._tractor = tractor
        self._bpl = bpl
        self._actors: list = []

    def attach_all(self):
        self._attach_cameras()
        self._attach_lidars()
        self._attach_gnss()
        self._attach_imu()

    def destroy(self):
        for a in self._actors:
            try:
                a.destroy()
            except Exception:
                pass

    # ── Cameras ────────────────────────────────────────────────────────────

    def _attach_cameras(self):
        import carla
        bp = self._bpl.find("sensor.camera.rgb")
        if bp is None:
            self._node.get_logger().warning("RGB camera blueprint not found")
            return

        for name, mount in CAMERA_MOUNTS.items():
            for k, v in CAMERA_ATTRS.items():
                if bp.has_attribute(k):
                    bp.set_attribute(k, v)

            transform = carla.Transform(
                carla.Location(x=mount["x"], y=mount["y"], z=mount["z"]),
                carla.Rotation(pitch=mount.get("pitch", 0), yaw=mount.get("yaw", 0)),
            )
            sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
            self._actors.append(sensor)

            pub_image = self._node._camera_pubs[name]["image"]
            pub_info  = self._node._camera_pubs[name]["info"]
            frame_id  = f"camera_{name}"

            sensor.listen(lambda data, p=pub_image, pi=pub_info, fid=frame_id:
                          self._on_camera(data, p, pi, fid))

    def _on_camera(self, data, pub_image, pub_info, frame_id: str):
        stamp = self._node.get_clock().now().to_msg()

        # Image message
        img_msg = Image()
        img_msg.header = Header(stamp=stamp, frame_id=frame_id)
        img_msg.height = data.height
        img_msg.width  = data.width
        img_msg.encoding = "bgra8"
        img_msg.step = 4 * data.width
        img_msg.data = bytes(data.raw_data)
        pub_image.publish(img_msg)

        # CameraInfo
        info_msg = CameraInfo()
        info_msg.header = Header(stamp=stamp, frame_id=frame_id)
        info_msg.height = data.height
        info_msg.width  = data.width
        fov_rad = math.radians(float(CAMERA_ATTRS["fov"]))
        fx = data.width / (2.0 * math.tan(fov_rad / 2.0))
        cx = data.width  / 2.0
        cy = data.height / 2.0
        info_msg.k = [fx, 0.0, cx, 0.0, fx, cy, 0.0, 0.0, 1.0]
        info_msg.p = [fx, 0.0, cx, 0.0, 0.0, fx, cy, 0.0, 0.0, 0.0, 1.0, 0.0]
        info_msg.distortion_model = "plumb_bob"
        info_msg.d = [0.0, 0.0, 0.0, 0.0, 0.0]
        pub_info.publish(info_msg)

    # ── LiDARs ─────────────────────────────────────────────────────────────

    def _attach_lidars(self):
        import carla
        bp = self._bpl.find("sensor.lidar.ray_cast")
        if bp is None:
            self._node.get_logger().warning("LiDAR blueprint not found")
            return

        for name, mount in LIDAR_MOUNTS.items():
            for k, v in LIDAR_ATTRS.items():
                if bp.has_attribute(k):
                    bp.set_attribute(k, v)

            transform = carla.Transform(
                carla.Location(x=mount["x"], y=mount["y"], z=mount["z"]),
                carla.Rotation(yaw=mount.get("yaw", 0)),
            )
            sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
            self._actors.append(sensor)

            pub = self._node._lidar_pubs[name]
            frame_id = f"lidar_{name}"
            sensor.listen(lambda data, p=pub, fid=frame_id: self._on_lidar(data, p, fid))

    def _on_lidar(self, data, pub, frame_id: str):
        stamp = self._node.get_clock().now().to_msg()
        points = np.frombuffer(data.raw_data, dtype=np.float32).reshape(-1, 4)

        msg = PointCloud2()
        msg.header = Header(stamp=stamp, frame_id=frame_id)
        msg.height = 1
        msg.width  = points.shape[0]
        msg.is_dense = False
        msg.is_bigendian = False
        msg.point_step = 16  # 4 float32

        fields = []
        for i, name in enumerate(["x", "y", "z", "intensity"]):
            f = PointField()
            f.name = name
            f.offset = i * 4
            f.datatype = PointField.FLOAT32
            f.count = 1
            fields.append(f)
        msg.fields = fields
        msg.row_step = msg.point_step * msg.width

        # CARLA → ROS2 coordinate conversion (left-handed → right-handed)
        pts_ros = points.copy()
        pts_ros[:, 1] = -pts_ros[:, 1]  # flip Y
        msg.data = pts_ros.tobytes()
        pub.publish(msg)

    # ── GNSS ───────────────────────────────────────────────────────────────

    def _attach_gnss(self):
        import carla
        bp = self._bpl.find("sensor.other.gnss")
        if bp is None:
            return
        bp.set_attribute("sensor_tick", "0.1")
        transform = carla.Transform(carla.Location(x=0, y=0, z=2.0))
        sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
        self._actors.append(sensor)

        pub = self._node.create_publisher(NavSatFix, tc.GNSS, 10)
        sensor.listen(lambda data, p=pub: self._on_gnss(data, p))

    def _on_gnss(self, data, pub):
        stamp = self._node.get_clock().now().to_msg()
        msg = NavSatFix()
        msg.header = Header(stamp=stamp, frame_id=tc.TF_GNSS)
        msg.latitude  = data.latitude
        msg.longitude = data.longitude
        msg.altitude  = data.altitude
        msg.status.status = 0  # FIX
        pub.publish(msg)

    # ── IMU ────────────────────────────────────────────────────────────────

    def _attach_imu(self):
        import carla
        bp = self._bpl.find("sensor.other.imu")
        if bp is None:
            return
        bp.set_attribute("sensor_tick", "0.02")
        transform = carla.Transform(carla.Location(x=0, y=0, z=1.0))
        sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
        self._actors.append(sensor)

        pub = self._node.create_publisher(Imu, tc.IMU, 10)
        sensor.listen(lambda data, p=pub: self._on_imu(data, p))

    def _on_imu(self, data, pub):
        stamp = self._node.get_clock().now().to_msg()
        msg = Imu()
        msg.header = Header(stamp=stamp, frame_id=tc.TF_IMU)
        msg.linear_acceleration.x =  data.accelerometer.x
        msg.linear_acceleration.y = -data.accelerometer.y
        msg.linear_acceleration.z =  data.accelerometer.z
        msg.angular_velocity.x =  data.gyroscope.x
        msg.angular_velocity.y = -data.gyroscope.y
        msg.angular_velocity.z =  data.gyroscope.z
        # Orientation from compass
        yaw = math.radians(-data.compass)
        msg.orientation.z = math.sin(yaw / 2)
        msg.orientation.w = math.cos(yaw / 2)
        pub.publish(msg)

    # ── Thermal Camera (custom sensor via RGB + simulated thermal) ─────────

    def attach_thermal(self):
        """
        Thermal camera: uses CARLA RGB camera with thermal-like parameters.
        Real thermal sensor requires C++ CARLA plugin (see
        carla-fork/Unreal/.../ThermalCamera.h).
        This version uses semantic segmentation as a proxy for thermal response.
        """
        import carla
        bp = self._bpl.find("sensor.camera.semantic_segmentation")
        if bp is None:
            self._node.get_logger().warning("Thermal proxy: semantic camera not found")
            return
        bp.set_attribute("image_size_x", "640")
        bp.set_attribute("image_size_y", "480")
        bp.set_attribute("fov", "45")      # thermal typically narrower FOV
        bp.set_attribute("sensor_tick", "0.1")

        transform = carla.Transform(
            carla.Location(x=2.0, y=0.0, z=2.2),
            carla.Rotation(pitch=-5, yaw=0),
        )
        sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
        self._actors.append(sensor)

        pub = self._node.create_publisher(Image, tc.THERMAL, 10)
        sensor.listen(lambda data, p=pub: self._on_thermal(data, p))
        self._node.get_logger().info("Thermal camera (proxy) attached")

    def _on_thermal(self, data, pub):
        """
        Convert CARLA semantic image to simulated thermal response.
        Real thermal: humans (hot) = bright, vegetation = cool, ground = medium.
        Semantic label → temperature mapping:
          person(4) → 310K, vehicle(10) → 330K, vegetation(9) → 280K, terrain(7) → 288K
        Output: mono16 (Kelvin * 10 for 0.1K resolution)
        """
        import numpy as np
        LABEL_TO_TEMP_K = {
            0:  288,   # unlabeled → ambient
            4:  310,   # person → body temp ~37°C
            6:  282,   # vegetation → cool
            7:  288,   # terrain → ambient
            8:  295,   # road
            10: 330,   # vehicle → engine heat
        }
        raw = np.frombuffer(data.raw_data, dtype=np.uint8).reshape(data.height, data.width, 4)
        labels = raw[:, :, 2]  # R channel = semantic label

        temp_map = np.full((data.height, data.width), 288, dtype=np.float32)
        for label_id, temp in LABEL_TO_TEMP_K.items():
            temp_map[labels == label_id] = temp

        # Add Gaussian noise (sensor noise ~0.05K)
        noise = np.random.normal(0, 0.5, temp_map.shape).astype(np.float32)
        temp_map = np.clip(temp_map + noise, 250, 400)
        thermal_16 = (temp_map * 10).astype(np.uint16)

        msg = Image()
        msg.header = Header(stamp=self._node.get_clock().now().to_msg(), frame_id=tc.TF_THERMAL)
        msg.height   = data.height
        msg.width    = data.width
        msg.encoding = "16UC1"
        msg.step     = data.width * 2
        msg.data     = thermal_16.tobytes()
        pub.publish(msg)

    # ── Radar ──────────────────────────────────────────────────────────────

    def attach_radar(self):
        import carla
        from radar_msgs.msg import RadarReturn, RadarScan
        bp = self._bpl.find("sensor.other.radar")
        if bp is None:
            self._node.get_logger().warning("Radar blueprint not found")
            return
        bp.set_attribute("horizontal_fov", "35")
        bp.set_attribute("vertical_fov",   "10")
        bp.set_attribute("range",          "70")
        bp.set_attribute("points_per_second", "1500")
        bp.set_attribute("sensor_tick",    "0.05")

        transform = carla.Transform(
            carla.Location(x=2.2, y=0.0, z=1.0),
            carla.Rotation(yaw=0),
        )
        sensor = self._world.spawn_actor(bp, transform, attach_to=self._tractor)
        self._actors.append(sensor)

        pub = self._node.create_publisher(RadarScan, tc.RADAR_FRONT, 10)
        sensor.listen(lambda data, p=pub: self._on_radar(data, p))
        self._node.get_logger().info("Radar attached")

    def _on_radar(self, data, pub):
        stamp = self._node.get_clock().now().to_msg()
        try:
            from radar_msgs.msg import RadarReturn, RadarScan
        except ImportError:
            self._node.get_logger().warning("radar_msgs not installed", once=True)
            return

        msg = RadarScan()
        msg.header = Header(stamp=stamp, frame_id=tc.TF_RADAR_FRONT)

        for detect in data:
            r = RadarReturn()
            r.range         = detect.depth
            r.azimuth       = detect.azimuth
            r.elevation     = detect.altitude
            r.doppler_velocity = detect.velocity
            r.amplitude     = 1.0  # CARLA doesn't provide amplitude
            msg.returns.append(r)

        pub.publish(msg)
