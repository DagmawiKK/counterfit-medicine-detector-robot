import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import LifecycleNode, Node
from launch_ros.events.lifecycle import ChangeState
from launch.events import matches_action
from lifecycle_msgs.msg import Transition
from launch.event_handlers import OnExecutionComplete, OnProcessStart
from launch_ros.event_handlers import OnStateTransition

def generate_launch_description():
    # Paths
    pkg_pharmacy_gazebo = get_package_share_directory('pharmacy_counterfeit_detection_gazebo')
    
    # 1. Start Gazebo with the pharmacy world
    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_pharmacy_gazebo, 'launch', 'sim.launch.py')
        )
    )

    # 2. Spawner node (moves belt + spawns bottles with random labels)
    bottle_spawner = Node(
        package='pharmacy_verification',
        executable='bottle_spawner',
        output='screen'
    )

    # 3. Nodes Definition
    # We define all nodes (bridge + workers) in a list to apply uniform behavior
    lifecycle_node_names = [
        'sim_bridge', 
        'vision_manager', 
        'barcode_node', 
        'ocr_node', 
        'db_interface', 
        'conveyor_ctrl', 
        'robot_controller'
    ]
    
    lifecycle_nodes = []
    
    # Create the node actions
    for name in lifecycle_node_names:
        lifecycle_nodes.append(
            LifecycleNode(
                package='pharmacy_verification',
                executable=name,
                name=name,
                namespace='',
                output='screen'
            )
        )

    # 4. Lifecycle Management
    # Logic: For each node:
    # 1. When Process Starts -> Emit CONFIGURE
    # 2. When State=Inactive (Configured) -> Emit ACTIVATE
    
    events = []
    
    for node in lifecycle_nodes:
        # OnProcessStart -> Configure
        events.append(
            RegisterEventHandler(
                OnProcessStart(
                    target_action=node,
                    on_start=[
                        LogInfo(msg=f"Starting {node.name}, emitting CONFIGURE"),
                        EmitEvent(
                            event=ChangeState(
                                lifecycle_node_matcher=matches_action(node),
                                transition_id=Transition.TRANSITION_CONFIGURE,
                            )
                        )
                    ]
                )
            )
        )
        
        # OnStateTransition (Unconfigured -> Inactive) -> Activate
        events.append(
            RegisterEventHandler(
                OnStateTransition(
                    target_lifecycle_node=node,
                    start_state='unconfigured',
                    goal_state='inactive',
                    entities=[
                        LogInfo(msg=f"{node.name} is Confgured (Inactive). Emitting ACTIVATE"),
                        EmitEvent(
                            event=ChangeState(
                                lifecycle_node_matcher=matches_action(node),
                                transition_id=Transition.TRANSITION_ACTIVATE,
                            )
                        )
                    ]
                )
            )
        )

        
    # Create the launch description
    ld = LaunchDescription()

    # Add actions
    ld.add_action(gazebo_sim)
    ld.add_action(bottle_spawner)
    
    for node in lifecycle_nodes:
        ld.add_action(node)
        
    for event in events:
        ld.add_action(event)

    return ld
