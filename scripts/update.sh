#!/bin/bash
# Обновление работающего сервиса: git pull + rebuild образов + restart
# Использование: make update
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# shellcheck source=scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

# ─── 1. git pull ──────────────────────────────────────────────────────────────

echo "=== Получаем обновления ==="
git pull

# ─── 2. Перезапуск контейнеров ────────────────────────────────────────────────

echo ""
# Загружаем базовые образы в локальный кеш (только при отсутствии).
# DOCKER_BUILDKIT=0 переключает на классический builder: в отличие от BuildKit,
# он не обращается к Docker Hub за манифестом образа (load metadata) и не вызывает
# rate limit 429. Классический builder доступен в Docker 29 (deprecated, но не удалён).
ensure_base_images "$PROJECT_DIR"
echo ""
echo "=== Собираем образы ==="
DOCKER_BUILDKIT=0 docker compose build --progress plain

echo ""
echo "=== Запускаем контейнеры ==="
docker compose --progress plain up -d 

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
