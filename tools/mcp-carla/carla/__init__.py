"""
Carla stub for Python 3.10+ — proxies to carla_proxy_server.py via HTTP.

Environment:
  CARLA_PROXY_PORT  port where carla_proxy_server.py listens (default 19876)
"""
import os
import json
import urllib.request
import urllib.error

_PORT = int(os.environ.get("CARLA_PROXY_PORT", "19876"))
_BASE = f"http://127.0.0.1:{_PORT}"
_next_id = [1]


def _call(method, *args, **kwargs):
    rid = _next_id[0]
    _next_id[0] += 1
    payload = json.dumps({"id": rid, "call": method, "args": list(args), "kwargs": kwargs}).encode()
    req = urllib.request.Request(
        f"{_BASE}/rpc",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"carla proxy unreachable at {_BASE}: {e}")
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


class _Handle:
    def __init__(self, h):
        self._h = h

    def _m(self, method, *args):
        return _call(f"h{self._h}.{method}", *args)


class Client(_Handle):
    def __init__(self, host, port):
        r = _call("carla.Client", host, port)
        super().__init__(r["handle"])

    def set_timeout(self, t):
        self._m("set_timeout", t)

    def get_world(self):
        return World(self._m("get_world")["handle"])

    def get_available_maps(self):
        return self._m("get_available_maps")

    def load_world(self, name):
        return World(self._m("load_world", name)["handle"])

    def start_recorder(self, filename):
        return self._m("start_recorder", filename)

    def stop_recorder(self):
        self._m("stop_recorder")


class _Settings:
    def __init__(self, d):
        self.synchronous_mode = d.get("synchronous_mode", False)
        self.fixed_delta_seconds = d.get("fixed_delta_seconds")

    def _to_dict(self):
        return {"synchronous_mode": self.synchronous_mode,
                "fixed_delta_seconds": self.fixed_delta_seconds}


class _Weather:
    def __init__(self, d):
        self.cloudiness = d.get("cloudiness", 0.0)
        self.precipitation = d.get("precipitation", 0.0)
        self.wind_intensity = d.get("wind_intensity", 0.0)
        self.sun_altitude_angle = d.get("sun_altitude_angle", 45.0)
        self.fog_density = d.get("fog_density", 0.0)


class _LocationInline:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _RotationInline:
    def __init__(self, yaw):
        self.yaw = yaw


class _TransformInline:
    def __init__(self, x, y, z, yaw):
        self.location = _LocationInline(x, y, z)
        self.rotation = _RotationInline(yaw)


class _ActorInline:
    def __init__(self, d):
        self.id = d["id"]
        self.type_id = d["type_id"]
        self._x = d["x"]; self._y = d["y"]; self._z = d["z"]; self._yaw = d["yaw"]

    def get_transform(self):
        return _TransformInline(self._x, self._y, self._z, self._yaw)

    def destroy(self):
        pass


class _ActorList:
    def __init__(self, actors):
        self._actors = actors

    def __iter__(self):
        return iter(self._actors)

    def filter(self, pattern):
        pat = pattern.replace("*", "")
        return _ActorList([a for a in self._actors if pat in a.type_id])

    def __getitem__(self, i):
        return self._actors[i]


class _SpawnedActor(_Handle):
    def __init__(self, h, id_, type_id):
        super().__init__(h)
        self.id = id_
        self.type_id = type_id

    def destroy(self):
        self._m("destroy")


class _Map:
    def __init__(self, h, name, spawn_count, od_len):
        self.name = name
        self._spawn_count = spawn_count
        self._od_len = od_len

    def get_spawn_points(self):
        return [None] * self._spawn_count

    def to_opendrive(self):
        return "x" * self._od_len


class _Blueprint(_Handle):
    def __init__(self, h, id_):
        super().__init__(h)
        self.id = id_


class _BlueprintLibrary(_Handle):
    def filter(self, pattern):
        return self._m("filter", pattern)

    def find(self, bp_id):
        r = self._m("find", bp_id)
        if r is None:
            return None
        return _Blueprint(r["handle"], r["id"])


class World(_Handle):
    def get_settings(self):
        return _Settings(self._m("get_settings"))

    def apply_settings(self, settings):
        self._m("apply_settings", settings._to_dict())

    def get_weather(self):
        return _Weather(self._m("get_weather"))

    def set_weather(self, preset):
        self._m("set_weather", preset._h)

    def get_map(self):
        r = self._m("get_map")
        h = r["handle"]
        name = _call(f"h{h}.get_name")
        spawn_count = _call(f"h{h}.get_spawn_points")
        od_len = _call(f"h{h}.to_opendrive")
        return _Map(h, name, spawn_count, od_len)

    def get_actors(self):
        return _ActorList([_ActorInline(d) for d in self._m("get_actors")])

    def get_blueprint_library(self):
        return _BlueprintLibrary(self._m("get_blueprint_library")["handle"])

    def spawn_actor(self, blueprint, transform):
        r = self._m("spawn_actor", blueprint._h,
                    transform.location.x, transform.location.y,
                    transform.location.z, transform.rotation.yaw)
        return _SpawnedActor(r["handle"], r["id"], r["type_id"])

    def get_actor(self, actor_id):
        r = self._m("get_actor", actor_id)
        if r is None:
            return None
        return _SpawnedActor(r["handle"], r["id"], r["type_id"])

    def tick(self):
        return self._m("tick")


class _WeatherPreset(_Handle):
    pass


class _WeatherParameters:
    def __getattr__(self, name):
        r = _call(f"carla.WeatherParameters.{name}")
        p = _WeatherPreset(r["handle"])
        object.__setattr__(self, name, p)
        return p


WeatherParameters = _WeatherParameters()


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
