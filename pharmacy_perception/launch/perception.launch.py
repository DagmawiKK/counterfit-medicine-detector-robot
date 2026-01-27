from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="pharmacy_perception",
                executable="barcode_node",
                name="barcode_node",
                output="screen",
                parameters=[{"image_topic": "/camera/scanner_camera/image_raw"}],
            ),
            Node(
                package="pharmacy_perception",
                executable="ocr_node",
                name="ocr_node",
                output="screen",
                parameters=[{"image_topic": "/camera/scanner_camera/image_raw"}],
            ),
        ]
    )
