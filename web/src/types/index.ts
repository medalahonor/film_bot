export type ContentType = 'film' | 'serial';

export type SessionStatus = 'collecting' | 'voting' | 'rating' | 'completed';

export interface Movie {
  id: number;
  session_id: number | null;
  slot: number | null;
  kinopoisk_id: string;
  kinopoisk_url: string;
  title: string;
  year: number | null;
  year_end: number | null;
  type: ContentType;
  genres: string | null;
  description: string | null;
  poster_url: string | null;
  kinopoisk_rating: number | null;
  club_rating: number | null;
  trailer_url: string | null;
  proposer_username: string | null;
  proposer_first_name: string | null;
  proposer_last_name: string | null;
  proposer_telegram_id: number | null;
  created_at: string;
}

export interface Session {
  id: number;
  status: SessionStatus;
  created_at: string;
  voting_started_at: string | null;
  completed_at: string | null;
  winner_slot1_id: number | null;
  winner_slot2_id: number | null;
  runoff_slot1_ids: number[] | null;
  runoff_slot2_ids: number[] | null;
}

export interface SuggestResult {
  kinopoisk_id: string;
  title: string;
  year: number | null;
  year_end: number | null;
  type: ContentType;
  poster_url: string | null;
  kp_rating: number | null;
}

export interface MovieFull {
  kinopoisk_id: string;
  kinopoisk_url: string;
  title: string;
  year: number | null;
  year_end: number | null;
  type: ContentType;
  genres: string | null;
  description: string | null;
  poster_url: string | null;
  kinopoisk_rating: number | null;
  trailer_url: string | null;
}

export interface LeaderboardEntry {
  movie: Movie;
  vote_count: number;
  rating_count: number;
}

export interface LeaderboardResponse {
  items: LeaderboardEntry[];
  total: number;
  page: number;
  pages: number;
}

export interface ClubStats {
  total_movies: number;
  total_sessions: number;
  total_users: number;
  avg_club_rating: number | null;
}

export interface VoteResponse {
  id: number;
  session_id: number;
  movie_id: number;
  created_at: string;
}

export interface RatingResponse {
  id: number;
  session_id: number;
  movie_id: number;
  rating: number;
  created_at: string;
}

export interface UserResponse {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  is_allowed: boolean;
  created_at: string;
}

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

/** Format year or year range for display */
export const formatYear = (year: number | null, yearEnd: number | null): string => {
  if (!year) return '';
  if (yearEnd) return `${year}–${yearEnd}`;
  return String(year);
};

/** Format user display name. Priority: First+Last Name → @username → telegram_id → fallback. */
export const formatUserName = (
  firstName: string | null | undefined,
  lastName: string | null | undefined,
  username: string | null | undefined,
  telegramId?: number | null,
): string => {
  const parts = [firstName, lastName].filter(Boolean) as string[];
  if (parts.length > 0) return parts.join(' ');
  if (username) return `@${username}`;
  if (telegramId) return String(telegramId);
  return 'Участник';
};
