import pytest
from vsgraph import get_graph

import vapoursynth as vs

core = vs.core

pytestmark = pytest.mark.vpy


def test_single_audio_node(blank_audio: vs.AudioNode) -> None:
    graph = get_graph(blank_audio)

    assert graph.root_id == graph.root.id
    assert len(graph) == 1
    assert len(graph.edges) == 0

    root = graph.root
    assert root.name == "BlankAudio"

    ainfo = root.media_info
    assert ainfo.sample_rate == 44100
    assert ainfo.bits_per_sample == 16
    assert ainfo.num_channels == 2
    assert ainfo.num_samples == 44100
    assert ainfo.type == "audio"


def test_audio_pipeline(blank_audio: vs.AudioNode) -> None:
    spliced = core.std.AudioSplice([blank_audio, blank_audio])
    graph = get_graph(spliced)

    assert graph.root.name == "AudioSplice"
    root_ainfo = graph.root.media_info
    assert root_ainfo is not None
    assert root_ainfo.num_samples == 88200

    # AudioSplice has 2 inputs from BlankAudio
    deps = graph.get_dependencies(graph.root)
    assert len(deps) == 2
    assert {n.name for n in deps} == {"BlankAudio"}
    assert deps[0].id == deps[1].id

    incoming = graph.get_incoming_edges(graph.root)
    assert len(incoming) == 2
    assert all(e.from_ == deps[0].id for e in incoming)


def test_audio_call_stack(blank_audio: vs.AudioNode) -> None:
    graph = get_graph(blank_audio)
    root = graph.root

    assert len(root.call_stack) >= 1
    frame = root.call_stack[0]
    assert frame.plugin_ns == "std"
    assert frame.function == "BlankAudio"
    assert frame.level >= 0
