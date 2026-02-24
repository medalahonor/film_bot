# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram-бот для киноклуба с Telegram WebApp: предложение фильмов по ссылкам на Кинопоиск, голосование, рейтинги (1-10) и лидерборд. Бот выступает точкой входа (кнопка открытия WebApp), вся бизнес-логика — в FastAPI + React SPA.

Стек: Python 3.12, aiogram 3.x, FastAPI, PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic, React 18 + TypeScript + Vite.

## Commands

### Docker (основной способ запуска)
```bash
make up          # запуск (docker compose up -d)
make down        # остановка
make restart     # перезапуск контейнера бота
make update      # git pull + пересборка + перезапуск
make logs-bot    # логи бота
make status      # статус контейнеров
```

### Локальная разработка (без Docker)
```bash
pip install -r requirements.txt
alembic upgrade head
python -m bot.main                # запуск (PYTHONPATH=src)
```

### Миграции
```bash
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

Alembic настроен на `src/alembic/`, `prepend_sys_path = src`. URL базы берётся из переменной окружения `DATABASE_URL` напрямую (через `os.environ`), а не из alembic.ini.

## Architecture

### Общая структура

Три независимых сервиса, каждый в своём Docker-контейнере:

```
Telegram user
     │
     ├─→ Bot (aiogram)          ← /start, /help, /admin → открывает WebApp
     │
     └─→ WebApp (React SPA)     ← nginx раздаёт статику, собранную внутри Docker
              │
              └─→ API (FastAPI) ← вся бизнес-логика, аутентификация через Telegram initData
                       │
                       └─→ PostgreSQL ← единая БД для бота и API
