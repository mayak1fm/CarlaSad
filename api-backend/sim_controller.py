"""
Simulation controller — manages mission lifecycle, actor spawning, recording.
Bridges the API layer to CARLA and the logging system.
"""
import asyncio
import datetime
import uuid
import logging
import json
from pathlib import Path
from typing import Optional, List

from carla_client import carla_client
from models.mission import MissionRequest, MissionStatus, MissionEvent, set_active_mission, get_active_mission

LOG_DIR = Path("/logs")
logger = logging.getLogger("carlasad.sim_controller")


class SimController:
    """Manages the full mission lifecycle."""

    def __init__(self):
        self._tractor_actor = None
        self._recording_proc: Optional[asyncio.subprocess.Process] = None
        self._session_path: Optional[Path] = None
        self._tick_task: Optional[asyncio.Task] = None
        self._state_callbacks: List = []
        self._passive_tick_task: Optional[asyncio.Task] = None
        self._passive_tick_running: bool = False

    # ── Mission ────────────────────────────────────────────────────────────

    async def start_mission(self, req: MissionRequest) -> str:
        mission_id = str(uuid.uuid4())
        session_name = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{mission_id[:6]}"
        self._session_path = LOG_DIR / session_name
        self._session_path.mkdir(parents=True, exist_ok=True)

        await carla_client.ensure_connected()

        carla_client.load_world(req.map_name)
        carla_client.set_weather(req.weather_preset)

        if req.logging_mode in ("dataset_recording", "scenario_replay"):
            carla_client.set_sync_mode(True)

        self._tractor_actor = carla_client.spawn_tractor()

        if req.logging_mode != "online_debug":
            await self._start_rosbag(session_name)

        self._write_manifest(req, mission_id, session_name)

        status = MissionStatus(
            state="running",
            mission_id=mission_id,
            progress=0.0,
            elapsed_seconds=0.0,
        )
        set_active_mission(status)
        self._broadcast_event("mission_started", {"mission_id": mission_id})
        logger.info("Mission %s started, session: %s", mission_id, session_name)
        return mission_id

    async def stop_mission(self):
        if self._recording_proc:
            self._recording_proc.terminate()
            self._recording_proc = None

        carla_client.set_sync_mode(False)

        mission = get_active_mission()
        mission.state = "completed"
        mission.progress = 1.0
        set_active_mission(mission)
        self._broadcast_event("mission_stopped", {})
        logger.info("Mission stopped")

    async def pause_sim(self):
        if carla_client.is_connected():
            carla_client.set_sync_mode(True, 0.0)
        mission = get_active_mission()
        mission.state = "paused"
        set_active_mission(mission)
        self._broadcast_event("sim_paused", {})

    async def resume_sim(self):
        if carla_client.is_connected():
            carla_client.set_sync_mode(False)
        mission = get_active_mission()
        if mission.state == "paused":
            mission.state = "running"
        set_active_mission(mission)
        self._broadcast_event("sim_resumed", {})

    # ── Passive tick mode ──────────────────────────────────────────────────
    # Used when an external orchestrator drives the simulation step-by-step.
    # CARLA stays in sync mode; the API backend just echoes state without
    # advancing the clock itself. The external caller sends POST /api/v1/sim/tick.

    async def enter_passive_tick_mode(self, fixed_delta_seconds: float = 0.05):
        """
        Switch CARLA to sync mode without starting an internal tick loop.
        External orchestrator must call /api/v1/sim/tick to advance.
        """
        await carla_client.ensure_connected()
        carla_client.set_sync_mode(True, fixed_delta_seconds)
        self._passive_tick_running = True
        logger.info("Passive tick mode enabled (delta=%.3f s)", fixed_delta_seconds)
        self._broadcast_event("passive_tick_started", {"delta_seconds": fixed_delta_seconds})

    async def exit_passive_tick_mode(self):
        self._passive_tick_running = False
        if carla_client.is_connected():
            carla_client.set_sync_mode(False)
        logger.info("Passive tick mode disabled")
        self._broadcast_event("passive_tick_stopped", {})

    async def tick_once(self) -> dict:
        """Advance simulation by one tick. Only valid in passive or sync mode."""
        if not carla_client.is_connected():
            raise RuntimeError("CARLA not connected")
        frame_id = carla_client.tick()
        return {"frame_id": frame_id, "status": "ok"}

    @property
    def is_passive_tick_mode(self) -> bool:
        return self._passive_tick_running

    # ── Recording ──────────────────────────────────────────────────────────

    async def _start_rosbag(self, session_name: str):
        bag_path = self._session_path / "rosbag2"
        bag_path.mkdir(exist_ok=True)
        topics = [
            "/tractor/camera_front/image_raw",
            "/tractor/lidar/front/points",
            "/tractor/lidar/top/points",
            "/tractor/gnss",
            "/tractor/imu",
            "/carlasad/ground_truth/ego_pose",
            "/carlasad/ground_truth/objects",
            "/carlasad/process/worked_map",
            "/carlasad/process/worked_edge",
            "/carlasad/process/field_boundary",
            "/carlasad/world_info",
            "/tf",
            "/tf_static",
            "/carla/clock",
        ]
        cmd = (
            f"ros2 bag record -o {bag_path} " +
            " ".join(topics)
        )
        try:
            self._recording_proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            logger.info("rosbag2 recording started: %s", bag_path)
        except Exception as e:
            logger.warning("rosbag2 not available: %s", e)

    # ── Manifest ───────────────────────────────────────────────────────────

    def _write_manifest(self, req: MissionRequest, mission_id: str, session_name: str):
        manifest = {
            "mission_id": mission_id,
            "session_name": session_name,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "map": req.map_name,
            "world_mode": req.world_mode,
            "weather_preset": req.weather_preset,
            "logging_mode": req.logging_mode,
            "sensor_rig_profile": req.sensor_rig_profile,
            "seed": req.seed,
            "carla_status": carla_client.get_status(),
        }
        (self._session_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2)
        )

    # ── State broadcast ────────────────────────────────────────────────────

    def register_state_callback(self, callback):
        self._state_callbacks.append(callback)

    def unregister_state_callback(self, callback):
        self._state_callbacks.discard(callback) if hasattr(self._state_callbacks, 'discard') else None
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def _broadcast_event(self, event_type: str, payload: dict):
        import time
        event = MissionEvent(
            timestamp=time.time(),
            event_type=event_type,
            payload=payload,
        )
        for cb in list(self._state_callbacks):
            try:
                cb(event)
            except Exception:
                pass

    def get_ego_pose(self) -> dict:
        if not self._tractor_actor:
            return {}
        try:
            t = self._tractor_actor.get_transform()
            v = self._tractor_actor.get_velocity()
            return {
                "x": round(t.location.x, 3),
                "y": round(t.location.y, 3),
                "z": round(t.location.z, 3),
                "yaw": round(t.rotation.yaw, 2),
                "vx": round(v.x, 3),
                "vy": round(v.y, 3),
            }
        except Exception:
            return {}


# Global singleton
sim_controller = SimController()
