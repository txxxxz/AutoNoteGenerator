import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  askQuestion,
  exportArtifact,
  fetchCards,
  fetchMindmap,
  fetchMock,
  fetchNoteDoc,
  generateCards,
  generateMindmap,
  generateMock,
  generateNotes,
  getSessionDetail
} from '../../api/routes';
import { KnowledgeCards, MindmapGraph, MockPaper, NoteDoc, SessionDetail } from '../../api/types';
import ContentSection from '../../components/ContentBlock/NoteSectionView';
import ExportModal from '../../components/ExportModal';
import HistoryBar from '../../components/HistoryBar';
import QaDrawer from '../../components/QaDrawer';
import QaFab from '../../components/QaFab';
import StylePanel from '../../components/StylePanel';
import TemplateSelector from '../../components/TemplateSelector';
import TocTree from '../../components/TocTree';
import { useScrollSync } from '../../hooks/useScrollSync';
import { useSectionRegen } from '../../hooks/useSectionRegen';
import { useSessionState } from '../../hooks/useSessionState';
import { DetailLevel, ExpressionLevel, HistoryEntry } from '../../types/history';
import '../../styles/workspace.css';

const expressionToDifficulty: Record<ExpressionLevel, 'simple' | 'explanatory' | 'academic'> = {
  popular: 'simple',
  standard: 'explanatory',
  insightful: 'academic'
};

const difficultyToExpression: Record<'simple' | 'explanatory' | 'academic', ExpressionLevel> = {
  simple: 'popular',
  explanatory: 'standard',
  academic: 'insightful'
};

