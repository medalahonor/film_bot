.PHONY: up down restart update logs status build clean \
        setup build-web reload-nginx logs-nginx logs-api

# ── Первоначальный деплой ─────────────────────────────────────────────────────

# Первый деплой: валидация .env, SSL-сертификат, сборка образов, запуск сервисов
setup:
	sudo bash scripts/setup.sh

# ── Обновление ────────────────────────────────────────────────────────────────

# Обновление: git pull + пересборка образов (включая фронт) + рестарт контейнеров
update:
	bash scripts/update.sh

# ── Управление сервисами ──────────────────────────────────────────────────────

# Запуск всех сервисов
up:
	docker compose up -d

# Остановка всех сервисов
down:
	docker compose down

# Перезапуск с пересозданием контейнера бота
restart:
	docker compose up -d --force-recreate bot

# ── Сборка ────────────────────────────────────────────────────────────────────

# Пересборка nginx-образа (включает сборку React SPA внутри Docker)
build-web:
	docker compose build --no-pull nginx

# Пересборка docker-образов без запуска
build:
	docker compose build --no-pull

# ── nginx ─────────────────────────────────────────────────────────────────────

# Перезагрузить конфиг nginx без рестарта контейнера
reload-nginx:
	docker compose exec nginx nginx -s reload

# ── Логи ──────────────────────────────────────────────────────────────────────

# Логи всех сервисов (Ctrl+C для выхода)
logs:
	docker compose logs -f

# Логи бота
logs-bot:
	docker compose logs -f bot

# Логи API
logs-api:
	docker compose logs -f api

# Логи nginx
logs-nginx:
	docker compose logs -f nginx

# ── Статус и очистка ──────────────────────────────────────────────────────────

# Статус контейнеров
status:
	docker compose ps

# Удаление контейнеров и образов (данные БД сохраняются)
clean:
	docker compose down --rmi local

# Полная очистка включая данные БД (ОСТОРОЖНО!)
clean-all:
	docker compose down --rmi local -v
