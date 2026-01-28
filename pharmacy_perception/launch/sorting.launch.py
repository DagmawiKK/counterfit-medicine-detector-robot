from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    Launch the sorting actuator node with robot arm control parameters.
    
    The sorting robot arm picks up medicine bottles from the conveyor and places
    them into the appropriate bin based on verification status:
    - Status 0: Valid -> Green bin
    - Status 1: Expired -> Yellow bin  
    - Status 2: Counterfeit -> Red bin
    """
    return LaunchDescription(
        [
            Node(
                package="pharmacy_perception",
                executable="sorting_actuator",
                name="sorting_actuator",
                output="screen",
                parameters=[
                    {
                        "verification_topic": "/verification/result",
                        "conveyor_service": "/CONVEYORPOWER",
                        "robot_model_name": "sorting_robot_arm",
                        "resume_power": 50.0,
                        "cooldown_seconds": 5.0,
                        "motion_delay": 0.8,
                        "gripper_delay": 0.5,
                    }
                ],
            ),
        ]
    )
