import client from './client';
import type { Session, Movie } from '../types';

export const getCurrentSession = (groupId: number): Promise<Session> =>
  client
    .get<Session>('/sessions/current', { params: { group_id: groupId } })
    .then((r) => r.data);

export const getSessionMovies = (groupId: number): Promise<Movie[]> =>
  client
    .get<Movie[]>('/sessions/current/movies', { params: { group_id: groupId } })
    .then((r) => r.data);
