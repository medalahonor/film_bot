import React from 'react';
import { Poster } from '../Poster';
import { UserAvatar } from '../UserAvatar';
import type { Movie, SuggestResult, MovieFull } from '../../types';
import { formatYear, formatUserName } from '../../types';

type AnyMovie = Movie | SuggestResult | MovieFull;

interface MovieCardProps {
  movie: AnyMovie;
  onClick?: () => void;
  selected?: boolean;
  compact?: boolean;
}

const TypeBadge: React.FC<{ type: string }> = ({ type }) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 3,
      fontSize: 11,
      fontWeight: 500,
      padding: '2px 6px',
      borderRadius: 4,
      backgroundColor:
        type === 'serial'
          ? 'rgba(130, 100, 200, 0.15)'
          : 'rgba(36, 129, 204, 0.15)',
      color:
        type === 'serial'
          ? 'var(--tg-theme-link-color, #8264c8)'
          : 'var(--tg-theme-link-color, #2481cc)',
    }}
  >
    {type === 'serial' ? '📺 Сериал' : '🎬 Фильм'}
  </span>
);

const KpRating: React.FC<{ rating: number | null }> = ({ rating }) => {
  if (!rating) return null;
  const color =
    rating >= 7 ? '#27ae60' : rating >= 5 ? '#95a5a6' : '#e74c3c';
  return (
    <span
      style={{
        fontSize: 12,
        fontWeight: 600,
        color,
        whiteSpace: 'nowrap',
      }}
    >
      КП {rating.toFixed(1)}
    </span>
  );
};

const ClubRating: React.FC<{ rating: number | null | undefined }> = ({
  rating,
}) => {
  if (!rating) return null;
  const color =
    rating >= 7 ? '#27ae60' : rating >= 5 ? '#95a5a6' : '#e74c3c';
  return (
    <span
      style={{
        fontSize: 14,
        fontWeight: 700,
        color,
        whiteSpace: 'nowrap',
      }}
    >
      ★ {rating.toFixed(1)}
    </span>
  );
};

export const MovieCard: React.FC<MovieCardProps> = ({
  movie,
  onClick,
  selected = false,
  compact = false,
}) => {
  const title = movie.title;
  const year = 'year' in movie ? movie.year : null;
  const yearEnd = 'year_end' in movie ? movie.year_end : null;
  const type = movie.type;
  const posterUrl = movie.poster_url ?? null;
  const kpRating =
    'kinopoisk_rating' in movie
      ? movie.kinopoisk_rating
      : 'kp_rating' in movie
        ? movie.kp_rating
        : null;
  const clubRating = 'club_rating' in movie ? movie.club_rating : null;
  const proposerUsername =
    'proposer_username' in movie ? movie.proposer_username : null;
  const proposerFirstName =
    'proposer_first_name' in movie ? movie.proposer_first_name : null;
  const proposerLastName =
    'proposer_last_name' in movie ? movie.proposer_last_name : null;
  const proposerTelegramId =
    'proposer_telegram_id' in movie ? movie.proposer_telegram_id : null;

  const posterH = compact ? 72 : 90;
  const posterW = compact ? 48 : 60;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        gap: 12,
        padding: '10px 16px',
        cursor: onClick ? 'pointer' : 'default',
        backgroundColor: selected
          ? 'rgba(36, 129, 204, 0.08)'
          : 'transparent',
        borderLeft: selected ? '3px solid var(--tg-theme-button-color, #2481cc)' : '3px solid transparent',
        transition: 'background-color 0.15s',
        alignItems: 'flex-start',
      }}
    >
      <Poster src={posterUrl} alt={title} width={posterW} height={posterH} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {/* Type badge + Club rating row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <TypeBadge type={type} />
          <ClubRating rating={clubRating} />
        </div>

        {/* Title */}
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: 'var(--tg-theme-text-color, #000)',
            lineHeight: 1.3,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}
        >
          {title}
        </div>

        {/* Year */}
        {year && (
          <div style={{ fontSize: 13, color: 'var(--tg-theme-hint-color, #999)' }}>
            {formatYear(year, yearEnd)}
          </div>
        )}

        {/* Proposer + KP rating */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
          {(proposerFirstName || proposerLastName || proposerUsername || proposerTelegramId) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, minWidth: 0 }}>
              <UserAvatar
                telegramId={proposerTelegramId}
                username={proposerUsername}
                firstName={proposerFirstName}
                size={18}
              />
              <span style={{ fontSize: 12, color: 'var(--tg-theme-hint-color, #999)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {formatUserName(proposerFirstName, proposerLastName, proposerUsername, proposerTelegramId)}
              </span>
            </div>
          )}
          <KpRating rating={kpRating} />
        </div>
      </div>
    </div>
  );
};
