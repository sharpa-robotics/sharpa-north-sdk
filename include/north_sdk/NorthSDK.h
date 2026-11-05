#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <variant>
#include <vector>

#if defined(_WIN32)
#if defined(NORTHSDK_BUILDING_LIBRARY)
#define NORTHSDK_API __declspec(dllexport)
#else
#define NORTHSDK_API __declspec(dllimport)
#endif
#else
#define NORTHSDK_API __attribute__((visibility("default")))
#endif

#define NORTHSDK_VERSION "1.2.0"

namespace north {

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
    // Appended to preserve existing error values. Transport may remain connected.
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

class NORTHSDK_API Status {
   public:
    Status() = default;
    Status(ErrorCode code, std::string message = {});

    static Status Ok();
    bool ok() const noexcept;
    explicit operator bool() const noexcept;
    ErrorCode code() const noexcept;
    const std::string& message() const noexcept;

   private:
    Error error_;
};

template <typename T>
class Result {
   public:
    static Result Success(T value) {
        Result result;
        result.value_.emplace(std::move(value));
        return result;
    }

    static Result Failure(ErrorCode code, std::string message) {
        Result result;
        result.error_ = {code, std::move(message)};
        return result;
    }

    bool ok() const noexcept { return value_.has_value(); }
    explicit operator bool() const noexcept { return ok(); }
    T& value() & { return value_.value(); }
    const T& value() const& { return value_.value(); }
    T&& value() && { return std::move(value_.value()); }
    const Error& error() const noexcept { return error_; }

