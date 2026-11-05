# 推理机自动对时

NorthSDK 在 `connect()` 建立传输连接后，默认请求本机共享服务准备 gPTP。
适用 Ubuntu 22.04/24.04，使用匹配系统版本和 CPU 架构的 SDK 包。
机器人连接须接到 North 背部右侧交换机引出的以太网口；Zenoh 可达不代表 gPTP 可达。

## 模式与时间域

`TimeSyncMode` 支持 `Software`（默认）和显式 `Hardware`，没有 Auto 或运行时回退。
默认软件模式检查网卡的软件 TX/RX 时间戳能力；硬件模式检查硬件 TX/RX/raw 时间戳及 PHC。
能力不足、权限错误、外部授时冲突、链路错误、驱动异常和收敛超时均返回错误。
一次连接内模式、来源和网卡固定；运行中失锁恢复原模式。

硬件模式运行私有 `ptp4l -H`，调整推理机网卡 PHC；不修改系统时间。
软件模式运行私有 `ptp4l -S`，调整推理机的 `CLOCK_REALTIME`，包括首次可能向前或向后跳变。
硬件就绪门槛固定为偏差绝对值严格小于 50 ns；软件默认严格小于 1 ms，可通过
`software_offset_threshold_ns` 调整，允许范围 1 ns～1 s。两者都要求 10 个不同 ingress 的连续合格观测。
这些是 LinuxPTP 伺服观测判据，不等于经外部仪器认证的绝对精度。
软件模式私有配置的 `step_threshold` 为 0.003 秒（3 ms）；硬件模式保留原 profile 的 0.001 秒。
该软件运行期跳变门槛在 `tools/timesync/service.py` 的 `Servo.__init__` 中设置，
生成会话私有 `ptp4l.cfg` 时覆盖基础 `slave.cfg`，不是 SDK 的就绪门槛配置项。
首次调整继续使用 profile 的 `first_step_threshold`，不随软件质量门槛改变。

目标是 **North MGBE2 的 gPTP 数值域**，不保证与外部 UTC/NTP 相同。
根据平台说明，MGBE2 上电从 RTC 初始化，此后不会随 Thor 的 NTP 更新；传感器、电机状态和离线录制
应使用这个 gPTP 域。复用 automotive profile（domain 0、L2/P2P、BMCA noop、inhibit_announce 1）；
生成私有配置时设 `utc_offset 0`、`kernel_leap 0`，不附加未经确认的 UTC/TAI 偏移。
软件模式期间系统日志等也会使用跟随 North 的时间；本组件不写 RTC。
实机仍须对照推理机读数、机器人 MGBE2 PHC 和实际数据时间戳，确认平台契约与实现一致。

`robot_time_ns()` 在硬件模式读取经服务传递的只读 PHC FD；软件模式只有在服务确认同步就绪且持有系统授时权时，
才读取本机 CLOCK_REALTIME。未连接、禁用、失锁、诊断过期或取时失败均返回错误。
原始机器人数据时间戳不作改写。

## 一次性主机准备

交付仍为 tar.gz，包含 LinuxPTP 4.4 二进制、对应源码和许可证；不需要联网安装 LinuxPTP 或 pip 依赖。
需要系统自带 Python 3、systemd 和标准 Ubuntu 服务管理能力。

```bash
cd <解压后的 SDK 目录>
sudo ./tools/setup-host --user "$USER"
source ./setup.bash
./tools/setup-host check
```

该安装命令一次性授权登记账号请求硬件授时，以及软件模式下管理系统时间。
安装本身不开始授时。若只允许硬件，可用 `--no-system-time`；默认软件模式将返回权限错误，使用时应显式选择 Hardware。
后续 `connect()` 不需要 sudo，也不重复询问。
组件安装到 `/opt/northsdk-timesync`，配置 `/etc/northsdk-timesync.json`，通过专属 systemd socket 激活 root 管理服务。
socket 组权限与 SO_PEERCRED 共同限制登记账号/root；客户端不能提供程序、配置文件路径或任意命令。

