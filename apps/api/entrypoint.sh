#!/bin/sh
set -e

cd /app/packages/core
alembic upgrade head
cd /app

exec uvicorn main:app --host 0.0.0.0 --port 8000
