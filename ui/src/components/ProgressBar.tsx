import '../styles/progress.css';

type Segment = {
  label: string;
  value: number;
};

type ProgressBarProps = {
  segments: Segment[];
  indeterminate?: boolean;
};

const ProgressBar = ({ segments, indeterminate = false }: ProgressBarProps) => {
  if (indeterminate) {
    return (
      <div className="progress-root" aria-busy="true">
        <div className="progress-indeterminate" />
      </div>
    );
  }
  const total = segments.reduce((acc, seg) => acc + seg.value, 0);
  return (
    <div className="progress-root" role="progressbar" aria-valuenow={total} aria-valuemin={0} aria-valuemax={100}>
      {segments.map((segment) => (
        <div key={segment.label} className="progress-segment" style={{ width: `${segment.value}%` }}>
          <span>{segment.label}</span>
        </div>
      ))}
    </div>
  );
};

export default ProgressBar;
