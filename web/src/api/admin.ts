import client from './client';
import type { UserResponse, Session, Movie } from '../types';

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export const getAdminUsers = (): Promise<UserResponse[]> =>
  client.get<UserResponse[]>('/admin/users').then((r) => r.data);

export const getPendingUsers = (): Promise<UserResponse[]> =>
  client.get<UserResponse[]>('/admin/users/pending').then((r) => r.data);

export const allowUser = (telegramId: number): Promise<void> =>
  client.post(`/admin/users/${telegramId}/allow`).then(() => undefined);

export const blockUser = (telegramId: number): Promise<void> =>
  client.post(`/admin/users/${telegramId}/block`).then(() => undefined);

export interface CreateUserRequest {
  telegram_id: number;
  username?: string;
  first_name?: string;
  last_name?: string;
}

export const createUser = (data: CreateUserRequest): Promise<UserResponse> =>
  client.post<UserResponse>('/admin/users', data).then((r) => r.data);

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export const getAdminSessions = (): Promise<Session[]> =>
  client.get<Session[]>('/admin/sessions').then((r) => r.data);

export const createSession = (): Promise<Session> =>
  client.post<Session>('/sessions').then((r) => r.data);

export const changeSessionStatus = (sessionId: number, status: string): Promise<Session> =>
  client
    .patch<Session>(`/sessions/${sessionId}/status`, { status })
    .then((r) => r.data);

export const deleteSession = (sessionId: number): Promise<void> =>
  client.delete(`/sessions/${sessionId}`).then(() => undefined);

export const setSessionWinner = (
  sessionId: number,
  winnerSlot1Id: number | null,
  winnerSlot2Id: number | null,
): Promise<{ winner_slot1_id: number | null; winner_slot2_id: number | null }> =>
  client
    .post(`/admin/sessions/${sessionId}/set-winner`, {
      winner_slot1_id: winnerSlot1Id,
      winner_slot2_id: winnerSlot2Id,
    })
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Movies (admin)
// ---------------------------------------------------------------------------

export const getSessionMovies = (): Promise<Movie[]> =>
  client.get<Movie[]>('/sessions/current/movies').then((r) => r.data);

export const getAdminSessionMovies = (sessionId: number): Promise<Movie[]> =>
  client.get<Movie[]>(`/admin/sessions/${sessionId}/movies`).then((r) => r.data);

export const deleteMovie = (movieId: number): Promise<void> =>
  client.delete(`/movies/${movieId}`).then(() => undefined);

export const updateClubRating = (movieId: number, clubRating: number): Promise<Movie> =>
  client
    .patch<Movie>(`/movies/${movieId}/rating`, { club_rating: clubRating })
    .then((r) => r.data);

export interface MoviePageResponse {
  items: Movie[];
  total: number;
  page: number;
  pages: number;
}

export interface AddMovieRequest {
  kinopoisk_id: string;
  kinopoisk_url: string;
  title: string;
  year?: number | null;
  year_end?: number | null;
  type: 'film' | 'serial';
  genres?: string | null;
  description?: string | null;
  poster_url?: string | null;
  kinopoisk_rating?: number | null;
  trailer_url?: string | null;
}

export const addMovieToSession = (
  sessionId: number,
  slot: 1 | 2,
  data: AddMovieRequest,
): Promise<Movie> =>
  client.post<Movie>(`/admin/sessions/${sessionId}/movies`, { ...data, slot }).then((r) => r.data);

export const addLibraryMovie = (
  data: AddMovieRequest & { club_rating?: number },
): Promise<Movie> =>
  client.post<Movie>('/admin/movies', data).then((r) => r.data);

export const getAdminMovies = (page = 1, search = ''): Promise<MoviePageResponse> =>
  client
    .get<MoviePageResponse>('/admin/movies', {
      params: { page, per_page: 20, ...(search ? { search } : {}) },
    })
    .then((r) => r.data);

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

export interface DbStats {
  sessions: number;
  movies: number;
  users: number;
  votes: number;
  ratings: number;
}

export const getDbStats = (): Promise<DbStats> =>
  client.get<DbStats>('/admin/stats/db').then((r) => r.data);

// ---------------------------------------------------------------------------
// Logs
// ---------------------------------------------------------------------------

export const getAdminLogs = (n = 50): Promise<string[]> =>
  client.get<{ logs: string[] }>('/admin/logs', { params: { n } }).then((r) => r.data.logs);

// ---------------------------------------------------------------------------
// Batch import
// ---------------------------------------------------------------------------

export interface BatchImportResult {
  imported: Movie[];
  errors: { url: string; reason: string }[];
}

export const batchImport = (
  sessionId: number,
  slot: number,
  urls: string[],
): Promise<BatchImportResult> =>
  client
    .post<BatchImportResult>('/admin/batch-import', { session_id: sessionId, slot, urls })
    .then((r) => r.data);