```

### src/bot/ — Telegram-бот (aiogram)

Бот минималистичен: только регистрация команд и открытие WebApp. Не работает с БД напрямую — вся бизнес-логика в API.

- **handlers/session.py** — `/start` (отправляет inline-кнопку WebApp), `/help`.
- **handlers/admin.py** — `/admin` (отправляет ссылку на WebApp-панель, только для ADMIN_IDS).
- **keyboards.py** — `get_webapp_keyboard(url)` → InlineKeyboardMarkup с кнопкой «Открыть киноклуб» (WebAppInfo).
- **middlewares.py** — `AccessCheckMiddleware` (фильтр по GROUP_IDS, topic_id, приват только для ADMIN_IDS), `ErrorLoggingMiddleware`.
- **log_handler.py** — `InMemoryLogHandler` (deque на 200 записей), `get_recent_logs(n)` — только для логов бот-процесса.
- **formatters.py** — `format_movie_title`, `format_user_display_name`, `format_year_suffix`.
- **utils.py** — FSM-утилиты: `try_delete_message`, `replace_bot_message`, `abort_flow`, `finish_flow`.

### Точка входа бота

`src/bot/main.py` — создаёт Bot, Dispatcher, регистрирует middleware (Error → Access) и 2 router-а: `session`, `admin`. `PYTHONPATH=/app/src` (Dockerfile ENV).

### Bot handlers overview

| Модуль | Команды |
|--------|---------|
| session.py | `/start` — WebApp кнопка; `/help` — справка |
| admin.py | `/admin` — ссылка на WebApp-панель (только ADMIN_IDS) |

### src/api/ — FastAPI (вся бизнес-логика)

Аутентификация: `X-Telegram-InitData` header → HMAC-SHA256 валидация → резолв в `User`.

**Модели и сервисы** (`src/api/`):

- **database/models.py** — SQLAlchemy ORM-модели: `User`, `Admin`, `Session`, `SessionStatus`, `Movie`, `Vote`, `Rating`. Все relationship используют `lazy="selectin"`.
- **database/repositories.py** — DB-запросы (get/create user, session, movie CRUD, пагинация). Принимают `db: AsyncSession` первым аргументом.
- **database/status_manager.py** — константы статусов (`collecting` → `voting` → `rating` → `completed`) и seed-инициализация.
- **database/session.py** — async engine, sessionmaker (`AsyncSessionLocal`), `init_db()`. Читает `DATABASE_URL` из `api.config`.
- **services/kinopoisk.py** — парсинг фильма через GraphQL API Кинопоиска (`graphql.kinopoisk.ru`): `parse_movie_data(url)`, `get_movie_by_id(id)`, `get_series_by_id(id)`, `suggest_search(query)`.
- **services/_graphql_queries.py** — GraphQL-запросы для Кинопоиска (query allowlisting).
- **log_handler.py** — `InMemoryLogHandler` (deque на 200 записей), `get_recent_logs(n)` — для логов API-процесса, читается через `/api/admin/logs`.

**Роутеры** (`/api/*`):

| Роутер | Prefix | Назначение |
|--------|--------|-----------|
| sessions.py | `/api/sessions` | CRUD сессий, переходы статусов (finalize-voting, start-runoff, finalize-runoff, rate) |
| movies.py | `/api/movies` | Propose, replace, delete, update club_rating |
| votes.py | `/api/votes` | Submit голосов, finalize, my votes |
| ratings.py | `/api/ratings` | Submit рейтинга (upsert), пересчёт club_rating, my ratings |
| leaderboard.py | `/api/leaderboard` | Пагинированный топ по club_rating, поиск |
| kinopoisk.py | `/api/kinopoisk` | suggest(query), movie(id), parse(url) |
| users.py | `/api/users` | Proxy аватаров Telegram (in-memory cache) |
| admin.py | `/api/admin` | Управление users (allow/block), sessions, movies, просмотр логов |

**Зависимости** (`dependencies.py`):
- `get_db()` — AsyncSession из пула.
- `get_current_user(db, tg_user)` — резолв Telegram user → DB User (создаёт с `is_allowed=False` если нет).
- `get_admin(user)` — требует `telegram_id` в `ADMIN_IDS`.

**Уведомления** (`telegram_notify.py`) — best-effort отправка в Telegram-группу из API (aiohttp, raw Bot API). Учитывает `topic_id` из конфига.

**DB access pattern в API**: через `Depends(get_db)` (из `api.dependencies`). Бизнес-логика в роутерах, query-утилиты в `api.database.repositories`.

### src/api/schemas/ — Pydantic-схемы

`movie.py`, `session.py`, `user.py`, `vote.py`, `rating.py`, `kinopoisk.py`, `leaderboard.py` — Request/Response модели для каждого роутера.

### web/ — React SPA (Telegram WebApp)

Собирается **внутри Docker** (multi-stage `Dockerfile.nginx`), раздаётся nginx. Node.js на хосте не нужен.

```
web/src/
├── api/          # Axios-клиент + функции для каждого роутера API
├── components/   # TabBar, MovieCard, MovieCardFull, Poster, SearchBar,
│                 # StarRating, UserAvatar, Loader
├── hooks/        # useTelegram, useSession, useMovies, useVoting
├── pages/        # SessionPage, ProposePage, VotePage, RatingPage,
│                 # LeaderboardPage, AdminPage, AccessDeniedPage
├── store/        # useAppStore (Zustand): groupId, currentUser, isAdmin,
│                 # isAccessDenied, currentSession
└── types/        # Movie, Session, SuggestResult, LeaderboardEntry, ...
```

Аутентификация: `Telegram.WebApp.initData` → заголовок `X-Telegram-InitData` в каждом запросе.

### Контейнеризация

| Файл | Сервис | База |
|------|--------|------|
| `Dockerfile` | bot | python:3.12-slim; CMD: alembic upgrade head + python -m bot.main |
| `Dockerfile.api` | api | python:3.12-slim; CMD: uvicorn api.main:app --workers 2 |
| `Dockerfile.nginx` | nginx | Stage 1: node:20-alpine (npm run build); Stage 2: nginx:1.27-alpine |

### DB access pattern

API использует `Depends(get_db)` из `api.dependencies`. Все query-функции в `api.database.repositories` принимают `db: AsyncSession` первым аргументом. Бот к БД не обращается.

## Conventions

- **Запрет перекрёстных импортов.** `bot/` не импортирует из `api/`. Общий DB-код — в `api/database/`, сервисы — в `api/services/`.
- **Максимум 30-40 строк на функцию.** Длинные — разбивать на `_helper`-функции.
- **snake_case** для функций/переменных, **PascalCase** для классов, **SCREAMING_SNAKE_CASE** для констант, **_prefix** для приватных хелперов.
- Все клавиатуры бота — в `keyboards.py`.
- API-роутеры: внутренние хелперы именовать с `_` (например `_session_to_response`, `_resolve_group`).
- Новые API-эндпоинты добавляются в соответствующий роутер в `src/api/routers/`, схемы — в `src/api/schemas/`.
- Новые сервисы (внешние API, бизнес-логика) — в `src/api/services/`.
- ORM-модели и query-функции — в `src/api/database/`.

## Development Workflow

Воркфлоу состоит из четырёх последовательных фаз. Новая фаза не начинается до закрытия всех открытых вопросов текущей.

---

### Фаза 1: Планирование

**Цель:** превратить сырую идею в точное техническое задание без слепых пятен.

#### Процесс декомпозиции идеи

Идея проходит несколько слоёв уточнения — от общего к конкретному:

1. **Зачем?** — проблема, которую решаем. Кто пользователь, какой сценарий.
2. **Что?** — желаемое поведение системы с точки зрения пользователя (user stories).
3. **Как?** — технические решения: модели данных, API, состояния FSM, изменения БД.
4. **Что не делаем?** — явный scope exclusion: что намеренно откладываем на потом.

#### Чеклист планирования

- [ ] Все happy path сценарии описаны
- [ ] Corner cases и edge cases выявлены (пустые состояния, конкурентный доступ, сетевые ошибки)
- [ ] Описано поведение при ошибках (что видит пользователь)
- [ ] Если затрагивает UX — рассмотрено ≥2 варианта реализации с обоснованием выбора
- [ ] Изменения схемы БД определены (нужна ли миграция)
- [ ] Зависимости от внешних сервисов учтены (Кинопоиск API, Telegram Poll API)
- [ ] Scope exclusion зафиксирован явно

**Definition of Done:** все пункты чеклиста закрыты, нет открытых вопросов с пометкой "разберёмся по ходу".

---

### Фаза 2: Разработка

**Цель:** реализовать ТЗ чистым, тестируемым кодом.

#### Принципы функционального стиля (для Python-контекста)

- **Чистые функции где возможно** — функция зависит только от своих аргументов, не мутирует внешнее состояние, возвращает результат. Побочные эффекты (запись в БД, отправка сообщений) изолированы на верхнем уровне хэндлера.
- **Явные зависимости** — никаких глобальных переменных внутри функций. Всё, что нужно функции, передаётся через аргументы.
- **Иммутабельность данных** — предпочитать создание нового объекта изменению существующего. Использовать `dataclass(frozen=True)` или `TypedDict` для передачи данных между слоями.
- **Type hints как контракт** — каждая публичная функция имеет аннотации аргументов и возвращаемого значения. Это документация и инструмент статического анализа.
- **Одна ответственность** — функция делает одно дело. Если название содержит "и" (`fetch_and_save`), это сигнал к разбивке.
- **Самодокументируемость** — имена функций и переменных описывают намерение, а не механизм (`get_top_rated_movies`, а не `get_movies_sorted`). Комментарий нужен только там, где *почему* неочевидно из кода.

#### Definition of Done для разработки

- [ ] Код соответствует принципам выше и конвенциям проекта (Conventions)
- [ ] Нет функций длиннее 40 строк
- [ ] Type hints расставлены на всех публичных функциях
- [ ] Перекрёстные импорты хэндлеров отсутствуют
- [ ] Если изменилась архитектура — обновлён раздел Architecture в CLAUDE.md (новые модули, изменения слоёв, новые паттерны доступа к БД)

---

### Фаза 3: Code Review

**Цель:** поймать проблемы до попадания в `main`. Самые дешёвые баги — те, что не прошли ревью.

#### Чеклист ревьюера

- [ ] Логика соответствует ТЗ из фазы планирования
- [ ] Нет очевидных ошибок (off-by-one, неправильные условия, утечки соединений БД)
- [ ] Edge cases из планирования реально обработаны в коде
- [ ] Нет дублирования кода, который уже есть в repositories/utils/formatters
- [ ] Тесты написаны и покрывают заявленные сценарии
- [ ] Нет потенциальных уязвимостей (SQL injection через raw query, необработанный пользовательский ввод)
- [ ] CLAUDE.md актуален, если архитектура изменилась

---

### Фаза 4: Тестирование

**Цель:** подтвердить корректность поведения через автоматические тесты.

#### Стратегия тестирования

- **Unit-тесты** покрывают чистые функции: бизнес-логику (`api/services/kinopoisk.py`, `bot/formatters.py`), парсинг данных, трансформации.
- **Интеграционные тесты** покрывают слой репозиториев с тестовой БД (SQLite in-memory или PostgreSQL в Docker).
- **Тесты хэндлеров** — через `aiogram` test utilities, проверяют сценарии FSM-потоков.

#### Приоритеты покрытия

1. Бизнес-логика (подсчёт голосов, рейтингов, лидерборд) — покрытие близко к 100%
2. Репозитории — CRUD-операции, граничные случаи (пустая БД, дубликаты)
3. Хэндлеры — happy path + основные error path

#### Именование тестов

```
test_<что тестируем>_<при каком условии>_<ожидаемый результат>
# Пример:
test_calculate_winner_with_tie_returns_first_alphabetically
test_get_leaderboard_empty_db_returns_empty_list
```

#### Definition of Done для тестирования

- [ ] Все новые публичные функции бизнес-логики покрыты тестами
- [ ] Тесты проходят (`pytest`)
- [ ] Нет тестов, которые проходят случайно (flaky tests)

---

### Фаза 5: Исправление багов

**Цель:** устранить баг надёжно, не сломав остальное.

#### Протокол фикса

1. **Воспроизвести** — понять точный сценарий воспроизведения бага.
2. **Написать падающий тест** — тест описывает ожидаемое поведение и падает на текущем коде.
3. **Починить** — минимальное изменение кода, которое делает тест зелёным.
4. **Прогнать регрессию** — `pytest` целиком. Новый фикс не должен ломать существующие тесты.
5. **Post-mortem (для серьёзных багов)** — ответить на вопрос: "Почему этот баг прошёл через планирование и тестирование?" При необходимости закрыть пробел в тест-покрытии или в чеклисте планирования.

---

## Environment Variables

- `TELEGRAM_BOT_TOKEN` — токен бота от BotFather.
- `TELEGRAM_GROUP_IDS` — через запятую, опционально `:topic_id` после каждой группы (например `-100123:456,-100789`).
- `TELEGRAM_ADMIN_IDS` — через запятую, telegram_id администраторов.
- `DATABASE_URL` — `postgresql+asyncpg://user:pass@host/db`.
- `DB_PASSWORD` — пароль БД (используется в docker-compose для подстановки в DATABASE_URL).
- `WEBAPP_URL` — URL React SPA (вставляется в кнопку `/start`).
- `WEBAPP_ORIGIN` — CORS origin для FastAPI (например `https://example.com`).
