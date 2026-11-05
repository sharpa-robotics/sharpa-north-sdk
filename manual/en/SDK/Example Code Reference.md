# Example Code Reference

North SDK

[SDK Overview](SDK%20Overview.md) · [Application Development](Application%20Development.md) · [Software Service Interface](Software%20Service%20Interface.md) · [Example Code Reference](Example%20Code%20Reference.md) · [中文](../../zh/SDK/%E4%BE%8B%E7%A8%8B%E5%8F%82%E8%80%83.md)

## Contents

- [Example index](#example-index)
- [Included quickstart programs](#included-quickstart-programs)
- [Read-only connection diagnostics](#read-only-connection-diagnostics)
- [Shared entry point](#shared-entry-point)
- [Subscribe to Master status](#subscribe-to-master-status)
- [Read cached left-arm state](#read-cached-left-arm-state)
- [Subscribe to torso state](#subscribe-to-torso-state)
- [Subscribe to hand tactile images](#subscribe-to-hand-tactile-images)
- [Query hand calibration status](#query-hand-calibration-status)
- [Subscribe to IMU](#subscribe-to-imu)
- [Subscribe to Lidar points](#subscribe-to-lidar-points)
- [Read valid battery measurements](#read-valid-battery-measurements)
- [Subscribe to head JPEG](#subscribe-to-head-jpeg)
- [Align two-arm state](#align-two-arm-state)
- [Query configuration instances](#query-configuration-instances)
- [Master mode service](#master-mode-service)
- [Send a single-arm target](#send-a-single-arm-target)
- [WholeBody two-arm command](#wholebody-two-arm-command)

## Example index

Examples are organized by common tasks. Start with quickstart, then select a Client example. Motion examples have separate prerequisites. Combine one example function with the shared entry point to create a standalone application.

| Client | Task | C++ call | Python call |
| --- | --- | --- | --- |
| MasterClient | [Subscribe to Master status](#subscribe-to-master-status) | `master_status(*sdk);` | `master_status(sdk)` |
| ArmClient | [Read cached left-arm state](#read-cached-left-arm-state) | `arm_cache(*sdk);` | `arm_cache(sdk)` |
| TorsoClient | [Subscribe to torso state](#subscribe-to-torso-state) | `torso_state(*sdk);` | `torso_state(sdk)` |
| HandClient | [Subscribe to hand tactile images](#subscribe-to-hand-tactile-images) | `hand_tactile(*sdk);` | `hand_tactile(sdk)` |
| HandClient | [Query hand calibration status](#query-hand-calibration-status) | `hand_calibration_status(*sdk);` | `hand_calibration_status(sdk)` |
| SensorClient | [Subscribe to IMU](#subscribe-to-imu) | `imu_state(*sdk);` | `imu_state(sdk)` |
| SensorClient | [Subscribe to Lidar points](#subscribe-to-lidar-points) | `lidar_points(*sdk);` | `lidar_points(sdk)` |
| PowerClient | [Read valid battery measurements](#read-valid-battery-measurements) | `battery_state(*sdk);` | `battery_state(sdk)` |
| VideoClient | [Subscribe to head JPEG](#subscribe-to-head-jpeg) | `head_jpeg(*sdk);` | `head_jpeg(sdk)` |
| AlignmentClient | [Align two-arm state](#align-two-arm-state) | `aligned_arms(*sdk);` | `aligned_arms(sdk)` |
| ConfigClient | [Query configuration instances](#query-configuration-instances) | `config_instances(*sdk);` | `config_instances(sdk)` |
| MasterClient | [Master mode service](#master-mode-service) | `change_master_mode(*sdk, requested);` | `change_master_mode(sdk, requested)` |
| ArmClient | [Send a single-arm target](#send-a-single-arm-target) | `send_right_arm(*sdk, target);` | `send_right_arm(sdk, target)` |
| WholeBodyClient | [WholeBody two-arm command](#wholebody-two-arm-command) | `send_two_arms(*sdk, channel, left, right);` | `send_two_arms(sdk, channel, left, right)` |

Calls using `requested`, `target`, `channel`, `left` or `right` require application-provided arguments and the mode-change or motion prerequisites stated in their sections.

## Included quickstart programs

`examples/cpp/quickstart.cpp` and `examples/python/quickstart.py` demonstrate left-arm state subscription, handle retention and clean shutdown. Both accept an endpoint on the command line. C++ also accepts a Zenoh configuration path; Python uses `--zenoh-config`. State callbacks print sequence and joint count; press Ctrl+C to exit.

The example selects the left arm with `sdk.arm(Side::kLeft)` / `sdk.arm(Side.LEFT)`. Omitting `SubscribeOptions` uses the default DropOldest callback policy. Retain the Subscription until shutdown. See [`ArmClient::on_state`](Software%20Service%20Interface.md#armclient) for complete parameters and queue semantics.

```bash
"$NORTHSDK_PREFIX/bin/north_sdk_quickstart" "$NORTHSDK_ENDPOINT"
python3 "$NORTHSDK_PREFIX/examples/python/quickstart.py" --endpoint "$NORTHSDK_ENDPOINT"
```

Load the environment and set the robot endpoint through [Quick Start](Application%20Development.md#quick-start). Commands run from any directory.

## Read-only connection diagnostics

The installed north_sdk_robot_smoke counts state samples and rates over a bounded duration to check connection and reception. The complete package also includes the Python equivalent:

```bash
"$NORTHSDK_PREFIX/bin/north_sdk_robot_smoke" --endpoint "$NORTHSDK_ENDPOINT" --seconds 5
python3 "$NORTHSDK_PREFIX/examples/python/robot_smoke.py" --endpoint "$NORTHSDK_ENDPOINT" --seconds 5
```

Receiving Master status, hardware health and at least one heartbeat produces PASS and exit code 0. Check silent streams against the actual device configuration. Add `--query` for read-only service queries and inspect each result.

## Shared entry point

C++: create main.cpp containing these includes, one selected example function, then the entry point, in that order. Replace the default master_status(*sdk) call for other examples. Integrate the selected example into your existing C++ application using the delivered public headers and libraries.

```cpp
#include <north_sdk/NorthSDK.h>
#include <array>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <utility>
```

```cpp
int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: north_sdk_app <endpoint>\n";
        return 2;
    }
    try {
        north::SdkConfig config;
        config.connect_endpoints = {argv[1]};
        auto created = north::NorthSDK::Create(config);
        if (!created) throw std::runtime_error(created.error().message);
        auto sdk = std::move(created.value());
        auto connected = sdk->connect();
        if (!connected) throw std::runtime_error(connected.message());
        master_status(*sdk);
        sdk->close();
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
```

Compile and run using `NORTHSDK_PREFIX` from Quick Start:

```bash
g++ -std=c++17 main.cpp \
  -I"$NORTHSDK_PREFIX/include" -L"$NORTHSDK_PREFIX/lib" -lnorth_sdk \
  -Wl,-rpath,"$NORTHSDK_PREFIX/lib" \
  -o north_sdk_app
./north_sdk_app "$NORTHSDK_ENDPOINT"
```

Python: create app.py with these imports, one selected example function, then the entry point. Replace the example call in the entry point.

```python
import sys
import time
from north_sdk import (
    NorthSDK, SdkConfig, NorthSDKError, ErrorCode, Side,
    TactileImageKind, PowerDataQuality, MasterResult, LidarSource, LidarPayloadKind,
    OperationMode, CommandChannel, WholeBodyCommand, ArmCommand,
)
```

```python
def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 app.py <endpoint>")
    config = SdkConfig()
    config.connect_endpoints = [sys.argv[1]]
    try:
        with NorthSDK(config) as sdk:
            master_status(sdk)  # Replace with one example call from the index.
    except (NorthSDKError, RuntimeError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
```

```bash
python3 app.py udp/192.168.100.100:7449
```

The read-only subscription examples close their subscriptions after five seconds and require the robot to publish the corresponding data. The entry point reports exceptions, while each example checks business results.

## Subscribe to Master status

Receive robot phase, mode and task ID. Retain the subscription for five seconds; an active publisher produces multiple lines.

### C++

```cpp
void master_status(north::NorthSDK& sdk) {
    auto result = sdk.master().on_status([](const north::MasterStatus& state) {
        std::cout << "phase=" << static_cast<int>(state.phase)
                  << " mode=" << static_cast<int>(state.mode)
                  << " task=" << state.task_id << '\n';
    });
    if (!result) throw std::runtime_error(result.error().message);
    auto sub = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    sub.close();
}
```

### Python

```python
def master_status(sdk):
    sub = sdk.master().on_status(
        lambda state: print(state.phase, state.mode, state.task_id)
    )
    try:
        time.sleep(5)
    finally:
        sub.close()
```

## Read cached left-arm state

Try for up to two seconds to read left-arm state received within 500 ms. The first call may lack data. Retry only kStaleState; valid state prints the position count. Cache reads establish the required state reception automatically.

This example uses a 500 ms cache-age limit and a two-second first-sample wait. Choose values from the device publication period and application latency requirements. See [`ArmClient::latest_state`](Software%20Service%20Interface.md#armclient).

### C++

```cpp
void arm_cache(north::NorthSDK& sdk) {
    auto arm = sdk.arm(north::Side::kLeft);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
    while (std::chrono::steady_clock::now() < deadline) {
        auto result = arm.latest_state(std::chrono::milliseconds(500));
        if (result) {
            std::cout << "joints=" << result.value().joints.position.size() << '\n';
            return;
        }
        if (result.error().code != north::ErrorCode::kStaleState)
            throw std::runtime_error(result.error().message);
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    throw std::runtime_error("No fresh left-arm state within 2 seconds");
}
```

### Python

```python
def arm_cache(sdk):
    arm = sdk.arm(Side.LEFT)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            state = arm.latest_state(500)
        except NorthSDKError as error:
            if error.code != ErrorCode.STALE_STATE:
                raise
            time.sleep(0.05)
        else:
            print("joints=", len(state.joints.position))
            return
    raise RuntimeError("No fresh left-arm state within 2 seconds")
```

## Subscribe to torso state

Retain a subscription for five seconds and print position count. Complete joint positions contain eight entries: body J1–J5 then neck J6–J8.

### C++

```cpp
void torso_state(north::NorthSDK& sdk) {
    auto result = sdk.torso().on_state([](const north::TorsoState& state) {
        std::cout << "torso joints=" << state.joints.position.size() << '\n';
    });
    if (!result) throw std::runtime_error(result.error().message);
    auto sub = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    sub.close();
}
```

### Python

```python
def torso_state(sdk):
    sub = sdk.torso().on_state(
        lambda state: print("torso joints=", len(state.joints.position))
    )
    try:
        time.sleep(5)
    finally:
        sub.close()
```

## Subscribe to hand tactile images

Subscribe to the left thumb raw tactile image for five seconds. finger=4 selects the thumb. Print format and binary payload length; use the message format when decoding.

### C++

```cpp
void hand_tactile(north::NorthSDK& sdk) {
    auto result = sdk.hand(north::Side::kLeft).on_tactile_image(
        4, north::TactileImageKind::kRaw, [](const north::CompressedImage& image) {
            std::cout << "format=" << image.format
                      << " bytes=" << image.data.size() << '\n';
        });
    if (!result) throw std::runtime_error(result.error().message);
    auto sub = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    sub.close();
}
```

### Python

```python
def hand_tactile(sdk):
    sub = sdk.hand(Side.LEFT).on_tactile_image(
        4, TactileImageKind.RAW,
        lambda image: print("format=", image.format, "bytes=", len(image.data)),
    )
    try:
        time.sleep(5)
    finally:
        sub.close()
```

## Query hand calibration status

Query left-hand zero-calibration status. Handle SDK failure and business rejection separately, then print the response message.

### C++

```cpp
void hand_calibration_status(north::NorthSDK& sdk) {
    auto result = sdk.hand(north::Side::kLeft).zero_calibration_status();
    if (!result) throw std::runtime_error("SDK error: " + result.error().message);
    if (!result.value().success)
        throw std::runtime_error("Service rejected: " + result.value().message);
    std::cout << result.value().message << '\n';
}
```

### Python

```python
def hand_calibration_status(sdk):
    response = sdk.hand(Side.LEFT).zero_calibration_status()
    if not response.success:
        raise RuntimeError("Service rejected: " + response.message)
    print(response.message)
```

## Subscribe to IMU

Subscribe for five seconds. Iterate through imus in each sample and print angular velocity x in rad/s. The robot must provide an IMU source.

### C++

```cpp
void imu_state(north::NorthSDK& sdk) {
    auto result = sdk.sensors().on_imu([](const north::ImuSamples& samples) {
        for (const auto& imu : samples.imus)
            std::cout << "angular_velocity.x=" << imu.angular_velocity.x << '\n';
    });
    if (!result) throw std::runtime_error(result.error().message);
    auto sub = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    sub.close();
}
```

### Python

```python
def imu_state(sdk):
    def display(samples):
        for imu in samples.imus:
            print("angular_velocity.x=", imu.angular_velocity.x)
    sub = sdk.sensors().on_imu(display)
    try:
        time.sleep(5)
    finally:
        sub.close()
```

## Subscribe to Lidar points

Subscribe to the chassis-front Lidar for five seconds and print the first point of each frame: coordinates in meters and reflectivity. The SDK decompresses Zstd automatically. Select chest front or chest rear as needed; the robot must have the corresponding device installed and publishing.

### C++

```cpp
void lidar_points(north::NorthSDK& sdk) {
    auto result = sdk.sensors().on_lidar(
        north::LidarSource::kChassisFront, [](const north::LidarFrame& frame) {
            auto print_first = [](const auto& groups) {
                for (const auto& group : groups) {
                    if (group.points.empty()) continue;
                    const auto& point = group.points.front();
                    std::cout << "xyz(m)=" << point.x << ',' << point.y << ',' << point.z
                              << " reflectivity=" << point.reflectivity << '\n';
                    break;
                }
            };
            if (frame.kind == north::LidarPayloadKind::kLaserShots)
                print_first(frame.laser_shots);
            else if (frame.kind == north::LidarPayloadKind::kSubAreas)
                print_first(frame.sub_areas);
        });
    if (!result) throw std::runtime_error(result.error().message);
    auto sub = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    sub.close();
}
```

### Python

```python
def lidar_points(sdk):
    def display(frame):
        if frame.kind == LidarPayloadKind.LASER_SHOTS:
            groups = frame.laser_shots
        elif frame.kind == LidarPayloadKind.SUB_AREAS:
            groups = frame.sub_areas
        else:
            return
        for group in groups:
            points = group.points
            if points:
                point = points[0]
                print("xyz(m)=", point.x, point.y, point.z,
                      "reflectivity=", point.reflectivity)
                break
    sub = sdk.sensors().on_lidar(LidarSource.CHASSIS_FRONT, display)
    try:
        time.sleep(5)
    finally:
        sub.close()
```

## Read valid battery measurements

Subscribe to battery state for five seconds. Check voltage.quality and optional value for each pack, printing voltage in V only when valid. Otherwise print unavailable. If callbacks are absent, inspect the source and connection.

### C++

```cpp
void battery_state(north::NorthSDK& sdk) {
    auto result = sdk.power().on_battery([](const north::BatterySystemState& state) {
        for (const auto& pack : state.packs) {
            std::cout << "pack=" << pack.pack_id << " voltage=";
            if (pack.voltage.quality == north::PowerDataQuality::kValid
                    && pack.voltage.value)
                std::cout << *pack.voltage.value << " V\n";
            else
                std::cout << "unavailable\n";
        }
    });
    if (!result) throw std::runtime_error(result.error().message);
    auto sub = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    sub.close();
}
```

### Python

```python
def battery_state(sdk):
    def display(state):
        for pack in state.packs:
            reading = pack.voltage
            if reading.quality == PowerDataQuality.VALID and reading.value is not None:
                print("pack=", pack.pack_id, "voltage=", reading.value, "V")
            else:
                print("pack=", pack.pack_id, "voltage=unavailable")
    sub = sdk.power().on_battery(display)
    try:
        time.sleep(5)
    finally:
        sub.close()
```

## Subscribe to head JPEG

This example selects head-left with NVIDIA hardware decoding by default. Load the package environment and complete the [video environment check](Application%20Development.md#check-the-video-environment) first.

Software-decoder options for each program are listed below:

| Program or API | Select software decoding |
| --- | --- |
| C++ capture program `north_sdk_video_jpeg` | Pass `--software` at runtime; `--nvdec` selects hardware |
| Four-camera preview `examples/python/four_camera_viewer.py` | Pass `--decoder software`; `--decoder nvdec` selects hardware |
| Your C++ application | Before subscribing, set `options.decoder_backend = north::VideoDecoderBackend::kSoftware` |
| Your Python application | Before subscribing, set `options.decoder_backend = VideoDecoderBackend.SOFTWARE` |

The minimal subscription example below retains default hardware decoding; use the table to select software.

### Browser preview

Preview both head and both wrist cameras:

```bash
python3 "$NORTHSDK_PREFIX/examples/python/four_camera_viewer.py" \
  --endpoint "$NORTHSDK_ENDPOINT" --decoder nvdec --port 8080
```

The program opens a local browser; alternatively visit `http://127.0.0.1:8080/`. Without an NVIDIA GPU, use `--decoder software`. Press Ctrl+C or click the stop-preview button to exit. Cameras must already be online and publishing.

### C++

```cpp
void head_jpeg(north::NorthSDK& sdk) {
    north::VideoOptions options;
    auto result = sdk.video().on_jpeg(
        north::VideoSource::kHeadLeft,
        [](const north::JpegFrame& frame) {
            std::cout << frame.width << 'x' << frame.height
                      << " bytes=" << frame.data.size() << '\n';
        }, options);
    if (!result) throw std::runtime_error(result.error().message);
    auto subscription = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    subscription.close();
}
```

### Python

```python
def head_jpeg(sdk):
    from north_sdk import VideoDecoderBackend, VideoOptions, VideoSource

    options = VideoOptions()
    subscription = sdk.video().on_jpeg(
        VideoSource.HEAD_LEFT,
        lambda frame: print(frame.width, frame.height, len(frame.data)),
        options,
    )
    time.sleep(5)
    subscription.close()
```

Only one active subscription is allowed per source; retain the handle. See [`VideoClient`](Software%20Service%20Interface.md#videoclient) for dependencies, options, and diagnostics.

## Align two-arm state

This example uses left ArmState as baseline and matches right ArmState. Matching defaults to AtOrBefore with a fixed 7.5 ms right-arm tolerance; the first valid sample can be matched.

### C++

```cpp
void aligned_arms(north::NorthSDK& sdk) {
    north::AlignmentSource left;
    left.kind = north::AlignmentDataKind::kArmState;
    left.side = north::Side::kLeft;
    auto right = left;
    right.side = north::Side::kRight;
    north::AlignmentOptions options;
    options.baseline = left;
    options.sources = {right};
    auto result = sdk.alignment().on_frame(options, [](const north::AlignedFrame& frame) {
        std::cout << frame.timestamp_ns << " complete=" << frame.complete << '\n';
    });
    if (!result) throw std::runtime_error(result.error().message);
    auto subscription = std::move(result.value());
    std::this_thread::sleep_for(std::chrono::seconds(5));
    subscription.close();
}
```

### Python

```python
def aligned_arms(sdk):
    from north_sdk import AlignmentDataKind, AlignmentOptions, AlignmentSource, Side

    left = AlignmentSource()
    left.kind = AlignmentDataKind.ARM_STATE
    left.side = Side.LEFT
    right = AlignmentSource()
    right.kind = AlignmentDataKind.ARM_STATE
    right.side = Side.RIGHT
    options = AlignmentOptions()
    options.baseline = left
    options.sources = [right]
    subscription = sdk.alignment().on_frame(
        options, lambda frame: print(frame.timestamp_ns, frame.complete)
    )
    time.sleep(5)
    subscription.close()
```

`frame.samples[0]` is the right arm and `offset_ns` is right minus left time. See [`AlignmentClient`](Software%20Service%20Interface.md#alignmentclient) for matching and diagnostics.

## Query configuration instances

An empty `plugin_id` discovers all ready instances. Check both SDK failure and `ConfigResult`.

### C++

```cpp
void config_instances(north::NorthSDK& sdk) {
    auto result = sdk.config().get();
    if (!result) throw std::runtime_error(result.error().message);
    if (result.value().result != north::ConfigResult::kOk)
        throw std::runtime_error("configuration query rejected");
    for (const auto& instance : result.value().instances)
        std::cout << instance.plugin_id << '\n';
}
```

### Python

```python
def config_instances(sdk):
    from north_sdk import ConfigResult

    response = sdk.config().get()
    if response.result != ConfigResult.OK:
        raise RuntimeError(response.diagnostics)
    for instance in response.instances:
        print(instance.plugin_id)
```

Pass an ID returned by discovery, such as `get("chassis")`, for one instance. See [`ConfigClient`](Software%20Service%20Interface.md#configclient) for persistent SET/RESET parameters and timeout handling.

## Master mode service

This example changes robot mode. Call it only when the application has confirmed that switching is allowed. The application selects requested. Master responses use result rather than success; continue observing state after success.

`requested` is an `OperationMode`: Teleoperation, Inference or Automation. Select a mode that corresponds to the CommandChannel used by later motion. See [`MasterClient::set_mode`](Software%20Service%20Interface.md#masterclient) for parameters, results, and timeout handling.

### C++

```cpp
void change_master_mode(north::NorthSDK& sdk, north::OperationMode requested) {
    auto result = sdk.master().set_mode(requested);
    if (!result) throw std::runtime_error("SDK error: " + result.error().message);
    if (result.value().result != north::MasterResult::kOk)
        throw std::runtime_error("Service rejected: " + result.value().message);
    std::cout << result.value().message << '\n';
}
```

### Python

```python
def change_master_mode(sdk, requested):
    response = sdk.master().set_mode(requested)
    if response.result != MasterResult.OK:
        raise RuntimeError("Service rejected: " + response.message)
    print(response.message)
```

## Send a single-arm target

First follow [Prepare and end a task](Application%20Development.md#prepare-and-end-a-task) to configure the channel, devices and task. Generate seven finite rad targets in device order from fresh feedback within model limits, and use actual position feedback to confirm completion. See [`ArmClient::send_joint_positions`](Software%20Service%20Interface.md#armclient) for complete constraints.

### C++

```cpp
void send_right_arm(north::NorthSDK& sdk, const std::array<float, 7>& target) {
    auto sent = sdk.arm(north::Side::kRight).send_joint_positions(target);
    if (!sent) throw std::runtime_error(sent.message());
}
```

### Python

```python
def send_right_arm(sdk, target):
    if len(target) != 7:
        raise ValueError("Expected 7 joint positions")
    sdk.arm(Side.RIGHT).send_joint_positions(target)
```

No send error means local submission succeeded. Compare fresh right-arm feedback with the target using application-defined tolerance. Stop sending and reassess runtime conditions on kStaleState or kMotionNotAllowed.

## WholeBody two-arm command

Use the same motion prerequisites, with both arms prepared. Pass an explicit task-compatible channel and application-planned targets. This example updates both arms only; inspect each arm feedback to determine completion.

### C++

```cpp
void send_two_arms(north::NorthSDK& sdk, north::CommandChannel channel,
                   const std::array<float, 7>& left,
                   const std::array<float, 7>& right) {
    north::ArmCommand left_command, right_command;
    left_command.joints.position.assign(left.begin(), left.end());
    right_command.joints.position.assign(right.begin(), right.end());
    north::WholeBodyCommand command;
    command.left_arm = left_command;
    command.right_arm = right_command;
    auto sent = sdk.whole_body().send(channel, command);
    if (!sent) throw std::runtime_error(sent.message());
}
```

### Python

```python
def send_two_arms(sdk, channel, left, right):
    if len(left) != 7 or len(right) != 7:
        raise ValueError("Expected 7 positions for each arm")
    left_command, right_command = ArmCommand(), ArmCommand()
    from north_sdk import JointCommand
    left_joints, right_joints = JointCommand(), JointCommand()
    left_joints.position = list(left)
    right_joints.position = list(right)
    left_command.joints = left_joints
    right_command.joints = right_joints
    command = WholeBodyCommand()
    command.left_arm = left_command
    command.right_arm = right_command
    sdk.whole_body().send(channel, command)
```
