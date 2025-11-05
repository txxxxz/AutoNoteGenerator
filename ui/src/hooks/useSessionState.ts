import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

import {
  KnowledgeCards,
  MindmapGraph,
  MockPaper,
  NoteDoc,
  SessionDetail
} from '../api/types';
import { DetailLevel, ExpressionLevel, HistoryEntry } from '../types/history';
import { debug } from '../api/debug';

type SessionData = {
  summary?: SessionDetail;
  noteDocId?: string;
  noteDoc?: NoteDoc;
  noteHistory: HistoryEntry[];
  cardsId?: string;
  cards?: KnowledgeCards;
  mockId?: string;
  mock?: MockPaper;
  mindmapId?: string;
  mindmap?: MindmapGraph;
  outlineId?: string;
  layoutReady?: boolean;
  generating?: boolean;
  uploading?: boolean;
  progressLabel?: string;
  progressValue?: number;
  taskId?: string;
  currentSection?: string;
};

type SessionStore = {
  sessions: Record<string, SessionData>;
  initialiseSession: (sessionId: string) => void;
  setSummary: (sessionId: string, summary: SessionDetail) => void;
  setNote: (
    sessionId: string,
    noteDocId: string,
    noteDoc: NoteDoc,
    detailLevel: DetailLevel,
    difficulty: ExpressionLevel
  ) => void;
  setCards: (sessionId: string, cardsId: string, cards: KnowledgeCards) => void;
  setMock: (sessionId: string, mockId: string, mock: MockPaper) => void;
  setMindmap: (sessionId: string, mindmapId: string, mindmap: MindmapGraph) => void;
  setOutlineId: (sessionId: string, outlineId: string) => void;
  setGenerationState: (sessionId: string, state: Partial<SessionData>) => void;
};

export const useSessionState = create<SessionStore>()(
  immer((set) => ({
    sessions: {},
    initialiseSession: (sessionId) => {
      set((draft) => {
        if (!draft.sessions[sessionId]) {
          draft.sessions[sessionId] = { noteHistory: [] };
        }
      });
    },
    setSummary: (sessionId, summary) => {
      set((draft) => {
        draft.sessions[sessionId] = draft.sessions[sessionId] || { noteHistory: [] };
        draft.sessions[sessionId].summary = summary;
      });
    },
    setNote: (sessionId, noteDocId, noteDoc, detailLevel, difficulty) => {
      set((draft) => {
        draft.sessions[sessionId] = draft.sessions[sessionId] || { noteHistory: [] };
        const session = draft.sessions[sessionId];
        session.noteDocId = noteDocId;
        session.noteDoc = noteDoc;
        session.noteHistory = session.noteHistory.filter((entry) => entry.id !== noteDocId);
        session.noteHistory.unshift({
          id: noteDocId,
          detailLevel,
          difficulty,
          timestamp: new Date().toISOString()
        });
        session.noteHistory = session.noteHistory.slice(0, 3);
        debug.info('更新笔记状态', sessionId, noteDocId, detailLevel, difficulty);
      });
    },
    setCards: (sessionId, cardsId, cards) => {
      set((draft) => {
        draft.sessions[sessionId] = draft.sessions[sessionId] || { noteHistory: [] };
        draft.sessions[sessionId].cardsId = cardsId;
        draft.sessions[sessionId].cards = cards;
      });
    },
    setMock: (sessionId, mockId, mock) => {
      set((draft) => {
        draft.sessions[sessionId] = draft.sessions[sessionId] || { noteHistory: [] };
        draft.sessions[sessionId].mockId = mockId;
        draft.sessions[sessionId].mock = mock;
      });
    },
    setMindmap: (sessionId, mindmapId, mindmap) => {
      set((draft) => {
        draft.sessions[sessionId] = draft.sessions[sessionId] || { noteHistory: [] };
        draft.sessions[sessionId].mindmapId = mindmapId;
        draft.sessions[sessionId].mindmap = mindmap;
      });
    },
    setOutlineId: (sessionId, outlineId) => {
      set((draft) => {
        draft.sessions[sessionId] = draft.sessions[sessionId] || { noteHistory: [] };
        draft.sessions[sessionId].outlineId = outlineId;
      });
    },
    setGenerationState: (sessionId, state) => {
      set((draft) => {
        draft.sessions[sessionId] = draft.sessions[sessionId] || { noteHistory: [] };
        Object.assign(draft.sessions[sessionId], state);
      });
    }
  }))
);

export const getSessionData = (sessionId: string) =>
  useSessionState.getState().sessions[sessionId];
