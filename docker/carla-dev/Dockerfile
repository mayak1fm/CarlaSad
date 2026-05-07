FROM ubuntu:22.04

# Build context: project root
# CarlaSad CARLA dev — environment for building CARLA fork from source.
#
# Prerequisites (provided via volume mounts, NOT baked into image):
#   /home/ue4/UnrealEngine  — Unreal Engine 5 source (Epic Games license required)
#   /workspace/carla        — carla-fork git submodule
#
# Build CARLA:
#   docker compose --profile carla-build run --rm carla-dev bash
#   > make setup
#   > make CarlaUE4Editor ARGS=-game
#
# Build Python API (exports egg to carla-python-api volume):
#   > make PythonAPI
#   > cp PythonAPI/carla/dist/*.egg /carla-python-api/

ENV DEBIAN_FRONTEND=noninteractive
ENV UE4_ROOT=/home/ue4/UnrealEngine

RUN apt-get update && apt-get install -y \
    build-essential \
    clang-12 \
    lld-12 \
    g++-8 \
    cmake \
    ninja-build \
    libvulkan1 \
    python3.8 \
    python3.8-dev \
    python3-pip \
    python3-distutils \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    tzdata \
    sed \
    curl \
    wget \
    unzip \
    autoconf \
    libtool \
    rsync \
    libxml2-dev \
    libxslt1-dev \
    git \
    aria2 \
    xdg-user-dirs \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-12 100 && \
    update-alternatives --install /usr/bin/clang   clang   /usr/bin/clang-12   100

RUN pip3 install --no-cache-dir setuptools wheel auditwheel

# carla-python-api output volume (populated after `make PythonAPI`)
VOLUME /carla-python-api

WORKDIR /workspace/carla
CMD ["bash"]
