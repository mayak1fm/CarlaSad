"""Manifest writer — writes JSON manifests for sessions, datasets, scenarios."""
import json
import datetime
from pathlib import Path
from typing import Optional


def write_session_manifest(
    session_path: Path,
    mission_id: str,
    map_name: str,
    world_mode: str,
    weather_preset: str,
    logging_mode: str,
    sensor_rig: str,
    seed: int,
    scenario_id: Optional[str] = None,
    extra: Optional[dict] = None,
):
    manifest = {
        "version": "1.0",
        "type": "session",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "mission_id": mission_id,
        "map": map_name,
        "world_mode": world_mode,
        "weather_preset": weather_preset,
        "logging_mode": logging_mode,
        "sensor_rig_profile": sensor_rig,
        "seed": seed,
        "scenario_id": scenario_id,
    }
    if extra:
        manifest.update(extra)
    (session_path / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def write_sensor_rig_manifest(session_path: Path, rig_config: dict):
    (session_path / "sensor_rig.json").write_text(json.dumps(rig_config, indent=2))


def write_scenario_manifest(session_path: Path, scenario_config: dict, seed: int):
    manifest = {
        "type": "scenario",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "seed": seed,
        **scenario_config,
    }
    (session_path / "scenario.json").write_text(json.dumps(manifest, indent=2))


def write_completion_manifest(session_path: Path, duration_seconds: float, frame_count: int, error: Optional[str] = None):
    completion = {
        "completed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "duration_seconds": round(duration_seconds, 2),
        "frame_count": frame_count,
        "status": "error" if error else "completed",
        "error": error,
    }
    existing_path = session_path / "manifest.json"
    if existing_path.exists():
        manifest = json.loads(existing_path.read_text())
        manifest.update(completion)
        existing_path.write_text(json.dumps(manifest, indent=2))
    else:
        (session_path / "completion.json").write_text(json.dumps(completion, indent=2))
