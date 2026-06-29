#!/usr/bin/env bash
# Eternal Fall — launcher robusto per la diretta h24.
#   • tiene sveglio il Mac finché gira (niente sleep → la live non si congela di notte)
#   • riavvia automaticamente server.js se dovesse cadere (crash / OOM / kill)
# Avvio consigliato (resta attivo anche se chiudi il terminale):
#   nohup bash /Users/gennaroferrara/explain/caduta-eterna/keep-live.sh >/tmp/eternal-fall.log 2>&1 &
# Per fermarlo: pkill -f keep-live.sh   (poi eventualmente  pkill -f 'node server.js')
cd "$(dirname "$0")" || exit 1
LOG=/tmp/eternal-fall.log
caffeinate -dimsu -w $$ &            # impedisce sleep/standby finché vive questo script
echo "[$(date)] keep-live avviato (pid $$), caffeinate attivo" >> "$LOG"
while true; do
  echo "[$(date)] avvio server.js su porta ${PORT:-8099}" >> "$LOG"
  node server.js >> "$LOG" 2>&1
  echo "[$(date)] server.js uscito (exit $?), riavvio tra 2s" >> "$LOG"
  sleep 2
done
