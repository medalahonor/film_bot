import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
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
  const setCurrentSession = useAppStore((s) => s.setCurrentSession);

  const [session, setSession] = useState<Session | null>(null);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const sess = await getCurrentSession().catch((e) => {
        if (axios.isAxiosError(e) && e.response?.status === 404) return null;
        throw e;
      });
      setSession(sess);
      setCurrentSession(sess);
      if (sess) {
        const movs = await getSessionMovies();
        setMovies(movs);
      } else {
        setMovies([]);
      }
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [setCurrentSession]);

  // Initial load
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Keep a ref to latest refresh so the SSE handler never goes stale
  const refreshRef = useRef(refresh);
  useEffect(() => { refreshRef.current = refresh; }, [refresh]);

  // SSE subscription for real-time session updates
  useEffect(() => {
    const initData = window.Telegram?.WebApp?.initData;
    if (!initData) return;

    const url = `/api/sessions/events?init_data=${encodeURIComponent(initData)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = () => {
      // Re-fetch full session + movies to get consistent state
      refreshRef.current();
    };

    es.onerror = () => {
      // Browser auto-reconnects on error
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, []);

  return { session, movies, loading, error, refresh };
};
