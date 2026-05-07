from setuptools import find_packages, setup
from glob import glob
import os

package_name = "carlasad_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
        (f"share/{package_name}/config", glob("*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="CarlaSad Team",
    maintainer_email="mayak1fm@gmail.com",
    description="CarlaSad ROS2 bridge",
    license="MIT",
    entry_points={
        "console_scripts": [
            "bridge = carlasad_bridge.bridge_node:main",
            "process_publisher = carlasad_bridge.process_publisher:main",
        ],
    },
)
