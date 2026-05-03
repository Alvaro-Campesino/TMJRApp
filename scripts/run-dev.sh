#!/usr/bin/env bash
# Arranca un entorno de DESARROLLO local. Tres opciones:
#
#   bash scripts/run-dev.sh api      # Postgres + uvicorn --reload (sin bot)
#   bash scripts/run-dev.sh bot      # Postgres + bot polling (sin API)
#   bash scripts/run-dev.sh full     # Postgres + uvicorn --reload + bot polling
#
# En todos los modos:
# - Postgres se levanta vía `docker compose up -d db` (contenedor compartido).
# - DATABASE_URL se override-a a localhost:5432 para que la app lo alcance.
# - Migraciones (alembic upgrade head) se aplican automáticamente.
# - Para parar todo: Ctrl+C en este script + `docker compose stop db` cuando
#   ya no lo necesites.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d .venv ]]; then
    echo "✗ No hay .venv. Crea con: python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt" >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    echo "✗ Falta .env. Copia .env.example y rellena TELEGRAM_TOKEN." >&2
    exit 1
fi

MODE="${1:-full}"

echo "→ Levantando Postgres del compose"
docker compose up -d db

echo "→ Esperando a que Postgres esté healthy..."
for i in {1..30}; do
    if docker compose exec -T db pg_isready -U tmjr -d tmjr >/dev/null 2>&1; then
        echo "  ✓ db lista"
        break
    fi
    sleep 1
done

# DATABASE_URL apunta a localhost (no a "db" como dentro del contenedor)
export DATABASE_URL="postgresql+asyncpg://tmjr:tmjr@localhost:5432/tmjr"

# Carga el resto de .env (sin pisar DATABASE_URL)
set -a
# shellcheck disable=SC1091
source .env
set +a
export DATABASE_URL="postgresql+asyncpg://tmjr:tmjr@localhost:5432/tmjr"

echo "→ Aplicando migraciones de Alembic..."
.venv/bin/alembic upgrade head

trap 'echo "→ Stopping..."; kill 0; wait' EXIT INT TERM

case "$MODE" in
    api)
        echo "→ Modo: API only (uvicorn --reload en :8000)"
        exec .venv/bin/uvicorn tmjr.main:app --reload --host 0.0.0.0 --port 8000 --log-level info
        ;;

    bot)
        echo "→ Modo: bot polling"
        exec .venv/bin/python -m tmjr.devbot
        ;;

    full)
        echo "→ Modo: API + bot polling (logs entrelazados)"
        .venv/bin/uvicorn tmjr.main:app --reload --host 0.0.0.0 --port 8000 --log-level info &
        .venv/bin/python -m tmjr.devbot &
        wait
        ;;

    *)
        echo "Modo desconocido: $MODE. Usa api | bot | full" >&2
        exit 1
        ;;
esac
