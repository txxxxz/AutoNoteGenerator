export type NoteLanguage = 'zh' | 'en';

export interface SlideBlock {
  id: string;
  type: 'title' | 'text' | 'image' | 'formula' | 'table';
  order: number;
  bbox?: number[];
  raw_text?: string;
  asset_uri?: string;
  latex?: string;
}

export interface SlidePage {
  page_no: number;
  blocks: SlideBlock[];
}

export interface ParseResponse {
  doc_meta: { title: string; pages: number };
  slides: SlidePage[];
}

export interface LayoutElement {
  ref: string;
  kind: 'title' | 'text' | 'image' | 'formula' | 'table';
  content?: string;
  image_uri?: string;
  latex?: string;
  caption?: string;
}

export interface LayoutPage {
  page_no: number;
  elements: LayoutElement[];
}

export interface LayoutDoc {
  pages: LayoutPage[];
}

export interface AnchorRef {
  page: number;
  ref: string;
}

export interface OutlineNode {
  section_id: string;
  title: string;
  summary: string;
  anchors: AnchorRef[];
  children: OutlineNode[];
  level: number;
}

export interface OutlineTree {
  root: OutlineNode;
  markdown?: string;
}

export interface NoteFigure {
  image_uri: string;
  caption: string;
}

export interface NoteEquation {
  latex: string;
  caption: string;
}

export interface NoteSection {
  section_id: string;
  title: string;
  body_md: string;
  figures: NoteFigure[];
  equations: NoteEquation[];
  refs: string[];
}

export interface NoteDoc {
  style: { detail_level: string; difficulty: string; language?: NoteLanguage };
  toc: { section_id: string; title: string }[];
  sections: NoteSection[];
}

export interface NoteTaskResponse {
  task_id: string;
}

export type NoteTaskState = 'queued' | 'running' | 'completed' | 'failed';

export interface NoteTaskStatus {
  task_id: string;
  session_id: string;
  status: NoteTaskState;
  progress: number;
  detail_level: string;
  difficulty: string;
  language: NoteLanguage;
  total_sections: number;
  current_section?: string | null;
  message?: string | null;
  note_doc_id?: string | null;
  note_doc?: NoteDoc | null;
  error?: string | null;
}

export interface CardsPayload {
  concept: string;
  definition: string;
  exam_points: string[];
  example_q?: {
    stem: string;
    answer: string;
    key_points?: string[];
  } | null;
  anchors: string[];
}

export interface KnowledgeCards {
  cards: CardsPayload[];
}

export interface MockQuestion {
  id: string;
  type: 'mcq' | 'fill' | 'short';
  stem: string;
  options?: string[];
  answer: string;
  explain?: string | null;
  key_points?: string[] | null;
  refs: string[];
}

export interface MockPaper {
  meta: {
    mode: 'chapter' | 'full';
    size: number;
    difficulty: 'low' | 'mid' | 'high';
  };
  items: MockQuestion[];
}

export interface MindmapGraph {
  nodes: { id: string; label: string; level: number }[];
  edges: { from: string; to: string; type: string }[];
}

export interface ExportResponse {
  download_url: string;
  filename: string;
}

export interface QAResponse {
  answer: string;
  refs: string[];
}

export interface SessionSummary {
  id: string;
  title: string;
  status: string;
  created_at: string;
  file_id: string;
  note_doc_ids: string[];
  cards_ids: string[];
  mock_ids: string[];
  mindmap_ids: string[];
}

export interface SessionDetail extends SessionSummary {
  available_artifacts: Record<string, string[]>;
}

export interface DeleteSessionResponse {
  deleted: boolean;
  session_id: string;
  released_bytes: number;
}

export type LlmProvider = 'google' | 'openai';

export interface LlmSettingsPayload {
  provider?: LlmProvider;
  api_key?: string;
  base_url?: string;
  llm_model?: string;
  embedding_model?: string;
}

export interface LlmSettingsResponse {
  provider: LlmProvider;
  api_key_present: boolean;
  api_key_preview?: string | null;
  base_url?: string | null;
  llm_model?: string | null;
  embedding_model?: string | null;
}
