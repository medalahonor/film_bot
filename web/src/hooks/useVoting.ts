import { useState, useEffect, useCallback } from 'react';
import { submitVotes, getMyVotes } from '../api/votes';
import { getErrorMessage } from '../api/client';
import type { Movie } from '../types';

interface UseVotingResult {
  selectedIds: Set<number>;
  toggle: (movieId: number) => void;
  submit: () => Promise<void>;
  submitting: boolean;
  submitted: boolean;
  error: string | null;
  reset: () => void;
}

export const useVoting = (
  sessionId: number | undefined,
  slot: number,
  movies: Movie[],
): UseVotingResult => {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load previously submitted votes for this slot on mount
  useEffect(() => {
    if (!sessionId || movies.length === 0) return;
    const movieIds = new Set(movies.map((m) => m.id));
    getMyVotes(sessionId)
      .then((votes) => {
        const slotVotes = votes.filter((v) => movieIds.has(v.movie_id));
        if (slotVotes.length > 0) {
          setSelectedIds(new Set(slotVotes.map((v) => v.movie_id)));
          setSubmitted(true);
        }
      })
      .catch(() => {
        // Ignore; user just hasn't voted yet
      });
  }, [sessionId, slot]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = useCallback((movieId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(movieId)) {
        next.delete(movieId);
      } else {
        next.add(movieId);
      }
      return next;
    });
    setSubmitted(false);
  }, []);

  const submit = useCallback(async () => {
    if (!sessionId) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitVotes({
        session_id: sessionId,
        movie_ids: Array.from(selectedIds),
        slot,
      });
      setSubmitted(true);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }, [sessionId, slot, selectedIds]);

  const reset = useCallback(() => {
    setSelectedIds(new Set());
    setSubmitted(false);
    setError(null);
  }, []);

  return { selectedIds, toggle, submit, submitting, submitted, error, reset };
};
