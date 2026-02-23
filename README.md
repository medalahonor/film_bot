# Film Club Telegram Bot

Телеграм-бот для автоматизации проведения киноклуба: сбор предложений фильмов, голосование, рейтинговая система и таблица лидеров. Включает веб-приложение (Telegram WebApp) для просмотра результатов.

## Возможности

### Для участников (в группе)
- Предложение фильмов через reply на закрепленное сообщение
- Голосование за фильмы с помощью Telegram Poll
- Выставление рейтингов после просмотра (1-10)
- Просмотр таблицы лидеров с пагинацией
- Поиск фильмов по названию
- Веб-приложение внутри Telegram (WebApp)

### Для администраторов (в личных сообщениях)
- Добавление фильмов-победителей вручную (для истории)
- Добавление рейтингов для исторических фильмов
- Редактирование и удаление фильмов
- Экспорт таблицы лидеров
- Управление сессиями

## Технологии

- **Python 3.12** + **aiogram 3.x** — Telegram Bot
- **FastAPI** + **uvicorn** — REST API для WebApp
- **React 18** + **TypeScript** + **Vite** — фронтенд (Telegram WebApp)
- **PostgreSQL 16** + **SQLAlchemy 2.0** (async) + **Alembic** — база данных
- **Docker Compose** — контейнеризация (бот, API, БД, nginx)
- **nginx** + **Let's Encrypt** — reverse proxy, SSL/TLS, раздача SPA

---

## Деплой на VPS

### Требования

- VPS с Ubuntu 22.04+ (или другой Linux), минимум 1 ГБ RAM, 10 ГБ диска
- Домен, DNS A-запись которого указывает на IP сервера
- SSH-доступ с правами root

### 1. Подготовка сервера (один раз, от root)

#### Установка git

```bash
apt update && apt install -y git
```

#### Установка Docker

```bash
apt update && apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

#### Создание пользователя bot (опционально, рекомендуется)

```bash
adduser --disabled-password --gecos "" --shell /usr/sbin/nologin bot
usermod -aG docker bot
```

### 2. Клонирование и настройка

```bash
git clone <repository-url> ~/film_bot
cd ~/film_bot
cp .env.example .env
nano .env
```

Заполните `.env`:

```dotenv
# Telegram
TELEGRAM_BOT_TOKEN=токен_от_BotFather
TELEGRAM_GROUP_IDS=-1001234567890
TELEGRAM_ADMIN_IDS=123456789

# База данных
DB_PASSWORD=надёжный_пароль

# Домен и SSL
DOMAIN=yourdomain.com
WEBAPP_URL=https://yourdomain.com
CERTBOT_EMAIL=admin@yourdomain.com
```

> **Как получить Group ID:** добавьте [@userinfobot](https://t.me/userinfobot) в группу — он пришлёт ID.
> **Как получить свой ID:** напишите [@userinfobot](https://t.me/userinfobot) в личку.

### 3. Первый деплой

```bash
make setup
```

Команда выполнит всё автоматически:
1. Проверит `.env` и наличие всех необходимых переменных
2. Проверит prerequisites (Docker)
3. Получит SSL-сертификат от Let's Encrypt
4. Соберёт Docker-образы (включая React SPA внутри образа nginx) и запустит сервисы
5. Настроит cron для авторенивала сертификата (ежедневно в 03:00)

После завершения WebApp доступен по адресу `https://yourdomain.com`.

---

## Обновление

При появлении новой версии в репозитории:

```bash
make update
```

Команда выполнит:
- `git pull`
- `docker compose up -d --build` для пересборки образов (React SPA пересобирается внутри образа nginx) и перезапуска контейнеров
- Перезагрузку nginx, если изменился шаблон конфигурации

---

## Смена домена

```bash
# 1. Обновите DOMAIN, WEBAPP_URL и CERTBOT_EMAIL в .env

# 2. Получите сертификат для нового домена
docker compose stop nginx
certbot certonly --standalone --non-interactive --agree-tos \
    --email admin@newdomain.com --domain newdomain.com

# 3. Перезапустите — nginx подхватит новый DOMAIN из .env
docker compose up -d
```

---

## Справочник команд

| Команда | Описание |
|---------|----------|
| `make setup` | Первый деплой: SSL + сборка web + запуск |
| `make update` | Обновление: pull + rebuild + restart |
| `make up` | Запуск всех сервисов |
| `make down` | Остановка всех сервисов |
| `make restart` | Перезапуск контейнера бота |
| `make build-web` | Пересборка nginx-образа (включает React SPA) |
| `make reload-nginx` | Перезагрузить конфиг nginx без рестарта |
| `make logs` | Логи всех сервисов |
| `make logs-bot` | Логи бота |
| `make logs-api` | Логи API |
| `make logs-nginx` | Логи nginx |
| `make status` | Статус контейнеров |
| `make build` | Пересборка docker-образов |
| `make clean` | Удалить контейнеры и образы (БД сохраняется) |
| `make clean-all` | Полная очистка включая данные БД (ОСТОРОЖНО!) |

---

## Локальная разработка

### Запуск через Docker Compose

```bash
cp .env.example .env  # заполните токены, домен можно оставить localhost
make up               # соберёт образы (включая React SPA) и запустит сервисы
```

### Запуск без Docker

1. Установите PostgreSQL 16 и создайте БД
2. Установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Примените миграции:

```bash
alembic upgrade head
```

4. Запустите бота:

```bash
PYTHONPATH=src python -m bot.main
```

### Создание миграций

```bash
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

---

## Workflow использования

### 1. Создание сессии киноклуба

В группе любой участник отправляет `/new_session`. Бот закрепит сообщение для сбора предложений.

### 2. Предложение фильмов

Ответьте (reply) на закреп со ссылкой на Кинопоиск:

```
https://www.kinopoisk.ru/film/301/
https://www.kinopoisk.ru/film/326/
```

Затем выберите слот через inline-кнопки.

### 3. Голосование

```
/start_voting   — создать Telegram Poll
/finish_voting  — подвести итоги
```

### 4. Рейтинги

После просмотра:

```
/rate
```

### 5. Таблица лидеров

```
/leaderboard
/search Матрица
```

---

## Архитектура

```
film_bot/
├── src/
│   ├── bot/             # Telegram-бот (aiogram)
│   │   ├── handlers/    # Обработчики команд
│   │   ├── services/    # Кинопоиск API, логика голосований
│   │   ├── database/    # ORM-модели, репозитории, миграции
│   │   └── main.py
│   ├── api/             # FastAPI (для WebApp)
│   └── alembic/         # Миграции БД
├── web/                 # React SPA (Telegram WebApp); собирается внутри Docker
├── nginx/
│   └── templates/
│       └── filmbot.conf.template  # Шаблон конфига (DOMAIN из .env)
├── scripts/
│   ├── setup.sh         # Первый деплой
│   └── update.sh        # Обновление
├── docker-compose.yml
├── Dockerfile           # Bot
├── Dockerfile.api       # API
├── Dockerfile.nginx     # nginx + multi-stage сборка React SPA
└── Makefile
```

## Лицензия

MIT
