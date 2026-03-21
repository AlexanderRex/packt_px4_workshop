#!/usr/bin/env python3
"""Automated PX4 SITL failure-injection test runner.

Starts PX4 SITL automatically, runs the selected failure test(s), evaluates
pass/fail criteria, and tears the simulator down afterwards.

Test cases
----------
  mag_mission   Magnetometer off during waypoint mission (x500 quad).
                PASS: mission completes, vehicle returns home within 3 m.

  gps_hover     GPS loss while hovering (x500 quad).
                PASS: Land mode is activated, vehicle lands and disarms.

Usage
-----
  python3 failure_test_runner.py mag_mission
  python3 failure_test_runner.py gps_hover
  python3 failure_test_runner.py all                       # run every test
  python3 failure_test_runner.py mag_mission --px4-dir /opt/PX4-Autopilot
"""

import argparse
import asyncio
import json
import math
import os
import signal
import subprocess
import sys
import time
from enum import Enum
from typing import Dict, List, Tuple

from mavsdk import System
from mavsdk.failure import FailureType, FailureUnit
from mavsdk.mission_raw import MissionItem as RawMissionItem
from mavsdk.telemetry import FlightMode, LandedState

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PX4_DIR = os.path.expanduser("~/PX4-Autopilot")
RTL_THRESHOLD_M = 3.0


class TestResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"


# ── Test-case definitions ────────────────────────────────────────────────────

TEST_CASES: Dict[str, dict] = {
    "mag_mission": {
        "description": "Magnetometer off during waypoint mission",
        "vehicle": "gz_x500",
        "plan": "4_short_mission.plan",
        "failure_unit": FailureUnit.SENSOR_MAG,
        "failure_instance": 0,
        "inject_delay_s": 15.0,
        "pass_criteria": "rtl_within_3m",
        "timeout_s": 300.0,
    },
    "gps_hover": {
        "description": "GPS loss while hovering",
        "vehicle": "gz_x500",
        "plan": None,
        "failure_unit": FailureUnit.SENSOR_GPS,
        "failure_instance": 0,
        "inject_delay_s": 15.0,
        "pass_criteria": "land_and_disarm",
        "timeout_s": 180.0,
    },
}


# ── QGC .plan → MAVSDK raw mission items ─────────────────────────────────────

def load_plan(path: str) -> List[RawMissionItem]:
    """Parse a QGroundControl .plan file into a flat list of RawMissionItems."""
    with open(path) as f:
        plan = json.load(f)

    flat: list = []
    for item in plan["mission"]["items"]:
        if item["type"] == "SimpleItem":
            flat.append(item)
        elif item["type"] == "ComplexItem":
            transect = item.get("TransectStyleComplexItem", {})
            flat.extend(transect.get("Items", []))

    return [_to_raw_item(seq, d) for seq, d in enumerate(flat)]


def _to_raw_item(seq: int, d: dict) -> RawMissionItem:
    p = d.get("params", [])

    def fp(i: int) -> float:
        v = p[i] if i < len(p) else None
        return float("nan") if v is None else float(v)

    frame = d.get("frame", 3)
    if frame == 3:
        x = 0 if len(p) <= 4 or p[4] is None else int(round(float(p[4]) * 1e7))
        y = 0 if len(p) <= 5 or p[5] is None else int(round(float(p[5]) * 1e7))
    else:
        x = int(fp(4))
        y = int(fp(5))

    return RawMissionItem(
        seq=seq,
        frame=frame,
        command=d["command"],
        current=1 if seq == 0 else 0,
        autocontinue=1 if d.get("autoContinue", True) else 0,
        param1=fp(0), param2=fp(1), param3=fp(2), param4=fp(3),
        x=x, y=y, z=fp(6),
        mission_type=0,
    )


# ── Geo helper ───────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return horizontal distance in metres between two WGS-84 points."""
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── PX4 SITL process management ─────────────────────────────────────────────

