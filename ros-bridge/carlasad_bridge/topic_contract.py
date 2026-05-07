"""
CarlaSad ROS2 Topic Contract — canonical topic definitions.

This file is the single source of truth for all topic names and QoS profiles.
Must stay in sync with: api-backend, real tractor software, carlasad_msgs.

NEVER change topic names without checking real tractor compatibility.
"""

# ── Tractor Namespace ──────────────────────────────────────────────────────

TRACTOR_NS = "/tractor"
CARLASAD_NS = "/carlasad"

# ── Camera Topics ──────────────────────────────────────────────────────────

CAMERAS = ["front", "rear", "left", "right", "front_left", "front_right"]

def camera_image(name: str) -> str:
    return f"{TRACTOR_NS}/camera_{name}/image_raw"

def camera_info(name: str) -> str:
    return f"{TRACTOR_NS}/camera_{name}/camera_info"

CAMERA_IMAGE_TOPICS = {name: camera_image(name) for name in CAMERAS}
CAMERA_INFO_TOPICS = {name: camera_info(name) for name in CAMERAS}

# ── LiDAR Topics ──────────────────────────────────────────────────────────

LIDAR_FRONT = f"{TRACTOR_NS}/lidar/front/points"
LIDAR_TOP   = f"{TRACTOR_NS}/lidar/top/points"

# ── Other Sensor Topics ───────────────────────────────────────────────────

RADAR_FRONT = f"{TRACTOR_NS}/radar/front"
GNSS        = f"{TRACTOR_NS}/gnss"
IMU         = f"{TRACTOR_NS}/imu"
THERMAL     = f"{TRACTOR_NS}/thermal/image_raw"

# ── Ground Truth Topics ───────────────────────────────────────────────────

GT_EGO_POSE = f"{CARLASAD_NS}/ground_truth/ego_pose"
GT_OBJECTS  = f"{CARLASAD_NS}/ground_truth/objects"
GT_SEMANTIC = f"{CARLASAD_NS}/ground_truth/semantic"
GT_INSTANCE = f"{CARLASAD_NS}/ground_truth/instance"
GT_DEPTH    = f"{CARLASAD_NS}/ground_truth/depth"

# ── Process Layer Topics ──────────────────────────────────────────────────

PROCESS_WORKED_MAP    = f"{CARLASAD_NS}/process/worked_map"
PROCESS_WORKED_EDGE   = f"{CARLASAD_NS}/process/worked_edge"
PROCESS_FIELD_BOUNDARY = f"{CARLASAD_NS}/process/field_boundary"
PROCESS_TERRAIN_CLASSES = f"{CARLASAD_NS}/process/terrain_classes"
PROCESS_RISK_MAP      = f"{CARLASAD_NS}/process/risk_map"

# ── Mission Topics ─────────────────────────────────────────────────────────

MISSION_STATE  = f"{CARLASAD_NS}/mission/state"
MISSION_ROUTE  = f"{CARLASAD_NS}/mission/route"
MISSION_EVENTS = f"{CARLASAD_NS}/mission/events"

# ── World & Clock ──────────────────────────────────────────────────────────

CLOCK      = "/carla/clock"
WORLD_INFO = f"{CARLASAD_NS}/world_info"

# ── TF Frames ─────────────────────────────────────────────────────────────

TF_MAP       = "map"
TF_ODOM      = "odom"
TF_BASE_LINK = "base_link"
TF_CAMERA_PREFIX = "camera_"
TF_LIDAR_FRONT = "lidar_front"
TF_LIDAR_TOP   = "lidar_top"
TF_RADAR_FRONT = "radar_front"
TF_GNSS        = "gnss"
TF_IMU         = "imu"
TF_THERMAL     = "thermal"

SENSOR_FRAMES = (
    [f"camera_{name}" for name in CAMERAS] +
    [TF_LIDAR_FRONT, TF_LIDAR_TOP, TF_RADAR_FRONT, TF_GNSS, TF_IMU, TF_THERMAL]
)
