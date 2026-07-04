#!/bin/bash
# Uso: bash /root/rec.sh <episodio> [durata_secondi]   (default 1h)
N="${1:-1}"; DUR="${2:-3600}"
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native
cd /root/eternal-fall
getws(){ curl -s 127.0.0.1:9222/json | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{try{const a=JSON.parse(d);const p=a.find(t=>/8099/.test(t.url||"")&&t.webSocketDebuggerUrl);process.stdout.write(p?p.webSocketDebuggerUrl:"")}catch(e){process.stdout.write("")}})'; }
if curl -s --max-time 3 127.0.0.1:9222/json >/dev/null 2>&1 && [ -n "$(getws)" ]; then
  node cloud/cdp-eval.js "$(getws)" "location.href='/?ultra=1&ep=$N&t='+Date.now()" >/dev/null 2>&1
else
  setsid nohup bash /root/efchrome.sh "http://127.0.0.1:8099/?ultra=1&ep=$N" >/root/chrome.log 2>&1 </dev/null &
fi
echo "carico ep$N..."; sleep 9
node cloud/cdp-eval.js "$(getws)" "try{cadutaIntro()}catch(e){}" >/dev/null 2>&1
sleep 0.4
mkdir -p /root/episodes
OUT="/root/episodes/ep${N}_$(date +%Y%m%d_%H%M%S).mp4"
echo "REC ep$N -> $OUT (${DUR}s @4K60 nvenc)"
ffmpeg -y -hide_banner -loglevel warning -thread_queue_size 1024 -f x11grab -framerate 60 -video_size 3840x2160 -i :0.0 -thread_queue_size 1024 -f pulse -i stream.monitor -t "$DUR" -c:v h264_nvenc -preset p5 -cq 19 -c:a aac -b:a 192k "$OUT"
echo "DONE: $OUT ($(du -h "$OUT" 2>/dev/null|cut -f1))"
