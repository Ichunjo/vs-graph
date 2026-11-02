from typing import Any, assert_never, overload

import vapoursynth as vs

from .models import AudioMediaInfo, Graph, VideoMediaInfo

type MediaNode = vs.VideoNode | vs.AudioNode

core = vs.core


@overload
def get_graph(clip: vs.VideoNode, /, *, pretty: bool = False, reset_timing: bool = False) -> Graph[VideoMediaInfo]: ...
@overload
def get_graph(clip: vs.AudioNode, /, *, pretty: bool = False, reset_timing: bool = False) -> Graph[AudioMediaInfo]: ...
@overload
def get_graph(clip: MediaNode, /, *, pretty: bool = False, reset_timing: bool = False) -> Graph[Any]: ...
def get_graph(clip: MediaNode, /, *, pretty: bool = False, reset_timing: bool = False) -> Graph[Any]:
    """
    Inspect the dependency graph of a VideoNode or AudioNode and return a typed Graph.

    Args:
        clip: The VapourSynth VideoNode or AudioNode to inspect.
        pretty: Whether the underlying JSON should be formatted with indentation.
        reset_timing: Whether to reset the node and core freed node processing timers after inspection.
    """
    match clip:
        case vs.VideoNode():
            raw_json = core.graph.VideoGraph(clip, pretty, reset_timing)
        case vs.AudioNode():
            raw_json = core.graph.AudioGraph(clip, pretty, reset_timing)
        case _:
            assert_never(clip)
    return Graph.from_json(raw_json)
