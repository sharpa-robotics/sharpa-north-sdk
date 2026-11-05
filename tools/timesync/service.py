#!/usr/bin/python3
"""Socket-activated NorthSDK hardware/software gPTP session manager.

All executable/configuration paths are root-owned installation paths. The wire
protocol has no command, filename, timeout, or servo-policy arguments.
"""
import argparse
import array
import ctypes
import dataclasses
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import ipaddress
import socket
import struct
import subprocess
import threading
import time

READY, PREPARING, FAILED, LOST = 2, 1, 3, 4
OK, UNAVAILABLE, PERMISSION, UNSUPPORTED, CONFLICT, TIMEOUT, LOST_ERROR, INVALID = (
    range(8)
)


class UnsupportedHardware(OSError):
    """The NIC explicitly lacks the required hardware timestamping capability."""


class UnavailableError(OSError):
    """A recoverable host/link readiness problem."""


IFACE = re.compile(r"[A-Za-z0-9_.:-]{1,15}\Z")


@dataclasses.dataclass
class Health:
    state: int = PREPARING
    error: int = OK
    message: str = "waiting for fresh synchronization samples"
    offset: int = 0
    count: int = 0
    ingress: int = 0
    received: float = 0.0
    ever_ready: bool = False
    threshold: int = 50
    required: int = 10

    def invalidate(self, message):
        self.state = LOST if self.ever_ready else PREPARING
        self.error = LOST_ERROR if self.ever_ready else OK
        self.message = message
        self.count = 0

    def update(self, offset, ingress, client, now):
        if not client or ingress <= 0:
            self.invalidate("port is not a receiving PTP client")
            return
        if ingress == self.ingress:
            self.expire(now)
            return
        # Compare PHC elapsed time with a monotonic observer to reject steps in
        # either direction. A missing stream must earn ten fresh samples again.
        discontinuity = self.ingress and (
            ingress < self.ingress
            or abs((ingress - self.ingress) / 1e9 - (now - self.received)) > 0.25
        )
        if discontinuity:
            self.ingress = ingress
            self.received = now
            self.invalidate("PTP ingress clock discontinuity")
            return
        self.expire(now)
        self.ingress, self.received, self.offset = ingress, now, offset
        self.count = (
            min(self.required, self.count + 1) if abs(offset) < self.threshold else 0
        )
        if self.count >= self.required:
            self.state, self.error, self.message = READY, OK, "synchronized"
            self.ever_ready = True
        else:
            self.invalidate_if_outside()

    def invalidate_if_outside(self):
        self.state = LOST if self.ever_ready else PREPARING
        self.error = LOST_ERROR if self.ever_ready else OK
        self.message = "waiting for consecutive offsets below the configured threshold"

    def expire(self, now):
        if self.state != FAILED and (self.received == 0 or now - self.received > 1.0):
            self.invalidate("PTP synchronization samples are stale")


def timestamp_info(interface):
    if not IFACE.fullmatch(interface):
        raise ValueError("invalid interface")

    class Info(ctypes.Structure):
        _fields_ = [
            ("cmd", ctypes.c_uint32),
            ("timestamping", ctypes.c_uint32),
            ("index", ctypes.c_int32),
            ("tx_types", ctypes.c_uint32),
            ("tx_reserved", ctypes.c_uint32 * 3),
            ("rx_filters", ctypes.c_uint32),
            ("rx_reserved", ctypes.c_uint32 * 3),
        ]

    info = Info()
    info.cmd = 0x41  # ETHTOOL_GET_TS_INFO
    request = struct.pack("16sP", interface.encode(), ctypes.addressof(info)) + bytes(
        16
    )
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        fcntl.ioctl(sock.fileno(), 0x8946, request)  # SIOCETHTOOL
    if (Path("/sys/class/net") / interface / "carrier").read_text().strip() != "1":
        raise UnavailableError("interface link is down")
    return info.index, info.timestamping


def phc_index(interface):
    index, flags = timestamp_info(interface)
    if index < 0 or flags & 0x45 != 0x45:
        raise UnsupportedHardware("NIC lacks hardware TX/RX/raw timestamping and a PHC")
    return index


