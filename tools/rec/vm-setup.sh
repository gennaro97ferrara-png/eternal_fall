#!/bin/bash
# ============================================================================
# Eternal Fall — SETUP COMPLETO VM per registrazione 4K60. IDEMPOTENTE.
# Esegui COME ROOT sulla VM:  bash vm-setup.sh
# Presupposti: Ubuntu + KDE Plasma/SDDM autologin user (uid 1000, /home/user),
#   NVIDIA + Xorg su :0, il progetto già in /root/ef (fai prima il deploy dal Mac,
#   vedi tools/rec/README.md). Self-contained: scrive eflaunch.sh, efrec.sh, cdp.py.
#
# Scoperta chiave: su NVIDIA headless x11grab del ROOT legge NERO per il WebGL di
# Chrome. La registrazione cattura la FINESTRA via gstreamer ximagesrc xid= (OK).
# ============================================================================
set -u
export DEBIAN_FRONTEND=noninteractive
U="sudo -u user env DISPLAY=:0 XAUTHORITY=/home/user/.Xauthority XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus PULSE_SERVER=/run/user/1000/pulse/native"

echo "== [1/6] deps (attendo lock apt di boot) =="
for i in $(seq 1 24); do fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break; echo "  apt busy ($i)"; sleep 5; done
apt-get install -y gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-pulseaudio \
  wmctrl xdotool x11-utils mesa-utils imagemagick nodejs >/dev/null 2>&1 || echo "  (apt parziale, ok)"
gst-inspect-1.0 nvh264enc >/dev/null 2>&1 && echo "  nvh264enc OK" || echo "  ⚠ nvh264enc MANCANTE (serve gstreamer1.0-plugins-bad)"
# ffmpeg opzionale (ffprobe/verifica). BtbN n7.1 = compatibile driver 580 (master vuole 610+).
command -v ffmpeg >/dev/null 2>&1 || { cd /root && curl -sL https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux64-gpl-7.1.tar.xz -o ff.tar.xz 2>/dev/null && tar xf ff.tar.xz 2>/dev/null && cp ffmpeg-n7.1-*/bin/ffmpeg ffmpeg-n7.1-*/bin/ffprobe /usr/local/bin/ 2>/dev/null && hash -r; }

echo "== [2/6] risoluzione 4K a caldo =="
$U bash -c 'eval xrandr --newmode $(cvt -r 3840 2160 60 | grep Modeline | cut -d" " -f2-) 2>/dev/null; xrandr --addmode DP-0 3840x2160R 2>/dev/null; xrandr --output DP-0 --mode 3840x2160R 2>/dev/null; xset s off -dpms 2>/dev/null'
echo "  $($U xrandr 2>/dev/null | grep -oE 'current [0-9]+ x [0-9]+' | head -1)"

echo "== [3/6] desktop pulito (locker off, niente pannello) =="
loginctl unlock-sessions 2>/dev/null || true
mkdir -p /home/user/.config; printf "[Daemon]\nAutolock=false\nLockOnResume=false\n" > /home/user/.config/kscreenlockerrc; chown user:users /home/user/.config/kscreenlockerrc
killall -9 plasmashell 2>/dev/null || true   # NB: killall (per nome), NON pkill -f "...chrome/plasma..." che si suiciderebbe

echo "== [4/6] web server :8000 (serve /root/ef) =="
ss -ltn 2>/dev/null | grep -q ":8000" || { cd /root/ef && setsid python3 -m http.server 8000 </dev/null >/tmp/serve.log 2>&1 & }
sleep 1; curl -s -o /dev/null -w "  index HTTP %{http_code}\n" http://localhost:8000/index.html

echo "== [5/6] CDP helper + launcher + record script =="
cat >/root/cdp.py <<'PY'
import json,socket,os,struct,base64,urllib.request,sys
expr=sys.argv[1]; awaitp=("promise" in sys.argv[2:] or "await" in sys.argv[2:])
t=json.load(urllib.request.urlopen("http://localhost:9222/json"))
ws=[x["webSocketDebuggerUrl"] for x in t if x.get("type")=="page"][0]; path=ws.split(":9222",1)[1]
s=socket.create_connection(("localhost",9222)); key=base64.b64encode(os.urandom(16)).decode()
s.send(("GET %s HTTP/1.1\r\nHost: localhost:9222\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n"%(path,key)).encode()); s.recv(4096)
def snd(o):
 d=json.dumps(o).encode(); m=os.urandom(4); h=bytearray([0x81])
 h.append(0x80|len(d)) if len(d)<126 else (h.append(0x80|126),h.extend(struct.pack(">H",len(d))))
 h+=m; s.send(bytes(h)+bytes(b^m[i%4] for i,b in enumerate(d)))
