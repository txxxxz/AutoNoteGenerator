import { useState } from 'react';

import '../styles/modal.css';

type ExportModalProps = {
  open: boolean;
  onClose: () => void;
  onExport: (type: 'notes' | 'cards' | 'mock' | 'mindmap', format: 'md' | 'pdf' | 'png') => Promise<void>;
  available: {
    notes: boolean;
    cards: boolean;
    mock: boolean;
    mindmap: boolean;
  };
};

const ExportModal = ({ open, onClose, onExport, available }: ExportModalProps) => {
  const [target, setTarget] = useState<'notes' | 'cards' | 'mock' | 'mindmap'>('notes');
  const [format, setFormat] = useState<'md' | 'pdf' | 'png'>('pdf');
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  if (!open) return null;

  const handleSubmit = async () => {
    try {
      setLoading(true);
      setFeedback(null);
      await onExport(target, format);
      setFeedback('导出完成，可在新标签页下载。');
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : '导出失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const formatOptions: Record<typeof target, Array<'md' | 'pdf' | 'png'>> = {
    notes: ['md', 'pdf'],
    cards: ['md', 'pdf'],
    mock: ['md', 'pdf'],
    mindmap: ['png']
  };

  const formats = formatOptions[target];
  if (!formats.includes(format)) {
    setFormat(formats[0]);
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="export-modal-title">
      <div className="modal-content">
        <header className="modal-header">
          <h2 id="export-modal-title">导出学习资料</h2>
          <button type="button" onClick={onClose} aria-label="关闭">×</button>
        </header>
        <div className="modal-body">
          <label className="modal-field">
            <span>导出对象</span>
            <select value={target} onChange={(event) => setTarget(event.target.value as typeof target)}>
              {(
                [
                  { key: 'notes', label: '结构化笔记' },
                  { key: 'cards', label: '知识卡片' },
                  { key: 'mock', label: '模拟试题' },
                  { key: 'mindmap', label: '思维导图' }
                ] as const
              ).map((item) => (
                <option key={item.key} value={item.key} disabled={!available[item.key]}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="modal-field">
            <span>导出格式</span>
            <select value={format} onChange={(event) => setFormat(event.target.value as typeof format)}>
              {formats.map((fmt) => (
                <option key={fmt} value={fmt}>
                  {fmt.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          {feedback && <div className="modal-feedback">{feedback}</div>}
        </div>
        <footer className="modal-footer">
          <button type="button" onClick={onClose} className="modal-secondary">
            取消
          </button>
          <button type="button" onClick={handleSubmit} className="modal-primary" disabled={loading}>
            {loading ? '导出中…' : '导出'}
          </button>
        </footer>
      </div>
    </div>
  );
};

export default ExportModal;
