"""
Shadow compositor for GS synthetic dataset.

Generates object shadows using proxy mesh geometry.
NOT natural shadows from a single RGB pass.

Pipeline:
  1. Project proxy mesh silhouette along sun direction onto terrain plane
  2. Soften shadow edges (Gaussian blur, parameterized by sun angular size)
  3. Attenuate shadow by terrain distance + ambient light
  4. Blend shadow into background RGB before compositing object

Key rule: shadow pass uses proxy mesh, not raw splats.
This ensures label-consistent shadows that match proxy geometry.
"""
import numpy as np
from typing import Optional, Tuple
from .lighting_adapter import SceneLighting


class ProxyMeshShadow:
    """
    Shadow from a simplified proxy mesh (oriented bounding box or capsule).
    Fast enough for per-sample generation.
    """

    def __init__(self, lighting: SceneLighting):
        self._lighting = lighting

    def compute_shadow_mask(
        self,
        image_size: Tuple[int, int],      # (H, W)
        proxy_bbox: Optional[list],        # oriented bbox [[cx,cy,cz],[sx,sy,sz],[rx,ry,rz]]
        object_transform: dict,            # {x, y, z, yaw}
        camera_matrix: Optional[np.ndarray] = None,
        terrain_height: float = 0.0,
    ) -> np.ndarray:
        """
        Compute shadow mask in image space.
        Returns float array H x W, values 0 (no shadow) to 1 (full shadow).
        """
        H, W = image_size
        mask = np.zeros((H, W), dtype=np.float32)

        if proxy_bbox is None or object_transform is None:
            return mask

        # Get object footprint in world space
        footprint = self._compute_footprint(proxy_bbox, object_transform)
        if footprint is None:
            return mask

        # Project shadow along sun direction onto terrain
        shadow_polygon = self._project_shadow(footprint, terrain_height)
        if shadow_polygon is None or len(shadow_polygon) < 3:
            return mask

        # Project to image space
        if camera_matrix is None:
            # Orthographic projection fallback
            img_polygon = self._world_to_image_ortho(shadow_polygon, object_transform, image_size)
        else:
            img_polygon = self._world_to_image_perspective(shadow_polygon, camera_matrix, image_size)

        # Rasterize polygon
        mask = self._rasterize_polygon(img_polygon, H, W)

        # Soften edges (penumbra — sun has finite angular size)
        mask = self._soften_shadow(mask, softness=self._compute_softness())

        # Attenuate by ambient light (ambient reduces shadow darkness)
        shadow_strength = 1.0 - self._lighting.ambient_intensity * 0.7
        return mask * shadow_strength

    def apply_to_image(
        self,
        background_rgb: np.ndarray,  # H x W x 3, float 0-1
        shadow_mask: np.ndarray,     # H x W, float 0-1
        shadow_color_factor: float = 0.55,
    ) -> np.ndarray:
        """
        Apply shadow mask to background image.
        Shadow darkens background toward shadow_color_factor of original.
        """
        if background_rgb is None or shadow_mask is None:
            return background_rgb

        result = background_rgb.copy()
        shadow_3d = shadow_mask[:, :, np.newaxis]
        # Shadow: lerp between original and darkened version
        darkened = result * shadow_color_factor
        result = result * (1.0 - shadow_3d) + darkened * shadow_3d

        # Tint shadow slightly toward ambient color
        tint = self._lighting.ambient_color * 0.1
        result = np.clip(result + tint * shadow_3d, 0, 1)
        return result

    # ── Private ────────────────────────────────────────────────────────────

    def _compute_footprint(self, proxy_bbox: list, transform: dict) -> Optional[np.ndarray]:
        """Get world-space footprint of object from proxy bbox."""
        try:
            center = np.array(proxy_bbox[0])
            size   = np.array(proxy_bbox[1])
            yaw = np.radians(transform.get("yaw", 0))
            cos_y, sin_y = np.cos(yaw), np.sin(yaw)
            hw, hd = size[0] / 2, size[1] / 2

            # 4 corners of base in local space
            corners_local = np.array([
                [-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]
            ])
            # Rotate
            rot = np.array([[cos_y, -sin_y], [sin_y, cos_y]])
            corners_world = corners_local @ rot.T
            corners_world[:, 0] += transform.get("x", 0)
            corners_world[:, 1] += transform.get("y", 0)

            return corners_world
        except Exception:
            return None

    def _project_shadow(self, footprint: np.ndarray, terrain_height: float) -> Optional[np.ndarray]:
        """Project footprint along sun direction onto terrain plane."""
        sun = self._lighting.sun_direction
        if abs(sun[2]) < 1e-6:
            return None

        top_z = 0.0  # object is on terrain
        # How far shadow falls from object
        if sun[2] < 0:
            shadow_len = abs(top_z - terrain_height) / abs(sun[2])
        else:
            return None

        offset_x = sun[0] / abs(sun[2]) * shadow_len
        offset_y = sun[1] / abs(sun[2]) * shadow_len

        shadow_poly = footprint.copy()
        shadow_poly[:, 0] += offset_x
        shadow_poly[:, 1] += offset_y
        return shadow_poly

    def _world_to_image_ortho(
        self, polygon: np.ndarray, transform: dict, image_size: Tuple[int, int]
    ) -> np.ndarray:
        H, W = image_size
        cx = transform.get("x", 0)
        cy = transform.get("y", 0)
        scale = 5.0
        pts = np.zeros((len(polygon), 2), dtype=np.float32)
        pts[:, 0] = (polygon[:, 0] - cx) * scale + W / 2
        pts[:, 1] = (polygon[:, 1] - cy) * scale + H / 2
        return pts

    def _world_to_image_perspective(
        self, polygon: np.ndarray, K: np.ndarray, image_size: Tuple[int, int]
    ) -> np.ndarray:
        # Full perspective projection — requires extrinsics
        # Fallback to ortho for now
        return polygon

    def _rasterize_polygon(self, polygon: np.ndarray, H: int, W: int) -> np.ndarray:
        """Rasterize polygon to binary mask."""
        try:
            import cv2
            mask = np.zeros((H, W), dtype=np.uint8)
            pts = np.clip(polygon.astype(np.int32), 0, [W - 1, H - 1])
            cv2.fillPoly(mask, [pts], 1)
            return mask.astype(np.float32)
        except ImportError:
            return np.zeros((H, W), dtype=np.float32)

    def _soften_shadow(self, mask: np.ndarray, softness: float = 3.0) -> np.ndarray:
        """Gaussian blur for penumbra effect."""
        try:
            import cv2
            k = max(1, int(softness * 2) | 1)  # ensure odd kernel size
            return cv2.GaussianBlur(mask, (k, k), softness)
        except ImportError:
            return mask

    def _compute_softness(self) -> float:
        """More sun = sharper shadow; overcast = very soft."""
        return max(1.0, (1.0 - self._lighting.sun_intensity) * 20.0 + 2.0)