   private:
    std::optional<T> value_;
    Error error_{ErrorCode::kInternal, "result has no value"};
};

enum class ChassisControlMode { kMotion = 0, kForce = 1 };
enum class ChassisCommandMode { kKinematic = 0, kRaw = 1 };

enum class Side { kLeft = 1, kRight = 2 };
enum class SpaceMode { kJoint = 1, kCartesian = 2 };
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
    // Malformed/unrepresentable protobuf timestamps decode as zero.
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

// Motion sends accept only complete position arrays in fixed device joint order.
// name, velocity and torque must be empty; DTO fields remain for read/source compatibility.
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
    // Arm control mode; for chassis use chassis_control_mode instead.
    ControlMode control_mode = ControlMode::kJointPosition;
    std::optional<ChassisControlMode> chassis_control_mode;
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
    SpaceMode mode = SpaceMode::kJoint;
    JointCommand joints;
    Pose cartesian;
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
    SpaceMode mode = SpaceMode::kJoint;
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

struct ChassisRawCommand {
    std::array<float, 4> wheel_position{};
    std::array<float, 4> wheel_velocity{};
    std::array<float, 4> wheel_feedforward{};
    std::array<float, 4> steer_position{};
    std::array<float, 4> steer_velocity{};
    std::array<float, 4> steer_feedforward{};
};

struct ChassisPoseCommand {
    float target_x_m = 0;
    float target_y_m = 0;
    float target_theta_rad = 0;
    float max_linear_velocity_mps = 0;
    float max_angular_velocity_rps = 0;
    bool cancel = false;
};

enum class ChassisSteerStrategy { kClosedLoopPosition = 0, kForceCurrentMit = 1 };
enum class ChassisWheelStrategy { kClosedLoopSpeed = 0, kForceCurrentMit = 1 };
enum class ChassisStretchStrategy { kProfileVelocity = 0, kProfilePosition = 1 };

// Compatibility DTO; SDK strategy services are disabled and never send requests.
struct ChassisStrategyRequest {
    std::optional<ChassisCommandMode> command_mode;
    std::optional<ChassisSteerStrategy> steer;
    std::optional<ChassisWheelStrategy> wheel;
    std::optional<ChassisStretchStrategy> stretch;
};

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

// Joint order and count (22) follow the raw glove space consumed by retargeting.
struct GloveRaw {
    JointCommand joints;
    std::optional<ImuSample> imu;
};

struct GamepadState {
    Pose pose;
    bool valid = false;
    bool tracked = false;
};

struct WholeBodyRaw {
    Pose head_pose;
    GamepadState left_gamepad;
    GamepadState right_gamepad;
    std::vector<Pose> full_body_joint_poses;
    bool confident = false;
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

struct ChassisStrategyResponse : BasicResponse {
    ChassisCommandMode command_mode = ChassisCommandMode::kKinematic;
    ChassisSteerStrategy steer = ChassisSteerStrategy::kClosedLoopPosition;
    ChassisWheelStrategy wheel = ChassisWheelStrategy::kClosedLoopSpeed;
    ChassisStretchStrategy stretch = ChassisStretchStrategy::kProfileVelocity;
    ChassisCommandMode previous_command_mode = ChassisCommandMode::kKinematic;
    ChassisSteerStrategy previous_steer = ChassisSteerStrategy::kClosedLoopPosition;
    ChassisWheelStrategy previous_wheel = ChassisWheelStrategy::kClosedLoopSpeed;
    ChassisStretchStrategy previous_stretch = ChassisStretchStrategy::kProfileVelocity;
};

enum class ConfigValueType { kUnspecified = 0, kBool, kInteger, kDouble, kString, kArray };
enum class ConfigApplyPolicy { kUnspecified = 0, kImmediate, kSafeState, kInitOnly };
enum class ConfigOperation { kUnspecified = 0, kSet, kReset };
enum class ConfigOverrideStatus { kUnspecified = 0, kNone, kApplied, kPendingInit, kNotAdopted };
enum class ConfigResult {
    kUnspecified = 0,
    kOk,
    kInvalidRequest,
    kInstanceUnavailable,
    kValidationRejected,
    kBusy,
    kSafetyConditionUnmet,
    kStorageFailedUnchanged,
    kApplyFailedUnchanged,
    kFailedRestored,
    kRecoveryRequired,
    kResourceLimit,
};
// Raw JSON is observable in saved legacy data, but cannot be submitted by SET.
struct ConfigRawJson {
    std::string json;
};
// monostate denotes an unknown future wire value, never false/zero/an empty array.
using ConfigValue = std::variant<std::monostate, bool, std::int64_t, double, std::string,
                                 std::vector<double>, std::vector<std::int64_t>, ConfigRawJson>;
struct ConfigEnumOption {
    std::int64_t value = 0;
    std::string name;
};
struct ConfigElementConstraints {
    std::optional<double> minimum, maximum;
    bool minimum_exclusive = false, maximum_exclusive = false;
    std::optional<std::int64_t> integer_minimum, integer_maximum;
};
struct ConfigConstraints : ConfigElementConstraints {
    std::optional<std::uint32_t> max_string_bytes, min_items, max_items;
    std::vector<ConfigEnumOption> enum_options;
};
struct ConfigArrayElementDescriptor {
    std::optional<std::uint32_t> index;
    std::string name;
    ConfigElementConstraints constraints;
};
struct ConfigFieldDescriptor {
    std::string field_id, name, description, group, unit, safety_condition;
    ConfigValueType value_type = ConfigValueType::kUnspecified;
    ConfigValueType element_type = ConfigValueType::kUnspecified;
    ConfigApplyPolicy apply_policy = ConfigApplyPolicy::kUnspecified;
    ConfigConstraints constraints;
    std::vector<ConfigArrayElementDescriptor> array_elements;
};
struct ConfigDiagnostic {
    std::string code, field_id, message;
    std::optional<std::uint32_t> element_index;
};
struct ConfigFieldInfo {
    std::string field_id;
    ConfigFieldDescriptor field_descriptor;
    std::optional<ConfigValue> effective_value, saved_override;
    ConfigOverrideStatus override_status = ConfigOverrideStatus::kUnspecified;
    bool pending_init = false;
    std::vector<ConfigDiagnostic> diagnostics;
};
struct ConfigInstanceInfo {
    std::string plugin_id;
    std::vector<ConfigFieldInfo> fields;
    std::vector<ConfigDiagnostic> diagnostics;
};
struct ConfigGetResponse {
    ConfigResult result = ConfigResult::kUnspecified;
    std::vector<ConfigInstanceInfo> instances;
    std::vector<ConfigDiagnostic> diagnostics;
};
struct ConfigSetResponse {
    ConfigResult result = ConfigResult::kUnspecified;
    std::optional<ConfigInstanceInfo> instance;
    std::vector<ConfigDiagnostic> diagnostics;
};
struct ConfigFieldOperation {
    std::string field_id;
    ConfigOperation operation = ConfigOperation::kUnspecified;
    std::optional<ConfigValue> value;
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

struct TorqueCalibrationResponse : BasicResponse {
    float measured_torque_nm = 0;
    float theoretical_torque_nm = 0;
};

struct ZeroCalibrationResponse : BasicResponse {
    bool persisted = false;
    float position_after_deg = 0;
};

struct HandServiceResponse : BasicResponse {
    std::uint32_t result = 0;
    std::uint32_t previous_mode = 0;
    std::uint32_t current_mode = 0;
    std::int32_t sdk_error_code = 0;
    std::uint32_t calibration_state = 0;
    std::uint32_t progress_percent = 0;
};

struct Waypoint {
    std::optional<JointCommand> joints;
    std::optional<Pose> cartesian;
    float max_velocity_scale = 1;
    float max_acceleration_scale = 1;
    std::uint32_t dwell_ms = 0;
};

struct WaypointTask {
    std::uint32_t repeat_count = 1;
    float default_max_velocity_scale = 1;
    float default_max_acceleration_scale = 1;
    std::uint32_t default_dwell_ms = 0;
    std::vector<Waypoint> waypoints;
};

struct DeviceSetupResponse : BasicResponse {
    std::vector<std::uint32_t> affected_device_indices;
};

struct CompressedImage {
    Header header;
    std::string format;
    std::string data;
};

enum class VideoSource { kHeadLeft = 0, kHeadRight, kWristLeft, kWristRight };
enum class VideoDecoderBackend { kSoftware = 0, kNvdec }; // nvh264dec/nvh265dec (desktop NVIDIA).
enum class VideoTimestampStatus { kNotApplicable = 0, kValid, kMissing, kInvalid };

// One independently decodable JPEG. Header belongs to the corresponding input AU.
struct JpegFrame {
    Header header;
    VideoSource source = VideoSource::kHeadLeft;
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    std::string data;
    // SDK-local steady-clock durations; source header timestamp is not used.
    // AU ingress to C++ callback entry; excludes Python GIL/wrapping time.
    std::uint64_t sdk_latency_ns = 0;
    std::uint64_t pipeline_latency_ns = 0; // appsrc submission to copied JPEG.
    // Head cameras: RK SEI source time, independent of the original media Header PTS.
    // Missing/invalid SEI remains unavailable; never substitute Header or receive time.
    std::optional<std::int64_t> source_timestamp_ns;
    VideoTimestampStatus timestamp_status = VideoTimestampStatus::kNotApplicable;
};

struct VideoOptions {
    std::uint32_t jpeg_quality = 85;  // 1..100
    std::size_t max_pending_frames = 32;
    std::size_t max_pending_bytes = 16 * 1024 * 1024;
    std::size_t max_au_bytes = 4 * 1024 * 1024;
    VideoDecoderBackend decoder_backend = VideoDecoderBackend::kNvdec;
    std::uint32_t output_width = 1280; // Both zero preserve source size; both nonzero resize.
    std::uint32_t output_height = 960;
};

struct VideoDiagnostics {
    bool active = false;
    bool waiting_for_keyframe = true;
    std::uint64_t received_au_count = 0;
    std::uint64_t jpeg_frame_count = 0;
    std::uint64_t dropped_au_count = 0;
    std::uint64_t dropped_jpeg_count = 0;
    std::uint64_t reset_count = 0;
    std::uint64_t error_count = 0;
    std::size_t pending_frames = 0;
    std::size_t pending_bytes = 0;
    Error last_error;
    // Head-camera inspected AUs, before keyframe filtering or decode.
    std::uint64_t source_timestamp_valid_count = 0;
    std::uint64_t source_timestamp_missing_count = 0;
    std::uint64_t source_timestamp_invalid_count = 0;
};

// Hand tactile finger channel 0..4 (0 = little finger ... 4 = thumb).
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

// Zstd payloads are automatically decoded into points.
// kind describes the decoded representation; compression retains the wire encoding.
// Legacy compressed kinds and raw byte fields are retained but are not emitted.
// packed_groups/packed_points follow the little-endian layout documented in north.proto.
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

// value is present only when quality == kValid; zero is a real measurement.
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

// Chest and chassis boards share this shape; readings use the proto field names.
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

// Commands that can change power state are rejected unless confirm_power_change is true.
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
    // Share the bounded SDK callback queue; the oldest droppable callback is discarded on overflow.
    kDropOldest = 0,
    // Keep at most one pending callback per subscription; newer samples replace older ones.
    kLatestOnly,
    // Never drop locally; the transport thread waits for queue space (network may still drop).
    kReliable,
};

struct SubscribeOptions {
    QueuePolicy queue_policy = QueuePolicy::kDropOldest;
};

enum class TimeSyncMode { kHardware = 1, kSoftware = 2 };

enum class TimeSyncFailurePolicy { kKeepConnected = 0, kFailConnection };
enum class TimeSyncState { kDisabled = 0, kPreparing, kReady, kFailed, kLost };

struct TimeSyncOptions {
    // Host setup is authorized once; connect() needs no runtime administrator prompt.
    bool enabled = true;
    TimeSyncFailurePolicy failure_policy = TimeSyncFailurePolicy::kKeepConnected;
    // Empty uses the route to a numeric North endpoint, or a unique wired NIC.
    std::string interface;
    // Software PI startup can take about 37 s at 8 Hz; runtime monitoring continues
    // with KeepConnected after this positive preparation deadline.
    std::chrono::milliseconds timeout{60000};
    TimeSyncMode mode = TimeSyncMode::kSoftware;
    // Software servo criterion; hardware keeps the 50 ns criterion. Range: 1 ns to 1 s.
    std::uint64_t software_offset_threshold_ns = 1000000;
};

struct TimeSyncDiagnostics {
    TimeSyncState state = TimeSyncState::kDisabled;
    Error error;
    std::string interface;
    std::string phc_device;
    std::int64_t offset_ns = 0;
    std::uint32_t stable_samples = 0;
    std::chrono::milliseconds sample_age{0};
    // The service's measured servo criterion, not absolute accuracy certification.
    std::uint64_t offset_threshold_ns = 50;
    std::uint32_t required_samples = 10;
    TimeSyncMode mode = TimeSyncMode::kSoftware;
    std::string clock_source;
    bool system_time_owned = false;
};

struct SdkConfig {
    std::string zenoh_config_path;
    std::vector<std::string> connect_endpoints;
    std::chrono::milliseconds connect_timeout{5000};
    std::chrono::milliseconds service_timeout{6000};
    std::chrono::milliseconds master_timeout{15000};
    std::chrono::milliseconds torso_timeout{20000};
    std::size_t callback_queue_capacity = 256;
    // A fresh RUNNING Master status is mandatory for every motion command.
    std::chrono::milliseconds master_status_max_age{500};
    // Explicit Master channel for single-part sends. Unspecified disables those sends.
    CommandChannel command_channel = CommandChannel::kUnspecified;
    TimeSyncOptions time_sync;
};

struct CallbackDiagnostics {
    std::uint64_t dropped_callback_count = 0;
    std::uint64_t coalesced_callback_count = 0;
    Error last_decode_error;
};

// Observation and Master status payloads supported by AlignmentClient.
// Sources with additional identity use the matching fields in AlignmentSource.
enum class AlignmentDataKind {
    kChassisState = 0,
    kTorsoState,
    kArmState,
    kHandState,
    kTactileForce,
    kTactileImage,
    kHandEskinForce,
    kHandEskinRaw,
    kImuSamples,
    kTactileSkinSamples,
    kVideoJpeg,
    kMasterStatus,
};

enum class AlignmentMatchDirection {
    kNearest = 0,
    kAtOrBefore,
    kAtOrAfter,
};

struct AlignmentSource {
    AlignmentDataKind kind = AlignmentDataKind::kArmState;
    Side side = Side::kLeft;
    std::uint32_t finger = 0;
    TactileImageKind tactile_image_kind = TactileImageKind::kRaw;
    VideoSource video_source = VideoSource::kHeadLeft;
    // Explicit source override, then global override, then the fixed nominal-source tolerance.
    std::optional<std::chrono::nanoseconds> max_skew = std::nullopt;
    AlignmentMatchDirection direction = AlignmentMatchDirection::kAtOrBefore;
};

enum class AlignmentMatchStatus {
    kMatched = 0,
    kMissing,
    kOutOfTolerance,
    // Reserved for compatibility; fixed default tolerances do not require warm-up.
    kWarmingUp,
};

using AlignmentValue =
    std::variant<ChassisState, TorsoState, ArmState, HandState, TactileForce, CompressedImage,
                 HandEskinForce, HandEskinRaw, ImuSamples, TactileSkinSamples, JpegFrame,
                 MasterStatus>;

struct AlignedSample {
    AlignmentSource source;
    AlignmentMatchStatus status = AlignmentMatchStatus::kMissing;
    std::int64_t timestamp_ns = 0;
    // Sample timestamp minus the selected baseline timestamp.
    std::int64_t offset_ns = 0;
    std::shared_ptr<const AlignmentValue> value;

