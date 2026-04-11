import client from './client';
import type { VoteResponse, VoteResultsResponse } from '../types';

export interface VoteRequest {
  session_id: number;
  movie_ids: number[];
  slot: number;
}

export interface FinalizeResult {
  winner_slot1_id: number | null;
  winner_slot2_id: number | null;
  runoff_slot1_ids: number[] | null;
  runoff_slot2_ids: number[] | null;
  status: string;
}

export const submitVotes = (data: VoteRequest): Promise<VoteResponse[]> =>
  client.post<VoteResponse[]>('/votes', data).then((r) => r.data);

export const getMyVotes = (sessionId: number): Promise<VoteResponse[]> =>
  client
    .get<VoteResponse[]>('/votes/my', { params: { session_id: sessionId } })
    .then((r) => r.data);

export const getVoteResults = (sessionId: number): Promise<VoteResultsResponse> =>
  client.get<VoteResultsResponse>(`/votes/results/${sessionId}`).then((r) => r.data);

export const finalizeVotes = (sessionId: number): Promise<FinalizeResult> =>
  client.post<FinalizeResult>(`/votes/finalize/${sessionId}`).then((r) => r.data);
