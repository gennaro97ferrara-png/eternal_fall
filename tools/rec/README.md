# Registrazione episodio 4K60 su VM — runbook rapido

Testato 2026-07-08 su **RTX 3090 + Ryzen 5800X, Ubuntu 22.04 + KDE Plasma/SDDM**.
Primo video: https://youtu.be/HiLaxjP8WYI

## Perché serve questa ricetta (la trappola)
Su **NVIDIA headless**, `ffmpeg x11grab` del **root** cattura **NERO** per il contenuto WebGL di Chrome
(GL scanout non nel framebuffer XGetImage). `kmsgrab` fallisce su NVIDIA, `NvFBC` è bloccato su GeForce.
**Soluzione: catturare la FINESTRA** (non il root) con `gstreamer ximagesrc xid=<window>` → `nvh264enc`.

## Prossima volta (VM nuova) — ~5 passi

```bash
# 0) target VM
export VM='-p <PORT> root@<IP>'          # es: -p 50698 root@202.79.101.81   (stessa chiave ssh)

# 1) DEPLOY del progetto sulla VM (dal Mac, ~282MB; NON gli 8.7GB: escludi zoom/skies/voice/16k/wav)
#    In HYBRID lo sfondo è l'HDRI → skies inutili; deep-zoom inutile.
cd <repo>
{ echo index.html; find assets -type f ! -path 'assets/zoom/*' ! -path 'assets/skies/*' \
    ! -path 'assets/voice/*' ! -name 'milkyway_16k*.jpg'; } \
  | tar cf - -T - | ssh $VM 'mkdir -p /root/ef && tar xf - -C /root/ef'

# 2) SETUP VM (installa deps, 4K, locker off, serve, lancia Chrome). Idempotente.
scp ${VM/ /} tools/rec/vm-setup.sh <IP>:/root/vm-setup.sh   # oppure: scp -P PORT tools/rec/vm-setup.sh root@IP:/root/
ssh $VM 'bash /root/vm-setup.sh'
#    → stampa "SETUP OK | CDP=... | fps=60". Se fps<60, efFxaa è rimasto on: python3 /root/cdp.py "window.efFxaa=false"

# 3) REGISTRA 10 min (intro fresco + climax; poi finalizza da solo)
ssh $VM "python3 /root/cdp.py 'window.cadutaIntro&&window.cadutaIntro()'; sleep 2; \
         systemctl reset-failed efrec 2>/dev/null; rm -f /tmp/episode.mp4; \
         systemd-run --uid=1000 --gid=100 --unit=efrec --collect /usr/local/bin/efrec.sh 600"
#    attendi ~10 min. Verifica: ssh $VM 'systemctl is-active efrec; stat -c%s /tmp/episode.mp4'
#    ffprobe: ssh $VM '/usr/local/bin/ffprobe -v error -show_entries stream=width,height,avg_frame_rate -of default=nw=1 /tmp/episode.mp4'
#    atteso: 3839x2159 @ ~60fps + audio (-20dB). Se ~45fps → è rimasto un videoscale/scaling nel pipeline.

# 4) UPLOAD su YouTube DALLA VM (uplink veloce; credenziali dal .env locale gitignored)
scp ${VM/ /} yt-upload.js <IP>:/root/yt-upload.js
CID=$(grep '^YT_OAUTH_CLIENT_ID=' .env|cut -d= -f2-); CSEC=$(grep '^YT_OAUTH_CLIENT_SECRET=' .env|cut -d= -f2-); RTOK=$(grep '^YT_OAUTH_REFRESH_TOKEN=' .env|cut -d= -f2-)
ssh $VM "YT_OAUTH_CLIENT_ID='$CID' YT_OAUTH_CLIENT_SECRET='$CSEC' YT_OAUTH_REFRESH_TOKEN='$RTOK' \
         node /root/yt-upload.js /tmp/episode.mp4 'Eternal Fall — <titolo>' '<descrizione>' unlisted"
#    stampa https://youtu.be/XXXX . Rendi pubblico da Studio quando vuoi.

# (opz) copia locale:  scp $VM:/tmp/episode.mp4 ~/Downloads/eternal-fall.mp4
# (opz) 3840x2160 esatto:  ssh $VM '/usr/local/bin/ffmpeg -y -i /tmp/episode.mp4 -vf pad=3840:2160 -c:v h264_nvenc -preset p4 -b:v 55M -c:a copy /tmp/episode_4k.mp4'
```

## Trappole (già risolte negli script)
- **`pkill -f chrome` si SUICIDA** (matcha la propria shell ssh) → usa `killall -9 chrome`.
- **`/root` è 700** → gli script eseguibili da uid1000 vanno in `/usr/local/bin/`.
- **backgrounding `sudo &`/`nohup &` appende il canale ssh** → usa `systemd-run --uid=1000 --collect`.
- **Chrome throttla RAF a 1fps + nero** su X headless → flag `--disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling --disable-features=CalculateNativeWinOcclusion`.
- **videoscale CPU a 4K costa ~14fps** → niente scale, cattura nativa 3839x2159.
- **ffmpeg NVENC**: la static johnvansickle NON ha nvenc; BtbN *master* vuole driver 610+ → usa **BtbN n7.1** (driver 580). Per registrare basta gstreamer `nvh264enc`.
- **OAuth YouTube**: se il refresh token scade → rigenera con `node get-token.js` (serve CLIENT_ID+CLIENT_SECRET nel .env; apre il browser per il consenso). L'`AIzaSy…` è una API key, NON il secret.
