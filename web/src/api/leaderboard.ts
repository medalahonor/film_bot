import client from './client';
import type { LeaderboardResponse, ClubStats } from '../types';

export const getLeaderboard = (params: {
  group_id?: number;
  page?: number;
  search?: string;
}): Promise<LeaderboardResponse> =>
  client.get<LeaderboardResponse>('/leaderboard', { params }).then((r) => r.data);

export const getClubStats = (groupId?: number): Promise<ClubStats> =>
  client
    .get<ClubStats>('/leaderboard/stats', { params: { group_id: groupId } })
    .then((r) => r.data);
