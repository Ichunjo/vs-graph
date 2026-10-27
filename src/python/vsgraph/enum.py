from enum import IntEnum


class RequestPattern(IntEnum):
    """VapourSynth node request pattern."""

    GENERAL = 0
    NO_FRAME_REUSE = 1
    STRICT_SPATIAL = 2
    FRAME_REUSE_LAST_ONLY = 3
