# HANDOFF — Eternal Fall live nel cloud (4K60 via NvFBC)

> Documento per riprendere il lavoro in una nuova sessione. Stato al 2026-06-29, notte.

## TL;DR — dove siamo
La live 24/7 di **Eternal Fall** gira nel **cloud su GPU Mart (RTX A4000)** in un container Docker.
Dopo una lunga battaglia abbiamo ottenuto **4K60 catturato sulla GPU** (gpu-screen-recorder / NvFBC su
finestra Chrome). La pipeline sorgente è **verificata funzionante**: 4K60, audio, keyframe ogni 2s.

**ULTIMO STEP IN CORSO (da completare):**
1. Appena applicato un fix alla **race dell'audio** (gsr partiva prima che PulseAudio creasse il sink →
   `Audio device 'stream.monitor' is not a valid audio device`). Va fatto il **rebuild** e verificato che gsr
   parta pulito (con audio, senza fallback).
2. Poi **creare una diretta YouTube NUOVA** (le vecchie si incastrano su "Preparazione" dopo i restart).
3. Comandi:
   ```bash
   cd /Users/gennaroferrara/explain/caduta-eterna && ./cloud/deploy.sh administrator@108.181.152.249
   ssh administrator@108.181.152.249 'cd eternal-fall/cloud && sleep 25 && docker compose logs --tail=8 | grep -E "gpu-screen|fallback|caduta"; docker exec eternal-fall sh -c "grep -ivE \"update fps|damage fps\" /tmp/gsr.log | tail -6"'
   ```
   Atteso: `gpu-screen-recorder (NvFBC finestra 0x…) → YouTube`, niente `Audio device … not valid`, niente `fallback`.

## Accessi & percorsi
- **Server**: GPU Mart, `administrator@108.181.152.249` (chiave SSH già caricata, sudo = password di administrator).
  GPU: RTX A4000, driver 560.31.02, **24 core**, **`nvidia-drm.modeset=N`** (importante, vedi sotto).
- **Progetto sul server**: `~/eternal-fall` (montato in `/app` nel container). Kit in `~/eternal-fall/cloud`.
- **Progetto in locale (Mac)**: `/Users/gennaroferrara/explain/caduta-eterna`. Kit in `cloud/`.
- **Deploy**: `./cloud/deploy.sh administrator@108.181.152.249` (bootstrap idempotente + rsync + build + recreate).
- **Stream key YouTube**: in `~/eternal-fall/.env` come `YT_STREAM_KEY` (sensibile — valutare rotazione su YT Studio).

## Architettura della soluzione (com'è fatta ORA)
Un solo container (`cloud/Dockerfile` + `cloud/entrypoint.sh`):
1. **PulseAudio** system-mode, null-sink `stream` (monitor = `stream.monitor`).
2. **Display**: prova **Xorg+NVIDIA** (per NvFBC); se non parte → fallback **Xvfb** + ffmpeg x11grab.
3. **Chrome** kiosk su `?live=1` (render WebGL su GPU via EGL).
4. **Cattura**: **gpu-screen-recorder** cattura la **finestra Chrome** (`-w <id>`) sulla GPU → NVENC → RTMP YouTube.
   Fallback automatico a ffmpeg x11grab se Xorg/gsr non parte (la live non si rompe mai).
5. Supervisione 24/7 (riavvio di ciò che cade).

## I 10 ostacoli risolti (NON rifare questi errori)
1. **WebGL software con ANGLE vulkan** (manca ICD Vulkan) → usare `ANGLE_BACKEND=gl-egl` + forzare EGL NVIDIA
   (`__EGL_VENDOR_LIBRARY_FILENAMES=…/10_nvidia.json`). Il log "WebGL software" dell'entrypoint è un **falso positivo**.
2. **NVENC**: ffmpeg "master" di BtbN vuole driver 610+ → usare **ffmpeg di Ubuntu** (apt).
3. **Auto-scaler della scena** taglia la qualità in cattura → **disattivato in live** (in `index.html`,
   `autoscale()`: `if(window.obsstudio||/[?&]live=1/.test(location.search)) return;`). + `DEVICE_SCALE_FACTOR=2` per UI leggibile a 4K + `--window-size=RENDER/DSF` (altrimenti cattura 1/4 schermo).
