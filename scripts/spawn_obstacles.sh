#!/usr/bin/env bash
#
# spawn_obstacles.sh — Spawn and manage objects in a running Gazebo Harmonic simulation.
#
# Gazebo supports several ways to add objects to a world at runtime:
#
#   1. SDF primitives (box, cylinder, sphere)
#      Defined inline as SDF XML strings. Good for simple obstacles.
#      Primitives: <box>, <cylinder>, <sphere>, <capsule>, <ellipsoid>, <plane>
#
#   2. Gazebo Fuel models (online library)
#      Referenced by URI: https://fuel.gazebosim.org/1.0/<owner>/models/<name>
#      Hundreds of ready-made models: buildings, trees, vehicles, furniture, etc.
#      Browse: https://app.gazebosim.org/fuel/models
#
#   3. Local SDF models (custom)
#      A directory with model.sdf + model.config, referenced by file:// URI.
#      Set GZ_SIM_RESOURCE_PATH to the parent directory.
#
# All methods use the same Gazebo service:
#   gz service -s /world/<world>/create --reqtype gz.msgs.EntityFactory ...
#
# Requires the UserCommands plugin in the world SDF:
#   <plugin filename="gz-sim-user-commands-system"
#           name="gz::sim::systems::UserCommands"/>
#
# Usage (run inside the container):
#   ./spawn_obstacles.sh                   # spawn all demo obstacles
#   ./spawn_obstacles.sh --clear           # remove all spawned obstacles
#   ./spawn_obstacles.sh --list            # list obstacle names
#   ./spawn_obstacles.sh box <name> <sx> <sy> <sz> <x> <y> <z>
#   ./spawn_obstacles.sh cylinder <name> <radius> <length> <x> <y> <z>
#   ./spawn_obstacles.sh sphere <name> <radius> <x> <y> <z>
#   ./spawn_obstacles.sh fuel <name> <owner/model> <x> <y> <z>
#   ./spawn_obstacles.sh remove <name>
#
# Examples:
#   ./spawn_obstacles.sh box crate 1 1 1 5 0 0.5
#   ./spawn_obstacles.sh cylinder pole 0.3 4 8 4 2
#   ./spawn_obstacles.sh sphere ball 0.5 0 3 0.5
#   ./spawn_obstacles.sh fuel tree1 "OpenRobotics/models/Oak tree" 10 5 0
#   ./spawn_obstacles.sh fuel barrel1 "OpenRobotics/models/Construction Barrel" 3 0 0
#   ./spawn_obstacles.sh remove crate

set -euo pipefail

WORLD="${PX4_GZ_WORLD:-default}"

# ---------------------------------------------------------------------------
# Core: create via temp SDF file / remove via gz service
# ---------------------------------------------------------------------------

gz_spawn() {
    local name="$1" sdf_content="$2" x="$3" y="$4" z="$5"
    local tmpfile
    tmpfile=$(mktemp /tmp/gz_spawn_XXXXXX.sdf)
    cat > "$tmpfile" <<SDEOF
<?xml version="1.0" ?>
<sdf version="1.9">
${sdf_content}
</sdf>
SDEOF
    gz service \
        -s "/world/${WORLD}/create" \
        --reqtype gz.msgs.EntityFactory \
        --reptype gz.msgs.Boolean \
        --timeout 5000 \
        --req "sdf_filename: \"${tmpfile}\", name: \"${name}\", allow_renaming: false, pose: {position: {x: ${x}, y: ${y}, z: ${z}}}"
    echo "  + $name at ($x, $y, $z)"
}

gz_remove() {
    local name="$1"
    gz service \
        -s "/world/${WORLD}/remove" \
        --reqtype gz.msgs.Entity \
        --reptype gz.msgs.Boolean \
        --timeout 5000 \
        --req "name: \"${name}\", type: 2"
    echo "  - $name"
}

# ---------------------------------------------------------------------------
# Primitives: box, cylinder, sphere
# ---------------------------------------------------------------------------

# box <name> <size_x> <size_y> <size_z> <pos_x> <pos_y> <pos_z>
spawn_box() {
    local name="$1" sx="$2" sy="$3" sz="$4" x="$5" y="$6" z="$7"
    gz_spawn "$name" "
  <model name=\"${name}\">
    <static>true</static>
    <link name=\"link\">
      <visual name=\"visual\">
        <geometry><box><size>${sx} ${sy} ${sz}</size></box></geometry>
        <material>
          <ambient>0.7 0.3 0.3 1</ambient>
          <diffuse>0.7 0.3 0.3 1</diffuse>
        </material>
      </visual>
      <collision name=\"collision\">
        <geometry><box><size>${sx} ${sy} ${sz}</size></box></geometry>
      </collision>
    </link>
  </model>" "$x" "$y" "$z"
}

