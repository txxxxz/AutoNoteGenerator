import { KeyboardEvent, MouseEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

import FileUploader from '../components/FileUploader';
import ProgressBar from '../components/ProgressBar';
import {
  buildLayout,
  buildOutline,
  deleteSession,
  listSessions,
  parseFile,
  uploadFile
} from '../api/routes';
import { SessionSummary } from '../api/types';
import { useSessionState } from '../hooks/useSessionState';
import { debug } from '../api/debug';
import '../styles/dashboard.css';

const DashboardPage = () => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [uploadState, setUploadState] = useState<'idle' | 'uploading' | 'parsing' | 'layout' | 'outline'>('idle');
  const [progressMessage, setProgressMessage] = useState('');
  const [deletingMap, setDeletingMap] = useState<Record<string, boolean>>({});

  const refreshSessions = async () => {
    setLoadingSessions(true);
    try {
      const data = await listSessions();
      setSessions(data);
    } catch (error) {
      debug.error('加载会话列表失败', error);
    }
    setLoadingSessions(false);
  };

  useEffect(() => {
    void refreshSessions();
  }, []);

  const handleUpload = async (file: File) => {
    try {
      setUploadState('uploading');
      setProgressMessage('上传中…');
      const { session_id, file_id } = await uploadFile(file);
      debug.info('上传完成', { session_id, file_id });
      useSessionState.getState().initialiseSession(session_id);
      const fileType = file.name.toLowerCase().endsWith('.pptx') ? 'pptx' : 'pdf';
      setUploadState('parsing');
      setProgressMessage('解析课件中…');
      await parseFile(session_id, file_id, fileType);
      debug.info('解析完成', { session_id, file_id });
      setUploadState('layout');
      setProgressMessage('页面还原中…');
      await buildLayout(session_id, file_id);
      debug.info('页面还原完成', { session_id });
      setUploadState('outline');
      setProgressMessage('大纲生成中…');
      await buildOutline(session_id);
      debug.info('大纲生成完成', { session_id });
      await refreshSessions();
      navigate(`/session/${session_id}`);
    } catch (error) {
      const message = axios.isAxiosError(error)
        ? error.response?.data?.detail ?? error.message
        : error instanceof Error
          ? error.message
          : '处理失败';
      setProgressMessage(message);
      debug.error('上传流程失败', message, error);
      throw new Error(message);
    } finally {
      setUploadState('idle');
    }
  };

  const handleSessionNavigate = (sessionId: string) => {
    navigate(`/session/${sessionId}`);
  };

  const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>, sessionId: string) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleSessionNavigate(sessionId);
    }
  };

  const handleDeleteSession = async (event: MouseEvent<HTMLButtonElement>, session: SessionSummary) => {
    event.stopPropagation();
    if (deletingMap[session.id]) {
      return;
    }
    const confirmed = window.confirm(`确认删除“${session.title}”吗？该操作不可恢复。`);
    if (!confirmed) {
      return;
    }
    setDeletingMap((prev) => ({ ...prev, [session.id]: true }));
    try {
      await deleteSession(session.id);
      setSessions((prev) => prev.filter((item) => item.id !== session.id));
      debug.info('会话删除成功', session.id);
    } catch (error) {
      const message = axios.isAxiosError(error)
        ? error.response?.data?.detail ?? error.message
        : error instanceof Error
          ? error.message
          : '删除失败';
      window.alert(message);
      debug.error('删除会话失败', message, error);
    } finally {
      setDeletingMap((prev) => {
        const next = { ...prev };
        delete next[session.id];
        return next;
      });
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard__header">
        <div>
          <h1>StudyCompanion</h1>
          <p>上传课件，生成多形态学习资料。</p>
        </div>
        <div className="dashboard__uploader">
          <FileUploader onUpload={handleUpload} />
          {uploadState !== 'idle' && (
            <div className="dashboard__progress">
              <ProgressBar
                segments={[{ label: '', value: 100 }]}
                indeterminate
              />
              <span>{progressMessage}</span>
            </div>
          )}
        </div>
      </header>
      <section className="dashboard__list" aria-live="polite">
        <h2>最近会话</h2>
        {loadingSessions ? (
          <p>加载中…</p>
        ) : sessions.length ? (
          <div className="session-grid">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="session-card"
                role="button"
                tabIndex={0}
                onClick={() => handleSessionNavigate(session.id)}
                onKeyDown={(event) => handleCardKeyDown(event, session.id)}
                aria-label={`打开会话 ${session.title}`}
              >
                <div className="session-card__header">
                  <h3>{session.title}</h3>
                  <button
                    type="button"
                    className="session-card__delete"
                    onClick={(event) => handleDeleteSession(event, session)}
                    disabled={Boolean(deletingMap[session.id])}
                    aria-label={`删除会话 ${session.title}`}
                  >
                    {deletingMap[session.id] ? '删除中…' : '删除'}
                  </button>
                </div>
                <p>状态：{session.status}</p>
                <span>{new Date(session.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="dashboard__empty">
            <p>尚无学习会话，上传 PPT 或 PDF 后即可开始。</p>
          </div>
        )}
      </section>
    </div>
  );
};

export default DashboardPage;
