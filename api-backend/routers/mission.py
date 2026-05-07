"""Mission control endpoints."""
import time
import uuid
from fastapi import APIRouter
from models.mission import MissionRequest, MissionStatus, get_active_mission, set_active_mission

router = APIRouter()


@router.post("/start")
def start_mission(req: MissionRequest):
    mission_id = str(uuid.uuid4())
    status = MissionStatus(
        state="running",
        mission_id=mission_id,
        progress=0.0,
        elapsed_seconds=0.0,
    )
    set_active_mission(status)
    # TODO: send command to CARLA via carla_client
    return {"ok": True, "mission_id": mission_id}


@router.post("/stop")
def stop_mission():
    mission = get_active_mission()
    mission.state = "completed"
    set_active_mission(mission)
    return {"ok": True}


@router.get("/status", response_model=MissionStatus)
def get_status():
    return get_active_mission()
