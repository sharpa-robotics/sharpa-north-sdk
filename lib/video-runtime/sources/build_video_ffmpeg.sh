#!/usr/bin/env bash
# Build only native H.264/H.265 CPU decoding with LGPL FFmpeg, no GPL/nonfree codecs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="$(realpath -m "${1:?Usage: build_video_ffmpeg.sh PREFIX [BUILD_DIR]}")"
BUILD="$(realpath -m "${2:-${ROOT}/build/video-ffmpeg}")"
# Match the libav plugin ABI, independently of the Ubuntu release. With
# NORTHSDK_VIDEO_ROOT (prepare_video_root.py) the plugin and nasm come from that root.
VIDEO_ROOT="${NORTHSDK_VIDEO_ROOT:-}"
if [[ -n "${VIDEO_ROOT}" ]]; then
  PLUGIN="${VIDEO_ROOT}/usr/lib/x86_64-linux-gnu/gstreamer-1.0/libgstlibav.so"
  export PATH="${VIDEO_ROOT}/usr/bin:${PATH}"
else
  PLUGIN="$(LC_ALL=C gst-inspect-1.0 libav | awk '$1 == "Filename" {print $2; exit}')"
fi
ABI="$(readelf -d "${PLUGIN}" | sed -n 's/.*\[libavcodec\.so\.\([0-9]*\)\].*/\1/p')"
case "${ABI}" in
  58) VERSION=4.4.8; SHA256=c73848c4ae283d9eaee7be3b276affbc3543380483555500d0dd2c9b7e1c39c3 ;;
  60) VERSION=6.1.6; SHA256=d4fcb164028dd3beee5d92c0ac72e46aac6973c75ea12dc14de07bf8f407370a ;;
  *) echo "No pinned LGPL FFmpeg recipe for libavcodec ABI ${ABI}; add a matching recipe." >&2; exit 2 ;;
esac
[[ "$(uname -m)" == x86_64 ]] || { echo 'x86_64 build required' >&2; exit 2; }
URL="https://ffmpeg.org/releases/ffmpeg-${VERSION}.tar.xz"
mkdir -p "${BUILD}" "${PREFIX}/sources" "${PREFIX}/licenses"
ARCHIVE="${BUILD}/ffmpeg-${VERSION}.tar.xz"
if ! echo "${SHA256}  ${ARCHIVE}" | sha256sum -c --status 2>/dev/null; then
  curl -fsSL --retry 3 "${URL}" -o "${ARCHIVE}"
  echo "${SHA256}  ${ARCHIVE}" | sha256sum -c --quiet
fi
if ! command -v nasm >/dev/null; then
  echo 'nasm is required in the build environment for x86 SIMD optimizations.' >&2
  exit 2
fi
tar -xJf "${ARCHIVE}" -C "${BUILD}"
cd "${BUILD}/ffmpeg-${VERSION}"
FLAGS=(--prefix="${PREFIX}" --enable-shared --disable-static --enable-pic
  --disable-programs --disable-doc --disable-debug --disable-autodetect
  --disable-gpl --disable-nonfree --disable-version3 --disable-network
  --disable-everything --disable-avdevice --disable-vulkan
  --enable-decoder=h264,hevc --enable-parser=h264,hevc)
./configure "${FLAGS[@]}"
make -j"${JOBS:-6}"
make install
cp "${ARCHIVE}" "${PREFIX}/sources/"
cp COPYING.LGPLv2.1 LICENSE.md "${PREFIX}/licenses/"
{
  echo "url=${URL}"
  echo "sha256=${SHA256}"
  printf 'configure'; printf ' %q' "${FLAGS[@]}"; printf '\n'
  "${CC:-cc}" --version | head -1
} > "${PREFIX}/sources/ffmpeg-build.txt"
cp "${ROOT}/tools/build_video_ffmpeg.sh" "${PREFIX}/sources/"
echo "LGPL FFmpeg prefix: ${PREFIX}"
