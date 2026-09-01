#!/usr/bin/env bash

set -e

export PYTHONPATH="/app:${PYTHONPATH}"

echo "Applying migrations..."
alembic upgrade head

echo "Starting in production mode..."
exec hypercorn main:app \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --access-logfile - \
    --error-logfile -
