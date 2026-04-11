import React, { useState, useEffect, useCallback } from 'react';
import { useSession } from '../../hooks/useSession';
import { useTelegram } from '../../hooks/useTelegram';
import { StarRating } from '../../components/StarRating';
import { MovieCardFull } from '../../components/MovieCardFull';
import { Loader } from '../../components/Loader';
import { submitRating, getMyRatings } from '../../api/ratings';
import { changeSessionStatus } from '../../api/admin';
import { getErrorMessage } from '../../api/client';
import type { Movie } from '../../types';

interface MovieRatingCardProps {
  movie: Movie;
  sessionId: number;
}

const MovieRatingCard: React.FC<MovieRatingCardProps> = ({ movie, sessionId }) => {
  const { haptic } = useTelegram();
  const [rating, setRating] = useState<number | null>(null);
  const [committedRating, setCommittedRating] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFull, setShowFull] = useState(false);

  // Load existing rating
  useEffect(() => {
    getMyRatings(sessionId)
      .then((ratings) => {
        const existing = ratings.find((r) => r.movie_id === movie.id);
        if (existing) {
          setRating(existing.rating);
          setCommittedRating(existing.rating);
          setSaved(true);
        }
      })
      .catch(() => {});
  }, [sessionId, movie.id]);

  const handleRate = async (value: number) => {
    if (value === committedRating) return;

    setRating(value);
    setSaved(false);
    setSaving(true);
    setError(null);
    try {
      await submitRating({ session_id: sessionId, movie_id: movie.id, rating: value });
      setSaved(true);
      setCommittedRating(value);
      haptic?.notificationOccurred('success');
    } catch (e) {
      setError(getErrorMessage(e));
      haptic?.notificationOccurred('error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        margin: '0 16px 16px',
        padding: 16,
        borderRadius: 12,
        backgroundColor: 'var(--tg-theme-secondary-bg-color, #f8f8f8)',
      }}
    >
      {/* Movie title */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 2 }}>{movie.title}</div>
          <div style={{ fontSize: 12, color: 'var(--tg-theme-hint-color, #999)' }}>
            {movie.type === 'serial' ? '📺 Сериал' : '🎬 Фильм'}
            {movie.year ? ` · ${movie.year}` : ''}
          </div>
        </div>
        <button
          onClick={() => setShowFull(true)}
          style={{
            background: 'none', border: 'none',
            fontSize: 12, color: 'var(--tg-theme-link-color, #2481cc)',
            cursor: 'pointer', padding: 0,
            whiteSpace: 'nowrap', marginLeft: 8,
          }}
        >
          Подробнее →
        </button>
      </div>

      {/* Stars */}
      <StarRating value={rating} onChange={handleRate} size="sm" />

      {/* Club average */}
      <div style={{ textAlign: 'center', marginTop: 6, fontSize: 13, color: 'var(--tg-theme-hint-color, #999)' }}>
        Оценка клуба:{' '}
        {movie.club_rating !== null
          ? <span style={{ fontWeight: 700, color: movie.club_rating >= 7 ? '#27ae60' : movie.club_rating >= 5 ? '#95a5a6' : '#e74c3c' }}>{movie.club_rating.toFixed(1)}</span>
          : <span>–</span>
        }
      </div>

      {/* Status */}
      <div style={{ textAlign: 'center', marginTop: 8, fontSize: 12, minHeight: 18 }}>
        {saving && <span style={{ color: 'var(--tg-theme-hint-color, #999)' }}>Сохраняется...</span>}
        {!saving && saved && (
          <span style={{ color: '#27ae60', fontWeight: 600 }}>✓ Оценка сохранена</span>
        )}
        {error && <span style={{ color: '#e74c3c' }}>{error}</span>}
      </div>

      {/* Full movie drawer */}
      {showFull && (
        <MovieCardFull movie={movie} onClose={() => setShowFull(false)} />
      )}
    </div>
  );
};

export const RatingPage: React.FC = () => {
  const { session, movies, loading, error, refresh } = useSession();
  const [completing, setCompleting] = useState(false);
  const [completeError, setCompleteError] = useState<string | null>(null);

  const handleComplete = async () => {
    if (!session) return;
    setCompleting(true);
    setCompleteError(null);
    try {
      await changeSessionStatus(session.id, 'completed');
      refresh();
    } catch (e) {
      setCompleteError(getErrorMessage(e));
    } finally {
      setCompleting(false);
    }
  };

  // Find winner movies
  const winnerMovies = useCallback((): Movie[] => {
    if (!session) return [];
    const result: Movie[] = [];
    if (session.winner_slot1_id) {
      const m = movies.find((mv) => mv.id === session.winner_slot1_id);
      if (m) result.push(m);
    }
    if (session.winner_slot2_id) {
      const m = movies.find((mv) => mv.id === session.winner_slot2_id);
      if (m) result.push(m);
    }
    return result;
  }, [session, movies]);

  if (loading) return <Loader center size={36} />;

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)' }}>{error}</p>
        <button onClick={refresh} style={btnStyle}>Повторить</button>
      </div>
    );
  }

  if (!session || session.status !== 'rating') {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>⭐</div>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 15 }}>
          Оценивание сейчас не активно
        </p>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 13 }}>
          {session ? `Текущий статус: ${session.status}` : 'Нет активной сессии'}
        </p>
      </div>
    );
  }

  const winners = winnerMovies();

  if (winners.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>🏆</div>
        <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 15 }}>
          Победители ещё не определены
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ padding: '16px 16px 8px' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: 20, fontWeight: 700 }}>⭐ Оценки</h1>
        <p style={{ margin: 0, fontSize: 14, color: 'var(--tg-theme-hint-color, #999)' }}>
          Оцените фильм{winners.length > 1 ? 'ы' : ''} от 1 до 10
        </p>
      </div>

      <div style={{ padding: '8px 0 0' }}>
        {winners.map((movie, idx) => (
          <div key={movie.id}>
            <div style={{
              padding: '6px 16px',
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--tg-theme-hint-color, #999)',
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}>
              🏆 Победитель слота {idx + 1}
            </div>
            <MovieRatingCard movie={movie} sessionId={session.id} />
          </div>
        ))}
      </div>

      {/* Complete session button */}
      <div style={{ padding: '0 16px 24px' }}>
        {completeError && (
          <p style={{ color: '#e74c3c', fontSize: 13, marginBottom: 8 }}>{completeError}</p>
        )}
        <button
          onClick={handleComplete}
          disabled={completing}
          style={{
            width: '100%',
            padding: '13px 0',
            backgroundColor: 'transparent',
            color: completing ? 'var(--tg-theme-hint-color, #999)' : '#e74c3c',
            border: '1px solid currentColor',
            borderRadius: 10,
            fontSize: 14,
            fontWeight: 600,
            cursor: completing ? 'default' : 'pointer',
          }}
        >
          {completing ? 'Завершаем сессию...' : '🏁 Завершить оценивание'}
        </button>
      </div>
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
