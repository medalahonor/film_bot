import client from './client';
import type { Session, Movie } from '../types';

export const getCurrentSession = (): Promise<Session> =>
  client.get<Session>('/sessions/current').then((r) => r.data);

export const getSessionMovies = (): Promise<Movie[]> =>
  client.get<Movie[]>('/sessions/current/movies').then((r) => r.data);
