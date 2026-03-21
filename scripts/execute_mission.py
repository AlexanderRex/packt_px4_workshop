#!/usr/bin/env python3
"""Execute a QGroundControl .plan mission file on a PX4 drone via MAVSDK.

Supports SimpleItem and ComplexItem (survey / corridor scan) plan entries.

Usage:
    python3 execute_mission.py <mission.plan> [--address udp://:14540]
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import List

from mavsdk import System
from mavsdk.mission_raw import MissionItem as RawMissionItem


# ── QGC .plan → MAVSDK raw mission items ─────────────────────────────────────

def load_plan(path: str) -> List[RawMissionItem]:
    """Parse a QGroundControl .plan file into a flat list of MAVSDK RawMissionItems.

    Handles both top-level SimpleItems and SimpleItems nested inside
    ComplexItems (e.g. survey / corridor-scan patterns).
    """
    with open(path) as f:
        plan = json.load(f)

    if plan.get("fileType") != "Plan":
        raise ValueError(f"{path!r} is not a valid QGC .plan file")

    # Flatten: top-level SimpleItems + sub-items expanded from ComplexItems
    flat: list = []
    for item in plan["mission"]["items"]:
        if item["type"] == "SimpleItem":
            flat.append(item)
        elif item["type"] == "ComplexItem":
            transect = item.get("TransectStyleComplexItem", {})
            flat.extend(transect.get("Items", []))

    return [_to_raw_item(seq, d) for seq, d in enumerate(flat)]


def _to_raw_item(seq: int, d: dict) -> RawMissionItem:
    """Convert a SimpleItem dict to a MAVSDK RawMissionItem."""
    p = d.get("params", [])

    def fp(i: int) -> float:
        v = p[i] if i < len(p) else None
        return float('nan') if v is None else float(v)

    frame = d.get("frame", 3)

    # MAV_FRAME_GLOBAL_RELATIVE_ALT (3): params[4]=lat, params[5]=lon in decimal
    # degrees.  MissionRaw expects integers scaled by 1e7.
    # MAV_FRAME_MISSION (2) and others: params[4]/[5] are plain numeric values,
    # not geographic coordinates — do NOT scale them.
    if frame == 3:
        x = 0 if len(p) <= 4 or p[4] is None else int(round(float(p[4]) * 1e7))
        y = 0 if len(p) <= 5 or p[5] is None else int(round(float(p[5]) * 1e7))
    else:
        x = 0 if len(p) <= 4 or p[4] is None else int(float(p[4]))
        y = 0 if len(p) <= 5 or p[5] is None else int(float(p[5]))

    return RawMissionItem(
        seq=seq,
        frame=frame,
        command=d["command"],
        current=1 if seq == 0 else 0,
        autocontinue=1 if d.get("autoContinue", True) else 0,
        param1=fp(0),
        param2=fp(1),
        param3=fp(2),
        param4=fp(3),
        x=x,
        y=y,
        z=fp(6),
        mission_type=0,
    )


# ── Connection / readiness helpers ───────────────────────────────────────────

async def wait_for_connection(drone: System, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    async for state in drone.core.connection_state():
        if state.is_connected:
            return
        if time.monotonic() > deadline:
            raise TimeoutError("Drone did not connect within timeout")


async def wait_for_global_position(drone: System, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            return
        if time.monotonic() > deadline:
            raise TimeoutError("Global position estimate not ready within timeout")


async def _is_armed(drone: System) -> bool:
    async for armed in drone.telemetry.armed():
        return armed
    return False


# ── Mission execution ─────────────────────────────────────────────────────────

async def execute_mission(drone: System, timeout_s: float = 600.0) -> None:
    """Start the uploaded mission and block until the vehicle disarms on the ground."""
    from mavsdk.telemetry import LandedState

    print("[mission] Starting mission")
    await drone.mission_raw.start_mission()

    # Print progress updates from a background task while we poll for completion
    progress_task = asyncio.create_task(_print_progress(drone))

    start = time.monotonic()
    try:
        while True:
            elapsed = time.monotonic() - start

            if elapsed > timeout_s:
                print("[mission] Timeout reached – aborting")
                progress_task.cancel()
                return

            async for landed in drone.telemetry.landed_state():
                on_ground = landed == LandedState.ON_GROUND
                break

            # Disarmed on the ground is the definitive "mission complete" signal
            if on_ground and elapsed > 5.0 and not await _is_armed(drone):
                print(f"[mission] Vehicle disarmed on ground at t={elapsed:.0f}s – done")
                break

            await asyncio.sleep(0.5)
    finally:
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass


async def _print_progress(drone: System) -> None:
    """Background coroutine that logs mission item progress."""
    try:
        async for progress in drone.mission_raw.mission_progress():
            print(f"[mission] progress: item {progress.current}/{progress.total}")
    except asyncio.CancelledError:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    plan_path = args.plan
    if not os.path.isabs(plan_path):
        plan_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), plan_path)

    if not os.path.isfile(plan_path):
        print(f"Error: plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[mission] Loading: {plan_path}")
    items = load_plan(plan_path)
    print(f"[mission] {len(items)} mission item(s) loaded")

    drone = System()
    print(f"[mission] Connecting to {args.address} ...")
    await drone.connect(system_address=args.address)
    await wait_for_connection(drone)
    print("[mission] Connected")

    print("[mission] Waiting for global position estimate ...")
    await wait_for_global_position(drone)
    print("[mission] Position OK")

    print("[mission] Uploading mission ...")
    await drone.mission_raw.upload_mission(items)
    print("[mission] Mission uploaded")

    print("[mission] Arming ...")
    await drone.action.arm()
    print("[mission] Armed")

    await execute_mission(drone, timeout_s=args.timeout)
    print("[mission] Mission complete")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Execute a QGroundControl .plan mission file via MAVSDK"
    )
    parser.add_argument("plan", help="Path to the .plan mission file")
    parser.add_argument(
        "--address",
        default="udp://:14540",
        help="MAVSDK connection address (default: udp://:14540)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Maximum flight time in seconds before aborting (default: 600)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n[mission] Aborted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
