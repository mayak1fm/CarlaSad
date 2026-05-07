"""Mission control endpoints."""
from fastapi import APIRouter, HTTPException
from models.mission import MissionRequest, MissionStatus, get_active_mission
from sim_controller import sim_controller

router = APIRouter()


@router.post("/start")
async def start_mission(req: MissionRequest):
    mission = get_active_mission()
    if mission.state == "running":
        raise HTTPException(status_code=409, detail="Mission already running")
    mission_id = await sim_controller.start_mission(req)
    return {"ok": True, "mission_id": mission_id}


@router.post("/stop")
async def stop_mission():
    mission = get_active_mission()
    if mission.state not in ("running", "paused"):
        raise HTTPException(status_code=409, detail="No active mission")
    await sim_controller.stop_mission()
    return {"ok": True}


@router.get("/status", response_model=MissionStatus)
def get_status():
    return get_active_mission()
