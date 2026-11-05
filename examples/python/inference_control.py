#!/usr/bin/env python3
"""Control one part through Master INFERENCE using complete position targets.

Default: read-only preflight. With --execute, an already RUNNING task matching
--task-id is required. The example selects INFERENCE mode, runs a bounded demo
policy, checks feedback, and optionally stops the task with --stop-task.
It never enables devices, starts a task, publishes raw topics, or sends zeros
as a replacement for missing feedback. See docs/inference-example.md.
"""

import argparse
import json
import math
from pathlib import Path
import sys
import time

from north_sdk import (
    CommandChannel,
    ErrorCode,
    JointCommand,
    MasterPhase,
    MasterResult,
    NorthSDK,
    NorthSDKError,
    OperationMode,
    SdkConfig,
    Side,
)

PARTS = {"left_arm": 7, "right_arm": 7, "left_hand": 22, "right_hand": 22, "torso": 8}


def wait_for(read, predicate, description, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = read()
            if predicate(value):
                return value
        except NorthSDKError as exc:
            if exc.code != ErrorCode.STALE_STATE:
                raise
        time.sleep(0.02)
    raise RuntimeError("Timed out waiting for " + description)


def positions(client, count):
    values = list(client.latest_state(300).joints.position)
    if len(values) != count or not all(math.isfinite(x) for x in values):
        raise RuntimeError("Feedback must contain a complete finite position array")
    return values


def predict_positions(observation, baseline, joint, elapsed, duration, amplitude):
    """Replace with model inference; return every joint in fixed device order.

    This demo makes one smooth out-and-back excursion and holds the baseline after
    `duration`. A real policy may use observation as its input. Other joints retain
    valid baseline targets, rather than being omitted or implicitly filled with zero.
    """
    if len(observation) != len(baseline):
        raise ValueError("Invalid policy observation")
    target = baseline.copy()
    phase = min(elapsed / duration, 1.0)
    target[joint] += amplitude * math.sin(math.pi * phase) ** 2
    return target


def check_task(status, task_id, require_inference=True):
    if status.phase != MasterPhase.RUNNING or status.task_id != task_id:
        raise RuntimeError("Expected RUNNING task " + task_id + "; refusing motion")
    if require_inference and status.mode != OperationMode.INFERENCE:
        raise RuntimeError("Master mode changed away from INFERENCE; refusing motion")


def stop_selected_task(master, task_id):
    state = master.latest_status(500)
    if state.task_id != task_id:
        if state.phase == MasterPhase.RUNNING:
            raise RuntimeError("Another task is running; refusing to stop it")
        return
    if state.phase == MasterPhase.RUNNING:
        response = master.stop_task()
        if response.result != MasterResult.OK:
            raise RuntimeError("stop_task rejected: " + response.message)
    wait_for(
        master_status_reader(master),
        lambda s: s.phase != MasterPhase.RUNNING,
        "Master leaving RUNNING",
    )


def master_status_reader(master):
    return lambda: master.latest_status(500)


def run(args):
    config = SdkConfig()
    config.connect_endpoints = [args.endpoint]
    config.command_channel = CommandChannel.INFERENCE
    config.master_status_max_age_ms = 500
    config.master_timeout_ms = 5000
    report = {"part": args.part, "task_id": args.task_id, "sent": 0, "passed": False}
    with NorthSDK(config) as sdk:
        master = sdk.master()
        if args.part == "torso":
            part = sdk.torso()
        else:
            side = Side.LEFT if args.part.startswith("left_") else Side.RIGHT
            part = sdk.arm(side) if args.part.endswith("arm") else sdk.hand(side)
        subscriptions = [
            master.on_status(lambda _: None),
            part.on_state(lambda _: None),
        ]
        try:
            status = wait_for(
                master_status_reader(master), lambda _: True, "Master status"
            )
            wait_for(lambda: part.latest_state(300), lambda _: True, "part feedback")
            baseline = positions(part, PARTS[args.part])
            print(
                f"Master={status.phase.name} mode={status.mode.name} task={status.task_id!r}",
                flush=True,
            )
            if not args.execute:
                report.update(
                    preflight_only=True,
                    phase=status.phase.name,
                    mode=status.mode.name,
                    position=baseline,
                    passed=True,
                )
                return report
            check_task(status, args.task_id, require_inference=False)
            # Lifecycle services do not authorize motion by themselves: wait for the state stream.
            if status.mode != OperationMode.INFERENCE:
                response = master.set_mode(OperationMode.INFERENCE)
                if response.result != MasterResult.OK:
                    raise RuntimeError("set_mode rejected: " + response.message)
            status = wait_for(
                master_status_reader(master),
                lambda s: s.mode == OperationMode.INFERENCE,
                "INFERENCE status",
            )
            check_task(status, args.task_id)
            baseline = positions(part, PARTS[args.part])
            joint = (
                args.joint
                if args.joint is not None
                else (7 if "hand" in args.part else len(baseline) - 1)
            )
            start = next_tick = time.monotonic()
            peak = 0.0
            max_error = 0.0
            while (elapsed := time.monotonic() - start) < args.duration + args.hold:
                check_task(master.latest_status(500), args.task_id)
                observation = positions(part, len(baseline))
                if max(abs(a - b) for a, b in zip(observation, baseline)) > 0.10:
                    raise RuntimeError(
                        "Feedback moved more than the demo's 0.10 rad bound"
                    )
                target = predict_positions(
                    observation, baseline, joint, elapsed, args.duration, args.amplitude
                )
                command = JointCommand()
                command.position = (
                    target  # Full 7 / 22 / 8 values; all other arrays remain empty.
                )
                part.send_joint_command(command)  # SDK wraps this in inference/action.
                report["sent"] += 1
                peak = max(peak, abs(observation[joint] - baseline[joint]))
                max_error = max(max_error, abs(observation[joint] - target[joint]))
                # Do not replay missed frames if model inference or scheduling falls behind.
                next_tick = max(next_tick + 1.0 / args.hz, time.monotonic())
                time.sleep(max(0, next_tick - time.monotonic()))
            final = positions(part, len(baseline))
            return_error = abs(final[joint] - baseline[joint])
            report.update(
                joint=joint,
                target_excursion_rad=args.amplitude,
                observed_excursion_rad=peak,
                return_error_rad=return_error,
                max_tracking_error_rad=max_error,
            )
            if not (0.1 * args.amplitude < peak < 0.10 and return_error < 0.01):
                raise RuntimeError(
                    "Motion feedback did not meet demo acceptance bounds"
                )
            report["passed"] = True
            return report
        finally:
            # --stop-task authorizes closing the selected task even after an interrupted demo.
            try:
                if args.execute and args.stop_task:
                    stop_selected_task(master, args.task_id)
                    state = master.latest_status(500)
                    report["final_phase"] = state.phase.name
                    command = JointCommand()
                    command.position = positions(part, PARTS[args.part])
                    try:
                        part.send_joint_command(command)
                    except NorthSDKError as exc:
                        if exc.code != ErrorCode.MOTION_NOT_ALLOWED:
                            raise
                        report["stopped_motion_rejected"] = True
                    else:
                        raise RuntimeError(
                            "Motion after task stop was unexpectedly accepted"
                        )
            except BaseException:
                report["passed"] = False
                raise
            finally:
                for subscription in subscriptions:
                    subscription.close()
                if args.output:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(report, ensure_ascii=False), flush=True)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True, help="e.g. auto/ROBOT_HOST:7449")
    parser.add_argument("--part", choices=PARTS, default="right_arm")
    parser.add_argument(
        "--task-id", default="", help="exact ID of the externally prepared RUNNING task"
    )
    parser.add_argument(
        "--execute", action="store_true", help="send motion and select INFERENCE mode"
    )
    parser.add_argument(
        "--stop-task",
        action="store_true",
        help="stop the selected task on exit and check motion rejection",
    )
    parser.add_argument(
        "--joint", type=int, help="zero-based demo joint; full arrays are always sent"
    )
    parser.add_argument(
        "--amplitude",
        type=float,
        default=0.02,
        help="demo excursion in rad, maximum 0.03",
    )
    parser.add_argument(
        "--duration", type=float, default=3.0, help="out-and-back duration in seconds"
    )
    parser.add_argument(
        "--hold", type=float, default=1.5, help="baseline hold after trajectory"
    )
    parser.add_argument("--hz", type=float, default=40.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for key, low, high in (
        ("amplitude", 0.01, 0.03),
        ("duration", 3, 10),
        ("hold", 1, 5),
        ("hz", 10, 100),
    ):
        value = getattr(args, key)
        if not math.isfinite(value) or not low <= value <= high:
            parser.error(f"--{key} must be finite and between {low} and {high}")
    if args.joint is not None and not 0 <= args.joint < PARTS[args.part]:
        parser.error("--joint is outside the selected part")
    if args.execute and not args.task_id:
        parser.error(
            "--execute requires --task-id; INFERENCE mode alone does not start a task"
        )
    if args.stop_task and not args.execute:
        parser.error("--stop-task requires --execute")
    return args


if __name__ == "__main__":
    try:
        run(arguments())
    except (RuntimeError, NorthSDKError, KeyboardInterrupt) as exc:
        print("Control stopped: " + str(exc), file=sys.stderr)
        sys.exit(1)
