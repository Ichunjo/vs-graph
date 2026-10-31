from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field, fields
from fractions import Fraction
from typing import Any, Literal, Self, override

import vapoursynth as vs

from .vs import AudioFormat, RequestPattern

type NodeKey = vs.RawNode | Node[Any] | NodeRef | str


@dataclass(slots=True, kw_only=True)
class MediaInfo(ABC):
    @property
    @abstractmethod
    def format(self) -> vs.VideoFormat | AudioFormat: ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        data = dict[str, Any]()

        for dfield in fields(self):
            attr = getattr(self, dfield.name)
            if dfield.name != "gpu_resident" or attr is not None:
                data[dfield.name] = attr

        data["format"] = self.format._as_dict()

        return data

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Self: ...


@dataclass(slots=True, kw_only=True)
class VideoMediaInfo(MediaInfo):
    """Media information for video nodes."""

    format_id: vs.PresetVideoFormat
    width: int
    height: int
    fps_num: int
    fps_den: int
    num_frames: int
    gpu_resident: bool | None = None
    type: Literal["vnode"] = "vnode"

    @property
    def fps(self) -> Fraction:
        """Frame rate as an exact Fraction."""
        return Fraction(self.fps_num, self.fps_den) if self.fps_den != 0 else Fraction(0, 1)

    @property
    @override
    def format(self) -> vs.VideoFormat:
        """The resolved VideoFormat from the core."""
        return vs.core.get_video_format(self.format_id)

    @override
    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["format"] = self.format._as_dict()
        return data

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(
            format_id=vs.PresetVideoFormat(data["format_id"]),
            width=int(data["width"]),
            height=int(data["height"]),
            fps_num=int(data["fps_num"]),
            fps_den=int(data["fps_den"]),
            num_frames=int(data["num_frames"]),
            gpu_resident=data.get("gpu_resident"),
        )


@dataclass(slots=True, kw_only=True)
class AudioMediaInfo(MediaInfo):
    """Media information for audio nodes."""

    format_id: int
    sample_rate: int
    num_samples: int
    num_frames: int
    gpu_resident: bool | None = None
    type: Literal["anode"] = "anode"

    @property
    @override
    def format(self) -> AudioFormat:
        """The resolved AudioFormat."""
        return AudioFormat.from_id(self.format_id)

    @override
    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["format"] = self.format._as_dict()
        return data

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(
            format_id=int(data["format_id"]),
            sample_rate=int(data["sample_rate"]),
            num_samples=int(data["num_samples"]),
            num_frames=int(data["num_frames"]),
            gpu_resident=data.get("gpu_resident"),
        )


@dataclass(slots=True, kw_only=True)
class FrameInfo(ABC):
    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        data = dict[str, Any]()

        for dfield in fields(self):
            attr = getattr(self, dfield.name)
            if dfield.name != "gpu_resident" or attr is not None:
                data[dfield.name] = attr

        return data

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Self: ...


@dataclass(slots=True, kw_only=True)
class VideoFrameInfo(FrameInfo):
    """Video frame argument metadata."""

    id: str
    format_id: vs.PresetVideoFormat
    width: int
    height: int
    gpu_resident: bool | None = None
    type: Literal["vframe"] = "vframe"

    @property
    def format(self) -> vs.VideoFormat:
        """The resolved VideoFormat from the core."""
        return vs.core.get_video_format(self.format_id)

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(
            id=str(data["id"]),
            format_id=vs.PresetVideoFormat(data["format_id"]),
            width=int(data["width"]),
            height=int(data["height"]),
            gpu_resident=data.get("gpu_resident"),
        )


@dataclass(slots=True, kw_only=True)
class AudioFrameInfo(FrameInfo):
    """Audio frame argument metadata."""

    id: str
    format_id: int
    num_samples: int
    gpu_resident: bool | None = None
    type: Literal["aframe"] = "aframe"

    @property
    def format(self) -> AudioFormat:
        """The resolved AudioFormat."""
        return AudioFormat.from_id(self.format_id)

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(
            id=str(data["id"]),
            format_id=int(data["format_id"]),
            num_samples=int(data["num_samples"]),
            gpu_resident=data.get("gpu_resident"),
        )


@dataclass(slots=True, kw_only=True)
class NodeRef(ABC):
    """Reference to a node in a call frame argument."""

    id: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        return {dfield.name: getattr(self, dfield.name) for dfield in fields(self)}

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Self: ...


@dataclass(slots=True, kw_only=True)
class VideoNodeRef(NodeRef):
    """Video node argument reference."""

    type: Literal["vnode"] = "vnode"

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(id=str(data["id"]))


@dataclass(slots=True, kw_only=True)
class AudioNodeRef(NodeRef):
    """Audio node argument reference."""

    type: Literal["anode"] = "anode"

    @classmethod
    @override
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(id=str(data["id"]))


