import client from './client';
import type { SuggestResult, MovieFull } from '../types';

export const suggestSearch = (query: string): Promise<SuggestResult[]> =>
  client
    .get<SuggestResult[]>('/kinopoisk/suggest', { params: { query } })
    .then((r) => r.data);

export const getMovieById = (kinopoiskId: string): Promise<MovieFull> =>
  client.get<MovieFull>(`/kinopoisk/movie/${kinopoiskId}`).then((r) => r.data);

export const getSeriesById = (kinopoiskId: string): Promise<MovieFull> =>
  client.get<MovieFull>(`/kinopoisk/series/${kinopoiskId}`).then((r) => r.data);

export const parseMovieUrl = (url: string): Promise<MovieFull> =>
  client.post<MovieFull>('/kinopoisk/parse', { url }).then((r) => r.data);
