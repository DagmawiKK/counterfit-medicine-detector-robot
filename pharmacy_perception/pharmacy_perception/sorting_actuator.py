"""
Sorting Actuator Node - Controls a 4-DOF robotic arm to pick and place medicine bottles.
Uses JointTrajectory messages via gazebo_ros_joint_pose_trajectory plugin.
"""

import time
import math
from typing import List

import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from conveyorbelt_msgs.msg import VerificationResult
from conveyorbelt_msgs.srv import ConveyorBeltControl
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration as DurationMsg
from std_msgs.msg import Header


class RobotArmController:
    """Handles inverse kinematics and trajectory generation for the 4-DOF sorting robot arm."""
    
    # Robot arm dimensions (meters)
    BASE_HEIGHT = 0.175  # Height from robot base_link to shoulder joint
    UPPER_ARM_LENGTH = 0.24
    FOREARM_LENGTH = 0.20
    WRIST_LENGTH = 0.115
    
    # Robot base is at World (0.5, -0.35, 0.75), rotated 90° around Z
    # Robot +X axis = World +Y axis
    # Robot +Y axis = World -X axis
    # Robot +Z axis = World +Z axis
    
    # Bin positions in ROBOT LOCAL frame (x=forward, y=left, z=up from base)
    # Bins are at World (0.85, 0.30/0.0/-0.30, 0.75+bin_height)
    # In robot frame: x = world_y - robot_y = 0.30 - (-0.35) = 0.65, etc.
    #                 y = -(world_x - robot_x) = -(0.85 - 0.5) = -0.35
    #                 z = bin height above robot base ≈ 0.10
    BIN_POSITIONS = {
        0: (0.65, -0.35, 0.10),   # Valid bin (green) - World Y=0.30
        1: (0.35, -0.35, 0.10),   # Expired bin (yellow) - World Y=0.0
        2: (0.05, -0.35, 0.10),   # Counterfeit bin (red) - World Y=-0.30
    }
    
    # Pickup position in ROBOT LOCAL frame
    # Conveyor belt center is at World Y=0.0, X varies
    # At robot X position (0.5), belt is at World (0.5, 0.0, ~0.75)
    # In robot frame: x = world_y - robot_y = 0.0 - (-0.35) = 0.35
    #                 y = -(world_x - robot_x) = -(0.5 - 0.5) = 0.0
    #                 z = belt_surface - robot_base_z = 0.75 - 0.75 = 0.0, plus bottle height
    PICKUP_POSITION = (0.35, 0.0, -0.02)  # Reach down to belt level (slightly below robot base)
    
    # Home position joint angles
    HOME_JOINTS = [0.0, 0.3, -0.3, 0.0]  # Slight bend to hold arm up
    
    # Gripper states
    GRIPPER_OPEN = 0.02
    GRIPPER_CLOSED = 0.0
    
    @classmethod
    def get_pickup_joints(cls) -> List[float]:
        x, y, z = cls.PICKUP_POSITION
        return cls._compute_ik(x, y, z)
    
    @classmethod
    def get_place_joints(cls, status: int) -> List[float]:
        x, y, z = cls.BIN_POSITIONS.get(status, cls.BIN_POSITIONS[2])
        return cls._compute_ik(x, y, z)
    
    @classmethod
    def _compute_ik(cls, x: float, y: float, z: float) -> List[float]:
        """
        Compute inverse kinematics for reaching position (x, y, z) in robot local frame.
        x = forward, y = left, z = up from base_link
        """
        # Joint 1: Base rotation to face target
        joint_1 = math.atan2(y, x)
        
        # Horizontal distance to target
        r = math.sqrt(x*x + y*y)
        
        # Vertical distance from shoulder to target wrist position
        # Shoulder is at BASE_HEIGHT above base_link
        # We want wrist to be at z, so wrist_z_from_shoulder = z - BASE_HEIGHT
        z_eff = z - cls.BASE_HEIGHT
        
        # Distance from shoulder to wrist
        d = math.sqrt(r*r + z_eff*z_eff)
        
        # Clamp to reachable workspace
        max_reach = cls.UPPER_ARM_LENGTH + cls.FOREARM_LENGTH
        min_reach = abs(cls.UPPER_ARM_LENGTH - cls.FOREARM_LENGTH)
        d = max(min_reach + 0.01, min(d, max_reach - 0.01))
        
        # Elbow angle using law of cosines
        cos_elbow = (cls.UPPER_ARM_LENGTH**2 + cls.FOREARM_LENGTH**2 - d**2) / \
                    (2 * cls.UPPER_ARM_LENGTH * cls.FOREARM_LENGTH)
        cos_elbow = max(-1.0, min(1.0, cos_elbow))
        elbow_angle = math.acos(cos_elbow)  # Angle at elbow joint
        
        # Shoulder angle
        # alpha = angle from horizontal to the line connecting shoulder to wrist
        alpha = math.atan2(z_eff, r)
        
        # beta = angle between upper arm and the line to wrist
        cos_beta = (cls.UPPER_ARM_LENGTH**2 + d**2 - cls.FOREARM_LENGTH**2) / \
                   (2 * cls.UPPER_ARM_LENGTH * d)
        cos_beta = max(-1.0, min(1.0, cos_beta))
        beta = math.acos(cos_beta)
        
        # Shoulder pitch: to reach down, we need negative angle
        # joint_2 positive = arm goes up, negative = arm goes down
        joint_2 = alpha + beta
        
        # Elbow: negative to bend "inward" 
        joint_3 = -(math.pi - elbow_angle)
        
        # Wrist rotation
        joint_4 = 0.0
        
        return [joint_1, joint_2, joint_3, joint_4]
    
    @classmethod
    def get_approach_joints(cls, target_joints: List[float]) -> List[float]:
        """Get joint angles for approach position (slightly above target)."""
        approach = target_joints.copy()
        approach[1] += 0.3   # Raise shoulder more
        approach[2] += 0.15  # Adjust elbow
        return approach


