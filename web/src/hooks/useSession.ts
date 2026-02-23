import { useState, useEffect, useCallback } from 'react';
import { useAppStore } from '../store/useAppStore';
import { getCurrentSession, getSessionMovies } from '../api/sessions';
import { getErrorMessage } from '../api/client';
import type { Session, Movie } from '../types';

interface UseSessionResult {
  session: Session | null;
  movies: Movie[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export const useSession = (): UseSessionResult => {
  const groupId = useAppStore((s) => s.groupId);
  const setCurrentSession = useAppStore((s) => s.setCurrentSession);

  const [session, setSession] = useState<Session | null>(null);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!groupId) {
      setError('Группа не определена. Откройте приложение из группы.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [sess, movs] = await Promise.all([
        getCurrentSession(groupId),
        getSessionMovies(groupId),
      ]);
      setSession(sess);
      setCurrentSession(sess);
      setMovies(movs);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [groupId, setCurrentSession]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { session, movies, loading, error, refresh };
};
