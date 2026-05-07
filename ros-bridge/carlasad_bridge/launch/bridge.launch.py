"""CarlaSad bridge launch file."""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    carla_host    = LaunchConfiguration("carla_host",    default=os.environ.get("CARLA_HOST", "localhost"))
    carla_port    = LaunchConfiguration("carla_port",    default=os.environ.get("CARLA_PORT", "2000"))
    sync_mode     = LaunchConfiguration("sync_mode",     default="false")
    fixed_delta   = LaunchConfiguration("fixed_delta",   default="0.05")
    log_level     = LaunchConfiguration("log_level",     default="info")
    ros_domain_id = LaunchConfiguration("ros_domain_id", default=os.environ.get("ROS_DOMAIN_ID", "0"))

    bridge_node = Node(
        package="carlasad_bridge",
        executable="bridge",
        name="carlasad_bridge",
        output="screen",
        parameters=[{
            "carla_host":   carla_host,
            "carla_port":   carla_port,
            "sync_mode":    sync_mode,
            "fixed_delta":  fixed_delta,
        }],
        arguments=["--ros-args", "--log-level", log_level],
        remappings=[],
    )

    process_pub_node = Node(
        package="carlasad_bridge",
        executable="process_publisher",
        name="carlasad_process_publisher",
        output="screen",
        parameters=[{
            "carla_host": carla_host,
            "carla_port": carla_port,
        }],
    )

    return LaunchDescription([
        DeclareLaunchArgument("carla_host",    default_value="localhost",   description="CARLA server hostname"),
        DeclareLaunchArgument("carla_port",    default_value="2000",        description="CARLA server port"),
        DeclareLaunchArgument("sync_mode",     default_value="false",       description="Enable synchronous mode"),
        DeclareLaunchArgument("fixed_delta",   default_value="0.05",        description="Fixed timestep in sync mode"),
        DeclareLaunchArgument("log_level",     default_value="info",        description="ROS2 log level"),
        LogInfo(msg=["Starting CarlaSad bridge → CARLA at ", carla_host, ":", carla_port]),
        bridge_node,
        process_pub_node,
    ])
