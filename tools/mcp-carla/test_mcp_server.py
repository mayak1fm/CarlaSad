"""
MCP server smoke tests.

Two modes:
  1. Offline (default) — validates tool registration and error handling without CARLA
  2. Online (--carla)  — connects to a real CARLA instance and exercises all tools

Usage:
  python test_mcp_server.py                    # offline
  python test_mcp_server.py --carla            # live CARLA at localhost:2000
  python test_mcp_server.py --carla --host X   # live CARLA at custom host
"""
import sys
import json
import argparse
import importlib.util
from pathlib import Path

# Load server module without executing __main__
spec = importlib.util.spec_from_file_location(
    "mcp_server",
    Path(__file__).parent / "server.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []


def check(name: str, fn):
    try:
        result = fn()
        print(f"  {PASS}  {name}")
        results.append((name, True, result))
        return result
    except Exception as e:
        print(f"  {FAIL}  {name}: {e}")
        results.append((name, False, str(e)))
        return None


# ── Offline tests — no CARLA needed ──────────────────────────────────────────

def test_offline():
    print("\n[offline] Tool registration")

    # All expected tools should be registered in the MCP server
    expected_tools = [
        "carla_status",
        "carla_list_maps",
        "carla_load_map",
        "carla_set_weather",
        "carla_set_sync_mode",
        "carla_tick",
        "carla_list_actors",
        "carla_spawn_tractor",
        "carla_destroy_actor",
        "carla_list_blueprints",
        "carla_get_map_info",
        "carla_run_scenario",
        "carla_start_recording",
        "carla_stop_recording",
    ]

    # Tool keys in FastMCP _tool_manager are the function names
    if hasattr(mod.mcp, '_tool_manager') and hasattr(mod.mcp._tool_manager, '_tools'):
        registered = set(mod.mcp._tool_manager._tools.keys())
    else:
        registered = {name for name in dir(mod)
                      if callable(getattr(mod, name, None)) and name.startswith("carla_")}

    for tool in expected_tools:
        check(f"tool registered: {tool}",
              lambda t=tool: (_ for _ in ()).throw(AssertionError(f"{t} missing"))
              if t not in registered else True)

    print("\n[offline] Error handling (no CARLA)")

    # carla_status should return JSON with connected=False, not raise
    check("carla_status returns JSON on no CARLA",
          lambda: json.loads(mod.carla_status()))

    result = mod.carla_status()
    parsed = json.loads(result)
    check("carla_status.connected=False when no CARLA",
          lambda: True if not parsed.get("connected", True) else
          (_ for _ in ()).throw(AssertionError(f"expected connected=False, got {parsed}")))

    # All other tools should raise RuntimeError (not crash with unexpected exception type)
    for fn_name in ["carla_list_maps", "carla_tick"]:
        fn = getattr(mod, fn_name)
        check(f"{fn_name} raises RuntimeError on no CARLA",
              lambda f=fn: f() if False else
              _assert_raises_runtime(f))


def _assert_raises_runtime(fn):
    try:
        fn()
        raise AssertionError("expected RuntimeError, got no exception")
    except RuntimeError:
        return True
    except Exception as e:
        raise AssertionError(f"expected RuntimeError, got {type(e).__name__}: {e}")


# ── Online tests — requires running CARLA ────────────────────────────────────

def test_online():
    print("\n[online] CARLA connectivity")

    status_raw = check("carla_status", mod.carla_status)
    if status_raw is None:
        print("  Cannot connect — skipping online tests")
        return

    status = json.loads(status_raw)
    if not status.get("connected"):
        print(f"  Cannot connect: {status.get('error')}")
        return

    print(f"  Connected to CARLA: map={status['map']}")

    check("carla_list_maps", mod.carla_list_maps)

    print("\n[online] Map info")
    check("carla_get_map_info", mod.carla_get_map_info)

    print("\n[online] Sync mode")
    check("carla_set_sync_mode(True)", lambda: mod.carla_set_sync_mode(True, 0.05))
    check("carla_tick", mod.carla_tick)
    check("carla_tick", mod.carla_tick)
    check("carla_set_sync_mode(False)", lambda: mod.carla_set_sync_mode(False))

    print("\n[online] Blueprints")
    bp_raw = check("carla_list_blueprints(vehicle.*)", lambda: mod.carla_list_blueprints("vehicle.*"))
    if bp_raw:
        bps = json.loads(bp_raw)
        print(f"  Found {len(bps)} vehicle blueprints")
        tractor_found = any("tractor" in bp.lower() for bp in bps)
        check("vehicle.carlasad.tractor in blueprints",
              lambda: True if tractor_found else
              (_ for _ in ()).throw(AssertionError(
                  "Tractor blueprint not registered. Expected after CARLA fork build.")))

    print("\n[online] Actors")
    check("carla_list_actors", mod.carla_list_actors)

    print("\n[online] Weather")
    check("carla_set_weather ClearNoon", lambda: mod.carla_set_weather("ClearNoon"))
    check("carla_set_weather ClearSunset", lambda: mod.carla_set_weather("ClearSunset"))

    print("\n[online] Sensor blueprints")
    sensors_raw = check("carla_list_blueprints(sensor.*)", lambda: mod.carla_list_blueprints("sensor.*"))
    if sensors_raw:
        sensors = json.loads(sensors_raw)
        print(f"  Found {len(sensors)} sensor blueprints")
        thermal_found = "sensor.camera.thermal" in sensors
        check("sensor.camera.thermal registered",
              lambda: True if thermal_found else
              (_ for _ in ()).throw(AssertionError(
                  "sensor.camera.thermal not found. Expected after CARLA fork build.")))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--carla", action="store_true", help="Run online CARLA tests")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()

    if args.host != "localhost" or args.port != 2000:
        import os
        os.environ["CARLA_HOST"] = args.host
        os.environ["CARLA_PORT"] = str(args.port)
        # Reset cached client
        mod._client = None
        mod._world = None

    print("=" * 55)
    print("  CarlaSad MCP Server Test Suite")
    print("=" * 55)

    test_offline()

    if args.carla:
        test_online()

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{'='*55}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'='*55}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
