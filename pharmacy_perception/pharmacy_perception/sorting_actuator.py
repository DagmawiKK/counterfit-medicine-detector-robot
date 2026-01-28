import time

import rclpy
from rclpy.node import Node
from conveyorbelt_msgs.msg import VerificationResult
from conveyorbelt_msgs.srv import ConveyorBeltControl
from gazebo_msgs.srv import SetModelConfiguration


class SortingActuator(Node):
    def __init__(self) -> None:
        super().__init__("sorting_actuator")
        self.declare_parameter("verification_topic", "/verification/result")
        self.declare_parameter("conveyor_service", "/CONVEYORPOWER")
        self.declare_parameter("model_name", "diverter_arm")
        self.declare_parameter("joint_name", "diverter_joint")
        self.declare_parameter("home_angle", 0.0)
        self.declare_parameter("divert_angle", 1.0)
        self.declare_parameter("hold_seconds", 1.0)
        self.declare_parameter("resume_power", 50.0)
        self.declare_parameter("cooldown_seconds", 3.0)

        self._verification_topic = self.get_parameter("verification_topic").get_parameter_value().string_value
        self._conveyor_service = self.get_parameter("conveyor_service").get_parameter_value().string_value
        self._model_name = self.get_parameter("model_name").get_parameter_value().string_value
        self._joint_name = self.get_parameter("joint_name").get_parameter_value().string_value
        self._home_angle = self.get_parameter("home_angle").get_parameter_value().double_value
        self._divert_angle = self.get_parameter("divert_angle").get_parameter_value().double_value
        self._hold_seconds = self.get_parameter("hold_seconds").get_parameter_value().double_value
        self._resume_power = self.get_parameter("resume_power").get_parameter_value().double_value
        self._cooldown_seconds = self.get_parameter("cooldown_seconds").get_parameter_value().double_value

        self._busy = False
        self._last_action_time = 0.0

        self._verification_sub = self.create_subscription(
            VerificationResult,
            self._verification_topic,
            self._on_verification,
            10,
        )

        self._belt_client = self.create_client(ConveyorBeltControl, self._conveyor_service)
        self._joint_client = self.create_client(SetModelConfiguration, "/gazebo/set_model_configuration")

        self.get_logger().info("sorting_actuator started")

    def _on_verification(self, msg: VerificationResult) -> None:
        now = time.time()
        if now - self._last_action_time < self._cooldown_seconds:
            return
        if self._busy:
            return
        if msg.status not in (1, 2):
            return

        self._busy = True
        self._last_action_time = now
        self.get_logger().info(f"Invalid bottle detected (status={msg.status}). Activating diverter.")

        if not self._belt_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn("Conveyor service not available")
        else:
            self._set_conveyor_power(0.0)

        if not self._joint_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn("Gazebo joint config service not available. Ensure gazebo_ros_api is loaded.")
        else:
            self._set_joint_position(self._divert_angle)
            time.sleep(self._hold_seconds)
            self._set_joint_position(self._home_angle)

        if self._belt_client.service_is_ready():
            self._set_conveyor_power(self._resume_power)

        self._busy = False

    def _set_conveyor_power(self, power: float) -> None:
        request = ConveyorBeltControl.Request()
        request.power = float(power)
        self._belt_client.call_async(request)

    def _set_joint_position(self, angle: float) -> None:
        request = SetModelConfiguration.Request()
        request.model_name = self._model_name
        request.urdf_param_name = ""
        request.joint_names = [self._joint_name]
        request.joint_positions = [float(angle)]
        self._joint_client.call_async(request)


def main() -> None:
    rclpy.init()
    node = SortingActuator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
