"""
Ground truth exporter for CarlaSad.

Exports all GT data for dataset recording and ROS2 publishing.
"""
import time
from typing import Optional, Any
from .layers.terrain_layer import TerrainLayer
from .layers.process_layer import ProcessLayer


class GroundTruthExporter:
    """Exports ground truth from CARLA world state."""

    def __init__(self, terrain: TerrainLayer, process: ProcessLayer, world_metadata: dict):
        self._terrain = terrain
        self._process = process
        self._world_meta = world_metadata

    def export_frame(self, carla_world, ego_actor, frame_id: int, timestamp: float) -> dict:
        """Export full ground truth for a single simulation frame."""
        gt = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "world": self._world_meta,
            "ego_pose": self._export_ego_pose(ego_actor),
            "objects": self._export_objects(carla_world),
            "process": {
                "worked_map": self._process.to_worked_occupancy_grid(),
                "worked_edge": self._process.to_worked_edge_msg(),
                "field_boundary": self._process.to_field_boundary_msg(),
                "worked_fraction": self._process.get_worked_fraction(),
            },
        }
        return gt

    def _export_ego_pose(self, ego_actor) -> dict:
        if ego_actor is None:
            return {}
        t = ego_actor.get_transform()
        v = ego_actor.get_velocity()
        return {
            "x": t.location.x,
            "y": t.location.y,
            "z": t.location.z,
            "roll": t.rotation.roll,
            "pitch": t.rotation.pitch,
            "yaw": t.rotation.yaw,
            "vx": v.x,
            "vy": v.y,
            "vz": v.z,
        }

    def _export_objects(self, carla_world) -> list:
        actors = carla_world.get_actors()
        objects = []
        for actor in actors:
            if "vehicle" in actor.type_id or "walker" in actor.type_id:
                t = actor.get_transform()
                v = actor.get_velocity()
                objects.append({
                    "id": actor.id,
                    "type_id": actor.type_id,
                    "x": t.location.x,
                    "y": t.location.y,
                    "z": t.location.z,
                    "yaw": t.rotation.yaw,
                    "vx": v.x,
                    "vy": v.y,
                    "terrain_label": self._terrain.get_label(t.location.x, t.location.y),
                    "terrain_risk": self._terrain.get_risk(t.location.x, t.location.y),
                })
        return objects
