#!/usr/bin/env bash
# Actualiza la receta de Ollama a otra versión publicada en GitHub.
#
#   ./scripts/update-ollama.sh 0.40.7
#
# Descarga sha256sum.txt del release, toma el hash de ollama-linux-arm64.tar.zst,
# renombra la receta (ollama-bin_<versión>.bb) y actualiza SRC_URI[sha256sum].
set -euo pipefail
source "$(dirname "$0")/common.sh"

VERSION="${1:-}"
[ -n "$VERSION" ] || die "Uso: $0 <versión>   (ej. 0.40.7; requiere >= 0.35 para /v1/systemone)"
VERSION="${VERSION#v}"
RECIPE_DIR="$REPO_ROOT/meta-edgeai/recipes-ai/ollama"
current="$(ls "$RECIPE_DIR"/ollama-bin_*.bb)"

url="https://github.com/ollama/ollama/releases/download/v${VERSION}/sha256sum.txt"
info "Consultando $url"
sums="$(curl -fsSL "$url")" || die "No se pudo descargar $url (¿existe la versión?)"
hash="$(printf '%s\n' "$sums" | awk '$2 ~ /(^|\/|\*)ollama-linux-arm64\.tar\.zst$/ {print $1}')"
[[ "$hash" =~ ^[0-9a-f]{64}$ ]] || die "No encontré el hash de ollama-linux-arm64.tar.zst en sha256sum.txt"

new="$RECIPE_DIR/ollama-bin_${VERSION}.bb"
if [ "$current" != "$new" ]; then
    if git -C "$REPO_ROOT" ls-files --error-unmatch "$current" > /dev/null 2>&1; then
        git -C "$REPO_ROOT" mv "$current" "$new"
    else
        mv "$current" "$new"
    fi
fi
sed -i "s/^SRC_URI\[sha256sum\] = .*/SRC_URI[sha256sum] = \"${hash}\"/" "$new"
info "Receta: $(basename "$new")"
info "sha256: $hash"
