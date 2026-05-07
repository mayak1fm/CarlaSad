"""
CarlaSad world reconstruction pipeline.

Flow: images/video → COLMAP SfM → Gaussian Splatting → mesh extraction →
      collision mesh → heightmap → CARLA custom map import

Usage:
    python pipeline.py --input /data/field_photos/ --output /maps/reconstructed/field_01
    python pipeline.py --input /data/field_photos/ --stage sfm     # only SfM
    python pipeline.py --input /data/field_photos/ --stage gs       # SfM + GS
    python pipeline.py --input /data/field_photos/ --stage mesh     # all + mesh
    python pipeline.py --input /data/field_photos/ --stage carla    # full pipeline
"""
import argparse
import shutil
import subprocess
import logging
import json
import time
from pathlib import Path

logger = logging.getLogger("carlasad.reconstruction")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

STAGES = ["sfm", "gs", "mesh", "carla"]


def run_stage(name: str, cmd: list, cwd: Path, check: bool = True) -> bool:
    logger.info("[%s] Running: %s", name, " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        logger.debug(result.stdout[-2000:])
    if result.returncode != 0:
        logger.error("[%s] FAILED:\n%s", name, result.stderr[-2000:])
        if check:
            raise RuntimeError(f"Stage {name} failed")
        return False
    return True


class ReconstructionPipeline:
    def __init__(self, input_dir: Path, output_dir: Path, gpu: bool = True):
        self.input_dir  = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.gpu        = gpu

        # Stage output directories
        self.sfm_dir   = output_dir / "01_sfm"
        self.gs_dir    = output_dir / "02_gs"
        self.mesh_dir  = output_dir / "03_mesh"
        self.carla_dir = output_dir / "04_carla"

        for d in [self.sfm_dir, self.gs_dir, self.mesh_dir, self.carla_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.manifest = {
            "input": str(input_dir),
            "output": str(output_dir),
            "stages_completed": [],
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    # ── Stage 1: SfM (COLMAP) ─────────────────────────────────────────────

    def run_sfm(self):
        """
        Run COLMAP SfM to produce sparse point cloud + camera poses.
        Output: sfm_dir/sparse/0/{cameras.bin, images.bin, points3D.bin}
        """
        sparse_dir = self.sfm_dir / "sparse"
        database   = self.sfm_dir / "database.db"

        # Feature extraction
        run_stage("colmap:feature_extractor", [
            "colmap", "feature_extractor",
            "--database_path", str(database),
            "--image_path",    str(self.input_dir),
            "--ImageReader.camera_model", "OPENCV",
            "--SiftExtraction.use_gpu", "1" if self.gpu else "0",
        ], self.sfm_dir)

        # Feature matching
        run_stage("colmap:exhaustive_matcher", [
            "colmap", "exhaustive_matcher",
            "--database_path", str(database),
            "--SiftMatching.use_gpu", "1" if self.gpu else "0",
        ], self.sfm_dir)

        # Sparse reconstruction
        sparse_dir.mkdir(exist_ok=True)
        run_stage("colmap:mapper", [
            "colmap", "mapper",
            "--database_path", str(database),
            "--image_path",    str(self.input_dir),
            "--output_path",   str(sparse_dir),
        ], self.sfm_dir)

        logger.info("[sfm] Sparse reconstruction complete: %s", sparse_dir)
        self.manifest["stages_completed"].append("sfm")
        self._write_manifest()
        return sparse_dir / "0"

    # ── Stage 2: Gaussian Splatting (nerfstudio/3DGS) ─────────────────────

    def run_gs(self):
        """
        Train Gaussian Splatting model on SfM output.
        Uses nerfstudio (ns-train gaussian-splatting) as baseline.
        Output: gs_dir/output/splat.ply
        """
        sparse_path = self.sfm_dir / "sparse" / "0"
        if not sparse_path.exists():
            raise RuntimeError("SfM output not found. Run sfm stage first.")

        # Convert COLMAP to nerfstudio format
        run_stage("ns:colmap-to-ns", [
            "ns-process-data", "images",
            "--data",   str(self.input_dir),
            "--output", str(self.gs_dir / "ns_data"),
            "--colmap-dir", str(sparse_path),
            "--skip-colmap",
        ], self.gs_dir, check=False)

        # Train GS model
        run_stage("ns:train-gs", [
            "ns-train", "gaussian-splatting",
            "--data",           str(self.gs_dir / "ns_data"),
            "--output-dir",     str(self.gs_dir / "output"),
            "--max-num-iterations", "30000",
            "--pipeline.model.output-depth-during-training", "True",
        ], self.gs_dir, check=False)

        # Export .ply splat
        output_splat = self.gs_dir / "output" / "splat.ply"
        logger.info("[gs] GS training complete. Splat: %s", output_splat)
        self.manifest["stages_completed"].append("gs")
        self.manifest["splat_path"] = str(output_splat)
        self._write_manifest()
        return output_splat

    # ── Stage 3: Mesh Extraction ──────────────────────────────────────────

    def run_mesh_extraction(self):
        """
        Extract mesh from GS / point cloud.
        Produces:
          - visual_mesh.obj      (textured, for rendering)
          - collision_mesh.obj   (simplified, for CARLA physics)
          - heightmap.png        (terrain height, for CARLA import)
          - terrain_semantic.png (terrain label IDs, for CarlaSad)
        """
        from .mesh_extractor import MeshExtractor

        splat_path = self.gs_dir / "output" / "splat.ply"
        if not splat_path.exists():
            # Try to find any .ply in gs_dir
            plys = list(self.gs_dir.rglob("*.ply"))
            if plys:
                splat_path = plys[0]
            else:
                raise RuntimeError("No .ply file found. Run gs stage first.")

        extractor = MeshExtractor(splat_path, self.mesh_dir)
        extractor.extract_visual_mesh()
        extractor.extract_collision_mesh()
        extractor.extract_heightmap()

        logger.info("[mesh] Mesh extraction complete: %s", self.mesh_dir)
        self.manifest["stages_completed"].append("mesh")
        self._write_manifest()
        return self.mesh_dir

    # ── Stage 4: CARLA Map Import ─────────────────────────────────────────

    def run_carla_import(self, map_name: str = None):
        """
        Package mesh + heightmap as CARLA custom map.
        Output: carla_dir/ with .fbx, .xodr, heightmap.png
        Ready for: docker compose run carla-dev make import MAP=...
        """
        from .carla_map_builder import CarlaMapBuilder

        map_name = map_name or self.output_dir.name
        builder = CarlaMapBuilder(
            mesh_dir=self.mesh_dir,
            output_dir=self.carla_dir,
            map_name=map_name,
        )
        builder.build()

        logger.info("[carla] CARLA map package ready: %s", self.carla_dir)
        self.manifest["stages_completed"].append("carla")
        self.manifest["carla_map_name"] = map_name
        self._write_manifest()
        return self.carla_dir

    # ── Full Pipeline ─────────────────────────────────────────────────────

    def run(self, target_stage: str = "carla"):
        stage_idx = STAGES.index(target_stage)
        all_stages = STAGES[:stage_idx + 1]

        for stage in all_stages:
            if stage in self.manifest["stages_completed"]:
                logger.info("Skipping already-completed stage: %s", stage)
                continue
            getattr(self, f"run_{stage.replace('-', '_')}")()

    def _write_manifest(self):
        (self.output_dir / "reconstruction_manifest.json").write_text(
            json.dumps(self.manifest, indent=2)
        )


def main():
    parser = argparse.ArgumentParser(description="CarlaSad world reconstruction pipeline")
    parser.add_argument("--input",  required=True, help="Input images directory")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--stage",  default="carla", choices=STAGES,
                        help="Target stage (pipeline runs up to this stage)")
    parser.add_argument("--map-name", default=None, help="CARLA map name")
    parser.add_argument("--no-gpu",   action="store_true")
    args = parser.parse_args()

    pipeline = ReconstructionPipeline(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        gpu=not args.no_gpu,
    )
    pipeline.run(target_stage=args.stage)
    if args.stage == "carla" and args.map_name:
        pipeline.manifest["carla_map_name"] = args.map_name


if __name__ == "__main__":
    main()
