#!/bin/bash
# Doppio click su macOS: avvia un mini server locale e apre la live nel browser.
cd "$(dirname "$0")" || exit 1
PORT=8080
echo "Caduta Eterna → http://localhost:$PORT"
( sleep 1; open "http://localhost:$PORT" ) &
exec python3 -m http.server "$PORT"
