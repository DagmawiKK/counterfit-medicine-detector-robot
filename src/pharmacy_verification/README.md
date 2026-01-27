# Pharmacy Verification

## Bottle Spawner + Conveyor Control
This package includes a `bottle_spawner` node that:
- Publishes `geometry_msgs/Twist` to `/conveyor/cmd_vel` to keep the belt moving.
- Spawns new bottles in Gazebo at a fixed interval.
- Randomly selects a label variant (`medicine_bottle_v1` .. `medicine_bottle_v5`).

### Run the full system
```bash
source install/setup.bash
ros2 launch pharmacy_verification pharmacy.launch.py
```

### Run only the spawner (for testing)
```bash
bash src/pharmacy_verification/scripts/run_spawner_demo.sh
```

### Customize
You can set parameters at runtime:
- `spawn_interval_sec` (default: 4.0)
- `belt_velocity` (default: 0.2)
- `spawn_x`, `spawn_y`, `spawn_z`
- `spawn_roll`, `spawn_pitch`, `spawn_yaw`

Example:
```bash
ros2 run pharmacy_verification bottle_spawner --ros-args \
  -p spawn_interval_sec:=2.0 \
  -p belt_velocity:=0.3
```
