# Pharmacy Perception

ROS 2 Humble perception nodes for barcode detection and OCR from the Gazebo camera feed.

## Nodes

- `barcode_node`
  - Subscribes: `/camera/scanner_camera/image_raw`
  - Publishes: `/barcode/data` (decoded string), `/barcode/bbox` ([x, y, w, h])

- `ocr_node`
  - Subscribes: `/camera/scanner_camera/image_raw`, `/barcode/bbox`
  - Publishes: `/ocr/data` (OCR text)

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
