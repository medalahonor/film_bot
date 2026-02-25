import React, { useCallback, useEffect, useState } from 'react';
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
  getAdminSessions,
  getAdminSessionMovies,
  getAdminUsers,
  getDbStats,
  getPendingUsers,
  setSessionWinner,
  updateClubRating,
  type BatchImportResult,
  type CreateUserRequest,
  type DbStats,
} from '../../api/admin';
import { finalizeVotes } from '../../api/votes';
import type { Movie, Session, UserResponse } from '../../types';
import { UserAvatar } from '../../components/UserAvatar';

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

// ---------------------------------------------------------------------------
// Sub-sections
// ---------------------------------------------------------------------------

const SessionsTab: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

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

  const handleNext = async (session: Session) => {
    if (session.status === 'voting') {
      try {
        const result = await finalizeVotes(session.id);
        if (result.runoff_slot1_ids || result.runoff_slot2_ids) {
          setMsg('⚡ Ничья! Запущено переголосование');
        } else {
          setMsg('✅ Голосование завершено, победители определены');
        }
        load();
      } catch (e: any) {
        setMsg(e?.response?.data?.detail ?? 'Ошибка');
      }
      return;
    }
    const next = STATUS_NEXT[session.status];
    if (!next) return;
    try {
      await changeSessionStatus(session.id, next);
      setMsg(`Статус изменён → ${next}`);
      load();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail ?? 'Ошибка');
    }
  };

  const handleRevert = async (session: Session) => {
    const prev = STATUS_PREV[session.status];
    if (!prev) return;
    if (!window.confirm(`Откатить статус к "${STATUS_LABELS[prev]}"?`)) return;
    try {
      await changeSessionStatus(session.id, prev);
      setMsg(`Статус откачен → ${STATUS_LABELS[prev]}`);
      load();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail ?? 'Ошибка');
    }
  };

  const handleDelete = async (id: number) => {
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
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <p style={sectionTitle}>Сессии</p>
        <button style={btnStyle()} onClick={handleCreate}>+ Создать</button>
      </div>
      {msg && <p style={{ color: '#e74c3c', fontSize: 13, marginBottom: 8 }}>{msg}</p>}
      {loading && <p style={{ color: 'var(--tg-theme-hint-color)' }}>Загрузка…</p>}
      {sessions.map((s) => (
        <div key={s.id} style={cardStyle}>
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
                {new Date(s.created_at).toLocaleString('ru')}
              </p>
            </div>
            <div style={{ display: 'flex', gap: 4, flexShrink: 0, marginLeft: 6 }}>
              {STATUS_PREV[s.status] && (
                <button
                  style={{ ...btnStyle(false), padding: '6px 8px', fontSize: 12 }}
                  onClick={() => handleRevert(s)}
                  title={`Откатить к ${STATUS_LABELS[STATUS_PREV[s.status]]}`}
                >
                  ↩
                </button>
              )}
              {STATUS_NEXT[s.status] && (
                <button style={btnStyle(true)} onClick={() => handleNext(s)}>
                  → {STATUS_LABELS[STATUS_NEXT[s.status]]}
                </button>
              )}
              {s.status !== 'completed' && (
                <button style={btnStyle(false, true)} onClick={() => handleDelete(s.id)}>✕</button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// ---------------------------------------------------------------------------

const MoviesTab: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [editRating, setEditRating] = useState<Record<number, string>>({});

  useEffect(() => {
    getAdminSessions()
      .then((data) => {
        setSessions(data);
        if (data.length > 0) setSelectedSessionId(String(data[0].id));
      })
      .catch(() => {});
  }, []);

  const load = useCallback(async (sessionId: string) => {
    if (!sessionId) return;
    setLoading(true);
    setMsg('');
    try {
      const data = await getAdminSessionMovies(parseInt(sessionId, 10));
      setMovies(data);
    } catch {
      setMsg('Ошибка загрузки фильмов');
      setMovies([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedSessionId) load(selectedSessionId);
  }, [selectedSessionId, load]);

  const handleDelete = async (id: number) => {
    if (!window.confirm('Удалить фильм из сессии?')) return;
    try {
      await deleteMovie(id);
      setMsg('Удалено');
      load(selectedSessionId);
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
      load(selectedSessionId);
    } catch {
      setMsg('Ошибка');
    }
  };

  const selectStyle: React.CSSProperties = {
    width: '100%', padding: '6px 10px', borderRadius: 8, marginBottom: 10,
    border: '1px solid var(--tg-theme-secondary-bg-color, #ccc)', fontSize: 13,
    background: 'var(--tg-theme-bg-color, #fff)',
    color: 'var(--tg-theme-text-color, #000)',
  };

  return (
    <div>
      <p style={sectionTitle}>Фильмы сессии</p>
      <select
        style={selectStyle}
        value={selectedSessionId}
        onChange={(e) => setSelectedSessionId(e.target.value)}
      >
        <option value="">— Выберите сессию —</option>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            #{s.id} {STATUS_LABELS[s.status] ?? s.status} ({new Date(s.created_at).toLocaleDateString('ru')})
          </option>
        ))}
      </select>
      {msg && <p style={{ color: '#e74c3c', fontSize: 13, marginBottom: 8 }}>{msg}</p>}
      {loading && <p style={{ color: 'var(--tg-theme-hint-color)' }}>Загрузка…</p>}
      {!loading && selectedSessionId && movies.length === 0 && (
        <p style={{ color: 'var(--tg-theme-hint-color)', fontSize: 13 }}>Нет фильмов</p>
      )}
      {movies.map((m) => (
        <div key={m.id} style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, fontWeight: 600, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {m.type === 'serial' ? '📺' : '🎬'} {m.title}
              </p>
              <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--tg-theme-hint-color)' }}>
                Слот {m.slot} · КП {m.kinopoisk_rating ?? '—'} · Клуб {m.club_rating ?? '—'}
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
          style={{
            ...selectStyle,
            resize: 'vertical',
            fontFamily: 'monospace',
            fontSize: 12,
          }}
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
