# Application Development

North SDK

[SDK Overview](SDK%20Overview.md) · [Application Development](Application%20Development.md) · [Software Service Interface](Software%20Service%20Interface.md) · [Example Code Reference](Example%20Code%20Reference.md) · [中文](../../zh/SDK/%E5%BA%94%E7%94%A8%E5%BC%80%E5%8F%91.md)

## Contents

- [Packages and runtime environment](#packages-and-runtime-environment)
- [Quick Start](#quick-start)
  - [1. Connect the robot](#1-connect-the-robot)
  - [2. Set the SDK and robot address](#2-set-the-sdk-and-robot-address)
  - [3. Run the read-only diagnostic](#3-run-the-read-only-diagnostic)
  - [4. Receive left-arm state](#4-receive-left-arm-state)
  - [Python users](#python-users)
  - [Build the C++ example (optional)](#build-the-c-example-optional)
  - [Completion criteria](#completion-criteria)
  - [First-run troubleshooting](#first-run-troubleshooting)
- [Time synchronization](#time-synchronization)
- [Video environment setup](#video-environment-setup)
  - [NVIDIA drivers and bundled runtime](#nvidia-drivers-and-bundled-runtime)
  - [Check the video environment](#check-the-video-environment)
  - [Receive the first video stream](#receive-the-first-video-stream)
- [Subscriptions and caches](#subscriptions-and-caches)
- [Service results](#service-results)
- [Motion control](#motion-control)
  - [Prepare and end a task](#prepare-and-end-a-task)
  - [Joint arrays and coordinates](#joint-arrays-and-coordinates)
- [Motion protection and trajectory processing](#motion-protection-and-trajectory-processing)
  - [Command admission and fault protection](#command-admission-and-fault-protection)
  - [Position ranges and velocity constraints](#position-ranges-and-velocity-constraints)
  - [Smoothing continuous position commands](#smoothing-continuous-position-commands)
- [Shutdown and reconnect](#shutdown-and-reconnect)
- [Troubleshooting](#troubleshooting)

## Packages and runtime environment

The package contains C++ headers and shared libraries, Python bindings, examples, and video runtime dependencies. This manual recommends the following development environment.

| Development system | Recommended Python interpreter | C++ API |
| --- | --- | --- |
| Ubuntu 22.04 LTS x86_64 | CPython 3.10.x | C++17 |
| Ubuntu 24.04 LTS x86_64 | CPython 3.12.x | C++17 |

Other Linux x86_64 environments must meet the minimum runtime symbol requirements recorded in the package BUILD-MANIFEST.json. Compatibility requires validation in the target environment.

The development environment provides the Python interpreter. Its minor version and architecture must match a binding included in the package, as listed in the package manifest. This also applies to virtual environments. Python is unnecessary for C++-only applications.

Extract the entire package into a dedicated directory and preserve its structure. GStreamer runtime libraries and required video plugins are bundled; installing system GStreamer is unnecessary. NVIDIA drivers are not bundled; see [Video environment setup](#video-environment-setup).

| Directory or file | Purpose |
| --- | --- |
| `include/north_sdk/` | Public C++ headers |
| `lib/` | SDK and supporting runtime libraries |
| `lib/python/` | Bindings for the target Python version |
| `lib/video-runtime/` | Bundled video libraries, plugins and tools |
| `bin/` | C++ bring-up and connection diagnostic programs |
| `examples/python/` | Python examples and environment check script |
| `manual/` | User manual |
| `setup.bash` | Load this package's library, Python and video plugin paths |
| `BUILD-MANIFEST.json` | Build information, Python ABI and dependencies |

To update, replace the complete package, reload its environment and recheck import, read-only connection and state reception.

## Quick Start

This section connects to the robot and receives the first state stream with the fewest steps, without sending motion, mode, calibration or power commands.

> **Safety:** On a first connection, run only the read-only programs in this section. Do not call `send_*()`, `set_mode()`, `enable()`, `reset()`, calibration or Power management APIs.

### 1. Connect the robot

Connect the development computer to the Ethernet port led out from the switch on the robot’s rear right side. Power on the robot and wait for its software to start. State communication and time synchronization both use this wired connection.

The default robot IP is `192.168.100.100`; the SDK communicates over UDP port `7449`. For a direct connection, open Ubuntu Settings → Network → Wired → IPv4 and select Manual. For example, set the computer to `192.168.100.10` with netmask `255.255.255.0`, leaving gateway and DNS blank. Check that the address is unused. Use the actual subnet if changed at delivery.

### 2. Set the SDK and robot address

Replace the SDK path below with your extraction directory. Use the default robot address unless changed for your delivery.

```bash
export NORTHSDK_PREFIX=/absolute/path/to/north-sdk
export NORTHSDK_ENDPOINT=udp/192.168.100.100:7449
source "$NORTHSDK_PREFIX/setup.bash"
```

Environment variables apply only to this terminal and its child processes; configure new terminals separately.

`NORTHSDK_PREFIX` points to the extracted SDK root containing `setup.bash`.

Before first use of automatic time synchronization, run this one-time host setup from the ordinary development account:

```bash
sudo "$NORTHSDK_PREFIX/tools/setup-host" --user "$USER"
"$NORTHSDK_PREFIX/tools/setup-host" check
```

This installs the host time-sync component and authorizes the current account. Applications subsequently run without `sudo`; repeat setup from the new package after an SDK update. Software synchronization may step system time and temporarily pause system time services. Their previous service state is restored after the last time-sync session closes. See [Time synchronization](#time-synchronization) to disable it.

### 3. Run the read-only diagnostic

```bash
"$NORTHSDK_PREFIX/bin/north_sdk_robot_smoke" \
  --endpoint "$NORTHSDK_ENDPOINT" --seconds 5
```

When the basic connection is healthy, the final line is:

```text
PASS
```

`PASS` means Master status, hardware health and at least one heartbeat were received. Check each required device stream against the actual configuration; `silent` means no sample was received for that stream.

### 4. Receive left-arm state

```bash
"$NORTHSDK_PREFIX/bin/north_sdk_quickstart" "$NORTHSDK_ENDPOINT"
```

When the left arm is online and publishing, output resembles:

```text
left arm seq=1234 joints=7
```

Press Ctrl+C to exit. If the robot has no left arm, use streams for devices actually installed as reported by `robot_smoke`.

### Python users

Run `python3 --version` and check that the interpreter minor version matches an included binding. CPython 3.10.x on Ubuntu 22.04 and CPython 3.12.x on Ubuntu 24.04 are recommended; virtual environments must also use an interpreter minor version supported by the package.

Step 2 already sets the Python module path. Run the example directly:

```bash
python3 "$NORTHSDK_PREFIX/examples/python/quickstart.py" \
  --endpoint "$NORTHSDK_ENDPOINT"
```

### Build the C++ example (optional)

After the prebuilt program succeeds, verify the C++ development environment with one `g++` command:

```bash
g++ -std=c++17 "$NORTHSDK_PREFIX/examples/cpp/quickstart.cpp" \
  -I"$NORTHSDK_PREFIX/include" -L"$NORTHSDK_PREFIX/lib" -lnorth_sdk \
  -Wl,-rpath,"$NORTHSDK_PREFIX/lib" \
  -o north_sdk_quickstart

./north_sdk_quickstart "$NORTHSDK_ENDPOINT"
```

`-L` locates link libraries and `-Wl,-rpath` records the SDK library directory. Still load `setup.bash` before running to select bundled video libraries and plugins. Rebuild or update the runtime path if the SDK directory moves.

### Completion criteria

The read-only bring-up is complete when:

- `robot_smoke` reports `PASS`;
- streams required by the application continuously receive samples;
- the C++ or Python example exits cleanly;

Continue with the subscription and motion guidance below, then choose task examples in [Example Code Reference](Example%20Code%20Reference.md). If bring-up fails, see [First-run troubleshooting](#first-run-troubleshooting) below.

### First-run troubleshooting

For first-connection, startup or Python import failures, check the package, shared libraries and network in that order. These checks reuse the environment from step 2 and are needed only on failure.

#### Package or version

```bash
test -f "$NORTHSDK_PREFIX/include/north_sdk/NorthSDK.h"
test -f "$NORTHSDK_PREFIX/lib/libnorth_sdk.so"
cat "$NORTHSDK_PREFIX/Version"
```

Python import check:

```bash
python3 -c "import north_sdk; print(north_sdk.NorthSDK.version())"
```

If you see `No module named 'north_sdk._north_sdk'`, check that the extension exists and matches your Python version:

```bash
python3 --version
ls "$NORTHSDK_PREFIX"/lib/python/north_sdk/_north_sdk*.so
```

Check the package manifest and extensions provided in `lib/python/north_sdk/`. A `cpython-312` filename tag requires CPython 3.12. Switch to a matching interpreter or obtain a package containing the required binding. Replace the package if an extension listed in its manifest is missing.

#### Shared libraries

```bash
ldd "$NORTHSDK_PREFIX/bin/north_sdk_quickstart" | \
  grep -E 'north_sdk|zenoh|protobuf|not found'
```

North SDK, Zenoh and Protobuf should come from one package. If a library is `not found` or resolves to another SDK/ROS environment, fix `LD_LIBRARY_PATH`.

#### Network

```bash
ip route get 192.168.100.100
```

Replace the IP with the actual robot address and verify the intended interface. Use `ping` only when ICMP is permitted. A failed ping does not necessarily mean Zenoh is unavailable; `robot_smoke` is authoritative.

## Time synchronization

The SDK prepares gPTP synchronization after establishing communication. Complete the [host setup](#2-set-the-sdk-and-robot-address) before first use.

| Option | Usage |
| --- | --- |
| Software mode (default) | Adjusts host system time. The NIC must support software transmit/receive timestamps. |
| Hardware mode | Before SDK creation, set `config.time_sync.mode` to `TimeSyncMode::kHardware` (C++) or `TimeSyncMode.HARDWARE` (Python). Requires hardware timestamps and a NIC PHC; adjusts only the NIC clock. |
| Disable | Set `config.time_sync.enabled = false` (C++) or `False` (Python) before SDK creation. |

Check synchronization with:

```bash
python3 "$NORTHSDK_PREFIX/examples/python/time_sync_status.py" \
  --endpoint "$NORTHSDK_ENDPOINT" --mode software --seconds 10
```

When `state` is `READY` and `robot_time_ns` is present, use `sdk.robot_time_ns()` to read synchronized time. Robot time uses the gPTP domain and is not guaranteed to match UTC.

By default, a synchronization failure makes `connect()` return an error while retaining communication. Inspect `time_sync_diagnostics()` for the cause; the status script shows how to handle the error and continue using the connection. If synchronization is lost during operation, wait for readiness before resuming calculations that depend on synchronized time.

For communication-only checks, add `--no-time-sync` to `north_sdk_robot_smoke`. See [Time-sync parameters](Software%20Service%20Interface.md#time-sync-parameters) for configuration and diagnostic fields.

## Video environment setup

Complete this section when using video. First load the package environment as described in Quick Start. GStreamer runtime libraries, parsing/conversion/JPEG plugins, NVIDIA decoder plugins and a minimal H.264/H.265 software decoder are bundled; installing system GStreamer is unnecessary.

### NVIDIA drivers and bundled runtime

NVIDIA NVDEC is the default backend. The discrete GPU must support the camera's H.264/H.265 coding profile, with NVIDIA driver and decode libraries matched to the GPU and Ubuntu release. Install NVIDIA drivers separately.

Check the driver first:

```bash
nvidia-smi -L
```

If no GPU is listed, follow the [Ubuntu driver installation instructions](https://ubuntu.com/server/docs/nvidia-drivers-installation/) to install or repair the driver. NVDEC uses driver-provided `libcuda.so.1` and `libnvcuvid.so.1`. See [NVIDIA's decode support matrix](https://developer.nvidia.com/video-encode-decode-support-matrix) for supported input profiles.

`setup.bash` sets SDK video library, plugin and cache paths. Load it in each terminal or application launch environment, and use the current SDK’s runtime and plugins. If the application already loads another GStreamer runtime, receive video in a separate process.

The bundled software decoder supports compatibility and functional debugging. Select it explicitly when no NVIDIA GPU is available; it requires no NVIDIA driver. Software decoding has poor performance for multiple or high-resolution streams and may cause severe frame drops and latency, so it is not recommended for real-time tasks. The SDK never automatically falls back from hardware to software decoding.

### Check the video environment

Run in the same terminal as the video example. The default recommended backend is NVIDIA hardware decoding:

```bash
python3 "$NORTHSDK_PREFIX/examples/python/check_video_env.py" --backend nvdec
```

The script checks local SDK loading, GStreamer, video plugins and GPU/driver dependencies; C++ users can run it too. All checks reporting `OK` and a final `PASS` mean dependencies are available. Receive video next to verify decoding. On `FAIL`, check the current package environment, library/plugin completeness and driver status.

To check software decoding, pass `--backend software` to the script. Select the capture or preview program’s decoder separately, as shown next and in [Example Code Reference](Example%20Code%20Reference.md#subscribe-to-head-jpeg).

### Receive the first video stream

After the dependency check passes and the robot head-left camera is online, run a single read-only capture for five seconds without saving images:

```bash
"$NORTHSDK_PREFIX/bin/north_sdk_video_jpeg" \
  "$NORTHSDK_ENDPOINT" --no-save 0 85 --seconds=5 --nvdec
```

`0` selects head-left and `85` is JPEG quality. At completion, check that JPEG count is greater than zero and no subscription/decoder errors occurred. If no JPEG arrives, check camera publication, network and decoder requirements. For software decoding, replace `--nvdec` with `--software` after passing the corresponding environment check.

For browser preview, use the scripts in [Example Code Reference](Example%20Code%20Reference.md#subscribe-to-head-jpeg). See [VideoClient](Software%20Service%20Interface.md#videoclient) for parameters, sources and diagnostics.

## Subscriptions and caches

Retain the Subscription returned by on_*(). Destruction or close() cancels it. C++ callback arguments are borrowed references; copy data needed after the callback. Keep callbacks short and move expensive or blocking work to application workers.

latest_*(max_age) returns a local cached copy, aged from local reception. The first call may have no sample or return kStaleState. Wait for a new sample.

| Callback policy | Purpose |
| --- | --- |
| `kDropOldest` | Default; discard the oldest droppable callback when full |
| `kLatestOnly` | Coalesce pending samples per subscription for state display |
| `kReliable` | Apply backpressure instead of local dropping |

![No sample, fresh cache and expired cache](../../assets/en/SDK/Application%20Development/cache-timeline.svg)

This example uses max_age=500 ms; 250 ms and 700 ms are local receive ages. latest_* establishes the required state reception without a prior on_* call. A separate on_* subscription also receives callbacks.

## Service results

Check the SDK call result first, then the robot service's business result. Monitor heartbeats and error events during operation. C++ uses `Result<T>` / `Status`; Python raises `NorthSDKError`. See [Errors and result checking](Software%20Service%20Interface.md#errors-and-result-checking) for fields and handling.

## Motion control

> **Real motion is not a first-connection test.** SDK validation and the Master gate do not replace a hardware emergency stop, model-specific limits, site risk assessment or the robot-side safety controller.

Before the first motion command, complete at least these checks:

- the emergency stop has been verified and is immediately reachable; the work area is clear and the robot is restrained or supported as required by its model;
- the joint names, array order, positive directions, zero positions, hard/soft limits and recommended velocity/acceleration for this exact model are available;
- fresh feedback is read first and a small target is generated from the current position within model limits;
- the task ID, CommandChannel, Master mode, device enable state and control mode are a supported combination in the delivered robot configuration;
- the control loop stops sending immediately when feedback becomes stale, Master leaves RUNNING, or an SDK/business error occurs;
- reviewed task-stop, emergency-stop and recovery procedures are ready, and the on-site supervisor approves the test.

See [Motion protection and trajectory processing](#motion-protection-and-trajectory-processing) for robot-side protection, numeric limits and interpolation settings.

Motion commands require fresh RUNNING Master status. Channel-to-mode mapping is below; follow [Prepare and end a task](#prepare-and-end-a-task) for setup.

| Channel | Master mode |
| --- | --- |
| `kTeleoperation` | `kTeleoperation` |
| `kInference` | `kInference` |
| `kAutomation` | `kAutomation` |
| `kUniversal` | Any mode; fresh RUNNING is still required |

Each arm has seven joints, each hand twenty-two, and the torso eight. Positions are in rad, in fixed device order. Populate complete JointCommand.position only; leave name, velocity and torque empty. A successful send means submission succeeded; determine completion from fresh device feedback.

![Command submission versus device motion completion](../../assets/en/SDK/Application%20Development/motion-sequence.svg)

This sequence illustrates a single-arm position command. Invalid runtime conditions or targets return an SDK error. kUniversal skips mode matching but still requires fresh RUNNING.

### Prepare and end a task

The following example sends position targets with the `inference` task.

1. **Configure the channel.** Before SDK creation, set `config.command_channel = north::CommandChannel::kInference` (C++) or `config.command_channel = CommandChannel.INFERENCE` (Python). WholeBody takes its channel on each `send()`.

2. **Check idle state.** Read fresh Master status and require `STANDBY`. Check required device health and confirm other controllers have stopped sending commands. End any existing task using its own procedure first.

3. **Prepare devices.** Call `master().set_mode()` with `OperationMode::kInference` / `OperationMode.INFERENCE`. For each controlled arm select `ControlMode::kJointPosition` / `ControlMode.JOINT_POSITION` and call `enable()`. For torso select `TorsoControlMode::kPosition` / `TorsoControlMode.POSITION` and enable it. For hands select `HandMode::kPosition` / `HandMode.POSITION`. Check each service result and device feedback.

4. **Start the task.** Call `master().start_task("inference")`, check `MasterResult`, then wait for streamed status with `RUNNING`, `Inference` and `task_id == "inference"`. Resolve device health failures before proceeding.

5. **Send targets.** Generate complete, small, continuous targets from fresh position feedback. Continue checking task ID, Master phase/mode and device feedback. Use the joint ordering in the next section.

6. **End normally.** Stop the control loop. For chassis, keep sending zero velocity until feedback confirms rest. Call `master().stop_task()`, check its business result, wait for status to leave RUNNING and check device feedback before closing the SDK. On feedback or communication failure, use the site stopping procedure.

`start_task(task_id)` takes a case-sensitive task ID. Customer tasks in the standard configuration are listed below; availability follows the delivered configuration. Unconfigured IDs are rejected.

| Task ID | Purpose |
| --- | --- |
| `inference` | Inference control; used in this example. |
| `teleoperation` | Teleoperation, with its own preparation flow. |
| `home` | Homing; actively moves the robot. |
| `docking` | Docking. |

Normal `teleoperation` completion performs homing and leaves RUNNING after homing and recording finalization. **Stopping teleoperation may cause further motion and must not be used as an emergency stop.**

`master().exit_estop()` starts actuator reset and re-enable, including both arms, torso and hand mode recovery. Clear outgoing motion commands and confirm the site is ready before calling it. A successful response means recovery has started. Wait for Master to leave ESTOP, then check health, control modes and fresh position feedback before starting a new control loop.

### Joint arrays and coordinates

`joints.name[i]` and `joints.position[i]` refer to the same axis. Commands use the same fixed index, with `name` left empty. Print the complete device state and compare it with the joint definition for the delivered model.

| Part | Array indices | State names | Mapping |
| --- | --- | --- | --- |
| Each arm | 0–6 | `joint_0`–`joint_6` | J1–J7; `Side` selects left or right. |
| Torso | 0–4 | `torso_0`–`torso_4` | Body J1–J5; J3/J4 are waist pitch/roll joints. |
| Neck | 5–7 | `torso_5`–`torso_7` | Neck J6–J8, sent with the body as a complete eight-position command. |
| Each hand | 0–21 | `joint_0`–`joint_21` | Twenty-two joints. |

Positions are in rad. Use the delivered model’s joint definitions for each side’s zero positions, positive axes and hand joint groups.

## Motion protection and trajectory processing

The robot applies command-step checks, limits and interpolation to motion targets. Joint numbers start at 1; SDK indices start at 0.

### Command admission and fault protection

Arms and torso process streamed position commands using **the difference between the new target and the previous accepted target**. A frame within every direct-admission threshold is accepted when no catch-up or recovery is pending. Larger steps have their increments limited; steps above Hold reject the entire frame. Axes meeting the fresh-feedback condition below may be exempted from triggering Hold.

| Part and checking space | Direct-admission threshold | Hold threshold | Catch-up rate |
| --- | --- | --- | --- |
| Each arm, joint angles J1–J7 | 0.1745 rad per joint | J1–J4: 0.3491 rad; J5–J7: 0.5236 rad | J1–J7: 2.0944, 2.0944, 3.1416, 3.1416, 6.2832, 6.2832, 6.2832 rad/s |
| Torso, eight motor axes in motor-ID order 1–8 | 0.0349, 0.0349, 0.0698, 0.0698, 0.0698, 0.0873, 0.0873, 0.0873 rad | 0.1047, 0.1047, 0.2094, 0.2094, 0.2094, 0.2618, 0.2618, 0.2618 rad | 1.0472, 1.0472, 1.0472, 1.0472, 1.0472, 1.5708, 1.5708, 1.5708 rad/s |

During catch-up, all axes use the most restrictive axis's increment scaling factor, with a time allowance capped at 20 ms. Catch-up rates apply during catch-up and recovery.

If feedback is no older than 50 ms and the target-to-feedback difference is within the direct threshold, that axis may avoid Hold caused by a large step from the old target; position commands remain subject to catch-up limits. Recovery from Hold requires checked axes to return within the direct threshold or close to that fresh feedback. **Hold retains the previous target and existing motion may continue.** Torso thresholds are evaluated in motor coordinates.

The robot also checks measured state and hardware faults:

| Protection | Default setting and behavior |
| --- | --- |
| Arm feedback position | Feedback beyond the position range below expanded outward by 0.0262 rad triggers protection. Application targets must remain within the tabulated position range. |
| Arm position tracking error | When position safety checking is active, target-to-feedback error above 0.3491 rad for J1–J4 or 0.6982 rad for J5–J7 triggers fault protection. |
| Arm motor feedback and hardware faults | Non-finite feedback, drive faults or motor speed above 8.3776 rad/s for motors 1–3 or 26.7035 rad/s for motors 4–7 trigger fault protection. |
| Chassis command timeout | After 100 ms without a valid motion command, the current velocity command expires. Verify standstill using velocity feedback. |

After a fault, inspect heartbeat errors and service responses, then follow the recovery procedure. Self-collision checking is disabled by default; applications must plan collision-free motion.

### Position ranges and velocity constraints

#### Arms

Position targets are clamped per joint as follows. Left and right arms use their respective joint coordinate definitions.

| Joint | Lower position (rad) | Upper position (rad) | Joint velocity command clamp (rad/s) |
| --- | --- | --- | --- |
| J1 | -1.6144 | 4.2673 | 8.3776 |
| J2 | -2.0944 | 0.3491 | 8.3776 |
| J3 | -1.2217 | 4.3633 | 8.3776 |
| J4 | -0.1745 | 2.2689 | 11.4605 |
| J5 | -1.5708 | 2.6180 | 22.9210 |
| J6 | -1.0472 | 1.5708 | 26.7035 |
| J7 | -0.8727 | 0.8727 | 26.7035 |

The velocity column caps joint velocity commands. Applications plan operating speeds for the task. SDK Arm APIs accept position targets; motor limits and mechanism pose further affect actual motion.

#### Torso and hands

Torso positions are clamped in the fixed SDK joint order:

| Joint | J1 | J2 | J3 | J4 | J5 | J6 | J7 | J8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lower (rad) | 0 | -2.4435 | -0.5236 | -0.5236 | -3.1416 | -1.5708 | -0.5236 | -0.5236 |
| Upper (rad) | 1.4835 | 0 | 2.0944 | 0.5236 | 3.1416 | 1.5708 | 0.5236 | 0.8727 |

See [TorsoClient](Software%20Service%20Interface.md#torsoclient) for joint names and diagram. Combined waist poses must also satisfy mechanism and motor constraints.

Hand limits follow the delivered model's joint table. Default speed and current coefficients are 0.5 and 0.6 respectively; both are dimensionless.

#### Chassis

| Parameter | Default value | Meaning |
| --- | --- | --- |
| `vx` / `vy` acceleration | 10 m/s² each | Limits body-frame x and y acceleration separately. |
| `vtheta` angular acceleration | 10 rad/s² | Yaw velocity slew limit. |
| `extension_velocity` acceleration | 0.5 m/s² | Stretch-axis velocity slew limit. |
| Stretch speed | 0.05 m/s | Stretch synchronization speed cap. |
| Stretch length | 0.357–0.477 m | Mechanism stretch range; the SDK controls stretch through `extension_velocity`. |
| Wheel motor speed | 31.4159 rad/s | Motor cap; closed-loop wheel control caps speed at 20.9440 rad/s. The stricter limit applies. |
| Steering angle | ±2.7925 rad | Hard limit: ±2.7925 rad. Steering-angle selection uses a ±2.3562 rad soft band. |

Steering alignment and stretch state can further reduce wheel speed. Determine `vx/vy/vtheta` ranges from chassis motion constraints. After sending zero velocity, confirm standstill using velocity feedback.

### Smoothing continuous position commands

Arms and torso use quintic interpolation to convert streamed position targets into higher-rate control targets. Applications continuously send smooth targets.

| Parameter | Each arm | Torso |
| --- | --- | --- |
| Control period | 1 ms (1000 Hz) | 2 ms (500 Hz) |
| Nominal command period | 20 ms | 20 ms |
| Interpolation velocity parameter | 10 rad/s | 1.0472 rad/s (motor space) |
| Interpolation acceleration parameter | 30 rad/s² | 2.0944 rad/s² (motor space) |

The nominal period is an interpolation reference and allows variations in send intervals. Larger target changes may extend execution time. Interpolation parameters, catch-up rates and joint velocity limits act at different stages. Applications plan velocity, acceleration and jerk.

The robot connects each segment with a quintic polynomial, matching position, velocity and acceleration at both endpoints:

```text
q(t) = a0 + a1 t + a2 t² + a3 t³ + a4 t⁴ + a5 t⁵,  0 ≤ t ≤ T
```

Here `q` is position (rad), `T` is segment time (s), and the six coefficients are determined by endpoint position, velocity and acceleration. New streamed targets continue from the current motion state.

![Position target and smoothed control target](../../assets/en/SDK/Application%20Development/position-smoothing.svg)

The figure shows a single segment with zero endpoint velocity and acceleration. With `s=t/T`, its position is `q(t)=q0+(q1−q0)(10s³−15s⁴+6s⁵)`. Continuous motion uses the actual endpoint derivatives.

Segment time is estimated from the command period and extended for larger target changes:

```text
T0 = clamp(1.5 P, Tc, 0.2 s)
T  = max(T0, 1.875 × max_i |q1[i] − q0[i]| / vmax)
```

`P` is the estimated command period, `Tc` the control period, and `vmax` a positive interpolation velocity parameter. Position and velocity must use the same coordinate space. The 0.2 s cap applies to timing estimation; actual `T` may be longer. Velocity and acceleration parameters clamp derivative estimates and outputs. Applications must still check velocity, acceleration and jerk over the complete trajectory.

After a stream stops, the final position is retained and output velocity and acceleration decay within 50 ms. Confirm standstill through device feedback.

Hands receive the latest complete target directly; applications ensure target continuity. Hand feedback without progress for more than 300 ms is marked stale. Existing targets may continue executing after sending stops; confirm standstill through device feedback.

## Shutdown and reconnect

Finish the application task-stop workflow, then close subscriptions and the SDK. `close()` cancels subscriptions, clears caches and releases this object’s time-sync session. After the last time-sync session closes, the previous system time services are restored. Recreate user subscriptions after reconnecting. Python can use `with NorthSDK(config)` to connect and close automatically.

## Troubleshooting

Use this section for data reception, service calls and motion admission after application startup. See [First-run troubleshooting](#first-run-troubleshooting) for startup/library/import failures and [Video environment setup](#video-environment-setup) for video dependencies and decoding.

| Symptom | Check |
| --- | --- |
| No state output or silent stream | Subscription lifetime, installed/online device, robot-side publication and endpoint |
| Cache read failure | Sample reception, max_age and continued device updates |
| Call error or service rejection | Check the SDK error first, then response success/result and message; see [Errors and result checking](Software%20Service%20Interface.md#errors-and-result-checking) |
| Device fault during operation | Stop sending motion targets. Record the subsystem, error_code, fault_codes and Master reason. Resolve emergency-stop or connectivity causes before device recovery; contact support with these details and software versions for persistent faults. |
| Time-sync failure or loss | Check the wired robot connection, host setup and diagnostics; see [Time synchronization](#time-synchronization). |
| Motion rejected | Supported fields, complete targets, command_channel, Master phase and mode |
