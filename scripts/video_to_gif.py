#!/usr/bin/env python3
"""Convert a screen recording (mp4/webm/mov) to an animated GIF for GitHub comments.

GitHub Issues have no Jira-style multipart attach API. A short GIF posted as
``![caption](url)`` renders inline in the comment — unlike MP4 blob links on
``qa-evidence`` that open as opaque repo files.

Usage:
    python3 scripts/video_to_gif.py INPUT.mp4 [OUTPUT.gif]
    # prints output path on stdout

Exit 0 on success; 1 on missing ffmpeg / conversion failure / oversized output.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

# GitHub comment images stay usable under ~8MB; keep headroom for camo.
DEFAULT_MAX_BYTES = 8 * 1024 * 1024


def _size(path: str) -> int:
    return os.path.getsize(path)


def convert(
    src: str,
    dest: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> str:
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH")

    # Try progressively smaller encodings until under max_bytes.
    attempts: list[tuple[int, int]] = [
        (720, 8),
        (540, 6),
        (420, 5),
        (360, 4),
    ]
    last_err = ""
    for width, fps in attempts:
        vf = (
            f"fps={fps},scale={width}:-1:flags=lanczos,"
            f"split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            src,
            "-vf",
            vf,
            "-loop",
            "0",
            dest,
        ]
        r = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(dest):
            last_err = (r.stderr or r.stdout or "ffmpeg failed").strip()
            continue
        if _size(dest) <= max_bytes:
            return dest
        last_err = f"gif still {_size(dest)} bytes after {width}px@{fps}fps"

    if os.path.isfile(dest) and _size(dest) > max_bytes:
        raise RuntimeError(
            f"GIF exceeds {max_bytes} bytes after compression attempts ({last_err})"
        )
    raise RuntimeError(last_err or "GIF conversion failed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--max-mb", type=float, default=8.0)
    a = ap.parse_args()
    out = a.output
    if not out:
        base, _ = os.path.splitext(a.input)
        out = f"{base}.gif"
    try:
        path = convert(a.input, out, max_bytes=int(a.max_mb * 1024 * 1024))
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    # Allow import without running; keep tempfile unused for API stability.
    _ = tempfile
    sys.exit(main())
