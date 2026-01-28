from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="pharmacy_perception",
                executable="sorting_actuator",
                name="sorting_actuator",
                output="screen",
            ),
        ]
    )
