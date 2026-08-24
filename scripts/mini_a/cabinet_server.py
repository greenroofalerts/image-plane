#!/usr/bin/env python3
"""Launch the Image Plane V1 job screen on Mini A.

Restart:
  nohup python3 ~/image-plane/scripts/mini_a/cabinet_server.py > ~/image-plane/cabinet_server.log 2>&1 &

Stable URL:
  http://192.168.178.61:8790/job/1892-26
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
for candidate in (HERE.parents[2] / "src", Path.home() / "image-plane" / "src"):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break

from image_plane.server import serve  # noqa: E402

if __name__ == "__main__":
    serve()
