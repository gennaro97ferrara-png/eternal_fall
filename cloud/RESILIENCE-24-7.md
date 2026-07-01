# Resilienza 24/7 — perché la live è caduta a 28h e come è stata indurita

## Cosa è successo (2026-06-30/07-01)
La live su **Vast.ai VM (RTX 3060 Ti, 4K60)** è caduta dopo **~28h47m**.
Diagnosi (YouTube Data API, VOD `8EiIZTYjRCo`):

```
actualStartTime: 2026-06-29T16:45:28Z
actualEndTime:   2026-06-30T21:33:05Z   → durata 28h47m
liveBroadcastContent: none
```

- La **VM non è mai caduta** (uptime > 2 giorni), né Xorg/Chrome/server.js.
- YouTube ha **terminato il broadcast** su un blip di rete. ffmpeg però ha continuato a
  bufferare TCP verso l'ingest per **~12h** senza accorgersene (`Connection reset by peer`
  solo alle 10:03 del giorno dopo) → spingeva su un ingest **zombie**, nessun broadcast
  pubblico legato → live "giù" pur con ffmpeg vivo.
- Ripristino: l'utente aveva armato un nuovo broadcast `WSQqm-YiZwE` (upcoming), ma una
  connessione ffmpeg **stantia** (precedente alla creazione del broadcast) non lo faceva
  transitare a `live`. **Una riconnessione ffmpeg FRESCA → auto-start immediato.** (verificato)

## Indurimento applicato (systemd, enabled → sopravvive a crash E reboot)
Prima solo `server.js` era su systemd (per giunta *transient* → non sopravviveva al reboot);
Xorg/Chrome/streamloop erano processi `setsid` sciolti → **un reboot = blackout totale**.

- **`ef-server.service`** — convertito da transient a **persistente + enabled**, `Restart=always`.
- **`ef-supervise.service`** (`ef-supervise.sh`) — babysitter dei processi: PulseAudio, Xorg :0,
  Chrome `?live=1`, ef-server, streamloop+ffmpeg. (Ri)avvia solo ciò che è giù; azioni disruptive
  (Xorg/Chrome) solo dopo N controlli falliti di fila (anti falso-positivo). Recovery crash+reboot.
- **`ef-monitor.service`** (`ef-monitor.py`) — self-heal del broadcast YouTube: ogni 60s rileva a
  bassa latenza (playlist uploads) se il canale è live/upcoming. Se live → sincronizza `YT_VIDEO_ID`
  nel `.env` (chat/comandi sul broadcast giusto). Se non live ma **upcoming armato** → forza una
  riconnessione ffmpeg fresca (con cooldown) → auto-start. Se né live né upcoming → logga OUTAGE.

Installazione: `bash cloud/install-hardening.sh` (idempotente). La stream key si legge da
`.env` (`YT_STREAM_KEY`, gitignorato) — mai hardcoded.

## Cosa resta al di là dell'automazione (limiti onesti)
1. **Impedire a YouTube di terminare il broadcast su un blip** = in YouTube Studio → impostazioni
   dello stream → **disattivare "auto-stop"** (così un'interruzione breve non chiude la diretta).
   È l'unico vero fix lato-YouTube per i blip; non è modificabile via API-key (serve la UI o OAuth).
2. **Auto-ricreare un broadcast quando finisce davvero** richiede **OAuth in scrittura**
   (`youtube.force-ssl`) — oggi c'è solo la API-key in lettura. Con quello, `ef-monitor` potrebbe
   creare+bindare+transizionare una nuova diretta da solo. `get-token.js` va aggiornato allo scope
   di scrittura + consenso interattivo una volta.
