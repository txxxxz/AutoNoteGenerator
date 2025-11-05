import { HistoryEntry } from '../types/history';
import '../styles/history-bar.css';

type HistoryBarProps = {
  items: HistoryEntry[];
  onRevert: (id: string) => void;
};

const detailLabels: Record<string, string> = {
  brief: '简略',
  medium: '中等',
  detailed: '详细'
};

const expressionLabels: Record<string, string> = {
  popular: '通俗易懂',
  standard: '讲解型',
  insightful: '学术型'
};

const HistoryBar = ({ items, onRevert }: HistoryBarProps) => (
  <section className="panel-section" aria-labelledby="history-heading">
    <header className="panel-header">
      <h3 id="history-heading">最近版本</h3>
    </header>
    <ul className="history-list">
      {items.map((item) => (
        <li key={item.id}>
          <div>
            <strong>
              {detailLabels[item.detailLevel] ?? item.detailLevel} × {expressionLabels[item.difficulty] ?? item.difficulty}
            </strong>
            <span>{new Date(item.timestamp).toLocaleString()}</span>
          </div>
          <button type="button" onClick={() => onRevert(item.id)}>
            回退
          </button>
        </li>
      ))}
      {!items.length && <li className="history-empty">暂无版本记录</li>}
    </ul>
  </section>
);

export default HistoryBar;
