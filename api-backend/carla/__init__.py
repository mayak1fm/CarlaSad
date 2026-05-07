"""
Carla Python API stub for api-backend container.

The real carla egg is mounted at /carla-python-api at runtime and added to
PYTHONPATH via the container entrypoint. When it's present, Python imports
the real package (it appears earlier in sys.path).

This stub is a fallback so the API server starts and returns meaningful errors
instead of crashing when CARLA isn't available.
"""
import sys as _sys
import os as _os

# If the real carla egg is on PYTHONPATH, use it
_egg_dir = _os.environ.get("CARLA_EGG_DIR", "/carla-python-api")
for _entry in _os.listdir(_egg_dir) if _os.path.isdir(_egg_dir) else []:
    if _entry.endswith(".egg"):
        _egg_path = _os.path.join(_egg_dir, _entry)
        if _egg_path not in _sys.path:
            _sys.path.insert(0, _egg_path)
        try:
            import importlib
            importlib.invalidate_caches()
            from carla import *   # noqa: F401, F403 — re-export real carla
            break
        except ImportError:
            pass


# ── Stub classes used by carla_client.py ─────────────────────────────────────

class _StubAttrib:
    def __getattr__(self, name):
        return _StubAttrib()
    def __call__(self, *a, **kw):
        return _StubAttrib()
    def __float__(self):
        return 0.0
    def __int__(self):
        return 0
    def __bool__(self):
        return False
    def __iter__(self):
        return iter([])


try:
    Client  # noqa: F821 — check if real carla was loaded above
except NameError:
    # Real carla not available — define minimal stubs

    class Client:
        def __init__(self, host, port, worker_threads=0):
            self._connected = False

        def set_timeout(self, t): pass

        def get_server_version(self):
            raise RuntimeError("CARLA not available (stub)")

        def get_world(self):
            raise RuntimeError("CARLA not available (stub)")

        def load_world(self, map_name):
            raise RuntimeError("CARLA not available (stub)")

        def get_available_maps(self):
            return []

    class WeatherParameters:
        ClearNoon       = _StubAttrib()
        CloudyNoon      = _StubAttrib()
        WetNoon         = _StubAttrib()
        WetCloudyNoon   = _StubAttrib()
        SoftRainNoon    = _StubAttrib()
        MidRainyNoon    = _StubAttrib()
        HardRainNoon    = _StubAttrib()
        ClearSunset     = _StubAttrib()
        CloudySunset    = _StubAttrib()
        WetSunset       = _StubAttrib()
        WetCloudySunset = _StubAttrib()
        SoftRainSunset  = _StubAttrib()
        MidRainSunset   = _StubAttrib()
        HardRainSunset  = _StubAttrib()

    class Location:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x = x; self.y = y; self.z = z

    class Rotation:
        def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
            self.pitch = pitch; self.yaw = yaw; self.roll = roll

    class Transform:
        def __init__(self, location=None, rotation=None):
            self.location = location or Location()
            self.rotation = rotation or Rotation()

    class Vector3D:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x = x; self.y = y; self.z = z

    class ActorList:
        def __iter__(self): return iter([])
        def filter(self, pattern): return []
