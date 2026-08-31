#!/usr/bin/env python3
"""Entry point for the course platform. See `python platform/build.py --help`.

Courses are written in real typography — em dashes, middots, arrows — and the Windows
console still defaults to cp1252, which cannot encode most of it. Force UTF-8 on the way
out so a build report never dies on a character in its own summary line.
"""

import os
import sys

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # already redirected, or not a text stream
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coursekit.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
