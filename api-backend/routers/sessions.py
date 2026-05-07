"""Session browser and replay endpoints."""
import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

LOGS_DIR = Path(os.environ.get("LOG_DIR", "/logs"))


@router.get("")
def list_sessions():
    if not LOGS_DIR.exists():
        return []
    sessions = []
    for d in sorted(LOGS_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                sessions.append({
                    "session_id": d.name,
                    "path": str(d),
                    **manifest,
                })
            except Exception:
                sessions.append({"session_id": d.name, "path": str(d)})
    return sessions[:50]


class ReplayRequest(BaseModel):
    session_id: str


@router.post("/replay/start")
def start_replay(req: ReplayRequest):
    session_path = LOGS_DIR / req.session_id
    if not session_path.exists():
        raise HTTPException(status_code=404, detail=f"Session {req.session_id} not found")
    # TODO: trigger replay via CARLA Python API + rosbag2 play
    return {"ok": True, "session_id": req.session_id, "path": str(session_path)}
