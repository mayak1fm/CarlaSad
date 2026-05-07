"""World control endpoints."""
from fastapi import APIRouter, HTTPException
from models.world import WorldLoadRequest, WeatherRequest, WorldInfo, WEATHER_PRESETS, TERRAIN_CLASSES

router = APIRouter()

_world_info = WorldInfo(
    map="CarlaSad/Field_Main",
    mode="editor",
    weather_preset="ClearNoon",
    synchronous_mode=False,
)


@router.post("/load")
def load_world(req: WorldLoadRequest):
    global _world_info
    # TODO: call CARLA Python API to load map
    _world_info.map = req.map
    _world_info.mode = req.mode
    return {"ok": True, "map": req.map, "mode": req.mode}


@router.post("/weather")
def set_weather(req: WeatherRequest):
    global _world_info
    if req.preset not in WEATHER_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown preset. Valid: {WEATHER_PRESETS}")
    _world_info.weather_preset = req.preset
    # TODO: apply to CARLA
    return {"ok": True, "preset": req.preset}


@router.get("/info", response_model=WorldInfo)
def get_world_info():
    return _world_info


@router.get("/terrain_classes")
def get_terrain_classes():
    return TERRAIN_CLASSES


@router.get("/weather_presets")
def get_weather_presets():
    return WEATHER_PRESETS
