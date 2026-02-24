#!/bin/bash
# Обновление работающего сервиса: git pull + rebuild образов + restart
# Использование: make update
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# ─── 1. git pull ──────────────────────────────────────────────────────────────

echo "=== Получаем обновления ==="
git pull

# ─── 2. Перезапуск контейнеров ────────────────────────────────────────────────

echo ""
echo "=== Собираем образы ==="
docker compose build --progress plain

echo ""
echo "=== Запускаем контейнеры ==="
docker compose up -d --progress plain

# ─── 3. Перезагрузка nginx если изменился nginx/ ──────────────────────────────

NGINX_CHANGED=false
if git rev-parse ORIG_HEAD &>/dev/null; then
    if ! git diff --quiet ORIG_HEAD HEAD -- nginx/; then
        NGINX_CHANGED=true
    fi
fi

if [[ "$NGINX_CHANGED" == "true" ]]; then
    echo ""
    echo "=== nginx/ изменился — перезагружаем конфигурацию ==="
    sleep 2
    docker compose exec -T nginx nginx -s reload
    echo "nginx перезагружен."
fi

# ─── 4. Статус ────────────────────────────────────────────────────────────────

echo ""
echo "=== Статус сервисов ==="
docker compose ps
