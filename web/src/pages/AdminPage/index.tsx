import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '../../store/useAppStore';
import {
  allowUser,
  batchImport,
  blockUser,
  changeSessionStatus,
  createSession,
  createUser,
  deleteMovie,
  deleteSession,
  getAdminLogs,
  getAdminMovies,
  getAdminSessions,
  getAdminSessionMovies,
  getAdminUsers,
  getDbStats,
  getPendingUsers,
  setSessionWinner,
  updateClubRating,
  addMovieToSession,
  addLibraryMovie,
  type BatchImportResult,
  type CreateUserRequest,
  type DbStats,
  type MoviePageResponse,
  type AddMovieRequest,
} from '../../api/admin';
import { finalizeVotes } from '../../api/votes';
import type { Movie, Session, UserResponse, SuggestResult, MovieFull } from '../../types';
import { formatYear } from '../../types';
import { UserAvatar } from '../../components/UserAvatar';
import { useSuggest, useMovieDetail } from '../../hooks/useMovies';

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

type AdminTab = 'sessions' | 'movies' | 'users' | 'import' | 'logs';

const STATUS_LABELS: Record<string, string> = {
  collecting: '📝 Сбор',
  voting: '🗳 Голосование',
  rating: '⭐ Оценка',
  completed: '✅ Завершена',
};

const STATUS_NEXT: Record<string, string> = {
  collecting: 'voting',
  voting: 'rating',
  rating: 'completed',
};

const STATUS_PREV: Record<string, string> = {
  voting: 'collecting',
  rating: 'voting',
  completed: 'rating',
};

const btnStyle = (primary = true, danger = false): React.CSSProperties => ({
  padding: '6px 12px',
  borderRadius: 8,
  border: 'none',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 500,
  backgroundColor: danger
    ? '#e74c3c'
    : primary
    ? 'var(--tg-theme-button-color, #2481cc)'
    : 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
  color: primary || danger ? '#fff' : 'var(--tg-theme-text-color, #000)',
});

const cardStyle: React.CSSProperties = {
  background: 'var(--tg-theme-bg-color, #fff)',
  border: '1px solid var(--tg-theme-secondary-bg-color, #e0e0e0)',
  borderRadius: 10,
  padding: '10px 12px',
  marginBottom: 8,
};

const sectionTitle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--tg-theme-hint-color, #888)',
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  marginBottom: 8,
};

const inputBase: React.CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  borderRadius: 8,
  border: '1px solid var(--tg-theme-secondary-bg-color, #ccc)',
  fontSize: 13,
  background: 'var(--tg-theme-bg-color, #fff)',
  color: 'var(--tg-theme-text-color, #000)',
  boxSizing: 'border-box',
};

// ---------------------------------------------------------------------------
// AddMovieForm — shared between SessionOverlay and MoviesTab
// ---------------------------------------------------------------------------

type AddMovieFormProps =
  | { mode: 'session'; sessionId: number; slot: 1 | 2; onSuccess: () => void; onCancel: () => void }
  | { mode: 'library'; onSuccess: () => void; onCancel: () => void };

