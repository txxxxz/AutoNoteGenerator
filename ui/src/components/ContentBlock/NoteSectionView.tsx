import { useEffect, useMemo, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import classNames from 'classnames';

import { NoteSection, OutlineNode } from '../../api/types';
import '../../styles/note-section.css';
import '../../styles/github-markdown.css';

type NoteSectionViewProps = {
  section: NoteSection;
  pending?: boolean;
  onRegenerate?: (sectionId: string) => void;
  outlineNode?: OutlineNode;
};

type HeadingAnchor = {
  id: string;
  level: number;
};

const clampHeadingLevel = (level?: number | null) => {
  const normalized = typeof level === 'number' && level > 0 ? level : 2;
  return Math.min(5, Math.max(2, normalized));
};

const collectHeadingAnchors = (node?: OutlineNode | null): HeadingAnchor[] => {
  if (!node) return [];
  const anchors: HeadingAnchor[] = [];
  const visit = (current: OutlineNode) => {
    anchors.push({ id: current.section_id, level: clampHeadingLevel(current.level) });
    current.children?.forEach((child) => visit(child));
  };
  visit(node);
  return anchors.slice(1); // 顶层节点使用外层 section anchor
};

const NoteSectionView = ({ section, pending, onRegenerate, outlineNode }: NoteSectionViewProps) => {
  const bodyRef = useRef<HTMLElement | null>(null);
  const headingAnchors = useMemo(() => collectHeadingAnchors(outlineNode), [outlineNode]);

  useEffect(() => {
    const container = bodyRef.current;
    if (!container || !headingAnchors.length) {
      return;
    }
    const anchorsByLevel = headingAnchors.reduce<Record<number, HeadingAnchor[]>>((acc, anchor) => {
      if (!acc[anchor.level]) {
        acc[anchor.level] = [];
      }
      acc[anchor.level].push(anchor);
      return acc;
    }, {});
    const headings = container.querySelectorAll('h2, h3, h4, h5');
    headings.forEach((heading) => {
      const level = Number(heading.tagName.replace(/\D/g, '')) || 2;
      const queue = anchorsByLevel[level];
      if (queue && queue.length) {
        const anchor = queue.shift()!;
        heading.setAttribute('id', anchor.id);
        heading.setAttribute('data-section-id', anchor.id);
      }
    });
  }, [headingAnchors, section.body_md, section.section_id]);

  return (
    <section
      className={classNames('note-section', { pending })}
      data-section-id={section.section_id}
      id={section.section_id}
    >
      <header className="note-section__header">
        <h2>{section.title}</h2>
        <div className="note-section__actions">
          <button
            type="button"
            onClick={() => onRegenerate?.(section.section_id)}
            className="note-section__regen"
          >
            重生本节
          </button>
        </div>
      </header>
      <article className="note-section__body" ref={bodyRef}>
        {pending ? (
          <div className="note-section__skeleton" aria-live="polite">
            正在重新生成...
          </div>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex, rehypeRaw]}
            skipHtml={false}
          >
            {section.body_md}
          </ReactMarkdown>
        )}
      </article>
      {!!section.figures.length && (
        <div className="note-section__figures">
          {section.figures.map((figure) => (
            <figure key={figure.image_uri}>
              <img src={figure.image_uri} alt={figure.caption} />
              <figcaption>{figure.caption}</figcaption>
            </figure>
          ))}
        </div>
      )}
      {!!section.equations.length && (
        <div className="note-section__equations">
          {section.equations.map((equation) => (
            <div key={equation.latex} className="note-equation" aria-label="公式">
              <code>{equation.latex}</code>
              <span>{equation.caption}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

export default NoteSectionView;
