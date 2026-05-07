FROM ros:humble

# CarlaSad ROS2 bridge dev image

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    ros-humble-sensor-msgs \
    ros-humble-nav-msgs \
    ros-humble-geometry-msgs \
    ros-humble-tf2-ros \
    ros-humble-rosbag2 \
    ros-humble-rosbag2-storage-default-plugins \
    libboost-python-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# CARLA Python API wheel (built from fork)
ARG CARLA_VERSION=0.9.15
RUN pip3 install carla==${CARLA_VERSION} || \
    echo "CARLA wheel not on PyPI for this version - mount from build"

# CarlaSad custom messages
WORKDIR /workspace
COPY ros-bridge/ ros-bridge/

RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
    cd ros-bridge && \
    colcon build --symlink-install && \
    echo 'source /workspace/ros-bridge/install/setup.bash' >> ~/.bashrc"

COPY docker/ros2-bridge-dev/bridge.launch.py /workspace/

EXPOSE 0
