FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04

# CarlaSad world reconstruction pipeline
# SfM → GS → mesh extraction → CARLA import

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    cmake \
    libboost-all-dev \
    libeigen3-dev \
    libopencv-dev \
    libsuitesparse-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    colmap \
    && rm -rf /var/lib/apt/lists/*

RUN pip install \
    nerfstudio \
    open3d \
    trimesh \
    numpy \
    scipy \
    pillow \
    pyyaml

WORKDIR /workspace/reconstruction

COPY tools/reconstruction/ .
