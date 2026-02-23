import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useTelegramInit } from './hooks/useTelegram';
import { useAppStore } from './store/useAppStore';
import { SessionPage } from './pages/SessionPage';
import { ProposePage } from './pages/ProposePage';
import { VotePage } from './pages/VotePage';
import { RatingPage } from './pages/RatingPage';
import { LeaderboardPage } from './pages/LeaderboardPage';
import { AccessDeniedPage } from './pages/AccessDeniedPage';
import { AdminPage } from './pages/AdminPage';
import { TabBar } from './components/TabBar';

const App: React.FC = () => {
  useTelegramInit();

  const isAccessDenied = useAppStore((s) => s.isAccessDenied);
  const setAccessDenied = useAppStore((s) => s.setAccessDenied);

  // Listen for global 403 events from the API client
  useEffect(() => {
    const handler = () => setAccessDenied(true);
    window.addEventListener('filmbot:access-denied', handler);
    return () => window.removeEventListener('filmbot:access-denied', handler);
  }, [setAccessDenied]);

  if (isAccessDenied) {
    return <AccessDeniedPage />;
  }

  return (
    <BrowserRouter>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100dvh',
          overflow: 'hidden',
        }}
      >
        <main style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          <Routes>
            <Route path="/" element={<SessionPage />} />
            <Route path="/propose" element={<ProposePage />} />
            <Route path="/vote" element={<VotePage />} />
            <Route path="/rating" element={<RatingPage />} />
            <Route path="/leaderboard" element={<LeaderboardPage />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <TabBar />
      </div>
    </BrowserRouter>
  );
};

export default App;
