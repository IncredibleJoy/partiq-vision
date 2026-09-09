#!/usr/bin/env sh
set -eu

frontend="stopped"
backend="stopped"
database="stopped"

if podman ps --format '{{.Names}} {{.Status}}' | grep -q '^partiq-frontend '; then
  frontend="running"
fi

if podman ps --format '{{.Names}} {{.Status}}' | grep -q '^partiq-backend '; then
  backend="running"
fi

if podman ps --format '{{.Names}} {{.Status}}' | grep -q '^partiq-postgres '; then
  database="running"
fi

echo "PartIQ Vision App"
echo "Frontend:  ${frontend}  http://localhost:5174"
echo "Backend:   ${backend}  http://localhost:8000"
echo "Database:  ${database}  localhost:5433"

