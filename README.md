# Counterfeit Medicine Detector Robot

This repository contains the ROS 2 packages for a Counterfeit Medicine Detector Robot simulation. The project features a conveyor belt system controlled via Gazebo plugins and ROS 2 interfaces, designed to simulate a pharmacy or industrial medicine inspection environment.

## Project Structure

The project is organized into three main ROS 2 packages:

*   **`conveyorbelt_msgs`**: Defines the custom ROS 2 messages and services used to interact with the conveyor belt.
    *   `ConveyorBeltState.msg`: Monitors the belt's power and enabled status.
    *   `ConveyorBeltControl.srv`: Service to set the conveyor belt's power (0-100%).
*   **`conveyorbelt_gazebo`**: Contains the simulation environment and assets.
    *   `launch/`: Launch files to start the Gazebo simulation.
    *   `models/`: Gazebo models for the environment.
    *   `urdf/`: URDF descriptions for the scanner arm and other objects.
    *   `worlds/`: Gazebo world files.
*   **`ros2_conveyorbelt`**: Implements the logic and plugins for the conveyor belt.
    *   `src/ros2_conveyorbelt_plugin.cpp`: A Gazebo model plugin that interfaces with ROS 2 to control the belt's movement.
    *   `python/SpawnObject.py`: A utility script to spawn URDF/XACRO objects into the simulation.

## Prerequisites

*   ROS 2 (Humble or later recommended)
*   Gazebo Ignition or Classic (depending on the plugin configuration)
*   `gazebo_ros_pkgs`
*   `xacro`

## Installation & Build

1.  Clone the repository into your ROS 2 workspace:
    ```bash
    cd ~/ros2_ws/src
    git clone <repository_url>
    ```
2.  Install dependencies:
    ```bash
    cd ~/ros2_ws
    rosdep install --from-paths src --ignore-src -r -y
    ```
3.  Build the workspace:
    ```bash
    colcon build --symlink-install
    ```
4.  Source the workspace:
    ```bash
    source install/setup.bash
    ```

## Usage

### 1. Launch the Simulation
To start the conveyor belt simulation:
```bash
ros2 launch conveyorbelt_gazebo conveyorbelt.launch.py
```

### 2. Control the Conveyor Belt
Use the following service call to set the belt power (e.g., 50%):
```bash
ros2 service call /CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 50.0}"
```
To stop the belt:
```bash
ros2 service call /CONVEYORPOWER conveyorbelt_msgs/srv/ConveyorBeltControl "{power: 0.0}"
```

### 3. Monitor Belt State
You can check the current state of the conveyor belt by echoing the topic:
```bash
ros2 topic echo /CONVEYORSTATE
```

### 4. Spawn Objects
Use the provided Python script to spawn objects (like a box) onto the belt:
```bash
ros2 run ros2_conveyorbelt SpawnObject.py --package "conveyorbelt_gazebo" --urdf "box.urdf" --name "medicine_box" --x 0.0 --y -0.5 --z 0.76
```

Spawn the Phillips Milk of Magnesia model (Fuel) integrated into the workspace:
```bash
ros2 run ros2_conveyorbelt SpawnObject.py --package "conveyorbelt_gazebo" --sdf "model.sdf" --model "phillips_milk_of_magnesia" --name "phillips_milk" --x 0.0 --y -0.5 --z 0.76
```

## Verification Logic

Run the verification manager (barcode + OCR sync, inventory check):
```bash
ros2 run pharmacy_perception verification_manager
```

Results are published to `/verification/result` with status codes:
- `0` = Valid
- `1` = Expired
- `2` = Counterfeit/Mismatch

## Sorting Robot Arm System

The system features a 4-DOF industrial robotic arm with a parallel gripper that picks up medicine bottles from the conveyor belt and places them into designated sorting bins based on verification results.

### Sorting Bins

Three color-coded bins are positioned next to the conveyor:

| Status | Classification | Bin Color | Description |
|--------|---------------|-----------|-------------|
| 0 | Valid | **Green** | Approved medicines ready for distribution |
| 1 | Expired | **Yellow** | Expired medicines requiring proper disposal |
| 2 | Counterfeit | **Red** | Suspicious/counterfeit medicines for quarantine |

### Robot Arm Specifications

- **Type**: 4-DOF articulated arm with parallel jaw gripper
- **Joints**:
  - Joint 1: Base rotation (360°)
  - Joint 2: Shoulder pitch (±90°)
  - Joint 3: Elbow pitch (±135°)
  - Joint 4: Wrist rotation (360°)
  - Gripper: Parallel jaw with rubber grip pads

### Running the Sorting System

Launch the sorting actuator node:
```bash
ros2 launch pharmacy_perception sorting.launch.py
```

The robot arm automatically:
1. Stops the conveyor belt when a verification result is received
2. Moves to the pickup position above the bottle
3. Grasps the bottle with the gripper
4. Moves to the appropriate bin based on classification
5. Releases the bottle into the bin
6. Returns to home position
7. Resumes the conveyor belt

### Configuration Parameters

The sorting actuator accepts the following parameters:
- `robot_model_name`: Name of the robot arm model (default: `sorting_robot_arm`)
- `resume_power`: Conveyor belt power after sorting (default: `50.0`)
- `cooldown_seconds`: Minimum time between sorting operations (default: `5.0`)
- `motion_delay`: Delay between arm movements in seconds (default: `0.8`)
- `gripper_delay`: Delay for gripper open/close operations (default: `0.5`)

## References and Acknowledgments

The conveyor belt implementation in this project is based on the work by the **IFRA (Intelligent Flexible Robotics and Assembly) Group** at **Cranfield University**. We would like to acknowledge the original authors:

*   **Mikel Bueno Viso** (Mikel.Bueno-Viso@cranfield.ac.uk)
*   **Dr. Seemal Asif** (s.asif@cranfield.ac.uk)
*   **Prof. Phil Webb** (p.f.webb@cranfield.ac.uk)

For more information on the original plugin, visit: [IFRA_ConveyorBelt](https://github.com/IFRA-Cranfield/IFRA_ConveyorBelt).
