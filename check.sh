#!/usr/bin/env bash
set -euo pipefail
SDK_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SDK_DIR}/setup.bash"
case "${1:-}" in ""|--cpp-only|--video) ;; *) echo "Usage: $0 [--cpp-only|--video]" >&2; exit 2;; esac
[[ "$(uname -m)" == "x86_64" ]] || { echo "Wrong architecture" >&2; exit 1; }
for lib in "${SDK_DIR}"/lib/*.so*; do output="$(ldd "$lib")"; if [[ "$output" == *"not found"* ]]; then echo "$output"; exit 1; fi; done
if [[ "${1:-}" != --cpp-only ]]; then "${PYTHON:-python3}" -c "import north_sdk; print(north_sdk.__version__)"; fi
if [[ "${1:-}" == --video ]]; then "${PYTHON:-python3}" "${SDK_DIR}/examples/python/check_video_env.py" --backend "${VIDEO_BACKEND:-nvdec}"; fi
echo "PASS: local loading checked; no robot connection was made."
