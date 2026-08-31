"""Failure types for the course build.

One rule: a course either builds completely or fails with a message that names the file
and says what to do about it. Half-built output is worse than none, because it looks fine.
"""


class CourseError(Exception):
    """Anything wrong with a course's own files or manifest."""


class ManifestError(CourseError):
    """course.json is missing, malformed, or missing a required field."""


class ContentError(CourseError):
    """A markdown file does not match the shape the platform expects."""


class DataError(CourseError):
    """Assessments or suggestions are missing, malformed, or out of sync with the modules."""
