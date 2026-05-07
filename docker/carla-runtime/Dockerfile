FROM carlasim/carla:0.9.15

# Build context: project root
# CarlaSad runtime — base CARLA image + custom Python extensions

USER root

RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# CarlaSad Python extensions (Python 3.8 used by carlasim/carla:0.9.15)
COPY carla-fork/PythonAPI/carlasad /opt/carlasad
RUN pip3 install --no-cache-dir numpy pyyaml && \
    pip3 install --no-cache-dir -e /opt/carlasad

# Expose carla Python egg for other containers via shared volume at runtime
# (copy happens in entrypoint, not build, since egg path is inside the image)
COPY docker/carla-runtime/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2000 2001 2002

USER carla
ENTRYPOINT ["/entrypoint.sh"]
