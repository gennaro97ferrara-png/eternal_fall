# Eternal Fall — la live su TensorDock (economica)

TensorDock costa circa **metà** di un dedicato GPU (~$90–120/mese), con **banda
gratis** e GPU vere con NVENC. È un **marketplace**: in cambio del prezzo basso,
l'affidabilità dipende dall'host che scegli → segui i 2 accorgimenti qui sotto e va
benissimo per una live artistica (il kit si auto-ripristina dai crash; il rischio
vero è solo l'host che sparisce, e in quel caso ridistribuisci con un comando).

> Guida "blindata" alternativa (dedicato Hetzner, ~184 €): [README-cloud.md](README-cloud.md).

## 1. Crea la VM su TensorDock

[dashboard.tensordock.com/deploy](https://dashboard.tensordock.com/deploy) → **Deploy**:

- **GPU:**
  - **RTX A5000 24GB** → consigliata col tuo budget (~$0,14–0,22/h ≈ $100–160/mese):
    margine per **1440p60** e nessun calo a 1080p60.
  - **RTX A4000 16GB** → la più economica (~$0,08/h ≈ ~$90/mese): perfetta a **1080p60**.
  - (Entrambe Ampere → encoder **h264_nvenc / hevc_nvenc**. *No AV1*: è solo su Ada.)
- **CPU/RAM/Disco:** **4–6 vCPU**, **8–16 GB RAM**, **~50 GB SSD** (non scendere troppo:
  Chromium + scena + texture 8K hanno bisogno di un po' di RAM).
- **OS:** Ubuntu **24.04** (o 22.04).
- **SSH key:** aggiungi la tua chiave pubblica (`~/.ssh/id_ed25519.pub`).
- ⭐ **Scegli un host con rating/affidabilità alti** (TensorDock mostra lo storico
  di ogni host): è ciò che fa la differenza, non il prezzo più basso in assoluto.

Annota **IP** e **porta SSH** che ti dà TensorDock (spesso ≠ 22) e il nome **utente**.

## 2. Metti la stream key

Nel `.env` del progetto (root `caduta-eterna/`):
```
YT_STREAM_KEY=la-tua-chiave-da-youtube-studio
```
Per sfruttare l'A5000 a **1440p60** aggiungi anche:
```
RENDER_W=2560
RENDER_H=1440
VBITRATE=16M
VMAXRATE=16M
VBUF=32M
```
(Con A4000 lascia i default 1080p60.) Tutte le opzioni: [.env.cloud.example](.env.cloud.example).

## 3. Deploy con un comando

Dal tuo Mac, passando **utente@IP e la porta SSH** di TensorDock:
```bash
./cloud/deploy.sh user@IP-DELLA-VM PORTA-SSH
# es:  ./cloud/deploy.sh user@1.2.3.4 23456
```
Lo script gestisce da solo porta SSH non standard, utente non-root (usa `sudo` dove
serve) e salta l'installazione del driver se TensorDock l'ha già messo. Fa:
bootstrap (Docker + toolkit) → rsync del progetto → build → avvio. La live va in onda.

## 4. Verifica

```bash
ssh -p PORTA user@IP 'cd eternal-fall/cloud && docker compose logs -f'   # cerca "WebGL HARDWARE accelerato ✓"
ssh -p PORTA user@IP nvidia-smi                                          # chrome + ffmpeg sulla GPU
```
Regia (admin.html) via tunnel:
```bash
ssh -p PORTA -L 8099:localhost:8099 user@IP    # poi http://localhost:8099/admin.html
```

## 5. Se un host "sparisce" (raro)

È il limite del marketplace. Per rimettere su la live:
1. Crea una **nuova VM** su TensorDock (host con buon rating).
2. Rilancia `./cloud/deploy.sh user@NUOVO-IP PORTA`.

Il `deploy.sh` ricarica codice + asset via rsync (la prima sync sul nuovo host usa la
tua connessione: è il prezzo da pagare per non aver messo gli asset su storage esterno).
Se in futuro vuoi rendere il cambio-host istantaneo senza usare la tua linea, dimmelo:
aggiungo lo *staging* degli asset su un bucket economico.

## Promemoria

- **Affidabilità:** nessun SLA enterprise — scegli host ben valutati, il kit si
  auto-riavvia dai crash, e tieni il `.env` salvato anche in locale.
- **Costo:** ~$90 (A4000) / ~$100–160 (A5000) al mese, **banda inclusa**.
- **Niente OBS:** Chromium GPU + `ffmpeg` NVENC, dentro un container.
