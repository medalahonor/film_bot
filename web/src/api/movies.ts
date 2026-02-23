import client from './client';
import type { Movie, ContentType } from '../types';

export interface ProposeMovieRequest {
  session_id: number;
  slot: number;
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

export interface ReplaceMovieRequest {
  slot: number;
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

export const proposeMovie = (data: ProposeMovieRequest): Promise<Movie> =>
  client.post<Movie>('/movies/propose', data).then((r) => r.data);

export const replaceMovie = (movieId: number, data: ReplaceMovieRequest): Promise<Movie> =>
  client.put<Movie>(`/movies/${movieId}`, data).then((r) => r.data);

export const withdrawMovie = (movieId: number): Promise<void> =>
  client.delete(`/movies/${movieId}`).then(() => undefined);

export const getSessionMovies = (groupId: number): Promise<Movie[]> =>
  client
    .get<Movie[]>('/sessions/current/movies', { params: { group_id: groupId } })
    .then((r) => r.data);
