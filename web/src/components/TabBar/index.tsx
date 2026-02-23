import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAppStore } from '../../store/useAppStore';

interface TabItem {
  to: string;
  label: string;
  icon: string;
}

export const TabBar: React.FC = () => {
  const isAdmin = useAppStore((s) => s.isAdmin);
  const currentSession = useAppStore((s) => s.currentSession);
  const status = currentSession?.status;

  const tabs: TabItem[] = [
    { to: '/', label: 'Сессия', icon: '🎬' },
  ];

  // Show Propose tab only during collecting phase
  if (!status || status === 'collecting') {
    tabs.push({ to: '/propose', label: 'Предложить', icon: '➕' });
  }

  // Show Vote tab during voting phase
  if (status === 'voting') {
    tabs.push({ to: '/vote', label: 'Голосование', icon: '🗳️' });
  }

  // Show Rating tab during rating phase
  if (status === 'rating') {
    tabs.push({ to: '/rating', label: 'Оценить', icon: '⭐' });
  }

  tabs.push({ to: '/leaderboard', label: 'Топ', icon: '🏆' });

  if (isAdmin) {
    tabs.push({ to: '/admin', label: 'Управление', icon: '⚙️' });
  }

  return (
    <nav
      style={{
        display: 'flex',
        borderTop: '1px solid var(--tg-theme-secondary-bg-color, #e0e0e0)',
        backgroundColor: 'var(--tg-theme-bg-color, #fff)',
        paddingBottom: 'env(safe-area-inset-bottom, 0)',
        flexShrink: 0,
      }}
    >
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.to === '/'}
          style={({ isActive }) => ({
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2,
            padding: '8px 4px',
            textDecoration: 'none',
            color: isActive
              ? 'var(--tg-theme-button-color, #2481cc)'
              : 'var(--tg-theme-hint-color, #999)',
            fontSize: 10,
            fontWeight: isActive ? 600 : 400,
            transition: 'color 0.15s',
          })}
        >
          <span style={{ fontSize: 22 }}>{tab.icon}</span>
          <span>{tab.label}</span>
        </NavLink>
      ))}
    </nav>
  );
};
