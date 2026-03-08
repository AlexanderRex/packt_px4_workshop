#!/usr/bin/env bash
SCRIPT_DIR=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")
REPO_ROOT=$(dirname "$SCRIPT_DIR")

# Allow X11 from host (optional; skip if no DISPLAY)
xhost +local: 2>/dev/null || true

NVIDIA=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --nvidia)
            NVIDIA=1
            shift
            ;;
        -b|--build)
            "$SCRIPT_DIR/docker_build.sh"
            shift
            ;;
        *)
            break
            ;;
    esac
done

DEVICE_ARGS=()
if [[ -e /dev/dri ]]; then
    DEVICE_ARGS=(--device /dev/dri:/dev/dri)
elif [[ -e /dev/dxg ]]; then
    DEVICE_ARGS=(--device /dev/dxg:/dev/dri)
fi

RUN_OPTS=(
    -it --rm
    --network host
    -e DISPLAY="${DISPLAY}"
    -e QT_X11_NO_MITSHM=1
    -e QT_QPA_PLATFORM=xcb
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw
    -v "$REPO_ROOT/scripts:/home/ubuntu/scripts:rw"
    $([ -d /usr/lib/wsl ] && echo "-v /usr/lib/wsl:/usr/lib/wsl:ro")
    -w /home/ubuntu
    --name packt-px4
)

RUN_OPTS+=("${DEVICE_ARGS[@]}")

if [[ -n "$NVIDIA" ]]; then
    RUN_OPTS+=(
        --runtime nvidia
        -e NVIDIA_VISIBLE_DEVICES=all
        -e NVIDIA_DRIVER_CAPABILITIES=all
        -e MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
        -e LD_LIBRARY_PATH=/usr/lib/wsl/lib
    )
fi

# Default -i for interactive shell (entrypoint is /bin/bash; passing "bash" would run /bin/bash bash = error)
CMD=("${@:--i}")
docker run "${RUN_OPTS[@]}" packt-px4 "${CMD[@]}"
