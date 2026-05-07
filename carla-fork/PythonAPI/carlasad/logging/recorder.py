"""
CarlaSad session recorder.

Supports all logging modes:
  - online_debug:       sensor + tf + ego pose, no rosbag
  - dataset_recording:  sync mode, full sensors + full GT + manifests
  - scenario_replay:    fixed seeds, repeatable actor behavior
  - passive_tick:       external orchestrator ticks the sim
  - mission_log:        operator commands + route + events + sensors
"""
import json
import time
import threading
import datetime
import uuid
import logging
from pathlib import Path
from typing import Optional, Callable, Any

logger = logging.getLogger("carlasad.recorder")


class RecorderConfig:
    def __init__(
        self,
        mode: str = "online_debug",
        session_path: Optional[Path] = None,
        map_name: str = "",
        world_mode: str = "editor",
        weather_preset: str = "ClearNoon",
        sensor_rig: str = "default",
        scenario_id: Optional[str] = None,
        seed: int = 42,
        sync_mode: bool = False,
        fixed_delta: float = 0.05,
    ):
        self.mode = mode
        self.session_path = session_path or Path(f"/logs/session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.map_name = map_name
        self.world_mode = world_mode
        self.weather_preset = weather_preset
        self.sensor_rig = sensor_rig
        self.scenario_id = scenario_id
        self.seed = seed
        self.sync_mode = sync_mode
        self.fixed_delta = fixed_delta


class SessionRecorder:
    """
    Records a simulation session to disk.
    Writes:
      - manifest.json
      - gt_frames.jsonl     (ground truth per frame)
      - mission_events.jsonl (mission events)
      - process_states.jsonl (process layer snapshots)
    """

    def __init__(self, config: RecorderConfig):
        self.config = config
        self.session_id = str(uuid.uuid4())
        self.session_path = config.session_path
        self.session_path.mkdir(parents=True, exist_ok=True)

        self._gt_file = None
        self._events_file = None
        self._process_file = None
        self._frame_count = 0
        self._start_time: Optional[float] = None
        self._lock = threading.Lock()
        self._active = False

    def start(self):
        self._active = True
        self._start_time = time.time()

        # Open log files
        mode = "w"
        self._gt_file = open(self.session_path / "gt_frames.jsonl", mode)
        self._events_file = open(self.session_path / "mission_events.jsonl", mode)
        self._process_file = open(self.session_path / "process_states.jsonl", mode)

        # Write initial manifest
        from .manifest import write_session_manifest
        write_session_manifest(
            session_path=self.session_path,
            mission_id=self.session_id,
            map_name=self.config.map_name,
            world_mode=self.config.world_mode,
            weather_preset=self.config.weather_preset,
            logging_mode=self.config.mode,
            sensor_rig=self.config.sensor_rig,
            seed=self.config.seed,
            scenario_id=self.config.scenario_id,
        )
        logger.info("[Recorder] Session %s started: %s", self.session_id, self.session_path)

    def record_frame(self, frame_id: int, ground_truth: dict):
        if not self._active or self._gt_file is None:
            return
        with self._lock:
            record = {"frame": frame_id, "t": time.time() - self._start_time, **ground_truth}
            self._gt_file.write(json.dumps(record) + "\n")
            self._gt_file.flush()
            self._frame_count += 1

    def record_event(self, event_type: str, payload: dict):
        if not self._active or self._events_file is None:
            return
        with self._lock:
            record = {
                "t": time.time() - self._start_time,
                "event_type": event_type,
                **payload,
            }
            self._events_file.write(json.dumps(record) + "\n")
            self._events_file.flush()

    def record_process_state(self, process_state: dict):
        if not self._active or self._process_file is None:
            return
        with self._lock:
            record = {"t": time.time() - self._start_time, **process_state}
            self._process_file.write(json.dumps(record) + "\n")
            self._process_file.flush()

    def stop(self, error: Optional[str] = None):
        if not self._active:
            return
        self._active = False
        duration = time.time() - self._start_time if self._start_time else 0.0

        for f in (self._gt_file, self._events_file, self._process_file):
            if f:
                f.close()

        from .manifest import write_completion_manifest
        write_completion_manifest(self.session_path, duration, self._frame_count, error)
        logger.info(
            "[Recorder] Session %s stopped. Duration: %.1fs, Frames: %d",
            self.session_id, duration, self._frame_count
        )

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def elapsed(self) -> float:
        if not self._start_time:
            return 0.0
        return time.time() - self._start_time
