"""
Dataset Recording scenario.

Deterministic coverage run for collecting synthetic training data:
  - Synchronous mode (fixed timestep)
  - Full sensor rig + full ground truth
  - rosbag2 recording
  - Session manifest with all metadata
  - Seed-based reproducibility

Usage:
    python dataset_recording_run.py --seed 1337 --duration 600 --output /datasets/run_001
"""
import sys
import math
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "carla-fork" / "PythonAPI"))
from base_scenario import BaseScenario
from carlasad.logging import SessionRecorder, RecorderConfig
from carlasad.layers import ProcessLayer

logger = logging.getLogger("carlasad.scenario.dataset_recording")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class DatasetRecordingScenario(BaseScenario):
    def __init__(self, args):
        super().__init__(args)
        self._output_path = Path(args.output)
        self._recorder: SessionRecorder = None
        self._process = ProcessLayer()
        self._tractor = None
        self._waypoints: list = []
        self._wp_idx = 0

    def connect(self):
        world = super().connect()

        # Enable synchronous mode for deterministic recording
        import carla
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        logger.info("Synchronous mode enabled (50ms timestep)")
        return world

    def setup(self, world):
        # Build patrol route
        self._waypoints = self._build_route(x_range=80, y_range=80, row_spacing=4.0)

        # Find tractor
        self._tractor = self.get_tractor()
        if self._tractor is None:
            if self._waypoints:
                self._tractor = self.spawn_vehicle(
                    "vehicle.carlasad.tractor",
                    x=self._waypoints[0][0], y=self._waypoints[0][1], z=0.5,
                    role="tractor",
                )

        # Spawn scripted pedestrians at deterministic positions
        ped_positions = [(30, 20), (-20, 40), (10, -30)]
        for i, (px, py) in enumerate(ped_positions[:3]):
            w = self.spawn_walker(
                px + self.rng.uniform(-2, 2),
                py + self.rng.uniform(-2, 2),
            )
            logger.info("Pedestrian %d at (%.1f, %.1f)", i, px, py)

        # Start recorder
        config = RecorderConfig(
            mode="dataset_recording",
            session_path=self._output_path,
            map_name=world.get_map().name,
            world_mode="editor",
            weather_preset="ClearNoon",
            sensor_rig="default",
            seed=self.seed,
            sync_mode=True,
            fixed_delta=0.05,
        )
        self._recorder = SessionRecorder(config)
        self._recorder.start()
        logger.info("Recording started → %s", self._output_path)

    def step(self, world, frame: int):
        # Drive tractor
        if self._tractor and self._wp_idx < len(self._waypoints):
            wp = self._waypoints[self._wp_idx]
            t  = self._tractor.get_transform()
            dx = wp[0] - t.location.x
            dy = wp[1] - t.location.y
            dist = math.hypot(dx, dy)
            if dist < 2.0:
                self._wp_idx += 1
            else:
                import carla
                target_yaw = math.degrees(math.atan2(dy, dx))
                yaw_err = target_yaw - t.rotation.yaw
                while yaw_err > 180:  yaw_err -= 360
                while yaw_err < -180: yaw_err += 360
                ctrl = carla.VehicleControl(
                    throttle=0.35, steer=max(-1.0, min(1.0, yaw_err / 45.0)), brake=0.0
                )
                self._tractor.apply_control(ctrl)

        # Update process layer
        if self._tractor:
            pos = self._tractor.get_transform().location
            self._process.mark_worked(pos.x, pos.y)

        # Record ground truth every frame
        if self._recorder and self._recorder.is_active:
            gt = self._build_gt(world, frame)
            self._recorder.record_frame(frame, gt)

            # Record process state every 20 frames
            if frame % 20 == 0:
                ps = {
                    "worked_fraction": self._process.get_worked_fraction(),
                    "worked_edge_count": len(self._process._worked_edge),
                }
                self._recorder.record_process_state(ps)

        if frame % 200 == 0:
            logger.info("Frame %d | WP %d/%d | Worked: %.1f%%",
                        frame, self._wp_idx, len(self._waypoints),
                        self._process.get_worked_fraction() * 100)

    def teardown(self, world):
        if self._recorder:
            self._recorder.stop()

        # Disable sync mode
        import carla
        settings = world.get_settings()
        settings.synchronous_mode = False
        world.apply_settings(settings)

        super().teardown(world)
        logger.info("Dataset saved to: %s", self._output_path)

    def _build_gt(self, world, frame: int) -> dict:
        gt = {"frame": frame}
        if self._tractor:
            t = self._tractor.get_transform()
            v = self._tractor.get_velocity()
            gt["ego_pose"] = {
                "x": round(t.location.x, 3), "y": round(t.location.y, 3),
                "z": round(t.location.z, 3), "yaw": round(t.rotation.yaw, 2),
                "vx": round(v.x, 3), "vy": round(v.y, 3),
            }
        objects = []
        for actor in world.get_actors():
            if "walker" in actor.type_id or ("vehicle" in actor.type_id and actor.id != self._tractor.id):
                t = actor.get_transform()
                objects.append({
                    "id": actor.id, "type": actor.type_id,
                    "x": round(t.location.x, 3), "y": round(t.location.y, 3),
                    "yaw": round(t.rotation.yaw, 2),
                })
        gt["objects"] = objects
        return gt

    def _build_route(self, x_range: float, y_range: float, row_spacing: float):
        wps = []
        y = -y_range / 2
        ltr = True
        while y <= y_range / 2:
            xs = -x_range / 2 if ltr else x_range / 2
            xe =  x_range / 2 if ltr else -x_range / 2
            wps.append((xs, y))
            wps.append((xe, y))
            y += row_spacing
            ltr = not ltr
        return wps


def main():
    parser = BaseScenario.arg_parser("CarlaSad dataset recording scenario")
    parser.add_argument("--output", default="/datasets/recording_default")
    args = parser.parse_args()

    scenario = DatasetRecordingScenario(args)
    scenario.run()


if __name__ == "__main__":
    main()
