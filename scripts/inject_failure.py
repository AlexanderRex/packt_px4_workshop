#!/usr/bin/env python3
"""Inject failures into a running PX4 SITL session via MAVSDK failure plugin.

Usage:
    python3 inject_failure.py <unit> <type> [--instance N]

Units:  gyro, accel, mag, baro, gps, battery, motor, rc_signal
Types:  ok, off, stuck, garbage, wrong, slow, delayed, intermittent
"""

import asyncio
import argparse
from mavsdk import System
from mavsdk.failure import FailureType, FailureUnit

UNITS = {
    "gyro": FailureUnit.SENSOR_GYRO,
    "accel": FailureUnit.SENSOR_ACCEL,
    "mag": FailureUnit.SENSOR_MAG,
    "baro": FailureUnit.SENSOR_BARO,
    "gps": FailureUnit.SENSOR_GPS,
    "airspeed": FailureUnit.SENSOR_AIRSPEED,
    "battery": FailureUnit.SYSTEM_BATTERY,
    "motor": FailureUnit.SYSTEM_MOTOR,
    "rc_signal": FailureUnit.SYSTEM_RC_SIGNAL,
}

TYPES = {
    "ok": FailureType.OK,
    "off": FailureType.OFF,
    "stuck": FailureType.STUCK,
    "garbage": FailureType.GARBAGE,
    "wrong": FailureType.WRONG,
    "slow": FailureType.SLOW,
    "delayed": FailureType.DELAYED,
    "intermittent": FailureType.INTERMITTENT,
}


async def main():
    parser = argparse.ArgumentParser(description="Inject failure via MAVSDK")
    parser.add_argument("unit", choices=UNITS.keys(), help="Failure unit")
    parser.add_argument("type", choices=TYPES.keys(), help="Failure type")
    parser.add_argument("--instance", type=int, default=0, help="Instance (0=all). Default: 0")
    args = parser.parse_args()

    drone = System()
    await drone.connect(system_address="udp://:14540")

    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected to drone")
            break

    unit = UNITS[args.unit]
    ft = TYPES[args.type]
    print(f"Injecting: {args.unit} {args.type} (instance={args.instance})")

    try:
        await drone.failure.inject(unit, ft, args.instance)
        print("Failure injected")
    except Exception as e:
        print(f"Failed: {e}")
        return

    input("Press Enter to restore...")
    try:
        await drone.failure.inject(unit, FailureType.OK, args.instance)
        print("Restored")
    except Exception as e:
        print(f"Restore failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
