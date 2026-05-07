"""
CarlaSad session replay engine.

Reads a recorded session and replays it in CARLA:
  - Loads the same map and weather
  - Restores actor positions per frame
  - Optionally replays rosbag2 in parallel
  - Supports deterministic re-run with same seed
"""
import json
import time
import logging
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Iterator

logger = logging.getLogger("carlasad.replay")


def iter_gt_frames(session_path: Path) -> Iterator[dict]:
    gt_file = session_path / "gt_frames.jsonl"
    if not gt_file.exists():
        logger.warning("No gt_frames.jsonl in %s", session_path)
        return
    with open(gt_file) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_manifest(session_path: Path) -> dict:
    manifest_path = session_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json in {session_path}")
    return json.loads(manifest_path.read_text())


class SessionReplayer:
    """
    Replays a recorded session in CARLA.
    Deterministic: same map, same seed, same actor positions.
    """

    def __init__(self, session_path: Path, carla_host: str = "localhost", carla_port: int = 2000):
        self.session_path = Path(session_path)
        self.carla_host = carla_host
        self.carla_port = carla_port
        self._client = None
        self._world = None
        self._rosbag_proc: Optional[subprocess.Popen] = None

    def prepare(self) -> dict:
        manifest = load_manifest(self.session_path)
        logger.info("[Replay] Session: %s", manifest.get("mission_id"))
        logger.info("[Replay] Map: %s, Mode: %s", manifest.get("map"), manifest.get("world_mode"))
        logger.info("[Replay] Weather: %s, Seed: %s", manifest.get("weather_preset"), manifest.get("seed"))

        import carla
        self._client = carla.Client(self.carla_host, self.carla_port)
        self._client.set_timeout(10.0)
        self._world = self._client.load_world(manifest["map"])

        # Restore weather
        weather_name = manifest.get("weather_preset", "ClearNoon")
        preset = getattr(carla.WeatherParameters, weather_name, carla.WeatherParameters.ClearNoon)
        self._world.set_weather(preset)

        # Enable sync mode for deterministic replay
        settings = self._world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = manifest.get("fixed_delta_seconds", 0.05) or 0.05
        self._world.apply_settings(settings)

        return manifest

    def replay(self, speed: float = 1.0, replay_rosbag: bool = True):
        manifest = self.prepare()
        frames = list(iter_gt_frames(self.session_path))

        if not frames:
            logger.warning("[Replay] No frames to replay")
            return

        logger.info("[Replay] Replaying %d frames...", len(frames))

        if replay_rosbag:
            self._start_rosbag_replay()

        prev_t = frames[0].get("t", 0.0)
        start_wall = time.time()

        for frame_data in frames:
            frame_t = frame_data.get("t", 0.0)
            dt = (frame_t - prev_t) / speed
            if dt > 0:
                time.sleep(dt)
            prev_t = frame_t

            self._restore_frame(frame_data)
            self._world.tick()

        elapsed = time.time() - start_wall
        logger.info("[Replay] Done. Wall time: %.1fs", elapsed)
        self._cleanup()

    def _restore_frame(self, frame_data: dict):
        import carla
        ego = frame_data.get("ego_pose")
        if not ego:
            return
        actors = self._world.get_actors()
        for actor in actors.filter("vehicle.*"):
            if actor.attributes.get("role_name") == "tractor":
                t = carla.Transform(
                    carla.Location(x=ego["x"], y=ego["y"], z=ego["z"]),
                    carla.Rotation(yaw=ego.get("yaw", 0)),
                )
                actor.set_transform(t)
                break

    def _start_rosbag_replay(self):
        bag_path = self.session_path / "rosbag2"
        if not bag_path.exists():
            logger.info("[Replay] No rosbag2 directory, skipping bag replay")
            return
        try:
            self._rosbag_proc = subprocess.Popen(
                ["ros2", "bag", "play", str(bag_path), "--clock"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info("[Replay] rosbag2 replay started")
        except FileNotFoundError:
            logger.warning("[Replay] ros2 not found, skipping rosbag replay")

    def _cleanup(self):
        if self._rosbag_proc:
            self._rosbag_proc.terminate()
        if self._world:
            settings = self._world.get_settings()
            settings.synchronous_mode = False
            self._world.apply_settings(settings)


def main():
    parser = argparse.ArgumentParser(description="CarlaSad session replay")
    parser.add_argument("--session", required=True, help="Path to session directory")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier")
    parser.add_argument("--no-rosbag", action="store_true", help="Skip rosbag2 replay")
    args = parser.parse_args()

    replayer = SessionReplayer(Path(args.session), args.host, args.port)
    replayer.replay(speed=args.speed, replay_rosbag=not args.no_rosbag)


if __name__ == "__main__":
    main()
