#!/bin/sh
ENV_FILE="/host-config/.env"
if [ -f "$ENV_FILE" ]; then
    set -af
    . "$ENV_FILE"
    set +af
fi
exec "$@"
