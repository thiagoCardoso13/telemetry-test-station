#!/usr/bin/env bash
# Run simulator, ingest and web server together. UDP and the ingest interface stay on loopback.
# If any of them stops, stop the others and fail, so the host restarts the whole container.
set -u
: "${DATABASE_URL:?set DATABASE_URL}"

trap 'kill $(jobs -p) 2>/dev/null; wait; exit 0' TERM INT

python -m station.ingest --keep-minutes "${KEEP_MINUTES:-10}" &
python -m station.simulator --seed 1 &
node web/dist/server.js &

wait -n
echo "a part of the station stopped; shutting down" >&2
kill $(jobs -p) 2>/dev/null
wait
exit 1
