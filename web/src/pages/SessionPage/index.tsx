import React, { useMemo } from 'react';
import { useSession } from '../../hooks/useSession';
import { useAppStore } from '../../store/useAppStore';
import { Loader } from '../../components/Loader';
import { MovieCard } from '../../components/MovieCard';
import type { Movie, SessionStatus } from '../../types';

const STATUS_LABELS: Record<SessionStatus, string> = {
  collecting: 'Сбор предложений',
  voting: 'Голосование',
  rating: 'Оценки',
  completed: 'Завершена',
};

const STATUS_COLORS: Record<SessionStatus, string> = {
  collecting: '#27ae60',
  voting: '#2481cc',
  rating: '#f39c12',
  completed: '#95a5a6',
};

const StatusBadge: React.FC<{ status: SessionStatus }> = ({ status }) => (
  <span
    style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: 12,
      fontSize: 12,
      fontWeight: 600,
      backgroundColor: STATUS_COLORS[status] + '22',
      color: STATUS_COLORS[status],
    }}
  >
    {STATUS_LABELS[status]}
  </span>
);

const SlotSection: React.FC<{ slot: number; movies: Movie[] }> = ({
  slot,
  movies,
}) => (
  <div>
    <div
      style={{
        padding: '8px 16px 4px',
        fontSize: 13,
        fontWeight: 600,
        color: 'var(--tg-theme-hint-color, #999)',
        textTransform: 'uppercase',
        letterSpacing: 0.5,
      }}
    >
      Слот {slot}
    </div>
    {movies.map((movie) => (
      <MovieCard key={movie.id} movie={movie} />
    ))}
    {movies.length === 0 && (
      <div
        style={{
          padding: '12px 16px',
          fontSize: 14,
          color: 'var(--tg-theme-hint-color, #999)',
          fontStyle: 'italic',
        }}
      >
        Нет предложений
      </div>
    )}
  </div>
);

const Divider: React.FC = () => (
  <div
    style={{
      height: 1,
      backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
      margin: '4px 0',
    }}
  />
);

export const SessionPage: React.FC = () => {
  const groupId = useAppStore((s) => s.groupId);
  const { session, movies, loading, error, refresh } = useSession();

  const slot1Movies = useMemo(
    () => movies.filter((m) => m.slot === 1),
    [movies],
  );
  const slot2Movies = useMemo(
    () => movies.filter((m) => m.slot === 2),
    [movies],
  );

  if (!groupId) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          padding: 24,
          textAlign: 'center',
          gap: 12,
        }}
      >
        <div style={{ fontSize: 48 }}>👋</div>
        <p style={{ fontSize: 15, color: 'var(--tg-theme-hint-color, #999)' }}>
          Откройте приложение из группы киноклуба
        </p>
      </div>
    );
  }

  if (loading) {
    return <Loader center size={36} />;
  }

  if (error) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          alignItems: 'center',
        }}
      >
        <div style={{ fontSize: 48 }}>😔</div>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 14 }}>
          {error}
        </p>
        <button
          onClick={refresh}
          style={{
            padding: '10px 24px',
            backgroundColor: 'var(--tg-theme-button-color, #2481cc)',
            color: 'var(--tg-theme-button-text-color, #fff)',
            border: 'none',
            borderRadius: 8,
            fontSize: 15,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          Повторить
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div
        style={{
          padding: '16px 16px 12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: 20,
              fontWeight: 700,
              color: 'var(--tg-theme-text-color, #000)',
            }}
          >
            Текущая сессия
          </h1>
          {session && (
            <div style={{ marginTop: 4 }}>
              <StatusBadge status={session.status as SessionStatus} />
            </div>
          )}
        </div>
        <button
          onClick={refresh}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 20,
            cursor: 'pointer',
            padding: 4,
            opacity: 0.6,
          }}
          title="Обновить"
        >
          🔄
        </button>
      </div>

      <Divider />

      {/* No session */}
      {!session && !loading && (
        <div
          style={{
            padding: 32,
            textAlign: 'center',
            color: 'var(--tg-theme-hint-color, #999)',
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 12 }}>🎞️</div>
          <p style={{ fontSize: 15, margin: 0 }}>Активных сессий нет</p>
        </div>
      )}

      {/* Movies by slot */}
      {session && (
        <>
          <SlotSection slot={1} movies={slot1Movies} />
          <Divider />
          <SlotSection slot={2} movies={slot2Movies} />
        </>
      )}
    </div>
  );
};
