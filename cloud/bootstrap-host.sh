#!/usr/bin/env bash
# Bootstrap di un host Ubuntu (es. Hetzner GEX44) per la live nel cloud:
# installa Docker + driver NVIDIA + nvidia-container-toolkit. Idempotente.
# Lanciato in automatico da deploy.sh via ssh; eseguibile anche a mano (come root).
set -euo pipefail
echo "[bootstrap] host: $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-?}")"

SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

# ── Docker ──
if ! command -v docker >/dev/null 2>&1; then
  echo "[bootstrap] installo Docker…"
  curl -fsSL https://get.docker.com | $SUDO sh
fi
# l'utente non-root deve poter usare docker senza sudo (attivo al prossimo login SSH)
[ -n "${SUDO_USER:-}" ] && $SUDO usermod -aG docker "$SUDO_USER" 2>/dev/null || true

# ── Driver NVIDIA ──
if ! nvidia-smi >/dev/null 2>&1; then
  echo "[bootstrap] installo i driver NVIDIA (server)…"
  $SUDO apt-get update
  $SUDO apt-get install -y ubuntu-drivers-common
  $SUDO ubuntu-drivers install --gpgpu 2>/dev/null || $SUDO apt-get install -y nvidia-driver-550-server
  echo "[bootstrap] ⚠ Driver installato. Spesso serve un REBOOT prima che la GPU sia usabile."
  echo "[bootstrap]   Riavvia l'host:  reboot   poi rilancia  cloud/deploy.sh utente@host"
fi

# ── NVIDIA Container Toolkit ──
if ! command -v nvidia-ctk >/dev/null 2>&1; then
  echo "[bootstrap] installo nvidia-container-toolkit…"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | $SUDO gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | $SUDO tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
  $SUDO apt-get update && $SUDO apt-get install -y nvidia-container-toolkit
fi
$SUDO nvidia-ctk runtime configure --runtime=docker
$SUDO systemctl restart docker

# ── verifica finale ──
if nvidia-smi >/dev/null 2>&1; then
  echo "[bootstrap] GPU OK: $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader)"
  echo "[bootstrap] test GPU dentro un container…"
  if $SUDO docker run --rm --gpus all ubuntu:24.04 nvidia-smi -L >/dev/null 2>&1; then
    echo "[bootstrap] ✓ il container vede la GPU — pronto per il deploy."
    echo "[bootstrap] completato."
  else
    echo "[bootstrap] ⚠ il container NON vede ancora la GPU (tipico dopo l'installazione:"
    echo "[bootstrap]   kernel aggiornato e/o runtime docker da ricaricare). Serve un REBOOT."
    exit 42   # segnale per deploy.sh: riavvia e rilancia
  fi
else
  echo "[bootstrap] ⚠ GPU non ancora attiva: serve un REBOOT del server."
  exit 42   # segnale per deploy.sh: riavvia e rilancia
fi
