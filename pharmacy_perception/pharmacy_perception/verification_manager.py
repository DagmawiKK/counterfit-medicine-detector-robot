import json
import re
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from message_filters import Subscriber, ApproximateTimeSynchronizer
from std_msgs.msg import String

from conveyorbelt_msgs.msg import VerificationResult
from conveyorbelt_msgs.srv import VerifyDrug


DATE_FORMATS = ["%m/%Y", "%m-%Y", "%Y-%m", "%Y/%m", "%Y.%m"]
LOT_REGEX = re.compile(r"LOT[:\s]*([A-Z0-9\-]+)", re.IGNORECASE)
EXP_REGEX = re.compile(r"EXP[:\s]*([0-9]{1,2}[\/-][0-9]{4})", re.IGNORECASE)


class VerificationManager(Node):
    def __init__(self) -> None:
        super().__init__("verification_manager")
        self.declare_parameter("barcode_topic", "/barcode/data")
        self.declare_parameter("ocr_topic", "/ocr/data")
        self.declare_parameter("result_topic", "/verification/result")
        self.declare_parameter("inventory_path", "config/inventory.json")

        barcode_topic = self.get_parameter("barcode_topic").get_parameter_value().string_value
        ocr_topic = self.get_parameter("ocr_topic").get_parameter_value().string_value
        result_topic = self.get_parameter("result_topic").get_parameter_value().string_value
        inventory_path = self.get_parameter("inventory_path").get_parameter_value().string_value

        self._inventory = self._load_inventory(inventory_path)

        self._result_pub = self.create_publisher(VerificationResult, result_topic, 10)
        self._verify_srv = self.create_service(VerifyDrug, "VerifyDrug", self._handle_verify_service)

        self._barcode_sub = Subscriber(self, String, barcode_topic)
        self._ocr_sub = Subscriber(self, String, ocr_topic)
        self._sync = ApproximateTimeSynchronizer(
            [self._barcode_sub, self._ocr_sub],
            queue_size=10,
            slop=0.5,
            allow_headerless=True,
        )
        self._sync.registerCallback(self._on_synced)

        self.get_logger().info("verification_manager started")

    def _load_inventory(self, path: str) -> dict:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = Path(self.get_package_share_directory()) / path
        try:
            with open(resolved, "r") as handle:
                data = json.load(handle)
        except Exception as exc:
            self.get_logger().warn(f"Failed to load inventory at {resolved}: {exc}")
            data = {"items": []}
        return {item["barcode"]: item for item in data.get("items", [])}

    def get_package_share_directory(self) -> str:
        from ament_index_python.packages import get_package_share_directory
        return get_package_share_directory("pharmacy_perception")

    def _parse_lot(self, text: str) -> str:
        match = LOT_REGEX.search(text)
        return match.group(1).strip().upper() if match else ""

    def _parse_exp(self, text: str) -> str:
        match = EXP_REGEX.search(text)
        return match.group(1).strip() if match else ""

    def _parse_exp_date(self, exp: str) -> datetime | None:
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(exp, fmt)
            except ValueError:
                continue
        return None

    def _verify(self, barcode: str, ocr_text: str) -> tuple[int, str, str, str, str]:
        lot = self._parse_lot(ocr_text)
        exp = self._parse_exp(ocr_text)
        if not barcode:
            return 2, barcode, lot, exp, "Missing barcode"

        entry = self._inventory.get(barcode)
        if not entry:
            return 2, barcode, lot, exp, "Unknown barcode"

        expected_lot = entry.get("lot", "").upper()
        expected_exp = entry.get("expiry", "")

        if expected_lot and lot and expected_lot != lot:
            return 2, barcode, lot, exp, "Lot mismatch"

        exp_value = exp or expected_exp
        exp_date = self._parse_exp_date(exp_value)
        if exp_date and exp_date < datetime.now():
            return 1, barcode, lot, exp_value, "Expired"

        return 0, barcode, lot or expected_lot, exp_value, "Valid"

    def _publish_result(self, status: int, barcode: str, lot: str, exp: str, reason: str) -> None:
        msg = VerificationResult()
        msg.status = int(status)
        msg.barcode = barcode
        msg.lot = lot
        msg.expiry = exp
        msg.reason = reason
        self._result_pub.publish(msg)
        self.get_logger().info(f"Verification: status={status} reason={reason} barcode={barcode} lot={lot} exp={exp}")

    def _on_synced(self, barcode_msg: String, ocr_msg: String) -> None:
        status, barcode, lot, exp, reason = self._verify(barcode_msg.data.strip(), ocr_msg.data.strip())
        self._publish_result(status, barcode, lot, exp, reason)

    def _handle_verify_service(self, request: VerifyDrug.Request, response: VerifyDrug.Response) -> VerifyDrug.Response:
        status, barcode, lot, exp, reason = self._verify(request.barcode.strip(), f"LOT: {request.lot} EXP: {request.expiry}")
        response.status = int(status)
        response.reason = reason
        return response


def main() -> None:
    rclpy.init()
    node = VerificationManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
