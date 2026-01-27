import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node

def generate_launch_description():
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    pkg_pharmacy_world = get_package_share_directory('pharmacy_counterfeit_detection_gazebo')

    # Gazebo launch
    # Add models path to env
    pkg_share_path = pkg_pharmacy_world
    models_path = os.path.join(pkg_share_path, 'models')
    
    if 'GZ_SIM_RESOURCE_PATH' in os.environ:
        os.environ['GZ_SIM_RESOURCE_PATH'] += ':' + models_path
    else:
        os.environ['GZ_SIM_RESOURCE_PATH'] = models_path

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': f'-r {os.path.join(pkg_pharmacy_world, "worlds", "pharmacy.sdf")}'}.items(),
    )

    # Bridge
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/camera/image_raw@sensor_msgs/msg/Image@gz.msgs.Image',
            '/model/moving_belt_A/cmd_vel@geometry_msgs/msg/Twist@ignition.msgs.Twist',
            '/model/moving_belt_B/cmd_vel@geometry_msgs/msg/Twist@ignition.msgs.Twist',
            '/model/moving_belt_A_return/cmd_vel@geometry_msgs/msg/Twist@ignition.msgs.Twist',
            '/model/moving_belt_B_return/cmd_vel@geometry_msgs/msg/Twist@ignition.msgs.Twist',
            '/world/pharmacy_world/set_pose@ros_gz_interfaces/srv/SetEntityPose'
        ],
        output='screen'
    )

    return LaunchDescription([
        gazebo,
        bridge,
    ])
