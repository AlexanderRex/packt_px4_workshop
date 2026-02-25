# Setup

This page will guide you through building the Docker image and starting the PX4 + Gazebo simulation environment.

The image contains all the required dependencies for the workshop:

- [PX4](https://github.com/PX4/PX4-Autopilot) v1.16.0 SITL simulator
- [QGroundControl](https://qgroundcontrol.com/) — ground control station
- [MAVSDK-Python](https://github.com/mavlink/MAVSDK-Python) — scripted mission control
- [PlotJuggler](https://github.com/facontidavide/PlotJuggler) — log visualization and analysis

## Prerequisites

- **Docker** installed and running. See [docs/prerequisites.md](./prerequisites.md) for platform-specific instructions.
- **X11 forwarding** configured (required for QGroundControl, PlotJuggler). See the platform-specific sections in the prerequisites guide.

## Building the Docker Image

From the repository root:

```sh
./docker/docker_build.sh
```

This builds the `packt-px4` image. The first build takes 10–20 minutes depending on your network and hardware (PX4 is compiled from source inside the image).

## Starting the Container

```sh
./docker/docker_run.sh
```

The script will:

- Start the container with the name `packt-px4` and attach a shell to it.
- Forward X11 to run GUI applications (QGC, PlotJuggler) from inside the container.
- Mount the `scripts/` directory from the host so your work is persisted.

### Options

| Flag | Description |
|------|-------------|
| `--nvidia` | Run with NVIDIA GPU runtime (requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)) |
| `-b` / `--build` | Build the image before starting the container |

Examples:

```sh
# Build and run in one command
./docker/docker_run.sh --build

# Run with NVIDIA GPU acceleration (Linux)
./docker/docker_run.sh --nvidia
```

## Container Structure

- **PX4 SITL binaries:** `/home/ubuntu/PX4-Autopilot/` — full PX4 source with pre-built SITL
- **QGroundControl:** `/home/ubuntu/QGroundControl/` — extracted AppImage
- **Workshop scripts:** `/home/ubuntu/scripts/` — mounted from host `scripts/` directory

### QGroundControl

QGC is pre-installed in the container. To launch:

```sh
~/qgc
```

If you are running the container without GUI (headless), you can install QGC on the host and connect it via UDP to `127.0.0.1:18570`. See the [QGC installation guide](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html) for host installation.

## How to Start the Simulation

### 1. Start PX4 SITL

From inside the container:

```sh
cd ~/PX4-Autopilot
make px4_sitl gz_x500
```

This launches PX4 with the Gazebo x500 quadrotor model. You should see the PX4 shell prompt (`pxh>`).

### 2. Connect QGroundControl

In a second terminal (attach to the running container):

```sh
docker exec -it packt-px4 bash
~/qgc
```

QGC will auto-detect the simulated drone via UDP. Once connected, you'll see `Ready for takeoff!` in the PX4 terminal.

### 3. Run a Mission Script

In a third terminal:

```sh
docker exec -it packt-px4 bash
cd ~/scripts
python3 <script_name>.py
```

Mission scripts use MAVSDK-Python to command the drone programmatically.

### 4. Analyze Logs with PlotJuggler

```sh
plotjuggler
```

Load PX4 `.ulg` log files from the PX4 log directory to visualize telemetry data.

## Troubleshooting

### GUI not showing (`cannot open display`)

Make sure your X11 forwarding is configured:

- **Linux:** Run `xhost +local:` before starting the container.
- **macOS:** Ensure XQuartz is running with network clients allowed, and `DISPLAY` is set to `host.docker.internal:0`.
- **Windows (WSL 2):** Ensure VcXsrv is running with access control disabled, and `DISPLAY` is exported in your WSL shell.

### Permission denied on Docker socket

Add your user to the `docker` group and re-login:

```sh
sudo usermod -aG docker $USER
```

### WSL 2: `/dev/dri` not found

Use `--nvidia` with NVIDIA Container Toolkit on WSL 2, or remove the `--device /dev/dri:/dev/dri` line from `docker_run.sh` if you don't need GPU rendering.

### Slow GUI on macOS

This is expected due to XQuartz overhead. For the best experience, use a Linux host or WSL 2 with VcXsrv.
