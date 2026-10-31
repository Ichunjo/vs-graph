from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Self, override

import vapoursynth as vs


class RequestPattern(IntEnum):
    """VapourSynth node request pattern."""

    GENERAL = 0
    NO_FRAME_REUSE = 1
    STRICT_SPATIAL = 2
    FRAME_REUSE_LAST_ONLY = 3


@dataclass(slots=True)
class AudioFormat:
    sample_type: vs.SampleType
    bits_per_sample: int
    bytes_per_sample: int
    num_channels: int
    channel_layout: vs.ChannelLayout

    @override
    def __eq__(self, other: object) -> bool:
        return int(self) == int(other) if isinstance(other, AudioFormat) else NotImplemented

    @override
    def __hash__(self) -> int:
        return int(self)

    def __int__(self) -> int:
        return (
            (int(self.sample_type) & 0xF) << 60
            | (self.bits_per_sample & 0xFF) << 48
            | (self.channel_layout & 0x0000_FFFF_FFFF_FFFF)
        )

    @property
    def id(self) -> int:
        return int(self)

    @classmethod
    def from_id(cls, id: int) -> Self:
        sample_type = vs.SampleType((id >> 60) & 0xF)
        bits_per_sample = (id >> 48) & 0xFF
        channel_layout = vs.ChannelLayout(id & 0x0000_FFFF_FFFF_FFFF)

        bytes_per_sample = 1 << ((bits_per_sample + 7) // 8 - 1).bit_length()
        num_channels = channel_layout.bit_count()

        return cls(
            sample_type=sample_type,
            bits_per_sample=bits_per_sample,
            bytes_per_sample=bytes_per_sample,
            num_channels=num_channels,
            channel_layout=channel_layout,
        )

    def _as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sample_type": self.sample_type,
            "bits_per_sample": self.bits_per_sample,
            "bytes_per_sample": self.bytes_per_sample,
            "num_channels": self.num_channels,
            "channel_layout": self.channel_layout,
        }
