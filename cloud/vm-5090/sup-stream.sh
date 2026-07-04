#!/bin/bash
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native
while true; do KEY=$(cat /root/.streamkey 2>/dev/null); [ -z "$KEY" ] && { sleep 5; continue; }
  ffmpeg -hide_banner -loglevel warning -thread_queue_size 1024 -f x11grab -draw_mouse 0 -framerate 60 -video_size 3840x2160 -i :0.0 -thread_queue_size 1024 -f pulse -i stream.monitor -c:v h264_nvenc -preset p5 -tune hq -rc cbr -b:v 45M -maxrate 45M -bufsize 90M -spatial-aq 1 -temporal-aq 1 -rc-lookahead 16 -g 120 -keyint_min 120 -bf 3 -vsync cfr -r 60 -c:a aac -b:a 192k -ar 44100 -ac 2 -f flv "rtmp://a.rtmp.youtube.com/live2/$KEY" >>/root/stream.log 2>&1
  echo "[$(date +%T)] stream EXIT rc=$?" >>/root/stream.log; sleep 4; done
