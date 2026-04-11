import React, { useState, useEffect } from 'react';
import { UserAvatar } from '../UserAvatar';
import { Loader } from '../Loader';
import { getMovieRatings } from '../../api/ratings';
import { formatUserName } from '../../types';
import type { RaterInfo } from '../../types';

interface MovieRatingsListProps {
  movieId: number;
}

const getRatingColor = (rating: number): string => {
  if (rating >= 7) return '#27ae60';
  if (rating >= 5) return '#95a5a6';
  return '#e74c3c';
};

export const MovieRatingsList: React.FC<MovieRatingsListProps> = ({ movieId }) => {
  const [raters, setRaters] = useState<RaterInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getMovieRatings(movieId)
      .then(setRaters)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [movieId]);

  if (loading) return <Loader size={20} center />;
  if (raters.length === 0) return null;

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{
        fontSize: 12,
        color: 'var(--tg-theme-hint-color, #999)',
        marginBottom: 6,
        textAlign: 'center',
      }}>
        Оценки участников
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {raters.map((r) => (
          <div
            key={r.telegram_id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 13,
            }}
          >
            <UserAvatar
              telegramId={r.telegram_id}
              username={r.username}
              firstName={r.first_name}
              size={20}
            />
            <span style={{ color: 'var(--tg-theme-text-color, #333)' }}>
              {formatUserName(r.first_name, r.last_name, r.username)}
            </span>
            <span style={{ color: 'var(--tg-theme-hint-color, #999)' }}>&mdash;</span>
            <span style={{ fontWeight: 700, color: getRatingColor(r.rating) }}>
              {r.rating}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};
