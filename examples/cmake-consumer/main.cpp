#include <north_sdk/NorthSDK.h>

#include <iostream>
#include <string>

int main() {
    std::cout << north::NorthSDK::version() << '\n';
    if (std::string(north::NorthSDK::version()) != NORTHSDK_VERSION) return 1;
    north::SdkConfig config;
    auto created = north::NorthSDK::Create(config);
    if (!created) {
        // Codec-only builds intentionally have no default transport.
        std::cerr << created.error().message << '\n';
        return created.error().code == north::ErrorCode::kUnavailable ? 0 : 1;
    }
    auto sdk = std::move(created.value());
    // Check exported APIs without contacting hardware.
    if (sdk->config().get().error().code != north::ErrorCode::kNotConnected) return 1;
    const north::ConfigFieldOperation operation{
        "self_collision.enabled", north::ConfigOperation::kSet, north::ConfigValue{false}};
    if (sdk->config().set("master", {operation}).error().code != north::ErrorCode::kNotConnected)
        return 2;
    if (sdk->chassis().set_mode(north::ChassisControlMode::kMotion).error().code !=
        north::ErrorCode::kNotConnected)
        return 3;
    if (sdk->chassis().strategy().error().code != north::ErrorCode::kNotSupported) return 4;
    north::AlignmentOptions alignment;
    alignment.baseline.kind = north::AlignmentDataKind::kMasterStatus;
    if (sdk->alignment().on_frame(alignment, [](const north::AlignedFrame&) {}).error().code !=
        north::ErrorCode::kNotConnected)
        return 5;
    if (sdk->alignment().diagnostics(north::Subscription{}).error().code !=
        north::ErrorCode::kNotConnected)
        return 6;
    sdk->close();
    return 0;
}
