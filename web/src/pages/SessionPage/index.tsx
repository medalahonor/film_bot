import React, { useCallback, useMemo, useState } from 'react';
import { useSession } from '../../hooks/useSession';
import { createSession, changeSessionStatus } from '../../api/admin';
import { finalizeVotes } from '../../api/votes';
import { Loader } from '../../components/Loader';
import { MovieCard } from '../../components/MovieCard';
import { MovieCardFull } from '../../components/MovieCardFull';
import type { Movie, SessionStatus } from '../../types';

const STATUS_LABELS: Record<SessionStatus, string> = {
  collecting: 'Сбор предложений',
  voting: 'Голосование',
  rating: 'Оценки',
  completed: 'Завершена',
};

const STATUS_NEXT_LABEL: Partial<Record<SessionStatus, string>> = {
  collecting: '→ Начать голосование',
  voting: '→ Завершить голосование',
  rating: '→ Завершить оценивание',
};

const STATUS_COLORS: Record<SessionStatus, string> = {
  collecting: '#27ae60',
  voting: '#2481cc',
  rating: '#f39c12',
  completed: '#95a5a6',
};

const STATUS_NEXT: Partial<Record<SessionStatus, SessionStatus>> = {
  collecting: 'voting',
  rating: 'completed',
};

const CONFIRM_MESSAGES: Partial<Record<SessionStatus, string>> = {
  collecting: 'Начать голосование? Предложение фильмов будет закрыто.',
  voting: 'Завершить голосование и подвести итоги?',
  rating: 'Завершить оценивание и подвести итоги сессии?',
};

const showConfirmDialog = (message: string): Promise<boolean> => {
  const tg = window.Telegram?.WebApp;
  if (tg?.initData && tg.showConfirm) {
    return new Promise((resolve) => tg.showConfirm(message, resolve));
  }
  return Promise.resolve(window.confirm(message));
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
}) => {
  const [openMovie, setOpenMovie] = useState<Movie | null>(null);

  return (
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
        <div key={movie.id}>
          <MovieCard movie={movie} />
          <button
            onClick={() => setOpenMovie(movie)}
            style={{
              marginLeft: 88,
              marginBottom: 8,
              background: 'none',
              border: 'none',
              fontSize: 12,
              color: 'var(--tg-theme-link-color, #2481cc)',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            Подробнее →
          </button>
        </div>
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
      {openMovie && (
        <MovieCardFull movie={openMovie} onClose={() => setOpenMovie(null)} />
      )}
    </div>
  );
};

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
  const { session, movies, loading, error, refresh } = useSession();
  const [creating, setCreating] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [advanceMsg, setAdvanceMsg] = useState<string | null>(null);

  const handleCreateSession = useCallback(async () => {
    const confirmed = await showConfirmDialog('Начать новую сессию киноклуба?');
    if (!confirmed) return;
    setCreating(true);
    try {
      await createSession();
      await refresh();
    } finally {
      setCreating(false);
    }
  }, [refresh]);

  const handleAdvance = useCallback(async () => {
    if (!session) return;
    const message = CONFIRM_MESSAGES[session.status as SessionStatus];
    if (message) {
      const confirmed = await showConfirmDialog(message);
      if (!confirmed) return;
    }
    setAdvancing(true);
    setAdvanceMsg(null);
    try {
      if (session.status === 'voting') {
        const result = await finalizeVotes(session.id);
        if (result.runoff_slot1_ids || result.runoff_slot2_ids) {
          setAdvanceMsg('⚡ Ничья! Запущено переголосование');
        }
      } else {
        const next = STATUS_NEXT[session.status as SessionStatus];
        if (next) await changeSessionStatus(session.id, next);
      }
      await refresh();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setAdvanceMsg(detail ?? 'Ошибка при переходе');
    } finally {
      setAdvancing(false);
    }
  }, [session, refresh]);

  const slot1Movies = useMemo(
    () => movies.filter((m) => m.slot === 1),
    [movies],
  );
  const slot2Movies = useMemo(
    () => movies.filter((m) => m.slot === 2),
    [movies],
  );

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

  const nextLabel = session ? STATUS_NEXT_LABEL[session.status as SessionStatus] : undefined;

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
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 16,
          }}
        >
          <div style={{ fontSize: 48 }}>🎞️</div>
          <p style={{ fontSize: 15, margin: 0 }}>Активных сессий нет</p>
          <button
              onClick={handleCreateSession}
              disabled={creating}
              style={{
                padding: '10px 24px',
                backgroundColor: 'var(--tg-theme-button-color, #2481cc)',
                color: 'var(--tg-theme-button-text-color, #fff)',
                border: 'none',
                borderRadius: 8,
                fontSize: 15,
                cursor: 'pointer',
                fontWeight: 500,
                opacity: creating ? 0.7 : 1,
              }}
            >
              {creating ? 'Создаём…' : '+ Создать сессию'}
            </button>
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

      {/* Advance phase button (visible to all users) */}
      {session && nextLabel && (
        <div style={{ padding: '12px 16px 24px' }}>
          {advanceMsg && (
            <p style={{ fontSize: 13, color: '#e74c3c', marginBottom: 8 }}>{advanceMsg}</p>
          )}
          <button
            onClick={handleAdvance}
            disabled={advancing}
            style={{
              width: '100%',
              padding: '13px 0',
              backgroundColor: 'transparent',
              color: advancing ? 'var(--tg-theme-hint-color, #999)' : 'var(--tg-theme-button-color, #2481cc)',
              border: '1px solid currentColor',
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 600,
              cursor: advancing ? 'default' : 'pointer',
            }}
          >
            {advancing ? 'Переходим…' : nextLabel}
          </button>
        </div>
      )}
    </div>
  );
};
