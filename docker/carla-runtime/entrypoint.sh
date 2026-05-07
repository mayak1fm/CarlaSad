#!/bin/bash
set -e

HEADLESS=${HEADLESS:-true}
WORLD_PORT=${WORLD_PORT:-2000}

# Copy carla Python egg to shared volume so bridge/api/tools containers can use it
if [ -d /carla-python-api ]; then
    find /home/carla/PythonAPI -name "carla-*.egg" -exec cp -n {} /carla-python-api/ \; 2>/dev/null || true
    echo "[CarlaSad] Exported carla Python API to /carla-python-api"
fi

ARGS="-nosound -carla-server -world-port=${WORLD_PORT}"
if [ "$HEADLESS" = "true" ]; then
    ARGS="$ARGS -RenderOffScreen"
fi

echo "[CarlaSad] Starting CARLA: CarlaUE4.sh $ARGS"
exec /bin/bash /home/carla/CarlaUE4/CarlaUE4.sh $ARGS
