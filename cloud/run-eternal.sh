#!/usr/bin/env bash
# Eternal Fall — deploy diretto 4K60 su host con DISPLAY REALE (Hyperstack A6000 passthrough).
# Cattura SCHERMO via NvFBC (gsr -w screen) → NVENC → YouTube. Niente trucchi headless: qui DP-0 esiste.
#   sudo MODE=test bash run-eternal.sh   → cattura 10s su /tmp/live4k.mp4 (verifica), poi esce
#   sudo MODE=live nohup bash run-eternal.sh &  → stream a YouTube + supervisione 24/7
set -uo pipefail
APP=/home/ubuntu/eternal-fall
# auto-elevazione a root: Xorg, PulseAudio --system e NvFBC lo richiedono
[ "$(id -u)" -eq 0 ] || exec sudo env MODE="${MODE:-live}" bash "$0"
exec >>/tmp/eternal.log 2>&1
log(){ echo "[$(date '+%H:%M:%S')] $*"; }
MODE="${MODE:-live}"
PORT=8099; RW=3840; RH=2160; FPS=60; KBPS=45000; DSF=2
export DISPLAY=:0 HOME=/root PULSE_SERVER=unix:/tmp/pulse/native
# Forza EGL/GLX NVIDIA (evita Mesa/software)
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
export __GLX_VENDOR_LIBRARY_NAME=nvidia
set -a; [ -f "$APP/.env" ] && . "$APP/.env"; set +a
RTMP="rtmp://a.rtmp.youtube.com/live2/${YT_STREAM_KEY:-MISSING}"
CHROME_PID=""; GSR_PID=""; SERVER_PID=""; XORG_PID=""

# ---- audio: PulseAudio system + null-sink "stream" ----
mkdir -p /tmp/pulse && chmod 777 /tmp/pulse
pulseaudio --kill 2>/dev/null; sleep 1
pulseaudio --system -n --disallow-exit --exit-idle-time=-1 -D \
  --load="module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulse/native" \
  --load="module-null-sink sink_name=stream sink_properties=device.description=EternalFall" \
  --load="module-always-sink" 2>/dev/null
sleep 1; pactl set-default-sink stream 2>/dev/null || true
log "audio pronto (sink stream)"

# ---- policy gestita: spegne barra/popup di traduzione Chrome (--disable-features non basta) ----
mkdir -p /etc/opt/chrome/policies/managed
printf '{"TranslateEnabled": false}\n' > /etc/opt/chrome/policies/managed/eternalfall.json

# ---- EDID 4K + Xorg sulla A6000 (BusID 0:6:0) ----
python3 -c "import binascii;open('/tmp/edid.bin','wb').write(binascii.unhexlify('00ffffffffffff0031d801010100000000210104a5502d7802ee91a3544c99260f50540000000101010101010101010101010101010134d000a0f0703e803020350000000000001e000000fd00304b1ea03c0120202020202020000000fc004546414c4c2d344b0a202020200000001000000000000000000000000000000096'))"
cat > /etc/X11/xorg-ef.conf <<'CONF'
Section "ServerFlags"
    Option "AutoAddGPU" "false"
EndSection
Section "Monitor"
    Identifier "Monitor0"
    HorizSync 30.0-160.0
    VertRefresh 50.0-75.0
    Option "DPMS" "false"
EndSection
Section "Device"
    Identifier "nvidia"
    Driver "nvidia"
    BusID "PCI:0:6:0"
    Option "AllowEmptyInitialConfiguration" "true"
    Option "ConnectedMonitor" "DFP-0"
    Option "CustomEDID" "DFP-0:/tmp/edid.bin"
    Option "ModeValidation" "NoMaxPClkCheck,NoEdidMaxPClkCheck,NoMaxSizeCheck,NoHorizSyncCheck,NoVertRefreshCheck,NoVirtualSizeCheck,AllowNonEdidModes,NoEdidHDMI2Check,NoConfigConflictCheck"
