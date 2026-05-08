# Build context: project root
# Stage 1: pull CARLA files from the official image (Ubuntu 18.04)
FROM carlasim/carla:0.9.15 AS carla-source

# Stage 2: Ubuntu 24.04 base — Mesa 24.x supports AMD Phoenix (GC 11) APU
# CARLA binary requires only glibc >= 2.17, so it runs fine on 24.04 (glibc 2.39).
# NOTE: carlasad Python client libs are NOT installed here; they live in
#       ros-bridge / api-backend / tools containers via carla-python-api volume.
FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Healthcheck
    netcat-openbsd \
    # Vulkan: loader + Mesa RADV (supports AMD Phoenix APU, GC 11.0)
    libvulkan1 \
    mesa-vulkan-drivers \
    # X11 / display libraries for windowed mode
    libx11-6 \
    libxrandr2 \
    libxinerama1 \
    libxcursor1 \
    libxi6 \
    libxss1 \
    libxext6 \
    # OpenGL (UE4 fallback path)
    libgl1-mesa-dri \
    libgles2 \
    libegl1 \
    # UE4 runtime deps
    libstdc++6 \
    libgcc-s1 \
    libdbus-1-3 \
    libfontconfig1 \
    # find utility used in entrypoint for Python egg export
    findutils \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 ships with 'ubuntu' user at UID 1000 — rename it to 'carla'
RUN usermod -l carla ubuntu && groupmod -n carla ubuntu && usermod -d /home/carla -m carla

# Copy CARLA installation from upstream image (overwrites renamed home dir)
COPY --from=carla-source /home/carla /home/carla
RUN chown -R carla:carla /home/carla

# Remove NVIDIA Vulkan ICD — not present in Ubuntu 24.04 base, but guard anyway
RUN rm -f /etc/vulkan/icd.d/nvidia_icd.json

COPY docker/carla-runtime/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2000 2001 2002

USER carla
ENTRYPOINT ["/entrypoint.sh"]
