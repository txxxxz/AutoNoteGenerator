from __future__ import annotations

from typing import List

from app.schemas.common import MindmapEdge, MindmapGraph, OutlineNode, OutlineTree


class MindmapGenerator:
    def generate(self, outline: OutlineTree) -> MindmapGraph:
        nodes = []
        edges: List[MindmapEdge] = []
        self._walk(outline.root, level=0, nodes=nodes, edges=edges, parent_id=None)
        return MindmapGraph(nodes=nodes, edges=edges)

    def _walk(
        self,
        node: OutlineNode,
        level: int,
        nodes: List[dict],
        edges: List[MindmapEdge],
        parent_id: str | None,
    ) -> None:
        nodes.append({"id": node.section_id, "label": node.title, "level": level})
        if parent_id:
            edges.append(MindmapEdge(**{"from": parent_id, "to": node.section_id}))
        for child in node.children:
            self._walk(child, level + 1, nodes, edges, node.section_id)
