import React, { useState, useEffect, useCallback } from 'react';
import { SearchBar } from '../../components/SearchBar';
import { MovieCard } from '../../components/MovieCard';
import { Loader } from '../../components/Loader';
import { Poster } from '../../components/Poster';
import { useSuggest, useMovieDetail } from '../../hooks/useMovies';
import { useAppStore } from '../../store/useAppStore';
import { proposeMovie, replaceMovie, withdrawMovie, getSessionMovies } from '../../api/movies';
import { getErrorMessage } from '../../api/client';
import { useTelegram } from '../../hooks/useTelegram';
import type { SuggestResult, MovieFull, Movie } from '../../types';
import { formatYear } from '../../types';

type InputMode = 'search' | 'url';

const isKinopoiskUrl = (str: string): boolean =>
  str.includes('kinopoisk.ru/film/') || str.includes('kinopoisk.ru/series/');

export const ProposePage: React.FC = () => {
  const [inputMode, setInputMode] = useState<InputMode>('search');
  const [searchQuery, setSearchQuery] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [slot, setSlot] = useState<1 | 2>(1);
  const [selectedSuggest, setSelectedSuggest] = useState<SuggestResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [myMovies, setMyMovies] = useState<{ 1?: Movie; 2?: Movie }>({});
  const [withdrawing, setWithdrawing] = useState<number | null>(null);

  const currentSession = useAppStore((s) => s.currentSession);
  const { tg, haptic } = useTelegram();
  const myTelegramId = tg?.initDataUnsafe?.user?.id ?? null;

  const {
    results: suggestResults,
    loading: suggestLoading,
    error: suggestError,
    search,
    clear: clearSuggest,
  } = useSuggest();

  const {
    movie: detailMovie,
    loading: detailLoading,
    error: detailError,
    fetchById,
    fetchByUrl,
    reset: resetDetail,
  } = useMovieDetail();

  const loadMyMovies = useCallback(async () => {
    if (!currentSession || !myTelegramId) return;
    try {
      const movies = await getSessionMovies();
      const mine: { 1?: Movie; 2?: Movie } = {};
      movies.forEach((m) => {
        if (m.proposer_telegram_id === myTelegramId) {
          mine[m.slot as 1 | 2] = m;
        }
      });
      setMyMovies(mine);
    } catch {
      // ignore — not critical
    }
  }, [currentSession?.id, myTelegramId]);

  useEffect(() => {
    loadMyMovies();
  }, [loadMyMovies]);

  const handleSearchChange = (val: string) => {
    setSearchQuery(val);
    setSelectedSuggest(null);
    resetDetail();
    search(val);
  };

  const handleSuggestClick = async (item: SuggestResult) => {
    setSelectedSuggest(item);
    clearSuggest();
    setSearchQuery(item.title);
    await fetchById(item.kinopoisk_id);
  };

  const handleUrlParse = async () => {
    if (!urlInput.trim()) return;
    resetDetail();
    await fetchByUrl(urlInput.trim());
  };

  const handleModeSwitch = (mode: InputMode) => {
    setInputMode(mode);
    setSearchQuery('');
    setUrlInput('');
    setSelectedSuggest(null);
    resetDetail();
    clearSuggest();
    setSubmitError(null);
  };

  const activeMovie: MovieFull | null = detailMovie;

  const handleWithdraw = async (movieId: number, s: 1 | 2) => {
    setWithdrawing(movieId);
    try {
      await withdrawMovie(movieId);
      haptic?.notificationOccurred('success');
      setMyMovies((prev) => {
        const next = { ...prev };
        delete next[s];
        return next;
      });
    } catch {
      haptic?.notificationOccurred('error');
    } finally {
      setWithdrawing(null);
    }
  };

  const handlePropose = async () => {
    if (!activeMovie || !currentSession) return;
    setSubmitting(true);
    setSubmitError(null);
    const payload = {
      slot,
      kinopoisk_id: activeMovie.kinopoisk_id,
      kinopoisk_url: activeMovie.kinopoisk_url,
      title: activeMovie.title,
      year: activeMovie.year,
      year_end: activeMovie.year_end,
      type: activeMovie.type,
      genres: activeMovie.genres,
      description: activeMovie.description,
      poster_url: activeMovie.poster_url,
      kinopoisk_rating: activeMovie.kinopoisk_rating,
      trailer_url: activeMovie.trailer_url,
    };
    try {
      let result: Movie;
      const existingInSlot = myMovies[slot];
      if (existingInSlot) {
        result = await replaceMovie(existingInSlot.id, payload);
      } else {
        result = await proposeMovie({ session_id: currentSession.id, ...payload });
      }
      haptic?.notificationOccurred('success');
      setMyMovies((prev) => ({ ...prev, [result.slot]: result }));
      setSubmitSuccess(true);
    } catch (e) {
      setSubmitError(getErrorMessage(e));
      haptic?.notificationOccurred('error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setSubmitSuccess(false);
    setSubmitError(null);
    setSearchQuery('');
    setUrlInput('');
    setSelectedSuggest(null);
    resetDetail();
    clearSuggest();
  };

  const isReplacing = !!myMovies[slot];

  if (submitSuccess) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          padding: 24,
          gap: 16,
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: 64 }}>✅</div>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>
          {isReplacing ? 'Заменено!' : 'Предложено!'}
        </h2>
        <p style={{ margin: 0, color: 'var(--tg-theme-hint-color, #999)', fontSize: 14 }}>
          Фильм добавлен в сессию
        </p>
        <button onClick={handleReset} style={btnStyle}>
          Предложить ещё
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{ padding: '16px 16px 8px' }}>
        <h1 style={{ margin: '0 0 12px', fontSize: 20, fontWeight: 700 }}>
          Предложить
        </h1>

        {/* My proposals summary */}
        {currentSession && (myMovies[1] || myMovies[2]) && (
          <div
            style={{
              marginBottom: 12,
              padding: '10px 12px',
              borderRadius: 10,
              backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--tg-theme-hint-color, #999)',
                marginBottom: 6,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
              }}
            >
              Мои предложения
            </div>
            {([1, 2] as const).map((s) => {
              const m = myMovies[s];
              if (!m) return null;
              return (
                <div
                  key={s}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginTop: s === 2 && myMovies[1] ? 6 : 0,
                  }}
                >
                  <span
                    style={{
                      flex: 1,
                      fontSize: 13,
                      minWidth: 0,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    <span
                      style={{
                        fontWeight: 600,
                        color: 'var(--tg-theme-hint-color, #999)',
                        marginRight: 4,
                      }}
                    >
                      Слот {s}:
                    </span>
                    {m.title}
                  </span>
                  <button
                    onClick={() => handleWithdraw(m.id, s)}
                    disabled={withdrawing === m.id}
                    style={withdrawBtnStyle}
                  >
                    {withdrawing === m.id ? '...' : 'Отозвать'}
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Mode toggle */}
        <div
          style={{
            display: 'flex',
            gap: 0,
            backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
            borderRadius: 10,
            padding: 3,
          }}
        >
          {(['search', 'url'] as InputMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => handleModeSwitch(mode)}
              style={{
                flex: 1,
                padding: '7px 0',
                border: 'none',
                borderRadius: 8,
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 500,
                backgroundColor:
                  inputMode === mode
                    ? 'var(--tg-theme-bg-color, #fff)'
                    : 'transparent',
                color:
                  inputMode === mode
                    ? 'var(--tg-theme-text-color, #000)'
                    : 'var(--tg-theme-hint-color, #999)',
                boxShadow: inputMode === mode ? '0 1px 3px rgba(0,0,0,0.12)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              {mode === 'search' ? '🔍 Поиск' : '🔗 По URL'}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 16px 16px' }}>
        {/* Search mode */}
        {inputMode === 'search' && (
          <>
            <SearchBar
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="Название фильма или сериала..."
              autoFocus
            />

            {suggestLoading && <Loader center />}

            {suggestError && (
              <p style={errorStyle}>{suggestError}</p>
            )}

            {/* Suggest results */}
            {!selectedSuggest && suggestResults.length > 0 && (
              <div
                style={{
                  marginTop: 8,
                  borderRadius: 10,
                  overflow: 'hidden',
                  border: '1px solid var(--tg-theme-secondary-bg-color, #f1f1f1)',
                }}
              >
                {suggestResults.map((item) => (
                  <MovieCard
                    key={item.kinopoisk_id}
                    movie={item}
                    onClick={() => handleSuggestClick(item)}
                    compact
                  />
                ))}
              </div>
            )}
          </>
        )}

        {/* URL mode */}
        {inputMode === 'url' && (
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://www.kinopoisk.ru/film/..."
              style={{
                flex: 1,
                padding: '10px 12px',
                border: '1px solid var(--tg-theme-secondary-bg-color, #ddd)',
                borderRadius: 10,
                fontSize: 14,
                backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
                color: 'var(--tg-theme-text-color, #000)',
                outline: 'none',
              }}
            />
            <button
              onClick={handleUrlParse}
              disabled={!isKinopoiskUrl(urlInput) || detailLoading}
              style={{
                ...btnStyle,
                padding: '10px 16px',
                opacity: !isKinopoiskUrl(urlInput) || detailLoading ? 0.5 : 1,
              }}
            >
              {detailLoading ? '...' : '→'}
            </button>
          </div>
        )}

        {/* Detail loading */}
        {detailLoading && <Loader center />}

        {/* Detail error */}
        {detailError && (
          <p style={errorStyle}>{detailError}</p>
        )}

        {/* Movie preview */}
        {activeMovie && !detailLoading && (
          <MoviePreview movie={activeMovie} />
        )}

        {/* No active session warning */}
        {!currentSession && (
          <p style={{ color: 'var(--tg-theme-hint-color, #999)', fontSize: 13, marginTop: 12 }}>
            ⚠️ Нет активной сессии
          </p>
        )}

        {/* Slot selector + submit */}
        {activeMovie && currentSession && (
          <>
            <div
              style={{
                marginTop: 16,
                fontSize: 14,
                fontWeight: 600,
                marginBottom: 8,
                color: 'var(--tg-theme-text-color, #000)',
              }}
            >
              {isReplacing ? `Заменить фильм в слоте ${slot}:` : 'Выберите слот:'}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {([1, 2] as const).map((s) => {
                const occupied = !!myMovies[s];
                const active = slot === s;
                return (
                  <button
                    key={s}
                    onClick={() => setSlot(s)}
                    style={{
                      flex: 1,
                      padding: '10px 0',
                      border: `2px solid ${
                        active
                          ? 'var(--tg-theme-button-color, #2481cc)'
                          : occupied
                          ? '#27ae60'
                          : 'var(--tg-theme-secondary-bg-color, #ddd)'
                      }`,
                      borderRadius: 10,
                      backgroundColor: active
                        ? 'var(--tg-theme-button-color, #2481cc)'
                        : 'transparent',
                      color: active
                        ? 'var(--tg-theme-button-text-color, #fff)'
                        : occupied
                        ? '#27ae60'
                        : 'var(--tg-theme-text-color, #000)',
                      fontSize: 15,
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                  >
                    Слот {s}{occupied ? ' ✓' : ''}
                  </button>
                );
              })}
            </div>

            {isReplacing && (
              <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color, #999)', marginTop: 6 }}>
                Текущий фильм «{myMovies[slot]!.title}» будет заменён
              </p>
            )}

            {submitError && <p style={errorStyle}>{submitError}</p>}

            <button
              onClick={handlePropose}
              disabled={submitting}
              style={{ ...btnStyle, width: '100%', marginTop: 16, opacity: submitting ? 0.7 : 1 }}
            >
              {submitting
                ? 'Отправляется...'
                : isReplacing
                ? 'Заменить'
                : 'Предложить'}
            </button>
          </>
        )}
      </div>
    </div>
  );
};

const MoviePreview: React.FC<{ movie: MovieFull }> = ({ movie }) => {
  const { tg } = useTelegram();

  return (
    <div
      style={{
        marginTop: 12,
        padding: 12,
        borderRadius: 12,
        backgroundColor: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
        display: 'flex',
        gap: 12,
      }}
    >
      <Poster src={movie.poster_url} alt={movie.title} width={70} height={105} borderRadius={8} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>{movie.title}</div>
        <div style={{ fontSize: 13, color: 'var(--tg-theme-hint-color, #999)', marginBottom: 4 }}>
          {movie.type === 'serial' ? '📺 Сериал' : '🎬 Фильм'}
          {movie.year ? ` · ${formatYear(movie.year, movie.year_end)}` : ''}
        </div>
        {movie.genres && (
          <div style={{ fontSize: 12, color: 'var(--tg-theme-hint-color, #999)', marginBottom: 4 }}>
            {movie.genres}
          </div>
        )}
        {movie.kinopoisk_rating && (
          <div style={{ fontSize: 13, fontWeight: 600, color: '#27ae60' }}>
            КП {movie.kinopoisk_rating.toFixed(1)}
          </div>
        )}
        {movie.trailer_url && (
          <button
            onClick={() => tg?.openLink(movie.trailer_url!)}
            style={{
              marginTop: 6,
              background: 'none',
              border: '1px solid var(--tg-theme-link-color, #2481cc)',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: 12,
              color: 'var(--tg-theme-link-color, #2481cc)',
              cursor: 'pointer',
            }}
          >
            ▶ Трейлер
          </button>
        )}
      </div>
    </div>
  );
};

const btnStyle: React.CSSProperties = {
  padding: '12px 24px',
  backgroundColor: 'var(--tg-theme-button-color, #2481cc)',
  color: 'var(--tg-theme-button-text-color, #fff)',
  border: 'none',
  borderRadius: 10,
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
};

const withdrawBtnStyle: React.CSSProperties = {
  padding: '4px 10px',
  backgroundColor: 'transparent',
  color: '#e74c3c',
  border: '1px solid #e74c3c',
  borderRadius: 6,
  fontSize: 12,
  fontWeight: 500,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  flexShrink: 0,
};

const errorStyle: React.CSSProperties = {
  color: '#e74c3c',
  fontSize: 13,
  marginTop: 8,
};
