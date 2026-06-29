#!/usr/bin/env bash
# Abilita nvidia-drm.modeset=1 (per NvFBC / cattura schermo zero-copy 4K60).
# Fa un backup di /etc/default/grub e NON riavvia (il reboot lo fai tu quando vuoi).
# Uso:  sudo bash /tmp/enable-modeset.sh
set -euo pipefail
GRUB=/etc/default/grub
BAK=/etc/default/grub.bak-modeset
[ "$(id -u)" -eq 0 ] || { echo "Esegui con sudo: sudo bash $0"; exit 1; }

[ -f "$BAK" ] || cp -a "$GRUB" "$BAK"
echo "[1/3] backup GRUB → $BAK"

if grep -q 'nvidia-drm.modeset=1' "$GRUB"; then
  echo "[2/3] nvidia-drm.modeset=1 già presente"
else
  sed -i 's/^\(GRUB_CMDLINE_LINUX="[^"]*\)"/\1 nvidia-drm.modeset=1"/' "$GRUB"
  echo "[2/3] aggiunto nvidia-drm.modeset=1 a GRUB_CMDLINE_LINUX"
fi
grep -nE '^GRUB_CMDLINE_LINUX=' "$GRUB" | sed 's/^/      /'

echo "[3/3] update-grub…"
update-grub 2>&1 | tail -2
if grep -q 'nvidia-drm.modeset=1' /boot/grub/grub.cfg; then
  echo "OK ✓ parametro presente in /boot/grub/grub.cfg"
  echo
  echo ">>> Tutto pronto. Quando vuoi (meglio con pochi spettatori):  sudo reboot"
  echo ">>> Per annullare prima del reboot:  sudo bash /tmp/revert-modeset.sh"
else
  echo "ATTENZIONE: parametro NON trovato in grub.cfg — NON riavviare, avvisa Claude."
  exit 1
fi
