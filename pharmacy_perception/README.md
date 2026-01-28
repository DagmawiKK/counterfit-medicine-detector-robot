# Pharmacy Perception

ROS 2 Humble perception nodes for barcode detection and OCR from the Gazebo camera feed.

## Nodes

- `barcode_node`
  - Subscribes: `/camera/scanner_camera/image_raw`
  - Publishes: `/barcode/data` (decoded string), `/barcode/bbox` ([x, y, w, h])

- `ocr_node`
  - Subscribes: `/camera/scanner_camera/image_raw`, `/barcode/bbox`
  - Publishes: `/ocr/data` (OCR text)

- `verification_manager`
  - Subscribes: `/barcode/data`, `/ocr/data`
  - Publishes: `/verification/result` (status codes: 0 valid, 1 expired, 2 mismatch)
  - Service: `VerifyDrug`

- `sorting_actuator`
  - Subscribes: `/verification/result`
  - Controls: `/CONVEYORPOWER` and `/gazebo/set_model_configuration`

## Dependencies

System packages:
- `libzbar0`
- `tesseract-ocr`
- `python3-opencv`
- `ros-humble-cv-bridge`

Python packages:
- `pyzbar`
- `pytesseract`

## Install (example)

```bash
sudo apt update
sudo apt install -y libzbar0 tesseract-ocr python3-opencv ros-humble-cv-bridge
pip install pyzbar pytesseract
```

## Build

```bash
colcon build --symlink-install
source install/setup.bash
```

## Run

```bash
ros2 launch pharmacy_perception perception.launch.py
```

Run verification manager:

```bash
ros2 run pharmacy_perception verification_manager
```

Run sorting actuator:

```bash
ros2 launch pharmacy_perception sorting.launch.py
```

Note: Sorting uses `/gazebo/set_model_configuration`, which requires the Gazebo ROS API plugin (enabled in `conveyorbelt.world`).

Inventory file (default): `pharmacy_perception/config/inventory.json`

## Parameters

`ocr_node` parameters:
- `roi_padding_x` (default `10`)
- `roi_padding_y` (default `10`)
- `roi_offset_y` (default `40`)
- `tesseract_config` (default `--oem 3 --psm 6`)

Example override:

```bash
ros2 run pharmacy_perception ocr_node --ros-args -p roi_offset_y:=20
```
