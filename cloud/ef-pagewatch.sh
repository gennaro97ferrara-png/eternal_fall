#!/usr/bin/env bash
# ============================================================================
# Eternal Fall — watchdog della PAGINA live (non del processo).
#
# Problema che risolve: il tab può restare con il JS BLOCCATO (Chrome vivo,
# scena congelata) — era la causa del dialogo "Page Unresponsive" comparso
# IN ONDA. Il dialogo in sé non può più apparire (chrome.sh ha
# --disable-hang-monitor): qui curiamo la CAUSA, in automatico.
#
# Sonda ogni 20s: CDP eval "1+1" con timeout 12s sul tab 127.0.0.1:8099.
# 3 fallimenti consecutivi (pagina muta o tab sparito, ~1 minuto) →
# recovery PROVATO: pkill Chrome + profilo pulito → ef-supervise lo
# rilancia fresco in ~30s. Log in /tmp/pagewatch.log.
#
# NB pkill: la stringa 'google-chrome' sta DENTRO questo file, non nella
# command-line del processo watchdog → niente auto-suicidio (gotcha noto).
# ============================================================================
FAILS=0
log(){ echo "$(date '+%F %T') $*" >> /tmp/pagewatch.log; }
log "ef-pagewatch avviato"
while true; do
  sleep 20
  WS=$(curl -sm 5 127.0.0.1:9222/json 2>/dev/null | python3 -c "import sys,json;ts=json.load(sys.stdin);print([t['webSocketDebuggerUrl'] for t in ts if '8099' in t.get('url','')][0])" 2>/dev/null)
  if [ -z "$WS" ]; then
    FAILS=$((FAILS+1)); log "tab live assente da CDP (fail $FAILS/3)"
  else
    R=$(timeout 12 node /root/eternal-fall/cloud/cdp-eval.js "$WS" "1+1" 2>/dev/null | grep -c '"value":2')
    if [ "$R" -ge 1 ]; then FAILS=0; else FAILS=$((FAILS+1)); log "pagina muta al probe CDP (fail $FAILS/3)"; fi
  fi
  if [ "$FAILS" -ge 3 ]; then
    log "PAGINA WEDGED → recovery: pkill chrome + profilo pulito (ef-supervise rilancia)"
    pkill -9 -f 'google-chrome' 2>/dev/null
    rm -rf /tmp/cp /tmp/.config
    FAILS=0
    sleep 60   # tempo a supervise di rilanciare prima di riprendere le sonde
  fi
done
