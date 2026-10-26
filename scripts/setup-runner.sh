#!/usr/bin/env bash
set -euo pipefail
set +x
source "$(dirname "$0")/common.sh"

runner_dir="$HOME/.local/share/edgeai-runner"
repository="${EDGEAI_GITHUB_REPOSITORY:-DlynchR/Proyecto-2-Taller-de-Embebidos}"
[[ "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "Repositorio GitHub no valido"
if [[ ! -f "$runner_dir/.runner" ]]; then
    if command -v gh > /dev/null 2>&1 && gh auth status > /dev/null 2>&1; then
        registration_token="$(gh api --method POST "repos/$repository/actions/runners/registration-token" --jq .token)" \
            || die "La cuenta de gh necesita permiso de administracion para registrar el runner"
    else
        credentials="$(printf 'protocol=https\nhost=github.com\n\n' | GIT_TERMINAL_PROMPT=0 git credential fill)" \
            || die "Inicie sesion en GitHub desde VS Code o ejecute gh auth login --web"
        github_token="$(printf '%s\n' "$credentials" | sed -n 's/^password=//p')"
        [[ -n "$github_token" ]] || die "No se encontro autenticacion de GitHub"
        registration_token="$(printf 'header = "Authorization: Bearer %s"\n' "$github_token" | \
            curl --fail --silent --show-error --config - --request POST \
            "https://api.github.com/repos/$repository/actions/runners/registration-token" | jq -er .token)" \
            || die "La cuenta de GitHub necesita permiso de administracion para registrar el runner"
        unset credentials github_token
    fi
    [[ -n "$registration_token" && "$registration_token" != null ]] || die "GitHub no devolvio un token de registro"
fi
version=2.338.1
checksum=08e9ccb3604d2462c24b5e33604dc30810296ca15cc65f23cffd4317eb144c37
archive="$HOME/.cache/edgeai/actions-runner-linux-x64-$version.tar.gz"
mkdir -p "$runner_dir" "$(dirname "$archive")"
if [[ ! -x "$runner_dir/config.sh" ]]; then
    curl --fail --location --retry 3 --output "$archive" \
        "https://github.com/actions/runner/releases/download/v$version/actions-runner-linux-x64-$version.tar.gz"
    printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check --status
    tar -xzf "$archive" -C "$runner_dir"
fi
cd "$runner_dir"
if [[ ! -f .runner ]]; then
    ./config.sh --unattended \
        --url "https://github.com/$repository" \
        --token "$registration_token" --name "edgeai-$(hostname)" \
        --labels edgeai-yocto --work _work
    unset registration_token
fi
unit_dir="$HOME/.config/systemd/user"
mkdir -p "$unit_dir"
printf '%s\n' '[Unit]' 'Description=GitHub Actions runner EdgeAI' \
    '[Service]' "WorkingDirectory=$runner_dir" "ExecStart=$runner_dir/run.sh" \
    "Environment=EDGEAI_CACHE_DIR=$CACHE_DIR" 'Restart=on-failure' 'RestartSec=10' \
    '[Install]' 'WantedBy=default.target' > "$unit_dir/edgeai-runner.service"
systemctl --user daemon-reload
systemctl --user enable --now edgeai-runner.service
info "Runner iniciado. Mantenga la sesion del usuario abierta y el equipo encendido."