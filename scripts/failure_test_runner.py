#!/usr/bin/env python3
"""Minimal MAVSDK test runner for failure injection during missions.

Uploads a QGC .plan mission, arms, takes off, injects a failure mid-flight,
and monitors whether PX4 handles the failure correctly (e.g. RTL / land).
"""

import argparse
import asyncio
import json
import os
import sys
import time
from enum import Enum
from typing import List, Optional

from mavsdk import System
from mavsdk.failure import FailureType, FailureUnit
from mavsdk.mission_raw import MissionItem as RawMissionItem

# ── Lookup tables for CLI ────────────────────────────────────────────────────

FAILURE_UNITS = {
    "gyro":      FailureUnit.SENSOR_GYRO,
    "accel":     FailureUnit.SENSOR_ACCEL,
    "mag":       FailureUnit.SENSOR_MAG,
    "baro":      FailureUnit.SENSOR_BARO,
    "gps":       FailureUnit.SENSOR_GPS,
    "airspeed":  FailureUnit.SENSOR_AIRSPEED,
    "battery":   FailureUnit.SYSTEM_BATTERY,
    "motor":     FailureUnit.SYSTEM_MOTOR,
    "rc_signal": FailureUnit.SYSTEM_RC_SIGNAL,
}

class TestResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"


# ── QGC .plan → MAVSDK raw mission items ─────────────────────────────────────

def load_plan(path: str) -> List[RawMissionItem]:
    """Parse a QGroundControl .plan file into MAVSDK RawMissionItems."""
    with open(path, "r") as f:
        plan = json.load(f)

    items: List[RawMissionItem] = []
    for idx, item in enumerate(plan["mission"]["items"]):
        params = item["params"]
        raw = RawMissionItem(
            seq=idx,
            frame=item.get("frame", 3),
            command=item["command"],
            current=1 if idx == 0 else 0,
            autocontinue=int(item.get("autoContinue", True)),
            param1=float(params[0] or 0),
            param2=float(params[1] or 0),
            param3=float(params[2] or 0),
            param4=float(params[3] or 0),
            x=int(float(params[4] or 0) * 1e7),
            y=int(float(params[5] or 0) * 1e7),
            z=float(params[6] or 0),
            mission_type=0,
        )
        items.append(raw)
    return items


# ── Core test logic ──────────────────────────────────────────────────────────

async def wait_for_connection(drone: System, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    async for state in drone.core.connection_state():
        if state.is_connected:
            return
        if time.monotonic() > deadline:
            raise TimeoutError("Drone did not connect within timeout")


async def wait_for_global_position(drone: System, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            return
        if time.monotonic() > deadline:
            raise TimeoutError("Global position estimate not ready within timeout")


async def monitor_mission_and_inject(
    drone: System,
    unit: FailureUnit,
    instance: int,
    delay_s: float,
    duration_s: float,
    timeout_s: float,
) -> TestResult:
    """Run the uploaded mission, inject a failure after *delay_s* seconds,
    restore after *duration_s* seconds, and wait for the vehicle to land."""

    print("[runner] Starting mission")
    await drone.mission_raw.start_mission()

    start = time.monotonic()
    injected = False
    restored = False

    while True:
        elapsed = time.monotonic() - start

        # Safety timeout
        if elapsed > timeout_s:
            print("[runner] TIMEOUT reached – aborting")
            return TestResult.FAIL

        # Inject failure
        if not injected and elapsed >= delay_s:
            print(f"[runner] Injecting failure at t={elapsed:.1f}s")
            await drone.failure.inject(unit, FailureType.OFF, instance)
            injected = True
            inject_time = time.monotonic()

        # Restore after duration
        if injected and not restored:
            if time.monotonic() - inject_time >= duration_s:
                print(f"[runner] Restoring (duration={duration_s}s elapsed)")
                await drone.failure.inject(unit, FailureType.OK, instance)
                restored = True

        # Check if landed
        async for landed in drone.telemetry.landed_state():
            # Consume one update then break to keep the outer loop going
            from mavsdk.telemetry import LandedState
            if landed == LandedState.ON_GROUND and elapsed > delay_s + 2:
                print(f"[runner] Vehicle landed at t={elapsed:.1f}s")
                # Check armed state – fully disarmed means mission/failsafe complete
                if not await _is_armed(drone):
                    print("[runner] Vehicle disarmed – test complete")
                    return TestResult.PASS
            break

        await asyncio.sleep(0.5)


async def _is_armed(drone: System) -> bool:
    async for armed in drone.telemetry.armed():
        return armed
    return False


# ── Main entry point ─────────────────────────────────────────────────────────

async def run_test(args: argparse.Namespace) -> TestResult:
    plan_path = args.plan
    if not os.path.isabs(plan_path):
        plan_path = os.path.join(os.path.dirname(__file__), plan_path)

    if not os.path.isfile(plan_path):
        print(f"Plan file not found: {plan_path}")
        return TestResult.FAIL

    # Parse mission
    mission_items = load_plan(plan_path)
    print(f"[runner] Loaded {len(mission_items)} mission item(s) from {os.path.basename(plan_path)}")

    # Connect
    drone = System()
    address = args.address
    print(f"[runner] Connecting to {address} ...")
    await drone.connect(system_address=address)
    await wait_for_connection(drone)
    print("[runner] Connected")

    # Wait for position
    print("[runner] Waiting for global position estimate ...")
    await wait_for_global_position(drone, timeout=60)
    print("[runner] Position OK")

    # Upload mission
    print("[runner] Uploading mission ...")
    await drone.mission_raw.upload_mission(mission_items)
    print("[runner] Mission uploaded")

    # Arm
    print("[runner] Arming ...")
    await drone.action.arm()

    unit = FAILURE_UNITS[args.unit]

    result = await monitor_mission_and_inject(
        drone,
        unit=unit,
        instance=args.instance,
        delay_s=args.delay,
        duration_s=args.duration,
        timeout_s=args.timeout,
    )

    # Ensure failure is always cleared on exit
    try:
        await drone.failure.inject(unit, FailureType.OK, args.instance)
    except Exception:
        pass

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minimal MAVSDK test runner: fly a .plan mission with failure injection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("plan", help="Path to a QGC .plan file")
    parser.add_argument("unit", choices=FAILURE_UNITS.keys(), help="Failure unit")
    parser.add_argument("--instance", type=int, default=0,
                        help="Sensor instance (0 = all). Default: 0")
    parser.add_argument("--delay", type=float, default=10.0,
                        help="Seconds after mission start before injecting. Default: 10")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="Seconds to keep the failure active (0 = until end). Default: 0")
    parser.add_argument("--timeout", type=float, default=180.0,
                        help="Overall test timeout in seconds. Default: 180")
    parser.add_argument("--address", type=str, default="udp://:14540",
                        help="MAVSDK connection string. Default: udp://:14540")
    args = parser.parse_args()

    # If duration is 0, set it to match (timeout - delay) so restosal happens at the end
    if args.duration <= 0:
        args.duration = args.timeout

    result = asyncio.run(run_test(args))

    if result == TestResult.PASS:
        print(f"\n=== TEST {result.value} ===")
        sys.exit(0)
    else:
        print(f"\n=== TEST {result.value} ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
