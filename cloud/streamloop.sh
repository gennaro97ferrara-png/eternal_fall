#!/bin/bash
# ============================================================================
# Eternal Fall — loop di streaming ffmpeg -> YouTube RTMP (cattura X + audio).
# Riavvia ffmpeg se esce (YouTube non pronto / broadcast riarmato / blip rete).
# La stream key arriva come $1 (dal supervisore) o da .env (YT_STREAM_KEY) —
# MAI hardcoded (segreto).
#
# ⚠️ thread_queue_size BASSO (32 video / 128 audio): a 4K un buffer grande
# (1024) puo' accumulare ~17GB di frame quando l'RTMP si blocca (broadcast
# finito) -> OOM -> crash Xorg/Chrome. Causa reale della caduta del 2026-07-02.
# ============================================================================
export PULSE_SERVER=unix:/tmp/pulse/native DISPLAY=:0
[ -z "$1" ] && { set -a; . /root/eternal-fall/.env 2>/dev/null; set +a; }
KEY="${1:-${YT_STREAM_KEY:-}}"
if [ -z "$KEY" ]; then echo "[$(date +%H:%M:%S)] NESSUNA stream key (arg o YT_STREAM_KEY) -> esco" >>/tmp/streamloop.log; exit 1; fi
echo "[$(date +%H:%M:%S)] streamloop avviato, key=${KEY:0:4}..." >>/tmp/streamloop.log
while true; do
  ffmpeg -hide_banner -loglevel warning -nostats \
    -init_hw_device cuda=cu:0 -filter_hw_device cu \
    -thread_queue_size 200 -f x11grab -framerate 60 -video_size 3840x2160 -i :0.0 \
    -thread_queue_size 128 -f pulse -i stream.monitor \
    -vf hwupload_cuda -c:v h264_nvenc -preset p4 -b:v 25M -maxrate 25M -bufsize 50M -g 120 -keyint_min 120 \
    -c:a aac -b:a 160k -ar 44100 -ac 2 \
    -f flv "rtmp://a.rtmp.youtube.com/live2/$KEY" >>/tmp/ffmpeg.log 2>&1
  echo "[$(date +%H:%M:%S)] ffmpeg uscito (YouTube non pronto?) → ritento tra 6s" >>/tmp/streamloop.log
  sleep 6
done
