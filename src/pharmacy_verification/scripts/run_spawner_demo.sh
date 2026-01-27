#!/usr/bin/env bash
set -euo pipefail

source /opt/ros/humble/setup.bash
source "$(pwd)/install/setup.bash"

ros2 run pharmacy_verification bottle_spawner
