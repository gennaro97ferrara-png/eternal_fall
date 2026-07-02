#!/bin/bash
# ============================================================================
# Eternal Fall — supervisore 24/7 (process babysitter).
# Garantisce che PulseAudio, Xorg :0, Chrome (?live=1), ef-server e lo
# streamloop (ffmpeg->YouTube) siano SEMPRE su; (ri)avvia solo cio' che e' giu'.
# Recovery su crash E su reboot (systemd: ef-supervise.service, enabled).
# Non-disruptivo: un componente sano non viene mai toccato. Le azioni
# disruptive (Xorg/Chrome) scattano solo dopo N controlli falliti di fila
# (anti falso-positivo su blip transitori).
# ============================================================================
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
export __GLX_VENDOR_LIBRARY_NAME=nvidia
ENV_FILE=/root/eternal-fall/.env
# La stream key NON e' hardcoded (segreto): si legge da .env (YT_STREAM_KEY), che e' gitignorato.
set -a; . "$ENV_FILE" 2>/dev/null; set +a
KEY="${YT_STREAM_KEY:-}"
LOG=/tmp/ef-supervise.log
FAIL_LIMIT=3          # controlli falliti consecutivi prima di un restart disruptivo
say(){ echo "[$(date -u '+%m-%d %H:%M:%S')] $*" >>"$LOG"; }

pulse_ok(){ pactl info >/dev/null 2>&1 && pactl list short sinks 2>/dev/null | grep -q stream; }
xorg_ok(){ DISPLAY=:0 xset q >/dev/null 2>&1; }
chrome_ok(){ curl -s --max-time 4 http://127.0.0.1:9222/json 2>/dev/null | grep -q 'live=1'; }
server_ok(){ curl -s --max-time 4 http://127.0.0.1:8099/api/health 2>/dev/null | grep -q '"ok":true'; }
stream_ok(){ pgrep -f '[s]treamloop.sh' >/dev/null 2>&1 && pgrep -x ffmpeg >/dev/null 2>&1; }

start_pulse(){
  say "PulseAudio giu' -> start"
  setsid pulseaudio --system -n --disallow-exit --exit-idle-time=-1 -D \
    --load="module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulse/native" \
    --load="module-null-sink sink_name=stream sink_properties=device.description=EternalFall" \
    --load=module-always-sink >>/tmp/pulse.log 2>&1 </dev/null &
  sleep 3
}

say "===== supervisore avviato (pid $$) key=${KEY:0:4}$([ -n "$KEY" ] && echo '...' || echo 'ASSENTE!') ====="
xf=0; cf=0
while true; do
  # 0) GUARD anti-OOM: se ffmpeg gonfia la RAM (buffer verso un RTMP bloccato/broadcast finito),
  #    killalo -> lo streamloop lo respawna. Causa reale della caduta del 2026-07-02 (ffmpeg a 20GB).
  FMPID=$(pgrep -x ffmpeg | head -1)
  if [ -n "$FMPID" ]; then
    RSSKB=$(ps -o rss= -p "$FMPID" 2>/dev/null | tr -d ' ')
    if [ -n "$RSSKB" ] && [ "$RSSKB" -gt 4000000 ]; then say "ffmpeg RSS ${RSSKB}KB > 4GB -> kill (anti-OOM)"; kill -9 "$FMPID" 2>/dev/null; fi
  fi

  # 1) PulseAudio (non disruptivo: se manca il sink, ricrealo)
  pulse_ok || start_pulse

  # 2) Xorg :0  (disruptivo -> doppia/tripla conferma)
  if xorg_ok; then xf=0; else
    xf=$((xf+1)); say "Xorg check fallito ($xf/$FAIL_LIMIT)"
    if [ "$xf" -ge "$FAIL_LIMIT" ]; then
      say "Xorg GIU' -> x.sh (riavvia anche Chrome a cascata)"
      rm -f /tmp/.X11-unix/X0 /tmp/.X0-lock 2>/dev/null
      setsid bash /root/x.sh >>/tmp/x.log 2>&1 </dev/null &
      sleep 10; xf=0; cf=$FAIL_LIMIT   # forza il riavvio di Chrome (contesto GL perso)
      pkill -x ffmpeg   # ffmpeg cattura :0 stantio dopo il restart Xorg -> forza reconnect fresco
    fi
  fi

  # 3) Chrome kiosk su ?live=1 (disruptivo -> conferma). chrome.sh fa il pkill interno in sicurezza.
  if chrome_ok; then cf=0; else
    cf=$((cf+1)); say "Chrome check fallito ($cf/$FAIL_LIMIT)"
    if [ "$cf" -ge "$FAIL_LIMIT" ] && xorg_ok; then
      say "Chrome GIU' -> chrome.sh"
      setsid bash /root/chrome.sh >>/tmp/chrome.log 2>&1 </dev/null &
      sleep 20; cf=0
    fi
  fi

  # 4) ef-server (systemd) — economico da riavviare
  systemctl is-active --quiet ef-server || { say "ef-server giu' -> restart"; systemctl restart ef-server; sleep 2; }

  # 5) streamloop+ffmpeg (lo streamloop possiede il restart di ffmpeg; qui garantiamo che il LOOP viva)
  if ! pgrep -f '[s]treamloop.sh' >/dev/null 2>&1; then
    if [ -n "$KEY" ]; then
      say "streamloop giu' -> start (key ${KEY:0:4}...)"
      setsid bash /root/streamloop.sh "$KEY" >>/tmp/streamloop.log 2>&1 </dev/null &
      sleep 3
    else
      say "streamloop giu' MA YT_STREAM_KEY assente nel .env -> non avvio (aggiungi YT_STREAM_KEY=)"
    fi
  fi

  sleep 15
done
