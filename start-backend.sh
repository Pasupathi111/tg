#!/usr/bin/env bash
# Linux server start for TG. Reads .env (see .env.example); serves API + built frontend on TG_PORT.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
set -a; . "$ROOT/.env"; set +a
export DATA_DIR="${DATA_DIR:-$ROOT/data-tg}"
cd "$ROOT/open-webui/backend"
exec "$ROOT/open-webui/.venv-tg/bin/python" -m uvicorn open_webui.main:app --host 127.0.0.1 --port "${TG_PORT:-4060}"
