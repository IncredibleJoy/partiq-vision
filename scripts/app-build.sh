#!/usr/bin/env sh
set -eu

log_file="${TMPDIR:-/tmp}/partiq-compose-build.log"

echo "Building PartIQ Vision App..."
if podman compose build >"$log_file" 2>&1; then
  echo "Build complete"
else
  echo "Build failed. Compose output:"
  sed -n '1,180p' "$log_file"
  exit 1
fi

