# Adding a Custom Drone to PX4 SITL + Gazebo Harmonic

Step-by-step guide based on adding the Typhoon H480 hexacopter.

## 1. Prepare meshes

Place STL/DAE mesh files in `meshes/` subdirectory. Scale `0.001` if meshes are in millimeters.

## 2. Create `model.config`

```xml
<?xml version="1.0"?>
<model>
  <name>Typhoon H480</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <description>Typhoon H480 hexacopter.</description>
</model>
```

## 3. Create `model.sdf`

### Structure

```
<model>
  <link name="base_link">        — body, sensors
  <link name="rotor_0"> .. N     — one per motor
  <joint name="rotor_0_joint">   — revolute, axis Z
  <plugin ...MulticopterMotorModel> — one per motor
</model>
```

### Materials (ogre2)

```xml
<material>
  <ambient>0.3 0.3 0.3 1</ambient>
  <diffuse>0.3 0.3 0.3 1</diffuse>
</material>
```

### Sensors

Add to `base_link` — copy from a working model (e.g. `x500_base`):
- `air_pressure_sensor` (type `air_pressure`)
- `magnetometer_sensor` (type `magnetometer`)
- `imu_sensor` (type `imu`)
- `navsat_sensor` (type `navsat`)

### Motor plugins

One `MulticopterMotorModel` per rotor:

```xml
<plugin filename="gz-sim-multicopter-motor-model-system"
        name="gz::sim::systems::MulticopterMotorModel">
  <jointName>rotor_0_joint</jointName>
  <linkName>rotor_0</linkName>
  <turningDirection>cw</turningDirection>
  <motorNumber>0</motorNumber>
  <motorType>velocity</motorType>
  <motorConstant>8.54858e-06</motorConstant>
  <momentConstant>0.016</momentConstant>
  ...
</plugin>
```

`turningDirection` must match airframe `CA_ROTOR*_KM` sign:
- `cw` → negative KM
- `ccw` → positive KM

## 4. Create airframe file

File name: `<ID>_gz_<model_name>` (e.g. `4901_gz_typhoon_h480`)

Key parameters:
```bash
PX4_SIMULATOR=${PX4_SIMULATOR:=gz}
PX4_SIM_MODEL=${PX4_SIM_MODEL:=typhoon_h480}
param set-default SIM_GZ_EN 1
param set-default CA_ROTOR_COUNT 6
param set-default MAV_TYPE 13          # 2=quad, 13=hex
param set-default CA_ROTOR0_PX ...     # normalized rotor positions
param set-default CA_ROTOR0_KM -0.05   # yaw moment sign
param set-default SIM_GZ_EC_FUNC1 101  # motor function mapping
param set-default SIM_GZ_EC_MIN1 150
param set-default SIM_GZ_EC_MAX1 1000
```

## 5. Register in PX4 build

From the host (workshop repo root):

```bash
# Copy model to container
docker cp gazebo_models/typhoon_h480 \
  packt-px4:/home/ubuntu/PX4-Autopilot/Tools/simulation/gz/models/

# Copy airframe to container
docker cp gazebo_models/typhoon_h480/4901_gz_typhoon_h480 \
  packt-px4:/home/ubuntu/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix/airframes/
```

Inside the container:

```bash
# Add to CMakeLists.txt
sed -i '/# \[22000, 22999\] Reserve for custom models/i\    4901_gz_typhoon_h480' \
  ROMFS/px4fmu_common/init.d-posix/airframes/CMakeLists.txt

# Rebuild
make px4_sitl_default
```

## 6. Launch

Inside the container:

```bash
make px4_sitl gz_typhoon_h480
```

## Common pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| Props fly away from body | Wrong visual `<pose>` in rotor links | Visual pose must offset mesh origin to link center |
| Drone flips on takeoff | `turningDirection` doesn't match `CA_ROTOR*_KM` signs | `cw` → negative KM, `ccw` → positive KM |
| Drone spins in yaw | All turning directions inverted | Swap all `cw`↔`ccw` |
| Old params persist | Manual `param set` overrides defaults | Delete `parameters.bson` or let PX4 auto-reset on airframe change |
| Make target not found | Airframe not in CMakeLists | Add entry and run `make px4_sitl_default` |
| Black/unpainted models | Ogre1 material scripts | Use `<ambient>`/`<diffuse>` tags instead |
