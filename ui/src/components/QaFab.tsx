import '../styles/qa.css';

type QaFabProps = {
  onClick: () => void;
};

const QaFab = ({ onClick }: QaFabProps) => (
  <button className="qa-fab" onClick={onClick} aria-label="学习助手">
    <span className="qa-fab__icon">💬</span>
    <span>AI 助手</span>
  </button>
);

export default QaFab;
