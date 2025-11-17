import { useCallback, useEffect, useMemo, useState } from 'react';
import mermaid from 'mermaid';

import { MindmapGraph } from '../api/types';
import '../styles/github-markdown.css';

type MindmapDiagramProps = {
  graph: MindmapGraph;
};

const MindmapDiagram = ({ graph }: MindmapDiagramProps) => {
  const mermaidCode = useMemo(() => buildMermaidCode(graph), [graph]);
  const [svgMarkup, setSvgMarkup] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const renderDiagram = async () => {
      if (!mermaidCode.trim()) {
        setSvgMarkup('');
        return;
      }
      try {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: 'neutral'
        });
        const { svg } = await mermaid.render(`mindmap-${Date.now()}`, mermaidCode);
        if (!cancelled) {
          setSvgMarkup(svg);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setSvgMarkup('');
          setError(err instanceof Error ? err.message : '渲染失败');
        }
      }
    };
    void renderDiagram();
    return () => {
      cancelled = true;
    };
  }, [mermaidCode]);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => {
      clearTimeout(timer);
    };
  }, [copied]);

  const handleCopy = useCallback(async () => {
    if (!navigator?.clipboard) {
      setCopied(false);
      return;
    }
    try {
      await navigator.clipboard.writeText(mermaidCode);
      setCopied(true);
    } catch (err) {
      console.warn('复制 mermaid 代码失败', err);
      setCopied(false);
    }
  }, [mermaidCode]);

  return (
    <div className="mindmap mindmap-diagram">
      <div className="mindmap-diagram__toolbar">
        <span>知识树 · Mermaid 渲染</span>
        <button type="button" onClick={handleCopy} disabled={!mermaidCode}>
          {copied ? '已复制' : '复制代码'}
        </button>
      </div>
      {error && <p className="mindmap-diagram__error">渲染失败：{error}</p>}
      <div className="mindmap-diagram__canvas" aria-live="polite">
        {svgMarkup ? (
          <div
            className="mindmap-diagram__svg"
            dangerouslySetInnerHTML={{ __html: svgMarkup }}
          />
        ) : (
          <p>暂无知识树内容。</p>
        )}
      </div>
      <details className="mindmap-diagram__code">
        <summary>Mermaid 代码</summary>
        <pre>
          <code>{mermaidCode}</code>
        </pre>
      </details>
    </div>
  );
};

const buildMermaidCode = (graph: MindmapGraph): string => {
  if (!graph?.nodes?.length) {
    return '';
  }

  const nodeIndex = new Map<string, number>();
  const nodeMap = new Map<string, MindmapGraph['nodes'][number]>();
  graph.nodes.forEach((node, index) => {
    nodeIndex.set(node.id, index);
    nodeMap.set(node.id, node);
  });

  const children = new Map<string, MindmapGraph['nodes'][number][]>();
  graph.edges.forEach((edge) => {
    const parent = nodeMap.get(edge.from);
    const child = nodeMap.get(edge.to);
    if (!parent || !child) return;
    const bucket = children.get(edge.from) ?? [];
    bucket.push(child);
    children.set(edge.from, bucket);
  });
  children.forEach((bucket) => bucket.sort((a, b) => (nodeIndex.get(a.id) ?? 0) - (nodeIndex.get(b.id) ?? 0)));

  const targets = new Set(graph.edges.map((edge) => edge.to));
  const roots = graph.nodes.filter((node) => !targets.has(node.id));
  roots.sort((a, b) => (nodeIndex.get(a.id) ?? 0) - (nodeIndex.get(b.id) ?? 0));
  const traversalRoots = roots.length ? roots : [graph.nodes[0]];

  const lines = ['mindmap'];
  const visited = new Set<string>();

  const walk = (node: MindmapGraph['nodes'][number], depth: number) => {
    if (!node || visited.has(node.id)) return;
    visited.add(node.id);
    const indent = '  '.repeat(depth + 1);
    lines.push(`${indent}${formatLabel(node.label ?? node.id)}`);
    const childrenNodes = children.get(node.id);
    childrenNodes?.forEach((child) => walk(child, depth + 1));
  };

  traversalRoots.forEach((root) => walk(root, 0));

  if (visited.size < graph.nodes.length) {
    graph.nodes.forEach((node) => {
      if (!visited.has(node.id)) {
        walk(node, 0);
      }
    });
  }

  return lines.join('\n');
};

const formatLabel = (label: string) => {
  const normalized = label.replace(/\s+/g, ' ').trim();
  return normalized || '未命名节点';
};

export default MindmapDiagram;
