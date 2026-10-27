from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field, fields
from fractions import Fraction
from typing import Any, Literal, Self, override

import vapoursynth as vs

from .enum import RequestPattern

type NodeKey = vs.RawNode | Node[Any] | str


@dataclass(slots=True, kw_only=True)
class MediaInfo(ABC):
    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Self: ...


@dataclass(slots=True, kw_only=True)
class VideoMediaInfo(MediaInfo):
    """Media information for video nodes."""

    format: str
    width: int
    height: int
    fps_num: int
    fps_den: int
    num_frames: int
    type: Literal["video"] = "video"

    @property
    def fps(self) -> Fraction:
        """Frame rate as an exact Fraction."""
        return Fraction(self.fps_num, self.fps_den) if self.fps_den != 0 else Fraction(0, 1)

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(
            format=str(data["format"]),
            width=int(data["width"]),
            height=int(data["height"]),
            fps_num=int(data["fps_num"]),
            fps_den=int(data["fps_den"]),
            num_frames=int(data["num_frames"]),
        )


@dataclass(slots=True, kw_only=True)
class AudioMediaInfo(MediaInfo):
    """Media information for audio nodes."""

    format: str
    sample_rate: int
    bits_per_sample: int
    num_channels: int
    channel_layout: int
    num_samples: int
    num_frames: int
    type: Literal["audio"] = "audio"

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(
            format=str(data["format"]),
            sample_rate=int(data["sample_rate"]),
            bits_per_sample=int(data["bits_per_sample"]),
            num_channels=int(data["num_channels"]),
            channel_layout=int(data["channel_layout"]),
            num_samples=int(data["num_samples"]),
            num_frames=int(data["num_frames"]),
        )


@dataclass(slots=True, kw_only=True)
class CallFrame:
    """Represents a call frame in the node creation stack."""

    level: int
    frame_id: str
    plugin_id: str
    plugin_ns: str
    function: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(
            level=int(data["level"]),
            frame_id=str(data["frame_id"]),
            plugin_id=str(data["plugin_id"]),
            plugin_ns=str(data["plugin_ns"]),
            function=str(data["function"]),
            arguments=dict(data["arguments"]),
        )


@dataclass(slots=True, kw_only=True)
class Edge:
    """Represents a dependency edge between nodes in the graph."""

    from_: str
    to: str
    pattern: RequestPattern

    @property
    def source(self) -> str:
        """Alias for from_ (upstream node ID)."""
        return self.from_

    @property
    def target(self) -> str:
        """Alias for to (downstream node ID)."""
        return self.to

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        return {"from": self.from_, "to": self.to, "pattern": self.pattern}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        from_node = data.get("from")
        if from_node is None:
            from_node = data["from_"]
        return cls(from_=str(from_node), to=str(data["to"]), pattern=RequestPattern(data["pattern"]))


@dataclass(slots=True, kw_only=True)
class Node[MediaInfoT: MediaInfo]:
    """Represents a filter node in the graph."""

    id: str
    name: str
    filter_mode: vs.FilterMode
    processing_time_ns: int
    media_info: MediaInfoT
    call_stack: list[CallFrame] = field(default_factory=list)

    @property
    def processing_time_ms(self) -> float:
        """Processing time in milliseconds."""
        return self.processing_time_ns / 1_000_000.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "filter_mode": self.filter_mode,
            "processing_time_ns": self.processing_time_ns,
            "media_info": self.media_info.to_dict(),
            "call_stack": [frame.to_dict() for frame in self.call_stack],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        raw_info = data["media_info"]
        match raw_info["type"]:
            case "video":
                media_info = VideoMediaInfo.from_dict(raw_info)
            case "audio":
                media_info = AudioMediaInfo.from_dict(raw_info)
            case other:
                raise ValueError(f"Unknown media_info type: {other!r}")

        call_stack = [CallFrame.from_dict(frame) for frame in data["call_stack"]]

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            filter_mode=vs.FilterMode(data["filter_mode"]),
            processing_time_ns=int(data["processing_time_ns"]),
            media_info=media_info,
            call_stack=call_stack,
        )


