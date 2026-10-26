#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

lock="$REPO_ROOT/models.lock.json"
models_dir="${EDGEAI_MODELS_DIR:-$CACHE_DIR/ollama-models}"
output="$REPO_ROOT/models/ollama-models.tar"
jq -e '.models | length > 0' "$lock" > /dev/null
jq -e '.models | to_entries | all(.[];
    (.key | test("^[a-z0-9.]+:[a-z0-9.]+$")) and
    ([.value.config] + .value.layers | all(.[];
        (.digest | test("^sha256:[a-f0-9]{64}$")) and (.size > 0))))' "$lock" > /dev/null
if [[ "${1:-}" == --check ]]; then
    info "Manifiestos y hashes validos"
    exit 0
fi
[[ "$#" == 0 ]] || die "Uso: $0 [--check]"

mapfile -t models < <(jq -r '.models | keys[]' "$lock")
mkdir -p "$models_dir/blobs" "$(dirname "$output")"
for model in "${models[@]}"; do
    name="${model%:*}"
    tag="${model##*:}"
    manifest="$models_dir/manifests/registry.ollama.ai/library/$name/$tag"
    mkdir -p "$(dirname "$manifest")"
    jq --arg model "$model" '.models[$model]' "$lock" > "$manifest.tmp"
    while IFS=$'\t' read -r digest size; do
        blob="$models_dir/blobs/${digest/:/-}"
        expected="${digest#sha256:}"
        if [[ -f "$blob" ]] && printf '%s  %s\n' "$expected" "$blob" | sha256sum --check --status; then
            continue
        fi
        info "Descargando $model: $digest ($size bytes)"
        curl --fail --location --retry 3 --connect-timeout 30 --continue-at - \
            --output "$blob.part" "https://registry.ollama.ai/v2/library/$name/blobs/$digest"
        [[ "$(stat -c %s "$blob.part")" == "$size" ]] || die "Tamano incorrecto: $digest"
        printf '%s  %s\n' "$expected" "$blob.part" | sha256sum --check --status || die "SHA256 incorrecto: $digest"
        mv "$blob.part" "$blob"
    done < <(jq -r '([.config] + .layers)[] | [.digest, .size] | @tsv' "$manifest.tmp")
    mv "$manifest.tmp" "$manifest"
done
python3 "$REPO_ROOT/tools/export_models.py" "${models[@]}" -d "$models_dir" -o "$output.tmp"
mv "$output.tmp" "$output"
sha256sum "$output"