    bool matched() const noexcept { return status == AlignmentMatchStatus::kMatched; }

    template <typename T>
    const T* get() const noexcept {
        return value ? std::get_if<T>(value.get()) : nullptr;
    }
};

// Session-local statistics of decoded inputs, not transport/decode or callback-queue statistics.
struct AlignmentSourceDiagnostics {
    AlignmentSource source;
    std::uint64_t received_count = 0;
    std::uint64_t invalid_timestamp_count = 0;
    std::uint64_t duplicate_timestamp_count = 0;
    std::uint64_t regression_count = 0;
    std::uint64_t buffer_eviction_count = 0;
    std::int64_t newest_timestamp_ns = 0;
    // Empty until the first decoded input; age uses the local monotonic clock.
    std::optional<std::chrono::nanoseconds> last_receive_age;
    // Reserved for compatibility; always empty (source periods are no longer estimated).
    std::optional<std::chrono::nanoseconds> estimated_period;
    // Resolved at session creation; empty only for the baseline (which is not matched).
    std::optional<std::chrono::nanoseconds> effective_max_skew;
    std::uint64_t matched_count = 0;
    std::uint64_t missing_count = 0;
    std::uint64_t out_of_tolerance_count = 0;
    std::uint64_t warming_up_count = 0;  // Reserved for compatibility; always zero.
};

struct AlignmentDiagnostics {
    std::uint64_t invalid_timestamp_count = 0;
    std::uint64_t duplicate_timestamp_count = 0;
    // Counts arrivals older than the largest timestamp seen for that source.
    std::uint64_t regression_count = 0;
    std::uint64_t buffer_eviction_count = 0;
    // Left-eye baselines evicted before evaluation (default stereo mode only).
    std::uint64_t dropped_stereo_count = 0;
    // Baselines evicted before evaluation, for any baseline source.
    std::uint64_t dropped_baseline_count = 0;
    // Baselines at or before the last evaluated timestamp; never evaluated again.
    std::uint64_t late_baseline_count = 0;
    std::uint64_t evaluated_frame_count = 0;
    std::uint64_t emitted_frame_count = 0;
    std::uint64_t incomplete_frame_count = 0;
    AlignmentSourceDiagnostics baseline;
    // Present only for the automatic right eye in head-left baseline mode.
    std::optional<AlignmentSourceDiagnostics> right;
    std::vector<AlignmentSourceDiagnostics> sources;
};

struct AlignedFrame {
    // Stereo compatibility fields: populated only when the baseline is the head left eye.
    std::int64_t stereo_timestamp_ns = 0;
    std::shared_ptr<const JpegFrame> left_image;
    // Latest right-eye candidate at or before the baseline; null if missing.
    std::shared_ptr<const JpegFrame> right_image;
    AlignedSample right_sample;
    // Additional sources, in AlignmentOptions.sources order.
    std::vector<AlignedSample> samples;
    bool complete = false;
    AlignmentDiagnostics diagnostics;
    // Selected source timestamp and payload of the baseline; offset is always zero.
    // Head JPEG uses RK SEI source time, not its Header media PTS.
    std::int64_t timestamp_ns = 0;
    AlignedSample baseline_sample;
};

struct AlignmentOptions {
    // Additional sources, excluding the baseline and any automatically subscribed right eye.
    // With a head-left baseline the right eye is automatic; otherwise only these are matched.
    std::vector<AlignmentSource> sources;
    // nullopt: fixed nominal period * 1.5 (device/IMU 7.5 ms, skin 15 ms,
    // video 25 ms, finger tactile 50 ms, Master 150 ms).
    // Per-source overrides take precedence over this global override.
    std::optional<std::chrono::nanoseconds> max_skew = std::nullopt;
    // From each baseline arrival, wait this long for all requested sources.
    std::chrono::milliseconds wait_timeout{20};
    std::size_t buffer_capacity = 64;
    // Emit frames with missing/out-of-tolerance requested sources.
    bool emit_incomplete = true;
    // Applied to all requested cameras.
    VideoOptions video_options;
    // Head-left preserves automatic stereo pairing. Other baselines do not subscribe cameras
    // implicitly. The baseline's max_skew/direction are unused; its original time is preserved.
    AlignmentSource baseline{AlignmentDataKind::kVideoJpeg};
};

namespace detail {
class SdkCore;
}
struct NorthSDKTestAccess;

class NORTHSDK_API Subscription {
   public:
    Subscription();
    ~Subscription();
    Subscription(Subscription&&) noexcept;
    Subscription& operator=(Subscription&&) noexcept;
    Subscription(const Subscription&) = delete;
    Subscription& operator=(const Subscription&) = delete;

