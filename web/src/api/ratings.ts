import client from './client';
import type { RatingResponse, RaterInfo, OpenRatingsResponse } from '../types';

export interface RatingRequest {
  session_id: number;
  movie_id: number;
  rating: number;
}

export const submitRating = (data: RatingRequest): Promise<RatingResponse> =>
  client.post<RatingResponse>('/ratings', data).then((r) => r.data);

export const getMyRatings = (sessionId: number): Promise<RatingResponse[]> =>
  client
    .get<RatingResponse[]>('/ratings/my', { params: { session_id: sessionId } })
    .then((r) => r.data);

export const getOpenRatings = (sessionId: number): Promise<OpenRatingsResponse> =>
  client.get<OpenRatingsResponse>(`/ratings/open/${sessionId}`).then((r) => r.data);

export const getMovieRatings = (movieId: number): Promise<RaterInfo[]> =>
  client.get<RaterInfo[]>(`/ratings/movie/${movieId}`).then((r) => r.data);
