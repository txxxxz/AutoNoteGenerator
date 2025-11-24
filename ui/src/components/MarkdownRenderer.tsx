import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import classNames from 'classnames';

import '../styles/github-markdown.css';

type MarkdownRendererProps = {
  content?: string | null;
  className?: string;
};

const MarkdownRenderer = ({ content, className }: MarkdownRendererProps) => {
  if (!content) {
    return null;
  }

  return (
    <ReactMarkdown
      className={classNames('note-section__body', 'markdown-snippet', className)}
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex, rehypeRaw]}
      skipHtml={false}
    >
      {content}
    </ReactMarkdown>
  );
};

export default MarkdownRenderer;
