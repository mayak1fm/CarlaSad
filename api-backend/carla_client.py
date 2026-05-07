"""
CARLA connection manager for CarlaSad API backend.
Singleton that maintains connection across request lifecycle.
"""
import os
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("carlasad.carla_client")

CARLA_HOST = os.environ.get("CARLA_HOST", "localhost")
CARLA_PORT = int(os.environ.get("CARLA_PORT", "2000"))
CARLA_TIMEOUT = float(os.environ.get("CARLA_TIMEOUT", "10.0"))


class CarlaClient:
    """Thread-safe singleton CARLA client wrapper."""

    def __init__(self):
        self._client = None
        self._world = None
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        async with self._lock:
            if self._connected:
                return True
            try:
                import carla
                self._client = carla.Client(CARLA_HOST, CARLA_PORT)
                self._client.set_timeout(CARLA_TIMEOUT)
                self._world = self._client.get_world()
                self._connected = True
                logger.info("Connected to CARLA at %s:%d", CARLA_HOST, CARLA_PORT)
                return True
            except Exception as e:
                logger.warning("CARLA not available: %s", e)
                self._connected = False
                return False

    def is_connected(self) -> bool:
        return self._connected

    def get_world(self):
        return self._world

    def get_client(self):
        return self._client

    async def ensure_connected(self):
        if not self._connected:
            await self.connect()
        return self._connected

    def load_world(self, map_name: str):
        if not self._client:
            raise RuntimeError("Not connected to CARLA")
        self._world = self._client.load_world(map_name)
        return self._world

    def set_weather(self, preset_name: str):
        if not self._world:
            return
        import carla
        presets = {
            "ClearNoon": carla.WeatherParameters.ClearNoon,
            "CloudyNoon": carla.WeatherParameters.CloudyNoon,
            "WetNoon": carla.WeatherParameters.WetNoon,
            "WetCloudyNoon": carla.WeatherParameters.WetCloudyNoon,
            "SoftRainNoon": carla.WeatherParameters.SoftRainNoon,
            "MidRainyNoon": carla.WeatherParameters.MidRainyNoon,
            "HardRainNoon": carla.WeatherParameters.HardRainNoon,
            "ClearSunset": carla.WeatherParameters.ClearSunset,
            "CloudySunset": carla.WeatherParameters.CloudySunset,
            "WetSunset": carla.WeatherParameters.WetSunset,
            "WetCloudySunset": carla.WeatherParameters.WetCloudySunset,
            "SoftRainSunset": carla.WeatherParameters.SoftRainSunset,
            "MidRainSunset": carla.WeatherParameters.MidRainSunset,
            "HardRainSunset": carla.WeatherParameters.HardRainSunset,
        }
        weather = presets.get(preset_name)
        if weather:
            self._world.set_weather(weather)

    def set_sync_mode(self, enabled: bool, delta: float = 0.05):
        if not self._world:
            return
        import carla
        settings = self._world.get_settings()
        settings.synchronous_mode = enabled
        settings.fixed_delta_seconds = delta if enabled else None
        self._world.apply_settings(settings)

    def tick(self) -> int:
        if not self._world:
            return -1
        return self._world.tick()

    def get_status(self) -> dict:
        if not self._connected or not self._world:
            return {"connected": False, "host": CARLA_HOST, "port": CARLA_PORT}
        try:
            settings = self._world.get_settings()
            weather = self._world.get_weather()
            return {
                "connected": True,
                "host": CARLA_HOST,
                "port": CARLA_PORT,
                "map": self._world.get_map().name,
                "synchronous_mode": settings.synchronous_mode,
                "fixed_delta_seconds": settings.fixed_delta_seconds,
                "weather": {
                    "cloudiness": weather.cloudiness,
                    "precipitation": weather.precipitation,
                    "sun_altitude": weather.sun_altitude_angle,
                },
            }
        except Exception as e:
            self._connected = False
            return {"connected": False, "error": str(e)}

    def spawn_tractor(self, x: float = 0, y: float = 0, z: float = 0.5, yaw: float = 0):
        if not self._world:
            return None
        import carla
        bpl = self._world.get_blueprint_library()
        bp = bpl.find("vehicle.carlasad.tractor")
        if bp is None:
            vehicles = list(bpl.filter("vehicle.tesla.model3"))
            if not vehicles:
                return None
            bp = vehicles[0]
        t = carla.Transform(
            carla.Location(x=x, y=y, z=z),
            carla.Rotation(yaw=yaw),
        )
        return self._world.try_spawn_actor(bp, t)

    def get_actor_by_role(self, role: str):
        if not self._world:
            return None
        actors = self._world.get_actors()
        for a in actors:
            if a.attributes.get("role_name") == role:
                return a
        return None


# Global singleton
carla_client = CarlaClient()
