# Software Service Interface

North SDK

[SDK Overview](SDK%20Overview.md) · [Application Development](Application%20Development.md) · [Software Service Interface](Software%20Service%20Interface.md) · [Example Code Reference](Example%20Code%20Reference.md) · [中文](../../zh/SDK/%E8%BD%AF%E4%BB%B6%E6%9C%8D%E5%8A%A1%E6%8E%A5%E5%8F%A3.md)

## Contents

- [API conventions](#api-conventions)
- [Common parameters and results](#common-parameters-and-results)
- [SdkConfig defaults](#sdkconfig-defaults)
- [Errors and result checking](#errors-and-result-checking)
- [Python mapping](#python-mapping)
- [Public capability scope](#public-capability-scope)
- [Client APIs](#client-apis)
  - [NorthSDK](#northsdk)
  - [Subscription](#subscription)
  - [ConfigClient](#configclient)
  - [MasterClient](#masterclient)
  - [WholeBodyClient](#wholebodyclient)
  - [ChassisClient](#chassisclient)
  - [TorsoClient](#torsoclient)
  - [ArmClient](#armclient)
  - [HandClient](#handclient)
  - [SensorClient](#sensorclient)
  - [PowerClient](#powerclient)
  - [VideoClient](#videoclient)
  - [AlignmentClient](#alignmentclient)
- [Time-sync parameters](#time-sync-parameters)
- [Data types and fields](#data-types-and-fields)
- [Lifecycle and diagnostics](#lifecycle-and-diagnostics)

## API conventions

This chapter covers SDK subscriptions, caches, Actions and synchronous Services. Classes are in namespace `north`. Declarations and public data types follow; include `<north_sdk/NorthSDK.h>` when compiling an application.

## Common parameters and results

| Object | Usage rule |
| --- | --- |
| `Status` | SDK result for connect and Actions; check ok()/bool |
| `Result<T>` | Check bool before value; on failure inspect error.code/message |
| `BasicResponse` | After Result succeeds, check success and message |
| `MasterResponse` | Check result against kOk; before/after are service snapshots |
| `Header` | `stamp_ns` is source time and `system_time_ns` is remote system time; their domains may differ. `seq` is a sequence number, `key` identifies the source, and `frame_id` identifies a source or coordinate frame. |
| `Side` | kLeft/kRight; Python LEFT/RIGHT; invalid values are rejected |

Default units are SI: m, rad, m/s, rad/s, N, Nm, A and V, with temperature in degrees Celsius. Time fields use explicit _ns/_ms/_s units; power clocks use clock_domain. Arrays use fixed device joint order and quaternion fields are w/x/y/z.

These rules apply to state/event subscriptions using `SubscribeOptions` and to `latest_*` cache reads. See VideoClient and AlignmentClient for their specialized options.

| Common parameter | Type, default and rules |
| --- | --- |
| `callback` | Required, nonempty C++ `std::function<void(const T&)>` or Python callable. The C++ reference is callback-scoped; copy data needed afterward. |
| `options` | `SubscribeOptions`, default DropOldest; controls local callback queuing. Python defaults to `SubscribeOptions()`. |
| `max_age` / `max_age_ms` | Required C++ milliseconds; Python int defaults to 1000 ms. Must be nonnegative. Measures elapsed time since SDK reception on this computer, independently of message timestamps. |

Retain the subscription returned by `on_*`. Destruction, `close()`, or leaving a Python subscription context cancels it. SDK worker callbacks should remain short; no new callback starts after `close()` returns.

`latest_*` automatically receives state and returns a cached copy without a prior subscription. Missing or expired samples return `kStaleState`, negative age returns `kInvalidArgument`. Choose the age from the device publication period and application latency requirements. C++ checks `Result<T>`; Python returns data or raises `NorthSDKError`.

## SdkConfig defaults

| Field | Default | Meaning |
| --- | --- | --- |
| `zenoh_config_path` | Empty | Native Zenoh configuration file |
| `connect_endpoints` | {} | Supply endpoints explicitly or through the file |
| `connect_timeout` | 5000 ms | Wait for one communication-session connection attempt |
| `service_timeout` | 6000 ms | Ordinary service wait configuration |
| `master_timeout` | 15000 ms | Master services |
| `torso_timeout` | 20000 ms | Torso services |
| `callback_queue_capacity` | 256 | Bounded callback queue capacity in tasks |
| `master_status_max_age` | 500 ms | Maximum receive age for motion admission; must be positive |
| `command_channel` | kUnspecified | Set explicitly for single-part sends |
| `time_sync` | Enabled, software mode | Prepares gPTP after connection; see [Time-sync parameters](#time-sync-parameters). |

## Errors and result checking

Check SDK call errors, robot service outcomes and runtime device faults separately:

| Layer | How to obtain it | Handling |
| --- | --- | --- |
| SDK call result | C++: `Result<T>.error().code/message` or `Status.code()/message()`; Python: catch `NorthSDKError`, read `.code` and the exception text | Resolve argument, connection, timeout or SDK motion-gate issues first. Codes are listed below. |
| Robot service result | Ordinary response `success/message`; Master `result/message`; configuration service `result` and `diagnostics` | A received response still needs a business-result check. Master success is `MasterResult::kOk`; configuration success is `ConfigResult::kOk`. |
| Robot runtime fault | Part Client `on_heartbeat()`: `error_code/fault_mask/fault_codes`; Master `on_error()` / `on_degradation()`: `error_code/reason/device_errors` | Stop sending motion targets and record the subsystem, fault codes and reason. Resolve site causes before reset; contact support for persistent faults. |

Interpret device faults using the corresponding device definitions: `HandServiceResponse.sdk_error_code` comes from the hand device SDK, and `PowerCommandResponse.error_code` comes from the power service. North SDK call errors use `ErrorCode`; `kRemoteFailure` indicates a communication error reply.

| ErrorCode | Handling |
| --- | --- |
| `kOk` | Success |
| `kInvalidArgument` | Correct lengths, finite values, enum values, confirmations or configuration |
| `kNotConnected` | Connect successfully before calling |
| `kUnavailable` | Check device service availability and connectivity |
| `kTimeout` | Response wait timed out; inspect results before retrying side effects |
| `kSerialization` | Check matching software versions and retain error details and logs |
| `kTransport` | Retain the Zenoh/network error and inspect connectivity |
| `kStaleState` | Missing, malformed or stale state; wait for fresh state |
| `kOutcomeUnknown` | Master outcome unknown; inspect state without automatic retry |
| `kRemoteFailure` | Zenoh error reply received; inspect message |
| `kInternal` | Retain error details and logs, and contact support |
| `kMotionNotAllowed` | Check Master phase and channel/mode |
| `kNotSupported` | The current version or device does not support the requested operation or parameter; check arguments and version applicability |
| `kTimeSyncUnavailable` | Check host-component installation and the service error message. |
| `kTimeSyncPermission` | Use the authorized account; software mode also needs system-time authorization. |
| `kTimeSyncUnsupported` | Check the selected mode and NIC timestamping capabilities. |
| `kTimeSyncConflict` | Check other time services or conflicting synchronization sessions. |
| `kTimeSyncTimeout` | Check the link and interface, and whether synchronization continues converging. |
| `kTimeSyncLost` | Synchronization is not ready or has been lost; wait for readiness. |

After a timeout or error reply, the server may already have performed the operation. Inspect actual state before retrying.

## Python mapping

| C++ | Python |
| --- | --- |
| `NorthSDK::Create(config)` + `connect()` | `NorthSDK(config)` + `connect()` / `with NorthSDK(config)` |
| `Result<T>` | Return T directly; SDK failures raise NorthSDKError |
| `Status` | Return None on success; raise NorthSDKError on failure |
| `Side::kLeft` / `CommandChannel::kTeleoperation` | `Side.LEFT` / `CommandChannel.TELEOPERATION` |
| `connect_timeout` / `master_status_max_age` | `connect_timeout_ms` / `master_status_max_age_ms` |
| `latest_state(std::chrono::milliseconds(200))` | `latest_state(200)` |
| `sdk->connected()` / `subscription.active()` | `sdk.connected` / `subscription.active` |
| `std::optional<T>` | Value or None |
| `std::array / std::vector` | Python sequences |
| Binary std::string fields | `bytes` |

An incompatible Python argument type or length may also raise `TypeError`.

### Common Python signatures

Apart from the differences below, method names match C++ and enums use uppercase underscores. Subscription `options` may be omitted, defaulting to `SubscribeOptions()`. Synchronous services return response objects directly.

| Python call | Return |
| --- | --- |
| `NorthSDK(config)`; `sdk.connect()`; `sdk.close()` | SDK object; the latter two return `None` on success. |
| `sdk.time_sync_diagnostics()`; `sdk.robot_time_ns()` | `TimeSyncDiagnostics`; integer nanoseconds. |
| `client.latest_state(max_age_ms=1000)` | Part state; `latest_status/latest_imu/latest_battery` also use `max_age_ms=1000`. |
| `client.on_state(callback, options=SubscribeOptions())` | `Subscription`; Master uses `on_status`. |
| `sdk.master().on_heartbeat(subsystem, callback, options=SubscribeOptions())` | `Subscription`. |
| `sdk.master().set_mode(mode)`; `start_task(task_id)`; `stop_task(status=0)` | `MasterResponse`; check `result`. |
| `sdk.arm(side).send_joint_positions(positions)` | `None`; seven positions. The hand method of the same name takes twenty-two. |
| `sdk.torso().send_joint_command(command)` | `None`; `command` is a `JointCommand`. |
| `sdk.whole_body().send(channel, command)` | `None`; `command` is a `WholeBodyCommand`. |
| `sdk.video().on_jpeg(source, callback, options=VideoOptions())` | `Subscription`; `diagnostics(source)` returns `VideoDiagnostics`. |
| `sdk.alignment().on_frame(options, callback, callback_options=SubscribeOptions())` | `Subscription`; `diagnostics(subscription)` returns `AlignmentDiagnostics`. |
| `sdk.config().get(plugin_id="")`; `set(plugin_id, operations)` | `ConfigGetResponse` / `ConfigSetResponse`. |

Python tolerances are integer ns (`max_skew_ns`); waits and cache ages are integer ms (such as `timeout_ms` and `wait_timeout_ms`). `sdk.connected`, `subscription.active` and `sample.matched` are properties, without parentheses.

## Public capability scope

The following table summarizes the capabilities of each Client.

| Client | Public capability |
| --- | --- |
| Config | Instance discovery, descriptors, persistent SET/RESET |
| Master | Status, hardware health, events, heartbeat, task and lifecycle services |
| WholeBody | Multi-part position/velocity commands and command mirror |
| Chassis | State, heartbeat, cache, velocity, Motion/Force mode, enable and reset |
| Torso | State, heartbeat, cache, complete positions, enable, reset, mode and action cancel |
| Arm | Side-specific state, heartbeat, cache, complete positions, enable, mode, estop, reset and action cancel |
| Hand | State, tactile/e-skin, complete positions, modes, tactile/e-skin calibration, zero-calibration query/stop |
| Sensors | IMU, ultrasonic, tactile skin, Lidar and tactile-skin zeroing |
| Power | Board/battery state, heartbeat, read-only queries and explicitly confirmed power management |
| Video | Four AU decoders, JPEG callbacks and diagnostics; requires a video-enabled package and its runtime dependencies |
| Alignment | Source-timestamp matching and diagnostics for video, device and Master state |

Capabilities depend on installed and enabled robot devices. Check device state, SDK errors and business responses during operation.

## Client APIs

Each on_* returns `Result<Subscription>`; latest takes a maximum age. Usage rules and API declarations follow. For application workflows see [Application Development](Application%20Development.md).

### NorthSDK

Create and connect an instance, then use accessors to obtain Clients. version() reports the version; connected() reports local connection state.

```cpp
class NorthSDK {
public:
    static Result<std::unique_ptr<NorthSDK>> Create(const SdkConfig& config);
    ~NorthSDK();
    NorthSDK(const NorthSDK&) = delete;
    NorthSDK& operator=(const NorthSDK&) = delete;

    Status connect();
    void close();
    bool connected() const noexcept;
    CallbackDiagnostics callback_diagnostics() const;
    TimeSyncDiagnostics time_sync_diagnostics() const;
    Result<std::int64_t> robot_time_ns() const;
    static const char* version() noexcept;

    ConfigClient config();
    MasterClient master();
    WholeBodyClient whole_body();
    ChassisClient chassis();
    TorsoClient torso();
    ArmClient arm(Side side);
    HandClient hand(Side side);
    SensorClient sensors();
    PowerClient power();
    VideoClient video();
    AlignmentClient alignment();

};
```

| API | Parameters | Result and purpose | Notes |
| --- | --- | --- | --- |
| `Create(config)` | `config: SdkConfig` | C++ returns `Result<std::unique_ptr<NorthSDK>>`; creates without connecting | Validates channel, timeouts, and callback capacity. Python uses `NorthSDK(config)` and raises `NorthSDKError` on failure. |
| `connect()` | None | C++ `Status`; Python returns `None` on success | Establishes communication and prepares configured synchronization. By default a time-sync error retains communication; check `connected` and synchronization diagnostics separately. |
| `close()` | None | No result | Cancels subscriptions, clears caches, and closes connections. Recreate user subscriptions after reconnecting. Destruction and Python `with` exit also close. |
| `connected()` | None | `bool` | Reports whether the local communication session is established. Check heartbeats and state streams for device availability. |
| `callback_diagnostics()` | None | `CallbackDiagnostics` | Returns cumulative dropped/coalesced callback counts and the latest decode error. |
| `time_sync_diagnostics()` | None | `TimeSyncDiagnostics` | Reads synchronization state, offset and errors; see [Time-sync parameters](#time-sync-parameters). |
| `robot_time_ns()` | None | C++ `Result<int64_t>`; Python `int`, in ns | Reads a local clock synchronized to North gPTP. Returns an error if disconnected, disabled or not ready. |
| `version()` | None | Version string | Static; no SDK instance or connection is required. |
| `config()`, `master()`, `whole_body()`, `chassis()`, `torso()`, `sensors()`, `power()`, `video()`, `alignment()` | None | Corresponding Client | Clients cannot communicate after the SDK closes. |
| `arm(side)`, `hand(side)` | `side: Side` | Side-bound Client | Left/Right are from the robot's perspective. An invalid value is rejected by later calls. |

`SdkConfig.connect_endpoints` and `zenoh_config_path` select the target. Single-part motion also requires `command_channel` before creation. See [SdkConfig defaults](#sdkconfig-defaults).

### Subscription

A move-only subscription handle. Retain it to receive callbacks; destruction or `close()` cancels it.

```cpp
class Subscription {
public:
    Subscription();
    ~Subscription();
    Subscription(Subscription&&) noexcept;
    Subscription& operator=(Subscription&&) noexcept;
    Subscription(const Subscription&) = delete;
    Subscription& operator=(const Subscription&) = delete;

    void close();
    bool active() const noexcept;

};
```

| API | Parameters | Result and purpose | Notes |
| --- | --- | --- | --- |
| `close()` | None | Cancels the subscription | Call explicitly or rely on C++ destruction; Python may use `with subscription:`. No new callback starts after it returns. |
| `active()` | None | `bool` | Reports whether the handle remains open. |

### ConfigClient

```cpp
class ConfigClient {
public:
    Result<ConfigGetResponse> get(const std::string& plugin_id = {});
    Result<ConfigSetResponse> set(
        const std::string& plugin_id,
        const std::vector<ConfigFieldOperation>& operations);
};
```

`get()` queries robot-exposed configuration instances and fields. `set()` persists configuration changes. Use instance and field IDs returned by `get()`.

| API | Parameters and return |
| --- | --- |
| `get(plugin_id="")` | Empty queries all instances; a non-empty ID queries one instance. Returns `ConfigGetResponse`. |
| `set(plugin_id, operations)` | Takes an instance and a list of field operations. SET carries a value; RESET does not. Returns `ConfigSetResponse`. |

Require `result == ConfigResult::kOk`; inspect `diagnostics` on failure. Before writing, check the field descriptor’s type, range and application conditions. After writing, inspect `effective_value` and `pending_init`. After a write timeout, call `get()` to confirm the actual result.

See [Configuration data](#configuration-data) for types and fields.

### MasterClient

Provides runtime status, health, task events and system services. Use task IDs configured on the robot. on_heartbeat accepts a subsystem name or *. Check Master response.result, then observe state after transitions.

```cpp
class MasterClient {
public:
    Result<Subscription> on_status(std::function<void(const MasterStatus&)> callback,
                                   const SubscribeOptions& options = {});
    Result<Subscription> on_hardware_health(
        std::function<void(const SystemHardwareHealth&)> callback,
        const SubscribeOptions& options = {});
    Result<Subscription> on_task_start(std::function<void(const MasterEvent&)> callback,
                                       const SubscribeOptions& options = {});
    Result<Subscription> on_task_stop(std::function<void(const MasterEvent&)> callback,
                                      const SubscribeOptions& options = {});
    Result<Subscription> on_degradation(std::function<void(const MasterEvent&)> callback,
                                        const SubscribeOptions& options = {});
    Result<Subscription> on_error(std::function<void(const MasterEvent&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(const std::string& subsystem,
                                      std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<MasterStatus> latest_status(std::chrono::milliseconds max_age);

    Result<MasterResponse> set_mode(OperationMode mode);
    Result<MasterResponse> start_task(const std::string& task_id);
    Result<MasterResponse> stop_task(std::int32_t status = 0);
    Result<MasterResponse> reset();
    Result<MasterResponse> enter_ota();
    Result<MasterResponse> exit_ota();
    Result<MasterResponse> enter_estop();
    Result<MasterResponse> exit_estop();
    Result<ConfigSetResponse> set_health_requirement(const std::string& subsystem,
                                                     HealthRequirement requirement);
    Result<ConfigSetResponse> set_safety_guard_enabled(const std::string& guard_id, bool enabled);
    Result<BasicResponse> prepare_teleoperation();

};
```

| API | Parameters | Result data | Purpose and constraints |
| --- | --- | --- | --- |
| `on_status(callback, options)` | Common subscription parameters | `MasterStatus` | Subscribe to Master phase, operating mode, task ID, and degradation state. |
| `on_hardware_health(callback, options)` | Common subscription parameters | `SystemHardwareHealth` | Subscribe to subsystem health, safety guards, and host resource summary. |
| `on_task_start(callback, options)` | Common subscription parameters | `MasterEvent` | Subscribe to task-start acceptance, active state, and reason. |
| `on_task_stop(callback, options)` | Common subscription parameters | `MasterEvent` | Subscribe to task-stop events and final status. |
| `on_degradation(callback, options)` | Common subscription parameters | `MasterEvent` | Subscribe to system degradation events. |
| `on_error(callback, options)` | Common subscription parameters | `MasterEvent` | Subscribe to Master errors and per-device error details. |
| `on_heartbeat(subsystem, callback, options)` | `subsystem: string` and common subscription parameters | `Heartbeat` | Subscribe to a subsystem such as `"lidar"`; use `"*"` for all. A specific subsystem name must be non-empty and contain no wildcard/path special characters. |
| `latest_status(max_age)` | Maximum local receive age | `MasterStatus` | Actively read fresh Master cache; absent or expired data returns `kStaleState`. |
| `set_mode(mode)` | `OperationMode`: Teleoperation, Inference or Automation | `MasterResponse` | Changes Master operation mode; robot state determines whether switching is allowed. See [Application Development](Application%20Development.md#prepare-and-end-a-task) for the task preparation sequence. |
| `start_task(task_id)` | Non-empty, case-sensitive task ID, such as `inference`, `teleoperation`, `home` or `docking`; availability follows the delivery configuration | `MasterResponse` | Requests task start. After an accepted response, still wait for streamed RUNNING state. |
| `stop_task(status=0)` | 32-bit task exit status, default 0; other values are task-defined | `MasterResponse` | Requests normal task completion. `teleoperation` quiesces remote control, performs homing and finalizes recording while remaining RUNNING. An accepted response does not mean standstill. Observe status and feedback for other tasks too. Do not use as an emergency stop. |
| `reset()` | None | `MasterResponse` | Requests the Master recovery flow; allowed phases and result are decided by the robot state machine. |
| `enter_ota()` / `exit_ota()` | None | `MasterResponse` | Enter or leave OTA phase, affecting tasks and device operations. |
| `enter_estop()` | None | `MasterResponse` | Requests system emergency stop; check device feedback to confirm the outcome. |
| `exit_estop()` | None | `MasterResponse` | Starts asynchronous recovery: resets and re-enables both arms and torso, and returns both hands to position mode. Success means recovery started. Wait for Master to leave ESTOP and check device health and feedback. Confirm the site is ready first; do not restart the old control loop directly. |
| `set_health_requirement(subsystem, requirement)` | Subsystem ID and `HealthRequirement` such as `OK`, `WARNING`, or `OFF` | `ConfigSetResponse` | Persists Master health admission through Config and returns `ConfigSetResponse`. |
| `set_safety_guard_enabled(guard_id, enabled)` | Guard ID and enabled flag | `ConfigSetResponse` | Persists a safety-guard setting through Config and returns `ConfigSetResponse`; restrict to authorized management. |
| `prepare_teleoperation()` | None | `BasicResponse` | Prepares the teleoperation path in Master Teleoperation mode. Start the `teleoperation` task once preparation is complete. Check `BasicResponse.success/message`. |

Master services require a connected SDK and use `master_timeout` (15000 ms by default). C++ checks `Result<MasterResponse>` followed by `result == MasterResult::kOk`; Python checks `MasterResult.OK` on the returned response and raises `NorthSDKError` on SDK failures. Check `BasicResponse.success/message` for `prepare_teleoperation()`. Health-requirement and safety-guard settings persist through Config; check `ConfigResult::kOk` and diagnostics.

For `set_mode`, Teleoperation, Inference and Automation correspond to the same-named CommandChannels. Universal skips mode matching only when sending and still requires fresh RUNNING state. `before/after` are response snapshots and `message` explains the business result; continue observing `on_status` or `latest_status` to confirm actual mode and phase. See [Master mode service](Example%20Code%20Reference.md#master-mode-service).

Common SDK errors include `kNotConnected`, `kInvalidArgument`, `kTimeout`, `kTransport`, `kRemoteFailure` and `kOutcomeUnknown`. See [Common parameters and results](#common-parameters-and-results) for subscription and cache rules.

### WholeBodyClient

Combines position targets and chassis velocity commands for multiple parts.

```cpp
class WholeBodyClient {
public:
    Status send(CommandChannel channel, const WholeBodyCommand& command);
    Result<Subscription> on_command(std::function<void(const WholeBodyCommand&)> callback,
                                    const SubscribeOptions& options = {});

};
```

| API | Parameters | Result and purpose | Constraints |
| --- | --- | --- | --- |
| `send(channel, command)` | `channel: CommandChannel`; `command: WholeBodyCommand` | C++ `Status`; Python returns `None` on success | Channel must be Teleoperation, Inference, Automation, or Universal. Supply at least one part; only populated optionals update. Every part is locally validated. Parts execute separately; check feedback for each part. |
| `on_command(callback, options)` | Common subscription parameters | `WholeBodyCommand` callback | Records the combined command mirror; read device state for execution results. |

The `channel` argument of each `send()` call selects the sending channel. It still requires fresh RUNNING Master state.

### ChassisClient

Velocity uses m/s and rad/s and must be finite. `set_mode` explicitly selects overall Motion/Force mode; `mode` reads current mode from cached chassis heartbeat. Switching requires an idle chassis outside OTA.

```cpp
class ChassisClient {
public:
    Result<Subscription> on_state(std::function<void(const ChassisState&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<ChassisState> latest_state(std::chrono::milliseconds max_age);
    Status send_velocity(const ChassisVelocity& command);
    Result<ChassisModeResponse> set_mode(ChassisControlMode mode);
    Result<ChassisControlMode> mode(
        std::chrono::milliseconds max_age = std::chrono::milliseconds(500));
    Result<BasicResponse> enable(bool enabled = true);
    Result<BasicResponse> reset();

};
```

| API | Parameters | Result data | Purpose and constraints |
| --- | --- | --- | --- |
| `on_state(callback, options)` | Common subscription parameters | `ChassisState` | Subscribe to chassis velocity, joint, electrical, and mode state. |
| `on_heartbeat(callback, options)` | Common subscription parameters | `Heartbeat` | Subscribe to lifecycle, online masks, faults, and rates. |
| `latest_state(max_age)` | Maximum local receive age; Python default 1000 ms | `ChassisState` | Missing or expired data returns `kStaleState`. |
| `send_velocity(command)` | `ChassisVelocity` | `Status` / Python `None` | `vx`, `vy`, and `extension_velocity` are m/s; `vtheta` is rad/s. All values must be finite. Uses the single-part command channel and Master gate. |
| `set_mode(mode)` | `ChassisControlMode::kMotion` / `kForce` | `ChassisModeResponse` | Switches overall motion/force mode and returns `success/message`, previous_mode, and current_mode. After switching, confirm the device is enabled. |
| `mode(max_age=500ms)` | Maximum local heartbeat age | `ChassisControlMode` | Reads fresh cached heartbeat without a service request. First call or expired heartbeat returns `kStaleState`; Python uses `max_age_ms`. |
| `enable(enabled=true)` | `enabled: bool` | `BasicResponse` | Requests enable or disable; inspect business response and subsequent state. |
| `reset()` | None | `BasicResponse` | Requests chassis reset; determine enable/mode changes from device feedback. |

Mode switching requires an idle chassis outside OTA freeze. Heartbeat period may exceed the default 500 ms window, so applications may choose a larger age while still handling stale results. Velocity commands do not apply authoritative model limits in the SDK; use delivered limits. For normal stopping, keep sending zero velocity and use fresh `ChassisState.velocity` to require translation and rotation within application-defined rest tolerances for the required duration.

### TorsoClient

Eight joints are ordered body J1–J5 then neck J6–J8. Send complete positions. Reset leaves joints disabled; enable through the application workflow before motion. Services use torso_timeout.

![Torso joint numbers and position array indices](../../assets/en/SDK/Software%20Service%20Interface/torso-joint-order.svg)

Array indices start at zero: for example, J6 is position[5]. The figure shows array order; joint positions are in rad.

```cpp
class TorsoClient {
public:
    Result<Subscription> on_state(std::function<void(const TorsoState&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<TorsoState> latest_state(std::chrono::milliseconds max_age);
    Status send_joint_command(const JointCommand& command);
    Result<BasicResponse> enable(bool enabled = true);
    Result<BasicResponse> reset();
    Result<ModeResponse> set_mode(TorsoControlMode mode);
    Result<ModeResponse> set_mode(std::uint32_t mode);
    Result<BasicResponse> cancel_waypoints();

};
```

| API | Parameters | Result data | Purpose and constraints |
| --- | --- | --- | --- |
| `on_state(callback, options)` | Common subscription parameters | `TorsoState` | Subscribe to eight-joint state and electrical data. |
| `on_heartbeat(callback, options)` | Common subscription parameters | `Heartbeat` | Subscribe to torso health and rates. |
| `latest_state(max_age)` | Maximum local receive age; Python default 1000 ms | `TorsoState` | Missing or expired data returns `kStaleState`. |
| `send_joint_command(command)` | `JointCommand` | `Status` / Python `None` | Supports exactly eight position values in rad; name, velocity, and torque must be empty. Uses the single-part channel and Master gate. |
| `enable(enabled=true)` | `bool` | `BasicResponse` | Requests enable/disable and uses `torso_timeout`. |
| `reset()` | None | `BasicResponse` | Requests reset. The current contract leaves joints disabled after reset; explicitly re-enable before motion. |
| `set_mode(mode)` | Prefer `TorsoControlMode`; a `uint32_t` overload remains | `ModeResponse` | Switches Position/MIT device mode; check `success`, `previous_mode`, and `current_mode`. |
| `cancel_waypoints()` | None | `BasicResponse` | Requests waypoint cancellation; continue reading state to confirm the outcome. |

All torso services use `SdkConfig.torso_timeout`, 20000 ms by default.

### ArmClient

arm(Side) selects an arm with seven joints. Mode, enable, estop and reset are explicit services. Check business results and device state after mode changes.

```cpp
class ArmClient {
public:
    Side side() const noexcept;
    Result<Subscription> on_state(std::function<void(const ArmState&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<ArmState> latest_state(std::chrono::milliseconds max_age);
    Status send_joint_positions(const std::array<float, 7>& positions);
    Status send_joint_command(const JointCommand& command);
    Result<BasicResponse> enable(bool enabled = true);
    Result<ModeResponse> set_mode(ControlMode mode);
    Result<BasicResponse> estop(const std::string& reason = {});
    Result<BasicResponse> reset();
    Result<BasicResponse> cancel_waypoints();

};
```

Select the arm through `sdk.arm(Side)`; `side()` returns the Client’s bound side.

| API | Parameters | Result data | Purpose and constraints |
| --- | --- | --- | --- |
| `side()` | None | `Side` | Returns the side bound when the Client was created. |
| `on_state(callback, options)` | Common subscription parameters; default DropOldest | `ArmState` callback | Receive this arm’s state for feedback, monitoring or recording; retain the subscription. |
| `on_heartbeat(callback, options)` | Common subscription parameters | `Heartbeat` | Subscribe to lifecycle, joint online masks, faults, and rates for this arm. |
| `latest_state(max_age)` | Required C++ milliseconds; Python `max_age_ms=1000`, nonnegative | `ArmState` | Returns a copy subject to local receive age and automatically establishes reception; missing/expired samples return `kStaleState`. |
| `send_joint_positions(positions)` | C++ `std::array<float, 7>`; Python numeric sequence of length 7, finite values in rad | `Status` / Python `None` | Submits a complete target for this arm in model-defined joint order; no name reordering, sparse updates, velocity or torque control. |
| `send_joint_command(command)` | `JointCommand` | `Status` / Python `None` | Same constraints as `send_joint_positions`: exactly seven positions; name, velocity, and torque must be empty. |
| `enable(enabled=true)` | `bool` | `BasicResponse` | Requests enable/disable; check `success/message` and observe state. |
| `set_mode(mode)` | `ControlMode` | `ModeResponse` | Requests a device control mode. Position commands require the compatible mode defined by the robot procedure. Master `OperationMode` is a separate concept. |
| `estop(reason="")` | Optional reason string | `BasicResponse` | Requests an emergency stop for this arm. `reason` records the emergency-stop cause. |
| `reset()` | None | `BasicResponse` | Requests reset; reconfirm mode, enable state, heartbeat, and state afterward. |
| `cancel_waypoints()` | None | `BasicResponse` | Requests cancellation of an arm waypoint task; observe feedback to confirm. |

See [Common parameters and results](#common-parameters-and-results) for subscription and cache rules.

Position sending requires `SdkConfig.command_channel` set at creation, a connected SDK, Master RUNNING no older than `master_status_max_age`, matching Teleoperation/Inference/Automation channel and Master mode, and an enabled device in a compatible position mode. The SDK validates length, finite values and motion admission. See [Motion control](Application%20Development.md#motion-control) for target preparation.

Common send errors are `kInvalidArgument`, `kNotConnected`, `kStaleState`, `kMotionNotAllowed` and `kTransport`. Compare fresh `ArmState.joints.position` against the target using application tolerance and timeout. Stop sending on stale feedback, Master leaving RUNNING or errors. See [Send a single-arm target](Example%20Code%20Reference.md#send-a-single-arm-target).

Ordinary Arm services use `service_timeout`, 6000 ms by default. Use subsequent state to confirm mode, enable, reset and estop outcomes.

### HandClient

Each hand has twenty-two joints. Tactile finger channels 0–4 run from little finger to thumb, with kRaw/kDeform images. Python image payloads are bytes. Tactile calibration accepts enabled=true only. Zero-calibration status query and stop are available. Check success/message.

![Finger identities for tactile channels](../../assets/en/SDK/Software%20Service%20Interface/tactile-channels.svg)

Select the hand with hand(Side), then select the finger. Both hands use 0=little, 1=ring, 2=middle, 3=index, 4=thumb. finger=4 selects the thumb of the selected hand.

```cpp
class HandClient {
public:
    Side side() const noexcept;
    Result<Subscription> on_state(std::function<void(const HandState&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<Subscription> on_tactile_force(std::uint32_t finger,
                                          std::function<void(const TactileForce&)> callback,
                                          const SubscribeOptions& options = {});
    Result<Subscription> on_tactile_image(std::uint32_t finger, TactileImageKind kind,
                                          std::function<void(const CompressedImage&)> callback,
                                          const SubscribeOptions& options = {});
    Result<Subscription> on_eskin_force(std::function<void(const HandEskinForce&)> callback,
                                        const SubscribeOptions& options = {});
    Result<Subscription> on_eskin_raw(std::function<void(const HandEskinRaw&)> callback,
                                      const SubscribeOptions& options = {});
    Result<HandState> latest_state(std::chrono::milliseconds max_age);
    Status send_joint_positions(const std::array<float, 22>& positions);
    Status send_joint_command(const JointCommand& command);
    Result<HandServiceResponse> set_mode(HandMode mode);
    Result<HandServiceResponse> set_mode(std::uint32_t mode);
    Result<HandServiceResponse> calibrate_tactile(bool enabled = true);
    Result<HandServiceResponse> calibrate_eskin();
    Result<HandServiceResponse> zero_calibration_status();
    Result<HandServiceResponse> stop_zero_calibration();

};
```

Select the side with `sdk.hand(Side)`. All services use `service_timeout`. For `HandServiceResponse`, inspect `success/message` and, when relevant, result, mode, calibration state, and progress fields.

| API | Parameters | Callback/result | Purpose and constraints |
| --- | --- | --- | --- |
| `side()` | None | `Side` | Returns the bound hand side. |
| `on_state(callback, options)` | Common subscription parameters | `HandState` | Subscribe to 22-joint, electrical, and force information. |
| `on_heartbeat(callback, options)` | Common subscription parameters | `Heartbeat` | Subscribe to hand health and rates. |
| `on_tactile_force(finger, callback, options)` | `finger` 0–4 | `TactileForce` | Subscribe to six-axis tactile force; 0=little finger and 4=thumb. Out-of-range returns `kInvalidArgument`. |
| `on_tactile_image(finger, kind, callback, options)` | Finger 0–4 and Raw/Deform kind | `CompressedImage` | Subscribe to raw or deformation tactile images. `format` describes encoding and `data` is binary. |
| `on_eskin_force(callback, options)` | Common subscription parameters | `HandEskinForce` | Subscribe to fitted e-skin force. |
| `on_eskin_raw(callback, options)` | Common subscription parameters | `HandEskinRaw` | Subscribe to raw e-skin binary data. |
| `latest_state(max_age)` | Maximum local receive age; Python default 1000 ms | `HandState` | Missing or expired data returns `kStaleState`. |
| `send_joint_positions(positions)` | 22 finite rad values | `Status` / Python `None` | Submit a complete fixed-order target through the single-part channel and Master gate. |
| `send_joint_command(command)` | `JointCommand` | `Status` / Python `None` | Supports exactly 22 positions; name, velocity, and torque must be empty. |
| `set_mode(mode)` | Prefer `HandMode`; a `uint32_t` overload remains | `HandServiceResponse` | Switches hand device mode. |
| `calibrate_tactile(enabled=true)` | `enabled: bool` | `HandServiceResponse` | The current service accepts only `true`; `false` returns `kInvalidArgument`. |
| `calibrate_eskin()` | None | `HandServiceResponse` | Requests e-skin calibration and may change subsequent measurement baseline. |
| `zero_calibration_status()` | None | `HandServiceResponse` | Queries zero-calibration state/progress without starting it. |
| `stop_zero_calibration()` | None | `HandServiceResponse` | Requests stop of an active zero calibration; query status afterward. |

Tactile and e-skin streams may be high-rate or binary; do not perform expensive decoding or file I/O in callbacks.

### SensorClient

Provides IMU, ultrasonic, tactile skin and Lidar data. The SDK automatically decompresses Zstd Lidar data into points; no additional decompression library is required. Use `kind` to select `laser_shots[].points` or `sub_areas[].points`, containing coordinates in meters and reflectivity. Unsupported compression formats return `kNotSupported`.

```cpp
class SensorClient {
public:
    Result<Subscription> on_imu(std::function<void(const ImuSamples&)> callback,
                                const SubscribeOptions& options = {});
    Result<Subscription> on_ultrasonic(std::function<void(const UltrasonicSamples&)> callback,
                                       const SubscribeOptions& options = {});
    Result<Subscription> on_tactile_skin(std::function<void(const TactileSkinSamples&)> callback,
                                         const SubscribeOptions& options = {});
    Result<Subscription> on_lidar(LidarSource source,
                                  std::function<void(const LidarFrame&)> callback,
                                  const SubscribeOptions& options = {});
    Result<ImuSamples> latest_imu(std::chrono::milliseconds max_age);
    Result<BasicResponse> zero_tactile_skin(bool enabled = true);

};
```

| API | Parameters | Callback/result | Purpose and constraints |
| --- | --- | --- | --- |
| `on_imu(callback, options)` | Common subscription parameters | `ImuSamples` | Subscribe to one or more IMUs per frame. Angular velocity is rad/s, linear acceleration is m/s², and quaternion fields are w/x/y/z. |
| `on_ultrasonic(callback, options)` | Common subscription parameters | `UltrasonicSamples` | Subscribe to ultrasonic distance/status. Check both `valid` and `status`; distance is in mm. |
| `on_tactile_skin(callback, options)` | Common subscription parameters | `TactileSkinSamples` | Subscribe to body tactile-skin force points in N; check each skin's `valid`. |
| `on_lidar(source, callback, options)` | `source: LidarSource` | `LidarFrame` | Select chassis front, chest front, or chest rear Lidar. Invalid source returns `kInvalidArgument`; Zstd data are automatically decompressed into points. |
| `latest_imu(max_age)` | Maximum local receive age; Python default 1000 ms | `ImuSamples` | Read fresh IMU cache; missing or expired data returns `kStaleState`. |
| `zero_tactile_skin(enabled=true)` | `enabled: bool` | `BasicResponse` | `true` uses current force as the 0 N baseline; `false` restores fitted force. This changes interpretation of later readings; check `success/message`. |

Sensor availability depends on robot configuration. If a subscription produces no callbacks, check the corresponding data source and connection.

### PowerClient

Check sample freshness and reading.quality for power/battery data. Use a reading only when quality is kValid and value is present; zero may be valid. channel_command requires a specific node. Power-changing operations require confirm_power_change; release_estop and shutdown also require a nonempty reason.

```cpp
class PowerClient {
public:
    Result<Subscription> on_chest_state(std::function<void(const PowerBoardState&)> callback,
                                        const SubscribeOptions& options = {});
    Result<Subscription> on_chassis_state(std::function<void(const PowerBoardState&)> callback,
                                          const SubscribeOptions& options = {});
    Result<Subscription> on_battery(std::function<void(const BatterySystemState&)> callback,
                                    const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<BatterySystemState> latest_battery(std::chrono::milliseconds max_age);
    Result<PowerCommandResponse> channel_command(const PowerChannelCommand& command);
    Result<PowerCommandResponse> estop(PowerNode node, const std::string& reason);
    Result<PowerCommandResponse> release_estop(PowerNode node, const std::string& reason,
                                               bool confirm_power_change);
    Result<PowerCommandResponse> shutdown(PowerNode node, const std::string& reason,
                                          bool confirm_power_change);

};
```

Power streams may continue publishing when measurements are unavailable. Check sample freshness, `PowerDataQuality`, and optional `value` together; numeric zero may be valid.

| API | Parameters | Callback/result | Purpose and constraints |
| --- | --- | --- | --- |
| `on_chest_state(callback, options)` | Common subscription parameters | `PowerBoardState` | Subscribe to chest power-board readings, outputs, and switching state. |
| `on_chassis_state(callback, options)` | Common subscription parameters | `PowerBoardState` | Subscribe to chassis power-board state. |
| `on_battery(callback, options)` | Common subscription parameters | `BatterySystemState` | Subscribe to voltage, current, SOC, temperature, limits, and fault codes per pack. |
| `on_heartbeat(callback, options)` | Common subscription parameters | `Heartbeat` | Subscribe to power subsystem lifecycle and faults. |
| `latest_battery(max_age)` | Maximum local receive age; Python default 1000 ms | `BatterySystemState` | Read fresh battery cache, then validate quality/value for every reading. |
| `channel_command(command)` | `PowerChannelCommand` | `PowerCommandResponse` | Select a specific node (`kAll` is invalid), opcode, and operation fields. Read-only operations need no confirmation; state-changing opcodes require `confirm_power_change=true`. |
| `estop(node, reason)` | `PowerNode` and reason | `PowerCommandResponse` | Request emergency stop for a power node. Supply a traceable reason and check `success`, `error_code`, and later state. |
| `release_estop(node, reason, confirm_power_change=false)` | Node, non-empty reason, explicit confirmation | `PowerCommandResponse` | Releasing estop changes power state. Pass `true`; the default `false` prevents accidental calls. |
| `shutdown(node, reason, confirm_power_change=false)` | Node, non-empty reason, explicit confirmation | `PowerCommandResponse` | Shut down a node. Explicit confirmation is mandatory and connection/state streams may stop immediately. |

In `PowerChannelCommand`, `channel_id/action` apply to channel operations, `set_mask/clear_mask` to mask operations, and `heartbeat_period_ms` to the corresponding heartbeat-period command; the selected `PowerOpCode` determines the valid combination. Power services use `service_timeout`; after timeout, inspect remaining telemetry or the physical system before retrying.

### VideoClient

```cpp
class VideoClient {
public:
    Result<Subscription> on_jpeg(
        VideoSource source,
        std::function<void(const JpegFrame&)> callback,
        const VideoOptions& options = {});
    Result<VideoDiagnostics> diagnostics(VideoSource source) const;
};
```

Subscribe to camera JPEG images and inspect reception diagnostics. Video runtime dependencies are bundled; complete [Video environment setup](Application%20Development.md#video-environment-setup) before use.

| Method | Parameters | Return | Notes |
| --- | --- | --- | --- |
| `on_jpeg(source, callback, options)` | source: head left/right H.265 or wrist left/right H.264; callback: receives JpegFrame; options: VideoOptions | `Result<Subscription>` | Retain the handle. Each camera permits one active subscription, including use by alignment sessions. |
| `diagnostics(source)` | The subscribed VideoSource | `Result<VideoDiagnostics>` | Inspect received/output counts, drops, resets and the latest error. |

`VideoOptions` defaults to NVDEC, JPEG quality 85 and 1280×960 output. Configure `decoder_backend`, `jpeg_quality`, `output_width/output_height` and input queue capacities. Both dimensions set to 0 preserve source size. Select `kSoftware` explicitly for software decoding; there is no automatic fallback, and multi-stream or high-resolution performance is limited.

`JpegFrame` contains the source, header, dimensions and complete JPEG `data`. C++ references are valid only during the callback; copy for asynchronous use. Python data is `bytes`. Keep callbacks short; slow consumers may skip frames.

Invalid parameters return `kInvalidArgument`; an occupied camera returns `kUnavailable`. Inspect returned errors and `diagnostics()` for video environment failures.

### AlignmentClient

```cpp
class AlignmentClient {
public:
    Result<Subscription> on_frame(
        const AlignmentOptions& options,
        std::function<void(const AlignedFrame&)> callback,
        const SubscribeOptions& callback_options = {});
    Result<AlignmentDiagnostics> diagnostics(
        const Subscription& subscription) const;
};
```

Matches samples from multiple sources using timestamps in the same clock domain.

| Method | Parameters | Return | Notes |
| --- | --- | --- | --- |
| `on_frame(options, callback, callback_options)` | options: AlignmentOptions; callback: receives AlignedFrame | `Result<Subscription>` | Retain the handle. `callback_options` currently does not affect output behavior. Keep callbacks short. |
| `diagnostics(subscription)` | An active alignment subscription belonging to this SDK | `Result<AlignmentDiagnostics>` | Inspect complete/incomplete frames, timestamp anomalies and per-source matching counts. |

| AlignmentOptions | Description |
| --- | --- |
| `baseline` / `sources` | Baseline and additional sources. Head-left is the default baseline and automatically includes head-right. Other baselines match only explicit sources. Sources must not repeat. |
| `max_skew` / per-source `max_skew` | Matching tolerance; per-source settings take precedence. 0 requires identical timestamps. Unset values use the defaults below. |
| Per-source `direction` | Default `kAtOrBefore` selects data no later than the baseline. Alternatives are `kNearest` and `kAtOrAfter`. |
| `wait_timeout` | Alignment waiting time, default 20 ms. |
| `buffer_capacity` / `emit_incomplete` | Default per-source capacity 64; incomplete frames are emitted by default. |
| `video_options` | Shared VideoOptions for video sources, which occupy camera subscriptions. |

Default tolerances: arm/torso/chassis/hand joints/IMU 7.5 ms, eskin 15 ms, video 25 ms, finger tactile 50 ms, Master 150 ms. Python tolerance and wait attributes are `max_skew_ns` and `wait_timeout_ms`; `None` uses default tolerance.

`AlignedFrame` contains `timestamp_ns`, `baseline_sample`, `samples` in sources order, and `complete`. Status is Matched, Missing or OutOfTolerance. See [Video and alignment data](#video-and-alignment-data) for reading results. `offset_ns` is the candidate timestamp minus the baseline timestamp.

Head JPEG uses RK SEI source time; other devices usually use Header time. Confirm a common clock domain before cross-source alignment. See [Example Code Reference](Example%20Code%20Reference.md) for usage.

## Time-sync parameters

`SdkConfig.time_sync` uses the fields below. Software mode adjusts host system time; see [Time synchronization](Application%20Development.md#time-synchronization) for host setup.

| TimeSyncOptions field | Default and constraints |
| --- | --- |
| `enabled` | `true`; disable to skip synchronization. |
| `mode` | `TimeSyncMode::kSoftware`; alternatively `kHardware`. Python: `TimeSyncMode.SOFTWARE/HARDWARE`. |
| `interface` | Empty; select the physical wired NIC from the robot endpoint route. Ambiguous selection is an error. |
| `timeout` / Python `timeout_ms` | 60000 ms, strictly positive; initial synchronization preparation deadline. |
| `failure_policy` | `TimeSyncFailurePolicy::kKeepConnected`: initial synchronization error retains communication. `kFailConnection` closes communication. Python: `KEEP_CONNECTED/FAIL_CONNECTION`. |
| `software_offset_threshold_ns` | 1000000 ns; range 1–1000000000 ns, for software readiness only. Hardware mode uses a fixed 50 ns threshold. |

`TimeSyncDiagnostics.state` is `Disabled`, `Preparing`, `Ready`, `Failed` or `Lost` (C++ enum names have a `k` prefix; Python uses uppercase underscores). Readiness requires ten consecutive new observations with absolute offset below the threshold. Check again after synchronization loss during operation.

| Diagnostic field | Meaning |
| --- | --- |
| `error` | SDK error code and message. |
| `mode/interface/phc_device` | Selected mode, NIC and hardware clock device; software mode has no PHC device. |
| `clock_source/system_time_owned` | Clock source, `CLOCK_REALTIME` or `PHC`, and whether this component manages system-time synchronization. |
| `offset_ns/offset_threshold_ns` | Observed offset and readiness threshold in ns; the threshold determines synchronization readiness. |
| `stable_samples/required_samples` | Consecutive acceptable observations and required count. |
| `sample_age` / Python `sample_age_ms` | Diagnostic sample age; over one second is no longer ready. |

## Data types and fields

The excerpts below cover public types and fields used by the documented APIs, and result-reading methods. Refer to the delivered public headers for declarations. Plan command targets in the application. Inspect quality, heartbeat and freshness before using state data.

### Common field meanings

| Field | Units and reading rules |
| --- | --- |
| `JointState` / `JointElectricalState` | Equal indices identify the same joint. See [Joint arrays and coordinates](Application%20Development.md#joint-arrays-and-coordinates). Read valid fields within the actual array lengths. |
| `ChassisVelocity` / `ChassisState.velocity` | Body +x forward, +y left; positive yaw is counterclockwise viewed from above. `vx/vy` are m/s and `vtheta` is rad/s. Feedback is `velocity.linear.x/y` and `velocity.angular.z`. |
| `Header.stamp_ns` | Source time; 0 means unavailable. `latest_*` ages data from local reception. |
| `Header.frame_id` / `Pose` / `Wrench` / `LidarPoint` | `frame_id` identifies a source or coordinate frame. Points are in m, forces in N and torques in Nm. Apply the delivered coordinate definitions before combining devices. |
| `ImuSamples.imus` | Each entry is one IMU, with rad/s angular velocity and m/s² linear acceleration. Identify sources by their Headers and use the mounting definition when interpreting orientation. |
| `HandState.force_info` | Raw integer force-sensor information from the device. Use `on_tactile_force()` for fingertip six-axis forces. |
| `Heartbeat` / `MasterDeviceError` | Heartbeat `expected_mask/online_mask/fault_mask` are device bitmasks. In both types, `fault_codes` are device fault codes. Retain the subsystem and error message for diagnosis. |
| `BatteryPack` | Pack and cell voltages in V, current in A, `soc/soh` in percent (0–100), power limits in W and temperatures in °C. Check `quality/value` per `PowerReading`. |
| `PowerBoardState.readings` | Read by `name` and `unit`. Absent `outputs[].enabled` means unknown. |
| `PowerSampleMetadata` | `clock_domain` identifies the power sample’s clock domain; confirm a common clock domain before comparing timestamps. |

### Configuration data

| Type or field | Meaning |
| --- | --- |
| `ConfigGetResponse` / `ConfigSetResponse` | `result` is the business outcome and `diagnostics` explains it. Queries return `instances`; writes return an optional `instance`. |
| `ConfigInstanceInfo` / `ConfigFieldInfo` | `plugin_id` identifies the instance, `field_id` the field, and `field_descriptor` its type, unit, constraints and safety conditions. |
| `ConfigFieldOperation` | `field_id`, `operation` and optional `value`. `ConfigValue` supports bool, int64, finite double, string, double array and int64 array. Python constructors are `boolean/integer/real/string/double_array/integer_array()`. |
| `effective_value` / `saved_override` | Current effective value and saved override; either may be absent. |
| `apply_policy` / `pending_init` | Application policy is IMMEDIATE, SAFE_STATE or INIT_ONLY. `pending_init` indicates a change awaiting initialization. |
| `ConfigDiagnostic` | `code/field_id/message` identify the problem; optional `element_index` identifies an array element. |

On `RecoveryRequired`, restore device state before changing configuration.

### Video and alignment data

| Type | Essential fields and rules |
| --- | --- |
| `VideoSource` | `kHeadLeft/kHeadRight/kWristLeft/kWristRight`; Python: `HEAD_LEFT/HEAD_RIGHT/WRIST_LEFT/WRIST_RIGHT`. |
| `VideoOptions` | `jpeg_quality` defaults to 85 (1–100); `decoder_backend` defaults to NVDEC. Default dimensions are 1280×960; both zero preserve input size. `max_pending_frames` defaults to 32 (1–4096), `max_pending_bytes` to 16 MiB, and `max_au_bytes` to 4 MiB (positive, at most 64 MiB and no larger than `max_pending_bytes`). Width and height must not exceed 8192. |
| `JpegFrame` | `source/header/width/height/data` describe a complete JPEG. Optional `source_timestamp_ns` requires checking `timestamp_status` (Valid/Missing/Invalid/NotApplicable). `sdk_latency_ns` covers input reception to C++ callback entry; `pipeline_latency_ns` covers processing inside the decoder pipeline. Neither includes browser display or Python GIL wait. |
| `VideoDiagnostics` | `active/waiting_for_keyframe`, `received_au_count/jpeg_frame_count`, drop/reset counters and `last_error` distinguish no input, waiting for a keyframe and decode failure. |
| `AlignmentSource` | `kind` selects the type. Arms/hands use `side`; tactile sources also use `finger/tactile_image_kind`; video uses `video_source`. Match controls are `direction` and optional `max_skew`; Python tolerance is `max_skew_ns`. |
| `AlignmentDataKind` | Supports ChassisState, TorsoState, ArmState, HandState, TactileForce, TactileImage, HandEskinForce, HandEskinRaw, ImuSamples, TactileSkinSamples, VideoJpeg and MasterStatus. C++ uses a `k` prefix; Python uses uppercase underscores. |
| `AlignedSample` | `source/status/timestamp_ns/offset_ns/value`. When `matched()` (Python property `matched`) is true, read the matched result with C++ `get<T>()` or Python `value`. |
| `AlignedFrame` | `timestamp_ns/baseline_sample` are the baseline time and data. `samples` follows explicit `sources` order. `complete` means all required sources matched. Default stereo also exposes left/right results through `left_image/right_sample`. |
| `AlignmentDiagnostics` | Frame counts: `evaluated_frame_count/emitted_frame_count/incomplete_frame_count`. Per-source `baseline/sources` expose `received_count/matched_count/missing_count/out_of_tolerance_count` to diagnose missing input or tolerance failures. `invalid_timestamp_count/regression_count` identify invalid or regressing time. |

Before computing data latency from `robot_time_ns()`, confirm that the source uses the same gPTP domain. For head video, use `source_timestamp_ns` with a valid `timestamp_status`.

### Basic type declarations

```cpp
enum class ErrorCode {
    kOk = 0,
    kInvalidArgument,
    kNotConnected,
    kUnavailable,
    kTimeout,
    kSerialization,
    kTransport,
    kStaleState,
    kOutcomeUnknown,
    kRemoteFailure,
    kInternal,
    kMotionNotAllowed,
    kNotSupported,
    kTimeSyncUnavailable,
    kTimeSyncPermission,
    kTimeSyncUnsupported,
    kTimeSyncConflict,
    kTimeSyncTimeout,
    kTimeSyncLost,
};

struct Error {
    ErrorCode code = ErrorCode::kOk;
    std::string message;
};

class Status {
public:
    bool ok() const noexcept;
    explicit operator bool() const noexcept;
    ErrorCode code() const noexcept;
    const std::string& message() const noexcept;
};

template <typename T>
class Result {
public:
    bool ok() const noexcept;
    explicit operator bool() const noexcept;
    T& value() &;
    const T& value() const&;
    T&& value() &&;
    const Error& error() const noexcept;
};

enum class Side { kLeft = 1, kRight = 2 };
enum class ControlMode {
    kJointPosition = 0,
    kJointPd = 1,
    kJointTorque = 2,
    kSpeed = 3,
    kFloating = 4,
    kMotorPd = 5,
    kCartesianImpedance = 6,
};
enum class LifecyclePhase { kUnspecified = 0, kInit, kStandby, kRunning, kError, kFatal };
enum class OperationMode { kUnspecified = 0, kTeleoperation, kInference, kAutomation };
enum class MasterPhase { kUnspecified = 0, kInit, kStandby, kRunning, kError, kOta, kEstop };
enum class CommandChannel {
    kUnspecified = 0,
    kTeleoperation = 1,
    kInference = 2,
    kAutomation = 3,
    kUniversal = 4,
};
enum class TorsoControlMode { kPosition = 0, kMit = 1 };
enum class HandMode {
    kLegacyPosition = 0,
    kLegacyZeroForce = 1,
    kZeroForce = 10,
    kPosition = 13,
    kAdmittance = 14,
    kMit = 15,
};
enum class HealthRequirement { kUnspecified = 0, kOk, kWarning, kOff };
enum class HardwareHealthVerdict { kOk = 0, kWarning, kFault, kStale, kNeverSeen };
enum class MasterResult {
    kUnspecified = 0,
    kOk,
    kInvalidRequest,
    kInvalidPhase,
    kUnknownTarget,
    kBusy,
    kUnavailable,
    kHealthCheckFailed,
    kExecutionFailed,
    kOutcomeUnknown,
    kInternalError,
};

struct Header {
    std::int64_t stamp_ns = 0;
    std::int64_t system_time_ns = 0;
    std::uint32_t seq = 0;
    std::string key;
    std::string frame_id;
};

struct Vector3 {
    float x = 0, y = 0, z = 0;
};
struct Quaternion {
    float w = 1, x = 0, y = 0, z = 0;
};
struct Pose {
    Vector3 position;
    Quaternion orientation;
};
struct Twist {
    Vector3 linear;
    Vector3 angular;
};
struct Wrench {
    Vector3 force;
    Vector3 torque;
};

struct JointState {
    std::vector<std::string> name;
    std::vector<float> position;
    std::vector<float> velocity;
    std::vector<float> torque;
};

struct JointCommand {
    std::vector<std::string> name;
    std::vector<float> position;
    std::vector<float> velocity;
    std::vector<float> torque;
};

struct JointElectricalState {
    std::vector<std::string> name;
    std::vector<float> temperature_celsius;
    std::vector<float> current;
    std::vector<float> bus_voltage;
};

struct HeartbeatMetric {
    std::uint32_t kind = 0;
    std::uint32_t instance = 0;
    float value = 0;
};

struct Heartbeat {
    Header header;
    std::string subsystem;
    std::uint32_t seq = 0;
    LifecyclePhase phase = LifecyclePhase::kUnspecified;
    std::uint32_t severity = 0;
    ControlMode control_mode = ControlMode::kJointPosition;
    std::uint32_t expected_mask = 0;
    std::uint32_t online_mask = 0;
    std::uint32_t fault_mask = 0;
    std::vector<std::uint32_t> fault_codes;
    std::uint32_t error_code = 0;
    float feedback_age_ms = 0;
    float control_rate_hz = 0;
    float state_rate_hz = 0;
    float publish_rate_hz = 0;
    float bus_load_pct = 0;
    std::vector<HeartbeatMetric> metrics;
};

struct MasterStatus {
    Header header;
    MasterPhase phase = MasterPhase::kUnspecified;
    OperationMode mode = OperationMode::kUnspecified;
    std::string task_id;
    bool degraded = false;
};

struct HardwareHealth {
    Heartbeat heartbeat;
    std::uint64_t receive_age_ms = 0;
    HardwareHealthVerdict verdict = HardwareHealthVerdict::kNeverSeen;
    HealthRequirement requirement = HealthRequirement::kUnspecified;
};

struct SafetyGuardStatus {
    std::string guard_id;
    bool enabled = false;
};

struct HostResourceMetrics {
    float cpu_temperature_celsius = 0;
    float cpu_load_pct = 0;
    float memory_used_pct = 0;
    std::vector<float> cpu_core_load_pct;
};

struct CommandChannelRate {
    CommandChannel channel = CommandChannel::kUnspecified;
    float receive_hz = 0;
    float accepted_hz = 0;
};

struct SystemHardwareHealth {
    Header header;
    std::uint32_t worst_severity = 0;
    std::vector<HardwareHealth> subsystems;
    MasterStatus master_status;
    std::vector<SafetyGuardStatus> safety_guards;
    HostResourceMetrics host;
    std::vector<CommandChannelRate> command_rates;
};

struct MasterDeviceError {
    std::string subsystem_id;
    HealthRequirement required = HealthRequirement::kUnspecified;
    HardwareHealthVerdict actual = HardwareHealthVerdict::kNeverSeen;
    std::uint32_t error_code = 0;
    std::uint32_t fault_mask = 0;
    std::vector<std::uint32_t> fault_codes;
};

struct MasterEvent {
    Header header;
    std::string task_id;
    bool accepted = false;
    bool active = false;
    std::int32_t status = 0;
    std::uint32_t error_code = 0;
    std::string reason;
    std::string guard_id;
    std::vector<MasterDeviceError> device_errors;
};

struct ArmState {
    Header header;
    Side side = Side::kLeft;
    Pose cartesian;
    JointState joints;
    Wrench wrench;
    JointElectricalState electrical;
};

struct ArmCommand {
    JointCommand joints;
};

struct HandForceInfo {
    std::uint32_t online = 0;
    std::array<std::int32_t, 4> strain_sensors{};
    std::int32_t torque_x = 0;
    std::int32_t torque_y = 0;
    std::int32_t force_z = 0;
    std::int32_t temperature_celsius = 0;
    std::int32_t error_code = 0;
};

struct HandState {
    Header header;
    Side side = Side::kLeft;
    JointState joints;
    JointElectricalState electrical;
    std::vector<HandForceInfo> force_info;
};

struct HandCommand {
    JointCommand joints;
};

struct TorsoState {
    Header header;
    JointState joints;
    JointElectricalState electrical;
};

struct TorsoCommand {
    JointCommand joints;
};

struct ChassisState {
    Header header;
    Twist velocity;
    JointState joints;
    JointElectricalState electrical;
    std::vector<std::uint32_t> joint_mode;
};

struct ChassisVelocity {
    float vx = 0;
    float vy = 0;
    float vtheta = 0;
    float extension_velocity = 0;
};

enum class ChassisControlMode { kMotion = 0, kForce = 1 };

struct ImuSample {
    Header header;
    Quaternion orientation;
    Vector3 angular_velocity;
    Vector3 linear_acceleration;
    Quaternion aligned_orientation;
    Vector3 gravity;
};

struct ImuSamples {
    std::uint64_t stamp_ns = 0;
    std::vector<ImuSample> imus;
};

struct WholeBodyCommand {
    std::optional<ArmCommand> left_arm;
    std::optional<ArmCommand> right_arm;
    std::optional<HandCommand> left_hand;
    std::optional<HandCommand> right_hand;
    std::optional<TorsoCommand> torso;
    std::optional<ChassisVelocity> chassis;
};

struct BasicResponse {
    bool success = false;
    std::string message;
};

struct ModeResponse : BasicResponse {
    std::uint32_t previous_mode = 0;
    std::uint32_t current_mode = 0;
};

struct ChassisModeResponse : BasicResponse {
    ChassisControlMode previous_mode = ChassisControlMode::kMotion;
    ChassisControlMode current_mode = ChassisControlMode::kMotion;
};

enum class MasterResponseDetailKind {
    kNone = 0,
    kStartTask,
    kStopTask,
    kSetMode,
    kHealthRequirement,
    kSafetyGuard,
    kPhaseTransition,
};

struct MasterResponseDetail {
    MasterResponseDetailKind kind = MasterResponseDetailKind::kNone;
    std::string task_id;
    std::int32_t status = 0;
    OperationMode requested_mode = OperationMode::kUnspecified;
    std::string subsystem_id;
    HealthRequirement requirement = HealthRequirement::kUnspecified;
    std::string guard_id;
    bool enabled = false;
    std::uint32_t phase_transition_operation = 0;
};

struct MasterResponse {
    Header header;
    MasterResult result = MasterResult::kUnspecified;
    std::string message;
    MasterStatus before;
    MasterStatus after;
    MasterResponseDetail detail;
};

struct HandServiceResponse : BasicResponse {
    std::uint32_t result = 0;
    std::uint32_t previous_mode = 0;
    std::uint32_t current_mode = 0;
    std::int32_t sdk_error_code = 0;
    std::uint32_t calibration_state = 0;
    std::uint32_t progress_percent = 0;
};

struct CompressedImage {
    Header header;
    std::string format;
    std::string data;
};

struct TactileForce {
    Header header;
    std::uint32_t finger = 0;
    Wrench wrench;
};

enum class TactileImageKind { kRaw = 0, kDeform = 1 };

struct HandEskinForce {
    Header header;
    std::int32_t frame_id = 0;
    std::int32_t channel = 0;
    std::vector<float> force_n;
};

struct HandEskinRaw {
    Header header;
    std::int32_t frame_id = 0;
    std::int32_t channel = 0;
    std::string data;
};

enum class UltrasonicStatus {
    kUnspecified = 0,
    kValid,
    kNoTarget,
    kInterference,
    kNotReady,
    kInvalid,
};

struct UltrasonicSample {
    Header header;
    std::uint32_t distance_mm = 0;
    std::uint32_t raw_value = 0;
    float temperature_celsius = 0;
    UltrasonicStatus status = UltrasonicStatus::kUnspecified;
    bool valid = false;
};

struct UltrasonicSamples {
    std::uint64_t stamp_ns = 0;
    std::vector<UltrasonicSample> samples;
};

struct TactileSkinPoint {
    std::string serial_id;
    std::uint32_t row = 0;
    std::uint32_t col = 0;
    float force_n = 0;
};

struct TactileSkin {
    Header header;
    std::vector<TactileSkinPoint> points;
    bool valid = false;
};

struct TactileSkinSamples {
    std::uint64_t stamp_ns = 0;
    std::vector<TactileSkin> skins;
};

enum class LidarSource { kChassisFront = 0, kChestFront, kChestRear };

enum class LidarPayloadKind {
    kNone = 0,
    kLaserShots,
    kSubAreas,
    kCompressedLaserShots,
    kCompressedSubAreas,
};

struct LidarPoint {
    float x = 0, y = 0, z = 0;
    std::uint32_t reflectivity = 0;
};

struct LidarLaserShot {
    std::uint64_t timestamp_ns = 0;
    float azimuth_rad = 0;
    std::vector<LidarPoint> points;
};

struct LidarSubArea {
    std::uint64_t timestamp_ns = 0;
    std::uint32_t row_id = 0;
    std::uint32_t column_id = 0;
    std::vector<LidarPoint> points;
};

struct LidarFrame {
    Header header;
    std::uint64_t stamp_ns = 0;
    LidarPayloadKind kind = LidarPayloadKind::kNone;
    std::vector<LidarLaserShot> laser_shots;
    std::vector<LidarSubArea> sub_areas;
    std::string compression;
    std::uint32_t packed_group_count = 0;
    std::uint32_t packed_point_count = 0;
    std::string packed_groups;
    std::string packed_points;
};

enum class PowerDataQuality {
    kUnspecified = 0,
    kValid,
    kNotReceived,
    kStale,
    kSourceOffline,
    kSensorInvalid,
    kNotSupported,
    kUnverified,
};
enum class PowerLinkState { kUnknown = 0, kOnline, kOffline };
enum class PowerClockDomain { kUnknown = 0, kDeviceMonotonic, kGptp };

struct PowerReading {
    std::optional<float> value;
    PowerDataQuality quality = PowerDataQuality::kUnspecified;
    std::uint64_t sample_time_ns = 0;
};

struct NamedPowerReading {
    std::string name;
    std::string unit;
    PowerReading reading;
};

struct PowerSampleMetadata {
    bool received = false;
    bool transport_online = false;
    PowerLinkState source_link = PowerLinkState::kUnknown;
    std::int64_t received_at_ns = 0;
    std::uint64_t receive_age_ms = 0;
    std::uint64_t sample_time_ns = 0;
    std::uint64_t envelope_time_ns = 0;
    PowerClockDomain clock_domain = PowerClockDomain::kUnknown;
    std::uint32_t envelope_seq = 0;
    std::uint32_t sample_seq = 0;
};

struct PowerOutput {
    std::string name;
    std::optional<bool> enabled;
};

struct PowerBoardState {
    Header header;
    PowerSampleMetadata sample;
    std::vector<NamedPowerReading> readings;
    std::uint32_t operating_state = 0;
    std::vector<PowerOutput> outputs;
    std::optional<bool> switching;
};

struct BatteryPack {
    std::uint32_t pack_id = 0;
    PowerLinkState online = PowerLinkState::kUnknown;
    PowerDataQuality quality = PowerDataQuality::kUnspecified;
    PowerReading voltage;
    PowerReading current;
    PowerReading soc;
    PowerReading soh;
    PowerReading minimum_cell_voltage;
    PowerReading maximum_cell_voltage;
    PowerReading charge_power_limit;
    PowerReading discharge_power_limit;
    PowerReading ambient_temperature;
    std::vector<PowerReading> cell_temperatures;
    std::vector<PowerReading> mos_temperatures;
    std::optional<std::uint32_t> fault_code;
    std::optional<std::uint32_t> alarm_code;
    std::optional<std::uint32_t> protection_code;
};

struct BatterySystemState {
    Header header;
    PowerSampleMetadata sample;
    std::vector<BatteryPack> packs;
};

enum class PowerNode : std::uint32_t {
    kAll = 0x00,
    kChassis = 0x10,
    kBody = 0x20,
    kRt1186 = 0x30,
};

enum class PowerOpCode : std::uint32_t {
    kNop = 0,
    kPing = 1,
    kGetProtocolVersion = 2,
    kSetChannel = 16,
    kSetMask = 17,
    kGetStatus = 18,
    kAllOn = 19,
    kAllOff = 20,
    kSystemSleep = 32,
    kSystemWakeup = 33,
    kSystemGetStatus = 34,
    kSystemReset = 35,
    kSystemSetHeartbeatPeriod = 36,
};

struct PowerChannelCommand {
    PowerNode node = PowerNode::kBody;
    PowerOpCode opcode = PowerOpCode::kNop;
    std::uint32_t channel_id = 0;
    std::uint32_t action = 0;
    std::uint32_t set_mask = 0;
    std::uint32_t clear_mask = 0;
    std::uint32_t heartbeat_period_ms = 0;
    bool confirm_power_change = false;
};

struct PowerCommandResponse : BasicResponse {
    std::uint32_t node = 0;
    std::uint32_t error_code = 0;
    std::uint32_t state_mask = 0;
};

enum class QueuePolicy {
    kDropOldest = 0,
    kLatestOnly,
    kReliable,
};

struct SubscribeOptions {
    QueuePolicy queue_policy = QueuePolicy::kDropOldest;
};

struct SdkConfig {
    std::string zenoh_config_path;
    std::vector<std::string> connect_endpoints;
    std::chrono::milliseconds connect_timeout{5000};
    std::chrono::milliseconds service_timeout{6000};
    std::chrono::milliseconds master_timeout{15000};
    std::chrono::milliseconds torso_timeout{20000};
    std::size_t callback_queue_capacity = 256;
    std::chrono::milliseconds master_status_max_age{500};
    CommandChannel command_channel = CommandChannel::kUnspecified;
    TimeSyncOptions time_sync;
};

struct CallbackDiagnostics {
    std::uint64_t dropped_callback_count = 0;
    std::uint64_t coalesced_callback_count = 0;
    Error last_decode_error;
};
```

## Lifecycle and diagnostics

Rebuild user subscriptions after reconnect. `dropped_callback_count` and `coalesced_callback_count` count cumulative dropped and coalesced callbacks; `last_decode_error` is the latest decode error.
