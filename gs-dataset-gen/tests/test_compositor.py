"""Unit tests for GS dataset compositor."""
import sys
import numpy as np
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from compositor.lighting_adapter import LightingAdapter, SceneLighting
from compositor.shadow_compositor import ProxyMeshShadow


class TestSceneLighting:
    def test_from_weather_preset_clear_noon(self):
        l = SceneLighting.from_weather_preset("ClearNoon")
        assert l.sun_intensity > 0.5
        assert l.ambient_intensity > 0.0
        assert len(l.sun_direction) == 3
        assert abs(np.linalg.norm(l.sun_direction) - 1.0) < 1e-3

    def test_from_weather_preset_cloudy(self):
        l = SceneLighting.from_weather_preset("CloudyNoon")
        clear = SceneLighting.from_weather_preset("ClearNoon")
        assert l.sun_intensity < clear.sun_intensity
        assert l.ambient_intensity > clear.ambient_intensity

    def test_unknown_preset_falls_back_to_clear_noon(self):
        l = SceneLighting.from_weather_preset("NonExistent")
        default = SceneLighting.from_weather_preset("ClearNoon")
        assert l.sun_intensity == default.sun_intensity

    def test_estimate_from_image_returns_valid_lighting(self):
        bg = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
        l = SceneLighting.estimate_from_image(bg)
        assert 0.0 <= l.sun_intensity <= 1.0
        assert 0.0 <= l.ambient_intensity <= 1.0
        assert abs(np.linalg.norm(l.sun_direction) - 1.0) < 0.1

    def test_estimate_from_none_returns_default(self):
        l = SceneLighting.estimate_from_image(None)
        default = SceneLighting.from_weather_preset("ClearNoon")
        assert l.sun_intensity == default.sun_intensity


class TestLightingAdapter:
    def setup_method(self):
        self.lighting = SceneLighting.from_weather_preset("ClearNoon")
        self.adapter = LightingAdapter(self.lighting)

    def test_relight_returns_same_shape(self):
        obj = np.random.rand(64, 64, 4).astype(np.float32)
        result = self.adapter.relight_object(obj)
        assert result.shape == obj.shape

    def test_relight_preserves_alpha(self):
        obj = np.ones((32, 32, 4), dtype=np.float32) * 0.5
        obj[:, :, 3] = 0.8
        result = self.adapter.relight_object(obj)
        np.testing.assert_allclose(result[:, :, 3], 0.8, atol=1e-5)

    def test_relight_none_returns_none(self):
        result = self.adapter.relight_object(None)
        assert result is None

    def test_relight_rgb_values_in_range(self):
        obj = np.ones((64, 64, 4), dtype=np.float32) * 0.7
        result = self.adapter.relight_object(obj)
        assert result[:, :, :3].min() >= 0.0
        assert result[:, :, :3].max() <= 1.0

    def test_night_vs_day_brightness(self):
        day_lighting = SceneLighting.from_weather_preset("ClearNoon")
        day_adapter = LightingAdapter(day_lighting)
        obj = np.ones((32, 32, 3), dtype=np.float32) * 0.5
        day_result = day_adapter.relight_object(obj)
        # Day should produce some non-zero output
        assert day_result.mean() > 0.01


class TestShadowCompositor:
    def setup_method(self):
        self.lighting = SceneLighting.from_weather_preset("ClearNoon")
        self.shadow = ProxyMeshShadow(self.lighting)

    def test_shadow_mask_shape(self):
        proxy_bbox = [[0, 0, 0.875], [0.5, 0.4, 1.75], [0, 0, 0]]
        transform = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}
        mask = self.shadow.compute_shadow_mask((480, 640), proxy_bbox, transform)
        assert mask.shape == (480, 640)

    def test_shadow_mask_values_in_range(self):
        proxy_bbox = [[0, 0, 0.875], [0.5, 0.4, 1.75], [0, 0, 0]]
        transform = {"x": 5.0, "y": 5.0, "z": 0.0, "yaw": 30.0}
        mask = self.shadow.compute_shadow_mask((480, 640), proxy_bbox, transform)
        assert mask.min() >= 0.0
        assert mask.max() <= 1.0

    def test_no_proxy_bbox_returns_zeros(self):
        mask = self.shadow.compute_shadow_mask((480, 640), None, {"x": 0, "y": 0, "z": 0, "yaw": 0})
        assert mask.sum() == 0.0

    def test_apply_darkens_background(self):
        bg = np.ones((100, 100, 3), dtype=np.float32) * 0.8
        mask = np.ones((100, 100), dtype=np.float32) * 0.5
        result = self.shadow.apply_to_image(bg, mask)
        assert result.mean() < bg.mean()

    def test_apply_zero_mask_unchanged(self):
        bg = np.ones((100, 100, 3), dtype=np.float32) * 0.7
        mask = np.zeros((100, 100), dtype=np.float32)
        result = self.shadow.apply_to_image(bg, mask)
        np.testing.assert_allclose(result[:, :, :3], bg * 0.7 + self.lighting.ambient_color * 0.0, atol=0.01)

    def test_cloudy_shadow_softer(self):
        cloudy = SceneLighting.from_weather_preset("CloudyNoon")
        clear  = SceneLighting.from_weather_preset("ClearNoon")
        cloudy_shadow = ProxyMeshShadow(cloudy)
        clear_shadow  = ProxyMeshShadow(clear)
        assert cloudy_shadow._compute_softness() > clear_shadow._compute_softness()
