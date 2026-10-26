#!/usr/bin/env bash
# Variables comunes de los scripts del proyecto EdgeAI (se carga con "source").
# shellcheck disable=SC2034  # las variables las usan los scripts que cargan este archivo

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$REPO_ROOT/edgeai-build.env" ]]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/edgeai-build.env"
fi
SOURCES_DIR="${SOURCES_DIR:-$REPO_ROOT/sources}"
CACHE_DIR="${EDGEAI_CACHE_DIR:-$REPO_ROOT}"
DL_DIR="${DL_DIR:-$CACHE_DIR/downloads}"
SSTATE_DIR="${SSTATE_DIR:-$CACHE_DIR/sstate-cache}"
MACHINE="${MACHINE:-raspberrypi4-64}"
BUILD_DIR="${BUILD_DIR:-$REPO_ROOT/build/$MACHINE}"
YOCTO_BRANCH="${YOCTO_BRANCH:-wrynose}"
IMAGE="${IMAGE:-edgeai-image}"
LOCK_FILE="$REPO_ROOT/layers.lock"
TEMPLATECONF_DIR="$REPO_ROOT/meta-edgeai/conf/templates/edgeai"
BITBAKE_BRANCH="${BITBAKE_BRANCH:-2.18}"

# nombre|url (rama: $YOCTO_BRANCH)
LAYER_REPOS=(
    "openembedded-core|https://git.openembedded.org/openembedded-core"
    "bitbake|https://git.openembedded.org/bitbake"
    "meta-yocto|https://git.yoctoproject.org/meta-yocto"
    "meta-raspberrypi|https://git.yoctoproject.org/meta-raspberrypi"
)

info()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[aviso]\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# Carga el entorno de BitBake (oe-init-build-env) en el shell actual.
load_build_env() {
    [ -f "$SOURCES_DIR/openembedded-core/oe-init-build-env" ] || die "Falta openembedded-core. Ejecute primero: ./scripts/setup-build.sh"
    mkdir -p "$BUILD_DIR"
    # oe-init-build-env no está escrito para 'set -eu': se relaja mientras corre.
    # Deja el shell dentro de $BUILD_DIR, que es donde debe ejecutarse bitbake.
    set +eu
    # shellcheck disable=SC1091
    TEMPLATECONF="$TEMPLATECONF_DIR" source "$SOURCES_DIR/openembedded-core/oe-init-build-env" "$BUILD_DIR" "$SOURCES_DIR/bitbake" > /dev/null
    local rc=$?
    set -eu
    [ "$rc" -eq 0 ] || die "oe-init-build-env falló (código $rc)"
}

deploy_dir() {
    echo "$BUILD_DIR/tmp/deploy/images/$MACHINE"
}

# Ruta de la imagen .wic.bz2 más reciente (vacío si no hay).
latest_wic() {
    find "$(deploy_dir)" -maxdepth 1 -name "${IMAGE}-${MACHINE}*.wic.bz2" -printf '%T@ %p\n' 2> /dev/null \
        | sort -nr | head -n1 | cut -d' ' -f2-
}
