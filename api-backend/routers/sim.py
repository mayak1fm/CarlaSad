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
    """Advance simulation by one step (synchronous or passive tick mode)."""
    if not carla_client.is_connected():
        return {"ok": False, "error": "CARLA not connected"}
    result = await sim_controller.tick_once()
    return {"ok": True, **result}


@router.post("/sync")
async def set_sync(enabled: bool, fixed_delta_seconds: float = 0.05):
    await carla_client.ensure_connected()
    carla_client.set_sync_mode(enabled, fixed_delta_seconds)
    return {"ok": True, "synchronous_mode": enabled, "fixed_delta_seconds": fixed_delta_seconds}


@router.post("/passive-tick/enter")
async def enter_passive_tick(fixed_delta_seconds: float = 0.05):
    """
    Switch to passive tick mode for external orchestrator control.
    After calling this, POST /tick to advance each simulation step.
    """
    await sim_controller.enter_passive_tick_mode(fixed_delta_seconds)
    return {"ok": True, "mode": "passive_tick", "fixed_delta_seconds": fixed_delta_seconds}


@router.post("/passive-tick/exit")
async def exit_passive_tick():
    """Return to free-running (async) simulation."""
    await sim_controller.exit_passive_tick_mode()
    return {"ok": True, "mode": "free_running"}


@router.get("/passive-tick/status")
async def passive_tick_status():
    return {
        "passive_tick_active": sim_controller.is_passive_tick_mode,
        "carla_connected": carla_client.is_connected(),
    }
