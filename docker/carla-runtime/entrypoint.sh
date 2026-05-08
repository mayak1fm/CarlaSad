#!/bin/bash
set -e

HEADLESS=${HEADLESS:-true}
WORLD_PORT=${WORLD_PORT:-2000}
CARLA_NULLRHI=${CARLA_NULLRHI:-true}

# Force Mesa RADV — use first available radeon ICD (name differs: Ubuntu 18 uses x86_64 suffix, 24 does not)
_RADV_ICD=$(ls /usr/share/vulkan/icd.d/radeon_icd*.json 2>/dev/null | head -1)
if [ -n "$_RADV_ICD" ]; then
    export VK_ICD_FILENAMES=$_RADV_ICD
    echo "[CarlaSad] Vulkan ICD: $VK_ICD_FILENAMES"
fi

# Export carla Python egg to shared volume for other containers
if [ -d /carla-python-api ]; then
    find /home/carla/PythonAPI -name "carla-*.egg" -exec cp -n {} /carla-python-api/ \; 2>/dev/null || true
    echo "[CarlaSad] Exported carla Python API to /carla-python-api"
fi

ARGS="-nosound -carla-server -world-port=${WORLD_PORT}"

if [ "$HEADLESS" = "true" ]; then
    ARGS="$ARGS -RenderOffScreen"
    echo "[CarlaSad] Running headless (no display)"
else
    # Windowed mode: requires DISPLAY and X11 socket mounted
    if [ -z "$DISPLAY" ]; then
        echo "[CarlaSad] WARNING: HEADLESS=false but DISPLAY is not set — falling back to -RenderOffScreen"
        ARGS="$ARGS -RenderOffScreen"
    else
        echo "[CarlaSad] Running with display $DISPLAY"
        ARGS="$ARGS -windowed -ResX=${CARLA_RES_X:-1280} -ResY=${CARLA_RES_Y:-720}"
    fi
fi

# -nullrhi: run without GPU/rendering hardware — sensors return no data.
# Set CARLA_NULLRHI=false to enable GPU rendering (requires compatible GPU + VRAM).
if [ "$CARLA_NULLRHI" = "true" ]; then
    ARGS="$ARGS -nullrhi"
    echo "[CarlaSad] GPU rendering disabled (nullrhi mode)"
fi

echo "[CarlaSad] Starting: CarlaUE4.sh $ARGS"
exec /bin/bash /home/carla/CarlaUE4.sh $ARGS
