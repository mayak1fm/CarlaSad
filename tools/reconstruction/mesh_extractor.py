"""
Mesh extraction from Gaussian Splatting .ply output.

Produces:
  visual_mesh.obj      — textured mesh for rendering
  collision_mesh.obj   — simplified convex hulls for CARLA physics
  heightmap.png        — 16-bit terrain height for CARLA import
  terrain_semantic.png — semantic label IDs for CarlaSad layers
"""
import logging
import struct
import numpy as np
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("carlasad.reconstruction.mesh_extractor")

# Heightmap output resolution (pixels per meter)
HEIGHTMAP_PPM = 2.0
HEIGHTMAP_SIZE = (1024, 1024)

# Poisson reconstruction depth (higher = more detail, slower)
POISSON_DEPTH = 9

# Decimation target for collision mesh (fraction of original faces)
COLLISION_DECIMATION = 0.05


class PLYReader:
    """Minimal PLY reader for GS output (positions + optional colors)."""

    def read(self, path: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Returns (points Nx3, colors Nx3 uint8). Colors may be empty."""
        with open(path, "rb") as f:
            header, data_start = self._parse_header(f)
            points, colors = self._read_data(f, header, data_start)
        return points, colors

    def _parse_header(self, f):
        header = {"format": "binary_little_endian", "elements": []}
        current_element = None
        data_start = 0

        while True:
            line = f.readline().decode("ascii", errors="replace").strip()
            data_start += len(line) + 1
            if line == "end_header":
                break
            tokens = line.split()
            if not tokens:
                continue
            if tokens[0] == "format":
                header["format"] = tokens[1]
            elif tokens[0] == "element":
                current_element = {"name": tokens[1], "count": int(tokens[2]), "props": []}
                header["elements"].append(current_element)
            elif tokens[0] == "property" and current_element is not None:
                current_element["props"].append({"type": tokens[1], "name": tokens[2]})

        return header, f.tell()

    def _read_data(self, f, header, data_start):
        f.seek(data_start)
        points = np.empty((0, 3), dtype=np.float32)
        colors = np.empty((0, 3), dtype=np.uint8)

        for element in header["elements"]:
            if element["name"] != "vertex":
                continue

            n = element["count"]
            props = element["props"]
            prop_names = [p["name"] for p in props]
            prop_types = [p["type"] for p in props]

            fmt_map = {
                "float": ("f", 4), "float32": ("f", 4),
                "double": ("d", 8), "float64": ("d", 8),
                "uchar": ("B", 1), "uint8": ("B", 1),
                "int": ("i", 4), "int32": ("i", 4),
                "uint": ("I", 4), "uint32": ("I", 4),
            }

            row_fmt = ""
            row_size = 0
            for pt in prop_types:
                fmt, sz = fmt_map.get(pt, ("f", 4))
                row_fmt += fmt
                row_size += sz

            raw = f.read(n * row_size)
            if len(raw) < n * row_size:
                logger.warning("PLY: truncated data (%d/%d bytes)", len(raw), n * row_size)
                n = len(raw) // row_size

            rows = struct.unpack_from(f"<{n}{row_fmt}", raw)
            nprops = len(props)
            arr = np.array(rows, dtype=object).reshape(n, nprops)

            xyz_idx = [prop_names.index(ax) for ax in ("x", "y", "z") if ax in prop_names]
            if len(xyz_idx) == 3:
                points = arr[:, xyz_idx].astype(np.float32)

            rgb_idx = [prop_names.index(ch) for ch in ("red", "green", "blue")
                       if ch in prop_names]
            if len(rgb_idx) == 3:
                colors = arr[:, rgb_idx].astype(np.uint8)

        return points, colors


class MeshExtractor:
    def __init__(self, splat_path: Path, output_dir: Path):
        self.splat_path = Path(splat_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._points = None
        self._colors = None

    def _load_splat(self):
        if self._points is not None:
            return
        logger.info("[mesh] Loading splat: %s", self.splat_path)
        reader = PLYReader()
        self._points, self._colors = reader.read(self.splat_path)
        logger.info("[mesh] Loaded %d points", len(self._points))

    # ── Visual mesh ───────────────────────────────────────────────────────

    def extract_visual_mesh(self) -> Path:
        """
        Run Poisson surface reconstruction on GS point cloud.
        Falls back to writing a dense point cloud .obj if open3d unavailable.
        """
        self._load_splat()
        out_path = self.output_dir / "visual_mesh.obj"

        try:
            import open3d as o3d
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(self._points)
            if len(self._colors) == len(self._points):
                pcd.colors = o3d.utility.Vector3dVector(self._colors.astype(np.float64) / 255.0)

            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
            )
            pcd.orient_normals_consistent_tangent_plane(100)

            logger.info("[mesh] Running Poisson reconstruction (depth=%d)...", POISSON_DEPTH)
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=POISSON_DEPTH
            )

            # Remove low-density vertices (surface boundary cleanup)
            density_arr = np.asarray(densities)
            threshold = np.quantile(density_arr, 0.05)
            vertices_to_remove = density_arr < threshold
            mesh.remove_vertices_by_mask(vertices_to_remove)

            o3d.io.write_triangle_mesh(str(out_path), mesh)
            logger.info("[mesh] Visual mesh: %s (%d triangles)", out_path, len(mesh.triangles))

        except ImportError:
            logger.warning("[mesh] open3d not available — writing point cloud .obj as fallback")
            self._write_point_cloud_obj(out_path)

        return out_path

    def _write_point_cloud_obj(self, path: Path):
        with open(path, "w") as f:
            f.write("# CarlaSad point cloud (no open3d)\n")
            for i, (x, y, z) in enumerate(self._points):
                f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
        logger.info("[mesh] Wrote %d points to %s", len(self._points), path)

    # ── Collision mesh ────────────────────────────────────────────────────

    def extract_collision_mesh(self) -> Path:
        """
        Simplified mesh for CARLA physics (convex decomposition or decimated).
        Target: < 5% of visual mesh face count, watertight.
        """
        self._load_splat()
        visual_path = self.output_dir / "visual_mesh.obj"
        out_path    = self.output_dir / "collision_mesh.obj"

        if not visual_path.exists():
            self.extract_visual_mesh()

        try:
            import open3d as o3d
            mesh = o3d.io.read_triangle_mesh(str(visual_path))

            original_count = len(mesh.triangles)
            target_count   = max(100, int(original_count * COLLISION_DECIMATION))

            simplified = mesh.simplify_quadric_decimation(target_count)
            simplified.remove_degenerate_triangles()
            simplified.remove_duplicated_vertices()

            o3d.io.write_triangle_mesh(str(out_path), simplified)
            logger.info("[mesh] Collision mesh: %s (%d/%d triangles)",
                        out_path, len(simplified.triangles), original_count)

        except ImportError:
            logger.warning("[mesh] open3d not available — copying visual mesh as collision mesh")
            import shutil
            shutil.copy2(visual_path, out_path)

        return out_path

    # ── Heightmap ─────────────────────────────────────────────────────────

    def extract_heightmap(self) -> Path:
        """
        Project point cloud onto XY plane, interpolate Z → 16-bit PNG.
        Also produces terrain_semantic.png using color clustering if colors present.
        """
        self._load_splat()
        hm_path  = self.output_dir / "heightmap.png"
        sem_path = self.output_dir / "terrain_semantic.png"

        pts = self._points
        if len(pts) == 0:
            logger.error("[mesh] No points loaded, cannot extract heightmap")
            return hm_path

        x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
        x_min, x_max = float(x.min()), float(x.max())
        y_min, y_max = float(y.min()), float(y.max())

        w, h = HEIGHTMAP_SIZE
        x_norm = ((x - x_min) / max(x_max - x_min, 1e-6) * (w - 1)).astype(np.int32)
        y_norm = ((y - y_min) / max(y_max - y_min, 1e-6) * (h - 1)).astype(np.int32)

        z_min, z_max = float(z.min()), float(z.max())
        z_norm = ((z - z_min) / max(z_max - z_min, 1e-6) * 65535).astype(np.uint16)

        heightmap = np.zeros((h, w), dtype=np.uint16)
        heightmap[y_norm, x_norm] = z_norm

        # Fill gaps with nearest-neighbor (simple max-pool diffusion)
        heightmap = self._fill_heightmap_gaps(heightmap)

        try:
            import cv2
            cv2.imwrite(str(hm_path), heightmap)
            logger.info("[mesh] Heightmap: %s (%dx%d, z range %.2f–%.2f m)",
                        hm_path, w, h, z_min, z_max)
            self._extract_terrain_semantic(sem_path, x_norm, y_norm, w, h)
        except ImportError:
            self._write_heightmap_pgm(hm_path.with_suffix(".pgm"), heightmap)
            logger.info("[mesh] Heightmap (PGM): %s", hm_path.with_suffix(".pgm"))

        self._write_heightmap_metadata(x_min, x_max, y_min, y_max, z_min, z_max, w, h)
        return hm_path

    def _fill_heightmap_gaps(self, hm: np.ndarray) -> np.ndarray:
        filled = hm.copy()
        empty = filled == 0
        if not empty.any():
            return filled

        # Iterative dilation to fill gaps (max 5 passes)
        try:
            import cv2
            kernel = np.ones((5, 5), np.uint8)
            for _ in range(5):
                dilated  = cv2.dilate(filled, kernel)
                filled   = np.where(empty, dilated, filled)
                empty    = filled == 0
                if not empty.any():
                    break
        except ImportError:
            pass
        return filled

    def _extract_terrain_semantic(self, out_path: Path, xi, yi, w, h):
        """Rough semantic map from color clustering (if colors present)."""
        if len(self._colors) != len(self._points):
            logger.info("[mesh] No colors in splat, skipping semantic map")
            return

        import cv2
        colors_f = self._colors.astype(np.float32)

        # K-means cluster into N terrain classes
        n_clusters = 6
        criteria   = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, _ = cv2.kmeans(colors_f, n_clusters, None, criteria, 3,
                                  cv2.KMEANS_RANDOM_CENTERS)
        labels = labels.flatten().astype(np.uint8)

        # Map cluster IDs → CarlaSad semantic IDs (rough: cluster 0→100, etc.)
        CLUSTER_TO_SEMANTIC = {0: 100, 1: 101, 2: 102, 3: 104, 4: 110, 5: 111}
        sem_labels = np.array([CLUSTER_TO_SEMANTIC.get(int(l), 100) for l in labels],
                              dtype=np.uint8)

        sem_map = np.full((h, w), 100, dtype=np.uint8)
        sem_map[yi, xi] = sem_labels
        cv2.imwrite(str(out_path), sem_map)
        logger.info("[mesh] Terrain semantic map: %s", out_path)

    def _write_heightmap_pgm(self, path: Path, hm: np.ndarray):
        h, w = hm.shape
        with open(path, "wb") as f:
            f.write(f"P5\n{w} {h}\n65535\n".encode())
            f.write(hm.astype(">u2").tobytes())

    def _write_heightmap_metadata(self, x_min, x_max, y_min, y_max, z_min, z_max, w, h):
        import json
        meta = {
            "width_px": w, "height_px": h,
            "x_min_m": x_min, "x_max_m": x_max,
            "y_min_m": y_min, "y_max_m": y_max,
            "z_min_m": z_min, "z_max_m": z_max,
            "meters_per_pixel_x": (x_max - x_min) / max(w - 1, 1),
            "meters_per_pixel_y": (y_max - y_min) / max(h - 1, 1),
        }
        meta_path = self.output_dir / "heightmap_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
        logger.info("[mesh] Heightmap metadata: %s", meta_path)
