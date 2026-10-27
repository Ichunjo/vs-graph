from fractions import Fraction

import pytest
from vsgraph import get_graph

import vapoursynth as vs

pytestmark = pytest.mark.vpy


def test_single_video_node(blank_video: vs.VideoNode) -> None:
    graph = get_graph(blank_video)

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


def test_video_call_stack(blank_video: vs.VideoNode) -> None:
    graph = get_graph(blank_video)
    node = graph.root

    assert len(node.call_stack) >= 1
    frame = node.call_stack[0]
    assert frame.plugin_ns == "std"
    assert frame.function == "BlankClip"
    assert frame.level >= 0
    assert frame.frame_id.startswith("frame_")


@pytest.mark.parametrize("pretty", [True, False])
def test_video_graph_pretty_param(blank_video: vs.VideoNode, pretty: bool) -> None:
    graph = get_graph(blank_video, pretty=pretty)
    assert graph.root.name == "BlankClip"
    assert len(graph) == 1
