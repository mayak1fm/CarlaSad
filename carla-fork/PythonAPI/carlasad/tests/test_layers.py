"""Unit tests for terrain and process layers."""
import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from carlasad.layers.terrain_layer import TerrainLayer, TERRAIN_LABELS, TERRAIN_RISK
from carlasad.layers.process_layer import ProcessLayer, WORKED, UNWORKED, WORKED_EDGE
from carlasad.layers.field_boundary_layer import FieldBoundaryLayer


# ── TerrainLayer ───────────────────────────────────────────────────────────

class TestTerrainLayer:
    def test_default_label_is_normal_field(self):
        layer = TerrainLayer()
        assert layer.get_label(0.0, 0.0) == TERRAIN_LABELS["normal_field"]

    def test_default_risk_is_zero(self):
        layer = TerrainLayer()
        assert layer.get_risk(0.0, 0.0) == 0.0

    def test_is_drivable_normal(self):
        layer = TerrainLayer()
        assert layer.is_drivable(0.0, 0.0) is True

    def test_terrain_label_ids_are_correct(self):
        assert TERRAIN_LABELS["normal_field"]   == 100
        assert TERRAIN_LABELS["wet_field"]      == 101
        assert TERRAIN_LABELS["swamp"]          == 102
        assert TERRAIN_LABELS["mochak"]         == 103
        assert TERRAIN_LABELS["rough_terrain"]  == 104
        assert TERRAIN_LABELS["field_boundary"] == 105
        assert TERRAIN_LABELS["worked_area"]    == 110
        assert TERRAIN_LABELS["worked_edge"]    == 112

    def test_impassable_terrain_high_risk(self):
        assert TERRAIN_RISK[102] >= 0.8   # swamp
        assert TERRAIN_RISK[103] >= 0.7   # mochak
        assert TERRAIN_RISK[105] >= 1.0   # field_boundary
        assert TERRAIN_RISK[114] >= 1.0   # restricted_zone

    def test_drivable_terrain_low_risk(self):
        assert TERRAIN_RISK[100] == 0.0   # normal_field
        assert TERRAIN_RISK[110] == 0.0   # worked_area
        assert TERRAIN_RISK[106] == 0.0   # drivable_path

    def test_to_occupancy_grid_empty(self):
        layer = TerrainLayer()
        result = layer.to_occupancy_grid()
        assert result == {}  # no grid loaded yet

    def test_height_default_zero(self):
        layer = TerrainLayer()
        assert layer.get_height(10.0, 10.0) == 0.0


# ── ProcessLayer ───────────────────────────────────────────────────────────

class TestProcessLayer:
    def setup_method(self):
        self.layer = ProcessLayer(resolution=1.0, width=100.0, height=100.0)

    def test_initial_worked_fraction_is_zero(self):
        assert self.layer.get_worked_fraction() == 0.0

    def test_mark_worked_increases_fraction(self):
        self.layer.mark_worked(0.0, 0.0, radius=5.0)
        assert self.layer.get_worked_fraction() > 0.0

    def test_multiple_marks_increase_fraction(self):
        for x in range(-20, 20, 5):
            self.layer.mark_worked(float(x), 0.0, radius=2.5)
        frac = self.layer.get_worked_fraction()
        assert frac > 0.05

    def test_worked_fraction_bounded(self):
        for x in range(-40, 40, 2):
            for y in range(-40, 40, 2):
                self.layer.mark_worked(float(x), float(y), radius=3.0)
        assert 0.0 <= self.layer.get_worked_fraction() <= 1.0

    def test_worked_edge_populated_after_mark(self):
        self.layer.mark_worked(10.0, 10.0)
        assert len(self.layer._worked_edge) > 0
        assert self.layer._worked_edge[-1].x == pytest.approx(10.0)

    def test_field_boundary_set(self):
        polygon = [(-40, -40), (40, -40), (40, 40), (-40, 40)]
        self.layer.set_field_boundary(polygon)
        boundary_msg = self.layer.to_field_boundary_msg()
        assert len(boundary_msg["polygon"]) == 4

    def test_to_worked_occupancy_grid_structure(self):
        self.layer.mark_worked(0.0, 0.0)
        grid = self.layer.to_worked_occupancy_grid()
        assert "resolution" in grid
        assert "width" in grid
        assert "height" in grid
        assert "data" in grid
        assert grid["resolution"] == pytest.approx(1.0)

    def test_reset_clears_state(self):
        self.layer.mark_worked(5.0, 5.0)
        self.layer.reset()
        assert self.layer.get_worked_fraction() == 0.0
        assert len(self.layer._worked_edge) == 0

    def test_worked_edge_capped_at_1000(self):
        for i in range(1500):
            self.layer.mark_worked(float(i % 50), float(i % 50))
        assert len(self.layer._worked_edge) <= 1000


# ── FieldBoundaryLayer ─────────────────────────────────────────────────────

class TestFieldBoundaryLayer:
    def setup_method(self):
        self.layer = FieldBoundaryLayer()
        self.layer.set_boundary([(-50, -50), (50, -50), (50, 50), (-50, 50)])

    def test_point_inside_boundary(self):
        assert self.layer.is_inside_boundary(0.0, 0.0) is True
        assert self.layer.is_inside_boundary(10.0, 20.0) is True

    def test_point_outside_boundary(self):
        assert self.layer.is_inside_boundary(60.0, 0.0) is False
        assert self.layer.is_inside_boundary(0.0, -60.0) is False

    def test_near_boundary_detection(self):
        assert self.layer.is_near_boundary(49.0, 0.0, threshold=2.0) is True
        assert self.layer.is_near_boundary(0.0, 0.0, threshold=2.0) is False

    def test_no_go_zone(self):
        self.layer.add_no_go_zone([(10, 10), (20, 10), (20, 20), (10, 20)])
        assert self.layer.is_in_no_go_zone(15.0, 15.0) is True
        assert self.layer.is_in_no_go_zone(5.0, 5.0) is False

    def test_get_boundary_polygon(self):
        poly = self.layer.get_boundary_polygon()
        assert len(poly) == 4

    def test_empty_boundary_no_crash(self):
        layer = FieldBoundaryLayer()
        assert layer.is_inside_boundary(0.0, 0.0) is False
