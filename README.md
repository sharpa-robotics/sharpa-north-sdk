# North SDK 1.2.0

Target: Linux x86_64.
Python bindings: CPython 3.10, CPython 3.12. Use an interpreter matching an included binding.
Minimum runtime symbol requirements: {"GLIBC": "2.35", "GLIBCXX": "3.4.30", "CXXABI": "1.3.13"}.
The target system must provide compatible C/C++ runtime libraries.

```bash
sudo ./tools/setup-host --user "$USER"
source ./setup.bash
./check.sh
./bin/north_sdk_robot_smoke --endpoint 'udp/192.168.100.100:7449' --seconds 5
```

Connections use software gPTP by default, temporarily managing CLOCK_REALTIME and recognized NTP services.
The one-time setup authorizes this; hardware PHC mode is opt-in through `TimeSyncOptions.mode`.
The last SDK lease restores prior NTP service state; see `docs/time-sync.md` for lifecycle and error handling.

C++ only: `./check.sh --cpp-only`. Video: `./check.sh --video` (NVIDIA), or
`VIDEO_BACKEND=software ./check.sh --video`. NVIDIA drivers remain a system prerequisite.
GStreamer, required plugins and the minimal LGPL H.264/H.265 software decoder are bundled privately.
Always source setup.bash; do not mix plugins from other installations.
Software decoding has limited performance; there is no automatic fallback.

Start with `manual/zh/SDK/应用开发.md` or `manual/en/SDK/Application Development.md`.
Offline HTML: `manual/html/index.html`; PDF: `manual/pdf/`; Word: `manual/word/`.
License notices and FFmpeg sources: `licenses/` and `lib/video-runtime/`.
Corresponding Ubuntu sources: `north-sdk-video-sources-linux-x86_64.tar.gz`, delivered alongside this archive.
Its SHA256 is recorded in BUILD-MANIFEST.json.
Check archive integrity using the adjacent .sha256 file; extracted files use SHA256SUMS.

Automatic gPTP is enabled by default. One-time offline host setup: `sudo ./tools/setup-host --user "$USER"`. The account then uses the SDK without sudo. The service adjusts only the selected NIC PHC; system time is unchanged. Disable with `config.time_sync.enabled = false`. See `docs/time-sync.md`.
