#!/bin/bash
set -e

HEADLESS=${HEADLESS:-true}
WORLD_PORT=${WORLD_PORT:-2000}
MAP=${MAP:-""}

ARGS="-nosound -carla-server -world-port=${WORLD_PORT}"

if [ "$HEADLESS" = "true" ]; then
    ARGS="$ARGS -RenderOffScreen"
fi

echo "[CarlaSad] Starting CARLA: CarlaUE4.sh $ARGS"
exec /bin/bash /home/carla/CarlaUE4/CarlaUE4.sh $ARGS