const SessionWorkspacePage = () => {
  const { sessionId = '' } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<'notes' | 'cards' | 'mock' | 'mindmap'>('notes');
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('medium');
  const [expressionLevel, setExpressionLevel] = useState<ExpressionLevel>('standard');
  const [templates, setTemplates] = useState<{ notes: boolean; cards: boolean; mock: boolean; mindmap: boolean }>({
    notes: true,
    cards: false,
    mock: false,
    mindmap: false
  });
  const [exportOpen, setExportOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const session = useSessionState((state) => state.sessions[sessionId]);
  const setSummary = useSessionState((state) => state.setSummary);
  const setNote = useSessionState((state) => state.setNote);
  const setCards = useSessionState((state) => state.setCards);
  const setMock = useSessionState((state) => state.setMock);
  const setMindmap = useSessionState((state) => state.setMindmap);
  const setOutlineId = useSessionState((state) => state.setOutlineId);
  const setGenerationState = useSessionState((state) => state.setGenerationState);
  const initialiseSession = useSessionState((state) => state.initialiseSession);
  const { pendingSection, startRegen, finishRegen } = useSectionRegen();

  useEffect(() => {
    if (!sessionId) return;
    initialiseSession(sessionId);
    const load = async () => {
      try {
        const detail: SessionDetail = await getSessionDetail(sessionId);
        setSummary(sessionId, detail);
        const latestNoteId = detail.note_doc_ids.at(-1);
        if (latestNoteId) {
          const noteDoc = await fetchNoteDoc(latestNoteId);
          const expression = difficultyToExpression[noteDoc.style.difficulty as keyof typeof difficultyToExpression];
          setNote(
            sessionId,
            latestNoteId,
            noteDoc,
            noteDoc.style.detail_level as DetailLevel,
            expression
          );
          setDetailLevel(noteDoc.style.detail_level as DetailLevel);
          setExpressionLevel(expression);
        }
        const latestCards = detail.cards_ids.at(-1);
        if (latestCards) {
          const cardsDoc = await fetchCards(latestCards);
          setCards(sessionId, latestCards, cardsDoc);
        }
        const latestMock = detail.mock_ids.at(-1);
        if (latestMock) {
          const mockDoc = await fetchMock(latestMock);
          setMock(sessionId, latestMock, mockDoc);
        }
        const latestMindmap = detail.mindmap_ids.at(-1);
        if (latestMindmap) {
          const mindmap = await fetchMindmap(latestMindmap);
          setMindmap(sessionId, latestMindmap, mindmap);
        }
      } catch (error) {
        setMessage(error instanceof Error ? error.message : '加载会话失败');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [sessionId]);

  const noteDoc: NoteDoc | undefined = session?.noteDoc;
  const cards: KnowledgeCards | undefined = session?.cards;
  const mock: MockPaper | undefined = session?.mock;
  const mindmap: MindmapGraph | undefined = session?.mindmap;

  const tocItems = useMemo(() => {
    if (!noteDoc) return [];
    return noteDoc.sections.map((section, index) => ({
      id: section.section_id,
      title: `${index + 1}. ${section.title}`,
      level: 1
    }));
  }, [noteDoc]);

  const { activeId, setActiveId } = useScrollSync(tocItems.map((item) => item.id));

  const handleGenerate = async () => {
    if (!sessionId) return;
    setMessage(null);
    setGenerationState(sessionId, { generating: true, progressLabel: '生成中…' });
    try {
      const { note_doc_id, note_doc } = await generateNotes(
        sessionId,
        `outline_${sessionId}`,
        detailLevel,
        expressionToDifficulty[expressionLevel]
      );
      setNote(sessionId, note_doc_id, note_doc, detailLevel, expressionLevel);
      if (templates.cards) {
        const { cards_id, cards: cardsDoc } = await generateCards(sessionId, note_doc_id);
        setCards(sessionId, cards_id, cardsDoc);
      }
      if (templates.mock) {
        const { paper_id, paper } = await generateMock(sessionId, note_doc_id, 'full', 10, 'mid');
        setMock(sessionId, paper_id, paper);
      }
      if (templates.mindmap) {
        const { graph_id, graph } = await generateMindmap(sessionId, `outline_${sessionId}`);
        setMindmap(sessionId, graph_id, graph);
      }
      setMessage('生成完成。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '生成失败');
    } finally {
      setGenerationState(sessionId, { generating: false, progressLabel: undefined });
      finishRegen();
    }
  };

  const handleRegenSection = async (sectionId: string) => {
    if (!sessionId) return;
    startRegen(sectionId);
    await handleGenerate();
  };

  const handleRevert = async (noteId: string) => {
    if (!sessionId) return;
    try {
      const noteDoc = await fetchNoteDoc(noteId);
      const expression = difficultyToExpression[noteDoc.style.difficulty as keyof typeof difficultyToExpression];
      setNote(
        sessionId,
        noteId,
        noteDoc,
        noteDoc.style.detail_level as DetailLevel,
        expression
      );
      setDetailLevel(noteDoc.style.detail_level as DetailLevel);
      setExpressionLevel(expression);
      setMessage('已回退到所选版本。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '回退失败');
    }
  };

  const handleExport = async (type: 'notes' | 'cards' | 'mock' | 'mindmap', format: 'md' | 'pdf' | 'png') => {
    if (!sessionId || !session) return;
    const targetMap: Record<typeof type, string | undefined> = {
      notes: session.noteDocId,
      cards: session.cardsId,
      mock: session.mockId,
      mindmap: session.mindmapId
    };
    const targetId = targetMap[type];
    if (!targetId) {
      throw new Error('该类型尚未生成');
    }
    const result = await exportArtifact(sessionId, targetId, type, format);
    window.open(result.download_url, '_blank');
  };

  const handleAsk = async (scope: 'notes' | 'cards' | 'mock', question: string) => {
    const response = await askQuestion(sessionId, scope, question);
    return response;
  };

  useEffect(() => {
    if (!session) return;
    const outlineIds = session.summary?.available_artifacts?.outline;
    if (outlineIds && outlineIds.length) {
      const latest = outlineIds[outlineIds.length - 1];
      if (latest) {
        setOutlineId(sessionId, latest);
      }
    }
  }, [session]);

  if (!sessionId) {
    return (
      <div className="workspace__missing">
        <p>未找到会话，请返回首页。</p>
        <button onClick={() => navigate('/')}>返回</button>
      </div>
    );
  }

  if (loading && !session?.summary) {
    return (
      <div className="workspace__loading">
        <p>加载工作台中…</p>
      </div>
    );
  }

  const historyItems: HistoryEntry[] = session?.noteHistory ?? [];

  return (
    <div className="workspace">
      <header className="workspace__top">
        <div>
          <button className="workspace__back" onClick={() => navigate('/')}>返回仪表盘</button>
          <h1>{session?.summary?.title ?? '学习会话'}</h1>
          <p className="workspace__status">当前状态：{session?.summary?.status ?? '就绪'}</p>
        </div>
        <div className="workspace__actions">
          <button className="primary" onClick={handleGenerate} disabled={session?.generating}>生成</button>
          <button onClick={() => setExportOpen(true)}>导出</button>
        </div>
      </header>
      {message && <div className="workspace__message">{message}</div>}
      <main className="workspace__body">
        <aside className="workspace__toc">
          <div className="workspace__search">
            <input
              type="text"
              placeholder="搜索章节…"
              aria-label="搜索章节"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </div>
          <TocTree
            items={tocItems}
            activeId={activeId}
            searchTerm={searchTerm}
            onSelect={(id) => {
              setActiveId(id);
              const elem = document.querySelector(`[data-section-id="${id}"]`);
              if (elem) {
                elem.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
            }}
          />
        </aside>
        <section className="workspace__content" aria-live="polite">
          <div className="workspace__view-tabs">
            {['notes', 'cards', 'mock', 'mindmap'].map((tab) => (
              <button key={tab} className={view === tab ? 'active' : ''} onClick={() => setView(tab as typeof view)}>
                {tab === 'notes' && '笔记'}
                {tab === 'cards' && '知识卡'}
                {tab === 'mock' && '模拟试题'}
                {tab === 'mindmap' && '知识树'}
              </button>
            ))}
          </div>
          {view === 'notes' && noteDoc ? (
            noteDoc.sections.map((section) => (
              <ContentSection
                key={section.section_id}
                section={section}
                pending={pendingSection === section.section_id || session?.generating}
                onRegenerate={handleRegenSection}
              />
            ))
          ) : null}
          {view === 'cards' && cards ? (
            <div className="cards-grid">
              {cards.cards.map((card) => (
                <article key={card.concept} className="card-item">
                  <h3>{card.concept}</h3>
                  <p>{card.definition}</p>
                  <div>
                    <strong>考点：</strong>
                    <ul>
                      {card.exam_points.map((point) => (
                        <li key={point}>{point}</li>
                      ))}
                    </ul>
                  </div>
                  {card.example_q && (
                    <details>
                      <summary>例题</summary>
                      <p>Q: {card.example_q.stem}</p>
                      <p>A: {card.example_q.answer}</p>
                    </details>
                  )}
                </article>
              ))}
            </div>
          ) : view === 'cards' ? (
            <p>尚未生成知识卡片，请在右侧勾选模板并点击生成。</p>
          ) : null}
          {view === 'mock' && mock ? (
            <div className="mock-paper">
              <header>
                <h2>模拟试卷</h2>
                <span>
                  模式：{mock.meta.mode === 'full' ? '整卷' : '章节'}｜难度：{mock.meta.difficulty}
                </span>
              </header>
              <ol>
                {mock.items.map((item) => (
                  <li key={item.id}>
                    <h3>{item.stem}</h3>
                    {item.options && (
                      <ul>
                        {item.options.map((opt) => (
                          <li key={opt}>{opt}</li>
                        ))}
                      </ul>
                    )}
                    <details>
                      <summary>查看答案/解析</summary>
                      <p>答案：{item.answer}</p>
                      {item.explain && <p>解析：{item.explain}</p>}
                      {item.key_points && <p>得分点：{item.key_points.join('、')}</p>}
                    </details>
                  </li>
                ))}
              </ol>
            </div>
          ) : view === 'mock' ? (
            <p>尚未生成模拟试题。</p>
          ) : null}
          {view === 'mindmap' && mindmap ? (
            <div className="mindmap">
              <ul>
                {mindmap.nodes.map((node) => (
                  <li key={node.id} style={{ marginLeft: `${node.level * 24}px` }}>
                    {node.label}
                  </li>
                ))}
              </ul>
            </div>
          ) : view === 'mindmap' ? (
            <p>尚未生成思维导图。</p>
          ) : null}
          {!noteDoc && view === 'notes' && <p>尚未生成笔记，点击右上角“生成”。</p>}
        </section>
        <aside className="workspace__panel">
          <StylePanel
            detailLevel={detailLevel}
            expressionLevel={expressionLevel}
            disabled={session?.generating}
            onChange={({ detailLevel: d, expressionLevel: e }) => {
              setDetailLevel(d);
              setExpressionLevel(e);
            }}
          />
          <TemplateSelector
            values={templates}
            disabled={session?.generating}
            onChange={(values) => setTemplates(values)}
          />
          <HistoryBar items={historyItems} onRevert={handleRevert} />
        </aside>
      </main>
      <QaFab onClick={() => setDrawerOpen(true)} />
      <QaDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onAsk={handleAsk} />
      <ExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        onExport={handleExport}
        available={{
          notes: Boolean(session?.noteDocId),
          cards: Boolean(session?.cardsId),
          mock: Boolean(session?.mockId),
          mindmap: Boolean(session?.mindmapId)
        }}
      />
    </div>
  );
};

export default SessionWorkspacePage;