# cylinder <name> <radius> <length> <pos_x> <pos_y> <pos_z>
spawn_cylinder() {
    local name="$1" r="$2" l="$3" x="$4" y="$5" z="$6"
    gz_spawn "$name" "
  <model name=\"${name}\">
    <static>true</static>
    <link name=\"link\">
      <visual name=\"visual\">
        <geometry><cylinder><radius>${r}</radius><length>${l}</length></cylinder></geometry>
      </visual>
      <collision name=\"collision\">
        <geometry><cylinder><radius>${r}</radius><length>${l}</length></cylinder></geometry>
      </collision>
    </link>
  </model>" "$x" "$y" "$z"
}

# sphere <name> <radius> <pos_x> <pos_y> <pos_z>
spawn_sphere() {
    local name="$1" r="$2" x="$3" y="$4" z="$5"
    gz_spawn "$name" "
  <model name=\"${name}\">
    <static>true</static>
    <link name=\"link\">
      <visual name=\"visual\">
        <geometry><sphere><radius>${r}</radius></sphere></geometry>
      </visual>
      <collision name=\"collision\">
        <geometry><sphere><radius>${r}</radius></sphere></geometry>
      </collision>
    </link>
  </model>" "$x" "$y" "$z"
}

# ---------------------------------------------------------------------------
# Gazebo Fuel: online model library
# ---------------------------------------------------------------------------

# fuel <name> <owner/model_name> <pos_x> <pos_y> <pos_z>
# Example: ./spawn_obstacles.sh fuel cone1 "OpenRobotics/models/Construction Cone" 3 0 0
# Browse models: https://app.gazebosim.org/fuel/models
spawn_fuel() {
    local name="$1" model="$2" x="$3" y="$4" z="$5"
    local uri="https://fuel.gazebosim.org/1.0/${model}"
    gz_spawn "$name" "
  <include>
    <name>${name}</name>
    <uri>${uri}</uri>
  </include>" "$x" "$y" "$z"
}

# ---------------------------------------------------------------------------
# Demo obstacle set
# ---------------------------------------------------------------------------

OBSTACLES=(
    wall_front wall_side wall_back
    tower_1 tower_2
    ball_1
    platform
)

spawn_demo() {
    echo "Spawning demo obstacles..."
    echo ""
    echo "[Primitives: box]"
    spawn_box    wall_front   4 0.3 2.5   5  0    1.25
    spawn_box    wall_side    0.3 4 2.5   0  6    1.25
    spawn_box    wall_back    6 0.3 3     -3 -5   1.5

    echo ""
    echo "[Primitives: cylinder]"
    spawn_cylinder tower_1    0.4 4       8  4    2
    spawn_cylinder tower_2    0.4 4       -5 3    2

    echo ""
    echo "[Primitives: sphere]"
    spawn_sphere   ball_1     0.5         3  3    0.5

    echo ""
    echo "[Primitives: box (flat)]"
    spawn_box    platform     2 2 0.15    10 10   0.075

    echo ""
    echo "Done. ${#OBSTACLES[@]} obstacles spawned."
    echo "Run '$0 --clear' to remove them."
}

# Remove all spawned models (keeps ground_plane and drone)
clear_all() {
    echo "Clearing all spawned models..."
    local models
    models=$(gz model --list 2>/dev/null | grep '^ ' | sed 's/^ *- //')
    for name in $models; do
        case "$name" in
            ground_plane|x500*|sunUTC) continue ;;
            *) gz_remove "$name" 2>/dev/null || true ;;
        esac
    done
    echo "Done."
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

case "${1:-}" in
    --clear)    clear_all ;;
    --list)     printf '%s\n' "${OBSTACLES[@]}" ;;
    box)        shift; spawn_box "$@" ;;
    cylinder)   shift; spawn_cylinder "$@" ;;
    sphere)     shift; spawn_sphere "$@" ;;
    fuel)       shift; spawn_fuel "$@" ;;
    remove)     shift; gz_remove "$@" ;;
    -h|--help)
        sed -n '2,/^[^#]/{ /^#/s/^# \?//p }' "$0"
        ;;
    *)          spawn_demo ;;
esac