const AddMovieForm: React.FC<AddMovieFormProps> = (props) => {
  const [inputMode, setInputMode] = useState<'search' | 'url'>('search');
  const [searchQuery, setSearchQuery] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { results, loading: searchLoading, search, clear } = useSuggest();
  const { movie: detail, loading: detailLoading, fetchById, fetchSeriesById, fetchByUrl, reset } = useMovieDetail();

  const handleSearchChange = (val: string) => {
    setSearchQuery(val);
    reset();
    search(val);
  };

  const handleSuggestClick = async (item: SuggestResult) => {
    clear();
    setSearchQuery(item.title);
    if (item.type === 'serial') await fetchSeriesById(item.kinopoisk_id);
    else await fetchById(item.kinopoisk_id);
  };

  const handleUrlParse = async () => {
    if (!urlInput.trim()) return;
    reset();
    await fetchByUrl(urlInput.trim());
  };

  const handleSubmit = async () => {
    if (!detail) return;
    setSubmitting(true);
    setError(null);
    const data: AddMovieRequest = {
      kinopoisk_id: detail.kinopoisk_id,
      kinopoisk_url: detail.kinopoisk_url,
      title: detail.title,
      year: detail.year,
      year_end: detail.year_end,
      type: detail.type,
      genres: detail.genres,
      description: detail.description,
      poster_url: detail.poster_url,
      kinopoisk_rating: detail.kinopoisk_rating,
      trailer_url: detail.trailer_url,
    };
    try {
      if (props.mode === 'session') {
        await addMovieToSession(props.sessionId, props.slot, data);
      } else {
        await addLibraryMovie(data);
      }
      props.onSuccess();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Ошибка добавления');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleStyle = (active: boolean): React.CSSProperties => ({
    flex: 1,
    padding: '6px 0',
    border: 'none',
    borderRadius: 7,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 500,
    background: active ? 'var(--tg-theme-bg-color, #fff)' : 'transparent',
    color: active ? 'var(--tg-theme-text-color, #000)' : 'var(--tg-theme-hint-color, #999)',
    boxShadow: active ? '0 1px 3px rgba(0,0,0,0.12)' : 'none',
  });

  return (
    <div style={{ ...cardStyle, marginTop: 4 }}>
      {/* Mode toggle */}
      <div style={{
        display: 'flex', gap: 0,
        background: 'var(--tg-theme-secondary-bg-color, #f1f1f1)',
        borderRadius: 9, padding: 2, marginBottom: 8,
      }}>
        <button style={toggleStyle(inputMode === 'search')} onClick={() => { setInputMode('search'); reset(); clear(); setUrlInput(''); }}>🔍 Поиск</button>
        <button style={toggleStyle(inputMode === 'url')} onClick={() => { setInputMode('url'); reset(); clear(); setSearchQuery(''); }}>🔗 URL</button>
      </div>

      {inputMode === 'search' && (
        <>
          <input
            type="search"
            placeholder="Название фильма или сериала…"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            style={{ ...inputBase, marginBottom: 6 }}
            autoFocus
          />
          {searchLoading && <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '0 0 4px' }}>Поиск…</p>}
          {results.length > 0 && !detail && (
            <div style={{ borderRadius: 8, overflow: 'hidden', border: '1px solid var(--tg-theme-secondary-bg-color, #eee)', marginBottom: 6 }}>
              {results.map((item) => (
                <div
                  key={item.kinopoisk_id}
                  onClick={() => handleSuggestClick(item)}
                  style={{ padding: '7px 10px', cursor: 'pointer', borderBottom: '1px solid var(--tg-theme-secondary-bg-color, #eee)', fontSize: 13 }}
                >
                  {item.type === 'serial' ? '📺' : '🎬'} {item.title}
                  {item.year ? ` (${formatYear(item.year, item.year_end)})` : ''}
                  {item.kp_rating ? <span style={{ color: '#27ae60', marginLeft: 6, fontSize: 12 }}>★ {item.kp_rating}</span> : null}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {inputMode === 'url' && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
          <input
            type="url"
            placeholder="https://www.kinopoisk.ru/film/…"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            style={{ ...inputBase, flex: 1, marginBottom: 0 }}
          />
          <button
            style={{ ...btnStyle(), flexShrink: 0, opacity: detailLoading ? 0.6 : 1 }}
            onClick={handleUrlParse}
            disabled={detailLoading || !urlInput.includes('kinopoisk.ru')}
          >
            {detailLoading ? '…' : '→'}
          </button>
        </div>
      )}

      {detailLoading && <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '0 0 4px' }}>Загрузка…</p>}

      {detail && (
        <div style={{ display: 'flex', gap: 8, marginBottom: 8, padding: '8px', background: 'var(--tg-theme-secondary-bg-color, #f5f5f5)', borderRadius: 8 }}>
          {detail.poster_url && (
            <img src={detail.poster_url} alt={detail.title} style={{ width: 48, height: 72, borderRadius: 6, objectFit: 'cover', flexShrink: 0 }} />
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ margin: 0, fontWeight: 600, fontSize: 13 }}>{detail.title}</p>
            <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--tg-theme-hint-color)' }}>
              {detail.type === 'serial' ? '📺' : '🎬'} {formatYear(detail.year, detail.year_end)}
              {detail.kinopoisk_rating ? ` · КП ${detail.kinopoisk_rating}` : ''}
            </p>
          </div>
        </div>
      )}

      {error && <p style={{ color: '#e74c3c', fontSize: 12, margin: '0 0 6px' }}>{error}</p>}

      <div style={{ display: 'flex', gap: 6 }}>
        <button
          style={{ ...btnStyle(), flex: 1, opacity: (!detail || submitting) ? 0.6 : 1 }}
          disabled={!detail || submitting}
          onClick={handleSubmit}
        >
          {submitting ? 'Добавляем…' : 'Добавить'}
        </button>
        <button style={btnStyle(false)} onClick={props.onCancel}>Отмена</button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// SessionOverlay — full-screen modal with context-specific session actions
// ---------------------------------------------------------------------------

interface SessionOverlayProps {
  session: Session;
  onClose: () => void;
  onReload: () => void;
}

const SessionOverlay: React.FC<SessionOverlayProps> = ({ session, onClose, onReload }) => {
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [editRating, setEditRating] = useState<Record<number, string>>({});
  const [addingSlot, setAddingSlot] = useState<1 | 2 | null>(null);
  const [slot1WinnerId, setSlot1WinnerId] = useState<number | null>(session.winner_slot1_id);
  const [slot2WinnerId, setSlot2WinnerId] = useState<number | null>(session.winner_slot2_id);

  const loadMovies = useCallback(async () => {
    setLoading(true);
    try {
      setMovies(await getAdminSessionMovies(session.id));
    } catch {
      setMsg('Ошибка загрузки фильмов');
    } finally {
      setLoading(false);
    }
  }, [session.id]);

  useEffect(() => { loadMovies(); }, [loadMovies]);

  const handleDeleteMovie = async (id: number) => {
    if (!window.confirm('Удалить фильм из сессии?')) return;
    try {
      await deleteMovie(id);
      setMsg('Удалено');
      loadMovies();
    } catch {
      setMsg('Ошибка удаления');
    }
  };

  const handleSaveRating = async (id: number) => {
    const val = parseFloat(editRating[id] ?? '');
    if (isNaN(val) || val < 0 || val > 10) return setMsg('Оценка 0–10');
    try {
      await updateClubRating(id, val);
      setMsg('Оценка обновлена');
      setEditRating((prev) => { const n = { ...prev }; delete n[id]; return n; });
      loadMovies();
    } catch {
      setMsg('Ошибка сохранения');
    }
  };

  const handleSetWinner = async () => {
    try {
      await setSessionWinner(session.id, slot1WinnerId, slot2WinnerId);
      setMsg('Победители назначены');
      onReload();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail ?? 'Ошибка');
    }
  };

  const slot1Movies = movies.filter((m) => m.slot === 1);
  const slot2Movies = movies.filter((m) => m.slot === 2);

  const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'var(--tg-theme-bg-color, #fff)',
    zIndex: 100,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
  };

  const headerStyle: React.CSSProperties = {
    position: 'sticky',
    top: 0,
    zIndex: 1,
    background: 'var(--tg-theme-bg-color, #fff)',
    borderBottom: '1px solid var(--tg-theme-secondary-bg-color, #eee)',
    padding: '10px 16px',
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  };

  return (
    <div style={overlayStyle}>
      {/* Header */}
      <div style={headerStyle}>
        <button style={{ ...btnStyle(false), padding: '6px 10px' }} onClick={onClose}>← Назад</button>
        <span style={{ fontWeight: 600, fontSize: 15 }}>
          Сессия #{session.id} · {STATUS_LABELS[session.status] ?? session.status}
        </span>
      </div>

      {/* Body */}
      <div style={{ padding: '12px 16px', flex: 1 }}>
        {msg && (
          <p style={{ color: msg.includes('Ошибка') ? '#e74c3c' : '#27ae60', fontSize: 13, marginBottom: 8 }}>
            {msg}
          </p>
        )}
        {loading && <p style={{ color: 'var(--tg-theme-hint-color)', fontSize: 13 }}>Загрузка…</p>}

        {/* === COLLECTING: manage movies per slot === */}
        {session.status === 'collecting' && !loading && (
          <>
            {([1, 2] as const).map((sl) => {
              const slotMovies = sl === 1 ? slot1Movies : slot2Movies;
              return (
                <div key={sl} style={{ marginBottom: 16 }}>
                  <p style={sectionTitle}>Слот {sl}</p>
                  {slotMovies.length === 0 && addingSlot !== sl && (
                    <p style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)', marginBottom: 6 }}>Нет фильмов</p>
                  )}
                  {slotMovies.map((m) => (
                    <div key={m.id} style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ flex: 1, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {m.type === 'serial' ? '📺' : '🎬'} {m.title}
                      </span>
                      <button style={{ ...btnStyle(false, true), padding: '4px 8px', flexShrink: 0 }} onClick={() => handleDeleteMovie(m.id)}>✕</button>
                    </div>
                  ))}
                  {addingSlot === sl ? (
                    <AddMovieForm
                      mode="session"
                      sessionId={session.id}
                      slot={sl}
                      onSuccess={() => { setAddingSlot(null); loadMovies(); }}
                      onCancel={() => setAddingSlot(null)}
                    />
                  ) : (
                    <button style={{ ...btnStyle(false), width: '100%', marginTop: 4 }} onClick={() => setAddingSlot(sl)}>
                      + Добавить в слот {sl}
                    </button>
                  )}
                </div>
              );
            })}
          </>
        )}

        {/* === VOTING: pick winner per slot === */}
        {session.status === 'voting' && !loading && (
          <>
            <p style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)', marginBottom: 12 }}>
              Вручную назначьте победителя в каждом слоте, затем нажмите «Сохранить».
            </p>
            {([1, 2] as const).map((sl) => {
              const slotMovies = sl === 1 ? slot1Movies : slot2Movies;
              const currentWinnerId = sl === 1 ? slot1WinnerId : slot2WinnerId;
              const setWinnerId = sl === 1 ? setSlot1WinnerId : setSlot2WinnerId;
              return (
                <div key={sl} style={{ marginBottom: 16 }}>
                  <p style={sectionTitle}>Слот {sl}</p>
                  {slotMovies.length === 0 && (
                    <p style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>Нет фильмов</p>
                  )}
                  {slotMovies.map((m) => {
                    const isWinner = currentWinnerId === m.id;
                    return (
                      <div
                        key={m.id}
                        style={{
                          ...cardStyle,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          borderColor: isWinner ? 'var(--tg-theme-button-color, #2481cc)' : undefined,
                          cursor: 'pointer',
                        }}
                        onClick={() => setWinnerId(isWinner ? null : m.id)}
                      >
                        <span style={{ flex: 1, fontSize: 13 }}>
                          {m.type === 'serial' ? '📺' : '🎬'} {m.title}
                          {m.kinopoisk_rating ? <span style={{ color: 'var(--tg-theme-hint-color)', fontSize: 11, marginLeft: 6 }}>КП {m.kinopoisk_rating}</span> : null}
                        </span>
                        {isWinner && <span style={{ fontSize: 18 }}>🏆</span>}
                      </div>
                    );
                  })}
                </div>
              );
            })}
            <button style={{ ...btnStyle(), width: '100%', marginTop: 4 }} onClick={handleSetWinner}>
              Сохранить победителей
            </button>
          </>
        )}

        {/* === RATING: edit club_rating === */}
        {session.status === 'rating' && !loading && (
          <>
            {movies.length === 0 && <p style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>Нет фильмов</p>}
            {movies.map((m) => (
              <div key={m.id} style={cardStyle}>
                <p style={{ margin: '0 0 6px', fontWeight: 600, fontSize: 13 }}>
                  {m.type === 'serial' ? '📺' : '🎬'} {m.title}
                  <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--tg-theme-hint-color)', marginLeft: 6 }}>
                    КП {m.kinopoisk_rating ?? '—'}
                  </span>
                </p>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    step={0.1}
                    placeholder={`Клуб ${m.club_rating ?? '—'}`}
                    value={editRating[m.id] ?? ''}
                    onChange={(e) => setEditRating((prev) => ({ ...prev, [m.id]: e.target.value }))}
                    style={{ width: 80, padding: '4px 6px', borderRadius: 6, border: '1px solid #ccc', fontSize: 13 }}
                  />
                  <button style={btnStyle()} onClick={() => handleSaveRating(m.id)}>Сохранить</button>
                </div>
              </div>
            ))}
          </>
        )}

        {/* === COMPLETED: read-only === */}
        {session.status === 'completed' && !loading && (
          <>
            {session.winner_slot1_id && (
              <div style={cardStyle}>
                <p style={{ margin: 0, fontWeight: 600, fontSize: 13 }}>🏆 Победитель слот 1</p>
                {movies.filter((m) => m.id === session.winner_slot1_id).map((m) => (
                  <p key={m.id} style={{ margin: '2px 0 0', fontSize: 13 }}>
                    {m.type === 'serial' ? '📺' : '🎬'} {m.title}
                    {m.club_rating ? ` · Клуб ${m.club_rating}` : ''}
                  </p>
                ))}
              </div>
            )}
            {session.winner_slot2_id && (
              <div style={cardStyle}>
                <p style={{ margin: 0, fontWeight: 600, fontSize: 13 }}>🏆 Победитель слот 2</p>
                {movies.filter((m) => m.id === session.winner_slot2_id).map((m) => (
                  <p key={m.id} style={{ margin: '2px 0 0', fontSize: 13 }}>
                    {m.type === 'serial' ? '📺' : '🎬'} {m.title}
                    {m.club_rating ? ` · Клуб ${m.club_rating}` : ''}
                  </p>
                ))}
              </div>
            )}
            <p style={sectionTitle}>Все фильмы</p>
            {movies.map((m) => (
              <div key={m.id} style={cardStyle}>
                <p style={{ margin: 0, fontSize: 13 }}>
                  {m.type === 'serial' ? '📺' : '🎬'} {m.title}
                  <span style={{ color: 'var(--tg-theme-hint-color)', fontSize: 11, marginLeft: 6 }}>
                    Слот {m.slot} · КП {m.kinopoisk_rating ?? '—'} · Клуб {m.club_rating ?? '—'}
                  </span>
                </p>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// SessionsTab
// ---------------------------------------------------------------------------

const SessionsTab: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAdminSessions();
      setSessions(data);
    } catch {
      setMsg('Ошибка загрузки сессий');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    try {
      await createSession();
      setMsg('Сессия создана');
      load();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail ?? 'Ошибка создания');
    }
  };

  const handleNext = async (session: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    if (session.status === 'voting') {
      try {
        const result = await finalizeVotes(session.id);
        if (result.runoff_slot1_ids || result.runoff_slot2_ids) {
          setMsg('⚡ Ничья! Запущено переголосование');
        } else {
          setMsg('✅ Голосование завершено, победители определены');
        }
        load();
      } catch (err: any) {
        setMsg(err?.response?.data?.detail ?? 'Ошибка');
      }
      return;
    }
    const next = STATUS_NEXT[session.status];
    if (!next) return;
    try {
      await changeSessionStatus(session.id, next);
      setMsg(`Статус → ${STATUS_LABELS[next] ?? next}`);
      load();
    } catch (err: any) {
      setMsg(err?.response?.data?.detail ?? 'Ошибка');
    }
  };

  const handleRevert = async (session: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    const prev = STATUS_PREV[session.status];
    if (!prev) return;
    if (!window.confirm(`Откатить статус к "${STATUS_LABELS[prev]}"?`)) return;
    try {
      await changeSessionStatus(session.id, prev);
      setMsg(`Статус откачен → ${STATUS_LABELS[prev]}`);
      load();
    } catch (err: any) {
      setMsg(err?.response?.data?.detail ?? 'Ошибка');
    }
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Удалить сессию и все её данные (фильмы, голоса, оценки)?')) return;
    try {
      await deleteSession(id);
      setMsg('Сессия удалена');
      load();
    } catch {
      setMsg('Ошибка удаления');
    }
  };

  return (
    <>
      {selectedSession && (
        <SessionOverlay
          session={selectedSession}
          onClose={() => setSelectedSession(null)}
          onReload={load}
        />
      )}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <p style={sectionTitle}>Сессии</p>
          <button style={btnStyle()} onClick={handleCreate}>+ Создать</button>
        </div>
        {msg && <p style={{ color: msg.startsWith('✅') || msg.startsWith('⚡') ? '#27ae60' : '#e74c3c', fontSize: 13, marginBottom: 8 }}>{msg}</p>}
        {loading && <p style={{ color: 'var(--tg-theme-hint-color)' }}>Загрузка…</p>}
        {sessions.map((s) => (
          <div
            key={s.id}
            style={{ ...cardStyle, cursor: 'pointer' }}
            onClick={() => setSelectedSession(s)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>#{s.id}</span>
                  <span style={{ fontSize: 13 }}>{STATUS_LABELS[s.status] ?? s.status}</span>
                  {(s.runoff_slot1_ids || s.runoff_slot2_ids) && (
                    <span style={{ fontSize: 11, color: '#e74c3c', fontWeight: 600 }}>⚡ Переголосование</span>
                  )}
                </div>
                {(s.winner_slot1_id || s.winner_slot2_id) && (
                  <div style={{ fontSize: 11, color: 'var(--tg-theme-hint-color)', marginTop: 2, display: 'flex', gap: 8 }}>
                    {s.winner_slot1_id && <span>🏆 Слот 1: #{s.winner_slot1_id}</span>}
                    {s.winner_slot2_id && <span>🏆 Слот 2: #{s.winner_slot2_id}</span>}
                  </div>
                )}
                <p style={{ fontSize: 11, color: 'var(--tg-theme-hint-color)', margin: '2px 0 0' }}>
                  {new Date(s.created_at).toLocaleString('ru')} · нажмите для управления
                </p>
              </div>
              <div style={{ display: 'flex', gap: 4, flexShrink: 0, marginLeft: 6 }} onClick={(e) => e.stopPropagation()}>
                {STATUS_PREV[s.status] && (
                  <button
                    style={{ ...btnStyle(false), padding: '6px 8px', fontSize: 12 }}
                    onClick={(e) => handleRevert(s, e)}
                    title={`Откатить к ${STATUS_LABELS[STATUS_PREV[s.status]]}`}
                  >↩</button>
                )}
                {STATUS_NEXT[s.status] && (
                  <button style={btnStyle(true)} onClick={(e) => handleNext(s, e)}>
                    → {STATUS_LABELS[STATUS_NEXT[s.status]]}
                  </button>
                )}
                {s.status !== 'completed' && (
                  <button style={btnStyle(false, true)} onClick={(e) => handleDelete(s.id, e)}>✕</button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
};

// ---------------------------------------------------------------------------
// MoviesTab — global library
// ---------------------------------------------------------------------------

const MoviesTab: React.FC = () => {
  const [data, setData] = useState<MoviePageResponse | null>(null);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [editRating, setEditRating] = useState<Record<number, string>>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (p: number, q: string) => {
    setLoading(true);
    setMsg('');
    try {
      setData(await getAdminMovies(p, q));
    } catch {
      setMsg('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page, search);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, load]);

  const handleSearchChange = (val: string) => {
    setSearch(val);
    setPage(1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(1, val), 300);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Удалить фильм?')) return;
    try {
      await deleteMovie(id);
      load(page, search);
    } catch {
      setMsg('Ошибка удаления');
    }
  };

  const handleSaveRating = async (id: number) => {
    const val = parseFloat(editRating[id] ?? '');
    if (isNaN(val) || val < 0 || val > 10) return setMsg('Оценка 0–10');
    try {
      await updateClubRating(id, val);
      setMsg('Оценка обновлена');
      setEditRating((prev) => { const n = { ...prev }; delete n[id]; return n; });
      load(page, search);
    } catch {
      setMsg('Ошибка');
    }
  };

  const items = data?.items ?? [];

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center' }}>
        <button style={btnStyle()} onClick={() => setShowAddForm((v) => !v)}>
          {showAddForm ? '— Скрыть форму' : '+ Добавить фильм'}
        </button>
      </div>

      {showAddForm && (
        <AddMovieForm
          mode="library"
          onSuccess={() => { setShowAddForm(false); load(1, search); }}
          onCancel={() => setShowAddForm(false)}
        />
      )}

      <input
        type="search"
        placeholder="🔍 Поиск по названию…"
        value={search}
        onChange={(e) => handleSearchChange(e.target.value)}
        style={{ ...inputBase, marginBottom: 10 }}
      />

      {msg && <p style={{ color: msg === 'Оценка обновлена' ? '#27ae60' : '#e74c3c', fontSize: 13, marginBottom: 8 }}>{msg}</p>}
      {loading && <p style={{ color: 'var(--tg-theme-hint-color)' }}>Загрузка…</p>}
      {!loading && items.length === 0 && (
        <p style={{ color: 'var(--tg-theme-hint-color)', fontSize: 13 }}>Нет фильмов</p>
      )}

      {items.map((m) => (
        <div key={m.id} style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {m.type === 'serial' ? '📺' : '🎬'} {m.title}
              </p>
              <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--tg-theme-hint-color)' }}>
                {m.session_id ? `Сессия #${m.session_id}` : '📚 Библиотека'}
                {' · '}КП {m.kinopoisk_rating ?? '—'} · Клуб {m.club_rating ?? '—'}
              </p>
            </div>
            <button style={{ ...btnStyle(false, true), marginLeft: 8, flexShrink: 0 }} onClick={() => handleDelete(m.id)}>✕</button>
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 6, alignItems: 'center' }}>
            <input
              type="number"
              min={0}
              max={10}
              step={0.1}
              placeholder="Оценка"
              value={editRating[m.id] ?? ''}
              onChange={(e) => setEditRating((prev) => ({ ...prev, [m.id]: e.target.value }))}
              style={{ width: 70, padding: '4px 6px', borderRadius: 6, border: '1px solid #ccc', fontSize: 13 }}
            />
            <button style={btnStyle()} onClick={() => handleSaveRating(m.id)}>Сохранить</button>
          </div>
        </div>
      ))}

      {data && data.pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 8 }}>
          <button style={btnStyle(false)} disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Пред</button>
          <span style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>
            {page} / {data.pages} ({data.total})
          </span>
          <button style={btnStyle(false)} disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>След →</button>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------

const UsersTab: React.FC = () => {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [tab, setTab] = useState<'all' | 'pending'>('all');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [newTgId, setNewTgId] = useState('');
  const [newUsername, setNewUsername] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = tab === 'pending' ? await getPendingUsers() : await getAdminUsers();
      setUsers(data);
    } catch {
      setMsg('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  const handleAllow = async (tgId: number) => {
    try { await allowUser(tgId); load(); } catch { setMsg('Ошибка'); }
  };
  const handleBlock = async (tgId: number) => {
    try { await blockUser(tgId); load(); } catch { setMsg('Ошибка'); }
  };

  const handleAdd = async () => {
    const id = parseInt(newTgId, 10);
    if (!id) return setMsg('Введите Telegram ID');
    const req: CreateUserRequest = { telegram_id: id, username: newUsername || undefined };
    try {
      await createUser(req);
      setMsg('Пользователь добавлен');
      setNewTgId(''); setNewUsername('');
      load();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail ?? 'Ошибка');
    }
  };

  const inputStyle: React.CSSProperties = {
    flex: 1, padding: '6px 10px', borderRadius: 8,
    border: '1px solid var(--tg-theme-secondary-bg-color, #ccc)', fontSize: 13,
    background: 'var(--tg-theme-bg-color, #fff)',
    color: 'var(--tg-theme-text-color, #000)',
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <button style={btnStyle(tab === 'all')} onClick={() => setTab('all')}>Все</button>
        <button style={btnStyle(tab === 'pending')} onClick={() => setTab('pending')}>Ожидают</button>
      </div>
      {msg && <p style={{ color: '#e74c3c', fontSize: 13, marginBottom: 8 }}>{msg}</p>}

      {/* Add user form */}
      <div style={{ ...cardStyle, display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
        <p style={{ margin: 0, fontSize: 12, fontWeight: 600 }}>Добавить вручную</p>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="number"
            placeholder="Telegram ID"
            value={newTgId}
            onChange={(e) => setNewTgId(e.target.value)}
            style={{ ...inputStyle, flex: 1.5 }}
          />
          <input
            type="text"
            placeholder="@username"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
            style={inputStyle}
          />
        </div>
        <button style={btnStyle()} onClick={handleAdd}>Добавить</button>
      </div>

      {loading && <p style={{ color: 'var(--tg-theme-hint-color)' }}>Загрузка…</p>}
      {users.map((u) => (
        <div key={u.id} style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <UserAvatar
                telegramId={u.telegram_id}
                username={u.username}
                firstName={u.first_name}
                size={32}
              />
              <div>
                <span style={{ fontWeight: 600, fontSize: 13 }}>
                  {u.username ? `@${u.username}` : u.first_name ?? '—'}
                </span>
                <span style={{ fontSize: 11, color: 'var(--tg-theme-hint-color)', marginLeft: 6 }}>
                  {u.telegram_id}
                </span>
                {!u.is_allowed && (
                  <span style={{ marginLeft: 6, fontSize: 11, color: '#e74c3c' }}>🔒</span>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {!u.is_allowed && (
                <button style={btnStyle(true)} onClick={() => handleAllow(u.telegram_id)}>✓</button>
              )}
              {u.is_allowed && (
                <button style={btnStyle(false, true)} onClick={() => handleBlock(u.telegram_id)}>✕</button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ---------------------------------------------------------------------------

const ImportTab: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [slot, setSlot] = useState('1');
  const [urlsText, setUrlsText] = useState('');
  const [result, setResult] = useState<BatchImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    getAdminSessions()
      .then(setSessions)
      .catch(() => {});
  }, []);

  const handleImport = async () => {
    const id = parseInt(sessionId, 10);
    if (!id) return setMsg('Выберите сессию');
    const urls = urlsText.split('\n').map((u) => u.trim()).filter(Boolean);
    if (!urls.length) return setMsg('Введите URL');
    setLoading(true);
    setMsg('');
    setResult(null);
    try {
      const res = await batchImport(id, parseInt(slot, 10), urls);
      setResult(res);
    } catch (e: any) {
      setMsg(e?.response?.data?.detail ?? 'Ошибка импорта');
    } finally {
      setLoading(false);
    }
  };

  const selectStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 8,
    border: '1px solid var(--tg-theme-secondary-bg-color, #ccc)', fontSize: 13,
    background: 'var(--tg-theme-bg-color, #fff)',
    color: 'var(--tg-theme-text-color, #000)',
  };

  return (
    <div>
      <p style={sectionTitle}>Batch-импорт фильмов</p>
      {msg && <p style={{ color: '#e74c3c', fontSize: 13, marginBottom: 8 }}>{msg}</p>}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <select style={selectStyle} value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
          <option value="">— Выберите сессию —</option>
          {sessions.map((s) => (
            <option key={s.id} value={s.id}>
              #{s.id} {STATUS_LABELS[s.status] ?? s.status} ({new Date(s.created_at).toLocaleDateString('ru')})
            </option>
          ))}
        </select>

        <select style={{ ...selectStyle, width: 120 }} value={slot} onChange={(e) => setSlot(e.target.value)}>
          <option value="1">Слот 1</option>
          <option value="2">Слот 2</option>
        </select>

        <textarea
          rows={6}
          placeholder={'Ссылки на Кинопоиск (по одной в строке):\nhttps://www.kinopoisk.ru/film/12345/\nhttps://www.kinopoisk.ru/series/67890/'}
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          style={{ ...selectStyle, resize: 'vertical', fontFamily: 'monospace', fontSize: 12 }}
        />

        <button style={btnStyle()} onClick={handleImport} disabled={loading}>
          {loading ? 'Импортируем…' : 'Импортировать'}
        </button>
      </div>

      {result && (
        <div style={{ marginTop: 12 }}>
          <p style={{ fontSize: 13, color: '#27ae60', margin: '0 0 4px' }}>
            ✅ Импортировано: {result.imported.length}
          </p>
          {result.errors.length > 0 && (
            <>
              <p style={{ fontSize: 13, color: '#e74c3c', margin: '0 0 4px' }}>
                ❌ Ошибок: {result.errors.length}
              </p>
              {result.errors.map((e, i) => (
                <div key={i} style={{ ...cardStyle, borderColor: '#e74c3c' }}>
                  <p style={{ margin: 0, fontSize: 12, wordBreak: 'break-all' }}>{e.url}</p>
                  <p style={{ margin: '2px 0 0', fontSize: 11, color: '#e74c3c' }}>{e.reason}</p>
                </div>
              ))}
            </>
          )}
          {result.imported.map((m) => (
            <div key={m.id} style={{ ...cardStyle, borderColor: '#27ae60' }}>
              <p style={{ margin: 0, fontSize: 13 }}>{m.type === 'serial' ? '📺' : '🎬'} {m.title}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------

const LogsTab: React.FC = () => {
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setLogs(await getAdminLogs(100));
    } catch {
      setLogs(['Ошибка загрузки логов']);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <p style={sectionTitle}>Логи API</p>
        <button style={btnStyle(false)} onClick={load}>↻ Обновить</button>
      </div>
      {loading && <p style={{ color: 'var(--tg-theme-hint-color)' }}>Загрузка…</p>}
      <div
        style={{
          fontFamily: 'monospace',
          fontSize: 10,
          lineHeight: 1.5,
          background: 'var(--tg-theme-secondary-bg-color, #f5f5f5)',
          borderRadius: 8,
          padding: '8px 10px',
          maxHeight: 400,
          overflowY: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}
      >
        {[...logs].reverse().map((line, i) => (
          <div key={i} style={{ borderBottom: '1px solid rgba(0,0,0,0.05)', padding: '1px 0' }}>
            {line}
          </div>
        ))}
        {logs.length === 0 && !loading && (
          <span style={{ color: 'var(--tg-theme-hint-color)' }}>Логи отсутствуют</span>
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Stats bar
// ---------------------------------------------------------------------------

const StatsBar: React.FC = () => {
  const [stats, setStats] = useState<DbStats | null>(null);

  useEffect(() => {
    getDbStats().then(setStats).catch(() => {});
  }, []);

  if (!stats) return null;

  const items = [
    { label: 'Сессий', value: stats.sessions },
    { label: 'Фильмов', value: stats.movies },
    { label: 'Юзеров', value: stats.users },
    { label: 'Голосов', value: stats.votes },
    { label: 'Оценок', value: stats.ratings },
  ];

  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        overflowX: 'auto',
        padding: '8px 0 4px',
        marginBottom: 12,
      }}
    >
      {items.map((item) => (
        <div
          key={item.label}
          style={{
            flexShrink: 0,
            textAlign: 'center',
            background: 'var(--tg-theme-secondary-bg-color, #f5f5f5)',
            borderRadius: 8,
            padding: '6px 12px',
          }}
        >
          <p style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{item.value}</p>
          <p style={{ margin: 0, fontSize: 10, color: 'var(--tg-theme-hint-color)' }}>{item.label}</p>
        </div>
      ))}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main AdminPage
// ---------------------------------------------------------------------------

export const AdminPage: React.FC = () => {
  const isAdmin = useAppStore((s) => s.isAdmin);
  const [activeTab, setActiveTab] = useState<AdminTab>('sessions');

  if (!isAdmin) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <p style={{ fontSize: 24 }}>🚫</p>
        <p style={{ fontWeight: 600 }}>Доступ только для администраторов</p>
      </div>
    );
  }

  const tabs: { key: AdminTab; label: string; icon: string }[] = [
    { key: 'sessions', label: 'Сессии', icon: '📋' },
    { key: 'movies', label: 'Фильмы', icon: '🎬' },
    { key: 'users', label: 'Юзеры', icon: '👥' },
    { key: 'import', label: 'Импорт', icon: '📥' },
    { key: 'logs', label: 'Логи', icon: '📜' },
  ];

  return (
    <div style={{ padding: '12px 16px', paddingBottom: 24 }}>
      <h2 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 700 }}>⚙️ Управление</h2>

      <StatsBar />

      {/* Tab strip */}
      <div
        style={{
          display: 'flex',
          overflowX: 'auto',
          gap: 6,
          marginBottom: 12,
          paddingBottom: 4,
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            style={{
              flexShrink: 0,
              padding: '6px 10px',
              borderRadius: 20,
              border: 'none',
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: activeTab === t.key ? 600 : 400,
              background:
                activeTab === t.key
                  ? 'var(--tg-theme-button-color, #2481cc)'
                  : 'var(--tg-theme-secondary-bg-color, #f0f0f0)',
              color:
                activeTab === t.key ? '#fff' : 'var(--tg-theme-text-color, #000)',
            }}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'sessions' && <SessionsTab />}
      {activeTab === 'movies' && <MoviesTab />}
      {activeTab === 'users' && <UsersTab />}
      {activeTab === 'import' && <ImportTab />}
      {activeTab === 'logs' && <LogsTab />}
    </div>
  );
};
