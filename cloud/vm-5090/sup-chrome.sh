#!/bin/bash
export DISPLAY=:0 PULSE_SERVER=unix:/tmp/pulse/native
while true; do echo "[$(date +%T)] chrome start" >>/root/chrome.log; bash /root/efchrome.sh 'http://127.0.0.1:8099/?ultra=1&live=1&ep=1' >>/root/chrome.log 2>&1; echo "[$(date +%T)] chrome EXIT" >>/root/chrome.log; sleep 3; done