    void close();
    bool active() const noexcept;

   private:
    struct State;
    explicit Subscription(std::shared_ptr<State> state);
    std::shared_ptr<State> state_;
    friend class detail::SdkCore;
};

class NORTHSDK_API ConfigClient {
   public:
    // Empty plugin_id discovers ready instances. Results retain server business errors.
    Result<ConfigGetResponse> get(const std::string& plugin_id = {});
    // Synchronous persistent batch. Timeout does not cancel a write; never auto-retry.
    Result<ConfigSetResponse> set(const std::string& plugin_id,
                                  const std::vector<ConfigFieldOperation>& operations);

   private:
    explicit ConfigClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

class NORTHSDK_API MasterClient {
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
    // subsystem is the system/heartbeat/<subsystem> suffix, e.g. "lidar"; "*" subscribes to all.
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

   private:
    explicit MasterClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

// All supported sends route through Master. Unsupported legacy methods return kNotSupported.
class NORTHSDK_API WholeBodyClient {
   public:
    Status send(CommandChannel channel, const WholeBodyCommand& command);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Status send_glove_raw(Side side, const GloveRaw& glove);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Status send_whole_body_raw(const WholeBodyRaw& observation);
    Result<Subscription> on_command(std::function<void(const WholeBodyCommand&)> callback,
                                    const SubscribeOptions& options = {});

