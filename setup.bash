# Source this file from Bash after unpacking; no installation or sudo required.
_NORTH_SDK_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export NORTH_SDK_ROOT="${_NORTH_SDK_DIR}"
export NORTHSDK_PREFIX="${NORTH_SDK_ROOT}"
export LD_LIBRARY_PATH="${NORTH_SDK_ROOT}/lib:${NORTH_SDK_ROOT}/lib/video-runtime/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
if [[ -d "${NORTH_SDK_ROOT}/lib/video-runtime/plugins" ]]; then
  export PATH="${NORTH_SDK_ROOT}/lib/video-runtime/bin:${PATH}"
  export GST_PLUGIN_PATH_1_0="${NORTH_SDK_ROOT}/lib/video-runtime/plugins"
  export GST_PLUGIN_SYSTEM_PATH_1_0=""
  export GST_PLUGIN_SCANNER_1_0="${NORTH_SDK_ROOT}/lib/video-runtime/libexec/gst-plugin-scanner"
  export GST_REGISTRY_1_0="${XDG_CACHE_HOME:-${HOME}/.cache}/north-sdk/$(printf '%s' "${NORTH_SDK_ROOT}" | sha256sum | cut -c1-16)-registry.bin"
  mkdir -p "$(dirname "${GST_REGISTRY_1_0}")"
fi
export PYTHONPATH="${NORTH_SDK_ROOT}/lib/python${PYTHONPATH:+:${PYTHONPATH}}"
export CMAKE_PREFIX_PATH="${NORTH_SDK_ROOT}${CMAKE_PREFIX_PATH:+:${CMAKE_PREFIX_PATH}}"
unset _NORTH_SDK_DIR
