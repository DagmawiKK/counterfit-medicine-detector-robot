import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String, Int32MultiArray
from cv_bridge import CvBridge
import cv2
import pytesseract


class OcrNode(Node):
    def __init__(self):
        super().__init__("ocr_node")
        self.declare_parameter("image_topic", "/camera/raw")
        self.declare_parameter("bbox_topic", "/barcode/bbox")
        self.declare_parameter("ocr_topic", "/ocr/data")
        self.declare_parameter("roi_expand_x_factor", 2.0)
        self.declare_parameter("roi_above_factor", 0.8)
        self.declare_parameter("roi_below_factor", 3.0)
        self.declare_parameter("roi_offset_y", -10)
        self.declare_parameter(
            "tesseract_config",
            "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/-",
        )

        self._image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        self._bbox_topic = self.get_parameter("bbox_topic").get_parameter_value().string_value
        self._ocr_topic = self.get_parameter("ocr_topic").get_parameter_value().string_value
        self._roi_expand_x_factor = self.get_parameter("roi_expand_x_factor").get_parameter_value().double_value
        self._roi_above_factor = self.get_parameter("roi_above_factor").get_parameter_value().double_value
        self._roi_below_factor = self.get_parameter("roi_below_factor").get_parameter_value().double_value
        self._roi_offset_y = self.get_parameter("roi_offset_y").get_parameter_value().integer_value
        self._tesseract_config = self.get_parameter("tesseract_config").get_parameter_value().string_value

        image_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )

        self._bridge = CvBridge()
        self._ocr_pub = self.create_publisher(String, self._ocr_topic, 10)
        self._image_sub = self.create_subscription(Image, self._image_topic, self._on_image, image_qos)
        self._bbox_sub = self.create_subscription(Int32MultiArray, self._bbox_topic, self._on_bbox, 10)

        self._latest_image = None
        self._latest_bbox = None

        self.get_logger().info("ocr_node started")

    def _on_bbox(self, msg: Int32MultiArray) -> None:
        if len(msg.data) != 4:
            return
        self._latest_bbox = msg.data

    def _on_image(self, msg: Image) -> None:
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().warn(f"cv_bridge failed: {exc}")
            return

        self._latest_image = frame
        if self._latest_bbox is None:
            return

        x, y, w, h = self._latest_bbox
        expand_x = int(w * self._roi_expand_x_factor)
        above = int(h * self._roi_above_factor)
        below = int(h * self._roi_below_factor)

        roi_x1 = max(0, x - expand_x)
        roi_x2 = min(frame.shape[1], x + w + expand_x)
        roi_y1 = max(0, y - above + self._roi_offset_y)
        roi_y2 = min(frame.shape[0], y + below + self._roi_offset_y)

        if roi_x2 <= roi_x1 or roi_y2 <= roi_y1:
            return

        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        blur = cv2.bilateralFilter(resized, 7, 50, 50)
        thresh = cv2.adaptiveThreshold(
            blur,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )

        text = pytesseract.image_to_string(thresh, config=self._tesseract_config)
        cleaned = " ".join(text.split())
        if not cleaned:
            return

        msg_out = String()
        msg_out.data = cleaned
        self._ocr_pub.publish(msg_out)
        self.get_logger().info(f"OCR: {cleaned}")


def main() -> None:
    rclpy.init()
    node = OcrNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
