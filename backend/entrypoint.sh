#!/bin/bash

set -e

export PYTHONPATH="/app:${PYTHONPATH}"

echo "Applying migrations..."
alembic upgrade head

echo "Seeding initial WBS data (no-op if already loaded)..."
python scripts/seed_from_json.py

echo "Starting in production mode..."
exec hypercorn main:app --bind 0.0.0.0:8000 --workers 1