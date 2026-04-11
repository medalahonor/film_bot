import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useSession } from '../../hooks/useSession';
import { useVoting } from '../../hooks/useVoting';
import { useTelegram } from '../../hooks/useTelegram';
import { MovieCard } from '../../components/MovieCard';
import { MovieCardFull } from '../../components/MovieCardFull';
import { VotersList } from '../../components/VotersList';
import { Loader } from '../../components/Loader';
import { getVoteResults } from '../../api/votes';
import type { Movie, MovieVoteResult } from '../../types';

interface SlotVotePanelProps {
  slot: number;
  movies: Movie[];
  sessionId: number;
  isRunoff?: boolean;
}

const SlotVotePanel: React.FC<SlotVotePanelProps> = ({ slot, movies, sessionId, isRunoff }) => {
  const { selectedIds, toggle, submit, submitting, submitted, error } = useVoting(
    sessionId,
    slot,
    movies,
  );
  const { haptic } = useTelegram();
  const [openMovie, setOpenMovie] = useState<Movie | null>(null);
  const [voteResults, setVoteResults] = useState<MovieVoteResult[]>([]);

  const fetchVoteResults = useCallback(() => {
    getVoteResults(sessionId).then((r) => setVoteResults(r.results)).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    fetchVoteResults();
    const handler = () => fetchVoteResults();
    window.addEventListener('filmbot:votes-updated', handler);
    return () => window.removeEventListener('filmbot:votes-updated', handler);
  }, [fetchVoteResults]);

  const handleToggle = (movie: Movie) => {
    toggle(movie.id);
    haptic?.selectionChanged();
  };

  const handleSubmit = async () => {
    await submit();
    fetchVoteResults();
    haptic?.notificationOccurred(submitted ? 'success' : 'warning');
  };

  if (movies.length === 0) {
    return (
      <div style={{ padding: '20px 16px', color: 'var(--tg-theme-hint-color, #999)', fontSize: 14 }}>
        Нет предложений в слоте {slot}
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: 16 }}>
      {isRunoff && (
        <div style={{
          margin: '8px 16px',
          padding: '8px 12px',
          borderRadius: 8,
          backgroundColor: 'rgba(231, 76, 60, 0.1)',
          color: '#e74c3c',
          fontSize: 13,
          fontWeight: 600,
        }}>
          ⚡ Переголосование — предыдущие голоса сброшены
        </div>
      )}

      {/* Selection hint */}
      <div style={{ padding: '8px 16px', fontSize: 13, color: 'var(--tg-theme-hint-color, #999)' }}>
        {selectedIds.size > 0
          ? `Выбрано: ${selectedIds.size}`
          : 'Нажмите на фильм, чтобы проголосовать'}
      </div>

      {/* Movie cards */}
      {movies.map((movie) => (
        <div key={movie.id}>
          <MovieCard
            movie={movie}
            selected={selectedIds.has(movie.id)}
            onClick={() => handleToggle(movie)}
          />
          <button
            onClick={() => setOpenMovie(movie)}
            style={{
              marginLeft: 88, marginBottom: 4,
              background: 'none', border: 'none',
              fontSize: 12, color: 'var(--tg-theme-link-color, #2481cc)',
              cursor: 'pointer', padding: 0,
            }}
          >
            Подробнее →
          </button>
          <VotersList voters={voteResults.find((r) => r.movie_id === movie.id)?.voters ?? []} />
        </div>
      ))}

      {error && (
        <p style={{ color: '#e74c3c', fontSize: 13, padding: '0 16px' }}>{error}</p>
      )}

      {/* Submit button */}
      <div style={{ padding: '4px 16px' }}>
        <button
          onClick={handleSubmit}
          disabled={submitting || selectedIds.size === 0}
          style={{
            width: '100%',
            padding: '13px 0',
            backgroundColor:
              submitted && selectedIds.size > 0
                ? '#27ae60'
                : 'var(--tg-theme-button-color, #2481cc)',
            color: 'var(--tg-theme-button-text-color, #fff)',
            border: 'none',
            borderRadius: 10,
            fontSize: 15,
            fontWeight: 600,
            cursor: submitting || selectedIds.size === 0 ? 'default' : 'pointer',
            opacity: selectedIds.size === 0 ? 0.5 : 1,
            transition: 'background-color 0.2s',
          }}
        >
          {submitting ? 'Сохраняется...' : submitted ? '✓ Голос сохранён' : 'Проголосовать'}
        </button>
      </div>

      {/* Movie detail drawer */}
      {openMovie && (
        <MovieCardFull
          movie={openMovie}
          onClose={() => setOpenMovie(null)}
          footer={
            <button
              onClick={() => { handleToggle(openMovie); setOpenMovie(null); }}
              style={{
                width: '100%',
                padding: '12px 0',
                backgroundColor: selectedIds.has(openMovie.id)
                  ? '#e74c3c'
                  : 'var(--tg-theme-button-color, #2481cc)',
                color: '#fff',
                border: 'none',
                borderRadius: 10,
                fontSize: 15,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {selectedIds.has(openMovie.id) ? '✕ Убрать голос' : '✓ Проголосовать за этот'}
            </button>
          }
        />
      )}
    </div>
  );
};

export const VotePage: React.FC = () => {
  const { session, movies, loading, error, refresh } = useSession();
  const [activeSlot, setActiveSlot] = useState<1 | 2>(1);

  const runoffIds1 = session?.runoff_slot1_ids ?? null;
  const runoffIds2 = session?.runoff_slot2_ids ?? null;
  const inRunoff = !!(runoffIds1 || runoffIds2);

  const slot1Movies = useMemo(() => {
    const all = movies.filter((m) => m.slot === 1);
    return runoffIds1 ? all.filter((m) => runoffIds1.includes(m.id)) : all;
  }, [movies, runoffIds1]);

  const slot2Movies = useMemo(() => {
    const all = movies.filter((m) => m.slot === 2);
    return runoffIds2 ? all.filter((m) => runoffIds2.includes(m.id)) : all;
  }, [movies, runoffIds2]);

  if (loading) return <Loader center size={36} />;

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)' }}>{error}</p>
        <button onClick={refresh} style={btnStyle}>Повторить</button>
      </div>
    );
  }

  if (!session || session.status !== 'voting') {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>🗳️</div>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 15 }}>
          Голосование сейчас не активно
        </p>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 13 }}>
          {session ? `Текущий статус: ${session.status}` : 'Нет активной сессии'}
        </p>
      </div>
    );
  }

  const slotLabel = (s: 1 | 2) => {
    const count = s === 1 ? slot1Movies.length : slot2Movies.length;
    const hasRunoff = s === 1 ? !!runoffIds1 : !!runoffIds2;
    return `${hasRunoff ? '⚡ ' : ''}Слот ${s} (${count})`;
  };

  return (
    <div>
      <div style={{ padding: '16px 16px 0' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: 20, fontWeight: 700 }}>
          {inRunoff ? '⚡ Переголосование' : '🗳️ Голосование'}
        </h1>
        {inRunoff && (
          <p style={{ margin: '0 0 8px', fontSize: 13, color: '#e74c3c' }}>
            По слотам с ничьёй проводится повторное голосование
          </p>
        )}

        {/* Slot tabs */}
        <div style={{ display: 'flex', gap: 0, borderBottom: '2px solid var(--tg-theme-secondary-bg-color, #f0f0f0)' }}>
          {([1, 2] as const).map((s) => (
            <button
              key={s}
              onClick={() => setActiveSlot(s)}
              style={{
                flex: 1,
                padding: '10px 0',
                border: 'none',
                backgroundColor: 'transparent',
                color:
                  activeSlot === s
                    ? 'var(--tg-theme-button-color, #2481cc)'
                    : 'var(--tg-theme-hint-color, #999)',
                fontWeight: activeSlot === s ? 700 : 400,
                fontSize: 14,
                cursor: 'pointer',
                borderBottom: activeSlot === s
                  ? '2px solid var(--tg-theme-button-color, #2481cc)'
                  : '2px solid transparent',
                marginBottom: -2,
                transition: 'all 0.15s',
              }}
            >
              {slotLabel(s)}
            </button>
          ))}
        </div>
      </div>

      <SlotVotePanel
        key={`${activeSlot}-${inRunoff}`}
        slot={activeSlot}
        movies={activeSlot === 1 ? slot1Movies : slot2Movies}
        sessionId={session.id}
        isRunoff={activeSlot === 1 ? !!runoffIds1 : !!runoffIds2}
      />
    </div>
  );
};

const btnStyle: React.CSSProperties = {
  padding: '10px 24px',
  backgroundColor: 'var(--tg-theme-button-color, #2481cc)',
  color: 'var(--tg-theme-button-text-color, #fff)',
  border: 'none',
  borderRadius: 8,
  fontSize: 15,
  cursor: 'pointer',
  fontWeight: 500,
};
