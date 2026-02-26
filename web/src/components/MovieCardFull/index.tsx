import React, { useEffect } from 'react';
import { Poster } from '../Poster';
import { useTelegram } from '../../hooks/useTelegram';
import type { Movie } from '../../types';
import { formatYear, formatUserName } from '../../types';

interface MovieCardFullProps {
  movie: Movie;
  onClose: () => void;
  /** Extra content rendered at the bottom (e.g. voting checkboxes) */
  footer?: React.ReactNode;
}

export const MovieCardFull: React.FC<MovieCardFullProps> = ({
  movie,
  onClose,
  footer,
}) => {
  const { tg } = useTelegram();

  // Prevent body scroll when drawer is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          zIndex: 100,
        }}
      />

      {/* Drawer */}
      <div
        style={{
          position: 'fixed',
          bottom: 0, left: 0, right: 0,
          maxHeight: '85dvh',
          backgroundColor: 'var(--tg-theme-bg-color, #fff)',
          borderRadius: '16px 16px 0 0',
          zIndex: 101,
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
        }}
      >
        {/* Handle */}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 4px' }}>
          <div style={{ width: 40, height: 4, borderRadius: 2, backgroundColor: 'var(--tg-theme-hint-color, #ccc)' }} />
        </div>

        <div style={{ padding: '4px 16px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Poster + meta */}
          <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
            <Poster src={movie.poster_url} alt={movie.title} width={90} height={135} borderRadius={10} />
            <div style={{ flex: 1, minWidth: 0 }}>
              {/* Type badge */}
              <div style={{
                display: 'inline-block',
                fontSize: 11, fontWeight: 600,
                padding: '2px 8px', borderRadius: 4,
                backgroundColor: movie.type === 'serial'
                  ? 'rgba(130,100,200,0.15)' : 'rgba(36,129,204,0.15)',
                color: movie.type === 'serial'
                  ? 'var(--tg-theme-link-color, #8264c8)' : 'var(--tg-theme-link-color, #2481cc)',
                marginBottom: 6,
              }}>
                {movie.type === 'serial' ? '📺 Сериал' : '🎬 Фильм'}
              </div>

              <div style={{ fontSize: 17, fontWeight: 700, lineHeight: 1.3, marginBottom: 4 }}>
                {movie.title}
              </div>

              {movie.year && (
                <div style={{ fontSize: 13, color: 'var(--tg-theme-hint-color, #999)', marginBottom: 2 }}>
                  {formatYear(movie.year, movie.year_end)}
                </div>
              )}

              {movie.genres && (
                <div style={{ fontSize: 12, color: 'var(--tg-theme-hint-color, #999)', marginBottom: 6 }}>
                  {movie.genres}
                </div>
              )}

              {/* Ratings row */}
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {movie.kinopoisk_rating != null && (
                  <span style={{ fontSize: 13, fontWeight: 700, color: movie.kinopoisk_rating >= 7 ? '#27ae60' : '#95a5a6' }}>
                    КП {movie.kinopoisk_rating.toFixed(1)}
                  </span>
                )}
                {movie.club_rating != null && (
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--tg-theme-link-color, #2481cc)' }}>
                    ★ {movie.club_rating.toFixed(1)}
                  </span>
                )}
              </div>

              <div style={{ fontSize: 12, color: 'var(--tg-theme-hint-color, #999)', marginTop: 4 }}>
                {formatUserName(movie.proposer_first_name, movie.proposer_last_name, movie.proposer_username, movie.proposer_telegram_id)}
              </div>
            </div>
          </div>

          {/* Description */}
          {movie.description && (
            <p style={{
              fontSize: 14,
              lineHeight: 1.5,
              color: 'var(--tg-theme-text-color, #000)',
              margin: 0,
            }}>
              {movie.description}
            </p>
          )}

          {/* Trailer button */}
          {movie.trailer_url && (
            <button
              onClick={() => tg?.openLink(movie.trailer_url!)}
              style={{
                padding: '10px 16px',
                backgroundColor: 'transparent',
                border: '1.5px solid var(--tg-theme-link-color, #2481cc)',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 600,
                color: 'var(--tg-theme-link-color, #2481cc)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
              }}
            >
              ▶ Смотреть трейлер
            </button>
          )}

          {/* Footer slot (e.g. vote checkbox) */}
          {footer}
        </div>
      </div>
    </>
  );
};
