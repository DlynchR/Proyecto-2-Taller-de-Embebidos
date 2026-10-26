#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
mkdir -p "$CACHE_DIR" "$REPO_ROOT/logs"
exec 9> "$CACHE_DIR/edgeai-build.lock"
flock 9
cd "$REPO_ROOT"
./scripts/prepare-models.sh
for machine in qemuarm64 raspberrypi4-64; do
    MACHINE="$machine" BUILD_DIR="$REPO_ROOT/build/$machine" ./scripts/setup-build.sh
    MACHINE="$machine" BUILD_DIR="$REPO_ROOT/build/$machine" ./scripts/build-image.sh
    if [[ "$machine" == qemuarm64 ]]; then
        BUILD_DIR="$REPO_ROOT/build/qemuarm64" ./scripts/test-qemu.sh
    fi
    MACHINE="$machine" BUILD_DIR="$REPO_ROOT/build/$machine" ./scripts/collect-artifacts.sh
done