4. **Popup Google Translate** → policy `/etc/opt/chrome/policies/managed/…json` con `{"TranslateEnabled":false}`.
5. **Anti-banding** scena scura → ffmpeg `-spatial-aq 1 -temporal-aq 1` (path ffmpeg).
6. **x11grab non regge 4K60** (single-thread, frame duplicati) → serve cattura GPU = **gpu-screen-recorder**.
7. **gsr da compilare** (no apt): deps `meson ninja-build cmake libpipewire-0.3-dev libdbus-1-dev libvulkan-dev` + x11/wayland/ffmpeg-dev; **patch root-check** `sed s/if(geteuid() == 0)/if(0)/ src/main.cpp`.
8. **Xorg+NVIDIA crasha** caricando `libglxserver_nvidia.so` (libnvidia-glcore) → **rimuovere quel modulo** prima di avviare Xorg (Chrome usa EGL, gsr la GLX generica). NON usare `-extension GLX` (la GLX generica serve a gsr per il fbconfig).
9. **`modeset=N`** → Xorg headless **non espone output monitor** → gsr `-w screen` fallisce ("no usable output") → catturare la **FINESTRA**: `gpu-screen-recorder -w <window_id> -s WxH …`. Window id trovato per nome con `xwininfo … | grep "google chrome"`. (`-w focused` è fragile senza WM → id 0 = nero.)
10. **Chrome divorava la GPU** (`--disable-gpu-vsync --disable-frame-rate-limit` = render senza cap → 93% GPU, fps ballerini) → **rimossi quei flag** → Chrome si sincronizza a 60Hz → **GPU scesa al 37%, 4K60 stabile**. ← *Questo ha sbloccato il 4K60.*
11. **YouTube "Preparazione" infinita / nero a intermittenza** → keyframe troppo radi → gsr `-keyint 2`.
12. **Race audio al restart** → gsr aspetta `pactl … | grep stream.monitor` prima di partire (fix appena messo, da verificare).
13. **Cattura CONGELATA dopo reboot host (2026-06-29)** — su YouTube si vedeva tutto bloccato + audio assente,
    ma Chrome renderizzava benissimo (verificato via CDP: rAF 60Hz, draw-call ~24k/3s, clock DOM che avanza,
    2 screenshot CDP DIVERSI). Il problema era SOLO la cattura: la finestra Chrome GPU-composita a tutto schermo
    NON aggiornava più la pixmap XComposite che gpu-screen-recorder legge (Xorg headless, modeset=N, nessun
    compositor) → gsr esportava sempre lo stesso frame. **Fix: `--disable-gpu-compositing` nel lancio di Chrome**
    (composizione finale in software → la finestra X si aggiorna; WebGL resta su GPU). Effetto: cattura di nuovo
    fluida, GPU ~28%, encoder ~95%, load ~3.7/24 core (Chrome ~2.3 core in più per il compositing SW). Sostenibile.
    Diagnosi: abilitato `--remote-debugging-port=9222` (loopback) + mini-client CDP `cloud/cdp.js` / `cloud/cdp-eval.js`.
    ATTENZIONE: NON rimuovere `--disable-gpu-compositing`, altrimenti la cattura si ricongela.

## Risultato & limiti
- **4K60 funziona**: gsr 60fps stabili, GPU ~37%/64°C (con il cap di Chrome). Audio presente (sink-input RUNNING).
- **Per il 4K60 con NvFBC dello SCHERMO** (più leggero della cattura-finestra xcomposite) servirebbe
  `nvidia-drm.modeset=1` sull'host → **ticket a GPU Mart** (testo pronto: chiedere di settare `nvidia-drm.modeset=1` e reboot).
  Con la cattura-finestra attuale comunque i 4K60 reggono dopo il fix del cap Chrome.
- `BROWSER_RESTART_HOURS=0` (il restart periodico di Chrome romperebbe la cattura per window-id). Per l'anti-leak: fare semmai un `docker compose restart` giornaliero via cron host.
- **24/7 da indurire**: se Chrome crasha, il window-id cambia → la supervisione riavvia gsr che ri-cerca la finestra (start_gsr ha già il retry su xwininfo). Verificare tenuta nel tempo.

## Config attuale (`~/eternal-fall/.env` sul server)
`RENDER_W=3840 RENDER_H=2160 FPS=60 VBITRATE=45M VMAXRATE=45M VBUF=90M DEVICE_SCALE_FACTOR=2`
`ANGLE_BACKEND=gl-egl BROWSER_RESTART_HOURS=0 YT_STREAM_KEY=…`
(NVENC_PRESET/lookahead/AQ sono per il path ffmpeg di fallback; gsr usa VBITRATE/FPS/RENDER.)

## Comandi utili
```bash
# log live
ssh administrator@108.181.152.249 'cd eternal-fall/cloud && docker compose logs -f'
# gsr fps + GPU
ssh administrator@108.181.152.249 'docker exec eternal-fall sh -c "grep \"update fps\" /tmp/gsr.log | tail"; ssh administrator@108.181.152.249 nvidia-smi'
# comando gsr in esecuzione
ssh administrator@108.181.152.249 'docker exec eternal-fall sh -c "ps -eo args | grep gpu-screen-recorder | grep -v grep"'
# audio (NB: serve PULSE_SERVER nell'exec)
ssh administrator@108.181.152.249 'docker exec -e PULSE_SERVER=unix:/tmp/pulse/native eternal-fall pactl list short sink-inputs'
# cambiare qualità: edita .env (RENDER_W/H, FPS, VBITRATE) poi
ssh administrator@108.181.152.249 'cd eternal-fall/cloud && docker compose up -d --force-recreate'
# regia admin via tunnel
ssh -L 8099:localhost:8099 administrator@108.181.152.249   # http://localhost:8099/admin.html
```

## Se serve scendere di risoluzione (smooth garantito)
Su A4000 il 4K60 regge col cap di Chrome, ma se dà problemi: **2880×1620** (1620p, "3K") o **2560×1440@60**
sono comodissimi. Edita `.env` (RENDER_W/H + DEVICE_SCALE_FACTOR=1 sotto il 4K) e `up -d --force-recreate`.