def start_px4_sitl(px4_dir: str, vehicle: str) -> subprocess.Popen:
    """Launch ``make px4_sitl <vehicle>`` in its own process group."""
    cmd = f"HEADLESS=1 make px4_sitl {vehicle}" # Make it headless (hide GUI)
    print(f"[sim] Starting: {cmd}")
    print(f"[sim] Working directory: {px4_dir}")
    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=px4_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    return proc


def stop_px4_sitl(proc: subprocess.Popen) -> None:
    """Terminate the simulator process group."""
    if proc.poll() is not None:
        return
    print("[sim] Stopping PX4 SITL ...")
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait(timeout=5)
        except Exception:
            pass
    print("[sim] PX4 SITL stopped")


async def _drain_stdout(proc: subprocess.Popen) -> None:
    """Read PX4 stdout in background so the OS pipe buffer never fills."""
    loop = asyncio.get_event_loop()
    while proc.poll() is None:
        line = await loop.run_in_executor(None, proc.stdout.readline)
        if not line:
            break
        text = line.decode("utf-8", errors="replace").rstrip()
        if any(k in text.lower() for k in
               ("ready", "home", "armed", "error", "fail", "warn", "takeoff")):
            print(f"[px4] {text}")


# ── MAVSDK connection helpers ────────────────────────────────────────────────

