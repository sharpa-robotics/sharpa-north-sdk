#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>

#include "north_sdk/NorthSDK.h"

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: north_sdk_video_jpeg <zenoh-endpoint> [output-directory|--no-save] "
                     "[all|0|1|2|3] [quality:1..100] [--seconds=N] [--warmup=N] "
                     "[--scale=WxH|source] [--wrist-scale=WxH|source] [--nvdec|--software]\n";
        return 1;
    }
    const bool save = argc < 3 || std::string(argv[2]) != "--no-save";
    const std::filesystem::path directory = argc >= 3 ? argv[2] : "video-jpeg";
    const std::string selection = argc >= 4 ? argv[3] : "all";
    if (selection != "all" && selection != "0" && selection != "1" && selection != "2" &&
        selection != "3") {
        std::cerr << "Invalid source\n";
        return 1;
    }
    north::VideoOptions options;
    std::optional<std::pair<std::uint32_t, std::uint32_t>> wrist_size;
    unsigned seconds = 10;
    unsigned warmup = 0;
    if (argc >= 5) {
        try {
            std::size_t consumed = 0;
            const auto quality = std::stoul(argv[4], &consumed);
            if (consumed != std::string(argv[4]).size() || quality < 1 || quality > 100) {
                std::cerr << "Invalid quality\n";
                return 1;
            }
            options.jpeg_quality = static_cast<std::uint32_t>(quality);
        } catch (...) {
            std::cerr << "Invalid quality\n";
            return 1;
        }
    }
    for (int argument = 5; argument < argc; ++argument) {
        const std::string value = argv[argument];
        if (value == "--nvdec") {
            options.decoder_backend = north::VideoDecoderBackend::kNvdec;
            continue;
        }
        if (value == "--software") {
            options.decoder_backend = north::VideoDecoderBackend::kSoftware;
            continue;
        }
        if (value == "--scale=source") {
            options.output_width = options.output_height = 0;
            continue;
        }
        const auto numeric = [&](const std::string& prefix, unsigned maximum) {
            std::size_t consumed = 0;
            const auto text = value.substr(prefix.size());
            const auto parsed = std::stoul(text, &consumed);
            if (consumed != text.size() || parsed > maximum) throw std::invalid_argument("range");
            return static_cast<unsigned>(parsed);
        };
        try {
            if (value.rfind("--seconds=", 0) == 0) {
                seconds = numeric("--seconds=", 600);
                if (!seconds) throw std::invalid_argument("duration");
            } else if (value.rfind("--warmup=", 0) == 0)
                warmup = numeric("--warmup=", 599);
            else if (value.rfind("--scale=", 0) == 0 || value.rfind("--wrist-scale=", 0) == 0) {
                const bool wrist = value.rfind("--wrist-scale=", 0) == 0;
                const auto text = value.substr(wrist ? 14 : 8);
                if (wrist && text == "source") {
                    wrist_size = {{0, 0}};
                    continue;
                }
                const auto separator = text.find('x');
                if (separator == std::string::npos) throw std::invalid_argument("size");
                std::size_t consumed = 0;
                const auto width = std::stoul(text.substr(0, separator), &consumed);
                if (consumed != separator || !width || width > 8192)
                    throw std::invalid_argument("width");
                const auto height_text = text.substr(separator + 1);
                const auto height = std::stoul(height_text, &consumed);
                if (consumed != height_text.size() || !height || height > 8192)
                    throw std::invalid_argument("height");
                if (wrist)
                    wrist_size = {
                        {static_cast<std::uint32_t>(width), static_cast<std::uint32_t>(height)}};
                else {
                    options.output_width = static_cast<std::uint32_t>(width);
                    options.output_height = static_cast<std::uint32_t>(height);
                }
            } else
                throw std::invalid_argument("option");
        } catch (...) {
            std::cerr << "Invalid option: " << value << '\n';
            return 1;
        }
    }
    if (warmup >= seconds) {
        std::cerr << "Warmup must be shorter than capture\n";
        return 1;
    }
    if (save) std::filesystem::create_directories(directory);
    std::array<std::atomic<std::uint64_t>, 4> callback_ns{}, callbacks{}, write_errors{};
    std::array<std::atomic<std::uint32_t>, 4> widths{}, heights{};
    std::array<std::chrono::steady_clock::time_point, 4> last_callback{};
    std::array<double, 4> largest_callback_gap_ms{};
    // Only the corresponding stream worker writes each vector. Read after close().
    std::array<std::vector<double>, 4> sdk_latency, pipeline_latency;
    std::atomic<bool> measuring{warmup == 0};
    for (auto& samples : sdk_latency) samples.reserve(36000);
    for (auto& samples : pipeline_latency) samples.reserve(36000);
    std::cout << "quality=" << options.jpeg_quality << " software_threads=1 parallel=baseline"
              << " save=" << save << " seconds=" << seconds << " warmup=" << warmup
              << " decoder=" << static_cast<int>(options.decoder_backend)
              << " scale=" << options.output_width << 'x' << options.output_height << '\n';
    north::SdkConfig config;
    config.connect_endpoints = {argv[1]};
    auto created = north::NorthSDK::Create(config);
    if (!created) {
        std::cerr << created.error().message << '\n';
        return 1;
    }
    auto sdk = std::move(created.value());
    auto status = sdk->connect();
    if (!status) {
        std::cerr << status.message() << '\n';
        return 1;
    }
    std::vector<north::Subscription> subscriptions;
    for (const auto source : {north::VideoSource::kHeadLeft, north::VideoSource::kHeadRight,
                              north::VideoSource::kWristLeft, north::VideoSource::kWristRight}) {
        if (selection != "all" && selection != std::to_string(static_cast<int>(source))) continue;
        auto source_options = options;
        if (static_cast<int>(source) >= 2 && wrist_size) {
            source_options.output_width = wrist_size->first;
            source_options.output_height = wrist_size->second;
        }
        auto subscribed = sdk->video().on_jpeg(
            source,
            [&](const north::JpegFrame& frame) {
                const auto start = std::chrono::steady_clock::now();
                const auto i = static_cast<std::size_t>(frame.source);
                widths[i] = frame.width;
                heights[i] = frame.height;
                if (measuring.load() && sdk_latency[i].size() < 36000) {
                    if (last_callback[i] != std::chrono::steady_clock::time_point{}) {
                        largest_callback_gap_ms[i] = std::max(
                            largest_callback_gap_ms[i],
                            std::chrono::duration<double, std::milli>(start - last_callback[i])
                                .count());
                    }
                    sdk_latency[i].push_back(frame.sdk_latency_ns / 1e6);
                    pipeline_latency[i].push_back(frame.pipeline_latency_ns / 1e6);
                }
                last_callback[i] = start;
                if (save) {
                    const auto path = directory / (std::to_string(static_cast<int>(frame.source)) +
                                                   "-" + std::to_string(frame.header.seq) + ".jpg");
                    std::ofstream output(path, std::ios::binary);
                    output.write(frame.data.data(),
                                 static_cast<std::streamsize>(frame.data.size()));
                    output.close();
                    if (!output) ++write_errors[i];
                }
                callback_ns[i] +=
                    static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                                                   std::chrono::steady_clock::now() - start)
                                                   .count());
                ++callbacks[i];
            },
            source_options);
        if (!subscribed) {
            std::cerr << subscribed.error().message << '\n';
            return 1;
        }
        subscriptions.push_back(std::move(subscribed.value()));
    }
    // Bounded capture example; applications should move slow disk/vision work to their own queue.
    const auto started = std::chrono::steady_clock::now();
    std::array<north::VideoDiagnostics, 4> previous{};
    std::array<north::VideoDiagnostics, 4> measurement_start{}, measurement_end{};
    auto last = started;
    auto measured_since = started;
    for (unsigned second = 0; second < seconds; ++second) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        const auto now = std::chrono::steady_clock::now();
        const auto elapsed = std::chrono::duration<double>(now - last).count();
        for (const auto source :
             {north::VideoSource::kHeadLeft, north::VideoSource::kHeadRight,
              north::VideoSource::kWristLeft, north::VideoSource::kWristRight}) {
            const auto i = static_cast<std::size_t>(source);
            if (selection != "all" && selection != std::to_string(i)) continue;
            const auto d = sdk->video().diagnostics(source).value();
            std::cout << "t=" << second + 1 << " source=" << i << " size=" << widths[i] << 'x'
                      << heights[i] << " AU_FPS="
                      << (d.received_au_count - previous[i].received_au_count) / elapsed
                      << " JPEG_FPS="
                      << (d.jpeg_frame_count - previous[i].jpeg_frame_count) / elapsed
                      << " pending=" << d.pending_frames << " dropped_AU=" << d.dropped_au_count
                      << " overwritten_JPEG=" << d.dropped_jpeg_count << " resets=" << d.reset_count
                      << " waiting_IDR=" << d.waiting_for_keyframe
                      << " error=" << d.last_error.message << '\n';
            previous[i] = d;
            measurement_end[i] = d;
        }
        last = now;
        if (second + 1 == warmup) {
            measurement_start = measurement_end;
            measured_since = now;
            measuring.store(true);
        }
    }
    measuring.store(false);
    const double measured_seconds = std::chrono::duration<double>(last - measured_since).count();
    sdk->close();
    const auto percentile = [](std::vector<double>& samples, double quantile) {
        if (samples.empty()) return 0.0;
        std::sort(samples.begin(), samples.end());
        return samples[static_cast<std::size_t>((samples.size() - 1) * quantile)];
    };
    for (const auto source : {north::VideoSource::kHeadLeft, north::VideoSource::kHeadRight,
                              north::VideoSource::kWristLeft, north::VideoSource::kWristRight}) {
        const auto diagnostics = sdk->video().diagnostics(source).value();
        const auto i = static_cast<std::size_t>(source);
        if (selection != "all" && selection != std::to_string(i)) continue;
        std::cout << static_cast<int>(source) << ": AU=" << diagnostics.received_au_count
                  << " width=" << widths[i] << " height=" << heights[i]
                  << " JPEG=" << diagnostics.jpeg_frame_count
                  << " resets=" << diagnostics.reset_count << " callback_mean_ms="
                  << (callbacks[i] ? callback_ns[i].load() / 1e6 / callbacks[i].load() : 0)
                  << " write_errors=" << write_errors[i] << " measured_seconds=" << measured_seconds
                  << " measured_AU_FPS="
                  << (measurement_end[i].received_au_count -
                      measurement_start[i].received_au_count) /
                         measured_seconds
                  << " measured_JPEG_FPS="
                  << (measurement_end[i].jpeg_frame_count - measurement_start[i].jpeg_frame_count) /
                         measured_seconds
                  << " measured_resets="
                  << measurement_end[i].reset_count - measurement_start[i].reset_count
                  << " measured_dropped_AU="
                  << measurement_end[i].dropped_au_count - measurement_start[i].dropped_au_count
                  << " measured_overwritten_JPEG="
                  << measurement_end[i].dropped_jpeg_count - measurement_start[i].dropped_jpeg_count
                  << " latency_samples=" << sdk_latency[i].size()
                  << " sdk_p50_ms=" << percentile(sdk_latency[i], .5)
                  << " sdk_p95_ms=" << percentile(sdk_latency[i], .95)
                  << " sdk_p99_ms=" << percentile(sdk_latency[i], .99)
                  << " sdk_max_ms=" << percentile(sdk_latency[i], 1)
                  << " pipeline_p50_ms=" << percentile(pipeline_latency[i], .5)
                  << " pipeline_p95_ms=" << percentile(pipeline_latency[i], .95)
                  << " max_callback_gap_ms=" << largest_callback_gap_ms[i]
                  << " error=" << diagnostics.last_error.message << '\n';
    }
}
