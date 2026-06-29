# Eternal Fall — la live 24/7 nel cloud

Sposta **tutta** la pipeline (render WebGL + `server.js` + cattura + encoding + push
RTMP a YouTube) su un server con GPU. La tua connessione di casa serve **solo per
l'SSH**: lo streaming parte dall'uplink veloce del datacenter. Niente OBS, niente
Mac sempre acceso, qualità identica al locale.

> **Perché non un servizio di restream?** Quello ri-trasmette uno stream che gli
> mandi comunque dalla **tua** linea lenta → non risolve nulla. L'unica vera
> soluzione è far partire l'upload da una macchina con banda larga: il cloud.

## Cosa fa il container

Un solo container fa girare, e tiene in piedi 24/7:
1. **PulseAudio** con un sink virtuale (`stream`) per l'audio del browser
2. **Xvfb** (display virtuale `:0`)
3. **`server.js`** (sito + `/api/stars` per le stelle del pubblico)
4. **Chromium** GPU-accelerato che apre `?live=1` (autostart, audio incluso)
5. **ffmpeg** che cattura schermo+audio e fa push **NVENC → YouTube**
6. un **supervisore**: riavvia ciò che cade e riavvia il browser ogni N ore
   (contro il memory-leak del browser sulle lunghe distanze)

---

## 1. Prendi il server (Hetzner GEX44)

- **Hetzner → Dedicated → GPU → GEX44** (NVIDIA RTX 4000 SFF Ada 20GB).
  ~**184 €/mese** + ~79 € una-tantum. (Da privato senza P.IVA aggiungi il 22% di IVA.)
- Sistema operativo: **Ubuntu 24.04 LTS**.
- Accesso **SSH come root** (chiave SSH consigliata).
- Banda: **illimitata 1 Gbit/s** inclusa → i ~3 TB/mese dello stream sono di fatto gratis.

> La GPU **deve** essere vera: da Chrome 130+ non c'è più il fallback software,
> quindi senza GPU il WebGL non parte proprio. Niente VM solo-CPU.

## 2. Metti la stream key

Nel `.env` del progetto (in locale, nella root `caduta-eterna/`) aggiungi almeno:

```
YT_STREAM_KEY=la-tua-chiave-da-youtube-studio
```

(Le altre opzioni — risoluzione, bitrate, ecc. — sono in
[`.env.cloud.example`](.env.cloud.example). I default sono già 1080p60.)

Se non hai un `.env` locale, creane uno con quella riga; lo script lo copierà sul server.

## 3. Deploy con un comando

Dalla cartella del progetto, sul tuo Mac:

```bash
./cloud/deploy.sh root@IP-DEL-SERVER
```

Lo script, via SSH:
1. installa **Docker + driver NVIDIA + nvidia-container-toolkit** (idempotente);
2. **rsync** del progetto su `/opt/eternal-fall` (la prima volta è lenta: salgono
   gli asset — musica, voce, texture; poi è incrementale);
3. copia il `.env` se manca sul server;
4. **build** dell'immagine e **avvio** del container.

> **Reboot dopo i driver:** la prima volta, dopo l'installazione del driver NVIDIA
> spesso serve un riavvio. Se lo script lo segnala: `ssh root@IP reboot`, aspetta un
> minuto e **rilancia `deploy.sh`**. Il deploy riparte da dove era.

A fine corsa la live è in onda. Su YouTube Studio vedrai il segnale arrivare.

## 4. Verifica che vada (e che sia su GPU)

```bash
# log in tempo reale (cerca "WebGL HARDWARE accelerato ✓" e "ffmpeg → YouTube")
ssh root@IP 'cd /opt/eternal-fall/cloud && docker compose logs -f'

# uso GPU: deve mostrare i processi chrome + ffmpeg
ssh root@IP nvidia-smi
```

Se vedi **"WebGL forse NON su GPU"** nei log → vedi *Troubleshooting* sotto.

## 5. Regia / admin (admin.html)

L'admin è esposto **solo su loopback** del server (il token è debole): raggiungilo
con un tunnel SSH, non aprirlo in pubblico.

```bash
ssh -L 8099:localhost:8099 root@IP
# poi nel browser:  http://localhost:8099/admin.html
```

