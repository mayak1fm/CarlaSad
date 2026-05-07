from setuptools import setup, find_packages

setup(
    name="carlasad",
    version="0.1.0",
    description="CarlaSad Python extensions for CARLA tractor simulation",
    author="CarlaSad Team",
    author_email="mayak1fm@gmail.com",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "numpy>=1.24.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "carla": ["carla>=0.9.15"],
        "ros":   ["rclpy"],
        "dev":   ["pytest>=7.0", "pytest-asyncio"],
    },
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "carlasad-replay=carlasad.logging.replay:main",
        ],
    },
)
