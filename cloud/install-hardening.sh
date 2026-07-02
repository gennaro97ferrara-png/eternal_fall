#!/bin/bash
# Installa la resilienza 24/7 di Eternal Fall sulla VM Vast.
# - ef-server: da unit TRANSIENT (muore al reboot) -> unit PERSISTENTE enabled
# - ef-supervise: babysitter processi (pulse/Xorg/chrome/streamloop) crash+reboot
# - ef-monitor: self-heal broadcast YouTube (riconnessione fresca su upcoming; sync video-id)
set -u
echo "== chmod scripts =="
chmod +x /root/ef-supervise.sh /root/ef-monitor.py

echo "== scrivo unit ef-server (persistente) =="
cat > /etc/systemd/system/ef-server.service <<'UNIT'
[Unit]
Description=Eternal Fall bridge server (server.js)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/eternal-fall
ExecStart=/bin/bash -c 'set -a; . ./.env; set +a; exec node server.js'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

echo "== scrivo unit ef-supervise =="
cat > /etc/systemd/system/ef-supervise.service <<'UNIT'
[Unit]
Description=Eternal Fall 24/7 process supervisor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
KillMode=process
ExecStart=/bin/bash /root/ef-supervise.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

echo "== scrivo unit ef-monitor =="
cat > /etc/systemd/system/ef-monitor.service <<'UNIT'
[Unit]
Description=Eternal Fall YouTube broadcast monitor/self-heal
After=network-online.target ef-server.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /root/ef-monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

echo "== daemon-reload =="
systemctl daemon-reload

echo "== converto ef-server: stop transient -> start persistente =="
systemctl stop ef-server 2>/dev/null
systemctl reset-failed ef-server 2>/dev/null
systemctl daemon-reload
systemctl enable --now ef-server
sleep 3
echo "ef-server active: $(systemctl is-active ef-server)  transient: $(systemctl show ef-server -p Transient --value)"
curl -s --max-time 5 http://127.0.0.1:8099/api/health; echo ""

echo "== abilito+avvio supervise e monitor =="
systemctl enable --now ef-supervise
systemctl enable --now ef-monitor
sleep 6
echo "ef-supervise: $(systemctl is-active ef-supervise)   ef-monitor: $(systemctl is-active ef-monitor)"
echo "-- supervise log --"; tail -n 8 /tmp/ef-supervise.log 2>/dev/null
echo "-- monitor log --";   tail -n 6 /tmp/ef-monitor.log 2>/dev/null
echo "== stato processi live (devono essere tutti ancora su) =="
echo "Xorg: $(pgrep -x Xorg >/dev/null && echo UP || echo DOWN)  chrome: $(pgrep -f 'user-data-dir=/tmp/cp' >/dev/null && echo UP || echo DOWN)  ffmpeg: $(pgrep -x ffmpeg >/dev/null && echo UP || echo DOWN)  streamloop: $(pgrep -f '[s]treamloop.sh' >/dev/null && echo UP || echo DOWN)"
echo "== enabled per boot =="
systemctl is-enabled ef-server ef-supervise ef-monitor
echo "DONE"
