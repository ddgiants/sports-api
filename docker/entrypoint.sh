#!/bin/sh
set -eu

case "${1:-serve}" in
  serve)
    if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
      alembic upgrade head
    fi
    if [ "$#" -gt 0 ]; then
      shift
    fi
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
    ;;
  sync)
    shift
    alembic upgrade head
    exec sports-sync sync "$@"
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  shell)
    exec /bin/sh
    ;;
  *)
    exec "$@"
    ;;
esac