def route_interface(target):
    """Read the kernel route through netlink, without changing networking."""
    address = ipaddress.ip_address(target)
    family = socket.AF_INET if address.version == 4 else socket.AF_INET6
    route = struct.pack("BBBBBBBBI", family, address.max_prefixlen, 0, 0, 0, 0, 0, 0, 0)
    attribute = struct.pack("HH", 4 + len(address.packed), 1) + address.packed
    packet = struct.pack("IHHII", 16 + len(route) + len(attribute), 26, 1, 1, 0)
    with socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 0) as sock:
        sock.settimeout(0.1)
        sock.sendto(packet + route + attribute, (0, 0))
        data = sock.recv(8192)
    if len(data) < 28 or struct.unpack_from("H", data, 4)[0] != 24:
        raise UnavailableError("no route to the configured North endpoint")
    pos = 28
    while pos + 4 <= len(data):
        size, kind = struct.unpack_from("HH", data, pos)
        if size < 4 or pos + size > len(data):
            break
        if kind == 4 and size == 8:  # RTA_OIF
            return socket.if_indextoname(struct.unpack_from("I", data, pos + 4)[0])
        pos += (size + 3) & ~3
    raise UnavailableError("route has no outgoing interface")


def wired_interface(interface):
    path = Path("/sys/class/net") / interface
    return (
        (path / "device").exists()
        and not (path / "wireless").exists()
        and (path / "type").read_text().strip() == "1"
    )


def select_interface(interface, target):
    if not interface:
        if target:
            interface = route_interface(target)
        else:
            candidates = []
            for path in sorted(Path("/sys/class/net").iterdir()):
                try:
                    if (
                        wired_interface(path.name)
                        and (path / "carrier").read_text().strip() == "1"
                    ):
                        candidates.append(path.name)
                except OSError:
                    continue
            if len(candidates) != 1:
                raise ValueError(
                    "cannot uniquely select the North wired interface; configure time_sync.interface"
                )
            interface = candidates[0]
    if not IFACE.fullmatch(interface) or not wired_interface(interface):
        raise ValueError(
            "North gPTP requires a physical wired interface; configure time_sync.interface"
        )
    return interface


def external_ptp(managed_pids):
    # Never stop/reconfigure an existing host servo. Conservatively reject unknown
    # ptp4l/phc2sys owners, since their config may select this same PHC indirectly.
    for path in Path("/proc").glob("[0-9]*/comm"):
        try:
            if int(
                path.parent.name
            ) not in managed_pids and path.read_text().strip() in (
                "ptp4l",
                "phc2sys",
                "ts2phc",
            ):
                return True
        except (OSError, ValueError):
            continue
    return False


