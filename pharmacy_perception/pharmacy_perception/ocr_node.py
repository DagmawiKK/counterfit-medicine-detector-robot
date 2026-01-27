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
        self.declare_parameter("roi_padding_x", 10)
        self.declare_parameter("roi_padding_y", 10)
        self.declare_parameter("roi_offset_y", 40)
        self.declare_parameter("tesseract_config", "--oem 3 --psm 6")

        self._image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        self._bbox_topic = self.get_parameter("bbox_topic").get_parameter_value().string_value
        self._ocr_topic = self.get_parameter("ocr_topic").get_parameter_value().string_value
        self._roi_padding_x = self.get_parameter("roi_padding_x").get_parameter_value().integer_value
        self._roi_padding_y = self.get_parameter("roi_padding_y").get_parameter_value().integer_value
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
        roi_x1 = max(0, x - self._roi_padding_x)
        roi_y1 = max(0, y + h + self._roi_offset_y)
        roi_x2 = min(frame.shape[1], x + w + self._roi_padding_x)
        roi_y2 = min(frame.shape[0], roi_y1 + h + self._roi_padding_y)

        if roi_x2 <= roi_x1 or roi_y2 <= roi_y1:
            return

        roi = frame[roi_y1:roi_y2, roi_x1:roi_x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

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
    rclpy.shutdown()


if __name__ == "__main__":
    main()
