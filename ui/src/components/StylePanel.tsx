import '../styles/panel.css';

type StylePanelProps = {
  detailLevel: 'brief' | 'medium' | 'detailed';
  expressionLevel: 'popular' | 'standard' | 'insightful';
  disabled?: boolean;
  onChange: (value: { detailLevel: 'brief' | 'medium' | 'detailed'; expressionLevel: 'popular' | 'standard' | 'insightful' }) => void;
};

const detailOptions: Array<{ value: 'brief' | 'medium' | 'detailed'; label: string }> = [
  { value: 'brief', label: '简略' },
  { value: 'medium', label: '中等' },
  { value: 'detailed', label: '详细' }
];

const expressionOptions: Array<{ value: 'popular' | 'standard' | 'insightful'; label: string }> = [
  { value: 'popular', label: '通俗易懂' },
  { value: 'standard', label: '讲解型' },
  { value: 'insightful', label: '学术型' }
];

const StylePanel = ({ detailLevel, expressionLevel, disabled, onChange }: StylePanelProps) => {
  return (
    <section className="panel-section" aria-labelledby="style-panel-heading">
      <header className="panel-header">
        <h3 id="style-panel-heading">风格调节</h3>
        <span className="panel-tag">{detailOptions.find((o) => o.value === detailLevel)?.label} × {expressionOptions.find((o) => o.value === expressionLevel)?.label}</span>
      </header>
      <div className="panel-group" role="radiogroup" aria-label="详略程度">
        {detailOptions.map((option) => (
          <button
            key={option.value}
            className={`panel-radio ${detailLevel === option.value ? 'active' : ''}`}
            onClick={() => !disabled && onChange({ detailLevel: option.value, expressionLevel })}
            disabled={disabled}
            aria-pressed={detailLevel === option.value}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="panel-group" role="radiogroup" aria-label="表达层级">
        {expressionOptions.map((option) => (
          <button
            key={option.value}
            className={`panel-radio ${expressionLevel === option.value ? 'active' : ''}`}
            onClick={() => !disabled && onChange({ detailLevel, expressionLevel: option.value })}
            disabled={disabled}
            aria-pressed={expressionLevel === option.value}
          >
            {option.label}
          </button>
        ))}
      </div>
    </section>
  );
};

export default StylePanel;