class Servo:
    def __init__(self, interface, index, prefix, runtime, threshold=50):
        self.interface, self.index = interface, index
        self.prefix, self.runtime = prefix, runtime / interface
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.health = Health(threshold=threshold)
        self.stop = threading.Event()
        self.pmc = None
        self.writer = None
        self.started = time.monotonic()
        self.guard = (
            runtime / ("clock-" + (str(index) if index >= 0 else "realtime") + ".lock")
        ).open("a")
        fcntl.flock(self.guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = (prefix / "slave.cfg").read_text()
        # North's automotive profile synchronizes the raw MGBE2 numeric domain.
        # Announce/BMCA are disabled: do not invent a TAI-UTC correction. In
        # software mode CLOCK_REALTIME consequently follows North, not NTP UTC.
        overrides = {
            "servo_offset_threshold": threshold,
            "utc_offset": 0,
            "kernel_leap": 0,
        }
        if index < 0:
            # Keep software timestamp jitter below the expensive PI reset path.
            # The SDK quality criterion remains independently configurable.
            overrides["step_threshold"] = 0.003
        for key, value in overrides.items():
            pattern = r"(?m)^" + key + r"\s+[^\n]*"
            line = key + " " + str(value)
            if re.search(pattern, config):
                config = re.sub(pattern, line, config)
            else:
                config += "\n" + line + "\n"
        # Private sockets prevent interference with system-wide ptp4l clients.
        config += "\nuds_address " + str(self.runtime / "ptp4l") + "\n"
        config += "uds_ro_address " + str(self.runtime / "ptp4l-ro") + "\n"
        config += "uds_file_mode 0600\nuds_ro_file_mode 0600\n"
        (self.runtime / "ptp4l.cfg").write_text(config)
        try:
            self.process = subprocess.Popen(
                [
                    str(prefix / "runtime/bin/ptp4l"),
                    "-H" if index >= 0 else "-S",
                    "-i",
                    interface,
                    "-f",
                    str(self.runtime / "ptp4l.cfg"),
                    "-l",
                    "4",
                ],
                stdin=subprocess.DEVNULL,
            )  # diagnostics go to journal
        except BaseException:
            self.guard.close()
            raise
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()

    def watch(self):
        # Keep one PMC client: one-shot PMC waits at batch boundaries and would
        # undersample the 8 Hz Sync stream. Only GET queries are ever submitted.
        command = [
            str(self.prefix / "runtime/bin/pmc"),
            "-u",
            "-b",
            "0",
            "-d",
            "0",
            "-t",
            "1",
            "-i",
            str(self.runtime / "pmc"),
            "-s",
            str(self.runtime / "ptp4l-ro"),
        ]
        try:
            with self.lock:
                if self.stop.is_set():
                    return
                self.pmc = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                self.writer = threading.Thread(target=self.query, daemon=True)
                self.writer.start()
            fields = {}
            for line in self.pmc.stdout:
                match = re.fullmatch(
                    r"\s*(master_offset|ingress_time|portState)\s+(-?\w+)\s*", line
                )
                if not match:
                    continue
                key, value = match.groups()
                fields[key] = value
                if key == "portState" and all(
                    k in fields for k in ("master_offset", "ingress_time")
                ):
                    with self.lock:
                        self.health.update(
                            int(fields["master_offset"]),
                            int(fields["ingress_time"]),
                            value in ("SLAVE", "CLIENT"),
                            time.monotonic(),
                        )
                    fields.clear()
            if not self.stop.is_set():
                with self.lock:
                    self.health.state, self.health.error = FAILED, UNAVAILABLE
                    self.health.message = "PTP management monitor exited"
        except (OSError, ValueError):
            with self.lock:
                self.health.state, self.health.error = FAILED, UNAVAILABLE
                self.health.message = "cannot monitor LinuxPTP management responses"
        finally:
            self.stop.set()
            try:
                (self.runtime / "pmc").unlink(missing_ok=True)
            except OSError:
                pass

    def query(self):
        command = 0
        while not self.stop.is_set():
            if self.process.poll() is not None:
                with self.lock:
                    self.health.state, self.health.error = FAILED, UNAVAILABLE
                    self.health.message = (
                        "ptp4l exited; inspect northsdk-timesync journal"
                    )
                self.pmc.terminate()
                return
            try:
                # One line at a time: PMC polls stdin before fgets(), whose
                # read-ahead can otherwise leave a second line buffered forever.
                self.pmc.stdin.write(
                    ("GET TIME_STATUS_NP\n", "GET PORT_DATA_SET\n")[command]
                )
                command = 1 - command
                self.pmc.stdin.flush()
            except (OSError, ValueError):
                return
            self.stop.wait(0.05)

    def snapshot(self):
        with self.lock:
            self.health.expire(time.monotonic())
            return dataclasses.replace(self.health)

    def close(self):
        self.stop.set()
        # Synchronize with monitor creation so a concurrent close cannot miss a
        # PMC process that is about to start.
        with self.lock:
            pmc, writer = self.pmc, self.writer
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if pmc is not None and pmc.poll() is None:
            pmc.terminate()
            try:
                pmc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pmc.kill()
                pmc.wait()
        if writer is not None:
            writer.join(timeout=2)
        self.thread.join(timeout=2)
        if pmc is not None:
            pmc.stdin.close()
            pmc.stdout.close()
        self.guard.close()


# Runtime masks prevent timedated or dependency activation from restarting a
# competing service. Never change persistent enablement or RTC contents.
NTP_UNITS = (
    "systemd-timesyncd.service",
    "chrony.service",
    "ntp.service",
    "ntpsec.service",
    "openntpd.service",
)
NTP_PROCESSES = {"systemd-timesyn", "chronyd", "ntpd", "openntpd"}


def systemctl(*args):
    return subprocess.run(
        ["/usr/bin/systemctl", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout


def unknown_time_process(groups):
    for path in Path("/proc").glob("[0-9]*/comm"):
        try:
            if path.read_text().strip() in NTP_PROCESSES:
                memberships = (path.parent / "cgroup").read_text().splitlines()
                if not any(
                    line.split(":", 2)[-1] == group
                    for line in memberships
                    for group in groups
                    if group
                ):
                    return True
        except FileNotFoundError:
            continue
    return False


class SystemTime:
    """Crash-recoverable ownership of recognized system time services."""

    def __init__(self, runtime):
        self.journal = runtime / "ntp-state.json"

    def acquire(self):
        if self.journal.exists():
            raise BlockingIOError("previous system-time ownership requires recovery")
        states = []
        groups = []
        for unit in NTP_UNITS:
            values = dict(
                line.split("=", 1)
                for line in systemctl(
                    "show",
                    unit,
                    "--property=LoadState,ActiveState,UnitFileState,ControlGroup",
                ).splitlines()
                if "=" in line
            )
            if values.get("LoadState") == "not-found":
                continue
            active = values.get("ActiveState")
            if active not in ("active", "inactive", "failed"):
                raise BlockingIOError("system time service is changing state: " + unit)
            if active == "active":
                groups.append(values.get("ControlGroup", ""))
            if values.get("UnitFileState") not in ("masked", "masked-runtime"):
                states.append({"unit": unit, "active": active == "active"})
            elif active == "active":
                raise BlockingIOError("active masked system time service: " + unit)
        if unknown_time_process(groups):
            raise BlockingIOError("unmanaged system time process exists")
        temporary = self.journal.with_suffix(".tmp")
        with temporary.open("w") as stream:
            json.dump(states, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        temporary.replace(self.journal)
        try:
            for state in states:
                systemctl("mask", "--runtime", "--now", state["unit"])
            for state in states:
                status = dict(
                    line.split("=", 1)
                    for line in systemctl(
                        "show", state["unit"], "--property=ActiveState,UnitFileState"
                    ).splitlines()
                    if "=" in line
                )
                if status.get("ActiveState") not in (
                    "inactive",
                    "failed",
                ) or status.get("UnitFileState") not in ("masked", "masked-runtime"):
                    raise BlockingIOError(
                        "cannot safely pause system time service: " + state["unit"]
                    )
            if unknown_time_process([]):
                raise BlockingIOError(
                    "external time process remains after pausing recognized services"
                )
        except BaseException:
            self.restore()
            raise

    def restore(self):
        if not self.journal.exists():
            return
        states = json.loads(self.journal.read_text())
        # Validate the journal before issuing any privileged command.
        if not isinstance(states, list) or any(
            not isinstance(s, dict)
            or s.get("unit") not in NTP_UNITS
            or type(s.get("active")) is not bool
            for s in states
        ):
            raise ValueError("invalid system-time recovery journal")
        for state in states:
            systemctl("unmask", "--runtime", state["unit"])
        # Unmask every alias/dependency before restarting any original service.
        for state in states:
            if state["active"]:
                systemctl("start", state["unit"])
        self.journal.unlink()


@dataclasses.dataclass
class Session:
    interface: str
    index: int
    mode: int
    target: str
    threshold: int
    servo: object = None
    health: Health = dataclasses.field(default_factory=Health)
    ntp_owned: bool = False
    retry_at: float = 0.0
    closing: bool = False
    lock: object = dataclasses.field(default_factory=threading.Lock)

    def snapshot(self):
        with self.lock:
            if self.closing:
                return Health(
                    message="previous session is stopping; waiting for NTP restoration",
                    threshold=self.threshold,
                )
            return (
                self.servo.snapshot()
                if self.servo
                else dataclasses.replace(self.health)
            )


class Manager:
    LEASE_SECONDS = 5.0

    def __init__(self, prefix, runtime, allow_system_time=False):
        self.prefix, self.runtime = prefix, runtime
        self.allow_system_time = allow_system_time
        self.servos = {}
        self.leases = {}
        self.closed = False
        self.failure = None
        self.last_conflict_check = 0.0
        self.foreign_ptp = False
        self.foreign_system_time = False
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.system_time = SystemTime(runtime)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def prepare(
        self, interface, mode=2, token="test", uid=0, target="", threshold=1000000
    ):
        with self.lock:
            if self.failure:
                raise UnavailableError("host session cleanup failed: " + self.failure)
            if self.closed:
                raise UnavailableError("time-sync manager is stopping")
            identity = (uid, token)
            existing = self.leases.get(identity)
            if existing:
                key = existing[0]
                session = self.servos[key]
                if (
                    (interface and interface != session.interface)
                    or (mode and mode != session.mode)
                    or target != session.target
                    or (session.mode == 2 and threshold != session.threshold)
                ):
                    raise ValueError(
                        "a lease cannot change its synchronization source or policy"
                    )
                self.leases[identity] = (key, time.monotonic() + self.LEASE_SECONDS)
                return session
            interface = select_interface(interface, target)
            if mode == 2:
                index, flags = timestamp_info(interface)
                index = -1
                if flags & 0x1A != 0x1A:
                    raise OSError("NIC lacks software TX/RX timestamping")
            else:
                index = phc_index(interface)
            if mode == 2 and not self.allow_system_time:
                raise PermissionError(
                    "software synchronization requires setup-host system-time authorization"
                )
            limit = 50 if mode == 1 else threshold
            key = (interface, mode, target, limit)
            if key not in self.servos:
                if any(
                    s.interface == interface
                    or (index >= 0 and s.index == index)
                    or (mode == 2 and s.mode == 2)
                    for s in self.servos.values()
                ):
                    raise BlockingIOError(
                        "another session owns this interface, PHC, or system clock"
                    )
                self.servos[key] = Session(
                    interface,
                    index,
                    mode,
                    target,
                    limit,
                    health=Health(threshold=limit),
                )
            session = self.servos[key]
            self.leases[identity] = (key, time.monotonic() + self.LEASE_SECONDS)
            self.wake.set()
            return session

    def release(self, uid, token):
        with self.lock:
            self.leases.pop((uid, token), None)
            self.wake.set()

    def run(self):
        try:
            self.manage_sessions()
        except Exception as error:
            # Fail closed; main exits so systemd kills any children before the
            # recovery hook restores NTP. Never continue serving stale READY.
            with self.lock:
                self.failure = str(error)

    def manage_sessions(self):
        # Only this worker starts/stops servos and changes NTP ownership. Requests
        # remain responsive during systemctl calls and process cleanup.
        while True:
            self.wake.wait(0.1)
            self.wake.clear()
            with self.lock:
                now = time.monotonic()
                self.leases = {
                    k: v
                    for k, v in self.leases.items()
                    if v[1] > now and not self.closed
                }
                sessions = list(self.servos.items())
                closed = self.closed
                pids = {s.servo.process.pid for s in self.servos.values() if s.servo}
            if now - self.last_conflict_check >= 1:
                self.foreign_ptp = external_ptp(pids)
                self.foreign_system_time = any(
                    s.ntp_owned for _, s in sessions
                ) and unknown_time_process([])
                self.last_conflict_check = now
            for key, session in sessions:
                with self.lock:
                    unused = not any(v[0] == key for v in self.leases.values())
                    if unused:
                        with session.lock:
                            session.closing = True
                if unused:
                    self.cleanup(session)
                    with self.lock:
                        # A connection arriving during cleanup must start a fresh
                        # session only after prior NTP restoration has finished.
                        if any(v[0] == key for v in self.leases.values()):
                            session.closing = False
                            session.health = Health(threshold=session.threshold)
                        else:
                            self.servos.pop(key, None)
                    continue
                if session.closing or now < session.retry_at:
                    continue
                conflict = self.foreign_ptp or (
                    session.mode == 2 and self.foreign_system_time
                )
                if session.servo and not conflict:
                    if (
                        not session.servo.stop.is_set()
                        and session.servo.process.poll() is None
                    ):
                        continue
                    self.cleanup(session)
                    with session.lock:
                        session.closing = False
                        session.health = Health(
                            state=FAILED,
                            error=UNAVAILABLE,
                            message="servo process failed; retrying after backoff",
                            threshold=session.threshold,
                        )
                    session.retry_at = time.monotonic() + 5
                    continue
                try:
                    if session.servo:
                        self.cleanup(session)
                        session.closing = False
                    with self.lock:
                        pids = {
                            s.servo.process.pid for s in self.servos.values() if s.servo
                        }
                    if conflict or external_ptp(pids):
                        raise BlockingIOError("an unmanaged host PTP servo exists")
                    if session.mode == 2:
                        self.system_time.acquire()
                        session.ntp_owned = True
                    servo = Servo(
                        session.interface,
                        session.index,
                        self.prefix,
                        self.runtime,
                        session.threshold,
                    )
                    with session.lock:
                        session.servo = servo
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    self.cleanup(session)
                    session.closing = False
                    session.health = Health(
                        state=FAILED,
                        error=error_code(error),
                        message=str(error),
                        threshold=session.threshold,
                    )
                    session.retry_at = time.monotonic() + 5
            if closed:
                return

    def cleanup(self, session):
        with session.lock:
            session.closing = True
            servo, session.servo = session.servo, None
        if servo:
            servo.close()
        if session.ntp_owned:
            self.system_time.restore()
            session.ntp_owned = False

    def close(self):
        with self.lock:
            self.closed = True
            self.wake.set()
        self.thread.join()


def error_code(error):
    if isinstance(error, PermissionError):
        return PERMISSION
    if isinstance(error, BlockingIOError):
        return CONFLICT
    if isinstance(error, (UnavailableError, subprocess.SubprocessError)):
        return UNAVAILABLE
    return UNSUPPORTED if isinstance(error, OSError) else INVALID


def response(health, interface="", phc="", mode=2, ntp_owned=False):
    age = (
        min(86400000, max(0, int((time.monotonic() - health.received) * 1000)))
        if health.received
        else 86400000
    )
    message = health.message.replace("\t", " ").replace("\n", " ")[:500] or "ok"
    return "\t".join(
        map(
            str,
            [
                "NTS2",
                health.error,
                health.state,
                interface,
                phc,
                health.offset,
                health.count,
                age,
                health.threshold,
                health.required,
                message,
                mode,
                int(ntp_owned),
            ],
        )
    ).encode()


def handle(connection, manager, allowed):
    fd = None
    mode = 2
    try:
        connection.settimeout(0.2)
        _, uid, _ = struct.unpack(
            "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        )
        payload = connection.recv(1024)
        if uid not in allowed and uid != 0:
            raise PermissionError("user is not registered by setup-host")
        request = payload.decode("ascii").split("\t")
        if (
            len(request) != 8
            or request[0] != "NTS2"
            or request[1] not in ("prepare", "clock", "release")
        ):
            raise ValueError(
                "invalid or incompatible control request; update setup-host and SDK together"
            )
        _, operation, interface, mode, token, target, threshold, reserved = request
        if (
            (interface and not IFACE.fullmatch(interface))
            or not re.fullmatch(r"[a-f0-9]{32}", token)
            or reserved != "0"
        ):
            raise ValueError("invalid interface or session token")
        mode, threshold = int(mode), int(threshold)
        if mode not in (1, 2) or not 1 <= threshold <= 1000000000:
            raise ValueError("invalid time-sync policy")
        if target:
            ipaddress.ip_address(target)
        if operation == "release":
            manager.release(uid, token)
            connection.send(response(Health(message="lease released")))
            return
        session = manager.prepare(interface, mode, token, uid, target, threshold)
        health = session.snapshot()
        path = "/dev/ptp" + str(session.index) if session.mode == 1 else ""
        if session.closing:
            health = Health(
                message="previous session is stopping; waiting for NTP restoration",
                threshold=session.threshold,
            )
        if operation == "clock":
            if health.state != READY:
                health.error = LOST_ERROR
                health.message = "clock synchronization is not ready"
            elif session.mode == 1:
                fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
        control = (
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [fd]))]
            if fd is not None
            else []
        )
        connection.sendmsg(
            [
                response(
                    health,
                    session.interface,
                    path,
                    session.mode,
                    session.ntp_owned,
                )
            ],
            control,
        )
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        code = error_code(error)
        try:
            connection.send(
                response(
                    Health(state=FAILED, error=code, message=str(error)),
                    mode=mode if mode in (1, 2) else 2,
                )
            )
        except OSError:
            pass
    finally:
        if fd is not None:
            os.close(fd)
        connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, default=Path("/opt/northsdk-timesync"))
    parser.add_argument(
        "--config", type=Path, default=Path("/etc/northsdk-timesync.json")
    )
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("time-sync service must run under its installed system unit")
    runtime = Path("/run/northsdk-timesync")
    if args.recover:
        SystemTime(runtime).restore()
        return
    if (
        os.environ.get("LISTEN_PID") != str(os.getpid())
        or os.environ.get("LISTEN_FDS") != "1"
    ):
        raise SystemExit("time-sync service requires systemd socket activation")
    config = json.loads(args.config.read_text())
    allowed = set(config["allowed_uids"])
    manager = Manager(args.prefix, runtime, config.get("allow_system_time", False))
    listener = socket.socket(fileno=3)
    listener.settimeout(0.5)
    done = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: done.set())
    slots = threading.BoundedSemaphore(16)

    def serve(connection):
        try:
            handle(connection, manager, allowed)
        finally:
            slots.release()

    try:
        while not done.is_set():
            if manager.failure:
                raise RuntimeError("host session cleanup failed: " + manager.failure)
            try:
                connection, _ = listener.accept()
            except socket.timeout:
                continue
            # Slow clients cannot block other SDK instances or the servo monitor.
            if slots.acquire(blocking=False):
                threading.Thread(target=serve, args=(connection,), daemon=True).start()
            else:
                connection.close()
    finally:
        listener.close()
        manager.close()


if __name__ == "__main__":
    main()
