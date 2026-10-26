#!/usr/bin/env bash
# Construye la imagen edgeai-image para la Raspberry Pi 4.
#
#   ./scripts/build-image.sh                # imagen completa
#   ./scripts/build-image.sh ollama-bin     # cualquier otro objetivo de BitBake
#
# El primer build tarda varias horas (compila toolchain, kernel y userspace);
# los siguientes reutilizan sstate-cache y tardan minutos.
set -euo pipefail
source "$(dirname "$0")/common.sh"

TARGET="${1:-$IMAGE}"
[ -f "$BUILD_DIR/conf/local.conf" ] || die "No existe $BUILD_DIR/conf/local.conf. Ejecute ./scripts/setup-build.sh"

load_build_env
info "bitbake $TARGET  (MACHINE=$MACHINE)"
start=$(date +%s)
bitbake "$TARGET"
mins=$(( ($(date +%s) - start) / 60 ))
info "Terminado en ${mins} min"

if [ "$TARGET" = "$IMAGE" ]; then
    wic="$(latest_wic)"
    [ -n "$wic" ] || die "No se encontró la imagen .wic.bz2 en $(deploy_dir)"
    info "Imagen: $wic"
    info "Tamaño comprimido: $(du -h "$wic" | cut -f1)"
    cat <<TXT

Grabar en la microSD (16 GB o más):
    ./scripts/flash-sd.sh /dev/sdX
TXT
fi