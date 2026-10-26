#!/usr/bin/env bash
# Genera el árbol de dependencias de la imagen para la documentación (rúbrica: análisis
# de dependencias). Resultado en docs/generated/:
#
#   recetas-build.txt          recetas que BitBake construye para la imagen
#   edgeai-build-deps.dot/svg  dependencias de compilación de las recetas propias
#   edgeai-runtime-deps.dot/svg dependencias de ejecución de los paquetes propios
#   paquetes-instalados.txt    paquetes y tamaños dentro de la imagen (buildhistory)
#
# Requiere haber ejecutado setup-build.sh; la parte de runtime requiere un build completo.
set -euo pipefail
source "$(dirname "$0")/common.sh"

OUT="$REPO_ROOT/docs/generated"
mkdir -p "$OUT"
load_build_env

info "bitbake -g $IMAGE (grafo de tareas, no compila nada)"
work="$(mktemp -d)"
# bitbake -g escribe task-depends.dot y pn-buildlist en el directorio de build.
bitbake -g "$IMAGE" > /dev/null
mv "$BUILD_DIR/task-depends.dot" "$BUILD_DIR/pn-buildlist" "$work/"
cp "$work/pn-buildlist" "$OUT/recetas-build.txt"
python3 "$REPO_ROOT/tools/filter_dot.py" "$work/task-depends.dot" \
    --roots ollama-bin edgeai-helpdesk edgeai-network packagegroup-edgeai edgeai-image \
    --depth 1 --tasks > "$OUT/edgeai-build-deps.dot"
rm -rf "$work"

hist="$BUILD_DIR/buildhistory/images/${MACHINE//-/_}/glibc/$IMAGE"
if [ -f "$hist/depends.dot" ]; then
    info "Dependencias de ejecución desde buildhistory"
    python3 "$REPO_ROOT/tools/filter_dot.py" "$hist/depends.dot" \
        --roots ollama-bin edgeai-helpdesk edgeai-network packagegroup-edgeai \
        --depth 2 > "$OUT/edgeai-runtime-deps.dot"
    cp "$hist/installed-package-sizes.txt" "$OUT/paquetes-instalados.txt"
    [ -f "$hist/image-info.txt" ] && cp "$hist/image-info.txt" "$OUT/image-info.txt"
else
    warn "No hay buildhistory de la imagen todavía (construya con ./scripts/build-image.sh)"
fi

if command -v dot > /dev/null 2>&1; then
    for f in "$OUT"/*.dot; do dot -Tsvg "$f" -o "${f%.dot}.svg"; done
    info "SVG generados (graphviz)"
else
    warn "Instale graphviz para generar los SVG: sudo apt install graphviz"
fi
info "Resultados en docs/generated/"
