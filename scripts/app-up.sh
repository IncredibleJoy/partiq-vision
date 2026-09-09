#!/usr/bin/env sh
set -eu

log_file="${TMPDIR:-/tmp}/partiq-compose-up.log"

if podman compose up -d >"$log_file" 2>&1; then
  scripts/app-status.sh
else
  echo "Failed to start PartIQ Vision. Compose output:"
  sed -n '1,160p' "$log_file"
  exit 1
fi

