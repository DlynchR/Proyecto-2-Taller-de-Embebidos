#!/usr/bin/env bash
# Graba la imagen EdgeAI en una microSD.
#
#   ./scripts/flash-sd.sh /dev/sdX                 # usa la última imagen construida
#   ./scripts/flash-sd.sh /dev/sdX imagen.wic.bz2  # o una imagen específica
#
# ¡Borra todo el contenido del dispositivo! Verifique con 'lsblk' cuál es la microSD.
set -euo pipefail
source "$(dirname "$0")/common.sh"

DEV="${1:-}"
WIC="${2:-}"
[ -n "$DEV" ] || die "Uso: $0 /dev/sdX [imagen.wic.bz2]"
[ -b "$DEV" ] || die "$DEV no es un dispositivo de bloques"
[ "$(lsblk -dno TYPE "$DEV")" = "disk" ] || die "Indique el disco completo (p. ej. /dev/sdb o /dev/mmcblk0), no una partición"

# Protección: nunca grabar sobre el disco del sistema.
root_src="$(findmnt -n -o SOURCE / || true)"
root_disk="/dev/$(lsblk -no PKNAME "$root_src" 2> /dev/null || true)"
[ "$DEV" != "$root_disk" ] || die "$DEV contiene el sistema operativo actual"

if [ -z "$WIC" ]; then
    WIC="$(latest_wic)"
    [ -n "$WIC" ] || die "No hay imagen construida. Ejecute ./scripts/build-image.sh"
fi
[ -f "$WIC" ] || die "No existe $WIC"
BMAP="${WIC%.bz2}"; BMAP="${BMAP}.bmap"

info "Imagen:      $WIC"
info "Dispositivo: $DEV"
lsblk -o NAME,SIZE,MODEL,TRAN,MOUNTPOINTS "$DEV" || true
size_bytes=$(lsblk -bdno SIZE "$DEV")
[ "$size_bytes" -ge 15000000000 ] || warn "La tarjeta tiene menos de 16 GB: la imagen (~7.5 GB) puede no caber si se cambió IMAGE_ROOTFS_EXTRA_SPACE"
echo
read -r -p "Se BORRARÁ todo en $DEV. Escriba el nombre del dispositivo para confirmar ($DEV): " answer
[ "$answer" = "$DEV" ] || die "Cancelado"

info "Desmontando particiones de $DEV"
for part in $(lsblk -nlo NAME "$DEV" | tail -n +2); do
    sudo umount "/dev/$part" 2> /dev/null || true
done

if command -v bmaptool > /dev/null 2>&1 && [ -f "$BMAP" ]; then
    info "Grabando con bmaptool (solo copia los bloques usados)"
    sudo bmaptool copy --bmap "$BMAP" "$WIC" "$DEV"
else
    warn "bmaptool no disponible: se usa dd (más lento)"
    bzcat "$WIC" | sudo dd of="$DEV" bs=4M conv=fsync status=progress
fi
sync
info "Listo. Inserte la microSD en la Raspberry Pi 4 y enciéndala."
