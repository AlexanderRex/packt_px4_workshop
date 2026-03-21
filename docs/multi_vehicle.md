# Multi-Vehicle Simulation

Running multiple drones in a single Gazebo world.

## Launch

```bash
# Terminal 1 — first drone (instance 0, starts Gazebo)
make px4_sitl gz_x500

# Terminal 2 — second drone (instance 1)
cd build/px4_sitl_default
PX4_GZ_MODEL_POSE="0,3" PX4_SIM_MODEL=gz_x500 ./bin/px4 -i 1

# Terminal 3 — third drone (instance 2)
cd build/px4_sitl_default
PX4_GZ_MODEL_POSE="0,6" PX4_SIM_MODEL=gz_x500 ./bin/px4 -i 2
```

## Mixed models

```bash
# Terminal 1 — x500 quad
make px4_sitl gz_x500

# Terminal 2 — Typhoon H480 hex (needs Z offset for landing gear)
cd build/px4_sitl_default
PX4_GZ_MODEL_POSE="0,5,0.26" PX4_SIM_MODEL=gz_typhoon_h480 ./bin/px4 -i 1
```

## Key parameters

| Parameter | Description |
|-----------|-------------|
| `PX4_GZ_MODEL_POSE="x,y,z"` | Spawn position. Always specify Z for models with landing gear |
| `PX4_SIM_MODEL=gz_<name>` | Airframe/model to use |
| `-i N` | Instance ID (0, 1, 2...). Shifts all MAVLink ports |

## MAVLink ports per instance

| Instance | QGC UDP | Onboard UDP | SITL TCP |
|----------|---------|-------------|----------|
| 0 | 14550 | 14540 | 4560 |
| 1 | 14551 | 14541 | 4561 |
| 2 | 14552 | 14542 | 4562 |

## Notes

- Only instance 0 can be launched via `make`. All others must use `./bin/px4 -i N`
- `PX4_GZ_MODEL_POSE` overrides the model's SDF root `<pose>` — always specify Z for models that need ground clearance
- To reset instance parameters: `rm -rf build/px4_sitl_default/rootfs/N/`
- QGroundControl auto-connects to instance 0. For others, add UDP connections manually
