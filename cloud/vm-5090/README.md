# Deploy VM RTX 5090 (Vast.ai) — Eternal Fall 4K60

Ricetta provata 2026-07-04. VM: RTX 5090 + Ryzen, Ubuntu 22.04, Chrome + ffmpeg(nvenc).

## Setup (una volta)
1. `apt install -y nodejs ffmpeg mesa-utils pulseaudio-utils`
2. **Display 4K** (NVIDIA headless via CustomEDID): copia `xorg-4k.conf`→`/etc/X11/`, l'EDID
   4K (hex in `startx4k.sh`), poi `setsid nohup bash startx4k.sh &`. Verifica `DISPLAY=:0 xrandr` = 3840x2160.
3. **Codice**: metti `eternal-fall/` in `/root/` (trasferimento veloce box→box: `tar` + cloudflared tunnel).
4. **Voce intro** (opzionale): `gen_intro.py` (serve una chiave ElevenLabs) → `assets/voice/intro.mp3`.

## Avvio supervisionato (server+chrome, auto-restart)
`bash /root/efboot.sh`  → scrive e lancia `sup-server.sh` + `sup-chrome.sh`.
- Perché supervisionato: se `server.js` muore, i nuovi asset vanno in 404 → **quadrati neri**.
  Il loop lo riavvia in 2s. **Non usare mai un server non supervisionato in produzione.**

## Streaming YouTube
Metti la stream key in `/root/.streamkey`, poi `setsid nohup bash /root/sup-stream.sh &`
(RTMP CBR 45Mbps, GOP 2s, NVENC). Auto-restart se YouTube droppa.

## Registrare un episodio
`bash /root/rec.sh <N> [durata_sec]` → `/root/episodes/epN_*.mp4` (x11grab 4K60 + pulse audio + NVENC).

## ★Trappole
- `pkill -f Xorg` / `-f "node server.js"` inline via SSH matcha la **propria shell** → usa `pkill -x`.
- Chrome kiosk: `--use-gl=angle --use-angle=gl --autoplay-policy=no-user-gesture-required`, DSF=1, window 3840x2160.
- URL: `?ultra=1&live=1&ep=N` (live=1 alza l'esposizione per compensare la compressione YouTube).
