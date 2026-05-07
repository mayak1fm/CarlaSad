"""Unit tests for SessionRecorder and manifest writer."""
import json
import time
import pytest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carlasad.logging.recorder import SessionRecorder, RecorderConfig
from carlasad.logging.manifest import (
    write_session_manifest, write_completion_manifest, write_scenario_manifest
)


class TestSessionRecorder:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.session_path = Path(self.tmpdir) / "session_test"

    def _make_recorder(self, mode="online_debug"):
        config = RecorderConfig(
            mode=mode,
            session_path=self.session_path,
            map_name="TestMap",
            world_mode="editor",
            weather_preset="ClearNoon",
            seed=42,
        )
        return SessionRecorder(config)

    def test_start_creates_directory(self):
        rec = self._make_recorder()
        rec.start()
        assert self.session_path.exists()
        rec.stop()

    def test_start_creates_manifest(self):
        rec = self._make_recorder()
        rec.start()
        manifest_path = self.session_path / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["map_name"] == "TestMap"
        assert manifest["seed"] == 42
        rec.stop()

    def test_record_frame_writes_to_jsonl(self):
        rec = self._make_recorder()
        rec.start()
        rec.record_frame(0, {"ego_pose": {"x": 1.0, "y": 2.0}})
        rec.record_frame(1, {"ego_pose": {"x": 1.5, "y": 2.5}})
        rec.stop()

        gt_path = self.session_path / "gt_frames.jsonl"
        assert gt_path.exists()
        lines = [json.loads(l) for l in gt_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        assert lines[0]["ego_pose"]["x"] == pytest.approx(1.0)
        assert lines[1]["ego_pose"]["x"] == pytest.approx(1.5)

    def test_record_event_writes_to_jsonl(self):
        rec = self._make_recorder()
        rec.start()
        rec.record_event("obstacle_detected", {"id": 42, "distance": 5.0})
        rec.stop()

        events_path = self.session_path / "mission_events.jsonl"
        assert events_path.exists()
        lines = [json.loads(l) for l in events_path.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        assert lines[0]["event_type"] == "obstacle_detected"
        assert lines[0]["id"] == 42

    def test_frame_count_tracked(self):
        rec = self._make_recorder()
        rec.start()
        for i in range(10):
            rec.record_frame(i, {})
        assert rec.frame_count == 10
        rec.stop()

    def test_stop_writes_completion_manifest(self):
        rec = self._make_recorder()
        rec.start()
        time.sleep(0.05)
        rec.stop()

        manifest = json.loads((self.session_path / "manifest.json").read_text())
        assert "completed_at" in manifest
        assert manifest["frame_count"] == 0
        assert manifest["status"] == "completed"

    def test_stop_with_error_sets_error_status(self):
        rec = self._make_recorder()
        rec.start()
        rec.stop(error="CARLA disconnected")
        manifest = json.loads((self.session_path / "manifest.json").read_text())
        assert manifest["status"] == "error"
        assert "CARLA disconnected" in manifest["error"]

    def test_is_active_flag(self):
        rec = self._make_recorder()
        assert not rec.is_active
        rec.start()
        assert rec.is_active
        rec.stop()
        assert not rec.is_active

    def test_no_write_after_stop(self):
        rec = self._make_recorder()
        rec.start()
        rec.stop()
        rec.record_frame(999, {"test": True})  # should not crash or write
        lines = list(
            filter(None, (self.session_path / "gt_frames.jsonl").read_text().splitlines())
        )
        assert len(lines) == 0


class TestManifest:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.session_path = Path(self.tmpdir)

    def test_write_session_manifest(self):
        m = write_session_manifest(
            self.session_path, "mid-001", "Field_Main", "editor",
            "ClearNoon", "dataset_recording", "default", 42,
            scenario_id="field_patrol",
        )
        assert m["mission_id"] == "mid-001"
        assert m["world_mode"] == "editor"
        assert m["seed"] == 42

        on_disk = json.loads((self.session_path / "manifest.json").read_text())
        assert on_disk["scenario_id"] == "field_patrol"

    def test_write_completion_manifest(self):
        write_session_manifest(
            self.session_path, "m2", "Map", "editor", "ClearNoon", "debug", "default", 0
        )
        write_completion_manifest(self.session_path, 123.5, 2470)
        m = json.loads((self.session_path / "manifest.json").read_text())
        assert m["duration_seconds"] == pytest.approx(123.5)
        assert m["frame_count"] == 2470
        assert m["status"] == "completed"
