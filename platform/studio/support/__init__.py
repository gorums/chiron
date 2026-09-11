"""The helpers more than one part of Studio needs, each in one place.

They are here rather than copied because a second copy of `write_json` is a second answer
to "is a half-written file possible?" — and the answer has to stay no.

    files     atomic read_json / write_json / write_text, and the small string helpers
    ids       what a course id, a module id and a profile name may be
    errors    GenerationError
    log       the `studio` logger: a rotating file plus the ring buffer /api/logs reads
"""