   private:
    explicit WholeBodyClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

class NORTHSDK_API ChassisClient {
   public:
    Result<Subscription> on_state(std::function<void(const ChassisState&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<ChassisState> latest_state(std::chrono::milliseconds max_age);
    Status send_velocity(const ChassisVelocity& command);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Status send_raw(const ChassisRawCommand& command);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Status send_pose(const ChassisPoseCommand& command);
    // Explicit overall Motion/Force switch; stretch strategy is unchanged.
    Result<ChassisModeResponse> set_mode(ChassisControlMode mode);
    // Read-only, from a fresh chassis heartbeat; first call may return kStaleState.
    Result<ChassisControlMode> mode(
        std::chrono::milliseconds max_age = std::chrono::milliseconds(500));
    // Compatibility only: returns kNotSupported without sending, including empty requests.
    Result<ChassisStrategyResponse> set_strategy(const ChassisStrategyRequest& request);
    // Compatibility only: returns kNotSupported without querying platform strategies.
    Result<ChassisStrategyResponse> strategy();
    Result<BasicResponse> enable(bool enabled = true);
    Result<BasicResponse> reset();

   private:
    explicit ChassisClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

// Torso joints are ordered J1..J5 (body) followed by J6..J8 (neck), 8 in total.
// After reset() the joints stay disabled; call enable() before sending commands.
class NORTHSDK_API TorsoClient {
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
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Result<TorqueCalibrationResponse> calibrate_torque(std::uint32_t joint_index);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Result<ZeroCalibrationResponse> calibrate_zero(std::uint32_t joint_index);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Result<BasicResponse> submit_waypoints(const WaypointTask& task);
    Result<BasicResponse> cancel_waypoints();

   private:
    explicit TorsoClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

class NORTHSDK_API ArmClient {
   public:
    Side side() const noexcept;
    Result<Subscription> on_state(std::function<void(const ArmState&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    Result<ArmState> latest_state(std::chrono::milliseconds max_age);
    Status send_joint_positions(const std::array<float, 7>& positions);
    Status send_joint_command(const JointCommand& command);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Status send_cartesian_pose(const Pose& pose);
    Result<BasicResponse> enable(bool enabled = true);
    Result<ModeResponse> set_mode(ControlMode mode);
    Result<BasicResponse> estop(const std::string& reason = {});
    Result<BasicResponse> reset();
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Result<BasicResponse> submit_waypoints(const WaypointTask& task);
    Result<BasicResponse> cancel_waypoints();
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Result<DeviceSetupResponse> setup_device(const std::string& operation,
                                             const std::vector<std::uint32_t>& device_indices,
                                             const std::string& payload = {});

   private:
    ArmClient(std::shared_ptr<detail::SdkCore> core, Side side);
    std::shared_ptr<detail::SdkCore> core_;
    Side side_;
    friend class NorthSDK;
};

class NORTHSDK_API HandClient {
   public:
    Side side() const noexcept;
    Result<Subscription> on_state(std::function<void(const HandState&)> callback,
                                  const SubscribeOptions& options = {});
    Result<Subscription> on_heartbeat(std::function<void(const Heartbeat&)> callback,
                                      const SubscribeOptions& options = {});
    // finger is the tactile channel 0..4 (0 = little finger ... 4 = thumb).
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
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Result<HandServiceResponse> set_parameter(const std::string& json);
    // Disabled in Master-only SDK: returns kNotSupported without sending.
    Result<HandServiceResponse> start_zero_calibration();
    Result<HandServiceResponse> zero_calibration_status();
    Result<HandServiceResponse> stop_zero_calibration();

   private:
    HandClient(std::shared_ptr<detail::SdkCore> core, Side side);
    std::shared_ptr<detail::SdkCore> core_;
    Side side_;
    friend class NorthSDK;
};

class NORTHSDK_API SensorClient {
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
    // vr/config carries UTF-8 JSON text rather than protobuf.
    Result<Subscription> on_vr_config(std::function<void(const std::string&)> callback,
                                      const SubscribeOptions& options = {});
    Result<ImuSamples> latest_imu(std::chrono::milliseconds max_age);
    // enabled=true uses the current force as the 0 N baseline; false restores fitted force.
    Result<BasicResponse> zero_tactile_skin(bool enabled = true);

   private:
    explicit SensorClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

// Power topics publish at 10 Hz even when data is unavailable; also treat missing updates as stale.
class NORTHSDK_API PowerClient {
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

   private:
    explicit PowerClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

class NORTHSDK_API VideoClient {
   public:
    // Requires NORTHSDK_WITH_VIDEO. One active subscription per source in this prototype.
    // Callbacks run serially on that source's video worker, independently of state callbacks.
    // Retain the returned Subscription. The frame reference is valid during the callback.
    Result<Subscription> on_jpeg(VideoSource source,
                                std::function<void(const JpegFrame&)> callback,
                                const VideoOptions& options = {});
    Result<VideoDiagnostics> diagnostics(VideoSource source) const;

   private:
    explicit VideoClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

class NORTHSDK_API AlignmentClient {
   public:
    // Inputs enter alignment caches directly; output callbacks run on the SDK worker.
    // callback_options is retained for compatibility and ignored.
    Result<Subscription> on_frame(const AlignmentOptions& options,
                                  std::function<void(const AlignedFrame&)> callback,
                                  const SubscribeOptions& callback_options = {});
    // Snapshot of this client's active session, available even when no baseline arrives.
    Result<AlignmentDiagnostics> diagnostics(const Subscription& subscription) const;

   private:
    explicit AlignmentClient(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend class NorthSDK;
};

class NORTHSDK_API NorthSDK {
   public:
    static Result<std::unique_ptr<NorthSDK>> Create(const SdkConfig& config);
    ~NorthSDK();
    NorthSDK(const NorthSDK&) = delete;
    NorthSDK& operator=(const NorthSDK&) = delete;

    // With KeepConnected a time-sync error leaves connected() true.
    Status connect();
    TimeSyncDiagnostics time_sync_diagnostics() const;
    // Read North gPTP from synchronized CLOCK_REALTIME (Software) or NIC PHC (Hardware).
    Result<std::int64_t> robot_time_ns() const;
    void close();
    bool connected() const noexcept;
    CallbackDiagnostics callback_diagnostics() const;
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

   private:
    explicit NorthSDK(std::shared_ptr<detail::SdkCore> core);
    std::shared_ptr<detail::SdkCore> core_;
    friend struct NorthSDKTestAccess;
};

}  // namespace north
