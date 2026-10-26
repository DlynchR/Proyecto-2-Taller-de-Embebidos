#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
deploy="$(deploy_dir)"
output="$REPO_ROOT/artifacts/$MACHINE"
mkdir -p "$output"
base="$IMAGE-$MACHINE.rootfs"
if [[ "$MACHINE" == qemuarm64 ]]; then
    cp -L "$deploy/$base.ext4" "$deploy/$base.qemuboot.conf" "$output/"
    kernel="$(readlink -f "$deploy/Image")"
    cp "$kernel" "$output/"
    cp "$kernel" "$output/Image"
else
    cp -L "$deploy/$base.wic.bz2" "$deploy/$base.wic.bmap" "$output/"
fi
cp -L "$deploy/$base.manifest" "$output/"
cp "$REPO_ROOT/layers.lock" "$REPO_ROOT/models.lock.json" "$output/"
git -C "$REPO_ROOT" rev-parse HEAD > "$output/COMMIT"
cd "$output"
mapfile -d '' -t files < <(find . -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z)
sha256sum "${files[@]}" > SHA256SUMS
info "Artefactos: $output"