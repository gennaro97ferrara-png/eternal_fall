#!/usr/bin/env bash
# Eternal Fall — deploy della live nel cloud con UN comando.
#   ./cloud/deploy.sh utente@host [porta-ssh]
#   es. Hetzner:    ./cloud/deploy.sh root@203.0.113.10
#   es. GPU Mart:   ./cloud/deploy.sh administrator@108.181.152.249
# Gestisce: utente non-root (sudo con terminale), porta SSH ≠ 22, gruppo docker.
# Rieseguibile in sicurezza: aggiorna codice/asset e riavvia. NON tocca .env né permanent.json sul server.
set -euo pipefail

HOST="${1:-}"
PORT="${2:-${SSH_PORT:-22}}"
REMOTE_DIR="${REMOTE_DIR:-eternal-fall}"      # relativa alla home → niente sudo per crearla
ROOT="$(cd "$(dirname "$0")/.." && pwd)"      # root del progetto (caduta-eterna/)

if [ -z "$HOST" ]; then
  echo "Uso: $0 utente@host [porta-ssh]"
  echo "  Hetzner:   $0 root@203.0.113.10"
  echo "  GPU Mart:  $0 administrator@108.181.152.249"
  exit 1
fi

REMOTE_USER="${HOST%@*}"; [ "$REMOTE_USER" = "$HOST" ] && REMOTE_USER="$(whoami)"
if [ "$REMOTE_USER" = "root" ]; then SUDO=""; else SUDO="sudo"; fi
SSHO=(-p "$PORT" -o StrictHostKeyChecking=accept-new)
RSH="ssh -p $PORT -o StrictHostKeyChecking=accept-new"

echo "==> 1/4  Bootstrap host (porta $PORT): Docker + driver NVIDIA + toolkit"
scp -P "$PORT" -o StrictHostKeyChecking=accept-new "$ROOT/cloud/bootstrap-host.sh" "$HOST:/tmp/ef-bootstrap.sh"
# -t = terminale vero → sudo può chiedere la password una volta; lo script gira come root
set +e
ssh -t "${SSHO[@]}" "$HOST" "$SUDO bash /tmp/ef-bootstrap.sh"
rc=$?
set -e
if [ "$rc" = 42 ]; then
  echo
  echo "⚠  Il server ha bisogno di un REBOOT (driver NVIDIA appena installato). Fai così:"
  echo "    1) ssh -t ${SSHO[*]} $HOST ${SUDO:+sudo }reboot"
  echo "    2) aspetta ~1 minuto che riparta"
  echo "    3) rilancia:  $0 $HOST $PORT"
  exit 1
elif [ "$rc" != 0 ]; then
  echo "Bootstrap fallito (codice $rc). Guarda l'output qui sopra."
  exit 1
fi

echo
echo "==> 2/4  Sincronizzo il progetto su $HOST:~/$REMOTE_DIR"
echo "         (la PRIMA volta è lenta: salgono gli asset — musica, voce, texture. Poi incrementale.)"
ssh "${SSHO[@]}" "$HOST" "mkdir -p '$REMOTE_DIR'"
rsync -a --delete --partial --progress -e "$RSH" \
  --exclude '.git' --exclude '.idea' --exclude 'node_modules' \
  --exclude '.env' --exclude 'permanent.json' \
  --exclude '*.log' --exclude 'scratchpad' \
  "$ROOT/" "$HOST:$REMOTE_DIR/"

echo
echo "==> 3/4  Controllo il .env sul server"
if ssh "${SSHO[@]}" "$HOST" "test -f '$REMOTE_DIR/.env'"; then
  echo "         .env già presente sul server (lo lascio com'è)."
elif [ -f "$ROOT/.env" ]; then
  echo "         copio il .env locale sul server…"
  scp -P "$PORT" -o StrictHostKeyChecking=accept-new "$ROOT/.env" "$HOST:$REMOTE_DIR/.env"
else
  echo "         ⚠ Nessun .env. Crea ~/$REMOTE_DIR/.env con almeno  YT_STREAM_KEY=la-tua-chiave"
  echo "           Modello: cloud/.env.cloud.example  →  poi rilancia."
  exit 1
fi

echo
echo "==> 4/4  Build & avvio del container"
# grazie al gruppo docker (aggiunto dal bootstrap) la nuova sessione non serve sudo;
# fallback a sudo se per qualche motivo non bastasse.
ssh -t "${SSHO[@]}" "$HOST" "cd '$REMOTE_DIR/cloud' && (docker compose up -d --build || sudo docker compose up -d --build)"

echo
echo "✅  Fatto. Comandi utili:"
echo "    Log live : ssh ${SSHO[*]} $HOST 'cd $REMOTE_DIR/cloud && docker compose logs -f'"
echo "    GPU      : ssh ${SSHO[*]} $HOST nvidia-smi"
echo "    Regia    : ssh ${SSHO[*]} -L 8099:localhost:8099 $HOST   → http://localhost:8099/admin.html"
echo "    Stop     : ssh ${SSHO[*]} $HOST 'cd $REMOTE_DIR/cloud && docker compose down'"
