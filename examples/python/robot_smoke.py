#!/usr/bin/env python3
"""Read-only bring-up check for a real robot, following sharpa_interface.md section 15.

Subscribes to every state stream, reports per-stream rates, and optionally issues
read-only service queries. It never sends motion, mode, calibration, or power changes.
"""

import argparse
import collections
import sys
import threading
import time

from north_sdk import (
    LidarSource,
    NorthSDK,
    NorthSDKError,
    PowerChannelCommand,
    PowerNode,
    PowerOpCode,
    QueuePolicy,
    SdkConfig,
    Side,
    SubscribeOptions,
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zenoh-config", default="", help="Zenoh JSON5 config file")
    parser.add_argument("--endpoint", action="append", default=[],
                        help="Zenoh connect endpoint; may be repeated")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--query", action="store_true",
                        help="also call read-only services")
    parser.add_argument("--no-time-sync", action="store_true", help="skip host gPTP preparation")
    return parser.parse_args()


class Counters:
    def __init__(self):
        self._lock = threading.Lock()
        self._counts = collections.Counter()

    def counter(self, name):
        with self._lock:
            self._counts[name] += 0

        def tick(_sample):
            with self._lock:
                self._counts[name] += 1

        return tick

    def heartbeat(self, sample):
        with self._lock:
            self._counts["heartbeat/" + sample.subsystem] += 1

    def snapshot(self):
        with self._lock:
            return dict(self._counts)


def report_query(name, call):
    try:
        response = call()
    except NorthSDKError as error:
        print(f"  {name:<36}FAILED code={error.code} {error}")
        return
    print(f"  {name:<36}{'ok' if response.success else 'rejected'} {response.message}")


def main():
    args = parse_args()
    config = SdkConfig()
    config.time_sync.enabled = not args.no_time_sync
    config.zenoh_config_path = args.zenoh_config
    if args.endpoint:
        config.connect_endpoints = args.endpoint

    counters = Counters()
    latest = SubscribeOptions(QueuePolicy.LATEST_ONLY)
    with NorthSDK(config) as sdk:
        subscriptions = []

        def keep(name, subscribe, *leading):
            try:
                subscriptions.append(subscribe(*leading, counters.counter(name), latest))
            except NorthSDKError as error:
                print(f"subscribe {name} failed: {error}", file=sys.stderr)

        master = sdk.master()
        keep("master/status", master.on_status)
        keep("master/hardware", master.on_hardware_health)
        subscriptions.append(master.on_heartbeat("*", counters.heartbeat))
        keep("chassis/state", sdk.chassis().on_state)
        keep("torso/state", sdk.torso().on_state)
        for side, prefix in ((Side.LEFT, "left"), (Side.RIGHT, "right")):
            keep(f"{prefix}_arm/state", sdk.arm(side).on_state)
            hand = sdk.hand(side)
            keep(f"{prefix}_hand/state", hand.on_state)
            keep(f"{prefix}_hand/eskin_force", hand.on_eskin_force)
            keep(f"{prefix}_hand/tactile_force0", hand.on_tactile_force, 0)
        sensors = sdk.sensors()
        keep("sensors/imu", sensors.on_imu)
        keep("sensors/ultrasonic", sensors.on_ultrasonic)
        keep("sensors/tactile_skin", sensors.on_tactile_skin)
        keep("sensors/lidar_chassis_front", sensors.on_lidar, LidarSource.CHASSIS_FRONT)
        keep("sensors/lidar_chest_front", sensors.on_lidar, LidarSource.CHEST_FRONT)
        keep("sensors/lidar_chest_rear", sensors.on_lidar, LidarSource.CHEST_REAR)
        power = sdk.power()
        keep("power/chest", power.on_chest_state)
        keep("power/chassis", power.on_chassis_state)
        keep("power/battery", power.on_battery)

        print(f"listening for {args.seconds:g} s ...")
        time.sleep(args.seconds)
        counts = counters.snapshot()

        print("\nstreams (samples, Hz):")
        for name in sorted(counts):
            samples = counts[name]
            silent = "  (silent)" if samples == 0 else ""
            print(f"  {name:<36}{samples:>8}{samples / args.seconds:>10.1f}{silent}")

        if args.query:
            print("\nread-only services:")
            for node in (PowerNode.CHASSIS, PowerNode.BODY):
                command = PowerChannelCommand()
                command.node = node
                command.opcode = PowerOpCode.GET_STATUS
                report_query(f"power/get_status node={node.name}",
                             lambda command=command: power.channel_command(command))
            for side, prefix in ((Side.LEFT, "left"), (Side.RIGHT, "right")):
                report_query(f"{prefix}_hand/zero_calibration/status",
                             sdk.hand(side).zero_calibration_status)

        diagnostics = sdk.callback_diagnostics()
        print(f"\ncallbacks: dropped={diagnostics.dropped_callback_count} "
              f"coalesced={diagnostics.coalesced_callback_count}")
        for subscription in subscriptions:
            subscription.close()

    master_ok = counts["master/status"] > 0 and counts["master/hardware"] > 0
    heartbeat_ok = any(n.startswith("heartbeat/") and c > 0 for n, c in counts.items())
    if not (master_ok and heartbeat_ok):
        print("FAIL: master status, hardware health and at least one heartbeat are required",
              file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
