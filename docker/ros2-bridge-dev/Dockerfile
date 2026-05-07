FROM ros:humble

# Build context: project root

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    ros-humble-sensor-msgs \
    ros-humble-nav-msgs \
    ros-humble-geometry-msgs \
    ros-humble-tf2-ros \
    ros-humble-tf2-geometry-msgs \
    ros-humble-rosbag2 \
    ros-humble-rosbag2-storage-default-plugins \
    ros-humble-radar-msgs \
    libboost-python-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# CarlaSad Python layers (no hard carla dep — egg mounted at runtime via carla-python-api volume)
COPY carla-fork/PythonAPI/carlasad /opt/carlasad
RUN pip3 install --no-cache-dir numpy pyyaml && \
    pip3 install --no-cache-dir -e /opt/carlasad

# ROS2 workspace — build carlasad_msgs + carlasad_bridge
WORKDIR /workspace/ros-bridge
COPY ros-bridge/ .

RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    colcon build --symlink-install && \
    echo 'source /workspace/ros-bridge/install/setup.bash' >> ~/.bashrc"

EXPOSE 0
