"""
Base scenario class for CarlaSad.

All scenarios inherit from BaseScenario and implement:
  - setup(world)  — spawn actors, configure world
  - step(world, frame)  — per-tick logic (actor behavior)
  - teardown(world)  — cleanup

Usage:
    python my_scenario.py --host localhost --port 2000 --seed 42 --duration 300
"""
import argparse
import random
import time
import sys
import logging
from typing import Optional

logger = logging.getLogger("carlasad.scenario")


class BaseScenario:
    def __init__(self, args):
        self.host    = args.host
        self.port    = args.port
        self.seed    = args.seed
        self.duration = args.duration
        self.rng     = random.Random(args.seed)

        self._client = None
        self._world  = None
        self._actors: list = []

    def connect(self):
        import carla
        self._client = carla.Client(self.host, self.port)
        self._client.set_timeout(10.0)
        self._world = self._client.get_world()
        logger.info("[%s] Connected to CARLA at %s:%d", self.__class__.__name__, self.host, self.port)
        return self._world

    def run(self):
        self.connect()
        self.setup(self._world)
        logger.info("[%s] Scenario started (seed=%d, duration=%ds)", self.__class__.__name__, self.seed, self.duration)

        start = time.time()
        frame = 0
        try:
            while time.time() - start < self.duration:
                self.step(self._world, frame)
                self._world.tick()
                frame += 1
        except KeyboardInterrupt:
            logger.info("[%s] Interrupted", self.__class__.__name__)
        finally:
            self.teardown(self._world)
            logger.info("[%s] Done. Frames: %d, Elapsed: %.1fs", self.__class__.__name__, frame, time.time() - start)

    def setup(self, world):
        raise NotImplementedError

    def step(self, world, frame: int):
        pass

    def teardown(self, world):
        for a in self._actors:
            try:
                a.destroy()
            except Exception:
                pass
        self._actors.clear()
        logger.info("[%s] Actors destroyed", self.__class__.__name__)

    def spawn_vehicle(self, blueprint_id: str, x: float, y: float, z: float = 0.5, yaw: float = 0.0, role: str = "npc"):
        import carla
        bpl = self._world.get_blueprint_library()
        bp = bpl.find(blueprint_id)
        if bp is None:
            bp = list(bpl.filter("vehicle.tesla.model3"))[0]
        if bp.has_attribute("role_name"):
            bp.set_attribute("role_name", role)
        t = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))
        actor = self._world.try_spawn_actor(bp, t)
        if actor:
            self._actors.append(actor)
        return actor

    def spawn_walker(self, x: float, y: float, z: float = 0.0, yaw: float = 0.0):
        import carla
        bpl = self._world.get_blueprint_library()
        walkers = list(bpl.filter("walker.pedestrian.*"))
        if not walkers:
            return None
        bp = self.rng.choice(walkers)
        t = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))
        actor = self._world.try_spawn_actor(bp, t)
        if actor:
            self._actors.append(actor)
        return actor

    def get_tractor(self):
        actors = self._world.get_actors()
        for a in actors:
            if a.attributes.get("role_name") == "tractor":
                return a
        return None

    @staticmethod
    def arg_parser(description: str) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(description=description)
        p.add_argument("--host",     default="localhost")
        p.add_argument("--port",     type=int, default=2000)
        p.add_argument("--seed",     type=int, default=42)
        p.add_argument("--duration", type=int, default=300, help="Scenario duration seconds")
        return p