> **Cambia `ADMIN_TOKEN`** nel `.env` (è ancora `eternalfall`). Anche dietro tunnel,
> meglio un token forte.

## 6. Aggiornare la live

Hai modificato `index.html`, la musica, gli asset? Ridai semplicemente:

```bash
./cloud/deploy.sh root@IP-DEL-SERVER
```

rsync manda solo le differenze e il container riparte. `.env` e `permanent.json`
sul server **non** vengono toccati.

## 7. Qualità: 1080p60 → 1440p60

La banda è inclusa, quindi puoi alzare. Nel `.env`:

```
RENDER_W=2560
RENDER_H=1440
VBITRATE=16M
VMAXRATE=16M
VBUF=32M
```

e ridai `deploy.sh`. Per la massima nitidezza "retina" senza cambiare risoluzione di
uscita, usa il supersampling (render 1440 → output 1080): vedi `.env.cloud.example`.

---

## Costi (promemoria)

| Voce | Costo |
|---|---|
| Hetzner GEX44 | ~184 €/mese (+IVA da privato) + ~79 € setup |
| Banda (3–5 TB/mese) | **inclusa** (0 €) |
| **Totale** | **~184–224 €/mese** |

Da evitare per il 24/7: **AWS/GCP/Azure** (l'egress da solo è 250–660 $/mese,
*prima* della GPU) e le istanze **spot/preemptible** (ti staccano lo stream).

## Comandi rapidi

```bash
ssh root@IP 'cd /opt/eternal-fall/cloud && docker compose logs -f'      # log
ssh root@IP 'cd /opt/eternal-fall/cloud && docker compose restart'     # riavvia
ssh root@IP 'cd /opt/eternal-fall/cloud && docker compose down'        # ferma
ssh root@IP 'cd /opt/eternal-fall/cloud && docker compose up -d --build' # ricostruisci
ssh root@IP 'docker exec eternal-fall cat /tmp/ffmpeg.log'             # log ffmpeg
ssh root@IP 'docker exec eternal-fall cat /tmp/chrome.log'             # log chrome
```

## Troubleshooting

**"WebGL forse NON su GPU" / scena a scatti**
- `ssh root@IP nvidia-smi` deve funzionare. Se no → driver mancante: rilancia
  `cloud/bootstrap-host.sh` e **reboot**.
- Prova il backend GL classico: nel `.env` metti `ANGLE_BACKEND=gl-egl`, ridai deploy.
- Verifica dal container: `docker exec eternal-fall google-chrome-stable --headless=new
  --no-sandbox --use-gl=angle --use-angle=vulkan --dump-dom chrome://gpu | grep -i webgl`.

**Schermo nero su YouTube ma audio ok**
- Quasi sempre è la cattura GPU↔X: prova `ANGLE_BACKEND=gl-egl`.
- Controlla `docker exec eternal-fall cat /tmp/chrome.log` per errori di contesto WebGL.

**Niente audio**
- `docker exec eternal-fall pactl list short sinks` deve elencare `stream`.
- Verifica che la scena sia partita in modalità live (l'audio parte solo dopo `begin()`,
  che `?live=1` chiama da solo).

**ffmpeg si disconnette da YouTube**
- Normale ogni tanto: il supervisore riconnette da solo (vedi i log).
- Se è continuo, abbassa `VBITRATE` o controlla che la stream key sia giusta.

**Il container non vede la GPU**
- `docker run --rm --runtime=nvidia --gpus all nvidia/cuda:12.4.1-base-ubuntu24.04 nvidia-smi -L`
  deve elencare la scheda. Se no: `nvidia-ctk runtime configure --runtime=docker && systemctl restart docker`.

**Il contatore GIORNO N è ripartito da 1**
- Il profilo Chromium (con il `localStorage` `ce_launch`) è su un volume Docker
  (`chrome-profile`), quindi sopravvive ai riavvii. Migrando dal Mac riparte però da
  zero: per ancorarlo alla data originale, apri `admin.html` via tunnel oppure imposta
  a mano `ce_launch` nel `localStorage` dalla console del browser (DevTools remoto).
