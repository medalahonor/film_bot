# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Telegram-бот для киноклуба: сбор предложений фильмов через ссылки на Кинопоиск, голосование (Telegram Poll), рейтинги (1-10) и лидерборд. Python 3.12, aiogram 3.x, PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic.

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

Alembic настроен на `src/alembic/`, `prepend_sys_path = src`. URL базы берётся из `bot.config` (env var `DATABASE_URL`), а не из alembic.ini.

## Architecture

### Слоистая структура (src/bot/)

```
handlers/  → repositories + services + formatters + keyboards + utils
                 ↓
           database/models.py
```

- **handlers/** — тонкие обработчики (aiogram Router). Каждый handler-модуль создаёт `router = Router()`, регистрируемый в `main.py`. Хэндлеры не импортируют друг друга.
- **database/repositories.py** — все повторяющиеся DB-запросы (get/create group, user, session, movie CRUD, пагинация).
- **database/models.py** — SQLAlchemy ORM-модели: User, Group, Admin, Session, SessionStatus, Movie, Vote, Rating. Все relationship используют `lazy="selectin"`.
- **database/status_manager.py** — статусы сессий (`collecting` → `voting` → `rating` → `completed`) с seed-инициализацией.
- **database/session.py** — async engine, sessionmaker (`AsyncSessionLocal`), `init_db()`, `get_session()`.
- **services/kinopoisk.py** — парсинг данных фильма через GraphQL API Кинопоиска (`graphql.kinopoisk.ru`).
- **services/voting_logic.py** — подсчёт голосов, определение победителя, форматирование результатов.
- **formatters.py** — форматирование текста для пользователя.
- **keyboards.py** — все reply/inline клавиатуры и callback-константы (BTN_*, get_*_keyboard).
- **utils.py** — FSM-утилиты: `try_delete_message`, `replace_bot_message`, `abort_flow`, `finish_flow`. Bot message ID хранится в FSM data как `bot_message_id`.
- **middlewares.py** — AccessCheckMiddleware (группа по GROUP_ID, приват только для админов, фильтр топиков), ErrorLoggingMiddleware, PollAnswerLoggingMiddleware.
- **log_handler.py** — InMemoryLogHandler (deque на 200 записей) для просмотра логов админом.

### Точка входа

`src/bot/main.py` — создаёт Bot, Dispatcher, регистрирует middleware (Error → Access) и 6 router-ов (session, proposals, voting, rating, leaderboard, admin). `PYTHONPATH=/app/src` (Dockerfile ENV).

### Handlers overview

| Модуль | Назначение |
|--------|-----------|
| session.py | /start, создание/отмена сессии, /help, универсальный cancel (BTN_CANCEL) |
| proposals.py | Предложения фильмов (reply на закреп или кнопка), слот-выбор через inline callback |
| voting.py | Запуск/завершение голосования, переголосование, PollAnswer обработка |
| rating.py | Выставление рейтингов (inline 1-10), пересчёт club_rating |
| leaderboard.py | /leaderboard с пагинацией, /search, статистика |
| admin.py | Админ-панель в ЛС: управление сессиями, фильмами, batch-импорт, логи |

### DB access pattern

Хэндлеры используют `async with AsyncSessionLocal() as db:` напрямую (не DI). Все query-функции принимают `db: AsyncSession` первым аргументом.

## Conventions

- **Запрет перекрёстных импортов хэндлеров.** Общий код — в repositories.py, formatters.py, utils.py.
- **Максимум 30-40 строк на функцию.** Длинные — разбивать на `_helper`-функции.
- **snake_case** для функций/переменных, **PascalCase** для классов, **SCREAMING_SNAKE_CASE** для констант, **_prefix** для приватных хелперов.
- FSM-потоки: удалять сообщение пользователя на каждом шаге, заменять prompt бота через `replace_bot_message`.
- Все клавиатуры — в keyboards.py. Callback data формат: `"prefix:param1:param2"`.

## Environment Variables

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_GROUP_IDS` (через запятую, опционально `:topic_id` после каждой группы), `TELEGRAM_ADMIN_IDS` (через запятую), `DATABASE_URL`, `DB_PASSWORD` (для docker-compose).
