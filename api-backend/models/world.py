"""World and simulation data models."""
from typing import Literal, Optional, List
from pydantic import BaseModel


WEATHER_PRESETS = [
    "ClearNoon", "CloudyNoon", "WetNoon", "WetCloudyNoon",
    "SoftRainNoon", "MidRainyNoon", "HardRainNoon",
    "ClearSunset", "CloudySunset", "WetSunset",
    "WetCloudySunset", "SoftRainSunset", "MidRainSunset", "HardRainSunset",
]


class WorldLoadRequest(BaseModel):
    map: str
    mode: Literal["editor", "reconstructed"] = "editor"


class WeatherRequest(BaseModel):
    preset: str


class WorldInfo(BaseModel):
    map: str
    mode: Literal["editor", "reconstructed"]
    weather_preset: str
    synchronous_mode: bool
    fixed_delta_seconds: Optional[float] = None


class TerrainClass(BaseModel):
    label_id: int
    name: str
    description: str
    drivable: bool
    risk_level: float  # 0.0 = safe, 1.0 = impassable


TERRAIN_CLASSES: List[TerrainClass] = [
    TerrainClass(label_id=100, name="normal_field", description="Dry field", drivable=True, risk_level=0.0),
    TerrainClass(label_id=101, name="wet_field", description="Wet field after rain", drivable=True, risk_level=0.2),
    TerrainClass(label_id=102, name="swamp", description="Swampy area", drivable=False, risk_level=0.9),
    TerrainClass(label_id=103, name="mochak", description="Soft boggy ground", drivable=False, risk_level=0.8),
    TerrainClass(label_id=104, name="rough_terrain", description="Rough uneven terrain", drivable=True, risk_level=0.4),
    TerrainClass(label_id=105, name="field_boundary", description="Field edge boundary", drivable=False, risk_level=1.0),
    TerrainClass(label_id=106, name="drivable_path", description="Field road/path", drivable=True, risk_level=0.0),
    TerrainClass(label_id=107, name="non_drivable", description="Non-drivable zone", drivable=False, risk_level=1.0),
    TerrainClass(label_id=110, name="worked_area", description="Already processed", drivable=True, risk_level=0.0),
    TerrainClass(label_id=111, name="unworked_area", description="Not yet processed", drivable=True, risk_level=0.1),
    TerrainClass(label_id=112, name="worked_edge", description="Active processing boundary", drivable=True, risk_level=0.0),
    TerrainClass(label_id=113, name="active_work_zone", description="Current work zone", drivable=True, risk_level=0.0),
    TerrainClass(label_id=114, name="restricted_zone", description="Restricted area", drivable=False, risk_level=1.0),
]
