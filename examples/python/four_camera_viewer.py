#!/usr/bin/env python3
"""Preview left/right head and wrist JPEGs; head 1280x960, wrists 960x960."""

from stereo_viewer import main


if __name__ == "__main__":
    raise SystemExit(main(default_cameras="all"))
