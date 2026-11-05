#!/usr/bin/env python3
"""Build a small offline LinuxPTP runtime from pinned corresponding source.

Build natively inside an Ubuntu 22.04/24.04 environment, or cross-compile with
--cc/--sysroot and an explicit --ubuntu target. Either way the binaries must not
require a newer glibc than that release ships; packaging rejects a mismatch.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile

VERSION = "4.4"
SHA256 = "61757bc0a58d789b8fcbdddf56c88a0230597184a70dcb2ac05b4c6b619f7d5c"
SOURCE = "https://codeload.github.com/richardcochran/linuxptp/tar.gz/refs/tags/v4.4"
# glibc shipped by each supported release; binaries must not require newer symbols.
GLIBC_LIMITS = {"22.04": (2, 35), "24.04": (2, 39)}
ELF_MACHINES = {62: "x86_64", 183: "aarch64"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--source",
        required=True,
        type=Path,
        help="download the pinned official archive separately",
    )
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--cc", help="cross C compiler (default: native gcc)")
    p.add_argument("--sysroot", type=Path, help="target sysroot for --cc")
    p.add_argument("--ubuntu", choices=sorted(GLIBC_LIMITS),
                   help="oldest target Ubuntu release; required with --cc")
    p.add_argument("--ldflags", default="", help="extra linker flags for the cross toolchain")
    p.add_argument("--emulator", help="user-mode emulator used to smoke-test cross binaries")
    p.add_argument("--emulator-root", type=Path,
                   help="library root for --emulator (default: --sysroot)")
    args = p.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SHA256:
        p.error("LinuxPTP source checksum mismatch")
    cross = bool(args.cc)
    if cross:
        if not args.ubuntu:
            p.error("--ubuntu is required for cross builds")
        ubuntu = args.ubuntu
        compiler = args.cc
        prefix = compiler[:-3] if compiler.endswith("gcc") else ""
        ar, strip = prefix + "ar", prefix + "strip"
        if args.sysroot:
            compiler += " --sysroot=" + str(args.sysroot.resolve())
    else:
        release = dict(
            line.split("=", 1)
            for line in Path("/etc/os-release").read_text().splitlines()
            if "=" in line
        )
        ubuntu = release.get("VERSION_ID", "").strip('"')
        if release.get("ID", "").strip('"') != "ubuntu" or ubuntu not in GLIBC_LIMITS:
            p.error("build in an Ubuntu 22.04 or 24.04 environment")
        if args.ubuntu and args.ubuntu != ubuntu:
            p.error("--ubuntu must describe the actual build host")
        if platform.machine() not in ("x86_64", "aarch64"):
            p.error("runtime supports x86_64 and aarch64 only")
        compiler, ar, strip = "gcc", "ar", "strip"
    if args.output.exists():
        p.error("output already exists; choose a new staging directory")
    with tempfile.TemporaryDirectory(prefix="northsdk-linuxptp-") as temp:
        with tarfile.open(args.source) as archive:
            for member in archive.getmembers():
                path = Path(temp) / member.name
                if (
                    not path.resolve().is_relative_to(Path(temp))
                    or member.issym()
                    or member.islnk()
                    or not (member.isdir() or member.isfile())
                ):
                    p.error("unsafe source archive")
            archive.extractall(temp)
        tree = Path(temp) / ("linuxptp-" + VERSION)
        # Disable optional crypto backends to retain a libc-only runtime. Never
        # link SDK code to GPL LinuxPTP: these are independent executable tools.
        env = dict(os.environ, CC=compiler)
        for variable in ("MAKEFLAGS", "MFLAGS", "CROSS_COMPILE"):
            env.pop(variable, None)
        detected = subprocess.check_output(
            ["sh", "incdefs.sh"], cwd=tree, env=env, text=True
        ).split()
        definitions = " ".join(
            flag
            for flag in detected
            if flag
            not in ("-DHAVE_NETTLE", "-DHAVE_GNUTLS", "-DHAVE_GNUPG", "-DHAVE_OPENSSL")
        )
        subprocess.run(
            [
                "make",
                "-j2",
                "CC=" + compiler,
                "AR=" + ar,
                "incdefs=" + definitions,
                "EXTRA_CFLAGS=",
                "EXTRA_LDFLAGS=" + args.ldflags,
                "ptp4l",
                "pmc",
            ],
            cwd=tree,
            env=env,
            check=True,
        )
        root = args.output
        (root / "bin").mkdir(parents=True)
        try:
            architectures = set()
            required_glibc = (0,)
            for name in ("ptp4l", "pmc"):
                binary = root / "bin" / name
                shutil.copy2(tree / name, binary)
                subprocess.run([strip, str(binary)], check=True)
                machine = int.from_bytes(binary.read_bytes()[18:20], "little")
                if machine not in ELF_MACHINES:
                    raise ValueError("unsupported LinuxPTP architecture: " + str(machine))
                architectures.add(ELF_MACHINES[machine])
                if not cross:
                    subprocess.run([str(binary), "-v"], check=True)
                elif args.emulator:
                    smoke = [args.emulator]
                    library_root = args.emulator_root or args.sysroot
                    if library_root:
                        smoke += ["-L", str(library_root.resolve())]
                    subprocess.run(smoke + [str(binary), "-v"], check=True)
                symbols = subprocess.check_output(
                    ["readelf", "--version-info", str(binary)], text=True
                )
                glibc = max(
                    (tuple(map(int, v.split("."))) for v in re.findall(r"GLIBC_([\d.]+)", symbols)),
                    default=(0,),
                )
                if glibc > GLIBC_LIMITS[ubuntu]:
                    raise ValueError(
                        f"{name} requires GLIBC {'.'.join(map(str, glibc))}, newer than Ubuntu {ubuntu}"
                    )
                required_glibc = max(required_glibc, glibc)
                dependencies = subprocess.check_output(
                    ["readelf", "-d", str(binary)], text=True
                )
                needed = set(re.findall(r"Shared library: \[(.*?)\]", dependencies))
                if not needed <= {
                    "libc.so.6",
                    "libm.so.6",
                    "librt.so.1",
                    "libpthread.so.0",
                    "ld-linux-x86-64.so.2",
                    "ld-linux-aarch64.so.1",
                }:
                    raise ValueError(
                        "unexpected LinuxPTP runtime dependencies: " + str(needed)
                    )
            if len(architectures) != 1:
                raise ValueError("LinuxPTP tools were built for different architectures")
            shutil.copy2(tree / "COPYING", root / "COPYING")
            shutil.copy2(args.source, root / "source.tar.gz")
            shutil.copy2(__file__, root / "build_timesync_runtime.py")
            files = {
                str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in sorted(root.rglob("*"))
                if f.is_file()
            }
            manifest = dict(
                schema=1,
                version=VERSION,
                source_url=SOURCE,
                source_sha256=SHA256,
                architecture=architectures.pop(),
                # glibc is backward compatible: newer releases run binaries built for older ones.
                ubuntu=[release for release in sorted(GLIBC_LIMITS)
                        if release >= ubuntu and required_glibc <= GLIBC_LIMITS[release]],
                modes=["hardware", "software"],
                build=dict(
                    cross=cross,
                    compiler=subprocess.check_output(
                        compiler.split() + ["--version"], text=True
                    ).splitlines()[0],
                    sysroot=args.sysroot.name if args.sysroot else None,
                ),
                files=files,
            )
            (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
        except BaseException:
            shutil.rmtree(root)
            raise
    print(args.output)


if __name__ == "__main__":
    main()
