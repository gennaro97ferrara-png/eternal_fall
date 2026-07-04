#!/bin/bash
# Uso: bash /root/stream.sh <episodio>   → streamma quell'episodio in 4K60 su YouTube (key in /root/.streamkey)
N="${1:-7}"
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native
cd /root/eternal-fall
KEY=$(cat /root/.streamkey 2>/dev/null)
[ -z "$KEY" ] && { echo "NO KEY (/root/.streamkey)"; exit 1; }
getws(){ curl -s 127.0.0.1:9222/json | node -e 'let d="";process.stdin.on("data",c=>d+=c).on("end",()=>{try{const a=JSON.parse(d);const p=a.find(t=>/8099/.test(t.url||"")&&t.webSocketDebuggerUrl);process.stdout.write(p?p.webSocketDebuggerUrl:"")}catch(e){process.stdout.write("")}})'; }
node cloud/cdp-eval.js "$(getws)" "location.href='/?ultra=1&live=1&ep=$N&t='+Date.now()" >/dev/null 2>&1
echo "carico ep$N (ultra+live)..."; sleep 11
pkill -x ffmpeg 2>/dev/null; sleep 1
setsid nohup ffmpeg -hide_banner -loglevel warning \
  -thread_queue_size 1024 -f x11grab -draw_mouse 0 -framerate 60 -video_size 3840x2160 -i :0.0 \
  -thread_queue_size 1024 -f pulse -i stream.monitor \
  -c:v h264_nvenc -preset p5 -tune hq -rc cbr -b:v 45M -maxrate 45M -bufsize 90M \
  -spatial-aq 1 -temporal-aq 1 -rc-lookahead 16 \
  -g 120 -keyint_min 120 -bf 3 -vsync cfr -r 60 \
  -c:a aac -b:a 192k -ar 44100 -ac 2 \
  -f flv "rtmp://a.rtmp.youtube.com/live2/$KEY" >/tmp/ffmpeg.log 2>&1 </dev/null &
sleep 8
echo "ffmpeg: $(pgrep -cx ffmpeg) proc(s)"
