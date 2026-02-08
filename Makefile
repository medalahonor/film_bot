.PHONY: up down restart update logs status build clean

# Запуск всех сервисов
up:
	docker compose up -d

# Остановка всех сервисов
down:
	docker compose down

# Перезапуск с пересозданием контейнера (подхватывает новый образ и volume-изменения)
restart:
	docker compose up -d --force-recreate bot

# Полное обновление: pull + пересборка + перезапуск
update:
	git pull
	docker compose up -d --build

# Просмотр логов (Ctrl+C для выхода)
logs:
	docker compose logs -f

# Логи только бота
logs-bot:
	docker compose logs -f bot

# Статус контейнеров
status:
	docker compose ps

# Пересборка образа без запуска
build:
	docker compose build

# Полная очистка (контейнеры + образы, БД сохраняется)
clean:
	docker compose down --rmi local

# Полная очистка включая данные БД (ОСТОРОЖНО!)
clean-all:
	docker compose down --rmi local -v
