#!/usr/bin/env python3
"""
Direct CARLA connectivity test — runs with Python 3.7 + carla wheel.
No MCP required. Tests the same operations the MCP server would call.

Usage:
  python3.7 test_carla_direct.py [--host localhost] [--port 2000]
"""
import sys
import json
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="localhost")
parser.add_argument("--port", type=int, default=2000)
args = parser.parse_args()

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []


def check(name, fn):
    try:
        r = fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, r))
        return r
    except Exception as e:
        print(f"  {FAIL}  {name}: {e}")
        results.append((name, False, str(e)))
        return None


# Remove the script directory from sys.path so Python uses
# the real installed carla egg, not our tools/mcp-carla/carla/ stub.
import os as _os
_script_dir = _os.path.dirname(_os.path.abspath(__file__))
sys.path = [p for p in sys.path if _os.path.realpath(p) != _os.path.realpath(_script_dir)]

import carla

print("=" * 55)
print("  CARLA Direct Connectivity Test")
print(f"  Target: {args.host}:{args.port}")
print("=" * 55)

print("\n[1] Connection")
client = check("carla.Client()", lambda: carla.Client(args.host, args.port))
if client is None:
    sys.exit(1)

client.set_timeout(20.0)
world = check("client.get_world()", lambda: client.get_world())
if world is None:
    sys.exit(1)

print("\n[2] World state")
settings = check("world.get_settings()", lambda: world.get_settings())
weather = check("world.get_weather()", lambda: world.get_weather())
m = check("world.get_map()", lambda: world.get_map())
if m:
    print(f"    map name: {m.name}")
    spawn_pts = check("map.get_spawn_points()", lambda: m.get_spawn_points())
    if spawn_pts is not None:
        print(f"    spawn points: {len(spawn_pts)}")

print("\n[3] Blueprint library")
bpl = check("world.get_blueprint_library()", lambda: world.get_blueprint_library())
if bpl:
    vehicles = check("bpl.filter('vehicle.*')", lambda: list(bpl.filter("vehicle.*")))
    if vehicles:
        print(f"    vehicles: {len(vehicles)}")
        ids = [b.id for b in vehicles]
        has_tractor = any("carlasad.tractor" in i for i in ids)
        check("vehicle.carlasad.tractor in blueprints",
              lambda: True if has_tractor else (_ for _ in ()).throw(
                  AssertionError("tractor blueprint not found (expected after fork build)")))

    sensors = check("bpl.filter('sensor.*')", lambda: list(bpl.filter("sensor.*")))
    if sensors:
        print(f"    sensors: {len(sensors)}")
        s_ids = [b.id for b in sensors]
        has_thermal = "sensor.camera.thermal" in s_ids
        check("sensor.camera.thermal in blueprints",
              lambda: True if has_thermal else (_ for _ in ()).throw(
                  AssertionError("thermal camera not found (expected after fork build)")))

print("\n[4] Actors")
actors = check("world.get_actors()", lambda: list(world.get_actors()))
if actors is not None:
    print(f"    actors: {len(actors)}")

print("\n[5] Weather")
check("set_weather ClearNoon",
      lambda: world.set_weather(carla.WeatherParameters.ClearNoon))
check("set_weather ClearSunset",
      lambda: world.set_weather(carla.WeatherParameters.ClearSunset))

def _mk_settings(w, synchronous, delta=None):
    s = w.get_settings()
    s.synchronous_mode = synchronous
    s.fixed_delta_seconds = delta
    return s


print("\n[6] Sync mode + tick")
check("enable sync mode", lambda: world.apply_settings(
    _mk_settings(world, synchronous=True, delta=0.05)))
frame1 = check("tick 1", lambda: world.tick())
frame2 = check("tick 2", lambda: world.tick())
if frame1 and frame2:
    print(f"    frames: {frame1} → {frame2}")
check("disable sync mode", lambda: world.apply_settings(
    _mk_settings(world, synchronous=False)))


passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"\n{'='*55}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'='*55}")

sys.exit(0 if failed == 0 else 1)
