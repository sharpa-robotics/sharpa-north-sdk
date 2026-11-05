// Read-only bring-up check for a real robot, following sharpa_interface.md §15.
// It subscribes to every state stream, reports per-stream rates, and optionally issues
// read-only service queries. It never sends motion, mode, calibration, or power changes.
#include <north_sdk/NorthSDK.h>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Options {
    std::string zenoh_config;
    std::vector<std::string> endpoints;
    int seconds = 5;
    bool query = false;
    bool time_sync = true;
};

void usage() {
    std::cerr << "usage: north_sdk_robot_smoke [--zenoh-config FILE | --endpoint EP]...\n"
                 "                             [--seconds N] [--query] [--no-time-sync]\n"
                 "  --query  also call read-only services (power get_status, hand zero\n"
                 "           calibration status)\n";
}

bool parse(int argc, char** argv, Options& options) {
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        const bool has_value = i + 1 < argc;
        if (arg == "--zenoh-config" && has_value) {
            options.zenoh_config = argv[++i];
        } else if (arg == "--endpoint" && has_value) {
            options.endpoints.emplace_back(argv[++i]);
        } else if (arg == "--seconds" && has_value) {
            options.seconds = std::atoi(argv[++i]);
        } else if (arg == "--no-time-sync") {
            options.time_sync = false;
        } else if (arg == "--query") {
            options.query = true;
        } else {
            return false;
        }
    }
    return options.seconds > 0;
}

class Counters {
   public:
    std::function<void()> counter(const std::string& name) {
        std::lock_guard<std::mutex> lock(mutex_);
        counts_.emplace(name, 0);
        return [this, name] {
            std::lock_guard<std::mutex> lock(mutex_);
            ++counts_[name];
        };
    }
    void heartbeat(const north::Heartbeat& heartbeat) {
        std::lock_guard<std::mutex> lock(mutex_);
        ++counts_["heartbeat/" + heartbeat.subsystem];
    }
    std::map<std::string, std::uint64_t> snapshot() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return counts_;
    }

   private:
    mutable std::mutex mutex_;
    std::map<std::string, std::uint64_t> counts_;
};

std::string side_name(north::Side side) { return side == north::Side::kLeft ? "left" : "right"; }

template <typename T>
void report_query(const std::string& name, const north::Result<T>& result) {
    std::cout << "  " << std::left << std::setw(36) << name;
    if (!result) {
        std::cout << "FAILED code=" << static_cast<int>(result.error().code) << ' '
                  << result.error().message << '\n';
    } else {
        std::cout << (result.value().success ? "ok " : "rejected ") << result.value().message
                  << '\n';
    }
}

}  // namespace

