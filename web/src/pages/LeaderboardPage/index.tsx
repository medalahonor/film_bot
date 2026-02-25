import React, { useState, useEffect, useCallback } from 'react';
import { SearchBar } from '../../components/SearchBar';
import { MovieCard } from '../../components/MovieCard';
import { Loader } from '../../components/Loader';
import { getLeaderboard, getClubStats } from '../../api/leaderboard';
import { getErrorMessage } from '../../api/client';
import type { LeaderboardEntry, ClubStats } from '../../types';

const useDebounce = (value: string, delay: number): string => {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
};

const StatsBar: React.FC<{ stats: ClubStats }> = ({ stats }) => (
  <div
    style={{
      display: 'flex',
      gap: 0,
      padding: '8px 16px 12px',
      overflowX: 'auto',
    }}
  >
    {[
      { label: 'Фильмов', value: stats.total_movies },
      { label: 'Сессий', value: stats.total_sessions },
      { label: 'Участников', value: stats.total_users },
      {
        label: 'Ср. оценка',
        value: stats.avg_club_rating ? stats.avg_club_rating.toFixed(1) : '—',
      },
    ].map((item) => (
      <div
        key={item.label}
        style={{
          flex: '1 0 auto',
          textAlign: 'center',
          padding: '8px 12px',
          borderRight: '1px solid var(--tg-theme-secondary-bg-color, #f0f0f0)',
          minWidth: 70,
        }}
      >
        <div
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--tg-theme-text-color, #000)',
          }}
        >
          {item.value}
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--tg-theme-hint-color, #999)',
            marginTop: 2,
          }}
        >
          {item.label}
        </div>
      </div>
    ))}
  </div>
);

export const LeaderboardPage: React.FC = () => {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<LeaderboardEntry[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [stats, setStats] = useState<ClubStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debouncedSearch = useDebounce(search, 300);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const data = await getClubStats();
      setStats(data);
    } catch {
      // Stats are optional; swallow error
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadPage = useCallback(
    async (p: number, q: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await getLeaderboard({
          page: p,
          search: q || undefined,
        });
        setItems(data.items);
        setTotalPages(data.pages);
        setPage(data.page);
      } catch (e) {
        setError(getErrorMessage(e));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    setPage(1);
    loadPage(1, debouncedSearch);
  }, [debouncedSearch, loadPage]);

  const handleSearchChange = (val: string) => {
    setSearch(val);
  };

  return (
    <div>
      {/* Header */}
      <div style={{ padding: '16px 16px 8px' }}>
        <h1 style={{ margin: '0 0 12px', fontSize: 20, fontWeight: 700 }}>
          🏆 Лидерборд
        </h1>
        <SearchBar
          value={search}
          onChange={handleSearchChange}
          placeholder="Поиск по фильмам..."
        />
      </div>

      {/* Stats */}
      {!statsLoading && stats && <StatsBar stats={stats} />}

      {/* Divider */}
      <div
        style={{
          height: 1,
          backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
        }}
      />

      {/* Content */}
      {loading && <Loader center size={36} />}

      {!loading && error && (
        <div style={{ padding: 24, textAlign: 'center' }}>
          <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 14 }}>
            {error}
          </p>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div
          style={{
            padding: 40,
            textAlign: 'center',
            color: 'var(--tg-theme-hint-color, #999)',
          }}
        >
          <div style={{ fontSize: 48, marginBottom: 12 }}>🎞️</div>
          <p style={{ fontSize: 14, margin: 0 }}>
            {search ? 'Ничего не найдено' : 'Пока нет оценённых фильмов'}
          </p>
        </div>
      )}

      {!loading &&
        items.map(({ movie, vote_count, rating_count }, idx) => {
          const globalIdx = idx + (page - 1) * 20;
          return (
          <div key={movie.id}>
            <div style={{ position: 'relative' }}>
              {/* Rank badge */}
              <div
                style={{
                  position: 'absolute',
                  top: 10,
                  left: 4,
                  width: 20,
                  height: 20,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 11,
                  fontWeight: 700,
                  color:
                    globalIdx === 0
                      ? '#f39c12'
                      : globalIdx === 1
                        ? '#95a5a6'
                        : globalIdx === 2
                          ? '#cd7f32'
                          : 'var(--tg-theme-hint-color, #999)',
                  zIndex: 1,
                }}
              >
                {globalIdx + 1}
              </div>
              <MovieCard movie={movie} />
            </div>
            <div
              style={{
                paddingLeft: 88,
                paddingBottom: 8,
                display: 'flex',
                gap: 12,
                fontSize: 12,
                color: 'var(--tg-theme-hint-color, #999)',
              }}
            >
              {vote_count > 0 && <span>👍 {vote_count} голосов</span>}
              {rating_count > 0 && <span>⭐ {rating_count} оценок</span>}
            </div>
            <div
              style={{
                height: 1,
                backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
              }}
            />
          </div>
          );
        })}

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 12,
            padding: '16px 0 24px',
          }}
        >
          <button
            onClick={() => loadPage(page - 1, debouncedSearch)}
            disabled={page <= 1}
            style={paginationBtnStyle(page <= 1)}
          >
            ← Назад
          </button>
          <span
            style={{
              fontSize: 13,
              color: 'var(--tg-theme-hint-color, #999)',
            }}
          >
            {page} / {totalPages}
          </span>
          <button
            onClick={() => loadPage(page + 1, debouncedSearch)}
            disabled={page >= totalPages}
            style={paginationBtnStyle(page >= totalPages)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </div>
  );
};

const paginationBtnStyle = (disabled: boolean): React.CSSProperties => ({
  padding: '8px 16px',
  border: '1px solid var(--tg-theme-secondary-bg-color, #ddd)',
  borderRadius: 8,
  backgroundColor: 'transparent',
  color: disabled
    ? 'var(--tg-theme-hint-color, #ccc)'
    : 'var(--tg-theme-link-color, #2481cc)',
  cursor: disabled ? 'default' : 'pointer',
  fontSize: 13,
  fontWeight: 500,
  opacity: disabled ? 0.5 : 1,
});
