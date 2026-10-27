import pytest
from vsgraph import get_graph

import vapoursynth as vs

pytestmark = pytest.mark.vpy


def test_graph_traversal(diamond_video_dag: vs.VideoNode) -> None:
    graph = get_graph(diamond_video_dag)
    splice_node = graph.root

    # Test accepting either Node or str ID
    incoming_by_node = graph.get_incoming_edges(splice_node)
    incoming_by_id = graph.get_incoming_edges(splice_node.id)
    assert incoming_by_node == incoming_by_id

    outgoing_by_node = graph.get_outgoing_edges(splice_node)
    outgoing_by_id = graph.get_outgoing_edges(splice_node.id)
    assert outgoing_by_node == outgoing_by_id

    deps_by_node = graph.get_dependencies(splice_node)
    deps_by_id = graph.get_dependencies(splice_node.id)
    assert deps_by_node == deps_by_id

    dependents_by_node = graph.get_dependents(splice_node)
    dependents_by_id = graph.get_dependents(splice_node.id)
    assert dependents_by_node == dependents_by_id

    # Root has no downstream dependents in this DAG
    assert len(dependents_by_node) == 0

    # Test edge properties
    for edge in graph.edges:
        assert edge.source == edge.from_
        assert edge.target == edge.to


def test_mermaid_export(diamond_video_dag: vs.VideoNode) -> None:
    graph = get_graph(diamond_video_dag)
    mermaid = graph.to_mermaid()

    lines = mermaid.splitlines()
    assert lines[0] == "flowchart TD"

    for node in graph.nodes:
        assert any(node.id in line for line in lines)

    for edge in graph.edges:
        assert any(f"{edge.from_} -->" in line for line in lines)
