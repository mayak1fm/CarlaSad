"""
Lighting adapter for GS object insertion.

D3DR-inspired post-insertion relighting:
  1. Estimate scene lighting from background GS scene (sun direction, ambient)
  2. Compute irradiance on object surface via proxy mesh normals
  3. Adjust object appearance: brightness, shadow softness, color temperature
  4. Composit adjusted object into scene

This is NOT manual light parameter tuning.
The scene lighting is estimated automatically from the background.
"""
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class SceneLighting:
    """Estimated lighting parameters from background GS scene."""
    sun_direction: np.ndarray      # unit vector [dx, dy, dz]
    sun_intensity: float           # 0–1
    sun_color: np.ndarray          # [R, G, B] 0–1
    ambient_intensity: float       # 0–1
    ambient_color: np.ndarray      # [R, G, B] 0–1
    sky_luminance: float           # overall sky brightness

    @classmethod
    def from_weather_preset(cls, preset: str) -> "SceneLighting":
        """Construct lighting parameters from named weather preset."""
        presets = {
            "ClearNoon": cls(
                sun_direction=np.array([0.5, -0.5, -0.7]),
                sun_intensity=0.9,
                sun_color=np.array([1.0, 0.98, 0.92]),
                ambient_intensity=0.4,
                ambient_color=np.array([0.7, 0.85, 1.0]),
                sky_luminance=0.85,
            ),
            "CloudyNoon": cls(
                sun_direction=np.array([0.3, -0.3, -0.9]),
                sun_intensity=0.4,
                sun_color=np.array([0.9, 0.9, 1.0]),
                ambient_intensity=0.7,
                ambient_color=np.array([0.85, 0.9, 1.0]),
                sky_luminance=0.65,
            ),
            "ClearSunset": cls(
                sun_direction=np.array([0.9, 0.0, -0.1]),
                sun_intensity=0.6,
                sun_color=np.array([1.0, 0.6, 0.3]),
                ambient_intensity=0.3,
                ambient_color=np.array([1.0, 0.7, 0.5]),
                sky_luminance=0.5,
            ),
            "HardRainNoon": cls(
                sun_direction=np.array([0.2, -0.2, -0.95]),
                sun_intensity=0.15,
                sun_color=np.array([0.8, 0.85, 0.95]),
                ambient_intensity=0.6,
                ambient_color=np.array([0.8, 0.85, 0.95]),
                sky_luminance=0.4,
            ),
        }
        return presets.get(preset, presets["ClearNoon"])

    @classmethod
    def estimate_from_image(cls, background_rgb: np.ndarray) -> "SceneLighting":
        """
        Estimate lighting from background GS render.
        Uses: brightest region → sun direction proxy,
              mean color of sky region → ambient.
        Fast approximation, not full inverse rendering.
        """
        if background_rgb is None:
            return cls.from_weather_preset("ClearNoon")

        h, w = background_rgb.shape[:2]
        sky_region = background_rgb[:h // 3, :]
        ambient_color = sky_region.mean(axis=(0, 1)) / 255.0
        sky_luminance = float(ambient_color.mean())

        # Find brightest patch → estimate sun position
        gray = background_rgb.mean(axis=2)
        bright_y, bright_x = np.unravel_index(gray[:h // 2].argmax(), gray[:h // 2].shape)
        sun_azimuth = (bright_x / w - 0.5) * np.pi
        sun_elevation = 0.3 + (0.5 - bright_y / (h // 2)) * 0.8
        sun_direction = np.array([
            np.cos(sun_elevation) * np.sin(sun_azimuth),
            np.cos(sun_elevation) * np.cos(sun_azimuth),
            -np.sin(sun_elevation),
        ])

        return cls(
            sun_direction=sun_direction / np.linalg.norm(sun_direction),
            sun_intensity=min(1.0, float(gray[:h // 2].max()) / 255.0 * 1.2),
            sun_color=np.clip(ambient_color * 1.3, 0, 1),
            ambient_intensity=sky_luminance * 0.6,
            ambient_color=ambient_color,
            sky_luminance=sky_luminance,
        )


class LightingAdapter:
    """
    Applies lighting correction to inserted object images.

    Pipeline per object:
      1. Compute per-pixel irradiance from proxy mesh normals + scene lighting
      2. Blend object irradiance with scene ambient
      3. Apply tone-mapping to match background exposure
      4. Adjust white balance to match scene color temperature
    """

    def __init__(self, lighting: Optional[SceneLighting] = None):
        self._lighting = lighting or SceneLighting.from_weather_preset("ClearNoon")

    def set_lighting(self, lighting: SceneLighting):
        self._lighting = lighting

    def relight_object(
        self,
        object_rgba: np.ndarray,       # H x W x 4  (RGBA, float 0-1)
        object_normals: Optional[np.ndarray] = None,  # H x W x 3  surface normals
        depth_mask: Optional[np.ndarray] = None,       # H x W  binary mask
    ) -> np.ndarray:
        """
        Apply scene lighting to object RGBA image.
        Returns relit RGBA float array.
        """
        if object_rgba is None:
            return object_rgba

        lit = object_rgba.copy().astype(np.float32)
        rgb = lit[:, :, :3]
        alpha = lit[:, :, 3:4] if lit.shape[2] == 4 else np.ones((*lit.shape[:2], 1))

        if object_normals is not None:
            irradiance = self._compute_irradiance(object_normals)
        else:
            # Fallback: flat frontal lighting
            irradiance = np.full(rgb.shape[:2], self._lighting.sun_intensity * 0.7 + self._lighting.ambient_intensity)

        # Apply diffuse shading
        irradiance_rgb = (
            irradiance[:, :, np.newaxis] * self._lighting.sun_color
            + self._lighting.ambient_intensity * self._lighting.ambient_color
        )
        rgb_lit = np.clip(rgb * irradiance_rgb, 0, 1)

        # Exposure matching: scale to match background luminance
        target_lum = self._lighting.sky_luminance
        current_lum = rgb_lit.mean()
        if current_lum > 1e-6:
            rgb_lit = np.clip(rgb_lit * (target_lum / current_lum) * 0.85, 0, 1)

        if object_rgba.shape[2] == 4:
            return np.concatenate([rgb_lit, alpha], axis=2)
        return rgb_lit

    def _compute_irradiance(self, normals: np.ndarray) -> np.ndarray:
        """Lambertian + ambient irradiance from surface normals."""
        n = normals / (np.linalg.norm(normals, axis=2, keepdims=True) + 1e-8)
        l = -self._lighting.sun_direction
        l = l / (np.linalg.norm(l) + 1e-8)
        diffuse = np.clip(np.sum(n * l, axis=2), 0, 1) * self._lighting.sun_intensity
        return diffuse + self._lighting.ambient_intensity
