import '../styles/qa.css';

type QaFabProps = {
  onClick: () => void;
};

const QaFab = ({ onClick }: QaFabProps) => (
  <button className="qa-fab" onClick={onClick} aria-label="学习助手">
    问
  </button>
);

export default QaFab;
