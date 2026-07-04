#!/bin/bash
URL='http://127.0.0.1:8099/?ultra=1&live=1&ep=1'
cat > /root/sup-server.sh <<'S'
#!/bin/bash
cd /root/eternal-fall
while true; do echo "[$(date +%T)] server start" >>/root/server.log; node server.js >>/root/server.log 2>&1; echo "[$(date +%T)] server EXIT" >>/root/server.log; sleep 2; done
S
cat > /root/sup-chrome.sh <<S
#!/bin/bash
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native
while true; do echo "[\$(date +%T)] chrome start" >>/root/chrome.log; bash /root/efchrome.sh '$URL' >>/root/chrome.log 2>&1; echo "[\$(date +%T)] chrome EXIT" >>/root/chrome.log; sleep 3; done
S
cat > /root/sup-stream.sh <<'S'
#!/bin/bash
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native
while true; do KEY=$(cat /root/.streamkey 2>/dev/null); [ -z "$KEY" ] && { sleep 5; continue; }
  ffmpeg -hide_banner -loglevel warning -thread_queue_size 1024 -f x11grab -draw_mouse 0 -framerate 60 -video_size 3840x2160 -i :0.0 -thread_queue_size 1024 -f pulse -i stream.monitor -c:v h264_nvenc -preset p5 -tune hq -rc cbr -b:v 45M -maxrate 45M -bufsize 90M -spatial-aq 1 -temporal-aq 1 -rc-lookahead 16 -g 120 -keyint_min 120 -bf 3 -vsync cfr -r 60 -c:a aac -b:a 192k -ar 44100 -ac 2 -f flv "rtmp://a.rtmp.youtube.com/live2/$KEY" >>/root/stream.log 2>&1
  echo "[$(date +%T)] stream EXIT rc=$?" >>/root/stream.log; sleep 4; done
S
chmod +x /root/sup-*.sh
fuser -k 8099/tcp 2>/dev/null; sleep 1
setsid nohup bash /root/sup-server.sh >/dev/null 2>&1 </dev/null &
sleep 3
setsid nohup bash /root/sup-chrome.sh >/dev/null 2>&1 </dev/null &
echo "server+chrome supervisori partiti"
