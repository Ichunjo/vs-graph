from fractions import Fraction

import pytest
from vsgraph import get_graph

import vapoursynth as vs

core = vs.core
pytestmark = pytest.mark.vpy


def test_single_video_node(blank_video: vs.VideoNode) -> None:
    graph = get_graph(blank_video, pretty=True)

    assert graph.root_id == graph.root.id
    assert len(graph) == 1
    assert len(graph.edges) == 0

    root = graph.root
    assert root.name == "BlankClip"

    vinfo = root.media_info
    assert vinfo.format == "RGB24"
    assert vinfo.width == 640
    assert vinfo.height == 480
    assert vinfo.fps_num == 24
    assert vinfo.fps_den == 1
    assert vinfo.fps == Fraction(24, 1)
    assert vinfo.num_frames == 100
    assert vinfo.type == "video"

    assert len(root.call_stack) >= 1
    frame = root.call_stack[0]
    assert frame.plugin_ns == "std"
    assert frame.function == "BlankClip"
    assert frame.level >= 0
    assert frame.frame_id.startswith("frame_")


def test_linear_video_pipeline(video_pipeline: vs.VideoNode) -> None:
    graph = get_graph(video_pipeline)

    assert graph.root.name == "Bicubic"
    assert len(graph) == 3
    assert len(graph.edges) == 2

    # Verify nodes in chain
    node_names = [n.name for n in graph.nodes]
    assert "BlankClip" in node_names
    assert "Text" in node_names
    assert "Bicubic" in node_names

    # Verify root media info changed according to resize
    vinfo = graph.root.media_info
    assert vinfo is not None
    assert vinfo.width == 1280
    assert vinfo.height == 720
    assert vinfo.format == "YUV420P8"

    # Verify edge connectivity
    bicubic_node = graph.root
    incoming_to_bicubic = graph.get_incoming_edges(bicubic_node)
    assert len(incoming_to_bicubic) == 1

    text_node = graph[incoming_to_bicubic[0].from_]
    assert text_node.name == "Text"

    incoming_to_text = graph.get_incoming_edges(text_node)
    assert len(incoming_to_text) == 1

    blank_node = graph[incoming_to_text[0].from_]
    assert blank_node.name == "BlankClip"


def test_branching_video_dag(diamond_video_dag: vs.VideoNode) -> None:
    graph = get_graph(diamond_video_dag)

    assert graph.root.name == "Splice"
    splice_node = graph.root

    # Splice has two inputs: video_pipeline and invert
    dependencies = graph.get_dependencies(splice_node)
    dep_names = {node.name for node in dependencies}
    assert "Bicubic" in dep_names
    assert "Invert" in dep_names

    # Invert in turn depends on Bicubic
    invert_node = next(n for n in graph.nodes if n.name == "Invert")
    invert_deps = graph.get_dependencies(invert_node)
    assert any(n.name == "Bicubic" for n in invert_deps)

    # Bicubic has two downstream dependents: Splice and Invert
    bicubic_node = next(n for n in graph.nodes if n.name == "Bicubic")
    bicubic_dependents = graph.get_dependents(bicubic_node)
    dependent_names = {n.name for n in bicubic_dependents}
    assert "Splice" in dependent_names
    assert "Invert" in dependent_names


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

    assert len(root.call_stack) >= 1
    frame = root.call_stack[0]
    assert frame.plugin_ns == "std"
    assert frame.function == "BlankAudio"
    assert frame.level >= 0


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