软件会话开始前记录本次会话的授时服务状态，临时停止并 runtime mask 已识别的
systemd-timesyncd、chrony、ntp、ntpsec、openntpd 服务，防止它们与 ptp4l 同时调钟。
不修改这些服务的持久启用状态。检测到未托管的 ptp4l/phc2sys/ts2phc 或无法归属的已识别调钟进程时返回冲突。
不会停止未知进程；自行调用调钟系统调用的任意第三方程序无法全面检测，主机须避免其他调钟者。

每个 SDK 对象有独立随机租约，同进程的多个对象也分别计数；普通 monitor/取时请求续租。
同来源、模式、门槛的客户端共享一个 servo。关闭一个不影响其他客户端；最后一个释放租约后，后台先停止 servo，
再恢复会话开始前的授时服务状态。原先关闭的不会被启动。进程异常退出则在最后一次续租约 5 秒后清理。
硬件会话也按租约停止自己的 servo。管理服务和安装授权继续保留，下一次连接自动重新准备。
清理期间重连会等待前次恢复完成，避免 NTP 与软件 PTP 重叠。
系统只有一个 CLOCK_REALTIME；请求不同机器人端点、网卡或软件门槛的冲突会话不会同时运行。

恢复意图保存在 root 私有运行目录的事务记录中。systemd 在启动前和退出后运行恢复钩子；
异常退出先清理进程，再恢复 NTP。runtime mask 在重启后消失，持久服务启用状态保持原样。
恢复失败时保留记录并报告错误，升级/卸载拒绝删除未完成恢复的组件。
同账号可重新安装更新；可用以下命令维护：

```bash
journalctl -u northsdk-timesync.service --since '10 minutes ago' --no-pager
sudo ./tools/setup-host uninstall
```

## C++ 使用

```cpp
north::SdkConfig config;
config.connect_endpoints = {"auto/192.168.100.100:7449"};
// 可选：config.time_sync.interface = "enp2s0";
// 默认 Software、软件 1 ms、等待 60 秒、失败保留连接。
// config.time_sync.mode = north::TimeSyncMode::kHardware;
// config.time_sync.enabled = false;  // 完全跳过对时
// config.time_sync.failure_policy = north::TimeSyncFailurePolicy::kFailConnection;
auto created = north::NorthSDK::Create(config);
if (!created) return;
auto sdk = std::move(created.value());
auto status = sdk->connect();
if (!status) {
    // 记录 status.code()/message()。对时错误默认保留传输连接。
    if (!sdk->connected()) return;
}
auto diagnostic = sdk->time_sync_diagnostics();
if (diagnostic.state == north::TimeSyncState::kReady) {
    auto time = sdk->robot_time_ns();  // 取时期间也可能失锁，仍需处理错误。
    if (time) { /* 使用 time.value() */ }
}
sdk->close();
```

空网卡配置优先使用数字 IP 机器人端点对应的内核路由；不选择其他不相关的硬件时间戳网卡。
无数字 IP（如发现模式或 hostname）时要求只有一个已连通的物理有线候选，否则显式配置网卡。
多机器人数字端点存在歧义时须显式配置；Wi-Fi、VLAN、桥、虚拟网卡须选择实际接入 gPTP 的物理网卡。
选定网卡在该 SDK 对象后续重连时保留；连接和重连均使用配置的模式。
端点地址用于区分软件会话来源，不是对 PTP 主时钟的身份认证；必须接入受控 North gPTP 网络。

默认对时失败返回错误，传输连接保留且持续监测；严格策略只在本次连接初始化失败时断开。
运行期间失锁更新诊断，不主动关闭传输。重获就绪仍需 10 个新合格样本。
SDK 内部等待和租约使用单调时钟，不受系统时间跳变影响。
默认准备期限 60 秒：LinuxPTP 4.4 软件 PI 默认参数在 8 Hz Sync 下，初始频率估计约需 37 秒，
再累计新样本后就绪。保留默认伺服增益；需要时可显式配置 `timeout` / `timeout_ms`。

## Python 与观测

Python 对应 `TimeSyncMode.HARDWARE/SOFTWARE`；失败抛出带 `.code` 的 `NorthSDKError`。
需要保留连接继续使用时，显式创建对象、捕获异常并检查 `sdk.connected`。
`with NorthSDK(config)` 在 `__enter__` 报错时不会进入代码块。

