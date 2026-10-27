# vsgraph

VapourSynth plugin (Rust) and typed Python API for inspecting filter graphs.

Walks the dependency graph of a `VideoNode` or `AudioNode` and returns typed dataclasses describing every node (filter name, filter mode, media info, processing time, creation call stack) and edge (request pattern).

Graphs can be exported to Mermaid, Graphviz DOT, ASCII, Cytoscape.js or JSON.

## Requirements

- Python ≥ 3.12
- VapourSynth ≥ R79 (API 4.2 or 4.3)
- The core must be created with `vs.CoreCreationFlags.ENABLE_GRAPH_INSPECTION`

## Installation

```powershell
pip install vsgraph
```

The wheel ships the native `graph` plugin, which VapourSynth autoloads.

## Usage

```python
import vapoursynth as vs
from vsgraph import get_graph

core = vs.core
vs._try_enable_introspection(0)

clip = core.std.BlankClip(width=1920, height=1080, format=vs.YUV420P8)
clip = core.resize.Bicubic(clip, width=1280, height=720)

graph = get_graph(clip)

print(graph.root.name, graph.root.media_info.fps)
print(graph.to_ascii())

for node in graph.get_dependencies(graph.root):
    print(node.name, node.filter_mode, f"{node.processing_time_ms:.2f} ms")
```

### Exports

| Method                 | Output                     |
| ---------------------- | -------------------------- |
| `Graph.to_mermaid()`   | Mermaid flowchart          |
| `Graph.to_dot()`       | Graphviz DOT               |
| `Graph.to_ascii()`     | Tree view                  |
| `Graph.to_cytoscape()` | Cytoscape.js elements dict |
| `Graph.to_json()`      | JSON string                |

The raw plugin functions are also available as `core.graph.VideoGraph(clip, pretty)` and `core.graph.AudioGraph(clip, pretty)`, both returning a JSON string.

## Development

Requires a Rust toolchain and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --no-editable
uv run pytest
```
