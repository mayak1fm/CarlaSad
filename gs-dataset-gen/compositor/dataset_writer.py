"""Dataset writer — saves samples to disk in standardized format."""
import json
import datetime
from pathlib import Path
from typing import Optional


class DatasetWriter:
    """
    Output structure:
        {output_dir}/
            rgb/        0000.png, 0001.png, ...
            semantic/   0000.png, ...
            instance/   0000.png, ...
            depth/      0000.exr, ...
            labels/     0000.json, ...
            manifest.json
    """

    def __init__(self, output_dir: Path):
        self._dir = Path(output_dir)
        for subdir in ["rgb", "semantic", "instance", "depth", "labels"]:
            (self._dir / subdir).mkdir(parents=True, exist_ok=True)

    def write_sample(self, idx: int, passes: dict, labels: dict):
        name = f"{idx:06d}"

        if passes.get("rgb") is not None:
            self._save_image(self._dir / "rgb" / f"{name}.png", passes["rgb"])

        if passes.get("semantic") is not None:
            self._save_image(self._dir / "semantic" / f"{name}.png", passes["semantic"])

        if passes.get("object_id") is not None:
            self._save_image(self._dir / "instance" / f"{name}.png", passes["object_id"])

        if passes.get("depth") is not None:
            self._save_exr(self._dir / "depth" / f"{name}.exr", passes["depth"])

        label_path = self._dir / "labels" / f"{name}.json"
        label_path.write_text(json.dumps(labels, indent=2))

    def write_manifest(self, meta: dict):
        manifest = {
            "created_at": datetime.datetime.utcnow().isoformat(),
            "generator": "carlasad-gs-dataset-gen",
            "version": "0.1.0",
            **meta,
        }
        (self._dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    def _save_image(self, path: Path, data):
        if data is None:
            path.touch()
            return
        # TODO: save numpy array as PNG using PIL
        path.touch()

    def _save_exr(self, path: Path, data):
        if data is None:
            path.touch()
            return
        # TODO: save depth as EXR using OpenEXR or imageio
        path.touch()
