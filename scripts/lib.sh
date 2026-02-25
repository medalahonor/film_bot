#!/bin/bash

# Загружает только те базовые образы из Dockerfile*, которых нет в локальном кеше.
# Это позволяет обойти rate limit Docker Hub: сборка запускается с --no-pull и
# не обращается к реестру, если все базовые образы уже присутствуют локально.
ensure_base_images() {
    local project_dir="$1"

    # Собираем все Dockerfile* из корня проекта (включая будущие)
    local dockerfiles=()
    while IFS= read -r -d '' f; do
        dockerfiles+=("$f")
    done < <(find "$project_dir" -maxdepth 1 -name 'Dockerfile*' -type f -print0)

    if [[ ${#dockerfiles[@]} -eq 0 ]]; then
        echo "WARN: Dockerfile* не найдены в $project_dir"
        return
    fi

    # Извлекаем имена базовых образов: пропускаем флаги вида --platform
    local images
    images=$(grep -h '^FROM' "${dockerfiles[@]}" \
        | awk '{for(i=2;i<=NF;i++) if($i!~/^--/) {print $i; break}}' \
        | sort -u)

    echo "=== Проверяем базовые образы ==="
    for image in $images; do
        if ! docker image inspect "$image" >/dev/null 2>&1; then
            echo "Загружаем: $image"
            docker pull "$image"
        else
            echo "В кеше:    $image"
        fi
    done
}
