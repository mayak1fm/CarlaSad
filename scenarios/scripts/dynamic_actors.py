"""
Dynamic actors scenario — pedestrians and farm machinery move on
pre-recorded / procedurally-generated pose clips from the PoseBank.

Replaces the CARLA AI walker controller with deterministic, seed-based
motion so the scenario is fully reproducible.

Usage:
    python dynamic_actors.py --seed 42 --duration 300
"""
import time
import logging
from pathlib import Path

from base_scenario import BaseScenario

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent /
                       "carla-fork" / "PythonAPI"))
from carlasad.actors.pose_bank import PoseBank
from carlasad.physics.terrain_physics import TerrainPhysicsModifier
from carlasad.layers import TerrainLayer

logger = logging.getLogger("carlasad.scenario.dynamic_actors")


class DynamicActorsScenario(BaseScenario):

    def __init__(self, config: dict):
        super().__init__(config)
        self._dynamic_actors = []   # list of (actor, PoseInterpolator, TerrainPhysicsModifier)
        self._terrain_layer: TerrainLayer | None = None
        self._start_time: float = 0.0

    def setup(self):
        self._connect(sync=True)

        # Load terrain layer if config provides one
        terrain_config = self.config.get("terrain_config")
        if terrain_config:
            self._terrain_layer = TerrainLayer.from_config(terrain_config)

        # Spawn tractor
        tractor_cfg = self.config.get("tractor_spawn",
                                       {"x": 0.0, "y": 0.0, "z": 0.5, "yaw": 0.0})
        self._tractor = self._spawn_tractor(**tractor_cfg)

        # Attach terrain physics modifier to tractor
        if self._tractor:
            self._tractor_physics = TerrainPhysicsModifier(self._tractor)
        else:
            self._tractor_physics = None

        # Spawn dynamic pedestrians
        for i, spec in enumerate(self.config.get("pedestrians", [])):
            self._spawn_dynamic_actor("person", spec, seed=self._seed + i)

        # Spawn dynamic machinery (stationary or slow-moving)
        for i, spec in enumerate(self.config.get("machinery", [])):
            self._spawn_dynamic_actor("machinery", spec, seed=self._seed + 100 + i)

        logger.info("[dynamic_actors] Setup complete: %d dynamic actors", len(self._dynamic_actors))

    def _spawn_dynamic_actor(self, class_name: str, spec: dict, seed: int):
        actor = self._spawn_walker(
            x=spec.get("x", 0.0),
            y=spec.get("y", 0.0),
            z=spec.get("z", 0.5),
        )
        if actor is None:
            logger.warning("[dynamic_actors] Failed to spawn %s at %s", class_name, spec)
            return

        bank = PoseBank(class_name, rng=self._rng)
        interp = bank.make_interpolator(
            origin_x   = spec.get("x", 0.0),
            origin_y   = spec.get("y", 0.0),
            origin_z   = spec.get("z", 0.5),
            origin_yaw = spec.get("yaw", 0.0),
            seed       = seed,
        )
        phys = TerrainPhysicsModifier(actor) if class_name == "machinery" else None
        self._dynamic_actors.append((actor, interp, phys))
        logger.info("[dynamic_actors] Spawned %s (seed=%d) at (%.1f, %.1f)",
                    class_name, seed, spec.get("x", 0), spec.get("y", 0))

    def run(self):
        self._start_time = time.time()
        duration = float(self.config.get("duration_seconds", 120.0))
        frame = 0

        try:
            while True:
                elapsed_ms = (time.time() - self._start_time) * 1000.0
                if elapsed_ms > duration * 1000.0:
                    break

                self._tick_all_actors(elapsed_ms)
                self._tick_tractor_physics()

                self._world.tick()
                frame += 1

                if frame % 100 == 0:
                    logger.info("[dynamic_actors] frame=%d elapsed=%.1f s", frame, elapsed_ms / 1000.0)

        except KeyboardInterrupt:
            logger.info("[dynamic_actors] Interrupted by user")
        finally:
            self.teardown()

    def _tick_all_actors(self, elapsed_ms: float):
        """Move all dynamic actors to their pose-bank positions."""
        try:
            import carla
        except ImportError:
            return

        for actor, interp, phys in self._dynamic_actors:
            wx, wy, wz, wyaw = interp.get_transform(elapsed_ms)
            t = carla.Transform(
                carla.Location(x=wx, y=wy, z=wz),
                carla.Rotation(yaw=wyaw),
            )
            try:
                actor.set_transform(t)
            except Exception:
                pass

    def _tick_tractor_physics(self):
        """Update terrain physics for tractor based on its current position."""
        if self._tractor is None or self._terrain_layer is None or self._tractor_physics is None:
            return
        try:
            loc = self._tractor.get_transform().location
            label = self._terrain_layer.get_label(loc.x, loc.y)
            self._tractor_physics.apply(label)
        except Exception as exc:
            logger.debug("[dynamic_actors] terrain physics tick: %s", exc)

    def teardown(self):
        if self._tractor_physics:
            self._tractor_physics.reset()
        for actor, _, _ in self._dynamic_actors:
            try:
                actor.destroy()
            except Exception:
                pass
        self._dynamic_actors.clear()
        logger.info("[dynamic_actors] Teardown complete")


def main():
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description="CarlaSad dynamic actors scenario")
    parser.add_argument("--config",   default=None,  help="YAML scenario config path")
    parser.add_argument("--seed",     type=int, default=42)
    parser.add_argument("--duration", type=float, default=120.0, help="Duration in seconds")
    parser.add_argument("--host",     default="localhost")
    parser.add_argument("--port",     type=int, default=2000)
    args = parser.parse_args()

    config = {}
    if args.config:
        config = yaml.safe_load(Path(args.config).read_text())

    config.setdefault("seed",             args.seed)
    config.setdefault("duration_seconds", args.duration)
    config.setdefault("carla_host",       args.host)
    config.setdefault("carla_port",       args.port)
    config.setdefault("pedestrians", [
        {"x":  5.0, "y":  3.0, "z": 0.5, "yaw":  45.0},
        {"x": -3.0, "y":  8.0, "z": 0.5, "yaw": 180.0},
        {"x": 10.0, "y": -2.0, "z": 0.5, "yaw":  90.0},
    ])
    config.setdefault("machinery", [
        {"x": 15.0, "y": 10.0, "z": 0.5, "yaw": 0.0},
    ])

    scenario = DynamicActorsScenario(config)
    scenario.setup()
    scenario.run()


if __name__ == "__main__":
    main()
