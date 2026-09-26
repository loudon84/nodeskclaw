#!/usr/bin/env bash
set -euo pipefail

log() { echo "[cloud-start] $*"; }

log "Starting PostgreSQL cluster (16/main)"
sudo pg_ctlcluster 16 main start 2>/dev/null || true

log "Waiting for PostgreSQL to accept connections"
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q 2>/dev/null; then
    break
  fi
  sleep 1
done

if ! sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='nodeskclaw'" | grep -q 1; then
  log "Creating role nodeskclaw (开发数据库账号)"
  sudo -u postgres psql -c "CREATE ROLE nodeskclaw LOGIN PASSWORD 'nodeskclaw';"
fi

if ! sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='nodeskclaw'" | grep -q 1; then
  log "Creating database nodeskclaw"
  sudo -u postgres createdb -O nodeskclaw nodeskclaw
fi

log "PostgreSQL ready"
