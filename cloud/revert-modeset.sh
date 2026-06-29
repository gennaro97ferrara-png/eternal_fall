#!/usr/bin/env bash
# Annulla nvidia-drm.modeset=1: ripristina il GRUB di backup. Poi serve un reboot.
# Uso (anche da console seriale di recupero):  sudo bash /tmp/revert-modeset.sh && sudo reboot
set -euo pipefail
GRUB=/etc/default/grub
BAK=/etc/default/grub.bak-modeset
[ "$(id -u)" -eq 0 ] || { echo "Esegui con sudo: sudo bash $0"; exit 1; }

if [ -f "$BAK" ]; then
  cp -a "$BAK" "$GRUB"
  update-grub 2>&1 | tail -2
  echo "OK ✓ GRUB ripristinato (modeset rimosso). Riavvia per tornare allo stato precedente: sudo reboot"
else
  # fallback: rimuovi il parametro a mano
  sed -i 's/ *nvidia-drm.modeset=1//g' "$GRUB"
  update-grub 2>&1 | tail -2
  echo "OK ✓ parametro rimosso (backup non trovato, pulizia manuale). Riavvia: sudo reboot"
fi
