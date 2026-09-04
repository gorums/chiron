"""The one error a generation job raises on purpose."""


class GenerationError(RuntimeError):
    """A run cannot continue: the model returned nothing usable, or the brief is unusable."""
