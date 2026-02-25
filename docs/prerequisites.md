# Prerequisites Installation

## Linux (Ubuntu 22.04 / 24.04)

### 1. Install Docker Engine

1. Install using the `apt` repository:

    ```sh
    # Add Docker's official GPG key:
    sudo apt-get update
    sudo apt-get install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ```

2. Run Docker as non-root user:

    ```sh
    sudo usermod -aG docker $USER
    ```

    Log out and log back in for this to take effect.

3. Verify the installation:

    ```sh
    docker run hello-world
    ```

For further information, refer to the [official Docker documentation](https://docs.docker.com/engine/install/ubuntu/).

### 2. Install X11 utilities

Required to display GUI applications (QGroundControl, PlotJuggler) from inside the container:

```sh
sudo apt install x11-xserver-utils
```

### 3. (Optional) NVIDIA Container Toolkit

Only required if you have an NVIDIA GPU and want GPU-accelerated rendering:

- Follow the [NVIDIA Container Toolkit install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

---

## Windows (Windows 10 / 11)

### 1. Install WSL 2 with Ubuntu

Open PowerShell as Administrator:

```powershell
wsl --install Ubuntu-22.04
```

Follow the [official WSL instructions](https://learn.microsoft.com/en-us/windows/wsl/install) if needed.

### 2. Install Docker Engine inside WSL 2

Once inside your Ubuntu WSL terminal, follow the same Docker Engine installation steps as described in the **Linux** section above.

Alternatively, you can install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) with the WSL 2 backend enabled — both approaches work.

### 3. Install an X11 Server (for GUI)

Install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) on Windows, then launch **XLaunch** with:
- Display number: `0`
- Multiple windows
- **Disable access control** checked

Before running the container in WSL, set the display:

```sh
export DISPLAY=$(grep nameserver /etc/resolv.conf | awk '{print $2}'):0
```

> **Note:** All `docker/docker_*.sh` scripts must be run from **inside a WSL 2 terminal**, not from PowerShell or CMD.

---

## macOS (Intel & Apple Silicon)

### 1. Install Docker Desktop

Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/). Requires macOS 12 Monterey or later.

After install, open Docker Desktop and wait until the whale icon shows "Running".

### 2. Install XQuartz (for GUI)

```sh
brew install --cask xquartz
```

After installation, **log out and log back in**, then:

1. Open XQuartz → Preferences → Security → check **"Allow connections from network clients"**.
2. Restart XQuartz.

Before running the container:

```sh
xhost +localhost
export DISPLAY=host.docker.internal:0
```

> **Note:** GUI performance on macOS is slower than on Linux due to the XQuartz bridge.

---

## VS Code + Docker Extension

For all platforms, install [VS Code](https://code.visualstudio.com/) with the following extensions:

- **Docker** (`ms-azuretools.vscode-docker`)
- **Dev Containers** (`ms-vscode-remote.remote-containers`)

This allows you to attach VS Code directly to the running container for a seamless editing experience.
