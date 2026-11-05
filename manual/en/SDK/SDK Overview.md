# SDK Overview

North SDK

[SDK Overview](SDK%20Overview.md) · [Application Development](Application%20Development.md) · [Software Service Interface](Software%20Service%20Interface.md) · [Example Code Reference](Example%20Code%20Reference.md) · [中文](../../zh/SDK/SDK%20%E6%A6%82%E8%A7%88.md)

## Contents

- [Introduction](#introduction)
- [Modules](#modules)
- [Interaction patterns](#interaction-patterns)
- [Runtime environment](#runtime-environment)
- [Reading path](#reading-path)

## Introduction

North SDK provides C++ and Python APIs for Sharpa North robots. Applications use Clients to receive robot state, call device services and send joint-position and chassis-velocity commands.

C++ APIs are in namespace `north`, with public header `<north_sdk/NorthSDK.h>`. The Python package is `north_sdk`. Both languages share the same capabilities, with language-specific results and resource management.

![Robot capabilities and Client accessors](../../assets/en/SDK/SDK%20Overview/client-map.svg)

The figure uses C++ accessors. Side refers to the robot’s own left or right; Python uses Side.LEFT / Side.RIGHT.

`NorthSDK` is the common entry point; accessors return each Client directly. `MasterClient` manages system state and tasks, part Clients control their mechanisms, and `WholeBodyClient` combines commands for multiple parts. Other Clients provide sensing, video, alignment, power and configuration. The figure groups Clients by purpose.

## Modules

| Module | Purpose |
| --- | --- |
| Master | Runtime status, health, task events and system management |
| WholeBody | Combine joint-position targets and chassis velocity commands |
| Chassis | State, velocity commands, mode switching, enable and reset |
| Torso | Eight torso/neck joints: state, position commands and services |
| Arm | Seven joints per arm: state, position commands and services |
| Hand | Twenty-two joints per hand: state, position commands, tactile data and services |
| Sensors | IMU, ultrasonic, tactile skin and Lidar |
| Power | Power-board and battery state, and power management |
| Video | Decode head stereo H.265 and wrist H.264 streams and deliver JPEG callbacks; NVIDIA NVDEC is recommended, with software decoding as a compatibility option |
| Alignment | Match video, device state, and Master state by source timestamp |
| Config | Discover and safely modify robot-exposed persistent user configuration |

Available capabilities depend on robot configuration and software version. See the API reference in [Software Service Interface](Software%20Service%20Interface.md).

## Interaction patterns

| Pattern | Typical API | Meaning |
| --- | --- | --- |
| Subscription | `on_*()` | Receive state/events continuously and retain the subscription handle |
| Cached state | `latest_*(max_age)` | Read the latest local sample subject to a freshness limit |
| Command | `send_*()` | Submit a command, then observe device feedback |
| Service | `set_mode()` / `reset()` | Wait for a response and check SDK errors and business results |

## Runtime environment

| Item | Requirement |
| --- | --- |
| Runtime system | Recommended: Ubuntu 22.04 LTS x86_64 / Ubuntu 24.04 LTS x86_64 |
| C++ API | C++17, using public headers and libraries from the delivered package |
| Python API | Recommended: CPython 3.10.x / 3.12.x; the interpreter minor version and architecture must match a binding included in the package. See the package manifest |
| Robot | Matching software, a reachable communication address and required devices |
| Video component | All packages include video support, GStreamer runtime libraries and required plugins. Default hardware decoding requires a discrete NVIDIA GPU supporting H.264/H.265 decoding and a compatible driver. |

Available capabilities depend on the delivered package, runtime dependencies, and robot configuration. Use C++ headers, Python extensions and SDK libraries from one delivery package. Refer to the delivery notes for matching robot software versions.

Time synchronization is enabled by default. Complete the one-time host setup before first use. The default software mode adjusts host system time; see [Time synchronization](Application%20Development.md#time-synchronization).

## Reading path

1. [Application Development](Application%20Development.md): complete read-only bring-up in Quick Start, then learn about resources, service results and motion admission.
2. [Example Code Reference](Example%20Code%20Reference.md): choose C++ or Python examples by task.
3. [Software Service Interface](Software%20Service%20Interface.md): look up support status, parameters, results, units and data fields.