EndSection
Section "Screen"
    Identifier "screen"
    Device "nvidia"
    Monitor "Monitor0"
    Option "MetaModes" "DFP-0: 3840x2160 +0+0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "3840x2160"
        Virtual 3840 2160
    EndSubSection
EndSection
CONF

start_xorg(){
  pkill -f "Xorg :0" 2>/dev/null; sleep 1
  Xorg :0 -config /etc/X11/xorg-ef.conf -noreset -novtswitch -sharevts -nolisten tcp >/tmp/xorg-ef.log 2>&1 &
  XORG_PID=$!
  for _ in $(seq 1 40); do xrandr -q 2>/dev/null | grep -q " connected" && break; sleep 0.25; done
  log "Xorg :0 → output: $(xrandr -q 2>/dev/null | grep ' connected' | awk '{print $1}' | head -1)"
}
start_server(){ ( cd "$APP" && node server.js >/tmp/server.log 2>&1 ) & SERVER_PID=$!; }
start_chrome(){
  rm -f /tmp/chrome-profile/Singleton* 2>/dev/null
  # senza window manager --kiosk non massimizza: window-size esplicito = RENDER/DSF (×DSF = pixel fisici)
  local WIN_W=$(( RW / DSF )) WIN_H=$(( RH / DSF ))
  google-chrome-stable --user-data-dir=/tmp/chrome-profile --no-sandbox --no-first-run \
    --no-default-browser-check --disable-infobars --disable-session-crashed-bubble \
    --disable-features=Translate,TranslateUI,CalculateNativeWinOcclusion \
    --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling \
    --kiosk --start-fullscreen --window-position=0,0 --window-size="${WIN_W},${WIN_H}" \
    --force-device-scale-factor="$DSF" --hide-scrollbars \
    --use-gl=angle --use-angle=gl-egl --ignore-gpu-blocklist --enable-gpu-rasterization \
    --autoplay-policy=no-user-gesture-required \
    "http://localhost:${PORT}/?live=1" >/tmp/chrome.log 2>&1 &
  CHROME_PID=$!
}
start_gsr(){
  # MAI due gsr sulla stessa stream key: YouTube accetta una sola connessione → "Broken pipe".
  pkill -f gpu-screen-recorder 2>/dev/null; sleep 1
  for _ in $(seq 1 40); do pactl list short sources 2>/dev/null | grep -q stream.monitor && break; sleep 0.5; done
  if [ "$MODE" = test ]; then OUTOPT="-c mp4 -o /tmp/live4k.mp4"; else OUTOPT="-c flv -o $RTMP"; fi
  # shellcheck disable=SC2086
  gpu-screen-recorder -w screen -s "${RW}x${RH}" -f "$FPS" -k h264 -bm cbr -q "$KBPS" -fm cfr \
    -cursor no -keyint 2 -encoder gpu -a stream.monitor -ac aac $OUTOPT >/tmp/gsr.log 2>&1 &
  GSR_PID=$!
}

start_xorg; sleep 3
start_server; sleep 2
start_chrome; sleep 8
start_gsr
log "pipeline avviata (MODE=$MODE)"

if [ "$MODE" = test ]; then
  sleep 11; kill -INT "$GSR_PID" 2>/dev/null; sleep 2
  log "test: file /tmp/live4k.mp4 = $(stat -c%s /tmp/live4k.mp4 2>/dev/null) bytes"
  exit 0
fi

log "live 4K60 in onda. Supervisione attiva."
while true; do
  sleep 5
  kill -0 "$SERVER_PID" 2>/dev/null || { log "server.js riavvio"; start_server; }
  kill -0 "$CHROME_PID" 2>/dev/null || { log "Chrome riavvio"; start_chrome; sleep 6; }
  kill -0 "$GSR_PID" 2>/dev/null || { log "gsr riconnetto"; sleep 3; start_gsr; }
  kill -0 "$XORG_PID" 2>/dev/null || { log "Xorg riavvio"; start_xorg; sleep 5; start_chrome; sleep 6; start_gsr; }
done
