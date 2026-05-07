FROM carlasim/carla:0.9.15

# CarlaSad runtime image
# Adds custom maps and Python API extensions on top of base CARLA image

USER root

RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# CarlaSad Python extensions
COPY carla-fork/PythonAPI/carlasad /opt/carlasad
RUN pip3 install -e /opt/carlasad

# Custom startup script
COPY docker/carla-runtime/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2000 2001 2002

USER carla
ENTRYPOINT ["/entrypoint.sh"]
