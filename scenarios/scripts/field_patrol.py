"""
Field Patrol scenario.

Scenario:
  - Tractor performs boustrophedon (serpentine) coverage of the field
  - 1–3 pedestrians walk random paths within the field
  - Optional: 1 other farm vehicle (static or slow-moving)
  - Process layer updated as tractor moves
  - Logging: online_debug mode

Usage:
    python field_patrol.py --seed 42 --duration 300 --field-width 100 --field-height 100
"""
import sys
import math
import random
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "carla-fork" / "PythonAPI"))
from base_scenario import BaseScenario
from carlasad.layers import ProcessLayer

logger = logging.getLogger("carlasad.scenario.field_patrol")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class FieldPatrolScenario(BaseScenario):
    def __init__(self, args):
        super().__init__(args)
        self._field_width  = args.field_width
        self._field_height = args.field_height
        self._num_pedestrians = args.pedestrians
        self._process = ProcessLayer(resolution=0.5, width=self._field_width, height=self._field_height)
        self._tractor = None
        self._patrol_waypoints: list = []
        self._current_wp_idx = 0

    def setup(self, world):
        # Build boustrophedon patrol route
        self._patrol_waypoints = self._build_boustrophedon_route(
            x_start=-self._field_width / 2 + 5,
            x_end=self._field_width / 2 - 5,
            y_start=-self._field_height / 2 + 5,
            y_end=self._field_height / 2 - 5,
            row_spacing=5.0,
        )

        # Find or spawn tractor
        self._tractor = self.get_tractor()
        if self._tractor is None:
            self._tractor = self.spawn_vehicle(
                "vehicle.carlasad.tractor",
                x=self._patrol_waypoints[0][0],
                y=self._patrol_waypoints[0][1],
                z=0.5,
                role="tractor",
            )
            logger.info("Tractor spawned at (%.1f, %.1f)", *self._patrol_waypoints[0])

        # Spawn pedestrians at random field positions
        for i in range(self._num_pedestrians):
            px = self.rng.uniform(-self._field_width / 2 + 10, self._field_width / 2 - 10)
            py = self.rng.uniform(-self._field_height / 2 + 10, self._field_height / 2 - 10)
            walker = self.spawn_walker(px, py)
            if walker:
                ctrl = world.get_blueprint_library().find("controller.ai.walker")
                if ctrl:
                    controller = world.try_spawn_actor(ctrl, walker.get_transform(), attach_to=walker)
                    if controller:
                        self._actors.append(controller)
                        controller.start()
                        controller.go_to_location(world.get_random_location_from_navigation())
                        controller.set_max_speed(1.0 + self.rng.random())
                logger.info("Pedestrian %d spawned at (%.1f, %.1f)", i, px, py)

        # Set field boundary in process layer
        half_w = self._field_width / 2 - 2
        half_h = self._field_height / 2 - 2
        self._process.set_field_boundary([
            (-half_w, -half_h), (half_w, -half_h),
            (half_w,  half_h), (-half_w,  half_h),
        ])

    def step(self, world, frame: int):
        if self._tractor is None:
            return

        # Move tractor toward next waypoint
        if self._current_wp_idx < len(self._patrol_waypoints):
            wp = self._patrol_waypoints[self._current_wp_idx]
            t = self._tractor.get_transform()
            dx = wp[0] - t.location.x
            dy = wp[1] - t.location.y
            dist = math.hypot(dx, dy)

            if dist < 2.0:
                self._current_wp_idx += 1
            else:
                import carla
                # Compute control
                target_yaw = math.degrees(math.atan2(dy, dx))
                yaw_error  = target_yaw - t.rotation.yaw
                while yaw_error > 180:  yaw_error -= 360
                while yaw_error < -180: yaw_error += 360

                ctrl = carla.VehicleControl()
                ctrl.throttle = 0.4 if dist > 5 else 0.2
                ctrl.steer    = max(-1.0, min(1.0, yaw_error / 45.0))
                ctrl.brake    = 0.0
                self._tractor.apply_control(ctrl)

        # Update process layer
        tpos = self._tractor.get_transform().location
        self._process.mark_worked(tpos.x, tpos.y, radius=2.5)

        if frame % 100 == 0:
            pct = self._process.get_worked_fraction() * 100
            logger.info("Frame %d | WP %d/%d | Worked: %.1f%%",
                        frame, self._current_wp_idx, len(self._patrol_waypoints), pct)

    def _build_boustrophedon_route(
        self, x_start: float, x_end: float,
        y_start: float, y_end: float,
        row_spacing: float = 5.0,
    ):
        waypoints = []
        y = y_start
        left_to_right = True
        while y <= y_end:
            if left_to_right:
                waypoints.append((x_start, y))
                waypoints.append((x_end,   y))
            else:
                waypoints.append((x_end,   y))
                waypoints.append((x_start, y))
            y += row_spacing
            left_to_right = not left_to_right
        return waypoints


def main():
    parser = BaseScenario.arg_parser("CarlaSad field patrol scenario")
    parser.add_argument("--field-width",  type=float, default=100.0)
    parser.add_argument("--field-height", type=float, default=100.0)
    parser.add_argument("--pedestrians",  type=int,   default=2)
    args = parser.parse_args()

    scenario = FieldPatrolScenario(args)
    scenario.run()


if __name__ == "__main__":
    main()
