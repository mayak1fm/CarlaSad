"""Recording control endpoints."""
import asyncio
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sim_controller import sim_controller
from models.mission import get_active_mission

router = APIRouter()

_recording_session_id: Optional[str] = None
_recording_mode: Optional[str] = None


class RecordingStartRequest(BaseModel):
    mode: Literal[
        "online_debug", "dataset_recording", "scenario_replay",
        "passive_tick", "mission_log"
    ] = "online_debug"


@router.post("/start")
async def start_recording(req: RecordingStartRequest):
    global _recording_session_id, _recording_mode
    mission = get_active_mission()
    if mission.state not in ("running", "idle"):
        raise HTTPException(status_code=409, detail="Start a mission first or use idle recording")

    import datetime, uuid
    _recording_session_id = (
        f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    _recording_mode = req.mode

    if req.mode == "dataset_recording":
        from carla_client import carla_client
        await carla_client.ensure_connected()
        carla_client.set_sync_mode(True, 0.05)

    return {"ok": True, "session_id": _recording_session_id, "mode": req.mode}


@router.post("/stop")
async def stop_recording():
    global _recording_session_id
    session = _recording_session_id
    if not session:
        raise HTTPException(status_code=409, detail="No active recording")

    if _recording_mode == "dataset_recording":
        from carla_client import carla_client
        carla_client.set_sync_mode(False)

    _recording_session_id = None
    return {"ok": True, "session_id": session}


@router.get("/status")
def recording_status():
    return {
        "active": _recording_session_id is not None,
        "session_id": _recording_session_id,
        "mode": _recording_mode,
    }
