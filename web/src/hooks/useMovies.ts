import { useState, useCallback, useRef } from 'react';
import { suggestSearch, getMovieById, parseMovieUrl } from '../api/kinopoisk';
import { getErrorMessage } from '../api/client';
import type { SuggestResult, MovieFull } from '../types';

interface UseSuggestResult {
  results: SuggestResult[];
  loading: boolean;
  error: string | null;
  search: (query: string) => void;
  clear: () => void;
}

/** Debounced Kinopoisk suggest search hook */
export const useSuggest = (debounceMs = 300): UseSuggestResult => {
  const [results, setResults] = useState<SuggestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback((query: string) => {
    if (timerRef.current) clearTimeout(timerRef.current);

    if (!query.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    timerRef.current = setTimeout(async () => {
      try {
        const data = await suggestSearch(query.trim());
        setResults(data);
      } catch (e) {
        setError(getErrorMessage(e));
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, debounceMs);
  }, [debounceMs]);

  const clear = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setResults([]);
    setLoading(false);
    setError(null);
  }, []);

  return { results, loading, error, search, clear };
};

interface UseMovieDetailResult {
  movie: MovieFull | null;
  loading: boolean;
  error: string | null;
  fetchById: (id: string) => Promise<void>;
  fetchByUrl: (url: string) => Promise<void>;
  reset: () => void;
}

/** Fetch full movie details by ID or URL */
export const useMovieDetail = (): UseMovieDetailResult => {
  const [movie, setMovie] = useState<MovieFull | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchById = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMovieById(id);
      setMovie(data);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchByUrl = useCallback(async (url: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await parseMovieUrl(url);
      setMovie(data);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setMovie(null);
    setError(null);
  }, []);

  return { movie, loading, error, fetchById, fetchByUrl, reset };
};
