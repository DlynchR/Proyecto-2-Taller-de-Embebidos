#!/usr/bin/env bash
set -euo pipefail
export MACHINE=qemuarm64
source "$(dirname "$0")/common.sh"
load_build_env
bitbake "$IMAGE" -c testimage