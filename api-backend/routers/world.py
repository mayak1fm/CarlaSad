"""World control endpoints."""
from fastapi import APIRouter, HTTPException
from models.world import WorldLoadRequest, WeatherRequest, WorldInfo, WEATHER_PRESETS, TERRAIN_CLASSES
from carla_client import carla_client

router = APIRouter()

_world_info = WorldInfo(
    map="CarlaSad/Field_Main",
    mode="editor",
    weather_preset="ClearNoon",
    synchronous_mode=False,
)


@router.post("/load")
async def load_world(req: WorldLoadRequest):
    global _world_info
    await carla_client.ensure_connected()
    if carla_client.is_connected():
        try:
            carla_client.load_world(req.map)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    _world_info.map = req.map
    _world_info.mode = req.mode
    return {"ok": True, "map": req.map, "mode": req.mode}


@router.post("/weather")
async def set_weather(req: WeatherRequest):
    global _world_info
    if req.preset not in WEATHER_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown preset '{req.preset}'. Valid: {WEATHER_PRESETS}"
        )
    await carla_client.ensure_connected()
    if carla_client.is_connected():
        carla_client.set_weather(req.preset)
    _world_info.weather_preset = req.preset
    return {"ok": True, "preset": req.preset}


@router.get("/info", response_model=WorldInfo)
async def get_world_info():
    if carla_client.is_connected():
        status = carla_client.get_status()
        if status.get("connected"):
            _world_info.map = status.get("map", _world_info.map)
            _world_info.synchronous_mode = status.get("synchronous_mode", False)
    return _world_info


@router.get("/terrain_classes")
def get_terrain_classes():
    return TERRAIN_CLASSES


@router.get("/weather_presets")
def get_weather_presets():
    return WEATHER_PRESETS


@router.get("/maps")
async def list_maps():
    await carla_client.ensure_connected()
    if not carla_client.is_connected():
        return {"maps": [], "error": "CARLA not connected"}
    client = carla_client.get_client()
    maps = sorted(client.get_available_maps())
    return {"maps": maps}
