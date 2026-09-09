#!/usr/bin/env sh
set -eu

log_file="${TMPDIR:-/tmp}/partiq-compose-down.log"

if podman compose down >"$log_file" 2>&1; then
  echo "PartIQ Vision App stopped"
else
  echo "Failed to stop PartIQ Vision. Compose output:"
  sed -n '1,160p' "$log_file"
  exit 1
fi

