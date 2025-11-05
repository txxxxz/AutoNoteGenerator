import '../styles/template-selector.css';

type TemplateSelectorProps = {
  values: {
    notes: boolean;
    cards: boolean;
    mock: boolean;
    mindmap: boolean;
  };
  disabled?: boolean;
  onChange: (values: TemplateSelectorProps['values']) => void;
};

const TemplateSelector = ({ values, disabled, onChange }: TemplateSelectorProps) => {
  const toggle = (key: keyof TemplateSelectorProps['values']) => {
    if (key === 'notes') return;
    onChange({ ...values, [key]: !values[key] });
  };
  return (
    <section className="panel-section" aria-labelledby="template-selector-heading">
      <header className="panel-header">
        <h3 id="template-selector-heading">生成模板</h3>
      </header>
      <div className="template-grid">
        {[
          { key: 'notes', label: '结构化笔记', description: '必选，生成章节化笔记' },
          { key: 'cards', label: '知识卡片', description: '概念、考点、例题' },
          { key: 'mock', label: '模拟试题', description: '选择/填空/简答题' },
          { key: 'mindmap', label: '思维导图', description: '章节知识树' }
        ].map((item) => (
          <label key={item.key} className={`template-item ${values[item.key as keyof typeof values] ? 'selected' : ''}`}>
            <input
              type="checkbox"
              checked={values[item.key as keyof typeof values]}
              disabled={disabled || item.key === 'notes'}
              onChange={() => toggle(item.key as keyof typeof values)}
            />
            <div>
              <span className="template-label">{item.label}</span>
              <p className="template-description">{item.description}</p>
            </div>
          </label>
        ))}
      </div>
    </section>
  );
};

export default TemplateSelector;
