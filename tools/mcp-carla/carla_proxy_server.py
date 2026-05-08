#!/usr/bin/env python3
"""
Carla JSON-RPC proxy — HTTP server, runs with Python 3.7 + carla wheel.

Usage:
  python3.7 carla_proxy_server.py [--port 19876] [--egg /path/to/carla.egg]

POST /rpc  {"call": "...", "args": [...], "id": N}
           → {"id": N, "result": ...}  or  {"id": N, "error": "msg"}

GET /health → {"ok": true}
"""
import sys
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=19876)
parser.add_argument("--egg", default=None)
args, _ = parser.parse_known_args()

if args.egg:
    sys.path.insert(0, args.egg)

import carla

_handles = {}
_next_h = [1]


def _store(obj):
    h = _next_h[0]
    _handles[h] = obj
    _next_h[0] += 1
    return h


def _ref(h):
    return _handles[int(h)]


def _settings_dict(s):
    return {"synchronous_mode": s.synchronous_mode,
            "fixed_delta_seconds": s.fixed_delta_seconds}


def _apply_settings_dict(world, d):
    s = world.get_settings()
    s.synchronous_mode = d.get("synchronous_mode", False)
    fds = d.get("fixed_delta_seconds")
    s.fixed_delta_seconds = fds
    return s


def _weather_dict(w):
    return {"cloudiness": w.cloudiness, "precipitation": w.precipitation,
            "wind_intensity": w.wind_intensity, "sun_altitude_angle": w.sun_altitude_angle,
            "fog_density": w.fog_density}


def _actor_dict(a):
    t = a.get_transform()
    return {"id": a.id, "type_id": a.type_id,
            "x": t.location.x, "y": t.location.y, "z": t.location.z, "yaw": t.rotation.yaw}


PRESETS = {
    "ClearNoon": carla.WeatherParameters.ClearNoon,
    "CloudyNoon": carla.WeatherParameters.CloudyNoon,
    "WetNoon": carla.WeatherParameters.WetNoon,
    "HardRainNoon": carla.WeatherParameters.HardRainNoon,
    "ClearSunset": carla.WeatherParameters.ClearSunset,
    "MidRainSunset": carla.WeatherParameters.MidRainSunset,
}


def dispatch(call, args, kwargs):
    parts = call.split(".", 1)

    if call == "carla.Client":
        return {"handle": _store(carla.Client(args[0], args[1]))}

    if call.startswith("carla.WeatherParameters."):
        return {"handle": _store(PRESETS[call.split(".")[-1]])}

    if parts[0].startswith("h"):
        h = int(parts[0][1:])
        obj = _ref(h)
        m = parts[1]

        if isinstance(obj, carla.Client):
            if m == "set_timeout":
                obj.set_timeout(args[0]); return None
            if m == "get_world":
                return {"handle": _store(obj.get_world())}
            if m == "get_available_maps":
                return sorted(obj.get_available_maps())
            if m == "load_world":
                return {"handle": _store(obj.load_world(args[0]))}
            if m == "start_recorder":
                return str(obj.start_recorder(args[0]))
            if m == "stop_recorder":
                obj.stop_recorder(); return None

        if isinstance(obj, carla.World):
            if m == "get_settings":
                return _settings_dict(obj.get_settings())
            if m == "apply_settings":
                obj.apply_settings(_apply_settings_dict(obj, args[0])); return None
            if m == "get_weather":
                return _weather_dict(obj.get_weather())
            if m == "set_weather":
                obj.set_weather(_ref(args[0])); return None
            if m == "get_map":
                return {"handle": _store(obj.get_map())}
            if m == "get_actors":
                return [_actor_dict(a) for a in obj.get_actors()]
            if m == "get_blueprint_library":
                return {"handle": _store(obj.get_blueprint_library())}
            if m == "spawn_actor":
                bp_h, tx, ty, tz, tyaw = args
                t = carla.Transform(carla.Location(x=tx, y=ty, z=tz), carla.Rotation(yaw=tyaw))
                a = obj.spawn_actor(_ref(bp_h), t)
                return {"handle": _store(a), "id": a.id, "type_id": a.type_id}
            if m == "get_actor":
                a = obj.get_actor(args[0])
                if a is None: return None
                return {"handle": _store(a), "id": a.id, "type_id": a.type_id}
            if m == "tick":
                return obj.tick()

        if isinstance(obj, carla.Map):
            if m == "get_name":  return obj.name
            if m == "get_spawn_points": return len(obj.get_spawn_points())
            if m == "to_opendrive": return len(obj.to_opendrive())

        if isinstance(obj, carla.BlueprintLibrary):
            if m == "filter":
                return [bp.id for bp in obj.filter(args[0])]
            if m == "find":
                bp = obj.find(args[0])
                if bp is None: return None
                return {"handle": _store(bp), "id": bp.id}

        if m == "destroy":
            obj.destroy(); return None

    raise ValueError(f"Unknown call: {call!r}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass  # quiet

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        req = json.loads(body)
        rid = req.get("id")
        try:
            result = dispatch(req["call"], req.get("args", []), req.get("kwargs", {}))
            self._json(200, {"id": rid, "result": result})
        except Exception as e:
            self._json(200, {"id": rid, "error": str(e)})

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


import socket
import socketserver


class DualStackServer(socketserver.TCPServer):
    """Binds on IPv6 with IPV6_V6ONLY=0 → accepts both IPv4 and IPv6."""
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


class ThreadedServer(socketserver.ThreadingMixIn, DualStackServer):
    daemon_threads = True


if __name__ == "__main__":
    print(f"[carla-proxy] starting on ::::{args.port}", flush=True)
    with ThreadedServer(("::", args.port), Handler) as srv:
        srv.serve_forever()
