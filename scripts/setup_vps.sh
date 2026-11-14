#!/usr/bin/env bash
# One-shot setup for a fresh Ubuntu/Debian VPS. Run as root:  bash scripts/setup_vps.sh
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH || true
  ufw allow 80/tcp || true
  ufw allow 443/tcp || true
  ufw --force enable || true
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env. Edit it now (nano .env), then run:  docker compose up -d --build"
  exit 0
fi

mkdir -p data
docker compose up -d --build
echo "Started. Logs: docker compose logs -f game"