@dataclass(slots=True, kw_only=True)
class Graph[MediaInfoT: (VideoMediaInfo, AudioMediaInfo)](Collection[Node[MediaInfoT]]):
    """Full VapourSynth dependency graph output."""

    root_id: str
    nodes: list[Node[MediaInfoT]] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    @override
    def __contains__(self, node_or_id: object) -> bool:
        return to_node_id(node_or_id) in self.nodes_by_id if isinstance(node_or_id, (vs.RawNode, Node, str)) else False

    @override
    def __iter__(self) -> Iterator[Node[MediaInfoT]]:
        return iter(self.nodes)

    @override
    def __len__(self) -> int:
        return len(self.nodes)

    def __getitem__(self, node_or_id: NodeKey) -> Node[MediaInfoT]:
        if node := self.nodes_by_id.get(to_node_id(node_or_id)):
            return node
        raise KeyError(node_or_id)

    @property
    def root(self) -> Node[MediaInfoT]:
        """The root node where inspection started."""
        for node in self.nodes:
            if node.id == self.root_id:
                return node
        raise KeyError(f"Root node '{self.root_id}' not found in graph nodes")

    @property
    def nodes_by_id(self) -> dict[str, Node[MediaInfoT]]:
        """Dictionary of nodes keyed by their ID."""
        return {node.id: node for node in self.nodes}

    def get_incoming_edges(self, node_or_id: NodeKey) -> list[Edge]:
        """Return all edges where this node is the target (inputs to this node)."""
        nid = to_node_id(node_or_id)
        return [edge for edge in self.edges if edge.to == nid]

    def get_outgoing_edges(self, node_or_id: NodeKey) -> list[Edge]:
        """Return all edges where this node is the source (outputs from this node)."""
        nid = to_node_id(node_or_id)
        return [edge for edge in self.edges if edge.from_ == nid]

    def get_dependencies(self, node_or_id: NodeKey) -> list[Node[MediaInfoT]]:
        """Return upstream nodes that this node directly depends on."""
        node_map = self.nodes_by_id
        incoming = self.get_incoming_edges(node_or_id)
        return [node_map[e.from_] for e in incoming if e.from_ in node_map]

    def get_dependents(self, node_or_id: NodeKey) -> list[Node[MediaInfoT]]:
        """Return downstream nodes that directly depend on this node."""
        node_map = self.nodes_by_id
        outgoing = self.get_outgoing_edges(node_or_id)
        return [node_map[e.to] for e in outgoing if e.to in node_map]

    def to_dict(self) -> dict[str, Any]:
        """Convert graph to a dictionary matching the JSON format."""
        return {
            "root_id": self.root_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    def to_json(self, *, indent: int | None = None, **kwargs: Any) -> str:
        """Serialize graph to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, **kwargs)

    def to_mermaid(self) -> str:
        """Generate a Mermaid flowchart diagram of the graph."""
        lines = ["flowchart TD"]
        for node in self.nodes:
            lbl = f"{node.name} ({node.id})"
            lines.append(f'    {node.id}["{lbl}"]')
        for edge in self.edges:
            pattern_label = edge.pattern.name if edge.pattern != RequestPattern.GENERAL else ""
            if pattern_label:
                lines.append(f"    {edge.from_} -->|{pattern_label}| {edge.to}")
            else:
                lines.append(f"    {edge.from_} --> {edge.to}")
        return "\n".join(lines)

    def to_dot(self, *, direction: str = "TB", detailed: bool = True, fontname: str | None = None) -> str:
        """
        Generate a Graphviz DOT representation of the graph.

        Args:
            direction: Layout direction ('TB', 'LR', 'BT', 'RL'). Default is 'TB'.
            detailed: Whether to render HTML-like table record labels with media info and profiling.
            fontname: Font name for Graphviz nodes and edges (e.g. 'Helvetica'). If None, uses Graphviz defaults.
        """
        font_attr = f'fontname="{fontname}", ' if fontname else ""
        lines = [
            "digraph VSDependencyGraph {",
            f'    rankdir="{direction}";',
            f'    node [shape=box, style="filled,rounded", {font_attr}fillcolor="#f8f9fa", color="#343a40"];',
            f'    edge [{font_attr}color="#495057"];',
        ]

        for node in self.nodes:
            is_root = node.id == self.root_id
            if detailed:
                border_color = "#dc3545" if is_root else "#6c757d"
                header_bg = "#ffc107" if is_root else "#e9ecef"
                root_badge = " (Root)" if is_root else ""

                match node.media_info:
                    case VideoMediaInfo() as vi:
                        info_line = f"{vi.width}x{vi.height} | {vi.format} | {float(vi.fps):.3f} fps"
                    case AudioMediaInfo() as ai:
                        info_line = f"{ai.sample_rate} Hz | {ai.num_channels} ch | {ai.format}"

                perf_line = f"Time: {node.processing_time_ms:.2f} ms | Mode: {node.filter_mode.name}"

                label = (
                    f'<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="2" COLOR="{border_color}">'
                    f'<TR><TD BGCOLOR="{header_bg}"><B>{node.name} [{node.id}]{root_badge}</B></TD></TR>'
                    f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{info_line}</FONT></TD></TR>'
                    f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="10">{perf_line}</FONT></TD></TR>'
                    f"</TABLE>>"
                )
                lines.append(f'    "{node.id}" [shape=none, margin=0, label={label}];')
            else:
                root_style = ', fillcolor="#fff3cd", color="#856404"' if is_root else ""
                lines.append(f'    "{node.id}" [label="{node.name} ({node.id})"{root_style}];')

        for edge in self.edges:
            pattern_label = edge.pattern.name if edge.pattern != RequestPattern.GENERAL else ""
            if pattern_label:
                lines.append(f'    "{edge.from_}" -> "{edge.to}" [label="{pattern_label}"];')
            else:
                lines.append(f'    "{edge.from_}" -> "{edge.to}";')

        lines.append("}")
        return "\n".join(lines)

    def to_ascii(self, *, compact: bool = False) -> str:
        """
        Generate an ASCII / Unicode tree representation of the dependency graph starting at root.

        Args:
            compact: If True, only prints 'Name [id]'. If False, includes format, resolution, and time.
        """
        root_node = self.root
        lines = list[str]()
        visited = set[str]()

        def format_node_label(node: Node[MediaInfoT]) -> str:
            if compact:
                return f"{node.name} [{node.id}]"

            match node.media_info:
                case VideoMediaInfo() as vi:
                    spec = f"{vi.width}x{vi.height} {vi.format}"
                case AudioMediaInfo() as ai:
                    spec = f"{ai.sample_rate}Hz {ai.num_channels}ch {ai.format}"

            return f"{node.name} [{node.id}] ({spec}, {node.processing_time_ms:.2f}ms)"

        def walk(current_node: Node[MediaInfoT], prefix: str = "") -> None:
            deps = self.get_dependencies(current_node)
            count = len(deps)
            for i, dep in enumerate(deps):
                is_last = i == count - 1
                branch = "└── " if is_last else "├── "
                extension = "    " if is_last else "│   "

                if dep.id in visited:
                    lines.append(f"{prefix}{branch}{dep.name} [{dep.id}] (ref)")
                else:
                    visited.add(dep.id)
                    lines.append(f"{prefix}{branch}{format_node_label(dep)}")
                    walk(dep, prefix + extension)

        lines.append(format_node_label(root_node))
        visited.add(root_node.id)
        walk(root_node)
        return "\n".join(lines)

    def to_cytoscape(self) -> dict[str, list[dict[str, Any]]]:
        """
        Export the graph to a Cytoscape.js compatible dictionary.

        Returns:
            A dictionary with 'nodes' and 'edges' lists formatted for Cytoscape.js.
        """
        return {
            "nodes": [
                {
                    "data": {
                        "id": node.id,
                        "label": node.name,
                        "name": node.name,
                        "filter_mode": node.filter_mode.value,
                        "filter_mode_name": node.filter_mode.name,
                        "processing_time_ns": node.processing_time_ns,
                        "processing_time_ms": node.processing_time_ms,
                        "media_info": node.media_info.to_dict(),
                        "call_stack": [frame.to_dict() for frame in node.call_stack],
                        "is_root": node.id == self.root_id,
                    }
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "data": {
                        "id": f"e{i}_{edge.from_}_{edge.to}",
                        "source": edge.from_,
                        "target": edge.to,
                        "pattern": edge.pattern.value,
                        "pattern_name": edge.pattern.name,
                        "label": edge.pattern.name if edge.pattern != RequestPattern.GENERAL else "",
                    }
                }
                for i, edge in enumerate(self.edges)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct a Graph from a dictionary."""
        return cls(
            root_id=str(data["root_id"]),
            nodes=[Node.from_dict(n) for n in data["nodes"]],
            edges=[Edge.from_dict(e) for e in data["edges"]],
        )

    @classmethod
    def from_json(cls, json_str: str | bytes | bytearray) -> Self:
        """Construct a Graph from a JSON string or bytes."""
        return cls.from_dict(json.loads(json_str))


def to_node_id(node_or_id: NodeKey) -> str:
    """Normalize a Python VideoNode/AudioNode, graph Node, or string ID to a node ID string."""
    if isinstance(node_or_id, vs.RawNode):
        return f"node_{hash(node_or_id)}"
    if isinstance(node_or_id, Node):
        return node_or_id.id
    return str(node_or_id)
