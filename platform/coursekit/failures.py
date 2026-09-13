"""Where `coursekit.llm.failures` used to live.

The classifier moved into the provider layer, next to the code that produces the stderr it
reads. This re-export stays because two things import it from outside the package by path -
`tools/bridge/tutor-bridge.py` and the tests - and because the name is in the docstrings of
half of Studio. Like the module it points at, it is standard library only.
"""

from __future__ import annotations

from .llm.failures import (  # noqa: F401  (a re-export is the whole point)
    AUTH,
    MODEL,
    QUOTA,
    TIMEOUT,
    TRANSIENT,
    UNKNOWN,
    classify,
    describe,
    explain,
    from_status,
    resets_at,
)
