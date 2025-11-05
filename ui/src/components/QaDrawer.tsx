import { FormEvent, useState } from 'react';

import { QAResponse } from '../api/types';
import '../styles/qa.css';

type QaDrawerProps = {
  open: boolean;
  onClose: () => void;
  onAsk: (mode: 'notes' | 'cards' | 'mock', question: string) => Promise<QAResponse>;
};

const QaDrawer = ({ open, onClose, onAsk }: QaDrawerProps) => {
  const [tab, setTab] = useState<'explain' | 'quiz'>('explain');
  const [scope, setScope] = useState<'notes' | 'cards' | 'mock'>('notes');
  const [question, setQuestion] = useState('');
  const [response, setResponse] = useState<QAResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [quizResult, setQuizResult] = useState<{ correct: number; total: number } | null>(null);

  if (!open) return null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setQuizResult(null);
    try {
      const answer = await onAsk(scope, question);
      setResponse(answer);
    } catch (error) {
      setResponse({
        answer: error instanceof Error ? error.message : '未能获取答案',
        refs: []
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <aside className="qa-drawer" aria-label="学习助手" aria-modal="true">
      <header className="qa-drawer__header">
        <div className="qa-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={tab === 'explain'}
            onClick={() => setTab('explain')}
            className={tab === 'explain' ? 'active' : ''}
          >
            Explain
          </button>
          <button
            role="tab"
            aria-selected={tab === 'quiz'}
            onClick={() => setTab('quiz')}
            className={tab === 'quiz' ? 'active' : ''}
          >
            Quiz
          </button>
        </div>
        <button onClick={onClose} aria-label="关闭问答" className="qa-close">
          ×
        </button>
      </header>
      {tab === 'explain' ? (
        <form className="qa-form" onSubmit={handleSubmit}>
          <label>
            <span>提问范围</span>
            <select value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}>
              <option value="notes">笔记</option>
              <option value="cards">知识卡片</option>
              <option value="mock">模拟试题</option>
            </select>
          </label>
          <label>
            <span>问题</span>
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} />
          </label>
          <div className="qa-actions">
            <button type="submit" disabled={loading}>
              {loading ? '思考中…' : '发送'}
            </button>
          </div>
        </form>
      ) : (
        <div className="qa-quiz">
          <p className="qa-quiz__hint">Quiz 模式将随机抽取 3-5 题供自测（前端占位）。</p>
          <button
            type="button"
            onClick={async () => {
              setLoading(true);
              await new Promise((resolve) => setTimeout(resolve, 800));
              setLoading(false);
              setQuizResult({ correct: 4, total: 5 });
            }}
          >
            生成小测
          </button>
          {quizResult && (
            <div className="qa-quiz__result">
              本次正确率 {(quizResult.correct / quizResult.total * 100).toFixed(0)}%，建议复习“核心概念”章节。
            </div>
          )}
        </div>
      )}
      <section className="qa-answer" aria-live="polite">
        {response ? (
          <div>
            <p>{response.answer}</p>
            {!!response.refs.length && (
              <ul>
                {response.refs.map((ref) => (
                  <li key={ref}>{ref}</li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <p className="qa-placeholder">等待你的问题…</p>
        )}
      </section>
    </aside>
  );
};

export default QaDrawer;
