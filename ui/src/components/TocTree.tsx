import { useMemo } from 'react';
import classNames from 'classnames';

import '../styles/toc-tree.css';

export type TocItem = {
  id: string;
  title: string;
  level: number;
  targetId: string;
};

type TocTreeProps = {
  items: TocItem[];
  activeId?: string | null;
  searchTerm?: string;
  onSelect: (item: TocItem) => void;
};

const TocTree = ({ items, activeId, searchTerm = '', onSelect }: TocTreeProps) => {
  const filtered = useMemo(() => {
    if (!searchTerm.trim()) return items;
    return items.filter((item) => item.title.toLowerCase().includes(searchTerm.toLowerCase()));
  }, [items, searchTerm]);

  return (
    <nav className="toc-container" aria-label="章节导航">
      <div role="tree">
        {filtered.map((item) => (
          <button
            key={item.id}
            className={classNames('toc-item', `level-${item.level}`, { active: activeId === item.targetId })}
            role="treeitem"
            onClick={() => onSelect(item)}
          >
            {item.title}
          </button>
        ))}
      </div>
      {!filtered.length && <div className="toc-empty">未找到匹配章节</div>}
    </nav>
  );
};

export default TocTree;
