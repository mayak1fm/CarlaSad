"""Simulation control: play/pause/tick/sync."""
from fastapi import APIRouter
from sim_controller import sim_controller
from carla_client import carla_client

router = APIRouter()


@router.post("/play")
async def play():
    await sim_controller.resume_sim()
    return {"ok": True, "state": "playing"}


@router.post("/pause")
async def pause():
    await sim_controller.pause_sim()
    return {"ok": True, "state": "paused"}


@router.post("/tick")
async def tick():
    """Advance simulation by one step (only in synchronous mode)."""
    if not carla_client.is_connected():
        return {"ok": False, "error": "CARLA not connected"}
    frame = carla_client.tick()
    return {"ok": True, "frame": frame}


@router.post("/sync")
async def set_sync(enabled: bool, fixed_delta_seconds: float = 0.05):
    await carla_client.ensure_connected()
    carla_client.set_sync_mode(enabled, fixed_delta_seconds)
    return {"ok": True, "synchronous_mode": enabled, "fixed_delta_seconds": fixed_delta_seconds}
