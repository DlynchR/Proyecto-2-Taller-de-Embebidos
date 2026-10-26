#!/usr/bin/env bash
set -euo pipefail
export MACHINE=qemuarm64
source "$(dirname "$0")/common.sh"
load_build_env
export QB_SLIRP_OPT="-netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:8080-:80"
runqemu "$MACHINE" "$IMAGE" slirp nographic "$@"