```python
import north_sdk as north
config = north.SdkConfig()
config.connect_endpoints = ["auto/192.168.100.100:7449"]
config.time_sync.mode = north.TimeSyncMode.SOFTWARE
config.time_sync.software_offset_threshold_ns = 1_000_000
sdk = north.NorthSDK(config)
try:
    try:
        sdk.connect()
    except north.NorthSDKError as error:
        print(error.code, str(error), sdk.connected)
        if not sdk.connected:
            raise
    d = sdk.time_sync_diagnostics()
    print(d.mode, d.clock_source, d.system_time_owned)
    if d.state == north.TimeSyncState.READY:
        print(sdk.robot_time_ns())
finally:
    sdk.close()
```

```bash
python3 examples/python/time_sync_status.py --mode software --seconds 300 > time-sync.jsonl
journalctl -u northsdk-timesync.service --since '10 minutes ago' --no-pager > time-sync-service.log
```

诊断包含所选模式、时钟来源、系统授时权、偏差、门槛、样本数和样本年龄。
PMC 交替查询 TIME_STATUS_NP/PORT_DATA_SET，约每 100 ms 一组；重复 ingress 不计数。
超过 1 秒无新样本、非 CLIENT/SLAVE、时间跳变、偏差越界、进程失败或外部授时冲突都会撤销就绪。
SDK 每 250 ms 更新诊断。比较 READY 覆盖、失锁次数、偏差分布和恢复时间，不只检查首次连接。

| C++ 错误码（Python 去掉 k 并转大写下划线） | 含义 |
| --- | --- |
| `kTimeSyncUnavailable` | 组件不可达、进程或监测失败、恢复失败 |
| `kTimeSyncPermission` | 账号未授权或软件接管系统时间未授权 |
| `kTimeSyncUnsupported` | 硬件/软件时间戳能力或取时接口不支持 |
| `kTimeSyncConflict` | 外部授时或另一来源/策略占用时钟 |
| `kTimeSyncTimeout` | 在期限内未收敛 |
| `kTimeSyncLost` | 同步失效、过期或取时未就绪 |
| `kInvalidArgument` | 配置无效或来源/网卡不唯一 |

## 构建、发布和验收

```bash
tools/build_thirdparty.sh x86 timesync    # thirdparty/x86_64/linuxptp-4.4（原生，Ubuntu 22.04）
tools/build_thirdparty.sh thor timesync   # thirdparty/thor/linuxptp-4.4（交叉，Ubuntu 24.04）
tools/build_thirdparty.sh orin timesync   # thirdparty/orin/linuxptp-4.4（交叉，Ubuntu 22.04）
python3 tools/package_release.py x86_64 build/release --without-video
```

固定官方 v4.4 源码 URL/SHA-256，构建独立 ptp4l/pmc，不链接到 SDK；运行时包含源码、许可证、构建脚本和清单。
`package_release.py`、`package.sh`、`package_production.sh` 默认使用 `thirdparty/<目标>/linuxptp-4.4`，
`--timesync-runtime` 或 `NORTHSDK_TIMESYNC_RUNTIME` 可覆盖。ARM 使用仓库内交叉工具链构建
（`build_timesync_runtime.py --cc/--sysroot/--ubuntu`），设置 `NORTHSDK_QEMU_AARCH64` 时用 QEMU 执行 `-v` 冒烟。
清单声明 hardware/software 能力及可运行的 Ubuntu 版本：从构建目标版本起，列出 glibc 满足二进制要求的全部版本
（22.04 为 2.35，24.04 为 2.39），因此 x86/Orin 为 22.04、24.04，Thor 为 24.04；24.04 构建不能冒充 22.04。
`setup-host` 拒绝清单未列出的系统。
所有打包入口仍要求匹配运行时；主机组件与 SDK 必须一起更新，控制协议升级为 NTS2，拒绝混用旧组件。
版本 1.2.0 / API level 4 / SOVERSION 3，公开配置布局改变，消费者须重新编译。

本地测试用假 systemctl/servo 验证策略，不改变开发机时钟；真实 PMC 仅连接假管理服务。
真实验收须分别覆盖硬件和软件、空闲和负载、首次跳变、5 分钟偏差、MGBE2 数值对照、多实例、异常退出、
服务崩溃、网线拔插、重连和 NTP 恢复。当前开发机只有软件时间戳能力，硬件实测需要支持 PHC 的网卡。
