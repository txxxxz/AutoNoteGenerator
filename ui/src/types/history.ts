export type DetailLevel = 'brief' | 'medium' | 'detailed';
export type ExpressionLevel = 'popular' | 'standard' | 'insightful';

export type HistoryEntry = {
  id: string;
  detailLevel: DetailLevel;
  difficulty: ExpressionLevel;
  timestamp: string;
};
