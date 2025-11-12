import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  askQuestion,
  exportArtifact,
  fetchCards,
  fetchMindmap,
  fetchMock,
  fetchNoteDoc,
  fetchOutline,
  generateCards,
  generateMindmap,
  generateMock,
  generateNotes,
  getSessionDetail,
  openNoteTaskStream
} from '../../api/routes';
import {
  KnowledgeCards,
  MindmapGraph,
  MockPaper,
  NoteDoc,
  NoteTaskStatus,
  OutlineNode,
  SessionDetail
} from '../../api/types';
import ContentSection from '../../components/ContentBlock/NoteSectionView';
import ExportModal from '../../components/ExportModal';
import HistoryBar from '../../components/HistoryBar';
import QaDrawer from '../../components/QaDrawer';
import QaFab from '../../components/QaFab';
import StylePanel from '../../components/StylePanel';
import TemplateSelector from '../../components/TemplateSelector';
import TocTree, { TocItem } from '../../components/TocTree';
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
  const [noteLanguage, setNoteLanguage] = useState<'zh' | 'en'>('zh');
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
  const setOutline = useSessionState((state) => state.setOutline);
  const setGenerationState = useSessionState((state) => state.setGenerationState);
  const initialiseSession = useSessionState((state) => state.initialiseSession);
  const { pendingSection, startRegen, finishRegen } = useSectionRegen();
  const taskSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    initialiseSession(sessionId);
    const load = async () => {
      try {
        const detail: SessionDetail = await getSessionDetail(sessionId);
        setSummary(sessionId, detail);
        
        // 加载 outline
        const outlineIds = detail.available_artifacts?.outline;
        if (outlineIds && outlineIds.length > 0) {
          const latestOutlineId = outlineIds[outlineIds.length - 1];
          try {
            const outlineDoc = await fetchOutline(latestOutlineId);
            setOutline(sessionId, latestOutlineId, outlineDoc);
          } catch (error) {
            console.warn('加载 outline 失败:', error);
          }
        }
        
        if (detail.note_doc_ids.length > 0) {
          const latestNoteId = detail.note_doc_ids[detail.note_doc_ids.length - 1];
          const noteDoc = await fetchNoteDoc(latestNoteId);
          const expression = difficultyToExpression[noteDoc.style.difficulty as keyof typeof difficultyToExpression];
          const language = (noteDoc.style.language as 'zh' | 'en') === 'en' ? 'en' : 'zh';
          setNote(
            sessionId,
            latestNoteId,
            noteDoc,
            noteDoc.style.detail_level as DetailLevel,
            expression,
            language
          );
          setDetailLevel(noteDoc.style.detail_level as DetailLevel);
          setExpressionLevel(expression);
          setNoteLanguage(language);
        }
        if (detail.cards_ids.length > 0) {
          const latestCards = detail.cards_ids[detail.cards_ids.length - 1];
          const cardsDoc = await fetchCards(latestCards);
          setCards(sessionId, latestCards, cardsDoc);
        }
        if (detail.mock_ids.length > 0) {
          const latestMock = detail.mock_ids[detail.mock_ids.length - 1];
          const mockDoc = await fetchMock(latestMock);
          setMock(sessionId, latestMock, mockDoc);
        }
        if (detail.mindmap_ids.length > 0) {
          const latestMindmap = detail.mindmap_ids[detail.mindmap_ids.length - 1];
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

  useEffect(() => {
    return () => {
      if (taskSourceRef.current) {
        taskSourceRef.current.close();
        taskSourceRef.current = null;
      }
    };
  }, []);

  const noteDoc: NoteDoc | undefined = session?.noteDoc;
  const cards: KnowledgeCards | undefined = session?.cards;
  const mock: MockPaper | undefined = session?.mock;
  const mindmap: MindmapGraph | undefined = session?.mindmap;

  const tocItems = useMemo<TocItem[]>(() => {
    const outline = session?.outline;
    console.log('[DEBUG] tocItems生成:', {
      hasOutline: !!outline,
      hasRoot: !!outline?.root,
      rootChildren: outline?.root?.children,
      rootChildrenLength: outline?.root?.children?.length,
      hasNoteDoc: !!noteDoc,
      noteDocSectionsLength: noteDoc?.sections?.length
    });
    
    // 打印 outline 的前几个子节点标题
    if (outline?.root?.children?.length) {
      console.log('[DEBUG] Outline前5个章节标题:', 
        outline.root.children.slice(0, 5).map(child => ({
          title: child.title,
          level: child.level,
          section_id: child.section_id
        }))
      );
    }
    
    // 打印 noteDoc 的前几个 section 标题（如果存在）
    if (noteDoc?.sections?.length) {
      console.log('[DEBUG] NoteDoc前5个章节标题:', 
        noteDoc.sections.slice(0, 5).map(section => ({
          title: section.title,
          section_id: section.section_id
        }))
      );
    }
    
    if (outline?.root?.children?.length) {
      const items: TocItem[] = [];
      const visit = (node: OutlineNode, numbering: string) => {
        const level = Math.min(Math.max(node.level || 1, 1), 5);
        const title = `${numbering} ${node.title}`;
        items.push({
          id: node.section_id,
          title,
          level,
          targetId: node.section_id
        });
        if (node.children && node.children.length > 0) {
          node.children.forEach((child, index) => {
            visit(child, `${numbering}.${index + 1}`);
          });
        }
      };
      outline.root.children.forEach((child, index) => {
        visit(child, `${index + 1}.`);
      });
      console.log('[DEBUG] 使用outline生成tocItems (前5项):', items.slice(0, 5));
      return items;
    }
    if (!noteDoc) return [];
    const fallbackItems = noteDoc.sections.map((section, index) => ({
      id: section.section_id,
      title: `${index + 1}. ${section.title}`,
      level: 1,
      targetId: section.section_id
    }));
    console.log('[DEBUG] 使用noteDoc生成tocItems (fallback, 前5项):', fallbackItems.slice(0, 5));
    return fallbackItems;
  }, [session?.outline, noteDoc]);

  const scrollTargets = useMemo(() => {
    if (!noteDoc) return [];
    return noteDoc.sections.map((section) => section.section_id);
  }, [noteDoc]);

  const { activeId, setActiveId } = useScrollSync(scrollTargets);

  const handleTaskFailure = (errorMessage?: string | null) => {
    if (!sessionId) return;
    setGenerationState(sessionId, {
      generating: false,
      progressLabel: undefined,
      progressValue: 0,
      taskId: undefined,
      currentSection: undefined
    });
    finishRegen();
    setMessage(errorMessage ? `生成失败：${errorMessage}` : '生成失败');
  };

  const handleTaskSuccess = async (status: NoteTaskStatus) => {
    if (!sessionId) return;
      const noteDocId = status.note_doc_id;
    let notePayload = status.note_doc ?? undefined;
    try {
      if (!noteDocId) {
        throw new Error('任务完成但未返回笔记标识');
      }
      if (!notePayload) {
        notePayload = await fetchNoteDoc(noteDocId);
      }
      const detail = notePayload.style.detail_level as DetailLevel;
      const difficulty = (notePayload.style.difficulty ?? 'explanatory') as keyof typeof difficultyToExpression;
      const expression = difficultyToExpression[difficulty] ?? expressionLevel;
      const language = (notePayload.style.language as 'zh' | 'en') === 'en' ? 'en' : 'zh';
      setNote(sessionId, noteDocId, notePayload, detail, expression, language);
      setNoteLanguage(language);
      setMessage('笔记生成完成。');

      const needsExtras = templates.cards || templates.mock || templates.mindmap;
      setGenerationState(sessionId, {
        generating: needsExtras,
        progressLabel: needsExtras ? '笔记生成完成，正在生成附加内容…' : undefined,
        progressValue: 100,
        taskId: undefined,
        currentSection: undefined
      });

      if (!needsExtras) {
        finishRegen();
        return;
      }

      try {
        if (templates.cards) {
          setGenerationState(sessionId, { progressLabel: '正在生成知识卡片…' });
          const { cards_id, cards: cardsDoc } = await generateCards(sessionId, noteDocId);
          setCards(sessionId, cards_id, cardsDoc);
        }
        if (templates.mock) {
          setGenerationState(sessionId, { progressLabel: '正在生成模拟试题…' });
          const { paper_id, paper } = await generateMock(sessionId, noteDocId, 'full', 10, 'mid');
          setMock(sessionId, paper_id, paper);
        }
        if (templates.mindmap) {
          setGenerationState(sessionId, { progressLabel: '正在生成思维导图…' });
          const { graph_id, graph } = await generateMindmap(sessionId, `outline_${sessionId}`);
          setMindmap(sessionId, graph_id, graph);
        }
        setMessage('生成完成。');
      } catch (error) {
        const reason = error instanceof Error ? error.message : '附加内容生成失败';
        setMessage(reason);
      } finally {
        setGenerationState(sessionId, {
          generating: false,
          progressLabel: undefined,
          progressValue: 100,
          currentSection: undefined,
          taskId: undefined
        });
        finishRegen();
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : '笔记结果获取失败';
      handleTaskFailure(reason);
    }
  };

  const handleGenerate = async () => {
    if (!sessionId) return;
    setMessage(null);
    if (taskSourceRef.current) {
      taskSourceRef.current.close();
      taskSourceRef.current = null;
    }
    setGenerationState(sessionId, {
      generating: true,
      progressLabel: '任务排队中…',
      progressValue: 0,
      currentSection: undefined,
      taskId: undefined
    });
    try {
      const { task_id } = await generateNotes(
        sessionId,
        `outline_${sessionId}`,
        detailLevel,
        expressionToDifficulty[expressionLevel],
        noteLanguage
      );
      setGenerationState(sessionId, {
        generating: true,
        progressLabel: '任务已创建，等待执行…',
        progressValue: 0,
        currentSection: undefined,
        taskId: task_id
      });
      const source = openNoteTaskStream(task_id);
      taskSourceRef.current = source;
      source.onmessage = (event) => {
        try {
          const data: NoteTaskStatus = JSON.parse(event.data);
          const progressValue =
            typeof data.progress === 'number' && Number.isFinite(data.progress)
              ? Math.min(Math.max(data.progress, 0), 100)
              : 0;
          const label =
            data.message ??
            (data.current_section
              ? `正在处理：${data.current_section}`
              : data.status === 'queued'
              ? '任务排队中…'
              : '生成中…');
          const isActive = data.status === 'running' || data.status === 'queued';
          setGenerationState(sessionId, {
            generating: isActive,
            progressLabel: label,
            progressValue,
            currentSection: data.current_section ?? undefined,
            taskId: data.status === 'completed' || data.status === 'failed' ? undefined : task_id
          });
          if (data.status === 'completed') {
            source.close();
            taskSourceRef.current = null;
            void handleTaskSuccess(data);
          } else if (data.status === 'failed') {
            source.close();
            taskSourceRef.current = null;
            handleTaskFailure(data.error);
          }
        } catch (error) {
          source.close();
          taskSourceRef.current = null;
          handleTaskFailure('进度解析失败');
        }
      };
      source.onerror = () => {
        source.close();
        taskSourceRef.current = null;
        handleTaskFailure('进度推送中断');
      };
    } catch (error) {
      const reason = error instanceof Error ? error.message : '任务创建失败';
      handleTaskFailure(reason);
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
      const language = (noteDoc.style.language as 'zh' | 'en') === 'en' ? 'en' : 'zh';
      setNote(
        sessionId,
        noteId,
        noteDoc,
        noteDoc.style.detail_level as DetailLevel,
        expression,
        language
      );
      setDetailLevel(noteDoc.style.detail_level as DetailLevel);
      setExpressionLevel(expression);
      setNoteLanguage(language);
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
    // exportArtifact 现在会直接触发浏览器下载
    await exportArtifact(sessionId, targetId, type, format);
    setMessage(`${type} 导出成功`);
  };

  const handleAsk = async (scope: 'notes' | 'cards' | 'mock', question: string) => {
    const response = await askQuestion(sessionId, scope, question);
    return response;
  };

  useEffect(() => {
    if (!sessionId || !session?.summary) return;
    const outlineIds = session.summary.available_artifacts?.outline;
    console.log('[DEBUG] outline加载检查:', {
      sessionId,
      hasSessionSummary: !!session?.summary,
      availableArtifacts: session.summary.available_artifacts,
      outlineIds,
      currentOutlineId: session.outlineId,
      hasOutline: !!session.outline,
      outlineRoot: session.outline?.root
    });
    if (!outlineIds?.length) return;
    const latest = outlineIds[outlineIds.length - 1];
    if (!latest) return;
    if (session.outlineId !== latest) {
      setOutlineId(sessionId, latest);
    }
    if (session.outline && session.outlineId === latest) {
      return;
    }
    let cancelled = false;
    const loadOutline = async () => {
      try {
        console.log('[DEBUG] 开始加载outline:', latest);
        const outlineTree = await fetchOutline(latest);
        console.log('[DEBUG] outline加载成功:', outlineTree);
        if (!cancelled) {
          setOutline(sessionId, latest, outlineTree);
        }
      } catch (error) {
        console.error('加载大纲失败', error);
      }
    };
    void loadOutline();
    return () => {
      cancelled = true;
    };
  }, [sessionId, session?.summary, session?.outlineId, session?.outline, setOutlineId, setOutline]);

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
  const showProgress = Boolean(session?.progressLabel);
  const progressValue = Math.min(Math.max(session?.progressValue ?? 0, 0), 100);

  return (
    <div className="workspace">
      <header className="workspace__top">
        <div>
          <button className="workspace__back" onClick={() => navigate('/')}>返回仪表盘</button>
          <h1>{session?.summary?.title ?? '学习会话'}</h1>
          <p className="workspace__status">
            当前状态：{session?.summary?.status ?? '就绪'}
            {' | '}
            目录来源：{session?.outline?.root?.children?.length ? `GPT大纲(${tocItems.length}项)` : `PPT标题(${tocItems.length}项)`}
          </p>
        </div>
        <div className="workspace__actions">
          <button className="primary" onClick={handleGenerate} disabled={session?.generating}>生成</button>
          <button onClick={() => setExportOpen(true)}>导出</button>
        </div>
      </header>
      {showProgress && (
        <div className="workspace__progress" role="status">
          <div className="workspace__progress-text">{session?.progressLabel}</div>
          <progress value={progressValue} max={100} />
        </div>
      )}
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
            onSelect={(item) => {
              const targetId = item.targetId;
              setActiveId(targetId);
              const elem = document.querySelector(`[data-section-id="${targetId}"]`);
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
            language={noteLanguage}
            disabled={session?.generating}
            onChange={({ detailLevel: d, expressionLevel: e, language: lang }) => {
              setDetailLevel(d);
              setExpressionLevel(e);
               setNoteLanguage(lang);
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
