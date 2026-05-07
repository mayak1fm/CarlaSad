#!/usr/bin/env bash
# setup_fork.sh — Apply CarlaSad patches to a cloned CARLA 0.9.15 source tree.
#
# Usage (run from inside the CARLA source root):
#   CARLASAD_DIR=/path/to/CarlaSad/carla-fork bash setup_fork.sh
#
# What it does:
#   1. Copies new CarlaSad C++ files into the CARLA source tree
#   2. Applies .patch files to existing CARLA files
#   3. Patches Carla.Build.cs to include the new sources

set -euo pipefail

CARLA_ROOT="${1:-$(pwd)}"
CARLASAD_DIR="${CARLASAD_DIR:-$(dirname "$(realpath "$0")")}"

echo "[setup_fork] CARLA root:    $CARLA_ROOT"
echo "[setup_fork] CarlaSad fork: $CARLASAD_DIR"

UE_PLUGIN="$CARLA_ROOT/Unreal/CarlaUE4/Plugins/Carla/Source/Carla"
LIB_CARLA="$CARLA_ROOT/LibCarla/source"

# ── 1. Verify CARLA source tree ───────────────────────────────────────────────
if [ ! -f "$CARLA_ROOT/Makefile" ]; then
    echo "[setup_fork] ERROR: $CARLA_ROOT does not look like a CARLA source root (no Makefile)"
    exit 1
fi

# ── 2. Copy new C++ files ─────────────────────────────────────────────────────

echo "[setup_fork] Copying Sensor/ThermalCamera..."
cp -v "$CARLASAD_DIR/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Sensor/ThermalCamera.h" \
      "$UE_PLUGIN/Sensor/ThermalCamera.h"
cp -v "$CARLASAD_DIR/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Sensor/ThermalCamera.cpp" \
      "$UE_PLUGIN/Sensor/ThermalCamera.cpp"

echo "[setup_fork] Copying Vehicle/CarlaSadTractorVehicle..."
cp -v "$CARLASAD_DIR/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Vehicle/CarlaSadTractorVehicle.h" \
      "$UE_PLUGIN/Vehicle/CarlaSadTractorVehicle.h"
cp -v "$CARLASAD_DIR/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Vehicle/CarlaSadTractorVehicle.cpp" \
      "$UE_PLUGIN/Vehicle/CarlaSadTractorVehicle.cpp"

echo "[setup_fork] Copying Tagger overrides..."
cp -v "$CARLASAD_DIR/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Tagger.h"   "$UE_PLUGIN/Tagger.h"
cp -v "$CARLASAD_DIR/Unreal/CarlaUE4/Plugins/Carla/Source/Carla/Tagger.cpp" "$UE_PLUGIN/Tagger.cpp"

echo "[setup_fork] Copying LibCarla ObjectLabel..."
cp -v "$CARLASAD_DIR/LibCarla/source/carla/rpc/ObjectLabel.h" \
      "$LIB_CARLA/carla/rpc/ObjectLabel.h"

# ── 3. Apply patches ──────────────────────────────────────────────────────────

echo "[setup_fork] Applying SensorFactory patch..."
if patch -p1 --dry-run -s < "$CARLASAD_DIR/patches/SensorFactory_ThermalCamera.patch" 2>/dev/null; then
    patch -p1 < "$CARLASAD_DIR/patches/SensorFactory_ThermalCamera.patch"
    echo "[setup_fork] SensorFactory patch applied"
else
    echo "[setup_fork] WARN: SensorFactory patch already applied or conflict — skipping"
fi

# ── 4. Patch Carla.Build.cs ───────────────────────────────────────────────────

BUILD_CS="$UE_PLUGIN/../Carla.Build.cs"
if [ -f "$BUILD_CS" ]; then
    # Add ThermalCamera.cpp and CarlaSadTractorVehicle.cpp to private sources
    # if not already present
    if ! grep -q "ThermalCamera" "$BUILD_CS"; then
        echo "[setup_fork] Patching Carla.Build.cs with CarlaSad sources..."
        sed -i 's|// CarlaSad sensor sources|// CarlaSad sensor sources|' "$BUILD_CS" || true
        # Append after last PrivateDependencyModuleNames closing brace
        python3 - <<'PYEOF'
import re, sys

with open("$BUILD_CS") as f:
    content = f.read()

carlasad_block = """
    // CarlaSad additions — do not remove
    PrivateIncludePaths.AddRange(new string[] {
        "Carla/Sensor",
        "Carla/Vehicle",
    });
"""

if "CarlaSad additions" not in content:
    # Insert after PublicIncludePaths block
    content = content.replace(
        "public Carla(ReadOnlyTargetRules Target) : base(Target)",
        "public Carla(ReadOnlyTargetRules Target) : base(Target)\n" + carlasad_block,
        1
    )
    with open("$BUILD_CS", "w") as f:
        f.write(content)
    print("[setup_fork] Carla.Build.cs patched")
else:
    print("[setup_fork] Carla.Build.cs already contains CarlaSad additions")
PYEOF
    fi
fi

# ── 5. Copy vehicle content ───────────────────────────────────────────────────

VEHICLE_CONTENT="$CARLA_ROOT/Unreal/CarlaUE4/Content/CarlaSad/Vehicles/Tractor"
mkdir -p "$VEHICLE_CONTENT"
cp -v "$CARLASAD_DIR/Unreal/CarlaUE4/Content/CarlaSad/Vehicles/Tractor/TractorVehicleData.json" \
      "$VEHICLE_CONTENT/TractorVehicleData.json"

echo ""
echo "[setup_fork] ✓ CarlaSad patches applied successfully."
echo ""
echo "Next steps:"
echo "  1. Open CarlaUE4 in Unreal Editor"
echo "  2. Create Blueprint BP_CarlaSadTractor (parent: CarlaSadTractorVehicle)"
echo "  3. Create material M_ThermalOverlay in Content/CarlaSad/Materials/"
echo "  4. make PythonAPI   (rebuild Python egg with new sensor)"
echo "  5. make CarlaUE4Editor ARGS=-game"
