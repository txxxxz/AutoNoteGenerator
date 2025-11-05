import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import classNames from 'classnames';

import { NoteSection } from '../../api/types';
import '../../styles/note-section.css';

type NoteSectionViewProps = {
  section: NoteSection;
  pending?: boolean;
  onRegenerate?: (sectionId: string) => void;
};

const NoteSectionView = ({ section, pending, onRegenerate }: NoteSectionViewProps) => {
  return (
    <section className={classNames('note-section', { pending })} data-section-id={section.section_id}>
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
      <article className="note-section__body">
        {pending ? (
          <div className="note-section__skeleton" aria-live="polite">
            正在重新生成...
          </div>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.body_md}</ReactMarkdown>
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
