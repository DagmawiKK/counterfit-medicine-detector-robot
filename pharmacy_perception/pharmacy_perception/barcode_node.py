import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import String, Int32MultiArray
from cv_bridge import CvBridge
from pyzbar import pyzbar
import cv2


ALLOWED_TYPES = {"EAN13", "DATAMATRIX", "DATA_MATRIX", "QRCODE"}


class BarcodeNode(Node):
    def __init__(self):
        super().__init__("barcode_node")
        self.declare_parameter("image_topic", "/camera/raw")
        self.declare_parameter("barcode_topic", "/barcode/data")
        self.declare_parameter("bbox_topic", "/barcode/bbox")

        image_topic = self.get_parameter("image_topic").get_parameter_value().string_value
        barcode_topic = self.get_parameter("barcode_topic").get_parameter_value().string_value
        bbox_topic = self.get_parameter("bbox_topic").get_parameter_value().string_value

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )

        self._bridge = CvBridge()
        self._barcode_pub = self.create_publisher(String, barcode_topic, 10)
        self._bbox_pub = self.create_publisher(Int32MultiArray, bbox_topic, 10)
        self._image_sub = self.create_subscription(Image, image_topic, self._on_image, qos)

        self.get_logger().info("barcode_node started")

    def _on_image(self, msg: Image) -> None:
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().warn(f"cv_bridge failed: {exc}")
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        barcodes = pyzbar.decode(gray)
        if not barcodes:
            return

        for barcode in barcodes:
            if barcode.type not in ALLOWED_TYPES:
                continue

            decoded = barcode.data.decode("utf-8", errors="ignore")
            rect = barcode.rect

            barcode_msg = String()
            barcode_msg.data = decoded
            self._barcode_pub.publish(barcode_msg)

            bbox_msg = Int32MultiArray()
            bbox_msg.data = [int(rect.left), int(rect.top), int(rect.width), int(rect.height)]
            self._bbox_pub.publish(bbox_msg)

            self.get_logger().info(
                f"Barcode: {decoded} | type={barcode.type} | bbox=({rect.left},{rect.top},{rect.width},{rect.height})"
            )


def main() -> None:
    rclpy.init()
    node = BarcodeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