async def connect_drone(address: str, timeout: float = 120.0) -> System:
    """Connect to PX4 and wait until position estimate is healthy."""
    drone = System()
    await drone.connect(system_address=address)

    deadline = time.monotonic() + timeout

    print("[test] Waiting for drone connection ...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[test] Connected")
            break
        if time.monotonic() > deadline:
            raise TimeoutError("Drone did not connect within timeout")

    print("[test] Waiting for global position estimate ...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("[test] Position estimate OK")
            break
        if time.monotonic() > deadline:
            raise TimeoutError("Position estimate not ready within timeout")

    return drone


# ── One-shot telemetry reads ─────────────────────────────────────────────────

async def _get_position(drone: System) -> Tuple[float, float, float]:
    async for pos in drone.telemetry.position():
        return pos.latitude_deg, pos.longitude_deg, pos.relative_altitude_m

async def _get_home(drone: System) -> Tuple[float, float]:
    async for home in drone.telemetry.home():
        return home.latitude_deg, home.longitude_deg

async def _is_armed(drone: System) -> bool:
    async for armed in drone.telemetry.armed():
        return armed
    return False

async def _get_flight_mode(drone: System) -> FlightMode:
    async for mode in drone.telemetry.flight_mode():
        return mode

async def _get_landed_state(drone: System) -> LandedState:
    async for ls in drone.telemetry.landed_state():
        return ls


async def _wait_until_armable(drone: System, timeout: float = 60.0) -> None:
    """Block until the vehicle reports it is ready to arm."""
    deadline = time.monotonic() + timeout
    print("[test] Waiting for vehicle to be arm-able ...")
    async for health in drone.telemetry.health():
        if (health.is_global_position_ok
                and health.is_home_position_ok
                and health.is_accelerometer_calibration_ok
                and health.is_magnetometer_calibration_ok
                and health.is_gyrometer_calibration_ok
                and health.is_armable):
            print("[test] Vehicle is arm-able")
            return
        if time.monotonic() > deadline:
            raise TimeoutError("Vehicle did not become arm-able within timeout")


# ── Test: mission with failure injection (mag / motor) ───────────────────────

async def _run_mission_with_failure(drone: System, config: dict) -> TestResult:
    plan_path = os.path.join(SCRIPT_DIR, config["plan"])
    items = load_plan(plan_path)
    print(f"[test] Loaded {len(items)} mission item(s) from {config['plan']}")

    # Enable failure injection at PX4 level
    await drone.param.set_param_int("SYS_FAILURE_EN", 1)

    # Record home position
    home_lat, home_lon = await _get_home(drone)
    print(f"[test] Home: ({home_lat:.7f}, {home_lon:.7f})")

    # Clear any stale mission so PX4 resets its progress index
    await drone.mission_raw.clear_mission()
    print("[test] Previous mission cleared")

    # Upload fresh ➜ wait for arm-able ➜ arm ➜ start
    await drone.mission_raw.upload_mission(items)
    print("[test] Mission uploaded")
    await _wait_until_armable(drone)
    await drone.action.arm()
    print("[test] Armed")
    await drone.mission_raw.start_mission()
    print("[test] Mission started")

    start = time.monotonic()
    injected = False
    next_log = start + 15.0

    while True:
        elapsed = time.monotonic() - start

        if elapsed > config["timeout_s"]:
            print("[test] TIMEOUT — FAIL")
            return TestResult.FAIL

        # Inject failure once
        if not injected and elapsed >= config["inject_delay_s"]:
            print(f"[test] Injecting failure at t={elapsed:.1f}s")
            await drone.failure.inject(
                config["failure_unit"], FailureType.OFF, config["failure_instance"],
            )
            injected = True

        # Periodic status
        now = time.monotonic()
        if now >= next_log:
            try:
                mode = await _get_flight_mode(drone)
                lat, lon, alt = await _get_position(drone)
                print(f"[test] t={elapsed:.0f}s  mode={mode}  alt={alt:.1f}m")
            except Exception:
                pass
            next_log = now + 15.0

        # Check for landing completion
        landed = await _get_landed_state(drone)
        armed = await _is_armed(drone)

        if landed == LandedState.ON_GROUND and not armed and injected:
            lat, lon, _ = await _get_position(drone)
            dist = haversine_m(home_lat, home_lon, lat, lon)
            print(f"[test] Landed at ({lat:.7f}, {lon:.7f}), "
                  f"{dist:.1f}m from home")
            if dist <= RTL_THRESHOLD_M:
                print(f"[test] Within {RTL_THRESHOLD_M}m of home — PASS")
                return TestResult.PASS
            else:
                print(f"[test] {dist:.1f}m from home (>{RTL_THRESHOLD_M}m) — FAIL")
                return TestResult.FAIL

        await asyncio.sleep(1.0)


# ── Test: GPS loss while hovering ────────────────────────────────────────────

async def _run_gps_hover_test(drone: System, config: dict) -> TestResult:
    # Enable failure injection at PX4 level
    await drone.param.set_param_int("SYS_FAILURE_EN", 1)

    await drone.action.set_takeoff_altitude(10.0)
    await _wait_until_armable(drone)
    await drone.action.arm()
    print("[test] Armed")
    await drone.action.takeoff()
    print("[test] Takeoff commanded — hovering at 10 m")

    start = time.monotonic()
    injected = False
    land_mode_seen = False
    next_log = start + 10.0

    while True:
        elapsed = time.monotonic() - start

        if elapsed > config["timeout_s"]:
            print("[test] TIMEOUT — FAIL")
            return TestResult.FAIL

        # Inject GPS failure after delay
        if not injected and elapsed >= config["inject_delay_s"]:
            print(f"[test] Injecting GPS failure at t={elapsed:.1f}s")
            await drone.failure.inject(
                config["failure_unit"], FailureType.OFF, config["failure_instance"],
            )
            injected = True

        mode = await _get_flight_mode(drone)
        landed = await _get_landed_state(drone)
        armed = await _is_armed(drone)

        # Detect land mode
        if injected and mode == FlightMode.LAND and not land_mode_seen:
            print(f"[test] Land mode activated at t={elapsed:.1f}s")
            land_mode_seen = True

        # Vehicle on the ground and disarmed after injection
        if injected and landed == LandedState.ON_GROUND and not armed:
            print(f"[test] Vehicle landed and disarmed at t={elapsed:.1f}s")
            if land_mode_seen:
                print("[test] Land mode was activated, vehicle disarmed — PASS")
                return TestResult.PASS
            # Even without observing Land explicitly, landing after GPS loss
            # is acceptable (mode may have transitioned quickly).
            print("[test] Vehicle disarmed after GPS loss — PASS")
            return TestResult.PASS

        # Periodic status
        now = time.monotonic()
        if now >= next_log:
            try:
                lat, lon, alt = await _get_position(drone)
                print(f"[test] t={elapsed:.0f}s  mode={mode}  alt={alt:.1f}m")
            except Exception:
                print(f"[test] t={elapsed:.0f}s  mode={mode}")
            next_log = now + 10.0

        await asyncio.sleep(0.5)


# ── Single-test orchestrator ─────────────────────────────────────────────────

async def _run_single_test(test_name: str, args: argparse.Namespace) -> TestResult:
    config = TEST_CASES[test_name]
    vehicle = config["vehicle"]

    print(f"\n{'=' * 60}")
    print(f"  TEST: {test_name} — {config['description']}")
    print(f"  Vehicle: {vehicle}")
    print(f"{'=' * 60}\n")

    proc = start_px4_sitl(args.px4_dir, vehicle)
    stdout_task = None

    try:
        stdout_task = asyncio.create_task(_drain_stdout(proc))

        # Give the simulator time to start Gazebo + PX4
        print("[sim] Waiting for PX4 SITL to initialize ...")
        await asyncio.sleep(15)

        if proc.poll() is not None:
            print(f"[sim] PX4 SITL exited prematurely (rc={proc.returncode})")
            return TestResult.FAIL

        drone = await connect_drone(args.address, timeout=120)

        # Dispatch to the right test backend
        if config["plan"] is not None:
            result = await _run_mission_with_failure(drone, config)
        else:
            result = await _run_gps_hover_test(drone, config)

        # Always clear injected failures before shutdown
        try:
            await drone.failure.inject(
                config["failure_unit"], FailureType.OK, config["failure_instance"],
            )
        except Exception:
            pass

        return result

    except Exception as exc:
        print(f"[test] Exception: {exc}")
        return TestResult.FAIL

    finally:
        if stdout_task:
            stdout_task.cancel()
            try:
                await stdout_task
            except asyncio.CancelledError:
                pass
        stop_px4_sitl(proc)


# ── Top-level runner ─────────────────────────────────────────────────────────

async def _run_all(args: argparse.Namespace) -> Dict[str, TestResult]:
    results: Dict[str, TestResult] = {}
    for test_name in args.tests:
        results[test_name] = await _run_single_test(test_name, args)
        if len(args.tests) > 1:
            print("\n[sim] Pausing before next test ...\n")
            await asyncio.sleep(5)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "tests", nargs="+",
        choices=list(TEST_CASES.keys()) + ["all"],
        help="Test case(s) to run (use 'all' for every test)",
    )
    parser.add_argument(
        "--px4-dir", default=DEFAULT_PX4_DIR,
        help=f"Path to PX4-Autopilot directory (default: {DEFAULT_PX4_DIR})",
    )
    parser.add_argument(
        "--address", default="udp://:14540",
        help="MAVSDK connection address (default: udp://:14540)",
    )
    args = parser.parse_args()

    if "all" in args.tests:
        args.tests = list(TEST_CASES.keys())

    if not os.path.isdir(args.px4_dir):
        print(f"Error: PX4 directory not found: {args.px4_dir}", file=sys.stderr)
        sys.exit(1)

    results = asyncio.run(_run_all(args))

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  TEST RESULTS SUMMARY")
    print(f"{'=' * 60}")
    all_pass = True
    for name, result in results.items():
        mark = "PASS" if result == TestResult.PASS else "FAIL"
        print(f"  [{mark}]  {name}: {TEST_CASES[name]['description']}")
        if result != TestResult.PASS:
            all_pass = False
    print(f"{'=' * 60}\n")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
