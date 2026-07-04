#!/bin/bash
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native __GLX_VENDOR_LIBRARY_NAME=nvidia
mkdir -p /tmp/pulse; chmod 777 /tmp/pulse
pactl info >/dev/null 2>&1 || setsid pulseaudio --system -n --disallow-exit --exit-idle-time=-1 -D --load="module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulse/native" --load="module-null-sink sink_name=stream sink_properties=device.description=EF" --load=module-always-sink >/root/pulse.log 2>&1 </dev/null &
sleep 1
mkdir -p /etc/opt/chrome/policies/managed
printf '{"TranslateEnabled": false}\n' > /etc/opt/chrome/policies/managed/ef.json
pkill -9 -x google-chrome-stable 2>/dev/null; sleep 1; rm -f /tmp/cp/Singleton* 2>/dev/null
URL="${1:-http://127.0.0.1:8099/?ultra=1&live=1&ep=1}"
exec env PULSE_SERVER=unix:/tmp/pulse/native google-chrome-stable --user-data-dir=/tmp/cp --no-sandbox --disable-hang-monitor --no-first-run --no-default-browser-check --disable-session-crashed-bubble --password-store=basic --lang=en-US --disable-features=Translate,TranslateUI --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling --kiosk --start-fullscreen --window-position=0,0 --window-size=3840,2160 --force-device-scale-factor=1 --hide-scrollbars --use-gl=angle --use-angle=gl --ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy --autoplay-policy=no-user-gesture-required --remote-debugging-port=9222 "$URL"
