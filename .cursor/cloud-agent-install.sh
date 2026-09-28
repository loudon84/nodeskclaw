#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log() { echo "[cloud-install] $*"; }

if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  log "Installing uv (Python 包管理器)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

if ! command -v pg_ctlcluster >/dev/null 2>&1; then
  log "Installing PostgreSQL (数据库)"
  sudo apt-get update -qq
  sudo apt-get install -y -qq postgresql postgresql-contrib
fi

if [ ! -f nodeskclaw-backend/.env ]; then
  log "Generating nodeskclaw-backend/.env (随机 JWT / 加密密钥)"
  JWT="$(openssl rand -hex 32)"
  ENC="$(openssl rand -base64 32)"
  cat > nodeskclaw-backend/.env <<EOF
DEBUG=true
NODESKCLAW_EDITION=ce
DATABASE_URL=postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw
DATABASE_NAME_SUFFIX=
INIT_ADMIN_ACCOUNT=admin
RESET_ADMIN_PASSWORD=false
JWT_SECRET=${JWT}
JWT_EXPIRE_HOURS=24
FORCE_PASSWORD_CHANGE_ON_LOGIN=false
ENCRYPTION_KEY=${ENC}
SEED_GENES=true
TELEMETRY_ENABLED=false
POSTHOG_API_KEY=
CORS_ORIGINS=["http://localhost:4517","http://localhost:4518"]
EOF
fi

log "Installing backend dependencies (uv sync)"
(cd nodeskclaw-backend && uv sync)

log "Installing llm-proxy dependencies (uv sync)"
(cd nodeskclaw-llm-proxy && uv sync)

log "Installing portal dependencies (npm install)"
(cd nodeskclaw-portal && npm install)

log "Install complete"
