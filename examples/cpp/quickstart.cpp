#include <north_sdk/NorthSDK.h>

#include <array>
#include <chrono>
#include <csignal>
#include <iostream>
#include <thread>

namespace {
volatile std::sig_atomic_t running = 1;
void on_signal(int) { running = 0; }
}  // namespace

int main(int argc, char** argv) {
    std::signal(SIGINT, on_signal);
    if (argc != 2) {
        std::cerr << "usage: north_sdk_quickstart <auto/HOST:PORT | zenoh-config.json5>\n";
        return 2;
    }

    north::SdkConfig config;
    const std::string endpoint = argv[1];
    if (endpoint.rfind("auto/", 0) == 0 || endpoint.rfind("tcp/", 0) == 0 ||
        endpoint.rfind("udp/", 0) == 0)
        config.connect_endpoints = {endpoint};
    else
        config.zenoh_config_path = endpoint;

    auto created = north::NorthSDK::Create(config);
    if (!created) {
        std::cerr << "create failed: " << created.error().message << '\n';
        return 1;
    }
    auto sdk = std::move(created.value());
    const auto connected = sdk->connect();
    if (!connected) {
        std::cerr << "connect failed: " << connected.message() << '\n';
        return 1;
    }

    auto left_arm = sdk->arm(north::Side::kLeft);
    auto subscription = left_arm.on_state([](const north::ArmState& state) {
        std::cout << "left arm seq=" << state.header.seq
                  << " joints=" << state.joints.position.size() << '\n';
    });
    if (!subscription) {
        std::cerr << "subscribe failed: " << subscription.error().message << '\n';
        return 1;
    }

    // Read-only quickstart. Motion requires a prepared task and fresh RUNNING status.
    while (running) std::this_thread::sleep_for(std::chrono::milliseconds(100));

    sdk->close();
    return 0;
}
