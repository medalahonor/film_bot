import client from './client';
import type { LeaderboardResponse, ClubStats } from '../types';

export const getLeaderboard = (params: {
  page?: number;
  search?: string;
}): Promise<LeaderboardResponse> =>
  client.get<LeaderboardResponse>('/leaderboard', { params }).then((r) => r.data);

export const getClubStats = (): Promise<ClubStats> =>
  client.get<ClubStats>('/leaderboard/stats').then((r) => r.data);
