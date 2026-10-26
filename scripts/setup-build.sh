#!/usr/bin/env bash
# Descarga las capas de Yocto y crea el directorio de build con la plantilla EdgeAI.
#
#   ./scripts/setup-build.sh          prepara las capas wrynose
#   ./scripts/setup-build.sh --lock   además guarda las revisiones exactas en layers.lock
#   ./scripts/setup-build.sh --existing --lock   usa capas existentes sin cambiarlas
#
# Si layers.lock existe, se usan esas revisiones (build reproducible para todo el equipo).
set -euo pipefail
source "$(dirname "$0")/common.sh"

LOCK=0
EXISTING="${EDGEAI_EXISTING_LAYERS:-0}"
for argument in "$@"; do
    case "$argument" in
        --lock) LOCK=1 ;;
        --existing) EXISTING=1 ;;
        *) die "Opcion desconocida: $argument" ;;
    esac
done
case "$MACHINE" in
    raspberrypi4-64|qemuarm64) ;;
    *) die "MACHINE no soportada: $MACHINE" ;;
esac

locked_rev() {
    [ -f "$LOCK_FILE" ] || return 0
    awk -v n="$1" '$1 == n {print $2}' "$LOCK_FILE"
}

mkdir -p "$SOURCES_DIR"
for entry in "${LAYER_REPOS[@]}"; do
    name="${entry%%|*}"
    url="${entry##*|}"
    dir="$SOURCES_DIR/$name"
    rev="$(locked_rev "$name")"
    branch="$YOCTO_BRANCH"
    [[ "$name" != bitbake ]] || branch="$BITBAKE_BRANCH"
    if [[ "$EXISTING" == 1 ]]; then
        git -C "$dir" rev-parse HEAD > /dev/null || die "Falta la capa $name"
        [[ -z "$(git -C "$dir" status --porcelain)" ]] || die "La capa $name tiene cambios locales"
        if [[ "$LOCK" != 1 && -n "$rev" && "$(git -C "$dir" rev-parse HEAD)" != "$rev" ]]; then
            die "$name no coincide con layers.lock; no se modificaron las capas existentes"
        fi
        continue
    fi
    if [ ! -d "$dir/.git" ]; then
        info "Clonando $name ($branch)"
        git clone --branch "$branch" "$url" "$dir"
    else
        [[ -z "$(git -C "$dir" status --porcelain)" ]] || die "La capa $name tiene cambios locales"
        info "Actualizando $name"
        git -C "$dir" fetch origin
    fi
    if [ -n "$rev" ]; then
        info "  $name fijado en $rev (layers.lock)"
        git -C "$dir" checkout --quiet "$rev"
    else
        git -C "$dir" checkout --quiet "$branch"
        git -C "$dir" merge --ff-only --quiet "origin/$branch"
    fi
done

if [ "$LOCK" -eq 1 ]; then
    : > "$LOCK_FILE"
    for entry in "${LAYER_REPOS[@]}"; do
        name="${entry%%|*}"
        echo "$name $(git -C "$SOURCES_DIR/$name" rev-parse HEAD)" >> "$LOCK_FILE"
    done
    info "Revisiones guardadas en layers.lock (agréguelo al repositorio)"
fi

if [ ! -f "$BUILD_DIR/conf/local.conf" ]; then
    info "Creando $BUILD_DIR con la plantilla meta-edgeai/conf/templates/edgeai"
else
    info "Usando la configuración existente en $BUILD_DIR/conf"
fi
load_build_env
printf 'MACHINE = "%s"\nDL_DIR = "%s"\nSSTATE_DIR = "%s"\n' \
    "$MACHINE" "$DL_DIR" "$SSTATE_DIR" > "$BUILD_DIR/conf/auto.conf"

if [ ! -f "$REPO_ROOT/edgeai-secrets.conf" ]; then
    cp "$REPO_ROOT/edgeai-secrets.conf.example" "$REPO_ROOT/edgeai-secrets.conf"
    chmod 0600 "$REPO_ROOT/edgeai-secrets.conf"
    info "Se creó edgeai-secrets.conf (Wi-Fi y contraseña de root, opcional)"
fi

info "Capas activas:"
bitbake-layers show-layers
cat <<TXT

Listo. Siguiente paso:
    MACHINE=$MACHINE ./scripts/build-image.sh

O manualmente:
    source $SOURCES_DIR/openembedded-core/oe-init-build-env $BUILD_DIR $SOURCES_DIR/bitbake
    bitbake $IMAGE
TXT
