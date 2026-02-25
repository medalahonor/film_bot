#!/bin/bash
# Первоначальный деплой: валидация .env, SSL, сборка образов, запуск сервисов
# Использование: make setup (или: sudo bash scripts/setup.sh)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ─── 1. Проверка .env ─────────────────────────────────────────────────────────

ENV_FILE="$PROJECT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: файл .env не найден: $ENV_FILE"
    echo "       Скопируйте .env.example в .env и заполните значения."
    exit 1
fi

set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

REQUIRED_VARS=(DOMAIN TELEGRAM_BOT_TOKEN DB_PASSWORD TELEGRAM_GROUP_IDS TELEGRAM_ADMIN_IDS)
MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        MISSING+=("$var")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "ERROR: отсутствуют обязательные переменные в .env:"
    for var in "${MISSING[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

if [[ -z "${CERTBOT_EMAIL:-}" ]]; then
    read -r -p "Email для уведомлений Let's Encrypt: " CERTBOT_EMAIL
    if [[ -z "$CERTBOT_EMAIL" ]]; then
        echo "ERROR: email обязателен для certbot."
        exit 1
    fi
fi

echo "Домен:  $DOMAIN"
echo "Email:  $CERTBOT_EMAIL"

# ─── 2. Проверка prerequisites ────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
    echo "ERROR: docker не найден. Установите Docker."
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "ERROR: docker compose (v2) не найден."
    exit 1
fi

# ─── 3. SSL-сертификат ────────────────────────────────────────────────────────

echo ""
echo "=== SSL-сертификат ==="

CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"

if [[ -f "$CERT_PATH" ]]; then
    echo "Сертификат для $DOMAIN уже существует — пропускаем certbot."
else
    echo "Получаем SSL-сертификат для $DOMAIN..."

    if ! command -v certbot &>/dev/null; then
        echo "Устанавливаем certbot..."
        apt-get update -q && apt-get install -y -q certbot
    fi

    mkdir -p /var/www/certbot

    # Освобождаем порт 80 для certbot standalone
    docker compose -f "$PROJECT_DIR/docker-compose.yml" stop nginx 2>/dev/null || true

    certbot certonly --standalone --non-interactive --agree-tos \
        --email "$CERTBOT_EMAIL" \
        --domain "$DOMAIN"

    echo "Сертификат получен."
fi

# ─── 4. Запуск сервисов ───────────────────────────────────────────────────────

echo ""
echo "=== Запуск сервисов ==="
cd "$PROJECT_DIR"

# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

# --no-pull: обход rate limit Docker Hub — BuildKit не обращается к реестру,
# если образ уже есть локально. ensure_base_images загружает только недостающие.
ensure_base_images "$PROJECT_DIR"
docker compose build --no-pull
docker compose up -d

# ─── 5. Cron для авторенивала сертификата ─────────────────────────────────────

echo ""
echo "=== Настройка авторенивала сертификата ==="

DOCKER_BIN=$(command -v docker)
CRON_LINE="0 3 * * * certbot renew --quiet && $DOCKER_BIN compose -f $PROJECT_DIR/docker-compose.yml exec -T nginx nginx -s reload"

if ! command -v crontab &>/dev/null; then
    echo "WARN: crontab не найден — авторенивал не настроен."
    echo "      Установите cron (apt-get install -y cron) и добавьте вручную:"
    echo "      $CRON_LINE"
elif ! crontab -l 2>/dev/null | grep -qF "$PROJECT_DIR/docker-compose.yml"; then
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "Cron добавлен: авторенивал ежедневно в 03:00"
else
    echo "Cron уже настроен — пропускаем."
fi

# ─── 6. Готово ────────────────────────────────────────────────────────────────

echo ""
echo "=== Деплой завершён ==="
echo "WebApp: https://$DOMAIN"
echo ""
docker compose ps
