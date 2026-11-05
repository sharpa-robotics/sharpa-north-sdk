#!/usr/bin/env python3
"""Read-only left-arm state subscription."""

import argparse
import signal
import time

from north_sdk import NorthSDK, SdkConfig, Side


running = True


def stop(_signum, _frame):
    global running
    running = False


signal.signal(signal.SIGINT, stop)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    connection = parser.add_mutually_exclusive_group(required=True)
    connection.add_argument(
        "--endpoint",
        action="append",
        help="Zenoh endpoint such as auto/192.168.100.100:7449; may be repeated",
    )
    connection.add_argument(
        "--zenoh-config",
        default="",
        help="path to a native Zenoh JSON5 configuration file",
    )
    return parser.parse_args()


args = parse_args()
config = SdkConfig()
if args.endpoint:
    config.connect_endpoints = args.endpoint
else:
    config.zenoh_config_path = args.zenoh_config

with NorthSDK(config) as sdk:
    arm = sdk.arm(Side.LEFT)
    subscription = arm.on_state(
        lambda state: print(
            f"left arm seq={state.header.seq}, joints={len(state.joints.position)}"
        )
    )
    try:
        while running:
            time.sleep(0.1)
    finally:
        subscription.close()