@dataclass(slots=True, kw_only=True)
class FuncRef:
    """Function argument reference."""

    id: str
    type: Literal["func"] = "func"

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        return {"id": self.id, "type": self.type}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(id=str(data["id"]))


@dataclass(slots=True, kw_only=True)
class CallFrame:
    """Represents a call frame in the node creation stack."""

    level: int
    id: str
    plugin_id: str
    plugin_ns: str
    function: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""

        def serialize_arg(val: Any) -> Any:
            if isinstance(val, (FrameInfo, NodeRef, FuncRef)):
                return val.to_dict()
            if isinstance(val, list):
                return [serialize_arg(item) for item in val]
            return val

        return {
            "level": self.level,
            "id": self.id,
            "plugin_id": self.plugin_id,
            "plugin_ns": self.plugin_ns,
            "function": self.function,
            "arguments": {k: serialize_arg(v) for k, v in self.arguments.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""

        def parse_args(val: Any) -> Any:
            if isinstance(val, dict):
                match val.get("type"):
                    case "vnode":
                        return VideoNodeRef.from_dict(val)
                    case "anode":
                        return AudioNodeRef.from_dict(val)
                    case "vframe":
                        return VideoFrameInfo.from_dict(val)
                    case "aframe":
                        return AudioFrameInfo.from_dict(val)
                    case "func":
                        return FuncRef.from_dict(val)
                    case _:
                        return val
            return [parse_args(item) for item in val] if isinstance(val, list) else val

        return cls(
            level=int(data["level"]),
            id=str(data["id"]),
            plugin_id=str(data["plugin_id"]),
            plugin_ns=str(data["plugin_ns"]),
            function=str(data["function"]),
            arguments={k: parse_args(v) for k, v in data["arguments"].items()},
        )


@dataclass(slots=True, kw_only=True)
class Edge:
    """Represents a dependency edge between nodes in the graph."""

    source: str
    target: str
    pattern: RequestPattern

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary."""
        return {"source": self.source, "target": self.target, "pattern": self.pattern}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        return cls(source=str(data["source"]), target=str(data["target"]), pattern=RequestPattern(data["pattern"]))


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
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "filter_mode": self.filter_mode,
            "processing_time_ns": self.processing_time_ns,
            "media_info": self.media_info.to_dict(),
            "call_stack": [frame.to_dict() for frame in self.call_stack],
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Construct from a dictionary."""
        match (raw_info := data["media_info"])["type"]:
            case "vnode":
                media_info = VideoMediaInfo.from_dict(raw_info)
            case "anode":
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
        return (
            to_node_id(node_or_id) in self.nodes_by_id
            if isinstance(node_or_id, (vs.RawNode, Node, NodeRef, str))
            else False
        )

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
        return [edge for edge in self.edges if edge.target == nid]

    def get_outgoing_edges(self, node_or_id: NodeKey) -> list[Edge]:
        """Return all edges where this node is the source (outputs from this node)."""
        nid = to_node_id(node_or_id)
        return [edge for edge in self.edges if edge.source == nid]

    def get_dependencies(self, node_or_id: NodeKey) -> list[Node[MediaInfoT]]:
        """Return upstream nodes that this node directly depends on."""
        node_map = self.nodes_by_id
        incoming = self.get_incoming_edges(node_or_id)
        return [node_map[e.source] for e in incoming if e.source in node_map]

    def get_dependents(self, node_or_id: NodeKey) -> list[Node[MediaInfoT]]:
        """Return downstream nodes that directly depend on this node."""
        node_map = self.nodes_by_id
        outgoing = self.get_outgoing_edges(node_or_id)
        return [node_map[e.target] for e in outgoing if e.target in node_map]

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
                lines.append(f"    {edge.source} -->|{pattern_label}| {edge.target}")
            else:
                lines.append(f"    {edge.source} --> {edge.target}")
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
                        info_line = f"{vi.width}x{vi.height} | {vi.format.name} | {float(vi.fps):.3f} fps"
                    case AudioMediaInfo() as ai:
                        info_line = f"{ai.sample_rate} Hz | {ai.format.num_channels} ch"

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
                lines.append(f'    "{edge.source}" -> "{edge.target}" [label="{pattern_label}"];')
            else:
                lines.append(f'    "{edge.source}" -> "{edge.target}";')

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
                    spec = f"{vi.width}x{vi.height} {vi.format.name}"
                case AudioMediaInfo() as ai:
                    spec = f"{ai.sample_rate}Hz {ai.format.num_channels}ch"

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
                        "id": f"e{i}_{edge.source}_{edge.target}",
                        "source": edge.source,
                        "target": edge.target,
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
    """Normalize a Python VideoNode/AudioNode, graph Node, NodeRef, or string ID to a node ID string."""
    if isinstance(node_or_id, vs.RawNode):
        return str(hash(node_or_id))
    if isinstance(node_or_id, (Node, NodeRef)):
        return node_or_id.id
    return str(node_or_id)
