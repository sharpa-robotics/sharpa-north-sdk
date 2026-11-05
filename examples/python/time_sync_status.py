#!/usr/bin/env python3
"""Observe automatic gPTP preparation and read the local synchronized gPTP clock."""
import argparse
import json
import time

import north_sdk as north


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="auto/192.168.100.100:7449")
    parser.add_argument(
        "--interface",
        default="",
        help="North wired NIC; empty selects the endpoint route or a unique candidate",
    )
    parser.add_argument("--mode", choices=("hardware", "software"), default="software")
    parser.add_argument("--software-threshold-ns", type=int, default=1000000)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="close transport if initial synchronization fails",
    )
    parser.add_argument("--no-time-sync", action="store_true")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    config = north.SdkConfig()
    config.connect_endpoints = [args.endpoint]
    config.time_sync.interface = args.interface
    config.time_sync.mode = getattr(north.TimeSyncMode, args.mode.upper())
    config.time_sync.software_offset_threshold_ns = args.software_threshold_ns
    config.time_sync.enabled = not args.no_time_sync
    if args.strict:
        config.time_sync.failure_policy = north.TimeSyncFailurePolicy.FAIL_CONNECTION
    sdk = north.NorthSDK(config)
    try:
        try:
            sdk.connect()
        except north.NorthSDKError as error:
            print(
                json.dumps(
                    {
                        "event": "connect_error",
                        "code": int(error.code),
                        "message": str(error),
                        "connected": sdk.connected,
                    }
                ),
                flush=True,
            )
            if not sdk.connected:
                return 1
        for _ in range(args.seconds):
            diagnostic = sdk.time_sync_diagnostics()
            record = {
                "event": "time_sync",
                "state": str(diagnostic.state),
                "mode": str(diagnostic.mode),
                "clock_source": diagnostic.clock_source,
                "system_time_owned": diagnostic.system_time_owned,
                "code": int(diagnostic.error.code),
                "message": diagnostic.error.message,
                "interface": diagnostic.interface,
                "phc_device": diagnostic.phc_device,
                "offset_ns": diagnostic.offset_ns,
                "stable_samples": diagnostic.stable_samples,
                "required_samples": diagnostic.required_samples,
                "offset_threshold_ns": diagnostic.offset_threshold_ns,
                "sample_age_ms": diagnostic.sample_age_ms,
                "connected": sdk.connected,
            }
            try:
                record["robot_time_ns"] = sdk.robot_time_ns()
            except north.NorthSDKError as error:
                record["clock_error"] = {"code": int(error.code), "message": str(error)}
            print(json.dumps(record), flush=True)
            time.sleep(1)
    finally:
        sdk.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