def rcv():
 b=s.recv(2); l=b[1]&0x7f
 if l==126: l=struct.unpack(">H",s.recv(2))[0]
 elif l==127: l=struct.unpack(">Q",s.recv(8))[0]
 data=b""
 while len(data)<l: data+=s.recv(l-len(data))
 return json.loads(data)
snd({"id":1,"method":"Runtime.evaluate","params":{"expression":expr,"awaitPromise":awaitp,"returnByValue":True}})
for _ in range(80):
 m=rcv()
 if m.get("id")==1: print(m.get("result",{}).get("result",{}).get("value")); break
PY

cat >/usr/local/bin/eflaunch.sh <<'SH'
#!/bin/bash
export DISPLAY=:0 XAUTHORITY=/home/user/.Xauthority XDG_RUNTIME_DIR=/run/user/1000 PULSE_SERVER=/run/user/1000/pulse/native
exec google-chrome --user-data-dir=/tmp/efchrome --no-first-run --no-default-browser-check \
  --start-fullscreen --kiosk --window-size=3840,2160 --autoplay-policy=no-user-gesture-required \
  --disable-infobars --disable-session-crashed-bubble \
  --disable-features=CalculateNativeWinOcclusion,Translate,TranslateUI \
  --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling \
  --ignore-gpu-blocklist --remote-debugging-port=9222 --remote-allow-origins=* \
  "http://localhost:8000/index.html?ultra=1"
SH
chmod 755 /usr/local/bin/eflaunch.sh

# ⚠ efrec.sh: cattura la FINESTRA (ximagesrc xid), NON il root. NIENTE videoscale (costa ~14fps a 4K).
#   Cattura 3839x2159@60 (drawable finestra) = per YouTube = 2160p60. Arg1 = durata sec (default 600).
cat >/usr/local/bin/efrec.sh <<'SH'
#!/bin/bash
export DISPLAY=:0 XAUTHORITY=/home/user/.Xauthority XDG_RUNTIME_DIR=/run/user/1000 PULSE_SERVER=/run/user/1000/pulse/native
DUR="${1:-600}"
WIDD=$(printf "%d" $(wmctrl -lx | grep "google-chrome (/tmp/efchrome)" | awk '{print $1}' | head -1))
exec timeout -s INT "$DUR" gst-launch-1.0 -e \
  ximagesrc xid=$WIDD use-damage=false ! video/x-raw,framerate=60/1 ! videoconvert ! queue max-size-buffers=8 ! \
  nvh264enc bitrate=55000 preset=hq ! h264parse ! queue ! mp4mux name=mux ! filesink location=/tmp/episode.mp4 \
  pulsesrc device=auto_null.monitor ! audioconvert ! audioresample ! voaacenc bitrate=256000 ! aacparse ! queue ! mux.
SH
chmod 755 /usr/local/bin/efrec.sh

echo "== [6/6] avvio Chrome (systemd-run, uid user; MAI 'sudo &' → appende ssh) =="
killall -9 chrome 2>/dev/null || true; sleep 2
rm -rf /tmp/efchrome; mkdir -p /tmp/efchrome/Default; printf '{"translate":{"enabled":false}}' >/tmp/efchrome/Default/Preferences; chown -R user:users /tmp/efchrome
systemctl stop efchrome 2>/dev/null; systemctl reset-failed efchrome 2>/dev/null
systemd-run --uid=1000 --gid=100 --unit=efchrome --collect /usr/local/bin/eflaunch.sh
sleep 16
python3 /root/cdp.py "window.efFxaa=false" >/dev/null 2>&1   # efFxaa off = 60fps (on = 57 a 4K)
echo ""
echo "SETUP OK | CDP=$(curl -s --max-time 5 http://localhost:9222/json/version 2>/dev/null | head -c 24) | fps=$(python3 /root/cdp.py '(()=>new Promise(r=>{let c=0,t0=performance.now();function f(){c++;if(performance.now()-t0<1500)requestAnimationFrame(f);else r(Math.round(c/((performance.now()-t0)/1000)))}requestAnimationFrame(f)}))()' promise 2>/dev/null)"
echo "PER REGISTRARE:  python3 /root/cdp.py 'window.cadutaIntro&&window.cadutaIntro()'; sleep 2; systemd-run --uid=1000 --gid=100 --unit=efrec --collect /usr/local/bin/efrec.sh 600"
echo "AL TERMINE (600s):  /tmp/episode.mp4  (3839x2159@60 + audio)"
