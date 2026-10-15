"""Every file an exported ONNX model consists of, and their hashes (P90).

torch's exporter writes a graph above 2 GB-adjacent sizes — and here, any graph
with enough initialisers — as TWO files: `x.onnx`, the graph, and
`x.onnx.data`, the weights. Hashing only the first certifies the structure and
leaves the weights unverified, so an untrained `.data` beside a verified graph
would load and serve. The set of files is read from the graph itself, so a
graph that references a data file nobody recorded cannot pass either.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def external_files(graph: Path) -> list[str]:
    """Names of the external data files the graph references, sorted."""
    import onnx

    model = onnx.load(str(graph), load_external_data=False)
    names = set()
    for tensor in model.graph.initializer:
        if tensor.data_location == onnx.TensorProto.EXTERNAL:
            for entry in tensor.external_data:
                if entry.key == "location":
                    names.add(entry.value)
    return sorted(names)


def file_hashes(graph: Path) -> dict[str, str]:
    """{file name: sha256} for the graph and every file it references."""
    graph = Path(graph)
    files = [graph.name] + external_files(graph)
    return {name: hashlib.sha256((graph.parent / name).read_bytes()).hexdigest()
            for name in files}
