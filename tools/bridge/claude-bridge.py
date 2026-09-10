#!/usr/bin/env python3
"""Where the bridge used to live.

It is `tutor-bridge.py` now: it reaches whatever provider is configured rather than one
company's model, and its own name should not say otherwise. This file stays because
`start-bridge.bat`, the README and a shortcut on somebody's desktop point at it. It will go
once nothing names it any more.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "tutor-bridge.py")


def load():
    """Import it by path: a file name with a hyphen in it is not an identifier."""
    spec = importlib.util.spec_from_file_location("tutor_bridge", TARGET)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    print("  (claude-bridge.py is now tutor-bridge.py; starting that instead.)")
    sys.exit(load().main())
