"""Recording control endpoints."""
from typing import Literal, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

_recording_active = False
_recording_session_id: Optional[str] = None


class RecordingStartRequest(BaseModel):
    mode: Literal[
        "online_debug", "dataset_recording", "scenario_replay",
        "passive_tick", "mission_log"
    ] = "online_debug"


@router.post("/start")
def start_recording(req: RecordingStartRequest):
    global _recording_active, _recording_session_id
    import uuid, datetime
    _recording_session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    _recording_active = True
    # TODO: start rosbag2 recording via subprocess
    return {"ok": True, "session_id": _recording_session_id, "mode": req.mode}


@router.post("/stop")
def stop_recording():
    global _recording_active
    session = _recording_session_id
    _recording_active = False
    # TODO: stop rosbag2, write manifest
    return {"ok": True, "session_id": session}


@router.get("/status")
def recording_status():
    return {"active": _recording_active, "session_id": _recording_session_id}