class SortingActuator(Node):
    def __init__(self) -> None:
        super().__init__("sorting_actuator")
        
        self.declare_parameter("verification_topic", "/verification/result")
        self.declare_parameter("conveyor_service", "/CONVEYORPOWER")
        self.declare_parameter("robot_model_name", "sorting_robot_arm")
        self.declare_parameter("resume_power", 50.0)
        self.declare_parameter("cooldown_seconds", 5.0)
        self.declare_parameter("motion_delay", 1.0)
        self.declare_parameter("gripper_delay", 0.5)
        self.declare_parameter("travel_time", 5.5)  # Time for bottle to travel from camera to robot
        
        self._verification_topic = self.get_parameter("verification_topic").get_parameter_value().string_value
        self._conveyor_service = self.get_parameter("conveyor_service").get_parameter_value().string_value
        self._robot_model_name = self.get_parameter("robot_model_name").get_parameter_value().string_value
        self._resume_power = self.get_parameter("resume_power").get_parameter_value().double_value
        self._cooldown_seconds = self.get_parameter("cooldown_seconds").get_parameter_value().double_value
        self._motion_delay = self.get_parameter("motion_delay").get_parameter_value().double_value
        self._gripper_delay = self.get_parameter("gripper_delay").get_parameter_value().double_value
        self._travel_time = self.get_parameter("travel_time").get_parameter_value().double_value
        
        self._busy = False
        self._last_action_time = 0.0
        self._arm_joints = ["joint_1", "joint_2", "joint_3", "joint_4"]
        self._gripper_joints = ["finger_left_joint", "finger_right_joint"]
        
        # Subscribe to verification results
        self._verification_sub = self.create_subscription(
            VerificationResult, self._verification_topic, self._on_verification, 10
        )
        
        # Conveyor client
        self._belt_client = self.create_client(ConveyorBeltControl, self._conveyor_service)
        
        # Trajectory publisher - NOTE: Topic MUST match the plugin remapping in model.sdf
        self._trajectory_pub = self.create_publisher(
            JointTrajectory, 
            f"/{self._robot_model_name}/set_joint_trajectory", 
            10
        )
        
        self.get_logger().info(f"Sorting actuator started - controlling {self._robot_model_name}")
        self.get_logger().info(f"Publishing to /{self._robot_model_name}/set_joint_trajectory")
        
        time.sleep(1.0)
        self.get_logger().info("Moving to home position...")
        self._move_to_home()
    
    def _on_verification(self, msg: VerificationResult) -> None:
        now = time.time()
        if now - self._last_action_time < self._cooldown_seconds or self._busy:
            return
        
        self._busy = True
        self._last_action_time = now
        self.get_logger().info(f"Processing bottle: status={msg.status}")
        
        try:
            self._execute_sorting_sequence(msg.status)
        except Exception as e:
            self.get_logger().error(f"Sorting sequence failed: {e}")
        finally:
            self._busy = False
    
    def _execute_sorting_sequence(self, status: int) -> None:
        self.get_logger().info(f"Waiting {self._travel_time:.1f}s for bottle to reach robot...")
        time.sleep(self._travel_time)
        
        self.get_logger().info("Stopping conveyor belt...")
        self._set_conveyor_power(0.0)
        time.sleep(1.0)  # Wait for belt to fully stop
        
        pickup_joints = RobotArmController.get_pickup_joints()
        approach_joints = RobotArmController.get_approach_joints(pickup_joints)
        
        self.get_logger().info("Moving to pickup approach...")
        self._set_arm_joints(approach_joints)
        self._open_gripper()
        time.sleep(self._motion_delay)
        
        self.get_logger().info("Lowering to pickup position...")
        self._set_arm_joints(pickup_joints)
        time.sleep(self._motion_delay)
        
        self.get_logger().info("Grasping bottle...")
        self._close_gripper()
        time.sleep(self._gripper_delay)
        
        self.get_logger().info("Lifting bottle...")
        self._set_arm_joints(approach_joints)
        time.sleep(self._motion_delay)
        
        place_joints = RobotArmController.get_place_joints(status)
        place_approach = RobotArmController.get_approach_joints(place_joints)
        
        self.get_logger().info("Moving to bin...")
        self._set_arm_joints(place_approach)
        time.sleep(self._motion_delay)
        
        self.get_logger().info("Lowering to bin...")
        self._set_arm_joints(place_joints)
        time.sleep(self._motion_delay)
        
        self.get_logger().info("Releasing bottle...")
        self._open_gripper()
        time.sleep(self._gripper_delay)
        
        self._set_arm_joints(place_approach)
        time.sleep(0.5)
        
        self.get_logger().info("Returning home...")
        self._move_to_home()
        time.sleep(self._motion_delay)
        
        self.get_logger().info("Resuming conveyor...")
        self._set_conveyor_power(self._resume_power)
    
    def _set_conveyor_power(self, power: float) -> None:
        if self._belt_client.wait_for_service(timeout_sec=1.0):
            req = ConveyorBeltControl.Request()
            req.power = float(power)
            self._belt_client.call_async(req)
    
    def _publish_trajectory(self, joint_names: List[str], positions: List[float], duration_sec: float = 0.5) -> None:
        msg = JointTrajectory()
        # Set frame_id to a valid link in the model to avoid "needs a reference link" error
        # "base_link" is the root link of our robot model
        msg.header = Header()
        msg.header.frame_id = "base_link"
        msg.joint_names = joint_names
        
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in positions]
        point.time_from_start = DurationMsg(sec=0, nanosec=int(duration_sec * 1e9))
        
        msg.points = [point]
        self._trajectory_pub.publish(msg)
    
    def _set_arm_joints(self, angles: List[float]) -> None:
        self._publish_trajectory(self._arm_joints, angles, duration_sec=0.5)
    
    def _set_gripper(self, position: float) -> None:
        positions = [float(position), float(position)]
        self._publish_trajectory(self._gripper_joints, positions, duration_sec=0.2)
    
    def _open_gripper(self) -> None:
        self._set_gripper(RobotArmController.GRIPPER_OPEN)
    
    def _close_gripper(self) -> None:
        self._set_gripper(RobotArmController.GRIPPER_CLOSED)
    
    def _move_to_home(self) -> None:
        self._set_arm_joints(RobotArmController.HOME_JOINTS)
        self._open_gripper()


def main(args=None):
    rclpy.init(args=args)
    node = SortingActuator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
