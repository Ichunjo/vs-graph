from typing import Any, assert_never, overload

import vapoursynth as vs

from .models import AudioMediaInfo, Graph, VideoMediaInfo

core = vs.core


@overload
def get_graph(clip: vs.VideoNode, /, *, pretty: bool = False) -> Graph[VideoMediaInfo]: ...
@overload
def get_graph(clip: vs.AudioNode, /, *, pretty: bool = False) -> Graph[AudioMediaInfo]: ...
@overload
def get_graph(clip: vs.VideoNode | vs.AudioNode, /, *, pretty: bool = False) -> Graph[Any]: ...
def get_graph(clip: vs.VideoNode | vs.AudioNode, /, *, pretty: bool = False) -> Graph[Any]:
    """
    Inspect the dependency graph of a VideoNode or AudioNode and return a typed Graph.

    Args:
        clip: The VapourSynth VideoNode or AudioNode to inspect.
        pretty: Whether the underlying JSON should be formatted with indentation.
    """
    match clip:
        case vs.VideoNode():
            raw_json = core.graph.VideoGraph(clip, pretty)
        case vs.AudioNode():
            raw_json = core.graph.AudioGraph(clip, pretty)
        case _:
            assert_never(clip)
    return Graph.from_json(raw_json)
