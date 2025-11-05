import { useMemo } from 'react';
import { Route, Routes, useNavigate } from 'react-router-dom';

import DashboardPage from './pages/DashboardPage';
import SessionWorkspacePage from './pages/session/SessionWorkspacePage';

const App = () => {
  const navigate = useNavigate();
  useMemo(() => {
    if (window.location.pathname === '/') {
      document.title = 'StudyCompanion';
    }
  }, [navigate]);
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/session/:sessionId" element={<SessionWorkspacePage />} />
    </Routes>
  );
};

export default App;