int main(int argc, char** argv) {
    Options options;
    if (!parse(argc, argv, options)) {
        usage();
        return 2;
    }

    north::SdkConfig config;
    config.time_sync.enabled = options.time_sync;
    config.zenoh_config_path = options.zenoh_config;
    if (!options.endpoints.empty()) config.connect_endpoints = options.endpoints;
    auto created = north::NorthSDK::Create(config);
    if (!created) {
        std::cerr << "create failed: " << created.error().message << '\n';
        return 1;
    }
    auto sdk = std::move(created.value());
    if (const auto connected = sdk->connect(); !connected) {
        std::cerr << "connect failed: " << connected.message() << '\n';
        return 1;
    }

    Counters counters;
    std::vector<north::Subscription> subscriptions;
    const north::SubscribeOptions latest{north::QueuePolicy::kLatestOnly};
    auto keep = [&](const std::string& name, auto result) {
        if (!result) {
            std::cerr << "subscribe " << name << " failed: " << result.error().message << '\n';
            return;
        }
        subscriptions.push_back(std::move(result.value()));
    };
    auto count = [&](const std::string& name) {
        return [tick = counters.counter(name)](const auto&) { tick(); };
    };

    auto master = sdk->master();
    keep("master/status", master.on_status(count("master/status"), latest));
    keep("master/hardware", master.on_hardware_health(count("master/hardware"), latest));
    keep("heartbeat", master.on_heartbeat(
                          "*", [&](const north::Heartbeat& value) { counters.heartbeat(value); }));
    keep("chassis/state", sdk->chassis().on_state(count("chassis/state"), latest));
    keep("torso/state", sdk->torso().on_state(count("torso/state"), latest));
    for (const auto side : {north::Side::kLeft, north::Side::kRight}) {
        const auto prefix = side_name(side);
        keep(prefix + "_arm/state", sdk->arm(side).on_state(count(prefix + "_arm/state"), latest));
        auto hand = sdk->hand(side);
        keep(prefix + "_hand/state", hand.on_state(count(prefix + "_hand/state"), latest));
        keep(prefix + "_hand/eskin_force",
             hand.on_eskin_force(count(prefix + "_hand/eskin_force"), latest));
        keep(prefix + "_hand/tactile_force0",
             hand.on_tactile_force(0, count(prefix + "_hand/tactile_force0"), latest));
    }
    auto sensors = sdk->sensors();
    keep("sensors/imu", sensors.on_imu(count("sensors/imu"), latest));
    keep("sensors/ultrasonic", sensors.on_ultrasonic(count("sensors/ultrasonic"), latest));
    keep("sensors/tactile_skin", sensors.on_tactile_skin(count("sensors/tactile_skin"), latest));
    keep("sensors/lidar_chassis_front",
         sensors.on_lidar(north::LidarSource::kChassisFront, count("sensors/lidar_chassis_front"),
                          latest));
    keep("sensors/lidar_chest_front", sensors.on_lidar(north::LidarSource::kChestFront,
                                                       count("sensors/lidar_chest_front"), latest));
    keep("sensors/lidar_chest_rear", sensors.on_lidar(north::LidarSource::kChestRear,
                                                      count("sensors/lidar_chest_rear"), latest));
    auto power = sdk->power();
    keep("power/chest", power.on_chest_state(count("power/chest"), latest));
    keep("power/chassis", power.on_chassis_state(count("power/chassis"), latest));
    keep("power/battery", power.on_battery(count("power/battery"), latest));

    std::cout << "listening for " << options.seconds << " s ...\n";
    std::this_thread::sleep_for(std::chrono::seconds(options.seconds));
    const auto counts = counters.snapshot();

    std::cout << "\nstreams (samples, Hz):\n";
    for (const auto& [name, samples] : counts) {
        std::cout << "  " << std::left << std::setw(36) << name << std::right << std::setw(8)
                  << samples << std::setw(10) << std::fixed << std::setprecision(1)
                  << static_cast<double>(samples) / options.seconds
                  << (samples == 0 ? "  (silent)" : "") << '\n';
    }

    if (options.query) {
        std::cout << "\nread-only services:\n";
        for (const auto node : {north::PowerNode::kChassis, north::PowerNode::kBody}) {
            north::PowerChannelCommand command;
            command.node = node;
            command.opcode = north::PowerOpCode::kGetStatus;
            report_query("power/get_status node=" + std::to_string(static_cast<int>(node)),
                         power.channel_command(command));
        }
        for (const auto side : {north::Side::kLeft, north::Side::kRight}) {
            report_query(side_name(side) + "_hand/zero_calibration/status",
                         sdk->hand(side).zero_calibration_status());
        }
    }

    const auto diagnostics = sdk->callback_diagnostics();
    std::cout << "\ncallbacks: dropped=" << diagnostics.dropped_callback_count
              << " coalesced=" << diagnostics.coalesced_callback_count << '\n';

    subscriptions.clear();
    sdk->close();

    const bool master_ok = counts.at("master/status") > 0 && counts.at("master/hardware") > 0;
    const bool heartbeat_ok = std::any_of(counts.begin(), counts.end(), [](const auto& entry) {
        return entry.first.rfind("heartbeat/", 0) == 0 && entry.second > 0;
    });
    if (!master_ok || !heartbeat_ok) {
        std::cerr << "FAIL: master status, hardware health and at least one heartbeat are "
                     "required\n";
        return 1;
    }
    std::cout << "PASS\n";
    return 0;
}
