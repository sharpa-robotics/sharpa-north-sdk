#!/usr/bin/env python3
"""Check video runtime dependencies without connecting to a robot or installing packages."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess


def run(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(command, 1, "", str(error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("nvdec", "software"), default="nvdec")
    parser.add_argument("--prefix", type=Path,
                        default=Path(os.environ.get("NORTHSDK_PREFIX", Path(__file__).resolve().parents[2])))
    args = parser.parse_args()
    args.prefix = args.prefix.resolve()
    failures = []

    def report(name, ok, detail):
        print(f"{'OK' if ok else 'FAIL'} {name}: {detail}")
        if not ok:
            failures.append(name)

    report("architecture", platform.machine() == "x86_64", platform.machine())
    try:
        release = platform.freedesktop_os_release()
    except OSError:
        release = {}
    print("OS: " + release.get("PRETTY_NAME", "unknown") + " (informational)")
    manifest = args.prefix / "BUILD-MANIFEST.json"
    if manifest.exists():
        try:
            metadata = json.loads(manifest.read_text())
            if metadata.get("video", {}).get("enabled") is False:
                report("video component", False, "video component is missing; obtain a complete SDK package")
        except (OSError, ValueError):
            report("package manifest", False, "cannot read BUILD-MANIFEST.json")
    # Load the delivered library, so version and transitive dependency errors surface here.
    candidates = [args.prefix / name / "libnorth_sdk.so" for name in ("lib", "lib64")]
    library = next((path for path in candidates if path.exists()), candidates[0])
    try:
        ctypes.CDLL(str(library), mode=os.RTLD_NOW)
        report("SDK runtime", True, str(library))
    except OSError as error:
        report("SDK runtime", False, str(error))

    runtime = args.prefix / "lib/video-runtime"
    inspect = str(runtime / "bin/gst-inspect-1.0") if (runtime / "bin/gst-inspect-1.0").is_file() else None
    report("bundled runtime", bool(inspect), str(runtime))
    report("plugin environment", os.environ.get("GST_PLUGIN_PATH_1_0") == str(runtime / "plugins")
           and os.environ.get("GST_PLUGIN_SYSTEM_PATH_1_0") == "", "source the SDK setup.bash before running")
    if not inspect:
        report("GStreamer", False, "gst-inspect-1.0 is missing")
    else:
        result = run([inspect, "--version"])
        version = re.search(r"(?:GStreamer|version)\s+(\d+)\.(\d+)(?:\.(\d+))?", result.stdout)
        compatible = bool(version and tuple(map(int, version.group(1, 2))) >= (1, 20))
        report("GStreamer", result.returncode == 0 and compatible,
               version.group(0) if version else result.stderr.strip() or "cannot read version")
        decoders = ("nvh264dec", "nvh265dec") if args.backend == "nvdec" else ("avdec_h264", "avdec_h265")
        for element in ("appsrc", "appsink", "h264parse", "h265parse", "videoconvert",
                        "videoscale", "queue", "jpegenc", *decoders):
            result = run([inspect, element])
            report(element, result.returncode == 0,
                   "available" if result.returncode == 0 else "missing or cannot load")
    if args.backend == "nvdec":
        smi = shutil.which("nvidia-smi")
        result = run([smi, "-L"]) if smi else None
        ok = bool(result and result.returncode == 0 and result.stdout.strip())
        report("NVIDIA driver/GPU", ok, result.stdout.strip() if ok else "nvidia-smi -L failed or unavailable")
    if failures:
        print("FAIL: resolve the checks above, then run this command again.")
        print("Source the complete SDK setup.bash; do not mix system GStreamer plugins.")
        print("Missing bundled libraries/plugins: verify package integrity or obtain a complete package.")
        if args.backend == "nvdec":
            print("For NVDEC, verify the NVIDIA driver and its decode libraries.")
        print("Use the SDK package matching your architecture and runtime library requirements.")
        return 1
    print("PASS: dependencies are available. Run the video example to verify actual stream decoding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
