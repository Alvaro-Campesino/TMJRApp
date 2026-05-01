#!/bin/sh
set -e

echo "[start] Aplicando migraciones de Alembic..."
alembic upgrade head

echo "[start] Arrancando uvicorn..."
exec uvicorn tmjr.main:app --host 0.0.0.0 --port 80 --proxy-headers
