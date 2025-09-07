#!/bin/sh
# entrypoint.sh

set -e

echo "ENTRYPOINT: Running database migrations..."
alembic upgrade head
echo "ENTRYPOINT: Migrations complete."

echo "ENTRYPOINT: Starting bot with live reload..."
exec watchmedo auto-restart \
    --pattern="*.py" \
    --ignore-patterns="*/__pycache__/*" \
    --recursive \
    -- \
    python -m aiogram_bot_template.bot