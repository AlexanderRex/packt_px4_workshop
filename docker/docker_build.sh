#!/usr/bin/env bash
set -e
SCRIPT_DIR=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")
REPO_ROOT=$(dirname "$SCRIPT_DIR")
docker build -t packt-px4 -f "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT"
