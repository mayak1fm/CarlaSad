"""Scenario management endpoints."""
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

SCENARIOS_DIR = Path("/scenarios/configs")


class ScenarioRunRequest(BaseModel):
    scenario_id: str
    seed: int = 42


@router.get("")
def list_scenarios():
    if not SCENARIOS_DIR.exists():
        return []
    scenarios = []
    for f in sorted(SCENARIOS_DIR.glob("*.yaml")):
        scenarios.append({
            "scenario_id": f.stem,
            "path": str(f),
        })
    return scenarios


@router.post("/run")
def run_scenario(req: ScenarioRunRequest):
    config_path = SCENARIOS_DIR / f"{req.scenario_id}.yaml"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario {req.scenario_id} not found")
    # TODO: launch scenario script via subprocess
    return {"ok": True, "scenario_id": req.scenario_id, "seed": req.seed}
