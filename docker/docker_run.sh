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

RUN_OPTS=(
    -it --rm
    --network host
    -e DISPLAY="${DISPLAY}"
    -e QT_X11_NO_MITSHM=1
    -e QT_QPA_PLATFORM=xcb
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw
    -v "$REPO_ROOT/scripts:/home/ubuntu/scripts:rw"
    --device /dev/dri:/dev/dri
    -w /home/ubuntu
    --name packt-px4
)

if [[ -n "$NVIDIA" ]]; then
    RUN_OPTS+=(--runtime nvidia -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=all)
fi

# Default -i for interactive shell (entrypoint is /bin/bash; passing "bash" would run /bin/bash bash = error)
CMD=("${@:--i}")
docker run "${RUN_OPTS[@]}" packt-px4 "${CMD[@]}"
