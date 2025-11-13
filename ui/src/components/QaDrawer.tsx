import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';

import { QAResponse } from '../api/types';
import '../styles/qa.css';

type QaDrawerProps = {
  open: boolean;
  onClose: () => void;
  onAsk: (mode: 'notes' | 'cards' | 'mock', question: string) => Promise<QAResponse>;
};

type QaMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  scope: 'notes' | 'cards' | 'mock';
  refs?: string[];
  status?: 'pending' | 'error' | 'done';
};

const QaDrawer = ({ open, onClose, onAsk }: QaDrawerProps) => {
  const [tab, setTab] = useState<'chat' | 'quiz'>('chat');
  const [scope, setScope] = useState<'notes' | 'cards' | 'mock'>('notes');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<QaMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [quizResult, setQuizResult] = useState<{ correct: number; total: number } | null>(null);
  const chatRef = useRef<HTMLDivElement | null>(null);

  const scopeLabels = useMemo(
    () => ({
      notes: '笔记',
      cards: '知识卡',
      mock: '模拟题'
    }),
    []
  );

  const quickPrompts = useMemo(
    () => [
      '帮我总结这一章的核心结论',
      '列出该章节最可能考的知识点',
      '解释下“关键概念”的来龙去脉',
      '基于模拟题给我一些答题建议'
    ],
    []
  );

  useEffect(() => {
    if (!open || tab !== 'chat') return;
    const el = chatRef.current;
    if (!el) return;
    el.scrollTo({
      top: el.scrollHeight,
      behavior: 'smooth'
    });
  }, [messages, open, tab]);

  const nextId = () => {
    if (typeof window !== 'undefined' && window.crypto?.randomUUID) {
      return window.crypto.randomUUID();
    }
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  };

  if (!open) return null;

  const submitQuestion = async (payload?: string) => {
    const raw = (payload ?? question).trim();
    if (!raw) return;
    if (loading) return;
    const text = raw;
    setQuestion('');
    setLoading(true);
    setQuizResult(null);
    const userMessage: QaMessage = {
      id: nextId(),
      role: 'user',
      content: text,
      scope
    };
    const pendingId = nextId();
    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: pendingId,
        role: 'assistant',
        content: '思考中…',
        scope,
        status: 'pending'
      }
    ]);
    try {
      const answer = await onAsk(scope, text);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === pendingId
            ? {
                ...msg,
                content: answer.answer,
                refs: answer.refs,
                status: 'done'
              }
            : msg
        )
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '未能获取答案，请稍后再试';
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === pendingId
            ? {
                ...msg,
                content: message,
                refs: [],
                status: 'error'
              }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event?: FormEvent) => {
    event?.preventDefault();
    void submitQuestion();
  };

  const handlePromptClick = (prompt: string) => {
    void submitQuestion(prompt);
  };

  const handleTextareaKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void submitQuestion();
    }
  };

  return (
    <aside className="qa-drawer" aria-label="学习助手" aria-modal="true" role="dialog">
      <header className="qa-drawer__header">
        <div className="qa-tabs" role="tablist" aria-label="模式切换">
          <button
            role="tab"
            aria-selected={tab === 'chat'}
            onClick={() => setTab('chat')}
            className={tab === 'chat' ? 'active' : ''}
          >
            Chat
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
      {tab === 'chat' ? (
        <>
          <div className="qa-chat__scopes" role="radiogroup" aria-label="检索范围">
            {(['notes', 'cards', 'mock'] as const).map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={scope === option}
                className={scope === option ? 'active' : ''}
                onClick={() => setScope(option)}
                disabled={loading && scope === option}
              >
                {scopeLabels[option]}
              </button>
            ))}
          </div>
          <section className="qa-chat" ref={chatRef}>
            {messages.length === 0 ? (
              <div className="qa-chat__empty">
                <p>像 ChatGPT 一样提问，让它即刻引用你生成的资料。</p>
                <div className="qa-chat__prompts">
                  {quickPrompts.map((prompt) => (
                    <button key={prompt} onClick={() => handlePromptClick(prompt)}>
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <article key={msg.id} className={`qa-message qa-message--${msg.role}`}>
                  <header>
                    <span>{msg.role === 'user' ? '你' : 'StudyCompanion'}</span>
                    <small>{scopeLabels[msg.scope]}</small>
                  </header>
                  <p>{msg.content}</p>
                  {msg.status === 'pending' && <span className="qa-message__status">检索中…</span>}
                  {!!msg.refs?.length && (
                    <ul className="qa-message__refs">
                      {msg.refs.map((ref) => (
                        <li key={ref}>{ref}</li>
                      ))}
                    </ul>
                  )}
                </article>
              ))
            )}
          </section>
          <form className="qa-input" onSubmit={handleSubmit}>
            <textarea
              rows={1}
              placeholder="像和 ChatGPT 对话一样输入，Enter 发送，Shift+Enter 换行"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleTextareaKey}
              disabled={loading}
            />
            <button type="submit" disabled={loading || !question.trim()}>
              {loading ? '…' : '发送'}
            </button>
          </form>
        </>
      ) : (
        <div className="qa-quiz">
          <div className="qa-quiz__card">
            <p className="qa-quiz__hint">Quiz 模式将随机抽取 3-5 题供自测（前端占位）。</p>
            <p className="qa-quiz__subhint">题目来自当前 session 的笔记、知识卡或模拟题。</p>
          </div>
          <button
            type="button"
            onClick={async () => {
              setLoading(true);
              await new Promise((resolve) => setTimeout(resolve, 800));
              setLoading(false);
              setQuizResult({ correct: 4, total: 5 });
            }}
            disabled={loading}
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
    </aside>
  );
};

export default QaDrawer;
