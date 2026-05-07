#!/usr/bin/env python3
"""
MCP server for CARLA simulator.
Wraps CARLA Python API for use with Claude Code.
Requires running CARLA instance at CARLA_HOST:CARLA_PORT.
"""
import os
import json
import sys
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("mcp not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

CARLA_HOST = os.environ.get("CARLA_HOST", "localhost")
CARLA_PORT = int(os.environ.get("CARLA_PORT", "2000"))
CARLA_TIMEOUT = float(os.environ.get("CARLA_TIMEOUT", "10.0"))

mcp = FastMCP("carla-carlasad")

_client = None
_world = None


def _get_client():
    global _client, _world
    if _client is None:
        try:
            import carla
            _client = carla.Client(CARLA_HOST, CARLA_PORT)
            _client.set_timeout(CARLA_TIMEOUT)
            _world = _client.get_world()
        except Exception as e:
            raise RuntimeError(f"Cannot connect to CARLA at {CARLA_HOST}:{CARLA_PORT}: {e}")
    return _client, _world


# ── Connection & World ─────────────────────────────────────────────────────

@mcp.tool()
def carla_status() -> str:
    """Check CARLA connection and return server/world info."""
    try:
        client, world = _get_client()
        settings = world.get_settings()
        weather = world.get_weather()
        map_name = world.get_map().name
        return json.dumps({
            "connected": True,
            "host": CARLA_HOST,
            "port": CARLA_PORT,
            "map": map_name,
            "synchronous_mode": settings.synchronous_mode,
            "fixed_delta_seconds": settings.fixed_delta_seconds,
            "weather": {
                "cloudiness": weather.cloudiness,
                "precipitation": weather.precipitation,
                "wind_intensity": weather.wind_intensity,
                "sun_altitude_angle": weather.sun_altitude_angle,
                "fog_density": weather.fog_density,
            }
        }, indent=2)
    except Exception as e:
        return json.dumps({"connected": False, "error": str(e)})


@mcp.tool()
def carla_list_maps() -> str:
    """List all available maps in CARLA."""
    client, _ = _get_client()
    maps = client.get_available_maps()
    return json.dumps(sorted(maps), indent=2)


@mcp.tool()
def carla_load_map(map_name: str) -> str:
    """
    Load a map by name.
    Args:
        map_name: Map name, e.g. '/Game/Carla/Maps/Town01' or 'CarlaSad/Field_Main'
    """
    global _world
    client, _ = _get_client()
    _world = client.load_world(map_name)
    return json.dumps({"loaded": map_name, "ok": True})


@mcp.tool()
def carla_set_weather(preset: str) -> str:
    """
    Set weather by preset name.
    Args:
        preset: One of: ClearNoon, CloudyNoon, WetNoon, WetCloudyNoon, SoftRainNoon,
                MidRainyNoon, HardRainNoon, ClearSunset, CloudySunset, WetSunset,
                WetCloudySunset, SoftRainSunset, MidRainSunset, HardRainSunset
    """
    import carla
    _, world = _get_client()
    preset_map = {
        "ClearNoon": carla.WeatherParameters.ClearNoon,
        "CloudyNoon": carla.WeatherParameters.CloudyNoon,
        "WetNoon": carla.WeatherParameters.WetNoon,
        "HardRainNoon": carla.WeatherParameters.HardRainNoon,
        "ClearSunset": carla.WeatherParameters.ClearSunset,
        "MidRainSunset": carla.WeatherParameters.MidRainSunset,
    }
    if preset not in preset_map:
        return json.dumps({"error": f"Unknown preset. Choose from: {list(preset_map.keys())}"})
    world.set_weather(preset_map[preset])
    return json.dumps({"weather_preset": preset, "ok": True})


# ── Simulation Control ─────────────────────────────────────────────────────

@mcp.tool()
def carla_set_sync_mode(enabled: bool, fixed_delta_seconds: float = 0.05) -> str:
    """
    Enable or disable synchronous mode.
    Args:
        enabled: True = sync mode (deterministic), False = async
        fixed_delta_seconds: Physics timestep (default 0.05 = 20Hz)
    """
    import carla
    _, world = _get_client()
    settings = world.get_settings()
    settings.synchronous_mode = enabled
    settings.fixed_delta_seconds = fixed_delta_seconds if enabled else None
    world.apply_settings(settings)
    return json.dumps({"synchronous_mode": enabled, "fixed_delta_seconds": fixed_delta_seconds})


@mcp.tool()
def carla_tick() -> str:
    """Advance simulation by one tick (only in synchronous mode)."""
    _, world = _get_client()
    frame = world.tick()
    return json.dumps({"frame": frame})


# ── Actors ─────────────────────────────────────────────────────────────────

@mcp.tool()
def carla_list_actors(filter_type: Optional[str] = None) -> str:
    """
    List actors in the world.
    Args:
        filter_type: Optional filter, e.g. 'vehicle', 'walker', 'sensor'
    """
    _, world = _get_client()
    actors = world.get_actors()
    if filter_type:
        actors = actors.filter(f"*{filter_type}*")
    result = []
    for a in actors:
        result.append({
            "id": a.id,
            "type_id": a.type_id,
            "transform": {
                "x": a.get_transform().location.x,
                "y": a.get_transform().location.y,
                "z": a.get_transform().location.z,
                "yaw": a.get_transform().rotation.yaw,
            }
        })
    return json.dumps(result[:50], indent=2)


@mcp.tool()
def carla_spawn_tractor(x: float = 0.0, y: float = 0.0, z: float = 0.5, yaw: float = 0.0) -> str:
    """
    Spawn the CarlaSad tractor at given position.
    Args:
        x, y, z: World coordinates in meters
        yaw: Heading in degrees
    """
    import carla
    client, world = _get_client()
    bpl = world.get_blueprint_library()
    tractor_bp = bpl.find("vehicle.carlasad.tractor")
    if tractor_bp is None:
        tractor_bp = bpl.filter("vehicle.*")[0]
        return json.dumps({
            "warning": "CarlaSad tractor asset not found, used fallback",
            "blueprint": tractor_bp.id
        })
    transform = carla.Transform(
        carla.Location(x=x, y=y, z=z),
        carla.Rotation(yaw=yaw)
    )
    actor = world.spawn_actor(tractor_bp, transform)
    return json.dumps({"id": actor.id, "type_id": actor.type_id, "ok": True})


@mcp.tool()
def carla_destroy_actor(actor_id: int) -> str:
    """
    Destroy an actor by ID.
    Args:
        actor_id: Actor ID from carla_list_actors
    """
    _, world = _get_client()
    actor = world.get_actor(actor_id)
    if actor is None:
        return json.dumps({"error": f"Actor {actor_id} not found"})
    actor.destroy()
    return json.dumps({"destroyed": actor_id, "ok": True})


# ── Blueprints ─────────────────────────────────────────────────────────────

@mcp.tool()
def carla_list_blueprints(filter_str: str = "*") -> str:
    """
    List available actor blueprints.
    Args:
        filter_str: Filter pattern, e.g. 'vehicle.*', 'sensor.*', 'walker.*'
    """
    _, world = _get_client()
    bpl = world.get_blueprint_library()
    result = [bp.id for bp in bpl.filter(filter_str)]
    return json.dumps(sorted(result), indent=2)


# ── Map / Waypoints ─────────────────────────────────────────────────────────

@mcp.tool()
def carla_get_map_info() -> str:
    """Get current map name, open drive data summary, spawn points count."""
    _, world = _get_client()
    m = world.get_map()
    spawn_points = m.get_spawn_points()
    return json.dumps({
        "name": m.name,
        "spawn_points_count": len(spawn_points),
        "opendrive_length": len(m.to_opendrive()),
    })


# ── Traffic Manager / Scenario ─────────────────────────────────────────────

@mcp.tool()
def carla_run_scenario(scenario_path: str, seed: int = 42) -> str:
    """
    Run a CarlaSad scenario script.
    Args:
        scenario_path: Path relative to /scenarios/scripts/, e.g. 'field_patrol.py'
        seed: Random seed for reproducibility
    """
    import subprocess
    full_path = f"/home/mayakfm/dev/CarlaSad/scenarios/scripts/{scenario_path}"
    result = subprocess.run(
        ["python", full_path, "--seed", str(seed),
         "--host", CARLA_HOST, "--port", str(CARLA_PORT)],
        capture_output=True, text=True, timeout=30
    )
    return json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-1000:],
    })


# ── Recording ──────────────────────────────────────────────────────────────

@mcp.tool()
def carla_start_recording(filename: str) -> str:
    """
    Start CARLA built-in recording.
    Args:
        filename: Path for .log file, e.g. '/logs/session_001.log'
    """
    client, _ = _get_client()
    result = client.start_recorder(filename)
    return json.dumps({"recording": filename, "result": result})


@mcp.tool()
def carla_stop_recording() -> str:
    """Stop CARLA built-in recording."""
    client, _ = _get_client()
    client.stop_recorder()
    return json.dumps({"ok": True})


if __name__ == "__main__":
    mcp.run()
