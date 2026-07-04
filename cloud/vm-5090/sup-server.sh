#!/bin/bash
cd /root/eternal-fall
while true; do echo "[$(date +%T)] server start" >>/root/server.log; node server.js >>/root/server.log 2>&1; echo "[$(date +%T)] server EXIT" >>/root/server.log; sleep 2; done
