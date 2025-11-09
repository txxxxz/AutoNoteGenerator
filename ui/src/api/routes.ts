import client from './client';
import { debug } from './debug';
import {
  CardsPayload,
  KnowledgeCards,
  LayoutDoc,
  NoteTaskResponse,
  NoteTaskStatus,
  MindmapGraph,
  MockPaper,
  NoteDoc,
  OutlineTree,
  ParseResponse,
  QAResponse,
  SessionDetail,
  SessionSummary,
  ExportResponse,
  DeleteSessionResponse
} from './types';

export const uploadFile = async (file: File, title?: string) => {
  debug.info('准备上传文件', file.name, file.size / 1024 / 1024, 'MB');
  const formData = new FormData();
  formData.append('file', file);
  if (title) {
    formData.append('title', title);
  }
  const response = await client.post('/files', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data as { file_id: string; session_id: string };
};

export const parseFile = async (sessionId: string, fileId: string, fileType: 'pptx' | 'pdf') => {
  debug.info('请求解析文件', sessionId, fileId, fileType);
  const response = await client.post('/parse', {
    session_id: sessionId,
    file_id: fileId,
    file_type: fileType
  });
  return response.data as ParseResponse;
};

export const buildLayout = async (sessionId: string, fileId: string) => {
  debug.info('请求版式还原', sessionId, fileId);
  const response = await client.post('/layout/build', {
    session_id: sessionId,
    file_id: fileId
  });
  return response.data as LayoutDoc;
};

export const buildOutline = async (sessionId: string) => {
  debug.info('请求生成大纲', sessionId);
  const response = await client.post('/outline/build', {
    session_id: sessionId
  });
  return response.data as OutlineTree;
};

export const generateNotes = async (
  sessionId: string,
  outlineTreeId: string,
  detailLevel: string,
  difficulty: string
) => {
  const response = await client.post('/notes/generate', {
    session_id: sessionId,
    outline_tree_id: outlineTreeId,
    style: {
      detail_level: detailLevel,
      difficulty
    }
  });
  return response.data as NoteTaskResponse;
};

export const getNoteTaskStatus = async (taskId: string) => {
  const response = await client.get(`/notes/tasks/${taskId}`);
  return response.data as NoteTaskStatus;
};

export const openNoteTaskStream = (taskId: string) =>
  new EventSource(`/api/v1/notes/tasks/${taskId}/stream`);

export const generateCards = async (sessionId: string, noteDocId: string) => {
  const response = await client.post('/cards/generate', {
    session_id: sessionId,
    note_doc_id: noteDocId
  });
  return response.data as { cards_id: string; cards: KnowledgeCards };
};

export const generateMock = async (
  sessionId: string,
  noteDocId: string,
  mode: 'chapter' | 'full',
  size: number,
  difficulty: 'low' | 'mid' | 'high'
) => {
  const response = await client.post('/mock/generate', {
    session_id: sessionId,
    note_doc_id: noteDocId,
    options: { mode, size, difficulty }
  });
  return response.data as { paper_id: string; paper: MockPaper };
};

export const generateMindmap = async (sessionId: string, outlineTreeId: string) => {
  const response = await client.post('/mindmap/generate', {
    session_id: sessionId,
    outline_tree_id: outlineTreeId
  });
  return response.data as { graph_id: string; graph: MindmapGraph };
};

export const exportArtifact = async (
  sessionId: string,
  targetId: string,
  type: 'notes' | 'cards' | 'mock' | 'mindmap',
  format: 'md' | 'pdf' | 'png'
) => {
  const response = await client.post('/export', {
    session_id: sessionId,
    target_id: targetId,
    type,
    format
  });
  return response.data as ExportResponse;
};

export const askQuestion = async (sessionId: string, scope: 'notes' | 'cards' | 'mock', question: string) => {
  const response = await client.post('/qa/ask', {
    session_id: sessionId,
    scope,
    question
  });
  return response.data as QAResponse;
};

export const listSessions = async () => {
  debug.info('请求会话列表');
  const response = await client.get('/sessions');
  return response.data.sessions as SessionSummary[];
};

export const getSessionDetail = async (sessionId: string) => {
  debug.info('请求会话详情', sessionId);
  const response = await client.get(`/sessions/${sessionId}`);
  return response.data as SessionDetail;
};

export const fetchNoteDoc = async (noteDocId: string) => {
  const response = await client.get(`/notes/${noteDocId}`);
  return response.data as NoteDoc;
};

export const fetchCards = async (cardsId: string) => {
  const response = await client.get(`/cards/${cardsId}`);
  return response.data as KnowledgeCards;
};

export const fetchMock = async (mockId: string) => {
  const response = await client.get(`/mock/${mockId}`);
  return response.data as MockPaper;
};

export const fetchMindmap = async (graphId: string) => {
  const response = await client.get(`/mindmap/${graphId}`);
  return response.data as MindmapGraph;
};

export const deleteSession = async (sessionId: string) => {
  const response = await client.delete(`/sessions/${sessionId}`);
  return response.data as DeleteSessionResponse;
};
