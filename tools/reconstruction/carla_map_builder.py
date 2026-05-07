"""
Package reconstructed mesh as a CARLA custom map.

Produces in output_dir/:
  {map_name}.fbx        — merged visual mesh (Datasmith/FBX for UE5 import)
  {map_name}.xodr       — minimal OpenDRIVE road network (single straight road)
  heightmap.png         — copied from mesh stage
  terrain_semantic.png  — copied from mesh stage (if present)
  map_config.json       — map dimensions and import hints

Usage inside CARLA Makefile:
  docker compose run carla-dev bash -c \
    "cp -r /maps/{map_name} /carla/Import && make import MAP={map_name}"
"""
import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger("carlasad.reconstruction.carla_map_builder")


class CarlaMapBuilder:
    def __init__(self, mesh_dir: Path, output_dir: Path, map_name: str):
        self.mesh_dir   = Path(mesh_dir)
        self.output_dir = Path(output_dir)
        self.map_name   = map_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build(self):
        logger.info("[carla_map] Building CARLA map package: %s", self.map_name)

        self._copy_heightmap()
        self._convert_mesh_to_fbx()
        self._write_xodr()
        self._write_map_config()

        logger.info("[carla_map] Package ready: %s", self.output_dir)

    # ── Assets ────────────────────────────────────────────────────────────

    def _copy_heightmap(self):
        for fname in ("heightmap.png", "terrain_semantic.png", "heightmap.pgm"):
            src = self.mesh_dir / fname
            if src.exists():
                dst = self.output_dir / fname
                shutil.copy2(src, dst)
                logger.info("[carla_map] Copied %s", fname)

        meta_src = self.mesh_dir / "heightmap_meta.json"
        if meta_src.exists():
            shutil.copy2(meta_src, self.output_dir / "heightmap_meta.json")

    def _convert_mesh_to_fbx(self):
        """
        Convert visual_mesh.obj → {map_name}.fbx via Blender headless.
        Falls back to copying .obj if Blender not available.
        """
        visual_obj  = self.mesh_dir / "visual_mesh.obj"
        out_fbx     = self.output_dir / f"{self.map_name}.fbx"
        collision_obj = self.mesh_dir / "collision_mesh.obj"

        if not visual_obj.exists():
            logger.warning("[carla_map] visual_mesh.obj not found, skipping FBX conversion")
            return

        converted = self._try_blender_fbx(visual_obj, out_fbx)
        if not converted:
            logger.warning("[carla_map] Blender not available — copying .obj as .fbx placeholder")
            shutil.copy2(visual_obj, out_fbx.with_suffix(".obj"))

        if collision_obj.exists():
            shutil.copy2(collision_obj, self.output_dir / f"{self.map_name}_collision.obj")

    def _try_blender_fbx(self, obj_path: Path, fbx_path: Path) -> bool:
        """Run Blender headlessly to export FBX. Returns True on success."""
        import subprocess
        import tempfile

        script = f"""
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.obj(filepath=r"{obj_path}")
bpy.ops.export_scene.fbx(
    filepath=r"{fbx_path}",
    use_selection=False,
    apply_scale_options='FBX_SCALE_ALL',
    axis_forward='-Z',
    axis_up='Y',
    mesh_smooth_type='FACE',
)
"""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            result = subprocess.run(
                ["blender", "--background", "--python", script_path],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                logger.info("[carla_map] FBX exported: %s", fbx_path)
                return True
            else:
                logger.debug("[carla_map] Blender error: %s", result.stderr[-500:])
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        finally:
            Path(script_path).unlink(missing_ok=True)

    # ── OpenDRIVE ─────────────────────────────────────────────────────────

    def _write_xodr(self):
        """
        Minimal OpenDRIVE 1.6 file with a single 1000 m straight road.
        CARLA requires at least one road to load the map.
        Adjust manually in RoadRunner for real road networks.
        """
        meta_path = self.output_dir / "heightmap_meta.json"
        road_length = 1000.0
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            road_length = max(
                meta.get("x_max_m", 0) - meta.get("x_min_m", 0),
                meta.get("y_max_m", 0) - meta.get("y_min_m", 0),
            )

        xodr_content = f"""<?xml version="1.0" standalone="yes"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="6" name="{self.map_name}"
          version="1.00" date="2024-01-01T00:00:00"
          north="{road_length:.2f}" south="0.0" east="{road_length:.2f}" west="0.0"
          vendor="CarlaSad">
  </header>
  <road name="Road_0" length="{road_length:.4f}" id="0" junction="-1">
    <link/>
    <type s="0.0000000000000000e+0" type="rural"/>
    <planView>
      <geometry s="0.0000000000000000e+0"
                x="0.0000000000000000e+0"
                y="0.0000000000000000e+0"
                hdg="0.0000000000000000e+0"
                length="{road_length:.4f}">
        <line/>
      </geometry>
    </planView>
    <elevationProfile/>
    <lateralProfile/>
    <lanes>
      <laneSection s="0.0000000000000000e+0">
        <center>
          <lane id="0" type="none" level="false">
            <roadMark sOffset="0.0" type="solid" weight="standard"
                      color="white" width="0.13"/>
          </lane>
        </center>
        <right>
          <lane id="-1" type="driving" level="false">
            <width sOffset="0.0" a="3.5" b="0.0" c="0.0" d="0.0"/>
          </lane>
        </right>
      </laneSection>
    </lanes>
    <objects/>
    <signals/>
  </road>
</OpenDRIVE>
"""
        xodr_path = self.output_dir / f"{self.map_name}.xodr"
        xodr_path.write_text(xodr_content)
        logger.info("[carla_map] OpenDRIVE: %s (road length %.1f m)", xodr_path, road_length)

    # ── Config ────────────────────────────────────────────────────────────

    def _write_map_config(self):
        meta_path = self.output_dir / "heightmap_meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())

        config = {
            "map_name":  self.map_name,
            "map_type":  "reconstructed",
            "source":    "CarlaSad reconstruction pipeline",
            "terrain": {
                "width_m":  round(meta.get("x_max_m", 0) - meta.get("x_min_m", 0), 2),
                "height_m": round(meta.get("y_max_m", 0) - meta.get("y_min_m", 0), 2),
                "z_min_m":  meta.get("z_min_m", 0),
                "z_max_m":  meta.get("z_max_m", 0),
            },
            "import_hints": {
                "fbx_file":        f"{self.map_name}.fbx",
                "xodr_file":       f"{self.map_name}.xodr",
                "heightmap_file":  "heightmap.png",
                "collision_file":  f"{self.map_name}_collision.obj",
                "carla_import_cmd": (
                    f"docker compose run carla-dev bash -c "
                    f"'cp -r /maps/{self.map_name} /carla/Import && "
                    f"make import MAP={self.map_name}'"
                ),
            },
        }

        config_path = self.output_dir / "map_config.json"
        config_path.write_text(json.dumps(config, indent=2))
        logger.info("[carla_map] Config: %s", config_path)
