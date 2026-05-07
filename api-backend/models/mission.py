"""Mission data models."""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
import uuid


class MissionRequest(BaseModel):
    map_name: str = "CarlaSad/Field_Main"
    world_mode: Literal["editor", "reconstructed"] = "editor"
    route_id: Optional[str] = None
    work_zone_id: Optional[str] = None
    logging_mode: Literal[
        "online_debug", "dataset_recording", "scenario_replay",
        "passive_tick", "mission_log"
    ] = "online_debug"
    weather_preset: str = "ClearNoon"
    sensor_rig_profile: str = "default"
    seed: int = 42


class MissionEvent(BaseModel):
    timestamp: float
    event_type: str
    payload: dict = Field(default_factory=dict)


class MissionStatus(BaseModel):
    state: Literal["idle", "running", "paused", "completed", "error"] = "idle"
    mission_id: Optional[str] = None
    progress: float = 0.0
    elapsed_seconds: float = 0.0
    current_pose: Optional[dict] = None
    events: List[MissionEvent] = Field(default_factory=list)


class RouteDefinition(BaseModel):
    route_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    waypoints: List[dict]
    work_zone_polygon: Optional[List[dict]] = None
    map_name: str


_active_mission: Optional[MissionStatus] = None


def get_active_mission() -> MissionStatus:
    global _active_mission
    if _active_mission is None:
        _active_mission = MissionStatus()
    return _active_mission


def set_active_mission(status: MissionStatus):
    global _active_mission
    _active_mission = status
