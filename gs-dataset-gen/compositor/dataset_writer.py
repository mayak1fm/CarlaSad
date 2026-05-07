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
        if data is None or not hasattr(data, "shape"):
            return
        arr = data
        try:
            from PIL import Image
            if arr.dtype != "uint8":
                arr = arr.astype("uint8")
            if arr.ndim == 2:
                Image.fromarray(arr, mode="L").save(str(path))
            elif arr.shape[2] == 4:
                Image.fromarray(arr, mode="RGBA").save(str(path))
            else:
                Image.fromarray(arr, mode="RGB").save(str(path))
            return
        except ImportError:
            pass
        try:
            import cv2
            cv2.imwrite(str(path), arr)
        except ImportError:
            path.write_bytes(arr.astype("uint8").tobytes())

    def _save_exr(self, path: Path, data):
        if data is None or not hasattr(data, "shape"):
            return
        arr = data.astype("float32")
        try:
            import imageio
            imageio.imwrite(str(path), arr)
            return
        except ImportError:
            pass
        # Fallback: 16-bit PNG (depth in mm, clamped to 65535)
        png_path = path.with_suffix(".png")
        depth_mm = (arr * 1000.0).clip(0, 65535).astype("uint16")
        try:
            import cv2
            cv2.imwrite(str(png_path), depth_mm)
        except ImportError:
            pass
