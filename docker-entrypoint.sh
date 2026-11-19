#!/bin/sh
# Load the demo book the first time a fresh /data volume starts (set GAMEBOOK_SEED_DEMO=0 to skip).
# A marker file means a book you later delete is not brought back on restart.
set -e
marker="${GAMEBOOK_DATA_DIR:-/data}/.demo-seeded"
if [ "${GAMEBOOK_SEED_DEMO:-1}" = "1" ] && [ ! -e "$marker" ]; then
    mkdir -p "$(dirname "$marker")"
    gamebook import /app/examples/the-drowned-crown || echo "Demo book not loaded (continuing)"
    touch "$marker"
fi
exec "$@"
