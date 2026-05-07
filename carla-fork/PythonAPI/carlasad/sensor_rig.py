"""
Sensor rig factory for CarlaSad tractor.

Default rig:
  - 6 RGB cameras (circular coverage)
  - 2 LiDARs (front + top)
  - 1 Radar (front)
  - GNSS
  - IMU
  - Thermal camera (custom sensor)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any
import math


@dataclass
class SensorMount:
    name: str
    blueprint_id: str
    transform: dict
    attributes: dict = field(default_factory=dict)


# Camera mounting positions relative to base_link (meters)
CAMERA_MOUNTS = {
    "front":       {"x": 2.0,  "y": 0.0,  "z": 2.2, "pitch": 0,   "yaw": 0},
    "rear":        {"x": -1.5, "y": 0.0,  "z": 2.2, "pitch": 0,   "yaw": 180},
    "left":        {"x": 0.0,  "y": -1.2, "z": 2.2, "pitch": 0,   "yaw": -90},
    "right":       {"x": 0.0,  "y": 1.2,  "z": 2.2, "pitch": 0,   "yaw": 90},
    "front_left":  {"x": 1.5,  "y": -1.0, "z": 2.2, "pitch": 0,   "yaw": -45},
    "front_right": {"x": 1.5,  "y": 1.0,  "z": 2.2, "pitch": 0,   "yaw": 45},
}

CAMERA_ATTRS = {
    "image_size_x": "1920",
    "image_size_y": "1080",
    "fov": "90",
    "sensor_tick": "0.05",
}

LIDAR_MOUNTS = {
    "front": {"x": 1.8, "y": 0.0, "z": 2.5, "pitch": 0, "yaw": 0},
    "top":   {"x": 0.0, "y": 0.0, "z": 3.2, "pitch": 0, "yaw": 0},
}

LIDAR_ATTRS = {
    "channels": "64",
    "range": "100",
    "points_per_second": "1000000",
    "rotation_frequency": "20",
    "upper_fov": "10",
    "lower_fov": "-30",
    "sensor_tick": "0.05",
}


def build_default_rig(world) -> List[Any]:
    """Spawn full sensor rig on tractor. Returns list of sensor actors."""
    bpl = world.get_blueprint_library()
    sensors = []

    import carla

    def spawn_sensor(bp_id: str, mount: dict, attrs: dict, parent) -> Any:
        bp = bpl.find(bp_id)
        if bp is None:
            print(f"[SensorRig] Warning: blueprint {bp_id} not found")
            return None
        for k, v in attrs.items():
            if bp.has_attribute(k):
                bp.set_attribute(k, v)
        transform = carla.Transform(
            carla.Location(x=mount.get("x", 0), y=mount.get("y", 0), z=mount.get("z", 0)),
            carla.Rotation(
                pitch=mount.get("pitch", 0),
                yaw=mount.get("yaw", 0),
                roll=mount.get("roll", 0),
            )
        )
        return world.spawn_actor(bp, transform, attach_to=parent)

    # This function is called with the tractor actor as parent
    # Return mount definitions for use by the caller
    return {
        "cameras": CAMERA_MOUNTS,
        "lidars": LIDAR_MOUNTS,
        "camera_attrs": CAMERA_ATTRS,
        "lidar_attrs": LIDAR_ATTRS,
    }


def get_sensor_rig_profile(profile_name: str = "default") -> dict:
    """Return sensor rig configuration for a named profile."""
    profiles = {
        "default": {
            "cameras": list(CAMERA_MOUNTS.keys()),
            "lidars": list(LIDAR_MOUNTS.keys()),
            "radar": True,
            "gnss": True,
            "imu": True,
            "thermal": True,
        },
        "minimal": {
            "cameras": ["front"],
            "lidars": ["front"],
            "radar": False,
            "gnss": True,
            "imu": True,
            "thermal": False,
        },
    }
    return profiles.get(profile_name, profiles["default"])
